# Configuration

Where orrery keeps its files and which language model the wildcard manager uses.

Everything lives in the **orrery home** (`$ORRERY_HOME`, default `~/.orrery`):
`library/*.yaml`, `weights.json`, `galaxy.jsonl`, `orrery.yaml`, `history/`.
The CLI and the ComfyUI nodes share it. Inside ComfyUI the node's gear sets the
home folder (a pointer in `~/.config/orrery/home`); `ORRERY_HOME`, the CLI's
`--home` and a node's own `home` field win over it.

`~/.orrery/orrery.yaml` picks the model for the wildcard manager:

```yaml
models:
  library:
    backend: transformers
    path: /path/to/ComfyUI/models/LLM/Qwen3.5-4B
    device: auto        # cpu while ComfyUI needs the VRAM
    temperature: 0.3
```

Any OpenAI-compatible server works too (`backend: openai`, `base_url`, `model`).
Qwen3.5-4B handles semantic edits; 2B is too weak for them.

Inside ComfyUI the gear picks a text encoder as the language model instead;
see [wildcard-manager.md](wildcard-manager.md#the-language-model-in-comfyui).
