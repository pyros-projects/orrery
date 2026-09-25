"""ComfyUI nodes: Orrery Prompt (seeded text + picks) and Orrery Log (galaxy.jsonl).

The node pack folder `comfyui/` in the repo is what gets symlinked into
ComfyUI/custom_nodes; it only puts `src/` on the path and re-exports these
mappings. Everything testable lives here.
"""

import hashlib
import json
import math
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from orrery.autolib import needs
from orrery.chain import DEFAULT_CHAIN, load, previous_clip
from orrery.comfy_llm import ComfyBackend, can_write, llm_config
from orrery.dsl import MissingLibrary, bindings, expand, override, parse, wanted_libraries
from orrery.h3 import compile_scene
from orrery.h3_ref import word_issue
from orrery.home import Home, resolve_home
from orrery.library import library_files
from orrery.llm import InvalidProposal
from orrery.loras import lora_files, lora_stack
from orrery.presets import (
    list_presets,
    load_preset,
    preset_exists,
    remember_template,
    resolve_includes,
)
from orrery.reel import ReelEnd
from orrery.slots import SLOT, fill, request, slots, write

TARGETS = ["text", "h3-base", "flat"]
NO_PRESET = "(none)"
DEFAULT_TEMPLATE = "$hero = __animal__\n$hero in a {misty|frozen:2|burning} forest"


H3_FPS = 24
H3_DEFAULT_LENGTH = 124  # the MiniMax H3 nodes' default: about 5 s


def h3_length(seconds: float) -> int:
    """Frames at 24 fps, snapped up to H3's 17k+5 grid like the MiniMax H3 nodes do."""
    frames = max(5, math.ceil(seconds * H3_FPS - 1e-4))
    return frames + (5 - frames) % 17


def h3_canvas(ratio: str) -> tuple[int, int] | None:
    """The MiniMax H3 canvas for a ratio: 768 short edge, 768×1344 area cap, multiples of 32."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)", ratio or "")
    if not m or not float(m.group(2)):
        return None
    r = float(m.group(1)) / float(m.group(2))
    w, h = (768 * r, 768) if r >= 1 else (768, 768 / r)
    if w * h > 768 * 1344:
        scale = math.sqrt(768 * 1344 / (w * h))
        w, h = w * scale, h * scale
    return max(32, round(w / 32) * 32), max(32, round(h / 32) * 32)


def shape(template: str) -> tuple[int, int, int]:
    """width, height and H3 length for the node's outputs: `: w… h…` wins, then an @h3 ratio."""
    params = parse(template).params
    lines = [line.strip() for line in template.splitlines() if line.strip()]
    header = re.match(r"@h3\s+\w+(.*)$", lines[0], re.IGNORECASE) if lines else None
    ratio = next((t for t in header.group(1).split() if h3_canvas(t)), "") if header else ""
    canvas = h3_canvas(ratio) or (1024, 1024)
    seconds = sum(float(m.group(1)) for line in lines
                  if (m := re.match(r"SHOT\s+(\d+(?:\.\d+)?)\s*s\b", line, re.IGNORECASE)))
    return (params.width or canvas[0], params.height or canvas[1],
            h3_length(seconds) if seconds else H3_DEFAULT_LENGTH)


def linked_preset(extra_pnginfo, unique_id) -> str | None:
    """The preset the node's editor is linked to, from the workflow ComfyUI sends along."""
    workflow = (extra_pnginfo or {}).get("workflow") or {}
    graphs = [workflow, *((workflow.get("definitions") or {}).get("subgraphs") or [])]
    node_id = str(unique_id or "").rsplit(":", 1)[-1]
    for graph in graphs:
        for node in graph.get("nodes") or []:
            if str(node.get("id")) == node_id:
                return (node.get("properties") or {}).get("orrery_preset") or None
    return None


def dial_values(params: str) -> dict[str, str]:
    """The node's params widget: JSON {binding: expression}; blanks and bad JSON count as unset."""
    try:
        values = json.loads(params) if params and params.strip() else {}
    except json.JSONDecodeError:
        print("[orrery] warn: the dials are not valid JSON and are ignored.")
        return {}
    return {str(k).lstrip("$"): str(v).strip() for k, v in values.items() if str(v).strip()} if isinstance(values, dict) else {}


def llm_for(home: Home, clip=None, seed: int = 0) -> ComfyBackend | None:
    """The active language model: a text encoder on the node's clip input, else the one chosen in
    orrery's settings, else none."""
    cfg = llm_config(home)
    options = {"temperature": float(cfg["temperature"]), "max_length": int(cfg["max_tokens"]), "seed": seed}
    if clip is not None:
        return ComfyBackend(clip=clip, **options)
    if cfg["file"] and can_write(cfg["file"]):
        return ComfyBackend(file=cfg["file"], clip_type=cfg["clip_type"], **options)
    return None


def _missing_libraries(home: Home, template: str) -> bool:
    libraries = home.libraries()
    return not all(name in libraries and len(libraries[name].entries) >= n
                   for name, n in wanted_libraries(template).items())


def _count(frames) -> int:
    return len(frames) if frames is not None else 0


def run_prompt(template: str, seed: int, target: str, home: str = "",
               preset: str = NO_PRESET, linked: str | None = None,
               params: str = "", segment: int = 0, clip=None,
               frames=None) -> tuple[str, str, int, int, int, int, list, int, int]:
    """`frames`: the previous clip's stills, which the model sees when it writes `--…--` slots."""
    h = resolve_home(home or None)
    if preset and preset != NO_PRESET:
        template, linked = load_preset(h, preset), preset
    if linked and not preset_exists(h, linked):
        linked = None
    known = {name for name, _ in bindings(template)}
    dials = {k: v for k, v in dial_values(params).items() if k in known}
    source = resolve_includes(h, override(template, dials))

    # One request per run (ComfyUI cannot safely generate twice): libraries still missing and the
    # slots go together, the slots then seeing the template; otherwise the slots see the compiled prompt.
    written, missing = slots(source), _missing_libraries(h, source)
    backend = llm_for(h, clip, seed=seed) if written or missing else None
    if written and backend is None:
        raise ValueError("--…-- slots are written by a language model: pick one in orrery's settings (the gear in "
                         "the node) or wire a text encoder into its clip input")
    texts: dict[str, str] = {}
    notes: list[str] = []
    missed: dict[str, str] = {}  # marker → directions of the slots the combined answer left out
    wanted = needs(h, source, int(llm_config(h)["entries"])) if missing and backend is not None else []
    if wanted:
        see = frames if written else None
        reply = backend.complete(request(wanted, written, source, _count(see)), images=see)
        answered, notes = write(h, wanted, written, reply, backend)
        texts = {f"slot {i}": answered.get(d) or d for i, d in enumerate(written, start=1)}
        missed = {f"slot {i}": d for i, d in enumerate(written, start=1) if d not in answered}
        source = SLOT.sub(lambda m: f"--slot {written.index(m.group(1)) + 1}--", source)  # survives the compile
    try:
        if target == "text":
            result = expand(source, seed, h.libraries(), h.weights())
            lint = []
        else:
            result = compile_scene(source, seed, h.libraries(), h.weights(), target=target, segment=segment)
            lint = [{"severity": i.severity, "message": i.message} for i in result.lint]
    except MissingLibrary as err:
        raise ValueError(f"{err}, or pick a language model in orrery's settings (the gear in the node) "
                         "and it is created when the node runs") from err
    todo = slots(result.text)
    if todo and not wanted:
        try:
            texts, _ = write(h, [], todo, backend.complete(request([], todo, result.text, _count(frames)),
                                                          images=frames), backend)
        except InvalidProposal as err:
            lint.append({"severity": "warn", "message": f"The language model wrote no slots ({err})."})
    unanswered = [missed[k] for k in todo if k in missed] if wanted else [d for d in todo if d not in texts]
    lint += [{"severity": "warn", "message": f"--{d}-- got no text from the language model; its directions stand in."}
             for d in unanswered]
    result.text = fill(result.text, texts)
    if texts and "\ndetailed_description:\n" in result.text:  # count what the model wrote too
        lint = [i for i in lint if not i["message"].startswith("detailed_description has")]
        described = result.text.split("\ndetailed_description:\n", 1)[1].split("\n\noverall_soundscape:", 1)[0]
        if issue := word_issue(described):
            lint.append({"severity": issue.severity, "message": issue.message})
    lint = [{"severity": "info", "message": n} for n in notes] + lint
    stack: list = []
    if target != "text" and result.loras:
        stack, warnings = lora_stack(result.loras, lora_files())
        lint += [{"severity": "warn", "message": w} for w in warnings]
    for issue in lint:
        print(f"[orrery] {issue['severity']}: {issue['message']}")
    data = {
        "seed": seed,
        "target": target,
        "template": remember_template(h, template),
        "preset": linked,
        "edited": bool(linked) and template != load_preset(h, linked),
        "params": dials,
        "text": result.text,
        "picks": [{"label": p.label, "value": p.value, "keys": list(p.keys)} for p in result.picks],
        "lint": lint,
    }
    width, height, length = shape(source)
    if target != "text":
        if result.scene.shots:
            length = h3_length(result.scene.duration)
        if result.chunks:
            data["segment"], data["chunks"], data["segments"] = result.segment, result.chunks, result.segments
    return (result.text, json.dumps(data, ensure_ascii=False), seed, width, height, length, stack,
            segment, segment + 1)


def _previous(latent_path: str, segment: int):
    """(stills, tail, audio) of the clip before this segment in the Motion Context chain, else Nones."""
    try:
        import folder_paths  # ComfyUI
    except ImportError:
        return None, None, None
    path = previous_clip(Path(folder_paths.get_output_directory()), latent_path or DEFAULT_CHAIN, segment)
    return load(path) if path else (None, None, None)


def state_token(home: Home) -> str:
    """Changes whenever a library, a preset or the learned weights change, so ComfyUI re-runs the node."""
    digest = hashlib.sha256()
    presets = sorted(home.presets_dir.rglob("*.orr")) if home.presets_dir.exists() else []  # @include
    for f in [*library_files(home.library_dir).values(), home.weights_path, *presets]:
        if f.exists():
            digest.update(f.as_posix().encode() + f.read_bytes())
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
        "preset": data.get("preset"),
        "edited": bool(data.get("edited")),
        "params": data.get("params") or {},
        "text": data.get("text"),
        "picks": data.get("picks", []),
        **({"segment": data["segment"], "chunks": data["chunks"]} if data.get("chunks") else {}),
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
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT", "INT", "INT", "LORA_STACK", "INT", "INT", "IMAGE", "AUDIO")
    RETURN_NAMES = ("text", "picks", "seed", "width", "height", "length", "lora_stack", "load_index", "save_index",
                    "previous", "previous_audio")
    OUTPUT_TOOLTIPS = ("", "", "", "From `: w…` in the template, else the @h3 ratio, else 1024.",
                       "From `: h…` in the template, else the @h3 ratio, else 1024.",
                       ("Frames at 24 fps for the MiniMax H3 nodes' length input: the sum of the SHOT "
                        "durations (in a reel: the chunk's, plus the pinned context from the second "
                        "chunk on), snapped up to H3's 17k+5 grid (124 without SHOTs)."),
                       ("The LORA: lines (global, plus the chunk's in a reel) as a LORA_STACK for any "
                        "loader with a lora_stack input (LoraManager, Efficiency, Easy-Use …)."),
                       "The segment: wire it into H3 Motion Context Load Latent's clip_index.",
                       "The segment + 1: wire it into H3 Motion Context Save Latent's clip_index.",
                       ("The last 3 s of the clip before this segment (H3 Motion Context's Chain Video), for the "
                        "Reference to Video node's ref_video; None in the first segment, which ref2va skips."),
                       "The soundtrack of `previous`, for the Reference to Video node's ref_video_audio.")
    DESCRIPTION = ("Expands an orrery template (text) or compiles a screenplay (h3-base, flat) "
                   "and outputs the picks that produced it.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {"multiline": True, "default": DEFAULT_TEMPLATE,
                                        "pysssss.autocomplete": False}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF,
                                 "control_after_generate": True}),
                "target": (TARGETS,),
            },
            "optional": {
                "preset": ([NO_PRESET, *list_presets(resolve_home())],),
                "home": ("STRING", {"default": ""}),
                "params": ("STRING", {"default": "", "tooltip": "The dials: JSON {binding: expression}, "
                                                                "set in the Prompt tab."}),
                "clip": ("CLIP", {"tooltip": "Optional: a text encoder that can write (Krea 2's Qwen3-VL) "
                                             "as the language model, in place of the one in orrery's settings."}),
                "segment": ("INT", {"default": 0, "min": 0, "max": 99999, "control_after_generate": True,
                                    "tooltip": "The reel's clip to write, from 0. With increment, every queued "
                                               "run plays the next clip; load_index and save_index drive H3 "
                                               "Motion Context. Plain screenplays ignore it."}),
                "latent_path": ("STRING", {"forceInput": True, "tooltip": (
                    "H3 Motion Context's latent_path (default h3_context): where the chain of clips lives. From "
                    "the second segment on the model watches the previous clip when it writes --…-- slots.")}),
            },
            "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    @classmethod
    def IS_CHANGED(cls, template, seed, target, preset=NO_PRESET, home="", params="", segment=0,
                   latent_path=DEFAULT_CHAIN, **_):
        h = resolve_home(home or None)
        chosen = load_preset(h, preset) if preset and preset != NO_PRESET else template
        return f"{seed}:{target}:{hash(chosen)}:{hash(params)}:{segment}:{latent_path}:{state_token(h)}"

    def run(self, template, seed, target, preset=NO_PRESET, home="", params="", segment=0, clip=None,
            latent_path=DEFAULT_CHAIN, unique_id=None, extra_pnginfo=None):
        stills, tail, audio = _previous(latent_path, segment)
        try:
            return (*run_prompt(template, seed, target, home, preset, linked_preset(extra_pnginfo, unique_id),
                                params, segment, clip, stills), tail, audio)
        except ReelEnd as end:
            try:
                from comfy_execution.graph_utils import ExecutionBlocker  # ComfyUI
            except ImportError:
                raise end from None
            print(f"[orrery] {end} The reel is done, so nothing downstream runs.")
            return tuple(ExecutionBlocker(None) for _ in self.RETURN_TYPES)


class OrreryLog:
    CATEGORY = "orrery"
    FUNCTION = "log"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = ("Saves images (PNG) or a video (MP4, e.g. from Create Video) with their picks "
                   "embedded and appends one line per output to galaxy.jsonl. For files saved by "
                   "another node, pass the path as media_path.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"picks": ("STRING", {"forceInput": True})},
            "optional": {
                "images": ("IMAGE",),
                "video": ("VIDEO", {"tooltip": "A video (with its audio), e.g. from Create Video; "
                                              "saved as MP4 in place of Save Video."}),
                "filename_prefix": ("STRING", {"default": "orrery"}),
                "media_path": ("STRING", {"default": ""}),
                "home": ("STRING", {"default": ""}),
            },
        }

    def log(self, picks, images=None, video=None, filename_prefix="orrery", media_path="", home=""):
        media, ui = [], []
        if video is not None:
            import folder_paths  # ComfyUI

            folder, name, counter, subfolder, _ = folder_paths.get_save_image_path(
                filename_prefix, folder_paths.get_output_directory())
            file = f"{name}_{counter:05}_.mp4"
            video.save_to(os.path.join(folder, file), metadata={"orrery": json.loads(picks)})
            media.append(os.path.join(folder, file))
            log_outputs(resolve_home(home or None), picks, media)
            return {"ui": {"images": [{"filename": file, "subfolder": subfolder, "type": "output"}],
                           "animated": (True,)}}
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
