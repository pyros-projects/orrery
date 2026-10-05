"""orrery's language model writes screenplays: three writers, each with a prompt of its own that
teaches only what it writes (the static language, no wildcards), so a small model is not confused by
the rules of the others.

    continue   the reel's scenes so far, resolved (picks filled)  →  the next SCENE
    story      the first and the last frame                       →  the SHOT between them (fl2va)
    describe   a picture                                          →  an image prompt, or an i2va SHOT

The prompts ship in builtin/writers/ (Markdown, one per name; describe has two, an image prompt and
an i2va shot) and can be edited in the settings; an edit lives in the orrery home's writers/ folder
and shadows the default. The model writes once per
ComfyUI run (a second generate in one run crashes the process), so an answer that does not fit is
reported with what is wrong, not retried: the app shows it as an idea and asks for the next one.
"""

import re
from pathlib import Path

from orrery.home import Home, write_atomic

BUILTIN = Path(__file__).parent / "builtin" / "writers"
NAMES = ("continue", "story", "describe", "describe_shot")
TASKS = ("continue", "story", "describe")
DEFAULT_SECONDS = 5

_SHOT = re.compile(r"^\s*SHOT\s+(\d+(?:\.\d+)?)\s*s\b", re.IGNORECASE)
_CHUNK = re.compile(r"^\s*(?:SCENE|CHUNK)\b", re.IGNORECASE)
_FORBIDDEN = (
    (re.compile(r"__[\w/]+__"), "wildcards (__name__)"),
    (re.compile(r"\$[A-Za-z_]"), "variables ($name)"),
    (re.compile(r"\{[^{}\n]*\|[^{}\n]*\}"), "choices ({a|b})"),
    (re.compile(r"--[^-\n]{1,80}--"), "slots (--text--)"),
    (re.compile(r"<lora:", re.IGNORECASE), "LoRA tags"),
)


class WriterError(ValueError):
    pass


# What a writer expects to see when nothing else is sent along (#334): the pictures its prompt names.
EXPECTS = {"continue": [], "story": ["the first frame", "the last frame"], "describe": ["the picture"],
           "describe_shot": ["the first frame"]}
_HEADLINE = re.compile(r"\s*(#|@|\$\w+\s*=|(style|summary|context|music|lora|set|voice|keep|export)\s*:|cast\s*$)|[ \t]", re.IGNORECASE)


def as_reel(template: str) -> str:
    """A screenplay without SCENE lines as a reel of one scene (#334): `SCENE the start` before its first shot,
    or before its first line of prose when it has no SHOT line."""
    lines = template.splitlines()
    at = next((i for i, ln in enumerate(lines) if _SHOT.match(ln)), None)
    if at is None:
        at = next((i for i, ln in enumerate(lines) if ln.strip() and not _HEADLINE.match(ln)), len(lines))
    return "\n".join([*lines[:at], "SCENE the start", *lines[at:]])


# --- the texts --------------------------------------------------------------------------------

def _edited(home: Home, name: str) -> Path:
    return home.root / "writers" / f"{name}.md"


def default(name: str) -> str:
    return (BUILTIN / f"{name}.md").read_text(encoding="utf-8")


def text(home: Home, name: str) -> str:
    path = _edited(home, name)
    return path.read_text(encoding="utf-8") if path.is_file() else default(name)


def texts(home: Home) -> dict:
    return {n: {"text": text(home, n), "default": default(n), "edited": _edited(home, n).is_file()} for n in NAMES}


def save(home: Home, name: str, value: str | None) -> dict:
    """Keep an edit; None, an empty text or the default itself goes back to the default."""
    if name not in NAMES:
        raise ValueError(f"no writer text {name!r}; there are {', '.join(NAMES)}")
    path = _edited(home, name)
    if value is None or not value.strip() or value.strip() == default(name).strip():
        path.unlink(missing_ok=True)
    else:
        write_atomic(path, value.rstrip() + "\n")
    return texts(home)[name]


# --- what the model reads ---------------------------------------------------------------------

def is_h3(template: str) -> bool:
    first = next((ln.strip() for ln in template.splitlines() if ln.strip() and not ln.strip().startswith("#")), "")
    return bool(re.match(r"@h3\b", first, re.IGNORECASE))


def shot_seconds(template: str) -> int:
    m = next((m for ln in template.splitlines() if (m := _SHOT.match(ln))), None)
    return round(float(m.group(1))) if m else DEFAULT_SECONDS


def _world(head: list[str]) -> str:
    """The lines a writer may lean on (style, CAST, MUSIC …): no header, comments, params or bindings."""
    keep = [ln for ln in head if ln.strip() and not re.match(r"\s*(@h3\b|@(grid|unique|size|seed|batch|rng)\b|#|:|\$\w+\s*=|context:)", ln)]
    return "\n".join(keep)


def _head(template: str) -> list[str]:
    lines = template.splitlines()
    end = next((i for i, ln in enumerate(lines) if _SHOT.match(ln) or _CHUNK.match(ln)), len(lines))
    return lines[:end]


def _fill(task: str, values: dict) -> str:
    """{name} for the values given; any other braces (an edit may use them) stay as written."""
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), task)


def task_name(task: str, template: str) -> str:
    if task not in TASKS:
        raise WriterError(f"no writer {task!r}; there are {', '.join(TASKS)}")
    return "describe_shot" if task == "describe" and is_h3(template) else task


def request(home: Home, task: str, template: str, seed: int, libraries, weights, steer: str = "",
            given: list[str] | None = None) -> str:
    """The writer's prompt, filled in for this template. `template` is the source as the node
    compiles it: dials applied, includes resolved, comments out. `given`: what the pictures sent along are, in
    order (None: what the writer expects); `steer`: the sheet's steering line (#334)."""
    from orrery.dsl import with_inline

    template, libraries = with_inline(template, libraries)
    name = task_name(task, template)
    if name != "continue" and any(_CHUNK.match(ln) for ln in template.splitlines()):
        raise WriterError("This writer writes one shot, and this template is a reel: its shot would take the "
                          "place of every scene. Use Continue the reel, or a template without SCENE lines.")
    if name == "continue":
        from orrery.reel import reel_path, resolved, split_reel

        if not any(_CHUNK.match(ln) for ln in template.splitlines()):
            if not is_h3(template):
                raise WriterError("Continue the reel writes the next scene of a screenplay (@h3), and this template "
                                  "is an image prompt.")
            template = as_reel(template)  # the screenplay is its first scene, the model writes the second
        reel = split_reel(template)
        path, ended = reel_path(reel, seed, libraries, weights)
        if not ended:
            raise WriterError("This reel plays on and on (a scene that repeats forever, or a CUT TO: without ×N), "
                              "so there is no next scene to write.")
        head, segments = resolved(reel, seed, libraries, weights, len(path))
        chunks = "\n\n".join(
            f"SCENE {s['title'] or f'clip {i + 1}'}\n" + "\n".join(s["lines"])
            + (f"\nEND ON: {s['handoff']}" if s["handoff"] else "") for i, s in enumerate(segments))
        last = segments[-1]["handoff"] if segments else None
        values = {"world": _world(head), "chunks": chunks, "next": len(segments) + 1,
                  "handoff": f"the last clip ended as: {last}" if last else "where the last clip ended"}
    else:
        from orrery.dsl import Expander, parse

        ex = Expander(seed, libraries, weights, parse(template).params.rng)
        world = []
        for ln in _head(template):
            if m := re.match(r"\s*\$(\w+)\s*=\s*(.+)$", ln):
                ex.bind(m.group(1), m.group(2))
            else:
                world.append(ex.expr(ln))
        values = {"seconds": shot_seconds(template), "world": _world(world)}
    parts = [_fill(text(home, name), values).strip()]
    if (note := _came_along(name, given, template, seed, libraries, weights)):
        parts.append(note)
    if steer.strip():
        parts.append(f"Steer it: {' '.join(steer.split())}.")
    return "\n\n".join(parts)


def _came_along(name: str, given: list[str] | None, template: str, seed: int, libraries, weights) -> str:
    """What the pictures sent along are, when they are not what the writer's prompt expects (#334); without the
    pictures it needs, what to write from instead."""
    if given is None or given == EXPECTS[name]:
        return ""
    said = ("The pictures that came along this time, in this order: "
            + "; ".join(f"Picture {i} is {what}" for i, what in enumerate(given, 1)) + "." if given
            else "No pictures came along this time.")
    if name == "continue" or set(EXPECTS[name]) <= set(given):
        return said + (" Let them shape what you write." if given else "")
    if name == "story":
        return f"{said} Imagine the first and the last frame from what you know, and write the shot from one to the other."
    from orrery.dsl import expand

    rolled = expand(template, seed, libraries, weights).text.strip()
    what = "the prompt" if name == "describe" else "the shot"
    return f"{said} Write {what} from this one instead, as the picture it makes would look:\n\n{rolled}"


# --- what comes back --------------------------------------------------------------------------

def _clean(answer: str, starts: re.Pattern | None) -> list[str]:
    """The answer's lines without code fences, comments and chatter before the first expected line."""
    lines = [ln.rstrip() for ln in re.sub(r"```\w*", "", answer or "").splitlines()]
    lines = [ln for ln in lines if not ln.strip().startswith("#")]
    if starts is not None:
        first = next((i for i, ln in enumerate(lines) if starts.match(ln)), None)
        lines = lines[first:] if first is not None else lines
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return lines


def check(task: str, template: str, answer: str) -> tuple[str, str | None]:
    """(the answer as orrery takes it, what is wrong with it or None)."""
    name = task_name(task, template)
    starts = {"continue": _CHUNK, "story": _SHOT, "describe_shot": _SHOT}.get(name)
    lines = _clean(answer, starts)
    if name == "describe":  # one paragraph, without a "Prompt:" label or the quotes around it
        joined = re.sub(r"^(image )?prompt:\s*", "", " ".join(ln.strip() for ln in lines if ln.strip()), flags=re.IGNORECASE)
        lines = [joined.strip().strip('"').strip()] if joined.strip() else []
    out = "\n".join(lines).strip()
    if not out:
        return out, "The answer is empty."
    for pattern, what in _FORBIDDEN:
        if pattern.search(out):
            return out, f"The answer writes {what}, which the writers leave out."
    shots, chunks = sum(1 for ln in lines if _SHOT.match(ln)), sum(1 for ln in lines if _CHUNK.match(ln))
    if name == "continue":
        if not _CHUNK.match(lines[0]):
            return out, "The answer does not start with a SCENE line."
        if chunks > 1:
            return out, f"The answer writes {chunks} scenes; one was asked for."
        if not shots:
            return out, "The scene has no SHOT line."
    elif name in ("story", "describe_shot"):
        if chunks:
            return out, "The answer writes a SCENE; one shot was asked for."
        if not shots:
            return out, "The answer has no SHOT line."
    elif shots or chunks:
        return out, "The answer writes a screenplay; an image prompt was asked for."
    if name != "describe":
        try:
            _compile(lines)
        except Exception as err:  # noqa: BLE001 - the compiler's message is what the user needs
            return out, f"orrery cannot compile it: {err}"
    return out, None


def _compile(lines: list[str]) -> None:
    """The written shots alone, as a screenplay: the template's own wildcards stay out of it."""
    from orrery.h3 import compile_scene

    shots = [ln for ln in lines if not _CHUNK.match(ln) and not re.match(r"\s*(?:END ON|HANDOFF):", ln, re.IGNORECASE)]
    compile_scene("@h3 t2va 16:9\n" + "\n".join(shots), 0, {}, {}, target="h3-base")


def apply(task: str, template: str, text_: str) -> str:
    """The template with the writer's text in its place: a new scene at the end; a shot instead of the
    template's shots (header, style and CAST kept); an image prompt instead of the prompt lines
    (comments and `: w… h…` kept)."""
    name = task_name(task, template)
    if name == "continue":
        reel = template if any(_CHUNK.match(ln) for ln in template.splitlines()) else as_reel(template)
        return f"{reel.rstrip()}\n\n{text_.strip()}\n"
    lines = template.splitlines()
    if name in ("story", "describe_shot"):
        first = next((i for i, ln in enumerate(lines) if _SHOT.match(ln)), len(lines))
        head = "\n".join(lines[:first]).rstrip()
        return f"{head}\n\n{text_.strip()}\n" if head else f"{text_.strip()}\n"
    comments = [ln for ln in lines if ln.strip().startswith("#")]
    params = [ln for ln in lines if re.match(r"\s*(:\s*\S|@(grid|unique|size|seed|batch|rng)\b)", ln)]
    blocks, inside = [], False  # the template's own libraries stay, @lib line and entries
    for ln in lines:
        inside = bool(re.match(r"\s*@lib\s", ln)) or (inside and (ln[:1] in (" ", "\t") or not ln.strip()))
        if inside and ln.strip():
            blocks.append(ln)
    return "\n".join([*comments, *blocks, text_.strip(), *params]) + "\n"
