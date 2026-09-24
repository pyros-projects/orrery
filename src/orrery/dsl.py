"""The orrery prompt DSL: seeded expansion that records every pick.

    $hero = __animal__
    $hero in a {misty|frozen:3} forest, {1-2$$__style__}
    > moody, cinematic
    : x8 seed=100 w1216 h832

Every expansion returns the text *and* the picks that produced it. Pick keys
(`__animal__=fox`, `{misty|frozen}=misty`) are what learned weights attach to.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from orrery.library import Library
from orrery.rng import Rng, weighted_pick

_BRACE = re.compile(r"\{([^{}]*)\}")
# __name[tag]:N__(directions): N = at least N entries; (directions) guide the model that writes the
# library and never reach the prompt
_LIB = re.compile(r"__(\w+(?:/\w+)*)(?:\[([\w-]+)\])?(?::(\d+))?__(?:\(([^()]*)\))?")
_VAR = re.compile(r"\$([A-Za-z_]\w*)(?:~(\d+))?")  # $x, or $x~N: x as it was N clips ago
_BINDING = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$")
_BINDING_LINE = re.compile(r"^(\s*)\$([A-Za-z_]\w*)(\s*=\s*)(.+)$")
_MULTI = re.compile(r"^(\d+)(?:-(\d+))?\$\$(.+)$")
_WEIGHTED = re.compile(r"^(.*?):(\d+(?:\.\d+)?)$")
_LIB_ONLY = re.compile(r"^__(\w+(?:/\w+)*)(?:\[([\w-]+)\])?(?::\d+)?__(?:\([^()]*\))?$")
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


@dataclass
class Expansion:
    seed: int
    text: str
    picks: list[Pick]
    params: Params = field(default_factory=Params)
    enhance: str | None = None


@dataclass
class _Parsed:
    bindings: list[tuple[str, str]]
    body: list[str]
    enhance: str | None
    params: Params


def parse(template: str) -> _Parsed:
    parsed = _Parsed([], [], None, Params())
    for raw in template.splitlines():
        line = raw.strip()
        if not line:
            continue
        if m := _BINDING.match(line):
            parsed.bindings.append((m.group(1), m.group(2)))
        elif line.startswith(">"):
            parsed.enhance = line[1:].strip()
        elif line.startswith(":"):
            parsed.params = _parse_params(line[1:])
        else:
            parsed.body.append(line)
    return parsed


def wanted_libraries(template: str) -> dict[str, int]:
    """Every library a template uses, with the entries it asks for (`__name:N__`, else 0)."""
    wanted: dict[str, int] = {}
    for m in _LIB.finditer(_LORA_TAG.sub("", template)):
        wanted[m.group(1)] = max(wanted.get(m.group(1), 0), int(m.group(3) or 0))
    return wanted


def library_directions(template: str) -> dict[str, str]:
    """What the template tells the model about each library it may write: `__name__(directions)`."""
    return {m.group(1): m.group(4).strip() for m in _LIB.finditer(_LORA_TAG.sub("", template)) if m.group(4)}


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


def _parse_params(text: str) -> Params:
    def grab(pattern: str) -> int | None:
        m = re.search(pattern, text)
        return int(m.group(1)) if m else None

    return Params(grab(r"\bx(\d+)"), grab(r"\bseed=(\d+)"), grab(r"\bw(\d+)"), grab(r"\bh(\d+)"))


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

    def learned(self, key: str) -> float:
        return float(self.weights.get(key, 1.0))

    def bind(self, name: str, expr: str) -> str:
        self.vars[name] = self.expr(expr, label_prefix=f"${name} ← ")
        return self.vars[name]

    def expr(self, text: str, label_prefix: str = "") -> str:
        tags: list[str] = []
        text = _LORA_TAG.sub(lambda m: tags.append(m.group(0)) or f"\x00{len(tags) - 1}\x00", text)
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
        text = _LIB.sub(lambda m: self._library(m.group(1), m.group(2), label_prefix), text)
        text = _VAR.sub(self._var, text)
        return self._articles(text)

    def _var(self, m: re.Match) -> str:
        name, back = m.group(1), m.group(2)
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

    def _pool(self, name: str, tag: str | None) -> tuple[str, list[tuple[str, float]]]:
        if name not in self.libraries:
            raise MissingLibrary(name)
        family = f"__{name}__"
        entries = [e for e in self.libraries[name].entries if tag is None or tag in e.tags]
        return family, [(e.value, e.weight * self.learned(f"{family}={e.value}")) for e in entries]

    def _library(self, name: str, tag: str | None, label_prefix: str) -> str:
        family, pool = self._pool(name, tag)
        value = pool[weighted_pick([w for _, w in pool], self.rng)][0]
        label = label_prefix + (f"__{name}[{tag}]__" if tag else family)
        self.picks.append(Pick(label, value, (f"{family}={value}",)))
        return value

    def _brace(self, inner: str) -> str:
        if m := _MULTI.match(inner):
            return self._multi(int(m.group(1)), int(m.group(2) or m.group(1)), m.group(3).strip())
        options = []
        for raw in inner.split("|"):
            wm = _WEIGHTED.match(raw)
            options.append((wm.group(1).strip(), float(wm.group(2))) if wm else (raw.strip(), 1.0))
        family = "{" + "|".join(v for v, _ in options) + "}"
        weights = [w * self.learned(f"{family}={v}") for v, w in options]
        value = options[weighted_pick(weights, self.rng)][0]
        self.picks.append(Pick(family, value, (f"{family}={value}",)))
        return value

    def _multi(self, lo: int, hi: int, source: str) -> str:
        n = lo + int(self.rng.random() * (hi - lo + 1))
        if lm := _LIB_ONLY.match(source):
            family, pool = self._pool(lm.group(1), lm.group(2))
        else:
            family = "{" + source + "}"
            pool = [(v.strip(), self.learned(f"{family}={v.strip()}")) for v in source.split("|")]
        chosen: list[str] = []
        while pool and len(chosen) < n:
            i = weighted_pick([w for _, w in pool], self.rng)
            chosen.append(pool.pop(i)[0])
        span = str(lo) if lo == hi else f"{lo}–{hi}"
        self.picks.append(Pick(f"{family} ×{span}", ", ".join(chosen),
                               tuple(f"{family}={v}" for v in chosen)))
        return ", ".join(chosen)


def expand(template: str, seed: int, libraries: Mapping[str, Library],
           weights: Mapping[str, float] | None = None) -> Expansion:
    parsed = parse(template)
    ex = Expander(seed, libraries, weights)
    for name, expr in parsed.bindings:
        ex.bind(name, expr)
    text = ex.expr(" ".join(parsed.body))
    if parsed.enhance:
        ex.picks.append(Pick("> enhance", parsed.enhance))
    return Expansion(seed, text, ex.picks, parsed.params, parsed.enhance)


def expand_batch(template: str, seed: int, count: int, libraries: Mapping[str, Library],
                 weights: Mapping[str, float] | None = None) -> list[Expansion]:
    return [expand(template, seed + i, libraries, weights) for i in range(count)]
