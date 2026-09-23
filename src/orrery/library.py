"""Wildcard libraries: YAML files of entries, optionally tagged and weighted.

Two accepted shapes:

    - fox                          # plain list
    - {value: lynx, tags: [feline], weight: 2}

    meta: {generated_by: Qwen3.5-2B}
    entries:
      - first snow
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Entry:
    value: str
    tags: tuple[str, ...] = ()
    weight: float = 1.0


@dataclass
class Library:
    name: str
    entries: list[Entry]
    meta: dict = field(default_factory=dict)

    def values(self) -> list[str]:
        return [e.value for e in self.entries]


def _entry(raw) -> Entry:
    if isinstance(raw, str):
        return Entry(raw.strip())
    if isinstance(raw, dict) and "value" in raw:
        return Entry(
            str(raw["value"]).strip(),
            tuple(str(t) for t in raw.get("tags") or ()),
            float(raw.get("weight", 1.0)),
        )
    raise ValueError(f"not a library entry: {raw!r}")


def load_library(path: Path) -> Library:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    meta: dict = {}
    if isinstance(data, dict):
        meta = dict(data.get("meta") or {})
        data = data.get("entries") or []
    if data is None:
        data = []
    if not isinstance(data, list):
        raise TypeError(f"{path}: expected a list of entries")
    return Library(path.stem, [_entry(x) for x in data], meta)


def _dump_entry(e: Entry):
    if not e.tags and e.weight == 1.0:
        return e.value
    out: dict = {"value": e.value}
    if e.tags:
        out["tags"] = list(e.tags)
    if e.weight != 1.0:
        out["weight"] = e.weight
    return out


def save_library(lib: Library, path: Path) -> None:
    entries = [_dump_entry(e) for e in lib.entries]
    data = {"meta": lib.meta, "entries": entries} if lib.meta else entries
    Path(path).write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def load_libraries(directory: Path) -> dict[str, Library]:
    directory = Path(directory)
    if not directory.is_dir():
        return {}
    return {p.stem: load_library(p) for p in sorted(directory.glob("*.yaml"))}
