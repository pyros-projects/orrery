"""ComfyUI nodes: Orrery Prompt (seeded text + picks) and Orrery Log (galaxy.jsonl).

The node pack folder `comfyui/` in the repo is what gets symlinked into
ComfyUI/custom_nodes; it only puts `src/` on the path and re-exports these
mappings. Everything testable lives here.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from orrery.dsl import MissingLibrary, expand
from orrery.h3 import compile_scene
from orrery.home import Home, resolve_home
from orrery.presets import list_presets, load_preset, remember_template

TARGETS = ["text", "h3-base", "flat"]
NO_PRESET = "(none)"
DEFAULT_TEMPLATE = "$hero = __animal__\n$hero in a {misty|frozen:2|burning} forest"


def run_prompt(template: str, seed: int, target: str, home: str = "",
               preset: str = NO_PRESET) -> tuple[str, str, int]:
    h = resolve_home(home or None)
    if preset and preset != NO_PRESET:
        template = load_preset(h, preset)
    try:
        if target == "text":
            result = expand(template, seed, h.libraries(), h.weights())
            lint = []
        else:
            result = compile_scene(template, seed, h.libraries(), h.weights(), target=target)
            lint = [{"severity": i.severity, "message": i.message} for i in result.lint]
    except MissingLibrary as err:
        raise ValueError(str(err)) from err
    for issue in lint:
        print(f"[orrery] {issue['severity']}: {issue['message']}")
    data = {
        "seed": seed,
        "target": target,
        "template": remember_template(h, template),
        "text": result.text,
        "picks": [{"label": p.label, "value": p.value, "keys": list(p.keys)} for p in result.picks],
        "lint": lint,
    }
    return result.text, json.dumps(data, ensure_ascii=False), seed


def state_token(home: Home) -> str:
    """Changes whenever a library or the learned weights change, so ComfyUI re-runs the node."""
    digest = hashlib.sha256()
    files = sorted(home.library_dir.glob("*.yaml")) if home.library_dir.exists() else []
    for f in [*files, home.weights_path]:
        if f.exists():
            digest.update(f.name.encode() + f.read_bytes())
    return digest.hexdigest()[:16]


def log_outputs(home: Home, picks_json: str, media: list[str]) -> list[dict]:
    data = json.loads(picks_json)
    ts = datetime.now(UTC).isoformat(timespec="seconds")
    rows = [{
        "ts": ts,
        "media": m,
        "seed": data.get("seed"),
        "target": data.get("target"),
        "template": data.get("template"),
        "text": data.get("text"),
        "picks": data.get("picks", []),
        "rating": None,
    } for m in (media or [None])]
    home.root.mkdir(parents=True, exist_ok=True)
    with home.galaxy_path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def save_png(image, path: Path | str, picks_json: str) -> None:
    """Save one HxWxC float image (0..1) with the picks in a PNG text chunk."""
    import numpy as np
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    pixels = (np.clip(np.asarray(image), 0.0, 1.0) * 255).round().astype(np.uint8)
    info = PngInfo()
    info.add_text("orrery", picks_json)
    Image.fromarray(pixels).save(path, pnginfo=info)


class OrreryPrompt:
    CATEGORY = "orrery"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("text", "picks", "seed")
    DESCRIPTION = ("Expands an orrery template (text) or compiles a screenplay (h3-base, flat) "
                   "and outputs the picks that produced it.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {"multiline": True, "default": DEFAULT_TEMPLATE}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF,
                                 "control_after_generate": True}),
                "target": (TARGETS,),
            },
            "optional": {
                "preset": ([NO_PRESET, *list_presets(resolve_home())],),
                "home": ("STRING", {"default": ""}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, template, seed, target, preset=NO_PRESET, home=""):
        h = resolve_home(home or None)
        chosen = load_preset(h, preset) if preset and preset != NO_PRESET else template
        return f"{seed}:{target}:{hash(chosen)}:{state_token(h)}"

    def run(self, template, seed, target, preset=NO_PRESET, home=""):
        return run_prompt(template, seed, target, home, preset)


class OrreryLog:
    CATEGORY = "orrery"
    FUNCTION = "log"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = ("Saves images with their picks embedded and appends one line per output to "
                   "galaxy.jsonl. For videos saved elsewhere, pass the file path as media_path.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"picks": ("STRING", {"forceInput": True})},
            "optional": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "orrery"}),
                "media_path": ("STRING", {"default": ""}),
                "home": ("STRING", {"default": ""}),
            },
        }

    def log(self, picks, images=None, filename_prefix="orrery", media_path="", home=""):
        media, ui = [], []
        if images is not None:
            import folder_paths  # ComfyUI

            height, width = images[0].shape[0], images[0].shape[1]
            folder, name, counter, subfolder, _ = folder_paths.get_save_image_path(
                filename_prefix, folder_paths.get_output_directory(), width, height)
            for image in images:
                file = f"{name}_{counter:05}_.png"
                save_png(image.cpu().numpy(), os.path.join(folder, file), picks)
                media.append(os.path.join(folder, file))
                ui.append({"filename": file, "subfolder": subfolder, "type": "output"})
                counter += 1
        elif media_path:
            media.append(media_path)
        log_outputs(resolve_home(home or None), picks, media)
        return {"ui": {"images": ui}}


NODE_CLASS_MAPPINGS = {"OrreryPrompt": OrreryPrompt, "OrreryLog": OrreryLog}
NODE_DISPLAY_NAME_MAPPINGS = {"OrreryPrompt": "Orrery Prompt", "OrreryLog": "Orrery Log"}
