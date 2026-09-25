import json

import pytest

from orrery.cli import main
from orrery.dsl import expand
from orrery.h3 import compile_scene
from orrery.home import Home
from orrery.presets import (
    delete_preset,
    list_presets,
    load_preset,
    preset_meta,
    save_preset,
    tag_preset,
)

SEEDS = range(30)


def tutorial(home):
    return list_presets(Home(home), folder="tutorial")


def test_thirteen_tutorial_presets_ship_in_order(home):
    names = tutorial(home)
    assert len(names) == 13
    assert names == sorted(names)
    assert names[0] == "tutorial/01_first_wildcard"


@pytest.mark.parametrize("n", range(13))
def test_every_lesson_has_title_lesson_and_tag(home, n):
    meta = preset_meta(Home(home), tutorial(home)[n])
    assert meta["title"] and len(meta["lesson"]) > 40
    assert "tutorial" in meta["tags"]


@pytest.mark.parametrize("n", range(13))
def test_every_lesson_runs_clean_across_seeds(home, n):
    h = Home(home)
    text = load_preset(h, tutorial(home)[n])
    libs, weights = h.libraries(), h.weights()
    for seed in SEEDS:
        if text.lstrip().startswith("@h3"):
            result = compile_scene(text, seed, libs, weights)
            assert result.lint == [], (seed, result.lint)
            out = result.text
        else:
            out = expand(text, seed, libs, weights).text
        assert "__" not in out and "$" not in out and "{" not in out, (seed, out)


def test_builtin_presets_are_read_only(home):
    h = Home(home)
    with pytest.raises(ValueError, match="built-in"):
        delete_preset(h, "tutorial/01_first_wildcard")
    with pytest.raises(ValueError, match="built-in"):
        tag_preset(h, "tutorial/01_first_wildcard", add=["mine"])


def test_user_preset_shadows_builtin(home):
    h = Home(home)
    save_preset(h, "tutorial/01_first_wildcard", "my own version")
    assert load_preset(h, "tutorial/01_first_wildcard") == "my own version"
    assert list_presets(h, folder="tutorial").count("tutorial/01_first_wildcard") == 1


def test_expand_honours_the_params_line(home, capsys):
    main(["expand", "@tutorial/09_batch", "--json"])
    rows = json.loads(capsys.readouterr().out)
    assert [r["seed"] for r in rows] == list(range(100, 108))


def test_flags_override_the_params_line(home, capsys):
    main(["expand", "@tutorial/09_batch", "--seed", "5", "-n", "2", "--json"])
    assert [r["seed"] for r in json.loads(capsys.readouterr().out)] == [5, 6]


def test_preset_list_shows_titles(home, capsys):
    main(["preset", "list", "--folder", "tutorial"])
    out = capsys.readouterr().out
    assert "01 · Your first wildcard" in out and "(built-in)" in out
