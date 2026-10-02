"""Which settings made which clip: reads the prompt ComfyUI's Save Video stores in every .mp4.

    python experiments/refmod-abc/configs.py "<ComfyUI output folder>/refmod_abc/*.mp4"

One line per clip, oldest first: the file, the segment and seed of its Orrery Prompt, its
`refmods:` line and the CAST lines that name a RefMod. So a round needs no notes on the side.
"""

import glob
import json
import os
import sys

import av


def config(path: str) -> dict:
    with av.open(path) as container:
        prompt = json.loads(dict(container.metadata).get("prompt") or "{}")
    inputs = next((n["inputs"] for n in prompt.values() if n.get("class_type") == "OrreryPrompt"), {})
    lines = inputs.get("template", "").splitlines()
    return {"file": os.path.basename(path), "segment": inputs.get("segment"), "seed": inputs.get("seed"),
            "refmods": next((line for line in lines if line.startswith("refmods:")), ""),
            "cast": [line.split(":", 1)[0] for line in lines if "(refmod " in line and not line.startswith("#")]}


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for path in sorted(glob.glob(sys.argv[1]), key=os.path.getmtime):
        c = config(path)
        print(f"{c['file']:28} segment {c['segment']}  seed {c['seed']}  {c['refmods'] or '-':28} {'; '.join(c['cast'])}")


if __name__ == "__main__":
    main()
