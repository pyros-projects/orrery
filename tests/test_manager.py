import json

import pytest

from orrery.home import Home
from orrery.library import load_library
from orrery.llm import FakeBackend, InvalidProposal
from orrery.manager import (
    Ops,
    apply_ops,
    diff_text,
    edit_prompt,
    generate,
    parse_list,
    parse_ops,
    propose_edit,
    propose_more,
    undo,
)


@pytest.fixture
def lib_home(home):
    (home / "library" / "animal.yaml").write_text("- fox\n- lynx\n- tabby cat\n- heron\n")
    Home(home).save_weights({"__animal__=lynx": 1.6, "__animal__=fox": 0.4})
    return Home(home)


def test_parse_list_cleans_and_dedupes():
    assert parse_list('["fog", " fog ", "", 3, "sleet"]') == ["fog", "sleet"]


def test_parse_list_rejects_empty_results():
    with pytest.raises(InvalidProposal):
        parse_list("[]")


def test_parse_ops_matches_entries_case_insensitively(lib_home):
    lib = lib_home.libraries()["animal"]
    ops = parse_ops('{"remove": ["Lynx"], "add": ["ibex"], "rename": [], "new_lists": []}', lib)
    assert ops.remove == ["lynx"] and ops.add == ["ibex"]


def test_parse_ops_rejects_unknown_entries(lib_home):
    lib = lib_home.libraries()["animal"]
    with pytest.raises(InvalidProposal, match="wolf"):
        parse_ops('{"remove": ["wolf"]}', lib)


def test_parse_ops_rejects_broken_json(lib_home):
    with pytest.raises(InvalidProposal):
        parse_ops("remove the cats please", lib_home.libraries()["animal"])


def test_parse_ops_sanitizes_new_list_names(lib_home):
    lib = lib_home.libraries()["animal"]
    ops = parse_ops('{"remove": ["lynx"], "new_lists": [{"name": "Big Cats!", "entries": ["lynx"]}]}', lib)
    assert ops.new_lists == [("big_cats", ["lynx"])]


def test_diff_text_shows_every_kind_of_change():
    ops = Ops(remove=["lynx"], add=["ibex"], rename=[("fox", "arctic fox")],
              new_lists=[("feline", ["lynx"])], note="moved cats")
    text = diff_text("animal", ops)
    for line in ("- lynx", "+ ibex", "~ fox → arctic fox", "new list __feline__: lynx", "moved cats"):
        assert line in text


def test_apply_moves_entries_and_their_weights(lib_home):
    ops = Ops(remove=["lynx", "tabby cat"], add=["ibex"], rename=[("fox", "arctic fox")],
              new_lists=[("feline", ["lynx", "tabby cat"])])
    apply_ops(lib_home, "animal", ops, by="test")
    assert load_library(lib_home.library_dir / "animal.yaml").values() == ["arctic fox", "heron", "ibex"]
    assert load_library(lib_home.library_dir / "feline.yaml").values() == ["lynx", "tabby cat"]
    w = lib_home.weights()
    assert w == {"__animal__=arctic fox": 0.4, "__feline__=lynx": 1.6}


def test_undo_restores_libraries_and_weights(lib_home):
    before = (lib_home.library_dir / "animal.yaml").read_text()
    apply_ops(lib_home, "animal", Ops(remove=["lynx"], new_lists=[("feline", ["lynx"])]), by="t")
    assert undo(lib_home)
    assert (lib_home.library_dir / "animal.yaml").read_text() == before
    assert not (lib_home.library_dir / "feline.yaml").exists()
    assert lib_home.weights() == {"__animal__=lynx": 1.6, "__animal__=fox": 0.4}


def test_undo_without_history_returns_false(lib_home):
    assert undo(lib_home) is False


def test_generate_creates_a_marked_library_and_is_undoable(lib_home):
    backend = FakeBackend(['["first snow", "ground fog"]'])
    generate(lib_home, "weather", backend, model_name="Qwen3.5-2B", template="a __weather__ day")
    lib = load_library(lib_home.library_dir / "weather.yaml")
    assert lib.values() == ["first snow", "ground fog"]
    assert lib.meta["generated_by"] == "Qwen3.5-2B"
    assert "a __weather__ day" in backend.prompts[0]
    undo(lib_home)
    assert not (lib_home.library_dir / "weather.yaml").exists()


def test_generate_refuses_to_overwrite(lib_home):
    with pytest.raises(FileExistsError):
        generate(lib_home, "animal", FakeBackend(['["x"]']), model_name="m")


def test_propose_more_only_adds_new_entries(lib_home):
    ops = propose_more(lib_home, "animal", FakeBackend(['["fox", "ibex", "axolotl"]']), n=8)
    assert ops.add == ["ibex", "axolotl"] and not ops.remove


def test_propose_edit_sends_entries_and_instruction(lib_home):
    backend = FakeBackend([json.dumps({"remove": ["lynx"], "add": [], "rename": [],
                                       "new_lists": [{"name": "feline", "entries": ["lynx"]}]})])
    ops = propose_edit(lib_home, "animal", "Lösch alle Katzen", backend)
    assert ops.new_lists == [("feline", ["lynx"])]
    assert "Lösch alle Katzen" in backend.prompts[0] and "tabby cat" in backend.prompts[0]


def test_edit_prompt_describes_the_operation_schema(lib_home):
    prompt = edit_prompt(lib_home.libraries()["animal"], ["style"], "make it specific")
    for word in ("remove", "add", "rename", "note", "JSON"):
        assert word in prompt


def test_parse_ops_reads_per_entry_decisions(lib_home):
    lib = lib_home.libraries()["animal"]
    reply = json.dumps({"decisions": [
        {"entry": "fox", "action": "rename", "to": "arctic fox"},
        {"entry": "lynx", "action": "move", "to": "feline"},
        {"entry": "tabby cat", "action": "move", "to": "feline"},
        {"entry": "heron", "action": "keep"},
    ], "add": ["ibex"], "note": "moved the cats"})
    ops = parse_ops(reply, lib)
    assert ops.rename == [("fox", "arctic fox")]
    assert ops.remove == ["lynx", "tabby cat"]
    assert ops.new_lists == [("feline", ["lynx", "tabby cat"])]
    assert ops.add == ["ibex"] and ops.note == "moved the cats"


def test_per_entry_decision_on_unknown_entry_is_rejected(lib_home):
    lib = lib_home.libraries()["animal"]
    with pytest.raises(InvalidProposal, match="wolf"):
        parse_ops('{"decisions": [{"entry": "wolf", "action": "remove"}]}', lib)


def test_edit_prompt_asks_for_a_decision_per_entry(lib_home):
    prompt = edit_prompt(lib_home.libraries()["animal"], [], "move the cats")
    for word in ("decisions", "every entry", "keep", "remove", "move", "rename", "add"):
        assert word in prompt


def test_edit_prompt_asks_for_a_criterion_before_the_decisions(lib_home):
    prompt = edit_prompt(lib_home.libraries()["animal"], [], "move the cats")
    assert "criterion" in prompt
    assert prompt.index('"criterion"') < prompt.index('"decisions"')


def test_criterion_is_parsed_and_shown_in_the_diff(lib_home):
    lib = lib_home.libraries()["animal"]
    ops = parse_ops('{"criterion": "members of the cat family", '
                    '"decisions": [{"entry": "lynx", "action": "remove"}]}', lib)
    assert ops.criterion == "members of the cat family"
    assert "understood as: members of the cat family" in diff_text("animal", ops)


def test_renaming_a_library_carries_its_weights_references_and_presets(home):
    from orrery.manager import rename_library, undo
    h = Home(home)
    (h.library_dir / "film_moods.yaml").write_text("- a hush\n- a storm\n")
    (h.library_dir / "scene.txt").write_text("{a|b} __film_moods__ over __film_moods#tone:dark__\n")
    (h.presets_dir / "mine").mkdir(parents=True)
    (h.presets_dir / "mine" / "rainy.orr").write_text("a street in __film_moods__\n")
    h.save_weights({"__film_moods__=a hush": 1.5, "__other__=x": 0.8})
    summary = rename_library(h, "film_moods", "film/moods")
    assert (h.library_dir / "film" / "moods.yaml").exists() and not (h.library_dir / "film_moods.yaml").exists()
    assert (h.library_dir / "scene.txt").read_text() == "{a|b} __film/moods__ over __film/moods#tone:dark__\n"
    assert (h.presets_dir / "mine" / "rainy.orr").read_text() == "a street in __film/moods__\n"
    assert h.weights() == {"__film/moods__=a hush": 1.5, "__other__=x": 0.8}
    assert summary == {"weights": 1, "libraries": ["scene"], "presets": ["mine/rainy"]}
    undo(h)
    assert (h.library_dir / "film_moods.yaml").exists() and not (h.library_dir / "film" / "moods.yaml").exists()
    assert "__film_moods__" in (h.library_dir / "scene.txt").read_text()


def test_a_rename_refuses_builtins_and_taken_names(home):
    from orrery.manager import rename_library
    h = Home(home)
    (h.library_dir / "mine.yaml").write_text("- x\n")
    with pytest.raises(ValueError, match="built-in"):
        rename_library(h, "camera", "cam")
    with pytest.raises(ValueError, match="exists"):
        rename_library(h, "mine", "camera")
