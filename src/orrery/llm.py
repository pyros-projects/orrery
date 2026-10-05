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

Without a `models.library`, the API endpoint set in the node's settings writes (orrery.endpoint).
Models only ever *propose*; orrery validates their JSON before anything is written.
"""

import base64
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Protocol

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


# Where a prompt shows the model its pictures (#333): a writer's text may put them after what they belong to, which
# a small model weighs differently from pictures first. Without it they come first; with several, picture i stands
# at the i-th, the ones left over at the last.
PICTURES = "<|orrery_pictures|>"


def placed(prompt: str, pictures: int) -> list[tuple[str, int]]:
    """The prompt as (text, pictures after it) pieces: where its PICTURES marks stand, or all of them first."""
    parts = prompt.split(PICTURES)
    if len(parts) == 1:
        return [("", pictures), (prompt, 0)]
    marks = len(parts) - 1
    counts = [1 if i < pictures else 0 for i in range(marks)]
    counts[-1] += max(0, pictures - marks)
    return [*zip(parts[:-1], counts), (parts[-1], 0)]


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


FRAME_EDGE = 768  # the long edge of a frame the model sees: enough to read it, a few hundred tokens
RETRIES = (2, 6)  # seconds to wait before asking a busy endpoint again
_QUIRKS: dict[tuple[str, str], set[str]] = {}  # (url, model) → what the model refused, so the next request adapts


def data_urls(images, edge: int = FRAME_EDGE) -> list[str]:
    """Frames as JPEG data URLs, the long edge at most `edge`: a ComfyUI IMAGE batch (frames × height × width ×
    RGB, 0–1), PIL images, or paths."""
    from PIL import Image  # ComfyUI ships Pillow; only frames need it

    if hasattr(images, "shape") and len(images.shape) == 4:  # an IMAGE batch, torch or numpy
        import numpy as np
        batch = images.detach().cpu().numpy() if hasattr(images, "detach") else np.asarray(images)
        pictures = [Image.fromarray((batch[i].clip(0, 1) * 255).round().astype("uint8")) for i in range(len(batch))]
    else:
        pictures = [p if isinstance(p, Image.Image) else Image.open(p) for p in images]
    urls = []
    for picture in pictures:
        picture = picture.convert("RGB")
        picture.thumbnail((edge, edge))
        buffer = io.BytesIO()
        picture.save(buffer, "JPEG", quality=88)
        urls.append("data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode())
    return urls


class OpenAIBackend:
    """Any server that speaks the OpenAI chat-completions protocol. It adapts to what a model refuses (newer
    OpenAI models want max_completion_tokens, and some no temperature but their own) and remembers it per model."""

    def __init__(self, base_url: str, model: str, api_key_env: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 1024, name: str | None = None,
                 api_key: str | None = None) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key if api_key is not None else os.environ.get(api_key_env, "") if api_key_env else ""
        self.temperature, self.max_tokens = temperature, max_tokens
        self.name = name or model

    def _body(self, prompt: str, images) -> dict:
        if images is None or not len(images):
            content = prompt.replace(PICTURES, "")
        else:  # the frames where the prompt puts them (#333), else first; as Picture 1, 2 … in the prompt
            urls, content = iter(data_urls(images)), []
            for text, n in placed(prompt, len(images)):
                content += [*([{"type": "text", "text": text}] if text.strip() else []),
                            *({"type": "image_url", "image_url": {"url": next(urls)}} for _ in range(n))]
        body = {"model": self.model, "messages": [{"role": "user", "content": content}],
                "temperature": self.temperature, "max_tokens": self.max_tokens}
        for quirk in _QUIRKS.get((self.url, self.model), ()):
            _adapt(body, quirk)
        return body

    def complete(self, prompt: str, images=None) -> str:
        applied = set(_QUIRKS.get((self.url, self.model), ()))  # what this body adapted to (#333: takes ask at once)
        body, waits = self._body(prompt, images), list(RETRIES)
        while True:
            request = urllib.request.Request(self.url, data=json.dumps(body).encode(), method="POST",
                                             headers={"Content-Type": "application/json",
                                                      **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    return json.loads(response.read())["choices"][0]["message"]["content"] or ""
            except urllib.error.HTTPError as err:
                message, param = _error(err)
                quirk = _quirk(err.code, param, message)
                if quirk and quirk not in applied:  # learned here, or by a request asked beside this one
                    _QUIRKS.setdefault((self.url, self.model), set()).add(quirk)
                    applied.add(quirk)
                    _adapt(body, quirk)
                    continue
                if err.code in (408, 429, 500, 502, 503, 504) and waits:
                    time.sleep(min(float(err.headers.get("Retry-After") or waits[0]), 30))
                    waits.pop(0)
                    continue
                hint = " Check the key in orrery's settings." if err.code in (401, 403) else ""
                raise RuntimeError(f"{self.name}: {message} (HTTP {err.code}).{hint}") from None
            except (urllib.error.URLError, TimeoutError) as err:
                if waits:
                    time.sleep(waits.pop(0))
                    continue
                reason = getattr(err, "reason", err)
                raise RuntimeError(f"{self.name}: cannot reach {self.url} ({reason}).") from None


def _error(err: urllib.error.HTTPError) -> tuple[str, str]:
    """The endpoint's own words for an error, and the parameter it names."""
    try:
        data = json.loads(err.read() or b"{}")
    except ValueError:
        data = {}
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or err.reason), str(error.get("param") or "")
    return str(error or err.reason), ""


def _quirk(status: int, param: str, message: str) -> str | None:
    """What to change when a model refuses a parameter: `max_tokens` for `max_completion_tokens`, or no temperature."""
    if status != 400:
        return None
    if param == "max_tokens" or "max_completion_tokens" in message:
        return "completion_tokens"
    if param == "temperature" or "'temperature'" in message:
        return "no_temperature"
    return None


def _adapt(body: dict, quirk: str) -> None:
    if quirk == "completion_tokens" and "max_tokens" in body:
        body["max_completion_tokens"] = body.pop("max_tokens")
    elif quirk == "no_temperature":
        body.pop("temperature", None)


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
        text = tok.apply_chat_template([{"role": "user", "content": prompt.replace(PICTURES, "")}], tokenize=False,
                                       add_generation_prompt=True, enable_thinking=False)
        inputs = tok(text, return_tensors="pt").to(self._model.device)
        output = self._model.generate(**inputs, max_new_tokens=self.max_new_tokens,
                                      do_sample=True, temperature=self.temperature)
        return tok.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def backend_for(home, role: str) -> Backend:
    cfg = (home.config().get("models") or {}).get(role)
    if not cfg:
        from orrery import endpoint  # it builds on this module
        if (api := endpoint.backend(home)) is not None:
            return api
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
