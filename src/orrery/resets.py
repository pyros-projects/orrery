"""Resets from the Settings (#310): the ratings, the history, the gallery, the presets or the libraries back to
factory, or everything at once.

A reset deletes orrery's records. What was made by hand (presets, libraries, exported pairs) goes to the home's
trash instead, where it can still be fetched; so do the logged pictures and videos, when the reset is asked to take
the files too (they stay in ComfyUI's output otherwise). Everything at once leaves the home as a fresh install finds
it, the trash aside."""

import shutil
import time
from pathlib import Path

from orrery import galaxy, uistate
from orrery.home import Home, locked

WHAT = ("ratings", "history", "gallery", "presets", "libraries", "all")


def _gone(path: Path) -> bool:
    """Delete a file or a folder; True when there was one."""
    if path.is_dir():
        shutil.rmtree(path)
        return True
    if path.exists():
        path.unlink()
        return True
    return False


def _to_trash(home: Home, path: Path, label: str) -> Path | None:
    """A file or a folder into trash/<label> <time>/, kept there; None when there was nothing."""
    if not path.exists() or (path.is_dir() and not any(path.iterdir())):
        _gone(path)
        return None
    into = home.trash_dir / f"{label} {time.strftime('%Y-%m-%d %H.%M.%S')}"
    into.mkdir(parents=True, exist_ok=True)
    return Path(shutil.move(str(path), str(into / path.name)))


@locked
def reset_ratings(home: Home) -> int:
    """Every rating taken back, and the learned weights with them: the dice roll as before the first rating."""
    rated = sum(1 for r in galaxy.read_rows(home) if r.get("rating"))
    galaxy._edit_rows(home, lambda r: {**r, "rating": None} if r.get("rating") else r)
    _gone(home.weights_path)
    return rated


def delete_history(home: Home) -> int:
    from orrery import history

    runs = history.read(home, limit=1)["total"]
    _gone(home.root / history.FILE)
    return runs


@locked
def delete_gallery(home: Home, files: bool = False) -> dict:
    """The gallery's records gone: its outputs, collections, thumbnails, and the learned weights its ratings made.
    With `files`, the pictures and videos it logged go to the trash too."""
    rows = galaxy.read_rows(home)
    moved = 0
    if files:
        shown = {r.get("media") for r in rows if r.get("media")}
        into = home.trash_dir / f"gallery {time.strftime('%Y-%m-%d %H.%M.%S')}"
        for media in sorted(m for m in shown if Path(m).is_file()):
            into.mkdir(parents=True, exist_ok=True)
            src = Path(media)
            shutil.move(str(src), str(galaxy._free(into, src.stem, src.suffix)))
            moved += 1
    for path in (home.galaxy_path, home.galaxy_folders_path, home.root / "thumbs", home.weights_path):
        _gone(path)
    return {"outputs": len(rows), "files": moved}


def reset_presets(home: Home) -> int:
    """Your presets to the trash, and the favorites and recents with them: the built-in ones stay."""
    count = len(list(home.presets_dir.rglob("*.orr"))) if home.presets_dir.exists() else 0
    _to_trash(home, home.presets_dir, "presets")
    uistate.clear_lists(home)
    return count


def reset_libraries(home: Home) -> int:
    """Your libraries to the trash, their saved versions with them: the built-in ones stay."""
    count = len([p for p in home.library_dir.rglob("*") if p.suffix in (".yaml", ".txt")]) if home.library_dir.exists() else 0
    _to_trash(home, home.library_dir, "libraries")
    _to_trash(home, home.history_dir, "library versions")
    return count


def reset_all(home: Home, files: bool = False) -> dict:
    """Everything back to a fresh install: the gallery (its files too, when asked), the ratings, the history, your
    presets, libraries and exports (to the trash), the settings, the API key, the remembered templates, the Refs'
    anchors and every cache. Only the trash stays."""
    done = {"gallery": delete_gallery(home, files), "history": delete_history(home),
            "presets": reset_presets(home), "libraries": reset_libraries(home)}
    _to_trash(home, home.export_dir, "exports")
    if home.root.exists():
        for path in home.root.iterdir():
            if path != home.trash_dir:
                _gone(path)
    return done


def reset(home: Home, what: str, files: bool = False):
    if what not in WHAT:
        raise ValueError(f"a reset is one of {', '.join(WHAT)}")
    return {"ratings": lambda: reset_ratings(home), "history": lambda: delete_history(home),
            "gallery": lambda: delete_gallery(home, files), "presets": lambda: reset_presets(home),
            "libraries": lambda: reset_libraries(home), "all": lambda: reset_all(home, files)}[what]()
