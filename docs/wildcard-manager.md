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
  `SHOT … | after video 1`:

  ```
  CHUNK next repeat forever
  SHOT 5s | after video 1, tracking, slow
  --what WASHER does in the next 5 seconds, moving the story on--
  ```

  In a reel with per-chunk CASTs, put **Orrery Refs** between your images and
  Reference to Video: it hands each clip only the images its CAST uses, and
  the prompt renumbers `<Picture N>` to match.

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

Everything a run needs goes to the model in one request (ComfyUI cannot
safely generate twice in one run); ComfyUI moves the model out when the video
model needs the room, and orrery keeps it for the next run. What it wrote waits
on top of the Libraries tab under **To review**, marked in violet: **Accept**
keeps it, **Discard** drops it (a discarded library is written again on the
next run, so change the directions first). After every run the node refreshes
its libraries and points at anything new to review. Writes can also be undone
with `orrery lib undo`.
