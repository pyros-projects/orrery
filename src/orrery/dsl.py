"""The orrery prompt DSL: seeded expansion that records every pick.

    $hero = __animal__
    $hero in a {misty|frozen:3} forest, {1-2$$__style__}, __animal[myth,!bird]__, {0.4-0.9}
    > moody, cinematic
    : x8 seed=100 w1216 h832 unique=$hero
    : grid __style__ × {dawn|noon}

Every expansion returns the text *and* the picks that produced it. Pick keys
(`__animal__=fox`, `{misty|frozen}=misty`) are what learned weights attach to.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from orrery.library import Library
from orrery.loras import long_form
from orrery.rng import Rng, weighted_pick
from orrery.sweep import concrete as sweep_tag
from orrery.sweep import tags as sweep_tags

_BRACE = re.compile(r"\{([^{}]*)\}")
FIX = "\x1f"  # FIX n FIX inside a library or a brace: the draw lands on option n (grids, unique=; see orrery.batch)
# __name[tags]:N__(directions): N = at least N entries; (directions) guide the model that writes the
# library and never reach the prompt. [tags]: `myth` · `myth,!bird` (all, none of) · `water|deep_sea` (either).
_LIB = re.compile(r"__(\w+(?:/\w+)*)(?:\[([\w,|!-]+)\])?((?:#[\w-]+:\$?[\w.-]+)*)(?::(\d+))?(?:\x1f(\d+)\x1f)?__"
                  r"(?:\(([^()]*)\))?")
_VAR = re.compile(r"\$([A-Za-z_]\w*)(?:~(\d+))?(?:\.([A-Za-z_][\w-]*))?")  # $x, $x~N (N clips ago), $x.field
# `$w.kind=rain,snow`, `$w!=x`: a condition on a binding's text or on a property of its pick
_COND = r"\$([A-Za-z_]\w*)(?:\.([A-Za-z_][\w-]*))?\s*(!=|=)\s*([\w-]+(?:\s*,\s*[\w-]+)*)"
_GUARD = re.compile(rf"^\?\s*{_COND}\s*:\s*(.*)$", re.DOTALL)  # ? cond: a line kept only when it holds
_IF = re.compile(rf"^\?\s*{_COND}\s*:(.*)$", re.DOTALL)  # {? cond: then|else}
_BINDING = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$")
_BINDING_LINE = re.compile(r"^(\s*)\$([A-Za-z_]\w*)(\s*=\s*)(.+)$")
_MULTI = re.compile(r"^(\d+)(?:-(\d+))?\$\$(.+)$")
_WEIGHTED = re.compile(r"^(.*?):(\d+(?:\.\d+)?)$")
_DP_WEIGHT = re.compile(r"^\s*(\d+(?:\.\d+)?)::(.*)$", re.DOTALL)  # Dynamic Prompts: {3::red|1::blue}
_LIB_ONLY = re.compile(r"^__(\w+(?:/\w+)*)(?:\[([\w,|!-]+)\])?((?:#[\w-]+:\$?[\w.-]+)*)(?::\d+)?__(?:\([^()]*\))?$")
_NUMBER = r"-?\d+(?:\.\d+)?"
_RANGE = re.compile(rf"\s*({_NUMBER})\s*-\s*({_NUMBER})\s*")  # {0.4-0.9}, {2-6}: a number rolled in between
_LORA_PARTS = re.compile(r"<lora:([^:<>]+):([^:<>]+)(?::([^:<>]+))?>")
BINS = 10  # a range finer than this learns per tenth of it (0.40–0.44), not per value
_PROP = re.compile(r"#([\w-]+):(\$?[\w.-]+)")  # a value may be $var or $var.field
_ARTICLE = re.compile(r"(?:A|An|The) ")
_LORA_TAG = re.compile(r"<lora:[^<>]*>")  # opaque: LoRA file names may contain __
_HIDDEN = re.compile("\x00(\\d+)\x00")
_AN_PREFIXES = ("hour", "honest", "honor", "honour", "heir")
_A_PREFIXES = ("uni", "use", "usu", "eu", "one ", "once")


def _wants_an(word: str) -> bool:
    w = word.lower()
    if w.startswith(_AN_PREFIXES):
        return True
    return w[:1] in "aeiou" and not w.startswith(_A_PREFIXES)


class MissingLibrary(KeyError):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name

    def __str__(self) -> str:
        return f"library __{self.name}__ does not exist (create it: orrery lib gen {self.name})"


@dataclass(frozen=True)
class Pick:
    label: str
    value: str
    keys: tuple[str, ...] = ()


@dataclass
class Params:
    count: int | None = None
    seed: int | None = None
    width: int | None = None
    height: int | None = None
    grid: str | None = None  # `: grid __style__ × {dawn|noon}`, the axes as written (orrery.batch)
    unique: list[str] = field(default_factory=list)  # `unique=__creature__`, `unique=$hero`


@dataclass
class Expansion:
    seed: int
    text: str
    picks: list[Pick]
    params: Params = field(default_factory=Params)
    enhance: str | None = None
    cell: int | None = None  # the run of a `: grid`
    warnings: list[str] = field(default_factory=list)  # what rolled, but not as written (a sweep in an entry)


@dataclass
class _Parsed:
    bindings: list[tuple[str, str]]
    body: list[str]
    enhance: str | None
    params: Params


_COMMENT = re.compile(r"^[ \t]*#.*(?:\r?\n|$)", re.MULTILINE)


def strip_comments(template: str) -> str:
    """A line whose first character (after indentation) is `#` is a comment, as in wildcard files.
    `#key:value` inside `__lib__` never starts a line, so filters are untouched."""
    return _COMMENT.sub("", template)


def parse(template: str) -> _Parsed:
    parsed = _Parsed([], [], None, Params())
    for raw in strip_comments(template).splitlines():
        line = raw.strip()
        if not line:
            continue
        if m := _BINDING.match(line):
            parsed.bindings.append((m.group(1), m.group(2)))
        elif line.startswith(">"):
            parsed.enhance = line[1:].strip()
        elif line.startswith(":"):
            parsed.params = _parse_params(line[1:], parsed.params)  # several `:` lines add up
        else:
            parsed.body.append(line)
    return parsed


def wanted_libraries(template: str) -> dict[str, int]:
    """Every library a template uses, with the entries it asks for (`__name:N__`, else 0)."""
    wanted: dict[str, int] = {}
    for m in _LIB.finditer(_LORA_TAG.sub("", template)):
        wanted[m.group(1)] = max(wanted.get(m.group(1), 0), int(m.group(4) or 0))
    return wanted


def library_directions(template: str) -> dict[str, str]:
    """What the template tells the model about each library it may write: `__name__(directions)`."""
    return {m.group(1): m.group(6).strip() for m in _LIB.finditer(_LORA_TAG.sub("", template)) if m.group(6)}


def without_directions(text: str) -> str:
    """The text with every `__name__(directions)` cut back to `__name__`."""
    return _LIB.sub(lambda m: m.group(0).split("(", 1)[0] if m.group(6) is not None else m.group(0), text)


def bindings(template: str) -> list[tuple[str, str]]:
    """A template's bindings, in order: its dials, with their default expressions."""
    return parse(template).bindings


def override(template: str, values: Mapping[str, str]) -> str:
    """Turn dials: each named binding (`hero` or `$hero`) gets a new expression, which may itself
    use the DSL. Empty values keep the default; unknown names are ignored."""
    wanted = {k.strip().lstrip("$"): v.strip() for k, v in values.items() if v and v.strip()}

    def swap(line: str) -> str:
        m = _BINDING_LINE.match(line)
        return f"{m.group(1)}${m.group(2)}{m.group(3)}{wanted[m.group(2)]}" if m and m.group(2) in wanted else line

    return "\n".join(swap(line) for line in template.split("\n"))


def _parse_params(text: str, before: Params | None = None) -> Params:
    """`x8 seed=100 w1216 h832 unique=X` and `grid A × B` (the rest of its line), on top of `before`."""
    before = before or Params()
    grid = None
    if m := re.search(r"(?:^|\s)grid\b(.*)$", text):
        text, grid = text[:m.start()], m.group(1).strip()

    def grab(pattern: str, old: int | None) -> int | None:
        m = re.search(pattern, text)
        return int(m.group(1)) if m else old

    return Params(grab(r"\bx(\d+)", before.count), grab(r"\bseed=(\d+)", before.seed), grab(r"\bw(\d+)", before.width),
                  grab(r"\bh(\d+)", before.height), grid or before.grid,
                  before.unique + re.findall(r"\bunique=(\S+)", text))


def split_options(inner: str, most: int = -1) -> list[str]:
    """A brace's options: split at `|`, but not inside `[...]` (`{__a[x|y]__|b}` has two)."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(inner):
        depth += (ch == "[") - (ch == "]" and depth > 0)
        if ch == "|" and depth == 0 and most != len(out):
            out.append(inner[start:i])
            start = i + 1
    return [*out, inner[start:]]


def tags_match(spec: str | None, tags) -> bool:
    """`[myth]` · `[myth,!bird]`: every comma-separated term holds · `[water|deep_sea]`: either does."""
    if not spec:
        return True
    have = set(tags)
    for term in spec.split(","):
        alts = [a for a in term.split("|") if a]
        if alts and not any((a[1:] not in have) if a.startswith("!") else (a in have) for a in alts):
            return False
    return True


def _places(number: str) -> int:
    return len(number.split(".", 1)[1]) if "." in number else 0


def _mid_line(value: str, m: re.Match) -> str:
    """A picked sentence that the sentence around it goes on after loses its final period, so
    `doing __pose__ at __place__` stays one sentence. It stays before a capital (a new sentence),
    another pick (unknown), at the end of the line, and as an ellipsis."""
    rest = m.string[m.end():].split("\n", 1)[0].lstrip()
    goes_on = bool(rest) and (rest[0].islower() or rest[0].isdigit() or rest[0] in ".,;:)!?")
    if goes_on and value.endswith(".") and not value.endswith(".."):
        value = value[:-1]
    before = m.string[:m.start()].rsplit("\n", 1)[-1].rstrip()
    if before and (before[-1].islower() or before[-1] == ",") and _ARTICLE.match(value):
        value = value[0].lower() + value[1:]  # "at A wooded course" reads "at a wooded course"
    return value


def _label(name: str, tag: str | None, props: str | None) -> str:
    return f"__{name}{f'[{tag}]' if tag else ''}{props or ''}__"


class Expander:
    """Expands DSL expressions against libraries, one seeded draw sequence per instance."""

    def __init__(self, seed: int, libraries: Mapping[str, Library],
                 weights: Mapping[str, float] | None = None) -> None:
        self.rng = Rng(seed)
        self.libraries = libraries
        self.weights = weights or {}
        self.picks: list[Pick] = []
        self.vars: dict[str, str] = {}
        # (name, clips back) → that clip's value; set by reels. Without it, $x~N is $x.
        self.history: Callable[[str, int], str | None] | None = None
        self.var_props: dict[str, dict[str, str]] = {}  # a binding → the properties of the picks it rolled
        self.var_fields: dict[str, dict[str, str]] = {}  # the same, each rolled once as a template ($x.field reads it)
        # (name, clips back) → that clip's fields of the binding, as it showed them; set by reels, for $x~N.field
        self.history_props: Callable[[str, int], dict[str, str]] | None = None
        self._props_seen: dict[str, str] = {}
        self._within: list[str] = []  # the libraries whose entry is being expanded, outermost first
        self._where: list[tuple[str, str]] = []  # (what is being expanded, the grid that would run all of it)
        self.warnings: list[str] = []  # a reel's expanders share their world's list

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def learned(self, key: str) -> float:
        return float(self.weights.get(key, 1.0))

    def bind(self, name: str, expr: str) -> str:
        self._props_seen = {}
        self.vars[name] = self.expr(expr, label_prefix=f"${name} ← ")
        self.var_props[name] = props = self._props_seen
        self._props_seen = {}  # a field's own picks are not the binding's
        self.var_fields[name] = {k: self._field(name, k, v) for k, v in props.items()}
        return self.vars[name]

    def _field(self, name: str, field: str, raw: str) -> str:
        """A property as $name.field shows it: a template like an entry, rolled once when it is bound, so
        every read shows the same. Filters and conditions read the property as written."""
        value = long_form(raw) if "@" in raw else raw
        if "__" not in value and "{" not in value and "$" not in value and "<lora:" not in value:
            return value
        self._where.append((f"${name}.{field}", f"${name}"))
        try:
            return " ".join(self.expr(value, label_prefix=f"${name}.{field} ← ").split())
        except MissingLibrary as err:
            raise ValueError(f"Library __{err.name}__ is missing; ${name}.{field} uses it.") from err
        finally:
            self._where.pop()

    def holds(self, name: str, field: str | None, op: str, values: str) -> bool:
        actual = (self.var_props.get(name, {}).get(field) if field else self.vars.get(name)) or ""
        hit = actual.strip().casefold() in {v.strip().casefold() for v in values.split(",")}
        return hit if op == "=" else not hit

    def guarded(self, line: str) -> str | None:
        """A `? cond: rest` line: its rest when the condition holds, else None. Other lines as they are."""
        if not (m := _GUARD.match(line.strip())):
            return line
        return m.group(5) if self.holds(*m.group(1, 2, 3, 4)) else None

    def expr(self, text: str, label_prefix: str = "") -> str:
        if "\n" not in text and (text := self.guarded(text)) is None:
            return ""
        tags: list[str] = []
        text = _LORA_TAG.sub(lambda m: tags.append(self._lora(m.group(0))) or f"\x00{len(tags) - 1}\x00", text)
        first = len(self.picks)
        text = self._expand(text, label_prefix)
        if not tags:
            return text
        show = lambda s: _HIDDEN.sub(lambda m: tags[int(m.group(1))], s)
        self.picks[first:] = [Pick(show(p.label), show(p.value), tuple(show(k) for k in p.keys))
                              for p in self.picks[first:]]
        return show(text)

    def _expand(self, text: str, label_prefix: str) -> str:
        for _ in range(200):
            m = _BRACE.search(text)
            if not m:
                break
            text = text[: m.start()] + self._brace(m.group(1)) + text[m.end():]
        text = _LIB.sub(lambda m: _mid_line(self._library(m.group(1), m.group(2), label_prefix, m.group(3),
                                                          None if m.group(5) is None else int(m.group(5))), m), text)
        text = _VAR.sub(lambda m: _mid_line(self._var(m), m), text)
        return self._articles(text)

    def _var(self, m: re.Match) -> str:
        name, back, field = m.group(1), m.group(2), m.group(3)
        if field:  # a property of the pick behind the binding (N clips back with ~N); empty when it has none
            if back is not None:
                return (self.history_props(name, int(back)) if self.history_props else self.var_fields.get(name, {})).get(field, "")
            return self.var_fields.get(name, {}).get(field, "")
        value = self.history(name, int(back)) if back is not None and self.history else None
        if value is None:
            value = self.vars.get(name)
        return m.group(0) if value is None else value

    def _articles(self, text: str) -> str:
        """Make a/an agree with picked values ('a axolotl' → 'an axolotl')."""
        values = {p.value for p in self.picks} | set(self.vars.values())
        for v in sorted((v for v in values if v), key=len, reverse=True):
            text = re.sub(r"\b([Aa])n? (?=" + re.escape(v) + r"\b)",
                          lambda m, v=v: m.group(1) + ("n " if _wants_an(v) else " "), text)
        return text

    def _pool(self, name: str, tag: str | None, props: str = "") -> tuple[str, list[tuple[str, float]]]:
        """The entries a pick draws from: those with the tag and every `#key:value` property (any case)."""
        if name not in self.libraries:
            raise MissingLibrary(name)
        family = f"__{name}__"
        wanted = [(k, self._resolve(v).casefold()) for k, v in _PROP.findall(props or "")]
        entries = [e for e in self.libraries[name].entries if tags_match(tag, e.tags)
                   and all((e.prop(k) or "").casefold() == v for k, v in wanted)]
        if not entries:
            raise ValueError(f"{_label(name, tag, props)} matches no entry")
        return family, [(e.value, e.weight * self.learned(f"{family}={e.value}"), e.props) for e in entries]

    def _resolve(self, value: str) -> str:
        """A filter value: as written, or `$var` / `$var.field` from what was rolled before."""
        if not value.startswith("$"):
            return value
        name, _, field = value[1:].partition(".")
        return (self.var_props.get(name, {}).get(field) if field else self.vars.get(name)) or ""

    def _library(self, name: str, tag: str | None, label_prefix: str, props: str = "", fixed: int | None = None) -> str:
        family, pool = self._pool(name, tag, props)
        i = weighted_pick([w for _, w, _ in pool], self.rng)  # a fixed draw rolls too: the picks after it stay put
        if fixed is not None:
            if fixed >= len(pool):
                raise ValueError(f"{_label(name, tag, props)} has {len(pool)} entries now, fewer than the grid counted")
            i = fixed
        value, _, entry_props = pool[i]
        label = label_prefix + _label(name, tag, props)
        self.picks.append(Pick(label, value, (f"{family}={value}",)))
        text = self._nested(name, value, label_prefix)
        self._props_seen.update(entry_props)  # after the nested picks: the outer library's fields win
        return text

    def _nested(self, name: str, value: str, label_prefix: str) -> str:
        """An entry is a template itself, as in Dynamic Prompts: its libraries, braces and $vars expand,
        its LoRA tags as in the template (`@style(0.8)`, a strength range)."""
        if "@" in value:
            value = long_form(value)
        if "__" not in value and "{" not in value and "$" not in value and "<lora:" not in value:
            return value
        if name in self._within:
            raise ValueError("A library comes back to itself: " + " → ".join([*self._within, name]))
        self._within.append(name)
        self._where.append((f"an entry of __{name}__", f"__{name}__"))
        try:
            return " ".join(self.expr(value, label_prefix).split())  # `{|red} perm` leaves no stray space
        except MissingLibrary as err:
            raise ValueError(f"Library __{err.name}__ is missing; an entry of __{name}__ uses it.") from err
        finally:
            self._within.pop()
            self._where.pop()

    def _brace(self, inner: str) -> str:
        fixed = None
        if inner.startswith(FIX):
            n, _, inner = inner[1:].partition(FIX)
            fixed = int(n)
        if m := _IF.match(inner.strip()):
            then, otherwise = (split_options(m.group(5), 1) + [""])[:2]
            return (then if self.holds(*m.group(1, 2, 3, 4)) else otherwise).strip()
        if m := _MULTI.match(inner):
            return self._multi(int(m.group(1)), int(m.group(2) or m.group(1)), m.group(3).strip())
        if m := _RANGE.fullmatch(inner):
            family = "{" + inner.strip() + "}"
            value, bin_ = self._number(m.group(1), m.group(2), family)
            self.picks.append(Pick(family, value, (f"{family}={bin_}",)))
            return value
        raws = split_options(inner)
        keep = len(raws) > 1 and any(not raw.strip() for raw in raws)  # `{|red }car`: an optional word
        options = []
        for raw in raws:
            wm, dp = _WEIGHTED.match(raw), _DP_WEIGHT.match(raw)
            value, weight = (dp.group(2), float(dp.group(1))) if dp else \
                (wm.group(1), float(wm.group(2))) if wm else (raw, 1.0)
            options.append((value if keep else value.strip(), weight))
        # Labels and learned keys leave `(directions)` out: editing them must not rename the choice.
        family = without_directions("{" + "|".join(v for v, _ in options) + "}")
        weights = [w * self.learned(f"{family}={without_directions(v)}") for v, w in options]
        i = weighted_pick(weights, self.rng)  # a fixed draw rolls too: the picks after it stay put
        value = options[i if fixed is None else fixed][0]
        shown = without_directions(value)
        self.picks.append(Pick(family, shown, (f"{family}={shown}",)))
        return value

    def _multi(self, lo: int, hi: int, source: str) -> str:
        n = lo + int(self.rng.random() * (hi - lo + 1))
        if lm := _LIB_ONLY.match(source):
            family, pool3 = self._pool(lm.group(1), lm.group(2), lm.group(3))
            pool = [(v, w) for v, w, _ in pool3]
        else:
            options = [(dp.group(2).strip(), float(dp.group(1))) if (dp := _DP_WEIGHT.match(v)) else (v.strip(), 1.0)
                       for v in split_options(source)]
            family = without_directions("{" + "|".join(v for v, _ in options) + "}")
            pool = [(v, w * self.learned(f"{family}={without_directions(v)}")) for v, w in options]
        chosen: list[str] = []
        while pool and len(chosen) < n:
            i = weighted_pick([w for _, w in pool], self.rng)
            chosen.append(pool.pop(i)[0])
        span = str(lo) if lo == hi else f"{lo}–{hi}"
        self.picks.append(Pick(f"{family} ×{span}", without_directions(", ".join(chosen)),
                               tuple(f"{family}={without_directions(v)}" for v in chosen)))
        return ", ".join(chosen)


    def _number(self, lo: str, hi: str, family: str) -> tuple[str, str]:
        """A number between `lo` and `hi` (both in), at their decimals: (it, the bin it learns in).
        The bins are weighted by what was learned, the number within its bin is even."""
        places = max(_places(lo), _places(hi))
        scale = 10 ** places
        a, b = round(float(lo) * scale), round(float(hi) * scale)
        if b < a:
            raise ValueError(f"{family} runs backwards; write {{{hi}-{lo}}}")
        count = b - a + 1
        bins = min(count, BINS)
        edges = [a + count * k // bins for k in range(bins + 1)]
        show = lambda v: f"{v / scale:.{places}f}"
        labels = [show(edges[k]) if edges[k + 1] - edges[k] == 1 else f"{show(edges[k])}–{show(edges[k + 1] - 1)}"
                  for k in range(bins)]
        k = weighted_pick([self.learned(f"{family}={label}") for label in labels], self.rng)
        return show(edges[k] + int(self.rng.random() * (edges[k + 1] - edges[k]))), labels[k]

    def _lora(self, tag: str) -> str:
        """`<lora:style:0.4-0.9>` (and `:0.2-0.5` for CLIP): a strength rolled per run and recorded as a
        pick of `<lora:style>`; any other tag as it is."""
        if self._where and (swept := sweep_tags(tag)):  # a sweep runs only where the template writes it
            first = swept[0].variants()[0]
            where, grid = self._where[-1]
            shown = sweep_tag(swept[0], first) if first[0] or first[1] else ""
            self.warn(f"{tag} in {where} is a sweep, and a sweep runs only where the template writes it: it takes "
                      f"{shown or 'it off'} there. To run every entry, write : grid {grid}.")
            return shown
        m = _LORA_PARTS.fullmatch(tag)
        if not m or not any(part and _RANGE.fullmatch(part) for part in (m.group(2), m.group(3))):
            return tag
        label, out, keys = f"<lora:{m.group(1).strip()}>", [], []
        for which, part in (("", m.group(2)), (" clip", m.group(3))):
            if part is None:
                continue
            if r := _RANGE.fullmatch(part):
                value, bin_ = self._number(r.group(1), r.group(2), label + which)
                keys.append(f"{label}{which}={bin_}")
                out.append(value)
            else:
                out.append(part.strip())
        self.picks.append(Pick(label, "/".join(out), tuple(keys)))
        return f"<lora:{m.group(1)}:{':'.join(out)}>"


def expand(template: str, seed: int, libraries: Mapping[str, Library],
           weights: Mapping[str, float] | None = None, cell: int | None = None) -> Expansion:
    """`cell`: the run of the template's `: grid` (orrery.batch); None rolls its axes like any pick."""
    from orrery.batch import prepare

    template = prepare(template, seed, libraries, cell)
    parsed = parse(template)
    ex = Expander(seed, libraries, weights)
    for name, expr in parsed.bindings:
        ex.bind(name, expr)
    text = ex.expr(" ".join(line for raw in parsed.body if (line := ex.guarded(raw)) is not None))
    if parsed.enhance:
        ex.picks.append(Pick("> enhance", parsed.enhance))
    return Expansion(seed, text, ex.picks, parsed.params, parsed.enhance, cell, ex.warnings)


def expand_batch(template: str, seed: int, count: int, libraries: Mapping[str, Library],
                 weights: Mapping[str, float] | None = None) -> list[Expansion]:
    """`count` seeds from `seed` on; with a `: grid`, every cell at each of them."""
    from orrery.batch import axes, cells
    from orrery.loras import long_form

    source = long_form(template)
    found = axes(source, libraries) if parse(source).params.grid is not None else []
    grid = range(cells(found)) if found else [None]
    return [expand(template, seed + i, libraries, weights, cell=c) for i in range(count) for c in grid]
