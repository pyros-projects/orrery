"""Does the Prompt from image writer use the prompt sent along and the steer? (#333)

Pyro's case: "winter forest" (an @h3 screenplay: a badger in a misty forest), a photo of a woman in first_frame,
the prompt sent along and the steer "made her join the previous shots". With the 8B text encoder the takes
animated the photo and ignored the screenplay. This sends the 8B each framing of that request, as orrery's
text encoder backend does (its chat template, the frame at 768 px on the long edge, its sampling), through
the running ComfyUI's core Generate Text node, a few seeds each, and keeps what came back.

    uv run python experiments/writer-framing/run.py [--seeds 3] [--only V3]

It needs the ComfyUI at 127.0.0.1:8188 and reads (never writes) the orrery home's libraries.
"""

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

from orrery import writers
from orrery.comfy_llm import VISION, chat
from orrery.dsl import strip_comments
from orrery.home import Home

COMFY = "http://127.0.0.1:8188"
HERE = Path(__file__).parent
PICTURE = "2022-06-09 01.12.02 2856404072522572109_45219232759.jpg"  # Pyro's first_frame, in ComfyUI's input
SIZE = (736, 768)  # as orrery fits it: 768 on the long edge, multiples of 16
ENCODER = "qwen3vl_8b_int8_convrot.safetensors"
STEER = "made her join the previous shots"
SEED = 1010


def template() -> str:
    text = (Path.home() / ".orrery/presets/h3/winter_forest.orr").read_text(encoding="utf-8")
    return strip_comments(text.split("---\n", 2)[2] if text.startswith("---") else text)


def variants(h: Home) -> dict[str, str]:
    t, libs, weights = template(), h.libraries(), h.weights()
    rolled = writers._rolled(t, SEED, libs, weights)
    base = writers.request(h, "describe", t, SEED, libs, weights, STEER, ["the first frame"], True)
    plain = writers.request(h, "describe", t, SEED, libs, weights, "", ["the first frame"], False)
    shot = writers.shot_seconds(t)
    return {
        # V0: what the writers send today (6af5530): the writer's text, then the prompt and the direction after it
        "V0": base,
        # V1: the screenplay first, then the writer's task, then the direction
        "V1": f"The screenplay you write for, as it rolls now:\n\n{rolled}\n\n{plain}\n\n"
              f"The direction, which outweighs everything above: {STEER}.\n\nAnswer as asked above, with what you write alone.",
        # V2: today's request with the direction at its start as well
        "V2": f"Your direction for this, above everything else: {STEER}.\n\n{base}",
        # V3: the task itself changes when the prompt goes along: the next shot of this screenplay, with what the
        # picture shows in it
        "V3": f"""You write one more shot for a screenplay of the MiniMax H3 video model, which makes video with sound. The screenplay as it rolls now:

{rolled}

The picture sent along shows who or what your shot brings into this screenplay. Write the next shot: it goes on from the shots above, in their place, their light and their style, and shows what the picture shows, named by what it is (a woman with long red hair in a black top, not "the picture"), doing something there.

How the shot is written:

SHOT {shot}s: <camera move>, <size>, <speed>
Two or three sentences in the present tense: what happens, in the order it happens.
SFX: a sound; another sound

The direction, which outweighs everything above: {STEER}.

Start with "SHOT {shot}s:". Answer with the shot alone.""",
        # V4: V3, and what to take from the picture said plainly: the person, not the room
        "V4": v4(rolled, shot, ""),
        # V5: V3 with the picture after the screenplay, where the text introduces it (orrery puts it first)
        "V5": v3_at(rolled, shot),
        # V6: V4 with the picture after the screenplay
        "V6": v4(rolled, shot, PICTURE_AT),
        # V7: what the writers send since V6 won: the describe_shot_into text, the picture where it says
        "V7": writers.request(h, "describe", t, SEED, libs, weights, STEER, ["the first frame"], True),
        # V8: V7 without a steer; V9: V7 steered elsewhere, to see the direction count
        "V8": writers.request(h, "describe", t, SEED, libs, weights, "", ["the first frame"], True),
        "V9": writers.request(h, "describe", t, SEED, libs, weights, "she chases the badger away", ["the first frame"], True),
    }


PICTURE_AT = "<<picture>>"  # where the picture goes in a variant's text; without it, first (as orrery does)


def v4(rolled: str, shot: int, at: str) -> str:
    return f"""You write one more shot for a screenplay of the MiniMax H3 video model, which makes video with sound. The screenplay as it rolls now:

{rolled}

{f"The picture: {at}" if at else "The picture sent along"} shows a person who joins this screenplay. From the picture take only the person: how they look, their hair, their clothes. Leave everything else in the picture behind (its room, its walls, its light, its furniture): your shot happens where the screenplay's shots happen, in their place, light and weather.

Write the next shot: it goes on from the shots above, and the person from the picture is in it, named by what they look like (a woman with long red hair in a black top), doing something in the screenplay's place.

How the shot is written:

SHOT {shot}s: <camera move>, <size>, <speed>
Two or three sentences in the present tense: what happens, in the order it happens.
SFX: a sound; another sound

The direction, which outweighs everything above: {STEER}.

Start with "SHOT {shot}s:". Answer with the shot alone."""


def v3_at(rolled: str, shot: int) -> str:
    return f"""You write one more shot for a screenplay of the MiniMax H3 video model, which makes video with sound. The screenplay as it rolls now:

{rolled}

This picture shows who or what your shot brings into this screenplay: {PICTURE_AT}

Write the next shot: it goes on from the shots above, in their place, their light and their style, and shows what the picture shows, named by what it is (a woman with long red hair in a black top, not "the picture"), doing something there.

How the shot is written:

SHOT {shot}s: <camera move>, <size>, <speed>
Two or three sentences in the present tense: what happens, in the order it happens.
SFX: a sound; another sound

The direction, which outweighs everything above: {STEER}.

Start with "SHOT {shot}s:". Answer with the shot alone."""


def turn(prompt: str) -> str:
    """orrery's chat turn, the picture first, or where the variant's text puts it."""
    if PICTURE_AT not in prompt:
        return chat(prompt, 1)
    return chat(prompt, 0).replace(PICTURE_AT, VISION.strip())


def post(path: str, body: dict | None = None):
    req = urllib.request.Request(COMFY + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def generate(prompt: str, seed: int) -> str:
    graph = {
        "1": {"class_type": "CLIPLoader", "inputs": {"clip_name": ENCODER, "type": "minimax"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": PICTURE}},
        "3": {"class_type": "ImageScale", "inputs": {"image": ["2", 0], "upscale_method": "bilinear", "width": SIZE[0],
                                                      "height": SIZE[1], "crop": "disabled"}},
        "4": {"class_type": "TextGenerate", "inputs": {
            "clip": ["1", 0], "prompt": turn(prompt), "image": ["3", 0], "max_length": 2048,
            "sampling_mode": "on", "sampling_mode.temperature": 0.8, "sampling_mode.top_k": 64, "sampling_mode.top_p": 0.95,
            "sampling_mode.min_p": 0.05, "sampling_mode.repetition_penalty": 1.05, "sampling_mode.seed": seed,
            "thinking": False, "use_default_template": False}},
        "5": {"class_type": "PreviewAny", "inputs": {"source": ["4", 0]}},
    }
    pid = post("/prompt", {"prompt": graph})["prompt_id"]
    for _ in range(600):
        time.sleep(0.5)
        h = post(f"/history/{pid}").get(pid)
        if h and h.get("status", {}).get("completed"):
            return h["outputs"]["5"]["text"][0]
        if h and h.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(h["status"])[:800])
    raise TimeoutError(pid)


STORY = re.compile(r"\b(forest|snow|log|badger|frost|pine|trees?|winter|mist)\b", re.IGNORECASE)
HER = re.compile(r"\b(woman|she|her|red[- ]haired|red hair)\b", re.IGNORECASE)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    h = Home(Path.home() / ".orrery")
    path = HERE / "results.json"
    out = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    for name, prompt in variants(h).items():
        if args.only and name not in args.only.split(","):
            continue
        out[name] = {"prompt": prompt, "takes": []}
        for k in range(args.seeds):
            text = generate(prompt, SEED + k)
            take, problem = writers.check("describe", template(), text)
            out[name]["takes"].append({"seed": SEED + k, "text": take, "problem": problem,
                                       "story": bool(STORY.search(take)), "her": bool(HER.search(take))})
            print(f"--- {name} seed {SEED + k}: story={bool(STORY.search(take))} her={bool(HER.search(take))} {problem or ''}\n{take}\n")
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
