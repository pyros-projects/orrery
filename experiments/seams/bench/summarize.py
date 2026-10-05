"""The seam bench's films measured with one yardstick and summed up per tool (#360): every seam's percentile among the
steps inside its own film, over every seed run.

    uv run python experiments/seams/bench/summarize.py [--out experiments/seams/bench/results.md]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "seam_meter"))
from measure import decode
from meter import measure, seams_from

OUTPUT = Path("/home/pyro/repos/comfy-ui/output/seam_bench")
QUANTITIES = ("luma jump", "luma pulse", "pixel MAE", "sound step", "20ms level dB")


def films(seed_dir: Path) -> dict[str, tuple[Path, str]]:
    """Each tool's film in a seed's folder, with its seams: orrery and Motion Context 124 frames, then 102 new ones a
    clip; Continuum 124, then 119 (its chunks are 141 frames, 22 of them context)."""
    found = {}
    if (f := sorted(seed_dir.glob("orrery_film_*.mp4"))):
        found["orrery"] = (f[-1], "124,102")
    if (f := sorted(seed_dir.glob("orrery_onepass_*.mp4"))):
        found["orrery one decode"] = (f[-1], "124,102")
    for name in ("raw", "repaired"):
        if (f := sorted(seed_dir.glob(f"continuum_{name}_*.mp4"))):
            found[f"continuum {name}"] = (f[-1], "124,119")
    if (f := sorted(seed_dir.glob("mc/chain_video/run_*/merged.mp4"))):
        found["motion context"] = (f[-1], "124,102")
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    per_tool: dict[str, list[dict]] = {}
    for seed_dir in sorted(OUTPUT.glob("s*")):
        for tool, (path, spec) in films(seed_dir).items():
            frames, fps, sound, rate = decode(path)
            result = measure(frames, seams_from(spec, len(frames)), fps, sound, rate)
            for seam in result["seams"]:
                seam["seed"], seam["inside_p99"] = seed_dir.name, {k: v["p99"] for k, v in result["inside"].items()}
                per_tool.setdefault(tool, []).append(seam)
            print(f"measured {seed_dir.name} {tool}: {len(result['seams'])} seams", file=sys.stderr)
    lines = ["| Tool | Seams | " + " | ".join(QUANTITIES) + " |", "|---|---|" + "---|" * len(QUANTITIES)]
    for tool in ("orrery", "orrery one decode", "continuum raw", "continuum repaired", "motion context"):
        seams = per_tool.get(tool, [])
        if not seams:
            continue
        cells = []
        for q in QUANTITIES:
            pct = [s["percentile"][q] for s in seams if q in s.get("percentile", {})]
            ratio = [s[q] / s["inside_p99"][q] for s in seams if q in s and s["inside_p99"].get(q)]
            above = sum(p >= 99 for p in pct)
            cells.append(f"median p{np.median(pct):.0f}, {above}/{len(pct)} ≥ p99, {np.median(ratio):.2f}× p99")
        lines.append(f"| {tool} | {len(seams)} | " + " | ".join(cells) + " |")
    table = "\n".join(lines)
    print(table)
    if args.out:
        args.out.write_text(table + "\n\n" + json.dumps(per_tool, indent=1, default=float) + "\n")


if __name__ == "__main__":
    main()
