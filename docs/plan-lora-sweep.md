# Plan: LoRA sweeps, one Generate for every strength

Status: approved 2026-10-01.

## The tag

A LoRA tag with several strengths runs once per strength:

```
<lora:relim_v2_lora_500:0.5,0.6,0.7>        three runs
<lora:relim_v2_lora_500:0-1;0.1>            0, 0.1 … 1 (the end included): eleven runs
<lora:slider_age:-1-1;0.5>                  negative strengths, for slider LoRAs
<lora:style_x:0.5,1.0:1.0>                  the model strength swept, CLIP fixed
<lora:a:0.5,1.0:solo>                       its own turn, see below
<lora:H3-Icy-real-v1_000004200:test>        the macro: 1.0,0.7,0.5:solo
```

- Values are numbers or `from-to;step` ranges (the end included when a step
  lands on it), mixed with commas: `0, 0.5-1;0.25`. Values are rounded to
  four decimals.
- With both a model and a CLIP list, the tag runs every pair.
- `solo` is the last field; `test` stands for `1.0,0.7,0.5:solo`.
- It works wherever a LoRA tag goes: text prompts (LoRA Text Loader) and H3
  `LORA:` lines (the `lora_stack` output). A tag without a list, a range,
  `solo` or the macro stays as it is.

## Runs

- Swept LoRAs combine: the runs are the cross product, the first tag in the
  text changing slowest.
- Solo LoRAs take turns: every value of the first, the other solo LoRAs off,
  then every value of the next. In total, the product of the combined counts
  times the sum of the solo counts. The solo turns are the outer loop.
- The same tag written twice is one LoRA.
- Strength 0 means off: the tag leaves the prompt and the stack. Identical runs
  (two solo turns at 0 are both the bare baseline) run once.

## Generate

- Generate queues every run. The button says how: `Generate ×4 (sweep 2 + 2)`.
  Above 50 runs it asks first.
- The seed stays fixed within a sweep. `×N` beside Generate is the number of
  seeds: each runs the whole sweep, the seed stepping between sweeps as its
  control after generate says. A reel's segment stays: every run renders the
  same clip.
- Every run puts the concrete tags into the text and the stack, records each
  swept LoRA as a pick (`<lora:name>` = `0.6`, or `off`), and its outputs land
  in a galaxy folder `sweeps/<first swept LoRA> <date> <time>`.
- ComfyUI's own Run takes the first run, and the lint says how many there are.

## Tests

- pytest: values, ranges, negatives, CLIP, `solo`, the macro and errors; the
  runs (product, solo turns, both together, order, off, doubles); the
  substitution into text and `LORA:` lines; the node's sweep input, picks,
  folder and lint; the galaxy row's folder.
- node: the app's plan (count and formula) against the same cases.
- Browser, on the isolated CPU ComfyUI on :8190: Generate on a sweep queues
  the runs with one seed and the right tags, and the outputs land in the folder.

## Out of scope

Sweeps of anything but LoRA strengths, a contact sheet, user-defined macros.
