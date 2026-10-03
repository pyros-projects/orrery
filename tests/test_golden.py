"""The golden corpus (#20): what every preset that ships rolls, pinned.

Each built-in preset is rolled at a few seeds, as Generate rolls it: its text and its picks; for a
reel the clips it plays (up to CLIPS), each with its scene, text and picks; for a grid its first CELLS
cells. The snapshots live in tests/golden/<folder>/<name>.json, and a difference fails, naming the
preset, the seed, the take and what changed. Determinism is a promise: a change that moves them
needs a reason in the PR (AGENTS.md). Then rewrite them:

    uv run python tests/test_golden.py --write

Only orrery's own libraries take part (an empty home, no learned weights). A library a language model
would write is stubbed (`name 0`, `name 1` …), and `--…--` slots and `>` lines stay as written, so no
model is needed.
"""

import difflib
import json
import sys
import tempfile
from pathlib import Path

import pytest

from orrery.batch import axes, cells
from orrery.dsl import expand, parse, strip_comments, wanted_libraries, with_inline
from orrery.h3 import compile_scene
from orrery.home import Home
from orrery.presets import BUILTIN_PRESETS, load_preset, resolve_includes
from orrery.reel import reel_path, split_reel

GOLDEN = Path(__file__).parent / "golden"
SEEDS = (0, 1, 7)
WALK_SEEDS = (0, 1, 2, 3, 4, 5, 6, 7)  # a reel whose path hangs on its rolls walks more seeds
CLIPS = 6
CELLS = 6
PRESETS = sorted(p.relative_to(BUILTIN_PRESETS).with_suffix("").as_posix()
                 for p in BUILTIN_PRESETS.rglob("*.orr"))


def take(result, **where) -> dict:
    return {**where, "text": result.text, "picks": [[p.label, p.value] for p in result.picks]}


def snapshot(home: Home, name: str) -> dict:
    """What `name` rolls at each seed, as the node would: every take with its text and picks."""
    source = resolve_includes(home, load_preset(home, name))
    for lib, least in wanted_libraries(source).items():  # the lists a language model would write
        if lib not in home.libraries():
            path = home.library_dir / f"{lib}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(f"{lib} {i}" for i in range(max(least, 3))) + "\n", encoding="utf-8")
    libs, weights = home.libraries(), home.weights()
    screenplay = strip_comments(source).lstrip().startswith("@h3")
    grid = (cells(axes(*with_inline(strip_comments(source), libs)))
            if parse(source).params.grid is not None else 0)
    runs = list(range(min(grid, CELLS))) if grid else [None]
    reel = split_reel(source) if screenplay else None
    seeds = WALK_SEEDS if reel and reel.jumps_on_rolls else SEEDS
    out = {}
    for seed in seeds:
        rolled: dict = {}
        clips = [None]
        if reel:
            walked, merged = with_inline(strip_comments(source), libs)
            path, ended = reel_path(split_reel(walked), seed, merged, weights, upto=CLIPS)
            rolled["path"], rolled["ended"] = [reel.label(k, path) for k in range(len(path))], ended
            clips = list(range(len(path)))
        takes = []
        for cell in runs:
            for clip in clips:
                where = {k: v for k, v in (("cell", cell), ("clip", clip)) if v is not None}
                if screenplay:
                    takes.append(take(compile_scene(source, seed, libs, weights, segment=clip or 0, cell=cell),
                                      **where))
                else:
                    takes.append(take(expand(source, seed, libs, weights, cell=cell), **where))
        out[str(seed)] = {**rolled, "takes": takes}
    return {"preset": name, "seeds": out}


def golden_file(name: str) -> Path:
    return GOLDEN / f"{name}.json"


def words(was: str, now: str, context: int = 6, most: int = 5) -> list[str]:
    """The changed words, each with a few words around it: H3 puts a whole shot on one line."""
    a, b = was.split(" "), now.split(" ")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        before = " ".join(a[max(i1 - context, 0):i1])
        out.append(f"  … {before} [{' '.join(a[i1:i2])} → {' '.join(b[j1:j2])}] {' '.join(a[i2:i2 + context])} …")
        if len(out) == most:
            out.append("  (and more)")
            break
    return out


def differences(name: str, want: dict, got: dict) -> list[str]:
    """What moved, in words: the first difference per seed, with a short diff of a text."""
    said = []
    for seed in sorted(set(want["seeds"]) | set(got["seeds"]), key=int):
        a, b = want["seeds"].get(seed), got["seeds"].get(seed)
        if a == b:
            continue
        if a is None or b is None:
            said.append(f"{name}, seed {seed}: {'new' if a is None else 'gone'}")
            continue
        if a.get("path") != b.get("path"):
            said.append(f"{name}, seed {seed}: the path moved\n  was {a.get('path')}\n  now {b.get('path')}")
            continue
        for x, y in zip(a["takes"], b["takes"], strict=False):
            if x == y:
                continue
            at = ", ".join(f"{k} {v + 1}" for k, v in x.items() if k in ("cell", "clip"))
            where = f"{name}, seed {seed}" + (f", {at}" if at else "")
            if x["picks"] != y["picks"]:
                moved = [f"{p} = {v!r}" for p, v in y["picks"] if [p, v] not in x["picks"]][:5]
                said.append(f"{where}: picks moved: {'; '.join(moved) or 'fewer picks'}")
            if x["text"] != y["text"]:
                said.append(f"{where}: the text changed\n" + "\n".join(words(x["text"], y["text"])))
            break
        else:
            said.append(f"{name}, seed {seed}: {len(a['takes'])} takes, now {len(b['takes'])}")
    return said


@pytest.fixture(scope="module")
def bare_home(tmp_path_factory):
    return Home(tmp_path_factory.mktemp("golden-home"))


@pytest.mark.parametrize("name", PRESETS)
def test_the_preset_rolls_what_it_rolled(bare_home, name):
    path = golden_file(name)
    assert path.exists(), f"{name} has no snapshot: uv run python tests/test_golden.py --write"
    want, got = json.loads(path.read_text(encoding="utf-8")), snapshot(bare_home, name)
    said = differences(name, want, got)
    assert not said, "\n".join(said) + "\n\nIntended? Say why in the PR and run: " \
                                       "uv run python tests/test_golden.py --write"


def test_every_snapshot_has_its_preset():
    stale = sorted(p.relative_to(GOLDEN).with_suffix("").as_posix() for p in GOLDEN.rglob("*.json")
                   if p.relative_to(GOLDEN).with_suffix("").as_posix() not in PRESETS)
    assert not stale, f"snapshots without a preset (remove them): {stale}"


def write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Home(Path(tmp))
        for path in GOLDEN.rglob("*.json"):
            path.unlink()
        for name in PRESETS:
            path = golden_file(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(snapshot(home, name), ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        print(f"{len(PRESETS)} snapshots in {GOLDEN}")


if __name__ == "__main__":
    if sys.argv[1:] != ["--write"]:
        sys.exit(__doc__)
    write()
