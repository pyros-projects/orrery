"""What the ComfyUI editor needs to complete a template: libraries, H3 words and LoRAs."""

from pathlib import PurePosixPath

from orrery.h3 import CAMERA, TRANSITIONS
from orrery.home import BUILTIN_DIR, Home
from orrery.library import load_libraries

MODIFIERS = ["small", "large", "slow", "fast"]
SAMPLE = 5


def _source(name: str, meta: dict, builtin: set[str]) -> str:
    if meta.get("generated_by"):
        return "llm"
    return "builtin" if name in builtin else "user"


def lora_files() -> list[str]:
    """ComfyUI's LoRA files (relative paths, any subfolder); empty outside ComfyUI."""
    try:
        import folder_paths  # ComfyUI
        return [f.replace("\\", "/") for f in folder_paths.get_filename_list("loras")]
    except Exception:  # noqa: BLE001 - not inside ComfyUI, or no loras folder
        return []


def _lora(path: str) -> dict:
    """Named the way LoraManager's LoRA Text Loader resolves `<lora:name:strength>`: file name, no extension."""
    p = PurePosixPath(path)
    return {"name": p.stem, "folder": "" if str(p.parent) == "." else str(p.parent)}


def completion_data(home: Home, loras: list[str] | None = None) -> dict:
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
        "loras": sorted((_lora(f) for f in (lora_files() if loras is None else loras)), key=lambda x: x["name"].lower()),
    }
