import pytest

from orrery.dsl import expand
from orrery.h3 import compile_scene
from orrery.home import Home
from orrery.presets import BUILTIN_PRESETS, load_preset, preset_meta
from orrery.reel import split_reel

MINIMUM = {"krea": 5, "h3": 5, "effects": 17, "fashion": 5, "loops": 5}
FOLDERS = tuple(MINIMUM)
SEEDS = range(30)
SHOWCASE = [f"{folder}/{p.stem}" for folder in FOLDERS
            for p in sorted((BUILTIN_PRESETS / folder).glob("*.orr"))]


@pytest.mark.parametrize("folder", FOLDERS)
def test_a_handful_ship_per_folder(folder):
    assert sum(name.startswith(folder + "/") for name in SHOWCASE) >= MINIMUM[folder]


@pytest.mark.parametrize("name", SHOWCASE)
def test_every_showcase_preset_has_title_note_and_folder_tag(home, name):
    meta = preset_meta(Home(home), name)
    assert meta["title"] and len(meta["note"]) > 40
    assert name.split("/")[0] in meta["tags"]


@pytest.mark.parametrize("name", SHOWCASE)
def test_every_showcase_preset_runs_clean_across_seeds(home, name):
    h = Home(home)
    text = load_preset(h, name)
    screenplay = text.lstrip().startswith("@h3")
    assert screenplay == (name.split("/")[0] in ("h3", "effects", "loops") or "h3" in preset_meta(h, name)["tags"])
    libs, weights = h.libraries(), h.weights()
    for seed in SEEDS:
        outs = []
        if screenplay:
            reel = split_reel(text)
            for segment in range(1 if not reel else (reel.segments or 6)):
                result = compile_scene(text, seed, libs, weights, segment=segment)
                assert result.lint == [], (seed, segment, result.lint)
                outs.append(result.text)
        else:
            outs.append(expand(text, seed, libs, weights).text)
        for out in outs:
            assert "__" not in out and "$" not in out and "{" not in out, (seed, out)


@pytest.mark.parametrize("name", [n for n in SHOWCASE if n.split("/")[0] == "effects"])
def test_body_horror_presets_write_subject_definitions(home, name):
    assert load_preset(Home(home), name).lstrip().splitlines()[0].split()[-1] == "lite"
