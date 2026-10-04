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
another one; segment 0 starts a new run only when the size or the sound changes. Older takes and runs stay
on disk. A take's meta names the take
it continues (`after`), so sample surfing (#206) offers only the takes that fit the clip before, and
`pick_take` makes one of them active again.
"""

import itertools
import json
import os
import re
import shutil
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

from orrery.chain import chain_folder, input_file
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


def _continues(clips: list, take: int, segment: int) -> bool:
    """Whether the take of segment `take` continues segment `segment`, itself or through the ones between."""
    while take is not None and take > segment:
        take = clips[take].get("continues", take - 1)
    return take == segment


def _before(latent_path: str, segment: int, run: Path | None, clips: list) -> None:
    if run is None or len(clips) < segment:
        raise FilmError(f"clip {segment + 1} continues clip {segment}, which the reel {latent_path!r} does not hold "
                        f"yet: render clip {len(clips) + 1} first (segment {len(clips)}), or Restart the reel.")


def previous_tail(output: Path | str, latent_path: str, segment: int, continues: int | None = None) -> Tail:
    """The tail of the take segment `segment` continues: `continues`' in the active run (a scene's AFTER:),
    else segment - 1's."""
    run, state = _active(_root(output, latent_path))
    clips = state.get("clips", [])
    _before(latent_path, segment, run, clips)
    import numpy as np

    take = run / clips[segment - 1 if continues is None else continues]["folder"]
    with np.load(take / "tail.npz") as stored:
        video, audio = stored["video"], stored["audio"]
    meta = json.loads((take / "meta.json").read_text(encoding="utf-8"))
    return Tail(video, audio, float(meta["grid_offset"]))


def save_take(output: Path | str, latent_path: str, segment: int, frames: Sequence, sound, sample_rate: int,
              tail: Tail, meta: dict, continues: int | None = -1, test: bool = False) -> Path:
    """Keep a clip as segment `segment`'s take and join the film again; returns the take's folder.
    `frames`: the clip's frames as uint8 [height, width, 3], one by one (anything with len() that
    iterates); `sound`: float32 [channels, samples]. `continues`: the segment it continues (-1: the one
    before; None: none, it started afresh). The takes after it stay as long as none of them continues it.
    A `test` take (a test scene's) is kept, and the film is joined without it."""
    import numpy as np

    root = _root(output, latent_path)
    count = len(frames)
    if not count:
        raise FilmError("the clip has no frames left once the pinned ones are trimmed.")
    rest = iter(frames)
    first = next(rest)
    height, width = int(first.shape[0]), int(first.shape[1])
    settings = [width, height, str(FPS), int(sample_rate), int(sound.shape[0])]
    run, state = _active(root)
    clips = state.get("clips", [])
    was = state.get("settings") or settings
    if segment == 0 and (run is None or was != settings):  # clip 1 stays in its run, beside its other takes
        run, clips, state = root / f"run_{time.strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:6]}", [], {}
    elif segment:
        _before(latent_path, segment, run, clips)
        if was[:2] != settings[:2]:
            raise FilmError(f"clip {segment + 1} is {width}×{height}, the reel's clips before it "
                            f"{was[0]}×{was[1]}: a reel keeps one size (Restart it to change).")
        if was[3:] != settings[3:]:
            raise FilmError(f"clip {segment + 1}'s sound is {sample_rate} Hz × {sound.shape[0]}, the reel's "
                            f"{was[3]} Hz × {was[4]}.")
    continues = segment - 1 if continues == -1 else continues
    after = clips[continues]["folder"] if continues is not None and 0 <= continues < len(clips) else None
    follows = clips[segment - 1]["folder"] if 0 < segment <= len(clips) else None  # its parent in the take tree (#240)
    last = dict(state.get("last") or {})
    name = f"seg_{segment:04d}_{uuid.uuid4().hex[:8]}"
    tmp = run / f".{name}.tmp"
    tmp.mkdir(parents=True)
    sound = np.ascontiguousarray(sound, dtype=np.float32)
    _write_clip(tmp / "video.mp4", first, rest, sound, sample_rate)
    np.save(tmp / "audio.npy", sound)
    np.savez(tmp / "tail.npz", video=np.asarray(tail.video, np.float32), audio=np.asarray(tail.audio, np.float32))
    (tmp / "meta.json").write_text(json.dumps({**meta, "segment": segment, "frames": count, "continues": continues,
                                               "after": after, "follows": follows, "grid_offset": tail.grid_offset,
                                               **({"test": True} if test else {}),
                                               "created": datetime.now(UTC).astimezone().isoformat(timespec="microseconds")}, indent=2),
                                   encoding="utf-8")
    os.replace(tmp, run / name)
    later = list(itertools.takewhile(lambda c: not _continues(clips, c, segment), range(segment + 1, len(clips))))
    clips = [*clips[:segment], {"folder": name, "frames": count, "continues": continues, **({"test": True} if test else {})},
             *(clips[c] for c in later)]
    if follows:
        last[follows] = name  # the take last made on its parent: the way back along this path (#240)
    write_atomic(run / "clips.json", json.dumps({"settings": settings, "clips": clips, "last": last}, indent=2))
    write_atomic(root / "active.json", json.dumps({"run": run.name}))
    _join(run, clips, int(sample_rate))
    return run / name


def keep_input(source: Path | str, output: Path | str, latent_path: str) -> Path:
    """The Orrery Prompt's input video as the chain's clip before clip 1 (chain.clip_file(-1)): at 24 fps
    (each frame the one showing at that moment), even-sized for H.264, its sound as it is. Written again
    only when the source file changes."""
    import av
    import numpy as np

    source, target = Path(source), input_file(output, latent_path)
    if target is None:
        raise FilmError(f"the reel's latent_path {latent_path!r} lies outside ComfyUI's output folder.")
    stat = source.stat()
    stamp = {"source": str(source.resolve()), "size": stat.st_size, "mtime": stat.st_mtime_ns}
    kept = target.with_suffix(".json")
    if target.is_file() and kept.is_file() and json.loads(kept.read_text(encoding="utf-8")) == stamp:
        return target
    with av.open(str(source)) as container:
        sound, rate = _input_sound(container)
    tmp = target.with_name(f".{target.name}.tmp.mp4")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(source)) as container:
        frames = _at_24_fps(container)
        first = next(frames, None)
        if first is None:
            raise FilmError(f"the input video {source.name} has no frames.")
        _write_clip(tmp, first, frames, sound if sound is not None else np.zeros((1, 0), np.float32), rate)
    os.replace(tmp, target)
    write_atomic(kept, json.dumps(stamp))
    return target


def _at_24_fps(container):
    """The video's frames at FPS, as uint8 [height, width, 3] cut to even sizes: for every 1/24 s the frame
    showing then (repeated when the source is slower, skipped when it is faster)."""
    stream, k = container.streams.video[0], 0
    held, start = None, None
    for i, frame in enumerate(container.decode(stream)):
        t = float(frame.pts * stream.time_base) if frame.pts is not None else i / float(stream.average_rate or FPS)
        start = t if start is None else start
        t -= start  # a stream may start late: its first frame is the clip's first
        picture = frame.to_ndarray(format="rgb24")
        picture = picture[: picture.shape[0] // 2 * 2, : picture.shape[1] // 2 * 2]
        while held is not None and k / FPS < t - 1e-6:
            yield held
            k += 1
        held = picture
    if held is not None:
        yield held


def _input_sound(container):
    """The input video's sound as float32 [channels, samples] and its rate, or (None, 48000) without one."""
    import av
    import numpy as np

    if not container.streams.audio:
        return None, 48000
    stream = container.streams.audio[0]
    layout = "mono" if stream.channels == 1 else "stereo"
    resampler = av.AudioResampler(format="fltp", layout=layout, rate=stream.rate)
    parts = [r.to_ndarray() for frame in container.decode(stream) for r in resampler.resample(frame)]
    parts += [r.to_ndarray() for r in resampler.resample(None)]
    return (np.concatenate(parts, axis=1).astype(np.float32) if parts else None), int(stream.rate)


_TAKE = re.compile(r"^seg_(\d{4})_[0-9a-f]{8}$")


def _meta(take: Path) -> dict:
    try:
        return json.loads((take / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def takes(output: Path | str, latent_path: str) -> dict[int, list[dict]]:
    """The takes of every segment in the active run that fit the clip before as it is now (a take made on
    another take of it would not continue it), oldest first: {segment: [{folder, seed, take, created, active,
    scene, template}]}, the scene it plays and its template's hash telling the prompt it was made with (#242)."""
    run, state = _active(_root(output, latent_path))
    if run is None:
        return {}
    clips, out = state.get("clips", []), {}
    for take in sorted(p for p in run.iterdir() if p.is_dir() and _TAKE.match(p.name)):
        segment, meta = int(_TAKE.match(take.name).group(1)), _meta(take)
        before = meta.get("continues")
        fits = meta.get("after") is None or (before is not None and 0 <= before < len(clips)
                                            and clips[before]["folder"] == meta["after"])
        if fits and segment < len(clips):
            out.setdefault(segment, []).append({"folder": take.name, "seed": meta.get("seed"), "take": meta.get("take") or 0,
                                                "created": meta.get("created"), "active": clips[segment]["folder"] == take.name,
                                                "scene": meta.get("chunk"), "template": meta.get("template"),
                                                "_at": (meta.get("created") or "", (take / "meta.json").stat().st_mtime_ns)})
    for listed in out.values():
        listed.sort(key=lambda t: t.pop("_at"))  # the order they were made in (older takes count whole seconds)
    return out


def take_file(output: Path | str, latent_path: str, folder: str) -> Path | None:
    """A take's video in the active run, by its folder's name."""
    run, _ = _active(_root(output, latent_path))
    path = run / folder / "video.mp4" if run is not None and _TAKE.match(folder) else None
    return path if path is not None and path.is_file() else None


def _take(output: Path | str, latent_path: str, segment: int, folder: str) -> tuple[Path, dict, list]:
    """The active run, its state and clips, if it holds the take `folder` of `segment`."""
    run, state = _active(_root(output, latent_path))
    match = _TAKE.match(folder or "")
    if run is None or not match or int(match.group(1)) != segment or not (run / folder).is_dir():
        raise FilmError(f"clip {segment + 1} has no take {folder!r} in the reel {latent_path!r}.")
    return run, state, state.get("clips", [])


def _keep(run: Path, state: dict, clips: list, last: dict | None = None) -> None:
    settings = state.get("settings") or []
    last = state.get("last") or {} if last is None else last
    write_atomic(run / "clips.json", json.dumps({"settings": settings, "clips": clips, "last": last}, indent=2))
    _join(run, clips, int(settings[3]) if len(settings) > 3 else 48000)


def _entry(run: Path, folder: str, was: dict | None = None) -> dict:
    """A take as the film lists it: its folder, frames, the segment it continues and whether it is a test's."""
    meta, was = _meta(run / folder), was or {}
    return {"folder": folder, "frames": meta.get("frames", was.get("frames")), "continues": meta.get("continues", was.get("continues")),
            **({"test": True} if meta.get("test") or was.get("test") else {})}


def _parent(run: Path, folder: str) -> str | None:
    """The take a take came after in the film (#240): `follows`, or before it was kept, the take it continues."""
    meta = _meta(run / folder)
    return meta.get("follows") or meta.get("after")


def _onward(run: Path, last: dict, folder: str) -> list[str]:
    """The path last walked on from a take (#240): the take last made on it, the one last made on that, and so on."""
    out, at = [], folder
    while (child := last.get(at)) and (run / child).is_dir() and int(_TAKE.match(child).group(1)) == int(_TAKE.match(at).group(1)) + 1:
        out.append(child)
        at = child
    return out


def pick_take(output: Path | str, latent_path: str, segment: int, folder: str) -> dict:
    """Make a take of `segment` the active one (sample surfing, #206): the film is joined again with it. The takes
    after it that continued the one it replaces leave the film; when none stays, the film goes on along the path
    last walked from the take picked (#240), so a path comes back. Returns the take's seed and take number."""
    run, state, clips = _take(output, latent_path, segment, folder)
    if segment >= len(clips):
        raise FilmError(f"clip {segment + 1} is not in the reel {latent_path!r}'s film.")
    fitting = {t["folder"] for t in takes(output, latent_path).get(segment, [])}
    if folder not in fitting:
        raise FilmError(f"take {folder!r} was made on another take of clip {segment}: it would not continue it.")
    meta, last = _meta(run / folder), dict(state.get("last") or {})
    later = list(itertools.takewhile(lambda c: not _continues(clips, c, segment), range(segment + 1, len(clips))))
    onward = [] if later else [_entry(run, f) for f in _onward(run, last, folder)]
    clips = [*clips[:segment], _entry(run, folder, clips[segment]), *(clips[c] for c in later), *onward]
    if segment:
        last[clips[segment - 1]["folder"]] = folder  # walked: the way back along it
    _keep(run, state, clips, last)
    return {"folder": folder, "seed": meta.get("seed"), "take": meta.get("take") or 0}


def walk_to(output: Path | str, latent_path: str, folder: str) -> dict:
    """The film through any take of the tree (#240): the takes it came after, back to clip 1, then it, then on along
    the path last walked from it. Returns the take's seed and take number, and how many clips the film has now."""
    run, state = _active(_root(output, latent_path))
    if run is None or not _TAKE.match(folder or "") or not (run / folder).is_dir():
        raise FilmError(f"the reel {latent_path!r} has no take {folder!r}.")
    path = [folder]
    while (segment := int(_TAKE.match(path[0]).group(1))) > 0:
        parent = _parent(run, path[0])
        if not parent or not (run / parent).is_dir() or int(_TAKE.match(parent).group(1)) != segment - 1:
            raise FilmError(f"take {path[0]!r} does not say which take of clip {segment} it came after, so no path "
                            "leads to it from clip 1; pick it under its clip.")
        path.insert(0, parent)
    last = dict(state.get("last") or {})
    path += _onward(run, last, folder)
    last.update({path[i]: path[i + 1] for i in range(len(path) - 1)})
    clips = {c["folder"]: c for c in state.get("clips", [])}
    _keep(run, state, [_entry(run, f, clips.get(f)) for f in path], last)
    meta = _meta(run / folder)
    return {"folder": folder, "seed": meta.get("seed"), "take": meta.get("take") or 0, "clips": len(path)}


def end_film(output: Path | str, latent_path: str, segment: int) -> dict:
    """The film ends after clip `segment + 1` (#240); the clips after it stay where the tree remembers them."""
    run, state = _active(_root(output, latent_path))
    clips = state.get("clips", [])
    if run is None or not 0 <= segment < len(clips):
        raise FilmError(f"the reel {latent_path!r} has no clip {segment + 1} in its film.")
    _keep(run, state, clips[: segment + 1])
    return {"clips": segment + 1}


def tree(output: Path | str, latent_path: str) -> dict:
    """The run's takes as a tree (#240): every take with its clip, its parent, seed, take number, when it was made,
    the scene it plays and its template; the film's path; and the take last walked on from each."""
    run, state = _active(_root(output, latent_path))
    if run is None:
        return {"takes": [], "path": [], "last": {}}
    out = []
    for take in sorted(p for p in run.iterdir() if p.is_dir() and _TAKE.match(p.name)):
        meta = _meta(take)
        out.append({"folder": take.name, "segment": int(_TAKE.match(take.name).group(1)), "parent": _parent(run, take.name),
                    "seed": meta.get("seed"), "take": meta.get("take") or 0, "created": meta.get("created"),
                    "scene": meta.get("chunk"), "template": meta.get("template"), "frames": meta.get("frames"),
                    "continues": meta.get("continues"), "test": bool(meta.get("test")),
                    "_at": (take / "meta.json").stat().st_mtime_ns if (take / "meta.json").exists() else 0})
    out.sort(key=lambda t: (t["segment"], t["created"] or "", t.pop("_at")))
    return {"takes": out, "path": [c["folder"] for c in state.get("clips", [])], "last": state.get("last") or {}}


def delete_take(output: Path | str, latent_path: str, segment: int, folder: str) -> dict:
    """Delete a take of `segment` from disk (#214). The take in the film gives its place to the newest other take
    of the clip that fits; without one, the film ends before the clip. Returns the take in the film there now (as
    pick_take does), or folder None."""
    run, state, clips = _take(output, latent_path, segment, folder)
    got = {"folder": clips[segment]["folder"] if segment < len(clips) else None}
    if got["folder"] == folder:
        others = [t["folder"] for t in takes(output, latent_path).get(segment, []) if t["folder"] != folder]
        if others:
            got = pick_take(output, latent_path, segment, others[-1])
        else:
            got = {"folder": None}
            _keep(run, state, clips[:segment])
    shutil.rmtree(run / folder)
    return got


def delete_takes(output: Path | str, latent_path: str, segment: int, keep_film: bool = True) -> dict:
    """Delete the takes of `segment` its strip shows, the ones that fit the clip before (#234): every one but the
    take in the film (`keep_film`), or that one too, and the film then ends before the clip. Takes made on another
    take of the clip before stay: they belong to another path. Returns how many went and the take in the film."""
    run, state = _active(_root(output, latent_path))
    clips = state.get("clips", [])
    shown = [t["folder"] for t in takes(output, latent_path).get(segment, [])]
    if run is None or not shown:
        raise FilmError(f"clip {segment + 1} has no takes in the reel {latent_path!r}.")
    film = clips[segment]["folder"] if segment < len(clips) else None
    gone = [f for f in shown if not (keep_film and f == film)]
    if film in gone:
        _keep(run, state, clips[:segment])
    for folder in gone:
        shutil.rmtree(run / folder)
    return {"deleted": len(gone), "folder": film if film not in gone else None}


def film_file(take: Path) -> Path:
    """The film the take belongs to; the take itself while the film has only test takes."""
    film = take.parent / "film.mp4"
    return film if film.exists() else take / "video.mp4"


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
    """film.mp4: the takes' video stream-copied one after another, their sound joined and encoded once;
    test takes are left out (none left: no film)."""
    import av
    import numpy as np

    clips = [c for c in clips if not c.get("test")]
    if not clips:
        (run / "film.mp4").unlink(missing_ok=True)
        return

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
