"""What the node app remembers between sessions: favorite and recently opened presets."""

import json

from orrery.home import Home, write_atomic

RECENT_MAX = 12


def _path(home: Home):
    return home.root / "ui.json"


def load_ui(home: Home) -> dict:
    path = _path(home)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {"favorites": list(data.get("favorites") or []), "recent": list(data.get("recent") or [])}


def _save(home: Home, data: dict) -> dict:
    write_atomic(_path(home), json.dumps(data, indent=2, ensure_ascii=False))
    return data


def set_favorite(home: Home, name: str, on: bool) -> list[str]:
    data = load_ui(home)
    data["favorites"] = [n for n in data["favorites"] if n != name] + ([name] if on else [])
    return _save(home, data)["favorites"]


def touch_recent(home: Home, name: str) -> list[str]:
    data = load_ui(home)
    data["recent"] = [name, *(n for n in data["recent"] if n != name)][:RECENT_MAX]
    return _save(home, data)["recent"]


def rename_everywhere(home: Home, old: str, new: str) -> None:
    data = load_ui(home)
    _save(home, {k: [new if n == old else n for n in v] for k, v in data.items()})


def forget(home: Home, name: str) -> None:
    data = load_ui(home)
    _save(home, {k: [n for n in v if n != name] for k, v in data.items()})
