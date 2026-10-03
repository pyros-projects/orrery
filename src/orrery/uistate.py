"""What the node app remembers between sessions: favorite and recently opened presets, and its
switches: New templates open with their quickstart comments, the editor draws chunk dividers and
shows the reel's clips under its scenes, each run prints its prompt and picks to ComfyUI's log, sample
surfing numbers its takes' seeds and keeps the takes not picked. Every switch is on until turned off. And its sizes: `clip_min`, the shorter side of a clip in the clips view."""

import json

from orrery.home import Home, write_atomic

RECENT_MAX = 12
LISTS = ("favorites", "recent")  # preset names, followed by renames and deletes
FLAGS = ("quickstart", "dividers", "timeline", "log_prompts", "surf_numbered", "keep_takes")  # surfing: #206
SIZES = {"clip_min": (360, 96, 1600)}  # name → (default, least, most), in CSS pixels


def _path(home: Home):
    return home.root / "ui.json"


def load_ui(home: Home) -> dict:
    path = _path(home)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {"favorites": list(data.get("favorites") or []), "recent": list(data.get("recent") or []),
            **{flag: data.get(flag) is not False for flag in FLAGS},
            **{name: _size(name, data.get(name)) for name in SIZES}}


def _size(name: str, value) -> int:
    default, least, most = SIZES[name]
    try:
        return min(max(int(value), least), most)
    except (TypeError, ValueError):
        return default


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


def set_flag(home: Home, flag: str, on: bool) -> bool:
    if flag not in FLAGS:
        raise ValueError(f"unknown switch {flag!r}")
    return _save(home, {**load_ui(home), flag: bool(on)})[flag]


def set_size(home: Home, name: str, value) -> int:
    if name not in SIZES:
        raise ValueError(f"unknown size {name!r}")
    return _save(home, {**load_ui(home), name: _size(name, value)})[name]


def rename_everywhere(home: Home, old: str, new: str) -> None:
    data = load_ui(home)
    _save(home, {**data, **{k: [new if n == old else n for n in data[k]] for k in LISTS}})


def forget(home: Home, name: str) -> None:
    data = load_ui(home)
    _save(home, {**data, **{k: [n for n in data[k] if n != name] for k in LISTS}})
