"""Pictures by name: the gallery's pictures, for a CAST member's `image <name>`.

Every preset's pictures in the gallery are a library, `__pictures/<preset>__`, with one entry per
character: a seed of the preset with its dials (`krea/09_character_creator/1283456183`), carrying all
the pictures that seed made (a grid's views) and the prompt that made them. So
`@HERO (image __pictures/krea/09_character_creator__)` rolls a character like any library does
(seeded, recorded, steered by ratings), and `@HERO (image krea/09_character_creator/1283456183)` names
one. A picture of a character is also named by its file: `krea/09_character_creator/krea2_00092_`.
Pictures a template without a preset made are under `unsaved/<template hash>`.

A character also carries what its template rolled for it, as properties named after the bindings
(`gender`, `origin`, `genre`, `colour` …, its dials included), so a second character can be told to
differ from the first: `__pictures/krea/09_character_creator[origin!=$hero.origin]__`. What its
template EXPORTed comes along too, and wins: `$hero.who`, `$hero.mood`, an exported entry's
properties as `$hero.job_tool`, a list as its items joined with commas.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

from orrery import galaxy
from orrery.dsl import bindings, split_options
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


_OWN = ("pictures", "prompt")  # the properties every character has; a binding of that name gives way
_PICKED = re.compile(r"^\$(\w+) ← ")  # `$origin ← __characters/creator/origin__`: a library binding's pick


def _plain(value) -> str:
    """A rolled value as a property to compare: its own choices, bindings and libraries left out, so
    `Tamil descent, with {deep brown|dark brown} skin` reads the same however its skin rolled."""
    text = str(value)
    while (shorter := re.sub(r"\{[^{}]*\}", "", text)) != text:
        text = shorter
    text = re.sub(r"__[\w/*\[\]=|!,$. -]*?__|\$\w+(?:\.\w+)?", "", text)
    return " ".join(text.replace(" ,", ",").split()).strip(" ,")


def _choices_by_label(template: str) -> dict[str, str]:
    """The template's choice bindings by the label their picks carry: `{woman|man|nonbinary person}` → gender."""
    out = {}
    for name, expr in bindings(template):
        e = expr.strip()
        if e.startswith("{") and e.endswith("}") and not re.match(r"\{\s*(IF\b|\?|\d+(-\d+)?\$\$)", e):
            options = [re.sub(r":\d+(\.\d+)?$|^\d+(\.\d+)?::", "", o.strip()) for o in split_options(e[1:-1])]
            out["{" + "|".join(options) + "}"] = name
    return out


def _traits(home, row: dict, labels: dict) -> dict[str, str]:
    """What the row's template rolled, by binding name, and its dials."""
    digest = str(row.get("template") or "")
    if digest not in labels:
        from orrery import presets

        text = presets.recall_template(home, digest) if re.fullmatch(r"[0-9a-f]{16}", digest) else None
        labels[digest] = _choices_by_label(text or "")
    out = {}
    for pick in row.get("picks") or []:
        label = str(pick.get("label") or "")
        name = m.group(1) if (m := _PICKED.match(label)) else labels[digest].get(label)
        if name and name not in _OWN and (value := _plain(pick.get("value", ""))):
            out[name] = value
    for name, value in (row.get("params") or {}).items():
        if name not in _OWN and (value := _plain(value)):
            out[name] = value
    for name, value in (row.get("exports") or {}).items():  # EXPORT: (#157): what the picture carries on purpose
        fields = value if isinstance(value, dict) else {"value": value}
        for field, text in fields.items():
            key = name if field == "value" else f"{name}_{field}"
            text = ", ".join(map(str, text)) if isinstance(text, list) else " ".join(str(text).split())
            if key not in _OWN and re.fullmatch(r"\w+", key) and text:
                out[key] = text
    return out


def libraries(home) -> dict[str, Library]:
    """The gallery's pictures as libraries, one per preset; a picture whose file is gone is left out."""
    groups: dict[str, dict[str, list[dict]]] = {}
    for row in reversed(galaxy.read_rows(home)):  # oldest first: a grid's views in the order they were made
        media = row.get("media")
        if row.get("kind") != "image" or not media or not Path(media).is_file():
            continue
        groups.setdefault(_owner(row), {}).setdefault(_character(row), []).append(row)
    out, labels = {}, {}
    for owner, characters in groups.items():
        entries = []
        for name, rows in characters.items():
            factors = [RATING.get(r.get("rating") or "", 1.0) for r in rows]
            rated = sorted({f"{r['rating']}d" for r in rows if r.get("rating") in RATING}  # loved, liked, noped, hated
                           | ({"exported"} if any(r.get("exports") for r in rows) else set()))  # it carries EXPORT: data
            each = [_traits(home, r, labels) for r in rows]
            traits = {k: v for k, v in each[0].items() if all(t.get(k) == v for t in each)}  # not the view, say
            props = {**traits, "pictures": "\n".join(str(r["media"]) for r in rows), "prompt": str(rows[0].get("text") or "")}
            entries.append(Entry(name, tuple(rated), round(sum(factors) / len(factors), 3), tuple(sorted(props.items()))))
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
