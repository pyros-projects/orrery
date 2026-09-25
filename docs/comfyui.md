# The ComfyUI nodes

Everything the Orrery Prompt node puts out, the five tabs of its app, Generate and Restart, and Orrery Log.

```bash
ln -s /path/to/orrery/comfyui /path/to/ComfyUI/custom_nodes/orrery   # Windows: mklink /J …\custom_nodes\orrery …\orrery\comfyui
```

Restart ComfyUI. Nodes under **orrery**:

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
  reported in the log and in the Test tab. For H3 Motion Context chains, a reel
  (`CHUNK` blocks, `repeat N|forever`, `$x~N`; see [h3.md](h3.md) 1d) writes one
  clip per run: `segment` counts up by itself, and `load_index`/`save_index`
  go into Load and Save Latent's `clip_index`. The node is the whole of orrery, in five tabs (⤢ opens the
  same app over the canvas, Esc brings it back):
  - **Prompt**: the template editor with syntax colours and completion
    (`__` libraries, `__creature[` tags, `$` bindings, camera words after
    `SHOT 5s |`, your LoRA files after `LORA:`). **New** starts a fresh
    template linked to no preset: an H3 scene, an H3 reel for Motion Context,
    H3 references (ref2va), H3 keyframes (i2va, fl2va, l2va) or a Krea prompt,
    each with a quickstart of the essentials as `#` comments on top (the gear
    turns the quickstart off). Open a preset from the bar above it; ● marks unsaved
    edits; Save, Save as…, Revert. Under the editor, every binding is a
    **dial**: pick a library entry or choice, or type any expression; empty
    means its default roll. Saving bakes the dials in, and a galaxy output
    restores them. **Test** jumps to the Test tab and rolls.
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
    to fixed.
  - **Help**: the DSL at a glance, the tutorial lessons, writing tips.

  Workflows that used the old `preset` dropdown open with that preset loaded
  into the editor.
- **Orrery Log**: `picks` (+ `images`) → saves PNGs with the picks embedded and
  appends one line per output to `~/.orrery/galaxy.jsonl`. For videos saved by
  another node, put the file path into `media_path`.
