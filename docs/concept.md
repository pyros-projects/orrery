# orrery: concept

Status: concept, nothing built yet (2026-09-23).
Interactive mock: https://claude.ai/artifact/9RpLrL2GnDKfaiUZo8fGYC

## One sentence

A prompt language whose every expansion records *which choices produced which
text*, plus a galaxy of images that learns from your love/like/nope/hate
verdicts and steers the next batch toward the regions you like.

## Why the name

An orrery is a clockwork model of the heavens: turn the crank and every body
lands in an exact, reproducible position. orrery does the same for prompt
space. The same template, library and seed always yield the same picks, and the
same picks always yield the same text.

## The problem

Random prompt exploration in ComfyUI exists (wildcards, `{a|b}`, OneButtonPrompt,
Impact Pack, PPP), but none of it records **which choice led to which image**.
Without that, you can't learn which region of prompt space produces good
results, and you can't steer toward it. The generator loses its history the
moment it hands over a string.

OneButtonPrompt no longer works with current ComfyUI. Its value was a huge
hand-curated category tree tuned for SD1.5 tags, not its mechanics, and that
tree has aged badly.

## The load-bearing decision

> Every expansion returns `(text, picks)`, not just `text`.

`picks` maps each choice point (a library reference, an inline choice, a
binding, an enhancement) to the value drawn, deterministically from the seed.
Everything else follows from this. Images know their coordinates, the galaxy is
an accumulation of those coordinates, and ratings can flow back as weights on
exactly the values that produced a result.

## The DSL (v0)

Lineage: z-explorer's grammar (`__variable__`, `>` enhancement, `:` batch
parameters), plus the best ideas from PPP, AB Wildcard and Wildcards-rework.

```
$hero = __animal__
$hero in a {misty|burning|frozen:3} forest, {1-2$$__style__}, $hero's eyes glowing
> moody, cinematic
: x8 seed=100 w1216 h832
```

| Syntax | Meaning |
|---|---|
| `__animal__` | pick one entry from `library/animal.txt`, weighted by learned weights |
| `{a\|b\|c:3}` | inline choice; `:3` is a static weight |
| `{1-2$$__style__}` / `{2$$a\|b\|c}` | pick N (or a range) of distinct values |
| `$name = expr` | bind once per expansion, reuse everywhere (the hero stays the same fox) |
| `> instruction` | optional LLM enhancement; logged as a pick |
| `: x8 seed=100 w1216 h832` | batch count, seed, size |

Deferred until missed in real use: conditionals, history recall
(`__name[0]__`), model-variant detection, negative-prompt routing.

## The wildcard manager

Libraries are YAML files in `library/`: a list of entries, each optionally
carrying tags and a static weight, so one library can serve tag-based picks
(AB Wildcard style) as well as plain random ones. A bare list of strings is
valid YAML too, so the simple case stays simple. The manager works on them with
an LLM:

- **Missing wildcard:** a template references `__weather__` and no library
  exists, so the LLM generates one *from the template's context* and marks it
  as generated.
- **Generate more:** N new entries in the spirit of the existing list.
- **Semantic edits in natural language, any language:** "remove all cat-like
  animals and make them a new list `feline`", "make every entry more specific",
  "add 8 mythical creatures".

Rules:

- The LLM never writes directly. It returns structured operations
  (`remove`, `add`, `rename`, `new_lists`, `note`), shown as a **diff**, then
  Apply or Discard. Every applied change can be undone.
- Learned weights move with their entries on rename and move (a loved lynx stays
  loved in `__feline__`).
- Models are configurable per role (library manager, `>` enhancement).
  Defaults are local, loaded with transformers from `ComfyUI/models/LLM`
  (currently Qwen3.5-4B, Qwen3.5-2B, Qwen3-VL-4B). List operations are small
  structured tasks, and Qwen3.5-2B should be enough. A remote model is
  optional, never required.

## Three layers

Each layer is usable on its own. **No layer starts until the previous one has
been used on real images.** Each slice must be small enough that an agent can
build and verify it autonomously, because a project that stalls at the agent's
capability ceiling stalls for good.

| Layer | What | Done when |
|---|---|---|
| **1. Core library + CLI** | Pure Python, no runtime dependencies for the core: parser, seeded expander returning `(text, picks)`, library loading, learned-weight file. CLI: `orrery expand "…" --seed 5 -n 10`, `orrery lib gen weather`, `orrery lib edit animal "…"` (diff → confirm). LLM ops behind a small backend interface (local transformers first). | Tests pass; the CLI expands real templates; one semantic edit round-trips through diff → apply → undo on a real library. |
| **2. ComfyUI nodes** | *Orrery Prompt* (template, seed → `text`, `picks`, `seed`) and *Orrery Log* (images + picks → PNG metadata, and one line per image in `galaxy.jsonl`). Standard ComfyUI everywhere else. | One real workflow has logged 50 images. |
| **3. Galaxy v0** | A single local HTML page over `galaxy.jsonl` + thumbnails: filter by pick, rate with love/like/nope/hate, ratings update the learned-weight file that layer 1 reads. The wildcard manager lives here as a UI over layer 1's operations. | 100 real images rated, and the next batch visibly shifts toward loved regions. |

## Data formats

- `library/<name>.yaml`: a list of entries; an entry is a string or
  `{value, tags, weight}`. Generated lists carry a header comment naming the
  model and date.
- `orrery.yaml`: configuration, including the model per role
  (`models.library`, `models.enhance`).
- `weights.json`: `{"__animal__=fox": 1.6, …}`, multipliers on top of static
  weights; default 1.0, floor 0.15.
- `galaxy.jsonl`: one line per image:
  `{ts, image, seed, template, text, picks, model, size, rating}`; `template`
  is a content hash of the template source.

Ratings map to weight deltas: love +0.6, like +0.25, nope −0.25, hate −0.6.
Re-rating reverts the previous delta first. **No numeric rating scale, ever.**

## Non-goals

- No platform: no Kiln, no Northstar, no own image runtime, no training.
  ComfyUI stays the front end.
- No 2D embedding map in v0. A CLIP + UMAP star map is v1, only if still wanted
  after v0 is in use.
- No hash-gated model admission, no evidence ceremonies. Any model is allowed.
- No accounts, no cloud requirement.

## Prior art

- **z-explorer** (Pyro): the grammar and the "unknown output loop" philosophy.
- **ai-foundry / Kiln**: the *Prompt Galaxy* idea and its stated dependency:
  the galaxy is an accumulation of lineage, not a visualization. Kiln shipped
  Curate and stalled before the galaxy.
- **crucible**: the *Probe Runs & Prompt Galaxy* backlog. orrery takes the
  lineage idea without Temper's run contract; measurement instruments (seed
  lotteries, token gravity, per-block ΔW) can plug in later.
- **ComfyUI ecosystem (checked 2026-09-22):** Prompt PostProcessor (acorderob),
  AB Wildcard, Wildcards-rework (aria1th), Impact Pack wildcards, native `{a|b}`
  in the ComfyUI frontend, DynamicPromptComposer, RandomTagWeights, CreaPrompt.
  None of them records picks per image or learns from ratings.

## Decisions (2026-09-23)

- Library format: **YAML** with optional tags and weights.
- LLM per role (library manager, enhancement): **configurable**.

## Open questions

- Should real prompt corpora (HuggingFace prompt datasets such as
  `xzuyn/Stable-Diffusion-Prompts-Deduped-2.008M`) be usable as a library
  source, sampling whole human-written prompts instead of composing them?
