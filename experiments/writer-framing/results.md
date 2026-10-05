# Writer framing: does Prompt from image use the screenplay sent along? (#333)

Pyro's case on 2026-10-05: "winter forest" (an @h3 screenplay: a badger steps onto a log in a misty forest), a photo
of a red-haired woman in a room as first_frame, **the prompt** sent along, the steer "made her join the previous
shots". With the 8B text encoder (qwen3vl_8b_int8_convrot, temperature 0.8) every take animated the photo in its
room and ignored the screenplay.

`run.py` sends the 8B each framing through the running ComfyUI's core Generate Text node, as orrery's text encoder
backend does (its chat template, the frame at 768 px on the long edge, its sampling), seeds 1010 on. "She is in the forest":
read take by take (the keyword check in `run.py` counts V5 as a hit, but those takes keep her in her room). `results.json` keeps every prompt and take.

| Framing | What | She is in the forest (read) | A take |
|---|---|---|---|
| V0 | today's request (6af5530): the writer's text, then the prompt and the direction | 0 of 3 | The girl with red hair adjusts her black lace top, her fingers brushing the fabric as she … |
| V1 | the screenplay first, then the writer's task, then the direction | 0 of 3 | The young woman with fiery red hair stands centered, her gaze fixed on the camera as she s… |
| V2 | the direction at the start as well | 0 of 3 | The woman with red hair adjusts her black lace crop top as she turns her head slightly to … |
| V3 | the task changes: the next shot of this screenplay, with what the picture shows | 0 of 3 | The woman with long red hair stands in the center of the room, her black lace crop top cat… |
| V4 | V3, and said plainly: take only the person from the picture, leave its room behind | 3 of 3 | The woman with long red hair in a black top steps onto a mossy log in the misty forest at … |
| V5 | V3 with the picture after the screenplay (orrery put it first) | 0 of 3 (her room, the forest only named) | The woman with long red hair in a black top stands in the center of the room, her gaze fix… |
| V6 | V4 with the picture after the screenplay | 3 of 3 | The woman with long red hair in a black top steps onto the fallen log beside the badger, h… |
| V7 | what the writers send now: describe_shot_into, the picture where it stands | 3 of 3 | The woman with long red hair in a black top steps onto the fallen log beside the badger, h… |
| V8 | V7 without a steer | 2 of 2 | The woman with long red hair in a black top steps onto the fallen log beside the badger, h… |
| V9 | V7 steered elsewhere: "she chases the badger away" | 2 of 2 | The woman with long red hair in a black top steps onto the fallen log beside the badger, h… |

**What it showed.** Moving the prompt or the direction around (V0–V2) changed nothing: the picture sets the place.
Changing the task (V3) or only moving the picture after the screenplay (V5) neither. What worked was saying plainly
what to take from the picture, the person, and what to leave behind, its room (V4); with the picture after the
screenplay as well (V6) she joins the badger's shot. That is `builtin/writers/describe_shot_into.md`, used when the
prompt goes along with a picture on a screenplay (V7: 3 of 3, V8 without a steer 2 of 2), and the direction steers it
(V9: "Get out of here!", the badger bolts).

## The story interpolator, from a photo to the prompt (#343)

Pyro's next case: Lucy the cat on a pink ottoman in a living room as first_frame, the story **from first_frame to the
prompt** ("winter forest"), 3 scenes of 10 s, no steer: how she gets up and walks into the badger's forest. The ends
were written as the writers do; "Arrives": the last scene reaches the forest and stops where its first shot begins
(read take by take).

| Framing | What | Arrives (read) | The cat talks |
|---|---|---|---|
| S1 | the story text of 8882217: the start a picture shown first, the end the whole screenplay | 0 of 3: she never leaves the ottoman | 3 of 3 |
| S2 | S1 with the picture where the start is named | 1 of 3 (through a door) | 3 of 3 |
| S3 | S2 and the journey said plainly | 2 of 3, but by writing the end's own shots again, without her | 3 of 3 |
| S4 | S2, the end shown as its first shot only, the journey said with who travels and where the last scene stops, who may speak | 3 of 3 on the way, 1 of 3 onto the log | 3 of 3 |
| S6 | what the writers send since: S4 in `story_scenes.md`, the speech line out of the scene's skeleton and example | 2 of 3 onto the log (the third stops at the window, looking out at the forest) | 0 of 3 |

**What it showed.** As with Prompt from image, a picture shown first sets the place and the story stays there; shown
where the start is named, and the way said plainly, she travels. The whole end screenplay invited the 8B to write it
again; its first shot alone is where to arrive. A `NAME (…)` line in the scene's skeleton made every cat talk.
