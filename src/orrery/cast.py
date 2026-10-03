"""The cast: named references a screenplay can mention by name.

    CAST
    DOG (image 2, image 3): the fluffy white Samoyed, with thick white fur and a curved tail
    MAYA (video 1 + audio): the young blonde woman, in a light-pink shirt
    voice: audio 1, containing a spoken English vocal layer
    keep: partial - only her face and hair are kept      (or a macro: keep: face, hair)

A member is a memory: a description (head noun phrase, then details after the first comma)
plus where it comes from (`image N`, `video N`, `video N + audio`, `refmod NAME`). An image and a
RefMod can carry a strength and a start (`refmod salon_canon at 0.5 from 35%`, `image 1 at 0.5`), and
`always` (`global`, the earlier word) keeps the member in every clip, not only in the clips that name
it. In `@h3 references` (ref2va) the
compiler turns members into <Subject N> labels and sources into the labels the MiniMax H3
Reference to Video node gives its inputs; in the other modes names expand to descriptions,
which is also how RefMods bind to a prompt.

A member may be written `@JINX` anywhere (in the CAST, the prose, a voice, SET:), as Fountain forces
a character with `@`; `bare` writes it `JINX` before the screenplay is read. `@name(0.8)` stays the
LoRA shortcut for every name that is not a member's (orrery.loras.long_form asks `names`).
"""

import re
from dataclasses import dataclass, field

from orrery.dsl import _wants_an

MAX_SLOTS = {"image": 9, "video": 3, "audio": 3}
KEEP = {  # any of these spellings (spaces, hyphens or underscores) name a retention marker
    "fully_preserved": "fully_preserved", "fully": "fully_preserved", "full": "fully_preserved",
    "preserved": "fully_preserved",
    "partially_preserved": "partially_preserved", "partially": "partially_preserved", "partial": "partially_preserved",
    "attribute_transfer": "attribute_transfer", "transfer": "attribute_transfer", "attribute": "attribute_transfer",
    "weak_reference": "weak_reference", "weak": "weak_reference",
}

MEMBER = re.compile(r"^([A-Z][A-Z0-9 _-]*?)\s*(?:\(([^)]*)\))?\s*:\s*(.+)$")
_DIALS = r"(?:\s+at\s+(\d*\.?\d+))?(?:\s+from\s+(\d+(?:\.\d+)?)\s*%)?(?:\s+to\s+(\d+(?:\.\d+)?)\s*%)?"  # `at 0.5 from 35% to 80%`
_SOURCE = re.compile(rf"^(image|video|audio)\s+(\d+)(\s*\+\s*audio)?{_DIALS}$|^refmod\s+([\w./-]+){_DIALS}$",
                     re.IGNORECASE)
# `image krea/09_character_creator/1283456183`: a picture of the gallery by name (orrery.pictures), or a
# library of them (`image __pictures/krea/09_character_creator__`, rolled before the CAST is read)
_NAMED = re.compile(rf"^image\s+((?!\d+\b)[\w./-]+){_DIALS}$", re.IGNORECASE)
_VOICE = re.compile(r"^(?:(audio)\s+(\d+)|video\s+(\d+)\s+audio)\s*(?:,\s*(.*))?$", re.IGNORECASE)
# keep: macros, written out as a marker and a reason ({who} is the member's head noun)
KEEP_PARTS = {"face": "face", "identity": "face", "hair": "hair", "body": "build", "build": "build",
              "outfit": "outfit", "clothes": "outfit", "clothing": "outfit"}
KEEP_WHOLE = {
    "all": ("fully_preserved", "{who} is retained as defined, in every detail."),
    "everything": ("fully_preserved", "{who} is retained as defined, in every detail."),
    "style": ("attribute_transfer", ("only the style of {who} carries over, its colours, materials and finish; what it "
                                     "is follows the prompt.")),
    "colors": ("attribute_transfer", "only the colours of {who} carry over."),
    "colours": ("attribute_transfer", "only the colours of {who} carry over."),
    "place": ("fully_preserved", "{who} is retained as a place: its layout, surfaces and light."),
    "location": ("fully_preserved", "{who} is retained as a place: its layout, surfaces and light."),
    "background": ("fully_preserved", "{who} is retained as a place: its layout, surfaces and light."),
    "setting": ("fully_preserved", "{who} is retained as a place: its layout, surfaces and light."),
    "loose": ("weak_reference", ("{who} is only a loose reference: its general look guides the shot, and its details "
                                 "may change.")),
}
_KEEP = re.compile(r"^([A-Za-z_ -]+?)\s*(?:[-–—:,]\s*(.*))?$")
_BRACKET = re.compile(r"\[(image|video|audio)\s+(\d+)(\s+audio)?\]", re.IGNORECASE)
_DETAIL = re.compile(r"\s+(?:with|wearing|in|who|whose|that|holding|carrying|facing|dressed)\s", re.IGNORECASE)
_ENDS_CAST = re.compile(r"^(?:SHOT|SCENE|CHUNK)\b")


def names(text: str) -> list[str]:
    """The names the CAST blocks of a template give their members, written with `@` or without."""
    out, in_cast = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "CAST":
            in_cast = True
        elif _ENDS_CAST.match(line):
            in_cast = False
        elif in_cast and (m := MEMBER.match(line.removeprefix("@"))) and m.group(1).strip() not in out:
            out.append(m.group(1).strip())
    return out


def bare(text: str) -> str:
    """The template with every `@NAME` of a CAST member written `NAME`."""
    found = names(text) if "@" in text else []
    if not found:
        return text
    member = "|".join(re.escape(n) for n in sorted(found, key=len, reverse=True))
    return re.sub(rf"(?<![\w@<\\])@({member})(?![\w-])", r"\1", text)


@dataclass(frozen=True)
class Source:
    kind: str  # image | video | audio | refmod
    index: int = 0
    name: str = ""
    soundtrack: bool = False
    strength: float | None = None  # refmod: `at 0.5`; None takes the screenplay's default
    start: float | None = None  # refmod: `from 35%` as 0.35, the share of sampling it waits; None, the default
    end: float | None = None  # `to 80%` as 0.8, the share of sampling where it stops; None, the default


@dataclass
class Member:
    name: str
    head: str
    tail: str = ""
    sources: list[Source] = field(default_factory=list)
    voice: Source | None = None  # an audio slot, or a video's soundtrack (kind "video", soundtrack True)
    voice_note: str = ""
    keep: tuple[str, str | None] | None = None  # (marker, reason or None for the default)
    everywhere: bool = False  # `global`: its RefMods go with every clip, named in it or not
    block: int = 0  # the CAST block that declared it: a chunk's own CAST replaces the head's member
    problems: list[str] = field(default_factory=list)  # advice for lint; parsing never fails

    def split_head(self) -> tuple[str, str]:
        """The head as (noun phrase, detail): 'a man in a suit' → ('a man', ' in a suit')."""
        m = _DETAIL.search(_SLOT_SPAN.sub(lambda s: "-" * len(s.group(0)), self.head))  # a slot's words are its own
        return (self.head[:m.start()], self.head[m.start():]) if m and m.start() else (self.head, "")

    @property
    def short(self) -> str:
        """The head noun phrase for later mentions: 'a young woman' becomes 'the young woman', and
        'a compact alien with an elongated head' becomes 'the compact alien'."""
        return re.sub(r"^(an?)\s+", "the ", self.split_head()[0], flags=re.IGNORECASE)


_SLOT_SPAN = re.compile(r"--(?=[^\s-])[^\n]*?[^\s-]--")  # a `--…--` slot (orrery.slots.SLOT): its commas are its own


def parse_member(name: str, spec: str, text: str) -> Member:
    text = text.strip()
    hidden = _SLOT_SPAN.sub(lambda m: "-" * len(m.group(0)), text)  # where the head ends: the first comma outside a slot
    cut = hidden.find(",")
    head, rest = (text, "") if cut < 0 else (text[:cut], text[cut + 1:])
    # a slot that writes who the member is says whose it is: two members with the same directions get a
    # text each (orrery.slots writes each directions once), and the model knows which subject it describes
    head = _SLOT_SPAN.sub(lambda m: m.group(0) if f"(for {name.strip()})" in m.group(0)
                          else f"{m.group(0)[:-2]} (for {name.strip()})--", head)
    member = Member(name.strip(), head.strip(), f", {rest.strip()}" if rest.strip() else "")
    for raw in filter(None, (s.strip() for s in (spec or "").split(","))):
        m, named = _SOURCE.match(raw), _NAMED.match(raw)
        if raw.lower() in ("always", "global"):  # global: the earlier word
            member.everywhere = True
        elif not (m or named):
            member.problems.append(f"{member.name}: \"{raw}\" is not a reference orrery knows (image N, "
                                   "image NAME, video N, video N + audio, audio N, refmod NAME, always), so it is "
                                   "left out.")
        else:
            refmod = m.group(7) if m else None
            at, start, end = (named.group(2, 3, 4) if named else m.group(8, 9, 10) if refmod
                              else m.group(4, 5, 6))
            what = (f"image {named.group(1)}" if named else f"refmod {refmod}" if refmod
                    else f"{m.group(1).lower()} {m.group(2)}")
            if (at or start or end) and not (refmod or named) and m.group(1).lower() != "image":
                member.problems.append(f"{member.name}: {what} takes no at, from or to (images and RefMods do), so "
                                       "they are left out.")
                at = start = end = None
            share = float(start) / 100 if start else None
            if share is not None and share > 1:
                member.problems.append(f"{member.name}: {what} from {start}% waits past the end of sampling; it "
                                       "starts at 100% instead.")
                share = 1.0
            until = min(1.0, float(end) / 100) if end else None
            if until is not None and until <= (share or 0.0):
                member.problems.append(f"{member.name}: {what} to {end}% stops before it starts; the end is left out.")
                until = None
            strength = float(at) if at else None
            if refmod:
                member.sources.append(Source("refmod", name=refmod, strength=strength, start=share, end=until))
            elif named:  # its number comes when the clip is compiled (orrery.h3.name_pictures)
                member.sources.append(Source("image", name=named.group(1), strength=strength, start=share, end=until))
            else:
                member.sources.append(Source(m.group(1).lower(), int(m.group(2)), soundtrack=bool(m.group(3)),
                                             strength=strength, start=share, end=until))
    return member


def attach(member: Member, key: str, value: str) -> None:
    if key == "voice":
        m = _VOICE.match(value.strip())
        if not m:
            member.problems.append(f"{member.name}: voice takes \"audio N\" or \"video N audio\" "
                                   f"(then optionally a comma and a note); \"{value}\" is left out.")
            return
        member.voice = (Source("audio", int(m.group(2))) if m.group(1)
                        else Source("video", int(m.group(3)), soundtrack=True))
        member.voice_note = (m.group(4) or "").strip()
    elif key == "keep":
        member.keep = parse_keep(value)


def keep_macro(value: str) -> tuple[str, str] | None:
    """`keep: face, hair` · `keep: all` · `keep: style` · `keep: place` · `keep: loose`: a marker and a
    reason with {who} in it; None when the value is not made of these words."""
    words = [w for w in re.split(r"\s*(?:,|\+|\band\b)\s*|\s+", value.strip().lower()) if w]
    if not words or not all(w in KEEP_PARTS or w in KEEP_WHOLE for w in words):
        return None
    whole = [w for w in words if w in KEEP_WHOLE]
    if whole:
        if len(words) > 1:
            raise ValueError(f"keep: {value}: {whole[0]} stands alone; the parts that combine are "
                             f"{', '.join(sorted(set(KEEP_PARTS)))}.")
        return KEEP_WHOLE[whole[0]]
    parts = list(dict.fromkeys(KEEP_PARTS[w] for w in words))
    return "partially_preserved", f"only the {oxford(parts)} of {{who}} are retained; everything else follows the prompt."


def parse_keep(value: str) -> tuple[str, str | None]:
    """A macro (`face, hair`, `all`, `style`, `place`, `loose`), `full`, `partially preserved - only her
    face`, `weak: a hint`, or just a reason."""
    if macro := keep_macro(value):
        return macro
    text = value.strip()
    m = _KEEP.match(text)
    marker = m and KEEP.get(re.sub(r"[\s-]+", "_", m.group(1).strip().lower()))
    if marker:
        return marker, (m.group(2) or "").strip() or None
    return "fully_preserved", text or None


def oxford(items: list[str]) -> str:
    if len(items) < 3:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def article(phrase: str) -> str:
    return "an" if _wants_an(phrase) else "a"


class Labels:
    """The labels the MiniMax H3 Reference to Video node gives its inputs: images and videos by
    slot; <Audio j> first for each wired video soundtrack (in video order), then standalone audio."""

    def __init__(self, cast: list[Member], extra: list[Source] = ()) -> None:
        self.subjects = {m.name: i for i, m in enumerate(cast, start=1)}
        sources = [s for m in cast for s in m.sources] + [m.voice for m in cast if m.voice] + list(extra)
        self.soundtracks = sorted({s.index for s in sources if s.kind == "video" and s.soundtrack})

    def label(self, source: Source) -> str:
        if source.kind == "image":
            return f"<Picture {source.index}>"
        if source.kind == "video" and not source.soundtrack:
            return f"<Video {source.index}>"
        if source.kind == "video":
            return f"<Audio {self.soundtracks.index(source.index) + 1}>"
        if source.kind == "audio":
            return f"<Audio {len(self.soundtracks) + source.index}>"
        return ""

    def sources_phrase(self, member: Member) -> str:
        return oxford([self.label(Source(s.kind, s.index)) for s in member.sources if s.kind != "refmod"])

    def brackets(self, text: str) -> str:
        """`[image 2]`, `[video 1]`, `[audio 1]` and `[video 1 audio]` in prose become labels."""
        def swap(m: re.Match) -> str:
            kind, index = m.group(1).lower(), int(m.group(2))
            return self.label(Source(kind, index, soundtrack=bool(m.group(3)) and kind == "video"))
        return _BRACKET.sub(swap, text)


def bracket_sources(text: str) -> list[Source]:
    return [Source(m.group(1).lower(), int(m.group(2)), soundtrack=bool(m.group(3)) and m.group(1).lower() == "video")
            for m in _BRACKET.finditer(text)]


class Names:
    """Renders cast names in prose. ref2va: <Subject N>, the first mention in the video with its
    description, the first mention in a shot where the member speaks with its speaker ID.
    Other modes: the full description on first mention, then the head noun phrase."""

    def __init__(self, cast: list[Member], labels: Labels | None = None, describe: bool = True) -> None:
        self.members = {m.name: m for m in cast}
        self.labels = labels
        self.describe = describe  # False: labels only, the descriptions live in definitions (lite)
        self.introduced: set[str] = set()
        self.appears: dict[str, list[int]] = {m.name: [] for m in cast}
        self.pattern = (re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(self.members, key=len, reverse=True)) + r")\b")
                        if self.members else None)

    def note(self, name: str, shot_no: int) -> None:
        if name in self.appears and shot_no not in self.appears[name]:
            self.appears[name].append(shot_no)

    def render(self, text: str, shot_no: int, speakers: dict[str, str] | None = None,
               tagged: set[str] | None = None) -> str:
        """`speakers`: members speaking in this shot → speaker ID; `tagged`: members already
        given their ID in this shot (updated in place)."""
        if not self.pattern:
            return text
        speakers, tagged = speakers or {}, tagged if tagged is not None else set()

        def swap(m: re.Match) -> str:
            name, member = m.group(1), self.members[m.group(1)]
            self.note(name, shot_no)
            after = text[m.end():m.end() + 1]
            closing = "" if not after or after in ".,;:!?)'" else ","
            if self.labels is None:
                if name in self.introduced:
                    return member.short
                self.introduced.add(name)
                return f"{member.head}{member.tail}{closing if member.tail else ''}"
            label = f"<Subject {self.labels.subjects[name]}>"
            if name in speakers and name not in tagged:
                tagged.add(name)
                label += f" ({speakers[name]})"
            if name in self.introduced or not self.describe:
                return label
            self.introduced.add(name)
            return f"{label}, {member.head}{member.tail}{closing}"

        return self.pattern.sub(swap, text)

    def plain(self, text: str) -> str:
        """Labels without descriptions or IDs, for the summary."""
        if not self.pattern or self.labels is None:
            return text
        return self.pattern.sub(lambda m: f"<Subject {self.labels.subjects[m.group(1)]}>", text)
