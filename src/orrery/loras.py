"""LoRAs: the files ComfyUI knows, and `<lora:name:strength>` tags turned into a LORA_STACK.

A LORA_STACK is a list of (lora_name, model_strength, clip_strength), with lora_name the path
as ComfyUI's `loras` list spells it: what LoraManager's loaders, Efficiency, Easy-Use and the
other stack nodes read. Tags name a file the way LoraManager does: its name without extension,
or its path; case and extension don't matter.
"""

import re
from pathlib import PurePosixPath

TAG = re.compile(r"<lora:([^:<>]+):([^:<>]+)(?::([^:<>]+))?>")
EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".bin")

Stack = list[tuple[str, float, float]]


def lora_files() -> list[str]:
    """ComfyUI's LoRA files as its `loras` list spells them; empty outside ComfyUI."""
    try:
        import folder_paths  # ComfyUI
        return list(folder_paths.get_filename_list("loras"))
    except Exception:  # noqa: BLE001 - not inside ComfyUI, or no loras folder
        return []


def _key(path: str) -> str:
    key = path.replace("\\", "/").strip().lower()
    return next((key[: -len(ext)] for ext in EXTENSIONS if key.endswith(ext)), key)


def lora_stack(text: str, files: list[str]) -> tuple[Stack, list[str]]:
    """The tags in `text` as a stack, and a warning for every tag left out or guessed."""
    tags = list(TAG.finditer(text or ""))
    if tags and not files:
        return [], ["No LoRA files found (is this running inside ComfyUI?), so lora_stack is empty."]
    by_path = {_key(f): f for f in files}
    by_name: dict[str, list[str]] = {}
    for f in sorted(files, key=str.lower):
        by_name.setdefault(PurePosixPath(_key(f)).name, []).append(f)
    stack, warnings = [], []
    for m in tags:
        name, model = m.group(1).strip(), m.group(2).strip()
        try:
            strengths = float(model), float((m.group(3) or model).strip())
        except ValueError:
            warnings.append(f"{m.group(0)} has no numeric strength, so it is left out.")
            continue
        found = [by_path[_key(name)]] if _key(name) in by_path else by_name.get(PurePosixPath(_key(name)).name, [])
        if not found:
            warnings.append(f"LoRA \"{name}\" is not among your LoRA files, so it is left out.")
            continue
        if len(found) > 1:
            warnings.append(f"LoRA \"{name}\" matches {', '.join(found)}; using {found[0]} (write the folder to choose).")
        stack.append((found[0], *strengths))
    return stack, warnings
