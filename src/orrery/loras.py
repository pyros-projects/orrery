"""LoRAs: the files ComfyUI knows, `<lora:name:strength>` tags resolved to them as a stack, and the stack put on
the model that passes through the Orrery Prompt (#208), so no LoRA node is needed.

A stack is a list of (lora_name, model_strength, clip_strength), with lora_name the path
as ComfyUI's `loras` list spells it (the LORA_STACK of LoraManager and the other stack nodes). Tags name a file the way LoraManager does: its name without extension,
or its path; case and extension don't matter.
"""

import re
from pathlib import PurePosixPath

from orrery import knobs

TAG = re.compile(r"<lora:([^:<>]+):([^:<>]+)(?::([^:<>]+))?>")
# @style(0.8) is <lora:style:0.8>; @style(0.4-0.9), @style(0.5,0.7), @style(1.0:0.5) as their long forms
SHORT = re.compile(r"(?<![\w@<\\])@([\w./\\-]+)\(([^()<>]*)\)")
NOT_LORAS = {"include", "h3"}
IMAGE = re.compile(r"^image[_\s]*(\d+)$", re.IGNORECASE)  # `@image_1(0.6)`, a reference image's knob
EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".bin")

Stack = list[tuple[str, float, float, float, float]]  # (file, model, clip, start, end): start and end a share of sampling


def long_form(text: str, loras: list[str] | None = None, refmods: list[str] | None = None) -> str:
    """Every `@name(…)` as its long form (#227), which orrery's sweeps and compilers read: a RefMod's name as
    `<refmod:name:…>`, `@image_1(…)` as `<image:1:…>`, any other as `<lora:name:…>` (a name that is a LoRA
    and a RefMod too stays a LoRA; the long form chooses). A CAST member's name stays as it is (`SET: @JINX(0.6)`
    turns her references). `loras`, `refmods`: the files to tell them apart by, else ComfyUI's."""
    from orrery.cast import names
    from orrery.knobs import kind_of

    members = set(names(text)) if "@" in (text or "") else set()

    def one(m: re.Match) -> str:
        name, spec = m.group(1), m.group(2).strip()
        if name.lower() in NOT_LORAS or name in members:
            return m.group(0)
        if image := IMAGE.match(name):
            return f"<image:{image.group(1)}:{spec}>"
        if kind_of(name, loras, refmods) == "refmod":
            return f"<refmod:{name}:{spec}>"
        return f"<lora:{name}:{spec}>"

    return SHORT.sub(one, text or "")


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
        name, (model, *when) = m.group(1).strip(), [f.strip() for f in m.group(2).split(",")]  # strength, start, end (#227)
        try:
            strengths = float(model), float((m.group(3) or model).strip())
            start, end = (knobs.share(when[0]) if when else None) or 0.0, (knobs.share(when[1]) if len(when) > 1 else None)
        except ValueError:
            warnings.append(f"{m.group(0)} has no numeric strength (strength, start, end), so it is left out.")
            continue
        end = 1.0 if end is None else end
        if end <= start:
            warnings.append(f"{m.group(0)} ends before it starts, so it is left out.")
            continue
        found = [by_path[_key(name)]] if _key(name) in by_path else by_name.get(PurePosixPath(_key(name)).name, [])
        if not found:
            warnings.append(f"LoRA \"{name}\" is not among your LoRA files, so it is left out.")
            continue
        if len(found) > 1:
            warnings.append(f"LoRA \"{name}\" matches {', '.join(found)}; using {found[0]} (write the folder to choose).")
        stack.append((found[0], *strengths, start, end))
    return stack, warnings


_LOADED: dict[str, object] = {}  # path → a LoRA's weights, the ones the last clip used (ComfyUI's LoraLoader keeps one)


def apply(model, stack: Stack):
    """The model with the stack's LoRAs on it, as LoraLoaderModelOnly puts one (#208): model strengths only, since
    MiniMax H3's and Krea 2's LoRAs change the model; a strength of 0 leaves a LoRA out. A LoRA with a start or an
    end (#227) comes on and goes off on ComfyUI's hook keyframes (timed). The weights are shared."""
    import comfy.sd
    import comfy.utils
    import folder_paths

    loaded: dict[str, object] = {}
    timing: list[tuple] = []
    for name, strength, _clip, *when in stack:
        if not strength:
            continue
        path = folder_paths.get_full_path_or_raise("loras", name)
        loaded[path] = _LOADED.get(path) or loaded.get(path) or comfy.utils.load_torch_file(path, safe_load=True)
        start, end = when or (0.0, 1.0)
        if start > 0 or end < 1:
            timing.append((name, loaded[path], strength, start, end))
        else:
            model, _ = comfy.sd.load_lora_for_models(model, None, loaded[path], strength, 0)
    _LOADED.clear()
    _LOADED.update(loaded)
    return timed(model, timing) if timing else model


def timed(model, timing: list[tuple]):
    """The model with a wrapper around its sampler that puts these LoRAs on from their start to their end (#227):
    each a hook LoRA whose keyframes switch it on at its start and off at its end, as ComfyUI's hook nodes make
    them. ComfyUI registers the hooks of the conditionings before the wrapper runs, so the wrapper hangs them on
    every conditioning and registers them itself; `sample` takes them off again when it is done. Should that
    fail (another ComfyUI), the LoRA holds from the first step to the last, and the log says so."""
    import comfy.patcher_extension

    def wrapper(executor, *args, **kwargs):
        try:
            _hook(executor.class_obj, timing)
        except Exception as err:  # noqa: BLE001 - the LoRAs, then, for the whole of sampling
            print(f"[orrery] warn: LoRAs with a start or an end hold from first step to last here ({err}).")
            patcher = executor.class_obj.model_patcher
            import comfy.lora
            for _name, sd, strength, _start, _end in timing:
                patches = comfy.lora.load_lora(sd, comfy.lora.model_lora_keys_unet(patcher.model, {}))
                patcher.add_patches(patches, strength)
        return executor(*args, **kwargs)

    m = model.clone()
    m.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.OUTER_SAMPLE, "orrery_timed_loras", wrapper)
    return m


def _hook(guider, timing: list[tuple]) -> None:
    import comfy.hooks

    group = comfy.hooks.HookGroup()
    for _name, sd, strength, start, end in timing:
        hooks = comfy.hooks.create_hook_lora(sd, strength, 0)
        frames = comfy.hooks.HookKeyframeGroup()
        if start > 0:
            frames.add(comfy.hooks.HookKeyframe(strength=0.0, start_percent=0.0))
        frames.add(comfy.hooks.HookKeyframe(strength=1.0, start_percent=start))
        if end < 1:
            frames.add(comfy.hooks.HookKeyframe(strength=0.0, start_percent=end))
        hooks.set_keyframes_on_hooks(frames)
        for hook in hooks.hooks:
            group.add(hook)
    for conds in guider.conds.values():
        for c in conds:
            own = c.get("hooks")
            hooked = own.clone() if own is not None else comfy.hooks.HookGroup()
            for hook in group.hooks:
                hooked.add(hook)
            c["hooks"] = hooked
    registered = guider.model_options.get("registered_hooks") or comfy.hooks.HookGroup()
    target = comfy.hooks.create_target_dict(comfy.hooks.EnumWeightTarget.Model)
    guider.model_patcher.register_all_hook_patches(group, target, guider.model_options, registered)
    guider.model_options["registered_hooks"] = registered
