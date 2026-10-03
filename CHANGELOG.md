# Changelog

What changed for people who use orrery, one line per pull request. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Changes to how orrery is developed (the dev flow, the
checks) are left out.

## [Unreleased]

### Added

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

- A reel keeps its clips in a folder named after it, `output/reels/<preset>` or `reels/untitled/<date time>`, which
  moves with Save as; two reels no longer write into one `h3_context`. The Orrery Prompt's `latent_path` input
  is gone (#197).
- A scene's divider generates its clip and stays on it, goes to the next scene, or both; the clip rendering now
  shows the sampler's preview and its step under its scene (KJNodes' Model Preview Override, or ComfyUI's own) (#197).
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
