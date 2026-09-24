import pytest


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An isolated orrery home with two small libraries."""
    root = tmp_path / "orrery-home"
    lib = root / "library"
    lib.mkdir(parents=True)
    (lib / "animal.yaml").write_text("- fox\n- heron\n- owl\n")
    (lib / "style.yaml").write_text("- linocut\n- gouache\n")
    monkeypatch.setenv("ORRERY_HOME", str(root))
    return root


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Never read or write the real ~/.config/orrery/home pointer."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))


@pytest.fixture(autouse=True)
def _force_fake_llm(monkeypatch):
    """Never let the test suite load or call a real model (lesson LS-G0010)."""
    monkeypatch.setenv("ORRERY_FORCE_FAKE_LLM", "1")
