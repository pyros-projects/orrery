"""The live preview of the clip being sampled (#205, #209), on CPU tensors and stand-ins for ComfyUI."""

import sys
import time
import types

import pytest

from orrery import preview

torch = pytest.importorskip("torch")


class RGB:  # a latent format with Latent2RGB factors, as ComfyUI's have
    latent_rgb_factors = ((0.5, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 0.5), (0.1, 0.1, 0.1))
    latent_rgb_factors_bias = None


def test_a_clips_frames_spread_over_it_and_scaled_to_a_preview():
    pictures = preview.frames(("rgb", RGB()), torch.zeros(1, 4, 30, 8, 12))
    assert len(pictures) == preview.MAX_LATENT_FRAMES and pictures[0].size == (12, 8)
    assert len(preview.frames(("rgb", RGB()), torch.zeros(1, 4, 5, 8, 12))) == 5  # a short clip: all of it


def test_the_tiny_vae_decodes_a_smaller_latent():
    seen = {}

    class Tiny:
        def decode(self, x):
            seen["shape"] = tuple(x.shape)
            t, h, w = x.shape[2], x.shape[3] * 16, x.shape[4] * 16
            return torch.rand(1, t * 4, h, w, 3)

    pictures = preview.frames(("tae", Tiny()), torch.zeros(1, 4, 40, 60, 40))  # 960×640 at full size
    assert seen["shape"][2] == preview.MAX_LATENT_FRAMES and max(seen["shape"][3:]) == 24  # 384 / 16
    assert len(pictures) == preview.MAX_LATENT_FRAMES * 4 and max(pictures[0].size) <= preview.MAX_EDGE


def test_the_wrapper_keeps_the_samplers_callback_and_sends_the_clip(monkeypatch):
    sent, called = [], []
    monkeypatch.setattr(preview, "_send", sent.append)
    monkeypatch.setattr(preview, "_decoder", lambda model_patcher: ("rgb", RGB()))
    wrapper = preview._Wrapper("24")

    def executor(noise, latent_image, sampler, sigmas, denoise_mask, callback, disable_pbar, seed, latent_shapes=None):
        for step in range(2):
            callback(step, torch.rand(1, 4, 6, 8, 12) * 2 - 1, None, 2)
        return "sampled"

    executor.class_obj = types.SimpleNamespace(model_patcher=None)
    out = wrapper(executor, None, None, None, [1.0, 0.5, 0.0], callback=lambda *a: called.append(a[0]))
    assert out == "sampled" and called == [0, 1]
    for _ in range(100):  # the sender works in a thread of its own
        if sent and sent[-1]["step"] == 2:
            break
        time.sleep(0.02)
    last = sent[-1]
    assert last["step"] == 2 and last["total"] == 2 and last["node"] == "24"
    import base64
    import io

    from PIL import Image
    clip = Image.open(io.BytesIO(base64.b64decode(last["image"])))
    assert last["mime"] == "image/webp" and last["animated"] and clip.format == "WEBP" and clip.n_frames == 6


def test_the_patched_model_is_a_clone_with_the_wrapper(monkeypatch):
    extension = types.ModuleType("comfy.patcher_extension")
    extension.WrappersMP = types.SimpleNamespace(OUTER_SAMPLE="outer_sample")
    comfy = types.ModuleType("comfy")
    comfy.patcher_extension = extension
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.patcher_extension", extension)

    class Model:
        def __init__(self):
            self.wrappers = []

        def clone(self):
            return Model()

        def add_wrapper_with_key(self, kind, key, fn):
            self.wrappers.append((kind, key, fn))

    original = Model()
    m = preview.patched(original, "24")
    assert m is not original and original.wrappers == []
    assert [(k, key) for k, key, _ in m.wrappers] == [("outer_sample", "orrery_preview")]
