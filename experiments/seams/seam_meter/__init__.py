"""Orrery Seam Meter: one yardstick for the seams of any chained H3 film (see meter.py). An experiment pack, kept out of
orrery's node pack: copy this folder into ComfyUI's custom_nodes as `orrery-seam-meter` and put the node at the end of
each tool's workflow, on the film it delivers."""

import json
import time
from pathlib import Path

from .meter import measure, report, seams_from


class OrrerySeamMeter:
    CATEGORY = "orrery/experiments"
    FUNCTION = "meter"
    OUTPUT_NODE = True
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report",)
    DESCRIPTION = ("How a chained film's seams compare with the inside of its clips, picture and sound, as percentiles. "
                   "Seams: `121,99` (the first clip 121 frames, then 99 each) or `@121,220` (where clips start).")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "seams": ("STRING", {"default": "121,99"}),
                             "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 240.0}),
                             "label": ("STRING", {"default": "orrery"})},
                "optional": {"audio": ("AUDIO",)}}

    def meter(self, images, seams, fps, label, audio=None):
        import folder_paths  # ComfyUI

        frames = images.cpu().numpy()
        sound = rate = None
        if audio is not None:
            sound, rate = audio["waveform"][0].cpu().float().numpy(), int(audio["sample_rate"])
        result = measure(frames, seams_from(seams, len(frames)), fps, sound, rate)
        result |= {"label": label, "seams_spec": seams, "made": time.strftime("%Y-%m-%d %H:%M:%S")}
        out = Path(folder_paths.get_output_directory()) / "seams"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{label}-{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(json.dumps(result, indent=1))
        text = report(result, label)
        print(f"[orrery seam meter]\n{text}")
        return {"ui": {"text": [text]}, "result": (text,)}


class OrreryLatentKeep:
    """Keeps a MiniMax H3 latent (video and audio together, which core Save Latent cannot store) as
    output/<prefix>.pt, for decoding clips again later: one decode over a joined film (#360)."""

    CATEGORY = "orrery/experiments"
    FUNCTION = "keep"
    OUTPUT_NODE = True
    RETURN_TYPES = ()

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"samples": ("LATENT",), "filename_prefix": ("STRING", {"default": "seam_bench/latent"})}}

    def keep(self, samples, filename_prefix):
        import folder_paths  # ComfyUI
        import torch

        latent = samples["samples"]
        parts = latent.unbind() if getattr(latent, "is_nested", False) else [latent]
        path = Path(folder_paths.get_output_directory()) / f"{filename_prefix}.pt"
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save([t.detach().cpu() for t in parts], path)
        return {}


class OrreryLatentJoin:
    """Joins clips kept with Orrery Latent Keep (`<prefix>0.pt` …) into one MiniMax H3 latent, each later clip without
    the frames Orrery Continue pinned (22 frames: 7 video slots, 37 audio ticks), for one decode over the whole film
    instead of one a clip (#360). A 124-frame clip has 37 slots: the 30 it adds keep H3's 1-4-4-4-4 rhythm."""

    CATEGORY = "orrery/experiments"
    FUNCTION = "join"
    RETURN_TYPES = ("LATENT",)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"prefix": ("STRING", {"default": "seam_bench/s1/orrery/latent_"}),
                             "clips": ("INT", {"default": 4, "min": 1, "max": 64}),
                             "context_slots": ("INT", {"default": 7, "min": 0, "max": 64}),
                             "context_ticks": ("INT", {"default": 37, "min": 0, "max": 512})}}

    def join(self, prefix, clips, context_slots, context_ticks):
        import folder_paths  # ComfyUI
        import torch
        from comfy.nested_tensor import NestedTensor

        root = Path(folder_paths.get_output_directory())
        videos, audios = [], []
        for k in range(clips):
            video, audio = torch.load(root / f"{prefix}{k}.pt")
            videos.append(video if k == 0 else video[:, :, context_slots:])
            audios.append(audio if k == 0 else audio[..., context_ticks:])
        return ({"samples": NestedTensor((torch.cat(videos, dim=2), torch.cat(audios, dim=-1)))},)


NODE_CLASS_MAPPINGS = {"OrrerySeamMeter": OrrerySeamMeter, "OrreryLatentKeep": OrreryLatentKeep, "OrreryLatentJoin": OrreryLatentJoin}
NODE_DISPLAY_NAME_MAPPINGS = {"OrrerySeamMeter": "Orrery Seam Meter", "OrreryLatentKeep": "Orrery Latent Keep",
                              "OrreryLatentJoin": "Orrery Latent Join"}
