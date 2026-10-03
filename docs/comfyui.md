# The ComfyUI nodes

Everything the Orrery Prompt node puts out, the six tabs of its app, Generate and Restart, Orrery Log and Orrery Refs.

```bash
cd /path/to/ComfyUI/custom_nodes && git clone https://github.com/pyros-projects/orrery.git
# or keep it elsewhere and link its node folder:
ln -s /path/to/orrery/comfyui /path/to/ComfyUI/custom_nodes/orrery   # Windows: mklink /J …\custom_nodes\orrery …\orrery\comfyui
```

Restart ComfyUI. While it loads, orrery prints its banner in the console: a
small orrery in brass, then its boot lines (the nodes it registered, its home,
whether RefMod strengths are on and the RefMod pack is there, and anything that
did not come up, marked with a red `!`); `NO_COLOR` prints
it without colour. **Templates → orrery** (or `example_workflows/` in the
repository) holds a workflow per mode, built from ComfyUI's own nodes plus
orrery's: Krea 2 (`text`), MiniMax H3 t2va, i2va, fl2va, l2va, ref2va, reels
on t2va and on ref2va with Orrery Continue / Orrery Film, a reel with
RefMods (Orrery RefMods, with the Jinx RefMod that ships with orrery) and a reel
that goes on from a video of your own. Their notes name the
models and where they go; sampling follows ComfyUI's own templates (H3:
`res_multistep`, 20 steps; Krea 2 Turbo: 8 steps). Each puts ComfyUI's Model
Attention Backend on `comfy kitchen attention` after the model loader: INT8
attention, much faster on Nvidia and AMD GPUs; elsewhere the node falls back to
PyTorch attention by itself. With the repository linked
as its `comfyui` folder, the template browser does not list them; drag the
files in instead.

Nodes under **orrery**:

- **Orrery Prompt**: seed and target (`text`, `h3-base`, `flat`), optional
  `segment`, `first_frame`, `last_frame` and `video` → `text`, `picks`, `seed`, `width`,
  `height`, `length`, `lora_stack` and
  `megapixels`. A picture wired into `first_frame` (else
  `last_frame`), the same one the H3 node gets, gives `width`/`height` its shape
  at the header's megapixels (else H3's canvas area), on the 32 grid as close to
  its shape as the grid allows: H3 stretches a first frame and crops a last one
  into any other shape. A written `: w… h…` still wins, and the lint says when
  the header's ratio is set aside or two frames differ in shape.
  Wire `text` into your text encoder or the MiniMax H3 prompt input;
  `width`/`height` come from `: w… h…` or the `@h3` ratio (`@h3 references 16:9 0.6MP`
  sizes the canvas by area, and `megapixels` puts that out for resolution and
  scale nodes), `length` is the
  screenplay's duration in frames for the H3 latent, `lora_stack` carries the
  `LORA:` lines as a LORA_STACK for any loader with a `lora_stack` input
  (LoraManager, Efficiency, Easy-Use …); unknown or ambiguous names are
  reported in the log and in the Test tab. A reel (`SCENE` blocks, `×N` and
  `forever`, `$x[-1]`, `AFTER:`, `(test)`; see [h3.md](h3.md) 1d) writes one clip per run:
  `segment` counts up by itself, and Orrery Continue / Orrery Film (below)
  chain the clips. A video wired into `video` (Load Video) is the scene before
  the reel's first: the node keeps it at 24 fps beside the clips, a head
  `REMEMBER:` keeps its frames, and a scene with `AFTER: the input video`
  continues it ([h3.md](h3.md) 1d, *The input video*). The node is the whole of orrery, in six tabs (⤢ opens the
  same app over the canvas, Esc brings it back):
  - **Prompt**: the template editor with syntax colours and completion
    (`__` libraries, `__creature[` tags, `__creature#` properties and their
    values, `$` bindings, the CAST after `@` (`@KEEPER`; at a line's start also
    `@KEEPER (…): ` for speech; every member shows in brass), camera words after
    `SHOT 5s:`, your LoRA files after `LORA:`, your RefMods after `refmod ` in
    a CAST member's parentheses, the scenes after `CUT TO:` and `AFTER:`, what to
    keep after `REMEMBER:`, the dials after `SET:` (`@JINX(1)`, and inside it the
    words `refmods`, `images` …), the mode words after `@h3 `). **New** starts a fresh
    template linked to no preset: an H3 scene, an H3 reel,
    H3 references, H3 keyframes (image, first-last, last) or a Krea prompt,
    each with a quickstart of the essentials as `#` comments on top (the gear
    turns the quickstart off). Open a preset from the bar above it; ● marks unsaved
    edits; Save, Save as…, Revert. Under the editor, every binding is a
    **dial**: pick a library entry or choice, or type any expression; empty
    means its default roll. Saving bakes the dials in, and a galaxy output
    restores them. **Test** jumps to the Test tab and rolls. **Write** has
    the language model write the reel's next scene, the shot between two
    frames or a prompt from a picture, one idea per short run, browsed
    before it goes in ([wildcard-manager.md](wildcard-manager.md)).
    In a reel, every `SCENE` line carries a divider that says which clips
    it plays (counted from 1), when and how much film is left (`clips 2–5 · 4 × 5 s · 0:05 →
    0:25 · 1:35 left`); the scene that plays the next clip is
    marked (`▶ next`), and **Jump** beside *Next clip* puts the caret
    there. Beside the editor, the **timeline** lines up each scene's clips
    as Orrery Film (or H3 Motion Context's Chain Video) keeps them (hover plays one, a click
    opens it; dashed boxes are clips not rendered yet) and, under a scene
    with `REMEMBER:` lines, the frames Orrery Refs last fetched for each image (its
    anchors). It reads the chain from the string wired into `latent_path`,
    else `h3_context`, and refreshes after every run. Drag the edge between
    editor and timeline to widen it. **Clips beside / Clips below** in the
    footer switches to the cells view: the editor cut into one cell per
    SCENE, each followed by a section with that scene's clips and remembered
    frames; drag a section's lower edge to resize it (kept per scene, like
    the width, in the node). Arrow keys cross from cell to cell, Backspace at
    a cell's start and Delete at its end join two, and a SCENE line typed or
    removed cuts the text anew. The gear turns dividers and timeline off.
  - **Test**: what the template makes, without queueing anything. **Rolls**
    shows three seeds (a reel: six clips at one seed, pageable through a
    forever loop). **Frequencies** rolls it 50, 200 or 500 times, across seeds
    or across a reel's clips, and shows how often every value comes up, plus
    how often each lint warning fires.
  - **Presets**: every preset with your newest output as its preview; search,
    folders, favorites, recents, a sample roll and the template per preset.
  - **Libraries**: edit wildcard lists by hand: entries, tags, weights, and
    the weight each entry learned from your ratings. Libraries that share a
    name prefix sit in a folder (`couture_form`, `couture_house` → couture);
    what the language model wrote waits on top for review. Built-ins become
    yours with **Make it mine**. Drag the list's edge to widen it; a long
    property opens when you click it.
  - **Galaxy**: every logged output. love / like / nope / hate multiply the
    learned weight of each pick by 1.5 / 1.2 / 0.8 / 0.5 (re-rating replaces
    the factor). **Use template + seed** restores an output and sets the seed
    to fixed. Folders on the left sort outputs without moving their files:
    drag cards onto a folder (a selected card brings the whole selection),
    drag a folder onto another to nest it, double-click to rename. Removing
    a folder moves what is in it up a level. Select with the checkbox,
    Shift-click for a range, Ctrl/Cmd-click for one more; then **Export
    pairs** copies each picture or video into `~/.orrery/export/<name>/`
    with a `.txt` of the prompt that made it (training pairs), and
    **Delete** takes outputs out of the galaxy and moves their files to
    `~/.orrery/trash/`. Learned weights stay. The big picture of an open
    output drags onto the canvas like the file itself: a new Load Image node,
    a Load Image node's new picture, or the workflow the picture carries.
  - **History**: every run of the node as it resolved, newest first: the
    seed, the segment, the dials, every pick and the prompt, kept even when
    the output was not (the last 2000 runs, in `prompt_history.jsonl` in the
    orrery home). Search by prompt, pick, preset or seed; **Use template +
    seed** puts the run back in the Prompt tab (segment included, control
    after generate fixed), so a lucky roll can be made again (a run from before
    2026-10-02 comes back with `@rng 1` on top: the dice it was made with). Each run is
    also printed to ComfyUI's console (seed, picks, prompt); the gear turns
    that off.
  - **Help**: the DSL at a glance, the tutorial lessons, writing tips.

  Workflows that used the old `preset` dropdown open with that preset loaded
  into the editor.
- **Orrery Log**: `picks` (+ `images`) → saves PNGs with the picks embedded and
  appends one line per output to `~/.orrery/galaxy.jsonl`. For videos saved by
  another node, put the file path into `media_path`.
- **Orrery Refs**: `picks` + `image_1` … `image_9` → `ref_1` … `ref_9` and `preview`, between
  your reference images and MiniMax H3 Reference to Video. Every clip gets only
  the images its screenplay uses, packed from `ref_1` and numbered as the prompt
  numbers them, plus the frames of earlier clips a reel `REMEMBER:`s (a picture
  wired into that image stands in until they exist); `preview` shows
  them all in one Preview Image, each labelled with its ref. Remembered frames are kept
  as anchors in the orrery home; `keep_sent` on holds them from clip 1 for the
  next run, so a character stays. The tutorial:
  [orrery-refs.md](orrery-refs.md).
- **Orrery Continue** and **Orrery Film**: orrery chains a reel's clips itself,
  on the Masked AV continuation of
  [H3 Continuum](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum) (MIT).
  In every clip that continues one, Orrery Continue starts the clip's latent with the
  last 22 frames of that clip (the one before, or the one `AFTER:` names), picture and sound, and a `noise_mask`
  keeps the sampler off them; no model or layout patch is involved. After the
  input video it takes the video's last 22 frames and sound instead, fitted to
  the clip's canvas and encoded with the H3 video VAE in its `vae` and the audio
  VAE in its `audio_vae` (only that clip needs them). Wire:

  ```
  Orrery Prompt picks ───────────────▶ Orrery Continue picks
  H3 node (Reference to Video …) latent ▶ Orrery Continue latent ──▶ sampler latent_image
                         conditioning ▶ Orrery Continue conditioning ▶ sampler positive (optional)
  sampled latent ─────────────────────▶ Orrery Film samples
  decoded images / audio ─────────────▶ Orrery Film images / audio
  Orrery Film film (VIDEO) ───────────▶ Save Video, Orrery Log
  ```

  The H3 node's `length` comes from the Orrery Prompt (it counts the 22 frames).
  Orrery Continue drops a first-frame image from the conditioning in those
  clips (they start with the one before); the first clip and a `(test)` scene start afresh; Orrery Film refuses a
  clip whose pinned frames the sampler changed (a sampler that ignores
  `noise_mask`). Orrery Film trims the 22 frames, puts out the clip
  (`images`, `audio`) and `film`, the reel so far, and keeps the takes under
  `output/<latent_path>/orrery_film/` (`h3_context` unless the Orrery Prompt's
  `latent_path` says otherwise): each clip, its sound and the tail the
  next one continues from. Rendering a clip again replaces its take and drops
  the ones after it that continue it (branches beside it stay); clip 1 starts a new
  run; older takes stay on disk. A `(test)` scene's take is kept but left out of
  the joined film. The previous clip, `REMEMBER:` and the timeline read
  this store or H3 Motion Context's Chain Video, whichever was written last.
  Another `context:` than 22 is a warning: 22 frames are pinned all the same.
- **Orrery RefMods**: `conditioning` + `picks` → `conditioning`. It puts the
  clip's RefMods on the conditioning, the ones its CAST names
  (`refmod NAME` with `SET: @JINX(0.5, 35%)`, see [h3.md](h3.md#1e-refmods-refmod-name-set-jinx05-35)),
  each with its strength and its start. It loads them from `models/refmods`
  with the [ComfyUI-H3RefMods](https://github.com/FranckyB/ComfyUI-H3RefMods)
  pack, which needs to be installed; the pack's Load and Apply nodes are not
  needed. One RefMod ships with orrery, in `examples/refmods` (Jinx, Apache 2.0):
  the node finds it there without copying, and the completion offers it. Wire:

  ```
  Reference to Video conditioning ▶ Orrery RefMods conditioning ▶ Orrery Continue conditioning (or the guider)
  Orrery Prompt picks ────────────▶ Orrery RefMods picks
  H3 video VAE ───────────────────▶ Orrery RefMods vae (for RefMods made from the reel)
  ```

  A RefMod that a `REMEMBER:` line makes from the reel's own frames (`REMEMBER: every
  10th frame as refmod NAME`) needs no pack: the node takes those frames of the
  remembering clip from the chain and encodes them with the `vae` as
  Reference to Video encodes a video reference, on its 768 canvas and on the
  VAE's frame grid (the last frame held to fill it up, at most 73 frames spread
  out evenly). It encodes them once and keeps the result for the run; a new take
  of that clip encodes them again.

  It also applies a picture's dials (`image 1 at 0.5 from 35%`) to the pictures
  Reference to Video put on the conditioning: with Orrery Refs, the k-th picture
  is the k-th packed ref. A RefMod or a picture that starts later goes into a
  timestep range of its own, as ConditioningSetTimestepRange would put it. The strength comes from orrery's
  wrap of H3's attention, which orrery installs in memory when its nodes load.
  A picture's strength covers its reference latents and the vision tokens its
  text encoder left in the text. Outside its `from` and `to`, the picture stays
  on the conditioning at 0, so both stay hidden.

  With **H3SLAAttention** (sparse attention), every step where a strength other
  than 1 is in play runs dense: orrery's wrap widens the attention heads, and SLA
  takes only H3's own. The clip then renders at dense speed for those steps. A
  picture or RefMod at 1 runs sparse and can lose part of its reference to the
  sparsity, unless SLA's Protect Vid/Ref holds it (Light or Heavy). At 0.99 it
  runs dense and keeps all of it, so under SLA 0.99 can hold more than 1.
- **Orrery Write** (`orrery/internal`): the Write menu queues it on its own;
  you don't add it.
