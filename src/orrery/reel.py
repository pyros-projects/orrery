"""Reels: one screenplay for a chain of H3 Motion Context clips.

    @h3 t2va 9:16
    $venue = __couture_venue__             the head is the world: it rolls once per seed
    CHUNK the opening
    $look = __couture_form__               a chunk rolls anew in every segment it plays
    SHOT 6s: tracking, slow
    …
    HANDOFF: the model reaches the end of the runway
    CHUNK the rotation repeat forever      repeat N | forever: one segment per repetition
    $look = __couture_form__
    SHOT 6s: static
    A model in $look~1 walks back while one in $look walks in.   $x~N: x as it was N clips ago
    SEND: frame 0 to image 3               this clip's frame 0 is image 3 for every later clip

A segment is one clip. Its seed derives from the node's seed and the segment number, so every
clip is reproducible and a repeated chunk still varies; `$x~N` recomputes the earlier clip's
bindings instead of remembering them. The previous segment's handoff opens this one, its own
closes it, and from the second segment on Shot 1 also covers the frames Motion Context pins.

`SEND:` hands frames of a chunk's clip (counted from 0 in the clip Chain Video keeps, the pinned
frames trimmed off) to later clips as a reference image, the CAST's `image N`; several frames make
one image batch. A chunk that repeats sends from the first time it plays. Orrery Refs fetches the
frames; until they exist, the compiler leaves the image out of the clip.
"""

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from orrery.dsl import Expander, Pick
from orrery.h3 import DEFAULT_CONTEXT, H3_FPS, Issue, Scene, _clause, parse_scene
from orrery.library import Library

CHUNK = re.compile(r"^CHUNK\b\s*(.*)$")
REPEAT = re.compile(r"^(.*?)\s*\brepeat\s+(\d+|forever)\s*$", re.IGNORECASE)
HANDOFF = re.compile(r"^HANDOFF:\s*(.+)$")
SEND = re.compile(r"^SEND:\s*(.*)$")
_SEND = re.compile(r"^frames?\b\s*(?P<frames>.*?)\s*\bto\s+(?P<target>.+?)\s*$", re.IGNORECASE)
_TARGET = re.compile(r"^image\s+(\d+)$", re.IGNORECASE)
_FRAMES = re.compile(r"(\d+)(?:\s*-\s*(\d+))?")
SEND_SLOTS = 9  # Reference to Video takes nine reference images, ref_image_0 to ref_image_8
MAX_SEND_FRAMES = 3600  # the longest clip Reference to Video makes
BINDING = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$")


class ReelEnd(ValueError):
    """The segment asked for comes after the last clip of a finite reel."""


@dataclass
class Send:
    frames: list[int]  # counted from 0 in the chunk's clip, in the order written
    image: int  # the reference image they become: the CAST's `image N`


def parse_frames(spec: str) -> list[int]:
    """`2, 5, 34-46` → [2, 5, 34, 35, …, 46]."""
    frames: list[int] = []
    for part in (p.strip() for p in spec.split(",")):
        m = _FRAMES.fullmatch(part)
        if not m:
            raise ValueError(f'SEND: "{part}" is not a frame; frames are numbers from 0, or ranges like 34-46.')
        first, last = int(m.group(1)), int(m.group(2) or m.group(1))
        if last < first:
            raise ValueError(f"SEND: the range {part} runs backwards; write it as {last}-{first}.")
        frames.extend(range(first, last + 1))
        if len(frames) > MAX_SEND_FRAMES:
            raise ValueError(f"SEND: {spec} names more than {MAX_SEND_FRAMES} frames, longer than any clip.")
    return frames


def parse_send(text: str) -> Send:
    m = _SEND.match(text.strip())
    if not m or not m.group("frames"):
        raise ValueError(f'"SEND: {text.strip()}": write it as "SEND: frame 0 to image 3" '
                         'or "SEND: frames 2, 5, 34-46 to image 4".')
    target = _TARGET.match(m.group("target"))
    if not target:
        raise ValueError(f'SEND: sends to "image N" (the numbering of the CAST), not to "{m.group("target")}".')
    image = int(target.group(1))
    if not 1 <= image <= SEND_SLOTS:
        raise ValueError(f"SEND: image {image} does not exist; Reference to Video takes image 1–{SEND_SLOTS}.")
    return Send(parse_frames(m.group("frames")), image)


@dataclass
class Block:
    title: str
    repeat: int | None = 1  # None: forever
    lines: list[str] = field(default_factory=list)
    sends: list[Send] = field(default_factory=list)


@dataclass
class Reel:
    head: list[str]
    blocks: list[Block]

    @property
    def segments(self) -> int | None:
        """Clips in the reel, counting repeats; None when a chunk repeats forever."""
        total = 0
        for block in self.blocks:
            if block.repeat is None:
                return None
            total += block.repeat
        return total

    def locate(self, segment: int) -> tuple[int, int]:
        """(block index, repetition) of a segment."""
        if segment < 0:
            raise ValueError(f"segment {segment} is negative; segments count from 0.")
        start = 0
        for i, block in enumerate(self.blocks):
            if block.repeat is None or segment < start + block.repeat:
                return i, segment - start
            start += block.repeat
        raise ReelEnd(f"The reel has {self.segments} segments; segment {segment} is past its end "
                      "(segments count from 0, like Load Latent's clip_index).")

    @property
    def send_slots(self) -> list[int]:
        """Every image a SEND: line fills."""
        return sorted(send.image for block in self.blocks for send in block.sends)

    def ready(self, segment: int) -> dict[int, dict]:
        """The sent images that exist in `segment`: those of chunks that first played before it, each
        with the segment its frames come from."""
        out: dict[int, dict] = {}
        start = 0
        for block in self.blocks:
            if start >= segment:
                break
            for send in block.sends:
                out[send.image] = {"segment": start, "frames": list(send.frames)}
            if block.repeat is None:
                break
            start += block.repeat
        return out

    def label(self, segment: int) -> str:
        i, rep = self.locate(segment)
        block = self.blocks[i]
        name = block.title or f"chunk {i + 1}"
        if block.repeat == 1:
            return name
        return f"{name} {rep + 1}/{'∞' if block.repeat is None else block.repeat}"


def split_reel(src: str) -> Reel | None:
    """The reel in a template, or None when it has no CHUNK line."""
    lines = src.splitlines()
    if not any(CHUNK.match(line.strip()) for line in lines):
        return None
    head: list[str] = []
    blocks: list[Block] = []
    for raw in lines:
        if m := CHUNK.match(raw.strip()):
            title, repeat = m.group(1).strip(), 1
            if r := REPEAT.match(title):
                title = r.group(1).strip()
                repeat = None if r.group(2).lower() == "forever" else max(1, int(r.group(2)))
            blocks.append(Block(title, repeat))
        elif (send := SEND.match(raw.strip())) and blocks:
            blocks[-1].sends.append(parse_send(send.group(1)))
        else:
            (blocks[-1].lines if blocks else head).append(raw)
    sender: dict[int, int] = {}
    for i, block in enumerate(blocks):
        for send in block.sends:
            if send.image in sender:
                raise ValueError(f"image {send.image} is sent twice (CHUNK {sender[send.image] + 1} and CHUNK {i + 1}); "
                                 "each image comes from one SEND: line.")
            sender[send.image] = i
    return Reel(head, blocks)


def derive(seed: int, segment: int) -> int:
    """A segment's own seed: stable, and unrelated between neighbouring segments."""
    return int.from_bytes(hashlib.sha256(f"orrery-reel:{seed}:{segment}".encode()).digest()[:4], "big")


def build_segment(reel: Reel, seed: int, libraries: Mapping[str, Library],
                  weights: Mapping[str, float] | None, segment: int,
                  lint: list[Issue]) -> tuple[Scene, list[Pick]]:
    """Segment `segment` of the reel as a scene, with the picks that went into it."""
    reel.locate(segment)
    forever = next((i for i, b in enumerate(reel.blocks) if b.repeat is None), None)
    if forever is not None and forever < len(reel.blocks) - 1:
        lint.append(Issue("warn", f"CHUNK {forever + 1} repeats forever, so the "
                                  f"{len(reel.blocks) - forever - 1} CHUNK(s) after it never play."))

    world = Expander(seed, libraries, weights)
    for line in reel.head:
        if m := BINDING.match(line.strip()):
            world.bind(m.group(1), m.group(2))
    head = [world.expr(line.strip()) for line in reel.head if line.strip() and not BINDING.match(line.strip())]

    history: list[dict[str, str]] = []  # every earlier segment's bindings, recomputed
    history_props: list[dict[str, dict[str, str]]] = []  # and the properties of what they rolled

    def expander(t: int) -> tuple[Expander, Block]:
        block = reel.blocks[reel.locate(t)[0]]
        ex = Expander(derive(seed, t), libraries, weights)
        ex.vars = dict(world.vars)
        ex.var_props = dict(world.var_props)

        def back(name: str, n: int) -> str | None:
            target = max(t - n, 0)
            return ex.vars.get(name) if target >= t else history[target].get(name)

        ex.history = back
        ex.history_props = lambda name, n: (ex.var_props if max(t - n, 0) >= t
                                            else history_props[max(t - n, 0)]).get(name, {})
        for line in block.lines:
            if m := BINDING.match(line.strip()):
                ex.bind(m.group(1), m.group(2))
        return ex, block

    for t in range(segment + 1):
        ex_t = expander(t)[0]
        history.append(dict(ex_t.vars))
        history_props.append(dict(ex_t.var_props))

    def expand(t: int) -> tuple[list[str], str | None, list[Pick], list[Pick]]:
        ex, block = expander(t)
        lines, handoff, handoff_picks = [], None, []
        for raw in block.lines:
            line = raw.strip()
            if not line or BINDING.match(line):
                continue
            if m := HANDOFF.match(line):
                before = len(ex.picks)
                handoff = ex.expr(m.group(1)).strip().rstrip(".")
                handoff_picks = ex.picks[before:]
            else:
                lines.append(ex.expr(line))
        return lines, handoff, ex.picks, handoff_picks

    lines, handoff, picks, _ = expand(segment)
    before, before_picks = (expand(segment - 1)[1::2] if segment else (None, []))
    scene = parse_scene("\n".join(head + lines), Expander(0, {}), lint, expanded=True)
    if scene.shots and before:
        scene.shots[0].items.insert(0, f"The shot opens as {_clause(before)}")
    if scene.shots and handoff:
        scene.shots[-1].items.append(f"The shot ends as {_clause(handoff)}")
    context = DEFAULT_CONTEXT if scene.context is None else scene.context
    if scene.shots and segment and context:
        scene.shots[0].duration += context / H3_FPS
    t = 0.0
    for shot in scene.shots:
        shot.start, t = t, t + shot.duration
    return scene, world.picks + picks + before_picks
