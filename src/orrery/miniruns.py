"""Local language models, one task per run (#171).

A text encoder in ComfyUI can generate only once per run, and a small model does worse with several tasks in one
request. So with a text encoder orrery queues mini-runs (Orrery Ask): each holds only the language model's node and
what it needs, and answers one task: a library, a slot, a run's rewrites, a sheet's take. Before each render run Roll
queues its run's tasks (`plan`), libraries first, then the rewrites, then the slots, so a slot sees the prose
rewritten; each answer goes into a cache in the home, keyed on the exact roll, and the render run takes it from there
instead of asking the model. What has no answer there is asked in the run, as before.
"""

import hashlib
import json
import time

from orrery.home import locked, write_atomic

CACHE = "asked.json"
KEEP = 24 * 3600  # an answer older than a day is no roll anyone is about to render


def slot_key(source: str, seed: int, segment: int, cell, directions: str) -> str:
    """The roll a slot's text is for: the template as the run reads it, the seed, the clip, the grid's cell."""
    return "slot:" + hashlib.sha256(json.dumps([source, seed, segment, cell, directions]).encode()).hexdigest()[:16]


def rewrite_cache_key(key: str) -> str:
    """A rewrite written by a mini-run, by `takes.rewrite_key` (the instruction and the passage as it rolled)."""
    return f"rewrite:{key}"


def _path(home):
    return home.root / CACHE


def cached(home) -> dict[str, str]:
    path = _path(home)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        return {}
    return {k: v["text"] for k, v in data.items() if isinstance(v, dict) and "text" in v}


@locked
def put(home, key: str, text: str) -> None:
    path = _path(home)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        data = {}
    now = time.time()
    data = {k: v for k, v in data.items() if isinstance(v, dict) and now - v.get("at", 0) < KEEP}
    data[key] = {"text": text, "at": now}
    write_atomic(path, json.dumps(data, indent=1, ensure_ascii=False))


def plan(home, template: str, target: str, params, seed: int, segment: int = 0, sweep: str = "") -> list[dict]:
    """The language model's tasks of one run, in the order their mini-runs go: each library still to be written,
    the rewrites (one task, as the run asks them), each slot. What a rewrite kept with Use selected covers asks
    nothing. A library still to be written stands in as its name while the slots are found."""
    from orrery.autolib import needs
    from orrery.comfy import _passages, dialed, swept
    from orrery.comfy_llm import llm_config
    from orrery.dsl import MissingLibrary, expand
    from orrery.h3 import compile_scene
    from orrery.library import Entry, Library
    from orrery.reel import split_reel
    from orrery.slots import export_slots, names_output, slots
    from orrery.takes import kept_rewrites, rewrite_key

    source = dialed(home, template, params)
    if target == "text" or split_reel(source) is None:
        segment = 0
    source, cell = swept(home, source, sweep)
    missing = [n.name for n in needs(home, source, int(llm_config(home)["entries"]))]  # a top-up too (__name:30__)
    tasks = [{"task": "library", "what": name} for name in missing]
    libs = home.libraries()
    for _ in range(len(missing) + 8):
        try:
            result = (expand(source, seed, libs, home.weights(), cell=cell) if target == "text"
                      else compile_scene(source, seed, libs, home.weights(), target=target, segment=segment, cell=cell))
            break
        except MissingLibrary as err:
            libs = {**libs, err.name: Library(err.name, [Entry(f"\\__{err.name}\\__")])}
    else:
        return tasks
    kept = kept_rewrites(home)
    if [p for p in _passages(result, target) if rewrite_key(p[0], p[1]) not in kept]:
        tasks.append({"task": "rewrites", "what": ""})
    todo = slots(result.text) + [d for d in export_slots(getattr(result, "exports", {})) if d not in slots(result.text)]
    return tasks + [{"task": "slot", "what": d} for d in todo if not names_output(d)]
