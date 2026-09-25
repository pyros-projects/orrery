"""What the ComfyUI editor needs to complete a template: libraries, H3 words and LoRAs."""

import re
from collections import Counter
from pathlib import PurePosixPath

from orrery.h3 import CAMERA, TRANSITIONS
from orrery.home import BUILTIN_DIR, Home
from orrery.library import load_libraries
from orrery.loras import lora_files

MODIFIERS = ["small", "large", "slow", "fast"]
SAMPLE = 5
_FILTERABLE = re.compile(r"[\w.-]{1,40}")  # what `__lib#key:value__` can name (dsl._PROP)
VALUES_MAX = 60


def _source(name: str, meta: dict, builtin: set[str]) -> str:
    if meta.get("generated_by"):
        return "llm"
    return "builtin" if name in builtin else "user"


def _lora(path: str) -> dict:
    """Named the way LoraManager resolves `<lora:name:strength>`: file name, no extension."""
    p = PurePosixPath(path.replace("\\", "/"))
    return {"name": p.stem, "folder": "" if str(p.parent) == "." else str(p.parent)}


def _props(lib) -> dict[str, list[dict]]:
    """Per property key, the values a `#key:value` filter can name, most common first, each with
    how many entries carry it and the first of them. Keys whose values are sentences (sfx, cite)
    cannot be filtered on, so they are left out."""
    seen: dict[str, Counter] = {}
    first: dict[tuple[str, str], str] = {}
    for e in lib.entries:
        for key, value in e.props:
            if _FILTERABLE.fullmatch(value):
                seen.setdefault(key, Counter())[value] += 1
                first.setdefault((key, value), e.value)
    return {key: [{"value": v, "count": n, "sample": first[(key, v)][:90]}
                  for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:VALUES_MAX]]
            for key, counts in sorted(seen.items())}


def completion_data(home: Home, loras: list[str] | None = None) -> dict:
    builtin = set(load_libraries(BUILTIN_DIR)) - set(load_libraries(home.library_dir))
    libraries = [{
        "name": name,
        "count": len(lib.entries),
        "source": _source(name, lib.meta, builtin),
        "tags": sorted({t for e in lib.entries for t in e.tags}),
        "sample": lib.values()[:SAMPLE],
        "props": _props(lib),
    } for name, lib in sorted(home.libraries().items())]
    return {
        "libraries": libraries,
        "h3": {"camera": list(CAMERA), "modifiers": MODIFIERS, "transitions": list(TRANSITIONS)},
        "loras": sorted((_lora(f) for f in (lora_files() if loras is None else loras)), key=lambda x: x["name"].lower()),
    }
