"""`<lora:name:strength>` tags become a LORA_STACK: (path as ComfyUI lists it, model, clip)."""

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
