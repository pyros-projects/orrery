"""LLM backends for the wildcard manager, chosen per role in orrery.yaml:

    models:
      library:
        backend: transformers          # local, needs the `local` extra
        path: /home/pyro/repos/comfy-ui/models/LLM/Qwen3.5-2B
        device: auto                   # auto | cpu | cuda
      # or any OpenAI-compatible server (llama.cpp, LM Studio, Ollama, vLLM):
      #   backend: openai
      #   base_url: http://127.0.0.1:8080/v1
      #   model: qwen3.5-2b
      #   api_key_env: OPENAI_API_KEY  # optional

Models only ever *propose*; orrery validates their JSON before anything is written.
"""

import json
import os
import re
import urllib.request
from typing import Protocol

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class InvalidProposal(ValueError):
    """The model's answer cannot be used safely."""


class Backend(Protocol):
    name: str

    def complete(self, prompt: str, images=None) -> str: ...  # images: frames the model sees, if it can


def extract_json(text: str):
    """Parse the JSON value in a model reply, tolerating fences and a sentence around it."""
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text.strip()]
    starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
    if starts:
        start = min(starts)
        end = max(text.rfind("]"), text.rfind("}"))
        if end > start:
            candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    raise InvalidProposal(f"the model gave no usable JSON: {text.strip()[:160]!r}")


class FakeBackend:
    """Deterministic replies for tests: returns them in order, then repeats the last."""

    def __init__(self, replies: list[str], name: str = "fake") -> None:
        self.replies = list(replies) or ["[]"]
        self.name = name
        self.prompts: list[str] = []
        self.images: list = []

    def complete(self, prompt: str, images=None) -> str:
        self.prompts.append(prompt)
        self.images.append(images)
        return self.replies[min(len(self.prompts) - 1, len(self.replies) - 1)]


class OpenAIBackend:
    """Any server that speaks the OpenAI chat-completions protocol."""

    def __init__(self, base_url: str, model: str, api_key_env: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 1024, name: str | None = None) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = os.environ.get(api_key_env, "") if api_key_env else ""
        self.temperature, self.max_tokens = temperature, max_tokens
        self.name = name or model

    def complete(self, prompt: str, images=None) -> str:
        if images is not None:
            raise ValueError(f"{self.name} cannot see images; pick a Qwen3-VL text encoder in ComfyUI.")
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read())["choices"][0]["message"]["content"]


class TransformersBackend:
    """A local Hugging Face model, e.g. the Qwen3.5 models in ComfyUI/models/LLM."""

    def __init__(self, path: str, device: str = "auto", max_new_tokens: int = 768,
                 temperature: float = 0.7, name: str | None = None) -> None:
        self.path, self.device = path, device
        self.max_new_tokens, self.temperature = max_new_tokens, temperature
        self.name = name or os.path.basename(path.rstrip("/"))
        self._model = self._tokenizer = None

    def _load(self) -> None:
        try:
            import transformers
        except ImportError as err:
            raise RuntimeError("the transformers backend needs the `local` extra: "
                               "uv sync --extra local") from err
        self._tokenizer = transformers.AutoTokenizer.from_pretrained(self.path)
        kwargs = {"dtype": "auto", "device_map": "cpu" if self.device == "cpu" else self.device}
        try:
            self._model = transformers.AutoModelForCausalLM.from_pretrained(self.path, **kwargs)
        except ValueError:
            # Qwen3.5 checkpoints are natively multimodal; text generation still works.
            self._model = transformers.AutoModelForImageTextToText.from_pretrained(self.path, **kwargs)

    def complete(self, prompt: str, images=None) -> str:
        if images is not None:
            raise ValueError(f"{self.name} cannot see images; pick a Qwen3-VL text encoder in ComfyUI.")
        if self._model is None:
            self._load()
        tok = self._tokenizer
        text = tok.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False,
                                       add_generation_prompt=True, enable_thinking=False)
        inputs = tok(text, return_tensors="pt").to(self._model.device)
        output = self._model.generate(**inputs, max_new_tokens=self.max_new_tokens,
                                      do_sample=True, temperature=self.temperature)
        return tok.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def backend_for(home, role: str) -> Backend:
    cfg = (home.config().get("models") or {}).get(role)
    if not cfg:
        raise RuntimeError(f"no model configured for '{role}': add models.{role} to "
                           f"{home.config_path} (see `orrery lib --help`)")
    kind = cfg.get("backend")
    if os.environ.get("ORRERY_FORCE_FAKE_LLM") and kind != "fake":
        raise RuntimeError(f"tests force the fake LLM backend; refusing '{kind}'")
    temperature = float(cfg.get("temperature", 0.3))  # low: edits need reliable judgement
    if kind == "fake":
        return FakeBackend(cfg.get("replies") or [], name=cfg.get("name", "fake"))
    if kind == "openai":
        return OpenAIBackend(cfg["base_url"], cfg["model"], cfg.get("api_key_env"),
                             temperature=temperature, name=cfg.get("name"))
    if kind == "transformers":
        return TransformersBackend(cfg["path"], cfg.get("device", "auto"),
                                   int(cfg.get("max_new_tokens", 768)), temperature, cfg.get("name"))
    raise RuntimeError(f"unknown backend '{kind}' for '{role}' (transformers, openai, fake)")
