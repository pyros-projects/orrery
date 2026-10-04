"""Takes at the line (#173): what the language model would write at one place of a template, at the node's seed.

A place is a slot (`--directions--`), a library still to be written (`__name__`: an entry that could stand
there), or what a `> enhance` line rewrites. The model sees the prompt as it rolls, the place marked
`[this part]`, and writes N different takes in one request, so they differ; a steering line sharpens them, and
the takes written before are named so the next ones are new. With an API endpoint the server asks it directly,
outside ComfyUI's queue.
"""

from orrery.llm import InvalidProposal, extract_json
from orrery.slots import as_pictures

KINDS = ("slot", "library", "enhance")  # in the editor; "picture": an export slot of a gallery picture (#175)
MARK = "[this part]"


def request(kind: str, what: str, context: str, n: int = 3, steer: str = "", have: list[str] | tuple = (),
            directions: str = "", frames: int = 0, pictures: list[str] = ()) -> str:
    """The prompt for N takes. `context`: the prompt as it rolls with the place marked (MARK), or for `enhance`
    the passage the line rewrites; `what`: the slot's directions, the library's name or the rewrite's instruction;
    `directions`: a library's own, as written after it; `pictures`: those a slot names, sent after the frames (#174)."""
    parts = ["You write for a text-to-image and text-to-video prompt generator."]
    if frames:
        parts.append(f"The {'first ' if pictures else ''}{frames} images are frames of the previous clip, one a second, "
                     "the last one where it ends. The prompt below makes the clip that follows it: continue from that last "
                     "frame, with the same people and place, and move the story on instead of retelling it.")
    if pictures:
        parts.append(f"The {'images after them' if frames else 'images'} are "
                     + ", ".join(f"Picture {i}" for i in range(1, len(pictures) + 1)) + ", in that order. Look at them closely.")
    if kind == "picture":
        parts.append(context.strip())
        parts.append(f"Write {n} different takes for {MARK}, each following its directions exactly: {as_pictures(what, list(pictures))}")
    elif kind == "slot":
        parts.append(f"The prompt, with the part to write marked {MARK}:\n\n{context.strip()}")
        parts.append(f"Write {n} different takes for {MARK}, each prose that fits where it stands and follows its "
                     f"directions exactly: {as_pictures(what, list(pictures))}")
    elif kind == "library":
        parts.append(f"The prompt, with {MARK} where an entry of the wildcard list __{what}__ stands:\n\n{context.strip()}")
        parts.append(f"Write {n} different entries that could stand at {MARK}, each a short phrase that fits the "
                     "sentence around it" + (f", following these directions: {directions}" if directions else "") + ".")
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


def marked(text: str, find: str, nth: int = 0) -> str | None:
    """`text` with the `nth` occurrence of `find` replaced by MARK, or None when it is not there."""
    at = -1
    for _ in range(nth + 1):
        at = text.find(find, at + 1)
        if at < 0:
            return None
    return text[:at] + MARK + text[at + len(find):]
