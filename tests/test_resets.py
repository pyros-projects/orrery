"""The resets in the Settings (#310): each takes away what it says, what was made by hand into the trash."""

import json

import pytest

from orrery import history, resets, uistate, webapi
from orrery.galaxy import rate, read_rows, row_id
from orrery.home import Home
from orrery.presets import save_preset


def lived_in(home, tmp_path):
    """A home that was used (its two libraries come with it): a rated output with its file, a run, a preset of its own,
    a favorite, an export, a key."""
    picture = tmp_path / "out" / "fox.png"
    picture.parent.mkdir()
    picture.write_bytes(b"png")
    row = {"ts": "2026-10-04T10:00:00+00:00", "media": str(picture), "seed": 1, "target": "text", "template": "a" * 16,
           "text": "a fox", "rating": None, "picks": [{"label": "__animal__", "value": "fox", "keys": ["__animal__=fox"]}],
           "collections": ["best"]}
    (home / "galaxy.jsonl").write_text(json.dumps(row) + "\n")
    rate(Home(home), row_id(row), "love")
    history.record(Home(home), {"seed": 1, "target": "text", "text": "a fox"})
    save_preset(Home(home), "mine/fox", "a __animal__")
    uistate.set_favorite(Home(home), "mine/fox", True)
    (home / "export" / "set").mkdir(parents=True)
    (home / "export" / "set" / "a.txt").write_text("a fox\n")
    (home / ".env").write_text("ORRERY_API_KEY=secret\n")
    (home / "thumbs").mkdir(exist_ok=True)
    return picture


def trashed(home, kind):
    return sorted(p.name for p in (home / "trash").glob(f"{kind} *")) if (home / "trash").exists() else []


def test_resetting_the_ratings_takes_them_back_and_the_learned_weights(home, tmp_path):
    lived_in(home, tmp_path)
    assert Home(home).weights() == {"__animal__=fox": 1.5}
    assert resets.reset(Home(home), "ratings") == 1
    assert read_rows(Home(home))[0]["rating"] is None and Home(home).weights() == {}
    assert read_rows(Home(home))[0]["collections"] == ["best"]  # the rest of the gallery stays


def test_deleting_the_history(home, tmp_path):
    lived_in(home, tmp_path)
    assert resets.reset(Home(home), "history") == 1
    assert history.read(Home(home))["total"] == 0 and (home / "galaxy.jsonl").exists()


def test_deleting_the_gallery_keeps_its_files_unless_asked(home, tmp_path):
    picture = lived_in(home, tmp_path)
    assert resets.reset(Home(home), "gallery") == {"outputs": 1, "files": 0}
    assert read_rows(Home(home)) == [] and Home(home).weights() == {} and not (home / "thumbs").exists()
    assert picture.exists()
    (home / "galaxy.jsonl").write_text(json.dumps({"ts": "2026-10-04T11:00:00+00:00", "media": str(picture), "seed": 2}) + "\n")
    assert resets.reset(Home(home), "gallery", files=True) == {"outputs": 1, "files": 1}
    assert not picture.exists() and [p.name for p in (home / "trash").glob("gallery */fox.png")] == ["fox.png"]


def test_presets_and_libraries_go_back_to_factory_into_the_trash(home, tmp_path):
    lived_in(home, tmp_path)
    assert resets.reset(Home(home), "presets") == 1
    assert not (home / "presets").exists() and len(trashed(home, "presets")) == 1
    assert uistate.load_ui(Home(home))["favorites"] == []
    assert resets.reset(Home(home), "libraries") == 2
    assert not (home / "library").exists() and len(trashed(home, "libraries")) == 1
    assert "heron" in (next((home / "trash").glob("libraries */library")) / "animal.yaml").read_text()


def test_everything_at_once_leaves_only_the_trash(home, tmp_path):
    picture = lived_in(home, tmp_path)
    done = resets.reset(Home(home), "all", files=True)
    assert done == {"gallery": {"outputs": 1, "files": 1}, "history": 1, "presets": 1, "libraries": 2}
    assert [p.name for p in home.iterdir()] == ["trash"] and not picture.exists()
    kept = {p.name.split(" ")[0] for p in (home / "trash").iterdir()}
    assert kept == {"gallery", "presets", "libraries", "exports"}  # what was made by hand, and the files asked for


def test_the_reset_route_checks_what_it_is_asked(home, tmp_path):
    lived_in(home, tmp_path)
    assert webapi.reset(Home(home), {"what": "history"}) == {"what": "history", "done": 1}
    with pytest.raises(webapi.ApiError):
        webapi.reset(Home(home), {"what": "universe"})
