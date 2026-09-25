# Presets and the content pack

How templates are referenced and saved as presets, and what ships built in: tutorials, Krea stills, H3 scenes, endless loops, one-button generators and the libraries behind them.

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
`tutorial/` walks through the DSL in eighteen lessons, from a first wildcard
to a three-shot H3 scene, an endless reel and the language model's lists,
slots and `>` rewrites, `krea/` holds Krea 2 stills (natural language, the medium named, text
to render in quotes), and `h3/` holds MiniMax H3 scenes (dialogue in German
and Cantonese, a voiceover, fast cuts, an animated fable, on-screen music, and
an I2VA starter for your own stills, a three-clip reel for H3 Motion
Context, a drone flight, an impossible camera move that dives into a dewdrop
and comes out elsewhere, and a world swap inside one take, an entity test that shows how H3
renders five non-human SCP entities, with a dial for naming them, and an
archetype test that checks where H3 pulls an unfamiliar design). `effects/` holds Ito-style body-horror operators in the lite format,
from Codie's H3 tests: subsurface travel, body suit, mirror replacement, living
paper, glass body, living clay, elastic body, hollow vessel, filament, human
drawer and zipper spine, plus his operators surface press, feature migration,
feature multiply, pattern takeover, organic aperture and organic interface,
each with dials over its origin, room and ending; `@include` one into a reel
chunk to use it as an operator. They
follow Codie's rule for H3: turn an abstract property into a visible action
with two states (elastic: two fixed points moving apart; clay: a press and a
dent that stays). `characters/` holds seven sets of ten detailed people
(`average_joes`, `models`, `gothic`, `cyberpunk`, `horror`, `noir`, `fantasy`),
each with `gender` and `age` properties and hair and clothes rolled from nested
libraries: `__characters/noir#gender:female__`. The two Katamori curators live
in `__characters/horror#role:curator__`. `fashion/` strings snobby adjectives and impossible shapes
into runway looks for Krea and H3 (`couture_*` libraries). `loops/` holds H3 Motion Context reels
that never end (`repeat forever`, Run (Instant)): an endless tour through one
building (Codie's Garamonde method: the building described again in every
clip, each clip ending on a framed threshold the next one opens), a set change
where stagehands strike one place and reveal the next (Pyro's tested idea and
nineteen more mechanisms in `__transitions/between__`), a drone odyssey, a
rabbit hole that dives into ever smaller details and comes out at a new scale,
a time machine over one street corner from 1850 to 3000, and the Backrooms: a
found-footage walk on a 1990s camcorder that noclips from one empty level to
the next. `onebutton/` is
OneButtonPrompt's promise without its slop: `still` (Krea) and `clip` (H3)
roll a person, animal, object, idea or landscape, a moment that happens to it,
a place it belongs in, a look and a composition, and `$wild` dials from tame
to unhinged. They draw on the pack libraries: `world/` (landscapes, weather,
habitats), `looks/` (fifty-odd video looks with their own camera, sound and
music, still looks by family), `moments/`, `subjects/`, `frame/`, `drone/`,
`tour/`, `transitions/`, `scale/`, `time/` and `backrooms/`. One library is
licensed differently: the `scp/` libraries are adapted from the SCP Wiki and
are CC BY-SA 3.0, each entry carrying its article's citation in `cite`. Videos
made from it are adaptations as well: credit the cite and share them under
CC BY-SA. Styles are named by medium,
era, format and defects, never by artist: that is what MiniMax H3 follows, and
it keeps the pack free of borrowed names. `orrery preset list
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
