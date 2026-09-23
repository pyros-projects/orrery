import pytest

from orrery.home import Home
from orrery.presets import (
    delete_preset,
    list_presets,
    load_preset,
    preset_meta,
    recall_template,
    remember_template,
    resolve_template,
    save_preset,
    tag_preset,
    template_hash,
)


def test_save_list_load_delete(home):
    h = Home(home)
    save_preset(h, "forest", "a __animal__ in a forest")
    assert list_presets(h) == ["forest"]
    assert load_preset(h, "forest") == "a __animal__ in a forest"
    delete_preset(h, "forest")
    assert list_presets(h) == []


def test_preset_names_are_sanitized(home):
    h = Home(home)
    assert save_preset(h, "Frozen Forest!", "x") == "frozen_forest"
    assert (home / "presets" / "frozen_forest.orr").exists()


def test_saving_over_an_existing_preset_needs_overwrite(home):
    h = Home(home)
    save_preset(h, "forest", "one")
    with pytest.raises(FileExistsError):
        save_preset(h, "forest", "two")
    save_preset(h, "forest", "two", overwrite=True)
    assert load_preset(h, "forest") == "two"


def test_missing_preset_names_the_fix(home):
    with pytest.raises(KeyError, match="orrery preset list"):
        load_preset(Home(home), "nope")


def test_templates_are_remembered_by_content_hash(home):
    h = Home(home)
    digest = remember_template(h, "a __animal__")
    assert digest == template_hash("a __animal__") and len(digest) == 16
    assert remember_template(h, "a __animal__") == digest
    assert len(list((home / "templates").iterdir())) == 1
    assert recall_template(h, digest) == "a __animal__"
    assert recall_template(h, "0" * 16) is None


def test_resolve_template_understands_presets_hashes_files_and_text(home, tmp_path):
    h = Home(home)
    save_preset(h, "forest", "preset text")
    digest = remember_template(h, "stored text")
    f = tmp_path / "scene.orr"
    f.write_text("file text")
    assert resolve_template(h, "@forest") == "preset text"
    assert resolve_template(h, "#" + digest) == "stored text"
    assert resolve_template(h, str(f)) == "file text"
    assert resolve_template(h, "plain __animal__") == "plain __animal__"


def test_unknown_hash_reference_fails_clearly(home):
    with pytest.raises(KeyError, match="no stored template"):
        resolve_template(Home(home), "#deadbeefdeadbeef")


def test_presets_can_live_in_folders(home):
    h = Home(home)
    assert save_preset(h, "H3/Winter/Forest", "x") == "h3/winter/forest"
    assert (home / "presets" / "h3" / "winter" / "forest.orr").exists()
    save_preset(h, "portrait", "y")
    assert list_presets(h) == ["h3/winter/forest", "portrait"]
    assert list_presets(h, folder="h3") == ["h3/winter/forest"]
    assert resolve_template(h, "@h3/winter/forest") == "x"


def test_folder_names_cannot_escape_the_presets_dir(home):
    with pytest.raises(ValueError):
        save_preset(Home(home), "../outside", "x")


def test_deleting_the_last_preset_removes_empty_folders(home):
    h = Home(home)
    save_preset(h, "h3/forest", "x")
    delete_preset(h, "h3/forest")
    assert not (home / "presets" / "h3").exists()


def test_tags_live_in_front_matter_and_never_reach_the_template(home):
    h = Home(home)
    save_preset(h, "forest", "a __animal__", tags=["winter", "moody"])
    assert (home / "presets" / "forest.orr").read_text().startswith("---\n")
    assert load_preset(h, "forest") == "a __animal__"
    assert preset_meta(h, "forest")["tags"] == ["moody", "winter"]


def test_list_filters_by_tag(home):
    h = Home(home)
    save_preset(h, "forest", "x", tags=["winter"])
    save_preset(h, "beach", "y", tags=["summer"])
    assert list_presets(h, tag="winter") == ["forest"]


def test_tags_can_be_added_and_removed_later(home):
    h = Home(home)
    save_preset(h, "forest", "x")
    assert tag_preset(h, "forest", add=["winter", "keeper"]) == ["keeper", "winter"]
    assert tag_preset(h, "forest", remove=["keeper"]) == ["winter"]
    assert load_preset(h, "forest") == "x"


def test_template_files_with_front_matter_are_stripped_when_resolved(home, tmp_path):
    f = tmp_path / "scene.orr"
    f.write_text("---\ntags: [x]\n---\na __animal__\n")
    assert resolve_template(Home(home), str(f)) == "a __animal__\n"
