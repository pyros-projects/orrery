"""The seam meter (seam_meter/meter.py) from the command line: an Orrery Film run (its takes, the seams where they
join), or any film file with its seams given. See README.md.

    uv run python experiments/seams/measure.py <output>/<reel>/orrery_film/<run> [...]
    uv run python experiments/seams/measure.py film.mp4 --seams 121,99 [--label continuum]
"""

import argparse
import json
import sys
from pathlib import Path

import av
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "seam_meter"))
from meter import measure, report, seams_from


def decode(path: Path) -> tuple[np.ndarray, float, np.ndarray | None, int | None]:
    """Frames [N, H, W, 3] in 0..1, fps, sound [channels, samples], sample rate."""
    with av.open(str(path)) as c:
        stream = c.streams.video[0]
        fps = float(stream.average_rate)
        frames = np.stack([f.to_ndarray(format="rgb24") for f in c.decode(stream)]).astype(np.float32) / 255
    sound = rate = None
    with av.open(str(path)) as c:
        if c.streams.audio:
            parts = [f.to_ndarray() for f in c.decode(c.streams.audio[0])]
            rate = c.streams.audio[0].rate
            sound = np.concatenate([p if p.ndim > 1 else p[None] for p in parts], axis=1).astype(np.float32)
    return frames, fps, sound, rate


def run_film(run: Path) -> tuple[np.ndarray, list[int], float, np.ndarray, int]:
    """An Orrery Film run as one film: its takes' frames and sound end to end, the seams where they join."""
    state = json.loads((run / "clips.json").read_text())
    takes = [run / c["folder"] for c in state["clips"]]
    clips = [decode(t / "video.mp4")[0] for t in takes]
    sound = np.concatenate([np.load(t / "audio.npy") for t in takes], axis=1)
    starts = list(np.cumsum([len(c) for c in clips])[:-1])
    return np.concatenate(clips), [int(s) for s in starts], float(state["settings"][2]), sound, int(state["settings"][3])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--seams", help="for a film file: `121,99` (first clip, then each) or `@121,220` (clip starts)")
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    for path in args.paths:
        if path.is_dir():
            frames, starts, fps, sound, rate = run_film(path)
        else:
            frames, fps, sound, rate = decode(path)
            starts = seams_from(args.seams, len(frames))
        print(report(measure(frames, starts, fps, sound, rate), args.label or f"{path.parent.parent.name}/{path.name}"))
