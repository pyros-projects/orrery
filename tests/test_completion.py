import shutil
import subprocess
from pathlib import Path

import pytest

from orrery.comfy import OrreryPrompt
from orrery.completion import completion_data
from orrery.home import Home

REPO = Path(__file__).resolve().parents[1]


def test_libraries_carry_count_source_tags_and_preview(home):
    (home / "library" / "weather2.yaml").write_text("meta: {generated_by: Qwen3.5-4B}\nentries: [fog]\n")
    libs = {lib["name"]: lib for lib in completion_data(Home(home))["libraries"]}
    assert libs["animal"]["source"] == "user" and libs["animal"]["count"] == 3
    assert libs["creature"]["source"] == "builtin"
    assert "deep_sea" in libs["creature"]["tags"]
    assert libs["weather2"]["source"] == "llm"
    assert libs["animal"]["sample"] == ["fox", "heron", "owl"]


def test_h3_vocabulary_is_included(home):
    data = completion_data(Home(home))
    assert "push in" in data["h3"]["camera"]
    assert data["h3"]["modifiers"] == ["small", "large", "slow", "fast"]
    assert "dissolve" in data["h3"]["transitions"]


def test_template_widget_opts_out_of_other_autocompleters():
    options = OrreryPrompt.INPUT_TYPES()["required"]["template"][1]
    assert options["pysssss.autocomplete"] is False


def test_node_pack_serves_its_frontend():
    assert (REPO / "comfyui" / "web" / "orrery.js").exists()
    assert (REPO / "comfyui" / "web" / "orrery-complete.js").exists()
    assert 'WEB_DIRECTORY = "./web"' in (REPO / "comfyui" / "__init__.py").read_text()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_frontend_completion_logic():
    result = subprocess.run(["node", "--test", str(REPO / "tests" / "js" / "complete.test.mjs")],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
