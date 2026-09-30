# Plan: SEND, frames of a reel's clip as reference images for later clips

Status: approved 2026-09-30.

## Why

A Motion Context reel drifts: each clip sees only the clip before it, so a face
or an outfit is a copy of a copy by the seventh clip. Frames from an earlier
clip, handed to MiniMax H3 Reference to Video as reference images and bound to
a CAST member, give every later clip the same fixed anchor.

## The line

Inside a `CHUNK`, any number of lines:

```
SEND: frame 0 to image 3
SEND: frames 2, 5, 34-46 to image 4
```

- The target is `image N`, the numbering the CAST already uses
  (`GIRL (image 1, image 3)`) and Orrery Refs' `image_N` inputs, 1 to 9
  (Reference to Video takes nine reference images, `ref_image_0` to `ref_image_8`).
- Frames count from 0, at 24 fps, in the chunk's trimmed clip as Chain Video
  keeps it: frame 0 is the first new frame, after the frames Motion Context pins.
  Single frames and ranges mix, separated by commas; several frames become one
  image batch, in the order written. `frame` and `frames` are the same word.
- A chunk that repeats sends from the first time it plays, so the anchor holds
  still.
- Frames past the end of the clip are dropped with a console warning; when
  none is left, the clip's last frame stands in. A long reel does not stop.

## When an image exists

An image sent by a chunk exists from the segment after the one where that chunk
first plays. Before that, orrery leaves it out of the clip: the CAST members lose
that source, frame anchors on it (`SHOT … | from image N`) go, and nothing in
the prompt points at a `<Picture>` that is not there. An `[image N]` in prose
before the image exists stays as written and is flagged in lint.

## Orrery Refs

Orrery Refs, already between the images and Reference to Video, fills the sent
images itself: it reads the sending chunk's clip from Chain Video (the chain the
Orrery Prompt's `latent_path` names) and hands the frames on as that image,
packed like any other image. The outputs are the images the clip names (a CAST
source, a frame anchor or `[image N]`), in `<Picture N>` order, then every
other sent image that exists, named or not (amended 2026-09-30: SEND works
without a CAST; `SEND: frame 0 to image 1` alone makes `ref_1` the first clip's
frame 0 in every later clip). An empty output is `None` for Reference to Video,
which skips it, and an execution blocker for any other node, so a preview on a
ref that is empty in segment 0 waits instead of failing the run.

Reference to Video reads only the first image of each reference. When a sent
image with several frames is wired into it, Orrery Refs warns in the console:
several stills for ref2va belong on several `image N`; a batch is for nodes that
take many, such as Create H3 RefMod From Inputs.

## Errors

Each stops the run with a sentence that names the fix:

- `SEND:` before the first `CHUNK`, or in a screenplay without chunks.
- `SEND:` in a template that is not `@h3 ref2va`.
- A malformed frame list, a reversed range, or a target outside `image 1–9`.
- Two `SEND:` lines to the same image.
- A reel with `SEND:` whose Orrery Prompt picks reach no Orrery Refs.
- An image wired into Orrery Refs that a `SEND:` also fills.
- A sent image whose clip is not in the chain (the reel was not rendered from
  that chunk on, or `latent_path` points elsewhere).

## Tests

- pytest: the parser (lists, ranges, errors), availability per segment and the
  stripped sources and anchors, the picks orrery hands Orrery Refs, the clip
  lookup in the chain, frame selection and clamping, Orrery Refs filling and
  refusing.
- Browser, on the isolated CPU ComfyUI on :8190: a fabricated Chain Video with
  test clips, Orrery Prompt → Orrery Refs → preview, checking per segment which
  frames arrive on which reference.

## Out of scope

Automatic anchors without `SEND:`, sending to reference videos.
