"""The clip before this one, from H3 Motion Context's Chain Video: for the language model to watch
and for ref2va to continue.

Chain Video keeps every trimmed clip under `output/<latent_path>/chain_video`: `active.json` names
the current run, whose `clips.json` lists the clip folders in order (clip_index from 1), each with a
`video.mp4`. orrery's segments count from 0, so segment N continues clip N. The model sees one
frame a second plus the last one, scaled down (~250 tokens a frame instead of ~1000); ref2va gets
the last three seconds at full size, which is what video continuation wants. `SEND:` reads a
segment's own clip (`clip_file`) and only the frames it names (`frames`).
"""

import json
from pathlib import Path

DEFAULT_CHAIN = "h3_context"  # Chain Video's and Load Latent's default latent_path
STILL_WIDTH = 672
TAIL_SECONDS = 3.0


def previous_clip(output: Path | str, latent_path: str, segment: int) -> Path | None:
    """The video file of the clip before `segment`, or None (first segment, no chain, not made yet)."""
    return clip_file(output, latent_path, segment - 1) if segment >= 1 else None


def clip_file(output: Path | str, latent_path: str, index: int) -> Path | None:
    """The video file of segment `index`'s own clip (Chain Video's clip index + 1), or None."""
    if index < 0:
        return None
    output = Path(output).resolve()
    folder = (output / latent_path).resolve()
    if not folder.is_relative_to(output):
        return None
    if folder.is_file() or (not folder.is_dir() and folder.suffix == ".safetensors"):  # as Motion Context reads it
        folder = folder.parent
    root = folder / "chain_video"
    try:
        run = (root / json.loads((root / "active.json").read_text(encoding="utf-8"))["run"]).resolve()
        clips = json.loads((run / "clips.json").read_text(encoding="utf-8"))["clips"]
        path = (run / clips[index]["folder"] / "video.mp4").resolve() if len(clips) > index else None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if path is None or not run.is_relative_to(root) or not path.is_relative_to(run) or not path.is_file():
        return None
    return path


def frame_picks(count: int, wanted: list[int]) -> tuple[list[int], list[int]]:
    """(the frames kept, those past a clip of `count` frames); with none kept the last one stands in."""
    kept, dropped = [f for f in wanted if f < count], [f for f in wanted if f >= count]
    return (kept or ([count - 1] if count else [])), dropped


def frames(path: Path, wanted: list[int]):
    """(the frames a SEND: names as one IMAGE batch, those past the clip's end). Decodes only up to the
    last frame named, and keeps only those, not the whole clip. ComfyUI only (torch)."""
    import av
    import numpy as np
    import torch

    want, got, count, last = set(wanted), {}, 0, None
    with av.open(str(path)) as container:
        for i, frame in enumerate(container.decode(container.streams.video[0])):
            count, last = i + 1, frame
            if i in want:
                got[i] = frame.to_ndarray(format="rgb24")
            if i >= max(want):
                break
    picks, dropped = frame_picks(count, wanted)
    if not picks:
        raise ValueError(f"{path} has no video frames.")
    if picks[0] not in got:  # the last frame, standing in
        got[picks[0]] = last.to_ndarray(format="rgb24")
    return torch.from_numpy(np.stack([got[i] for i in picks])).float() / 255.0, dropped


def still_indices(frames: int, fps: float) -> list[int]:
    """One frame a second, and always the last one: the next clip starts there."""
    picks = list(range(0, frames, max(1, round(fps))))
    if frames and picks[-1] != frames - 1:
        picks.append(frames - 1)
    return picks


def tail_start(frames: int, fps: float, seconds: float = TAIL_SECONDS) -> int:
    return max(0, frames - round(seconds * fps))


def load(path: Path):
    """(stills for the model, the tail as an IMAGE batch, its AUDIO or None). ComfyUI only."""
    import comfy.utils
    from comfy_api.latest import InputImpl

    parts = InputImpl.VideoFromFile(str(path)).get_components()
    images, fps = parts.images, float(parts.frame_rate)
    stills = images[still_indices(len(images), fps)]
    height, width = stills.shape[1], stills.shape[2]
    if width > STILL_WIDTH:
        stills = comfy.utils.common_upscale(stills.movedim(-1, 1), STILL_WIDTH, round(height * STILL_WIDTH / width),
                                            "bilinear", "disabled").movedim(1, -1)
    start = tail_start(len(images), fps)
    audio = parts.audio
    if audio is not None:
        rate = audio["sample_rate"]
        audio = {"waveform": audio["waveform"][..., round(start / fps * rate):], "sample_rate": rate}
    return stills, images[start:], audio
