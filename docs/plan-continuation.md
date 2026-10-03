# Plan: orrery's own continuation, on Continuum's Masked AV

Status: approved and built 2026-10-02.

## Why

A reel chains one clip per run. Today H3 Motion Context does the chaining:
six nodes (Motion Context, Trim, Load Latent, Save Latent, Chain Video, the
Chain buttons), `load_index`/`save_index` wiring, and orrery reading Chain
Video's files for the previous clip, `SEND:` and the timeline. Motion Context
is GPL-3, so orrery (MIT) cannot take its code, and it rests on the meaning of
ComfyUI's internal H3 layout.

ComfyUI-H3-Continuum (MIT, © 2026 ukr8b3g-cmyk) continues clips another way,
its default since V3.6, **Masked AV**: the previous clip's last 22 frames, picture
and sound, are copied into the start of the new clip's latent and held there by
ComfyUI's ordinary `noise_mask`. The conditioning stays as it is; no model patch,
no layout patch. That part is small (about 550 lines) and has not changed since
August. orrery takes it, with attribution, and owns the rest.

## The two nodes

```
Orrery Prompt ──picks──┐
ReferenceToVideo ─ conditioning ─▶ (RefMods) ─▶ Orrery Continue ─▶ sampler positive
                 └ latent ─────────────────────▶ Orrery Continue ─▶ sampler latent_image
sampler latent ─┐
decoded images ─┼─▶ Orrery Film ─▶ images, audio (this clip, context trimmed)
decoded audio ──┘                └▶ film (VIDEO: the reel so far) ─▶ Save Video, Orrery Log
```

**Orrery Continue** (before the sampler). Inputs: `latent`, `conditioning`, `picks`.
- Segment 0: passes both through.
- Segment N ≥ 1: loads the stored state of segment N-1, copies its last
  `context` frames (video slots and audio ticks) into the start of the latent
  and adds the matching `noise_mask` (0 on the prefix, 1 after it). Drops a
  first-frame keyframe from the conditioning (the prefix is the first frame now);
  a last-frame keyframe stays.
- It records what it did in the LATENT (`orrery_continuation`: chain, segment,
  context, the take it continued). ComfyUI's samplers copy the latent dict, so
  Orrery Film reads it from the sampler's output without more wiring.
- Errors, in orrery's voice: segment N-1 not rendered yet (render it, or
  Restart); a different resolution than the clip before; a latent off H3's
  17k+5 grid or not longer than the 22 pinned frames.

**Orrery Film** (after decode). Inputs: `samples` (the sampler's latent), `images`,
`audio`.
- Checks that the prefix came back unchanged (it should, since ComfyUI resets the
  masked region at every step); an error when a sampler ignored the mask.
- Trims `context` frames off images and audio (segment ≥ 1), captures the state
  (the last 22 frames' latent, picture and sound), and stores
  the take: `video.mp4` (H.264, CRF 18, via PyAV, no ffmpeg on PATH needed), the
  clip's audio as float WAV, `state.safetensors`, `meta.json` (segment, frames,
  seed, template hash, picks).
- Re-rendering segment N makes the new take active and drops N+1… from the reel
  (they continued another take); old takes stay on disk. Segment 0 starts a new
  run folder.
- Merges the active takes into `film.mp4`: earlier clips' video stream-copied,
  the audio concatenated as PCM and encoded once (no clicks at the joins).
- Outputs `images` and `audio` (this clip) and `film` (VIDEO).

## Context

Orrery Continue pins 22 frames, orrery's default `context:`: picture and sound
continue (Masked AV, the one length Continuum validated with sound; for 5 and 39
it falls back to its patched Reference Context route, which orrery does not
take). Another `context:` is a warning, not an error: Orrery Prompt sees Orrery
Continue in the graph and its lint says that 22 frames are pinned all the same,
so each clip runs that much longer or shorter than its shots (39: +17 frames,
0.7 s). Motion Context still takes 5, 22, 39 and 56.

## The store, and what reads it

`output/<latent_path>/orrery_film/run_…/clips.json` + one folder per take,
with the same `clips.json` shape and `video.mp4` name as Chain Video. So
`chain.py` (previous clip for the language model and ref2va, `SEND:` frames, the
timeline) reads either store: the one written last, so switching engines back
and forth works. Motion Context stays supported; nothing of it is removed.

`picks` gains `chain` and `context`, which Orrery Continue needs.

## Vendored code

`src/orrery/continuum/`: `temporal.py` (the 17k+5 / 24 fps / 40 Hz grid),
`state.py` (state capture and context selection), `masked.py` (prefix and
masks), `trim_audio`; each file headed with its source and commit (1f6aec1), the
MIT text in `THIRD_PARTY_NOTICES.md`. Their temporal self-test and state tests
come along.

## Docs and templates

The H3 reel starter and its comments wire Orrery Continue / Film; Motion
Context is the named alternative. comfyui.md (the nodes), long-video.md (the
engine), h3.md (`context:`), orrery-refs.md (`SEND:` reads the active store), the
help reference.

## Tests

- pytest (CPU, fake tensors): the grid and state round trip; the prefix and its
  masks (slots, audio ticks); Continue (segment 0 passes through, N needs N-1,
  resolution errors, another context warns and pins 22, first-frame keyframe
  dropped); Film (trim to the frame and the audio sample, state and take
  written, re-render drops later takes, `film.mp4` frame count and audio length,
  the unchanged-prefix check); the readers prefer the newer store.
- The isolated CPU ComfyUI on :8190: both nodes in a graph with a stand-in for
  the sampler, the timeline and `SEND:` reading the new store.
- GPU, by Pyro: the same reel on Motion Context and on orrery, A/B: seams,
  sound across the cuts, drift over six or more segments (Continuum's open
  issue #13), time and VRAM.

## Out of scope

Continuum's Reference Context route and its model/layout patch, its one-run
Sampler, picking an older take in the UI, drift mitigation, second pass /
hires, removing Motion Context support.
