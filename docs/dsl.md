# The prompt language

Every construct of orrery's template language, where libraries live, how Dynamic Prompts packs come in, and how dials turn a template from outside. The H3 screenplay layer on top of it is in [h3.md](h3.md).

| Syntax | Meaning |
|---|---|
| `__animal__` | one entry from `library/animal.yaml` (or `animal.txt`, one entry per line), weighted by learned weights |
| `__film/genre__` | a library in a folder: `library/film/genre.yaml` or `.txt`, as in z-explorer |
| `__clothing/*__`, `__clothing/**__`, `__scenes/features*__` | a glob: one of the libraries it matches (this folder; it and below; a name's start), each as likely however many entries it has, then its entry. The pick learns on the library that rolled, and brackets filter as ever (`__clothing/**[winter]__`) |
| `__animal[feline]__` | only entries tagged `feline`. The brackets take a predicate: `[myth, !bird]` all of the terms (`!` not), `[water\|deep_sea]` either, `[habitat=sea]` a property (`!=` not that value), `[size=small\|tiny]` either value of a key, `[habitat=$a.habitat]` what rolled before |
| `__characters/cyberpunk#gender:female__` | only entries with that property (`props: {gender: female}` in the YAML, or `gender:female` typed into an entry's tag field); several `#key:value` must all match, in any case |
| `{a\|b\|c:3}` | inline choice; `:3` is a static weight (Dynamic Prompts' `{3::c\|a\|b}` works too) |
| `{\|red }car` | an empty option makes a word optional; the other options keep their spaces |
| `{30% in the rain}` | the words three times in ten, nothing otherwise, learned like a choice; when nothing rolls, the space before it goes too (`a fox {30% in the rain}.` → `a fox.`) |
| `{1-2$$__style__}` | pick 1–2 distinct values, joined with `, `; `{2$$ and $$a\|b\|c}` joins them with ` and ` (Dynamic Prompts' form) |
| `{0.4-0.9}`, `{2-6}` | a number in between (both included), at the decimals written; recorded as a pick that learns per value, or per tenth of a finer range (`0.40–0.44`) |
| `<lora:style:0.4-0.9>` | a LoRA strength rolled per run, recorded as the pick `<lora:style>` (`:0.2-0.5` after it for CLIP); with a step (`0-1;0.1`) or a list it is a sweep instead ([wildcard-manager.md](wildcard-manager.md)) |
| `@style(0.8)` | short for `<lora:style:0.8>`, with every strength form: `@style(0.4-0.9)`, `@style(0.5,0.7)`, `@style(1.0:0.5)` |
| `<lora:style:{0.5\|0.7}>`, `<lora:style:$s>` | a strength is a value like any other: a choice, a binding, a grid axis (`@grid {0.5\|0.7}` is a LoRA sweep in grid form). It is recorded as the pick `<lora:style>`; the name stays as written |
| `$hero = __animal__` | bind once, reuse everywhere |
| `@lib crowd` + indented lines | a library of this template's own, `__crowd__`: each indented line an entry (a template itself; `- ` before it allowed). It shadows a library of the same name, travels with the preset, and the language model never writes it |
| `@include effects/living_clay` + indented `room = the salon` | embed a preset where it stands; indented `key = value` lines turn its dials, so a preset is an operator with parameters (its `@h3` line gives way to yours) |
| `$w.sfx` | a property of the entry `$w` rolled (empty if it has none): the sound follows the weather. A property is a template like an entry (`{a\|b}`, `__lib__`, `$w`, LoRA tags), rolled once when `$w` is bound, so every `$w.sfx` reads the same; filters and `?` conditions compare it as written |
| `__world/habitats#habitat:$animal.habitat__` | a filter that depends on what was rolled before (`#key:$var` or `#key:$var.field`): the manta ray lands in the sea, never on a beach |
| `IF $c is wren, owl: …` | a line kept only when the condition holds: `$c` rolled either of them (its value, a tag or a property); `is not wren, owl`: neither. Works for SFX lines too |
| `IF $w.kind is rain, snow: …` | the same on a property of what `$w` rolled (`is not` for neither) |
| `{IF $w.kind is rain: wet \| dry}` | a choice made by a condition instead of the dice |
| `IF $c[myth, size=small\|tiny]: …`, `{IF $w[kind=rain]: wet \| dry}` | a condition in the brackets' language, against what `$c` rolled: all of them (`,`), either (`\|`), not (`!`). There is no AND or OR word: the brackets say it. Earlier orrery wrote `?` for `IF` (`? $c[wren]: It sings.`), and still may |
| `> make it moody and cinematic` | with a language model set in the node, it rewrites the rolled prompt as asked; in a screenplay a `>` before the first `SHOT` rewrites every shot's prose and one inside a `SHOT` only that shot's, never dialogue. The CLI records it with the picks |
| `--one detail, 5 to 8 words--` | a slot: the language model writes it where it stands, after everything else has rolled (see [wildcard-manager.md](wildcard-manager.md)) |
| `\{` `\}` `\|` `\$` `\__` `\@` `\#` `\\` | the character as written, not syntax: `a sign reading \{OPEN\}`, `\__init__` |
| `# a note` | a comment: a line starting with `#` never reaches the model (filters like `__lib#key:value__` are not comments) |
| `@size 832x1216` | the node's width and height outputs |
| `@batch 8`, `@seed 100` | how many seeds and the first (the CLI's; in ComfyUI the Run count and the seed widget) |
| `@grid __style__ × {dawn\|noon}` | every combination, one run each (3 styles × 2 = 6); everything else rolls the same in all of them. Axes: a library (with its `[tags]`), a choice, or a binding (`$hero`). Generate in the node queues them all, times a LoRA sweep; the CLI prints every cell per seed; Test rolls the axes like any pick |
| `@unique __creature__`, `@unique $hero` | seeds in a row never repeat it: each seed takes the next step of one shuffled order, so 8 seeds give 8 different creatures and the next batch goes on from there. Learned weights don't steer it. The node sets the seed's control after generate to increment |

**Seeds stay put.** Every pick has dice of its own, drawn from the seed, its label and how
often that label was drawn before. Add a `{small|big}` in front, and seed 7 still gives the same
animal and the same light: an edit changes what it touches. Templates made before 2026-10-02 rolled
everything from one stream; `@rng 1` on a line of its own brings those dice back, and History and
Galaxy put it on top when they restore a run from back then.

**What looks like syntax.** A `__name__` that rolled nothing (a `-` or a space in it) and a `{` or `}`
without its other half reach the prompt as written, with a warning; a backslash writes them on
purpose.

**How deep, and what comes back.** Entries and fields resolve as deep as they
go: a library in an entry in a library, a field that reads a sibling field
(`$p.a` with `$p.b` in it) or its own binding (`$p`). Bindings roll from the top
down, so a `$name` used above its binding (or never bound) stays as written,
with a warning. What would go round in circles stops with the path: a library
that comes back to itself (`a → b → a`), presets that include each other,
fields that read each other (`$p.a → $p.b → $p.a`), and a `{N$$__a__}` whose
entries bring it back (after 2000 choices in one place).

Directives stand on a line of their own (under the `@h3` line in a screenplay, which stays first);
completion offers them after `@` at the start of a line. The `:` line says the same and still works:
`: x8 seed=100 w1216 h832 unique=$hero` and `: grid …` (which takes the rest of its line); several of
them add up. A grid or `@unique` varies one clip
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
strength and warns: `@grid __my_lora_sets__` runs every entry instead.
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
