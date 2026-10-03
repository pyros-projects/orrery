"""Pictures by name: the gallery's pictures, for a CAST member's `image <name>`.

Every preset's pictures in the gallery are a library, `__pictures/<preset>__`, with one entry per
character: a seed of the preset with its dials (`krea/09_character_creator/1283456183`), carrying all
the pictures that seed made (a grid's views) and the prompt that made them. So
`@HERO (image __pictures/krea/09_character_creator__)` rolls a character like any library does
(seeded, recorded, steered by ratings), and `@HERO (image krea/09_character_creator/1283456183)` names
one. A picture of a character is also named by its file: `krea/09_character_creator/krea2_00092_`.
Pictures a template without a preset made are under `unsaved/<template hash>`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from orrery import galaxy
from orrery.library import Entry, Library

PREFIX = "pictures/"
RATING = {"love": 1.5, "like": 1.2, "nope": 0.8, "hate": 0.5}  # as the gallery multiplies learned weights


def _owner(row: dict) -> str:
    return row.get("preset") or f"unsaved/{str(row.get('template') or 'none')[:8]}"


def _character(row: dict) -> str:
    """A seed of the preset, with a short hash of its dials when it had any."""
    params = row.get("params") or {}
    tail = f"-{hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()[:4]}" if params else ""
    return f"{_owner(row)}/{row.get('seed')}{tail}"


def libraries(home) -> dict[str, Library]:
    """The gallery's pictures as libraries, one per preset; a picture whose file is gone is left out."""
    groups: dict[str, dict[str, list[dict]]] = {}
    for row in reversed(galaxy.read_rows(home)):  # oldest first: a grid's views in the order they were made
        media = row.get("media")
        if row.get("kind") != "image" or not media or not Path(media).is_file():
            continue
        groups.setdefault(_owner(row), {}).setdefault(_character(row), []).append(row)
    out = {}
    for owner, characters in groups.items():
        entries = []
        for name, rows in characters.items():
            factors = [RATING.get(r.get("rating") or "", 1.0) for r in rows]
            rated = sorted({f"{r['rating']}d" for r in rows if r.get("rating") in RATING})  # loved, liked, noped, hated
            entries.append(Entry(name, tuple(rated), round(sum(factors) / len(factors), 3),
                                 (("pictures", "\n".join(str(r["media"]) for r in rows)),
                                  ("prompt", str(rows[0].get("text") or "")))))
        out[PREFIX + owner] = Library(PREFIX + owner, entries, {"source": f"the gallery's pictures of {owner}",
                                                                "gallery": True})
    return out


def find(name: str, libraries: Mapping[str, Library]) -> list[Path] | None:
    """The pictures `name` stands for: a character's (all its views) or one picture by its file; None when
    the gallery has no such picture."""
    owner, _, last = name.strip().rpartition("/")
    lib = libraries.get(PREFIX + owner)
    if lib is None:
        return None
    for entry in lib.entries:
        files = [Path(p) for p in (entry.prop("pictures") or "").splitlines() if p]
        if entry.value == name:
            return files
        if one := [f for f in files if f.stem == last or f.name == last]:
            return one[:1]
    return None


def prompt(name: str, libraries: Mapping[str, Library]) -> str:
    """The prompt that made the pictures `name` stands for, or ''."""
    owner, _, last = name.strip().rpartition("/")
    lib = libraries.get(PREFIX + owner)
    for entry in lib.entries if lib else []:
        if entry.value == name or any(Path(p).stem == last for p in (entry.prop("pictures") or "").splitlines()):
            return entry.prop("prompt") or ""
    return ""
