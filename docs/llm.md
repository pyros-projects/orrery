# The language model in orrery

Everything orrery's language model does, how to switch it on, how to try each part, and what is
planned. The model is there for creative work: lists, slots, rewrites, the next scene. Copying what
a template rolled needs no model, so orrery never asks one for that.

## Choosing the model

The gear in the node opens the Settings tab; its section **Language model**:

| Choice | What it is | Where it runs |
|---|---|---|
| **A text encoder in ComfyUI** | A text encoder that is a whole language model: Krea 2's `qwen3vl_4b`, or a Qwen3-VL 8B build. MiniMax H3's encoder is cut short and cannot write. | In ComfyUI's queue, on the GPU. It loads when the node runs and answers **once per run**. ComfyUI moves it out when the video model needs the room. |
| **An API endpoint** (#165) | OpenAI, or a server that speaks its protocol (llama.cpp, LM Studio, OpenRouter): the endpoint, a key, a model. **Check** lists the models and asks for one answer. **Use this endpoint** checks it first and uses it. The key goes into the home folder's `.env`, never into `orrery.yaml`. | Beside ComfyUI: no VRAM, no queue. It can be asked more than once per run, and in parallel. |

`orrery.yaml` (`llm:`) also holds:
- `entries`: how many entries a new library starts with, 12 by default;
- `takes`: how many takes a 🎲 asks for, each 1 to 12, 3 by default (#274): `slot` (a gallery picture's slot too),
  `enhance`, `rolled` (entries rolled from a library) and `new` (entries the model writes for it). The gear shows
  them as *Takes a 🎲 asks for*;
- `max_tokens`: the longest answer, 16000 by default;
- `temperature`: 0.3, for lists, slots and rewrites;
- `writer_temperature`: 0.8, for the Write menu.

The CLI's `orrery lib` uses `models.library`, else the API endpoint ([configuration.md](configuration.md)).

The footer of the Prompt tab names the active model: `LLM qwen3vl_8b…`, or `LLM gpt-6-luna · API`.

## What it writes

| Feature | In a template | What happens |
|---|---|---|
| **A new library** | `__runway_shoes__` | A library you don't have is written when the node runs, from the lines around it. The editor marks it as "made when the node runs". |
| **A top-up** | `__runway_shoes:30__` | A library with fewer entries is topped up to at least 30, once. |
| **Directions for a list** | the library's takes sheet: **Keep the direction** | The list gets only its directions, never the prompt, and they stay with the library for later top-ups. The earlier `__film_scene__(at least 30 words, set and characters)` still works, deprecated (#275): the sheet shapes a library instead. |
| **Review** | Libraries tab, **To review** (violet) | What the model wrote waits: **Accept** keeps it, **Discard** drops it. `orrery lib undo` undoes a write. |
| **A slot** | `--one small object in their hands, 4 to 8 words--` | Prose written where it stands, after everything else has rolled. The model sees the whole prompt. In a screenplay, CAST names in the directions arrive as `<Subject N>` labels. |
| **A slot in a reel** | `--what WASHER does next, moving the story on--` | From the second clip on, the model also watches the clip before (one frame a second and its last frame) and continues it. |
| **A CAST description from a named picture** | `@MIRA (image krea/09_character_creator/…): --who she is, one sentence--` | The model is told the prompt that made the picture, so it needs no vision for this. |
| **A slot in an export** | `EXPORT:` block, `backstory = --two sentences of backstory for $who--` | It is written with the run and kept with the picture, never in the prompt. A screenplay that casts the picture reads it as `$hero.backstory`. |
| **Pictures in a slot** (#174) | `--the outfit in image first_frame, one phrase--` | The model gets the pictures a slot names, after the frames of the clip before, and reads them as Picture 1, 2 …: `image first_frame` and `image last_frame` (wired into the Orrery Prompt), `image 3` (a gallery picture the CAST names), a gallery name. One that is not there is said; the slot is written without it. The takes at the line see them too; without the picture they ask nothing and say what is missing. |
| **A slot from the picture the run makes** (#174) | `EXPORT:` `sheet = --a full character sheet from $who, as image output shows them--` | `image output` exists only after the run, so the run leaves the slot as it is, kept with the picture; outside `EXPORT:` the lint says so. |
| **Written from the Gallery** (API, #175) | a picture whose exports keep such a slot | The picture's sheet in the Gallery shows the slot with a 🎲: three takes written from the picture, with the prompt that made it beside it; **More takes** and a steer as at the line; select one and **Use selected** writes it into the picture's exports, where a screenplay that casts it reads it. The gear's **Picture slots: After every run** writes each such slot right after its run instead, one take each. |
| **`> enhance`** | `> make it moody and cinematic` | It rewrites the rolled prompt as asked. In a screenplay, a `>` before the first SHOT covers every shot's prose, and one inside a SHOT only that shot; dialogue is never touched. |
| **Write menu: Continue the reel** | a reel (SCENE lines) | The next SCENE, from every scene as it rolls at the node's seed, with an `END ON:`. It is appended. |
| **Write menu: Story between frames** | `@h3 fl2va`, both frames wired | The shot that gets from the first frame to the last. |
| **Write menu: Prompt from image** | a picture in `first_frame` | A Krea image prompt, or an i2va shot when the template is `@h3`. |
| **The writers' prompts** | the gear, **Writers** | What each writer is sent, editable, with **Reset to default**. |
| **Takes at the line** (API, #173) | a 🎲 at the end of a slot's line, of a library still to be written, of a `> enhance` line | The slots are violet in the editor; hovering a 🎲 outlines the place it stands for, so two slots on one line tell their dice apart, and Ctrl+click on a slot opens its takes too (#280). Three takes for that place (or as many as the gear's *Takes a 🎲 asks for* says, #274), written at the node's seed with the prompt as it rolls around it. **More takes** asks for as many more (new against those there), the steering line goes with them ("darker", "as an anime character"). A click selects a take (a violet border), a click on another moves the selection, and **Use selected** puts it in place of the slot or the library (#276); **Keep the direction** writes your steer into its directions (`--…, darker--`, `__name__(darker)`, `> …, darker`); both are unsaved edits with Undo. A `> enhance` line's takes show what the rewrite does at this seed; **Use selected** keeps the one you pick for exactly this roll (the instruction and the prompt as it rolled), and a run that rolls it uses it instead of asking the model; another roll is rewritten as before. A `>` over several passages of a screenplay keeps none, since the run rewrites each apart. With a text encoder the takes come with #171. |
| **A library at the line** (API, #272) | the 🎲 of a library still to be written (`__bus_smells__`) | The sheet writes the library itself: as many entries as a new library starts with (the gear, *A library it creates starts with*; `__name:30__` asks for at least 30), from the lines that use it, as a run would write it. Steer them, **More takes** for as many more; click the entries worth keeping (**All**, **None**), and **Keep as the library** writes them as the library, straight in, not To review (`orrery lib undo` takes it back). **Keep the direction** keeps your steer as the library's directions, for later top-ups. One entry selected, **Use selected** puts it into the line instead. |
| **A library that exists, at the line** (API, #273) | a library's roll at the line's end (`→ arcade · bob cut`), or Ctrl+click on its name | Its takes: entries rolled from it (the one at this seed first, then as its weights and your ratings roll them) and new ones the language model writes, none it has, as many of each as the gear says. Select several; **Add to the library** writes the new ones you picked straight in (the sheet stays: More, then add more), **Use selected** puts one entry into the line. **Keep the direction** saves your steer as the library's directions. With the annotations on Hover or None, Ctrl+click on a library's name opens it (on one still to be written, its sheet from #272). |
| **Generate in the Libraries tab** (#323) | **Generate** beside **Add** under a library of yours | The same sheet with new entries only: as many as the gear's *new for a library* says, none the library has or the sheet shows. Steer them, **More takes**, **Keep the direction**, select the good ones and **Add to the library**; the tab shows them at once. Greyed without a language model. |
| **Write now** (#168, #176) | a template with libraries still to write | A button in the footer writes them before any run, one request each: with an API endpoint all at once beside ComfyUI, with a text encoder each in a run of its own at the front of the queue. They wait in To review. |
| **`orrery lib`** (CLI) | `gen`, `more`, `edit`, `undo` | Libraries in plain language: `orrery lib edit animal 'make a feline list from the cats'`. Nothing is kept until you confirm it. |

The Write menu shows its ideas in a sheet: ‹ › pages through them, **Another idea** asks again, and
**Insert** puts one into the editor as an unsaved edit, with Undo. With an API endpoint the server
asks the model directly, so an idea comes while a render runs. A frame that something other than a
Load Image computes still takes a run of its own.

### What changes with a text encoder: one task per run (#171)

A text encoder in ComfyUI answers once per run, and a small model does better with one task at a time. So
orrery queues **mini-runs** (the node Orrery Ask, with only the text encoder and the frames): each answers one
task, and none loads the video model.

- **Roll** asks, before each run it queues, what that run needs from the model, and queues a mini-run for each
  ahead of it: each library still to be written, then the run's rewrites, then each slot (so a slot sees the
  prose rewritten). In a reel, the next clip's mini-runs come after the clip before, so its slots see that clip.
  Each answer is kept for that exact roll (the home's `asked.json`), and the run takes it instead of asking.
  ComfyUI's own Run queues no mini-runs: the run asks for everything at once, as before.
- **Write now** (#176) queues a run of its own per library, at the front of the queue.
- **The takes at the line** (#178) come from runs of their own at the front of the queue: one take per run for
  a slot or a `>` line, each sampled anew; a library's sheet in one run.

### What changes with an API endpoint

- A run writes each missing library in a request of its own, all at once. Then the slots and
  rewrites follow in one more request, and they see the compiled prompt. `> enhance` runs in the same run.
- Frames go to the model as pictures.
- Newer OpenAI models want other parameters. orrery asks again the way the model accepts and
  remembers that. A busy endpoint is asked twice more.
- A refused key says so, and points at the gear.

## Test it

The tutorials are the quickest way in: **17 · The language model writes your lists** and
**18 · Slots and > enhance**. The Character creator (`krea/09_character_creator`) takes a
`backstory = --…--` in its EXPORT block.

With a **text encoder** (the gear → A text encoder in ComfyUI):

- [ ] Tutorial 17: Run writes `__runway_shoes__` and `__unusual_runway_venue__`. They appear under To review; accept one, discard one.
- [ ] Tutorial 18: Run writes the slot, and the `>` line rewrites the prompt.
- [ ] Tutorial 18 with `__bus_smells__` added, **Roll**: the queue shows three runs of Orrery Ask (the library, the rewrites, the slot) before the render; the render's log asks the model nothing, and the prompt holds all three.
- [ ] Tutorial 17 with fresh library names: **Write now** queues a run per library at the front of the queue; they wait in To review.
- [ ] A slot's 🎲: three takes arrive one after another, each from a run of its own; a library's 🎲 writes its entries in one.
- [ ] A reel with a slot from the second clip on: the text continues the clip before.
- [ ] A CAST member with `image krea/09_character_creator/…` and `--who she is--`: the sentence fits the picture's prompt.
- [ ] The creator with `backstory = --…--` in EXPORT: the Gallery's sheet shows it.
- [ ] Write → Continue the reel, Story between frames (fl2va, two frames wired), Prompt from image.
- [ ] The gear → Writers: edit one, run it, Reset to default.

With an **API endpoint** (the gear → An API endpoint, then Check and Save):

- [ ] A wrong key is refused on **Use this endpoint**; the right one shows only how it ends.
- [ ] The footer says `LLM <model> · API`.
- [ ] Tutorial 17 with fresh library names: **Write now** appears in the footer, writes them, and disappears.
- [ ] Tutorial 18 with a new library added (`… on the last night bus that smells of __bus_smells__`): one Run writes the library, the slot and the rewrite. With a text encoder the rewrite waits for the next run.
- [ ] Write → Prompt from image while a render runs: the idea comes before the render ends.
- [ ] Write → Story between frames, both frames from Load Image nodes.
- [ ] Two slots on one line (`a fox with --one small object-- under --a sky, two words--`): both violet, two 🎲; hovering each outlines its slot; Ctrl+click on the second opens its takes.
- [ ] A slot's 🎲 (Tutorial 18): three takes; a steer and **More takes** bring three more in that direction; click one, another, then **Use selected**, then Undo; **Keep the direction** puts the steer into the slot.
- [ ] A library still to be written (`__bus_smells__`): its 🎲 writes 20 entries (the gear's count); a steer, **Keep the direction**, **More takes**; select some, **Keep as the library**: the Libraries tab has it, not under To review, with the directions; the line's 🎲 is gone and its roll shows.
- [ ] A line with libraries the home has (the Character creator's last line, or `A __animal__ in __style__ light`): click a roll at its end: rolls of that library, the one at this seed first, and new entries; select two new ones, **Add to the library**: they are in the Libraries tab, marked added in the sheet. Annotations on Hover: Ctrl+click on `__style__` opens the same.
- [ ] A `> enhance` line's 🎲: three rewrites of the prompt as it rolls; **Use selected** on one, then Run at the same seed: the prompt is that rewrite, and no request went to the model.
- [ ] A Krea or i2va template with a picture in `first_frame` (a Load Image) and `--the outfit in image first_frame, one phrase--`: Run writes it from the picture; its 🎲's takes do too. Unwire it: the lint says so, and the 🎲 says what is missing instead of asking.
- [ ] The creator with `sheet = --a full character sheet from $who, as image output shows them--` in its EXPORT: the run leaves it a slot.
- [ ] That picture in the Gallery: its sheet shows the slot with a 🎲; the takes describe the picture; **Use selected** writes one into the sheet.
- [ ] The gear → Picture slots: **After every run**, then run the creator: the sheet shows the slot written.
- [ ] Back to the text encoder in the gear: everything goes through the queue again.

## Planned

- 🧠 **The model watches the input video** (#82). It goes on with the video's story, writes the
  head's `END ON:` and draws CAST descriptions from what the video shows.

An idea, not planned: a director that runs outside the canvas, renders, looks at the result with a
vision model, and decides what comes next (keep, reroll, rewrite). See the studio concept,
[concept-studio.md](concept-studio.md).
