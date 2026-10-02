# Plan: the language model writes screenplays

Status: approved 2026-10-02, built the same day. The model writes once per ComfyUI run, so an
answer that does not fit is shown as an idea with its problem rather than asked for again (below).

## Why

orrery's language model (a text encoder that is a whole LLM, Krea 2's Qwen3-VL 4B or an 8B
build) so far fills `--slots--` and writes libraries. It can do more for a reel or a keyframe
clip if it knows the screenplay language. Three writers, all on static text, which keeps them
testable and within a 4B/8B model's reach:

1. **Continue the reel**: the model reads every chunk of the reel, resolved (wildcards rolled,
   bindings filled), and writes the next chunk.
2. **Story between two frames** (fl2va): the model sees the first and the last frame and writes
   a shot that gets from one to the other.
3. **Prompt from an image**: the model sees a picture and writes a prompt for it.

## The prompts

Each writer has a prompt of its own (Prompt from image two: an image prompt and an i2va shot),
with only the part of the static language it writes, so a 4B model does not mix up the rules of
the others. Built as one shared skill first; the GPU test with Qwen3-VL 4B and the 8B Heretic
(2026-10-02) showed the models copying the skill's examples (its first camera move in almost every
4B answer, "35mm photograph" for a flat icon, the word "orrery" in an image prompt), so it was
split, and each prompt got what the test asked for:

- **continue**: the chunk form, camera moves to choose (not copied), anyone without a CAST
  entry described in full again in every chunk (the clips do not see each other), speech on a
  NAME line, a line of speech when the reel has some, at least one sound.
- **story**: one continuous take, no cut ("the scene cuts to" was the 4B's way across), the
  camera move read from the two framings, everything that differs changes on screen.
- **describe**: the medium as the picture is (a flat vector icon is not a photograph), shape
  and color instead of a guess; a photo and an icon as examples.
- **describe_shot**: what moves from the frame on, not how it looks standing still.

Every prompt ends with what never to write: wildcards, `$bindings`, `{a|b}`, `--slots--`, LoRA
tags, comments, headers.

The writers sample at their own temperature (`writer_temperature`, 0.8): at the library's 0.3
the ideas were near copies of each other.

Before (one skill, 0.3) and after (a prompt per writer, 0.8), 12 cases × 5 ideas per model:

| | 4B before | 4B after | 8B before | 8B after |
|---|---|---|---|---|
| fits the check | 60/60 | 60/60 | 60/60 | 60/60 |
| copies the example's camera | 20/60 | 0/60 | 10/60 | 2/60 |
| a story that cuts instead of one take | 5/15 | 0/15 | 0/15 | 0/15 |
| a flat icon called a photograph | 5/5 | 0/5 | 5/5 | 0/5 |
| a cat without CAST described in full again | 0/5 | 5/5 | 0/5 | 5/5 |
| the reel's HANDOFF picked up | 0/5 | 5/5 | 5/5 | 5/5 |
| the narrator kept | 0/5 | 4/5 | 0/5 | 5/5 |
| idea similarity (mean pairwise) | 0.81 | 0.50 | 0.87 | 0.48 |

The examples in the prompts avoid the test pictures' subjects: a first version used them and
flattered the numbers. What neither model does: a costume change between two frames (the duck's
cap becoming a Santa hat), and the 4B misreads flat icons and breeds.

## The writers

| writer | what the model sees | what it writes | where it goes |
|---|---|---|---|
| continue the reel | the resolved chunks so far (the current seed), the reel's world (style, CAST, MUSIC) | one `CHUNK` block: title, SHOTs, prose, SFX, a `HANDOFF` that picks up the last chunk's | appended to the template, as a new cell in the cells view |
| story between frames | the first and the last frame (the Orrery Prompt's `first_frame`, `last_frame`), the header | one `SHOT` with prose and SFX, from frame A to frame B | the template's body, below its header |
| prompt from an image | the image | an image prompt, or an i2va shot when the template is `@h3 i2va` | the template's body, below its header |

**The resolved chunks**: orrery already expands every chunk to static screenplay lines (picks
filled) before it compiles them; the writer gets those lines, segment by segment, at the node's
seed, which is the reel as it was rendered.

**Checked before it lands**: the answer is parsed as orrery parses a template. A chunk that does
not compile, or that writes wildcards, comes back with the compiler's message. A run writes once
(a second generate in one run crashes ComfyUI), so there is no retry inside it: the app shows the
answer as an idea with its problem, **Another idea** asks again in a new run, and **Insert
anyway** takes it as it is.

## Where it runs

The model loads inside a ComfyUI run, as it does now for slots: ComfyUI's model management owns
the memory, and a run never blocks the web server. A **Write** menu in the Prompt tab
(Continue the reel · Story between frames · Prompt from image, each enabled when it applies)
queues a small prompt: a hidden Orrery Write node with the task, the template, the seed and the
frames, plus whatever the Orrery Prompt's `clip`, `first_frame` and `last_frame` are wired to
(Load Image, a text encoder loader). Nothing downstream runs, no video is made. The answer comes
back through the run's output and waits in an ideas sheet: ‹ › through the ideas so far,
**Another idea** (a new run; the model samples at seed + n, the chunks it reads still roll at
the node's seed), **Insert** (an unsaved edit, Undo in the toast). Closing the sheet keeps the
ideas for this template, and a toast says when a pending one is ready. A generation already in
the queue goes first. A shot writer refuses a reel (its shot would replace every chunk).

## Settings

A **Writers** section in the settings: each writer's prompt, a text field with **Reset to
default**. The defaults ship in `src/orrery/builtin/writers/` (Markdown, one file
each); what is edited is kept in the orrery home (`writers/`), so an update of orrery changes
only what was not edited.

## Tests

- pytest with the fake backend: each writer's prompt (its own rules only, the resolved chunks or
  the frames' count), the check (a good chunk lands, wildcards or a broken SHOT come back with their
  problem), the idea's seed, the settings (edited, reset, the built-in default behind it).
- The isolated ComfyUI on :8190: the Write menu queues the small prompt with the right inputs
  and the answer reaches the editor, with the fake backend standing in for the model (no model
  is loaded on :8190).
- Pyro, on the GPU: the three writers with Qwen3-VL 4B and 8B, on the night watch and on a pair
  of frames.

## Out of scope

Wildcards, bindings or slots in what the model writes; writing a whole reel at once; the model
seeing the clips themselves (beyond what the slots already do); chat with the model.

## Decided

1. The image for **prompt from an image** is the frame wired into the Orrery Prompt; a galaxy
   button can come later.
2. **Continue the reel** sees text only.
3. One model for everything: a text encoder wired into the node's clip, else the one in the
   settings.
