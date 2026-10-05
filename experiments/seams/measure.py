"""How a film's seams compare with the inside of its clips: the picture (mean luma jump, pixel MAE between the last
frame of a clip and the first of the next) and the sound (sample step, 20 ms level change across the join). Reads the
takes as Orrery Film stores them: video.mp4 (pinned frames trimmed) and audio.npy. See README.md.

    uv run python experiments/seams/measure.py <output>/<reel>/orrery_film/<run> [...]
"""

import json
import sys
from itertools import pairwise
from pathlib import Path

import av
import numpy as np


def frames(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as c:
        return [f.to_ndarray(format="gray").astype(np.float32) for f in c.decode(c.streams.video[0])]


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)) + 1e-9)


def report(run: Path) -> None:
    state = json.loads((run / "clips.json").read_text())
    takes = [run / c["folder"] for c in state["clips"]]
    rate = int(state["settings"][3])  # [width, height, fps, sample rate, channels]
    vids = [frames(t / "video.mp4") for t in takes]
    mono = [np.load(t / "audio.npy").mean(axis=0) for t in takes]
    w = int(0.02 * rate)
    inside = {
        "luma jump": np.concatenate([np.abs(np.diff([f.mean() for f in v])) for v in vids]),
        "pixel MAE": np.concatenate([[np.abs(a - b).mean() for a, b in pairwise(v)] for v in vids]),
        "sound step": np.concatenate([np.abs(np.diff(m)) for m in mono]),
        "20ms level dB": np.concatenate([[abs(20 * np.log10(rms(m[i + w:i + 2 * w]) / rms(m[i:i + w])))
                                          for i in range(0, len(m) - 2 * w, w)] for m in mono]),
    }
    seams = {
        "luma jump": [abs(b[0].mean() - a[-1].mean()) for a, b in pairwise(vids)],
        "pixel MAE": [np.abs(b[0] - a[-1]).mean() for a, b in pairwise(vids)],
        "sound step": [abs(b[0] - a[-1]) for a, b in pairwise(mono)],
        "20ms level dB": [abs(20 * np.log10(rms(b[:w]) / rms(a[-w:]))) for a, b in pairwise(mono)],
    }
    print(f"{run.parent.parent.name}/{run.name}: {len(takes)} clips")
    for name, values in inside.items():
        shown = ", ".join(f"{s:.4f} (p{(values < s).mean() * 100:.0f})" for s in seams[name])
        print(f"  {name:14s} inside: median {np.median(values):.4f}  p99 {np.percentile(values, 99):.4f} | seams: {shown}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        report(Path(arg))
