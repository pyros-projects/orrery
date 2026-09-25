import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from orrery.comfy import (
    NODE_CLASS_MAPPINGS,
    OrreryLog,
    OrreryPrompt,
    linked_preset,
    log_outputs,
    run_prompt,
    save_png,
    shape,
    state_token,
)
from orrery.home import Home
from orrery.presets import save_preset

REPO = Path(__file__).resolve().parents[1]
SCENE = "@h3 t2va\nSHOT 5s | static\nA __animal__ sleeps.\nSFX: wind\n"


def test_prompt_node_expands_plain_templates(home):
    text, picks, seed, *_ = run_prompt("a __animal__", 4, "text", str(home))
    data = json.loads(picks)
    value = data["picks"][0]["value"]
    assert seed == 4 and text in (f"a {value}", f"an {value}")
    assert data["target"] == "text" and data["seed"] == 4
    assert data["picks"][0]["label"] == "__animal__"
    assert data["picks"][0]["keys"] == [f"__animal__={data['picks'][0]['value']}"]
    assert len(data["template"]) == 16


def test_prompt_node_compiles_screenplays_for_h3(home):
    text, picks, *_ = run_prompt(SCENE, 1, "h3-base", str(home))
    assert text.startswith("integrated_multimodal_description: [Shot 1] ")
    assert json.loads(picks)["lint"] == []


def test_prompt_node_flat_target(home):
    text, *_ = run_prompt(SCENE, 1, "flat", str(home))
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
    _, picks, *_ = run_prompt("a __animal__", 2, "text", str(home))
    rows = log_outputs(Home(home), picks, ["out/a.png", "out/b.png"])
    lines = (home / "galaxy.jsonl").read_text().splitlines()
    assert len(rows) == len(lines) == 2
    row = json.loads(lines[1])
    assert row["media"] == "out/b.png" and row["seed"] == 2 and row["rating"] is None
    assert row["picks"][0]["label"] == "__animal__" and "ts" in row


def test_log_without_media_still_records_the_picks(home):
    _, picks, *_ = run_prompt("a __animal__", 2, "text", str(home))
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
    assert OrreryPrompt.RETURN_NAMES == ("text", "picks", "seed", "width", "height", "length", "lora_stack",
                                         "load_index", "save_index", "previous", "previous_audio")
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
    text, picks, *_ = run_prompt("ignored", 1, "text", str(home), preset="forest")
    assert text.endswith(" in the forest")
    assert recall_template(Home(home), json.loads(picks)["template"]) == "a __animal__ in the forest"


def test_prompt_node_offers_presets_in_a_dropdown(home):
    from orrery.presets import save_preset
    save_preset(Home(home), "forest", "x")
    choices = OrreryPrompt.INPUT_TYPES()["optional"]["preset"][0]
    assert choices[0] == "(none)" and "forest" in choices and "tutorial/01_first_wildcard" in choices


def test_prompt_node_outputs_size_and_h3_length(home):
    *_, width, height, length, _, _, _ = run_prompt("a __animal__\n: x8 seed=100 w832 h1216", 1, "text", str(home))
    assert (width, height, length) == (832, 1216, 124)


def test_size_defaults_and_h3_ratio(home):
    assert shape("a fox") == (1024, 1024, 124)
    assert shape("@h3 t2va 16:9\nSHOT 5s\nA fox.") == (1344, 768, 124)
    assert shape("@h3 t2va 9:16\nSHOT 5s\nA fox.") == (768, 1344, 124)
    assert shape("@h3 t2va 21:9\nSHOT 5s\nA fox.")[:2] == (1536, 672)
    assert shape("@h3 t2va 16:9\n: w1280 h720\nSHOT 5s\nA fox.")[:2] == (1280, 720)


def test_h3_length_is_frames_on_the_17k_plus_5_grid(home):
    assert shape("@h3 t2va\nSHOT 4s | cut\nA.\nSHOT 3s\nB.\nSHOT 4s\nC.")[2] == 277
    assert shape("@h3 t2va\nSHOT 4s\nA.")[2] == 107


def test_prompt_node_records_its_linked_preset_and_whether_it_was_edited(home):
    save_preset(Home(home), "stills/fox", "a __animal__")
    _, clean, *_ = run_prompt("a __animal__", 1, "text", str(home), linked="stills/fox")
    _, edited, *_ = run_prompt("a __animal__ at dusk", 1, "text", str(home), linked="stills/fox")
    _, missing, *_ = run_prompt("a __animal__", 1, "text", str(home), linked="gone/away")
    assert (json.loads(clean)["preset"], json.loads(clean)["edited"]) == ("stills/fox", False)
    assert json.loads(edited)["edited"] is True
    assert json.loads(missing)["preset"] is None
    [row] = log_outputs(Home(home), clean, ["x.png"])
    assert (row["preset"], row["edited"]) == ("stills/fox", False)


def test_the_linked_preset_is_read_from_the_workflow(home):
    info = {"workflow": {"nodes": [{"id": 3, "properties": {}}, {"id": 7, "properties": {"orrery_preset": "krea/x"}}],
                         "definitions": {"subgraphs": [{"nodes": [{"id": 9, "properties": {"orrery_preset": "h3/y"}}]}]}}}
    assert linked_preset(info, "7") == "krea/x"
    assert linked_preset(info, "12:9") == "h3/y"
    assert linked_preset(info, "3") is None
    assert linked_preset(None, "7") is None


class FakeVideo:
    def __init__(self):
        self.saved = None

    def save_to(self, path, metadata=None, **_):
        Path(path).write_bytes(b"video")
        self.saved = (path, metadata)


def test_log_saves_a_video_with_its_picks_and_records_it(home, tmp_path, monkeypatch):
    folder = types.SimpleNamespace(
        get_output_directory=lambda: str(tmp_path),
        get_save_image_path=lambda prefix, out, w=0, h=0: (str(tmp_path), "orrery", 7, "", prefix))
    monkeypatch.setitem(sys.modules, "folder_paths", folder)
    _, picks, *_ = run_prompt("a __animal__", 3, "text", str(home))
    video = FakeVideo()
    ui = OrreryLog().log(picks, video=video, home=str(home))["ui"]
    path, metadata = video.saved
    assert path.endswith("orrery_00007_.mp4") and metadata["orrery"]["seed"] == 3
    assert ui == {"images": [{"filename": "orrery_00007_.mp4", "subfolder": "", "type": "output"}], "animated": (True,)}
    row = json.loads((home / "galaxy.jsonl").read_text().splitlines()[-1])
    assert row["media"] == path
    assert "video" in OrreryLog.INPUT_TYPES()["optional"]


def test_dials_change_a_preset_without_editing_it(home):
    save_preset(Home(home), "stills/fox", "$hero = __animal__\na $hero at dusk")
    text, picks, *_ = run_prompt("$hero = __animal__\na $hero at dusk", 1, "text", str(home),
                                 linked="stills/fox", params='{"hero": "lynx", "gone": "x"}')
    data = json.loads(picks)
    assert text == "a lynx at dusk"
    assert (data["preset"], data["edited"], data["params"]) == ("stills/fox", False, {"hero": "lynx"})
    from orrery.presets import recall_template
    assert recall_template(Home(home), data["template"]) == "$hero = __animal__\na $hero at dusk"
    [row] = log_outputs(Home(home), picks, ["x.png"])
    assert row["params"] == {"hero": "lynx"}


def test_the_node_takes_dials_and_reruns_when_they_change(home):
    assert "params" in OrreryPrompt.INPUT_TYPES()["optional"]
    a = OrreryPrompt.IS_CHANGED("$a = x\n$a", 1, "text", params='{"a": "y"}')
    b = OrreryPrompt.IS_CHANGED("$a = x\n$a", 1, "text", params='{"a": "z"}')
    assert a != b


REEL = """@h3 t2va 16:9
LORA: <lora:all:1>
$hero = __animal__
CHUNK
SHOT 5s
A $hero sleeps.
SFX: wind
CHUNK
LORA: <lora:two:0.5>
SHOT 4s
The $hero wakes.
SFX: birds
"""


def fake_loras(monkeypatch, files):
    module = types.ModuleType("folder_paths")
    module.get_filename_list = lambda kind: list(files) if kind == "loras" else []
    monkeypatch.setitem(sys.modules, "folder_paths", module)


def test_the_node_writes_the_chunk_its_segment_asks_for(home, monkeypatch):
    from orrery.comfy import h3_length
    fake_loras(monkeypatch, ["x/all.safetensors", "two.safetensors"])
    text, picks, _, width, height, length, stack, *_ = run_prompt(REEL, 1, "h3-base", str(home), segment=1)
    data = json.loads(picks)
    assert "wakes" in text and "sleeps" not in text
    assert (data["segment"], data["chunks"]) == (1, 2)
    assert (width, height, length) == (1344, 768, h3_length(4 + 22 / 24))
    assert stack == [("x/all.safetensors", 1.0, 1.0), ("two.safetensors", 0.5, 0.5)]
    first = run_prompt(REEL, 1, "h3-base", str(home))
    assert first[5] == h3_length(5) and json.loads(first[1])["segment"] == 0


def test_unresolved_loras_are_left_out_and_reported(home, monkeypatch):
    fake_loras(monkeypatch, ["x/all.safetensors"])
    _, picks, _, _, _, _, stack, *_ = run_prompt(REEL, 1, "h3-base", str(home), segment=1)
    assert stack == [("x/all.safetensors", 1.0, 1.0)]
    assert any("two" in i["message"] for i in json.loads(picks)["lint"])


def test_the_node_counts_segments_and_outputs_motion_context_indices(home):
    optional = OrreryPrompt.INPUT_TYPES()["optional"]
    assert optional["segment"][0] == "INT" and optional["segment"][1]["control_after_generate"]
    assert "forceInput" not in optional["segment"][1]
    assert OrreryPrompt.RETURN_NAMES[6:9] == ("lora_stack", "load_index", "save_index")
    assert OrreryPrompt.RETURN_TYPES[6:9] == ("LORA_STACK", "INT", "INT")
    *_, load, save = run_prompt(REEL, 1, "h3-base", str(home), segment=1)
    assert (load, save) == (1, 2)


def test_past_the_end_of_a_reel_blocks_the_rest_of_the_graph(home, monkeypatch):
    blocker = types.ModuleType("comfy_execution.graph_utils")

    class ExecutionBlocker:
        def __init__(self, message):
            self.message = message

    blocker.ExecutionBlocker = ExecutionBlocker
    monkeypatch.setitem(sys.modules, "comfy_execution", types.ModuleType("comfy_execution"))
    monkeypatch.setitem(sys.modules, "comfy_execution.graph_utils", blocker)
    outputs = OrreryPrompt().run(REEL, 1, "h3-base", home=str(home), segment=2)
    assert len(outputs) == len(OrreryPrompt.RETURN_TYPES)
    assert all(isinstance(o, ExecutionBlocker) and o.message is None for o in outputs)
    a = OrreryPrompt.IS_CHANGED(REEL, 1, "h3-base", segment=0)
    assert a != OrreryPrompt.IS_CHANGED(REEL, 1, "h3-base", segment=1)


def test_the_node_lets_its_llm_create_missing_libraries(home, monkeypatch):
    from orrery import comfy
    from orrery.llm import FakeBackend
    backend = FakeBackend([json.dumps(["velvet mule", "chrome boot", "paper sandal"])], name="qwen3vl_4b")
    monkeypatch.setattr(comfy, "llm_for", lambda h, clip=None, **_: backend)
    text, picks, *_ = run_prompt("a model in __runway_shoes:3__", 1, "text", str(home))
    assert text.split(" in ")[1] in ("velvet mule", "chrome boot", "paper sandal")
    assert any("Created __runway_shoes__" in i["message"] for i in json.loads(picks)["lint"])


def test_without_an_llm_a_missing_library_still_names_the_fix(home, monkeypatch):
    from orrery import comfy
    monkeypatch.setattr(comfy, "llm_for", lambda h, clip=None, **_: None)
    with pytest.raises(ValueError, match="runway_shoes"):
        run_prompt("a model in __runway_shoes__", 1, "text", str(home))


def test_the_node_takes_an_optional_clip_as_its_llm():
    assert OrreryPrompt.INPUT_TYPES()["optional"]["clip"][0] == "CLIP"


def test_the_node_leaves_unloading_to_comfyui(home, monkeypatch):
    """Unloading right after generate frees tensors ComfyUI's CUDA graph still holds: a warning flood."""
    from orrery import comfy
    from orrery.llm import FakeBackend
    backend = FakeBackend([json.dumps(["velvet mule"])])
    backend.release = lambda: pytest.fail("orrery must not unload the model itself")
    monkeypatch.setattr(comfy, "llm_for", lambda h, clip=None, **_: backend)
    run_prompt("a model in __runway_shoes__", 1, "text", str(home))


def test_the_llm_answers_within_the_max_tokens_setting(home):
    from orrery.comfy import llm_for
    from orrery.home import Home as H
    H(home).save_config({"llm": {"file": "qwen3vl_4b_bf16.safetensors", "max_tokens": 9000}})
    assert llm_for(H(home)).max_length == 9000
    H(home).save_config({"llm": {"file": "qwen3vl_4b_bf16.safetensors"}})
    assert llm_for(H(home)).max_length == 16000


def fake_llm(monkeypatch, reply):
    from orrery import comfy
    from orrery.llm import FakeBackend
    backend = FakeBackend([json.dumps(reply) if not isinstance(reply, str) else reply], name="qwen3vl_4b")
    monkeypatch.setattr(comfy, "llm_for", lambda h, clip=None, **_: backend)
    return backend


def test_the_llm_writes_a_slot_where_it_stands(home, monkeypatch):
    backend = fake_llm(monkeypatch, {"slot 1": "a woman drops her keys"})
    text, *_ = run_prompt("A street at dawn, --what happens next--.", 1, "text", str(home))
    assert text == "A street at dawn, a woman drops her keys."
    assert len(backend.prompts) == 1 and "A street at dawn, [slot 1]." in backend.prompts[0]


def test_a_slot_and_a_missing_library_share_the_one_request(home, monkeypatch):
    backend = fake_llm(monkeypatch, {"mood": ["A hush.", "A storm."], "slot 1": "she runs"})
    text, *_ = run_prompt("__mood__(one sentence) Then --what happens next--.", 1, "text", str(home))
    assert len(backend.prompts) == 1
    assert text.endswith("Then she runs.") and text.split(" Then")[0] in ("A hush.", "A storm.")


def test_the_model_sees_the_clip_it_continues(home, monkeypatch):
    backend = fake_llm(monkeypatch, {"slot 1": "he lets go"})
    frames = [object()] * 6
    run_prompt("--what happens next--", 1, "text", str(home), frames=frames)
    assert backend.images[0] is frames and "6 images" in backend.prompts[0]


def test_frames_alone_ask_the_model_nothing(home, monkeypatch):
    backend = fake_llm(monkeypatch, {})
    run_prompt("a quiet street", 1, "text", str(home), frames=[object()])
    assert backend.prompts == []


def test_without_an_llm_a_slot_names_the_fix(home, monkeypatch):
    from orrery import comfy
    monkeypatch.setattr(comfy, "llm_for", lambda h, clip=None, **_: None)
    with pytest.raises(ValueError, match="language model"):
        run_prompt("--what happens next--", 1, "text", str(home))


def test_an_unusable_answer_keeps_the_directions_and_says_so(home, monkeypatch):
    """A failed run would leave a gap in a Motion Context chain; the directions stand in instead."""
    fake_llm(monkeypatch, "I cannot see anything.")
    text, picks, *_ = run_prompt("A street, --a woman drops her keys--.", 1, "text", str(home))
    assert text == "A street, a woman drops her keys."
    assert any(i["severity"] == "warn" and "slot" in i["message"] for i in json.loads(picks)["lint"])


def test_the_node_hands_on_the_previous_clip_for_ref2va():
    assert OrreryPrompt.RETURN_NAMES[-2:] == ("previous", "previous_audio")
    assert OrreryPrompt.RETURN_TYPES[-2:] == ("IMAGE", "AUDIO")
    assert OrreryPrompt.INPUT_TYPES()["optional"]["latent_path"][1]["forceInput"] is True


def test_outside_a_chain_there_is_no_previous_clip(home):
    outputs = OrreryPrompt().run("a quiet street", 1, "text", home=str(home), segment=2)
    assert len(outputs) == len(OrreryPrompt.RETURN_TYPES) and outputs[-2:] == (None, None)


def test_only_slots_in_the_played_chunk_can_go_unanswered(home, monkeypatch):
    fake_llm(monkeypatch, {"mood": ["A hush."], "slot 1": "she runs"})
    reel = """@h3 t2va
CHUNK one
SHOT 5s
__mood__ --what happens next--
SFX: rain
CHUNK two
SHOT 5s
--a later scene--
SFX: rain
"""
    _, picks, *_ = run_prompt(reel, 1, "h3-base", str(home), segment=0)
    assert not [i for i in json.loads(picks)["lint"] if "got no text" in i["message"]]


def test_the_word_count_is_taken_after_the_slots_are_filled(home, monkeypatch):
    fake_llm(monkeypatch, {"slot 1": " ".join(["word"] * 360)})
    src = "@h3 ref2va 16:9\nsummary: A waits.\nCAST\nA (image 1): a man\nSHOT 5s\nA waits. --what happens--\nSFX: wind\n"
    _, picks, *_ = run_prompt(src, 1, "h3-base", str(home))
    assert not [i for i in json.loads(picks)["lint"] if "words" in i["message"]]
