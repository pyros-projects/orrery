# The ComfyUI nodes

Everything the Orrery Prompt node puts out, the five tabs of its app, Generate and Restart, Orrery Log and Orrery Refs.

```bash
cd /path/to/ComfyUI/custom_nodes && git clone https://github.com/pyros-projects/orrery.git
# or keep it elsewhere and link its node folder:
ln -s /path/to/orrery/comfyui /path/to/ComfyUI/custom_nodes/orrery   # Windows: mklink /J …\custom_nodes\orrery …\orrery\comfyui
```

Restart ComfyUI. **Templates → orrery** (or `example_workflows/` in the
repository) holds a workflow per mode, built from ComfyUI's own nodes plus
orrery's: Krea 2 (`text`), MiniMax H3 t2va, i2va, fl2va, l2va, ref2va, and reels
on t2va and on ref2va with Orrery Continue / Orrery Film. Their notes name the
models and where they go; sampling follows ComfyUI's own templates (H3:
`res_multistep`, 20 steps; Krea 2 Turbo: 8 steps). With the repository linked
as its `comfyui` folder, the template browser does not list them; drag the
files in instead.

Nodes under **orrery**:

- **Orrery Prompt**: seed and target (`text`, `h3-base`, `flat`), optional
  `segment` → `text`, `picks`, `seed`, `width`, `height`, `length`, `lora_stack`,
  `load_index`, `save_index`, `previous`, `previous_audio`, `megapixels`.
  Wire `text` into your text encoder or the MiniMax H3 prompt input;
  `width`/`height` come from `: w… h…` or the `@h3` ratio (`@h3 ref2va 16:9 0.6MP`
  sizes the canvas by area, and `megapixels` puts that out for resolution and
  scale nodes), `length` is the
  screenplay's duration in frames for the H3 latent, `lora_stack` carries the
  `LORA:` lines as a LORA_STACK for any loader with a `lora_stack` input
  (LoraManager, Efficiency, Easy-Use …); unknown or ambiguous names are
  reported in the log and in the Test tab. A reel (`CHUNK` blocks,
  `repeat N|forever`, `$x~N`; see [h3.md](h3.md) 1d) writes one clip per run:
  `segment` counts up by itself, and Orrery Continue / Orrery Film (below)
  chain the clips; with H3 Motion Context instead, `load_index`/`save_index`
  go into its Load and Save Latent's `clip_index`. The node is the whole of orrery, in five tabs (⤢ opens the
  same app over the canvas, Esc brings it back):
  - **Prompt**: the template editor with syntax colours and completion
    (`__` libraries, `__creature[` tags, `__creature#` properties and their
    values, `$` bindings, camera words after
    `SHOT 5s:`, your LoRA files after `LORA:`). **New** starts a fresh
    template linked to no preset: an H3 scene, an H3 reel,
    H3 references (ref2va), H3 keyframes (i2va, fl2va, l2va) or a Krea prompt,
    each with a quickstart of the essentials as `#` comments on top (the gear
    turns the quickstart off). Open a preset from the bar above it; ● marks unsaved
    edits; Save, Save as…, Revert. Under the editor, every binding is a
    **dial**: pick a library entry or choice, or type any expression; empty
    means its default roll. Saving bakes the dials in, and a galaxy output
    restores them. **Test** jumps to the Test tab and rolls.
    In a reel, every `CHUNK` line carries a divider that says which segments
    it plays, when and how much film is left (`seg 1–4 · 4 × 5 s · 0:05 →
    0:25 · 1:35 left`); the chunk that plays the node's `segment` next is
    marked (`▶ next`), and **Jump** beside *Next segment* puts the caret
    there. Beside the editor, the **timeline** lines up each chunk's clips
    as Orrery Film (or H3 Motion Context's Chain Video) keeps them (hover plays one, a click
    opens it; dashed boxes are segments not rendered yet) and, under a chunk
    with `SEND:` lines, the frames Orrery Refs last sent to each image (its
    anchors). It reads the chain from the string wired into `latent_path`,
    else `h3_context`, and refreshes after every run. Drag the edge between
    editor and timeline to widen it. **Clips beside / Clips below** in the
    footer switches to the cells view: the editor cut into one cell per
    CHUNK, each followed by a section with that chunk's clips and sent
    frames; drag a section's lower edge to resize it (kept per chunk, like
    the width, in the node). Arrow keys cross from cell to cell, Backspace at
    a cell's start and Delete at its end join two, and a CHUNK line typed or
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
  - **Help**: the DSL at a glance, the tutorial lessons, writing tips.

  Workflows that used the old `preset` dropdown open with that preset loaded
  into the editor.
- **Orrery Log**: `picks` (+ `images`) → saves PNGs with the picks embedded and
  appends one line per output to `~/.orrery/galaxy.jsonl`. For videos saved by
  another node, put the file path into `media_path`.
- **Orrery Refs**: `picks` + `image_1` … `image_9` → `ref_1` … `ref_9` and `preview`, between
  your reference images and MiniMax H3 Reference to Video. Every clip gets only
  the images its screenplay uses, packed from `ref_1` and numbered as the prompt
  numbers them, plus the frames of earlier clips a reel `SEND:`s; `preview` shows
  them all in one Preview Image, each labelled with its ref. Sent frames are kept
  as anchors in the orrery home; `keep_sent` on holds them from segment 0 for the
  next run, so a character stays. The tutorial:
  [orrery-refs.md](orrery-refs.md).
- **Orrery Continue** and **Orrery Film**: orrery chains a reel's clips itself,
  on the Masked AV continuation of
  [H3 Continuum](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum) (MIT).
  From the second segment on, Orrery Continue starts the clip's latent with the
  last 22 frames of the segment before, picture and sound, and a `noise_mask`
  keeps the sampler off them; no model or layout patch is involved. Wire:

  ```
  Orrery Prompt picks ───────────────▶ Orrery Continue picks
  H3 node (Reference to Video …) latent ▶ Orrery Continue latent ──▶ sampler latent_image
                         conditioning ▶ Orrery Continue conditioning ▶ sampler positive (optional)
  sampled latent ─────────────────────▶ Orrery Film samples
  decoded images / audio ─────────────▶ Orrery Film images / audio
  Orrery Film film (VIDEO) ───────────▶ Save Video, Orrery Log
  ```

  The H3 node's `length` comes from the Orrery Prompt (it counts the 22 frames).
  Orrery Continue drops a first-frame image from the conditioning in segments
  after the first (the clip starts with the one before); Orrery Film refuses a
  clip whose pinned frames the sampler changed (a sampler that ignores
  `noise_mask`). Orrery Film trims the 22 frames, puts out the clip
  (`images`, `audio`) and `film`, the reel so far, and keeps the takes under
  `output/<latent_path>/orrery_film/` (`h3_context` unless the Orrery Prompt's
  `latent_path` says otherwise): each segment's clip, its sound and the tail the
  next one continues from. Rendering a segment again replaces its take and drops
  the segments after it (they continued the old one); segment 0 starts a new
  run; older takes stay on disk. The previous clip, `SEND:` and the timeline read
  this store or H3 Motion Context's Chain Video, whichever was written last.
  Another `context:` than 22 is a warning: 22 frames are pinned all the same.
