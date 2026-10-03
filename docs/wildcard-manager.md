# The wildcard manager

orrery's libraries can be edited in plain language from the CLI, and inside ComfyUI a language model (a local one, or an [API endpoint](#the-language-model-over-an-api)) writes the libraries and `--slots--` a template asks for. Nothing it writes is kept until you accept it.

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
  prompt around them. From a reel's second clip on it also watches the clip
  before (one frame a second and the last one, from Orrery Film's takes or H3
  Motion Context's Chain Video) and continues it:

  ```
  SCENE next forever
  SHOT 5s: tracking, slow
  --what WASHER does in the next 5 seconds, moving the story on--
  ```

  In a reel with per-chunk CASTs, put **Orrery Refs** between your images and
  Reference to Video: it hands each clip only the images its CAST uses, and
  the prompt renumbers `<Picture N>` to match ([tutorial](orrery-refs.md)).

  A slot the model leaves out keeps its directions as text (and a warning), so
  a queued chain never breaks on one bad answer. The chain is the reel's own
  folder, which orrery names after it ([comfyui.md](comfyui.md)).

**Roll** (next to Test in the Prompt tab, with how many runs after it: next 3 clips, next 8 images) queues only what this node feeds,
up to its Save and Preview nodes, and the files those Save nodes write go to
the gallery with this run's picks, so Orrery Log is optional. The `×` field
beside it queues that many runs in a row, seed and clip stepping between
them. For a reel the bar shows the clip being generated, or **Next clip**: a
field (type another to play it next) with **Hold** beside it, which plays the
same clip on every run, for takes. **Restart** cancels this node's queued and
running clips and generates from clip 1; other jobs in the queue stay.

**LoRA sweeps.** A LoRA tag with several strengths, in a text prompt or on a
`LORA:` line, makes Roll run once per strength:

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
do (`Roll ×4 · sweep 2 + 2`) and asks first above 50 runs. One seed holds
for the whole sweep; the `×` field becomes the number of seeds, each running
the whole sweep, and the seed steps between them and after the last as its
control after generate says, so the next Roll starts on a seed of its own. A reel's segment stays, so every run renders the same clip.
While the runs are being queued, the editor waits (each queue item reads the
template) and **Stop** ends the queueing. Every output records the swept
strengths as picks (`<lora:a>` = 0.5, or off) and lands in a gallery folder
`sweeps/<first swept LoRA> <date> <time>`. ComfyUI's own Run takes the first
run. `@style(0.5,0.7)` is short for the tag and sweeps the same; a range without
a step, `<lora:style:0.4-0.9>`, rolls a strength per run instead. A library
of LoRA sets (`LORA: __my_lora_sets__`, entries such as `<lora:ink:0.8>
<lora:grain:0.4>`) rolls a set per run; `@grid __my_lora_sets__` runs each set
once (see below). Sweeps sweep only where the template writes them: one in an
entry takes its first strength and warns.

**Grids.** `@grid __style__ × {dawn|noon}` sweeps picks the way a LoRA sweep
sweeps strengths, and a LoRA strength can be one of its axes
(`<lora:x:{0.5|0.7}>` with `@grid {0.5|0.7}`): one run per combination, everything else rolled the same, so
the cells compare. The server plans both (it knows the libraries), the
button says `Roll ×12 · sweep 2 × grid 3 × 2` with a LoRA sweep in the
template too (its runs the outer loop), and the outputs land in the same kind
of gallery folder. A grid that cannot run says why in the footer.

Everything a run needs goes to the model in one request (ComfyUI cannot
safely generate twice in one run); ComfyUI moves the model out when the video
model needs the room, and orrery keeps it for the next run. An API endpoint
can be asked more than once: each library in a request of its own, all at
once, then the slots and rewrites, which see the compiled prompt. What it wrote waits
on top of the Libraries tab under **To review**, marked in violet: **Accept**
keeps it, **Discard** drops it (a discarded library is written again on the
next run, so change the directions first). After every run the node refreshes
its libraries and points at anything new to review. Writes can also be undone
with `orrery lib undo`.

**The Write menu.** In the Prompt tab, **Write** has the language model write
for the editor, in the static screenplay language (no wildcards, bindings or
slots, which keeps it within a 4B or 8B model's reach):

- **Continue the reel**: it reads every scene as it rolls at the node's seed
  (picks filled in, with the reel's style and CAST) and writes the next
  `SCENE`, with an `END ON:` that picks up the last one's. It is appended to
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
model samples at seed + n and at `writer_temperature`, 0.8 by default in
`orrery.yaml`'s `llm:`, so each idea is a different one; the chunks it reads
still roll at the node's seed), **Insert** puts one into the editor as an unsaved edit (Undo in the
toast). An answer that writes wildcards, more than one chunk or a shot orrery
cannot compile is shown with what is wrong; **Insert anyway** takes it as it
is. Close the sheet while it writes, and a toast says when the idea is ready.
The gear's **Writers** section holds what the model is sent: each writer its
own prompt (the image prompt and the i2va shot of Prompt from image are two),
with only the rules and examples it needs, so a small model is not confused by
the others'. Each is editable, with **Reset to default**; an edit lives in `writers/` in the orrery home, so an
update of orrery leaves it alone.

## The language model over an API

The gear's **Language model** can be an API endpoint instead of a text
encoder: OpenAI, or any server that speaks its chat protocol (llama.cpp, LM
Studio, OpenRouter). It takes the endpoint (`https://api.openai.com/v1`), a
key and a model; **Check** lists the endpoint's chat models and has the model
answer once, and **Save** checks the same way before it switches. The key goes
into the home folder's `.env` (readable by you only), never into
`orrery.yaml`, and the gear shows only how it ends; `OPENAI_API_KEY` in
ComfyUI's environment wins over it.

From then on every language-model task goes to the endpoint: a run's
libraries, slots and `> enhance` (the frames a slot watches go as pictures),
the Write menu, and `orrery lib`, when `orrery.yaml` names no
`models.library`. It runs beside ComfyUI: no VRAM, no text encoder pushing
the video model out, no waiting behind a render. It wins over a text encoder
wired into `clip`. Models that want `max_completion_tokens` or refuse a
temperature (the newer OpenAI ones) are asked again the way they accept, and
a busy endpoint twice more before the run fails with its own words.

- **The Write menu** asks the endpoint directly, without a run: an idea comes
  while a render runs. Frames from a Load Image node go as its file; a frame
  that something else computes still takes a run (Orrery Write), which
  computes it.
- **Write now** stands in the Prompt tab's footer, beside the model's name,
  while the template names libraries to write (unknown ones, `__name:N__`
  above what a library holds): it writes them all at once, a request each,
  and they wait under **To review** in Libraries as a run's do. The next run
  finds them done, before any GPU time is spent on them.

A smoke test of every path against a real endpoint, and its results with
`gpt-6-luna`, is in `experiments/api-llm/`.
