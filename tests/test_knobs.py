"""The model's knobs (#227): LoRAs, RefMods, images and members written alike, with (strength, start, end),
a short form told by its name, a long form per kind, and sweeps in every field."""

import sys
import types

import pytest

from orrery import knobs, loras, sweep
from orrery.h3 import compile_scene
from orrery.loras import long_form, lora_stack

HEAD = "@h3 ref2va 16:9\nstyle: live-action\n"
SHOT = "SHOT 5s: static\na woman looking like <Image 1> dances.\n"


def h3(src: str):
    return compile_scene(src, 1, {}, {}, target="h3-base", packed=True)


def test_fields_are_split_by_commas_and_sweep_with_bars_or_a_range():
    assert knobs.fields("0.8, 20%|40%, 90%") == ["0.8", "20%|40%", "90%"]
    assert knobs.options("0.6|0.8") == ["0.6", "0.8"]
    assert knobs.options("0.2-1;0.4") == ["0.2", "0.6", "1"]
    assert knobs.options("0%-30%;10%") == ["0%", "10%", "20%", "30%"]
    assert knobs.sweeps("0.6|0.8") and knobs.sweeps("0-1;0.5") and not knobs.sweeps("0.8") and not knobs.sweeps("{0.3|0.6}")
    assert (knobs.share("35%"), knobs.share("0.35"), knobs.share("35"), knobs.share("")) == (0.35, 0.35, 0.35, None)
    with pytest.raises(ValueError, match="backwards"):
        knobs.options("1-0;0.5")


def test_a_short_form_is_told_by_its_name_and_a_shared_name_is_both():
    files, mods = ["minimax/turbo.safetensors", "shared.safetensors"], ["jinx_v1_refmod_Video.safetensors", "shared.safetensors"]
    assert knobs.kind_of("turbo", files, mods) == "lora"
    assert knobs.kind_of("minimax/turbo", files, mods) == "lora"
    assert knobs.kind_of("jinx_v1_refmod", files, mods) == "refmod"
    assert knobs.kind_of("shared", files, mods) == "both"
    assert knobs.kind_of("nothing", files, mods) is None
    text = "LORA: @turbo(0.8, 20%) @jinx_v1_refmod(0.8, 0%, 10%) @image_1(0.6)\nCAST\n@JINX (image 1): a woman\nSET: @JINX(0.6)"
    out = long_form(text, loras=files, refmods=mods)
    assert "<lora:turbo:0.8, 20%> <refmod:jinx_v1_refmod:0.8, 0%, 10%> <image:1:0.6>" in out and "SET: @JINX(0.6)" in out


def test_set_takes_every_kind_in_its_long_form_and_a_lora_line_hands_on_the_others():
    r = h3(HEAD + "SET: <lora:turbo:0.8, 0%, 50%>, <refmod:jinx:0.8, 0%, 10%>, <image:1:0.6, 20%>\n"
           "LORA: <lora:style:0.5> <refmod:other:0.3>\n" + SHOT)
    assert r.loras == "<lora:turbo:0.8, 0%, 50%> <lora:style:0.5>"
    assert [(m["name"], m["strength"], m["to"]) for m in r.refmods] == [("jinx", 0.8, 0.1), ("other", 0.3, 1.0)]
    assert r.images == [{"ref": 1, "image": 1, "member": None, "strength": 0.6, "from": 0.2, "to": 1.0}]
    member = h3(HEAD + "CAST\n@JINX (image 1): a woman\nSET: <cast:JINX:0.4>\nSHOT 5s: static\n@JINX dances.\n")
    assert member.images[0]["strength"] == 0.4
    nobody = h3(HEAD + "SET: <cast:NOBODY:0.4>\n" + SHOT)
    assert any("no member NOBODY" in i.message for i in nobody.lint)


def test_a_short_name_in_set_is_a_lora_when_a_lora_file_has_it(monkeypatch):
    kinds = {"turbo": "lora", "shared": "both"}
    monkeypatch.setattr(knobs, "kind_of", lambda name, loras=None, refmods=None: kinds.get(name))
    r = h3(HEAD + "SET: turbo(0.9, 10%), jinx_refmod(0.8), shared(0.5)\n" + SHOT)
    assert r.loras == "<lora:turbo:0.9, 10%>"
    assert [m["name"] for m in r.refmods] == ["jinx_refmod"]  # no file says otherwise: a RefMod, as before
    assert any("names a LoRA and a RefMod" in i.message for i in r.lint)


def test_every_knob_sweeps_and_commas_separate_its_fields():
    src = (HEAD + "SET: image_1(0.3|0.6), <refmod:jinx:0.8, 0%|20%>\n"
           "LORA: <lora:turbo:0|0.8, 0%, 50%> <lora:old:0.5,1.0>\n" + SHOT)
    assert [t.text for t in sweep.tags(src)] == ["image_1(0.3|0.6)", "<refmod:jinx:0.8, 0%|20%>",
                                                 "<lora:turbo:0|0.8, 0%, 50%>", "<lora:old:0.5,1.0>"]
    runs = sweep.runs(src)
    assert len(runs) == 16 and sweep.formula(src) == "2 × 2 × 2 × 2"
    first = sweep.apply(src, runs[1])
    assert "SET: image_1(0.3), <refmod:jinx:0.8, 0%>" in first and "<lora:turbo" not in first  # 0 takes a LoRA out
    assert "<lora:old:1>" in first  # the commas of before still sweep
    assert sweep.picks(src, runs[1])[:2] == [{"label": "image_1", "value": "0.3", "keys": ["image_1=0.3"]},
                                             {"label": "refmod:jinx", "value": "0.8, 0%", "keys": ["refmod:jinx=0.8, 0%"]}]
    assert sweep.legacy(src) == ["<lora:old:0.5,1.0>"]
    assert sweep.apply(HEAD + "SET: <lora:x:0|1>\n" + SHOT, {"<lora:x:0|1>": None}).count("SET:") == 0  # an emptied line goes


def test_a_lora_has_a_start_and_an_end():
    stack, warnings = lora_stack("<lora:turbo:0.8, 20%, 90%> <lora:style:0.5:0.25> <lora:bad:0.5, 60%, 20%>",
                                 ["minimax/turbo.safetensors", "style.safetensors", "bad.safetensors"])
    assert stack == [("minimax/turbo.safetensors", 0.8, 0.8, 0.2, 0.9), ("style.safetensors", 0.5, 0.25, 0.0, 1.0)]
    assert warnings == ["<lora:bad:0.5, 60%, 20%> ends before it starts, so it is left out."]


def test_a_timed_lora_goes_on_by_hook_keyframes_that_the_wrapper_registers(monkeypatch):
    """ComfyUI registers the conditionings' hooks before the sampler's wrappers run: orrery's wrapper hangs a
    timed LoRA on every conditioning and registers it itself."""
    made, registered = [], []

    class Group:
        def __init__(self):
            self.hooks = []

        def add(self, hook):
            self.hooks.append(hook)

        def clone(self):
            c = Group()
            c.hooks = list(self.hooks)
            return c

        def set_keyframes_on_hooks(self, frames):
            for hook in self.hooks:
                hook["frames"] = frames.frames

    class Frames:
        def __init__(self):
            self.frames = []

        def add(self, frame):
            self.frames.append(frame)

    hooks = types.SimpleNamespace(
        HookGroup=Group, HookKeyframeGroup=Frames, EnumWeightTarget=types.SimpleNamespace(Model="model"),
        HookKeyframe=lambda strength, start_percent: (strength, start_percent),
        create_target_dict=lambda target: {"target": target},
        create_hook_lora=lambda sd, strength, clip: made.append((sd, strength, clip)) or _group({"lora": sd}, Group))
    extension = types.SimpleNamespace(WrappersMP=types.SimpleNamespace(OUTER_SAMPLE="outer_sample"))
    comfy = types.ModuleType("comfy")
    comfy.hooks, comfy.patcher_extension = hooks, extension
    for name, mod in (("comfy", comfy), ("comfy.hooks", hooks), ("comfy.patcher_extension", extension)):
        monkeypatch.setitem(sys.modules, name, mod)

    class Model:
        def __init__(self):
            self.wrappers = []

        def clone(self):
            return Model()

        def add_wrapper_with_key(self, kind, key, fn):
            self.wrappers.append((kind, key, fn))

    model = loras.timed(Model(), [("turbo", "turbo-weights", 0.8, 0.2, 0.9)])
    (kind, key, wrapper), = model.wrappers
    assert (kind, key) == ("outer_sample", "orrery_timed_loras")
    guider = types.SimpleNamespace(conds={"positive": [{}], "negative": [{}]}, model_options={},
                                   model_patcher=types.SimpleNamespace(register_all_hook_patches=lambda group, target, options, reg:
                                                                       registered.append((len(group.hooks), target))))
    ran = []

    class Executor:
        class_obj = guider

        def __call__(self, *args, **kwargs):
            ran.append(True)
            return "sampled"

    assert wrapper(Executor(), "noise") == "sampled" and ran
    assert made == [("turbo-weights", 0.8, 0)]
    hook = guider.conds["positive"][0]["hooks"].hooks[0]
    assert hook["frames"] == [(0.0, 0.0), (1.0, 0.2), (0.0, 0.9)]  # off, on at its start, off at its end
    assert guider.conds["negative"][0]["hooks"].hooks == [hook]
    assert registered == [(1, {"target": "model"})] and "registered_hooks" in guider.model_options


def _group(hook: dict, group_class):
    g = group_class()
    g.add(hook)
    return g


def test_a_rolled_lora_strength_rolls_as_before_and_keeps_its_start_and_end():
    from orrery.dsl import expand

    assert expand("<lora:style:0.4-0.9>", 3, {}).text == "<lora:style:0.9>"
    assert expand("<lora:style:0.4-0.9, 20%, 80%>", 3, {}).text == "<lora:style:0.9, 20%, 80%>"  # the same roll
    assert expand("<lora:style:0.8, 20%>", 3, {}).text == "<lora:style:0.8, 20%>"
