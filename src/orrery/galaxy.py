"""The galaxy: every logged output, with stable ids, ratings that teach the weights, thumbnails.

A rating multiplies the learned weight of every pick key in the output. Re-rating
applies new/old, so ratings replace each other instead of stacking, and clearing
a rating restores the weights it changed.

Folders exist only here: a row's `folder` is a path such as `portraits/demons`, and
`galaxy_folders.json` keeps folders that hold nothing yet. Files stay where ComfyUI
wrote them until they are deleted (into the home's trash) or exported (copied).
"""

import hashlib
import json
import os
import re
import shutil
from collections import Counter
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
    raise KeyError(f"no gallery output {rid}")


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


# --- folders, delete, export ----------------------------------------------------------------

FOLDER_PART_MAX = 60
_EXPORT_NAME = re.compile(r"[\w .-]{1,80}")


def clean_folder(path) -> str:
    """A folder path as stored: trimmed parts joined by '/'; '' is the top level (unsorted)."""
    if path is None:
        return ""
    if not isinstance(path, str):
        raise TypeError("a folder is a path such as portraits/demons")
    trimmed = path.strip().strip("/")
    if not trimmed:
        return ""
    parts = [p.strip() for p in trimmed.split("/")]
    for p in parts:
        if not p or p in (".", "..") or len(p) > FOLDER_PART_MAX or any(ord(ch) < 32 for ch in p):
            raise ValueError(f"{path!r} is no folder: parts of 1 to {FOLDER_PART_MAX} characters, joined by /")
    return "/".join(parts)


def _parents(path: str) -> list[str]:
    """'a/b/c' -> ['a', 'a/b', 'a/b/c']."""
    parts = path.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]


def _inside(path: str, folder: str) -> bool:
    return path == folder or path.startswith(folder + "/")


def _saved_folders(home: Home) -> list[str]:
    path = home.galaxy_folders_path
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except ValueError:
        return []
    return [f for f in data if isinstance(f, str) and f] if isinstance(data, list) else []


def _save_folders(home: Home, folders: list[str]) -> None:
    write_atomic(home.galaxy_folders_path, json.dumps(sorted({f for f in folders if f}), ensure_ascii=False, indent=1))


def folders(home: Home, rows: list[dict] | None = None) -> list[dict]:
    """Every folder, saved or named by a row, with its parents, sorted, each with its own outputs' count."""
    rows = read_rows(home) if rows is None else rows
    counts = Counter(r.get("folder") or "" for r in rows)
    names = {p for f in [*_saved_folders(home), *counts] if f for p in _parents(f)}
    return [{"path": f, "count": counts.get(f, 0)} for f in sorted(names, key=str.lower)]


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


def _refolder(row: dict, folder: str) -> dict:
    if folder:
        row["folder"] = folder
    else:
        row.pop("folder", None)
    return row


def move(home: Home, ids, folder) -> int:
    """Put outputs into a folder ('' for unsorted); the folder stays listed after they leave."""
    folder = clean_folder(folder)
    wanted = _check_ids(home, ids)
    _edit_rows(home, lambda r: _refolder(r, folder) if row_id(r) in wanted else r)
    if folder:
        _save_folders(home, [*_saved_folders(home), folder])
    return len(wanted)


def _known(home: Home, path) -> str:
    path = clean_folder(path)
    if not path or path not in {f["path"] for f in folders(home)}:
        raise KeyError(f"no gallery folder {path or '(none)'}")
    return path


def add_folder(home: Home, path) -> str:
    path = clean_folder(path)
    if not path:
        raise ValueError("name the folder")
    if path in {f["path"] for f in folders(home)}:
        raise FileExistsError(f"the folder {path} already exists")
    _save_folders(home, [*_saved_folders(home), path])
    return path


def rename_folder(home: Home, path, to) -> str:
    """Rename a folder or move it into another (a/b to c/b); its subfolders and outputs go along."""
    path, to = _known(home, path), clean_folder(to)
    if not to:
        raise ValueError("name the folder")
    if to == path:
        return to
    if _inside(to, path):
        raise ValueError(f"{path} cannot move into itself")
    if to in {f["path"] for f in folders(home)}:
        raise FileExistsError(f"the folder {to} already exists")

    def moved(f: str) -> str:
        return to + f[len(path):] if _inside(f, path) else f

    _edit_rows(home, lambda r: _refolder(r, moved(r["folder"])) if r.get("folder") else r)
    _save_folders(home, [*map(moved, _saved_folders(home)), to])
    return to


def delete_folder(home: Home, path) -> str:
    """Remove a folder; its outputs and subfolders move up one level. Returns that level."""
    path = _known(home, path)
    parent = path.rpartition("/")[0]

    def up(f: str) -> str:
        if not _inside(f, path):
            return f
        rest = f[len(path) + 1:]
        return "/".join(p for p in (parent, rest) if p)

    _edit_rows(home, lambda r: _refolder(r, up(r["folder"])) if r.get("folder") else r)
    _save_folders(home, [*(up(f) for f in _saved_folders(home) if f != path), parent])
    return parent


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
