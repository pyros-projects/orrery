"""Batch parameters on a `:` line: `grid` runs every combination of a few choices, `unique=` keeps a
choice from repeating across seeds.

    : grid __style__ × {dawn|noon}     every style at dawn and at noon, one run each
    : grid $hero × __place[city]__     a binding's choices, a filtered library's entries
    : x8 unique=__creature__           eight seeds in a row, eight different creatures
    : unique=$hero                     never the same hero within as many seeds as it has choices

A grid run fixes each axis to one of its options where the template writes it, and every other draw
stays as it was: the fixed draw still uses the dice, so the picks after it don't move. The Orrery
Prompt's Generate queues every cell, as it does a LoRA sweep (the two multiply). `unique=` needs no
state: it walks one shuffled order of the choices, a step per seed, so seeds s … s+n-1 get n
different values and the next batch goes on where this one ended. Learned weights don't steer it:
a batch like that is there to cover the choices, not to favour some.
"""

import re
import zlib
from collections.abc import Mapping
from dataclasses import dataclass

from orrery.dsl import (
    _BRACE,
    _CHANCE,
    _DP_WEIGHT,
    _IF,
    _LIB,
    _LIB_ONLY,
    _MULTI,
    _RANGE,
    _WEIGHTED,
    FIX,
    glob_names,
    matches,
    parse,
    split_options,
    without_directions,
)
from orrery.library import Library
from orrery.loras import long_form
from orrery.rng import Rng

MAX_CELLS = 10000
_BINDING_LINE = re.compile(r"^(\s*\$([A-Za-z_]\w*)\s*=\s*)(.+)$")
_PROPS = re.compile(r"#([\w-]+):([\w.-]+)")


@dataclass(frozen=True)
class Axis:
    text: str  # as written: __style__, {dawn|noon}, $hero
    expr: str  # what is fixed: the library or the brace (a binding's expression)
    options: list[str]


def _choices(expr: str, libraries: Mapping[str, Library], what: str) -> list[str]:
    """The options of one library reference or one brace, in their order."""
    expr = without_directions(expr.strip())
    if m := _LIB_ONLY.match(expr):
        if "$" in (m.group(3) or "") + (m.group(2) or ""):
            raise ValueError(f"{what}: {expr} filters by a roll, so its entries are not known before the run.")
        name, tag = m.group(1), m.group(2)
        names = glob_names(name, libraries) if "*" in name else [name]  # a glob: every entry of each, in order
        if not names or names[0] not in libraries:
            raise ValueError(f"{what}: there is no library __{name}__.")
        wanted = [(k, v.casefold()) for k, v in _PROPS.findall(m.group(3) or "")]
        entries = [e.value for n in names for e in libraries[n].entries if matches(tag, e.tags, dict(e.props))
                   and all((e.prop(k) or "").casefold() == v for k, v in wanted)]
        if not entries:
            raise ValueError(f"{what}: {expr} matches no entry.")
        return entries
    if (m := _BRACE.fullmatch(expr)) and (c := _CHANCE.fullmatch(m.group(1))) and len(split_options(m.group(1))) == 1:
        return [c.group(2), ""]  # {30% in the rain}: with the words, without
    if (m := _BRACE.fullmatch(expr)) and not _IF.match(m.group(1).strip()) and not _MULTI.match(m.group(1)) \
            and not _RANGE.fullmatch(m.group(1)):
        out = []
        for raw in split_options(m.group(1)):
            dp, wm = _DP_WEIGHT.match(raw), _WEIGHTED.match(raw)
            out.append((dp.group(2) if dp else wm.group(1) if wm else raw).strip())
        return out
    raise ValueError(f"{what}: {expr} is neither one library (__style__) nor one choice ({{dawn|noon}}); "
                     "bind it ($style = …) and name the binding.")


def _binding(source: str, name: str, what: str) -> str:
    for bound, expr in parse(source).bindings:
        if bound == name:
            return expr
    raise ValueError(f"{what}: the template has no binding ${name}.")


def _axis(text: str, source: str, libraries: Mapping[str, Library], what: str) -> Axis:
    text = text.strip()
    if text.startswith("$"):
        expr = _binding(source, text[1:], what)
        return Axis(text, expr.strip(), _choices(expr, libraries, f"{what} {text}"))
    return Axis(text, without_directions(text), _choices(text, libraries, what))


def axes(source: str, libraries: Mapping[str, Library]) -> list[Axis]:
    """The template's grid axes, from its `: grid A × B` line; [] without one."""
    grid = parse(source).params.grid
    if grid is None:
        return []
    parts = [a for a in re.split(r"\s+[×*]\s+|\s*×\s*", grid) if a.strip()]
    if not parts:
        raise ValueError("`: grid` names no axes: write `: grid __style__ × {dawn|noon}`.")
    out = [_axis(a, source, libraries, "grid") for a in parts]
    if len({a.expr for a in out}) < len(out):
        raise ValueError("`: grid` names the same choice twice.")
    for axis in out:
        if not _places(source, axis):
            raise ValueError(f"`: grid` names {axis.text}, but the template doesn't use it.")
    return out


def cells(found: list[Axis]) -> int:
    n = 1
    for a in found:
        n *= len(a.options)
    if n > MAX_CELLS:
        raise ValueError(f"`: grid` makes {n} runs, more than {MAX_CELLS}; narrow an axis with a tag ([…]).")
    return n


def formula(found: list[Axis]) -> str:
    return " × ".join(str(len(a.options)) for a in found)


def _fix(source: str, axis: Axis, index) -> str:
    """The template with `axis` fixed where it is written: index(j) for its j-th place (one place for a
    binding)."""
    if axis.text.startswith("$"):
        name, done = axis.text[1:], False

        def line(raw: str) -> str:
            nonlocal done
            m = _BINDING_LINE.match(raw)
            if done or not m or m.group(2) != name:
                return raw
            done = True
            return m.group(1) + _fix(m.group(3), Axis(axis.expr, axis.expr, axis.options), lambda _: index(0))

        return "\n".join(line(raw) for raw in source.split("\n"))
    places = 0

    def mark(m: re.Match, inner: str | None = None) -> str:
        nonlocal places
        if without_directions(m.group(0)) != axis.expr:
            return m.group(0)
        n, places = index(places), places + 1
        if inner is not None:
            return "{" + f"{FIX}{n}{FIX}" + inner + "}"
        text = m.group(0)  # __name[tags]#k:v__(directions): the marker goes before the closing __
        close = (m.start(6) - 1 if m.group(6) is not None else m.end()) - 2 - m.start()
        return f"{text[:close]}{FIX}{n}{FIX}{text[close:]}"

    def fix_line(raw: str) -> str:
        if re.match(r"\s*([:#]|@(grid|unique|size|seed|batch|rng)\b)", raw):  # the @grid / @unique line itself, comments
            return raw
        if axis.expr.startswith("{"):
            return _BRACE.sub(lambda m: mark(m, m.group(1)), raw)
        return _LIB.sub(mark, raw)

    return "\n".join(fix_line(raw) for raw in source.split("\n"))


def _places(source: str, axis: Axis) -> int:
    count = []
    _fix(source, axis, lambda j: count.append(j) or 0)
    return len(count)


def apply_grid(source: str, found: list[Axis], cell: int) -> str:
    """The template as grid run `cell` has it, the first axis changing slowest."""
    total = cells(found)
    if not 0 <= cell < total:
        raise ValueError(f"Grid run {cell} does not exist: this grid has {total} runs ({formula(found)}).")
    for axis in reversed(found):
        cell, i = divmod(cell, len(axis.options))
        source = _fix(source, axis, lambda _, i=i: i)
    return source


def _order(axis: Axis) -> list[int]:
    """One shuffled order of an axis's options, the same for every seed (Fisher-Yates on orrery's rng)."""
    rng, order = Rng(zlib.crc32(axis.expr.encode())), list(range(len(axis.options)))
    for i in range(len(order) - 1, 0, -1):
        j = int(rng.random() * (i + 1))
        order[i], order[j] = order[j], order[i]
    return order


def apply_unique(source: str, seed: int, libraries: Mapping[str, Library], skip: set[str] = frozenset()) -> str:
    """Each `unique=` choice at seed's step of its shuffled order; a template writing it k times takes
    k steps per seed, so no two places in a batch share a value while the choices last."""
    for text in parse(source).params.unique:
        axis = _axis(text, source, libraries, f"unique={text}")
        if axis.expr in skip:
            raise ValueError(f"unique={text} is a grid axis too; the grid already gives every value once.")
        k = _places(source, axis)
        if not k:
            raise ValueError(f"unique={text}: the template doesn't use it.")
        order, n = _order(axis), len(axis.options)
        source = _fix(source, axis, lambda j, order=order, n=n, k=k: order[(seed * k + j) % n])
    return source


def prepare(source: str, seed: int, libraries: Mapping[str, Library], cell: int | None = None) -> str:
    """The template ready to expand at `seed`: LoRA short forms written out, grid run `cell` (None:
    the axes roll), `unique=` choices at this seed."""
    source = long_form(source)
    params = parse(source).params
    if params.grid is None and not params.unique:
        return source
    found = axes(source, libraries) if params.grid is not None else []
    if found and cell is not None:
        source = apply_grid(source, found, cell)
    return apply_unique(source, seed, libraries, {a.expr for a in found})


def plan(source: str, libraries: Mapping[str, Library]) -> dict:
    """What Generate queues for a template: the LoRA sweep's runs (the outer loop) times the grid's
    cells, how they come about (`2 × grid 3 × 2`, `(1 + 2) × grid 4`) and a name for the galaxy folder;
    {"runs": 0} when it is one run."""
    from orrery import sweep as sweeps
    from orrery.dsl import strip_comments, with_inline

    source, libraries = with_inline(long_form(strip_comments(source)), libraries)
    loras = sweeps.runs(source)
    found = axes(source, libraries) if parse(source).params.grid is not None else []
    if not loras and not found:
        return {"runs": 0}
    lora = sweeps.formula(source) if loras else ""
    parts = ([f"({lora})" if "+" in lora and found else lora] if loras else []) + \
        ([f"grid {formula(found)}"] if found else [])
    return {"runs": max(len(loras), 1) * (cells(found) if found else 1), "formula": " × ".join(parts),
            "first": sweeps.tags(source)[0].name if loras else " × ".join(a.text for a in found).replace("/", "-")}

