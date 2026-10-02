"""LoRA sweeps: a LoRA tag with several strengths runs once per strength.

    <lora:relim_v2_lora_500:0.5,0.6,0.7>     three runs
    <lora:relim_v2_lora_500:0-1;0.1>         0, 0.1 … 1: eleven runs
    <lora:style_x:0.5,1.0:1.0>               the model strength swept, CLIP fixed
    <lora:a:0.5,1.0:solo>                    its own turn, the other solo LoRAs off
    <lora:H3-Icy-real-v1_000004200:test>     the macro: 1.0,0.7,0.5:solo

Swept LoRAs combine (the cross product, the first tag changing slowest); solo LoRAs take turns,
the solo turns being the outer loop. Strength 0 is off: the tag leaves the text, and identical runs
run once. The Orrery Prompt's Generate queues every run with one seed; each run gets its concrete
tags through `apply`, recorded as picks.
"""

import math
import re
from dataclasses import dataclass
from itertools import product

TAG = re.compile(r"<lora:([^<>]+)>")
MACROS = {"test": ("1.0,0.7,0.5", True)}  # <lora:name:test> = <lora:name:1.0,0.7,0.5:solo>
MAX_VALUES = 1000  # strengths one tag may name
_NUM = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
_ITEM = re.compile(rf"({_NUM})(?:\s*-\s*({_NUM})\s*;\s*({_NUM}))?")
_RANGE = re.compile(rf"{_NUM}\s*-\s*{_NUM}")
_EMPTY_LORA_LINE = re.compile(r"^[ \t]*LORA:[ \t]*(?:\n|$)", re.MULTILINE)

Value = tuple[float, float | None]  # (model, clip or None for the model's)


@dataclass(frozen=True)
class Swept:
    text: str  # the tag as written
    name: str
    model: list[float]
    clip: list[float] | None
    solo: bool

    def variants(self) -> list[Value]:
        return list(product(self.model, self.clip or [None]))


def values(spec: str) -> list[float]:
    """`0.5,0.6,0.7` · `0-1;0.1` (the end included when a step lands on it) · `-1-1;0.5` · mixed."""
    out: list[float] = []
    for part in (p.strip() for p in spec.split(",")):
        m = _ITEM.fullmatch(part)
        if not m:
            if _RANGE.fullmatch(part):
                raise ValueError(f'LoRA sweep: the range "{part}" needs a step, e.g. {part};0.1')
            raise ValueError(f'LoRA sweep: "{part}" is no strength; write numbers (0.5,0.7) or a range with a '
                             "step (0-1;0.1).")
        first = float(m.group(1))
        if m.group(2) is None:
            out.append(round(first, 4))
        else:
            last, step = float(m.group(2)), float(m.group(3))
            if step <= 0:
                raise ValueError(f'LoRA sweep: the step in "{part}" must be above 0.')
            if last < first:
                raise ValueError(f'LoRA sweep: the range "{part}" runs backwards; write {m.group(2)}-{m.group(1)};'
                                 f"{m.group(3)}.")
            count = math.floor((last - first) / step + 1e-9) + 1
            if len(out) + count > MAX_VALUES:
                raise ValueError(f'LoRA sweep: "{spec}" names too many strengths (more than {MAX_VALUES}).')
            out.extend(round(first + i * step, 4) for i in range(count))
        if len(out) > MAX_VALUES:
            raise ValueError(f'LoRA sweep: "{spec}" names too many strengths (more than {MAX_VALUES}).')
    return out


def _parse(text: str, content: str) -> Swept | None:
    """The tag as a sweep, or None when it is an ordinary one (left as it is)."""
    name, *rest = content.split(":")
    solo = False
    if rest and rest[0].strip().lower() in MACROS:
        model, solo = MACROS[rest[0].strip().lower()]
        rest = [model, *rest[1:]]
    if rest and rest[-1].strip().lower() == "solo":
        solo, rest = True, rest[:-1]
    if not rest or len(rest) > 2:
        return None
    if not solo and not any(("," in r or ";" in r) for r in rest):
        return None
    return Swept(text, name.strip(), values(rest[0]), values(rest[1]) if len(rest) == 2 else None, solo)


def tags(source: str) -> list[Swept]:
    """The swept LoRAs in a text, in order; the same tag written twice is one."""
    seen: dict[str, Swept] = {}
    for m in TAG.finditer(source):
        if m.group(0) not in seen and (swept := _parse(m.group(0), m.group(1))):
            seen[m.group(0)] = swept
    return list(seen.values())


def _off(value: Value) -> bool:
    model, clip = value
    return model == 0 and (clip is None or clip == 0)


def runs(source: str) -> list[dict[str, Value | None]]:
    """Every run of the sweep as {tag text: (model, clip) or None for off}; [] without a sweep."""
    swept = tags(source)
    if not swept:
        return []
    combined, solos = [t for t in swept if not t.solo], [t for t in swept if t.solo]
    combos = list(product(*(t.variants() for t in combined)))
    turns = [(s, v) for s in solos for v in s.variants()] or [(None, None)]
    out, seen = [], set()
    for solo, value in turns:
        for combo in combos:
            run = {t.text: (None if _off(v) else v) for t, v in zip(combined, combo, strict=True)}
            run.update({s.text: None for s in solos})
            if solo is not None:
                run[solo.text] = None if _off(value) else value
            key = tuple(run[t.text] for t in swept)
            if key not in seen:
                seen.add(key)
                out.append(run)
    return out


def formula(source: str) -> str:
    """How the runs come about, before doubles drop: `2 × 3`, `2 + 2`, `2 × (1 + 2)`."""
    swept = tags(source)
    combined = [str(len(t.variants())) for t in swept if not t.solo]
    solos = [str(len(t.variants())) for t in swept if t.solo]
    turns = " + ".join(solos)
    if not combined:
        return turns
    return " × ".join(combined) + (f" × ({turns})" if len(solos) > 1 else f" × {turns}" if solos else "")


def fmt(number: float) -> str:
    return f"{round(number, 4):g}"


def concrete(swept: Swept, value: Value) -> str:
    """The tag at one of its strengths: <lora:name:0.5> (with :clip when it has one)."""
    model, clip = value
    return f"<lora:{swept.name}:{fmt(model)}{'' if clip is None else ':' + fmt(clip)}>"


def _gap(m: re.Match) -> str:
    """What stays where an off tag was: one space when something stands on both sides, else nothing."""
    if not (m.group(1) or m.group(2)):
        return ""
    before = m.string[m.start() - 1] if m.start() else " "
    after = m.string[m.end()] if m.end() < len(m.string) else " "
    return " " if not before.isspace() and not after.isspace() else ""


def apply(source: str, run: dict[str, Value | None]) -> str:
    """The text with each swept tag as this run has it: a concrete tag, or gone when off (a `LORA:`
    line left empty goes too)."""
    for swept in tags(source):
        value = run.get(swept.text)
        if value is None:
            source = re.sub(r"([ \t]?)" + re.escape(swept.text) + r"([ \t]?)", _gap, source)
        else:
            source = source.replace(swept.text, concrete(swept, value))
    return _EMPTY_LORA_LINE.sub("", source)


def picks(source: str, run: dict[str, Value | None]) -> list[dict]:
    """Each swept LoRA of the run as a pick: its strength, or off."""
    out = []
    for swept in tags(source):
        value = run.get(swept.text)
        shown = "off" if value is None else fmt(value[0]) + ("" if value[1] is None else f"/{fmt(value[1])}")
        label = f"<lora:{swept.name}>"
        out.append({"label": label, "value": shown, "keys": [f"{label}={shown}"]})
    return out
