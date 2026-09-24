"""MiniMax H3 as a compiler target: screenplay in, contract out.

A screenplay-shaped template expands (seeded, recording picks) into a scene
model; writers serialize the scene. The `h3-base` writer computes every
mechanical rule of the official guide (VIDEO_PROMPT_WRITING_GUIDE_base_en.md):
alignment lines, shot timestamps, speaker IDs, `<d>` tags, camera sentences,
soundscape and `N/A` rules. Randomness only ever fills slots.

    @h3 t2va 16:9
    style: live-action, cinematic
    SHOT 5s | push in, small, slow
    A misty forest at dawn.
    NARRATOR (calm voice, off-screen): The forest remembers.
    SFX: branches creak under frost; soft footfalls on snow
    SHOT 3s | cut, static
    A close-up of glowing eyes.
    MUSIC: sparse cello at a slow tempo, fading out

Speaker names are role nouns (WOMAN, NARRATOR, BAKER): the guide identifies
speakers by description, so they render as "The woman … (S1)".
"""

import copy
import dataclasses
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from orrery.cast import (
    MAX_SLOTS,
    MEMBER,
    Labels,
    Member,
    Names,
    article,
    attach,
    bracket_sources,
    oxford,
    parse_member,
)
from orrery.dsl import Expander, Pick
from orrery.library import Library

CAMERA = {
    "push in": "pushes in", "pull out": "pulls out", "zoom in": "zooms in", "zoom out": "zooms out",
    "pan left": "pans left", "pan right": "pans right",
    "truck left": "trucks left", "truck right": "trucks right",
    "tilt up": "tilts up", "tilt down": "tilts down",
    "pedestal up": "pedestals up", "pedestal down": "pedestals down",
    "arc": "arcs around the subject", "tracking": "tracks the moving subject",
    "static": "holds a static shot",
    "shake slightly": "shakes slightly", "shake strongly": "shakes strongly",
    "pov": "shows the subject's point of view",
    "roll clockwise": "rolls clockwise", "roll counterclockwise": "rolls counterclockwise",
}
TRANSITIONS = {
    "cut": "the camera cuts to",
    "dissolve": "the shot transitions with a cross-dissolve to",
    "fade": "the shot fades to",
    "wipe": "the shot wipes to",
}
MODES = ("t2va", "i2va", "fl2va", "l2va", "ref2va")
MOOD_WORDS = re.compile(
    r"\b(sad|happy|epic|emotional|melancholic|melancholy|uplifting|tense|dramatic|romantic|"
    r"hopeful|joyful|nostalgic|heartwarming|mournful|moody)\b", re.IGNORECASE)

_HEADER = re.compile(r"^@h3\s+(\w+)(.*)$", re.IGNORECASE)
_RATIO = re.compile(r"^\d+(?:\.\d+)?:\d+(?:\.\d+)?$")
_STYLE = re.compile(r"^style:\s*(.+)$", re.IGNORECASE)
_SUMMARY = re.compile(r"^summary:\s*(.+)$", re.IGNORECASE)
_ATTRIBUTE = re.compile(r"^(voice|keep):\s*(.+)$")
_ANCHOR = re.compile(r"\b(from|to)\s+image\s+(\d+)(?:\s*\(([^)]*)\))?", re.IGNORECASE)
_SHOT = re.compile(r"^SHOT\s+(\d+(?:\.\d+)?)\s*s\b\s*(?:\|\s*(.*))?$", re.IGNORECASE)
_MUSIC = re.compile(r"^MUSIC:\s*(.+)$", re.IGNORECASE)
_SFX = re.compile(r"^SFX:\s*(.+)$", re.IGNORECASE)
_VOICE = re.compile(r"^([A-Z][A-Z0-9 _-]*?)\s*(?:\(([^)]*)\))?\s*:\s*(.+)$")
_BINDING = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$")
_CHUNK = re.compile(r"^CHUNK\b\s*(.*)$")
_HANDOFF = re.compile(r"^HANDOFF:\s*(.+)$")
_LORA = re.compile(r"^LORA:\s*(.+)$")
_CONTEXT = re.compile(r"^context:\s*(\d+)\s*f?$", re.IGNORECASE)
H3_FPS = 24
DEFAULT_CONTEXT = 22  # H3 Motion Context's default context_length, in frames
_LANG = re.compile(r"^\[([A-Za-z ]+)\]\s*(.*)$")
_CLIP_WEIGHT = re.compile(r"\([^()]*:\s*\d+(?:\.\d+)?\)")
_FIRST_SENTENCE = re.compile(r"^(.*?[.!?])(?:\s+|$)(.*)$", re.DOTALL)


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" | "warn"
    message: str


@dataclass
class Voice:
    name: str
    mods: str
    text: str


@dataclass
class Shot:
    duration: float
    transition: str = "cut"
    camera: str = ""
    items: list = field(default_factory=list)  # str (prose) | Voice
    sfx: list[list[str]] = field(default_factory=list)
    start: float = 0.0
    first_frame: tuple[int, str] | None = None  # ref2va: (image slot, what it shows)
    last_frame: tuple[int, str] | None = None
    chunk: int = -1  # the reel CHUNK it belongs to


@dataclass
class Chunk:
    title: str = ""
    loras: list[str] = field(default_factory=list)
    music: str | None = None
    handoff: str | None = None


@dataclass
class Scene:
    mode: str = "t2va"
    ratio: str = ""
    style: str = ""
    shots: list[Shot] = field(default_factory=list)
    music: str | None = None
    silence: bool = False
    cast: list[Member] = field(default_factory=list)
    summary: str = ""
    lite: bool = False  # `lite` in the header: <Subject N> = … definitions over the base fields
    loras: list[str] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    context: int | None = None  # frames Motion Context pins at the start of every chunk after the first
    pick_owners: list[tuple] = field(default_factory=list)  # parallel to the picks: ("head",) | (kind, chunk)

    @property
    def duration(self) -> float:
        return round(sum(s.duration for s in self.shots), 6)


@dataclass
class Compiled:
    text: str
    picks: list[Pick]
    lint: list[Issue]
    scene: Scene
    loras: str = ""
    chunks: int = 0  # a reel's number of CHUNKs; 0 for a plain screenplay
    segment: int = 0


# --- front end ------------------------------------------------------------------------------

def parse_scene(src: str, ex: Expander, lint: list[Issue]) -> Scene:
    lines = [raw.strip() for raw in src.splitlines()]
    for line in lines:
        if m := _BINDING.match(line):
            ex.bind(m.group(1), m.group(2))
    scene, cur, in_cast = Scene(), None, False
    scene.pick_owners = [("head",)] * len(ex.picks)
    for raw in lines:
        if not raw or _BINDING.match(raw):
            continue
        chunk = len(scene.chunks) - (0 if _CHUNK.match(raw) else 1)
        owner = ("head",) if chunk < 0 else ("handoff" if _HANDOFF.match(raw) else "chunk", chunk)
        line = ex.expr(raw)
        scene.pick_owners += [owner] * (len(ex.picks) - len(scene.pick_owners))
        if m := _HEADER.match(line):
            scene.mode = m.group(1).lower()
            for token in m.group(2).split():
                if token.lower() == "lite":
                    scene.lite = True
                elif _RATIO.match(token):
                    scene.ratio = token
        elif m := _STYLE.match(line):
            scene.style = m.group(1).strip()
        elif m := _SUMMARY.match(line):
            scene.summary = m.group(1).strip()
        elif m := _CHUNK.match(line):
            scene.chunks.append(Chunk(m.group(1).strip()))
            cur, in_cast = None, False
        elif m := _LORA.match(line):
            (scene.chunks[-1].loras if scene.chunks else scene.loras).append(m.group(1).strip())
        elif m := _HANDOFF.match(line):
            if scene.chunks:
                scene.chunks[-1].handoff = m.group(1).strip().rstrip(".")
            else:
                lint.append(Issue("warn", "HANDOFF only works inside a CHUNK; it is ignored."))
        elif m := _CONTEXT.match(line):
            scene.context = int(m.group(1))
        elif line == "CAST" and cur is None:
            in_cast = True
        elif in_cast and cur is None and not _SHOT.match(line):
            _cast_line(scene, line, lint)
        elif m := _SHOT.match(line):
            spec, anchors = _anchors(m.group(2) or "")
            transition, head = "cut", spec.split(",")[0].strip().lower()
            if head in TRANSITIONS:
                transition, spec = head, ",".join(spec.split(",")[1:]).strip()
            cur = Shot(float(m.group(1)), transition, spec, first_frame=anchors.get("from"),
                       last_frame=anchors.get("to"), chunk=len(scene.chunks) - 1)
            scene.shots.append(cur)
        elif m := _MUSIC.match(line):
            if scene.chunks:
                scene.chunks[-1].music = m.group(1).strip()
            else:
                scene.music = m.group(1).strip()
        elif m := _SFX.match(line):
            body = m.group(1).strip()
            if body.lower() == "silence":
                scene.silence = True
            elif cur is None:
                lint.append(Issue("warn", "SFX before the first SHOT is ignored."))
            else:
                cur.sfx.append([x.strip() for x in body.split(";") if x.strip()])
        elif cur is None:
            lint.append(Issue("warn", f"Ignored text before the first SHOT: {line[:48]}"))
        elif m := _VOICE.match(line):
            cur.items.append(Voice(m.group(1).strip(), m.group(2) or "", m.group(3).strip()))
        else:
            cur.items.append(line)
    t = 0.0
    for shot in scene.shots:
        shot.start, t = t, t + shot.duration
    return scene


def _cast_line(scene: Scene, line: str, lint: list[Issue]) -> None:
    if (m := _ATTRIBUTE.match(line)) and scene.cast:
        attach(scene.cast[-1], m.group(1), m.group(2))
    elif m := MEMBER.match(line):
        if any(c.name == m.group(1).strip() for c in scene.cast):
            lint.append(Issue("warn", f"{m.group(1).strip()} is in the CAST twice; the first one counts."))
            return
        scene.cast.append(parse_member(m.group(1), m.group(2), m.group(3).rstrip(".")))
    else:
        lint.append(Issue("warn", f"Ignored CAST line (write NAME (sources): description): {line[:48]}"))


def _clause(text: str) -> str:
    """A handoff as the end of "The shot ends as …": lower-case unless it opens with a NAME."""
    text = text.strip().rstrip(".")
    return text if re.match(r"[A-Z][A-Z0-9_-]+\b", text) else _low(text)


def select_chunk(scene: Scene, index: int) -> Scene:
    """Chunk `index` of a reel as a scene of its own: the previous handoff opens it, its own closes
    it, and from the second chunk on Shot 1 also covers the frames Motion Context pins."""
    n = len(scene.chunks)
    if not 0 <= index < n:
        raise ValueError(f"The reel has {n} chunks; segment {index} is past its end (segments count "
                         "from 0, like Load Latent's clip_index).")
    chunk = scene.chunks[index]
    shots = [copy.deepcopy(s) for s in scene.shots if s.chunk == index]
    before = scene.chunks[index - 1].handoff if index else None
    if shots and before:
        shots[0].items.insert(0, f"The shot opens as {_clause(before)}")
    if shots and chunk.handoff:
        shots[-1].items.append(f"The shot ends as {_clause(chunk.handoff)}")
    context = DEFAULT_CONTEXT if scene.context is None else scene.context
    if shots and index and context:
        shots[0].duration += context / H3_FPS
    t = 0.0
    for shot in shots:
        shot.start, t = t, t + shot.duration
    return dataclasses.replace(scene, shots=shots, music=chunk.music or scene.music, loras=scene.loras + chunk.loras)


def _anchors(spec: str) -> tuple[str, dict[str, tuple[int, str]]]:
    found = {m.group(1).lower(): (int(m.group(2)), (m.group(3) or "").strip()) for m in _ANCHOR.finditer(spec)}
    rest = ", ".join(p.strip() for p in _ANCHOR.sub("", spec).split(",") if p.strip())
    return rest, found


# --- helpers --------------------------------------------------------------------------------

def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _low(s: str) -> str:
    return s[:1].lower() + s[1:]


def _end(s: str) -> str:
    s = s.strip()
    return s if s[-1:] in ".!?" else s + "."


def _sentence_case(s: str) -> str:
    return _cap(re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), s))


def timestamp(t: float) -> str:
    minutes = int(t // 60)
    return f"{minutes:02d}:{t - minutes * 60:06.3f}"


def camera_sentence(spec: str, shot_no: int, lint: list[Issue]) -> str:
    parts = [p.strip().lower() for p in spec.split(",") if p.strip()]
    if not parts:
        return ""
    motion, mods = parts[0], parts[1:]
    if motion not in CAMERA:
        lint.append(Issue("warn", f"Shot {shot_no}: \"{motion}\" is not in the guide's camera vocabulary "
                                  f"({', '.join(CAMERA)}); it goes in as written."))
        return f"Camera movement: {spec.strip()}."
    if motion == "static":
        return "The camera holds a static shot."
    amplitude = speed = ""
    for mod in mods:
        if mod in ("small", "large"):
            amplitude = f" with {mod} amplitude"
        elif mod in ("slow", "fast"):
            speed = f" at {mod} speed"
        else:
            lint.append(Issue("warn", f"Shot {shot_no}: camera modifier \"{mod}\" is not in the "
                                      "guide (small/large, slow/fast)."))
    return f"The camera {CAMERA[motion]}{amplitude}{speed}."


# --- writers --------------------------------------------------------------------------------

class _Speakers:
    """Speaker IDs in the order of first vocal events (assigned up front, so prose can carry a
    member's ID before its line). Cast members speak as their description or, in ref2va, as
    <Subject N> (Sx); everyone else as "The <role> with a <voice> (Sx)"."""

    def __init__(self, scene: Scene, labels: Labels | None = None, sep: str | None = None) -> None:
        self.ids: dict[str, str] = {}
        for shot in scene.shots:
            for it in shot.items:
                if isinstance(it, Voice) and it.name not in self.ids:
                    self.ids[it.name] = f"S{len(self.ids) + 1}"
        self.cast = {m.name: m for m in scene.cast}
        self.labels = labels
        self.sep = sep or ("," if labels else ":")
        self.seen: set[str] = set()

    def in_shot(self, shot: Shot) -> dict[str, str]:
        return {it.name: self.ids[it.name] for it in shot.items if isinstance(it, Voice) and it.name in self.cast}

    def render(self, v: Voice, shot_no: int, lint: list[Issue], names: Names | None = None,
               tagged: set[str] | None = None) -> str:
        mods = [m.strip() for m in v.mods.split(",") if m.strip()]
        flags = {m.lower() for m in mods}
        voiceover = "voiceover" in flags
        off_screen = bool(flags & {"off-screen", "offscreen"})
        desc = ", ".join(m for m in mods if m.lower() not in ("voiceover", "off-screen", "offscreen"))
        lang, words = "English", v.text
        if m := _LANG.match(words):
            lang, words = m.group(1), m.group(2)
        if not words:
            lint.append(Issue("warn", f"Shot {shot_no}: {v.name} has an empty line."))
        sid, sep, first = self.ids[v.name], self.sep, v.name not in self.seen
        self.seen.add(v.name)
        d = f"<d>[{lang}] {words}</d>"
        if member := self.cast.get(v.name):
            if names:
                names.note(v.name, shot_no)
            if tagged is not None:
                tagged.add(v.name)
            if self.labels:
                subject = f"<Subject {self.labels.subjects[v.name]}> ({sid})"
            elif names and v.name not in names.introduced:
                names.introduced.add(v.name)
                subject = f"{_cap(member.head)}{member.tail} ({sid})"
            else:
                subject = f"{_cap(member.short)} ({sid})"
            manner = ""
            if desc:
                has_article = re.match(r"(a|an|the)\s", desc, re.IGNORECASE)
                manner = (f" in {desc if has_article else article(desc) + ' ' + desc}" if "voice" in desc.lower()
                          else f" with {desc}")
            if self.labels and member.voice:
                manner += f", using the voice timbre referenced from {self.labels.label(member.voice)}"
            says = f"{subject} says{manner}"
        else:
            noun = v.name.lower().replace("_", " ")
            says = f"The {noun}{' with a ' + desc if desc and first else ''} ({sid}) says"
        if voiceover:
            return f"{says} in an off-screen voiceover{sep} {d} while their lips remain completely closed."
        if off_screen:
            return f"{says} off-screen{sep} {d}"
        return f"{says}{sep} {d}"


def _alignment(scene: Scene) -> str:
    n, s = len(scene.shots), f"{scene.duration:.2f}"
    if scene.mode == "i2va":
        return ("For the target video, at 0.00 seconds into the target video, "
                "<Picture 1> (from [Shot 1]) is fully referenced.")
    if scene.mode == "fl2va":
        return ("How the reference pictures align with the target video — Picture 1 (from Shot 1) "
                "aligns with the 0.00-second mark of the target video; Picture 2 (from Shot "
                f"{n}) aligns with the {s}-second mark of the target video.")
    if scene.mode == "l2va":
        return ("How the reference pictures align with the target video — <Picture 1> "
                f"(from [Shot {n}]) aligns with the {s}-second mark of the target video.")
    return ""


def render_shots(scene: Scene, lint: list[Issue], speakers: _Speakers, names: Names,
                 labels: Labels | None = None, style: str = "") -> list[str]:
    """One string per shot; `style` opens Shot 1 as its own sentence. With labels (ref2va and
    lite) cast names become <Subject N>, `[image 2]`-style sources become labels, and frame
    anchors are spelled out."""
    shots = []
    for i, shot in enumerate(scene.shots, start=1):
        speaking, tagged, parts = speakers.in_shot(shot) if labels else {}, set(), []
        for it in shot.items:
            if isinstance(it, str):
                text = labels.brackets(it) if labels else it
                parts.append(_sentence_case(_end(names.render(text, i, speaking, tagged))))
            else:
                parts.append(speakers.render(it, i, lint, names, tagged))
        if labels and shot.first_frame:
            parts.insert(0, f"The shot begins from <Picture {shot.first_frame[0]}>.")
        if labels and shot.last_frame:
            parts.append(f"The shot ends on <Picture {shot.last_frame[0]}>.")
        body = " ".join(parts)
        if not body:
            lint.append(Issue("warn", f"Shot {i} has no visible action."))
        m = _FIRST_SENTENCE.match(body)
        first, rest = (m.group(1), m.group(2)) if m else (body, "")
        if i == 1:
            head = "[Shot 1] " + " ".join(p for p in (style and _end(_cap(style)), _cap(first)) if p)
        else:
            head = f"[Shot {i}] At {timestamp(shot.start)}, {TRANSITIONS[shot.transition]} {_low(first)}"
        camera = camera_sentence(shot.camera, i, lint) if shot.camera else ""
        shots.append(" ".join(p for p in (head, camera, rest) if p))
    return shots


def soundscape(scene: Scene, lint: list[Issue]) -> str:
    sfx = [items for shot in scene.shots for items in shot.sfx]
    if sfx:
        sentences = [_end(_cap(oxford(it))) for it in sfx]
        joined = " ".join(sentences)
        if len(sentences) > 4:
            lint.append(Issue("warn", f"overall_soundscape has {len(sentences)} sentences; "
                                      "the guide wants 1–4."))
        if scene.silence:
            lint.append(Issue("warn", "SFX: silence next to other SFX lines is ignored."))
        return joined
    if not scene.silence:
        lint.append(Issue("warn", "No SFX lines, so overall_soundscape is N/A; the guide suggests 1–4 "
                                  "sentences of ambience (SFX: silence says the silence is intended)."))
    return "N/A"


def music(scene: Scene, lint: list[Issue]) -> str:
    if not scene.music or scene.music.strip().rstrip(".").upper() in ("N/A", "NONE"):
        return "N/A"
    if m := MOOD_WORDS.search(scene.music):
        lint.append(Issue("warn", f"MUSIC uses the mood word \"{m.group(1)}\"; the guide wants "
                                  "instrumentation, tempo and dynamics."))
    return _end(_cap(scene.music))


def _fields(scene: Scene, lint: list[Issue], shots: list[str]) -> str:
    return (f"integrated_multimodal_description: {' '.join(shots)}\n\n"
            f"overall_soundscape: {soundscape(scene, lint)}\n\nnon_diegetic_music: {music(scene, lint)}")


def write_h3_base(scene: Scene, lint: list[Issue]) -> str:
    shots = render_shots(scene, lint, _Speakers(scene), Names(scene.cast), style=scene.style)
    return "\n\n".join(p for p in (_alignment(scene), _fields(scene, lint, shots)) if p)


def write_h3_lite(scene: Scene, lint: list[Issue]) -> str:
    """`<Subject N> = description of <Picture i>` lines, then the base fields with every cast
    mention as its label."""
    prose = [it for shot in scene.shots for it in shot.items if isinstance(it, str)]
    labels = Labels(scene.cast, [s for text in prose for s in bracket_sources(text)])
    shots = render_shots(scene, lint, _Speakers(scene, labels, sep=":"), Names(scene.cast, labels, describe=False),
                         labels, style=scene.style)
    definitions = []
    for m in scene.cast:
        subject, phrase = f"<Subject {labels.subjects[m.name]}>", labels.sources_phrase(m)
        definitions.append(f"{subject} = {m.head}{' of ' + phrase if phrase else ''}{m.tail}")
        if m.voice:
            definitions.append(f"{labels.label(m.voice)} = the voice of {subject}")
    align = "" if scene.mode == "ref2va" else _alignment(scene)
    return "\n\n".join(p for p in ("\n".join(definitions), align, _fields(scene, lint, shots)) if p)


def write_flat(scene: Scene) -> str:
    if not scene.shots:
        return scene.style
    names = Names(scene.cast)
    prose = " ".join(_sentence_case(_end(names.render(it, 1))) for it in scene.shots[0].items if isinstance(it, str))
    return f"{_cap(scene.style)}, {_low(prose)}" if scene.style else prose


# --- lint that needs the whole scene --------------------------------------------------------

def _scene_lint(src: str, scene: Scene, lint: list[Issue]) -> None:
    n = len(scene.shots)
    if scene.mode not in MODES:
        lint.append(Issue("warn", f"Unknown mode \"{scene.mode}\" ({', '.join(MODES)}); compiled like t2va."))
    _cast_lint(scene, lint)
    if not n:
        lint.append(Issue("error", "No SHOT yet."))
        return
    if not 4 <= scene.duration <= 15:
        lint.append(Issue("warn", f"Duration {scene.duration:.2f} s is outside H3's trained 4–15 s."))

    def mentions(i: int, pattern: str) -> bool:
        return any(re.search(pattern, it if isinstance(it, str) else it.text)
                   for it in scene.shots[i].items)

    if scene.mode == "i2va" and not mentions(0, r"Picture 1"):
        lint.append(Issue("warn", "I2VA: anchor <Picture 1> in Shot 1, then describe the action."))
    if scene.mode == "fl2va":
        if n > 1:
            lint.append(Issue("warn", "FL2VA: the guide favors a single shot so the model can "
                                      "interpolate between the frames."))
        if not mentions(0, r"Picture 1"):
            lint.append(Issue("warn", "FL2VA: Shot 1 should start from Picture 1."))
        if not mentions(n - 1, r"Picture 2"):
            lint.append(Issue("warn", "FL2VA: the final shot should land on Picture 2."))
    if scene.mode == "l2va" and not mentions(n - 1, r"Picture 1"):
        lint.append(Issue("warn", "L2VA: the final shot must converge on <Picture 1>."))
    if scene.mode == "t2va" and any(mentions(i, r"Picture \d") for i in range(n)):
        lint.append(Issue("warn", "T2VA has no reference pictures; drop them or switch mode."))
    if _CLIP_WEIGHT.search(src):
        lint.append(Issue("warn", "CLIP weight syntax like (word:1.2) is inert on H3: its "
                                  "tokenizer disables weights."))


def _cast_lint(scene: Scene, lint: list[Issue]) -> None:
    ref = scene.mode == "ref2va"
    for m in scene.cast:
        lint.extend(Issue("warn", problem) for problem in m.problems)
        for src in m.sources:
            if src.kind == "refmod":
                lint.append(Issue("warn", f"{m.name} uses refmod {src.name}: orrery does not load RefMods yet, "
                                          f"so apply it with the H3 RefMod nodes. The prompt already describes {m.name}."))
            elif src.index > MAX_SLOTS[src.kind]:
                lint.append(Issue("warn", f"{m.name} uses {src.kind} {src.index}; the Reference to Video node "
                                          f"takes {src.kind} 1–{MAX_SLOTS[src.kind]}."))
        if not ref and (m.voice or any(s.kind != "refmod" for s in m.sources)):
            still = "" if scene.lite else f"; in {scene.mode} its name still expands to its description"
            lint.append(Issue("warn", f"{m.name}: image, video and audio references only take effect in "
                                      f"ref2va{still}."))
        if m.voice and not any(isinstance(it, Voice) and it.name == m.name for s in scene.shots for it in s.items):
            lint.append(Issue("warn", f"{m.name} has a voice reference but never speaks."))
    if not ref and any(s.first_frame or s.last_frame for s in scene.shots):
        lint.append(Issue("warn", "Frame anchors (from/to image N) only take effect in ref2va."))
    if ref and not scene.lite and not scene.summary:
        lint.append(Issue("warn", "ref2va reads best with a summary: line (one short paragraph about the "
                                  "target video, using CAST names)."))


def count_chunks(src: str) -> int:
    return sum(1 for line in src.splitlines() if _CHUNK.match(line.strip()))


def compile_scene(src: str, seed: int, libraries: Mapping[str, Library],
                  weights: Mapping[str, float] | None = None, target: str = "h3-base",
                  segment: int = 0) -> Compiled:
    """`segment` picks the CHUNK of a reel; the whole reel expands every time, so its bindings
    and handoffs are the same in every chunk. Plain screenplays ignore it."""
    ex = Expander(seed, libraries, weights)
    lint: list[Issue] = []
    full = parse_scene(src, ex, lint)
    scene, picks = full, ex.picks
    if full.chunks:
        scene = select_chunk(full, segment)
        mine = {("head",), ("chunk", segment), ("handoff", segment), ("handoff", segment - 1)}
        picks = [p for p, owner in zip(ex.picks, full.pick_owners, strict=True) if owner in mine]
    if target == "flat":
        text = write_flat(scene)
    elif target == "h3-base":
        if scene.lite:
            text = write_h3_lite(scene, lint)
        elif scene.mode == "ref2va":
            from orrery.h3_ref import write_h3_ref
            text = write_h3_ref(scene, lint)
        else:
            text = write_h3_base(scene, lint)
        _scene_lint(src, scene, lint)
    else:
        raise ValueError(f"unknown target {target!r} (h3-base, flat)")
    return Compiled(text, picks, lint, scene, " ".join(scene.loras), len(full.chunks),
                    segment if full.chunks else 0)
