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
    GOTO: the opening ×2                   after this chunk, back to that one (twice, then on)
    ? $look[kind=gown]: GOTO: the finale   a jump on what this clip rolled

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

`GOTO: <title or number> [×N]` at a chunk's end jumps instead of going on: N times (then the chunk
after it), or for good without ×N. Several GOTO lines: the first that holds and has jumps left wins;
`? cond: GOTO: …` holds on what that clip rolled. So the path through the chunks is walked clip by
clip (`Reel.walk`): which chunk a segment plays can depend on the seed.
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
GOTO_LINE = re.compile(r"^(?:\?[^\n]*?:\s*)?GOTO:", re.IGNORECASE)  # a GOTO line, with its `? cond:` or without
_GOTO = re.compile(r"GOTO:\s*(.+?)\s*(?:[×x]\s*(\d+))?\s*$", re.IGNORECASE)
MAX_WALK = 500  # clips a walk through a reel follows before it calls the reel endless
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
class Goto:
    line: str  # as written, its `? cond:` included
    target: int  # the chunk it jumps to (an index)
    count: int | None  # jumps it makes; None: every time

    @property
    def conditional(self) -> bool:
        return self.line.lstrip().startswith("?")


@dataclass
class Block:
    title: str
    repeat: int | None = 1  # None: forever
    lines: list[str] = field(default_factory=list)
    sends: list[Send] = field(default_factory=list)
    gotos: list[Goto] = field(default_factory=list)


@dataclass
class Reel:
    head: list[str]
    blocks: list[Block]
    rng: int | None = None  # `@rng 1`: the dice its template was made with

    @property
    def jumps_on_rolls(self) -> bool:
        """A `? cond: GOTO:` line: the path depends on the seed."""
        return any(g.conditional for b in self.blocks for g in b.gotos)

    def walk(self, decide=None, upto: int = MAX_WALK, on_segment=None) -> tuple[list[tuple[int, int]], bool]:
        """(chunk, repetition) of each segment from 0, and whether the reel ended within `upto`. At a
        chunk's last repetition its GOTO lines are tried in order; `decide(t, goto)` says whether a
        conditional one holds in segment t (without it, none does). `on_segment(t)` runs as each
        segment joins the path, before its chunk's GOTOs are tried."""
        path: list[tuple[int, int]] = []
        block, rep, used = 0, 0, {}
        while len(path) < upto:
            path.append((block, rep))
            if on_segment:
                on_segment(len(path) - 1, block)
            here = self.blocks[block]
            if here.repeat is None or rep + 1 < here.repeat:
                rep += 1
                continue
            nxt = block + 1
            for k, goto in enumerate(here.gotos):
                if goto.count is not None and used.get((block, k), 0) >= goto.count:
                    continue
                if goto.conditional and not (decide and decide(len(path) - 1, goto)):
                    continue
                used[(block, k)] = used.get((block, k), 0) + 1
                nxt = goto.target
                break
            if nxt >= len(self.blocks):
                return path, True
            block, rep = nxt, 0
        return path, False

    @property
    def segments(self) -> int | None:
        """Clips in the reel, counting repeats and jumps; None when it plays on and on (a chunk that
        repeats forever, a GOTO without ×N), or when a jump waits on what rolls (see `length`)."""
        if self.jumps_on_rolls:
            return None
        path, ended = self.walk()
        return len(path) if ended else None

    def locate(self, segment: int, path: list[tuple[int, int]] | None = None) -> tuple[int, int]:
        """(block index, repetition) of a segment, on `path` (a walk at a seed) or the reel's own."""
        if segment < 0:
            raise ValueError(f"segment {segment} is negative; segments count from 0.")
        if path is None:
            path, _ = self.walk(upto=segment + 1)
        if segment >= len(path):
            raise ReelEnd(f"The reel has {len(path)} segments; segment {segment} is past its end "
                          "(segments count from 0, like Load Latent's clip_index).")
        return path[segment]

    @property
    def send_slots(self) -> list[int]:
        """Every image a SEND: line fills."""
        return sorted({send.image for block in self.blocks for send in block.sends})

    def starts(self, path: list[tuple[int, int]] | None = None) -> list[int | None]:
        """The segment each chunk first plays in, on `path` or the reel's own; None for a chunk it
        never reaches (one after a chunk that repeats forever, one every GOTO jumps over)."""
        if path is None:
            path, _ = self.walk()
        out: list[int | None] = [None] * len(self.blocks)
        for t, (block, _) in enumerate(path):
            if out[block] is None:
                out[block] = t
        return out

    def ready(self, segment: int, held: set[int] | frozenset = frozenset(),
              path: list[tuple[int, int]] | None = None) -> dict[int, dict]:
        """The sent images that exist in `segment`, each with the segment its frames come from: sent by a
        chunk that first played before it, for a segment its `for` lists (any later one without). A `held`
        image (Orrery Refs' keep_sent, with a stored anchor) exists from segment 0 within its `for` list,
        and comes from that anchor instead."""
        out: dict[int, dict] = {}
        for block, start in zip(self.blocks, self.starts(path), strict=True):
            for send in block.sends:
                spans = (send.segments or [[0, None]]) if send.image in held else fills(send, start)
                if any(lo <= segment and (hi is None or segment <= hi) for lo, hi in spans):
                    out[send.image] = ({"held": True} if send.image in held
                                       else {"segment": start, "frames": [list(f) for f in send.frames]})
        return out

    def label(self, segment: int, path: list[tuple[int, int]] | None = None) -> str:
        i, rep = self.locate(segment, path)
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
    gotos: list[tuple[int, str]] = []  # (chunk, line): resolved once every title is known
    for raw in lines:
        if m := CHUNK.match(raw.strip()):
            title, repeat = m.group(1).strip(), 1
            if r := REPEAT.match(title):
                title = r.group(1).strip()
                repeat = None if r.group(2).lower() == "forever" else max(1, int(r.group(2)))
            blocks.append(Block(title, repeat))
        elif (send := SEND.match(raw.strip())) and blocks:
            blocks[-1].sends.append(parse_send(send.group(1)))
        elif GOTO_LINE.match(raw.strip()) and blocks:
            gotos.append((len(blocks) - 1, raw.strip()))
        else:
            (blocks[-1].lines if blocks else head).append(raw)
    for i, line in gotos:
        blocks[i].gotos.append(_goto(line, blocks))
    from orrery.dsl import parse

    reel = Reel(head, blocks, parse(src).params.rng)
    claims: dict[int, list[tuple[int, list]]] = {}  # image → (chunk, segment spans) of each SEND: line
    if reel.jumps_on_rolls:  # which segment a chunk starts in waits on the seed
        return reel
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


def _goto(line: str, blocks: list[Block]) -> Goto:
    m = _GOTO.search(line)
    target = m.group(1).strip() if m else ""
    if target.isdigit() and 1 <= int(target) <= len(blocks):
        index = int(target) - 1
    else:
        index = next((i for i, b in enumerate(blocks) if b.title.casefold() == target.casefold()), None)
    if index is None:
        titles = ", ".join(b.title or f"chunk {i + 1}" for i, b in enumerate(blocks))
        raise ValueError(f"{line}: no CHUNK is called {target!r} (there are {titles}; a number counts them from 1).")
    return Goto(line, index, int(m.group(2)) if m.group(2) else None)


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
            last: int, upto: int | None = None):
    """The world (its expander and its expanded lines), `expand(t)` for segments up to `last` (the
    chunk's screenplay lines as segment t rolls them: its own seed, the world's bindings, `$x~N`
    recomputed; its handoff and the picks), and the path the reel takes at this seed with whether it
    ended: walked to `last`, or to `upto` when given. A segment past the end raises ReelEnd."""
    world = Expander(seed, libraries, weights, reel.rng)
    for line in reel.head:
        if m := BINDING.match(line.strip()):
            world.bind(m.group(1), m.group(2))
    head = [world.expr(line.strip()) for line in reel.head if line.strip() and not BINDING.match(line.strip())]

    history: list[dict[str, str]] = []  # every earlier segment's bindings, recomputed
    history_props: list[dict[str, dict[str, str]]] = []  # and the fields of what they rolled, as their clips showed them

    blocks: list[int] = []  # the chunk of each segment walked so far
    rolled: dict[int, Expander] = {}

    def expander(t: int) -> tuple[Expander, Block]:
        block = reel.blocks[blocks[t]]
        ex = Expander(derive(seed, t), libraries, weights, reel.rng)
        ex.warnings = world.warnings  # one list for the whole reel
        ex.vars = dict(world.vars)
        ex.var_props = dict(world.var_props)
        ex.var_tags = dict(world.var_tags)
        ex.var_fields = dict(world.var_fields)  # the head's fields rolled once, for every clip

        def back(name: str, n: int) -> str | None:
            target = max(t - n, 0)
            return ex.vars.get(name) if target >= t else history[target].get(name)

        ex.history = back
        ex.history_props = lambda name, n: (ex.var_fields if max(t - n, 0) >= t
                                            else history_props[max(t - n, 0)]).get(name, {})
        for line in block.lines:
            if m := BINDING.match(line.strip()):
                ex.bind(m.group(1), m.group(2))
        return ex, block

    def record(t: int, block: int) -> None:
        blocks.append(block)
        rolled[t] = ex_t = expander(t)[0]
        history.append(dict(ex_t.vars))
        history_props.append(dict(ex_t.var_fields))

    def holds(t: int, goto: Goto) -> bool:  # `? cond: GOTO: …` on what segment t rolled
        return rolled[t].guarded(goto.line) is not None

    path, ended = reel.walk(holds, upto=max(last + 1, upto or 0), on_segment=record)
    if last >= len(path):
        raise ReelEnd(f"The reel has {len(path)} segments at this seed; segment {last} is past its end "
                      "(segments count from 0, like Load Latent's clip_index).")

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

    return world, head, expand, (path, ended)


def reel_path(reel: Reel, seed: int, libraries: Mapping[str, Library], weights: Mapping[str, float] | None,
              upto: int = MAX_WALK) -> tuple[list[tuple[int, int]], bool]:
    """The chunks the reel plays at `seed`, clip by clip, up to `upto` clips, and whether it ended."""
    if not reel.jumps_on_rolls:
        return reel.walk(upto=upto)
    return _unroll(reel, seed, libraries, weights, 0, upto)[3]


def resolved(reel: Reel, seed: int, libraries: Mapping[str, Library], weights: Mapping[str, float] | None,
             segments: int) -> tuple[list[str], list[dict]]:
    """The world's lines and the first `segments` segments as static screenplay lines, picks filled in:
    each {"title", "lines", "handoff"}, as the reel rendered them at `seed`. What a language model reads
    to continue the reel."""
    _, head, expand, (path, _) = _unroll(reel, seed, libraries, weights, segments - 1)
    out = []
    for t in range(segments):
        lines, handoff, _, _ = expand(t)
        out.append({"title": reel.blocks[path[t][0]].title, "lines": lines, "handoff": handoff})
    return head, out


def build_segment(reel: Reel, seed: int, libraries: Mapping[str, Library],
                  weights: Mapping[str, float] | None, segment: int,
                  lint: list[Issue]) -> tuple[Scene, list[Pick], list[tuple[int, int]]]:
    """Segment `segment` of the reel as a scene, with the picks that went into it and the path the reel
    took to it."""
    if segment < 0:
        raise ValueError(f"segment {segment} is negative; segments count from 0.")
    forever = next((i for i, b in enumerate(reel.blocks) if b.repeat is None), None)
    if forever is not None and forever < len(reel.blocks) - 1 and not reel.blocks[forever].gotos:
        lint.append(Issue("warn", f"CHUNK {forever + 1} repeats forever, so the "
                                  f"{len(reel.blocks) - forever - 1} CHUNK(s) after it never play."))
    elif not reel.jumps_on_rolls and any(b.gotos for b in reel.blocks):
        never = [i + 1 for i, start in enumerate(reel.starts()) if start is None]
        if never:
            lint.append(Issue("warn", f"The GOTO lines jump past CHUNK {', '.join(map(str, never))}: "
                                      "it never plays."))

    world, head, expand, (path, _) = _unroll(reel, seed, libraries, weights, segment)
    lines, handoff, picks, _ = expand(segment)
    before, before_picks = (expand(segment - 1)[1::2] if segment else (None, []))
    lint += [Issue("warn", w) for w in world.warnings]
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
    return scene, world.picks + picks + before_picks, path
