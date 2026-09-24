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
    assert main(["expand", "a __smell__ day"]) == 2
    assert "orrery lib gen smell" in capsys.readouterr().err


def test_learned_weights_from_home_are_applied(home, capsys):
    (home / "weights.json").write_text(json.dumps({"__animal__=owl": 50.0}))
    main(["expand", "__animal__", "-n", "40", "--json"])
    rows = json.loads(capsys.readouterr().out)
    assert sum(r["text"] == "owl" for r in rows) > 30


def test_expand_accepts_preset_references(home, capsys):
    main(["preset", "save", "zoo", "a __animal__ at the zoo"])
    capsys.readouterr()
    main(["expand", "@zoo", "--json"])
    assert json.loads(capsys.readouterr().out)[0]["text"].endswith(" at the zoo")


def test_preset_cli_list_show_rm(home, capsys):
    main(["preset", "save", "zoo", "a __animal__ at the zoo"])
    main(["preset", "list"])
    main(["preset", "show", "zoo"])
    out = capsys.readouterr().out
    assert "zoo" in out and "a __animal__ at the zoo" in out
    assert main(["preset", "rm", "zoo"]) == 0
    assert main(["preset", "show", "zoo"]) == 2


def test_preset_cli_folders_and_tags(home, capsys):
    main(["preset", "save", "h3/forest", "a __animal__", "--tags", "winter,moody"])
    main(["preset", "save", "beach", "a __animal__ on sand"])
    main(["preset", "tag", "beach", "summer"])
    capsys.readouterr()
    main(["preset", "list", "--tag", "winter"])
    out = capsys.readouterr().out
    assert "@h3/forest" in out and "moody" in out and "beach" not in out
    main(["preset", "list", "--folder", "h3"])
    assert "@h3/forest" in capsys.readouterr().out


def test_set_overrides_a_binding(home, capsys):
    assert main(["expand", "$hero = __animal__\n$hero at dawn", "--set", "hero=a lighthouse keeper"]) == 0
    assert "a lighthouse keeper at dawn" in capsys.readouterr().out


def test_set_names_an_unknown_binding_and_the_known_ones(home, capsys):
    assert main(["expand", "$hero = __animal__\n$hero", "--set", "villain=x"]) == 2
    err = capsys.readouterr().err
    assert "$villain" in err and "$hero" in err
