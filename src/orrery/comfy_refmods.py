"""Orrery RefMods: the clip's RefMods on its conditioning, each with its strength and its start.

The compiler lists them in the picks (orrery.h3.clip_refmods). This node loads them with the
ComfyUI-H3RefMods pack and adds one block per RefMod to the conditioning's `minimax_refs`, as the
pack's Apply H3 RefMod does, marked with its strength for orrery.refbias. A RefMod that waits
(`from 35%`) stays out of the conditioning for that share of sampling: the node splits the
conditioning into timestep ranges, as ConditioningSetTimestepRange does, so each range carries the
RefMods that have started by then. A RefMod that a SEND: line makes from frames of the reel (#13) is
built here, without the pack: the frames come from the chain and are encoded the way Reference to
Video encodes a video reference, then kept for the run. ComfyUI only.
"""

import json
import sys
from itertools import pairwise
from pathlib import Path

from orrery.refbias import KEY, PICTURE

PACK = "ComfyUI-H3RefMods"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "refmods"  # RefMods that ship with orrery
MAX_FRAMES = 73  # a sent RefMod's frames at most: 22 latents, about 23K tokens on the 768 canvas
_BUILT: dict[tuple, dict] = {}  # sent RefMods already encoded: (clip, its mtime, frames, step) → block


def _pack():
    """The pack's loader module, as ComfyUI imported it."""
    for name, module in list(sys.modules.items()):
        if name.endswith(".nodes.refmod_loader") and hasattr(module, "_load_mod") and hasattr(module, "_list_mod_names"):
            return module
    raise ValueError(f"Orrery RefMods loads RefMods with the {PACK} pack (github.com/FranckyB/{PACK}): install "
                     "it in custom_nodes and restart ComfyUI.")


def pack_installed() -> bool:
    """Whether ComfyUI's custom_nodes hold the RefMod pack (it may load after orrery, so look on disk)."""
    try:
        import folder_paths  # ComfyUI
    except ImportError:
        return False
    return any(any(Path(base).glob("*/nodes/refmod_loader.py")) for base in folder_paths.get_folder_paths("custom_nodes"))


def refmod_names() -> list[str]:
    """The RefMods in models/refmods as a CAST names them (`NAME` for `NAME_Video`), for the editor's
    completion; empty outside ComfyUI or before the pack has registered its folder."""
    try:
        import folder_paths  # ComfyUI
        files = folder_paths.get_filename_list("refmods")
    except Exception:  # noqa: BLE001 - not inside ComfyUI, or no refmods folder
        return []
    names = set()
    for f in files:
        stem = f.replace("\\", "/")
        if stem.endswith(".safetensors") and not stem.endswith("_Audio.safetensors"):
            names.add(stem.removesuffix(".safetensors").removesuffix("_Video"))
    return sorted(names, key=str.lower)


def shipped() -> list[str]:
    """The RefMods that ship with orrery (examples/refmods), by name."""
    return sorted(p.stem for p in EXAMPLES.glob("*.safetensors")) if EXAMPLES.is_dir() else []


def register_examples() -> None:
    """Lists orrery's own RefMods among ComfyUI's refmods, for the completion. The pack reads only
    models/refmods, so Orrery RefMods loads these itself."""
    try:
        import folder_paths  # ComfyUI
    except ImportError:  # not inside ComfyUI
        return
    folder_paths.add_model_folder_path("refmods", str(EXAMPLES))


def resolve(name: str, available: list[str]) -> str:
    """The pack's name for a CAST's `refmod NAME`: the name itself, or its `_Video` half."""
    for candidate in (name, f"{name}_Video"):
        if candidate in available:
            return candidate
    near = sorted(n for n in available if name.lower() in n.lower())[:5]
    raise ValueError(f"RefMod {name!r} is not in models/refmods"
                     + (f" (close: {', '.join(near)})." if near else ".")
                     + " Create it with Create H3 RefMod From Folder or From Inputs, or fix the name in the CAST.")


def schedule(refmods: list[dict], images: list[dict] = ()) -> list[tuple[float, float, list[dict]]]:
    """(start, end, RefMods active) for each share of sampling, from 0 to 1. A range starts where a
    RefMod or a picture starts or stops; one that waits until 100% never runs."""
    waits = [*refmods, *images]
    edges = sorted({0.0, 1.0} | {_share(r["from"]) for r in waits} | {_share(r.get("to", 1.0)) for r in waits})
    return [(lo, hi, [r for r in refmods if _share(r["from"]) <= lo and _share(r.get("to", 1.0)) >= hi])
            for lo, hi in pairwise(edges)]


def _share(value) -> float:
    return min(1.0, max(0.0, float(value)))


def video_frames(n: int) -> int:
    """How many frames a sent RefMod of n frames is encoded from: the next count on the grid H3's video VAE
    encodes (17k+5 frames to 5k+2 latents), so none is lost, and at most MAX_FRAMES."""
    if n >= MAX_FRAMES:
        return MAX_FRAMES
    return n + (5 - n) % 17


def encode(frames, vae) -> dict:
    """A ref block from frames [N, H, W, 3] in 0..1, as Reference to Video makes one: on its 768 canvas
    (never larger than the frames), a single frame as an image, more as a video of 17k+5 frames (the last
    one held to fill up, more than MAX_FRAMES spread out evenly)."""
    import torch
    from comfy_extras.nodes_minimax_h3 import _resize, adapt_canvas

    n, h, w = frames.shape[0], frames.shape[1], frames.shape[2]
    cw, ch = adapt_canvas(w, h)
    if w * h < cw * ch:
        cw, ch = max(32, round(w / 32) * 32), max(32, round(h / 32) * 32)
    if n == 1:
        return {"kind": "image", "latent_h": ch // 16, "latent_w": cw // 16,
                "latent": vae.encode(_resize(frames, cw, ch, "disabled"))}
    count = video_frames(n)
    if n > count:
        frames = frames[torch.linspace(0, n - 1, count).round().long()]
    elif n < count:
        frames = torch.cat([frames, frames[-1:].expand(count - n, -1, -1, -1)])
    z = vae.encode(_resize(frames, cw, ch, "disabled"))
    return {"kind": "video", "latent_t": z.shape[2], "latent_h": ch // 16, "latent_w": cw // 16,
            "ref_audio_t": 0, "latent": z, "audio_latent": None}


def sent_block(name: str, sent: dict, latent_path: str, vae) -> dict:
    """The block of a RefMod that a SEND: line makes from frames of the sending segment's clip, encoded
    once and kept for the run (a new take of that clip encodes it again)."""
    import folder_paths  # ComfyUI

    from orrery import chain

    segment, step = sent["segment"], int(sent.get("step", 1))
    path = chain.clip_file(Path(folder_paths.get_output_directory()), latent_path, segment)
    if path is None:
        raise ValueError(f"refmod {name} is sent from clip {segment + 1}, but the chain {latent_path!r} has no clip "
                         f"{segment + 1}: render the reel from that scene on, or check the Orrery Prompt's "
                         "latent_path.")
    key = (str(path), Path(path).stat().st_mtime_ns, json.dumps(sent["frames"]), step)
    if key not in _BUILT:
        if vae is None:
            raise ValueError(f"refmod {name} is made from frames of the reel, so Orrery RefMods needs the VAE: wire "
                             "the H3 video VAE (the one Reference to Video takes) into its vae input.")
        frames, dropped = chain.frames(path, sent["frames"], step)
        if dropped:
            print(f"[orrery] REMEMBER as refmod {name}: frames {', '.join(map(str, dropped))} are not in clip "
                  f"{segment + 1}, so they are left out.")
        _BUILT[key] = encode(frames, vae)
        print(f"[orrery] Orrery RefMods: built refmod {name} from {frames.shape[0]} frames of clip {segment + 1}")
    return _BUILT[key]


def _ranged(conditioning, blocks: list[dict], lo: float, hi: float, images: dict | None = None) -> list:
    """The conditioning with `blocks` added to its refs, for sampling from `lo` to `hi` (within any range
    an entry already has); entries that leave nothing of the range are dropped. `images`: {k: (strength,
    from, to)} for the k-th picture Reference to Video put on the conditioning, marked for orrery.refbias
    when its strength is not 1. A picture that waits past `lo`, stops before `hi` or is at 0 stays at 0
    for this range: refbias then hides its latents and the vision block its text encoder left in the text,
    which would stay if the picture left the refs (and the target would move between steps)."""
    out = []
    for tensor, meta in conditioning:
        meta = dict(meta)
        start, end = max(lo, meta.get("start_percent", 0.0)), min(hi, meta.get("end_percent", 1.0))
        if start >= end:
            continue
        refs, k = [], 0
        for block in meta.get("minimax_refs", []):
            if images and block.get("kind") == "image":
                k += 1
                strength, wait, until = images.get(k, (1.0, 0.0, 1.0))
                if wait > lo or until < hi:
                    strength = 0.0
                if strength != 1.0:
                    block = {**block, KEY: strength, PICTURE: k}
            refs.append(block)
        if refs or blocks or "minimax_refs" in meta:
            meta["minimax_refs"] = [*refs, *blocks]
        if (start, end) != (0.0, 1.0):
            meta["start_percent"], meta["end_percent"] = start, end
        out.append([tensor, meta])
    return out


def _span(dial: dict) -> str:
    """` from 10% to 50%` for the console; `to` only when it stops before the end."""
    end = float(dial.get("to", 1.0))
    return f" from {float(dial['from']) * 100:g}%" + (f" to {end * 100:g}%" if end < 1.0 else "")


def tokens(block: dict) -> int:
    """The tokens a video block packs: 2×2 latent patches per frame."""
    return int(block.get("latent_t", 1)) * (int(block.get("latent_h", 0)) // 2) * (int(block.get("latent_w", 0)) // 2)


class OrreryRefMods:
    """Puts the clip's RefMods (from the Orrery Prompt's picks) on the conditioning."""

    CATEGORY = "orrery"
    FUNCTION = "apply"
    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    DESCRIPTION = ("Loads the RefMods the clip's CAST names (refmod NAME) and puts them on the conditioning, with "
                   "their dials and a picture's (SET: @JINX(0.5, 35%), SET: image_1(0.5)): wire Reference to Video's "
                   "conditioning and the Orrery Prompt's picks in, and the output on to Orrery Continue or the "
                   "guider. RefMods from files need the ComfyUI-H3RefMods pack; one a REMEMBER: line makes from the "
                   "reel's frames (REMEMBER: every 10th frame as refmod NAME) needs the H3 video VAE in vae.")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"conditioning": ("CONDITIONING",),
                             "picks": ("STRING", {"forceInput": True})},
                "optional": {"vae": ("VAE", {"tooltip": "The H3 video VAE (Reference to Video's): it encodes the "
                                                        "RefMods a REMEMBER: line makes from the reel's frames."})}}

    @classmethod
    def IS_CHANGED(cls, **_):
        """Always run: the chain behind a sent RefMod changes while the picks stay the same (a segment rendered
        again), and a cached output would bring back an older take; the encoded blocks are kept all the same."""
        return float("NaN")

    def apply(self, conditioning, picks, vae=None):
        data = json.loads(picks or "{}")
        refmods, images = data.get("refmods") or [], data.get("images") or []
        if not refmods and not images:
            return (conditioning,)
        blocks: dict[str, dict] = {}
        files = [r for r in refmods if float(r["strength"]) > 0.0 and "sent" not in r]  # at 0 a RefMod is left out
        if files:
            pack = _pack()
            available, ours = pack._list_mod_names(), shipped()
            for r in files:
                name = resolve(r["name"], [*available, *ours])
                mod = pack._load_mod(name) if name in available else pack.H3RefMod.load(str(EXAMPLES / name), device="cpu")
                block = mod.ref_block(1.0, curve=None)
                if block is not None:
                    blocks[r["name"]] = {**block, KEY: float(r["strength"])}
        for r in refmods:
            if float(r["strength"]) > 0.0 and "sent" in r:
                block = sent_block(r["name"], r["sent"], data.get("chain") or "h3_context", vae)
                blocks[r["name"]] = {**block, KEY: float(r["strength"])}
        pictures = {int(i["ref"]): (float(i["strength"]), float(i["from"]), float(i.get("to", 1.0))) for i in images}
        out = []
        for lo, hi, active in schedule([r for r in refmods if r["name"] in blocks], images):
            out += _ranged(conditioning, [blocks[r["name"]] for r in active], lo, hi, pictures)
        said = [f"{r['name']} at {float(r['strength']):g}{_span(r)} ({tokens(blocks[r['name']])} tokens)"
                if r["name"] in blocks else f"{r['name']} at 0, left out" for r in refmods]
        said += [f"image {i['image']} at {float(i['strength']):g}{_span(i)}" for i in images]
        print("[orrery] Orrery RefMods: " + "; ".join(said))
        return (out or conditioning,)
