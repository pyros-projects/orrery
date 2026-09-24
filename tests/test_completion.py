import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from orrery.comfy import OrreryPrompt
from orrery.completion import completion_data, lora_files
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
    files = sorted(str(f) for f in (REPO / "tests" / "js").glob("*.test.mjs"))
    result = subprocess.run(["node", "--test", *files],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_loras_are_named_the_way_lora_manager_resolves_them(home):
    files = ["minimax/turbo/H3-PK-Parasyte-Turbo.safetensors", "Motion_Repair.safetensors", "style/indie90s_h3.ckpt"]
    assert completion_data(Home(home), loras=files)["loras"] == [
        {"name": "H3-PK-Parasyte-Turbo", "folder": "minimax/turbo"},
        {"name": "indie90s_h3", "folder": "style"},
        {"name": "Motion_Repair", "folder": ""},
    ]


def test_lora_files_come_from_comfyui_and_are_empty_outside_it(home, monkeypatch):
    assert completion_data(Home(home))["loras"] == [] and lora_files() == []
    fake = types.ModuleType("folder_paths")
    fake.get_filename_list = lambda kind: ["a\\b.safetensors"] if kind == "loras" else ["nope"]
    monkeypatch.setitem(sys.modules, "folder_paths", fake)
    assert lora_files() == ["a\\b.safetensors"]  # as ComfyUI spells it: get_full_path reads it back
    assert completion_data(Home(home))["loras"] == [{"name": "b", "folder": "a"}]
