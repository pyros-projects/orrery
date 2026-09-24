"""The orrery home: where libraries, learned weights, config and history live.

Resolution order: explicit path, then `$ORRERY_HOME`, then `~/.orrery`.
The CLI and the ComfyUI nodes share it.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from orrery.library import Library, load_libraries, save_library

BUILTIN_DIR = Path(__file__).parent / "builtin"


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file and rename, so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass(frozen=True)
class Home:
    root: Path

    @property
    def library_dir(self) -> Path:
        return self.root / "library"

    @property
    def weights_path(self) -> Path:
        return self.root / "weights.json"

    @property
    def galaxy_path(self) -> Path:
        return self.root / "galaxy.jsonl"

    @property
    def history_dir(self) -> Path:
        return self.root / "history"

    @property
    def presets_dir(self) -> Path:
        return self.root / "presets"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def config_path(self) -> Path:
        return self.root / "orrery.yaml"

    def library_file(self, name: str) -> Path | None:
        """The user's file for a library (yaml, else txt), or None when it only exists built in."""
        for suffix in (".yaml", ".txt"):
            path = self.library_dir / f"{name}{suffix}"
            if path.is_file():
                return path
        return None

    def library_path(self, name: str) -> Path:
        """Where orrery writes a library: YAML, in its folder."""
        return self.library_dir / f"{name}.yaml"

    def write_library(self, lib: Library) -> Path:
        """Save as YAML (folders included); a plain-text file of the same name retires."""
        path = self.library_path(lib.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        save_library(lib, path)
        path.with_suffix(".txt").unlink(missing_ok=True)
        return path

    def libraries(self) -> dict[str, Library]:
        """Built-in libraries (H3 camera, styles, instruments), overridden by the user's files."""
        return {**load_libraries(BUILTIN_DIR), **load_libraries(self.library_dir)}

    def weights(self) -> dict[str, float]:
        if not self.weights_path.exists():
            return {}
        return {k: float(v) for k, v in json.loads(self.weights_path.read_text()).items()}

    def save_weights(self, weights: dict[str, float]) -> None:
        write_atomic(self.weights_path, json.dumps(weights, indent=2, sort_keys=True))

    def config(self) -> dict:
        if not self.config_path.exists():
            return {}
        return yaml.safe_load(self.config_path.read_text()) or {}

    def save_config(self, config: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        write_atomic(self.config_path, yaml.safe_dump(config, sort_keys=False, allow_unicode=True))


def _user_home() -> Path:
    return Path(os.environ.get("HOME", Path.home()))


def _pointer() -> Path:
    """The home folder setting lives outside any home, so it can move the home."""
    base = os.environ.get("XDG_CONFIG_HOME") or _user_home() / ".config"
    return Path(base) / "orrery" / "home"


def home_setting() -> str:
    pointer = _pointer()
    return pointer.read_text(encoding="utf-8").strip() if pointer.is_file() else ""


def set_home_setting(path: str) -> None:
    """Point orrery at another home folder (created if missing); an empty path goes back to ~/.orrery."""
    pointer = _pointer()
    if not path.strip():
        pointer.unlink(missing_ok=True)
        return
    folder = Path(path).expanduser()
    if not folder.is_absolute():
        raise ValueError(f"the home folder must be an absolute path, not {path!r}")
    folder.mkdir(parents=True, exist_ok=True)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(pointer, str(folder))


def home_source(explicit: Path | str | None = None) -> tuple[Path, str]:
    """The home and where it comes from: explicit (the node's field, --home) > ORRERY_HOME >
    the setting > ~/.orrery."""
    if explicit:
        return Path(explicit), "explicit"
    if env := os.environ.get("ORRERY_HOME"):
        return Path(env), "env"
    if setting := home_setting():
        return Path(setting), "setting"
    return _user_home() / ".orrery", "default"


def resolve_home(explicit: Path | str | None = None) -> Home:
    return Home(home_source(explicit)[0])
