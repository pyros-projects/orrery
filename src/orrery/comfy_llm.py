"""A text encoder from ComfyUI's text_encoders folder, used as orrery's language model.

The same trick as Pixaroma's prompt nodes and core's TextGenerate: a complete LLM that a
diffusion pipeline loads as its text encoder can also write. Krea 2's Qwen3-VL-4B can; MiniMax
H3's encoder cannot (a Qwen3-VL-32B cut to 50 layers with no lm_head), so it is refused.

The choice lives in orrery.yaml, set from the node's settings:

    llm:
      file: qwen3vl_4b_bf16.safetensors   # a file in ComfyUI's text_encoders folder
      clip_type: minimax                  # how ComfyUI loads it; minimax suits Qwen3-VL builds
      entries: 12                         # a library the LLM creates starts with this many

A text encoder wired into the node's `clip` input wins over the setting and is never unloaded,
because the rest of the graph still needs it.
"""

import re
from pathlib import Path

DEFAULTS = {"file": None, "clip_type": "minimax", "entries": 12, "temperature": 0.3, "max_length": 768}
TRUNCATED = re.compile(r"minimax[_-]?h3|_h3_int|h3_te", re.IGNORECASE)  # encoders that cannot generate
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def can_write(file_name: str) -> bool:
    """False for encoders known to be truncated (MiniMax H3's): they load, but write garbage."""
    return not TRUNCATED.search(file_name or "")


def chat(prompt: str) -> str:
    """One user turn in Qwen's chat format, thinking off; used with skip_template, so a
    model's own conditioning template (Krea's "Describe the image…") stays out."""
    return f"<|im_start|>user\n{prompt.strip()}\n/no_think<|im_end|>\n<|im_start|>assistant\n"


def strip_reasoning(text: str) -> str:
    """The answer without any reasoning; an unfinished thought is no answer at all."""
    out = _THINK_BLOCK.sub("", text or "")
    if "</think>" in out:
        out = out.rsplit("</think>", 1)[-1]
    elif "<think>" in out:
        out = out.split("<think>", 1)[0]
    return out.replace("<think>", "").replace("</think>", "").strip()


def llm_config(home) -> dict:
    return {**DEFAULTS, **(home.config().get("llm") or {})}


def text_encoders() -> list[dict]:
    """The files the settings offer, with their size when ComfyUI can resolve them."""
    try:
        import folder_paths  # ComfyUI
        names = list(folder_paths.get_filename_list("text_encoders"))
    except Exception:  # noqa: BLE001 - outside ComfyUI
        return []
    files = []
    for name in names:
        path = folder_paths.get_full_path("text_encoders", name)
        size = Path(path).stat().st_size if path and Path(path).exists() else None
        files.append({"name": name, "size": size, "can_write": can_write(name)})
    return files


class ComfyBackend:
    """orrery's Backend protocol (`complete`) on a ComfyUI text encoder."""

    def __init__(self, file: str | None = None, clip=None, clip_type: str = "minimax",
                 temperature: float = 0.3, max_length: int = 768, seed: int = 0) -> None:
        self.file, self._clip, self.clip_type = file, clip, clip_type
        self.owned = clip is None  # only a model we loaded is ours to unload
        self.temperature, self.max_length, self.seed = temperature, max_length, seed
        self.name = Path(file).stem if file else "the wired text encoder"

    def _load(self):
        import comfy.sd  # ComfyUI
        import folder_paths

        path = folder_paths.get_full_path_or_raise("text_encoders", self.file)
        kind = getattr(comfy.sd.CLIPType, str(self.clip_type).upper(), comfy.sd.CLIPType.STABLE_DIFFUSION)
        return comfy.sd.load_clip(ckpt_paths=[path], embedding_directory=folder_paths.get_folder_paths("embeddings"),
                                  clip_type=kind, model_options={})

    def complete(self, prompt: str) -> str:
        if self._clip is None:
            self._clip = self._load()
        tokens = self._clip.tokenize(chat(prompt), skip_template=True, min_length=1, thinking=False)
        try:
            ids = self._clip.generate(tokens, do_sample=True, max_length=self.max_length,
                                      temperature=self.temperature, top_k=64, top_p=0.95, min_p=0.05,
                                      repetition_penalty=1.05, seed=self.seed)
        except AttributeError as err:
            if "generate" not in str(err):
                raise
            raise RuntimeError(f"{self.name} is not a language model and cannot write; pick a "
                               "Qwen3-VL build in orrery's settings.") from err
        out = self._clip.decode(ids)
        return strip_reasoning(out if isinstance(out, str) else str(out or ""))

    def release(self) -> None:
        """Give the VRAM back: unload first, then empty the cache (the cache alone frees nothing)."""
        if not self.owned or self._clip is None:
            return
        import comfy.model_management as mm  # ComfyUI

        try:
            mm.unload_model_and_clones(self._clip.patcher)
        except Exception:  # noqa: BLE001 - older ComfyUI
            mm.unload_all_models()
        mm.soft_empty_cache()
        self._clip = None
