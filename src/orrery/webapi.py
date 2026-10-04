"""The node app's HTTP API as plain functions: `fn(home, args) -> dict`, or a Path to send.

comfyui/__init__.py registers ROUTES with ComfyUI's server. `call` turns ApiError
(and crashes) into JSON error bodies, so every request answers with a sentence the
UI can show. The contract lives in docs/plan-node-app.md.
"""

import asyncio
import hashlib
import re
import traceback
from collections import Counter
from pathlib import Path

from orrery import endpoint, manager, pictures, uistate
from orrery import galaxy as gx
from orrery import presets as ps
from orrery.autolib import needs, write_apart
from orrery.chain import DEFAULT_CHAIN
from orrery.comfy_llm import can_write, llm_config, text_encoders
from orrery.completion import completion_data
from orrery.dsl import MissingLibrary, expand, override, strip_comments
from orrery.h3 import compile_scene
from orrery.home import BUILTIN_DIR, Home, home_setting, home_source, resolve_home, set_home_setting
from orrery.library import NAME, Entry, Library, load_library
from orrery.loras import lora_files, lora_stack
from orrery.manager import list_name
from orrery.reel import split_reel

TARGETS = ("text", "h3-base", "flat")
MAX_ROLLS = 12


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra) -> None:
        super().__init__(message)
        self.status, self.extra = status, extra

    def body(self) -> dict:
        return {"error": str(self), **self.extra}


def call(fn, args: dict) -> tuple[int, object]:
    args = dict(args)
    home = resolve_home(args.pop("home", None) or None)
    try:
        return 200, fn(home, args)
    except ApiError as err:
        return err.status, err.body()
    except Exception as err:  # noqa: BLE001 - a readable error beats a dead request
        traceback.print_exc()
        return 500, {"error": f"orrery: {err}"}


# --- argument helpers -----------------------------------------------------------------------

def _text(args: dict, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str):
        raise ApiError(400, f"'{key}' must be text.")
    return value


def _int(args: dict, key: str, default: int) -> int:
    try:
        return int(args.get(key, default))
    except (TypeError, ValueError):
        raise ApiError(400, f"'{key}' must be a whole number.") from None


def _tags(raw) -> list[str]:
    if not isinstance(raw, list | tuple):
        raise ApiError(400, "'tags' must be a list.")
    return sorted({re.sub(r"\s+", "_", str(t).strip().lower()) for t in raw if str(t).strip()})


def _preset_name(raw) -> str:
    raw = str(raw or "").strip()
    name = ps.preset_name(raw)
    if not name or raw.endswith("/"):
        raise ApiError(400, f"'{raw}' is not a usable preset name. Use letters and digits, "
                            "with / between folders.")
    return name


def _is_builtin(home: Home, name: str) -> bool:
    try:
        return ps.is_builtin(home, name)
    except KeyError:
        raise ApiError(404, f"There is no preset @{name}.") from None


def _user_preset(home: Home, raw) -> str:
    name = _preset_name(raw)
    if _is_builtin(home, name):
        raise ApiError(403, f"@{name} is built-in and read-only. Save a copy to change it.")
    return name


def _library_name(raw) -> str:
    """A library name as given when it is already one (film/genre, Film_Genre), else made usable."""
    name = str(raw or "").strip() if NAME.match(str(raw or "").strip()) else list_name(raw)
    if not name:
        raise ApiError(400, f"'{raw}' is not a usable library name. Use letters, digits and _.")
    if name.startswith(pictures.PREFIX):
        raise ApiError(403, f"__{name}__ holds the gallery's pictures: it follows the gallery and cannot be edited.")
    return name


# --- presets --------------------------------------------------------------------------------

def _owner(row: dict, by_hash: dict[str, str], known: set[str]) -> str | None:
    """The preset an output belongs to: the one it was rendered from unchanged (recorded by the
    node, so it survives later edits of the preset), else the preset whose text matches."""
    if row.get("preset") in known and not row.get("edited"):
        return row["preset"]
    return by_hash.get(row.get("template"))


def _outputs(home: Home) -> dict[str, list[str]]:
    """Ids of galaxy rows with a picture or video file, per owning preset, newest first."""
    by_hash, known = _preset_by_hash(home), set(ps.list_presets(home))
    by: dict[str, list[str]] = {}
    for row in gx.read_rows(home):
        if row["kind"] in ("image", "video") and (owner := _owner(row, by_hash, known)):
            by.setdefault(owner, []).append(row["id"])
    return by


def _card(home: Home, name: str, outputs: dict, with_text: bool = False) -> dict:
    meta, text = ps.preset_meta(home, name), ps.load_preset(home, name)
    digest = ps.template_hash(text)
    ids = outputs.get(name, [])
    card = {
        "name": name,
        "folder": name.rsplit("/", 1)[0] if "/" in name else "",
        "title": str(meta.get("title") or name.rsplit("/", 1)[-1].replace("_", " ")),
        "note": str(meta.get("note") or meta.get("lesson") or ""),
        "tags": list(meta.get("tags") or []),
        "builtin": ps.is_builtin(home, name),
        "hash": digest,
        "outputs": len(ids),
        "thumb": ids[0] if ids else None,
    }
    if with_text:
        card["text"] = text
    return card


def _full(home: Home, name: str) -> dict:
    return _card(home, name, _outputs(home), with_text=True)


def _meta_updates(args: dict) -> dict:
    updates = {k: str(args[k] or "").strip() for k in ("title", "note") if k in args}
    if "tags" in args:
        updates["tags"] = _tags(args["tags"])
    return updates


def presets(home: Home, args: dict) -> dict:
    names, outputs, ui = ps.list_presets(home), _outputs(home), uistate.load_ui(home)
    known = set(names)
    return {
        "presets": [_card(home, n, outputs) for n in names],
        "favorites": [n for n in ui["favorites"] if n in known],
        "recent": [n for n in ui["recent"] if n in known],
        **{flag: ui[flag] for flag in uistate.FLAGS},
        **{name: ui[name] for name in uistate.SIZES},
    }


def preset(home: Home, args: dict) -> dict:
    name = _preset_name(args.get("name"))
    _is_builtin(home, name)
    return _full(home, name)


def preset_save(home: Home, args: dict) -> dict:
    name, text = _preset_name(args.get("name")), _text(args, "text")
    try:
        user_exists, old = not ps.is_builtin(home, name), ps.preset_meta(home, name)
    except KeyError:
        user_exists, old = False, {}
    if user_exists and not args.get("overwrite"):
        raise ApiError(409, f"@{name} already exists. Overwrite it, or pick another name.",
                       exists=True)
    ps.save_preset(home, name, text, overwrite=True)
    fresh = ps.preset_meta(home, name)  # front matter that came with the text wins over old
    ps.set_meta(home, name, {**{k: v for k, v in old.items() if k not in fresh},
                             **_meta_updates(args)})
    return _full(home, name)


def preset_delete(home: Home, args: dict) -> dict:
    name = _user_preset(home, args.get("name"))
    ps.delete_preset(home, name)
    uistate.forget(home, name)
    return {"ok": True}


def preset_rename(home: Home, args: dict) -> dict:
    name, to = _user_preset(home, args.get("name")), _preset_name(args.get("to"))
    try:
        new = ps.rename_preset(home, name, to)
    except FileExistsError:
        raise ApiError(409, f"@{to} already exists. Pick another name.", exists=True) from None
    uistate.rename_everywhere(home, name, new)
    return _full(home, new)


def preset_meta(home: Home, args: dict) -> dict:
    name = _user_preset(home, args.get("name"))
    ps.set_meta(home, name, _meta_updates(args))
    return _full(home, name)


def favorite(home: Home, args: dict) -> dict:
    return {"favorites": uistate.set_favorite(home, _preset_name(args.get("name")),
                                              bool(args.get("on")))}


def recent(home: Home, args: dict) -> dict:
    return {"recent": uistate.touch_recent(home, _preset_name(args.get("name")))}


def ui_save(home: Home, args: dict) -> dict:
    """App switches kept in the home: `quickstart` (New templates open with their comments),
    `dividers` (chunk dividers in the editor), `timeline` (the reel's clips under its scenes), sample surfing's
    `surf_numbered` (#206), the live preview's `preview_light` (#205), and its sizes
    (`clip_min`: a clip's shorter side in the clips view; `take_min`: a take's, under it; `preview_fps`: the smooth live preview's pictures a second; `preview_edge`: its long edge)."""
    for flag in uistate.FLAGS:
        if flag in args:
            uistate.set_flag(home, flag, bool(args[flag]))
    for name in uistate.SIZES:
        if name in args:
            uistate.set_size(home, name, args[name])
    ui = uistate.load_ui(home)
    return {**{flag: ui[flag] for flag in uistate.FLAGS}, **{name: ui[name] for name in uistate.SIZES}}


def _preset_by_hash(home: Home) -> dict[str, str]:
    by: dict[str, str] = {}
    for name in ps.list_presets(home):
        digest = ps.template_hash(ps.load_preset(home, name))
        if digest not in by or not ps.is_builtin(home, name):  # a user preset wins
            by[digest] = name
    return by


def template(home: Home, args: dict) -> dict:
    digest = str(args.get("hash") or "")
    if not re.fullmatch(r"[0-9a-f]{16}", digest):
        raise ApiError(400, f"'{digest}' is not a template hash (16 hex digits).")
    text = ps.recall_template(home, digest)
    if text is None and (name := _preset_by_hash(home).get(digest)):
        text = ps.load_preset(home, name)
    if text is None:
        raise ApiError(404, f"No template #{digest} is stored in this orrery home.")
    return {"hash": digest, "text": text}


# --- libraries ------------------------------------------------------------------------------

def _source(home: Home, name: str, lib: Library) -> str:
    if lib.meta.get("gallery"):
        return "gallery"
    if lib.meta.get("generated_by"):
        return "llm"
    return "user" if home.library_file(name) else "builtin"


def _library_json(home: Home, name: str, lib: Library, weights: dict) -> dict:
    family = f"__{name}__"
    return {
        "name": name,
        "source": _source(home, name, lib),
        "entries": [{"value": e.value, "tags": list(e.tags), "weight": e.weight, "props": dict(e.props),
                     "learned": weights.get(f"{family}={e.value}", 1.0)} for e in lib.entries],
        "tags": sorted({t for e in lib.entries for t in e.tags}),
        "pending": bool(lib.meta.get("pending")),
        "pending_entries": list(lib.meta.get("pending_entries") or []),
        "directions": str(lib.meta.get("directions") or ""),
    }


_WORD = re.compile(r"[\w-]+")  # what `__lib#key:value__` can name


def _entries(raw) -> list[Entry]:
    if not isinstance(raw, list):
        raise ApiError(400, "'entries' must be a list.")
    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ApiError(400, "Every entry needs a value.")
        value = " ".join(str(item.get("value") or "").split())
        if not value:
            raise ApiError(400, "An entry is empty. Fill it in or remove it.")
        if value.lower() in seen:
            raise ApiError(400, f"'{value}' is in the list twice.", duplicate=value)
        seen.add(value.lower())
        try:
            weight = float(item.get("weight", 1.0))
        except (TypeError, ValueError):
            raise ApiError(400, f"The weight of '{value}' must be a number.") from None
        if not weight >= 0:
            raise ApiError(400, f"The weight of '{value}' can't be negative.")
        tags = dict.fromkeys(re.sub(r"\s+", "_", str(t).strip().lower())
                             for t in item.get("tags") or [] if str(t).strip())
        props = {}
        for key, val in (item.get("props") or {}).items():
            key, val = re.sub(r"\s+", "_", str(key).strip()), " ".join(str(val).split())
            if not (_WORD.fullmatch(key) and val):  # a word key; the value is any text ($w.sfx reads it)
                raise ApiError(400, f"A property of '{value}' is a word and a value, like gender:female.")
            props[key.lower()] = val
        out.append(Entry(value, tuple(tags), weight, tuple(sorted(props.items()))))
    return out


def libraries(home: Home, args: dict) -> dict:
    """The list of the Libraries tab: names, counts and sources, without entries (a home can hold a
    hundred thousand). `q`: only the libraries whose name or an entry holds it."""
    q = str(args.get("q") or "").strip().casefold()
    return {"libraries": [_library_head(home, n, lib) for n, lib in sorted(home.libraries().items())
                          if not q or q in n.casefold() or any(q in e.value.casefold() for e in lib.entries)]}


def _library_head(home: Home, name: str, lib: Library) -> dict:
    return {"name": name, "source": _source(home, name, lib), "count": len(lib.entries),
            "tags": sorted({t for e in lib.entries for t in e.tags}), "pending": bool(lib.meta.get("pending")),
            "pending_count": len(lib.meta.get("pending_entries") or []),
            "directions": str(lib.meta.get("directions") or "")}


def library(home: Home, args: dict) -> dict:
    """One library with its entries, when the tab opens it or a dial lists it."""
    name = str(args.get("name") or "")
    lib = home.libraries().get(name)
    if lib is None:
        raise ApiError(404, f"There is no library __{name}__.")
    return _library_json(home, name, lib, home.weights())


def library_save(home: Home, args: dict) -> dict:
    name = _library_name(args.get("name"))
    path = home.library_file(name)
    if not path and (BUILTIN_DIR / f"{name}.yaml").exists():
        raise ApiError(403, f"__{name}__ is built-in. Make it yours first.")
    entries, renames = _entries(args.get("entries")), args.get("renames") or {}
    if not isinstance(renames, dict):
        raise ApiError(400, "'renames' must map old entries to new ones.")
    meta = load_library(path, name).meta if path else {}
    path = home.write_library(Library(name, entries, {k: v for k, v in meta.items() if k != "builtin"}))
    weights, family = home.weights(), f"__{name}__"
    moved = [(o, n) for o, n in renames.items() if f"{family}={o}" in weights]
    for old, new in moved:
        weights[f"{family}={new}"] = weights.pop(f"{family}={old}")
    if moved:
        home.save_weights(weights)
    return _library_json(home, name, load_library(path, name), weights)


def library_own(home: Home, args: dict) -> dict:
    name = _library_name(args.get("name"))
    path = home.library_file(name)
    if not path:
        builtin = BUILTIN_DIR / f"{name}.yaml"
        if not builtin.exists():
            raise ApiError(404, f"There is no library __{name}__.")
        lib = load_library(builtin, name)
        path = home.write_library(Library(name, lib.entries, {k: v for k, v in lib.meta.items() if k != "builtin"}))
    return _library_json(home, name, load_library(path, name), home.weights())


def library_delete(home: Home, args: dict) -> dict:
    name = _library_name(args.get("name"))
    path = home.library_file(name)
    if not path:
        if (BUILTIN_DIR / f"{name}.yaml").exists():
            raise ApiError(403, f"__{name}__ is built-in and can't be deleted.")
        raise ApiError(404, f"There is no library __{name}__.")
    for twin in (path.with_suffix(".yaml"), path.with_suffix(".txt")):
        twin.unlink(missing_ok=True)
    return {"ok": True}


def library_rename(home: Home, args: dict) -> dict:
    """Rename a library of yours; weights, references in your libraries and presets follow."""
    name, to = _library_name(args.get("name")), _library_name(args.get("to"))
    try:
        summary = manager.rename_library(home, name, to)
    except ValueError as err:
        raise ApiError(400, str(err)) from None
    return {"name": to, **summary}


def _user_library(home: Home, args: dict) -> tuple[str, Path, Library]:
    name = _library_name(args.get("name"))
    path = home.library_file(name)
    if not path:
        raise ApiError(404, f"There is no library __{name}__ of yours.")
    return name, path, load_library(path, name)


def library_accept(home: Home, args: dict) -> dict:
    """Keep what the language model wrote: a new library, or the entries it added."""
    name, path, lib = _user_library(home, args)
    path = home.write_library(Library(name, lib.entries, {k: v for k, v in lib.meta.items() if k not in ("pending", "pending_entries")}))
    return _library_json(home, name, load_library(path, name), home.weights())


def library_discard(home: Home, args: dict) -> dict:
    """Drop what the language model wrote: the whole library if it made it, else the entries it added."""
    name, path, lib = _user_library(home, args)
    if lib.meta.get("pending"):
        path.unlink()
        return {"ok": True, "deleted": name}
    added = set(lib.meta.get("pending_entries") or [])
    path = home.write_library(Library(name, [e for e in lib.entries if e.value not in added],
                                      {k: v for k, v in lib.meta.items() if k != "pending_entries"}))
    return _library_json(home, name, load_library(path, name), home.weights())


# --- galaxy ---------------------------------------------------------------------------------

def _row_json(row: dict, by_hash: dict[str, str], known: set[str]) -> dict:
    media = row.get("media")
    return {
        "id": row["id"], "ts": row.get("ts"), "seed": row.get("seed"),
        "target": row.get("target"), "template": row.get("template"), "text": row.get("text"),
        "picks": row.get("picks") or [], "rating": row.get("rating"), "params": row.get("params") or {},
        "exports": row.get("exports") or {},
        "media_name": Path(media).name if media else None, "kind": row["kind"],
        "preset": _owner(row, by_hash, known), "folder": row.get("folder") or "",
    }


def _gx(fn, *args):
    """Run a galaxy edit, turning its errors into answers: bad input 400, unknown 404, taken 409."""
    try:
        return fn(*args)
    except FileExistsError as err:
        raise ApiError(409, str(err)) from None
    except (ValueError, TypeError) as err:
        raise ApiError(400, str(err)) from None
    except KeyError as err:
        raise ApiError(404, err.args[0]) from None


def _folder_list(home: Home, rows: list[dict] | None = None) -> dict:
    rows = gx.read_rows(home) if rows is None else rows
    return {"folders": gx.folders(home, rows), "total": len(rows),
            "unsorted": sum(1 for r in rows if not r.get("folder"))}


def galaxy(home: Home, args: dict) -> dict:
    """Outputs, newest first; `folder` shows one folder's own outputs ('' the unsorted ones)."""
    limit, wanted, owner = _int(args, "limit", 200), args.get("template") or None, args.get("preset") or None
    if limit < 1:
        raise ApiError(400, "'limit' must be at least 1.")
    folder = None if args.get("folder") is None else _gx(gx.clean_folder, args["folder"])
    by_hash, known, weights = _preset_by_hash(home), set(ps.list_presets(home)), home.weights()
    every = gx.read_rows(home)
    rows = [r for r in every if (wanted is None or r.get("template") == wanted)
            and (owner is None or _owner(r, by_hash, known) == owner)
            and (folder is None or (r.get("folder") or "") == folder)][:limit]
    keys = sorted({k for r in rows for p in r.get("picks") or [] for k in p.get("keys") or []})
    return {"rows": [_row_json(r, by_hash, known) for r in rows],
            "weights": {k: weights.get(k, 1.0) for k in keys}, **_folder_list(home, every)}


def _ids(args: dict) -> list[str]:
    ids = args.get("ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        raise ApiError(400, "'ids' must be a list of gallery output ids.")
    return ids


def galaxy_move(home: Home, args: dict) -> dict:
    return {"moved": _gx(gx.move, home, _ids(args), args.get("folder") or ""), **_folder_list(home)}


def galaxy_delete(home: Home, args: dict) -> dict:
    """Outputs leave the galaxy; their files go to the home's trash."""
    return {"deleted": _gx(gx.delete, home, _ids(args)), **_folder_list(home)}


def galaxy_export(home: Home, args: dict) -> dict:
    """Picture or video + prompt .txt pairs in export/<name>/, for training other models."""
    return _gx(gx.export, home, _ids(args), args.get("name"))


def galaxy_folder_add(home: Home, args: dict) -> dict:
    _gx(gx.add_folder, home, args.get("path"))
    return _folder_list(home)


def galaxy_folder_rename(home: Home, args: dict) -> dict:
    _gx(gx.rename_folder, home, args.get("path"), args.get("to"))
    return _folder_list(home)


def galaxy_folder_delete(home: Home, args: dict) -> dict:
    _gx(gx.delete_folder, home, args.get("path"))
    return _folder_list(home)


def _output_dir() -> Path:
    import folder_paths  # ComfyUI

    return Path(folder_paths.get_output_directory())


def galaxy_capture(home: Home, args: dict) -> dict:
    """Log the files a prompt's Save nodes wrote with the picks the Orrery node remembered for that
    prompt (Generate without Orrery Log). Only saved outputs, never temp previews or paths outside."""
    from orrery import runs
    from orrery.comfy import log_outputs

    picks = runs.recall(str(args.get("prompt_id") or ""), str(args.get("node") or ""))
    if picks is None:
        raise ApiError(404, "orrery has no run for that prompt (ComfyUI restarted since?).")
    root = _output_dir().resolve()
    paths = []
    for item in args.get("media") or []:
        if not isinstance(item, dict) or item.get("type") != "output":
            continue
        path = (root / str(item.get("subfolder") or "") / str(item.get("filename") or "")).resolve()
        if path.is_relative_to(root) and path.is_file():
            paths.append(str(path))
    if paths:
        log_outputs(home, picks, paths)
    return {"logged": len(paths)}


def galaxy_rate(home: Home, args: dict) -> dict:
    try:
        row, weights = gx.rate(home, str(args.get("id") or ""), args.get("rating"))
    except ValueError as err:
        raise ApiError(400, str(err)) from None
    except KeyError as err:
        raise ApiError(404, err.args[0]) from None
    return {"row": _row_json(row, _preset_by_hash(home), set(ps.list_presets(home))), "weights": weights}


def _file(fn, home: Home, args: dict) -> Path:
    try:
        return fn(home, str(args.get("id") or ""))
    except KeyError as err:
        raise ApiError(404, err.args[0]) from None


def galaxy_thumb(home: Home, args: dict) -> Path:
    return _file(gx.thumbnail, home, args)


def galaxy_media(home: Home, args: dict) -> Path:
    return _file(gx.media_path, home, args)


# --- the timeline: the chain's clips and the sent frames ------------------------------------

def _latent_path(args: dict) -> str:
    """The reel's chain folder under ComfyUI's output, as the app names it (#197), else h3_context."""
    return str(args.get("chain") or DEFAULT_CHAIN)


def chain(home: Home, args: dict) -> dict:
    """The clips the reel's chain holds (Orrery Film's or Chain Video's), by segment."""
    from orrery import film
    from orrery.chain import listing

    try:  # sample surfing (#206): a clip's takes, where it has more than one
        takes = {str(k): v for k, v in film.takes(_output_dir(), _latent_path(args)).items() if len(v) > 1}
    except film.FilmError:
        takes = {}
    return {"chain": _latent_path(args), **listing(_output_dir(), _latent_path(args)), "takes": takes}


def chain_pick(home: Home, args: dict) -> dict:
    """Sample surfing (#206): one take of a clip becomes the one the film, REMEMBER: and the next clip use."""
    from orrery import film

    try:
        return film.pick_take(_output_dir(), _latent_path(args), _int(args, "segment", -1), _text(args, "folder"))
    except film.FilmError as err:
        raise ApiError(400, str(err)) from None


def chain_delete(home: Home, args: dict) -> dict:
    """A take of a clip deleted from disk (#214); the film keeps the clip's newest other take, or ends before it."""
    from orrery import film

    try:
        return film.delete_take(_output_dir(), _latent_path(args), _int(args, "segment", -1), _text(args, "folder"))
    except film.FilmError as err:
        raise ApiError(400, str(err)) from None


def chain_clear(home: Home, args: dict) -> dict:
    """A clip's takes deleted at once (#234): all but the one in the film (`keep`), or that one too."""
    from orrery import film

    try:
        return film.delete_takes(_output_dir(), _latent_path(args), _int(args, "segment", -1), bool(args.get("keep", True)))
    except film.FilmError as err:
        raise ApiError(400, str(err)) from None


def chain_tree(home: Home, args: dict) -> dict:
    """The reel's takes as a tree (#240): every take, its parent, the film's path, the way last walked from each."""
    from orrery import film

    try:
        return film.tree(_output_dir(), _latent_path(args))
    except film.FilmError as err:
        raise ApiError(400, str(err)) from None


def chain_walk(home: Home, args: dict) -> dict:
    """The film through a take of the tree (#240): the path to it, and on from it as last walked."""
    from orrery import film

    try:
        return film.walk_to(_output_dir(), _latent_path(args), _text(args, "folder"))
    except film.FilmError as err:
        raise ApiError(400, str(err)) from None


def chain_end(home: Home, args: dict) -> dict:
    """The film ends after a clip (#240)."""
    from orrery import film

    try:
        return film.end_film(_output_dir(), _latent_path(args), _int(args, "segment", -1))
    except film.FilmError as err:
        raise ApiError(400, str(err)) from None


REELS = "reels"  # the reels the app names (#197) live under output/reels/


def chain_move(home: Home, args: dict) -> dict:
    """An unsaved reel saved as a preset (#197): its folder moves to the preset's name, so the next clip still
    continues the last. A folder already there is not touched: the reel then keeps its own."""
    from orrery.chain import chain_folder

    out, names = _output_dir().resolve(), [_text(args, k).strip().strip("/") for k in ("from", "to")]
    if not all(n.startswith(f"{REELS}/") and len(n) > len(REELS) + 1 for n in names):
        raise ApiError(400, f"Only a reel's own folder moves: both names start with {REELS}/.")
    source, target = (chain_folder(out, n) for n in names)
    if source is None or target is None or not source.is_relative_to(out / REELS) or not target.is_relative_to(out / REELS):
        raise ApiError(400, "A reel's folder stays inside ComfyUI's output.")
    if not source.is_dir():
        return {"moved": False, "chain": names[1]}  # no clip yet: the new name is simply used
    if target.exists() and any(target.iterdir()):
        return {"moved": False, "chain": names[0], "reason": f"{names[1]} already holds a reel"}
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.rmdir()
    source.rename(target)
    return {"moved": True, "chain": names[1]}


def chain_video(home: Home, args: dict) -> Path:
    from orrery.chain import clip_file

    if args.get("take"):  # one take of a clip (#206)
        from orrery import film
        path = film.take_file(_output_dir(), _latent_path(args), str(args["take"]))
        if path is None:
            raise ApiError(404, f"the reel has no take {args['take']}.")
        return path
    path = clip_file(_output_dir(), _latent_path(args), _int(args, "segment", -1))
    if path is None:
        raise ApiError(404, f"the chain has no clip for segment {args.get('segment')}.")
    return path


def chain_thumb(home: Home, args: dict) -> Path:
    src = chain_video(home, args)
    digest = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:16]
    try:
        return gx.thumb_file(src, home.root / "thumbs" / f"chain-{digest}.webp")
    except KeyError as err:
        raise ApiError(404, err.args[0]) from None


def anchor(home: Home, args: dict) -> Path:
    """The first frame stored for a sent image (Orrery Refs' anchors)."""
    from orrery import anchors

    image = str(args.get("image") or "")
    if not image.isdigit():
        raise ApiError(400, "'image' must be an image number.")
    path = anchors.folder(home, int(image)) / "0000.png"
    if not path.is_file():
        raise ApiError(404, f"image {image} has no stored anchor yet.")
    return path


def history_runs(home: Home, args: dict) -> dict:
    """The prompt history, newest first: `q` searches prompt, picks, preset and seed."""
    from orrery import history

    return history.read(home, limit=min(max(_int(args, "limit", 50), 1), 200), offset=max(_int(args, "offset", 0), 0),
                        query=str(args.get("q") or ""))


def writer_texts(home: Home, args: dict) -> dict:
    """The writers' prompts: each {text, default, edited}."""
    from orrery import writers

    return writers.texts(home)


def writer_save(home: Home, args: dict) -> dict:
    """Keep an edited writer text; a null or empty text goes back to the default."""
    from orrery import writers

    text = args.get("text")
    if text is not None and not isinstance(text, str):
        raise ApiError(400, "'text' must be a string or null.")
    try:
        return writers.save(home, str(args.get("name") or ""), text)
    except ValueError as err:
        raise ApiError(400, str(err)) from None


# --- roll -----------------------------------------------------------------------------------

ROLL_CLIPS = 6  # Roll on a reel shows this many clips at most
MAX_FREQUENCY = 500  # runs a frequency count may take
MAX_FREQUENCY_CLIPS = 200  # clips, when counting across a reel (each clip recomputes the ones before)


def _template_for(home: Home, args: dict) -> tuple[str, str]:
    """(template with the dials applied, target) from a roll or frequency request."""
    text, target = _text(args, "template"), args.get("target") or "text"
    if target not in TARGETS:
        raise ApiError(400, f"'target' must be one of {', '.join(TARGETS)}.")
    params = args.get("params") or {}
    if not isinstance(params, dict):
        raise ApiError(400, "'params' must be an object of binding: expression.")
    try:
        return ps.resolve_includes(home, override(text, {str(k): str(v) for k, v in params.items()})), target
    except (KeyError, FileNotFoundError, ValueError) as err:
        raise ApiError(400, str(err)) from None


def _run(loaded: tuple, text: str, seed: int, target: str, segment: int):
    """One expansion or compile, and its lint (LoRA warnings included when ComfyUI knows the files).
    `loaded`: the home's libraries and weights, loaded once for all the rolls of a request."""
    libraries, weights = loaded
    try:
        if target == "text":
            result = expand(text, seed, libraries, weights)
            return result, [{"severity": "warn", "message": w} for w in result.warnings]
        result = compile_scene(text, seed, libraries, weights, target=target, segment=segment)
    except MissingLibrary as err:
        raise ApiError(400, str(err), library=err.name) from None
    except ValueError as err:
        raise ApiError(400, str(err)) from None
    lint = [{"severity": i.severity, "message": i.message} for i in result.lint]
    if result.loras and (files := lora_files()):
        lint += [{"severity": "warn", "message": w} for w in lora_stack(result.loras, files)[1]]
    return result, lint


def generate_plan(home: Home, args: dict) -> dict:
    """What Generate queues: a LoRA sweep's runs times a grid's cells (orrery.batch.plan)."""
    from orrery import batch

    text, _ = _template_for(home, args)
    try:
        return batch.plan(text, home.libraries())
    except ValueError as err:
        raise ApiError(400, str(err)) from None


def _clips(home: Home, text: str, reel, seed: int, upto: int) -> int | None:
    """How many clips a reel plays at `seed` (looking up to `upto`); None when it plays on past that."""
    if not reel.jumps_on_rolls:
        return reel.segments
    from orrery.dsl import with_inline
    from orrery.reel import reel_path

    src, libraries = with_inline(strip_comments(text), home.libraries())
    path, ended = reel_path(split_reel(src), seed, libraries, home.weights(), upto)
    return len(path) if ended else None


def reel_walk(home: Home, args: dict) -> dict:
    """The chunk each clip of a reel plays at a seed: with GOTO lines the path can wait on what rolls."""
    from orrery.dsl import with_inline
    from orrery.loras import long_form
    from orrery.reel import MAX_WALK, reel_path

    text, _ = _template_for(home, args)
    src, libraries = with_inline(long_form(strip_comments(text)), home.libraries())
    reel = split_reel(src)
    if reel is None:
        return {"path": [], "ended": True}
    try:
        path, ended = reel_path(reel, _int(args, "seed", 0), libraries, home.weights(), MAX_WALK)
    except ValueError as err:
        raise ApiError(400, str(err)) from None
    return {"path": [block for block, _ in path], "ended": ended}


def reel_remembered(home: Home, args: dict) -> dict:
    """What each REMEMBER: line of a reel does at a seed (orrery.reel.remembered): the app shows where its
    frames go and cuts them from the clip they come from."""
    from orrery.dsl import with_inline
    from orrery.loras import long_form
    from orrery.reel import MAX_WALK, reel_path, remembered

    text, _ = _template_for(home, args)
    src, libraries = with_inline(long_form(strip_comments(text)), home.libraries())
    try:
        reel = split_reel(src)
        if reel is None:
            return {"lines": []}
        path, _ = (reel_path(reel, _int(args, "seed", 0), libraries, home.weights(), MAX_WALK)
                   if reel.jumps_on_rolls else reel.walk())
        return {"lines": remembered(reel, reel.starts(path))}
    except ValueError as err:
        raise ApiError(400, str(err)) from None


def _short(text, most: int = 72) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= most else text[:most - 1].rstrip(" ,") + "…"


def _shown(value) -> str:
    """An export as one line: its text, a list's items, an entry's value and its fields."""
    if isinstance(value, list):
        return ", ".join(map(str, value))
    if isinstance(value, dict):
        rest = " · ".join(f"{k} {v}" for k, v in value.items() if k != "value")
        return f"{value.get('value', '')}{f' · {rest}' if rest else ''}"
    return str(value)


def _slots(numbers: list[int]) -> str:
    """image 6–9, images 2, 5: how a member's pictures read at a line's end."""
    if not numbers:
        return ""
    if len(numbers) > 2 and numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f"images {numbers[0]}–{numbers[-1]}"
    return f"image{'s' if len(numbers) > 1 else ''} {', '.join(map(str, numbers))}"


def annotate(home: Home, args: dict) -> dict:
    """What lines of a template give at a seed, for the editor to show at their ends (#163): each binding
    as it rolled, each export, a grid's cells, and in a screenplay where each CAST member's pictures go
    (a named picture with its name). Errors leave a part empty: the editor shows what it can."""
    from orrery.dsl import parse, with_inline
    from orrery.loras import long_form

    text, target = _template_for(home, args)
    seed, libs = _int(args, "seed", 0), home.libraries()
    src = long_form(strip_comments(text))
    out: dict = {"bindings": {}, "fields": {}, "exports": {}, "grid": "", "cast": {}, "members": {}}
    grid = None
    try:
        if parse(src).params.grid is not None:
            from orrery import batch

            grid = batch.axes(*with_inline(src, libs))
            out["grid"] = _short(f"{batch.cells(grid)} runs: " + " × ".join(" · ".join(a.options) for a in grid), 110)
    except ValueError:
        pass
    try:
        for _ in range(8):  # a library still to be written stands in as its name, so the rest still shows
            try:
                x = expand(src, seed, libs, home.weights(), cell=0 if grid else None)
                break
            except MissingLibrary as err:
                libs = {**libs, err.name: Library(err.name, [Entry(f"\\__{err.name}\\__")])}  # escaped: shown, not rolled
        else:
            raise ValueError("too many libraries still to be written")
        out["bindings"] = {k: _short(v) for k, v in x.bound.items()}
        for name, expr in parse(src).bindings:  # a binding to one library: the fields of the entry it rolled
            m = re.match(r"^__([\w/]+?)(?:\[[^\]]*\]|#[\w-]+:\$?[\w.-]+)*__$", expr.strip())
            entry = m and libs.get(m.group(1)) and next((e for e in libs[m.group(1)].entries if e.value == x.bound.get(name)), None)
            if entry:
                out["fields"][name] = {k: _short(v, 160) for k, v in entry.props if k not in ("ids", "pictures")}
        out["exports"] = {k: _short(_shown(v)) for k, v in x.exports.items()}
    except (ValueError, KeyError, MissingLibrary):
        pass
    if target != "text" and src.lstrip().startswith("@h3"):
        try:
            c = compile_scene(src, seed, libs, home.weights(), segment=_int(args, "segment", 0), cell=0 if grid else None)
            for m in c.scene.cast:
                images = sorted({s.index for s in m.sources if s.kind == "image"})
                named = list(dict.fromkeys(c.pictures[n]["name"] for n in images if n in c.pictures))
                refmods = [s.name for s in m.sources if s.kind == "refmod"]
                parts = [_slots(images), *named, *(f"refmod {r}" for r in refmods)]
                out["cast"][m.name] = _short(" · ".join(p for p in parts if p) or "no picture in this clip", 90)
                dials = {i["image"]: i for i in c.images if i.get("member") == m.name}
                mods = {r["name"]: r for r in c.refmods}
                out["members"][m.name] = {  # who the member is in this clip, for the editor's hover (#147)
                    "who": " ".join(f"{m.head}{m.tail}".split()),
                    "pictures": [{"image": n, **({"name": c.pictures[n]["name"], "id": c.pictures[n].get("id")} if n in c.pictures else {}),
                                  **{k: dials[n][k] for k in ("strength", "from", "to", "start", "end") if n in dials and dials[n].get(k) is not None}}
                                 for n in images],
                    "refmods": [{"name": r, **{k: mods[r][k] for k in ("strength", "from", "to", "start", "end") if r in mods and mods[r].get(k) is not None}}
                                for r in refmods],
                    "voice": m.voice_note or "",
                }
        except (ValueError, KeyError, MissingLibrary):
            pass
    return out


def gallery_pictures(home: Home, args: dict) -> dict:
    """The gallery's pictures by preset, newest character first, for the editor's completion after
    `image ` (#137): a character's name, its pictures' gallery ids and who it is (its export, else its prompt)."""
    out = []
    for name, lib in sorted(pictures.libraries(home).items()):
        characters = []
        for entry in reversed(lib.entries[-PICTURES_MAX:]):
            ids = (entry.prop("ids") or "").splitlines()
            characters.append({"name": entry.value, "ids": ids[:4], "views": len(ids), "tags": list(entry.tags),
                               "who": _short(entry.prop("who") or entry.prop("prompt") or "", 110)})
        out.append({"preset": name.removeprefix(pictures.PREFIX), "count": len(lib.entries), "characters": characters})
    return {"presets": out}


PICTURES_MAX = 60  # characters per preset the completion lists, the newest


def roll(home: Home, args: dict) -> dict:
    text, target = _template_for(home, args)
    seed, n = _int(args, "seed", 0), min(max(_int(args, "n", 3), 1), MAX_ROLLS)
    reel = split_reel(text) if target != "text" else None
    # a reel shows its clips at one seed, from `start` (a few at a time); anything else shows n seeds
    start = max(_int(args, "start", 0), 0)
    total = _clips(home, text, reel, seed, start + ROLL_CLIPS) if reel else 0
    end = start + ROLL_CLIPS if reel and total is None else min(start + ROLL_CLIPS, total) if reel else 0
    runs = [(seed, k) for k in range(start, end)] if reel else [(s, None) for s in range(seed, seed + n)]
    rolls, loaded = [], (home.libraries(), home.weights())
    for s, segment in runs:
        result, lint = _run(loaded, text, s, target, segment or 0)
        rolls.append({"seed": s, "text": result.text, "lint": lint,
                      "picks": [{"label": p.label, "value": p.value, "keys": list(p.keys)}
                                for p in result.picks],
                      **({"segment": segment} if segment is not None else {})})
    return {"rolls": rolls}


def frequency(home: Home, args: dict) -> dict:
    """How often each value comes up: over n seeds, or over the first n clips of a reel at one seed."""
    text, target = _template_for(home, args)
    seed, n, across = _int(args, "seed", 0), min(max(_int(args, "n", 200), 1), MAX_FREQUENCY), args.get("across") or "seeds"
    reel = split_reel(text) if target != "text" else None
    if across == "clips":
        if not reel:
            raise ApiError(400, "Counting across clips needs a reel (SCENE lines) and a screenplay target.")
        n = min(n, MAX_FREQUENCY_CLIPS, _clips(home, text, reel, seed, n) or MAX_FREQUENCY_CLIPS)
        runs = [(seed, k) for k in range(n)]
    elif across == "seeds":
        segment = max(_int(args, "segment", 0), 0) if reel else 0
        runs = [(s, segment) for s in range(seed, seed + n)]
    else:
        raise ApiError(400, "'across' must be seeds or clips.")
    counts: dict[str, Counter] = {}
    lint: Counter = Counter()
    loaded = home.libraries(), home.weights()
    for s, segment in runs:
        result, issues = _run(loaded, text, s, target, segment)
        for p in result.picks:
            for key in p.keys:
                counts.setdefault(p.label, Counter())[key.split("=", 1)[1]] += 1
        lint.update({i["message"] for i in issues})
    return {
        "runs": len(runs),
        "labels": [{"label": label, "values": [{"value": v, "count": c} for v, c in values.most_common()]}
                   for label, values in counts.items()],
        "lint": [{"message": m, "count": c} for m, c in lint.most_common()],
    }


# --- home folder ----------------------------------------------------------------------------

def home_settings(home: Home, args: dict) -> dict:
    """Where orrery lives when a node's home field is empty, and why."""
    folder, source = home_source()
    return {"home": str(folder), "source": source, "setting": home_setting()}


def home_save(home: Home, args: dict) -> dict:
    try:
        set_home_setting(str(args.get("path") or ""))
    except ValueError as err:
        raise ApiError(400, str(err)) from None
    return home_settings(home, {})


# --- llm settings ---------------------------------------------------------------------------

def llm_settings(home: Home, args: dict) -> dict:
    cfg, api = llm_config(home), endpoint.config(home)
    value, where = endpoint.key(home, api)
    active = ({"kind": "api", "name": api["model"]} if api["source"] == "api" and api["model"]
              else {"kind": "comfy", "name": Path(cfg["file"]).stem} if cfg["file"] else None)
    return {"file": cfg["file"], "clip_type": cfg["clip_type"], "entries": int(cfg["entries"]),
            "max_tokens": int(cfg["max_tokens"]), "files": text_encoders(), "source": api["source"],
            "api": {"base_url": api["base_url"], "model": api["model"], "key_env": api["key_env"],
                    "key": endpoint.hint(value) if value else "", "key_from": where},
            "active": active}


def llm_save(home: Home, args: dict) -> dict:
    file = args.get("file") or None
    if file and not can_write(file):
        raise ApiError(400, f"{file} is a truncated text encoder (MiniMax H3's): it loads but cannot write. "
                            "Pick a Qwen3-VL build such as Krea 2's qwen3vl_4b.")
    source = str(args.get("source") or endpoint.config(home)["source"])
    if source not in ("comfy", "api"):
        raise ApiError(400, "'source' must be comfy or api.")
    config = home.config()
    api = {**((config.get("llm") or {}).get("api") or {})}
    api.update({k: str(args[k]).strip() for k in ("base_url", "model") if args.get(k) is not None})
    typed = str(args.get("key") or "").strip()
    if source == "api":  # the endpoint has to answer before it writes for orrery
        cfg = {**endpoint.config(home), **api}
        checked = endpoint.check(cfg["base_url"], typed or endpoint.key(home, cfg)[0], cfg["model"])
        if not checked["ok"]:
            raise ApiError(400, checked["error"])
    if typed:
        endpoint.save_key(home, api.get("key_env") or endpoint.DEFAULT_KEY_ENV, typed)
    llm = {**(config.get("llm") or {}), "file": file, "entries": min(max(_int(args, "entries", 12), 1), 200),
           "max_tokens": min(max(_int(args, "max_tokens", 16000), 64), 131072), "source": source,
           **({"api": api} if api else {})}
    if args.get("clip_type"):
        llm["clip_type"] = str(args["clip_type"])
    home.save_config({**config, "llm": llm})
    return llm_settings(home, {})


def llm_check(home: Home, args: dict) -> dict:
    """Whether an endpoint takes its key and its model answers, before it is saved; the models it offers."""
    cfg = {**endpoint.config(home), **{k: str(args[k]).strip() for k in ("base_url", "model") if args.get(k)}}
    return endpoint.check(cfg["base_url"], str(args.get("key") or "").strip() or endpoint.key(home, cfg)[0], cfg["model"])


def _input_picture(name) -> Path | None:
    """A picture ComfyUI holds, named as a Load Image node names it (`a.png`, `sub/a.png [output]`)."""
    if not name:
        return None
    import folder_paths  # ComfyUI

    path = Path(folder_paths.get_annotated_filepath(str(name))).resolve()
    roots = [Path(d).resolve() for d in (folder_paths.get_input_directory(), folder_paths.get_output_directory(),
                                         folder_paths.get_temp_directory())]
    if not path.is_file() or not any(path.is_relative_to(r) for r in roots):
        raise ApiError(400, f"No picture {name} in ComfyUI's input, output or temp folder.")
    return path


def write_idea(home: Home, args: dict) -> dict:
    """The Write menu over the API endpoint, outside ComfyUI's queue (#167): one idea, as Orrery Write gives it.
    `frames`: the files of the Load Image nodes wired into first_frame and last_frame."""
    from orrery import comfy_write, writers

    task = str(args.get("task") or "")
    if task not in writers.TASKS:
        raise ApiError(400, f"'task' must be one of {', '.join(writers.TASKS)}.")
    temperature = float(llm_config(home)["writer_temperature"])
    if endpoint.backend(home, temperature) is None:
        raise ApiError(400, "No API endpoint is set: the Write menu runs in ComfyUI's queue.")
    frames = args.get("frames") if isinstance(args.get("frames"), dict) else {}
    pictures_ = lambda: comfy_write.pick_frames(task, _input_picture(frames.get("first_frame")),
                                                _input_picture(frames.get("last_frame")))
    return comfy_write.write_idea(home, task, _text(args, "template"), _int(args, "seed", 0), _int(args, "idea", 0),
                                  args.get("params") or "", lambda: endpoint.backend(home, temperature), pictures_)


def write_libraries(home: Home, args: dict) -> dict:
    """Write now (#168): every library the template still needs, one request each, all at once."""
    from orrery.loras import long_form

    api = endpoint.backend(home)
    if api is None:
        raise ApiError(400, "Write now needs an API endpoint: set one in orrery's settings.")
    text, _ = _template_for(home, {**args, "target": "text"})
    wanted = needs(home, long_form(strip_comments(text)), int(llm_config(home)["entries"]))
    if not wanted:
        return {"asked": [], "notes": []}
    try:
        notes = write_apart(home, wanted, api)
    except RuntimeError as err:
        raise ApiError(502, str(err)) from None
    return {"asked": [n.name for n in wanted], "notes": notes}


ROUTES = [
    ("GET", "/orrery/completions", lambda home, args: completion_data(home)),
    ("GET", "/orrery/presets", presets),
    ("GET", "/orrery/preset", preset),
    ("POST", "/orrery/preset/save", preset_save),
    ("POST", "/orrery/preset/delete", preset_delete),
    ("POST", "/orrery/preset/rename", preset_rename),
    ("POST", "/orrery/preset/meta", preset_meta),
    ("POST", "/orrery/favorite", favorite),
    ("POST", "/orrery/recent", recent),
    ("POST", "/orrery/ui", ui_save),
    ("GET", "/orrery/template", template),
    ("GET", "/orrery/libraries", libraries),
    ("GET", "/orrery/library", library),
    ("POST", "/orrery/library/save", library_save),
    ("POST", "/orrery/library/own", library_own),
    ("POST", "/orrery/library/delete", library_delete),
    ("POST", "/orrery/library/rename", library_rename),
    ("GET", "/orrery/galaxy", galaxy),
    ("POST", "/orrery/galaxy/capture", galaxy_capture),
    ("POST", "/orrery/galaxy/rate", galaxy_rate),
    ("GET", "/orrery/galaxy/thumb", galaxy_thumb),
    ("GET", "/orrery/galaxy/media", galaxy_media),
    ("GET", "/orrery/chain", chain),
    ("GET", "/orrery/chain/thumb", chain_thumb),
    ("POST", "/orrery/chain/move", chain_move),
    ("POST", "/orrery/chain/pick", chain_pick),
    ("POST", "/orrery/chain/delete", chain_delete),
    ("POST", "/orrery/chain/clear", chain_clear),
    ("GET", "/orrery/chain/tree", chain_tree),
    ("POST", "/orrery/chain/walk", chain_walk),
    ("POST", "/orrery/chain/end", chain_end),
    ("GET", "/orrery/chain/video", chain_video),
    ("GET", "/orrery/anchor", anchor),
    ("GET", "/orrery/history", history_runs),
    ("GET", "/orrery/writers", writer_texts),
    ("POST", "/orrery/writers", writer_save),
    ("POST", "/orrery/galaxy/move", galaxy_move),
    ("POST", "/orrery/galaxy/delete", galaxy_delete),
    ("POST", "/orrery/galaxy/export", galaxy_export),
    ("POST", "/orrery/galaxy/folder/add", galaxy_folder_add),
    ("POST", "/orrery/galaxy/folder/rename", galaxy_folder_rename),
    ("POST", "/orrery/galaxy/folder/delete", galaxy_folder_delete),
    ("POST", "/orrery/roll", roll),
    ("POST", "/orrery/plan", generate_plan),
    ("POST", "/orrery/reel", reel_walk),
    ("POST", "/orrery/remembered", reel_remembered),
    ("POST", "/orrery/annotate", annotate),
    ("GET", "/orrery/pictures", gallery_pictures),
    ("POST", "/orrery/frequency", frequency),
    ("GET", "/orrery/home", home_settings),
    ("POST", "/orrery/home", home_save),
    ("GET", "/orrery/llm", llm_settings),
    ("POST", "/orrery/llm", llm_save),
    ("POST", "/orrery/llm/check", llm_check),
    ("POST", "/orrery/llm/libraries", write_libraries),
    ("POST", "/orrery/write", write_idea),
    ("POST", "/orrery/library/accept", library_accept),
    ("POST", "/orrery/library/discard", library_discard),
]


# routes that wait for a language model run in a thread, so ComfyUI's server answers meanwhile
SLOW = {llm_save, llm_check, write_libraries, write_idea, chain_pick, chain_delete, chain_clear, chain_walk, chain_end}


def _handler(fn, method: str, web):
    async def handle(request):
        args = dict(request.query)
        if method == "POST":
            try:
                body = await request.json()
            except ValueError:
                body = None
            if not isinstance(body, dict):
                return web.json_response({"error": "Send a JSON object."}, status=400)
            args.update(body)
        status, result = await asyncio.to_thread(call, fn, args) if fn in SLOW else call(fn, args)
        if isinstance(result, Path):
            return web.FileResponse(result)
        return web.json_response(result, status=status)
    return handle


def register(routes, web) -> None:
    """Attach ROUTES to an aiohttp route table, e.g. ComfyUI's PromptServer.instance.routes."""
    for method, path, fn in ROUTES:
        routes.route(method, path)(_handler(fn, method, web))
