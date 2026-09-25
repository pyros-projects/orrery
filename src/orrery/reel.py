"""Reels: one screenplay for a chain of H3 Motion Context clips.

    @h3 t2va 9:16
    $venue = __couture_venue__             the head is the world: it rolls once per seed
    CHUNK the opening
    $look = __couture_form__               a chunk rolls anew in every segment it plays
    SHOT 6s | tracking, slow
    …
    HANDOFF: the model reaches the end of the runway
    CHUNK the rotation repeat forever      repeat N | forever: one segment per repetition
    $look = __couture_form__
    SHOT 6s | static
    A model in $look~1 walks back while one in $look walks in.   $x~N: x as it was N clips ago

A segment is one clip. Its seed derives from the node's seed and the segment number, so every
clip is reproducible and a repeated chunk still varies; `$x~N` recomputes the earlier clip's
bindings instead of remembering them. The previous segment's handoff opens this one, its own
closes it, and from the second segment on Shot 1 also covers the frames Motion Context pins.
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
BINDING = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$")


class ReelEnd(ValueError):
    """The segment asked for comes after the last clip of a finite reel."""


@dataclass
class Block:
    title: str
    repeat: int | None = 1  # None: forever
    lines: list[str] = field(default_factory=list)


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
        else:
            (blocks[-1].lines if blocks else head).append(raw)
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

    def expander(t: int) -> tuple[Expander, Block]:
        block = reel.blocks[reel.locate(t)[0]]
        ex = Expander(derive(seed, t), libraries, weights)
        ex.vars = dict(world.vars)
        ex.var_props = dict(world.var_props)

        def back(name: str, n: int) -> str | None:
            target = max(t - n, 0)
            return ex.vars.get(name) if target >= t else history[target].get(name)

        ex.history = back
        for line in block.lines:
            if m := BINDING.match(line.strip()):
                ex.bind(m.group(1), m.group(2))
        return ex, block

    for t in range(segment + 1):
        history.append(dict(expander(t)[0].vars))

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
