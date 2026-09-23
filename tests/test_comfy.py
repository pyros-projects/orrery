import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from orrery.comfy import (
    NODE_CLASS_MAPPINGS,
    OrreryLog,
    OrreryPrompt,
    log_outputs,
    run_prompt,
    save_png,
    state_token,
)
from orrery.home import Home

REPO = Path(__file__).resolve().parents[1]
SCENE = "@h3 t2va\nSHOT 5s | static\nA __animal__ sleeps.\nSFX: wind\n"


def test_prompt_node_expands_plain_templates(home):
    text, picks, seed = run_prompt("a __animal__", 4, "text", str(home))
    data = json.loads(picks)
    value = data["picks"][0]["value"]
    assert seed == 4 and text in (f"a {value}", f"an {value}")
    assert data["target"] == "text" and data["seed"] == 4
    assert data["picks"][0]["label"] == "__animal__"
    assert data["picks"][0]["keys"] == [f"__animal__={data['picks'][0]['value']}"]
    assert len(data["template"]) == 16


def test_prompt_node_compiles_screenplays_for_h3(home):
    text, picks, _ = run_prompt(SCENE, 1, "h3-base", str(home))
    assert text.startswith("integrated_multimodal_description: [Shot 1] ")
    assert json.loads(picks)["lint"] == []


def test_prompt_node_flat_target(home):
    text, _, _ = run_prompt(SCENE, 1, "flat", str(home))
    assert text.endswith("sleeps.")


def test_prompt_node_names_missing_libraries(home):
    with pytest.raises(ValueError, match="orrery lib gen smell"):
        run_prompt("a __smell__ day", 1, "text", str(home))


def test_state_token_changes_with_libraries_and_weights(home):
    before = state_token(Home(home))
    (home / "library" / "animal.yaml").write_text("- ibex\n")
    after_lib = state_token(Home(home))
    Home(home).save_weights({"__animal__=ibex": 2.0})
    assert len({before, after_lib, state_token(Home(home))}) == 3


def test_log_appends_one_galaxy_line_per_output(home):
    _, picks, _ = run_prompt("a __animal__", 2, "text", str(home))
    rows = log_outputs(Home(home), picks, ["out/a.png", "out/b.png"])
    lines = (home / "galaxy.jsonl").read_text().splitlines()
    assert len(rows) == len(lines) == 2
    row = json.loads(lines[1])
    assert row["media"] == "out/b.png" and row["seed"] == 2 and row["rating"] is None
    assert row["picks"][0]["label"] == "__animal__" and "ts" in row


def test_log_without_media_still_records_the_picks(home):
    _, picks, _ = run_prompt("a __animal__", 2, "text", str(home))
    [row] = log_outputs(Home(home), picks, [])
    assert row["media"] is None


def test_save_png_embeds_the_picks(tmp_path):
    image = np.zeros((8, 12, 3), dtype=np.float32)
    path = tmp_path / "x.png"
    save_png(image, path, '{"seed": 1}')
    with Image.open(path) as img:
        assert img.size == (12, 8)
        assert img.text["orrery"] == '{"seed": 1}'


def test_node_classes_declare_comfy_interfaces():
    assert set(NODE_CLASS_MAPPINGS) == {"OrreryPrompt", "OrreryLog"}
    inputs = OrreryPrompt.INPUT_TYPES()["required"]
    assert inputs["target"][0] == ["text", "h3-base", "flat"]
    assert OrreryPrompt.RETURN_NAMES == ("text", "picks", "seed")
    assert OrreryLog.OUTPUT_NODE is True


def test_node_pack_imports_from_the_repo_folder(monkeypatch):
    monkeypatch.setattr(sys, "path", [p for p in sys.path if not p.endswith("/src")])
    spec = importlib.util.spec_from_file_location("orrery_pack", REPO / "comfyui" / "__init__.py")
    pack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pack)
    assert set(pack.NODE_CLASS_MAPPINGS) == {"OrreryPrompt", "OrreryLog"}


def test_prompt_node_uses_a_preset_and_remembers_the_template(home):
    from orrery.presets import recall_template, save_preset
    save_preset(Home(home), "forest", "a __animal__ in the forest")
    text, picks, _ = run_prompt("ignored", 1, "text", str(home), preset="forest")
    assert text.endswith(" in the forest")
    assert recall_template(Home(home), json.loads(picks)["template"]) == "a __animal__ in the forest"


def test_prompt_node_offers_presets_in_a_dropdown(home):
    from orrery.presets import save_preset
    save_preset(Home(home), "forest", "x")
    choices = OrreryPrompt.INPUT_TYPES()["optional"]["preset"][0]
    assert choices[0] == "(none)" and "forest" in choices and "tutorial/01_first_wildcard" in choices
