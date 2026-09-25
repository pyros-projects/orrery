# The prompt language

Every construct of orrery's template language, where libraries live, how Dynamic Prompts packs come in, and how dials turn a template from outside. The H3 screenplay layer on top of it is in [h3.md](h3.md).

| Syntax | Meaning |
|---|---|
| `__animal__` | one entry from `library/animal.yaml` (or `animal.txt`, one entry per line), weighted by learned weights |
| `__film/genre__` | a library in a folder: `library/film/genre.yaml` or `.txt`, as in z-explorer |
| `__animal[feline]__` | only entries tagged `feline` |
| `__characters/cyberpunk#gender:female__` | only entries with that property (`props: {gender: female}` in the YAML, or `gender:female` typed into an entry's tag field); several `#key:value` must all match, in any case |
| `{a\|b\|c:3}` | inline choice; `:3` is a static weight (Dynamic Prompts' `{3::c\|a\|b}` works too) |
| `{\|red }car` | an empty option makes a word optional; the other options keep their spaces |
| `{1-2$$__style__}` | pick 1–2 distinct values |
| `$hero = __animal__` | bind once, reuse everywhere |
| `@include effects/living_clay` + indented `room = the salon` | embed a preset where it stands; indented `key = value` lines turn its dials, so a preset is an operator with parameters (its `@h3` line gives way to yours) |
| `$w.sfx` | a property of the entry `$w` rolled (empty if it has none): the sound follows the weather |
| `__world/habitats#habitat:$animal.habitat__` | a filter that depends on what was rolled before (`#key:$var` or `#key:$var.field`): the manta ray lands in the sea, never on a beach |
| `? $w.kind=rain,snow: …` | a line kept only when the condition holds (`!=` for not); works for SFX lines too |
| `{? $w.kind=rain: wet\|dry}` | a choice made by a condition instead of the dice |
| `> make it moody and cinematic` | with a language model set in the node, it rewrites the rolled prompt as asked; in a screenplay a `>` before the first `SHOT` rewrites every shot's prose and one inside a `SHOT` only that shot's, never dialogue. The CLI records it with the picks |
| `--one detail, 5 to 8 words--` | a slot: the language model writes it where it stands, after everything else has rolled (see [wildcard-manager.md](wildcard-manager.md)) |
| `# a note` | a comment: a line starting with `#` never reaches the model (filters like `__lib#key:value__` are not comments) |
| `: x8 seed=100 w1216 h832` | batch parameters |

Libraries live in the home folder (`~/.orrery` unless set otherwise, see
[configuration.md](configuration.md)) under `library/`, in any subfolders. Plain `.txt` wildcard files work as
they are (one entry per line, `#` comments), so Dynamic Prompts collections can
be dropped in; the first edit in the node turns one into YAML. An entry is a
template itself: `__80s/Women/80s_sports__` or `{a|b}` inside it expand too,
as in Dynamic Prompts (a library that comes back to itself is an error).
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
