"""LoRAs: the files ComfyUI knows, `<lora:name:strength>` tags turned into a LORA_STACK, and the stack put on
the model that passes through the Orrery Prompt (#208), so no stack node is needed.

A LORA_STACK is a list of (lora_name, model_strength, clip_strength), with lora_name the path
as ComfyUI's `loras` list spells it: what LoraManager's loaders, Efficiency, Easy-Use and the
other stack nodes read. Tags name a file the way LoraManager does: its name without extension,
or its path; case and extension don't matter.
"""

import re
from pathlib import PurePosixPath

TAG = re.compile(r"<lora:([^:<>]+):([^:<>]+)(?::([^:<>]+))?>")
# @style(0.8) is <lora:style:0.8>; @style(0.4-0.9), @style(0.5,0.7), @style(1.0:0.5) as their long forms
SHORT = re.compile(r"(?<![\w@<\\])@([\w./\\-]+)\(([^()<>]*)\)")
NOT_LORAS = {"include", "h3"}
EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".bin")

Stack = list[tuple[str, float, float]]


def long_form(text: str) -> str:
    """Every `@name(strength)` as the `<lora:name:strength>` that LoRA loaders and orrery's sweeps read; a
    CAST member's name is no LoRA (`SET: @JINX(0.6)` turns her references)."""
    from orrery.cast import names

    members = set(names(text)) if "@" in (text or "") else set()
    return SHORT.sub(lambda m: m.group(0) if m.group(1).lower() in NOT_LORAS or m.group(1) in members
                     else f"<lora:{m.group(1)}:{m.group(2).strip()}>", text or "")


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


_LOADED: dict[str, object] = {}  # path → a LoRA's weights, the ones the last clip used (ComfyUI's LoraLoader keeps one)


def apply(model, stack: Stack):
    """The model with the stack's LoRAs on it, as LoraLoaderModelOnly puts one (#208): model strengths only, since
    MiniMax H3's and Krea 2's LoRAs change the model; a strength of 0 leaves a LoRA out. The weights are shared."""
    import comfy.sd
    import comfy.utils
    import folder_paths

    loaded: dict[str, object] = {}
    for name, strength, _clip in stack:
        if not strength:
            continue
        path = folder_paths.get_full_path_or_raise("loras", name)
        loaded[path] = _LOADED.get(path) or loaded.get(path) or comfy.utils.load_torch_file(path, safe_load=True)
        model, _ = comfy.sd.load_lora_for_models(model, None, loaded[path], strength, 0)
    _LOADED.clear()
    _LOADED.update(loaded)
    return model
