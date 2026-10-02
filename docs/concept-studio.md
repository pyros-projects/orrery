# orrery studio: concept

Status: concept, 2026-10-02. Nothing built; for Pyro to decide.

## One sentence

orrery on a page of its own, with ComfyUI as its engine: the text is the
source, a ComfyUI workflow is what it compiles to, and the canvas is opened
only to change the engine.

## Why now

orrery was cut small on purpose (`docs/concept.md`: "No platform: ComfyUI
stays the front end"), after three earlier tries stalled. Nine days of use
point the other way, for a reason the earlier tries did not have:

- **The graph turned into plumbing.** Replacing H3 Motion Context by Orrery
  Continue / Orrery Film removed six nodes and left the screenplay as it was.
  What the workflow still holds is the engine: loaders, sampler, decode.
- **Routing moved into text.** `SEND:` and `for segment 4+` route frames,
  the CAST routes reference images through Orrery Refs, `CHUNK … repeat`
  loops, `LORA:` patches, `<lora:a:0-1;0.1:solo>` runs a sweep. As nodes, each
  of these would be spaghetti or impossible.
- **orrery already reads its graph** (`wiring()`, `continued()`) to adapt
  to it. A compiler that inspects its target afterwards wants to own it.
- **The cells view** (one cell per CHUNK, its clips under it) is a notebook
  in all but name, squeezed into a node.

orrery is no anti-node tool. Text is better for content decisions (what goes
where in which clip); nodes stay good for plumbing (models, samplers, memory).
The studio gives each its place.

## The lesson of the earlier tries

| | thesis | owned | ended |
|---|---|---|---|
| z-explorer (2025-12) | "No spaghetti needed", `__variables__`, `>` enhance | its own runtime, NVIDIA only | parked |
| ai-foundry / kiln (2026-03) | one "Prompt IDE" product | a platform, desktop shell, training | stalled in phase 2 |
| crucible (2026-07 to 09) | a model workshop | Temper: an execution backend, kernels, model families | stalled at what agents can build |
| orrery (since 2026-09-23) | `(text, picks)` | language, lineage, galaxy | in use |

The thesis was right in z-explorer already. What sank the projects was owning
the runtime. The studio keeps orrery's line: **orrery owns the language and
everything about the takes; ComfyUI owns everything that runs a model.**

## The line

| orrery (the studio) | ComfyUI (the engine) |
|---|---|
| editor, libraries, presets, the cells view | model loading, samplers, VRAM, attention backends |
| rolls, picks, lineage, the galaxy and its weights | every node pack: H3, RefMods, LoRA loaders, upscalers |
| reels: segments, takes, the film, Generate ×N, Restart | the queue, execution, caching |
| routing written in the DSL | the engine workflow, opened on the canvas when it changes |

No training, no model families, no own runtime, no kernels: the opposite of
crucible.

## Engines

An engine is an ordinary ComfyUI workflow that contains an Orrery Prompt, as
`example_workflows/` already are. The studio does not generate graphs. It
takes the engine as the user saved it, sets the Orrery Prompt's inputs
(template, seed, target, segment, params) and queues it, so the engine stays
fully editable on the canvas and every node pack keeps working. The Orrery
Prompt still compiles on the server; Orrery Refs, Orrery Continue and Orrery
Film work unchanged.

- **Picking an engine:** per mode (the `@h3` header picks among
  `t2va / i2va / fl2va / l2va / ref2va`, reels and Krea), from a folder of
  engines. The shipped ones are the start; the user's own (Pyro's two-stage
  turbo sampler, SLA attention, sigma shift) sit beside them.
- **Format:** the API format (ComfyUI's "Export (API)"), which needs no
  frontend to queue. Image inputs such as Load Image become fields the studio
  fills (file uploaded through ComfyUI's `/upload/image`).

## How it works today, and what changes

The app already talks to ComfyUI through two seams only:

- **`bridge`** (`comfyui/web/orrery.js`): `getText/setText`, seed, control,
  target, params, `getSegment/setSegment`, `generate`, `generateSweep`,
  `stopGenerate`, `cancelRuns`, `latentPath`, `props` … implemented over the
  node's widgets and `app.queuePrompt`.
- **`api.js`**: ComfyUI's `fetchApi`, `apiURL` and its execution events.

Everything else (`shell`, `prompt`, `cells`, `timeline`, `galaxy`, `test`,
`libraries`, `presets`, `help`) knows nothing of the canvas. The studio is
therefore mostly a second bridge:

| bridge call | in the node | in the studio |
|---|---|---|
| text, seed, segment, params | widgets | the studio's own state, saved per project in the orrery home |
| `generate(n)` | `app.queuePrompt` of the node's subgraph | `POST /prompt` with the engine, its Orrery Prompt inputs set, n times |
| progress, outputs | ComfyUI's frontend events | ComfyUI's `/ws` socket and `/history` |
| `cancelRuns`, Restart | `/queue`, `/interrupt` | the same |

## The first step: a test of the thesis

A full page that the existing plugin serves at `/orrery/studio`, from the
same ComfyUI server, with the same app modules and a studio bridge over the
HTTP API. One engine per mode, chosen from `example_workflows/` or the user's
saved ones. No new repository, no Tauri, no new server.

If after a week of real use the canvas only opens to change an engine, the
thesis holds, and only then the next step is worth it (a project model, an
engine picker, perhaps a desktop shell). If the canvas keeps pulling Pyro
back, the node app was the right size and the cells view stays its best idea.

## Risks

- **Engines drift from the DSL.** A new orrery feature that needs wiring (as
  Orrery Refs and Orrery Continue did) needs every engine to have it. The
  shipped engines move with orrery; the studio warns when an engine lacks a
  node the template needs (the same check `wiring()` does today).
- **Two front ends to keep.** The node app stays; both share every module
  but the bridge. A feature that only works in one is a bug.
- **The platform trap.** The temptation to grow the studio into model
  management or training, which is exactly where crucible went. The table
  under "The line" is the test for every feature.
- **ComfyUI's API changes.** `/prompt`, `/ws`, `/history`, `/view` have been
  stable for years and are what every ComfyUI client uses.

## Non-goals

Owning model execution; generating graphs; training; replacing the node app;
a hosted service.

## Open questions

1. Is a project (several reels and their engines) the unit the studio
   saves, or is a preset enough?
2. Does the studio pick the engine from the `@h3` header alone, or should
   the template name it (`@engine my_turbo_ref2va`)?
3. The cells view as the studio's main editor, with the column as an option?
