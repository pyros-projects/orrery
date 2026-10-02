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
