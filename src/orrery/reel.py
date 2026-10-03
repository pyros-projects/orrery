"""Reels: one screenplay for a chain of H3 Motion Context clips.

    @h3 text 9:16
    $venue = __couture_venue__             the head is the world: it rolls once per seed
    SCENE the opening
    $look = __couture_form__               a scene rolls anew in every segment it plays
    SHOT 6s: tracking, slow
    …
    END ON: the model reaches the end of the runway
    SCENE the rotation forever             ×N | forever: one segment per repetition
    $look = __couture_form__
    SHOT 6s: static
    A model in $look~1 walks back while one in $look walks in.   $x~N: x as it was N clips ago
    SEND: frame 0 to image 3               this clip's frame 0 is image 3 for every later clip
    SEND: frame -1 to image 4 for segment 6+          its last frame, only for segments 6, 7, 8 …
    CUT TO: the opening ×2                 after this scene, back to that one (twice, then on)
    ? $look[kind=gown]: CUT TO: the finale   a jump on what this clip rolled

The words of an earlier orrery keep working, with the same dice: CHUNK for SCENE, `repeat N` and
`repeat forever` for ×N and forever, HANDOFF: for END ON:, GOTO: for CUT TO:.

A segment is one clip. Its seed derives from the node's seed and the segment number, so every
clip is reproducible and a repeated scene still varies; `$x~N` recomputes the earlier clip's
bindings instead of remembering them. The previous segment's END ON: opens this one, its own
closes it, and from the second segment on Shot 1 also covers the frames Motion Context pins.

`SEND:` hands frames of a scene's clip (counted from 0 in the clip Chain Video keeps, the pinned
frames trimmed off; -1 is the last) to later clips as a reference image, the CAST's `image N`;
several frames make one image batch. A scene that repeats sends from the first time it plays.
`for segment 4+` / `4, 6, 7` / `2-5` limits the clips that get it, so several lines may fill one
image in turns. Orrery Refs fetches the frames; where they do not exist, the compiler leaves the
image out of the clip.

`CUT TO: <title or number> [×N] [(30%)]` at a scene's end jumps instead of going on: N times (then
the scene after it), or for good without ×N; with a chance, only that often. Several CUT TO: lines:
the first that holds and has jumps left wins; `? cond: CUT TO: …` holds on what that clip rolled. So the path through the scenes is walked
clip by clip (`Reel.walk`): which scene a segment plays can depend on the seed.

`AFTER: <title or number>` in a scene makes it continue the last clip of that scene instead of the
clip before it, so many scenes can branch off one clip (each with its own `SET:`): its opening
sentence, the frames Orrery Continue pins, `$x~N` and what was sent follow that chain. A scene that
repeats continues itself from its second time on.

`SCENE the forest (test)` is a test scene: rendered and kept, but Orrery Film leaves it out of the
film. It starts afresh (unless an `AFTER:` names a scene), and a scene after it continues the last
clip that is in the film. What it sends and rolls reaches the clips after it all the same: the
memory follows the clips in order, the picture follows the film (`Reel.recalls`, `Reel.before`).
"""

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from orrery.dsl import Expander, Pick, question
from orrery.h3 import DEFAULT_CONTEXT, H3_FPS, Issue, Scene, _clause, parse_scene
from orrery.library import Library

CHUNK = re.compile(r"^(?:SCENE|CHUNK)\b\s*(.*)$")  # a scene's heading; CHUNK is the earlier word
REPEAT = re.compile(r"^(.*?)\s*(?:\brepeat\s+(\d+|forever)|(?<!\S)[×x]\s*(\d+)|(?<!\S)(forever))\s*$", re.IGNORECASE)
HANDOFF = re.compile(r"^(?:END ON|HANDOFF):\s*(.+)$")
SEND = re.compile(r"^SEND:\s*(.*)$")
AFTER = re.compile(r"^AFTER:\s*(.*)$")
TEST = re.compile(r"(?<!\S)\(test\)(?!\S)", re.IGNORECASE)  # `SCENE the forest (test)`
GOTO_LINE = re.compile(r"^(?:(?:\?|IF\s+(?=\$))[^\n]*?:\s*)?(?:CUT\s+TO|GOTO):", re.IGNORECASE)  # a cut, `? cond:` / `IF …:` or not
_GOTO = re.compile(r"(?:CUT\s+TO|GOTO):\s*(.+?)\s*(?:[×x]\s*(\d+))?\s*$", re.IGNORECASE)
_CUT_CHANCE = re.compile(r"\s*\((\d+(?:\.\d+)?)\s*%\)")  # `CUT TO: the fight (30%)`
MAX_WALK = 500  # clips a walk through a reel follows before it calls the reel endless
_SEND = re.compile(r"^(?:frames?\b\s*(?P<frames>.*?)|every\s+(?P<every>\d+)(?:st|nd|rd|th)?\s+frames?)"
                   r"\s*\bto\s+(?P<target>.+?)\s*$", re.IGNORECASE)
_FOR = re.compile(r"\s+for\s+", re.IGNORECASE)
_TARGET = re.compile(r"^(?:image\s+(?P<image>\d+)|refmod\s+(?P<refmod>[\w./-]+))$", re.IGNORECASE)
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
    image: int | None  # the reference image they become: the CAST's `image N`; None for a RefMod
    segments: list[list[int | None]] | None = None  # `for segment …`: [lo, hi] spans, hi None for `N+`
    refmod: str | None = None  # `to refmod NAME`: the frames become a RefMod of that name
    step: int = 1  # `every 10 frames`: every 10th frame of the spans

    @property
    def target(self) -> int | str:
        """What it fills: an image's number, or a RefMod's name."""
        return self.image if self.refmod is None else self.refmod

    @property
    def what(self) -> str:
        return f"image {self.image}" if self.refmod is None else f"refmod {self.refmod}"


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
    if not m or not (m.group("frames") or m.group("every")):
        raise ValueError(f'"SEND: {text.strip()}": write it as "SEND: frame 0 to image 3", '
                         '"SEND: frames 2, 5, 34-46 to image 4" or "SEND: every 10 frames to refmod NAME".')
    target = _TARGET.match(m.group("target"))
    if not target:
        raise ValueError(f'SEND: sends to "image N" (the numbering of the CAST) or to "refmod NAME", not to '
                         f'"{m.group("target")}".')
    step = int(m.group("every") or 1)
    if step < 1:
        raise ValueError("SEND: every 0 frames sends nothing; write every 1 frame or more.")
    frames = [[0, -1]] if m.group("every") else parse_frames(m.group("frames"))
    if target.group("refmod"):
        return Send(frames, None, segments, refmod=target.group("refmod"), step=step)
    image = int(target.group("image"))
    if not 1 <= image <= SEND_SLOTS:
        raise ValueError(f"SEND: image {image} does not exist; Reference to Video takes image 1–{SEND_SLOTS}.")
    return Send(frames, image, segments, step=step)


@dataclass
class Goto:
    line: str  # as written, its `? cond:` included
    target: int  # the chunk it jumps to (an index)
    count: int | None  # jumps it makes; None: every time
    chance: float | None = None  # `(30%)`: how often it holds, rolled each time it is tried

    @property
    def conditional(self) -> bool:
        return question(self.line).lstrip().startswith("?")

    @property
    def rolls(self) -> bool:
        """Whether it holds on what rolls: a `? cond:` or a chance."""
        return self.conditional or self.chance is not None


@dataclass
class Block:
    title: str
    repeat: int | None = 1  # None: forever
    lines: list[str] = field(default_factory=list)
    sends: list[Send] = field(default_factory=list)
    gotos: list[Goto] = field(default_factory=list)
    after: int | None = None  # `AFTER:`: the scene it continues (an index); None: the clip before
    test: bool = False  # `(test)`: rendered and kept, left out of the film


@dataclass
class Reel:
    head: list[str]
    blocks: list[Block]
    rng: int | None = None  # `@rng 1`: the dice its template was made with

    @property
    def jumps_on_rolls(self) -> bool:
        """A `? cond: CUT TO:` line or a cut with a chance: the path depends on the seed."""
        return any(g.rolls for b in self.blocks for g in b.gotos)

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
                on_segment(len(path) - 1, block, rep)
            here = self.blocks[block]
            if here.repeat is None or rep + 1 < here.repeat:
                rep += 1
                continue
            nxt = block + 1
            for k, goto in enumerate(here.gotos):
                if goto.count is not None and used.get((block, k), 0) >= goto.count:
                    continue
                if goto.rolls and not (decide and decide(len(path) - 1, goto)):
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
            raise ReelEnd(f"The reel has {len(path)} clips; segment {segment} (clip {segment + 1}) is past its end "
                          "(the segment counts from 0, like Load Latent's clip_index).")
        return path[segment]

    def before(self, segment: int, path: list[tuple[int, int]]) -> int | None:
        """The segment whose picture `segment` continues (its pinned frames, its END ON:), on `path`: with
        `AFTER:` the last clip of that scene, else the last clip before it that is in the film. None for
        the first clip and for a test scene without `AFTER:`, which start afresh."""
        if segment == 0:
            return None
        block, rep = path[segment]
        here = self.blocks[block]
        if rep:
            return segment - 1
        if here.after is not None:
            last = next((t for t in range(segment - 1, -1, -1) if path[t][0] == here.after), None)
            if last is None:
                raise ValueError(f"SCENE {block + 1} continues SCENE {here.after + 1} (AFTER:), which has not played "
                                 f"before clip {segment + 1}.")
            return last
        if here.test:
            return None
        return next((t for t in range(segment - 1, -1, -1) if not self.blocks[path[t][0]].test), None)

    def recalls(self, segment: int, path: list[tuple[int, int]]) -> int | None:
        """The segment whose memory `segment` carries on (what was sent, `$x~N`): the one it continues
        with `AFTER:`, so a branch keeps its own; else the clip before it, a test scene's too."""
        if segment and self.blocks[path[segment][0]].after is not None:
            return self.before(segment, path)
        return segment - 1 if segment else None

    def chain(self, segment: int, path: list[tuple[int, int]]) -> list[int]:
        """The segments whose memory `segment` carries on, nearest first: `recalls` again and again."""
        out, t = [], self.recalls(segment, path)
        while t is not None:
            out.append(t)
            t = self.recalls(t, path)
        return out

    @property
    def send_slots(self) -> list[int]:
        """Every image a SEND: line fills."""
        return sorted({send.image for block in self.blocks for send in block.sends if send.refmod is None})

    @property
    def send_refmods(self) -> list[str]:
        """Every RefMod a SEND: line makes."""
        return sorted({send.refmod for block in self.blocks for send in block.sends if send.refmod is not None})

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
        chunk that first played before it, for a segment its `for` lists (any later one without). When
        several SEND: lines fill one image there, the one sent last wins (a later line within a chunk).
        A `held` image (Orrery Refs' keep_sent, with a stored anchor) exists from segment 0 within its
        `for` list, and comes from that anchor instead."""
        return self._ready(segment, held, path, refmods=False)

    def refmods_ready(self, segment: int, path: list[tuple[int, int]] | None = None) -> dict[str, dict]:
        """The sent RefMods that exist in `segment`, by the rules of `ready`: from the clip after the
        sending one (or in the segments its `for` lists), the one sent last winning."""
        return self._ready(segment, frozenset(), path, refmods=True)

    def _ready(self, segment: int, held, path, refmods: bool) -> dict:
        out: dict = {}
        latest: dict = {}  # target → the segment its winning send so far comes from
        if path is None:
            path, _ = self.walk(upto=segment + 1)
        # what this clip continues; past the reel's end, every clip before it
        behind = set(self.chain(segment, path)) if segment < len(path) else set(range(segment))
        for block, start in zip(self.blocks, self.starts(path), strict=True):
            for send in block.sends:
                if (send.refmod is not None) != refmods:
                    continue
                key = send.target
                spans = (send.segments or [[0, None]]) if key in held else fills(send, start)
                when = -1 if start is None else start
                if (any(lo <= segment and (hi is None or segment <= hi) for lo, hi in spans)
                        and (key in held or start in behind) and when >= latest.get(key, -1)):
                    latest[key] = when
                    out[key] = ({"held": True} if key in held
                                else {"segment": start, "frames": [list(f) for f in send.frames],
                                      **({"step": send.step} if send.step > 1 else {})})
        return out

    def label(self, segment: int, path: list[tuple[int, int]] | None = None) -> str:
        i, rep = self.locate(segment, path)
        block = self.blocks[i]
        name = block.title or f"scene {i + 1}"
        if block.repeat == 1:
            return name
        return f"{name} {rep + 1}/{'∞' if block.repeat is None else block.repeat}"


def split_reel(src: str) -> Reel | None:
    """The reel in a template, or None when it has no SCENE line."""
    lines = src.splitlines()
    if not any(CHUNK.match(line.strip()) for line in lines):
        return None
    head: list[str] = []
    blocks: list[Block] = []
    gotos: list[tuple[int, str]] = []  # (chunk, line): resolved once every title is known
    afters: list[tuple[int, str]] = []  # (chunk, what its AFTER: names), the same
    for raw in lines:
        if m := CHUNK.match(raw.strip()):
            heading, repeat = m.group(1).strip(), 1
            title = " ".join(TEST.sub(" ", heading).split())
            if r := REPEAT.match(title):
                title, times = r.group(1).strip(), r.group(2) or r.group(3) or "forever"
                repeat = None if times.lower() == "forever" else max(1, int(times))
            blocks.append(Block(title, repeat, test=bool(TEST.search(heading))))
        elif (send := SEND.match(raw.strip())) and blocks:
            blocks[-1].sends.append(parse_send(send.group(1)))
        elif GOTO_LINE.match(raw.strip()) and blocks:
            gotos.append((len(blocks) - 1, raw.strip()))
        elif (after := AFTER.match(raw.strip())) and blocks:
            afters.append((len(blocks) - 1, after.group(1).strip()))
        else:
            (blocks[-1].lines if blocks else head).append(raw)
    for i, line in gotos:
        blocks[i].gotos.append(_goto(line, blocks))
    for i, name in afters:
        index = _scene(name, blocks)
        if index is None or index == i:
            problem = "a scene cannot continue itself" if index == i else f"no SCENE is called {name!r}"
            titles = ", ".join(b.title or f"scene {k + 1}" for k, b in enumerate(blocks))
            raise ValueError(f"AFTER: {name}: {problem} (there are {titles}; a number counts them from 1).")
        blocks[i].after = index
    from orrery.dsl import parse

    return Reel(head, blocks, parse(src).params.rng)


def shared_sends(reel: Reel, starts: list[int | None]) -> list[str]:
    """A warning for each two SEND: lines that fill one image in the same segment: there the one sent
    last takes over (Reel.ready)."""
    out: list[str] = []
    claims: dict = {}  # image or RefMod → (chunk, start, spans) per line
    for i, (block, start) in enumerate(zip(reel.blocks, starts, strict=True)):
        for send in block.sends:
            spans = fills(send, start)
            for j, other_start, other in claims.get((send.refmod is None, send.target), []):
                shared = [max(lo, olo) for lo, hi in spans for olo, ohi in other
                          if max(lo, olo) <= min([x for x in (hi, ohi) if x is not None], default=max(lo, olo))]
                if shared:
                    later = i if start >= other_start else j
                    out.append(f"{send.what} is filled by two SEND: lines in clip {min(shared) + 1} (SCENE "
                               f"{j + 1} and SCENE {i + 1}): where they meet, the one sent last (SCENE {later + 1}) "
                               "takes over.")
            claims.setdefault((send.refmod is None, send.target), []).append((i, start, spans))
    return out


def _scene(name: str, blocks: list[Block]) -> int | None:
    """The scene a CUT TO: or AFTER: names, by its number from 1 or its title."""
    if name.isdigit() and 1 <= int(name) <= len(blocks):
        return int(name) - 1
    return next((i for i, b in enumerate(blocks) if b.title.casefold() == name.casefold()), None)


def _goto(line: str, blocks: list[Block]) -> Goto:
    chance = _CUT_CHANCE.search(line)
    m = _GOTO.search(_CUT_CHANCE.sub("", line))
    target = m.group(1).strip() if m else ""
    index = _scene(target, blocks)
    if index is None:
        titles = ", ".join(b.title or f"scene {i + 1}" for i, b in enumerate(blocks))
        raise ValueError(f"{line}: no SCENE is called {target!r} (there are {titles}; a number counts them from 1).")
    return Goto(line, index, int(m.group(2)) if m.group(2) else None,
                min(float(chance.group(1)) / 100, 1.0) if chance else None)


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

    walked: list[tuple[int, int]] = []  # (scene, repetition) of each segment walked so far
    rolled: dict[int, Expander] = {}

    def expander(t: int) -> tuple[Expander, Block]:
        block = reel.blocks[walked[t][0]]
        ex = Expander(derive(seed, t), libraries, weights, reel.rng)
        ex.warnings = world.warnings  # one list for the whole reel
        ex.vars = dict(world.vars)
        ex.var_props = dict(world.var_props)
        ex.var_tags = dict(world.var_tags)
        ex.var_fields = dict(world.var_fields)  # the head's fields rolled once, for every clip

        def back(n: int) -> int:  # the clip n back along what t continues; the first one it reaches
            behind = reel.chain(t, walked)
            return behind[min(n, len(behind)) - 1] if n > 0 and behind else t

        ex.history = lambda name, n: ex.vars.get(name) if back(n) == t else history[back(n)].get(name)
        ex.history_props = lambda name, n: (ex.var_fields if back(n) == t else history_props[back(n)]).get(name, {})
        for line in block.lines:
            if m := BINDING.match(line.strip()):
                ex.bind(m.group(1), m.group(2))
        return ex, block

    def record(t: int, block: int, rep: int) -> None:
        walked.append((block, rep))
        rolled[t] = ex_t = expander(t)[0]
        history.append(dict(ex_t.vars))
        history_props.append(dict(ex_t.var_fields))

    def holds(t: int, goto: Goto) -> bool:  # a chance, and `? cond: CUT TO: …` on what segment t rolled
        # the chance rolls on the expander kept for this, under the cut's own label: no pick moves
        if goto.chance is not None and rolled[t]._stream(goto.line.strip()).random() >= goto.chance:
            return False
        return not goto.conditional or rolled[t].guarded(goto.line) is not None

    path, ended = reel.walk(holds, upto=max(last + 1, upto or 0), on_segment=record)
    if last >= len(path):
        raise ReelEnd(f"The reel has {len(path)} clips at this seed; segment {last} (clip {last + 1}) is past its end "
                      "(the segment counts from 0, like Load Latent's clip_index).")

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
        lint.append(Issue("warn", f"SCENE {forever + 1} repeats forever, so the "
                                  f"{len(reel.blocks) - forever - 1} SCENE(s) after it never play."))
    elif not reel.jumps_on_rolls and any(b.gotos for b in reel.blocks):
        never = [i + 1 for i, start in enumerate(reel.starts()) if start is None]
        if never:
            lint.append(Issue("warn", f"The CUT TO: lines jump past SCENE {', '.join(map(str, never))}: "
                                      "it never plays."))

    world, head, expand, (path, _) = _unroll(reel, seed, libraries, weights, segment)
    lines, handoff, picks, _ = expand(segment)
    continues = reel.before(segment, path)
    before, before_picks = (expand(continues)[1::2] if continues is not None else (None, []))
    lint += [Issue("warn", w) for w in world.warnings]
    scene = parse_scene("\n".join(head + lines), Expander(0, {}), lint, expanded=True)
    if scene.shots and before:
        scene.shots[0].items.insert(0, f"The shot opens as {_clause(before)}")
    if scene.shots and handoff:
        scene.shots[-1].items.append(f"The shot ends as {_clause(handoff)}")
    context = DEFAULT_CONTEXT if scene.context is None else scene.context
    if scene.shots and continues is not None and context:
        scene.shots[0].duration += context / H3_FPS
    t = 0.0
    for shot in scene.shots:
        shot.start, t = t, t + shot.duration
    return scene, world.picks + picks + before_picks, path
