"""Takes at the line (#173): what the language model would write at one place of a template, at the node's seed.

A place is a slot (`--directions--`), a library still to be written (`__name__`: an entry that could stand
there), or what a `> enhance` line rewrites. The model sees the prompt as it rolls, the place marked
`[this part]`, and writes N different takes in one request, so they differ; a steering line sharpens them, and
the takes written before are named so the next ones are new. With an API endpoint the server asks it directly,
outside ComfyUI's queue. A `> enhance` take picked with Use selected is kept for its roll (#276): the run that
rolls the same passage uses it instead of asking the model.
"""

import hashlib
import json

from orrery.home import locked, write_atomic
from orrery.llm import InvalidProposal, extract_json
from orrery.slots import as_pictures

REWRITES = "rewrites.json"
# how many takes each sheet asks for (#274), each writer of the Write menu its own (#334): a story writes a lot
COUNTS = {"slot": 3, "enhance": 3, "rolled": 3, "new": 3, "continue": 3, "story": 3, "describe": 3}
WRITERS = ("continue", "story", "describe")


def counts(llm: dict) -> dict[str, int]:
    """The takes a sheet asks for, from the llm settings: a slot's (a gallery picture's too), a `> enhance` line's,
    entries rolled from a library and new ones the model writes for it, each writer's of the Write menu (one count for
    all of them, `write`, before #333, is their default); 1 to 12 each."""
    saved = llm.get("takes") if isinstance(llm.get("takes"), dict) else {}
    out = {}
    for kind, default in COUNTS.items():
        if kind in WRITERS and "write" in saved:
            default = saved["write"]
        try:
            out[kind] = min(max(int(saved.get(kind, default)), 1), 12)
        except (TypeError, ValueError):
            out[kind] = default
    return out


KINDS = ("slot", "library", "entries", "enhance")  # in the editor; "picture": an export slot of a gallery picture (#175)
MARK = "[this part]"


def request(kind: str, what: str, context: str, n: int = 3, steer: str = "", have: list[str] | tuple = (),
            frames: int = 0, pictures: list[str] = (), labels: list[str] | None = None) -> str:
    """The prompt for N takes of a slot, a gallery picture's slot or a `> enhance` line (a library's: `for_library`).
    `context`: the prompt as it rolls with the place marked (MARK), or for `enhance` the passage the line rewrites;
    `what`: the slot's directions or the rewrite's instruction; `pictures`: those a slot names, then those sent along
    (#174, #335), after the frames; `labels`: what each of them is."""
    parts = ["You write for a text-to-image and text-to-video prompt generator."]
    if frames:
        parts.append(f"The {'first ' if pictures else ''}{frames} images are frames of the previous clip, one a second, "
                     "the last one where it ends. The prompt below makes the clip that follows it: continue from that last "
                     "frame, with the same people and place, and move the story on instead of retelling it.")
    if pictures:
        named = [f"Picture {i}{f' ({labels[i - 1]})' if labels and i <= len(labels) and labels[i - 1] else ''}"
                 for i in range(1, len(pictures) + 1)]
        parts.append(f"The {'images after them' if frames else 'images'} are " + ", ".join(named)
                     + ", in that order. Look at them closely, and write what they show: never name them (Picture 1) in a take.")
    if kind == "picture":
        parts.append(context.strip())
        parts.append(f"Write {n} different takes for {MARK}, each following its directions exactly: {as_pictures(what, list(pictures))}")
    elif kind == "slot":
        parts.append(f"The prompt, with the part to write marked {MARK}:\n\n{context.strip()}")
        parts.append(f"Write {n} different takes for {MARK}, each prose that fits where it stands and follows its "
                     f"directions exactly: {as_pictures(what, list(pictures))}")
    else:
        parts.append(f"Rewrite this passage {n} different ways, each following the instruction: {what}. Keep every "
                     "UPPERCASE name and every <label> exactly as written, keep the same events in the same order, and "
                     f"add concrete visual and sensory detail in the present tense.\n\nThe passage:\n{context.strip()}")
    if steer.strip():
        parts.append(f"Steer them: {steer.strip()}.")
    if have:
        parts.append("Not these, written already; make each new one different from them too:\n"
                     + "\n".join(f"- {h}" for h in have))
    parts.append(f"Reply with ONLY a JSON array of {n} strings, the takes.")
    return "\n\n".join(parts)


def parse(reply: str, n: int) -> list[str]:
    """The takes in a reply, at most N, each on one line; a reply that is no array (or an object holding one)
    has none."""
    try:
        data = extract_json(reply)
    except InvalidProposal:
        return []
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    if not isinstance(data, list):
        return []
    out = [" ".join(t.split()) for t in data if isinstance(t, str) and t.strip()]
    return list(dict.fromkeys(out))[:n]


def for_picture(row: dict, what: str, n: int = 3, steer: str = "", have: list[str] | tuple = ()) -> str | None:
    """The prompt for N takes of a gallery picture's export slot `--what--` (#175): the picture is Picture 1, sent
    with it; the model reads the prompt that made it and what it keeps, the slot marked. None: no such slot."""
    import json

    shown = marked(json.dumps(row.get("exports") or {}, ensure_ascii=False, indent=1), f"--{what}--")
    if shown is None:
        return None
    context = (f"The picture, Picture 1, was made from this prompt:\n\n{row.get('text') or ''}\n\nBeside the prompt it "
               f"keeps these exports (JSON), the part to write marked {MARK}:\n{shown}")
    return request("picture", what, context, n, steer, have, pictures=["output"])


def write_pictures(home, rows: list[dict]) -> list[str]:
    """After a run (the setting's `every run`, #175): every export slot from `image output` of its rows written over
    the API endpoint, one take each, into the gallery. Says what it could not write."""
    from orrery import endpoint, galaxy
    from orrery.comfy_llm import llm_config
    from orrery.slots import export_slots, names_output

    wanted = [(row, d) for row in rows for d in export_slots(row.get("exports") or {}) if names_output(d)]
    if not wanted:
        return []
    api = endpoint.backend(home, float(llm_config(home)["writer_temperature"]))
    if api is None:
        return ["Picture slots are written after a run over an API endpoint; the Gallery writes them on demand."]
    notes = []
    for row, what in wanted:
        try:
            out = parse(api.complete(for_picture(row, what, 1), images=[galaxy.picture_of(row)]), 1)
            if not out:
                raise RuntimeError("the language model wrote nothing")
            galaxy.write_export(home, galaxy.row_id(row), what, out[0])
        except (RuntimeError, KeyError, OSError, ValueError) as err:
            notes.append(f"--{what}--: {err}")
    return notes


def for_library(template: str, name: str, n: int, directions: str = "", steer: str = "", have=(), labels=()):
    """(prompt, need) for a library still to be written, in the sheet (#272): N entries, asked as a run asks for it
    (the lines that use it, its directions), the steer beside them; the entries the sheet has are not written again.
    `labels`: what the pictures sent along are (#335)."""
    from orrery.autolib import Need, _context, prompt_for

    need = Need(name, n, _context(template, name), " ".join(directions.split()), list(have), " ".join(steer.split()))
    prompt = prompt_for([need])
    if labels:
        prompt += ("\n\nThe pictures that came along, in this order: "
                   + "; ".join(f"Picture {i} is {what}" for i, what in enumerate(labels, 1)) + ". Let them shape the entries.")
    return prompt, need


def library_entries(reply: str, need) -> list[str]:
    """The entries a `for_library` reply holds, new against those the sheet has, at most N."""
    from orrery.autolib import lists_in

    known = {v.lower() for v in need.existing}
    out = [v for v in lists_in(extract_json(reply), [need]).get(need.name, []) if v.lower() not in known]
    return list(dict.fromkeys(out))[:need.count]


def rolled_entries(lib, weights: dict, seed: int, n: int, skip=(), first: str = "") -> list[str]:
    """N entries of a library that exists, as its rolls would bring them (#273): the one it rolled at the node's
    seed first (`first`, as the annotation shows it, maybe cut short with …), then weighted draws, each entry's
    weight times what the ratings taught, none of `skip`."""
    import random

    skip = {s.lower() for s in skip}
    pool = [(e.value, max(e.weight, 0.0) * weights.get(f"__{lib.name}__={e.value}", 1.0)) for e in lib.entries
            if e.value.lower() not in skip]
    cut = first[:-1] if first.endswith("…") else None
    out = [v for v, _ in pool if v == first or (cut and v.startswith(cut))][:1]
    rng = random.Random(f"{seed}:{lib.name}:{len(skip)}")
    pool = sorted(((v, w) for v, w in pool if w > 0 and v not in out), key=lambda p: rng.random() ** (1 / p[1]), reverse=True)
    return (out + [v for v, _ in pool])[:n]


def add_to_library(home, name: str, values: list[str], directions: str = "", by: str = "") -> int:
    """Entries picked in a takes sheet, straight into the library, not To review (#272, #273): a new library is
    made of them, an existing one gets the new ones (a built-in one becomes yours). `directions` are kept with it
    for later top-ups. `orrery lib undo` takes it back. Returns how many entries were added."""
    from datetime import UTC, datetime

    from orrery.library import Entry, Library
    from orrery.manager import _snapshot

    lib, path = home.libraries().get(name), home.library_path(name)
    known = {e.value.lower() for e in lib.entries} if lib else set()
    fresh = [v for v in dict.fromkeys(" ".join(str(v).split()) for v in values) if v and v.lower() not in known]
    directions = " ".join(directions.split())
    if not fresh and not (lib and directions):
        return 0
    if lib is None:
        _snapshot(home, [path], f"gen {name}")
        meta = {"generated_by": by or "the takes sheet", "created": datetime.now(UTC).date().isoformat(),
                **({"directions": directions} if directions else {})}
        home.write_library(Library(name, [Entry(v) for v in fresh], meta))
    else:
        _snapshot(home, [path, path.with_suffix(".txt")], f"add {name}")
        meta = {k: v for k, v in lib.meta.items() if k != "builtin"}
        if directions:
            meta["directions"] = directions
        home.write_library(Library(name, [*lib.entries, *(Entry(v) for v in fresh)], meta))
    return len(fresh)


def rewrite_key(instruction: str, passage: str) -> str:
    """The roll a `> enhance` rewrite is kept for (#276): its instruction and the passage as it rolled, slots and all."""
    return hashlib.sha256(f"{' '.join(instruction.split())}\n{passage}".encode()).hexdigest()[:16]


def kept_rewrites(home) -> dict[str, dict]:
    """The rewrites kept with Use selected, by `rewrite_key`: {"instruction", "text"}."""
    path = home.root / REWRITES
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@locked
def keep_rewrite(home, key: str, instruction: str, text: str) -> None:
    """Use selected on a `> enhance` take (#276): kept for the roll `key` names, the run uses it from now on."""
    text = text.strip()
    if not text:
        raise ValueError("an empty rewrite keeps nothing")
    data = kept_rewrites(home)
    data[key] = {"instruction": " ".join(instruction.split()), "text": text}
    write_atomic(home.root / REWRITES, json.dumps(data, indent=1, ensure_ascii=False))


def marked(text: str, find: str, nth: int = 0) -> str | None:
    """`text` with the `nth` occurrence of `find` replaced by MARK, or None when it is not there."""
    at = -1
    for _ in range(nth + 1):
        at = text.find(find, at + 1)
        if at < 0:
            return None
    return text[:at] + MARK + text[at + len(find):]
