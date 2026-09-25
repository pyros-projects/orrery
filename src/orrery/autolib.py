"""Libraries the active LLM makes on the fly: a template that names an unknown `__name__` gets
it created, `__name:N__` tops a library up to at least N entries, and `__name__(directions)`
tells the model what the entries should be like.

Everything the template needs is asked for in ONE request (ComfyUI can't safely generate twice in
one run, and one request keeps the lists consistent with each other). What the model writes waits
for review: a new library is marked `pending`, entries added to an existing one are listed in
`pending_entries`; the Libraries tab accepts or discards them. Writes are snapshotted
(`orrery lib undo`) and carry the model's name.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from orrery.dsl import library_directions, wanted_libraries, without_directions
from orrery.home import Home
from orrery.library import Entry, Library
from orrery.llm import Backend, InvalidProposal, extract_json
from orrery.manager import _snapshot, parse_list

DEFAULT_STYLE = "short and vivid entries (1-4 words), lowercase unless a proper noun"


@dataclass
class Need:
    name: str
    count: int  # entries to write
    context: str
    directions: str = ""
    existing: list[str] = field(default_factory=list)  # a top-up: the library as it is


def _context(template: str, name: str) -> str:
    """The template lines that use the library: what the model needs to know what it is for."""
    lines = "\n".join(line for line in template.splitlines() if f"__{name}" in line) or template
    return without_directions(lines).strip()  # one list's directions are not another's


def needs(home: Home, template: str, default_n: int) -> list[Need]:
    libraries, directions, out = home.libraries(), library_directions(template), []
    for name, minimum in wanted_libraries(template).items():
        lib = libraries.get(name)
        if lib is None:
            out.append(Need(name, max(minimum, default_n), _context(template, name), directions.get(name, "")))
        elif len(lib.entries) < minimum:
            out.append(Need(name, minimum - len(lib.entries), _context(template, name),
                            directions.get(name) or str(lib.meta.get("directions") or ""), lib.values()))
    return out


def prompt_for(wanted: list[Need]) -> str:
    lines = []
    for n in wanted:
        what = (f"{n.count} NEW entries in the spirit of the existing ones {json.dumps(n.existing, ensure_ascii=False)}, "
                "no duplicates" if n.existing else f"{n.count} entries")
        # A list with directions gets nothing but them: a default style beside them, or the template line
        # with its slot mid-sentence, still pulls small models toward short phrases, however it is ranked.
        guide = (f"Directions: {n.directions}" if n.directions
                 else f"Used in: {n.context}\n  Style: {DEFAULT_STYLE}")
        lines.append(f"- __{n.name}__: {what}.\n  {guide}")
    return ("You write wildcard lists for a text-to-image and text-to-video prompt generator.\n\n"
            + "\n".join(lines)
            + "\n\nEvery entry follows its list's Directions or Style exactly. Entries are distinct and spread widely "
            "across the space so random picks feel varied. Reply with ONLY a JSON object mapping each list name "
            "(without underscores) to a JSON array of its entries.")


def _answers(reply: str, wanted: list[Need]) -> dict[str, list[str]]:
    data = extract_json(reply)
    if isinstance(data, list) and len(wanted) == 1:  # small models answer one list with a bare array
        data = {wanted[0].name: data}
    if not isinstance(data, dict):
        raise InvalidProposal("the model did not answer with one list per library")
    return {n.name: parse_list(json.dumps(data.get(n.name) or data.get(f"__{n.name}__") or []))
            for n in wanted if data.get(n.name) or data.get(f"__{n.name}__")}


def ensure_libraries(home: Home, template: str, backend: Backend | None, default_n: int = 12) -> list[str]:
    """Create or top up what the template asks for, in one request; one note per library written."""
    wanted = needs(home, template, default_n) if backend is not None else []
    if not wanted:
        return []
    answers, notes = _answers(backend.complete(prompt_for(wanted)), wanted), []
    for n in wanted:
        known = {v.lower() for v in n.existing}
        values = [v for v in answers.get(n.name, []) if v.lower() not in known][:n.count]
        if not values:
            continue
        path = home.library_path(n.name)
        if n.existing:
            lib = home.libraries()[n.name]
            _snapshot(home, [path, path.with_suffix(".txt")], f"top up {n.name}")
            meta = {k: v for k, v in lib.meta.items() if k != "builtin"}
            meta["pending_entries"] = [*meta.get("pending_entries", []), *values]
            if n.directions:
                meta["directions"] = n.directions
            home.write_library(Library(n.name, [*lib.entries, *(Entry(v) for v in values)], meta))
            notes.append(f"Added {len(values)} entries to __{n.name}__ ({backend.name}), now "
                         f"{len(lib.entries) + len(values)}; review them in Libraries.")
        else:
            _snapshot(home, [path], f"gen {n.name}")
            meta = {"generated_by": backend.name, "created": datetime.now(UTC).date().isoformat(), "pending": True,
                    **({"directions": n.directions} if n.directions else {})}
            home.write_library(Library(n.name, [Entry(v) for v in values], meta))
            notes.append(f"Created __{n.name}__ with {len(values)} entries ({backend.name}); review it in Libraries.")
    return notes
