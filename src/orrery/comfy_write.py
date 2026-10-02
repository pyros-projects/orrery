"""Orrery Write: the language model writes for the editor, one idea per run (see orrery.writers).

The app queues it on its own, with only what the model needs (the frames and a text encoder wired
into the Orrery Prompt), so the run ends when the model has written and no video model is loaded.
The idea comes back as the node's UI output: the text, the template with it in place, or what is
wrong with it.
"""

import json

from orrery import writers
from orrery.comfy_llm import llm_config
from orrery.home import resolve_home

FRAME_EDGE = 768  # the long edge of a frame the model sees: enough to read it, a few hundred tokens


def _frames(task: str, first, last):
    """The frames a writer shows the model, as one IMAGE batch of one size, or None."""
    if task == "story":
        if first is None or last is None:
            raise writers.WriterError("The story between two frames needs the first and the last frame: wire them "
                                      "into the Orrery Prompt's first_frame and last_frame.")
        frames = [first, last]
    elif task == "describe":
        if first is None and last is None:
            raise writers.WriterError("A prompt from an image needs a picture: wire it into the Orrery Prompt's "
                                      "first_frame.")
        frames = [first if first is not None else last]
    else:
        return None
    import comfy.utils  # ComfyUI
    import torch

    h, w = int(frames[0].shape[1]), int(frames[0].shape[2])
    scale = min(1.0, FRAME_EDGE / max(h, w))
    size = (max(32, round(w * scale / 16) * 16), max(32, round(h * scale / 16) * 16))
    fitted = [comfy.utils.common_upscale(f[:1].movedim(-1, 1), size[0], size[1], "bilinear", "center").movedim(1, -1)
              for f in frames]
    return torch.cat(fitted)


class OrreryWrite:
    """The language model writes one idea for the Orrery Prompt's editor. Queued by the app; you do not
    need to add it yourself."""

    CATEGORY = "orrery/internal"
    FUNCTION = "write"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = ("Used by the Orrery Prompt's Write menu: the language model continues a reel, writes the "
                   "shot between two frames, or a prompt from a picture, in a run of its own.")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"task": (list(writers.TASKS),),
                             "template": ("STRING", {"multiline": True}),
                             "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF})},
                # idea n samples the model at seed + n; the picks it reads still roll at the node's seed
                "optional": {"idea": ("INT", {"default": 0, "min": 0, "max": 0xFFFF}),
                             "home": ("STRING", {"default": ""}), "params": ("STRING", {"default": ""}),
                             "clip": ("CLIP",), "first_frame": ("IMAGE",), "last_frame": ("IMAGE",)}}

    @classmethod
    def IS_CHANGED(cls, **_):
        return float("NaN")  # every request is a new idea

    def write(self, task, template, seed, idea=0, home="", params="", clip=None, first_frame=None, last_frame=None):
        from orrery import (
            comfy,  # the node pack's helpers; imported here, as comfy imports this module
        )
        from orrery.dsl import bindings, override, strip_comments
        from orrery.presets import resolve_includes

        h, answer = resolve_home(home or None), None
        try:
            known = {name for name, _ in bindings(template)}
            dials = {k: v for k, v in comfy.dial_values(params).items() if k in known}
            source = strip_comments(resolve_includes(h, override(template, dials)))
            prompt = writers.request(h, task, source, seed, h.libraries(), h.weights())
            images = _frames(task, first_frame, last_frame)
            backend = comfy.llm_for(h, clip, seed=(seed + idea) % 2**32,
                                    temperature=float(llm_config(h)["writer_temperature"]))  # ideas, not one answer
            if backend is None:
                raise writers.WriterError("The writers need a language model: pick one in orrery's settings (the gear "
                                          "in the node), or wire a text encoder into the Orrery Prompt's clip.")
            answer = backend.complete(prompt, images=images)
            text, problem = writers.check(task, template, answer)
            result = {"task": task, "seed": seed, "idea": idea, "text": text, "problem": problem,
                      "template": writers.apply(task, template, text) if text else None}  # the app asks before it inserts one with a problem
        except (writers.WriterError, ValueError, RuntimeError) as err:
            result = {"task": task, "seed": seed, "idea": idea, "error": str(err), "raw": answer}
        print(f"[orrery] write · {task} · seed {seed} · idea {idea}: {result.get('error') or result.get('problem') or 'an idea'}")
        if result.get("text"):
            print(result["text"])
        return {"ui": {"orrery_write": [json.dumps(result, ensure_ascii=False)]}}
