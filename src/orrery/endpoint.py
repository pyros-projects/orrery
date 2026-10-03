"""The language model as an API endpoint (#165): OpenAI, or any server that speaks its chat protocol
(llama.cpp, LM Studio, OpenRouter). Set in the node's settings and kept in orrery.yaml:

    llm:
      source: api                          # api, or comfy: a text encoder in ComfyUI (orrery.comfy_llm)
      api:
        base_url: https://api.openai.com/v1
        model: gpt-5.4-mini
        key_env: OPENAI_API_KEY            # the key: ComfyUI's environment, else the home's .env

The key never goes into orrery.yaml: the settings write it to the home's `.env`, and send back only
that it is set and how it ends. While the source is `api`, every language-model function uses the
endpoint: a run's libraries, slots and `> enhance`, the Write menu and `orrery lib`. It runs beside
ComfyUI, with no VRAM and no queue.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from orrery.comfy_llm import llm_config
from orrery.home import Home, write_atomic
from orrery.llm import OpenAIBackend

DEFAULT_URL = "https://api.openai.com/v1"
DEFAULT_KEY_ENV = "OPENAI_API_KEY"
CHECK = "Reply with the single word OK."
# what an endpoint's model list holds besides chat models
NOT_CHAT = re.compile(r"embed|tts|whisper|transcri|dall-e|image|audio|realtime|moderation|search|davinci|babbage|"
                      r"instruct|live|translate|sora|research|codex|-pro\b|-pro-", re.IGNORECASE)
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_]\w*)\s*=\s*(.*?)\s*$")


def config(home: Home) -> dict:
    llm = home.config().get("llm") or {}
    api = llm.get("api") or {}
    return {"source": llm.get("source") or "comfy", "base_url": api.get("base_url") or DEFAULT_URL,
            "model": api.get("model") or "", "key_env": api.get("key_env") or DEFAULT_KEY_ENV}


def env_path(home: Home) -> Path:
    return home.root / ".env"


def read_env(path: Path) -> dict[str, str]:
    """NAME=value lines, `export` and quotes allowed, `#` comments skipped."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _LINE.match(line)
        if m and not line.lstrip().startswith("#"):
            value = m.group(2)
            out[m.group(1)] = value[1:-1] if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"" else value
    return out


def key(home: Home, cfg: dict | None = None) -> tuple[str, str]:
    """The key and where it is: "env" (ComfyUI's environment, which wins), "file" (the home's .env), or ""."""
    name = (cfg or config(home))["key_env"]
    if os.environ.get(name):
        return os.environ[name], "env"
    value = read_env(env_path(home)).get(name, "")
    return value, "file" if value else ""


def save_key(home: Home, name: str, value: str) -> None:
    """Put the key in the home's .env, the file's other lines as they are; readable by its owner only."""
    path, line = env_path(home), f"{name}={value.strip()}"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    at = next((i for i, x in enumerate(lines) if (m := _LINE.match(x)) and m.group(1) == name), None)
    if at is None:
        lines.append(line)
    else:
        lines[at] = line
    write_atomic(path, "\n".join(lines) + "\n")
    path.chmod(0o600)


def hint(value: str) -> str:
    """How a key ends, to tell keys apart without showing one."""
    return f"…{value[-4:]}" if len(value) > 8 else "set"


def _local(url: str) -> bool:
    return bool(re.match(r"https?://(127\.0\.0\.1|localhost)[:/]", url))


def backend(home: Home, temperature: float | None = None) -> OpenAIBackend | None:
    """The endpoint as orrery's language model while the settings choose it, else None."""
    cfg = config(home)
    if cfg["source"] != "api" or not cfg["model"]:
        return None
    if os.environ.get("ORRERY_FORCE_FAKE_LLM") and not _local(cfg["base_url"]):
        raise RuntimeError("tests force the fake LLM backend; refusing the API endpoint")
    llm = llm_config(home)
    return OpenAIBackend(cfg["base_url"], cfg["model"], api_key=key(home, cfg)[0],
                         temperature=float(llm["temperature"] if temperature is None else temperature),
                         max_tokens=int(llm["max_tokens"]))


def models(base_url: str, api_key: str) -> list[str]:
    """The chat models the endpoint offers, sorted."""
    request = urllib.request.Request(base_url.rstrip("/") + "/models",
                                     headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read())
    ids = [str(m.get("id")) for m in data.get("data") or [] if isinstance(m, dict) and m.get("id")]
    return sorted(i for i in ids if not NOT_CHAT.search(i))


def check(base_url: str, api_key: str, model: str) -> dict:
    """Whether the endpoint takes the key and the model answers: {ok, models, seconds | error}."""
    out: dict = {"ok": False, "models": []}
    try:
        out["models"] = models(base_url, api_key)
    except urllib.error.HTTPError as err:
        refused = " The endpoint refused the key." if err.code in (401, 403) else ""
        return {**out, "error": f"{base_url} answered HTTP {err.code} for its model list.{refused}"}
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        return {**out, "error": f"Cannot reach {base_url} ({getattr(err, 'reason', err)})."}
    if not model:
        return {**out, "error": "Pick a model."}
    start = time.monotonic()
    try:
        answer = OpenAIBackend(base_url, model, api_key=api_key, temperature=0.3, max_tokens=1000).complete(CHECK)
    except RuntimeError as err:
        return {**out, "error": str(err)}
    return {**out, "ok": True, "seconds": round(time.monotonic() - start, 1), "answer": answer.strip()[:40]}
