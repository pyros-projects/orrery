"""Pictures by name: the gallery as libraries, and a CAST that names them (#128)."""

import json

from PIL import Image

from orrery import pictures
from orrery.h3 import compile_scene
from orrery.home import Home

CREATOR = "krea/09_character_creator"


def gallery(home, rows):
    """Gallery rows with real image files: (seed, params, rating, how many views) each."""
    out = home / "out"
    out.mkdir(exist_ok=True)
    lines, n = [], 0
    for seed, params, rating, views in rows:
        for _ in range(views):
            n += 1
            path = out / f"krea2_{n:05d}_.png"
            Image.new("RGB", (4, 6), (n, 0, 0)).save(path)
            lines.append({"ts": f"2026-10-03T12:{n:02d}:00", "media": str(path), "seed": seed, "preset": CREATOR,
                          "params": params, "text": f"a character of seed {seed}", "rating": rating})
    (home / "galaxy.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines))
    return out


def test_the_gallery_is_a_library_of_characters(home):
    out = gallery(home, [(7, {}, "love", 4), (8, {"genre": "noir"}, None, 4), (9, {}, "hate", 1)])
    (out / "krea2_00009_.png").unlink()  # a picture whose file is gone is left out
    lib = Home(home).libraries()["pictures/" + CREATOR]
    assert lib.meta["gallery"] and [e.value for e in lib.entries] == [f"{CREATOR}/7", f"{CREATOR}/8-" + lib.entries[1].value[-4:]]
    first = lib.entries[0]
    assert (first.weight, first.tags) == (1.5, ("loved",))
    assert first.prop("pictures").splitlines() == [str(out / f"krea2_{i:05d}_.png") for i in range(1, 5)]
    assert first.prop("prompt") == "a character of seed 7"
    libs = Home(home).libraries()
    assert pictures.find(f"{CREATOR}/7", libs) == [out / f"krea2_{i:05d}_.png" for i in range(1, 5)]
    assert pictures.find(f"{CREATOR}/krea2_00006_", libs) == [out / "krea2_00006_.png"]  # one picture by its file
    assert pictures.find(f"{CREATOR}/11", libs) is None and pictures.find("other/7", libs) is None


REEL = """@h3 references
CAST
@HERO (image {who}): a stranger
@DOG (image 1): a dog
SHOT 4s: static
@HERO walks @DOG."""


def test_a_named_character_brings_all_its_views_in_the_highest_free_slots(home):
    out = gallery(home, [(7, {}, None, 4)])
    c = compile_scene(REEL.format(who=f"{CREATOR}/7"), 1, Home(home).libraries(), packed=True)
    assert {n: p["file"] for n, p in c.pictures.items()} == {
        n: str(out / f"krea2_{i:05d}_.png") for n, i in zip(range(6, 10), range(1, 5), strict=True)}
    assert {p["prompt"] for p in c.pictures.values()} == {"a character of seed 7"}
    assert c.refs == [1, 6, 7, 8, 9]
    assert "<Picture 2>, <Picture 3>, <Picture 4>, and <Picture 5>" in c.text


def test_a_character_rolls_from_the_gallery_like_any_library(home):
    gallery(home, [(7, {}, "love", 4), (8, {}, None, 4), (9, {}, None, 4)])
    libs = Home(home).libraries()
    rolled = {compile_scene(REEL.format(who=f"__pictures/{CREATOR}__"), s, libs).picks[0].value for s in range(12)}
    assert rolled == {f"{CREATOR}/{n}" for n in (7, 8, 9)}
    c = compile_scene(REEL.format(who=f"__pictures/{CREATOR}__"), 3, libs)
    assert c.picks[0].label == f"__pictures/{CREATOR}__" and len(c.pictures) == 4


def test_set_reaches_a_named_picture_and_what_is_missing_says_so(home):
    gallery(home, [(7, {}, None, 1)])
    libs = Home(home).libraries()
    c = compile_scene(REEL.format(who=f"{CREATOR}/7 at 0.6").replace("SHOT 4s", "SET: @HERO(0.4)\nSHOT 4s"), 1, libs,
                      packed=True)
    assert [(i["image"], i["strength"]) for i in c.images] == [(9, 0.4)]
    c = compile_scene(REEL.format(who=f"{CREATOR}/99"), 1, libs)
    assert c.pictures == {} and any("no picture of the gallery" in i.message for i in c.lint)


def test_too_many_views_for_the_free_slots_are_left_out_with_a_warning(home):
    gallery(home, [(7, {}, None, 9)])
    c = compile_scene(REEL.format(who=f"{CREATOR}/7"), 1, Home(home).libraries())
    assert sorted(c.pictures) == list(range(2, 10)) and any("1 is left out" in i.message for i in c.lint)


GRAPH = {"9": {"class_type": "OrreryPrompt", "inputs": {}},
         "12": {"class_type": "OrreryRefs", "inputs": {"picks": ["9", 1], "image_1": ["5", 0]}},
         "20": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {"prompt": ["9", 0], "ref_images.ref_image_0": ["12", 0]}}}


def test_orrery_refs_loads_the_named_pictures_into_their_slots(home, monkeypatch):
    from orrery import comfy
    from orrery.comfy import OrreryPrompt, OrreryRefs

    out = gallery(home, [(7, {}, None, 2)])
    _, picks, *_ = OrreryPrompt().run(REEL.format(who=f"{CREATOR}/7"), 1, "h3-base", home=str(home), prompt=GRAPH,
                                      unique_id="9")
    data = json.loads(picks)
    assert data["refs"] == [1, 8, 9] and data["pictures"] == {"8": str(out / "krea2_00001_.png"),
                                                              "9": str(out / "krea2_00002_.png")}
    monkeypatch.setattr(comfy, "load_picture", lambda path: f"loaded {path.rsplit('/', 1)[1]}")
    monkeypatch.setattr(comfy, "stack_preview", lambda labelled: None)
    refs = OrreryRefs().route(picks, image_1="dog")
    assert refs[:3] == ("dog", "loaded krea2_00001_.png", "loaded krea2_00002_.png")


def test_named_pictures_need_orrery_refs(home):
    import pytest

    from orrery.comfy import OrreryPrompt

    gallery(home, [(7, {}, None, 1)])
    graph = {"9": GRAPH["9"], "20": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {"prompt": ["9", 0]}}}
    with pytest.raises(ValueError, match="Orrery Refs loads"):
        OrreryPrompt().run(REEL.format(who=f"{CREATOR}/7"), 1, "h3-base", home=str(home), prompt=graph, unique_id="9")


def test_the_gallery_libraries_are_read_only_in_the_tab(home):
    from orrery import webapi

    gallery(home, [(7, {}, None, 1)])
    heads = {h["name"]: h for h in webapi.libraries(Home(home), {})["libraries"]}
    assert heads["pictures/" + CREATOR]["source"] == "gallery"
    for call in (webapi.library_save, webapi.library_own):
        try:
            call(Home(home), {"name": "pictures/" + CREATOR, "entries": []})
        except webapi.ApiError as err:
            assert err.status == 403
        else:
            raise AssertionError("a gallery library was edited")


def test_the_slot_writer_learns_what_the_pictures_show(home):
    from orrery.comfy import _made
    from orrery.slots import request

    gallery(home, [(7, {}, None, 2)])
    c = compile_scene(REEL.format(who=f"{CREATOR}/7"), 1, Home(home).libraries(), packed=True)
    assert _made(c, packed=True) == ["<Picture 2> and <Picture 3>: a character of seed 7"]
    assert "<Picture 2> and <Picture 3>: a character of seed 7" in request([], ["who"], "A --who-- waits.",
                                                                           made=_made(c, True))


def test_a_slot_in_a_cast_line_keeps_its_commas():
    from orrery.cast import parse_member

    m = parse_member("HERO", "image 2", "--who they are, in one sentence--, in a red coat")
    assert (m.head, m.tail) == ("--who they are, in one sentence--", ", in a red coat")
    assert m.split_head() == (m.head, "")
