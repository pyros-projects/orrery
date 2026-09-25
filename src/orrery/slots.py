"""Slots: `--directions--` in a template is prose the language model writes for this run.

    SHOT 5s | after video 1, tracking, slow
    --what WASHER does in the next 5 seconds--

The slot stands where its text goes; the model sees the whole compiled prompt around it, so what it
writes fits, and in ref2va the CAST names inside the directions arrive as <Subject N> labels it
reuses. With a previous clip (H3 Motion Context's chain) the model also sees that clip, one frame a
second and its last frame, and continues it.

Everything goes to the model in ONE request per run (ComfyUI cannot safely generate twice in one
run): when the template also needs libraries, lists and slots are asked for together, and the slots
then see the template instead of the compiled prompt. A slot the model leaves out keeps its
directions as text, so a queued chain of clips never breaks on one bad answer.
"""

import re

from orrery.autolib import LIST_RULES, Need, library_lines, lists_in, prompt_for, write_lists
from orrery.home import Home
from orrery.llm import Backend, InvalidProposal, extract_json

SLOT = re.compile(r"--(?=[^\s-])([^\n]*?[^\s-])--")


def slots(text: str) -> list[str]:
    """The directions of every slot in the text, in order, each once."""
    found: list[str] = []
    for m in SLOT.finditer(text):
        if m.group(1) not in found:
            found.append(m.group(1))
    return found


def fill(text: str, texts: dict[str, str]) -> str:
    """The text with each slot replaced by what was written for it, else by its directions."""
    return SLOT.sub(lambda m: texts.get(m.group(1)) or m.group(1), text)


def request(wanted: list[Need], directions: list[str], context: str, frames: int = 0) -> str:
    """The one request of a run: libraries to write, slots to fill, and the clip to continue."""
    if not directions:
        return prompt_for(wanted)
    keys = {d: f"slot {i}" for i, d in enumerate(directions, start=1)}
    shown = SLOT.sub(lambda m: f"[{keys[m.group(1)]}]" if m.group(1) in keys else m.group(0), context)
    parts = ["You write for a text-to-image and text-to-video prompt generator."]
    if frames:
        parts.append(f"The {frames} images are frames of the previous clip, one a second, the last one where it "
                     "ends. The prompt below makes the clip that follows it: continue from that last frame, with the "
                     "same people and place, and move the story on instead of retelling it.")
    if wanted:
        parts.append("Wildcard lists to write:\n" + "\n".join(library_lines(wanted)) + f"\n{LIST_RULES}")
    parts.append(f"The prompt, with each part you write marked [slot N]:\n\n{shown.strip()}")
    parts.append("Parts to write, each as prose that fits where it stands and follows its directions exactly:\n"
                 + "\n".join(f'- "{keys[d]}": {d}' for d in directions))
    reply = ("each list name (without underscores) to a JSON array of its entries, and " if wanted else "")
    parts.append(f'Reply with ONLY a JSON object mapping {reply}each part ("slot 1", …) to its text.')
    return "\n\n".join(parts)


def write(home: Home, wanted: list[Need], directions: list[str], reply: str,
          backend: Backend) -> tuple[dict[str, str], list[str]]:
    """The slot texts in a reply, and notes on the libraries it wrote (for review)."""
    data = extract_json(reply)
    if directions and not isinstance(data, dict):
        raise InvalidProposal("the model did not answer with a JSON object")
    notes = write_lists(home, wanted, lists_in(data, wanted), backend) if wanted else []
    texts = {}
    for i, d in enumerate(directions, start=1):
        value = data.get(f"slot {i}")
        if isinstance(value, str) and value.strip():
            texts[d] = " ".join(value.split())
    return texts, notes
