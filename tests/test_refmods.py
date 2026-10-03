import json
import math
import sys
import types

import pytest

from orrery import refbias
from orrery.comfy_refmods import OrreryRefMods, resolve, schedule

SALON = {"name": "salon_canon", "member": "SALON", "strength": 0.5, "from": 0.35}
HALL = {"name": "hall_canon", "member": "HALL", "strength": 1.0, "from": 0.0}


def test_each_share_of_sampling_carries_the_refmods_that_have_started():
    assert schedule([SALON, HALL]) == [(0.0, 0.35, [HALL]), (0.35, 1.0, [SALON, HALL])]
    assert schedule([HALL]) == [(0.0, 1.0, [HALL])]
    assert schedule([{**SALON, "from": 1.0}]) == [(0.0, 1.0, [])]  # waits for ever: never runs


def test_a_refmod_or_a_picture_that_stops_leaves_the_ranges_after():
    early = {**HALL, "to": 0.2}
    assert schedule([early]) == [(0.0, 0.2, [early]), (0.2, 1.0, [])]
    assert schedule([SALON], [{"from": 0.0, "to": 0.5}]) == [(0.0, 0.35, []), (0.35, 0.5, [SALON]), (0.5, 1.0, [SALON])]


def test_a_refmod_is_found_by_its_name_or_its_video_half():
    assert resolve("salon_canon", ["salon_canon_Video", "other"]) == "salon_canon_Video"
    assert resolve("x", ["x", "x_Video"]) == "x"
    with pytest.raises(ValueError, match="close: salon_canon_old"):
        resolve("salon_canon", ["salon_canon_old"])


@pytest.fixture
def pack(monkeypatch):
    """A stand-in for ComfyUI-H3RefMods' loader, as ComfyUI imports it."""
    loaded = []

    class Mod:
        def __init__(self, name):
            self.name = name

        def ref_block(self, strength, curve=None):
            return {"kind": "video", "latent_t": 4, "latent_h": 36, "latent_w": 64, "latent": f"latent of {self.name}"}

    loader = types.ModuleType("ComfyUI-H3RefMods.nodes.refmod_loader")
    loader._list_mod_names = lambda: ["salon_canon_Video", "hall_canon"]
    loader._load_mod = lambda name: loaded.append(name) or Mod(name)
    monkeypatch.setitem(sys.modules, loader.__name__, loader)
    return loaded


def test_orrery_refmods_puts_each_refmod_on_the_conditioning_from_its_start(pack):
    cond = [["text", {"pooled": 1, "minimax_refs": [{"kind": "image", "latent": "earlier"}]}]]
    (out,) = OrreryRefMods().apply(cond, json.dumps({"refmods": [SALON, HALL]}))
    early, late = out
    assert (early[1]["start_percent"], early[1]["end_percent"]) == (0.0, 0.35)
    assert [b["latent"] for b in early[1]["minimax_refs"]] == ["earlier", "latent of hall_canon"]
    assert (late[1]["start_percent"], late[1]["end_percent"]) == (0.35, 1.0)
    assert [b.get(refbias.KEY) for b in late[1]["minimax_refs"]] == [None, 0.5, 1.0]
    assert cond[0][1]["minimax_refs"] == [{"kind": "image", "latent": "earlier"}]  # the input stays as it was
    assert pack == ["salon_canon_Video", "hall_canon"]


def test_without_refmods_the_conditioning_passes_and_at_zero_a_refmod_stays_out(pack):
    cond = [["text", {}]]
    assert OrreryRefMods().apply(cond, json.dumps({}))[0] is cond
    (out,) = OrreryRefMods().apply(cond, json.dumps({"refmods": [{**SALON, "strength": 0}, HALL]}))
    assert [[b["latent"] for b in meta["minimax_refs"]] for _, meta in out] == [["latent of hall_canon"]]


def test_a_range_the_conditioning_already_has_is_kept(pack):
    cond = [["text", {"start_percent": 0.5, "end_percent": 1.0}]]
    (out,) = OrreryRefMods().apply(cond, json.dumps({"refmods": [SALON]}))
    assert [(m["start_percent"], m["end_percent"], len(m["minimax_refs"])) for _, m in out] == [(0.5, 1.0, 1)]


def test_a_picture_with_at_and_from_is_marked_and_waits_at_zero_without_the_pack(monkeypatch):
    for name in [n for n in sys.modules if n.endswith(".nodes.refmod_loader")]:
        monkeypatch.delitem(sys.modules, name)
    cond = [["text", {"minimax_refs": [{"kind": "image", "latent": "one"}, {"kind": "image", "latent": "two"},
                                       {"kind": "video", "latent": "clip"}]}]]
    picks = {"images": [{"ref": 2, "image": 5, "member": "TOM", "strength": 0.5, "from": 0.35}]}
    (out,) = OrreryRefMods().apply(cond, json.dumps(picks))
    (early, late) = out
    marks = lambda c: [(b["latent"], b.get(refbias.KEY), b.get(refbias.PICTURE)) for b in c[1]["minimax_refs"]]
    # image 2 waits at 0, so refbias hides its vision block in the text too, which leaving would not
    assert marks(early) == [("one", None, None), ("two", 0.0, 2), ("clip", None, None)]
    assert marks(late) == [("one", None, None), ("two", 0.5, 2), ("clip", None, None)]
    picks["images"][0].update({"from": 0.0, "to": 0.5})  # image 2 only for the first half
    (out,) = OrreryRefMods().apply(cond, json.dumps(picks))
    assert [[b.get(refbias.KEY) for b in c[1]["minimax_refs"]] for c in out] == [[None, 0.5, None], [None, 0.0, None]]
    assert [(c[1].get("start_percent"), c[1].get("end_percent")) for c in out] == [(0.0, 0.5), (0.5, 1.0)]


def test_a_refmod_that_ships_with_orrery_is_loaded_from_its_own_folder(pack, monkeypatch, tmp_path):
    from orrery import comfy_refmods as cr
    assert "minimaxh3_jinx_v1_refmod" in cr.shipped()  # the example RefMod is in the repository
    (tmp_path / "jinx.safetensors").write_bytes(b"")
    monkeypatch.setattr(cr, "EXAMPLES", tmp_path)
    loader = next(m for n, m in sys.modules.items() if n.endswith(".nodes.refmod_loader"))
    paths = []
    monkeypatch.setattr(loader, "H3RefMod", types.SimpleNamespace(
        load=lambda path, device="cpu": paths.append(path) or loader._load_mod("jinx")), raising=False)
    jinx = {"name": "jinx", "member": "JINX", "strength": 1.0, "from": 0.0, "to": 1.0}
    (out,) = OrreryRefMods().apply([["text", {}]], json.dumps({"refmods": [jinx]}))
    assert paths == [str(tmp_path / "jinx")]  # not in models/refmods: from orrery's folder, with the pack's class
    assert [b["latent"] for b in out[0][1]["minimax_refs"]] == ["latent of jinx"]


def test_without_the_pack_the_node_says_where_to_get_it(monkeypatch):
    for name in [n for n in sys.modules if n.endswith(".nodes.refmod_loader")]:
        monkeypatch.delitem(sys.modules, name)
    with pytest.raises(ValueError, match="ComfyUI-H3RefMods"):
        OrreryRefMods().apply([["text", {}]], json.dumps({"refmods": [SALON]}))


# --- the attention bias (orrery.refbias) -------------------------------------------------------

def test_the_plan_follows_how_h3_packs_the_refs():
    blocks = [{"kind": "image"}, {"kind": "video", "ref_audio_t": 3, refbias.KEY: 0.5}, {"kind": "audio", "ref_audio_t": 0}]
    assert refbias.plan(blocks) == [(1.0, 1), (0.5, 2), (1.0, 0)]
    assert refbias.plan([{"kind": "video", refbias.KEY: 1.0}]) is None  # every strength 1: H3 untouched


def test_rows_bias_the_targets_queries_and_the_refmods_keys():
    segments = [(0, 10, "text"), (10, 20, "ref_img"), (20, 26, "ref_audio"), (26, 40, "ref_img"),
                (40, 50, "audio"), (50, 90, "video")]
    queries, keys = refbias.rows(segments, [(1.0, 1), (0.5, 2)])
    assert queries == [(40, 50), (50, 90)]
    assert keys == [(20, 26, math.log(0.5)), (26, 40, math.log(0.5))]


def test_a_pictures_vision_block_is_the_nth_run_of_vision_tokens_in_the_text():
    tags = [1, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1]  # <Picture 1>, <Picture 2>, then a video's block
    refs = [{"kind": "image"}, {"kind": "image", refbias.KEY: 0.25, refbias.PICTURE: 2}, {"kind": "video"}]
    assert refbias.vision(refs, tags) == [(6, 8, 0.25)]
    assert refbias.vision([{"kind": "image", refbias.KEY: 0.5, refbias.PICTURE: 1}], tags) == [(2, 5, 0.5)]
    assert refbias.vision(refs[:1], tags) is None  # every picture at 1
    assert refbias.vision(refs, None) is None  # no tags: only the latents


def test_rows_bias_a_pictures_vision_block_in_the_text_too():
    segments = [(0, 10, "text"), (10, 20, "ref_img"), (20, 60, "video")]
    queries, keys = refbias.rows(segments, [(0.5, 1)], [(2, 5, 0.5)])
    assert queries == [(20, 60)]
    assert keys == [(10, 20, math.log(0.5)), (2, 5, math.log(0.5))]


def test_the_forward_notes_the_strengths_and_vision_blocks_of_the_payload():
    forward = refbias._forward(lambda self, x, t, c, options, *args, **kwargs: dict(options))
    refs = [{"kind": "image", refbias.KEY: 0.5, refbias.PICTURE: 1}]
    options = {"other": 1}
    seen = forward(None, None, None, None, options, minimax_payload={"refs": refs, "text_token_tags": [1, 0, 0, 1]})
    assert seen == {"other": 1, refbias.OPTION: [(0.5, 1)], refbias.VISION: [(1, 3, 0.5)]}
    assert forward(None, None, None, None, options, minimax_payload={"refs": [{"kind": "image"}]}) == {"other": 1}


def test_the_extra_column_adds_exactly_log_s_and_keeps_the_rest_of_the_logits():
    dim = 128
    c, values, scale = refbias.columns([math.log(0.5), math.log(0.1)], dim)
    wide = dim + refbias.PAD
    for b, k in values.items():
        assert math.isclose(c * k / math.sqrt(wide), b)
    assert math.isclose(scale / math.sqrt(wide), 1 / math.sqrt(dim))  # q·k/√D survives the wider head
    assert math.isclose(abs(c), abs(values[math.log(0.1)]))  # balanced: no outlier for int8 kernels


def test_biased_attention_matches_softmax_with_the_bias():
    torch = pytest.importorskip("torch")

    class Container:
        def __init__(self, tensor):
            self.tensor = tensor

        def peek(self):
            return self.tensor

        def take(self):
            tensor, self.tensor = self.tensor, None
            return tensor

    def sdpa(q, k, v, heads, *args, transformer_options=None, **kwargs):
        out = torch.nn.functional.scaled_dot_product_attention(q.take(), k.take(), v.take())
        return out.transpose(1, 2).reshape(1, out.shape[2], -1)

    class Layout:
        segments = ((0, 6, "text"), (6, 14, "ref_img"), (14, 40, "video"))

    torch.manual_seed(0)
    heads, seq, dim = 10, 40, 16
    q, k, v = (torch.randn(1, heads, seq, dim, dtype=torch.float64) for _ in range(3))
    attention = refbias._attention(sdpa, Container)
    options = {"minimax_h3_layout": Layout(), refbias.OPTION: [(0.3, 1)]}
    got = attention(Container(q.clone()), Container(k.clone()), Container(v.clone()), heads, transformer_options=options)
    bias = torch.zeros(seq, seq, dtype=torch.float64)
    bias[14:40, 6:14] = math.log(0.3)
    want = torch.softmax(q @ k.transpose(-1, -2) / math.sqrt(dim) + bias, dim=-1) @ v
    assert torch.allclose(got, want.transpose(1, 2).reshape(1, seq, heads * dim), atol=1e-10)
    plain = attention(Container(q.clone()), Container(k.clone()), Container(v.clone()), heads,
                      transformer_options={"minimax_h3_layout": Layout()})
    assert torch.equal(plain, sdpa(Container(q), Container(k), Container(v), heads))


# --- RefMods a SEND: line makes from the reel's frames (#13) ------------------------------------

def test_a_sent_refmod_keeps_every_frame_on_the_vaes_grid():
    from orrery.comfy_refmods import MAX_FRAMES, video_frames
    assert [video_frames(n) for n in (2, 5, 6, 18, 22, 23, 72)] == [5, 5, 22, 22, 22, 39, 73]
    assert video_frames(MAX_FRAMES + 40) == MAX_FRAMES == 73


@pytest.fixture
def canvas(monkeypatch):
    """ComfyUI's Reference to Video helpers as orrery borrows them, with a 32×48 canvas."""
    torch = pytest.importorskip("torch")
    h3 = types.ModuleType("comfy_extras.nodes_minimax_h3")
    h3.adapt_canvas = lambda w, h: (32, 48)
    h3._resize = lambda image, w, h, crop: torch.zeros(image.shape[0], h, w, 3)
    monkeypatch.setitem(sys.modules, "comfy_extras", types.ModuleType("comfy_extras"))
    monkeypatch.setitem(sys.modules, "comfy_extras.nodes_minimax_h3", h3)
    return torch


class FakeVAE:
    """H3's video VAE in shape only: 17k+5 frames to 5k+2 latents, 16 times smaller."""

    def __init__(self):
        self.calls = []

    def encode(self, pixels):
        import torch
        n, h, w = pixels.shape[0], pixels.shape[1], pixels.shape[2]
        self.calls.append(n)
        return torch.zeros(1, 24, 1 if n == 1 else (n - 5) // 17 * 5 + 2, h // 16, w // 16)


def test_a_sent_refmod_is_encoded_like_a_video_reference(canvas):
    from orrery.comfy_refmods import encode
    torch, vae = canvas, FakeVAE()
    video = encode(torch.rand(18, 96, 64, 3), vae)  # every 10th frame of a 7 s clip
    assert vae.calls == [22]  # filled up to the VAE's grid with the last frame: none dropped
    assert (video["kind"], video["latent_t"], video["latent_h"], video["latent_w"]) == ("video", 7, 3, 2)
    still = encode(torch.rand(1, 96, 64, 3), vae)
    assert (still["kind"], still["latent_h"], still["latent_w"]) == ("image", 3, 2)
    encode(torch.rand(200, 96, 64, 3), vae)
    assert vae.calls[-1] == 73  # more than MAX_FRAMES: spread out to that many


def test_a_sent_refmod_is_built_once_from_the_chain_without_the_pack(canvas, monkeypatch, tmp_path):
    from orrery import chain
    from orrery import comfy_refmods as cr
    torch, vae = canvas, FakeVAE()
    clip = tmp_path / "video.mp4"
    clip.write_bytes(b"")
    monkeypatch.setitem(sys.modules, "folder_paths", types.SimpleNamespace(get_output_directory=lambda: str(tmp_path)))
    monkeypatch.setattr(chain, "clip_file", lambda output, latent_path, segment: clip if segment == 0 else None)
    monkeypatch.setattr(chain, "frames", lambda path, spans, step=1: (torch.rand(18, 96, 64, 3), []))
    monkeypatch.setattr(cr, "_BUILT", {})
    for name in [n for n in sys.modules if n.endswith(".nodes.refmod_loader")]:
        monkeypatch.delitem(sys.modules, name)  # no pack installed
    sent = {"name": "jinx_look", "member": "JINX", "strength": 0.5, "from": 0.0, "to": 1.0,
            "sent": {"segment": 0, "frames": [[0, -1]], "step": 10}}
    picks = json.dumps({"refmods": [sent], "chain": "h3_context"})
    cond = [["text", {"minimax_refs": []}]]
    (out,) = cr.OrreryRefMods().apply(cond, picks, vae=vae)
    (block,) = out[0][1]["minimax_refs"]
    assert (block["kind"], block["latent_t"], block[refbias.KEY]) == ("video", 7, 0.5)
    cr.OrreryRefMods().apply(cond, picks, vae=vae)
    assert vae.calls == [22]  # kept for the run: encoded once
    monkeypatch.setattr(cr, "_BUILT", {})
    with pytest.raises(ValueError, match="needs the VAE"):
        cr.OrreryRefMods().apply(cond, picks)
    later = json.dumps({"refmods": [{**sent, "sent": {**sent["sent"], "segment": 3}}], "chain": "h3_context"})
    with pytest.raises(ValueError, match="no clip for segment 3"):
        cr.OrreryRefMods().apply(cond, later, vae=vae)
