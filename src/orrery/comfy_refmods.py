"""Orrery RefMods: the clip's RefMods on its conditioning, each with its strength and its start.

The compiler lists them in the picks (orrery.h3.clip_refmods). This node loads them with the
ComfyUI-H3RefMods pack and adds one block per RefMod to the conditioning's `minimax_refs`, as the
pack's Apply H3 RefMod does, marked with its strength for orrery.refbias. A RefMod that waits
(`from 35%`) stays out of the conditioning for that share of sampling: the node splits the
conditioning into timestep ranges, as ConditioningSetTimestepRange does, so each range carries the
RefMods that have started by then. ComfyUI only.
"""

import json
import sys
from itertools import pairwise

from orrery.refbias import KEY

PACK = "ComfyUI-H3RefMods"


def _pack():
    """The pack's loader module, as ComfyUI imported it."""
    for name, module in list(sys.modules.items()):
        if name.endswith(".nodes.refmod_loader") and hasattr(module, "_load_mod") and hasattr(module, "_list_mod_names"):
            return module
    raise ValueError(f"Orrery RefMods loads RefMods with the {PACK} pack (github.com/FranckyB/{PACK}): install "
                     "it in custom_nodes and restart ComfyUI.")


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


def _ranged(conditioning, blocks: list[dict], lo: float, hi: float, images: dict | None = None) -> list:
    """The conditioning with `blocks` added to its refs, for sampling from `lo` to `hi` (within any range
    an entry already has); entries that leave nothing of the range are dropped. `images`: {k: (strength,
    from, to)} for the k-th picture Reference to Video put on the conditioning; a picture that waits past
    `lo`, stops before `hi` or is at 0 is left out of this range, any other strength marks it for
    orrery.refbias."""
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
                if wait > lo or until < hi or strength <= 0.0:
                    continue
                if strength != 1.0:
                    block = {**block, KEY: strength}
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
    DESCRIPTION = ("Loads the RefMods the clip's CAST names (refmod NAME at 0.5 from 35%) and puts them on the "
                   "conditioning, and applies a picture's at and from (image 1 at 0.5): wire Reference to Video's "
                   "conditioning and the Orrery Prompt's picks in, and the output on to Orrery Continue or the "
                   "guider. RefMods need the ComfyUI-H3RefMods pack.")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"conditioning": ("CONDITIONING",),
                             "picks": ("STRING", {"forceInput": True})}}

    def apply(self, conditioning, picks):
        data = json.loads(picks or "{}")
        refmods, images = data.get("refmods") or [], data.get("images") or []
        if not refmods and not images:
            return (conditioning,)
        blocks: dict[str, dict] = {}
        if refmods:
            pack = _pack()
            available = pack._list_mod_names()
            for r in refmods:
                if float(r["strength"]) <= 0.0:
                    continue  # at 0 a RefMod is left out, as the pack does
                block = pack._load_mod(resolve(r["name"], available)).ref_block(1.0, curve=None)
                if block is not None:
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
