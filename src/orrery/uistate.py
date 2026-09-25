"""What the node app remembers between sessions: favorite and recently opened presets, and
whether New templates open with their quickstart comments."""

import json

from orrery.home import Home, write_atomic

RECENT_MAX = 12
LISTS = ("favorites", "recent")  # preset names, followed by renames and deletes


def _path(home: Home):
    return home.root / "ui.json"


def load_ui(home: Home) -> dict:
    path = _path(home)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {"favorites": list(data.get("favorites") or []), "recent": list(data.get("recent") or []),
            "quickstart": data.get("quickstart") is not False}


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


def set_quickstart(home: Home, on: bool) -> bool:
    return _save(home, {**load_ui(home), "quickstart": bool(on)})["quickstart"]


def rename_everywhere(home: Home, old: str, new: str) -> None:
    data = load_ui(home)
    _save(home, {**data, **{k: [new if n == old else n for n in data[k]] for k in LISTS}})


def forget(home: Home, name: str) -> None:
    data = load_ui(home)
    _save(home, {**data, **{k: [n for n in data[k] if n != name] for k in LISTS}})
