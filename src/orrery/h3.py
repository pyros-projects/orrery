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

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

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
MODES = ("t2va", "i2va", "fl2va", "l2va")
MOOD_WORDS = re.compile(
    r"\b(sad|happy|epic|emotional|melancholic|melancholy|uplifting|tense|dramatic|romantic|"
    r"hopeful|joyful|nostalgic|heartwarming|mournful|moody)\b", re.IGNORECASE)

_HEADER = re.compile(r"^@h3\s+(\w+)(?:\s+(\S+))?", re.IGNORECASE)
_STYLE = re.compile(r"^style:\s*(.+)$", re.IGNORECASE)
_SHOT = re.compile(r"^SHOT\s+(\d+(?:\.\d+)?)\s*s\b\s*(?:\|\s*(.*))?$", re.IGNORECASE)
_MUSIC = re.compile(r"^MUSIC:\s*(.+)$", re.IGNORECASE)
_SFX = re.compile(r"^SFX:\s*(.+)$", re.IGNORECASE)
_VOICE = re.compile(r"^([A-Z][A-Z0-9 _-]*?)\s*(?:\(([^)]*)\))?\s*:\s*(.+)$")
_BINDING = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$")
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


@dataclass
class Scene:
    mode: str = "t2va"
    ratio: str = ""
    style: str = ""
    shots: list[Shot] = field(default_factory=list)
    music: str | None = None
    silence: bool = False

    @property
    def duration(self) -> float:
        return round(sum(s.duration for s in self.shots), 3)


@dataclass
class Compiled:
    text: str
    picks: list[Pick]
    lint: list[Issue]
    scene: Scene


# --- front end ------------------------------------------------------------------------------

def parse_scene(src: str, ex: Expander, lint: list[Issue]) -> Scene:
    lines = [raw.strip() for raw in src.splitlines()]
    for line in lines:
        if m := _BINDING.match(line):
            ex.bind(m.group(1), m.group(2))
    scene, cur = Scene(), None
    for raw in lines:
        if not raw or _BINDING.match(raw):
            continue
        line = ex.expr(raw)
        if m := _HEADER.match(line):
            scene.mode, scene.ratio = m.group(1).lower(), m.group(2) or ""
        elif m := _STYLE.match(line):
            scene.style = m.group(1).strip()
        elif m := _SHOT.match(line):
            spec, transition = (m.group(2) or "").strip(), "cut"
            head = spec.split(",")[0].strip().lower()
            if head in TRANSITIONS:
                transition, spec = head, ",".join(spec.split(",")[1:]).strip()
            cur = Shot(float(m.group(1)), transition, spec)
            scene.shots.append(cur)
        elif m := _MUSIC.match(line):
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
        lint.append(Issue("error", f"Shot {shot_no}: unknown camera motion \"{motion}\". "
                                   f"The guide knows: {', '.join(CAMERA)}."))
        return ""
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
    def __init__(self) -> None:
        self.ids: dict[str, str] = {}

    def render(self, v: Voice, shot_no: int, lint: list[Issue]) -> str:
        mods = [m.strip() for m in v.mods.split(",") if m.strip()]
        flags = {m.lower() for m in mods}
        voiceover = "voiceover" in flags
        off_screen = bool(flags & {"off-screen", "offscreen"})
        desc = ", ".join(m for m in mods if m.lower() not in ("voiceover", "off-screen", "offscreen"))
        lang, words = "English", v.text
        if m := _LANG.match(words):
            lang, words = m.group(1), m.group(2)
        if not words:
            lint.append(Issue("error", f"Shot {shot_no}: {v.name} has an empty line."))
        noun = v.name.lower().replace("_", " ")
        if v.name in self.ids:
            subject = f"The {noun} ({self.ids[v.name]})"
        else:
            self.ids[v.name] = f"S{len(self.ids) + 1}"
            subject = f"The {noun}{' with a ' + desc if desc else ''} ({self.ids[v.name]})"
        d = f"<d>[{lang}] {words}</d>"
        if voiceover:
            return f"{subject} says in an off-screen voiceover: {d} while their lips remain completely closed."
        if off_screen:
            return f"{subject} says off-screen: {d}"
        return f"{subject} says: {d}"


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


def write_h3_base(scene: Scene, lint: list[Issue]) -> str:
    speakers = _Speakers()
    shots = []
    for i, shot in enumerate(scene.shots, start=1):
        body = " ".join(
            _sentence_case(_end(it)) if isinstance(it, str) else speakers.render(it, i, lint)
            for it in shot.items)
        if not body:
            lint.append(Issue("error", f"Shot {i} has no visible action."))
        m = _FIRST_SENTENCE.match(body)
        first, rest = (m.group(1), m.group(2)) if m else (body, "")
        if i == 1:
            head = "[Shot 1] " + (f"{_cap(scene.style)}, {_low(first)}" if scene.style else _cap(first))
        else:
            head = f"[Shot {i}] At {timestamp(shot.start)}, {TRANSITIONS[shot.transition]} {_low(first)}"
        camera = camera_sentence(shot.camera, i, lint) if shot.camera else ""
        shots.append(" ".join(p for p in (head, camera, rest) if p))

    sfx = [items for shot in scene.shots for items in shot.sfx]
    if sfx:
        sentences = [_end(_cap(it[0])) if len(it) == 1
                     else _end(_cap(", ".join(it[:-1])) + " while " + it[-1]) for it in sfx]
        soundscape = " ".join(sentences)
        if len(sentences) > 4:
            lint.append(Issue("warn", f"overall_soundscape has {len(sentences)} sentences; "
                                      "the guide wants 1–4."))
        if scene.silence:
            lint.append(Issue("warn", "SFX: silence next to other SFX lines is ignored."))
    else:
        soundscape = "N/A"
        if not scene.silence:
            lint.append(Issue("error", "No SFX lines: overall_soundscape needs 1–4 sentences. "
                                       "Write SFX: silence only for complete silence."))
    music = "N/A"
    if scene.music:
        music = _end(_cap(scene.music))
        if m := MOOD_WORDS.search(scene.music):
            lint.append(Issue("warn", f"MUSIC uses the mood word \"{m.group(1)}\"; the guide wants "
                                      "instrumentation, tempo and dynamics."))
    fields = (f"integrated_multimodal_description: {' '.join(shots)}\n\n"
              f"overall_soundscape: {soundscape}\n\nnon_diegetic_music: {music}")
    align = _alignment(scene)
    return f"{align}\n\n{fields}" if align else fields


def write_flat(scene: Scene) -> str:
    if not scene.shots:
        return scene.style
    prose = " ".join(_sentence_case(_end(it)) for it in scene.shots[0].items if isinstance(it, str))
    return f"{_cap(scene.style)}, {_low(prose)}" if scene.style else prose


# --- lint that needs the whole scene --------------------------------------------------------

def _scene_lint(src: str, scene: Scene, lint: list[Issue]) -> None:
    n = len(scene.shots)
    if scene.mode not in MODES:
        lint.append(Issue("error", f"Unknown mode \"{scene.mode}\" ({', '.join(MODES)}; "
                                   "ref2va comes later)."))
    if not n:
        lint.append(Issue("error", "No SHOT yet."))
        return
    if not 4 <= scene.duration <= 15:
        lint.append(Issue("error", f"Duration {scene.duration:.2f} s is outside H3's 4–15 s."))

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


def compile_scene(src: str, seed: int, libraries: Mapping[str, Library],
                  weights: Mapping[str, float] | None = None, target: str = "h3-base") -> Compiled:
    ex = Expander(seed, libraries, weights)
    lint: list[Issue] = []
    scene = parse_scene(src, ex, lint)
    if target == "flat":
        text = write_flat(scene)
    elif target == "h3-base":
        text = write_h3_base(scene, lint)
        _scene_lint(src, scene, lint)
    else:
        raise ValueError(f"unknown target {target!r} (h3-base, flat)")
    return Compiled(text, ex.picks, lint, scene)
