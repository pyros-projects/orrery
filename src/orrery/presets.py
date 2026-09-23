"""Prompt management: named presets and a content-addressed store of every used template.

- `@name` / `@folder/name` → the preset in <home>/presets/folder/name.orr
- `#hash` → the template recorded under that hash in <home>/templates/, the same
            hash a galaxy.jsonl line carries, so any output can be traced back
            to (and re-run from) the exact template that produced it.

Presets may start with YAML front matter for metadata, e.g. tags:

    ---
    tags: [moody, winter]
    ---
    @h3 t2va 16:9
    ...

Front matter is stripped before a template is expanded.
"""

import hashlib
import re
from pathlib import Path

import yaml

from orrery.home import Home

EXT = ".orr"
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


def template_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def split_front_matter(text: str) -> tuple[dict, str]:
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    return (meta if isinstance(meta, dict) else {}), text[m.end():]


def _join_front_matter(meta: dict, body: str) -> str:
    if not meta:
        return body
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=True,
                                    default_flow_style=None).strip() + "\n---\n" + body


def preset_name(raw: str) -> str:
    """Lower-case snake_case segments joined by '/'; '' if unusable."""
    segments = [re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") for s in raw.strip("/").split("/")]
    return "/".join(segments) if segments and all(segments) else ""


def _path(home: Home, name: str) -> Path:
    clean = preset_name(name)
    if not clean:
        raise ValueError(f"'{name}' is not a usable preset name")
    return home.presets_dir / f"{clean}{EXT}"


def preset_meta(home: Home, name: str) -> dict:
    path = _path(home, name)
    if not path.exists():
        raise KeyError(f"preset '{name}' does not exist (see: orrery preset list)")
    return split_front_matter(path.read_text(encoding="utf-8"))[0]


def list_presets(home: Home, tag: str | None = None, folder: str | None = None) -> list[str]:
    if not home.presets_dir.exists():
        return []
    names = sorted(p.relative_to(home.presets_dir).with_suffix("").as_posix()
                   for p in home.presets_dir.rglob(f"*{EXT}"))
    if folder:
        prefix = preset_name(folder) + "/"
        names = [n for n in names if n.startswith(prefix)]
    if tag:
        names = [n for n in names if tag in (preset_meta(home, n).get("tags") or [])]
    return names


def load_preset(home: Home, name: str) -> str:
    path = _path(home, name)
    if not path.exists():
        raise KeyError(f"preset '{name}' does not exist (see: orrery preset list)")
    return split_front_matter(path.read_text(encoding="utf-8"))[1]


def save_preset(home: Home, name: str, text: str, overwrite: bool = False,
                tags: list[str] | None = None) -> str:
    path = _path(home, name)
    if path.exists() and not overwrite:
        raise FileExistsError(f"preset '{preset_name(name)}' already exists (use --overwrite)")
    meta, body = split_front_matter(text)
    if tags:
        meta["tags"] = sorted({*(meta.get("tags") or []), *tags})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_join_front_matter(meta, body), encoding="utf-8")
    return preset_name(name)


def tag_preset(home: Home, name: str, add=(), remove=()) -> list[str]:
    path = _path(home, name)
    if not path.exists():
        raise KeyError(f"preset '{name}' does not exist (see: orrery preset list)")
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    tags = sorted({*(meta.get("tags") or []), *add} - set(remove))
    if tags:
        meta["tags"] = tags
    else:
        meta.pop("tags", None)
    path.write_text(_join_front_matter(meta, body), encoding="utf-8")
    return tags


def delete_preset(home: Home, name: str) -> None:
    path = _path(home, name)
    if not path.exists():
        raise KeyError(f"preset '{name}' does not exist (see: orrery preset list)")
    path.unlink()
    folder = path.parent
    while folder != home.presets_dir and not any(folder.iterdir()):
        folder.rmdir()
        folder = folder.parent


def remember_template(home: Home, text: str) -> str:
    digest = template_hash(text)
    path = home.templates_dir / f"{digest}{EXT}"
    if not path.exists():
        home.templates_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return digest


def recall_template(home: Home, digest: str) -> str | None:
    path = home.templates_dir / f"{digest}{EXT}"
    return path.read_text(encoding="utf-8") if path.exists() else None


def resolve_template(home: Home, arg: str) -> str:
    """`@preset`, `#hash`, a file path, or the template text itself (front matter stripped)."""
    ref = arg.strip()
    if re.fullmatch(r"@[\w/-]+", ref):
        return load_preset(home, ref[1:])
    if re.fullmatch(r"#[0-9a-f]{16}", ref):
        text = recall_template(home, ref[1:])
        if text is None:
            raise KeyError(f"no stored template {ref} in {home.templates_dir}")
        return text
    if "\n" not in arg and len(arg) < 4096 and Path(arg).is_file():
        return split_front_matter(Path(arg).read_text(encoding="utf-8"))[1]
    return arg
