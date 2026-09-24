"""The galaxy: every logged output, with stable ids, ratings that teach the weights, thumbnails.

A rating multiplies the learned weight of every pick key in the output. Re-rating
applies new/old, so ratings replace each other instead of stacking, and clearing
a rating restores the weights it changed.
"""

import hashlib
import json
import os
from pathlib import Path

from orrery.home import Home, write_atomic

FACTORS = {"love": 1.5, "like": 1.2, "nope": 0.8, "hate": 0.5}
THUMB_SIZE = 384
_IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_VIDEO = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}


def row_id(row: dict) -> str:
    key = f"{row.get('ts')}|{row.get('media')}|{row.get('seed')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def media_kind(media) -> str:
    ext = Path(media).suffix.lower() if media else ""
    return "image" if ext in _IMAGE else "video" if ext in _VIDEO else "none"


def _lines(home: Home) -> list[str]:
    path = home.galaxy_path
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _parse(line: str) -> dict | None:
    try:
        row = json.loads(line)
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


def _with_id(row: dict, rid: str | None = None) -> dict:
    return {**row, "id": rid or row_id(row), "kind": media_kind(row.get("media"))}


def read_rows(home: Home) -> list[dict]:
    """Every readable row, newest first, with its id and media kind."""
    return [_with_id(r) for r in reversed([_parse(line) for line in _lines(home)]) if r is not None]


def _find(home: Home, rid: str) -> dict:
    for row in read_rows(home):
        if row["id"] == rid:
            return row
    raise KeyError(f"no galaxy output {rid}")


def rate(home: Home, rid: str, rating: str | None) -> tuple[dict, dict[str, float]]:
    if rating is not None and rating not in FACTORS:
        raise ValueError(f"rating must be one of {', '.join(FACTORS)} or null")
    lines = _lines(home)
    for i, line in enumerate(lines):
        row = _parse(line)
        if row is not None and row_id(row) == rid:
            break
    else:
        raise KeyError(f"no galaxy output {rid}")
    factor = FACTORS.get(rating, 1.0) / FACTORS.get(row.get("rating"), 1.0)
    keys = list(dict.fromkeys(k for p in row.get("picks") or [] for k in p.get("keys") or []))
    weights = home.weights()
    for key in keys:
        w = round(weights.get(key, 1.0) * factor, 4)
        if abs(w - 1.0) < 1e-9:
            weights.pop(key, None)
        else:
            weights[key] = w
    row["rating"] = rating
    lines[i] = json.dumps(row, ensure_ascii=False)
    write_atomic(home.galaxy_path, "\n".join(lines) + "\n")
    home.save_weights(weights)
    return _with_id(row, rid), {k: weights.get(k, 1.0) for k in keys}


def media_path(home: Home, rid: str) -> Path:
    """The output's file, only for paths the galaxy recorded."""
    media = _find(home, rid).get("media")
    if not media or not Path(media).is_file():
        raise KeyError(f"galaxy output {rid} has no file on disk")
    return Path(media)


def _poster(src: Path):
    """The frame a third of the way in: past fades and hand-off frames, before the ending."""
    import av  # ComfyUI ships PyAV

    try:
        with av.open(str(src)) as container:
            stream = container.streams.video[0]
            seconds = (float(stream.duration * stream.time_base) if stream.duration
                       else (container.duration or 0) / av.time_base)
            target = seconds / 3
            if target:
                container.seek(int(target / stream.time_base), stream=stream)
            for frame in container.decode(stream):
                if frame.time is None or frame.time >= target - 1e-3:
                    return frame.to_image()
    except (av.error.FFmpegError, IndexError, OSError) as err:
        raise KeyError(f"no frame could be read from {src.name}: {err}") from err
    raise KeyError(f"{src.name} has no video frames")


def thumbnail(home: Home, rid: str) -> Path:
    src = media_path(home, rid)
    kind = media_kind(src)
    if kind not in ("image", "video"):
        raise KeyError(f"galaxy output {rid} has no picture to preview")
    out = home.root / "thumbs" / f"{rid}.webp"
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    from PIL import Image  # ComfyUI ships Pillow; the CLI never needs it

    im = _poster(src) if kind == "video" else Image.open(src)
    try:
        im.thumbnail((THUMB_SIZE, THUMB_SIZE))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".tmp")
        im.save(tmp, "WEBP", quality=82)
    finally:
        im.close()
    os.replace(tmp, out)
    return out
