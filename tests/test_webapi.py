import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image

from orrery import webapi
from orrery.galaxy import row_id
from orrery.home import Home
from orrery.presets import load_preset, preset_meta, remember_template, save_preset, template_hash
from orrery.webapi import ROUTES, ApiError, call, register

CARD = {"name", "folder", "title", "note", "tags", "builtin", "hash", "outputs", "thumb"}


def api(home, fn, **args):
    return call(fn, {"home": str(home), **args})


def ok(home, fn, **args):
    status, body = api(home, fn, **args)
    assert status == 200, body
    return body


def log_row(home, tmp_path, template_text, seed=1, name="a.png", keys=("__animal__=fox",), **extra):
    path = tmp_path / name
    Image.new("RGB", (64, 96), "teal").save(path)
    r = {"ts": f"2026-09-24T00:00:0{seed}+00:00", "media": str(path), "seed": seed, "target": "text",
         "template": remember_template(Home(home), template_text), "text": "a fox", "rating": None,
         "picks": [{"label": "__animal__", "value": "fox", "keys": list(keys)}], **extra}
    with (home / "galaxy.jsonl").open("a") as f:
        f.write(json.dumps(r) + "\n")
    return row_id(r)


# --- plumbing -------------------------------------------------------------------------------

def test_routes_cover_the_contract():
    paths = {(m, p) for m, p, _ in ROUTES}
    assert paths == {
        ("GET", "/orrery/completions"), ("GET", "/orrery/presets"), ("GET", "/orrery/preset"),
        ("POST", "/orrery/preset/save"), ("POST", "/orrery/preset/delete"),
        ("POST", "/orrery/preset/rename"), ("POST", "/orrery/preset/meta"),
        ("POST", "/orrery/favorite"), ("POST", "/orrery/recent"), ("POST", "/orrery/ui"), ("GET", "/orrery/template"),
        ("GET", "/orrery/libraries"), ("GET", "/orrery/library"), ("POST", "/orrery/library/save"),
        ("POST", "/orrery/library/own"), ("POST", "/orrery/library/delete"), ("POST", "/orrery/library/rename"), ("POST", "/orrery/galaxy/capture"),
        ("GET", "/orrery/galaxy"), ("POST", "/orrery/galaxy/rate"),
        ("GET", "/orrery/galaxy/thumb"), ("GET", "/orrery/galaxy/media"), ("POST", "/orrery/roll"),
        ("POST", "/orrery/galaxy/move"), ("POST", "/orrery/galaxy/delete"), ("POST", "/orrery/galaxy/export"),
        ("POST", "/orrery/galaxy/folder/add"), ("POST", "/orrery/galaxy/folder/rename"),
        ("POST", "/orrery/galaxy/folder/delete"),
        ("POST", "/orrery/frequency"), ("GET", "/orrery/llm"), ("POST", "/orrery/llm"),
        ("POST", "/orrery/library/accept"), ("POST", "/orrery/library/discard"),
        ("GET", "/orrery/home"), ("POST", "/orrery/home"),
        ("GET", "/orrery/chain"), ("GET", "/orrery/chain/thumb"), ("GET", "/orrery/chain/video"),
        ("GET", "/orrery/anchor"),
        ("GET", "/orrery/history"),
        ("GET", "/orrery/writers"),
        ("POST", "/orrery/writers"),
        ("POST", "/orrery/plan"),
        ("POST", "/orrery/reel"),
        ("POST", "/orrery/remembered"), ("POST", "/orrery/annotate"),
    }


def test_call_maps_api_errors_and_crashes_to_json(home):
    def boom(h, args):
        raise ApiError(409, "taken", exists=True)

    def crash(h, args):
        raise RuntimeError("disk on fire")

    assert api(home, boom) == (409, {"error": "taken", "exists": True})
    status, body = api(home, crash)
    assert status == 500 and "disk on fire" in body["error"]


def test_call_uses_the_home_argument(home, tmp_path):
    other = tmp_path / "elsewhere"
    status, _ = call(webapi.favorite, {"home": str(other), "name": "a", "on": True})
    assert status == 200 and (other / "ui.json").exists()


class FakeRoutes:
    def __init__(self):
        self.handlers = {}

    def route(self, method, path):
        def attach(fn):
            self.handlers[(method, path)] = fn
            return fn
        return attach


class FakeWeb:
    @staticmethod
    def json_response(data, status=200):
        return ("json", status, data)

    @staticmethod
    def FileResponse(path):
        return ("file", path)


class FakeRequest:
    def __init__(self, query=None, body=None, broken=False):
        self.query, self._body, self._broken = query or {}, body, broken

    async def json(self):
        if self._broken:
            raise ValueError("Expecting value")
        return self._body


def test_register_attaches_every_route_through_one_adapter(home, tmp_path):
    routes = FakeRoutes()
    register(routes, FakeWeb)
    assert set(routes.handlers) == {(m, p) for m, p, _ in ROUTES}

    def hit(method, path, **request):
        return asyncio.run(routes.handlers[(method, path)](FakeRequest(**request)))

    q = {"home": str(home)}
    assert hit("POST", "/orrery/favorite", query=q, body={"name": "a", "on": True}) == \
        ("json", 200, {"favorites": ["a"]})
    kind, status, body = hit("GET", "/orrery/presets", query=q)
    assert (kind, status) == ("json", 200) and body["favorites"] == [] and body["quickstart"] is True
    assert hit("POST", "/orrery/ui", query=q, body={"quickstart": False}) == \
        ("json", 200, {"quickstart": False, "dividers": True, "timeline": True, "log_prompts": True, "clip_min": 360})
    assert hit("GET", "/orrery/presets", query=q)[2]["quickstart"] is False
    assert hit("GET", "/orrery/preset", query={**q, "name": "nope"})[1] == 404
    assert hit("POST", "/orrery/recent", query=q, broken=True)[1] == 400
    assert hit("POST", "/orrery/recent", query=q, body=["a"])[1] == 400
    rid = log_row(home, tmp_path, "a __animal__")
    assert hit("GET", "/orrery/galaxy/media", query={**q, "id": rid}) == ("file", tmp_path / "a.png")


# --- presets --------------------------------------------------------------------------------

def test_presets_list_cards_with_outputs_favorites_and_recents(home, tmp_path):
    save_preset(Home(home), "stills/mine", "a __animal__")
    first = log_row(home, tmp_path, "a __animal__", seed=1, name="1.png")
    newest = log_row(home, tmp_path, "a __animal__", seed=2, name="2.png")
    ok(home, webapi.favorite, name="stills/mine", on=True)
    ok(home, webapi.recent, name="tutorial/01_first_wildcard")
    data = ok(home, webapi.presets)
    cards = {c["name"]: c for c in data["presets"]}
    mine, lesson = cards["stills/mine"], cards["tutorial/01_first_wildcard"]
    assert set(mine) == CARD
    assert (mine["folder"], mine["builtin"], mine["outputs"], mine["thumb"]) == ("stills", False, 2, newest)
    assert mine["hash"] == template_hash("a __animal__") and first != newest
    assert lesson["builtin"] and lesson["note"] and lesson["title"].startswith("01")
    assert (lesson["outputs"], lesson["thumb"]) == (0, None)
    assert data["favorites"] == ["stills/mine"] and data["recent"] == ["tutorial/01_first_wildcard"]


def test_top_level_presets_have_an_empty_folder_and_a_default_title(home):
    save_preset(Home(home), "night_walk", "x")
    card = ok(home, webapi.preset, name="night_walk")
    assert (card["folder"], card["title"], card["text"]) == ("", "night walk", "x")


def test_missing_preset_is_404(home):
    assert api(home, webapi.preset, name="nope")[0] == 404
    assert api(home, webapi.preset, name="///")[0] == 400


def test_save_creates_then_refuses_to_clobber(home):
    card = ok(home, webapi.preset_save, name="Stills/Night Walk", text="a __animal__",
              title="Night walk", tags=["moody", "Moody"], note="why")
    assert card["name"] == "stills/night_walk" and card["tags"] == ["moody"]
    status, body = api(home, webapi.preset_save, name="stills/night_walk", text="other")
    assert status == 409 and body["exists"] is True
    assert load_preset(Home(home), "stills/night_walk") == "a __animal__"


def test_overwrite_keeps_title_tags_and_note(home):
    ok(home, webapi.preset_save, name="a", text="one", title="A", tags=["x"], note="n")
    card = ok(home, webapi.preset_save, name="a", text="two", overwrite=True)
    assert (card["text"], card["title"], card["tags"], card["note"]) == ("two", "A", ["x"], "n")


def test_saving_under_a_builtin_name_makes_a_shadowing_copy(home):
    card = ok(home, webapi.preset_save, name="tutorial/01_first_wildcard", text="mine")
    assert not card["builtin"] and card["text"] == "mine"
    assert "lesson" in preset_meta(Home(home), "tutorial/01_first_wildcard")


def test_bad_names_are_400(home):
    assert api(home, webapi.preset_save, name="", text="x")[0] == 400
    assert api(home, webapi.preset_save, name="a/", text="x")[0] == 400


def test_delete_rename_and_meta_guard_builtins(home):
    lesson = "tutorial/01_first_wildcard"
    for fn, extra in ((webapi.preset_delete, {}), (webapi.preset_rename, {"to": "x"}),
                      (webapi.preset_meta, {"title": "x"})):
        assert api(home, fn, name=lesson, **extra)[0] == 403
        assert api(home, fn, name="missing", **extra)[0] == 404


def test_delete_forgets_the_preset_in_ui_state(home):
    ok(home, webapi.preset_save, name="a", text="x")
    ok(home, webapi.favorite, name="a", on=True)
    assert ok(home, webapi.preset_delete, name="a") == {"ok": True}
    assert ok(home, webapi.presets)["favorites"] == []


def test_rename_moves_the_file_and_the_ui_state(home):
    ok(home, webapi.preset_save, name="a", text="x")
    ok(home, webapi.recent, name="a")
    ok(home, webapi.preset_save, name="b", text="y")
    assert api(home, webapi.preset_rename, name="a", to="b")[0] == 409
    card = ok(home, webapi.preset_rename, name="a", to="stills/c")
    assert card["name"] == "stills/c" and card["text"] == "x"
    assert ok(home, webapi.presets)["recent"] == ["stills/c"]


def test_meta_sets_and_clears_fields(home):
    ok(home, webapi.preset_save, name="a", text="x", note="old")
    card = ok(home, webapi.preset_meta, name="a", title="New", tags=["b", "a"], note="")
    assert (card["title"], card["tags"], card["note"]) == ("New", ["a", "b"], "")


def test_recent_is_newest_first(home):
    ok(home, webapi.recent, name="a")
    assert ok(home, webapi.recent, name="b") == {"recent": ["b", "a"]}


def test_template_by_hash_from_the_store_or_a_preset(home):
    digest = remember_template(Home(home), "stored text")
    assert ok(home, webapi.template, hash=digest) == {"hash": digest, "text": "stored text"}
    lesson = load_preset(Home(home), "tutorial/01_first_wildcard")
    assert ok(home, webapi.template, hash=template_hash(lesson))["text"] == lesson
    assert api(home, webapi.template, hash="0" * 16)[0] == 404
    assert api(home, webapi.template, hash="../x")[0] == 400


# --- libraries ------------------------------------------------------------------------------

def libs(home):
    """Every library with its entries, as the tab opens them one by one."""
    return {head["name"]: ok(home, webapi.library, name=head["name"]) for head in ok(home, webapi.libraries)["libraries"]}


def test_the_list_carries_no_entries_and_searches_them_on_the_server(home):
    """#152: a home of 109,722 entries sent them all (30 MB) whenever the tab opened."""
    (home / "library" / "big.yaml").write_text("entries: [" + ", ".join(f"thing {i}" for i in range(5000)) + ", a lone heron]\n")
    heads = {h["name"]: h for h in ok(home, webapi.libraries)["libraries"]}
    assert heads["big"] == {"name": "big", "source": "user", "count": 5001, "tags": [], "pending": False,
                            "pending_count": 0, "directions": ""}
    assert all("entries" not in h for h in heads.values())
    found = {h["name"] for h in ok(home, webapi.libraries, q="Lone Heron")["libraries"]}
    assert found == {"big"}
    assert "big" in {h["name"] for h in ok(home, webapi.libraries, q="bi")["libraries"]}  # the name counts too
    assert len(ok(home, webapi.library, name="big")["entries"]) == 5001
    assert api(home, webapi.library, name="missing")[0] == 404


def test_libraries_carry_source_tags_and_learned_weights(home):
    (home / "library" / "gen.yaml").write_text("meta: {generated_by: Qwen3.5-4B}\nentries: [fog]\n")
    Home(home).save_weights({"__animal__=fox": 1.5})
    by = libs(home)
    assert (by["animal"]["source"], by["creature"]["source"], by["gen"]["source"]) == ("user", "builtin", "llm")
    fox = by["animal"]["entries"][0]
    assert fox == {"value": "fox", "tags": [], "weight": 1.0, "props": {}, "learned": 1.5}
    assert "deep_sea" in by["creature"]["tags"]


def test_library_save_creates_edits_and_validates(home):
    lib = ok(home, webapi.library_save, name="Weather 2",
             entries=[{"value": " fog ", "tags": ["Cold"], "weight": 2}, {"value": "rain"}])
    assert lib["name"] == "weather_2" and lib["source"] == "user"
    assert lib["entries"][0] == {"value": "fog", "tags": ["cold"], "weight": 2.0, "props": {}, "learned": 1.0}
    assert api(home, webapi.library_save, name="w", entries=[{"value": "a"}, {"value": "A"}])[0] == 400
    assert api(home, webapi.library_save, name="w", entries=[{"value": " "}])[0] == 400
    assert api(home, webapi.library_save, name="w", entries=[{"value": "a", "weight": -1}])[0] == 400
    assert api(home, webapi.library_save, name="!!", entries=[])[0] == 400


def test_library_save_accepts_an_empty_new_library(home):
    lib = ok(home, webapi.library_save, name="fresh", entries=[])
    assert (lib["name"], lib["entries"], lib["source"]) == ("fresh", [], "user")
    assert "fresh" in libs(home)


def test_library_save_refuses_builtins_until_owned(home):
    assert api(home, webapi.library_save, name="creature", entries=[{"value": "x"}])[0] == 403
    owned = ok(home, webapi.library_own, name="creature")
    assert owned["source"] == "user" and (home / "library" / "creature.yaml").exists()
    assert "builtin" not in (home / "library" / "creature.yaml").read_text()
    assert ok(home, webapi.library_save, name="creature", entries=[{"value": "x"}])["entries"][0]["value"] == "x"
    assert api(home, webapi.library_own, name="missing")[0] == 404


def test_library_save_moves_learned_weights_for_renames_and_keeps_meta(home):
    (home / "library" / "gen.yaml").write_text("meta: {generated_by: Qwen3.5-4B}\nentries: [fog]\n")
    Home(home).save_weights({"__gen__=fog": 1.5})
    lib = ok(home, webapi.library_save, name="gen", entries=[{"value": "mist"}], renames={"fog": "mist"})
    assert lib["source"] == "llm" and lib["entries"][0]["learned"] == 1.5
    assert Home(home).weights() == {"__gen__=mist": 1.5}


def test_library_delete_guards_builtins(home):
    assert api(home, webapi.library_delete, name="creature")[0] == 403
    assert api(home, webapi.library_delete, name="missing")[0] == 404
    assert ok(home, webapi.library_delete, name="style") == {"ok": True}
    assert "style" not in libs(home)


# --- galaxy ---------------------------------------------------------------------------------

def test_galaxy_rows_name_their_preset_and_filter_by_template(home, tmp_path):
    lesson = load_preset(Home(home), "tutorial/01_first_wildcard")
    a = log_row(home, tmp_path, lesson, seed=1, name="1.png")
    log_row(home, tmp_path, "something else", seed=2, name="2.png")
    rows = ok(home, webapi.galaxy)["rows"]
    assert [r["seed"] for r in rows] == [2, 1]
    assert set(rows[0]) == {"id", "ts", "seed", "target", "template", "text", "picks", "rating", "exports",
                            "media_name", "kind", "preset", "params", "folder"}
    assert rows[1]["preset"] == "tutorial/01_first_wildcard" and rows[0]["preset"] is None
    assert rows[1]["media_name"] == "1.png" and rows[1]["kind"] == "image"
    only = ok(home, webapi.galaxy, template=template_hash(lesson))["rows"]
    assert [r["id"] for r in only] == [a]
    assert len(ok(home, webapi.galaxy, limit="1")["rows"]) == 1
    Home(home).save_weights({"__animal__=fox": 1.2})
    assert ok(home, webapi.galaxy)["weights"] == {"__animal__=fox": 1.2}
    assert api(home, webapi.galaxy, limit="many")[0] == 400


def test_galaxy_prefers_a_user_preset_over_a_builtin_with_the_same_text(home, tmp_path):
    lesson = load_preset(Home(home), "tutorial/01_first_wildcard")
    save_preset(Home(home), "stills/copy", lesson)
    log_row(home, tmp_path, lesson)
    assert ok(home, webapi.galaxy)["rows"][0]["preset"] == "stills/copy"


def test_rate_returns_the_row_and_its_weights(home, tmp_path):
    rid = log_row(home, tmp_path, "a __animal__")
    body = ok(home, webapi.galaxy_rate, id=rid, rating="love")
    assert body["row"]["rating"] == "love" and body["row"]["id"] == rid
    assert body["weights"] == {"__animal__=fox": 1.5}
    assert api(home, webapi.galaxy_rate, id=rid, rating="meh")[0] == 400
    assert api(home, webapi.galaxy_rate, id="000000000000", rating="love")[0] == 404


def test_galaxy_filters_by_folder_and_lists_folders_with_counts(home, tmp_path):
    a = log_row(home, tmp_path, "a __animal__", seed=1, name="1.png")
    b = log_row(home, tmp_path, "a __animal__", seed=2, name="2.png")
    log_row(home, tmp_path, "a __animal__", seed=3, name="3.png")
    body = ok(home, webapi.galaxy_move, ids=[a, b], folder="foxes/snow")
    assert body["moved"] == 2 and body["total"] == 3 and body["unsorted"] == 1
    assert body["folders"] == [{"path": "foxes", "count": 0}, {"path": "foxes/snow", "count": 2}]
    everything = ok(home, webapi.galaxy)
    assert len(everything["rows"]) == 3 and everything["folders"] == body["folders"]
    assert {r["folder"] for r in everything["rows"]} == {"foxes/snow", ""}
    assert [r["id"] for r in ok(home, webapi.galaxy, folder="foxes/snow")["rows"]] == [b, a]
    assert len(ok(home, webapi.galaxy, folder="")["rows"]) == 1
    assert ok(home, webapi.galaxy, folder="foxes")["rows"] == []
    assert api(home, webapi.galaxy, folder="a//b")[0] == 400


def test_galaxy_move_delete_and_export_check_their_input(home, tmp_path):
    a = log_row(home, tmp_path, "a __animal__")
    for bad in ({}, {"ids": "x"}, {"ids": []}, {"ids": [1]}):
        assert api(home, webapi.galaxy_move, folder="x", **bad)[0] == 400
    assert api(home, webapi.galaxy_move, ids=["000000000000"], folder="x")[0] == 404
    assert api(home, webapi.galaxy_move, ids=[a], folder="../x")[0] == 400
    assert api(home, webapi.galaxy_export, ids=[a], name="../x")[0] == 400
    out = ok(home, webapi.galaxy_export, ids=[a], name="set")
    assert out == {"path": str(home / "export" / "set"), "exported": 1, "skipped": 0}
    assert (home / "export" / "set" / "a.txt").read_text() == "a fox\n"
    body = ok(home, webapi.galaxy_delete, ids=[a])
    assert body["deleted"] == 1 and body["total"] == 0
    assert (home / "trash" / "a.png").exists()
    assert api(home, webapi.galaxy_delete, ids=[a])[0] == 404


def test_galaxy_folders_are_added_renamed_and_deleted(home, tmp_path):
    a = log_row(home, tmp_path, "a __animal__")
    assert ok(home, webapi.galaxy_folder_add, path="keep")["folders"] == [{"path": "keep", "count": 0}]
    assert api(home, webapi.galaxy_folder_add, path="keep")[0] == 409
    assert api(home, webapi.galaxy_folder_add, path="")[0] == 400
    ok(home, webapi.galaxy_move, ids=[a], folder="old")
    body = ok(home, webapi.galaxy_folder_rename, path="old", to="keep/old")
    assert [f["path"] for f in body["folders"]] == ["keep", "keep/old"]
    assert api(home, webapi.galaxy_folder_rename, path="keep", to="keep/old/x")[0] == 400
    assert api(home, webapi.galaxy_folder_rename, path="nope", to="x")[0] == 404
    ok(home, webapi.galaxy_folder_add, path="other")
    assert api(home, webapi.galaxy_folder_rename, path="other", to="keep")[0] == 409
    body = ok(home, webapi.galaxy_folder_delete, path="keep")
    assert [f["path"] for f in body["folders"]] == ["old", "other"]
    assert ok(home, webapi.galaxy, folder="old")["rows"][0]["id"] == a
    assert api(home, webapi.galaxy_folder_delete, path="keep")[0] == 404


def test_thumb_and_media_return_files(home, tmp_path):
    rid = log_row(home, tmp_path, "a __animal__")
    assert isinstance(ok(home, webapi.galaxy_thumb, id=rid), Path)
    assert ok(home, webapi.galaxy_media, id=rid).name == "a.png"
    assert api(home, webapi.galaxy_thumb, id="nope")[0] == 404


# --- roll -----------------------------------------------------------------------------------

def test_roll_expands_consecutive_seeds(home):
    rolls = ok(home, webapi.roll, template="a __animal__", seed=7)["rolls"]
    assert [r["seed"] for r in rolls] == [7, 8, 9]
    assert set(rolls[0]) == {"seed", "text", "picks", "lint"}
    assert rolls[0]["picks"][0]["keys"][0].startswith("__animal__=") and rolls[0]["lint"] == []


def test_roll_compiles_screenplays_with_lint(home):
    rolls = ok(home, webapi.roll, template="@h3 t2va\nSHOT 2s\nA __animal__.\n", seed=1, n=1,
               target="h3-base")["rolls"]
    assert len(rolls) == 1 and rolls[0]["text"].startswith("integrated_multimodal_description")
    assert any("4–15" in i["message"] for i in rolls[0]["lint"])


def test_roll_shows_every_chunk_of_a_reel_at_one_seed(home):
    reel = "@h3 t2va\n$hero = __animal__\nCHUNK\nSHOT 5s\nA $hero.\nSFX: x\nCHUNK\nSHOT 5s\nThe $hero naps.\nSFX: y\n"
    rolls = ok(home, webapi.roll, template=reel, seed=4, target="h3-base")["rolls"]
    assert [(r["seed"], r["segment"]) for r in rolls] == [(4, 0), (4, 1)]
    assert "naps" in rolls[1]["text"] and "naps" not in rolls[0]["text"]


def test_roll_warns_about_loras_it_cannot_find(home, monkeypatch):
    import sys
    import types
    module = types.ModuleType("folder_paths")
    module.get_filename_list = lambda kind: ["x/all.safetensors"] if kind == "loras" else []
    monkeypatch.setitem(sys.modules, "folder_paths", module)
    text = "@h3 t2va\nLORA: <lora:all:1> <lora:gone:1>\nSHOT 5s\nA.\nSFX: x\n"
    [roll] = ok(home, webapi.roll, template=text, seed=1, n=1, target="h3-base")["rolls"]
    assert [i["message"] for i in roll["lint"] if "lora" in i["message"].lower()] == [
        next(i["message"] for i in roll["lint"] if "gone" in i["message"])]


def test_roll_pages_through_the_clips_of_a_forever_loop(home):
    reel = "@h3 t2va\nCHUNK a\nSHOT 5s\nA.\nSFX: x\nCHUNK b repeat forever\nSHOT 5s\nB.\nSFX: y\n"
    rolls = ok(home, webapi.roll, template=reel, seed=2, target="h3-base", start=10)["rolls"]
    assert [r["segment"] for r in rolls] == list(range(10, 10 + webapi.ROLL_CLIPS))


def freq_table(body):
    return {entry["label"]: {v["value"]: v["count"] for v in entry["values"]} for entry in body["labels"]}


def test_frequency_counts_every_value_over_many_seeds(home):
    body = ok(home, webapi.frequency, template="a __animal__ in {mist|snow:3}", seed=1, n=200)
    table = freq_table(body)
    assert body["runs"] == 200
    assert set(table["__animal__"]) == {"fox", "heron", "owl"} and sum(table["__animal__"].values()) == 200
    assert 120 < table["{mist|snow}"]["snow"] < 180
    counts = [v["count"] for v in body["labels"][0]["values"]]
    assert counts == sorted(counts, reverse=True)


def test_frequency_counts_multi_picks_value_by_value_and_applies_dials(home):
    body = ok(home, webapi.frequency, template="$a = __animal__\n{2$$__style__} $a", seed=1, n=50,
              params={"a": "lynx"})
    table = freq_table(body)
    assert sum(table["__style__ ×2"].values()) == 100 and "$a ← __animal__" not in table


def test_frequency_across_the_clips_of_a_reel(home):
    reel = "@h3 t2va\n$w = {pool|garage}\nCHUNK a\nSHOT 5s\nA.\nSFX: x\nCHUNK b repeat forever\n$n = {1|2|3}\nSHOT 5s\nB $n.\nSFX: y\n"
    body = ok(home, webapi.frequency, template=reel, seed=3, n=40, target="h3-base", across="clips")
    table = freq_table(body)
    assert body["runs"] == 40 and len(table["{pool|garage}"]) == 1
    assert sum(table["{1|2|3}"].values()) == 39


def test_a_count_loads_the_libraries_once_however_many_rolls(home, monkeypatch):
    from orrery.home import Home
    loads, real = [], Home.libraries
    monkeypatch.setattr(Home, "libraries", lambda self: loads.append(1) or real(self))
    counts = []
    for fn, n in ((webapi.frequency, 5), (webapi.frequency, 50), (webapi.roll, 1), (webapi.roll, 6)):
        loads.clear()
        ok(home, fn, template="a __animal__", seed=1, n=n)
        counts.append(len(loads))
    assert counts == [1, 1, 1, 1]


def test_frequency_counts_lint_and_caps_the_runs(home):
    body = ok(home, webapi.frequency, template="@h3 t2va\nSHOT 2s\nA.\nSFX: x\n", seed=1, n=5000, target="h3-base")
    assert body["runs"] == webapi.MAX_FREQUENCY
    assert any("4–15" in m["message"] and m["count"] == body["runs"] for m in body["lint"])
    status, _ = api(home, webapi.frequency, template="a", seed=1, across="clips")
    assert status == 400


def test_llm_settings_list_text_encoders_and_are_saved(home, monkeypatch):
    import sys
    import types
    module = types.ModuleType("folder_paths")
    module.get_filename_list = lambda kind: ["qwen3vl_4b_bf16.safetensors", "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"] if kind == "text_encoders" else []
    module.get_full_path = lambda kind, name: None
    monkeypatch.setitem(sys.modules, "folder_paths", module)
    body = ok(home, webapi.llm_settings)
    assert (body["file"], body["entries"]) == (None, 12)
    assert [(f["name"], f["can_write"]) for f in body["files"]] == [
        ("qwen3vl_4b_bf16.safetensors", True), ("qwen3vl_32b_minimax_h3_int8_convrot.safetensors", False)]
    assert body["max_tokens"] == 16000
    ok(home, webapi.llm_save, file="qwen3vl_4b_bf16.safetensors", entries=20, max_tokens=4000)
    body = ok(home, webapi.llm_settings)
    assert (body["file"], body["entries"], body["max_tokens"]) == ("qwen3vl_4b_bf16.safetensors", 20, 4000)
    status, _ = api(home, webapi.llm_save, file="qwen3vl_32b_minimax_h3_int8_convrot.safetensors")
    assert status == 400


def test_llm_made_libraries_are_accepted_or_discarded(home):
    lib = home / "library"
    (lib / "runway_shoes.yaml").write_text("meta: {generated_by: qwen, pending: true, directions: short}\nentries: [mule, boot]\n")
    (lib / "animal.yaml").write_text("meta: {pending_entries: [lynx]}\nentries: [fox, heron, owl, lynx]\n")
    listed = {l["name"]: l for l in ok(home, webapi.libraries)["libraries"]}
    assert listed["runway_shoes"]["pending"] and listed["runway_shoes"]["directions"] == "short"
    assert listed["animal"]["pending_count"] == 1 and not listed["animal"]["pending"]
    assert ok(home, webapi.library, name="animal")["pending_entries"] == ["lynx"]
    ok(home, webapi.library_accept, name="runway_shoes")
    ok(home, webapi.library_discard, name="animal")
    listed = libs(home)
    assert not listed["runway_shoes"]["pending"] and listed["runway_shoes"]["directions"] == "short"
    assert [e["value"] for e in listed["animal"]["entries"]] == ["fox", "heron", "owl"] and listed["animal"]["pending_entries"] == []
    (lib / "shoes2.yaml").write_text("meta: {pending: true}\nentries: [clog]\n")
    ok(home, webapi.library_discard, name="shoes2")
    assert not (lib / "shoes2.yaml").exists()


def test_folder_and_text_libraries_through_the_api(home):
    lib = home / "library"
    (lib / "film").mkdir()
    (lib / "film" / "genre.txt").write_text("noir\nwestern\n")
    listed = libs(home)
    assert listed["film/genre"]["source"] == "user" and [e["value"] for e in listed["film/genre"]["entries"]] == ["noir", "western"]
    ok(home, webapi.library_save, name="film/genre", entries=[{"value": "noir", "tags": ["dark"]}, {"value": "western"}])
    assert (lib / "film" / "genre.yaml").exists() and not (lib / "film" / "genre.txt").exists()
    ok(home, webapi.library_save, name="Film/New Moods", entries=[{"value": "tense"}])
    assert (lib / "film" / "new_moods.yaml").exists()
    (lib / "film" / "old.txt").write_text("x\n")
    ok(home, webapi.library_delete, name="film/old")
    assert not (lib / "film" / "old.txt").exists()
    status, _ = api(home, webapi.library_save, name="../escape", entries=[{"value": "x"}])
    assert status == 400 or not (home.parent / "escape.yaml").exists()


def test_the_home_folder_is_read_and_set_through_the_api(home, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    body = ok(home, webapi.home_settings)
    assert body["source"] == "env" and body["setting"] == ""
    monkeypatch.delenv("ORRERY_HOME")
    body = ok(home, webapi.home_save, path=str(tmp_path / "elsewhere"))
    assert (body["home"], body["source"], body["setting"]) == (str(tmp_path / "elsewhere"), "setting", str(tmp_path / "elsewhere"))
    status, _ = api(home, webapi.home_save, path="relative/path")
    assert status == 400


def test_roll_applies_dials(home):
    rolls = ok(home, webapi.roll, template="$hero = __animal__\na $hero", seed=1, n=2, params={"hero": "lynx"})["rolls"]
    assert [r["text"] for r in rolls] == ["a lynx", "a lynx"]


def test_galaxy_rows_carry_their_dials(home, tmp_path):
    log_row(home, tmp_path, "$hero = __animal__\na $hero", params={"hero": "lynx"})
    [row] = ok(home, webapi.galaxy)["rows"]
    assert row["params"] == {"hero": "lynx"}


@pytest.mark.parametrize("args", [{"template": "a __smell__", "seed": 1},
                                  {"template": "x", "seed": "soon"},
                                  {"template": "x", "seed": 1, "target": "poster"}])
def test_roll_rejects_bad_input(home, args):
    status, body = api(home, webapi.roll, **args)
    assert status == 400 and body["error"]


def test_a_recorded_preset_keeps_its_outputs_after_the_text_changes(home, tmp_path):
    h = Home(home)
    save_preset(h, "stills/fox", "a __animal__")
    kept = log_row(home, tmp_path, "a __animal__", seed=1, name="a.png", preset="stills/fox", edited=False)
    variant = log_row(home, tmp_path, "a __animal__ at night", seed=2, name="b.png", preset="stills/fox", edited=True)
    save_preset(h, "stills/fox", "a __animal__ in fog", overwrite=True)
    card = next(c for c in ok(home, webapi.presets)["presets"] if c["name"] == "stills/fox")
    assert (card["outputs"], card["thumb"]) == (1, kept)
    rows = {r["id"]: r for r in ok(home, webapi.galaxy)["rows"]}
    assert rows[kept]["preset"] == "stills/fox" and rows[variant]["preset"] is None
    assert [r["id"] for r in ok(home, webapi.galaxy, preset="stills/fox")["rows"]] == [kept]


def test_a_recorded_preset_that_no_longer_exists_falls_back_to_the_hash(home, tmp_path):
    save_preset(Home(home), "stills/owl", "an owl")
    rid = log_row(home, tmp_path, "an owl", preset="gone/away", edited=False)
    assert {r["id"]: r for r in ok(home, webapi.galaxy)["rows"]}[rid]["preset"] == "stills/owl"


def test_cards_preview_and_count_only_outputs_with_a_file(home, tmp_path):
    save_preset(Home(home), "stills/owl", "an owl")
    shown = log_row(home, tmp_path, "an owl", seed=1)
    log_row(home, tmp_path, "an owl", seed=2, name="b.png", media=None)
    card = next(c for c in ok(home, webapi.presets)["presets"] if c["name"] == "stills/owl")
    assert (card["outputs"], card["thumb"]) == (1, shown)


def test_properties_travel_through_the_libraries_tab(home):
    """The tab saves the whole list; properties it did not send back would be lost on the first edit."""
    lib = ok(home, webapi.library_save, name="people",
             entries=[{"value": "Mara", "props": {"Gender": "female", "age": "30s"}}, {"value": "Tomas"}])
    assert lib["entries"][0]["props"] == {"age": "30s", "gender": "female"} and lib["entries"][1]["props"] == {}
    assert api(home, webapi.library_save, name="people",
               entries=[{"value": "Mara", "props": {"a key!": "female"}}])[0] == 400
    lib = ok(home, webapi.library_save, name="rainfall",
             entries=[{"value": "snow", "props": {"sfx": "footsteps  crunch in snow"}}])
    assert lib["entries"][0]["props"] == {"sfx": "footsteps crunch in snow"}


def test_renaming_through_the_tab_reports_what_followed(home):
    ok(home, webapi.library_save, name="film_moods", entries=[{"value": "a hush"}])
    out = ok(home, webapi.library_rename, name="film_moods", to="film/moods")
    assert out == {"name": "film/moods", "weights": 0, "libraries": [], "presets": []}
    assert api(home, webapi.library_rename, name="camera", to="cam")[0] == 400


def test_outputs_of_ordinary_save_nodes_reach_the_galaxy(home, tmp_path, monkeypatch):
    """Generate without Orrery Log: the node remembers its picks per prompt; the browser reports the files."""
    from orrery import runs
    out = tmp_path / "output"
    (out / "video").mkdir(parents=True)
    (out / "video" / "clip_00001_.mp4").write_bytes(b"x")
    monkeypatch.setattr(webapi, "_output_dir", lambda: out)
    runs.remember("p1", "9", json.dumps({"seed": 7, "text": "a fox", "picks": [], "template": "abc"}))
    media = [{"filename": "clip_00001_.mp4", "subfolder": "video", "type": "output"},
             {"filename": "preview.png", "subfolder": "", "type": "temp"}]
    assert ok(home, webapi.galaxy_capture, prompt_id="p1", node="9", media=media) == {"logged": 1}
    rows = [json.loads(line) for line in (home / "galaxy.jsonl").read_text().splitlines()]
    assert rows[-1]["media"] == str(out / "video" / "clip_00001_.mp4") and rows[-1]["seed"] == 7
    assert api(home, webapi.galaxy_capture, prompt_id="nope", node="9", media=media)[0] == 404
    bad = [{"filename": "../../etc/passwd", "subfolder": "", "type": "output"}]
    assert ok(home, webapi.galaxy_capture, prompt_id="p1", node="9", media=bad) == {"logged": 0}


# --- the timeline: the chain's clips and the sent frames ----------------------------------------

def fake_chain(output, clips=2):
    import av
    run = output / "h3_context" / "chain_video" / "run_1"
    run.mkdir(parents=True)
    folders = []
    for i in range(1, clips + 1):
        folder = run / f"clip_{i:05d}_abc"
        folder.mkdir()
        with av.open(str(folder / "video.mp4"), "w") as out:
            stream = out.add_stream("mpeg4", rate=24)
            stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
            for _ in range(24):
                for packet in stream.encode(av.VideoFrame.from_image(Image.new("RGB", (64, 48), (40 * i, 0, 0)))):
                    out.mux(packet)
            for packet in stream.encode():
                out.mux(packet)
        folders.append({"folder": folder.name, "frames": 24})
    (run.parent / "active.json").write_text(json.dumps({"run": "run_1"}))
    (run / "clips.json").write_text(json.dumps({"settings": [64, 48, "24", 48000, 2], "clips": folders}))


def test_the_chain_lists_its_clips_by_segment_and_serves_them(home, tmp_path, monkeypatch):
    out = tmp_path / "out"
    fake_chain(out)
    monkeypatch.setattr(webapi, "_output_dir", lambda: out)
    body = ok(home, webapi.chain)
    assert body == {"latent_path": "h3_context", "width": 64, "height": 48,  # Chain Video keeps one size per chain
                    "clips": [{"segment": 0, "frames": 24, "version": "clip_00001_abc"},
                              {"segment": 1, "frames": 24, "version": "clip_00002_abc"}]}
    assert ok(home, webapi.chain_video, segment="1").name == "video.mp4"
    thumb = ok(home, webapi.chain_thumb, segment="0")
    assert thumb.suffix == ".webp" and thumb.is_file()
    assert api(home, webapi.chain_video, segment="5")[0] == 404
    assert ok(home, webapi.chain, latent_path="nowhere") == {"latent_path": "nowhere", "width": None, "height": None, "clips": []}
    assert api(home, webapi.chain, latent_path="../../etc")[0] in (400, 200)


def test_an_anchor_is_served_by_image_number(home):
    import numpy as np

    from orrery import anchors
    anchors.save(Home(home), 3, np.zeros((2, 8, 8, 3), dtype=np.float32))
    assert ok(home, webapi.anchor, image="3").name == "0000.png"
    assert api(home, webapi.anchor, image="4")[0] == 404
    assert api(home, webapi.anchor, image="x")[0] == 400


def test_the_editor_switches_travel_with_the_presets_and_are_saved(home):
    assert ok(home, webapi.presets)["dividers"] is True and ok(home, webapi.presets)["timeline"] is True
    assert ok(home, webapi.ui_save, timeline=False) == {"quickstart": True, "dividers": True, "timeline": False, "log_prompts": True,
                                                         "clip_min": 360}
    assert ok(home, webapi.ui_save, clip_min=480)["clip_min"] == 480 and ok(home, webapi.presets)["clip_min"] == 480
    assert ok(home, webapi.presets)["timeline"] is False


def test_the_history_lists_runs_newest_first_and_searches(home):
    from orrery import history
    for seed, text in ((1, "a heron at dawn"), (2, "a fox in the snow"), (3, "a heron at dusk")):
        history.record(Home(home), {"seed": seed, "target": "text", "template": "0123456789abcdef", "text": text,
                                    "picks": [], "params": {}})
    body = ok(home, webapi.history_runs)
    assert body["total"] == 3 and [r["seed"] for r in body["runs"]] == [3, 2, 1]
    assert [r["seed"] for r in ok(home, webapi.history_runs, q="heron", limit="1")["runs"]] == [3]
    assert ok(home, webapi.history_runs, q="heron", offset="1")["runs"][0]["seed"] == 1


def test_generate_plans_a_lora_sweep_times_a_grid(home):
    body = ok(home, webapi.generate_plan, template="a __animal__ at {dawn|noon} @x(0.5,1.0)\n@grid __animal__ × {dawn|noon}")
    assert body == {"runs": 12, "formula": "2 × grid 3 × 2", "first": "x"}
    assert ok(home, webapi.generate_plan, template="a __animal__ at {dawn|noon}\n@grid {dawn|noon}") == \
        {"runs": 2, "formula": "grid 2", "first": "{dawn|noon}"}
    assert ok(home, webapi.generate_plan, template="a __animal__")["runs"] == 0
    status, body = api(home, webapi.generate_plan, template="a __animal__\n@grid __style__")
    assert status == 400 and "doesn't use it" in body["error"]


def test_the_app_gets_the_path_a_reel_takes_at_its_seed(home):
    loop = "@h3 t2va\nCHUNK a\nSHOT 5s\nA.\nCHUNK b\nSHOT 5s\nB.\nGOTO: a ×1"
    assert ok(home, webapi.reel_walk, template=loop, seed=3) == {"path": [0, 1, 0, 1], "ended": True}
    endless = ok(home, webapi.reel_walk, template=loop.replace(" ×1", ""), seed=3)
    assert endless["ended"] is False and endless["path"][:5] == [0, 1, 0, 1, 0]
    assert ok(home, webapi.reel_walk, template="a fox", seed=1) == {"path": [], "ended": True}


def test_the_app_learns_where_each_remember_line_goes(home):
    reel = ("@h3 references\nCAST\n@WOMAN: a woman\nSCENE a\nSHOT 5s\nREMEMBER: frame 0 as @WOMAN\n"
            "REMEMBER: frame 50 as @WOMAN\n@WOMAN waves.\nSCENE b\nSHOT 5s\n@WOMAN sits.")
    lines = ok(home, webapi.reel_remembered, template=reel, seed=0)["lines"]
    assert [(line["line"], line["source"], [f["what"] for f in line["fills"]]) for line in lines] == \
        [(0, 0, ["image 1"]), (1, 0, ["image 1"])]
    assert lines[0]["fills"][0]["replaced"] == {"from": 1, "by": 1} and lines[1]["fills"][0]["replaced"] is None
    assert ok(home, webapi.reel_remembered, template="a fox", seed=0) == {"lines": []}
    status, body = api(home, webapi.reel_remembered, template=reel.replace("as @WOMAN", "as @CAT", 1))
    assert status == 400 and "CAT is not in a CAST" in body["error"]


def test_the_writer_texts_are_read_edited_and_reset(home):
    body = ok(home, webapi.writer_texts)
    assert set(body) == {"continue", "story", "describe", "describe_shot"} and body["continue"]["edited"] is False
    edited = ok(home, webapi.writer_save, name="story", text="Write {seconds} seconds.")
    assert edited["edited"] is True and edited["text"].startswith("Write {seconds}")
    assert ok(home, webapi.writer_save, name="story", text=None)["edited"] is False
    assert api(home, webapi.writer_save, name="nope", text="x")[0] == 400


def test_annotate_says_what_each_line_gives_at_a_seed(home):
    """#163: bindings as they rolled, exports, a grid's cells, where a CAST member's pictures go."""
    text = "$a = __animal__\n$plain = a grey wall\nEXPORT: mood = {calm|grim}\n@grid {dawn|noon}\nA $a at {dawn|noon}."
    out = ok(home, webapi.annotate, template=text, seed=3, target="text")
    assert out["bindings"]["a"] in ("fox", "heron", "owl") and out["bindings"]["plain"] == "a grey wall"
    assert out["exports"]["mood"] in ("calm", "grim") and out["grid"] == "2 runs: dawn · noon"
    screenplay = "@h3 references\nCAST\n@HERO (image 2): a tall man\n@DOG: a dog\nSHOT 5s: static\n@HERO walks @DOG."
    out = ok(home, webapi.annotate, template=screenplay.replace("SHOT 5s", "SET: @HERO(0.6, 35%)\nSHOT 5s"), seed=1,
             target="h3-base")
    assert out["cast"] == {"HERO": "image 2", "DOG": "no picture in this clip"}
    assert out["members"]["HERO"] == {"who": "a tall man", "pictures": [{"image": 2, "strength": 0.6, "from": 0.35, "to": 1.0}],
                                      "refmods": [], "voice": ""}  # the hover's record (#147)
    assert ok(home, webapi.annotate, template="A __missing_lib__.", seed=1, target="text")["bindings"] == {}  # never fails
