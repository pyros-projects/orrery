"""One yardstick for every tool that chains H3 clips (orrery, ComfyUI-H3-Continuum, ComfyUI-H3-Motion-Context): how a
film's seams compare with the inside of its clips. Plain numpy, so the ComfyUI node and the command line share it.

Picture: the jump in mean luma and the mean pixel difference from a clip's last frame to the next one's first, and a
luma pulse: how far the 6 frames after a seam stray from the line between the frames before and after them (the
brief flash Continuum's assembly levels out). Sound: the step between the last sample of a clip and the first of the
next, and the change in level from the 20 ms before the seam to the 20 ms after it. Every seam value comes with its
percentile among the same quantity measured everywhere inside the clips: p99 is larger than 99% of them.
"""

from itertools import pairwise

import numpy as np

PULSE = 6  # frames after a seam a flash may last


def seams_from(spec: str, frames: int) -> list[int]:
    """The frame indices where a new clip starts. `spec`: `121,99` (the first clip 121 frames, then 99 each) or
    `@121,220,319` (the starts themselves)."""
    spec = spec.replace(" ", "")
    if spec.startswith("@"):
        starts = [int(v) for v in spec[1:].split(",") if v]
    else:
        first, *rest = [int(v) for v in spec.split(",") if v]
        each = rest[0] if rest else first
        starts, at = [], first
        while at < frames:
            starts.append(at)
            at += each
    return [s for s in starts if 0 < s < frames]


def _luma(images: np.ndarray) -> np.ndarray:
    """[N, H, W, 3] in 0..1 to [N, H, W] in 0..255 (Rec. 601)."""
    rgb = images[..., :3].astype(np.float32) * 255
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def _pulse(mean: np.ndarray, at: int) -> float:
    """How far the frames at at..at+PULSE-1 stray from the line between at-1 and at+PULSE."""
    if at < 1 or at + PULSE >= len(mean):
        return float("nan")
    line = np.linspace(mean[at - 1], mean[at + PULSE], PULSE + 2)[1:-1]
    return float(np.abs(mean[at:at + PULSE] - line).max())


def _level(mono: np.ndarray, at: int, w: int) -> float:
    def rms(x):
        return float(np.sqrt(np.mean(x ** 2)) + 1e-9)
    return abs(20 * np.log10(rms(mono[at:at + w]) / rms(mono[at - w:at])))


def measure(images: np.ndarray, starts: list[int], fps: float, sound: np.ndarray | None = None,
            rate: int | None = None) -> dict:
    """`images` [N, H, W, 3] in 0..1; `starts` the frames where a clip starts; `sound` [channels, samples] at `rate`.
    {"seams": [...per seam...], "inside": {quantity: {"median", "p99"}}, ...}."""
    luma = _luma(images)
    mean = luma.mean(axis=(1, 2))
    bounds = [0, *starts, len(images)]
    clips = list(pairwise(bounds))
    inside_frames = [i for a, b in clips for i in range(a + 1, b)]  # a frame and the one before it, same clip
    inside = {
        "luma jump": np.abs(mean[inside_frames] - mean[[i - 1 for i in inside_frames]]),
        "pixel MAE": np.array([np.abs(luma[i] - luma[i - 1]).mean() for i in inside_frames]),
        "luma pulse": np.array([p for a, b in clips for i in range(a + 1, b - PULSE) if not np.isnan(p := _pulse(mean, i))]),
    }
    seams = [{"frame": s, "second": round(s / fps, 3),
              "luma jump": float(abs(mean[s] - mean[s - 1])),
              "pixel MAE": float(np.abs(luma[s] - luma[s - 1]).mean()),
              "luma pulse": _pulse(mean, s)} for s in starts]
    if sound is not None and rate:
        mono = sound.mean(axis=0) if sound.ndim > 1 else sound
        cut = [round(s / fps * rate) for s in starts]
        w = int(0.02 * rate)
        edges = set(cut)
        steps = np.abs(np.diff(mono))
        keep = np.ones(len(steps), bool)
        keep[[c - 1 for c in cut if 0 < c <= len(steps)]] = False
        inside["sound step"] = steps[keep]
        inside["20ms level dB"] = np.array([_level(mono, i, w) for i in range(w, len(mono) - w, w)
                                            if not any(abs(i - e) < w for e in edges)])
        for seam, c in zip(seams, cut, strict=True):
            seam["sound step"] = float(abs(mono[c] - mono[c - 1])) if 0 < c < len(mono) else float("nan")
            seam["20ms level dB"] = _level(mono, c, w) if w <= c <= len(mono) - w else float("nan")
    out = {"frames": len(images), "fps": fps, "clips": len(clips), "seams": seams,
           "inside": {k: {"median": float(np.median(v)), "p99": float(np.percentile(v, 99))} for k, v in inside.items() if len(v)}}
    for seam in seams:
        seam["percentile"] = {k: round(float((inside[k] < seam[k]).mean() * 100), 1)
                              for k in inside if len(inside[k]) and not np.isnan(seam.get(k, np.nan))}
    return out


def report(result: dict, label: str = "") -> str:
    """The result as a few lines to read."""
    lines = [f"{label + ': ' if label else ''}{result['clips']} clips, {result['frames']} frames at {result['fps']} fps"]
    for k, v in result["inside"].items():
        at = ", ".join(f"{s[k]:.4g} (p{s['percentile'].get(k, float('nan')):.0f})" for s in result["seams"] if k in s)
        lines.append(f"  {k:14s} inside: median {v['median']:.4g}, p99 {v['p99']:.4g} | seams: {at}")
    worst = {k: max((s["percentile"].get(k, 0) for s in result["seams"]), default=0) for k in result["inside"]}
    lines.append("  worst seam percentile: " + ", ".join(f"{k} p{v:.0f}" for k, v in worst.items()))
    return "\n".join(lines)
