"""The node app's HTTP API as plain functions: `fn(home, args) -> dict`, or a Path to send.

comfyui/__init__.py registers ROUTES with ComfyUI's server. `call` turns ApiError
(and crashes) into JSON error bodies, so every request answers with a sentence the
UI can show. The contract lives in docs/plan-node-app.md.
"""

import re
import traceback
from collections import Counter
from pathlib import Path

from orrery import galaxy as gx
from orrery import manager, uistate
from orrery import presets as ps
from orrery.comfy_llm import can_write, llm_config, text_encoders
from orrery.completion import completion_data
from orrery.dsl import MissingLibrary, expand, override
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
    weights = home.weights()
    return {"libraries": [_library_json(home, n, lib, weights)
                          for n, lib in sorted(home.libraries().items())]}


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
        "media_name": Path(media).name if media else None, "kind": row["kind"],
        "preset": _owner(row, by_hash, known),
    }


def galaxy(home: Home, args: dict) -> dict:
    limit, wanted, owner = _int(args, "limit", 200), args.get("template") or None, args.get("preset") or None
    if limit < 1:
        raise ApiError(400, "'limit' must be at least 1.")
    by_hash, known, weights = _preset_by_hash(home), set(ps.list_presets(home)), home.weights()
    rows = [r for r in gx.read_rows(home) if (wanted is None or r.get("template") == wanted)
            and (owner is None or _owner(r, by_hash, known) == owner)][:limit]
    keys = sorted({k for r in rows for p in r.get("picks") or [] for k in p.get("keys") or []})
    return {"rows": [_row_json(r, by_hash, known) for r in rows],
            "weights": {k: weights.get(k, 1.0) for k in keys}}


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


def _run(home: Home, text: str, seed: int, target: str, segment: int):
    """One expansion or compile, and its lint (LoRA warnings included when ComfyUI knows the files)."""
    try:
        if target == "text":
            return expand(text, seed, home.libraries(), home.weights()), []
        result = compile_scene(text, seed, home.libraries(), home.weights(), target=target, segment=segment)
    except MissingLibrary as err:
        raise ApiError(400, str(err), library=err.name) from None
    except ValueError as err:
        raise ApiError(400, str(err)) from None
    lint = [{"severity": i.severity, "message": i.message} for i in result.lint]
    if result.loras and (files := lora_files()):
        lint += [{"severity": "warn", "message": w} for w in lora_stack(result.loras, files)[1]]
    return result, lint


def roll(home: Home, args: dict) -> dict:
    text, target = _template_for(home, args)
    seed, n = _int(args, "seed", 0), min(max(_int(args, "n", 3), 1), MAX_ROLLS)
    reel = split_reel(text) if target != "text" else None
    # a reel shows its clips at one seed, from `start` (a few at a time); anything else shows n seeds
    start = max(_int(args, "start", 0), 0)
    end = start + ROLL_CLIPS if reel and reel.segments is None else min(start + ROLL_CLIPS, reel.segments) if reel else 0
    runs = [(seed, k) for k in range(start, end)] if reel else [(s, None) for s in range(seed, seed + n)]
    rolls = []
    for s, segment in runs:
        result, lint = _run(home, text, s, target, segment or 0)
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
            raise ApiError(400, "Counting across clips needs a reel (CHUNK lines) and a screenplay target.")
        n = min(n, MAX_FREQUENCY_CLIPS, reel.segments or MAX_FREQUENCY_CLIPS)
        runs = [(seed, k) for k in range(n)]
    elif across == "seeds":
        segment = max(_int(args, "segment", 0), 0) if reel else 0
        runs = [(s, segment) for s in range(seed, seed + n)]
    else:
        raise ApiError(400, "'across' must be seeds or clips.")
    counts: dict[str, Counter] = {}
    lint: Counter = Counter()
    for s, segment in runs:
        result, issues = _run(home, text, s, target, segment)
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
    cfg = llm_config(home)
    return {"file": cfg["file"], "clip_type": cfg["clip_type"], "entries": int(cfg["entries"]),
            "max_tokens": int(cfg["max_tokens"]), "files": text_encoders()}


def llm_save(home: Home, args: dict) -> dict:
    file = args.get("file") or None
    if file and not can_write(file):
        raise ApiError(400, f"{file} is a truncated text encoder (MiniMax H3's): it loads but cannot write. "
                            "Pick a Qwen3-VL build such as Krea 2's qwen3vl_4b.")
    config = home.config()
    llm = {**(config.get("llm") or {}), "file": file, "entries": min(max(_int(args, "entries", 12), 1), 200),
           "max_tokens": min(max(_int(args, "max_tokens", 16000), 64), 131072)}
    if args.get("clip_type"):
        llm["clip_type"] = str(args["clip_type"])
    home.save_config({**config, "llm": llm})
    return llm_settings(home, {})


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
    ("GET", "/orrery/template", template),
    ("GET", "/orrery/libraries", libraries),
    ("POST", "/orrery/library/save", library_save),
    ("POST", "/orrery/library/own", library_own),
    ("POST", "/orrery/library/delete", library_delete),
    ("POST", "/orrery/library/rename", library_rename),
    ("GET", "/orrery/galaxy", galaxy),
    ("POST", "/orrery/galaxy/capture", galaxy_capture),
    ("POST", "/orrery/galaxy/rate", galaxy_rate),
    ("GET", "/orrery/galaxy/thumb", galaxy_thumb),
    ("GET", "/orrery/galaxy/media", galaxy_media),
    ("POST", "/orrery/roll", roll),
    ("POST", "/orrery/frequency", frequency),
    ("GET", "/orrery/home", home_settings),
    ("POST", "/orrery/home", home_save),
    ("GET", "/orrery/llm", llm_settings),
    ("POST", "/orrery/llm", llm_save),
    ("POST", "/orrery/library/accept", library_accept),
    ("POST", "/orrery/library/discard", library_discard),
]


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
        status, result = call(fn, args)
        if isinstance(result, Path):
            return web.FileResponse(result)
        return web.json_response(result, status=status)
    return handle


def register(routes, web) -> None:
    """Attach ROUTES to an aiohttp route table, e.g. ComfyUI's PromptServer.instance.routes."""
    for method, path, fn in ROUTES:
        routes.route(method, path)(_handler(fn, method, web))
