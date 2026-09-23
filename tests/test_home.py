from pathlib import Path

from orrery.home import Home, resolve_home


def test_explicit_path_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("ORRERY_HOME", "/somewhere/else")
    assert resolve_home(tmp_path).root == tmp_path


def test_env_var_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("ORRERY_HOME", str(tmp_path))
    assert resolve_home().root == tmp_path


def test_default_is_dot_orrery_in_user_home(tmp_path, monkeypatch):
    monkeypatch.delenv("ORRERY_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert resolve_home().root == Path(tmp_path) / ".orrery"


def test_libraries_load_from_library_dir(home):
    assert {"animal", "style"} <= set(Home(home).libraries())


def test_weights_are_empty_until_saved(home):
    h = Home(home)
    assert h.weights() == {}
    h.save_weights({"__animal__=fox": 1.6})
    assert Home(home).weights() == {"__animal__=fox": 1.6}


def test_builtin_h3_libraries_are_available(home):
    libs = Home(home).libraries()
    assert {"camera", "h3style", "instrument"} <= set(libs)
    assert "static" in libs["camera"].values()


def test_user_library_overrides_builtin(home):
    (home / "library" / "camera.yaml").write_text("- tracking, slow\n")
    assert Home(home).libraries()["camera"].values() == ["tracking, slow"]
