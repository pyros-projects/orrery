# Long H3 videos: the cast is the memory

Status: concept, agreed 2026-09-24. This is orrery's end stage; Ref2VA stage
R1 is its first building block. Sources: a design chat between Pyro and Codie
(a Garamonde virtual tour chained from 10 s clips with 1 s overlap), the
installed `ComfyUI-H3RefMods`, `comfyui-minimaxh3-contex-loop` and
`ComfyUI-H3-Motion-Context` packs, and the official full-reference guide.

## The problem

Chaining H3 clips with about one second of latent overlap gives smooth seams,
but the model only remembers what is inside that second. A room left thirty
seconds ago, a guest who walked out of frame, the house style: gone. The
common fix is bookkeeping in text: repeat a "continuity bible" in every
prompt, describe recurring things word for word, and hand each clip a
carefully worded opening state. It works, and it is exactly the kind of work
people get wrong by hand.

## Three memories, three owners

| Memory | Carries | Owner |
|---|---|---|
| Short term | the last ~1 s: position, motion, sound | the continuation nodes (Contex Loop, Motion Context): the latent tail |
| Long term | what places, people and the house look like | RefMods: packed reference tokens injected per chunk |
| Semantic | what happens next | the prompt, written by orrery |

RefMods need no labels in the prompt: they ride along as unnumbered reference
tokens, and H3 binds them to the text by description. So the prompt must still
describe whoever is present. Two text jobs remain: those descriptions and one
handoff sentence per seam. Both are mechanical once the screenplay knows who
and where each chunk is, so **the bookkeeper becomes the compiler**.

## The reel

```
@h3 reel 16:9 · context 22f
style: live-action, cinematic, photorealistic

CAST
MAYA (refmod maya_canon): a young blonde woman, in a light-pink shirt
SALON (refmod salon_noir_canon): a double-height salon, with a curved staircase and a black grand piano
LIBRARY (refmod bibliotheque_canon): a crimson library, with thousands of books and a brass ladder

CHUNK 10s @SALON
MAYA crosses SALON toward the staircase …
HANDOFF: the bottom of the curved staircase fills the lower foreground

CHUNK 10s @SALON > LIBRARY
…
```

Per chunk orrery emits:

- the prompt: descriptions only for the cast members present, the handoff
  sentence as the close of chunk N and the opening of chunk N+1;
- the length in frames, context included;
- the **memory list**: global, the places and people the chunk mentions, and
  optionally the previous chunk as "recent". The retrieval query for this
  RefMod-RAG is the screenplay itself.

```
reel ──orrery──▶ Contex Loop plan (prompts, lengths, seeds)
          └────▶ memory lists ──▶ Orrery Memory Router (inside the loop, loads RefMods per chunk)
                                        │
H3 ──▶ Review Gate / Galaxy ♥ ──▶ "make canon" ──▶ new RefMod ──▶ CAST entry
```

- **Contex Loop stays the engine.** It already does seams, review, retry,
  checkpoints and resume. Its plan is plain JSON (`prompt_prefix`, `shots[]`
  with `prompt`, `duration_seconds`, `seed`), so orrery writes it.
- **The missing piece is a per-chunk memory router.** Contex Loop takes
  references as global graph inputs; switching them per scene needs a node that
  reads the current shot and applies that chunk's RefMods.
- **Love makes canon.** A loved chunk can turn what H3 actually generated into
  the canonical RefMod of a place or person. The canon picker asks for varied
  angles (wide, reverse, detail), because RefMods built from near-identical
  frames teach composition instead of identity.

## Facts that shape the design

- RefMods are unmasked extra tokens: every frame of a chunk sees every RefMod.
  Memory is per chunk, not per second; a chunk that walks from one room into
  the next carries both.
- Tokens are not free: an encode-mode still costs about 1,280 tokens, a 16×16
  grid 64 per frame, against roughly 55,000 for a 15 s chunk. orrery should
  lint a per-chunk budget.
- RefMods do not disentangle identity, clothing and background. Retrieval must
  stay selective: global, the present cast, maybe recent. Never everything.
- Contex Loop's resume hash ignores references; change its
  `generation_fingerprint` when memories change.
- With a latent tail, handoffs may end mid-action (Contex Loop's advice); the
  text handoff keeps the prompt consistent with what the tail shows.

## Stages

1. **R1, Ref2VA compiler (now):** `CAST` as a general memory declaration
   (name, description, sources: `image N`, `video N`, `audio N`,
   `refmod NAME`), labels computed the way the Ref2VA node numbers its inputs,
   all six sections, lint. In the base modes, cast names expand to their
   descriptions, which is already the prompt half of RefMod memory.
2. **R2, the node knows its wiring:** walk the graph from `text` to the Ref2VA
   node (through any text nodes) and check the declared sources against what is
   connected. Declarations stay the source of truth.
3. **R3, the cast describes itself:** Qwen3-VL (Krea 2's text encoder) writes a
   member's description from its reference image.
4. **Reel:** `CHUNK`, `HANDOFF`, the Contex Loop plan writer, memory lists.
5. **Memory router and canon:** the per-chunk RefMod node, "make canon" from
   the galaxy.

## The experiment before stages 4 and 5

Everything above rests on one hypothesis: a RefMod built from an early chunk
brings a place back many chunks later without dragging its composition along.
Test it by hand with the installed H3RefMods (Codie's A/B/C):

| Run | Latent tail | Recent RefMod | Place/global RefMod |
|---|---|---|---|
| A | ✓ | | |
| B | ✓ | ✓ | |
| C | ✓ | ✓ | ✓ |

Same seed and prompt; judge room identity, material drift, recurring objects,
seam quality and composition leakage. Build the RefMods from stills (Create
From Folder): the video path of the installed pack snaps to a 4k+1 frame grid
instead of H3's 17k+5, and "Create From Inputs" with saving looks broken
(both unverified).
