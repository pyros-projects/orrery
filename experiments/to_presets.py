"""Copy every experiment template into the orrery home's presets, tagged `experiments`.

    uv run python experiments/to_presets.py [--home ~/.orrery]

experiments/refmod-abc/branch_cases.orr becomes the preset @experiments/refmod_abc/branch_cases, so the
node's preset list has it and nobody copies prompts around. Its title is the file's name ("Branch
cases"), so the card says which one it is; its leading comment lines are the note. The repo keeps the original (results and their templates belong in the repo); the
preset is a copy. A preset whose text was changed in the node since the last copy is left as it is and
named, so an edit there is not lost.
"""

import argparse
import sys
from pathlib import Path

import yaml

from orrery.cli import resolve_home
from orrery.presets import preset_name, split_front_matter, template_hash

HERE = Path(__file__).parent
TAG = "experiments"


def front(source: Path, text: str) -> dict:
    lines = []
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        lines.append(line.lstrip("#").strip())
    return {"title": source.stem.replace("_", " ").capitalize(), "note": " ".join(lines), "tags": [TAG]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--home", default=None)
    home = resolve_home(parser.parse_args().home)
    kept = []
    for source in sorted(HERE.rglob("*.orr")):
        name = preset_name(f"{TAG}/{source.relative_to(HERE).with_suffix('').as_posix()}")
        target = home.presets_dir / f"{name}.orr"
        text = source.read_text(encoding="utf-8")
        if target.exists():
            meta, body = split_front_matter(target.read_text(encoding="utf-8"))
            if body != text and meta.get("copied") != template_hash(body):
                kept.append(name)
                continue
        meta = {**front(source, text), "copied": template_hash(text)}  # what was copied, to see an edit in the node
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)}---\n{text}", encoding="utf-8")
        print(f"@{name}")
    for name in kept:
        print(f"@{name}: changed in the node since the last copy, left as it is", file=sys.stderr)


if __name__ == "__main__":
    main()
