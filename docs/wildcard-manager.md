# The wildcard manager

orrery's libraries can be edited in plain language from the CLI, and inside ComfyUI a local language model writes the libraries and `--slots--` a template asks for. Nothing it writes is kept until you accept it.

```bash
uv run orrery lib list
uv run orrery lib show animal                  # entries with learned weights
uv run orrery lib gen weather --template scene.orr
uv run orrery lib more style -n 8
uv run orrery lib edit animal 'Lösch alle katzenartigen Tiere und mach daraus eine neue Liste "feline"'
uv run orrery lib undo
```

The model only proposes. orrery shows how it understood the instruction and a
diff, and writes nothing until you confirm (`--yes` skips the question).
Every change can be undone, and learned weights move with renamed or moved
entries.

## The language model in ComfyUI

In the node, the gear picks orrery's language model: a text encoder from
ComfyUI's `text_encoders` folder that is a whole LLM, such as Krea 2's
`qwen3vl_4b` or a Qwen3-VL 8B build (MiniMax H3's encoder is cut short and
cannot write). A text encoder wired into the node's `clip` input wins over the
setting. When the node runs, the model

- creates a library the template names but you don't have (`__runway_shoes__`),
  with the number of entries set in the gear, using the lines around it as
  context;
- tops up `__name:30__` to at least 30 entries, once;
- follows directions written right after the library:
  `__film_scene__(at least 30 words, describe set, actions, characters)`. They
  never reach the prompt and stay with the library for later top-ups. A
  library with directions gets only its directions, and an entry may be any
  length (**Max tokens** in the gear, 16000 by default, bounds one answer); one
  without gets the lines around it and a default of 1-4 lowercase words.
- writes `--directions--` slots where they stand, seeing the whole compiled
  prompt around them. From a reel's second segment on it also watches the clip
  before (H3 Motion Context's Chain Video, one frame a second and the last one)
  and continues it; the node's `previous` and `previous_audio` outputs hand the
  last 3 s of that clip to the Reference to Video node's `ref_video`, for
  `SHOT …: after video 1`:

  ```
  CHUNK next repeat forever
  SHOT 5s: after video 1, tracking, slow
  --what WASHER does in the next 5 seconds, moving the story on--
  ```

  In a reel with per-chunk CASTs, put **Orrery Refs** between your images and
  Reference to Video: it hands each clip only the images its CAST uses, and
  the prompt renumbers `<Picture N>` to match ([tutorial](orrery-refs.md)).

  A slot the model leaves out keeps its directions as text (and a warning), so
  a queued chain never breaks on one bad answer. The chain is found under
  `output/h3_context`; wire a string into `latent_path` if yours lives
  elsewhere.

**Generate** (next to Test in the Prompt tab) queues only what this node feeds,
up to its Save and Preview nodes, and the files those Save nodes write go to
the galaxy with this run's picks, so Orrery Log is optional. The `×` field
beside it queues that many runs in a row, seed and segment stepping between
them. For a reel the bar shows the segment being generated (or the next one),
and **Restart** cancels this node's queued and running clips, sets segment to
0 and generates from the start; other jobs in the queue stay.

**LoRA sweeps.** A LoRA tag with several strengths, in a text prompt or on a
`LORA:` line, makes Generate run once per strength:

```
<lora:relim_v2_lora_500:0.5,0.6,0.7>                      3 runs
<lora:relim_v2_lora_500:0-1;0.1>                          0, 0.1 … 1: 11 runs
<lora:style_x:0.5,1.0:1.0>                                the model strength swept, CLIP fixed
<lora:a:0.5,1.0><lora:b:0.5,1.0>                          they combine: 2 × 2 = 4 runs
<lora:a:0.5,1.0:solo><lora:b:0.5,1.0:solo>                they take turns: 2 + 2 = 4 runs
<lora:H3-Icy-real-v1_000004200:test>                      the macro: 1.0,0.7,0.5:solo
```

Swept LoRAs combine, the first in the text changing slowest; `solo` ones take
turns with the other solo LoRAs off, and combined ones run with every turn.
Strength 0 is off (the tag leaves the prompt), and identical runs run once, so
`0,1` on two solo LoRAs gives one bare baseline. The button says what it will
do (`Generate ×4 · sweep 2 + 2`) and asks first above 50 runs. One seed holds
for the whole sweep; the `×` field becomes the number of seeds, each running
the whole sweep. A reel's segment stays, so every run renders the same clip.
While the runs are being queued, the editor waits (each queue item reads the
template) and **Stop** ends the queueing. Every output records the swept
strengths as picks (`<lora:a>` = 0.5, or off) and lands in a galaxy folder
`sweeps/<first swept LoRA> <date> <time>`. ComfyUI's own Run takes the first
run.

Everything a run needs goes to the model in one request (ComfyUI cannot
safely generate twice in one run); ComfyUI moves the model out when the video
model needs the room, and orrery keeps it for the next run. What it wrote waits
on top of the Libraries tab under **To review**, marked in violet: **Accept**
keeps it, **Discard** drops it (a discarded library is written again on the
next run, so change the directions first). After every run the node refreshes
its libraries and points at anything new to review. Writes can also be undone
with `orrery lib undo`.

**The Write menu.** In the Prompt tab, **Write** has the language model write
for the editor, in the static screenplay language (no wildcards, bindings or
slots, which keeps it within a 4B or 8B model's reach):

- **Continue the reel**: it reads every chunk as it rolls at the node's seed
  (picks filled in, with the reel's style and CAST) and writes the next
  `CHUNK`, with a `HANDOFF:` that picks up the last one's. It is appended to
  the reel.
- **Story between frames**: it sees the pictures wired into `first_frame` and
  `last_frame` and writes the shot that gets from one to the other (fl2va). It
  takes the place of the shots below the header.
- **Prompt from image**: it sees the picture in `first_frame` and writes an
  image prompt (Krea 2), or an i2va shot when the template is `@h3`. Comments
  and `: w… h…` lines stay.

Each idea is a short run of its own: Orrery Write with only the frames and the
text encoder wired into the node, so no video model loads and the run ends
when the model has written (a run already in the queue goes first). The ideas
wait in a sheet: ‹ › pages through them, **Another idea** asks again (the
model samples at seed + n, the chunks it reads still roll at the node's
seed), **Insert** puts one into the editor as an unsaved edit (Undo in the
toast). An answer that writes wildcards, more than one chunk or a shot orrery
cannot compile is shown with what is wrong; **Insert anyway** takes it as it
is. Close the sheet while it writes, and a toast says when the idea is ready.
The gear's **Writers** section holds what the model is sent: the skill (the
language, with examples, ahead of every task) and each task, editable, with
**Reset to default**; an edit lives in `writers/` in the orrery home, so an
update of orrery leaves it alone.
