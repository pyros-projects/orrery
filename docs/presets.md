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
`tutorial/` walks through the DSL in twenty lessons, from a first wildcard
to a three-shot H3 scene, an endless reel, the language model's lists,
slots and `>` rewrites, a reference named in the text without a CAST and the model's knobs, `krea/` holds Krea 2 stills (natural language, the medium named, text
to render in quotes; the cabinet of curiosities deals a different specimen to every seed with
`@unique` and shoots each in three lights with `@grid`; the character creator rolls an original
character from parts the way designers build one (a silhouette, a signature colour carried through
clothes and accents, one detail you remember, a face, hair that fits the age, a genre), every part a
dial, and shows it from four sides: portrait, three-quarter, full figure and profile, on a grey
studio backdrop, ready as references for H3 or a RefMod; set `$view` to one of them to try
characters faster; beside it a shelf of creators per world on the same parts (#138): fantasy
(sixty peoples beyond humans, each with its own body, classes with their gear, familiars),
cyberpunk (roles, chrome, street fashion, gangs), sci-fi (forty species, roles aboard and beyond),
creatures (seventy kinds with their coverings, features and habitats) and noir (a 1940s city,
black and white with one colour); each exports what the picture cannot show, for a reel that casts
it; the expression creator shows one face in the eight expressions of a set (basic, subtle, intense,
social, inner, playful), each told by what the face does and the muscles that do it, in FACS action
units; the landscape creator rolls a place to put them in, a land in a season of its climate, a sky,
an hour and one sign of life that belongs there (never a person), from four distances: establishing,
wide, medium and the ground up close; the setting creator rolls a place people are in, a room, hall,
shop, street, vehicle or ruin of one of five worlds, empty, as a film shows it: the outside, the whole,
one part with open floor in front and one thing in it up close; wild scenarios rolls something happening
in one of eight worlds, from tame to abstract, and lets the model picture it), and `h3/` holds MiniMax H3 scenes (dialogue in German
and Cantonese, a voiceover, fast cuts, an animated fable, on-screen music, and
an I2VA starter for your own stills, a three-clip reel for H3 Motion
Context, a drone flight, an impossible camera move that dives into a dewdrop
and comes out elsewhere, and a world swap inside one take, an entity test that shows how H3
renders five non-human SCP entities, with a dial for naming them, an
archetype test that checks where H3 pulls an unfamiliar design, three endings (one setup, and a
sitcom, a horror film and a romance that each continue the same clip with `AFTER:`) and between two
frames, where any first and last picture are joined in one take by a visible action, and wild scenarios, the
Krea preset's scenarios as a clip in one of the video looks). `effects/` holds Ito-style body-horror operators in the lite format,
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
into runway looks for Krea and H3 (`couture_*` libraries); `infinite_cakewalk` is an endless show
steered by CUT TO:: every clip rolls who walks next and cuts to the scene that dresses them, and the
season (a dial) puts the runway outside in spring and summer, inside in autumn and winter. `loops/` holds H3 Motion Context reels
that never end (`forever` or `CUT TO:`, Run (Instant)). Six are steered by `CUT TO:` and play out differently
with every seed: `the_specimen` (a test scene films the SCP the seed rolled and REMEMBER keeps it, so the
walk through the Backrooms meets that very thing, at a 35% chance, twice at most), `infinite_backrooms` (a found-footage horror film: after every third level a chance that
an SCP finds the camera, and which one decides how it gets away), `dice_dungeon` (rooms, foes and a relic
that ends it, so every seed is an adventure of its own length), `the_relay` (a thing passed from hand to
hand through a city), `evolution` (a creature that changes one trait per generation, and sometimes all of
them) and `endless_kitchen` (a dinner service where every ticket picks a station). Then: an endless tour through one
building (Codie's Garamonde method: the building described again in every
clip, each clip ending on a framed threshold the next one opens), a set change
where stagehands strike one place and reveal the next (Pyro's tested idea and
nineteen more mechanisms in `__transitions/between__`), a drone odyssey, a
rabbit hole that dives into ever smaller details and comes out at a new scale,
a time machine over one street corner from 1850 to 3000, the Backrooms (a
found-footage walk on a 1990s camcorder that noclips from one empty level to
the next), and `and_then`, which takes a video of your own (the Orrery Prompt's `video` input) and
lets it go on forever, a little stranger every clip. `onebutton/` is
OneButtonPrompt's promise without its slop: `still` (Krea) and `clip` (H3)
roll a person, animal, object, idea or landscape, a moment that happens to it,
a place it belongs in, a look and a composition, and `$wild` dials from tame
to unhinged. They draw on the pack libraries: `world/` (landscapes, weather,
habitats), `looks/` (fifty-odd video looks with their own camera, sound and
music, still looks by family), `moments/`, `subjects/`, `frame/`, `drone/`,
`tour/`, `transitions/`, `scale/`, `time/`, `backrooms/` and `places/` (the landscape creator's lands, seasons,
weather, hours and signs of life, filtered by climate and water, and the setting creator's places in
five worlds), `scenarios/` (eight worlds of situations, fantasy, sci-fi, pirates, fights, festive, everyday,
dreamlike and abstract, each from `wild: tame` through odd and wild to abstract). One library is
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
@h3 text 16:9
…
```

The ComfyUI node records every template it uses under its hash, so each
gallery line can be traced back to, and re-run from, its exact template.

## Writing a Krea 2 preset

Krea 2 reads its prompt with a language model (Qwen3-VL) and was trained mostly on long, dense captions,
so a Krea preset writes one paragraph of plain sentences, never a list of tags or weights. What matters is
the order and what the picture can show. The creators follow it (#138, from the Krea 2 prompting sweep of
4 October 2026: Krea's own prompting guide and samples, and what practitioners report):

1. **The medium and the shot first.** The first sentence names the medium, then the shot, then the
   subject: `A cinematic photograph, as from the set of a fantasy film: a head-and-shoulders portrait of
   …`. Name a style or a medium outright instead of only describing it.
2. **Only what the shot can show.** Whatever the prompt describes pulls the camera to include it: a
   portrait that mentions a lance, a cape and a familiar comes out waist-up, and a chrome arm in a
   head-and-shoulders view goes missing. With `@grid $view`, bind what every view shows as `$person`
   (the head, the shoulders, the clothes, what sits at the head) and add the gear, the companion and
   whatever is on the arms, the hands, the legs or the back in the full-length view only. A library
   whose entries sit in different places says where with a property (`where: head|body`, as the
   cyberpunk implants and gang signs do). In the fantasy creator's A/B this took the close views from
   0 to 11 of 12 at head-and-shoulders, and brought out a neck tattoo that had gone missing before.
3. **A second subject gets a sentence of its own**, after the pose, with its place: `With them: a crow
   perched on one shoulder.`
4. **Say what is there.** A negation (`no rider`, `without a hat`) doesn't hold. Bind an unusual body
   into one phrase: a centaur is "a human upper body rising from a horse's body where its neck and head
   would be", not a woman "on" a horse.
5. **The order of a creator's prompt:** the medium and the shot, the subject, the presence, the pose
   (`They face the camera.`, `They stand straight … with $gear, and floor and space around them are in
   frame.`), the backdrop (`Behind them is …`), the light, and the finish (lens, colour, rendering) last.
   Text to render goes in quotes.
6. **Whitespace:** an `{IF …}` branch is trimmed at both ends, so a sentence that comes and goes carries
   its neighbour inside the branch (`{IF $familiar is not none: $stand With them: $familiar.|$stand}`) or
   joins with a comma (`$hair{IF $beard is not none: , $beard|}`); give every view a pose sentence rather
   than an empty one.
7. **The checkpoint matters as much as the words.** Krea 2 Turbo renders the same flat face whatever the
   expression; Krea 2 Raw with the turbo LoRA renders them. Judge expressions, moods and faces on Raw.
