"""Wildcard libraries: YAML files of entries, optionally tagged and weighted.

Two accepted shapes:

    - fox                          # plain list
    - {value: lynx, tags: [feline], weight: 2}

    meta: {generated_by: Qwen3.5-2B}
    entries:
      - first snow
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

NAME = re.compile(r"^\w+(?:/\w+)*$")  # a library name: film/genre, or a flat one


@dataclass(frozen=True)
class Entry:
    value: str
    tags: tuple[str, ...] = ()
    weight: float = 1.0
    props: tuple[tuple[str, str], ...] = ()  # (key, value) pairs, sorted; `__lib#key:value__` filters on them

    def prop(self, key: str) -> str | None:
        return next((v for k, v in self.props if k == key), None)


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
            tuple(sorted((str(k), str(v)) for k, v in (raw.get("props") or {}).items())),
        )
    raise ValueError(f"not a library entry: {raw!r}")


def _text_entries(text: str) -> list[str]:
    """A plain wildcard file (Dynamic Prompts style): one entry per line, # comments."""
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def load_library(path: Path, name: str | None = None) -> Library:
    path = Path(path)
    if path.suffix == ".txt":
        return Library(name or path.stem, [Entry(v) for v in _text_entries(path.read_text(encoding="utf-8"))], {})
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    meta: dict = {}
    if isinstance(data, dict):
        meta = dict(data.get("meta") or {})
        data = data.get("entries") or []
    if data is None:
        data = []
    if not isinstance(data, list):
        raise TypeError(f"{path}: expected a list of entries")
    return Library(name or path.stem, [_entry(x) for x in data], meta)


def _dump_entry(e: Entry):
    if not e.tags and e.weight == 1.0 and not e.props:
        return e.value
    out: dict = {"value": e.value}
    if e.tags:
        out["tags"] = list(e.tags)
    if e.weight != 1.0:
        out["weight"] = e.weight
    if e.props:
        out["props"] = dict(e.props)
    return out


def save_library(lib: Library, path: Path) -> None:
    entries = [_dump_entry(e) for e in lib.entries]
    data = {"meta": lib.meta, "entries": entries} if lib.meta else entries
    Path(path).write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def library_files(directory: Path) -> dict[str, Path]:
    """Every library file under a folder, by name: `film/genre` is film/genre.yaml or .txt (YAML wins)."""
    directory = Path(directory)
    if not directory.is_dir():
        return {}
    found: dict[str, Path] = {}
    for suffix in (".txt", ".yaml"):  # yaml second, so it replaces a txt of the same name
        for p in sorted(directory.rglob(f"*{suffix}")):
            name = p.relative_to(directory).with_suffix("").as_posix()
            if NAME.match(name):
                found[name] = p
    return dict(sorted(found.items()))


def load_libraries(directory: Path) -> dict[str, Library]:
    return {name: load_library(p, name) for name, p in library_files(directory).items()}
