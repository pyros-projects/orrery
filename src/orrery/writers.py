"""orrery's language model writes screenplays: three writers, each with a prompt of its own that
teaches only what it writes (the static language, no wildcards), so a small model is not confused by
the rules of the others.

    continue   the reel's scenes so far, resolved (picks filled)  →  the next SCENE, after any scene
    story      a start and an end: a frame, a scene, the prompt   →  what happens between them: the SHOT
                                                                     between two frames (fl2va), N scenes,
                                                                     or N keyframe prompts for an image model
    describe   a picture                                          →  an image prompt, or an i2va SHOT

The prompts ship in builtin/writers/ (Markdown, one per name; story has three, a shot, scenes and
keyframes, describe two, an image prompt and an i2va shot) and can be edited in the settings; an edit lives in the orrery home's writers/ folder
and shadows the default. The model writes once per
ComfyUI run (a second generate in one run crashes the process), so an answer that does not fit is
reported with what is wrong, not retried: the app shows it as an idea and asks for the next one.
"""

import re
from pathlib import Path

from orrery.home import Home, write_atomic

BUILTIN = Path(__file__).parent / "builtin" / "writers"
NAMES = ("continue", "story", "story_scenes", "story_keyframes", "describe", "describe_shot", "describe_shot_into")
TASKS = ("continue", "story", "describe")
DEFAULT_SECONDS = 5
MAX_SCENES = 99  # the scenes (or keyframes) one story asks for
MAX_SECONDS = 60  # how long one of its scenes may be
HOWS = ("prepend", "append", "replace", "insert", "caret")  # where a sheet puts takes in (see `place`)
FIRST, LAST, PROMPT = "first_frame", "last_frame", "prompt"  # a story's start and end besides a scene (its index)

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
           "describe_shot": ["the first frame"], "describe_shot_into": ["the first frame"]}
_FRAME = {FIRST: "the first frame", LAST: "the last frame"}
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


def is_reel(template: str) -> bool:
    return any(_CHUNK.match(ln) for ln in template.splitlines())


def options(raw: dict | None, template: str) -> dict:
    """What a writer's sheet chose (#342, #343): `after`, the scene Continue continues after (its index; None, the
    end); `from` and `to`, the story's start and end (a scene's index, first_frame, last_frame or the prompt);
    `scenes`, how many it writes; `seconds`, how long each scene is."""
    raw = raw or {}

    def scene(v):
        return isinstance(v, int) and not isinstance(v, bool) and v >= 0

    def end(key, default):
        v = raw.get(key, default)
        return v if scene(v) or v in (FIRST, LAST, PROMPT) else default

    seconds = raw.get("seconds")
    return {"after": raw["after"] if scene(raw.get("after")) else None,
            "from": end("from", FIRST), "to": end("to", LAST if is_h3(template) else PROMPT),
            "scenes": max(1, min(MAX_SCENES, int(raw.get("scenes") or 1))),
            "seconds": max(1, min(MAX_SECONDS, int(seconds))) if seconds else shot_seconds(template)}


def task_name(task: str, template: str, opts: dict | None = None) -> str:
    """The text a writer sends: the story writes a shot between two frames only on a screenplay without scenes,
    one scene asked for; on a reel or for more, scenes; on an image prompt, keyframes (#343)."""
    if task not in TASKS:
        raise WriterError(f"no writer {task!r}; there are {', '.join(TASKS)}")
    if task == "story":
        if not is_h3(template):
            return "story_keyframes"
        o = opts or {}  # the fl2va shot: one scene from frame to frame on a screenplay without scenes
        shot = o.get("scenes", 1) == 1 and o.get("from", FIRST) == FIRST and o.get("to", LAST) == LAST
        return "story" if shot and not is_reel(template) else "story_scenes"
    return "describe_shot" if task == "describe" and is_h3(template) else task


def _run(reel, path: list[tuple[int, int]], k: int, start: int = 0) -> tuple[int, int] | None:
    """Where scene `k` first plays on the walk from clip `start` on, and how many clips have played when it ends:
    its repeats in a row, the first play of one that repeats forever (#342). None: it does not play."""
    at = next((t for t in range(start, len(path)) if path[t][0] == k), None)
    if at is None:
        return None
    end = at + 1
    while reel.blocks[k].repeat is not None and end < len(path) and path[end] == (k, path[end - 1][1] + 1):
        end += 1
    return at, end


def _scenes(segments: list[dict]) -> str:
    return "\n\n".join(f"SCENE {s['title'] or f'clip {i + 1}'}\n" + "\n".join(s["lines"])
                        + (f"\nEND ON: {s['handoff']}" if s["handoff"] else "") for i, s in enumerate(segments))


def _title(reel, k: int) -> str:
    return f"SCENE {k + 1}" + (f" ({reel.blocks[k].title})" if 0 <= k < len(reel.blocks) and reel.blocks[k].title else "")


def _walked(template: str, seed: int, libraries, weights, scenes: list[int | None]):
    """The world's lines, the clips as they play at the seed as far as `scenes` need, and for each of them (an index,
    in the order the walk meets them; None, the end) where it first plays and how many clips have played when it
    ends. The end of a reel that plays on and on is the first time its last scene ends (#342)."""
    from orrery.reel import reel_path, resolved, split_reel

    reel = split_reel(template)
    path, ended = reel_path(reel, seed, libraries, weights)
    runs, start = [], 0
    for k in scenes:
        if k is None:
            run = (len(path) - 1, len(path)) if ended else _run(reel, path, max(b for b, _ in path))
        elif not 0 <= k < len(reel.blocks):
            raise WriterError(f"The reel has {len(reel.blocks)} scenes; there is no scene {k + 1}.")
        elif (run := _run(reel, path, k, start)) is None:
            raise WriterError(f"{_title(reel, k)} does not play{' after ' + _title(reel, scenes[0]) if start else ''} at "
                              "this seed: a CUT TO: jumps past it, or a scene before it plays on and on.")
        runs.append(run)
        start = run[1]
    head, segments = resolved(reel, seed, libraries, weights, max((n for _, n in runs), default=0))
    return head, segments, runs


def _first_shot(lines: list[str]) -> str:
    """A screenplay's first shot, the lines from its first SHOT to the next: where the story's end begins. Shown
    whole, the 8B wrote the end's shots again instead of leading into them (experiments/writer-framing)."""
    at = [i for i, ln in enumerate(lines) if _SHOT.match(ln)]
    return "\n".join(lines[at[0]:at[1] if len(at) > 1 else len(lines)]).strip() if at else "\n".join(lines).strip()


def _story_ends(template: str, opts: dict, given: list[str] | None, seed: int, libraries, weights) -> tuple[dict, bool]:
    """The story's {start} and {end} (#343): a frame sent along, shown where it is named (imagined when it did not
    come); a scene of the reel as it plays at the seed (from: with every clip up to its end; to: its first shot); the
    screenplay itself (from: all of it; to: its first shot); or on an image prompt the picture the prompt makes. And
    whether the prompt as it rolls is in them."""
    from orrery.llm import PICTURES

    frm, to = opts["from"], opts["to"]
    came = given if given is not None else [_FRAME[k] for k in (frm, to) if k in _FRAME]
    ends = {}
    scenes = [k for k in (frm, to) if isinstance(k, int)]
    if scenes:
        if not is_reel(template):
            raise WriterError("A story from or to a scene needs a reel: this screenplay has no SCENE lines.")
        _, segments, runs = _walked(template, seed, libraries, weights, scenes)
        if isinstance(frm, int):
            n = runs[0][1]
            last = segments[n - 1]["handoff"]
            ends["start"] = (f"The reel so far, every clip as it was made:\n\n{_scenes(segments[:n])}\n\n"
                             f"The start: where the last of these clips ends{f' ({last})' if last else ''}.")
        if isinstance(to, int):
            ends["end"] = ("The end: a scene that begins with this shot; your last scene leads into it:\n\n"
                           + _first_shot(segments[runs[-1][0]]["lines"]))
    rolled = _rolled(template, seed, libraries, weights) if PROMPT in (frm, to) else ""
    for role, key in (("start", frm), ("end", to)):
        if key == PROMPT and not is_h3(template):
            ends[role] = f"The {role}: the picture this prompt makes:\n\n{rolled}"
        elif key == PROMPT and role == "start":  # the screenplay itself (#343): the story goes on from it
            ends[role] = f"The start: this screenplay, as it rolls; your first scene goes on from where it ends:\n\n{rolled}"
        elif key == PROMPT:  # or leads into it
            ends[role] = ("The end: a screenplay that begins with this shot; your last scene leads into it:\n\n"
                          + _first_shot(rolled.splitlines()))
        elif key in _FRAME:
            ends[role] = (f"The {role}: {_FRAME[key]}, this picture: {PICTURES}" if _FRAME[key] in came else
                          f"The {role}: {_FRAME[key]}, which did not come along this time: imagine it from what you know.")
    return ends, bool(rolled)


def request(home: Home, task: str, template: str, seed: int, libraries, weights, steer: str = "",
            given: list[str] | None = None, prompt: bool = False, opts: dict | None = None) -> str:
    """The writer's prompt, filled in for this template. `template` is the source as the node
    compiles it: dials applied, includes resolved, comments out. `given`: what the pictures sent along are, in
    order (None: what the writer expects); `steer`: the sheet's steering line (#334); `prompt`: the prompt as it
    rolls goes along too (#335; Continue has the reel anyway); `opts`: what the sheet chose (see `options`)."""
    from orrery.dsl import with_inline

    template, libraries = with_inline(template, libraries)
    opts = options(opts, template)
    name = task_name(task, template, opts)  # a reel's prompt from an image writes from its head (#334): at the caret
    if name == "describe_shot" and prompt and given != []:
        # the screenplay sent along with a picture (#333): who is in the picture joins it. The 8B kept the picture's
        # room and ignored the screenplay until told to take only them from it, the picture after the screenplay
        # (experiments/writer-framing)
        name = "describe_shot_into"
    inside = False  # whether the prompt as it rolls is in the request already
    if name == "continue":
        if not is_reel(template):
            if not is_h3(template):
                raise WriterError("Continue the reel writes the next scene of a screenplay (@h3), and this template "
                                  "is an image prompt.")
            template = as_reel(template)  # the screenplay is its first scene, the model writes the second
        # no guardrail for a reel that plays on and on (#342): it continues after its scene's first end
        head, segments, ((_, n),) = _walked(template, seed, libraries, weights, [opts["after"]])
        last = segments[n - 1]["handoff"] if n else None
        values = {"world": _world(head), "chunks": _scenes(segments[:n]), "next": n + 1,
                  "handoff": f"the last clip ended as: {last}" if last else "where the last clip ended"}
        inside = True
    else:
        from orrery.dsl import Expander, parse

        ex = Expander(seed, libraries, weights, parse(template).params.rng)
        world = []
        for ln in _head(template):
            if m := re.match(r"\s*\$(\w+)\s*=\s*(.+)$", ln):
                ex.bind(m.group(1), m.group(2))
            else:
                world.append(ex.expr(ln))
        n = opts["scenes"]
        values = {"seconds": opts["seconds"], "world": _world(world),
                  "scenes": "one scene" if n == 1 else f"{n} scenes", "keyframes": "one image prompt" if n == 1 else f"{n} image prompts"}
        if name in ("story_scenes", "story_keyframes"):
            ends, inside = _story_ends(template, opts, given, seed, libraries, weights)
            values.update(ends)
        elif name == "describe_shot_into":
            from orrery.llm import PICTURES

            values.update(screenplay=_rolled(template, seed, libraries, weights), picture=PICTURES)
            inside = True
    parts = [_fill(text(home, name), values).strip()]
    if (note := _came_along(name, given, template, seed, libraries, weights, opts)):
        parts.append(note)
    if prompt and not inside and "from this one instead" not in note:  # what it is for, or a small model passes it by
        parts.append("The prompt you write for, as it rolls at this seed. What you write goes into it: keep its world, "
                     "its people, its place and its style, and carry its story on"
                     + (", unless the direction below says otherwise" if steer.strip() else "")
                     + f":\n\n{_rolled(template, seed, libraries, weights)}")
    if steer.strip():  # last, where a small model weighs it most (#333)
        parts.append(f"The direction, which outweighs everything above: {' '.join(steer.split())}.")
    if len(parts) > 1:
        parts.append("Answer as asked above, with what you write alone.")
    return "\n\n".join(parts)


def _said(given: list[str]) -> str:
    return ("The pictures that came along this time, in this order: "
            + "; ".join(f"Picture {i} is {what}" for i, what in enumerate(given, 1)) + "." if given
            else "No pictures came along this time.")


def _came_along(name: str, given: list[str] | None, template: str, seed: int, libraries, weights, opts: dict) -> str:
    """What the pictures sent along are, when they are not what the writer's prompt expects (#334); without the
    pictures it needs, what to write from instead. A story's scenes or keyframes always say which picture is which:
    their prompt names the frames, not the pictures (#343)."""
    if name in ("story_scenes", "story_keyframes"):
        expects = [_FRAME[k] for k in (opts["from"], opts["to"]) if k in _FRAME]
        shown = expects if given is None else given
        if not shown:  # the start or the end says what did not come
            return ""
        return _said(shown) + ("" if shown == expects else " Let them shape what you write.")
    if given is None or given == EXPECTS[name]:
        return ""
    said = _said(given)
    if name == "describe_shot_into":  # any picture can be who joins
        return said
    if name == "continue" or set(EXPECTS[name]) <= set(given):
        return said + (" Let them shape what you write." if given else "")
    if name == "story":
        lacking = [w for w in EXPECTS[name] if w not in given]
        return (f"{said} There is no {' and no '.join(w.removeprefix('the ') for w in lacking)} this time: imagine "
                f"{'them' if len(lacking) > 1 else 'it'} from what you know, and write the shot from the first frame to the last.")
    what = "the prompt" if name == "describe" else "the shot"
    return (f"{said} Write {what} from this one instead, as the picture it makes would look:\n\n"
            f"{_rolled(template, seed, libraries, weights)}")


def _rolled(template: str, seed: int, libraries, weights) -> str:
    """The template as it rolls at the seed, line by line (a screenplay keeps its lines): no header, comments,
    params or bindings (#335)."""
    from orrery.dsl import Expander, parse

    ex, out = Expander(seed, libraries, weights, parse(template).params.rng), []
    for ln in template.splitlines():
        if m := re.match(r"\s*\$(\w+)\s*=\s*(.+)$", ln):
            ex.bind(m.group(1), m.group(2))
        elif ln.strip() and not re.match(r"\s*(@h3\b|@(grid|unique|size|seed|batch|rng)\b|#|:)", ln):
            out.append(ex.expr(ln))
    return "\n".join(out).strip()


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


_LABEL = re.compile(r"^\s*(?:\d+\s*[.):]|[-*•]|keyframe\s*\d+\s*[:.)-]?)\s*", re.IGNORECASE)


def _keyframes(lines: list[str]) -> list[str]:
    """The keyframe prompts of an answer, one a line: without numbers, labels, quotes and a line that announces them,
    and without the language's own signs (`{ } | $ __`), so they go on a grid as they are (#343)."""
    out = [_LABEL.sub("", ln).strip().strip('"').strip() for ln in lines]
    out = [re.sub(r"[{}$]", "", ln.replace("|", ",")).replace("__", "_") for ln in out]
    return [ln for ln in out if ln and not ln.endswith(":")]


def check(task: str, template: str, answer: str, opts: dict | None = None) -> tuple[str, str | None]:
    """(the answer as orrery takes it, what is wrong with it or None)."""
    opts = options(opts, template)
    name = task_name(task, template, opts)
    starts = {"continue": _CHUNK, "story": _SHOT, "story_scenes": _CHUNK, "describe_shot": _SHOT}.get(name)
    if starts is not None:  # an SFX: the model ran onto the end of the prose goes on a line of its own
        answer = re.sub(r"(?m)(?<=\S)[ \t]+(SFX:)", r"\n\1", answer or "")
    lines = _clean(answer, starts)
    if name == "describe":  # one paragraph, without a "Prompt:" label or the quotes around it
        joined = re.sub(r"^(image )?prompt:\s*", "", " ".join(ln.strip() for ln in lines if ln.strip()), flags=re.IGNORECASE)
        lines = [joined.strip().strip('"').strip()] if joined.strip() else []
    elif name == "story_keyframes":
        lines = _keyframes(lines)
    out = "\n".join(lines).strip()
    if not out:
        return out, "The answer is empty."
    for pattern, what in _FORBIDDEN:
        if pattern.search(out):
            return out, f"The answer writes {what}, which the writers leave out."
    shots, chunks = sum(1 for ln in lines if _SHOT.match(ln)), sum(1 for ln in lines if _CHUNK.match(ln))
    asked = opts["scenes"]
    if name in ("continue", "story_scenes"):
        if not _CHUNK.match(lines[0]):
            return out, "The answer does not start with a SCENE line."
        want = 1 if name == "continue" else asked
        if chunks != want:
            return out, f"The answer writes {chunks} scenes; {'one was' if want == 1 else f'{want} were'} asked for."
        per = []  # the SHOT lines of each scene
        for ln in lines:
            if _CHUNK.match(ln):
                per.append(0)
            elif _SHOT.match(ln):
                per[-1] += 1
        if not all(per):
            return out, "A scene has no SHOT line."
    elif name in ("story", "describe_shot"):
        if chunks:
            return out, "The answer writes a SCENE; one shot was asked for."
        if not shots:
            return out, "The answer has no SHOT line."
    elif shots or chunks:
        return out, "The answer writes a screenplay; an image prompt was asked for."
    elif name == "story_keyframes" and len(lines) != asked:
        return out, f"The answer writes {len(lines)} keyframes; {asked} were asked for."
    if name not in ("describe", "story_keyframes"):
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


def at_caret(task: str, template: str) -> bool:
    """A prompt from an image on a reel (#334): its shot cannot take the place of every scene, so it goes in where the
    caret is, and the app puts it there."""
    return task_name(task, template) == "describe_shot" and is_reel(template)


def _place(template: str, text_: str, after: int | None, until: int | None, insert: bool) -> str:
    """The reel with `text_` after scene `after` (-1: before the first; None: at the end), in place of the scenes
    from there up to scene `until` (None: all of them), or with them kept: `insert` (#342, #343)."""
    lines = template.rstrip().splitlines()
    at = [i for i, ln in enumerate(lines) if _CHUNK.match(ln)]

    def line(k):
        return at[k] if k < len(at) else len(lines)

    a = len(lines) if after is None else line(after + 1)
    b = a if insert else max(a, len(lines) if until is None else line(until))
    before, rest = lines[:a], lines[b:]
    while before and not before[-1].strip():
        before.pop()
    return "\n".join([*before, *([""] if before else []), text_.strip(), *(["", *rest] if rest else [])]) + "\n"


def apply(task: str, template: str, text_: str, opts: dict | None = None, insert: bool = False) -> str:
    """The template with the writer's text in its place: a new scene after the scene it continues, in place of the
    scenes after it or with them kept (`insert`); a story's shot instead of the template's shots (header, style and
    CAST kept), its scenes between its start and its end, its keyframes as the prompt, all of them on a grid; an
    image prompt instead of the prompt lines (comments and `: w… h…` kept)."""
    opts = options(opts, template)
    name = task_name(task, template, opts)
    if name == "continue":
        return _place(template if is_reel(template) else as_reel(template), text_, opts["after"], None, insert)
    if name == "story_scenes":
        frm, to = opts["from"], opts["to"]
        after = frm if isinstance(frm, int) else None if frm == PROMPT else -1  # from the prompt: after all of it
        until = to if isinstance(to, int) else (after + 1 if after is not None else None) if to == PROMPT else None
        return _place(template if is_reel(template) else as_reel(template), text_, after, until, insert)
    lines = template.splitlines()
    if name in ("story", "describe_shot"):
        first = next((i for i, ln in enumerate(lines) if _SHOT.match(ln)), len(lines))
        head = "\n".join(lines[:first]).rstrip()
        kept = "\n".join(lines[first:]).strip() if insert else ""
        body = f"{text_.strip()}\n\n{kept}" if kept else text_.strip()
        return f"{head}\n\n{body}\n" if head else f"{body}\n"
    comments = [ln for ln in lines if ln.strip().startswith("#")]
    params = [ln for ln in lines if re.match(r"\s*(:\s*\S|@(grid|unique|size|seed|batch|rng)\b)", ln)]
    blocks, inside = [], False  # the template's own libraries stay, @lib line and entries
    for ln in lines:
        inside = bool(re.match(r"\s*@lib\s", ln)) or (inside and (ln[:1] in (" ", "\t") or not ln.strip()))
        if inside and ln.strip():
            blocks.append(ln)
    prompt = [text_.strip()]
    frames = [ln for ln in text_.splitlines() if ln.strip()]
    if name == "story_keyframes" and len(frames) > 1:  # the storyboard: one Roll renders every keyframe, in order (#343)
        prompt = [f"$keyframe = {{{'|'.join(frames)}}}", "$keyframe"]
        params = [ln for ln in params if not re.match(r"\s*@(grid|unique)\b", ln)] + ["@grid $keyframe"]
    return "\n".join([*comments, *blocks, *prompt, *params]) + "\n"


# --- what the sheet puts in -------------------------------------------------------------------

def _escaped(text_: str) -> str:
    """A take inside `{a|b}`: what the language reads as its own (`{ } | $ __ \\`) written as itself."""
    return re.sub(r"[\\{}|$]", lambda m: "\\" + m.group(0), text_).replace("__", "\\__")


def _binding_name(text_: str) -> str:
    used, name, n = set(re.findall(r"\$(\w+)", text_)), "take", 1
    while name in used:
        n += 1
        name = f"take{n}"
    return name


def _scenes_of(take: str) -> list[list[str]]:
    """A take's scenes, each its SCENE line and the lines under it (lines before the first go with it)."""
    out, loose = [], []
    for ln in take.splitlines():
        if _CHUNK.match(ln):
            out.append([ln.strip(), *loose])
            loose = []
        elif out:
            out[-1].append(ln)
        else:
            loose.append(ln)
    return out


def as_choice(takes: list[str], template: str = "") -> tuple[str, str | None]:
    """Several takes as one choice (#336), so every Roll picks one: (the text, a binding for the template's head or
    None). One-line takes as `{a|b|c}`; takes of several lines (shots, keyframes) as a binding and IF lines, the
    whole take or nothing; scenes keep their SCENE lines (IF cannot hide one) and choose what is in them by a binding
    in the head, the same take in every scene (a binding in a scene holds only there)."""
    takes = [t.strip() for t in takes if t.strip()]
    if all("\n" not in t for t in takes):
        return "{" + "|".join(_escaped(t) for t in takes) + "}", None
    name = _binding_name(template + "\n" + "\n".join(takes))
    pick = f"${name} = {{{'|'.join(str(i) for i in range(1, len(takes) + 1))}}}"

    def guarded(i, lines):
        return [f"IF ${name} is {i}: {ln.strip()}" for ln in lines if ln.strip()]

    if not any(_CHUNK.match(ln) for t in takes for ln in t.splitlines()):
        return "\n".join([pick, *(g for i, t in enumerate(takes, 1) for g in guarded(i, t.splitlines()))]), None
    split, out = [_scenes_of(t) for t in takes], []
    for k in range(max(len(scenes) for scenes in split)):
        out += [next(scenes[k][0] for scenes in split if len(scenes) > k),
                *(g for i, scenes in enumerate(split, 1) if len(scenes) > k for g in guarded(i, scenes[k][1:])), ""]
    return "\n".join(out).strip(), pick


def _head_end(lines: list[str]) -> int:
    """Where a screenplay's head ends: its first SHOT or SCENE line, blank lines before it left out."""
    at = next((i for i, ln in enumerate(lines) if _SHOT.match(ln) or _CHUNK.match(ln)), len(lines))
    while at > 0 and not lines[at - 1].strip():
        at -= 1
    return at


def place(task: str, template: str, takes: list[str], opts: dict | None = None, how: str = "append",
          choice: bool = False) -> dict:
    """The takes a writer's sheet puts in (#333), one after the other in the order picked, or as a choice: {"text": as
    they go in, "template": with them in}. `how`: prepend (a screenplay's after its head, an image prompt's at the
    top) and append, a plain copy for every writer in every mode; replace and insert where the writer has a place
    (see `apply`: after the scene picked, between the story's start and end, in place of the shots or the prompt);
    caret, the text alone, for the app to put in at the caret. No limit on how many."""
    if how not in HOWS:
        raise WriterError(f"'how' is one of {', '.join(HOWS)}.")
    takes = [t.strip() for t in takes if t and t.strip()]
    if not takes:
        raise WriterError("Select a take first.")
    opts = options(opts, template)
    name = task_name(task, template, opts)
    if name == "story_keyframes":  # every keyframe of every take: on the grid, or one choice
        takes = [ln.strip() for t in takes for ln in t.splitlines() if ln.strip()]
        text_, head = as_choice(takes) if choice else ("\n".join(takes), None)
    elif choice and len(takes) > 1:
        text_, head = as_choice(takes, template)
    else:
        text_, head = "\n\n".join(takes), None
    if how == "caret":
        return {"text": text_, "template": None}
    lines = template.rstrip().splitlines()
    if head:
        lines.insert(_head_end(lines), head)
    base = "\n".join(lines)
    if how == "append":
        out = f"{base.rstrip()}\n\n{text_}\n" if base.strip() else f"{text_}\n"
    elif how == "prepend":
        at = _head_end(lines) if is_h3(base) else 0
        before, after = lines[:at], lines[at:]
        while after and not after[0].strip():
            after.pop(0)
        out = "\n".join([*before, *([""] if before else []), text_, *(["", *after] if after else [])]) + "\n"
    elif name == "story_keyframes" and choice:  # a choice of keyframes in place of the prompt, no grid
        out = apply("describe", base, text_)
    else:
        out = apply(task, base, text_, opts, insert=how == "insert")
    return {"text": text_, "template": out}

