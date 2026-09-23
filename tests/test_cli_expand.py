import json

from orrery.cli import main


def test_expand_prints_text_and_picks(home, capsys):
    assert main(["expand", "a __animal__", "--seed", "5", "-n", "2"]) == 0
    out = capsys.readouterr().out
    assert "[5]" in out and "[6]" in out
    assert "__animal__:" in out


def test_expand_json_is_machine_readable(home, capsys):
    main(["expand", "a __animal__ in __style__", "--seed", "3", "--json"])
    [row] = json.loads(capsys.readouterr().out)
    assert row["seed"] == 3
    assert row["text"].startswith("a ")
    assert set(row["picks"]) == {"__animal__", "__style__"}


def test_expand_reads_a_template_file(home, tmp_path, capsys):
    f = tmp_path / "t.txt"
    f.write_text("a __animal__")
    main(["expand", str(f), "--seed", "1", "--json"])
    assert json.loads(capsys.readouterr().out)[0]["text"].startswith("a ")


def test_missing_library_exits_with_hint(home, capsys):
    assert main(["expand", "a __weather__ day"]) == 2
    assert "orrery lib gen weather" in capsys.readouterr().err


def test_learned_weights_from_home_are_applied(home, capsys):
    (home / "weights.json").write_text(json.dumps({"__animal__=owl": 50.0}))
    main(["expand", "__animal__", "-n", "40", "--json"])
    rows = json.loads(capsys.readouterr().out)
    assert sum(r["text"] == "owl" for r in rows) > 30
