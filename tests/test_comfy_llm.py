"""The text encoder as a language model: the pieces that don't need ComfyUI."""

from orrery.comfy_llm import can_write, chat, strip_reasoning


def test_chat_writes_explicit_turns_and_switches_thinking_off():
    text = chat("List five shoes.")
    assert text.startswith("<|im_start|>user\nList five shoes.")
    assert "/no_think" in text and text.endswith("<|im_start|>assistant\n")


def test_reasoning_is_stripped_and_an_unfinished_thought_is_no_answer():
    assert strip_reasoning("<think>hmm</think>\n[\"a\"]") == '["a"]'
    assert strip_reasoning("<think>still thinking") == ""
    assert strip_reasoning('["a", "b"]') == '["a", "b"]'


def test_truncated_encoders_cannot_write():
    assert not can_write("qwen3vl_32b_minimax_h3_int8_convrot.safetensors")
    assert can_write("qwen3vl_4b_bf16.safetensors") and can_write("qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors")


class FakeClip:
    def tokenize(self, text, **_):
        return text

    def generate(self, tokens, **_):
        return [1, 2]

    def decode(self, ids):
        return '["a"]'


def test_the_engine_writes_once_per_run():
    import pytest

    from orrery.comfy_llm import ComfyBackend
    backend = ComfyBackend(clip=FakeClip())
    assert backend.complete("list") == '["a"]'
    with pytest.raises(RuntimeError, match="once"):
        backend.complete("again")


def test_a_loaded_encoder_is_reused_by_the_next_run(monkeypatch):
    from orrery import comfy_llm
    loads = []
    monkeypatch.setattr(comfy_llm.ComfyBackend, "_load", lambda self: loads.append(self.file) or FakeClip())
    comfy_llm._CACHE.clear()
    for _ in range(2):
        comfy_llm.ComfyBackend(file="qwen3vl_4b_bf16.safetensors").complete("list")
    assert loads == ["qwen3vl_4b_bf16.safetensors"]


def test_frames_go_first_in_the_user_turn_one_vision_block_each():
    text = chat("What happens next?", images=3)
    block = "<|vision_start|><|image_pad|><|vision_end|>"
    assert text.startswith(f"<|im_start|>user\n{block * 3}\nWhat happens next?")


def test_the_engine_hands_the_frames_to_the_tokenizer():
    from orrery.comfy_llm import ComfyBackend
    seen = {}

    class SeeingClip(FakeClip):
        def tokenize(self, text, **kwargs):
            seen.update(kwargs, text=text)
            return text

    frames = [object(), object()]
    ComfyBackend(clip=SeeingClip()).complete("next?", images=frames)
    assert seen["image"] is frames and seen["text"].count("<|image_pad|>") == 2
