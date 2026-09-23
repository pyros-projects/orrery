# orrery

A prompt language whose every expansion records which choices produced which
text, an LLM wildcard manager that edits your libraries in plain language, and
a compiler that turns screenplays into MiniMax H3 prompts.

```
$hero = __animal__
$hero in a {misty|frozen:3} forest, {1-2$$__style__}
```

Status: v0 (CLI + ComfyUI nodes). Design: [docs/concept.md](docs/concept.md),
[docs/h3.md](docs/h3.md), [docs/plan-v0.md](docs/plan-v0.md). Mock:
[docs/mock/](docs/mock/prompt-galaxy-mock.html).

## Setup

```bash
cd ~/projects/private/orrery
uv sync                  # core: only PyYAML
uv sync --extra local    # + torch/transformers for local LLMs in the wildcard manager
```

Everything lives in the **orrery home** (`$ORRERY_HOME`, default `~/.orrery`):
`library/*.yaml`, `weights.json`, `galaxy.jsonl`, `orrery.yaml`, `history/`.
The CLI and the ComfyUI nodes share it.

`~/.orrery/orrery.yaml` picks the model for the wildcard manager:

```yaml
models:
  library:
    backend: transformers
    path: /home/pyro/repos/comfy-ui/models/LLM/Qwen3.5-4B
    device: auto        # cpu while ComfyUI needs the VRAM
    temperature: 0.3
```

Any OpenAI-compatible server works too (`backend: openai`, `base_url`, `model`).
Qwen3.5-4B handles semantic edits; 2B is too weak for them.

## Prompt DSL

| Syntax | Meaning |
|---|---|
| `__animal__` | one entry from `library/animal.yaml`, weighted by learned weights |
| `__animal[feline]__` | only entries tagged `feline` |
| `{a\|b\|c:3}` | inline choice; `:3` is a static weight |
| `{1-2$$__style__}` | pick 1–2 distinct values |
| `$hero = __animal__` | bind once, reuse everywhere |
| `> moody, cinematic` | enhancement instruction (recorded, not yet executed) |
| `: x8 seed=100 w1216 h832` | batch parameters |

```bash
uv run orrery expand '$hero = __animal__
$hero in a {misty|frozen} forest' --seed 5 -n 3        # --json for machines
```

## Presets and template references

Anywhere a template is expected (CLI arguments, `preset save`), you can pass:

| Reference | Resolves to |
|---|---|
| `@forest`, `@h3/winter_forest` | a preset in `~/.orrery/presets/` (folders are path segments) |
| `#1a2b3c4d5e6f7a8b` | the exact template a `galaxy.jsonl` line recorded (its `template` hash) |
| a file path | the file's content |
| anything else | the text itself |

```bash
uv run orrery preset save h3/winter_forest examples/forest.orr --tags winter,moody
uv run orrery preset save keeper '#1a2b3c4d5e6f7a8b'   # a template that made a good output
uv run orrery preset tag keeper portrait
uv run orrery preset list --tag winter                 # or --folder h3
uv run orrery compile @h3/winter_forest --seed 7
```

Tags live in YAML front matter at the top of the preset file and are stripped
before expansion:

```
---
tags: [moody, winter]
---
@h3 t2va 16:9
…
```

The ComfyUI node records every template it uses under its hash, so each
galaxy line can be traced back to, and re-run from, its exact template.

## Wildcard manager

```bash
uv run orrery lib list
uv run orrery lib show animal                  # entries with learned weights
uv run orrery lib gen weather --template scene.orr
uv run orrery lib more style -n 8
uv run orrery lib edit animal 'Lösch alle katzenartigen Tiere und mach daraus eine neue Liste "feline"'
uv run orrery lib undo
```

The model only proposes. orrery shows how it understood the instruction and a
diff, and writes nothing until you confirm (`--yes` skips the question).
Every change can be undone, and learned weights move with renamed or moved
entries.

## MiniMax H3 screenplays

```bash
uv run orrery compile examples/forest.orr --seed 7              # h3-base
uv run orrery compile examples/forest.orr --target flat         # a still for image models
```

See [docs/h3.md](docs/h3.md) for the syntax. The compiler computes the
mechanical parts of the official guide (alignment lines, timestamps, speaker
IDs, `<d>` tags, camera sentences, `N/A`) and lints the rest; lint errors exit
with status 1. Built-in libraries: `__camera__`, `__h3style__`, `__instrument__`.

## ComfyUI

```bash
ln -s ~/projects/private/orrery/comfyui ~/repos/comfy-ui/custom_nodes/orrery
```

Restart ComfyUI. Nodes under **orrery**:

- **Orrery Prompt**: template, seed, target (`text`, `h3-base`, `flat`) →
  `text`, `picks`, `seed`. Wire `text` into your text encoder or the MiniMax H3
  prompt input. The optional `preset` dropdown replaces the template field
  (the list refreshes when ComfyUI reloads nodes).
- **Orrery Log**: `picks` (+ `images`) → saves PNGs with the picks embedded and
  appends one line per output to `~/.orrery/galaxy.jsonl`. For videos saved by
  another node, put the file path into `media_path`.

## Development

```bash
uv run pytest
uv run ruff check src tests comfyui
```
