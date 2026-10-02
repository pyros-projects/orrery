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
    SEND: frame -1 to image 4 for segment 6+          its last frame, only for segments 6, 7, 8 …

A segment is one clip. Its seed derives from the node's seed and the segment number, so every
clip is reproducible and a repeated chunk still varies; `$x~N` recomputes the earlier clip's
bindings instead of remembering them. The previous segment's handoff opens this one, its own
closes it, and from the second segment on Shot 1 also covers the frames Motion Context pins.

`SEND:` hands frames of a chunk's clip (counted from 0 in the clip Chain Video keeps, the pinned
frames trimmed off; -1 is the last) to later clips as a reference image, the CAST's `image N`;
several frames make one image batch. A chunk that repeats sends from the first time it plays.
`for segment 4+` / `4, 6, 7` / `2-5` limits the clips that get it, so several lines may fill one
image in turns. Orrery Refs fetches the frames; where they do not exist, the compiler leaves the
image out of the clip.
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
_FOR = re.compile(r"\s+for\s+", re.IGNORECASE)
_TARGET = re.compile(r"^image\s+(\d+)$", re.IGNORECASE)
_FRAMES = re.compile(r"(-?\d+)(?:\s*-\s*(-?\d+))?")
_SEGMENTS = re.compile(r"^segments?\b\s*(.*)$", re.IGNORECASE)
_SEGMENT = re.compile(r"(\d+)(?:\s*(\+)|\s*-\s*(\d+))?")
SEND_SLOTS = 9  # Reference to Video takes nine reference images, ref_image_0 to ref_image_8
MAX_SEND_FRAMES = 3600  # the longest clip Reference to Video makes
BINDING = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$")


class ReelEnd(ValueError):
    """The segment asked for comes after the last clip of a finite reel."""


@dataclass
class Send:
    frames: list[list[int]]  # [first, last] spans in the order written; negative counts from the clip's end
    image: int  # the reference image they become: the CAST's `image N`
    segments: list[list[int | None]] | None = None  # `for segment …`: [lo, hi] spans, hi None for `N+`


def parse_frames(spec: str) -> list[list[int]]:
    """`2, 5, 34-46, -24--1` → [[2, 2], [5, 5], [34, 46], [-24, -1]]: resolved against the clip's length
    when Orrery Refs reads it, so -1 is the last frame and 10--1 runs from frame 10 to the end."""
    spans: list[list[int]] = []
    total = 0
    for part in (p.strip() for p in spec.split(",")):
        m = _FRAMES.fullmatch(part)
        if not m:
            raise ValueError(f'SEND: "{part}" is not a frame; frames are numbers from 0 (-1 the last), '
                             "or ranges like 34-46 and -24--1.")
        first = int(m.group(1))
        last = int(m.group(2)) if m.group(2) is not None else first
        if (first < 0) == (last < 0):
            if last < first:
                raise ValueError(f"SEND: the range {part} runs backwards; write it as {last}-{first}.")
            total += last - first + 1
            if total > MAX_SEND_FRAMES:
                raise ValueError(f"SEND: {spec} names more than {MAX_SEND_FRAMES} frames, longer than any clip.")
        spans.append([first, last])
    return spans


def parse_segments(text: str) -> list[list[int | None]]:
    """`segment 4+` → [[4, None]]; `segments 2, 4-8, 12` → [[2, 2], [4, 8], [12, 12]]."""
    m = _SEGMENTS.match(text.strip())
    if not m or not m.group(1).strip():
        raise ValueError('SEND: "for" takes segments: "for segment 4+", "for segments 4, 6, 7" or "for segments 2-5".')
    spans: list[list[int | None]] = []
    for part in (p.strip() for p in m.group(1).split(",")):
        s = _SEGMENT.fullmatch(part)
        if not s:
            raise ValueError(f'SEND: "{part}" is not a segment; segments count from 0: 4, 4+ (and on), 4-8.')
        lo = int(s.group(1))
        hi = None if s.group(2) else int(s.group(3) or s.group(1))
        if hi is not None and hi < lo:
            raise ValueError(f"SEND: the segments {part} run backwards; write them as {hi}-{lo}.")
        spans.append([lo, hi])
    return spans


def parse_send(text: str) -> Send:
    body, *rest = _FOR.split(text.strip(), maxsplit=1)
    segments = parse_segments(rest[0]) if rest else None
    m = _SEND.match(body)
    if not m or not m.group("frames"):
        raise ValueError(f'"SEND: {text.strip()}": write it as "SEND: frame 0 to image 3" '
                         'or "SEND: frames 2, 5, 34-46 to image 4".')
    target = _TARGET.match(m.group("target"))
    if not target:
        raise ValueError(f'SEND: sends to "image N" (the numbering of the CAST), not to "{m.group("target")}".')
    image = int(target.group(1))
    if not 1 <= image <= SEND_SLOTS:
        raise ValueError(f"SEND: image {image} does not exist; Reference to Video takes image 1–{SEND_SLOTS}.")
    return Send(parse_frames(m.group("frames")), image, segments)


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
        return sorted({send.image for block in self.blocks for send in block.sends})

    def starts(self) -> list[int | None]:
        """The segment each chunk first plays in; None for chunks after one that repeats forever."""
        out: list[int | None] = []
        start: int | None = 0
        for block in self.blocks:
            out.append(start)
            if start is not None:
                start = None if block.repeat is None else start + block.repeat
        return out

    def ready(self, segment: int, held: set[int] | frozenset = frozenset()) -> dict[int, dict]:
        """The sent images that exist in `segment`, each with the segment its frames come from: sent by a
        chunk that first played before it, for a segment its `for` lists (any later one without). A `held`
        image (Orrery Refs' keep_sent, with a stored anchor) exists from segment 0 within its `for` list,
        and comes from that anchor instead."""
        out: dict[int, dict] = {}
        for block, start in zip(self.blocks, self.starts(), strict=True):
            for send in block.sends:
                spans = (send.segments or [[0, None]]) if send.image in held else fills(send, start)
                if any(lo <= segment and (hi is None or segment <= hi) for lo, hi in spans):
                    out[send.image] = ({"held": True} if send.image in held
                                       else {"segment": start, "frames": [list(f) for f in send.frames]})
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
    reel = Reel(head, blocks)
    claims: dict[int, list[tuple[int, list]]] = {}  # image → (chunk, segment spans) of each SEND: line
    for i, (block, start) in enumerate(zip(blocks, reel.starts(), strict=True)):
        for send in block.sends:
            spans = fills(send, start)
            for j, other in claims.get(send.image, []):
                for (lo, hi), (olo, ohi) in ((a, b) for a in spans for b in other):
                    first, ends = max(lo, olo), [x for x in (hi, ohi) if x is not None]
                    if first <= min(ends, default=first):
                        raise ValueError(f"image {send.image} is sent for segment {first} by two SEND: lines (CHUNK "
                                         f"{j + 1} and CHUNK {i + 1}); give each segment one, with for segment ….")
            claims.setdefault(send.image, []).append((i, spans))
    return reel


def fills(send: Send, start: int | None) -> list[list[int | None]]:
    """The segments a SEND: line fills: those its `for` lists (all, without) after the one it is sent from."""
    if start is None:
        return []
    first = start + 1
    return [[max(lo, first), hi] for lo, hi in (send.segments or [[first, None]]) if hi is None or hi >= max(lo, first)]


def derive(seed: int, segment: int) -> int:
    """A segment's own seed: stable, and unrelated between neighbouring segments."""
    return int.from_bytes(hashlib.sha256(f"orrery-reel:{seed}:{segment}".encode()).digest()[:4], "big")


def _unroll(reel: Reel, seed: int, libraries: Mapping[str, Library], weights: Mapping[str, float] | None,
            last: int):
    """The world (its expander and its expanded lines) and `expand(t)` for segments up to `last`: the
    chunk's screenplay lines as segment t rolls them (its own seed, the world's bindings, `$x~N`
    recomputed), its handoff and the picks."""
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

    for t in range(last + 1):
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

    return world, head, expand


def resolved(reel: Reel, seed: int, libraries: Mapping[str, Library], weights: Mapping[str, float] | None,
             segments: int) -> tuple[list[str], list[dict]]:
    """The world's lines and the first `segments` segments as static screenplay lines, picks filled in:
    each {"title", "lines", "handoff"}, as the reel rendered them at `seed`. What a language model reads
    to continue the reel."""
    _, head, expand = _unroll(reel, seed, libraries, weights, segments - 1)
    out = []
    for t in range(segments):
        lines, handoff, _, _ = expand(t)
        out.append({"title": reel.blocks[reel.locate(t)[0]].title, "lines": lines, "handoff": handoff})
    return head, out


def build_segment(reel: Reel, seed: int, libraries: Mapping[str, Library],
                  weights: Mapping[str, float] | None, segment: int,
                  lint: list[Issue]) -> tuple[Scene, list[Pick]]:
    """Segment `segment` of the reel as a scene, with the picks that went into it."""
    reel.locate(segment)
    forever = next((i for i, b in enumerate(reel.blocks) if b.repeat is None), None)
    if forever is not None and forever < len(reel.blocks) - 1:
        lint.append(Issue("warn", f"CHUNK {forever + 1} repeats forever, so the "
                                  f"{len(reel.blocks) - forever - 1} CHUNK(s) after it never play."))

    world, head, expand = _unroll(reel, seed, libraries, weights, segment)
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
