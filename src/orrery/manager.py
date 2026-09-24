"""The wildcard manager: LLM-proposed, human-approved changes to libraries.

The model never writes. It proposes operations (remove, add, rename,
new_lists), orrery validates them against the real library, shows a diff, and
applies only after confirmation. Every write is snapshotted for undo, and
learned weights move with renamed and moved entries.
"""

import json
import re
import shutil
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from orrery.home import Home
from orrery.library import Entry, Library, load_library
from orrery.llm import Backend, InvalidProposal, extract_json


@dataclass
class Ops:
    remove: list[str] = field(default_factory=list)
    add: list[str] = field(default_factory=list)
    rename: list[tuple[str, str]] = field(default_factory=list)
    new_lists: list[tuple[str, list[str]]] = field(default_factory=list)
    note: str = ""
    criterion: str = ""

    def empty(self) -> bool:
        return not (self.remove or self.add or self.rename or self.new_lists)


# --- prompts --------------------------------------------------------------------------------

def gen_prompt(name: str, template: str | None, n: int) -> str:
    context = f" It is used in this template:\n\n{template}\n\n" if template else " "
    return (f"Create a wildcard list named __{name}__ for a text-to-image and text-to-video "
            f"prompt generator.{context}Reply with ONLY a JSON array of {n} distinct, short, vivid "
            "entries (1-4 words each), lowercase unless a proper noun, no numbering, spread widely "
            "across the space so random picks feel varied.")


def more_prompt(lib: Library, n: int) -> str:
    return (f"This is the wildcard list __{lib.name}__ for an image and video prompt generator:\n"
            f"{json.dumps(lib.values(), ensure_ascii=False)}\n\nReply with ONLY a JSON array of {n} "
            "NEW entries in the same spirit and format. No duplicates of existing entries, "
            "no numbering.")


def edit_prompt(lib: Library, other_lists: list[str], instruction: str) -> str:
    """Ask for one decision per entry: small local models classify far better than they plan."""
    others = ", ".join(f"__{n}__" for n in other_lists) or "none"
    return (
        "You edit a wildcard list for an image and video prompt generator.\n"
        f"List: __{lib.name}__\nEntries: {json.dumps(lib.values(), ensure_ascii=False)}\n"
        f"Other lists: {others}\n"
        f"Instruction from the user (any language): {json.dumps(instruction, ensure_ascii=False)}\n\n"
        "First write the criterion: the instruction restated as one precise English rule that "
        "says which entries it selects. Then go through every entry of the list, one by one, and "
        "decide what the instruction means for it:\n"
        '- "keep": the instruction does not apply to this entry\n'
        '- "remove": delete the entry\n'
        '- "move": take the entry out of this list and put it into the list named in "to" '
        "(snake_case)\n"
        '- "rename": replace the entry with the text in "to"\n'
        "Copy every entry exactly as written in Entries. Brand-new entries go only into \"add\".\n\n"
        "Reply with ONLY a JSON object of this shape:\n"
        '{"criterion": "one precise English rule", "decisions": [{"entry": "exact entry", "action": "keep|remove|move|rename", '
        '"to": "target list or new text"}], "add": ["brand-new entry"], '
        '"note": "one short English sentence describing the change"}')


# --- parsing model output -------------------------------------------------------------------

def _clean(values) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, str):
            continue
        v = " ".join(v.split())  # any length: an entry can be a word or a whole saga
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def list_name(raw) -> str:
    """A usable library name: lower-case words and _, folders kept as `film/genre`."""
    parts = (re.sub(r"[^a-z0-9]+", "_", part.lower()).strip("_") for part in str(raw or "").split("/"))
    return "/".join(p for p in parts if p)


def parse_list(text: str) -> list[str]:
    data = extract_json(text)
    if not isinstance(data, list):
        raise InvalidProposal("expected a JSON array of entries")
    values = _clean(data)
    if not values:
        raise InvalidProposal("the model proposed no entries")
    return values


def parse_ops(text: str, lib: Library) -> Ops:
    data = extract_json(text)
    if not isinstance(data, dict):
        raise InvalidProposal("expected a JSON object with remove, add, rename and new_lists")
    index = {v.lower(): v for v in lib.values()}
    unknown: list[str] = []

    def existing(raw) -> str | None:
        found = index.get(str(raw).strip().lower())
        if found is None:
            unknown.append(str(raw))
        return found

    def text(raw) -> str:
        return " ".join(str(raw or "").split())

    remove = [e for e in (existing(v) for v in data.get("remove") or []) if e]
    rename = []
    moved: dict[str, list[str]] = {}
    for pair in data.get("rename") or []:
        if isinstance(pair, dict) and text(pair.get("to")):
            old = existing(pair.get("from", ""))
            if old:
                rename.append((old, text(pair["to"])))
    for d in data.get("decisions") or []:
        action = str(d.get("action", "keep")).strip().lower() if isinstance(d, dict) else "keep"
        if action == "keep":
            continue
        entry = existing(d.get("entry", ""))
        target = list_name(d.get("to")) if action == "move" else text(d.get("to"))
        if not entry or action not in ("remove", "move", "rename"):
            continue
        if action == "remove":
            remove.append(entry)
        elif action == "move" and target and target != lib.name:
            remove.append(entry)
            moved.setdefault(target, []).append(entry)
        elif action == "rename" and target:
            rename.append((entry, target))
    if unknown:
        raise InvalidProposal(f"the model referenced entries that are not in __{lib.name}__: "
                              + ", ".join(repr(u) for u in unknown))
    new_lists = list(moved.items())
    for raw in data.get("new_lists") or []:
        if isinstance(raw, dict):
            name, entries = list_name(raw.get("name")), _clean(raw.get("entries"))
            if name and entries and name != lib.name:
                new_lists.append((name, entries))
    add = [a for a in _clean(data.get("add")) if a.lower() not in index]
    return Ops(list(dict.fromkeys(remove)), add, rename, new_lists, str(data.get("note") or "")[:200],
               str(data.get("criterion") or "")[:300])


def diff_text(name: str, ops: Ops) -> str:
    lines = [f"__{name}__"]
    if ops.criterion:
        lines.append(f"understood as: {ops.criterion}")
    lines += [f"  - {v}" for v in ops.remove]
    lines += [f"  + {v}" for v in ops.add]
    lines += [f"  ~ {old} → {new}" for old, new in ops.rename]
    lines += [f"new list __{n}__: {', '.join(vals)}" for n, vals in ops.new_lists]
    if ops.note:
        lines.append(f"note: {ops.note}")
    if ops.empty():
        lines.append("  (no changes proposed)")
    return "\n".join(lines)


# --- history --------------------------------------------------------------------------------

def _snapshot(home: Home, files: list[Path], action: str) -> None:
    folder = home.history_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    folder.mkdir(parents=True)
    manifest = {"action": action, "files": {}}
    for f in files:
        rel = f.relative_to(home.root)
        manifest["files"][str(rel)] = f.exists()
        if f.exists():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, folder / rel)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))


def undo(home: Home) -> str | bool:
    """Restore the state before the last write. Returns its action, or False if none."""
    snapshots = sorted(home.history_dir.glob("*/manifest.json")) if home.history_dir.exists() else []
    if not snapshots:
        return False
    folder = snapshots[-1].parent
    manifest = json.loads(snapshots[-1].read_text())
    for rel, existed in manifest["files"].items():
        target = home.root / rel
        if existed:
            shutil.copy2(folder / rel, target)
        else:
            target.unlink(missing_ok=True)
    shutil.rmtree(folder)
    return manifest["action"]


# --- operations -----------------------------------------------------------------------------

def _library(home: Home, name: str) -> Library:
    libs = home.libraries()
    if name not in libs:
        raise KeyError(f"library __{name}__ does not exist (create it: orrery lib gen {name})")
    return libs[name]


def propose_new(home: Home, name: str, backend: Backend, template: str | None = None,
                n: int = 12) -> list[str]:
    if home.library_file(name):
        raise FileExistsError(f"library __{name}__ already exists (use: orrery lib more {name})")
    return parse_list(backend.complete(gen_prompt(name, template, n)))


def create_library(home: Home, name: str, values: list[str], model_name: str) -> Library:
    _snapshot(home, [home.library_path(name)], f"gen {name}")
    lib = Library(name, [Entry(v) for v in values],
                  {"generated_by": model_name, "created": datetime.now(UTC).date().isoformat()})
    home.write_library(lib)
    return lib


def generate(home: Home, name: str, backend: Backend, model_name: str,
             template: str | None = None, n: int = 12) -> Library:
    return create_library(home, name, propose_new(home, name, backend, template, n), model_name)


def propose_more(home: Home, name: str, backend: Backend, n: int = 8) -> Ops:
    lib = _library(home, name)
    known = {v.lower() for v in lib.values()}
    fresh = [v for v in parse_list(backend.complete(more_prompt(lib, n))) if v.lower() not in known]
    return Ops(add=fresh, note=f"{len(fresh)} new entries in the same spirit")


def propose_edit(home: Home, name: str, instruction: str, backend: Backend) -> Ops:
    lib = _library(home, name)
    others = [n for n in home.libraries() if n != name]
    return parse_ops(backend.complete(edit_prompt(lib, others, instruction)), lib)


def apply_ops(home: Home, name: str, ops: Ops, by: str) -> None:
    lib = _library(home, name)
    path = home.library_path(name)
    new_paths = [home.library_path(n) for n, _ in ops.new_lists]
    _snapshot(home, [path, path.with_suffix(".txt"), *new_paths, home.weights_path], f"edit {name}")

    by_value = {e.value: e for e in lib.entries}
    renamed = dict(ops.rename)
    entries = [replace(e, value=renamed.get(e.value, e.value))
               for e in lib.entries if e.value not in ops.remove]
    entries += [Entry(v) for v in ops.add if v not in {e.value for e in entries}]
    home.write_library(Library(name, entries, {k: v for k, v in lib.meta.items() if k != "builtin"}))

    for (new_name, values), new_path in zip(ops.new_lists, new_paths, strict=True):
        existing = home.library_file(new_name)
        target = load_library(existing, new_name) if existing else Library(new_name, [], {"generated_by": by})
        have = set(target.values())
        target.entries += [by_value.get(v, Entry(v)) for v in values if v not in have]
        home.write_library(target)

    weights, family = home.weights(), f"__{name}__"
    for old, new in ops.rename:
        if f"{family}={old}" in weights:
            weights[f"{family}={new}"] = weights.pop(f"{family}={old}")
    for new_name, values in ops.new_lists:
        for v in values:
            if f"{family}={v}" in weights:
                weights[f"__{new_name}__={v}"] = weights[f"{family}={v}"]
    for v in ops.remove:
        weights.pop(f"{family}={v}", None)
    home.save_weights(weights)
