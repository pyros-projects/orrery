"""The model's knobs (#227): a LoRA, a RefMod, a reference image and a CAST member all change how the
model behaves, and are written alike: (strength, start, end), the start and the end a share of sampling
(`20%`). A short form is resolved by its name (`@name(0.8, 20%)`, `SET: name(…)`); a long form per kind
never collides:

    <lora:name:0.8, 20%, 90%>      <refmod:name:0.8, 0%, 10%>      <image:1:0.6, 20%>      <cast:JINX:0.6, refmods>

A field may sweep: `0.6|0.8`, or a range with a step, `0.2-1;0.2` (`0%-30%;10%`); Roll renders every
combination (orrery.sweep). Commas separate the fields, `|` a sweep's values.
"""

import math
import re

KINDS = ("lora", "refmod", "image", "cast")
LONG = re.compile(r"<(lora|refmod|image|cast):([^<>:]+?)(?::([^<>]*))?>", re.IGNORECASE)
MAX_VALUES = 1000  # the values one field may sweep
_NUM = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
_RANGE = re.compile(rf"^({_NUM})(%?)\s*-\s*({_NUM})%?\s*;\s*({_NUM})%?$")


def fields(spec: str) -> list[str]:
    """A knob's fields as written: `0.8, 20%|40%, 90%` → ['0.8', '20%|40%', '90%']."""
    return [f.strip() for f in (spec or "").split(",")]


def sweeps(field: str) -> bool:
    """Whether a field names several values (a choice `{a|b}` rolls instead, so it is no sweep)."""
    return "{" not in field and ("|" in field or bool(_RANGE.match(field.strip())))


def options(field: str) -> list[str]:
    """A field's values: `0.6|0.8`, a range `0.2-1;0.2` (its end when a step lands on it), `0%-30%;10%`, or itself."""
    out: list[str] = []
    for part in (p.strip() for p in field.split("|")):
        m = _RANGE.match(part)
        if not m:
            out.append(part)
            continue
        first, pct, last, step = float(m.group(1)), m.group(2), float(m.group(3)), float(m.group(4))
        if step <= 0:
            raise ValueError(f'sweep: the step in "{part}" must be above 0.')
        if last < first:
            raise ValueError(f'sweep: the range "{part}" runs backwards.')
        count = math.floor((last - first) / step + 1e-9) + 1
        if len(out) + count > MAX_VALUES:
            raise ValueError(f'sweep: "{field}" names too many values (more than {MAX_VALUES}).')
        out.extend(f"{round(first + i * step, 4):g}{pct}" for i in range(count))
    return out


def share(text: str) -> float | None:
    """A start or an end as written: `35%`, `0.35`, or `35` (more than 1: a percentage)."""
    text = text.strip()
    if not text:
        return None
    value = float(text.rstrip("%"))
    return min(1.0, value / 100 if text.endswith("%") or value > 1 else value)


def lora_files() -> list[str]:
    from orrery.loras import lora_files as files

    return files()


def refmod_files() -> list[str]:
    """ComfyUI's RefMods as its `refmods` list spells them; empty outside ComfyUI."""
    try:
        import folder_paths  # ComfyUI
        return list(folder_paths.get_filename_list("refmods"))
    except Exception:  # noqa: BLE001 - not inside ComfyUI, or no refmods folder
        return []


def _stem(path: str) -> str:
    stem = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return stem.rsplit(".", 1)[0] if "." in stem else stem


def kind_of(name: str, loras: list[str] | None = None, refmods: list[str] | None = None) -> str | None:
    """What a short form's name is among the files: "lora", "refmod", "both" (write the long form), or None
    (no such file, or outside ComfyUI). A RefMod's `_Video`/`_Audio` halves are the RefMod."""
    key = _stem(name).removesuffix("_video").removesuffix("_audio")
    is_lora = any(_stem(f) == key or f.replace("\\", "/").lower().rsplit(".", 1)[0] == name.lower()
                  for f in (lora_files() if loras is None else loras))
    is_refmod = any(_stem(f).removesuffix("_video").removesuffix("_audio") == key
                    for f in (refmod_files() if refmods is None else refmods))
    return "both" if is_lora and is_refmod else "lora" if is_lora else "refmod" if is_refmod else None
