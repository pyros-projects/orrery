# orrery v0 build plan

Goal: software Pyro can use in ComfyUI: seeded prompt expansion that records
picks, the H3 compiler, the LLM wildcard manager (the differentiator), and the
nodes. Galaxy UI comes after v0.

Rules: test-first; each slice finishes with passing tests and a commit on the
`v0` branch; no slice needs a GPU to verify. Core runtime dependency: PyYAML
only. Heavy LLM dependencies live behind an optional extra.

## Shared layout

- `src/orrery/`: the package; CLI entry point `orrery` (argparse, no extra
  dependency).
- **orrery home** (`$ORRERY_HOME`, default `~/.orrery/`): `orrery.yaml`
  (config), `library/*.yaml`, `weights.json`, `galaxy.jsonl`, `history/`
  (library snapshots for undo). The CLI and the ComfyUI nodes share it.
- Determinism: an own seeded PRNG plus an own weighted pick, never
  `random.choices`, so picks stay stable across Python versions.

## Slice 1: core DSL

`__lib__`, `{a|b:3}`, `{1-2$$…}`, `$bind = …`, `> enhance`, `: x8 seed=… w… h…`.
`expand(template, seed, libraries, weights) -> Expansion(text, picks, params)`.
YAML libraries: a list of strings or `{value, tags, weight}`.

Done when: tests prove same seed gives same text and picks; weighted
selection matches its weights statistically; bindings and multi-picks work;
a missing library raises an error naming it; `orrery expand "…" --seed 5 -n 3`
prints text plus picks (`--json` for machines).

## Slice 2: H3 compiler

Screenplay front end (`.orr`) → scene model → writers `h3-base`, `flat` → lint,
as specified in [h3.md](h3.md). `orrery compile scene.orr --target h3-base --seed 7`.

Done when: golden tests reproduce the four official guide cases (T2VA, I2VA,
FL2VA, L2VA) structurally: field order, alignment lines byte-identical to the
guide, shot timestamps, speaker IDs, `<d>` wrapping, camera sentences, `N/A`
rules; each lint rule has a failing and a passing test.

## Slice 3: wildcard manager CLI

- `orrery lib list | show <name>`
- `orrery lib gen <name> [--template scene.orr]`: generate a missing library
  from template context.
- `orrery lib more <name> [-n 8]`
- `orrery lib edit <name> "<instruction in any language>"`: the model returns
  operations (`remove`, `add`, `rename`, `new_lists`, `note`); orrery
  validates them, shows a diff, and applies only after confirmation (`--yes`
  for scripts).
- `orrery lib undo`: restore the last snapshot.
- Learned weights move with renamed and moved entries.

LLM backends behind one interface, chosen per role in `orrery.yaml`:
`transformers` (local, e.g. `ComfyUI/models/LLM/Qwen3.5-2B`, optional extra
`local`), `openai` (any OpenAI-compatible server: llama.cpp, LM Studio,
Ollama, vLLM), and `fake` (deterministic, for tests; forced in the test suite).

Done when: diff → apply → undo round-trips on a real library file in tests
(fake backend); invalid model output (unknown entries, broken JSON) is
rejected with a clear message instead of corrupting a library; one real smoke
run with a local Qwen model produces a valid proposal.

## Slice 4: ComfyUI nodes

`comfyui/` node pack, symlinked into `ComfyUI/custom_nodes/orrery`:

- **Orrery Prompt**: template, seed, target (`flat`/`h3-base`) → `text`,
  `picks` (JSON), `seed`.
- **Orrery Log**: images or video + picks → one line in `galaxy.jsonl`, and
  picks in PNG metadata for images.

Done when: the pack imports under ComfyUI's Python 3.13 without a GPU, node
functions are covered by tests, and the symlink is in place.

## Acceptance by Pyro

One evening in ComfyUI: an image run with Orrery Prompt + Log, one H3 run
with a compiled screenplay, and one semantic library edit with a local model.
Findings decide what comes next (Galaxy v0, densifier, Ref2VA).
