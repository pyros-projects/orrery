import json

import pytest

from orrery.cli import main


@pytest.fixture
def fake_llm(home):
    def configure(*replies):
        (home / "orrery.yaml").write_text(
            "models:\n  library:\n    backend: fake\n    name: FakeQwen\n    replies:\n"
            + "".join(f"      - {json.dumps(r)}\n" for r in replies))
    return configure


def test_lib_list_shows_user_and_builtin_libraries(home, capsys):
    assert main(["lib", "list"]) == 0
    out = capsys.readouterr().out
    assert "animal" in out and "camera" in out and "builtin" in out


def test_lib_show_prints_entries_with_learned_weights(home, capsys):
    (home / "weights.json").write_text('{"__animal__=owl": 1.5}')
    main(["lib", "show", "animal"])
    out = capsys.readouterr().out
    assert "owl" in out and "1.50" in out


def test_lib_gen_creates_a_library(home, fake_llm, capsys):
    fake_llm('["first snow", "ground fog"]')
    assert main(["lib", "gen", "weather", "--yes"]) == 0
    assert (home / "library" / "weather.yaml").exists()


def test_lib_edit_applies_after_confirmation(home, fake_llm, capsys):
    fake_llm('{"remove": ["owl"], "add": ["ibex"]}')
    assert main(["lib", "edit", "animal", "swap the owl", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "- owl" in out and "+ ibex" in out
    assert "owl" not in (home / "library" / "animal.yaml").read_text()


def test_lib_edit_declined_changes_nothing(home, fake_llm, monkeypatch, capsys):
    fake_llm('{"remove": ["owl"]}')
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    before = (home / "library" / "animal.yaml").read_text()
    assert main(["lib", "edit", "animal", "drop the owl"]) == 0
    assert (home / "library" / "animal.yaml").read_text() == before


def test_lib_more_adds_entries(home, fake_llm, capsys):
    fake_llm('["ibex", "axolotl"]')
    main(["lib", "more", "animal", "-n", "2", "--yes"])
    assert "axolotl" in (home / "library" / "animal.yaml").read_text()


def test_lib_undo_restores(home, fake_llm, capsys):
    fake_llm('{"remove": ["owl"]}')
    before = (home / "library" / "animal.yaml").read_text()
    main(["lib", "edit", "animal", "drop the owl", "--yes"])
    assert main(["lib", "undo"]) == 0
    assert (home / "library" / "animal.yaml").read_text() == before


def test_invalid_model_output_is_rejected_and_nothing_changes(home, fake_llm, capsys):
    fake_llm("sorry, I can't")
    before = (home / "library" / "animal.yaml").read_text()
    assert main(["lib", "edit", "animal", "anything", "--yes"]) == 3
    assert "no usable JSON" in capsys.readouterr().err
    assert (home / "library" / "animal.yaml").read_text() == before
