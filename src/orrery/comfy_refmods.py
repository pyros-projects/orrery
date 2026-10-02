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


def schedule(refmods: list[dict]) -> list[tuple[float, float, list[dict]]]:
    """(start, end, RefMods active) for each share of sampling, from 0 to 1. A range starts where a
    RefMod starts; a RefMod that waits until 100% never runs."""
    starts = sorted({0.0} | {min(1.0, max(0.0, float(r["from"]))) for r in refmods} - {1.0})
    ends = [*starts[1:], 1.0]
    return [(lo, hi, [r for r in refmods if float(r["from"]) <= lo]) for lo, hi in zip(starts, ends, strict=True)]


def _ranged(conditioning, blocks: list[dict], lo: float, hi: float) -> list:
    """The conditioning with `blocks` added to its refs, for sampling from `lo` to `hi` (within any range
    an entry already has); entries that leave nothing of the range are dropped."""
    out = []
    for tensor, meta in conditioning:
        meta = dict(meta)
        start, end = max(lo, meta.get("start_percent", 0.0)), min(hi, meta.get("end_percent", 1.0))
        if start >= end:
            continue
        if blocks:
            meta["minimax_refs"] = [*meta.get("minimax_refs", []), *blocks]
        if (start, end) != (0.0, 1.0):
            meta["start_percent"], meta["end_percent"] = start, end
        out.append([tensor, meta])
    return out


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
                   "conditioning: wire Reference to Video's conditioning and the Orrery Prompt's picks in, and the "
                   "output on to Orrery Continue or the guider. Needs the ComfyUI-H3RefMods pack.")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"conditioning": ("CONDITIONING",),
                             "picks": ("STRING", {"forceInput": True})}}

    def apply(self, conditioning, picks):
        refmods = json.loads(picks or "{}").get("refmods") or []
        if not refmods:
            return (conditioning,)
        pack = _pack()
        available = pack._list_mod_names()
        blocks: dict[str, dict] = {}
        for r in refmods:
            if float(r["strength"]) <= 0.0:
                continue  # at 0 a RefMod is left out, as the pack does
            block = pack._load_mod(resolve(r["name"], available)).ref_block(1.0, curve=None)
            if block is not None:
                blocks[r["name"]] = {**block, KEY: float(r["strength"])}
        out = []
        for lo, hi, active in schedule([r for r in refmods if r["name"] in blocks]):
            out += _ranged(conditioning, [blocks[r["name"]] for r in active], lo, hi)
        print("[orrery] Orrery RefMods: " + "; ".join(
            f"{r['name']} at {float(r['strength']):g} from {float(r['from']) * 100:g}% ({tokens(blocks[r['name']])} tokens)"
            if r["name"] in blocks else f"{r['name']} at 0, left out" for r in refmods))
        return (out or conditioning,)
