"""Send along (#335): what goes to the language model beside a request's own text. A takes sheet (and a writer of
the Write menu, #334) sends what its toggles say: the prompt as it rolls, the frames wired into the Orrery Prompt's
first_frame and last_frame, four stills of the video wired into its video input, and any item of the Gallery (a
picture as it is, a video as four of its stills). The pictures go as pictures, each told to the model as what it is.

    sends = ["prompt", "first_frame", "video", "gallery:3f2a…"]
"""

from pathlib import Path

SOURCES = ("prompt", "first_frame", "last_frame", "video")
GALLERY = "gallery:"
STILLS = 4  # a video goes as this many stills, from its start to its end


def parse(sends) -> list[str] | None:
    """The sources a request names, in order and once each; None when it names none (the place's own defaults)."""
    if sends is None:
        return None
    if not isinstance(sends, list) or not all(isinstance(s, str) for s in sends):
        raise ValueError("'sends' is a list: prompt, first_frame, last_frame, video, gallery:<id>.")
    out = []
    for s in sends:
        s = s.strip()
        if s not in SOURCES and not (s.startswith(GALLERY) and len(s) > len(GALLERY)):
            raise ValueError(f"Nothing to send along as {s!r}: prompt, first_frame, last_frame, video or gallery:<id>.")
        if s not in out:
            out.append(s)
    return out


def _evenly(total: int, n: int) -> list[int]:
    """N frame indices from the first to the last of `total`."""
    if total <= 0:
        return []
    if total <= n:
        return list(range(total))
    return [round(i * (total - 1) / (n - 1)) for i in range(n)]


def file_stills(path: Path | str, n: int = STILLS) -> list:
    """N stills of a video file, from its first frame to its last, as PIL."""
    import av

    with av.open(str(path)) as container:
        total = container.streams.video[0].frames or sum(1 for _ in container.decode(video=0))
    wanted, out = set(_evenly(total, n)), []
    with av.open(str(path)) as container:
        for i, frame in enumerate(container.decode(video=0)):
            if i in wanted:
                out.append(frame.to_image())
            if len(out) == len(wanted):
                break
    return out


def video_stills(video, n: int = STILLS) -> list:
    """N stills of the Orrery Prompt's video input (ComfyUI's VIDEO, or its file over the API), as PIL."""
    if video is None:
        return []
    if isinstance(video, str | Path):
        return file_stills(video, n)
    source = video.get_stream_source()
    if isinstance(source, str):
        return file_stills(source, n)
    from orrery.comfy import _picture

    images = video.get_components().images  # a video held in memory: its decoded frames
    return [_picture(images[i:i + 1]) for i in _evenly(int(images.shape[0]), n)]


def pictures(home, sends: list[str], inputs: dict, video=None) -> tuple[list, list[str], list[str]]:
    """The pictures `sends` names, as PIL, what each is, and what could not be sent (a sentence each). `inputs`:
    first_frame and last_frame as a run has them (an IMAGE) or as files over the API; `video` likewise."""
    from PIL import Image

    from orrery import galaxy
    from orrery.comfy import _picture

    shown, labels, missing = [], [], []
    rows = None
    for s in sends:
        if s in ("first_frame", "last_frame"):
            wired = inputs.get(s)
            if wired is None:
                missing.append(f"nothing is wired into the Orrery Prompt's {s}")
                continue
            shown.append(Image.open(wired) if isinstance(wired, str | Path) else _picture(wired))
            labels.append(f"the {s.split('_')[0]} frame")
        elif s == "video":
            stills = video_stills(video)
            if not stills:
                missing.append("nothing is wired into the Orrery Prompt's video")
            shown += stills
            labels += [f"still {k} of {len(stills)} of the input video" for k in range(1, len(stills) + 1)]
        elif s.startswith(GALLERY):
            rows = rows if rows is not None else {r["id"]: r for r in galaxy.read_rows(home)}
            row = rows.get(s[len(GALLERY):])
            media = Path(row["media"]) if row and row.get("media") else None
            if media is None or not media.is_file():
                missing.append(f"the gallery has no file for {s[len(GALLERY):]}")
            elif row.get("kind") == "video" or media.suffix.lower() in (".mp4", ".webm", ".mov", ".mkv", ".m4v"):
                stills = file_stills(media)
                shown += stills
                labels += [f"still {k} of {len(stills)} of a video from the gallery" for k in range(1, len(stills) + 1)]
            else:
                shown.append(Image.open(media))
                labels.append("a picture from the gallery")
    return shown, labels, missing
