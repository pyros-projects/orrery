# Orrery Refs

The node between your reference images and MiniMax H3 **Reference to Video**.
It has one job: every clip gets exactly the reference images its screenplay
uses, numbered the way the prompt numbers them. In a reel it can also hand
frames of an earlier clip to the clips after it, so a face or an outfit holds
for the whole film.

This is a tutorial. It starts with why the node exists, wires it once, then
works through a single clip, a reel with different references per clip, and
anchors across a reel with `SEND:`. The last sections list exactly what reaches
the outputs, how the other reference types fit in, and every message the node
can give you.

- [1. Why it exists](#1-why-it-exists)
- [2. The node at a glance](#2-the-node-at-a-glance)
- [3. Wiring it](#3-wiring-it)
- [4. Lesson 1: one clip, numbers that match](#4-lesson-1-one-clip-numbers-that-match)
- [5. Lesson 2: a reel where every clip has its own references](#5-lesson-2-a-reel-where-every-clip-has-its-own-references)
- [6. Lesson 3: anchors across a reel with SEND](#6-lesson-3-anchors-across-a-reel-with-send)
- [7. What reaches the outputs, precisely](#7-what-reaches-the-outputs-precisely)
- [8. Videos, audio and RefMods](#8-videos-audio-and-refmods)
- [9. Messages and what to do about them](#9-messages-and-what-to-do-about-them)
- [10. Limits](#10-limits)

## 1. Why it exists

Reference to Video labels its images by the order they are wired: whatever
sits in `ref_image_0` is `<Picture 1>`, `ref_image_1` is `<Picture 2>`, and so
on. It counts only what is wired. Your screenplay, on the other hand, numbers
references its own way: a CAST line such as `DOG (image 3)` means "the third
image I have", not "the third image this clip needs".

Without Orrery Refs the two numberings have to agree by hand. `DOG (image 3)`
becomes `<Picture 3>`, so the node needs three images wired, even if this clip
uses only that one. In a reel it gets worse: the café matters in one clip and
the dog in the next, and wiring every image into every clip shows H3 references
the prompt never mentions.

Orrery Refs closes that gap. It reads the Orrery Prompt's `picks`, which say
which images this clip uses, and puts out exactly those, packed from `ref_1`.
The Orrery Prompt sees the node in its graph and renumbers `<Picture N>` to
match. You keep your numbers, and H3 gets a clean, short list.

It also fetches images that are not files at all: frames of an earlier clip of
the same reel, named by a `SEND:` line (lesson 3).

## 2. The node at a glance

| | Name | What goes there |
|---|---|---|
| input | `picks` | the Orrery Prompt's `picks` output (required) |
| inputs | `image_1` … `image_9` | your reference images: `image_N` is the `(image N)` of the CAST |
| outputs | `ref_1` … `ref_9` | into Reference to Video: `ref_1` → `ref_image_0`, `ref_2` → `ref_image_1`, … |
| output | `preview` | every image this clip gets, each labelled with its ref, as one batch for a Preview Image |
| switch | `keep_sent` | on: sent images come from their stored anchors, from segment 0 on (lesson 3) |

Two numbers to keep apart:

- **`image N`** is yours. It names an input slot of Orrery Refs, and the CAST,
  frame anchors, `[image N]` and `SEND:` all use it.
- **`ref_k`** is the clip's. It is the k-th image this clip uses, and the prompt
  calls it `<Picture k>`.

Nine slots, because Reference to Video takes nine reference images
(`ref_image_0` to `ref_image_8`).

## 3. Wiring it

```
Load Image (MAYA)  ──► image_1 ┐
Load Image (DOG)   ──► image_2 ├─ Orrery Refs ─ ref_1 ─► ref_image_0 ┐
Load Image (DOG 2) ──► image_3 ┘       ▲        ref_2 ─► ref_image_1 ├─ MiniMax H3 Reference to Video
                                       │        ref_3 ─► ref_image_2 ┘              ▲
Orrery Prompt ──── picks ──────────────┘                                            │
              ──── text ────────────────────────────────────────────────────► prompt
```

1. **`picks`**: Orrery Prompt `picks` → Orrery Refs `picks`. `picks` may go to
   Orrery Log as well; one output can feed several nodes.
2. **Images**: each reference image into the `image_N` that matches its CAST
   number. Gaps are fine: `image_1` and `image_4` with nothing in between works.
3. **Refs**: `ref_1` → `ref_image_0`, `ref_2` → `ref_image_1`, … without gaps.
   Wire as many as the busiest clip uses; Reference to Video offers the next
   `ref_image` slot as you connect the last one.
4. **Text**: Orrery Prompt `text` → Reference to Video `prompt`, directly or
   through text nodes (Text Concatenate and friends are fine).
5. **Header**: the screenplay starts with `@h3 ref2va` (the lite format by default; `@h3 ref2va … full` for the guide's full one).
6. **Preview** (optional): `preview` → Preview Image shows every reference the
   clip gets. Keep previews off the `ref_N` themselves (section 7 says why).

Nothing else to set. When the Orrery Prompt notices that an Orrery Refs reads
its `picks`, it packs the numbering by itself; when it notices that the
Reference to Video its text reaches has fewer `ref_image` slots wired than the
clip uses, it says so in its lint.

## 4. Lesson 1: one clip, numbers that match

Three images: MAYA on `image_1`, a kitchen still on `image_5` that the clip
starts from, a mug on `image_7` that the prose mentions.

```
@h3 ref2va 16:9 lite
style: live-action, cinematic
CAST
MAYA (image 1): the young woman, in a pink shirt
SHOT 5s: from image 5 (the kitchen at dawn), push in, slow
MAYA pours coffee into the mug from [image 7].
SFX: coffee pouring; a fridge hums
```

The clip uses images 1, 5 and 7, so Orrery Refs puts out `image_1` on
`ref_1`, `image_5` on `ref_2` and `image_7` on `ref_3`, and the prompt reads:

```
<Subject 1> = the young woman of <Picture 1>, in a pink shirt

integrated_multimodal_description: [Shot 1] Live-action, cinematic. The shot begins from <Picture 2>. The camera pushes in at slow speed. <Subject 1> pours coffee into the mug from <Picture 3>.
```

`image 5` became `<Picture 2>` and `image 7` became `<Picture 3>`, and three
wired `ref_image` slots are enough. Without Orrery Refs the same screenplay
would say `<Picture 5>` and `<Picture 7>` and need seven images wired.

What counts as "used":

- every image source of a CAST member (`MAYA (image 1)`, `DOG (image 2, image 3)`),
- frame anchors: `SHOT …: from image N` and `SHOT …: to image N`,
- `[image N]` anywhere in the prose or the `summary:` line.

## 5. Lesson 2: a reel where every clip has its own references

In a reel (`CHUNK` lines, chained by Orrery Continue or H3 Motion Context), everything before the first
`CHUNK` is the world and holds for every clip, and that includes a CAST there.
A chunk can have a CAST of its own, which holds for that clip only. This is
where Orrery Refs pays off.

```
@h3 ref2va 16:9 lite
style: live-action, cinematic
CAST
MAYA (image 1): the young woman, in a pink shirt

CHUNK the cafe
CAST
CAFE (image 4): the coffee shop, with a brick wall and an orange sofa
SHOT 5s: push in, slow
MAYA sits on the sofa in CAFE and sips her coffee.
SFX: espresso machine hiss; low chatter

CHUNK the park
CAST
DOG (image 2, image 3): the white Samoyed, with a curved tail
SHOT 5s: tracking, slow
MAYA throws a ball and DOG races after it across the grass.
SFX: a dog barking; wind in the trees
```

Wire `image_1` (MAYA), `image_2` and `image_3` (two views of the dog) and
`image_4` (the café) once. Then:

| Segment | Clip | `ref_1` | `ref_2` | `ref_3` | Subject lines |
|---|---|---|---|---|---|
| 0 | the cafe | image 1 | image 4 | – | `<Subject 1> = the young woman of <Picture 1>, …` · `<Subject 2> = the coffee shop of <Picture 2>, …` |
| 1 | the park | image 1 | image 2 | image 3 | `<Subject 1> = the young woman of <Picture 1>, …` · `<Subject 2> = the white Samoyed of <Picture 2> and <Picture 3>, …` |

The café clip never sees the dog and the park clip never sees the café, and in
each clip the pictures are numbered from 1.

One thing to know: a member of the world CAST counts in every clip, whether
the clip mentions it or not. If a reference belongs to some clips only, give it
to their chunks' CASTs.

## 6. Lesson 3: anchors across a reel with SEND

A reel drifts. Each clip sees only the clip before it, so by the
seventh clip the face is a copy of a copy of a copy. `SEND:` gives every later
clip a fixed anchor: a real frame of an earlier clip, as a reference image.

```
@h3 ref2va 9:16 lite
style: live-action, handheld phone video
CAST
GIRL (image 1, image 2): the young dancer, in a red tracksuit and white sneakers

CHUNK the warm-up
SHOT 6s: push in, small, slow
GIRL stretches her arms above her head in the middle of the studio.
SFX: sneakers squeaking on wood
SEND: frame 12 to image 2
HANDOFF: she drops into a low crouch

CHUNK the routine repeat 4
SHOT 6s: tracking, slow
GIRL spins and kicks across the studio floor.
SFX: sneakers squeaking on wood; a bass beat from a phone speaker
```

`image_1` is a photo of the dancer. `image_2` stays **unwired**: frame 12 of
the warm-up clip fills it.

| Segment | Clip | `ref_1` | `ref_2` | Subject line |
|---|---|---|---|---|
| 0 | the warm-up | image 1 | – | `<Subject 1> = the young dancer of <Picture 1>, …` |
| 1–4 | the routine | image 1 | frame 12 of segment 0 | `<Subject 1> = the young dancer of <Picture 1> and <Picture 2>, …` |

In segment 0 the frame does not exist yet, so orrery leaves `image 2` out of
the clip. From segment 1 on it is there in every clip, including all four
repetitions of the routine.

### The line

```
SEND: frame 0 to image 3
SEND: frames 2, 5, 34-46 to image 4
SEND: frame -1 to image 5 for segment 4+
SEND: frames -24--1 to image 6 for segments 4, 6, 7, 12
```

- **Where**: inside a `CHUNK`, any number of lines, in `@h3 ref2va` screenplays.
- **Frames** count from 0, at 24 fps, in the clip as the reel keeps it (Orrery
  Film, or H3 Motion Context's Chain Video): from the second clip on, the pinned
  frames are trimmed off, so frame 0 is always the first new frame. Single frames and
  ranges mix; `frame` and `frames` are the same word.
- **Negative frames** count from the clip's end: `-1` is the last, `-2` the one
  before. Ranges may mix signs: `-24--1` is the last second, `10--1` runs from
  frame 10 to the end. orrery resolves them against each clip's real length.
- **Several frames** become one image batch on that image, in the order written.
- **A chunk that repeats** sends from the first time it plays, so the anchor
  holds still.
- **Timing**: the image exists from the segment after the one where the chunk
  first plays. Where it does not exist it is left out: CAST sources and frame
  anchors on it go, and an `[image N]` in prose is flagged in lint.
- **`for segment …`** limits the clips that get it, by the node's segment
  numbers (from 0, as "Generating segment N" shows them): `4`, `4+` (4 and every
  one after), `4-8`, or a list such as `2, 4-8, 12+`; `segment` and `segments`
  are the same word. A listed segment before the frame exists goes without it,
  and lint says so.
- **One image, several lines**: fine. Where two fill it in the same segment,
  the one sent last takes over and lint names the segment; a `for segment …`
  lets them take turns. That re-anchors an image mid-reel, for a new outfit, say:

  ```
  CHUNK the old look repeat 4
  SEND: frame 0 to image 3 for segments 1-4
  …
  CHUNK the new look
  SEND: frame -1 to image 3 for segment 5+
  ```

  Segments 1–4 see the old look, every clip from 5 on the new one.

### With or without a CAST

A CAST line binds the frame to someone: `GIRL (image 1, image 2)` tells H3
that both pictures show the dancer. That is the strongest form, because H3
reads references through the prompt.

It also works without a CAST. With only

```
CHUNK the first pose
SHOT 7s: push in, small, slow
SEND: frame 0 to image 1
…
```

`ref_1` is the first clip's frame 0 in every clip after it. The prompt names it
nowhere; H3 gets it as an unlabelled reference. Write `[image 1]` into a shot
line if you want the prompt to point at it after all.

### Where the frames come from

Orrery Refs reads the clip from the reel's chain, in the folder the Orrery
Prompt's `latent_path` names (`h3_context` unless you wire another one): Orrery
Film's takes, or H3 Motion Context's Chain Video, whichever was written last.
Both replace a clip when its segment renders again and drop the ones after it,
so a reel rendered from the top with **Restart** always sends frames of this
reel, never of an older one. Start in the middle of a reel whose sending
clip was never rendered and Orrery Refs stops with a message instead of taking
the wrong frames.

It decodes only up to the last frame a `SEND:` names and keeps only those, so
anchors from many clips stay cheap. Orrery Refs runs on every queue, even when
nothing about its inputs changed: after a Restart the chain holds new clips
while the `picks` are the same as last time, and ComfyUI's cache would
otherwise hand on the older run's frames.

### Keeping a character across runs

Every frame Orrery Refs fetches for a `SEND:` is also stored as that image's
**anchor**, in the orrery home under `anchors/image_N/`. The Prompt tab's
timeline shows each anchor beside the chunk whose `SEND:` fills it, so you
see what a run handed on without a preview node. The `keep_sent` switch
on Orrery Refs decides what a run does with them:

- **Off** (the default): fresh frames from this run's chain, which replace the
  anchors. Before the sending clip exists, the image is not there.
- **On**: every sent image that has an anchor uses it, from segment 0 and for
  the whole run (within its `for segment …`, if it has one), in the prompt and
  on the refs. This run's frames do not replace it. Images without an anchor
  are fetched as usual, and stored.

So a reel whose dancer you like can hand her to the next one: switch
`keep_sent` on, change the story, keep the `SEND:` line that fills her image,
and every clip of the new reel starts from her, segment 0 included. To let go,
switch it off: the next run fetches fresh frames and they become the anchors.
The anchors belong to an image number, not to a template, so they hold across
edits as long as the character keeps her `image N`.

### Choosing the frame

- Pick a frame where the face is clear and sharp, not necessarily frame 0. A
  fast move at the start of a clip blurs it.
- To look before you choose, send a range once (`SEND: frames 0-47 to image 9`)
  and look at it on `preview`: every frame of the batch is there. Then send the
  one you like.
- A batch to Reference to Video counts as one picture: it reads only the first
  image of each reference. For several stills in ref2va, send them to several
  images (`SEND: frame 12 to image 2` and `SEND: frame 40 to image 3`). A batch
  is for nodes that take many images, such as Create H3 RefMod From Inputs (not
  tested with orrery yet).

## 7. What reaches the outputs, precisely

For every clip, Orrery Refs fills `ref_1`, `ref_2`, … in this order:

1. **The images the clip uses**, in `image N` order: CAST sources (the world's
   and the chunk's), frame anchors and `[image N]`. These are `<Picture 1>`,
   `<Picture 2>`, … in the prompt. A sent image that the clip uses is fetched
   from the chain; any other must be wired, or the run stops.
2. **Every other sent image that exists**, named or not, in `image N` order.
   The prompt does not label these.
3. **The rest is empty.** An empty ref that Reference to Video reads is `None`,
   which it skips. An empty ref that only other nodes read is blocked, so those
   nodes wait for a clip that has an image instead of failing the run.

**`preview`** carries every image of `ref_1` … `ref_9` in that order, every frame
of a batch included, scaled to 512 px high and centred on neutral grey at a
common width, so one Preview Image shows the whole clip's references. Each
image carries its ref (`ref_1`, `ref_2`, …) in white with a black edge in the
corner. A clip without any shows one grey frame that says `no refs`, so the
preview never keeps an older clip's images on screen. Preview there, not on a `ref_N`
that also goes into Reference to Video: an output hands every node it feeds the
same value, so an empty one is `None` for both, and Preview Image fails on
`None`. A plain white or black stand-in is no way out either: Reference to
Video would take it as a real reference.

When nothing tells the Orrery Prompt that an Orrery Refs reads its `picks` (the
`picks` pass through another node first, or the target is `text`), nothing is
packed: `ref_N` is simply `image_N`, and the prompt keeps your numbers.

## 8. Videos, audio and RefMods

Orrery Refs routes images only. The other reference types go straight into
Reference to Video and keep their own numbering:

| Reference | CAST source | Wire into | Label |
|---|---|---|---|
| video | `NAME (video 1)` | `ref_video_0` | `<Video 1>` |
| video with its sound | `NAME (video 1 + audio)` | `ref_video_0` + `ref_video_audio_0` | `<Video 1>`, its sound `<Audio 1>` |
| audio | `voice: audio 1` | `ref_audio_0` | `<Audio …>` after the video soundtracks |
| RefMod | `NAME (refmod NAME)` | nothing to wire: Orrery RefMods loads it from `models/refmods` onto the conditioning | none: a text-only `<Subject N>`, described in words |
| a clip to continue | `SHOT …: after video 1` | `ref_video_0` (a Load Video, for instance), its sound `ref_video_audio_0` | `<Video 1>` |


## 9. Messages and what to do about them

Errors stop the run; warnings appear in the Orrery Prompt's lint or in the
ComfyUI console.

| Message | What happened | Fix |
|---|---|---|
| `This clip's CAST uses image_2, but nothing is wired into it.` | the clip uses an image that is neither wired nor sent | wire `image_2`, or take it out of the clip's CAST |
| `This clip uses 3 reference images, but Reference to Video has 2 wired: <Picture 3> and up point at nothing.` (lint) | fewer `ref_image` slots are wired than the clip uses | wire `ref_3` → `ref_image_2` |
| `image 3 is wired into Orrery Refs and also filled by a SEND: line; …` | a sent image has a wire as well | unwire `image_3`, or send to a free image |
| `image 3 is sent from segment 0, but the chain 'h3_context' has no clip for segment 0: …` | the sending clip is not in the chain | render the reel from that chunk on (Restart), or check `latent_path` |
| `This reel SENDs frames as reference images, which Orrery Refs fetches: …` | no Orrery Refs reads the prompt's `picks` | wire `picks` into Orrery Refs |
| `image 3 is held (keep_sent), but it has no stored anchor: …` | `keep_sent` is on for an image that was never fetched | run once with `keep_sent` off, then switch it on |
| `SEND: hands frames to Reference to Video as reference images, so it needs an @h3 ref2va screenplay.` | `SEND:` in another mode | switch the header to `@h3 ref2va` |
| `SEND: belongs inside a CHUNK: …` | `SEND:` before the first `CHUNK` or in a screenplay without chunks | move it into the chunk whose clip it sends |
| `image 3 is filled by two SEND: lines in segment 5 (CHUNK 1 and CHUNK 3): …` (lint) | two lines fill one image in the same segment | fine if intended: the one sent last takes over; a `for segment …` lets them take turns |
| `SEND: to image 5 lists segment 2, but its frames come from segment 3: …` (lint) | a `for` names segments before the frame exists | fine if intended; those clips go without it |
| `[image 3] is mentioned before the SEND: line that fills it has played, …` (lint) | the prose names a sent image in a clip before it exists | fine if intended; it points at nothing in that clip |
| `[orrery] SEND to image 5: frame 60 is not in segment 1's clip, so it is left out.` (console) | the clip is shorter than the frame number (or a negative one reaches before its start) | pick another frame; with none left, the last frame stands in |
| `[orrery] ref_2 carries 5 frames, but Reference to Video reads only the first image of a reference; …` (console) | a batch goes into Reference to Video | send single frames to several images |

If a Preview Image fails on an empty ref (`'NoneType' object is not
subscriptable`), that ref goes into Reference to Video as well, so it stays
`None`. Move the preview to `preview`.

## 10. Limits

- Nine reference images per clip (`image_1` to `image_9`, `ref_1` to `ref_9`).
- Images only; videos and audio go straight into Reference to Video (section 8).
- `SEND:` needs `@h3 ref2va`, a reel, its clips kept (Orrery Film or Chain
  Video) and an Orrery Refs reading the prompt's `picks`.
- Reference to Video reads the first image of a batch only.

Related: [H3 screenplays](h3.md) (the CAST, frame anchors and reels in full),
[long videos](long-video.md) (the continuation, RefMods and the plan behind
reels), [the ComfyUI nodes](comfyui.md).
