"""Hand variant A's reel to B and C, so they continue from the same first clip.

    python experiments/refmod-abc/copy_segment0.py <ComfyUI output folder>

Copies output/abc_a/orrery_film to output/abc_b and output/abc_c. Orrery Film's store names its
takes relative to itself, so the copies work as they are; rendering segment 1 in B or C drops
whatever A rendered after segment 0.
"""

import shutil
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    output = Path(sys.argv[1])
    source = output / "abc_a" / "orrery_film"
    if not (source / "active.json").exists():
        sys.exit(f"{source} holds no reel yet: render segment 0 of abc_a.json first.")
    for variant in ("abc_b", "abc_c"):
        target = output / variant / "orrery_film"
        if target.exists():
            sys.exit(f"{target} exists already; delete it to start {variant} again.")
        shutil.copytree(source, target)
        print(f"{source} -> {target}")


if __name__ == "__main__":
    main()
