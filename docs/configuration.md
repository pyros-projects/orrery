# Configuration

Where orrery keeps its files and which language model the wildcard manager uses.

Everything lives in the **orrery home** (`$ORRERY_HOME`, default `~/.orrery`):
`library/*.yaml`, `weights.json`, `galaxy.jsonl` (the gallery; the file keeps the name it had when the gallery was the galaxy), `orrery.yaml`, `history/`.
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
The gear writes it to `orrery.yaml` as well, with two settings only the file has:

```yaml
llm:
  file: qwen3vl_4b_bf16.safetensors   # a text encoder in ComfyUI's text_encoders folder
  entries: 12                         # a library the model creates starts with this many
  max_tokens: 16000                   # the longest answer it may write
  temperature: 0.3                    # libraries, slots and > rewrites: reliable judgement
  writer_temperature: 0.8             # the Write menu: each idea a different one
  takes: {slot: 3, enhance: 3, rolled: 3, new: 3}   # what a 🎲 asks for: a slot's takes, a > line's, rolls of a library, new entries
```

Or an API endpoint, which then does all of the language model's work
([wildcard-manager.md](wildcard-manager.md#the-language-model-over-an-api)):

```yaml
llm:
  source: api                         # api, or comfy for the text encoder above
  api:
    base_url: https://api.openai.com/v1
    model: gpt-6-luna
    key_env: OPENAI_API_KEY           # ComfyUI's environment, else the home's .env
```

The key stays out of `orrery.yaml`: the gear writes it to `.env` in the orrery
home (`OPENAI_API_KEY=…`, readable by you only). Without a `models.library`,
`orrery lib` uses the endpoint too.

The Write menu's prompts, one per writer, are edited in the gear's **Writers**
section; an edit lives in `writers/` in the orrery home.
