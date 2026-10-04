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

    pictures = preview.frames(("tae", Tiny()), torch.zeros(1, 4, 40, 60, 40), edge=384)  # 960×640 at full size
    assert seen["shape"][2] == preview.MAX_LATENT_FRAMES and max(seen["shape"][3:]) == 24  # 384 / 16
    assert len(pictures) == preview.MAX_LATENT_FRAMES * 4 and max(pictures[0].size) <= 384
    full = preview.frames(("tae", Tiny()), torch.zeros(1, 4, 40, 60, 40), edge=0)  # as sampled
    assert max(seen["shape"][3:]) == 60 and full[0].size == (640, 960)
    preview.frames(("tae", Tiny()), torch.zeros(1, 4, 40, 60, 40))  # KJNodes' default: 1024, so 960 stays
    assert max(seen["shape"][3:]) == 60
    preview.frames(("tae", Tiny()), torch.zeros(1, 4, 1, 128, 96), edge=512, spatial=8)  # an image model's (#211): 1024×768
    assert max(seen["shape"][3:]) == 64  # 512 / 8, where H3's 16 would have made it 32


def test_a_flat_tiny_decoder_is_built_from_its_checkpoint():
    def block(at, n_in, n_out):
        sd = {f"{at}.conv.{i}.weight": torch.randn(n_out, n_in if i == 0 else n_out, 3, 3) for i in (0, 2, 4)}
        sd |= {f"{at}.conv.{i}.bias": torch.randn(n_out) for i in (0, 2, 4)}
        return sd | ({f"{at}.skip.weight": torch.randn(n_out, n_in, 1, 1)} if n_in != n_out else {})

    # as the 2D taeh3, smaller: clamp, conv, ReLU, block, upsample, conv, block, upsample, conv
    sd = {"1.weight": torch.randn(8, 4, 3, 3), "1.bias": torch.randn(8), **block(3, 8, 8),
          "5.weight": torch.randn(8, 8, 3, 3), **block(6, 8, 6), "8.weight": torch.randn(3, 6, 3, 3), "8.bias": torch.randn(3)}
    decoder = preview.flat_decoder(sd)  # loads strictly: every weight found its module
    assert [type(m).__name__ for m in decoder] == ["Clamp", "Conv2d", "ReLU", "Block", "Upsample", "Conv2d", "Block",
                                                    "Upsample", "Conv2d"]
    pictures = preview.frames(("tae2d", decoder), torch.zeros(1, 4, 30, 8, 12))
    assert len(pictures) == preview.MAX_LATENT_FRAMES and pictures[0].size == (48, 32)  # a picture per latent frame


def test_a_smooth_preview_has_so_many_pictures_a_second_as_its_latent_frames_give():
    clip = torch.zeros(1, 4, 47, 8, 12)  # 6.66 s of MiniMax H3
    assert round(preview.seconds(clip), 2) == 6.66
    assert len(preview.frames(("rgb", RGB()), clip, fps=2)) == 13
    assert len(preview.frames(("rgb", RGB()), clip, fps=12)) == 47  # one a latent frame: about 7 a second
    assert len(preview.frames(("rgb", RGB()), clip)) == preview.MAX_LATENT_FRAMES  # light


def sampled(monkeypatch, wrapper, latent_frames=6):
    """The last clip the wrapper sent, sampling two steps; checks that the sampler's own callback still runs."""
    sent, called = [], []
    monkeypatch.setattr(preview, "_send", sent.append)
    monkeypatch.setattr(preview, "_decoder", lambda model_patcher: ("rgb", RGB()))

    def executor(noise, latent_image, sampler, sigmas, denoise_mask, callback, disable_pbar, seed, latent_shapes=None):
        for step in range(2):
            callback(step, torch.rand(1, 4, latent_frames, 8, 12) * 2 - 1, None, 2)
        return "sampled"

    executor.class_obj = types.SimpleNamespace(model_patcher=None)
    out = wrapper(executor, None, None, None, [1.0, 0.5, 0.0], callback=lambda *a: called.append(a[0]))
    assert out == "sampled" and called == [0, 1]
    for _ in range(100):  # the sender works in a thread of its own
        if sent and sent[-1]["step"] == 2:
            break
        time.sleep(0.02)
    import base64
    import io

    from PIL import Image
    clip = Image.open(io.BytesIO(base64.b64decode(sent[-1]["image"])))
    clip.load()  # its first frame, and how long it shows
    return sent[-1], clip


def test_the_wrapper_keeps_the_samplers_callback_and_sends_the_clip_in_real_time(monkeypatch):
    last, clip = sampled(monkeypatch, preview._Wrapper("24"))
    assert last["step"] == 2 and last["total"] == 2 and last["node"] == "24"
    assert last["mime"] == "image/webp" and last["animated"] and clip.format == "WEBP" and clip.n_frames == 6
    assert clip.info["duration"] == 142  # 6 latent frames are 0.85 s: 6 pictures of 142 ms


def test_the_wrapper_reads_the_smooth_preview_from_the_home_as_it_samples(monkeypatch, tmp_path):
    from orrery.home import Home
    from orrery.uistate import set_flag, set_size

    home = Home(tmp_path)
    wrapper = preview._Wrapper("24", home)
    set_flag(home, "preview_light", False)
    set_size(home, "preview_fps", 4)
    set_size(home, "preview_edge", 6)
    _, clip = sampled(monkeypatch, wrapper, latent_frames=30)  # 4.25 s
    assert clip.n_frames == 17 and clip.info["duration"] == 250
    assert max(clip.size) == 6  # the gear's preview size: the 12-wide clip at 6


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
