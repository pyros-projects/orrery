"""The cast: named references a screenplay can mention by name.

    CAST
    DOG (image 2, image 3): the fluffy white Samoyed, with thick white fur and a curved tail
    MAYA (video 1 + audio): the young blonde woman, in a light-pink shirt
    voice: audio 1, containing a spoken English vocal layer
    keep: partial - only her face and hair are kept

A member is a memory: a description (head noun phrase, then details after the first comma)
plus where it comes from (`image N`, `video N`, `video N + audio`, `refmod NAME`). In ref2va the
compiler turns members into <Subject N> labels and sources into the labels the MiniMax H3
Reference to Video node gives its inputs; in the other modes names expand to descriptions,
which is also how RefMods bind to a prompt.
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
_SOURCE = re.compile(r"^(image|video|audio)\s+(\d+)(\s*\+\s*audio)?$|^refmod\s+([\w.-]+)$", re.IGNORECASE)
_VOICE = re.compile(r"^(?:(audio)\s+(\d+)|video\s+(\d+)\s+audio)\s*(?:,\s*(.*))?$", re.IGNORECASE)
_KEEP = re.compile(r"^([A-Za-z_ -]+?)\s*(?:[-–—:,]\s*(.*))?$")
_BRACKET = re.compile(r"\[(image|video|audio)\s+(\d+)(\s+audio)?\]", re.IGNORECASE)
_DETAIL = re.compile(r"\s+(?:with|wearing|in|who|whose|that|holding|carrying|facing|dressed)\s", re.IGNORECASE)


@dataclass(frozen=True)
class Source:
    kind: str  # image | video | audio | refmod
    index: int = 0
    name: str = ""
    soundtrack: bool = False


@dataclass
class Member:
    name: str
    head: str
    tail: str = ""
    sources: list[Source] = field(default_factory=list)
    voice: Source | None = None  # an audio slot, or a video's soundtrack (kind "video", soundtrack True)
    voice_note: str = ""
    keep: tuple[str, str | None] | None = None  # (marker, reason or None for the default)
    problems: list[str] = field(default_factory=list)  # advice for lint; parsing never fails

    def split_head(self) -> tuple[str, str]:
        """The head as (noun phrase, detail): 'a man in a suit' → ('a man', ' in a suit')."""
        m = _DETAIL.search(self.head)
        return (self.head[:m.start()], self.head[m.start():]) if m and m.start() else (self.head, "")

    @property
    def short(self) -> str:
        """The head noun phrase for later mentions: 'a young woman' becomes 'the young woman', and
        'a compact alien with an elongated head' becomes 'the compact alien'."""
        return re.sub(r"^(an?)\s+", "the ", self.split_head()[0], flags=re.IGNORECASE)


def parse_member(name: str, spec: str, text: str) -> Member:
    head, _, rest = text.strip().partition(",")
    member = Member(name.strip(), head.strip(), f", {rest.strip()}" if rest.strip() else "")
    for raw in filter(None, (s.strip() for s in (spec or "").split(","))):
        m = _SOURCE.match(raw)
        if not m:
            member.problems.append(f"{member.name}: \"{raw}\" is not a reference orrery knows (image N, "
                                   "video N, video N + audio, audio N, refmod NAME), so it is left out.")
        elif m.group(4):
            member.sources.append(Source("refmod", name=m.group(4)))
        else:
            member.sources.append(Source(m.group(1).lower(), int(m.group(2)), soundtrack=bool(m.group(3))))
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


def parse_keep(value: str) -> tuple[str, str | None]:
    """`full`, `partially preserved - only her face`, `weak: a hint`, or just a reason."""
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
