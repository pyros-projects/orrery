"""`<lora:name:strength>` tags become a stack: (path as ComfyUI lists it, model, clip), put on the model."""

from orrery.loras import lora_stack

FILES = ["minimax/Motion_Repair.safetensors", "style/indie90s.safetensors", "a/dup.safetensors",
         "b/dup.safetensors", "minimax/bf16__apply_to_fl2va__rank256.safetensors"]


def test_names_resolve_by_file_name_or_path():
    stack, warnings = lora_stack("<lora:Motion_Repair:1.00> <lora:style/indie90s:0.5:0.25>", FILES)
    assert stack == [("minimax/Motion_Repair.safetensors", 1.0, 1.0), ("style/indie90s.safetensors", 0.5, 0.25)]
    assert warnings == []


def test_resolution_ignores_case_and_extension_and_keeps_double_underscores():
    stack, _ = lora_stack("<lora:motion_repair.safetensors:0.8> <lora:bf16__apply_to_fl2va__rank256:0.5>", FILES)
    assert stack == [("minimax/Motion_Repair.safetensors", 0.8, 0.8),
                     ("minimax/bf16__apply_to_fl2va__rank256.safetensors", 0.5, 0.5)]


def test_ambiguous_missing_and_broken_tags_warn():
    stack, warnings = lora_stack("<lora:dup:1> <lora:gone:1> <lora:Motion_Repair:strong>", FILES)
    assert stack == [("a/dup.safetensors", 1.0, 1.0)]
    assert len(warnings) == 3
    assert "dup" in warnings[0] and "a/dup.safetensors" in warnings[0] and "b/dup.safetensors" in warnings[0]
    assert "gone" in warnings[1] and "strong" in warnings[2]


def test_nothing_to_resolve_against_means_no_stack_and_one_warning():
    assert lora_stack("", []) == ([], [])
    stack, warnings = lora_stack("<lora:Motion_Repair:1>", [])
    assert stack == [] and len(warnings) == 1


def test_the_stack_goes_on_the_model_with_model_strengths_only(monkeypatch):
    """#208: the Orrery Prompt puts its LoRAs on the model passing through it, as LoraLoaderModelOnly does."""
    import sys
    import types

    from orrery import loras

    calls, reads = [], []
    sd = types.SimpleNamespace(load_lora_for_models=lambda model, clip, lora, strength, clip_strength: (
        calls.append((model, clip, lora, strength, clip_strength)) or (f"{model}+{lora}", None)))
    utils = types.SimpleNamespace(load_torch_file=lambda path, safe_load=False: reads.append(path) or path.split("/")[-1])
    paths = types.SimpleNamespace(get_full_path_or_raise=lambda kind, name: f"/loras/{name}")
    comfy = types.ModuleType("comfy")
    comfy.sd, comfy.utils = sd, utils
    for name, mod in (("comfy", comfy), ("comfy.sd", sd), ("comfy.utils", utils), ("folder_paths", paths)):
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setattr(loras, "_LOADED", {})

    stack = [("turbo.safetensors", 0.8, 0.8), ("off.safetensors", 0.0, 1.0), ("style.safetensors", 0.5, 0.2)]
    assert loras.apply("model", stack) == "model+turbo.safetensors+style.safetensors"
    assert [(c[1], c[3], c[4]) for c in calls] == [(None, 0.8, 0), (None, 0.5, 0)]  # no CLIP; 0 leaves a LoRA out
    loras.apply("model", stack[:1])
    assert reads == ["/loras/turbo.safetensors", "/loras/style.safetensors"]  # read once while the clips use it
    assert list(loras._LOADED) == ["/loras/turbo.safetensors"]  # the ones the last clip used stay

