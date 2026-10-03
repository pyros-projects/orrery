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
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from orrery.library import Entry, Library
from orrery.loras import long_form
from orrery.rng import Rng, weighted_pick
from orrery.sweep import concrete as sweep_tag
from orrery.sweep import tags as sweep_tags

_BRACE = re.compile(r"\{([^{}]*)\}")
FIX = "\x1f"  # FIX n FIX inside a library or a brace: the draw lands on option n (grids, unique=; see orrery.batch)
# FIX p<hex> FIX inside a library: a dial set to this text (hex, so nothing in it rolls first); the entry with
# that value is picked with its tags and properties, and text that is no entry rolls as written (see override)
# __name[tags]:N__(directions): N = at least N entries; (directions) guide the model that writes the
# library and never reach the prompt. [tags]: `myth` · `myth,!bird` (all, none of) · `water|deep_sea` (either).
_LIB = re.compile(r"(?<!\\)__([\w*]+(?:/[\w*]+)*)(?:\[([^\[\]\n]+)\])?((?:#[\w-]+:\$?[\w.-]+)*)(?::(\d+))?(?:\x1f(\d+|p[0-9a-f]*)\x1f)?__"
                  r"(?:\(([^()]*)\))?")
# $x, $x[-N] (N clips ago, or the earlier $x~N), $x["the stairs"] (the last time that scene played), $x.field
_VAR = re.compile(r'\$([A-Za-z_]\w*)(?:~(\d+)|\[-(\d+)\]|\["([^"\]\n]+)"\])?(?:\.([A-Za-z_][\w-]*))?')
# `$w.kind=rain,snow`, `$w!=x`: a condition on a binding's text or on a property of its pick
_COND = r"\$([A-Za-z_]\w*)(?:\.([A-Za-z_][\w-]*))?\s*(!=|=)\s*([\w-]+(?:\s*,\s*[\w-]+)*)"
_GUARD = re.compile(rf"^\?\s*{_COND}\s*:\s*(.*)$", re.DOTALL)  # ? cond: a line kept only when it holds
_IF = re.compile(rf"^\?\s*{_COND}\s*:(.*)$", re.DOTALL)  # {? cond: then|else}
# the same with brackets: `? $w[kind=rain|snow]: …`, `{? $c[myth, !bird]: then|else}`
_PRED = r"\$([A-Za-z_]\w*)\[([^\[\]]*)\]"
_GUARD_PRED = re.compile(rf"^\?\s*{_PRED}\s*:\s*(.*)$", re.DOTALL)
_IF_PRED = re.compile(rf"^\?\s*{_PRED}\s*:(.*)$", re.DOTALL)
# the words for them: `IF $x is victory: …`, `IF $w.kind is not rain, snow: …`, `IF $c[myth, !bird]: …`
_IS = re.compile(r"^IF\s+\$([A-Za-z_]\w*)(?:\.([A-Za-z_][\w-]*))?\s+is\s+(not\s+)?([\w-]+(?:\s*,\s*[\w-]+)*)\s*:",
                 re.IGNORECASE)
_IF_WORD = re.compile(r"^IF\s+(?=\$)", re.IGNORECASE)
_BINDING = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$")
# EXPORT: what the run keeps beside its prompt: `EXPORT: mood = __moods__`, `EXPORT: $who, $job`, or
# `EXPORT:` and indented `name = expression` / `$name` lines under it
_EXPORT = re.compile(r"^EXPORT:\s*(.*)$")
_EXPORT_ONE = re.compile(r"^(?:\$([A-Za-z_]\w*)|([A-Za-z_]\w*)\s*=\s*(.+))$")
_BINDING_LINE = re.compile(r"^(\s*)\$([A-Za-z_]\w*)(\s*=\s*)(.+)$")
_MULTI = re.compile(r"^(\d+)(?:-(\d+))?\$\$(?:(.*?)\$\$)?(.+)$")  # {2$$ and $$a|b|c}: Dynamic Prompts' joiner
_ESCAPE = re.compile(r"\\([{}|$_@#\[\]\\<>])")  # \{ \__ \$ …: the character as written
_ESCAPED = re.compile("\ue000(\\d+)\ue001")
_WEIGHTED = re.compile(r"^(.*?):(\d+(?:\.\d+)?)$")
_DP_WEIGHT = re.compile(r"^\s*(\d+(?:\.\d+)?)::(.*)$", re.DOTALL)  # Dynamic Prompts: {3::red|1::blue}
_LIB_ONLY = re.compile(r"^__([\w*]+(?:/[\w*]+)*)(?:\[([^\[\]\n]+)\])?((?:#[\w-]+:\$?[\w.-]+)*)(?::\d+)?__(?:\([^()]*\))?$")
_NUMBER = r"-?\d+(?:\.\d+)?"
_RANGE = re.compile(rf"\s*({_NUMBER})\s*-\s*({_NUMBER})\s*")  # {0.4-0.9}, {2-6}: a number rolled in between
_LORA_PARTS = re.compile(r"<lora:([^:<>]+):([^:<>]+)(?::([^:<>]+))?>")
BINS = 10  # a range finer than this learns per tenth of it (0.40–0.44), not per value
RNG = 2  # the dice: 2 gives every pick a stream of its own, 1 is the single stream of old (`@rng 1`)
# one per line: @grid A × B · @unique $hero · @size 832x1216 · @seed 100 · @batch 8 · @rng 1 (the `:` line's aliases)
_DIRECTIVE = re.compile(r"^@(grid|unique|size|seed|batch|rng)\b\s*(.*)$")
DIRECTIVES = ("grid", "unique", "size", "seed", "batch", "rng")
_LOOKS_LIB = re.compile(r"__[^\s_\x00\ue000][^\s]*?__")  # what is left over looking like a wildcard
_LIB_BLOCK = re.compile(r"^@lib\s+(\w+(?:/\w+)*)\s*$")
_CHANCE = re.compile(r"\s*(\d+(?:\.\d+)?)%\s+(.*\S)\s*", re.DOTALL)  # {30% in the rain}
MAX_CHOICES = 2000  # {…} rolled in one expression: past it the braces keep coming back ({1$$__a__} in __a__)
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


def question(text: str) -> str:
    """`IF $x is victory: …` as the `? $x[victory]: …` it means: `is a, b` either of them, `is not a, b`
    none; `$x.field is …` compares the field; `IF` before any other condition is `?`. Other text as is."""
    line = text.lstrip()
    if m := _IS.match(line):
        name, field, negated, values = m.groups()
        words = [v.strip() for v in values.split(",")]
        if field:
            cond = f"${name}.{field}{'!=' if negated else '='}{','.join(words)}"
        else:
            cond = f"${name}[{', '.join('!' + w for w in words) if negated else '|'.join(words)}]"
        return f"? {cond}:{line[m.end():]}"
    if m := _IF_WORD.match(line):
        return "? " + line[m.end():]
    return text


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
    rng: int | None = None  # `@rng 1`: the dice a template was made with (None: RNG)
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
    exports: dict[str, object] = field(default_factory=dict)  # what EXPORT: rolled: text, {value, fields} or a list


@dataclass
class _Parsed:
    bindings: list[tuple[str, str]]
    body: list[str]
    enhance: str | None
    params: Params
    exports: list[tuple[str, str]] = field(default_factory=list)  # (name, expression); `$who` exports a binding


_COMMENT = re.compile(r"^[ \t]*#.*(?:\r?\n|$)", re.MULTILINE)


def strip_comments(template: str) -> str:
    """A line whose first character (after indentation) is `#` is a comment, as in wildcard files.
    `#key:value` inside `__lib__` never starts a line, so filters are untouched."""
    return _COMMENT.sub("", template)


def _exports(spec: str) -> list[tuple[str, str]]:
    """`mood = __moods__` or `$who, $job` as (name, expression) pairs; a binding is ("who", "$who")."""
    if (m := _EXPORT_ONE.match(spec.strip())) and m.group(2):
        return [(m.group(2), m.group(3).strip())]
    if all(re.fullmatch(r"\$[A-Za-z_]\w*", part.strip()) for part in spec.split(",")):
        return [(part.strip()[1:], part.strip()) for part in spec.split(",")]
    raise ValueError(f"EXPORT: {spec.strip()}: write `name = what it rolls` or `$binding`.")


def strip_exports(template: str) -> str:
    """The template without its EXPORT: lines and blocks (a screenplay reads exports from the gallery)."""
    out, block = [], False
    for raw in template.splitlines():
        if block and raw.strip() and raw[:1] in (" ", "\t"):
            continue
        block = False
        if m := _EXPORT.match(raw.strip()):
            block = not m.group(1).strip()
            continue
        out.append(raw)
    return "\n".join(out)


def parse(template: str) -> _Parsed:
    parsed = _Parsed([], [], None, Params())
    block = False  # in an `EXPORT:` block: its indented lines are exports
    for raw in strip_comments(template).splitlines():
        line = raw.strip()
        if not line:
            continue
        if block and raw[:1] in (" ", "\t"):
            parsed.exports += _exports(line)
            continue
        block = False
        if m := _EXPORT.match(line):
            if m.group(1).strip():
                parsed.exports += _exports(m.group(1))
            else:
                block = True
            continue
        if m := _BINDING.match(line):
            parsed.bindings.append((m.group(1), m.group(2)))
        elif line.startswith(">"):
            parsed.enhance = line[1:].strip()
        elif line.startswith(":"):
            parsed.params = _parse_params(line[1:], parsed.params)  # several `:` lines add up
        elif m := _DIRECTIVE.match(line):
            parsed.params = _directive(m.group(1), m.group(2).strip(), parsed.params)
        else:
            parsed.body.append(line)
    return parsed


def inline_libraries(template: str) -> tuple[str, dict[str, Library]]:
    """The template without its `@lib name` blocks, and those libraries: each indented line under the
    `@lib` line an entry (a template itself, `- ` before it allowed), until a line that is not indented.

        @lib crowd
          a few __animal__s
          a lone __animal__
    """
    out, found, current = [], {}, None
    for raw in template.split("\n"):
        if m := _LIB_BLOCK.match(raw.strip()):
            current = m.group(1)
            found[current] = []
            continue
        if current is not None and (raw[:1] in (" ", "\t") or not raw.strip()):
            entry = raw.strip()
            entry = entry[2:].strip() if entry.startswith("- ") else entry
            if entry and not entry.startswith("#"):
                found[current].append(entry)
            continue
        current = None
        out.append(raw)
    for name, values in found.items():
        if not values:
            raise ValueError(f"@lib {name} has no entries: write them on indented lines under it.")
    return "\n".join(out), {name: Library(name, [Entry(v) for v in values]) for name, values in found.items()}


def with_inline(template: str, libraries: Mapping[str, Library]) -> tuple[str, Mapping[str, Library]]:
    """The template's own libraries over the home's (a name in both: the template's)."""
    if "@lib" not in template:
        return template, libraries
    text, inline = inline_libraries(template)
    return text, {**libraries, **inline}


def wanted_libraries(template: str) -> dict[str, int]:
    """Every library a template uses, with the entries it asks for (`__name:N__`, else 0); its own
    `@lib` libraries are not wanted from anywhere else."""
    wanted: dict[str, int] = {}
    for m in _LIB.finditer(_LORA_TAG.sub("", template)):
        if "*" not in m.group(1):  # a glob names libraries that are there
            wanted[m.group(1)] = max(wanted.get(m.group(1), 0), int(m.group(4) or 0))
    if "@lib" in template:
        for name in inline_libraries(template)[1]:
            wanted.pop(name, None)
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
    use the DSL. Empty values keep the default; unknown names are ignored. A binding to one library
    keeps it: the dial's text picks the entry with that value, with its tags and properties (so
    `$look.family` still reads), and text that is no entry rolls as written."""
    wanted = {k.strip().lstrip("$"): v.strip() for k, v in values.items() if v and v.strip()}

    def swap(line: str) -> str:
        m = _BINDING_LINE.match(line)
        if not (m and m.group(2) in wanted):
            return line
        return f"{m.group(1)}${m.group(2)}{m.group(3)}{_pinned(m.group(4).strip(), wanted[m.group(2)])}"

    return "\n".join(swap(line) for line in template.split("\n"))


def _pinned(expr: str, value: str) -> str:
    """`__look__` dialed to `value`: the library with the value in it (FIX p<hex> FIX), or `value` itself
    when `expr` is not one library of its own (a choice, a glob, one already fixed)."""
    m = _LIB.fullmatch(expr)
    if not m or "*" in m.group(1) or m.group(5) is not None:
        return value
    close = (m.start(6) - 1 if m.group(6) is not None else len(expr)) - 2
    return f"{expr[:close]}{FIX}p{value.encode().hex()}{FIX}{expr[close:]}"


def _fixed(group: str | None) -> int | str | None:
    """A library's FIX group: a grid's option number, or a dial's text."""
    if group is None:
        return None
    return bytes.fromhex(group[1:]).decode() if group.startswith("p") else int(group)


def _parse_params(text: str, before: Params | None = None) -> Params:
    """`x8 seed=100 w1216 h832 unique=X` and `grid A × B` (the rest of its line), on top of `before`."""
    before = before or Params()
    grid = None
    if m := re.search(r"(?:^|\s)grid\b(.*)$", text):
        text, grid = text[:m.start()], m.group(1).strip()

    def grab(pattern: str, old: int | None) -> int | None:
        m = re.search(pattern, text)
        return int(m.group(1)) if m else old

    return Params(count=grab(r"\bx(\d+)", before.count), seed=grab(r"\bseed=(\d+)", before.seed),
                  width=grab(r"\bw(\d+)", before.width), height=grab(r"\bh(\d+)", before.height),
                  grid=grid or before.grid, rng=before.rng, unique=before.unique + re.findall(r"\bunique=(\S+)", text))


def _directive(name: str, value: str, params: Params) -> Params:
    """An `@name value` line into the params, as its `:` alias would put it."""
    number = re.fullmatch(r"\d+", value)
    if name == "grid":
        params.grid = value
    elif name == "unique":
        params.unique = params.unique + value.split()
    elif name == "size":
        m = re.fullmatch(r"(\d+)\s*[x×*\s]\s*(\d+)", value) or re.fullmatch(r"w(\d+)\s+h(\d+)", value)
        if not m:
            raise ValueError(f"@size {value}: write the width and the height, as in @size 832x1216.")
        params.width, params.height = int(m.group(1)), int(m.group(2))
    elif name == "rng":
        if value not in ("1", "2"):
            raise ValueError(f"@rng {value}: the dice are 1 (one stream, as before 2026-10-02) or 2.")
        params.rng = int(value)
    elif not number:
        raise ValueError(f"@{name} {value}: it takes a number, as in @{name} 8.")
    elif name == "seed":
        params.seed = int(value)
    else:
        params.count = int(value)
    return params


def is_directive(line: str) -> bool:
    return bool(_DIRECTIVE.match(line.strip()))


def glob_names(pattern: str, names) -> list[str]:
    """The library names a glob matches, sorted: `*` within a part of the path (`clothing/*`,
    `scenes/features*`), `**` across folders (`clothing/**`)."""
    rx = re.compile("/".join(".+" if part == "**" else re.escape(part).replace(r"\*", "[^/]*")
                             for part in pattern.split("/")) + "$")
    return sorted(n for n in names if rx.match(n))


def split_options(inner: str, most: int = -1) -> list[str]:
    """A brace's options: split at `|`, but not inside `[...]` (`{__a[x|y]__|b}` has two)."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(inner):
        depth += (ch == "[") - (ch == "]" and depth > 0)
        if ch == "|" and depth == 0 and most != len(out):
            out.append(inner[start:i])
            start = i + 1
    return [*out, inner[start:]]


def matches(spec: str | None, tags, props: Mapping[str, str] | None = None,
            resolve: Callable[[str], str] = lambda v: v) -> bool:
    """One predicate language for library filters and conditions:

        myth                      the tag            !bird            not the tag
        habitat=sea               a property         size!=large      not that value
        myth, !bird               all of them        water|deep_sea   either
        size=small|tiny           a key's values     habitat=$a.habitat   what rolled before

    Properties compare in any case; tags as written."""
    if not spec or not spec.strip():
        return True
    props = props or {}
    for term in spec.split(","):
        key, hit, alts = None, False, [a.strip() for a in term.split("|") if a.strip()]
        for alt in alts:
            neg, body = alt.startswith("!"), alt.lstrip("!").strip()
            if "!=" in body:
                key, _, value = body.partition("!=")
                neg, key = not neg, key.strip()
            elif "=" in body:
                key, _, value = body.partition("=")
                key = key.strip()
            else:
                value = body if key is not None else None  # size=small|tiny: tiny is a size too
            ok = body in tags if value is None else \
                (props.get(key) or "").strip().casefold() == resolve(value.strip()).strip().casefold()
            if ok != neg:
                hit = True
                break
        if alts and not hit:
            return False
    return True


def tags_match(spec: str | None, tags) -> bool:
    return matches(spec, tags)


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
                 weights: Mapping[str, float] | None = None, rng: int | None = None) -> None:
        self.seed, self.dice = seed, rng or RNG
        self.rng = Rng(seed)  # the single stream of `@rng 1`
        self._drawn: dict[str, int] = {}  # a label → how often it was drawn: each draw its own stream
        self.libraries = libraries
        self.weights = weights or {}
        self.picks: list[Pick] = []
        self.vars: dict[str, str] = {}
        # (name, clips back) → that clip's value; set by reels. Without it, $x~N is $x.
        self.history: Callable[[str, int | str], str | None] | None = None
        self.var_props: dict[str, dict[str, str]] = {}  # a binding → the properties of the picks it rolled
        self.var_fields: dict[str, dict[str, str]] = {}  # the same, each rolled once as a template ($x.field reads it)
        self.var_tags: dict[str, set[str]] = {}  # a binding → the tags of the picks it rolled (`? $c[myth]: …`)
        self._tags_seen: set[str] = set()
        # (name, clips back) → that clip's fields of the binding, as it showed them; set by reels, for $x~N.field
        self.history_props: Callable[[str, int | str], dict[str, str]] | None = None
        self._props_seen: dict[str, str] = {}
        self._within: list[str] = []  # the libraries whose entry is being expanded, outermost first
        self._where: list[tuple[str, str]] = []  # (what is being expanded, the grid that would run all of it)
        self._fields_open: list[str] = []  # the fields being rolled, so two that read each other are caught
        self._depth = 0  # expressions within expressions (an entry, a field): escapes come back at 0
        self._escaped: list[str] = []
        self.warnings: list[str] = []  # a reel's expanders share their world's list

    def _stream(self, label: str) -> Rng:
        """The dice for one pick. With RNG 2 a pick's stream comes from the seed, its label and how often
        that label was drawn before, so a choice added elsewhere leaves this pick as it was."""
        if self.dice == 1:
            return self.rng
        n = self._drawn.get(label, 0)
        self._drawn[label] = n + 1
        return Rng(zlib.crc32(f"{self.seed}\x1e{label}\x1e{n}".encode()))

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def learned(self, key: str) -> float:
        return float(self.weights.get(key, 1.0))

    def bind(self, name: str, expr: str) -> str:
        self._props_seen, self._tags_seen = {}, set()
        self.vars[name] = self.expr(expr, label_prefix=f"${name} ← ")
        self.var_tags[name] = self._tags_seen
        self.var_props[name] = props = self._props_seen
        self._props_seen = {}  # a field's own picks are not the binding's
        self.var_fields[name] = {}
        for key in props:
            self._field_of(name, key)
        return self.vars[name]

    def export(self, name: str, expr: str):
        """What `EXPORT: name = expr` keeps: its text, never in the prompt; `{value, field …}` when it rolled
        an entry with properties (or exports a binding that did), a list when it is a `{N$$…}` pick."""
        bound = re.fullmatch(r"\$([A-Za-z_]\w*)", expr.strip())
        if bound and bound.group(1) in self.vars:
            key = bound.group(1)
        else:
            key = f"\x1eexport {name}"  # beside the bindings, never one of them
            self._props_seen, self._tags_seen = {}, set()
            self.vars[key] = self.expr(expr, label_prefix=f"EXPORT {name} ← ")
            self.var_props[key], self._props_seen = self._props_seen, {}
            self.var_fields[key] = {}
        value = self.vars[key]
        if (b := _BRACE.fullmatch(expr.strip())) and (multi := _MULTI.match(b.group(1))):
            value = [v.strip() for v in value.split(", " if multi.group(3) is None else multi.group(3)) if v.strip()]
        fields = {f: self._field_of(key, f) for f in self.var_props.get(key, {})}
        return {"value": value, **fields} if fields else value

    def _field_of(self, name: str, field: str) -> str:
        """$name.field, rolled the first time it is needed (when bound, or by a field before it that
        reads it) and kept."""
        fields = self.var_fields.setdefault(name, {})
        if field not in fields:
            raw = self.var_props.get(name, {}).get(field)
            if raw is None:
                return ""
            here = f"${name}.{field}"
            if here in self._fields_open:
                raise ValueError("Fields read each other: " + " → ".join([*self._fields_open, here]))
            self._fields_open.append(here)
            try:
                fields[field] = self._field(name, field, raw)
            finally:
                self._fields_open.pop()
        return fields[field]

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

    def holds_pred(self, name: str, spec: str) -> bool:
        """`$c[myth, size=small]`: the predicate against what $c rolled: its tags, its properties, and
        its value as a tag of its own (`? $c[backbend]: …`)."""
        if name not in self.vars:
            self._unbound(name)
        value = (self.vars.get(name) or "").strip()
        return matches(spec, self.var_tags.get(name, set()) | {value}, self.var_props.get(name, {}), self._resolve)

    def guarded(self, line: str) -> str | None:
        """A `? cond: rest` line (or `IF …:`, see `question`): its rest when the condition holds, else None.
        Other lines as they are."""
        line = question(line)
        if m := _GUARD_PRED.match(line.strip()):
            return m.group(3) if self.holds_pred(m.group(1), m.group(2)) else None
        if not (m := _GUARD.match(line.strip())):
            return line
        return m.group(5) if self.holds(*m.group(1, 2, 3, 4)) else None

    def expr(self, text: str, label_prefix: str = "") -> str:
        if "\n" not in text and (text := self.guarded(text)) is None:
            return ""
        outermost, first = not self._depth, len(self.picks)
        self._depth += 1
        try:
            # escaped characters wait as placeholders until the outermost expression is done, so no
            # later pass (an entry's text, a binding's value) reads them as syntax
            text = _ESCAPE.sub(lambda m: self._escaped.append(m.group(1)) or f"\ue000{len(self._escaped) - 1}\ue001", text)
            tags: list[str] = []
            text = _LORA_TAG.sub(lambda m: tags.append(self._lora(m.group(0))) or f"\x00{len(tags) - 1}\x00", text)
            text = self._expand(text, label_prefix)
            if outermost:
                self._leftovers(text)
        finally:
            self._depth -= 1
        shows = []
        if tags:
            shows.append(lambda s: _HIDDEN.sub(lambda m: tags[int(m.group(1))], s))
        if outermost and self._escaped:
            shows.append(lambda s: _ESCAPED.sub(lambda m: self._escaped[int(m.group(1))], s))
        for show in shows:
            self.picks[first:] = [Pick(show(p.label), show(p.value), tuple(show(k) for k in p.keys))
                                  for p in self.picks[first:]]
            text = show(text)
        return text

    def _expand(self, text: str, label_prefix: str) -> str:
        for _ in range(MAX_CHOICES):
            m = _BRACE.search(text)
            if not m:
                break
            rolled, start = self._brace(m.group(1)), m.start()
            if not rolled and start and text[start - 1] == " " and text[m.end():m.end() + 1] in ("", " ", ",", ".", ";",
                                                                                                ":", "!", "?", ")"):
                start -= 1  # nothing rolled: the space before it goes too ("a fox {30% in the rain}.")
            text = text[:start] + rolled + text[m.end():]
        else:
            if m := _BRACE.search(text):
                raise ValueError(f"More than {MAX_CHOICES} {{…}} choices in one place, and {m.group(0)[:60]} is still "
                                 "to roll: a {N$$__lib__} whose entries bring it back?")
        text = _LIB.sub(lambda m: _mid_line(self._library(m.group(1), m.group(2), label_prefix, m.group(3),
                                                          _fixed(m.group(5))), m), text)
        text = _VAR.sub(lambda m: _mid_line(self._var(m), m), text)
        return self._articles(text)

    def _var(self, m: re.Match) -> str:
        name, field = m.group(1), m.group(5)
        clips = m.group(2) or m.group(3)
        back = int(clips) if clips else m.group(4)  # clips back, or a scene's title
        if field:  # a property of the pick behind the binding (back in the reel); empty when it has none
            if back is not None:
                return (self.history_props(name, back) if self.history_props else self.var_fields.get(name, {})).get(field, "")
            if name not in self.vars:
                self._unbound(name)
            return self._field_of(name, field)
        value = self.history(name, back) if back is not None and self.history else None
        if value is None:
            value = self.vars.get(name)
        if value is None:
            self._unbound(name)
            return m.group(0)
        return value

    def _leftovers(self, text: str) -> None:
        """What looks like syntax but rolled nothing: a misspelt wildcard, half a choice."""
        for m in _LOOKS_LIB.finditer(text):
            self.warn(f"{m.group(0)} looks like a wildcard but rolled nothing: a library name is letters, digits, _ "
                      f"and / (no - or spaces); \\__ writes the underscores as they are.")
        if "{" in text or "}" in text:
            self.warn("A { or } is left over: a choice is missing its other half; \\{ writes the brace as it is.")

    def _unbound(self, name: str) -> None:
        self.warn(f"${name} is not bound where it is used (bindings roll from the top down), so it stays as "
                  f"written: bind it on a line above, ${name} = ….")

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
        entries = [e for e in self.libraries[name].entries if matches(tag, e.tags, dict(e.props), self._resolve)
                   and all((e.prop(k) or "").casefold() == v for k, v in wanted)]
        if not entries:
            raise ValueError(f"{_label(name, tag, props)} matches no entry")
        return family, [(e.value, e.weight * self.learned(f"{family}={e.value}"), e.props, e.tags) for e in entries]

    def _resolve(self, value: str) -> str:
        """A filter value: as written, or `$var` / `$var.field` from what was rolled before."""
        if not value.startswith("$"):
            return value
        name, _, field = value[1:].partition(".")
        return (self.var_props.get(name, {}).get(field) if field else self.vars.get(name)) or ""

    def _glob(self, pattern: str, tag: str | None, props: str, rng: Rng, fixed: int | None) -> tuple[str, int | None]:
        """`__clothing/*__`: one of the libraries it matches that has such entries, each as likely
        (a fixed draw counts through their entries, in order), and the index within it."""
        names = glob_names(pattern, self.libraries)
        pools = []
        for name in names:
            try:
                pools.append((name, len(self._pool(name, tag, props)[1])))
            except ValueError:
                continue  # none of its entries match the brackets
        if not pools:
            raise ValueError(f"{_label(pattern, tag, props)} matches no library{' with such entries' if names else ''}")
        if fixed is None:
            return pools[int(rng.random() * len(pools))][0], None
        for name, count in pools:
            if fixed < count:
                return name, fixed
            fixed -= count
        raise ValueError(f"{_label(pattern, tag, props)} has fewer entries now than the grid counted")

    def _library(self, name: str, tag: str | None, label_prefix: str, props: str = "",
                 fixed: int | str | None = None) -> str:
        label = label_prefix + _label(name, tag, props)
        rng = self._stream(label)
        if "*" in name:
            name, fixed = self._glob(name, tag, props, rng, fixed)
        family, pool = self._pool(name, tag, props)
        i = weighted_pick([w for _, w, _, _ in pool], rng)  # a fixed draw rolls too (`@rng 1`)
        if isinstance(fixed, str):  # a dial: its entry, with what the entry carries, or its text as written
            dialed, fixed = fixed, next((j for j, entry in enumerate(pool) if entry[0].strip() == fixed.strip()), None)
            if fixed is None:
                return " ".join(self.expr(dialed, label_prefix).split())
        if fixed is not None:
            if fixed >= len(pool):
                raise ValueError(f"{_label(name, tag, props)} has {len(pool)} entries now, fewer than the grid counted")
            i = fixed
        value, _, entry_props, entry_tags = pool[i]
        self.picks.append(Pick(label, value, (f"{family}={value}",)))
        text = self._nested(name, value, label_prefix)
        self._props_seen.update(entry_props)  # after the nested picks: the outer library's fields win
        self._tags_seen.update(entry_tags)
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
        inner = question(inner)
        if m := _IF_PRED.match(inner.strip()):
            then, otherwise = (split_options(m.group(3), 1) + [""])[:2]
            return (then if self.holds_pred(m.group(1), m.group(2)) else otherwise).strip()
        if m := _IF.match(inner.strip()):
            then, otherwise = (split_options(m.group(5), 1) + [""])[:2]
            return (then if self.holds(*m.group(1, 2, 3, 4)) else otherwise).strip()
        if m := _MULTI.match(inner):
            return self._multi(int(m.group(1)), int(m.group(2) or m.group(1)), m.group(4).strip(),
                               ", " if m.group(3) is None else m.group(3))
        if (m := _CHANCE.fullmatch(inner)) and len(split_options(inner)) == 1:
            return self._chance(float(m.group(1)), m.group(2), "{" + inner.strip() + "}", fixed)
        if m := _RANGE.fullmatch(inner):
            family = "{" + inner.strip() + "}"
            value, bin_ = self._number(m.group(1), m.group(2), family)
            self.picks.append(Pick(family, value, (f"{family}={bin_}",)))
            return value
        raws = split_options(inner)
        options = []
        for raw in raws:
            wm, dp = _WEIGHTED.match(raw), _DP_WEIGHT.match(raw)
            options.append((dp.group(2), float(dp.group(1))) if dp else
                           (wm.group(1), float(wm.group(2))) if wm else (raw, 1.0))
        # `{|red }car`, `{ in the rain:3|:7}`: an empty option makes the others optional words, spaces kept
        if not (len(options) > 1 and any(not value.strip() for value, _ in options)):
            options = [(value.strip(), weight) for value, weight in options]
        # Labels and learned keys leave `(directions)` out: editing them must not rename the choice.
        family = without_directions("{" + "|".join(v for v, _ in options) + "}")
        weights = [w * self.learned(f"{family}={without_directions(v)}") for v, w in options]
        i = weighted_pick(weights, self._stream(family))  # a fixed draw rolls too (`@rng 1`)
        value = options[i if fixed is None else fixed][0]
        shown = without_directions(value)
        self.picks.append(Pick(family, shown, (f"{family}={shown}",)))
        return value

    def _chance(self, percent: float, words: str, family: str, fixed: int | None = None) -> str:
        """`{30% in the rain}`: the words three times in ten, nothing otherwise; learned like a choice."""
        p = min(max(percent / 100, 0.0), 1.0)
        weights = [p * self.learned(f"{family}={words}"), (1 - p) * self.learned(f"{family}=")]
        i = weighted_pick(weights, self._stream(family)) if any(weights) else 1
        value = words if (i if fixed is None else fixed) == 0 else ""
        self.picks.append(Pick(family, value, (f"{family}={value}",)))
        return value

    def _multi(self, lo: int, hi: int, source: str, joiner: str = ", ") -> str:
        if lm := _LIB_ONLY.match(source):
            family, pool3 = self._pool(lm.group(1), lm.group(2), lm.group(3))
            pool = [(v, w) for v, w, _, _ in pool3]
        else:
            options = [(dp.group(2).strip(), float(dp.group(1))) if (dp := _DP_WEIGHT.match(v)) else (v.strip(), 1.0)
                       for v in split_options(source)]
            family = without_directions("{" + "|".join(v for v, _ in options) + "}")
            pool = [(v, w * self.learned(f"{family}={without_directions(v)}")) for v, w in options]
        span = str(lo) if lo == hi else f"{lo}–{hi}"
        rng = self._stream(f"{family} ×{span}")
        n = lo + int(rng.random() * (hi - lo + 1))  # the count first, then the picks: as `@rng 1` always drew
        chosen: list[str] = []
        while pool and len(chosen) < n:
            i = weighted_pick([w for _, w in pool], rng)
            chosen.append(pool.pop(i)[0])
        self.picks.append(Pick(f"{family} ×{span}", without_directions(joiner.join(chosen)),
                               tuple(f"{family}={without_directions(v)}" for v in chosen)))
        return joiner.join(chosen)


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
        rng = self._stream(family)
        k = weighted_pick([self.learned(f"{family}={label}") for label in labels], rng)
        return show(edges[k] + int(rng.random() * (edges[k + 1] - edges[k]))), labels[k]

    def _lora(self, tag: str) -> str:
        """A LoRA tag with its strengths as values: `<lora:style:0.4-0.9>` rolls one, `<lora:style:{0.5|0.7}>`
        and `<lora:style:$s>` take what rolled (a grid axis may fix it), `:…` after it the CLIP's. Such a
        strength is a pick of `<lora:style>`, as a LoRA sweep records it; any other tag as it is. The name
        stays as written (file names may hold __)."""
        if self._where and (swept := sweep_tags(tag)):  # a sweep runs only where the template writes it
            first = swept[0].variants()[0]
            where, grid = self._where[-1]
            shown = sweep_tag(swept[0], first) if first[0] or first[1] else ""
            self.warn(f"{tag} in {where} is a sweep, and a sweep runs only where the template writes it: it takes "
                      f"{shown or 'it off'} there. To run every entry, write @grid {grid}.")
            return shown
        m = _LORA_PARTS.fullmatch(tag)
        parts = [m.group(2), m.group(3)] if m else []
        rolled = [p is not None and any(c in p for c in ("{", "$", "__")) for p in parts]
        before = len(self.picks)
        parts = [self.expr(p) if r else p for p, r in zip(parts, rolled, strict=True)]
        del self.picks[before:]  # the strength learns as `<lora:style>`, not as a `{0.5|0.7}` every LoRA shares
        if not m or not any(rolled) and not any(p and _RANGE.fullmatch(p) for p in parts):
            return tag
        label, out, keys = f"<lora:{m.group(1).strip()}>", [], []
        for which, part, was in (("", parts[0], rolled[0]), (" clip", parts[1], rolled[1])):
            if part is None:
                continue
            if was and not _RANGE.fullmatch(part):
                keys.append(f"{label}{which}={part.strip()}")
                out.append(part.strip())
            elif r := _RANGE.fullmatch(part):
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

    template, libraries = with_inline(template, libraries)
    template = prepare(template, seed, libraries, cell)
    parsed = parse(template)
    ex = Expander(seed, libraries, weights, parsed.params.rng)
    for name, expr in parsed.bindings:
        ex.bind(name, expr)
    text = ex.expr(" ".join(line for raw in parsed.body if (line := ex.guarded(raw)) is not None))
    if parsed.enhance:
        ex.picks.append(Pick("> enhance", parsed.enhance))
    exports = {name: ex.export(name, expr) for name, expr in parsed.exports}
    return Expansion(seed, text, ex.picks, parsed.params, parsed.enhance, cell, ex.warnings, exports)


def expand_batch(template: str, seed: int, count: int, libraries: Mapping[str, Library],
                 weights: Mapping[str, float] | None = None) -> list[Expansion]:
    """`count` seeds from `seed` on; with a `: grid`, every cell at each of them."""
    from orrery.batch import axes, cells
    from orrery.loras import long_form

    source, libraries = with_inline(long_form(template), libraries)
    found = axes(source, libraries) if parse(source).params.grid is not None else []
    grid = range(cells(found)) if found else [None]
    return [expand(template, seed + i, libraries, weights, cell=c) for i in range(count) for c in grid]
