import pytest

from orrery.dsl import expand
from orrery.h3 import compile_scene
from orrery.home import Home
from orrery.presets import BUILTIN_PRESETS, load_preset, preset_meta

FOLDERS = ("krea", "h3")
SEEDS = range(30)
SHOWCASE = [f"{folder}/{p.stem}" for folder in FOLDERS
            for p in sorted((BUILTIN_PRESETS / folder).glob("*.orr"))]


@pytest.mark.parametrize("folder", FOLDERS)
def test_a_handful_ship_per_folder(folder):
    assert sum(name.startswith(folder + "/") for name in SHOWCASE) >= 5


@pytest.mark.parametrize("name", SHOWCASE)
def test_every_showcase_preset_has_title_note_and_folder_tag(home, name):
    meta = preset_meta(Home(home), name)
    assert meta["title"] and len(meta["note"]) > 40
    assert name.split("/")[0] in meta["tags"]


@pytest.mark.parametrize("name", SHOWCASE)
def test_every_showcase_preset_runs_clean_across_seeds(home, name):
    h = Home(home)
    text = load_preset(h, name)
    assert text.lstrip().startswith("@h3") == name.startswith("h3/")
    libs, weights = h.libraries(), h.weights()
    for seed in SEEDS:
        if name.startswith("h3/"):
            result = compile_scene(text, seed, libs, weights)
            assert result.lint == [], (seed, result.lint)
            out = result.text
        else:
            out = expand(text, seed, libs, weights).text
        assert "__" not in out and "$" not in out and "{" not in out, (seed, out)
