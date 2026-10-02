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

## The skill

One text that teaches the model the static subset of the language, sent ahead of every writer's
task:

- a screenplay: the `@h3 <mode> <ratio>` header, `style:`, `SHOT 5s: camera move, size, speed`
  (with the camera vocabulary), the prose under a shot (what the camera sees, visible action, no
  frozen poses, people named by their CAST name), `NAME: line` speech, `SFX:` (sound next to its
  cause), `MUSIC:`, `CHUNK title` and `HANDOFF: …` (how a chunk ends and the next opens);
- an image prompt (Krea): medium first, then subject, place, light, framing; text to render in
  quotes; no quality tags, no negatives;
- what it never writes: wildcards, `$bindings`, `{a|b}`, `--slots--`, LoRA tags, comments.

A few short examples per form are part of it; small models follow examples better than rules.

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

A **Writers** section in the settings: the skill and the three tasks, each a text field with
**Reset to default**. The defaults ship in `src/orrery/builtin/writers/` (Markdown, one file
each); what is edited is kept in the orrery home (`writers/`), so an update of orrery changes
only what was not edited.

## Tests

- pytest with the fake backend: each writer's prompt (skill, task, the resolved chunks or the
  frames' count), the check (a good chunk lands, wildcards or a broken SHOT come back with their
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
