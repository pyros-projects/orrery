# RefMod A/B/C: run sheet

The experiment from [docs/long-video.md](../../docs/long-video.md#the-experiment-before-stages-4-and-5)
(issues #7 and #8). The hypothesis: a RefMod built from an early chunk brings a place back many
chunks later without dragging its composition along.

## The setup

`abc_tour.orr` is a camera tour of four 10 s chunks: **the salon → the hallway → the library →
back in the salon**, entering it from the other side. All three variants render the same template
at seed 7, so their prompts are the same word for word. Only the RefMods on the conditioning
differ:

| Variant | Workflow | Latent tail | Recent RefMod | Place RefMod |
|---|---|---|---|---|
| A | `abc_a.json` | ✓ | | |
| B | `abc_b.json` | ✓ | ✓ the chunk before (3 stills) | |
| C | `abc_c.json` | ✓ | ✓ the chunk before (3 stills) | ✓ the salon (4 stills from chunk 1) |

The RefMods are built in the graph from the reel's own frames. The `SEND:` lines of the template
hand the stills to Orrery Refs: images 3 to 6 are the salon from chunk 1 (frames 0, 60, 120, 180),
and images 7 to 9 are frames 0, 100 and 200 of the chunk before. **Create H3 RefMod From Inputs**
turns them into RefMods: `identity_encode` (Full Reference at 1024 px, no refinement steps),
concept type `background`, not saved. **Apply H3 RefMod** (strength 1) puts them on the
conditioning before Orrery Continue. Reference to Video gets no images in any variant.

The RefMods are built from stills only. The pack's video path trims a reference to 4k+1 frames,
but H3's own Reference to Video trims to 17k+5 (`comfy_extras/nodes_minimax_h3.py`), so a video
reference from the pack would not sit on H3's grid.

## Running it

1. **A:** load `abc_a.json` and Generate ×4. That renders segments 0 to 3 into `output/abc_a/`.
2. **Copy A's first clip** to B and C:
   `python experiments/refmod-abc/copy_segment0.py <ComfyUI output folder>`.
   B and C start from that clip: there is nothing to remember before it, and a RefMod built from
   no frames would block the run.
3. **B and C:** load each workflow. The Orrery Prompt's segment is already 1; Generate ×3.
4. For every segment, note the time and the peak VRAM, plus the token counts that Create H3
   RefMod From Inputs prints to the console.

GPU runs follow the machine's guardrails: anything expected above 23 GB of VRAM needs Pyro's go.

## Scoring

Score each segment 1 to 5, where 5 is best. Compare against the same segment of the other
variants, and the salon also against chunk 1.

| Criterion | 5 means |
|---|---|
| Room identity | it is recognisably the same room: layout, the piano, the staircase, the mirror, the chandelier |
| Material drift | the marble, the velvet, the wood and the gilt keep their look and colour |
| Recurring objects | objects from earlier chunks come back the same, with nothing invented or lost |
| Seam quality | the clip continues the one before without a jump in light, colour or motion |
| Composition leakage | the camera shows the room from the new viewpoint the prompt asks for, not a framing copied from chunk 1 |

### Round 1 (2026-10-02)

Rendered on Pyro's RTX 4090 with local settings that are not part of the workflows in the repo:
the turbo LoRA `minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16` at
0.7 (LoraLoaderModelOnly after the model loader), 4 steps, and the text encoder
`qwen3vl_32b_minimax_h3_int8_convrot`. Contact sheets: [results/round1/](results/round1/).
Scores are Claude's, from the sheets; for segment 3, identity means the salon of chunk 1.

| Segment | Variant | Identity | Drift | Objects | Seam | Leakage | Time | Peak VRAM | Tokens |
|---|---|---|---|---|---|---|---|---|---|
| 1 hallway | A | 4 | 4 | 4 | 4 | 5 | 103 s | 22.6 GB | — |
| 1 hallway | B | 4 | 4 | 4 | 4 | 5 | 101 s | 22.6 GB | 1,728 |
| 1 hallway | C | 4 | 4 | 4 | 4 | 5 | 106 s | 20.5 GB | 4,032 |
| 2 library | A | 3 | 4 | 3 | 4 | 4 | 97 s | 22.6 GB | — |
| 2 library | B | 2 | 3 | 2 | 4 | 2 | 100 s | 22.8 GB | 1,728 |
| 2 library | C | 2 | 3 | 2 | 3 | 1 | 107 s | 20.0 GB | 4,032 |
| 3 salon again | A | 2 | 3 | 2 | 4 | 5 | 99 s | 22.7 GB | — |
| 3 salon again | B | 1 | 3 | 1 | 4 | 1 | 102 s | 22.3 GB | 1,728 |
| 3 salon again | C | 5 | 4 | 5 | 3 | 1 | 107 s | 22.7 GB | 4,032 |

What the sheets show:

- **Segment 1:** A, B and C are nearly the same clip. The RefMods change almost nothing while the
  clip still looks like what they show.
- **B, the recent RefMod, copies the clip before.** B2 drifts back into the hallway and the
  staircase instead of the library. B3 repeats B2 almost frame for frame (mean pixel difference
  32, against 69 between A2 and A3), although its prompt asks for the salon. This is Pyro's "only
  the hallway in the end".
- **C, the place RefMod, brings the salon back, too literally.** C3 has every object of chunk 1:
  the piano, the gilt mirror, the green sofa, the staircase, the chandelier and the floor. But
  frames 60 and 180 repeat chunk 1's first still, seen from the gallery, instead of the new
  viewpoint the prompt asks for. In C2 the salon pushes into the library.
- **A** builds a plausible salon in segment 3, but not the one from chunk 1 (no sofa, no mirror,
  armchairs and a fireplace instead).
- **Cost:** RefMods add 576 tokens per still at 0.6 MP. Four to seven stills cost 3 to 10 seconds
  per clip, and peak VRAM stays under 23 GB.

Two things make B and C look worse than RefMods would on their own:

- **The sampler seed is the same in every segment.** The Orrery Prompt's `seed` output is the
  template's seed, and the rolls get a seed of their own per segment, but the sampler doesn't. With
  the same noise and a reference that looks like the last clip, H3 repeats the last clip.
- **The pack's `strength` does not weaken a RefMod's hold on the layout.** It mixes the reference
  toward a blurred copy of itself, so only detail fades, while the layout, which is what leaks,
  stays. H3 itself has no strength for references.

## Deciding

- **The place RefMod earns its place** when C beats A on room identity in segment 3 by at least
  one point, with composition leakage at 3 or better.
- **The recent RefMod earns its place** when B beats A on drift or seams in segments 1 and 2 by at
  least one point.
- **Neither is worth it** when a variant runs out of VRAM, or costs more time than its gain
  justifies; the numbers decide that, written down in #8.

The result and the go or no-go go into `docs/long-video.md`, and #5 and #6 (the risks) are updated
with what the run showed.
