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

from orrery import anchors, runs
from orrery import sweep as sweeps
from orrery.autolib import needs
from orrery.chain import DEFAULT_CHAIN, load, previous_clip
from orrery.comfy_film import OrreryContinue, OrreryFilm
from orrery.comfy_llm import ComfyBackend, can_write, llm_config
from orrery.continuum.grid import CONTEXT
from orrery.dsl import (
    MissingLibrary,
    bindings,
    expand,
    override,
    parse,
    strip_comments,
    wanted_libraries,
)
from orrery.h3 import DEFAULT_CONTEXT, compile_scene, image_slots, render_scene
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
from orrery.slots import SLOT, fill, keep_marks, put_back, request, rewrites_in, slots, write

TARGETS = ["text", "h3-base", "flat"]
NO_PRESET = "(none)"
DEFAULT_TEMPLATE = "$hero = __animal__\n$hero in a {misty|frozen:2|burning} forest"


H3_FPS = 24
H3_DEFAULT_LENGTH = 124  # the MiniMax H3 nodes' default: about 5 s


def h3_length(seconds: float) -> int:
    """Frames at 24 fps, snapped up to H3's 17k+5 grid like the MiniMax H3 nodes do."""
    frames = max(5, math.ceil(seconds * H3_FPS - 1e-4))
    return frames + (5 - frames) % 17


_MP = re.compile(r"(\d+(?:\.\d+)?)\s*mp", re.IGNORECASE)


def header_megapixels(template: str) -> float | None:
    """`0.6MP` in the @h3 line: the canvas area in megapixels."""
    first = next((line.strip() for line in template.splitlines() if line.strip()), "")
    header = re.match(r"@h3\s+\w+(.*)$", first, re.IGNORECASE)
    return next((float(m.group(1)) for t in header.group(1).split() if (m := _MP.fullmatch(t))), None) if header else None


def h3_canvas(ratio: str, megapixels: float | None = None) -> tuple[int, int] | None:
    """The MiniMax H3 canvas for a ratio: 768 short edge, 768×1344 area cap, multiples of 32. With
    megapixels, the area is that many pixels in the ratio's shape (square without a ratio)."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)", ratio or "")
    if (not m or not float(m.group(2))) and not megapixels:
        return None
    r = float(m.group(1)) / float(m.group(2)) if m and float(m.group(2)) else 1.0
    if megapixels:
        w, h = math.sqrt(megapixels * 1e6 * r), math.sqrt(megapixels * 1e6 / r)
        return max(32, round(w / 32) * 32), max(32, round(h / 32) * 32)
    w, h = (768 * r, 768) if r >= 1 else (768, 768 / r)
    if w * h > 768 * 1344:
        scale = math.sqrt(768 * 1344 / (w * h))
        w, h = w * scale, h * scale
    return max(32, round(w / 32) * 32), max(32, round(h / 32) * 32)


def fit_canvas(ratio: float, area: float, step: int = 32) -> tuple[int, int]:
    """Width and height in multiples of `step`, in `ratio`'s shape as closely as the grid allows, with an
    area within 10 % of `area`: a picture scaled to it is not stretched (H3 stretches a first frame)."""
    ideal, best = math.sqrt(area * ratio), None
    for k in range(max(1, int(ideal * 0.8 // step)), int(ideal * 1.25 // step) + 2):
        w = k * step
        h = max(step, round(w / ratio / step) * step)
        if 0.9 <= w * h / area <= 1.1:
            key = (round(abs(math.log(w / h / ratio)), 9), abs(math.log(w * h / area)))
            best = min(best, (key, (w, h))) if best else (key, (w, h))
    if best:
        return best[1]
    return max(step, round(ideal / step) * step), max(step, round(math.sqrt(area / ratio) / step) * step)


def _frame_area(template: str, ratio: float) -> float:
    """The canvas area for a frame-shaped clip: the header's megapixels, else H3's canvas in that shape
    (768 short edge, 768×1344 cap), else 1024²."""
    if megapixels := header_megapixels(template):
        return megapixels * 1e6
    first = next((line.strip() for line in template.splitlines() if line.strip()), "")
    if not re.match(r"@h3\b", first, re.IGNORECASE):
        return 1024 * 1024
    w, h = (768 * ratio, 768) if ratio >= 1 else (768, 768 / ratio)
    return min(w * h, 768 * 1344)


Size = tuple[int, int] | None  # (width, height) of a wired frame


def shape(template: str, frames: tuple[Size, Size] = (None, None)) -> tuple[int, int, int]:
    """width, height and H3 length for the node's outputs: `: w… h…` wins, then the shape of a wired frame
    (first, else last), then an @h3 ratio."""
    params = parse(template).params
    lines = [line.strip() for line in template.splitlines() if line.strip()]
    header = re.match(r"@h3\s+\w+(.*)$", lines[0], re.IGNORECASE) if lines else None
    ratio = next((t for t in header.group(1).split() if h3_canvas(t)), "") if header else ""
    canvas = h3_canvas(ratio, header_megapixels(template)) or (1024, 1024)
    frame = frames[0] or frames[1]
    if frame and not (params.width or params.height):
        canvas = fit_canvas(frame[0] / frame[1], _frame_area(template, frame[0] / frame[1]))
    seconds = sum(float(m.group(1)) for line in lines
                  if (m := re.match(r"SHOT\s+(\d+(?:\.\d+)?)\s*s\b", line, re.IGNORECASE)))
    return (params.width or canvas[0], params.height or canvas[1],
            h3_length(seconds) if seconds else H3_DEFAULT_LENGTH)


def _same_shape(a: tuple[int, int], b: tuple[int, int], tolerance: float = 0.02) -> bool:
    return abs(math.log((a[0] / a[1]) / (b[0] / b[1]))) <= tolerance


def frame_lint(template: str, sizes: tuple[Size, Size], width: int, height: int) -> list[dict]:
    """What the wired frames did to the size, and the mismatches H3 would stretch or crop."""
    first, last = sizes
    frame, which = (first, "first") if first else (last, "last")
    if not frame:
        return []
    out = []
    params = parse(template).params
    if params.width or params.height:
        if not _same_shape(frame, (width, height)):
            out.append({"severity": "warn", "message": (
                f"`: w… h…` makes the clip {width}×{height}, but the {which} frame is {frame[0]}×{frame[1]}: H3 "
                f"{'stretches' if which == 'first' else 'crops'} it. Leave the size out and orrery takes it from the frame.")})
    else:
        lines = [line.strip() for line in template.splitlines() if line.strip()]
        header = re.match(r"@h3\s+\w+(.*)$", lines[0], re.IGNORECASE) if lines else None
        ratio = next((t for t in header.group(1).split() if h3_canvas(t)), "") if header else ""
        written = h3_canvas(ratio) if ratio else None
        if written and not _same_shape(written, frame):
            out.append({"severity": "info", "message": (
                f"The {which} frame is {frame[0]}×{frame[1]}, so the clip is {width}×{height} in its shape; the "
                f"header's {ratio} is set aside (H3 would stretch the frame into it).")})
    if first and last and not _same_shape(first, last):
        out.append({"severity": "warn", "message": (
            f"The last frame is {last[0]}×{last[1]}, the first {first[0]}×{first[1]}: H3 crops the last frame to the "
            "first's shape. Use two pictures of one shape.")})
    return out


def _size(image) -> Size:
    """(width, height) of an IMAGE batch [frames, height, width, channels], or None."""
    return None if image is None else (int(image.shape[2]), int(image.shape[1]))


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


def _passages(result, target: str) -> list[tuple[str, str, object]]:
    """What `> instructions` ask to rewrite: (instruction, passage, put the rewrite in its place).
    A text prompt is one passage; in a screenplay, each prose line of a shot in scope, never dialogue."""
    if target == "text":
        if not result.enhance:
            return []
        return [(result.enhance, result.text, lambda new: setattr(result, "text", new))]
    out = []
    for shot in result.scene.shots:
        instruction = shot.enhance or result.scene.enhance
        for i, item in enumerate(shot.items if instruction else []):
            if isinstance(item, str) and item.strip():
                out.append((instruction, item, lambda new, items=shot.items, i=i: items.__setitem__(i, new)))
    return out


def run_prompt(template: str, seed: int, target: str, home: str = "",
               preset: str = NO_PRESET, linked: str | None = None,
               params: str = "", segment: int = 0, clip=None,
               frames=None, packed: bool = False,
               wired: int | None = None, chain: str = DEFAULT_CHAIN,
               keep: bool = False, sweep: str = "",
               continued: bool = False, sizes: tuple[Size, Size] = (None, None)) -> tuple[str, str, int, int, int, int, list, int, int]:
    """`frames`: the previous clip's stills, which the model sees when it writes `--…--` slots.
    `packed`: Orrery Refs routes the images per clip; `wired`: the reference images Reference to
    Video has (both from the graph, see `wiring`). `chain`: the Motion Context chain SEND: reads;
    `keep`: Orrery Refs' keep_sent, so sent images with a stored anchor are held from segment 0.
    `sweep`: "run|galaxy folder", set by Generate for each run of a LoRA sweep (see orrery.sweep).
    `continued`: an Orrery Continue reads the picks, which pins 22 frames whatever `context:` says.
    `sizes`: (width, height) of the frames wired into first_frame and last_frame, or None."""
    h = resolve_home(home or None)
    if preset and preset != NO_PRESET:
        template, linked = load_preset(h, preset), preset
    if linked and not preset_exists(h, linked):
        linked = None
    known = {name for name, _ in bindings(template)}
    dials = {k: v for k, v in dial_values(params).items() if k in known}
    source = strip_comments(resolve_includes(h, override(template, dials)))  # the hash keeps the comments
    plan, sweep_picks, sweep_data, folder = sweeps.runs(source), [], None, ""
    if plan:  # a LoRA sweep: this queue item is one of its runs (the first, from ComfyUI's own Run)
        index, _, folder = (sweep or "").partition("|")
        i = int(index) if index.strip().isdigit() else 0
        if i >= len(plan):
            raise ValueError(f"LoRA sweep run {i} does not exist: this template sweeps {len(plan)} runs "
                             f"({sweeps.formula(source)}).")
        sweep_picks, sweep_data = sweeps.picks(source, plan[i]), {"run": i, "runs": len(plan)}
        source_sweep, source = source, sweeps.apply(source, plan[i])

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
            result = compile_scene(source, seed, h.libraries(), h.weights(), target=target, segment=segment,
                                   packed=packed, held=anchors.stored(h) if keep else frozenset())
            lint = [{"severity": i.severity, "message": i.message} for i in result.lint]
            needed = len(result.refs) if packed else max(image_slots(result.scene), default=0)
            if wired is not None and wired < needed:
                lint.append({"severity": "warn", "message": f"This clip uses {needed} reference images, but Reference "
                                                            f"to Video has {wired} wired: <Picture {wired + 1}> and up "
                                                            "point at nothing."})
    except MissingLibrary as err:
        raise ValueError(f"{err}, or pick a language model in orrery's settings (the gear in the node) "
                         "and it is created when the node runs") from err
    todo = slots(result.text)
    passages = _passages(result, target)
    enhanced: list[dict] = []
    if passages and wanted:
        lint.append({"severity": "info", "message": "The > enhance instructions run on the next run; this one "
                                                    "writes the missing libraries."})
    elif passages and backend is None:
        backend = llm_for(h, clip, seed=seed)
        if backend is None:
            lint.append({"severity": "warn", "message": "> enhance needs a language model: pick one in orrery's "
                                                        "settings (the gear in the node); the prompt stays as written."})
    if (todo or (passages and backend is not None)) and not wanted:
        marked = [keep_marks(passage) for _, passage, _ in passages] if backend is not None else []
        prompt = request([], todo, result.text, _count(frames),
                         [(instruction, text) for (instruction, _, _), (text, _) in zip(passages, marked, strict=False)])
        try:
            reply = backend.complete(prompt, images=frames)
            texts, _ = write(h, [], todo, reply, backend)
            for (instruction, before, place), (_, kept), new in zip(passages, marked, rewrites_in(reply, len(marked)),
                                                                    strict=False):
                after = put_back(new, kept) if new else None
                if after is None:
                    lint.append({"severity": "warn", "message": f"> {instruction}: the language model left a passage "
                                                                "as it was."})
                    continue
                place(after)
                enhanced.append({"instruction": instruction, "before": before, "after": after})
            if enhanced and target != "text":
                result.text = render_scene(result.scene, target, [])
        except InvalidProposal as err:
            lint.append({"severity": "warn", "message": f"The language model wrote no slots or rewrites ({err})."})
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
    if plan and not sweep:
        lint.append({"severity": "info", "message": f"LoRA sweep: {len(plan)} runs ({sweeps.formula(source_sweep)}); "
                                                     "Generate runs them all, Run takes the first."})
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
        "picks": [{"label": p.label, "value": p.value, "keys": list(p.keys)} for p in result.picks] + sweep_picks,
        **({"sweep": sweep_data} if sweep_data else {}),
        **({"folder": folder.strip()} if sweep_data and folder.strip() else {}),
        "lint": lint,
        **({"refs": result.refs} if target != "text" and packed else {}),
        **({"sends": {"chain": chain, "home": str(h.root), "slots": result.send_slots,
                      "ready": {str(k): v for k, v in result.sends.items()}}}
           if target != "text" and result.send_slots else {}),
        **({"enhanced": enhanced} if enhanced else {}),
    }
    width, height, length = shape(source, sizes)
    lint += frame_lint(source, sizes, width, height)
    data["megapixels"] = header_megapixels(source) or round(width * height / 1e6, 3)
    if target != "text":
        if result.scene.shots:
            length = h3_length(result.scene.duration)
        if result.chunks:
            data["segment"], data["chunks"], data["segments"] = result.segment, result.chunks, result.segments
            context = DEFAULT_CONTEXT if result.scene.context is None else result.scene.context
            data["chain"], data["context"] = chain, context
            if continued and context != CONTEXT:
                off = abs(context - CONTEXT)
                data["lint"].append({"severity": "warn", "message": (
                    f"context: {context}, but Orrery Continue pins {CONTEXT} frames all the same, so from the second "
                    f"segment on each clip runs {off} frames ({off / 24:.1f} s) "
                    f"{'longer' if context > CONTEXT else 'shorter'} than its shots. Write context: {CONTEXT}, or "
                    "leave the line out; H3 Motion Context takes other lengths.")})
                print(f"[orrery] warn: {data['lint'][-1]['message']}")
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


def _announce(unique_id, segment: int, end: bool = False) -> None:
    """Tell the node's app which reel segment runs (or that the reel is over), so Generate can show it."""
    if unique_id is None:
        return
    try:
        from server import PromptServer  # ComfyUI
    except ImportError:
        return
    PromptServer.instance.send_sync("orrery.segment", {"node": str(unique_id), "prompt_id": runs.current_prompt(),
                                                       "segment": segment, "end": end})


def state_token(home: Home) -> str:
    """Changes whenever a library, a preset or the learned weights change, so ComfyUI re-runs the node."""
    digest = hashlib.sha256()
    presets = sorted(home.presets_dir.rglob("*.orr")) if home.presets_dir.exists() else []  # @include
    for f in [*library_files(home.library_dir).values(), home.weights_path, *presets]:
        if f.exists():
            digest.update(f.as_posix().encode() + f.read_bytes())
    return digest.hexdigest()[:16]


def _galaxy_folder(name) -> str:
    """A sweep's galaxy folder, when it is a valid one."""
    from orrery.galaxy import clean_folder

    try:
        return clean_folder(name) if name else ""
    except (ValueError, TypeError):
        return ""


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
        **({"folder": folder} if (folder := _galaxy_folder(data.get("folder"))) else {}),
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
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT", "INT", "INT", "LORA_STACK", "INT", "INT", "IMAGE", "AUDIO",
                    "FLOAT")
    RETURN_NAMES = ("text", "picks", "seed", "width", "height", "length", "lora_stack", "load_index", "save_index",
                    "previous", "previous_audio", "megapixels")
    OUTPUT_TOOLTIPS = ("", "", "", "From `: w…` in the template, else the @h3 ratio, else 1024.",
                       "From `: h…` in the template, else the @h3 ratio, else 1024.",
                       ("Frames at 24 fps for the MiniMax H3 nodes' length input: the sum of the SHOT "
                        "durations (in a reel: the chunk's, plus the pinned context from the second "
                        "chunk on), snapped up to H3's 17k+5 grid (124 without SHOTs)."),
                       ("The LORA: lines (global, plus the chunk's in a reel) as a LORA_STACK for any "
                        "loader with a lora_stack input (LoraManager, Efficiency, Easy-Use …)."),
                       ("The segment, for H3 Motion Context only: wire it into its Load Latent's clip_index "
                        "(Orrery Continue reads the segment from the picks)."),
                       "The segment + 1, for H3 Motion Context only: wire it into its Save Latent's clip_index.",
                       ("The last 3 s of the clip before this segment (from Orrery Film or H3 Motion Context's "
                        "Chain Video), for the Reference to Video node's ref_video; None in the first segment, "
                        "which ref2va skips."),
                       "The soundtrack of `previous`, for the Reference to Video node's ref_video_audio.",
                       ("The canvas area: `0.6MP` from the @h3 line, else width × height, for resolution and "
                        "scale nodes that take megapixels."))
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
                                               "run plays the next clip, which Orrery Continue (or H3 Motion "
                                               "Context, through load_index and save_index) chains to the one "
                                               "before. Plain screenplays ignore it."}),
                "first_frame": ("IMAGE", {"tooltip": (
                    "Optional: the picture the clip starts on (wire it into the H3 node's first_frame too). Width and "
                    "height then take its shape at the header's megapixels, so H3 does not stretch it.")}),
                "last_frame": ("IMAGE", {"tooltip": (
                    "Optional: the picture the clip ends on (and the H3 node's last_frame). Without a first frame, width "
                    "and height take its shape, so H3 does not crop it.")}),
                "latent_path": ("STRING", {"forceInput": True, "tooltip": (
                    "Where the reel's clips live, under ComfyUI's output (default h3_context; H3 Motion "
                    "Context's latent_path): Orrery Film keeps them in its orrery_film folder, Chain Video in "
                    "chain_video. From the second segment on the model watches the previous clip when it writes "
                    "--…-- slots.")}),
                "sweep": ("STRING", {"default": "", "tooltip": (
                    "Set by Generate for each run of a LoRA sweep (run|galaxy folder); empty runs the first.")}),
            },
            "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO", "prompt": "PROMPT"},
        }

    @classmethod
    def IS_CHANGED(cls, template, seed, target, preset=NO_PRESET, home="", params="", segment=0,
                   latent_path=DEFAULT_CHAIN, sweep="", **_):
        h = resolve_home(home or None)
        chosen = load_preset(h, preset) if preset and preset != NO_PRESET else template
        return f"{seed}:{target}:{hash(chosen)}:{hash(params)}:{segment}:{latent_path}:{sweep}:{state_token(h)}"

    def run(self, template, seed, target, preset=NO_PRESET, home="", params="", segment=0, clip=None,
            latent_path=DEFAULT_CHAIN, sweep="", unique_id=None, extra_pnginfo=None, prompt=None,
            first_frame=None, last_frame=None):
        stills, tail, audio = _previous(latent_path, segment)
        packed, wired, keep = wiring(prompt, unique_id)
        try:
            outputs = run_prompt(template, seed, target, home, preset, linked_preset(extra_pnginfo, unique_id),
                                 params, segment, clip, stills, packed, wired, latent_path or DEFAULT_CHAIN, keep,
                                 sweep, continued(prompt, unique_id), (_size(first_frame), _size(last_frame)))
            data = json.loads(outputs[1])
            if "sends" in data and not packed:
                raise ValueError("This reel SENDs frames as reference images, which Orrery Refs fetches: wire this "
                                 "node's picks into an Orrery Refs, and its ref outputs into Reference to Video.")
            if (prompt_id := runs.current_prompt()) and unique_id is not None:
                runs.remember(prompt_id, unique_id, outputs[1])  # for Generate: Save nodes log to the galaxy
            if "segments" in data:  # a reel
                _announce(unique_id, data["segment"])
            return (*outputs, tail, audio, data["megapixels"])
        except ReelEnd as end:
            try:
                from comfy_execution.graph_utils import ExecutionBlocker  # ComfyUI
            except ImportError:
                raise end from None
            print(f"[orrery] {end} The reel is done, so nothing downstream runs.")
            _announce(unique_id, segment, end=True)
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


REF2VA = "MiniMaxH3ReferenceToVideo"
PREVIEW_HEIGHT = 512
LABEL_SIZE = 40


def preview_frames(labelled: list[tuple[str, object]]):
    """Every frame of each (label, IMAGE batch) as one float array for a Preview Image: scaled to one
    height, the label in white with a black edge in the corner, centred on neutral grey at the widest
    width. Without any, one grey frame that says so."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default(size=LABEL_SIZE)
    shots = []
    for label, batch in labelled or [("no refs", np.full((1, PREVIEW_HEIGHT, PREVIEW_HEIGHT, 3), 0.5, np.float32))]:
        array = batch.cpu().numpy() if hasattr(batch, "cpu") else np.asarray(batch)
        for frame in array:
            pic = Image.fromarray(np.clip(frame[..., :3] * 255.0 + 0.5, 0, 255).astype(np.uint8))
            pic = pic.resize((max(1, round(pic.width * PREVIEW_HEIGHT / pic.height)), PREVIEW_HEIGHT), Image.BILINEAR)
            ImageDraw.Draw(pic).text((14, 10), label, font=font, fill="white", stroke_width=4, stroke_fill="black")
            shots.append(np.asarray(pic, dtype=np.float32) / 255.0)
    widest = max(shot.shape[1] for shot in shots)
    out = np.full((len(shots), PREVIEW_HEIGHT, widest, 3), 0.5, dtype=np.float32)
    for i, shot in enumerate(shots):
        x = (widest - shot.shape[1]) // 2
        out[i, :, x:x + shot.shape[1]] = shot
    return out


def stack_preview(labelled: list[tuple[str, object]]):
    """preview_frames as an IMAGE batch. ComfyUI only (torch)."""
    import torch

    return torch.from_numpy(preview_frames(labelled))


def to_image(array):
    """A float array (frames, height, width, 3) as an IMAGE batch. ComfyUI only (torch)."""
    import torch

    return torch.from_numpy(array)


def continued(prompt: dict | None, unique_id) -> bool:
    """Whether an Orrery Continue reads this node's picks (then orrery continues the reel itself)."""
    if not prompt or unique_id is None:
        return False
    return any(n.get("class_type") == "OrreryContinue" and n.get("inputs", {}).get("picks") == [str(unique_id), 1]
               for n in prompt.values())


def wiring(prompt: dict | None, unique_id) -> tuple[bool, int | None, bool]:
    """What the node's graph says (R2): whether an Orrery Refs reads its picks (then the images are
    packed per clip), how many reference images the Reference to Video node its text reaches
    (directly or through a few text nodes) has wired (None when there is none), and whether that
    Orrery Refs has keep_sent on."""
    if not prompt or unique_id is None:
        return False, None, False
    uid = str(unique_id)
    link = lambda v: (str(v[0]), v[1]) if isinstance(v, list) and len(v) == 2 else None
    readers = [n for n in prompt.values()
               if n.get("class_type") == "OrreryRefs" and link(n.get("inputs", {}).get("picks")) == (uid, 1)]
    packed, keep = bool(readers), any(n.get("inputs", {}).get("keep_sent") is True for n in readers)
    reach = {(uid, 0)}
    for _ in range(3):  # through Text Concatenate and friends
        reach |= {(str(nid), i) for nid, n in prompt.items() if n.get("class_type") != REF2VA
                  for v in n.get("inputs", {}).values() if link(v) in reach for i in range(4)}
    wired = [sum(1 for k, v in n["inputs"].items() if "ref_image" in k and link(v))
             for n in prompt.values() if n.get("class_type") == REF2VA and link(n.get("inputs", {}).get("prompt")) in reach]
    return packed, (max(wired) if wired else None), keep


class OrreryRefs:
    """Hands Reference to Video only the reference images the current clip's CAST uses, packed in
    order, so a reel's chunks don't all see every image. Orrery Prompt notices it and renumbers
    <Picture N> to match. Images a SEND: line fills come from the sending clip in the chain, and are
    kept as that image's anchor; with keep_sent on they come from the anchor instead."""

    CATEGORY = "orrery"
    FUNCTION = "route"
    SLOTS = 9
    RETURN_TYPES = ("IMAGE",) * (SLOTS + 1)
    RETURN_NAMES = (*(f"ref_{i}" for i in range(1, SLOTS + 1)), "preview")
    OUTPUT_TOOLTIPS = ("Wire ref_1 into Reference to Video ref_image_0, ref_2 into ref_image_1, and so on.",
                       *("",) * (SLOTS - 1),
                       ("Every image this clip gets, labelled with its ref, as one batch for a Preview Image (grey when "
                        "there is none). Preview here, not on the ref_N that go into Reference to Video: an empty one "
                        "is None there."))
    DESCRIPTION = ("Routes the reference images per reel clip: wire every image as image_N (N as in the CAST's "
                   "(image N)) and the Orrery Prompt's picks; the clip's images come out packed as ref_1, ref_2 …, "
                   "and all of them together on preview, for a Preview Image.")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"picks": ("STRING", {"forceInput": True})},
                "optional": {**{f"image_{i}": ("IMAGE",) for i in range(1, cls.SLOTS + 1)},
                             "keep_sent": ("BOOLEAN", {"default": False, "tooltip": (
                                 "On: every SEND: image with a stored anchor (the frames last fetched for it) uses that "
                                 "anchor from segment 0 and for the whole run, so a character you liked stays. "
                                 "Off: fresh frames from this run's chain, which replace the anchors.")})},
                "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"}}

    @classmethod
    def IS_CHANGED(cls, **_):
        """Always run: the chain behind a SEND: changes while the picks stay the same (a reel rendered again
        from Restart), and a cached output would hand on an older run's frames."""
        return float("NaN")

    def route(self, picks, prompt=None, unique_id=None, keep_sent=False, **images):
        data = json.loads(picks or "{}")
        refs, sends = data.get("refs"), data.get("sends") or {}
        clash = sorted(n for n in sends.get("slots", []) if images.get(f"image_{n}") is not None)
        if clash:
            raise ValueError(f"image {clash[0]} is wired into Orrery Refs and also filled by a SEND: line; "
                             "unwire it, or send to an image nothing is wired into.")
        if refs is None:  # nothing packed: pass the images through as wired
            order = [images.get(f"image_{i}") for i in range(1, self.SLOTS + 1)]
        else:
            ready = sends.get("ready", {})
            home = Home(Path(sends["home"])) if sends.get("home") else resolve_home(None)
            for n in refs:
                if str(n) not in ready:
                    continue
                if ready[str(n)].get("held"):
                    held = anchors.load(home, n)
                    if held is None:
                        raise ValueError(f"image {n} is held (keep_sent), but it has no stored anchor: switch keep_sent "
                                         "off for a run that sends it, then on again.")
                    images[f"image_{n}"] = to_image(held)
                else:
                    images[f"image_{n}"] = self._sent(n, ready[str(n)], sends.get("chain") or DEFAULT_CHAIN)
                    anchors.save(home, n, images[f"image_{n}"])
            missing = [f"image_{n}" for n in refs if images.get(f"image_{n}") is None]
            if missing:
                raise ValueError(f"This clip's CAST uses {', '.join(missing)}, but nothing is wired into it.")
            order = [images[f"image_{n}"] for n in refs]
            self._warn_batches(order, prompt, unique_id)
        out = order[:self.SLOTS] + [None] * (self.SLOTS - len(order))
        try:
            preview = stack_preview([(f"ref_{k + 1}", img) for k, img in enumerate(out) if img is not None])
        except ImportError:  # outside ComfyUI
            preview = None
        return (*(self._blocked(v, self._readers(prompt, unique_id, k)) for k, v in enumerate(out)),
                self._blocked(preview, self._readers(prompt, unique_id, self.SLOTS)))

    @staticmethod
    def _readers(prompt, unique_id, k: int) -> list[str]:
        """The class types of the nodes that read output k, from the graph."""
        if not prompt or unique_id is None:
            return []
        link = lambda v: (str(v[0]), v[1]) if isinstance(v, list) and len(v) == 2 else None
        return [n.get("class_type") for n in prompt.values()
                if (str(unique_id), k) in {link(v) for v in n.get("inputs", {}).values()}]

    @staticmethod
    def _blocked(value, readers: list[str]):
        """An empty ref that only nodes other than Reference to Video read (a preview, say) is blocked, so
        they skip this clip instead of failing on None; Reference to Video itself skips None."""
        if value is not None or not readers or REF2VA in readers:
            return value
        try:
            from comfy_execution.graph_utils import ExecutionBlocker  # ComfyUI
        except ImportError:
            return None
        return ExecutionBlocker(None)

    @staticmethod
    def _sent(n: int, send: dict, latent_path: str):
        """The frames a SEND: line names, from the sending segment's clip in the chain."""
        import folder_paths  # ComfyUI

        from orrery import chain

        segment = send["segment"]
        path = chain.clip_file(Path(folder_paths.get_output_directory()), latent_path, segment)
        if path is None:
            raise ValueError(f"image {n} is sent from segment {segment}, but the chain {latent_path!r} has no clip for "
                             f"segment {segment}: render the reel from that chunk on, or check the Orrery Prompt's "
                             "latent_path.")
        batch, dropped = chain.frames(path, send["frames"])
        if dropped:
            many = len(dropped) > 1
            print(f"[orrery] SEND to image {n}: frame{'s' if many else ''} {', '.join(map(str, dropped))} "
                  f"{'are' if many else 'is'} not in segment {segment}'s clip, so "
                  f"{'they are' if many else 'it is'} left out.")
        return batch

    @classmethod
    def _warn_batches(cls, order: list, prompt, unique_id) -> None:
        """Reference to Video reads the first image of each reference only: say so when a batch goes there."""
        for k, img in enumerate(order):
            if img is None or getattr(img, "shape", (1,))[0] < 2:
                continue
            if REF2VA in cls._readers(prompt, unique_id, k):
                print(f"[orrery] ref_{k + 1} carries {img.shape[0]} frames, but Reference to Video reads only the first "
                      "image of a reference; send several stills to several images for ref2va.")


NODE_CLASS_MAPPINGS = {"OrreryPrompt": OrreryPrompt, "OrreryLog": OrreryLog, "OrreryRefs": OrreryRefs,
                       "OrreryContinue": OrreryContinue, "OrreryFilm": OrreryFilm}
NODE_DISPLAY_NAME_MAPPINGS = {"OrreryPrompt": "Orrery Prompt", "OrreryLog": "Orrery Log", "OrreryRefs": "Orrery Refs",
                              "OrreryContinue": "Orrery Continue", "OrreryFilm": "Orrery Film"}
