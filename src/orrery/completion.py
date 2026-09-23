"""What the ComfyUI editor needs to complete a template: libraries and H3 words."""

from orrery.h3 import CAMERA, TRANSITIONS
from orrery.home import BUILTIN_DIR, Home
from orrery.library import load_libraries

MODIFIERS = ["small", "large", "slow", "fast"]
SAMPLE = 5


def _source(name: str, meta: dict, builtin: set[str]) -> str:
    if meta.get("generated_by"):
        return "llm"
    return "builtin" if name in builtin else "user"


def completion_data(home: Home) -> dict:
    builtin = set(load_libraries(BUILTIN_DIR)) - set(load_libraries(home.library_dir))
    libraries = [{
        "name": name,
        "count": len(lib.entries),
        "source": _source(name, lib.meta, builtin),
        "tags": sorted({t for e in lib.entries for t in e.tags}),
        "sample": lib.values()[:SAMPLE],
    } for name, lib in sorted(home.libraries().items())]
    return {
        "libraries": libraries,
        "h3": {"camera": list(CAMERA), "modifiers": MODIFIERS, "transitions": list(TRANSITIONS)},
    }
