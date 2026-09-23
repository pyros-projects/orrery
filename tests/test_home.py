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
    assert sorted(Home(home).libraries()) == ["animal", "style"]


def test_weights_are_empty_until_saved(home):
    h = Home(home)
    assert h.weights() == {}
    h.save_weights({"__animal__=fox": 1.6})
    assert Home(home).weights() == {"__animal__=fox": 1.6}
