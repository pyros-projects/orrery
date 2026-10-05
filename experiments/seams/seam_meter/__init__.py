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


NODE_CLASS_MAPPINGS = {"OrrerySeamMeter": OrrerySeamMeter}
NODE_DISPLAY_NAME_MAPPINGS = {"OrrerySeamMeter": "Orrery Seam Meter"}
