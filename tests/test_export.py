"""EXPORT: what a Krea template keeps beside its prompt, for the gallery and other systems (#157)."""

import json

import pytest

from orrery.dsl import expand, parse, strip_exports
from orrery.library import Entry, Library

LIBS = {"weather": Library("weather", [Entry("heavy snow", props=(("kind", "snow"), ("sfx", "snow crunches"))),
                                       Entry("summer rain", props=(("kind", "rain"), ("sfx", "rain drums")))]),
        "animal": Library("animal", [Entry("a fox"), Entry("a heron"), Entry("an owl")])}

T = """$weather_here = __weather__
$who = a {tall|short} heron
EXPORT:
  who = $who
  mood = {calm|restless}
  skills = {2$$fishing|flying|waiting}
  $weather_here
EXPORT: friend = __animal__
A photo of $who in $weather_here."""


def test_the_forms_of_an_export():
    assert parse("EXPORT: mood = {calm|grim}\nA fox.").exports == [("mood", "{calm|grim}")]
    assert parse("EXPORT: $a, $b\nA fox.").exports == [("a", "$a"), ("b", "$b")]
    block = parse("EXPORT:\n  who = $who\n  $job\nA fox.\n  indented prose")
    assert block.exports == [("who", "$who"), ("job", "$job")] and block.body == ["A fox.", "indented prose"]
    with pytest.raises(ValueError, match="name = what it rolls"):
        parse("EXPORT: just words\nA fox.")
    assert strip_exports("EXPORT:\n  a = b\nA fox.\nEXPORT: c = d") == "A fox."


def test_an_export_rolls_beside_the_prompt_and_never_in_it():
    x = expand(T, 3, LIBS)
    assert x.text.startswith("A photo of a ") and "calm" not in x.text and "restless" not in x.text
    ex = x.exports
    assert ex["who"] in ("a tall heron", "a short heron") and ex["mood"] in ("calm", "restless")
    assert len(ex["skills"]) == 2 and set(ex["skills"]) <= {"fishing", "flying", "waiting"}
    assert ex["weather_here"]["value"] in ("heavy snow", "summer rain") and ex["weather_here"]["sfx"]  # its fields
    assert ex["friend"] in ("a fox", "a heron", "an owl")
    assert expand(T, 3, LIBS).exports == ex  # seeded
    labels = [p.label for p in x.picks]
    assert "EXPORT friend ← __animal__" in labels and "{calm|restless}" in labels  # recorded, so they learn


def test_an_export_leaves_the_prompts_picks_alone():
    plain = "$who = a {tall|short} heron\nA photo of $who on __animal__."
    for seed in range(8):
        assert expand(plain + "\nEXPORT: mood = {calm|grim}\nEXPORT: pal = __animal__", seed, LIBS).text == \
               expand(plain, seed, LIBS).text


def test_slots_in_exports_are_written_with_the_run(home, monkeypatch):
    from orrery import comfy
    from orrery.comfy import run_prompt
    from orrery.llm import FakeBackend

    backend = FakeBackend([json.dumps({"slot 1": "She once outran a storm."})], name="qwen3vl_8b")
    monkeypatch.setattr(comfy, "llm_for", lambda h, clip=None, **_: backend)
    t = "$who = a {tall|short} heron\nEXPORT:\n  who = $who\n  backstory = --one sentence of backstory for $who--\nA photo of $who."
    text, picks, *_ = run_prompt(t, 2, "text", str(home))
    data = json.loads(picks)
    assert text.startswith("A photo of a ") and "storm" not in text
    assert data["exports"]["backstory"] == "She once outran a storm." and data["exports"]["who"] in text
    assert "backstory for a " in backend.prompts[0]  # the slot's directions arrive rolled


def test_the_gallery_keeps_the_exports_and_its_pictures_carry_them(home, tmp_path):
    from PIL import Image

    from orrery.comfy import log_outputs
    from orrery.home import Home

    pic = tmp_path / "krea2_00001_.png"
    Image.new("RGB", (4, 4)).save(pic)
    data = {"seed": 7, "preset": "krea/x", "template": "0" * 16, "text": "A heron.", "picks": [],
            "exports": {"who": "a tall heron", "skills": ["fishing", "waiting"],
                        "job": {"value": "a ferryman", "tool": "a long pole"}}}
    row = log_outputs(Home(home), json.dumps(data), [str(pic)])[0]
    assert row["exports"] == data["exports"]
    entry = Home(home).libraries()["pictures/krea/x"].entries[0]
    assert (entry.prop("who"), entry.prop("skills"), entry.prop("job"), entry.prop("job_tool")) == \
           ("a tall heron", "fishing, waiting", "a ferryman", "a long pole")
    assert entry.tags == ("exported",)  # `[exported]` keeps the pictures that carry data


def test_a_screenplay_leaves_exports_out_and_says_where_they_belong():
    from orrery.h3 import compile_scene

    c = compile_scene("@h3 t2va\nEXPORT:\n  mood = {calm|grim}\nSHOT 5s: static\nA fox waits.", 1, {})
    assert "calm" not in c.text and "grim" not in c.text
    assert any("EXPORT: is for text templates" in i.message for i in c.lint)
