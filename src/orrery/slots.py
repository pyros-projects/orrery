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
_FILLED = re.compile(SLOT.pattern + r"(\.?)")  # a period the compiler set after the slot


def slots(text: str) -> list[str]:
    """The directions of every slot in the text, in order, each once."""
    found: list[str] = []
    for m in SLOT.finditer(text):
        if m.group(1) not in found:
            found.append(m.group(1))
    return found


def fill(text: str, texts: dict[str, str]) -> str:
    """The text with each slot replaced by what was written for it, else by its directions."""
    def put(m: re.Match) -> str:
        written = texts.get(m.group(1)) or m.group(1)
        return written if written.endswith((".", "!", "?")) else written + m.group(2)
    return _FILLED.sub(put, text)


def request(wanted: list[Need], directions: list[str], context: str, frames: int = 0,
            rewrites: list[tuple[str, str]] = ()) -> str:
    """The one request of a run: libraries to write, slots to fill, passages to rewrite (`> …`,
    as (instruction, passage)), and the clip to continue."""
    if not directions and not rewrites:
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
    replies = ["each list name (without underscores) to a JSON array of its entries"] if wanted else []
    if directions:
        parts.append(f"The prompt, with each part you write marked [slot N]:\n\n{shown.strip()}")
        labels = " Name people and things by their labels (<Subject N>, <Video N> …) as the prompt does." \
            if re.search(r"<(?:Subject|Picture|Video|Audio) \d+>", context) else ""
        parts.append(f"Parts to write, each as prose that fits where it stands and follows its directions exactly.{labels}\n"
                     + "\n".join(f'- "{keys[d]}": {d}' for d in directions))
        replies.append('each part ("slot 1", …) to its text')
    if rewrites:
        parts.append("Passages to rewrite, each following its instruction. Keep every UPPERCASE name, every <label> "
                     "and every [keep N] marker exactly as written, keep the same events in the same order, and add "
                     "concrete visual and sensory detail in the present tense:\n"
                     + "\n".join(f'- "rewrite {i}" ({instruction}): {passage}'
                                  for i, (instruction, passage) in enumerate(rewrites, start=1)))
        replies.append('each rewrite ("rewrite 1", …) to its new passage')
    parts.append(f"Reply with ONLY a JSON object mapping {', and '.join(replies)}.")
    return "\n\n".join(parts)


def keep_marks(passage: str) -> tuple[str, list[str]]:
    """A passage to rewrite with its slots as [keep N] markers, and the slots to put back."""
    kept: list[str] = []
    return SLOT.sub(lambda m: kept.append(m.group(0)) or f"[keep {len(kept)}]", passage), kept


def put_back(rewritten: str, kept: list[str]) -> str | None:
    """The rewrite with its slots back in place; None when the model lost a marker."""
    for i, slot in enumerate(kept, start=1):
        if f"[keep {i}]" not in rewritten:
            return None
        rewritten = rewritten.replace(f"[keep {i}]", slot)
    return rewritten


def rewrites_in(reply: str, count: int) -> list[str | None]:
    """The rewritten passages in a reply, in order; None where the model wrote none."""
    try:
        data = extract_json(reply)
    except InvalidProposal:
        return [None] * count
    data = data if isinstance(data, dict) else {}
    return [" ".join(v.split()) if isinstance(v := data.get(f"rewrite {i}"), str) and v.strip() else None
            for i in range(1, count + 1)]


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
