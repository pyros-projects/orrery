# The prompt language

Every construct of orrery's template language, where libraries live, how Dynamic Prompts packs come in, and how dials turn a template from outside. The H3 screenplay layer on top of it is in [h3.md](h3.md).

| Syntax | Meaning |
|---|---|
| `__animal__` | one entry from `library/animal.yaml` (or `animal.txt`, one entry per line), weighted by learned weights |
| `__film/genre__` | a library in a folder: `library/film/genre.yaml` or `.txt`, as in z-explorer |
| `__animal[feline]__` | only entries tagged `feline`; `[myth,!bird]` all of the terms (`!` none of), `[water\|deep_sea]` either |
| `__characters/cyberpunk#gender:female__` | only entries with that property (`props: {gender: female}` in the YAML, or `gender:female` typed into an entry's tag field); several `#key:value` must all match, in any case |
| `{a\|b\|c:3}` | inline choice; `:3` is a static weight (Dynamic Prompts' `{3::c\|a\|b}` works too) |
| `{\|red }car` | an empty option makes a word optional; the other options keep their spaces |
| `{1-2$$__style__}` | pick 1–2 distinct values |
| `{0.4-0.9}`, `{2-6}` | a number in between (both included), at the decimals written; recorded as a pick that learns per value, or per tenth of a finer range (`0.40–0.44`) |
| `<lora:style:0.4-0.9>` | a LoRA strength rolled per run, recorded as the pick `<lora:style>` (`:0.2-0.5` after it for CLIP); with a step (`0-1;0.1`) or a list it is a sweep instead ([wildcard-manager.md](wildcard-manager.md)) |
| `@style(0.8)` | short for `<lora:style:0.8>`, with every strength form: `@style(0.4-0.9)`, `@style(0.5,0.7)`, `@style(1.0:0.5)` |
| `$hero = __animal__` | bind once, reuse everywhere |
| `@include effects/living_clay` + indented `room = the salon` | embed a preset where it stands; indented `key = value` lines turn its dials, so a preset is an operator with parameters (its `@h3` line gives way to yours) |
| `$w.sfx` | a property of the entry `$w` rolled (empty if it has none): the sound follows the weather. A property is a template like an entry (`{a\|b}`, `__lib__`, `$w`, LoRA tags), rolled once when `$w` is bound, so every `$w.sfx` reads the same; filters and `?` conditions compare it as written |
| `__world/habitats#habitat:$animal.habitat__` | a filter that depends on what was rolled before (`#key:$var` or `#key:$var.field`): the manta ray lands in the sea, never on a beach |
| `? $w.kind=rain,snow: …` | a line kept only when the condition holds (`!=` for not); works for SFX lines too |
| `{? $w.kind=rain: wet\|dry}` | a choice made by a condition instead of the dice |
| `> make it moody and cinematic` | with a language model set in the node, it rewrites the rolled prompt as asked; in a screenplay a `>` before the first `SHOT` rewrites every shot's prose and one inside a `SHOT` only that shot's, never dialogue. The CLI records it with the picks |
| `--one detail, 5 to 8 words--` | a slot: the language model writes it where it stands, after everything else has rolled (see [wildcard-manager.md](wildcard-manager.md)) |
| `# a note` | a comment: a line starting with `#` never reaches the model (filters like `__lib#key:value__` are not comments) |
| `: x8 seed=100 w1216 h832` | batch parameters (`x8` and `seed=` are for the CLI; in ComfyUI the Run count and the seed widget) |
| `: grid __style__ × {dawn\|noon}` | every combination, one run each (3 styles × 2 = 6); everything else rolls the same in all of them. Axes: a library (with its `[tags]`), a choice, or a binding (`$hero`). Generate in the node queues them all, times a LoRA sweep; the CLI prints every cell per seed; Test rolls the axes like any pick |
| `: unique=__creature__`, `unique=$hero` | seeds in a row never repeat it: each seed takes the next step of one shuffled order, so 8 seeds give 8 different creatures and the next batch goes on from there. Learned weights don't steer it. The node sets the seed's control after generate to increment |

Several `:` lines add up; `grid` takes the rest of its line. A grid or `unique=` varies one clip
across runs, so a reel (which gives every run a clip of its own) refuses them.

Libraries live in the home folder (`~/.orrery` unless set otherwise, see
[configuration.md](configuration.md)) under `library/`, in any subfolders. Plain `.txt` wildcard files work as
they are (one entry per line, `#` comments), so Dynamic Prompts collections can
be dropped in; the first edit in the node turns one into YAML. An entry is a
template itself: `__80s/Women/80s_sports__` or `{a|b}` inside it expand too,
as in Dynamic Prompts (a library that comes back to itself is an error). Entries
may hold LoRAs, so a library can be a set of LoRA combinations
(`- <lora:ink:0.8> <lora:grain:0.4>`, `- @clay(0.4-0.9)`, `- ""` for none) used
as `LORA: __my_lora_sets__` or in a text prompt; which set rolled is a pick that
learns like any other. To keep LoRAs with the words they belong to, give one entry
both as fields and bind it: `$p = __poses__`, then `LORA: $p.loras` and `$p.action`. A sweep in an entry (`0.5,1.0`) runs at its first
strength and warns: `: grid __my_lora_sets__` runs every entry instead.
Library names are word characters and `/`: a file with `-` or spaces in its
path is not found. When a name exists
as both, the YAML wins. `orrery lib import FOLDER [--into dp] [--merge NAME]`
brings in a whole pack: names become word characters (`80s-pack/daily-wear.txt`
is `__80s_pack/daily_wear__`), references between its files follow, readmes and
duplicate files are skipped, and `--merge` turns a folder of one-prompt files
into one library. `orrery lib mv OLD NEW` (or Rename in the Libraries tab)
moves a library into a folder or a new name; its learned weights and every
`__OLD__` in your libraries and presets follow. The Libraries tab rereads the folder whenever you open it and
shows big libraries 200 entries at a time; its search filters the entries. The home folder is set in the node's gear (a pointer in
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
