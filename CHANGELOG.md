# Changelog

What changed for people who use orrery, one line per pull request. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Changes to how orrery is developed (the dev flow, the
checks) are left out.

## [Unreleased]

### Added

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

- The galaxy is the gallery now, and Generate is Roll, with how many runs it queues after it:
  **Roll** next 3 clips, next 8 images (#23). Ratings and folders on disk stay as they are.

### Fixed

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
