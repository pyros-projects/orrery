"""The clip before this one, from the reel's chain: for the language model to watch and for ref2va
to continue.

Two stores keep a reel's trimmed clips under `output/<latent_path>`: Orrery Film's `orrery_film`
(see orrery.film) and H3 Motion Context's `chain_video`. In both, `active.json` names the current
run, whose `clips.json` lists the clip folders in order, each with a `video.mp4`; the store written
last is the one read, so a workflow can switch engines. orrery's segments count from 0: segment N
is the N+1th clip (Chain Video's clip_index N+1). The model sees one frame a second plus the last
one, scaled down (~250 tokens a frame instead of ~1000); ref2va gets the last three seconds at full
size, which is what video continuation wants. `SEND:` reads a
segment's own clip (`clip_file`) and only the frames it names (`frames`).
"""

import json
from pathlib import Path

DEFAULT_CHAIN = "h3_context"  # Chain Video's and Load Latent's default latent_path
STORES = ("orrery_film", "chain_video")  # Orrery Film's takes, H3 Motion Context's Chain Video
STILL_WIDTH = 672


def previous_clip(output: Path | str, latent_path: str, segment: int) -> Path | None:
    """The video file of the clip before `segment`, or None (first segment, no chain, not made yet)."""
    return clip_file(output, latent_path, segment - 1) if segment >= 1 else None


def chain_folder(output: Path | str, latent_path: str) -> Path | None:
    """The folder a reel's chain lives in, or None for a path outside ComfyUI's output."""
    output = Path(output).resolve()
    folder = (output / latent_path).resolve()
    if not folder.is_relative_to(output):
        return None
    if folder.is_file() or (not folder.is_dir() and folder.suffix == ".safetensors"):  # as Motion Context reads it
        folder = folder.parent
    return folder


def _run(root: Path) -> tuple[Path, list[dict], list, float] | None:
    """A store's active run folder, its clips, its settings (width, height, fps, audio) and when its
    clips.json was written; None when the store holds none."""
    try:
        run = (root / json.loads((root / "active.json").read_text(encoding="utf-8"))["run"]).resolve()
        listed = run / "clips.json"
        state = json.loads(listed.read_text(encoding="utf-8"))
        clips, settings, written = state["clips"], state.get("settings"), listed.stat().st_mtime
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    if not (run.is_relative_to(root) and isinstance(clips, list)):
        return None
    return run, clips, settings if isinstance(settings, list) else [], written


def _active(output: Path | str, latent_path: str) -> tuple[Path, list[dict], list] | None:
    """The active run, clips and settings of the store written last, or None (no chain, or a path
    outside the output)."""
    folder = chain_folder(output, latent_path)
    runs = [r for r in (_run(folder / store) for store in STORES) if r] if folder else []
    return max(runs, key=lambda r: r[3])[:3] if runs else None


def _video(run: Path, clip) -> Path | None:
    try:
        path = (run / clip["folder"] / "video.mp4").resolve()
    except (KeyError, TypeError):
        return None
    return path if path.is_relative_to(run) and path.is_file() else None


def clip_file(output: Path | str, latent_path: str, index: int) -> Path | None:
    """The video file of segment `index`'s own clip, or None."""
    active = _active(output, latent_path) if index >= 0 else None
    if active is None or len(active[1]) <= index:
        return None
    return _video(active[0], active[1][index])


def listing(output: Path | str, latent_path: str) -> dict:
    """The chain's frame size (one for all its clips; None when unknown) and the clips it holds, by
    segment, each with a version that changes when it is rendered again."""
    active = _active(output, latent_path)
    if active is None:
        return {"width": None, "height": None, "clips": []}
    run, clips, settings = active
    width, height = (settings[:2] if len(settings) >= 2 and all(isinstance(v, int) for v in settings[:2])
                     else (None, None))
    return {"width": width, "height": height,
            "clips": [{"segment": i, "frames": clip.get("frames"), "version": clip.get("folder")}
                      for i, clip in enumerate(clips) if isinstance(clip, dict) and _video(run, clip)]}


def frame_picks(count: int, spans: list[list[int]]) -> tuple[list[int], list]:
    """(the frames kept, those outside a clip of `count` frames, as written) for SEND: spans; a negative
    frame counts from the end (-1 the last). With none kept the last frame stands in."""
    kept, dropped = [], []
    for first, last in spans:
        a, b = (first + count if first < 0 else first), (last + count if last < 0 else last)
        for i in range(a, b + 1):
            if 0 <= i < count:
                kept.append(i)
            else:
                dropped.append(i - count if first < 0 and last < 0 else i)
        if a > b:
            dropped.append(f"{first}-{last}")
    return (kept or ([count - 1] if count else [])), dropped


def frames(path: Path, spans: list[list[int]], step: int = 1):
    """(the frames a SEND: names as one IMAGE batch, those outside the clip). Reads the clip's length from
    the container (counting packets when it has none), then decodes only up to the last frame named and
    keeps only those, not the whole clip. `step`: every step-th of them (`every 10 frames`). ComfyUI only
    (torch)."""
    import av
    import numpy as np
    import torch

    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        count = stream.frames or sum(1 for packet in container.demux(stream) if packet.size)
    picks, dropped = frame_picks(count, spans)
    picks = picks[::max(1, step)]
    if not picks:
        raise ValueError(f"{path} has no video frames.")
    want, got, last = set(picks), {}, None
    with av.open(str(path)) as container:
        for i, frame in enumerate(container.decode(container.streams.video[0])):
            last = frame
            if i in want:
                got[i] = frame.to_ndarray(format="rgb24")
            if i >= max(want):
                break
    dropped += [i for i in picks if i not in got]  # the container counted more frames than it holds
    kept = [got[i] for i in picks if i in got] or [last.to_ndarray(format="rgb24")]
    return torch.from_numpy(np.stack(kept)).float() / 255.0, dropped


def still_indices(frames: int, fps: float) -> list[int]:
    """One frame a second, and always the last one: the next clip starts there."""
    picks = list(range(0, frames, max(1, round(fps))))
    if frames and picks[-1] != frames - 1:
        picks.append(frames - 1)
    return picks


def load(path: Path):
    """The clip's stills, for the language model that writes `--…--` slots. ComfyUI only."""
    import comfy.utils
    from comfy_api.latest import InputImpl

    parts = InputImpl.VideoFromFile(str(path)).get_components()
    images, fps = parts.images, float(parts.frame_rate)
    stills = images[still_indices(len(images), fps)]
    height, width = stills.shape[1], stills.shape[2]
    if width > STILL_WIDTH:
        stills = comfy.utils.common_upscale(stills.movedim(-1, 1), STILL_WIDTH, round(height * STILL_WIDTH / width),
                                            "bilinear", "disabled").movedim(1, -1)
    return stills
