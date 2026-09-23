"""The orrery home: where libraries, learned weights, config and history live.

Resolution order: explicit path, then `$ORRERY_HOME`, then `~/.orrery`.
The CLI and the ComfyUI nodes share it.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from orrery.library import Library, load_libraries

BUILTIN_DIR = Path(__file__).parent / "builtin"


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

    def libraries(self) -> dict[str, Library]:
        """Built-in libraries (H3 camera, styles, instruments), overridden by the user's files."""
        return {**load_libraries(BUILTIN_DIR), **load_libraries(self.library_dir)}

    def weights(self) -> dict[str, float]:
        if not self.weights_path.exists():
            return {}
        return {k: float(v) for k, v in json.loads(self.weights_path.read_text()).items()}

    def save_weights(self, weights: dict[str, float]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.weights_path.write_text(json.dumps(weights, indent=2, sort_keys=True))

    def config(self) -> dict:
        if not self.config_path.exists():
            return {}
        return yaml.safe_load(self.config_path.read_text()) or {}


def resolve_home(explicit: Path | str | None = None) -> Home:
    if explicit:
        return Home(Path(explicit))
    if env := os.environ.get("ORRERY_HOME"):
        return Home(Path(env))
    return Home(Path(os.environ.get("HOME", Path.home())) / ".orrery")
