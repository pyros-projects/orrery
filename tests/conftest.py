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
