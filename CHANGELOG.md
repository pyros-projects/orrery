# Changelog

What changed for people who use orrery, one line per pull request. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Changes to how orrery is developed (the dev flow, the
checks) are left out.

## [Unreleased]

### Added

- The take tree: every take of a reel keeps its path, and picking it brings back the clips last made after it. **Tree**
  shows them all like a git graph with videos, the film's path lit; a click makes the film the way through a take, ✂
  ends it after one, ▶ Film plays the film as clicked together, a timeline of its clips under it, and a filter hides
  the dead ends (the takes fewer than N takes were made on). Switching takes
  never changes the editor; a take made with another prompt carries ✎, its hover shows what changed and a click puts
  that prompt back in the editor, with Undo. Beside a clip's takes, a column: play all, the clip in numbers, the
  others and all (#213).
- A clip's takes play all at once, from the start and in step, to compare their motion: play all, stop all (#227).
- The template's knobs beside its dials: LoRAs, RefMods, pictures and members, grouped where they hold (all clips,
  then each scene), with strength, start and end in number fields stepping 0.05 and a sweep's values as chips;
  turned as dials are, the template stays as written and Save bakes them in (#227).
- One way to turn the model's knobs: LoRAs, RefMods, pictures and members take (strength, start, end), in `SET:` or
  their own long form (`<lora:…>`, `<refmod:…>`, `<image:N:…>`, `<cast:NAME:…>`); a LoRA comes on at its start and
  goes off at its end, every field sweeps with `|` or a range, and `<` completes the long forms: `<refmod:` lists
  your RefMods, `<lora:` your LoRAs, `<cast:` the members (#227).
- A reference needs no CAST: `<Image N>` in the text, as H3's own prompts write it, hands the picture to H3 as
  `[image N]` does; `SET: image_N(…)` dials it, and `SET:` with a RefMod's name brings that RefMod in, with
  strength, start and end. Tutorial 19 shows it (#224).
- A clip's takes go at once: under their label, **the others** keeps only the one in the film, **all** deletes that
  one too and the film ends before the clip; each asks first (#234).
- The Orrery Prompt puts its `LORA:` lines on the model that passes through it, a clip's own and the head's, a
  sweep's run included: no LoRA node needed (#208).
- The language model can be an API endpoint (OpenAI, or a server that speaks its protocol), set in the gear
  with a key kept in the home's `.env`: a run's libraries, slots and `> enhance`, the Write menu and
  `orrery lib` go through it, beside ComfyUI (no VRAM, no queue). The Write menu answers while a render
  runs, and **Write now** writes a template's open libraries at once (#165).
- The editor remembers the language for you: a completion popup you can read (it wraps, previews in full,
  opens upward near the bottom, Ctrl+Space), every form of a keyword as you type its start, fields after
  `$hero.`, the gallery's characters with thumbnails after `image `, each line's result at its end (a
  binding's roll, an export, a grid's cells, where a member's pictures go), and hover help on keywords,
  CAST members, libraries and bindings (#132).
- A dial takes several choices: tick them in its menu, and it rolls among them (`{noir|gothic}`); on a
  library the chosen entries keep their properties (#156).
- `EXPORT:` keeps what a template rolled beside its prompt, never in it: the gallery, History and
  `orrery expand --json` hold it for other systems, the Gallery shows it as a sheet, and a picture
  carries it into the screenplays that cast it (`$hero.mood`). The Character creator exports who it
  drew (`$who`), a mood, a quirk, two skills and a voice (#157).
- Pictures by name in the CAST: `@HERO (image krea/09_character_creator/1283456183)` takes a character
  from the gallery with all its views, `image __pictures/<preset>__` rolls one (the gallery is a library,
  steered by ratings, `[origin!=$hero.origin]` for one who differs), Orrery Refs loads them without a Load Image, and a `--…--` description is written
  from the prompt that made them. A slot's commas in a CAST line stay inside the slot, two members' slots with the same
  directions get a text each, and the text reads as the member's definition (#128).
- A character creator for Krea 2 (`krea/09_character_creator`): an original character from about 800 parts
  (a silhouette, a signature colour carried through clothes and accents, one detail you remember, a face,
  hair that fits the age, seven genres, women in women's clothes and men in men's), every part a dial,
  shown from four sides as references. A grid axis dialed to one value is a grid of one (#121).
- The clips view is where a reel is worked: the default view, its clips big (a clip size in the
  settings sets their shorter side), the frames each `REMEMBER:` line takes cut from its clip as you
  type, where they go at the line's end, and a frame picked by eye written into the line (#97).
- Five presets for what no preset showed yet: The specimen (a Backrooms film that casts its monster
  in a test scene), Three endings (one setup, three genres with `AFTER:`), Cabinet of curiosities
  (`@unique` and `@grid` on Krea), And then… (your own video, going on forever) and Between two
  frames (first-last). The docs say what the language guarantees (`docs/dsl.md`), and the doc
  status lines what is built (#23).
- A reel can start from a video of your own: the Orrery Prompt's `video` input, the head's `END ON:`
  and `REMEMBER:` for it, and `AFTER: the input video`; Orrery Continue encodes its last 22 frames
  and their sound (#87).
- DSL 2.0, the film words: `SCENE`, `END ON:`, `START WITH:`, `AFTER:`, `CUT TO:` with `×N` and
  chances, `IF $x is …:`, `REMEMBER: … as @NAME`, `SET: @NAME(…)`, `@NAME` members, `(test)` scenes
  and history by title (`$x["the stairs"]`); the earlier words still work (#81).
- A picture's strength also reaches the vision tokens its text encoder writes into the text, so
  `SET: image_1(0.5)` turns down the whole picture (#66).
- RefMod memory for reels: a clip gets the RefMods its CAST names, with a strength, a start and an
  end, including RefMods made from the reel's own frames (#59).
- orrery's boot banner stands out in the ComfyUI console, with what loaded and what did not (#60).

### Changed

- A sweep's values are separated by `|` (`<lora:x:0.5|1.0>`), since commas separate a knob's fields now; the
  comma lists of before still sweep as they did, and the log suggests `|` (#227).
- The `lora_stack` output is gone, since a LoRA stack needed a third-party node: the LoRAs go on the model through
  the node. A workflow saved with it loses it when it opens, and its other outputs keep their links (#208).
- A reel keeps its clips in a folder named after it, `output/reels/<preset>` or `reels/untitled/<date time>`, which
  moves with Save as; two reels no longer write into one `h3_context`. The Orrery Prompt's `latent_path` input
  is gone (#197).
- A scene's divider names the next clip it plays (its hover all of them), and its 📊 shows the scene in numbers: where
  and how often it plays on the walk, how long, what plays before and after it, what it rolls, what it made (#197).
- A scene's divider adds takes of its clip (+) and stays on it, goes to the next scene, or both; the clip rendering now
  shows the sampler's preview and its step under its scene (KJNodes' Model Preview Override, or ComfyUI's own) (#197).
- Sample surfing: a scene's + adds ×1, ×2, ×4 or ×8 takes of its clip, you pick the best under it, and the
  film, `REMEMBER:` and the next clip use that one; 📌 keeps the scene's rolled prompt so only the noise changes, and
  the gear numbers the takes' seeds; a × deletes a take, under the clip or in its box, and a grip sizes the takes,
  in the clip's shape. Clip 1 too: rendering it again stays in its run beside its other takes; another size or
  sound starts a new run (#197).
- The Orrery Prompt takes the model through it: the clip being sampled then plays in orrery's clip box as it
  forms, in real time (the tiny VAE taeh3, else Latent2RGB), light or smooth at the pictures a second the gear's
  Live preview sets, at the size it sets (1024 px on the long side unless set, 0 as sampled). Without it, ComfyUI's own preview reaches the clip box in every open tab (#197).
- The dials are a list in a sidebar beside the editor, one a row with what it rolls at this seed, to widen,
  fold or clear; a dial's menu filters by a regex over text, properties and tags, with All and None; a reel's
  clips show only under its scenes, and the column beside the editor is gone; the node's segment widget is
  orrery's own now, set in the footer with Next clip and Hold, and a template without scenes stays at clip 1
  and never continues an old clip (#183).
- `REMEMBER: frames 0, 50 as @NAME` gives her one picture per frame (it was one batch, of which
  Reference to Video read only the first); the lint names the two lines that fill one picture (#97).
- The galaxy is the gallery now, and Generate is Roll, with how many runs it queues after it:
  **Roll** next 3 clips, next 8 images (#23). Ratings and folders on disk stay as they are.

### Fixed

- History's and the Gallery's restore no longer promise that the next run reproduces a run: it rolls again with today's
  libraries and learned weights, and says so (#259).
- Typing in a long reel no longer lags: the editor highlights a scene again only when something it shows
  changed, and works out once what every scene reads, instead of every scene on every keystroke (#218).
- Save as, the gear and the app's other sheets open at the top of the app, where their buttons are, not at the
  bottom edge of the node, which a tall node puts out of sight (#220).
- The editor's annotations follow a seed or target changed in the node, not only an edit or a run (#187).
- A new Orrery Prompt starts 1300 px wide, so the footer of a prompt or an H3 scene fits on one line (#181).
- The gear saves again when `max_tokens` in `orrery.yaml` is not a multiple of 500 (the browser refused the
  form); the API endpoint's text no longer looks like a label, and its model list waits for a pick (#179).
- A dial's list of choices opens every time: a menu of its own shows every choice while the dial holds
  one of them, filters what you type, and a library's choices come back after a run (#155).
- The Libraries tab opens at once with a home of a hundred thousand entries (it loaded all of them,
  30 MB, and after every run), keeps its place when a folder unfolds, and shows tags and properties
  on a line under each entry (#152).
- A dial set to a library entry keeps the entry's properties and tags, so what reads them (a
  photo look's lens in One button) still works (#122).
- After a grid or a LoRA sweep the seed steps as its control after generate says, so the next Roll
  starts on a seed of its own instead of repeating the last one (#125).
- The docs name DSL 2.0 as the language's version, apart from the package's, and `docs/h3.md`
  describes the Ref2VA writer as built (#123).
- Frequencies and Rolls load the libraries once per request instead of once per roll (#47).

## [0.1.0] - 2026-10-02

The first version, v0 (#1).

### Added

- A seeded prompt language that records every pick: wildcard libraries (YAML or Dynamic Prompts
  `.txt`, in folders, globs), inline choices, bindings and fields, tags and properties with one
  predicate language for filters and conditions, number ranges and chances, a template's own
  libraries (`@lib`), `@include` with dials, `@grid`, `@unique`, LoRA tags with strength ranges
  and sweeps; every pick has its own dice, so an edit moves only what it touches.
- The MiniMax H3 compiler: a screenplay of shots, camera moves, voices and sound turned into H3's
  official format for text, image, first-last, last and references, `lite` by default, with
  `keep:` macros and lint for what H3 would ignore.
- Reels: chunks chained clip by clip with Orrery Continue and Orrery Film (or H3 Motion Context),
  `SEND:` frames as references for later clips, `GOTO:` jumps that can hang on what a clip rolled.
- One ComfyUI node with an app in it (Prompt, Test, Galaxy, History, Libraries): an editor with
  syntax colours and completion, test rolls and frequencies, ratings that steer later rolls, and a
  language model that writes missing libraries, slots, `>` rewrites and the next chunk.
- Orrery Refs, Orrery Continue, Orrery Film and Orrery Log; example workflows for every mode; 75
  presets and the `orrery` CLI.
