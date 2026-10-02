"""Orrery Film's store: a reel's clips as orrery continues them, one take per segment.

Under `output/<latent_path>/orrery_film/`, `active.json` names the current run. The run's
`clips.json` lists the active take of every segment in order, in the shape Chain Video keeps, so
orrery.chain reads either store; `film.mp4` joins them. A take is a folder:

    video.mp4    the clip as kept (the pinned frames trimmed off): H.264 and AAC
    audio.npy    its sound as float32 [channels, samples]; the film encodes all of it at once, so
                 the joins don't click
    tail.npz     its last 22 frames' latent, picture and sound, which the next segment continues from
    meta.json    segment, frames, seed, template …

Rendering segment N again makes the new take active and drops the takes after it, which continued
another one; segment 0 starts a new run. Older takes and runs stay on disk.
"""

import json
import os
import time
import uuid
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path

from orrery.chain import chain_folder
from orrery.continuum.grid import FPS
from orrery.continuum.masked import Tail
from orrery.home import write_atomic

STORE = "orrery_film"
CRF = "18"


class FilmError(ValueError):
    pass


def _root(output: Path | str, latent_path: str) -> Path:
    folder = chain_folder(output, latent_path)
    if folder is None:
        raise FilmError(f"latent_path {latent_path!r} points outside ComfyUI's output folder.")
    return folder / STORE


def _active(root: Path) -> tuple[Path | None, dict]:
    try:
        run = root / json.loads((root / "active.json").read_text(encoding="utf-8"))["run"]
        return run, json.loads((run / "clips.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError):
        return None, {"clips": []}


def _before(latent_path: str, segment: int, run: Path | None, clips: list) -> None:
    if run is None or len(clips) < segment:
        raise FilmError(f"segment {segment} continues segment {segment - 1}, which the reel {latent_path!r} "
                        f"does not hold yet: render segment {len(clips)} first, or Restart the reel.")


def previous_tail(output: Path | str, latent_path: str, segment: int) -> Tail:
    """The tail of the take segment `segment` continues: segment - 1's in the active run."""
    run, state = _active(_root(output, latent_path))
    clips = state.get("clips", [])
    _before(latent_path, segment, run, clips)
    import numpy as np

    take = run / clips[segment - 1]["folder"]
    with np.load(take / "tail.npz") as stored:
        video, audio = stored["video"], stored["audio"]
    meta = json.loads((take / "meta.json").read_text(encoding="utf-8"))
    return Tail(video, audio, float(meta["grid_offset"]))


def save_take(output: Path | str, latent_path: str, segment: int, frames: Sequence, sound, sample_rate: int,
              tail: Tail, meta: dict) -> Path:
    """Keep a clip as segment `segment`'s take and join the film again; returns the take's folder.
    `frames`: the clip's frames as uint8 [height, width, 3], one by one (anything with len() that
    iterates); `sound`: float32 [channels, samples]."""
    import numpy as np

    root = _root(output, latent_path)
    count = len(frames)
    if not count:
        raise FilmError("the clip has no frames left once the pinned ones are trimmed.")
    rest = iter(frames)
    first = next(rest)
    height, width = int(first.shape[0]), int(first.shape[1])
    settings = [width, height, str(FPS), int(sample_rate), int(sound.shape[0])]
    if segment == 0:
        run, clips = root / f"run_{time.strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:6]}", []
    else:
        run, state = _active(root)
        clips = state.get("clips", [])
        _before(latent_path, segment, run, clips)
        was = state.get("settings") or settings
        if was[:2] != settings[:2]:
            raise FilmError(f"segment {segment} is {width}×{height}, the reel's segments before it "
                            f"{was[0]}×{was[1]}: a reel keeps one size (Restart it to change).")
        if was[3:] != settings[3:]:
            raise FilmError(f"segment {segment}'s sound is {sample_rate} Hz × {sound.shape[0]}, the reel's "
                            f"{was[3]} Hz × {was[4]}.")
    name = f"seg_{segment:04d}_{uuid.uuid4().hex[:8]}"
    tmp = run / f".{name}.tmp"
    tmp.mkdir(parents=True)
    sound = np.ascontiguousarray(sound, dtype=np.float32)
    _write_clip(tmp / "video.mp4", first, rest, sound, sample_rate)
    np.save(tmp / "audio.npy", sound)
    np.savez(tmp / "tail.npz", video=np.asarray(tail.video, np.float32), audio=np.asarray(tail.audio, np.float32))
    (tmp / "meta.json").write_text(json.dumps({**meta, "segment": segment, "frames": count,
                                               "grid_offset": tail.grid_offset,
                                               "created": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2),
                                   encoding="utf-8")
    os.replace(tmp, run / name)
    clips = [*clips[:segment], {"folder": name, "frames": count}]
    write_atomic(run / "clips.json", json.dumps({"settings": settings, "clips": clips}, indent=2))
    write_atomic(root / "active.json", json.dumps({"run": run.name}))
    _join(run, clips, int(sample_rate))
    return run / name


def film_file(take: Path) -> Path:
    return take.parent / "film.mp4"


def _layout(sound) -> str:
    return "mono" if sound.shape[0] == 1 else "stereo"


def _encode_sound(out, stream, sound, sample_rate: int) -> None:
    import av

    frame = av.AudioFrame.from_ndarray(sound, format="fltp", layout=_layout(sound))
    frame.sample_rate, frame.pts, frame.time_base = sample_rate, 0, Fraction(1, sample_rate)
    for packet in stream.encode(frame):
        out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)


def _sound_stream(out, sound, sample_rate: int):
    stream = out.add_stream("aac", rate=sample_rate)
    stream.layout = _layout(sound)
    return stream


def _write_clip(path: Path, first, rest, sound, sample_rate: int) -> None:
    """H.264 (no B-frames, so the film can stream-copy clips one after another) and AAC."""
    import av

    with av.open(str(path), "w") as out:
        video = out.add_stream("libx264", rate=FPS, options={"crf": CRF, "bf": "0"})
        video.width, video.height, video.pix_fmt = int(first.shape[1]), int(first.shape[0]), "yuv420p"
        audio = _sound_stream(out, sound, sample_rate) if sound.shape[-1] else None
        for frame in _chain(first, rest):
            for packet in video.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")):
                out.mux(packet)
        for packet in video.encode(None):
            out.mux(packet)
        if audio is not None:
            _encode_sound(out, audio, sound, sample_rate)


def _chain(first, rest):
    yield first
    yield from rest


def _join(run: Path, clips: list[dict], sample_rate: int) -> None:
    """film.mp4: the takes' video stream-copied one after another, their sound joined and encoded once."""
    import av
    import numpy as np

    sound = np.concatenate([np.load(run / c["folder"] / "audio.npy") for c in clips], axis=1)
    tmp = run / "film.tmp.mp4"
    sources = [av.open(str(run / c["folder"] / "video.mp4")) for c in clips]
    try:
        with av.open(str(tmp), "w") as out:
            video = out.add_stream_from_template(sources[0].streams.video[0])
            audio = _sound_stream(out, sound, sample_rate) if sound.shape[-1] else None
            start = 0.0
            for source, clip in zip(sources, clips, strict=True):
                stream = source.streams.video[0]
                shift = round(start / stream.time_base)
                for packet in source.demux(stream):
                    if packet.dts is None:
                        continue
                    packet.pts += shift
                    packet.dts += shift
                    packet.stream = video
                    out.mux(packet)
                start += clip["frames"] / FPS
            if audio is not None:
                _encode_sound(out, audio, sound, sample_rate)
    finally:
        for source in sources:
            source.close()
    os.replace(tmp, run / "film.mp4")
