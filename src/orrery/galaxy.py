"""The galaxy: every logged output, with stable ids, ratings that teach the weights, thumbnails.

A rating multiplies the learned weight of every pick key in the output. Re-rating
applies new/old, so ratings replace each other instead of stacking, and clearing
a rating restores the weights it changed.

The Gallery shows the outputs by day, and what belongs together as an album (#290): a sweep's or a grid's
runs (their `folder`, `sweeps/…`), a reel's clips (its `chain`) and in it each scene's (its `chunk`).
Collections hold outputs without moving them, one output in as many as you like: a row's `collections` are
paths such as `portraits/demons`, and `galaxy_folders.json` keeps the ones that hold nothing yet. A folder of
the time before collections (a row's `folder` that is no sweep's) counts as a collection, and becomes one when
the row next changes. Files stay where ComfyUI wrote them until they are deleted (into the home's trash) or
exported (copied).
"""

import hashlib
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from orrery.home import Home, locked, write_atomic

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
    raise KeyError(f"no gallery output {rid}")


@locked
def rate(home: Home, rid: str, rating: str | None) -> tuple[dict, dict[str, float]]:
    if rating is not None and rating not in FACTORS:
        raise ValueError(f"rating must be one of {', '.join(FACTORS)} or null")
    lines = _lines(home)
    for i, line in enumerate(lines):
        row = _parse(line)
        if row is not None and row_id(row) == rid:
            break
    else:
        raise KeyError(f"no gallery output {rid}")
    factor = FACTORS.get(rating, 1.0) / FACTORS.get(row.get("rating"), 1.0)
    keys = list(dict.fromkeys(k for p in row.get("picks") or [] for k in p.get("keys") or []))
    weights = home.weights()
    for key in keys:
        # significant digits, not decimal places (#257): a weight never sits on a rounding floor, so taking
        # ratings back gives it back, and the same ratings in any order give the same weight
        w = float(f"{weights.get(key, 1.0) * factor:.12g}")
        if abs(w - 1.0) < 1e-9:
            weights.pop(key, None)
        else:
            weights[key] = w
    row["rating"] = rating
    lines[i] = json.dumps(row, ensure_ascii=False)
    write_atomic(home.galaxy_path, "\n".join(lines) + "\n")
    home.save_weights(weights)
    return _with_id(row, rid), {k: weights.get(k, 1.0) for k in keys}


def picture_of(row: dict):
    """A row's picture as PIL: its image, or for a clip the frame a third of the way in (#175)."""
    from PIL import Image

    media = Path(str(row.get("media") or ""))
    if media_kind(media) == "image" and media.is_file():
        return Image.open(media)
    if media_kind(media) == "video" and media.is_file():
        return _poster(media)
    raise KeyError(f"gallery output {row_id(row)} has no picture to look at")


def write_export(home: Home, rid: str, directions: str, text: str) -> dict:
    """A written text in place of the export slot `--directions--` of row `rid` (#175): what the Gallery writes from
    the picture, kept with it; a screenplay that casts the picture reads it."""
    from orrery.slots import fill_exports

    text = " ".join(str(text).split())
    if not text:
        raise ValueError("an empty text writes nothing")
    touched = _edit_rows(home, lambda row: {**row, "exports": fill_exports(row.get("exports") or {}, {directions: text})}
                         if row_id(row) == rid else row)
    if not touched:
        raise KeyError(f"gallery output {rid} has no slot --{directions}--")
    return _find(home, rid)


def media_path(home: Home, rid: str) -> Path:
    """The output's file, only for paths the galaxy recorded."""
    media = _find(home, rid).get("media")
    if not media or not Path(media).is_file():
        raise KeyError(f"gallery output {rid} has no file on disk")
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
    if media_kind(src) not in ("image", "video"):
        raise KeyError(f"gallery output {rid} has no picture to preview")
    return thumb_file(src, home.root / "thumbs" / f"{rid}.webp")


def thumb_file(src: Path, out: Path) -> Path:
    """A small cached WEBP of a picture, or of a video's frame a third in."""
    kind = media_kind(src)
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


# --- collections, days, albums ---------------------------------------------------------------

FOLDER_PART_MAX = 60
SWEEPS = "sweeps/"  # the folder Roll gives a sweep's or a grid's runs: an album, never a collection
PREVIEWS = 8  # an album's card shows so many of its pictures: more get too small
_EXPORT_NAME = re.compile(r"[\w .-]{1,80}")


def clean_folder(path) -> str:
    """A collection's path (or a sweep's folder) as stored: trimmed parts joined by '/'; '' is none."""
    if path is None:
        return ""
    if not isinstance(path, str):
        raise TypeError("a collection is a path such as portraits/demons")
    trimmed = path.strip().strip("/")
    if not trimmed:
        return ""
    parts = [p.strip() for p in trimmed.split("/")]
    for p in parts:
        if not p or p in (".", "..") or len(p) > FOLDER_PART_MAX or any(ord(ch) < 32 for ch in p):
            raise ValueError(f"{path!r} is no collection: parts of 1 to {FOLDER_PART_MAX} characters, joined by /")
    return "/".join(parts)


def _parents(path: str) -> list[str]:
    """'a/b/c' -> ['a', 'a/b', 'a/b/c']."""
    parts = path.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]


def _inside(path: str, folder: str) -> bool:
    return path == folder or path.startswith(folder + "/")


def sweep_of(row: dict) -> str | None:
    """The sweep (or grid) a row was one run of: its folder `sweeps/…`."""
    folder = row.get("folder") or ""
    return folder if folder.startswith(SWEEPS) else None


def collections_of(row: dict) -> list[str]:
    """The collections a row is in: its own, and a folder of the time before collections."""
    out = [c for c in row.get("collections") or [] if isinstance(c, str) and c]
    folder = row.get("folder") or ""
    if folder and not folder.startswith(SWEEPS) and folder not in out:
        out.append(folder)
    return out


def _with_collections(row: dict, paths) -> dict:
    """The row in these collections; a folder of the time before collections goes into them."""
    if row.get("folder") and not sweep_of(row):
        row.pop("folder")
    paths = list(dict.fromkeys(p for p in paths if p))
    if paths:
        row["collections"] = paths
    else:
        row.pop("collections", None)
    return row


def _saved_folders(home: Home) -> list[str]:
    path = home.galaxy_folders_path
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except ValueError:
        return []
    return [f for f in data if isinstance(f, str) and f and not f.startswith(SWEEPS)] if isinstance(data, list) else []


def _save_folders(home: Home, folders: list[str]) -> None:
    write_atomic(home.galaxy_folders_path, json.dumps(sorted({f for f in folders if f}), ensure_ascii=False, indent=1))


def collections(home: Home, rows: list[dict] | None = None) -> list[dict]:
    """Every collection, saved or named by a row, with its parents, sorted, each with its own outputs' count."""
    rows = read_rows(home) if rows is None else rows
    counts = Counter(c for r in rows for c in collections_of(r))
    names = {p for f in [*_saved_folders(home), *counts] if f for p in _parents(f)}
    return [{"path": f, "count": counts.get(f, 0)} for f in sorted(names, key=str.lower)]


@locked
def _edit_rows(home: Home, edit) -> list[dict]:
    """Rewrite galaxy.jsonl: edit(row) gives the row to keep (changed or not) or None to drop it. Lines
    that are no rows stay as they are. Returns the rows it changed or dropped, as they were."""
    out, touched = [], []
    for line in _lines(home):
        row = _parse(line)
        if row is None:
            out.append(line)
            continue
        new = edit(dict(row))
        if new is None or new != row:
            touched.append(row)
        if new is not None:
            out.append(line if new == row else json.dumps(new, ensure_ascii=False))
    if touched:
        write_atomic(home.galaxy_path, "".join(f"{line}\n" for line in out))
    return touched


def _check_ids(home: Home, ids) -> set[str]:
    wanted = {str(i) for i in ids or []}
    if not wanted:
        raise ValueError("choose at least one output")
    missing = wanted - {r["id"] for r in read_rows(home)}
    if missing:
        raise KeyError(f"no gallery output {min(missing)}")
    return wanted


def _named(path) -> str:
    path = clean_folder(path)
    if not path:
        raise ValueError("name the collection")
    if path.startswith(SWEEPS) or path == SWEEPS.rstrip("/"):
        raise ValueError("sweeps/ holds the sweeps' albums; name the collection otherwise")
    return path


def collect(home: Home, ids, path) -> int:
    """Put outputs into a collection as well: they keep their other collections, their day and their album."""
    path, wanted = _named(path), _check_ids(home, ids)
    _edit_rows(home, lambda r: _with_collections(r, [*collections_of(r), path]) if row_id(r) in wanted else r)
    _save_folders(home, [*_saved_folders(home), path])
    return len(wanted)


def uncollect(home: Home, ids, path) -> int:
    """Take outputs out of a collection; they stay in the gallery, and in their other collections."""
    path, wanted = _known(home, path), _check_ids(home, ids)
    _edit_rows(home, lambda r: _with_collections(r, [c for c in collections_of(r) if c != path])
               if row_id(r) in wanted and path in collections_of(r) else r)
    return len(wanted)


def _known(home: Home, path) -> str:
    path = clean_folder(path)
    if not path or path not in {f["path"] for f in collections(home)}:
        raise KeyError(f"no gallery collection {path or '(none)'}")
    return path


def add_collection(home: Home, path) -> str:
    path = _named(path)
    if path in {f["path"] for f in collections(home)}:
        raise FileExistsError(f"the collection {path} already exists")
    _save_folders(home, [*_saved_folders(home), path])
    return path


def rename_collection(home: Home, path, to) -> str:
    """Rename a collection or move it into another (a/b to c/b); its own collections and outputs go along."""
    path, to = _known(home, path), _named(to)
    if to == path:
        return to
    if _inside(to, path):
        raise ValueError(f"{path} cannot move into itself")
    if to in {f["path"] for f in collections(home)}:
        raise FileExistsError(f"the collection {to} already exists")

    def moved(f: str) -> str:
        return to + f[len(path):] if _inside(f, path) else f

    _edit_rows(home, lambda r: _with_collections(r, [moved(c) for c in collections_of(r)])
               if any(_inside(c, path) for c in collections_of(r)) else r)
    _save_folders(home, [*map(moved, _saved_folders(home)), to])
    return to


def delete_collection(home: Home, path) -> str:
    """Remove a collection: its outputs leave it (they stay in the gallery), the collections in it move up one
    level. Returns that level."""
    path = _known(home, path)
    parent = path.rpartition("/")[0]

    def up(f: str) -> str:
        return "/".join(p for p in (parent, f[len(path) + 1:]) if p) if _inside(f, path) and f != path else f

    _edit_rows(home, lambda r: _with_collections(r, [up(c) for c in collections_of(r) if c != path])
               if any(_inside(c, path) for c in collections_of(r)) else r)
    _save_folders(home, [up(f) for f in _saved_folders(home) if f != path])
    return parent


def day_of(ts, tz: int = 0) -> str:
    """The day a row was made, `YYYY-MM-DD`, in the time zone `tz` minutes east of UTC (the viewer's)."""
    try:
        when = datetime.fromisoformat(str(ts))
    except ValueError:
        return ""
    return (when + timedelta(minutes=tz)).date().isoformat()


def album_of(row: dict) -> str | None:
    """The album a row belongs to: `sweep:<its folder>`, `reel:<its chain>` (a reel's clips logged before the
    chain was, by preset or template and seed); None for an output on its own."""
    if sweep := sweep_of(row):
        return f"sweep:{sweep}"
    if row.get("chunks"):
        reel = row.get("chain") or "{}|{}".format(row.get("preset") or row.get("template"), row.get("seed"))
        return f"reel:{reel}"
    return None


def scene_of(row: dict) -> str | None:
    """The album of a reel's scene a clip plays: `scene:<its reel>|<the scene's index>`."""
    album = album_of(row)
    if album and album.startswith("reel:") and isinstance(row.get("chunk"), int):
        return f"scene:{album[5:]}|{row['chunk']}"
    return None


def in_album(row: dict, key: str) -> bool:
    return (scene_of(row) if key.startswith("scene:") else album_of(row)) == key


def cards(rows: list[dict], album: str | None = None) -> list[dict]:
    """What the overview shows of these rows, newest first (#297, #298): an output on its own, or an album of two
    or more, a sweep's or a reel's; inside a reel, its scenes are albums; inside a sweep or a scene, the outputs.
    An album's card carries its ids, newest first, and the first PREVIEWS with a picture to show."""
    group = album_of if album is None else scene_of if album.startswith("reel:") else None
    groups: dict[str, list[dict]] = {}
    for r in rows:
        key = group(r) if group else None
        groups.setdefault(key or f"row:{r['id']}", []).append(r)
    out = []
    for key, members in groups.items():
        if key.startswith("row:") or len(members) == 1:
            out.extend({"kind": "row", "id": r["id"], "ts": r.get("ts") or ""} for r in members)
            continue
        out.append({"kind": "album", "type": key.partition(":")[0], "key": key, "count": len(members),
                    "ids": [r["id"] for r in members], "ts": max(r.get("ts") or "" for r in members),
                    "previews": [r["id"] for r in members if r["kind"] in ("image", "video")][:PREVIEWS],
                    "videos": sum(r["kind"] == "video" for r in members)})
    return sorted(out, key=lambda c: c["ts"], reverse=True)


def tree(rows: list[dict], tz: int = 0) -> dict:
    """The Gallery's tree (#296): every output, its pictures and its videos, and each day with its own, newest first."""
    kinds = Counter(r["kind"] for r in rows)
    days: dict[str, Counter] = {}
    for r in rows:
        days.setdefault(day_of(r.get("ts"), tz), Counter())[r["kind"]] += 1
    return {"total": len(rows), "images": kinds["image"], "videos": kinds["video"],
            "days": [{"day": d, "total": sum(c.values()), "images": c["image"], "videos": c["video"]}
                     for d, c in sorted(days.items(), reverse=True) if d]}


def _free(folder: Path, stem: str, suffix: str, *also: str) -> Path:
    """folder/stem+suffix, or stem_2, stem_3, … while that name (or a sibling with an `also` suffix) is taken."""
    name, n = stem, 1
    while any((folder / f"{name}{s}").exists() for s in (suffix, *also)):
        n += 1
        name = f"{stem}_{n}"
    return folder / f"{name}{suffix}"


def delete(home: Home, ids) -> int:
    """Drop outputs from the galaxy and move their files into the home's trash. A file another row
    still shows stays; learned weights stay too, since a rating was a real judgement."""
    wanted = _check_ids(home, ids)
    dropped = _edit_rows(home, lambda r: None if row_id(r) in wanted else r)
    kept = {r.get("media") for r in read_rows(home)}
    for row in dropped:
        media = row.get("media")
        if media and media not in kept and Path(media).is_file():
            src = Path(media)
            home.trash_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(_free(home.trash_dir, src.stem, src.suffix)))
        (home.root / "thumbs" / f"{row_id(row)}.webp").unlink(missing_ok=True)
    return len(dropped)


def export(home: Home, ids, name) -> dict:
    """Copy each output's picture or video into export/<name>/ with <stem>.txt beside it, holding the
    prompt that made it: pairs for training other models. Outputs without a file are skipped."""
    name = name.strip() if isinstance(name, str) else ""
    if not _EXPORT_NAME.fullmatch(name) or name.startswith("."):
        raise ValueError("an export name is one folder name: letters, digits, spaces, _ - and .")
    wanted = _check_ids(home, ids)
    out = home.export_dir / name
    exported = skipped = 0
    for row in reversed(read_rows(home)):
        if row["id"] not in wanted:
            continue
        media = row.get("media")
        if row["kind"] not in ("image", "video") or not Path(media).is_file():
            skipped += 1
            continue
        src = Path(media)
        out.mkdir(parents=True, exist_ok=True)
        dst = _free(out, src.stem, src.suffix, ".txt")
        shutil.copy2(src, dst)
        dst.with_suffix(".txt").write_text((row.get("text") or "").strip() + "\n", encoding="utf-8")
        exported += 1
    return {"path": str(out), "exported": exported, "skipped": skipped}
