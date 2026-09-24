import json

from orrery.cli import main

SCENE = "@h3 t2va\nSHOT 5s | push in, small, slow\nA __animal__ sleeps.\nSFX: wind\n"


def write(tmp_path, text):
    p = tmp_path / "scene.orr"
    p.write_text(text)
    return str(p)


def test_compile_prints_the_h3_prompt(home, tmp_path, capsys):
    assert main(["compile", write(tmp_path, SCENE), "--seed", "7"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("integrated_multimodal_description: [Shot 1] ")
    assert "overall_soundscape: Wind." in out


def test_compile_flat_target(home, tmp_path, capsys):
    main(["compile", write(tmp_path, SCENE), "--target", "flat"])
    assert capsys.readouterr().out.strip().endswith("sleeps.")


def test_compile_json_has_text_picks_and_lint(home, tmp_path, capsys):
    main(["compile", write(tmp_path, SCENE), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"text", "picks", "lint", "seed", "loras"}
    assert "__animal__" in data["picks"]


def test_lint_errors_go_to_stderr_and_fail(home, tmp_path, capsys):
    code = main(["compile", write(tmp_path, "@h3 t2va\nstyle: live-action\n")])
    err = capsys.readouterr().err
    assert code == 1
    assert "error:" in err and "SHOT" in err


def test_lint_warnings_do_not_fail(home, tmp_path, capsys):
    assert main(["compile", write(tmp_path, "@h3 t2va\nSHOT 2s\nA.\n")]) == 0
    assert "4–15" in capsys.readouterr().err


def test_compile_missing_library_exits_2(home, tmp_path, capsys):
    assert main(["compile", write(tmp_path, "@h3 t2va\nSHOT 5s\nA __smell__.\nSFX: x\n")]) == 2


def test_compile_set_overrides_a_binding(home, capsys):
    scene = "@h3 t2va\n$hero = __animal__\nSHOT 5s\nA $hero sleeps.\nSFX: wind\n"
    assert main(["compile", scene, "--set", "$hero=lynx"]) == 0
    assert "A lynx sleeps." in capsys.readouterr().out


REEL = "@h3 t2va\nLORA: <lora:a:1>\nCHUNK\nSHOT 5s\nA fox.\nSFX: x\nCHUNK\nSHOT 4s\nA heron.\nSFX: y\n"


def test_compile_prints_every_chunk_of_a_reel(home, capsys):
    assert main(["compile", REEL]) == 0
    out = capsys.readouterr().out
    assert "# CHUNK 1/2 · 5.00 s · 124 frames · <lora:a:1>" in out
    assert "# CHUNK 2/2 · 4.92 s · 124 frames · <lora:a:1>" in out
    assert out.index("A fox.") < out.index("A heron.")


def test_compile_segment_prints_one_chunk(home, capsys):
    assert main(["compile", REEL, "--segment", "1"]) == 0
    out = capsys.readouterr().out
    assert "A heron." in out and "A fox." not in out and "# CHUNK" not in out
