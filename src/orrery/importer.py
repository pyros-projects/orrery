"""Import a folder of wildcard files (Dynamic Prompts, z-explorer, Civitai packs) as libraries.

Library names are word characters and `/`, so `80s-pack/Women/daily-clothing.txt` becomes
`__80s_pack/Women/daily_clothing__` (case kept: other files refer to it by that case), and every
`__old/name__` inside the imported entries is rewritten to follow, prefix included. Pass the
folder the pack's own references start from. Readmes, empty files, exact duplicates of a file
already taken and names the home already has are skipped. `merge` turns a folder of
one-prompt-per-file downloads into one library. Files are written as plain `.txt`.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from orrery.library import _text_entries

_NOT_WORD = re.compile(r"[^\w]+")
_README = re.compile(r"^(readme|license|licence|changelog|credits)", re.IGNORECASE)


@dataclass
class Plan:
    libraries: dict[str, list[str]] = field(default_factory=dict)  # new name → entries
    renamed: dict[str, str] = field(default_factory=dict)  # old reference → new name, where it changed
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (file, reason)


def clean_name(rel: str) -> str:
    return "/".join(_NOT_WORD.sub("_", part).strip("_") or "x" for part in rel.split("/"))


def plan_import(src: Path, existing: set[str], into: str | None = None, merge: str | None = None) -> Plan:
    plan, seen = Plan(), {}
    prefix = f"{clean_name(into)}/" if into else ""
    found: list[tuple[str, list[str]]] = []
    for path in sorted(Path(src).rglob("*.txt")):
        rel = path.relative_to(src).with_suffix("").as_posix()
        if _README.match(path.stem):
            plan.skipped.append((rel, "readme"))
            continue
        entries = _text_entries(path.read_text(encoding="utf-8", errors="replace"))
        if not entries:
            plan.skipped.append((rel, "empty"))
            continue
        if merge:
            found.append((rel, entries))
            continue
        key = tuple(entries)
        if key in seen:
            plan.skipped.append((rel, f"duplicate of {seen[key]}"))
            continue
        seen[key] = rel
        found.append((rel, entries))
    if merge:
        merged: dict[str, str] = {}
        for _, entries in found:
            for e in entries:
                merged.setdefault(e.lower(), e)
        plan.libraries[merge] = list(merged.values())
        return plan
    for rel, entries in found:
        name = prefix + clean_name(rel)
        if name in existing or name in plan.libraries:
            plan.skipped.append((rel, f"exists as __{name}__"))
            continue
        plan.libraries[name] = entries
        if name != rel:
            plan.renamed[rel] = name
    for old, new in sorted(plan.renamed.items(), key=lambda kv: -len(kv[0])):  # longest first
        ref = re.compile(rf"__{re.escape(old)}(?=[\[#:]|__)")
        for name, entries in plan.libraries.items():
            plan.libraries[name] = [ref.sub(f"__{new}", e) for e in entries]
    return plan


def run_import(home, plan: Plan) -> list[Path]:
    written = []
    for name, entries in plan.libraries.items():
        path = home.library_dir / f"{name}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        written.append(path)
    return written
