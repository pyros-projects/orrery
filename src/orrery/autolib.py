"""Libraries the active LLM makes on the fly: a template that names an unknown `__name__` gets
it created, and `__name:N__` tops a library up to at least N entries. Every write goes through
the manager, so it is snapshotted (`orrery lib undo`) and marked with the model's name."""

from orrery.dsl import wanted_libraries
from orrery.home import Home
from orrery.llm import Backend
from orrery.manager import apply_ops, create_library, propose_more, propose_new


def _context(template: str, name: str) -> str:
    """The template lines that use the library: what the model needs to know what it is for."""
    return "\n".join(line for line in template.splitlines() if f"__{name}" in line) or template


def ensure_libraries(home: Home, template: str, backend: Backend | None, default_n: int = 12) -> list[str]:
    """Create or top up what the template asks for; returns one note per library written."""
    if backend is None:
        return []
    notes, libraries = [], home.libraries()
    for name, minimum in wanted_libraries(template).items():
        lib = libraries.get(name)
        if lib is None:
            n = max(minimum, default_n)
            values = propose_new(home, name, backend, _context(template, name), n)[:n]
            create_library(home, name, values, backend.name)
            notes.append(f"Created __{name}__ with {len(values)} entries ({backend.name}).")
        elif len(lib.entries) < minimum:
            missing = minimum - len(lib.entries)
            ops = propose_more(home, name, backend, missing)
            ops.add = ops.add[:missing]
            if ops.add:
                apply_ops(home, name, ops, by=backend.name)
                notes.append(f"Added {len(ops.add)} entries to __{name}__ ({backend.name}), "
                             f"now {len(lib.entries) + len(ops.add)}.")
    return notes
