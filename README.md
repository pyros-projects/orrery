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
| `__animal__` | one entry from `library/animal.yaml` (or `animal.txt`, one entry per line), weighted by learned weights |
| `__film/genre__` | a library in a folder: `library/film/genre.yaml` or `.txt`, as in z-explorer |
| `__animal[feline]__` | only entries tagged `feline` |
| `{a\|b\|c:3}` | inline choice; `:3` is a static weight |
| `{1-2$$__style__}` | pick 1–2 distinct values |
| `$hero = __animal__` | bind once, reuse everywhere |
| `> moody, cinematic` | enhancement instruction (recorded, not yet executed) |
| `: x8 seed=100 w1216 h832` | batch parameters |

Libraries live in the home folder (`~/.orrery` unless set otherwise, see
below) under `library/`, in any subfolders. Plain `.txt` wildcard files work as
they are (one entry per line, `#` comments), so Dynamic Prompts collections can
be dropped in; the first edit in the node turns one into YAML. When a name exists
as both, the YAML wins. The home folder is set in the node's gear (a pointer in
`~/.config/orrery/home`); `ORRERY_HOME`, `--home` and a node's own home field win
over it.

```bash
uv run orrery expand '$hero = __animal__
$hero in a {misty|frozen} forest' --seed 5 -n 3        # --json for machines
```

A template's bindings are its **dials**: turn one from outside without editing
the template, with a value or any DSL expression. A preset stays a preset; the
galaxy records the dials next to its picks.

```bash
uv run orrery compile @effects/subsurface_travel --set start="upper back" --set 'entity=__bh_entity__'
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

Built-in presets are read-only (`preset save NAME @NAME` makes a copy yours):
`tutorial/` walks through the DSL from a first wildcard to a three-shot H3
scene, `krea/` holds Krea 2 stills (natural language, the medium named, text
to render in quotes), and `h3/` holds MiniMax H3 scenes (dialogue in German
and Cantonese, a voiceover, fast cuts, an animated fable, on-screen music, and
an I2VA starter for your own stills, and a three-clip reel for H3 Motion
Context). `effects/` and `curator/` are Ito-style body-horror operators in the
lite format (Codie's subsurface travel, body suit and mirror replacement; the
Curator's paper, glass, clay and elastic lessons), each binding a dial over the
`bh_*` libraries. `fashion/` strings snobby adjectives and impossible shapes
into runway looks for Krea and H3 (`couture_*` libraries). `orrery preset list
--folder krea` shows them with their titles.

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

### The language model in ComfyUI

In the node, the gear picks orrery's language model: a text encoder from
ComfyUI's `text_encoders` folder that is a whole LLM, such as Krea 2's
`qwen3vl_4b` or a Qwen3-VL 8B build (MiniMax H3's encoder is cut short and
cannot write). A text encoder wired into the node's `clip` input wins over the
setting. When the node runs, the model

- creates a library the template names but you don't have (`__runway_shoes__`),
  with the number of entries set in the gear, using the lines around it as
  context;
- tops up `__name:30__` to at least 30 entries, once;
- follows directions written right after the library:
  `__film_scene__(at least 30 words, describe set, actions, characters)`. They
  never reach the prompt and stay with the library for later top-ups.

Everything a run needs goes to the model in one request (ComfyUI cannot
safely generate twice in one run), then the model unloads. What it wrote waits
on top of the Libraries tab under **To review**, marked in violet: **Accept**
keeps it, **Discard** drops it (a discarded library is written again on the
next run, so change the directions first). After every run the node refreshes
its libraries and points at anything new to review. Writes can also be undone
with `orrery lib undo`.

## MiniMax H3 screenplays

```bash
uv run orrery compile examples/forest.orr --seed 7              # h3-base
uv run orrery compile examples/forest.orr --target flat         # a still for image models
```

See [docs/h3.md](docs/h3.md) for the syntax. The compiler computes the
mechanical parts of the official guide (alignment lines, timestamps, speaker
IDs, `<d>` tags, camera sentences, `N/A`) and lints the rest; lint errors exit
with status 1. Built-in libraries: `__camera__`, `__h3style__`, `__instrument__`.

`@h3 ref2va` screenplays name their references once in a `CAST` block and
compile to the six full-reference sections, with every label numbered the way
the Reference to Video node numbers its inputs. `@h3/07_ref2va_sitcom` is the
official example as a screenplay. The long-video plan built on the cast is in
[docs/long-video.md](docs/long-video.md).

## ComfyUI

```bash
ln -s ~/projects/private/orrery/comfyui ~/repos/comfy-ui/custom_nodes/orrery
```

Restart ComfyUI. Nodes under **orrery**:

- **Orrery Prompt**: seed and target (`text`, `h3-base`, `flat`), optional
  `segment` → `text`, `picks`, `seed`, `width`, `height`, `length`, `lora_stack`,
  `load_index`, `save_index`.
  Wire `text` into your text encoder or the MiniMax H3 prompt input;
  `width`/`height` come from `: w… h…` or the `@h3` ratio, `length` is the
  screenplay's duration in frames for the H3 latent, `lora_stack` carries the
  `LORA:` lines as a LORA_STACK for any loader with a `lora_stack` input
  (LoraManager, Efficiency, Easy-Use …); unknown or ambiguous names are
  reported in the log and in the Test tab. For H3 Motion Context chains, a reel
  (`CHUNK` blocks, `repeat N|forever`, `$x~N`; see `docs/h3.md` 1d) writes one
  clip per run: `segment` counts up by itself, and `load_index`/`save_index`
  go into Load and Save Latent's `clip_index`. The node is the whole of orrery, in five tabs (⤢ opens the
  same app over the canvas, Esc brings it back):
  - **Prompt**: the template editor with syntax colours and completion
    (`__` libraries, `__creature[` tags, `$` bindings, camera words after
    `SHOT 5s |`, your LoRA files after `LORA:`). **New** starts a fresh H3
    screenplay or Krea prompt linked to no preset. Open a preset from the bar above it; ● marks unsaved
    edits; Save, Save as…, Revert. Under the editor, every binding is a
    **dial**: pick a library entry or choice, or type any expression; empty
    means its default roll. Saving bakes the dials in, and a galaxy output
    restores them. **Test** jumps to the Test tab and rolls.
  - **Test**: what the template makes, without queueing anything. **Rolls**
    shows three seeds (a reel: six clips at one seed, pageable through a
    forever loop). **Frequencies** rolls it 50, 200 or 500 times, across seeds
    or across a reel's clips, and shows how often every value comes up, plus
    how often each lint warning fires.
  - **Presets**: every preset with your newest output as its preview; search,
    folders, favorites, recents, a sample roll and the template per preset.
  - **Libraries**: edit wildcard lists by hand: entries, tags, weights, and
    the weight each entry learned from your ratings. Libraries that share a
    name prefix sit in a folder (`couture_form`, `couture_house` → couture);
    what the language model wrote waits on top for review. Built-ins become
    yours with **Make it mine**.
  - **Galaxy**: every logged output. love / like / nope / hate multiply the
    learned weight of each pick by 1.5 / 1.2 / 0.8 / 0.5 (re-rating replaces
    the factor). **Use template + seed** restores an output and sets the seed
    to fixed.
  - **Help**: the DSL at a glance, the tutorial lessons, writing tips.

  Workflows that used the old `preset` dropdown open with that preset loaded
  into the editor.
- **Orrery Log**: `picks` (+ `images`) → saves PNGs with the picks embedded and
  appends one line per output to `~/.orrery/galaxy.jsonl`. For videos saved by
  another node, put the file path into `media_path`.

## Development

```bash
uv run pytest          # also runs the editor completion tests if node is installed
uv run ruff check src tests comfyui
```
