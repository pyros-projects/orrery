"""orrery's language model writes screenplays: the three writers (continue the reel, the story
between two frames, a prompt from a picture), each with a prompt of its own, what they send, how an
answer is checked and where it lands in the template."""

import pytest

from orrery import writers
from orrery.home import Home

REEL = """@h3 t2va 16:9
style: live-action, cinematic
$storm = {a rising gale|a heavy sea fog}
CAST
KEEPER: an old lighthouse keeper
CHUNK the stairs
SHOT 8s: tracking, slow
KEEPER climbs the stairs while $storm batters the tower.
SFX: boots on iron steps
HANDOFF: KEEPER reaches the lamp room door
CHUNK the lamp repeat 2
SHOT 7s: push in, small, slow
KEEPER lights the lamp in $storm.
SFX: a match strikes
HANDOFF: the beam sweeps over the sea
"""
CHUNK_ANSWER = """Here is the next clip:
```
CHUNK the ship
SHOT 8s: pull out, slow
Far below, the beam finds a small fishing boat fighting the waves.
SFX: waves crash against the rocks
HANDOFF: the boat turns toward the light
```"""


def test_continue_reads_every_segment_resolved_and_asks_for_the_next(home):
    h = Home(home)
    assert writers.request(h, "continue", REEL, 3, {}, {}).startswith(writers.default("continue").strip()[:40])
    writers.save(h, "continue", "{world}\n\n{chunks}\n\nWrite clip {next}, from {handoff}.")
    prompt = writers.request(h, "continue", REEL, 3, {}, {})
    storm = "a rising gale" if "a rising gale" in prompt else "a heavy sea fog"
    assert f"KEEPER climbs the stairs while {storm} batters the tower." in prompt and "$storm" not in prompt
    assert prompt.count("CHUNK the lamp") == 2  # repeat 2: both clips, as they were made
    assert "Write clip 4, from the last clip ended as: the beam sweeps over the sea." in prompt
    assert "style: live-action, cinematic" in prompt and "@h3" not in prompt


@pytest.mark.parametrize("task, template, foreign", [
    ("continue", REEL, ("Krea", "Picture 1")),
    ("story", "@h3 fl2va\nSHOT 5s\nA.", ("Krea", "CHUNK", "HANDOFF")),
    ("describe", "a photo", ("SHOT", "CHUNK", "H3")),
    ("describe", "@h3 i2va\nSHOT 5s\nA.", ("Krea", "CHUNK", "HANDOFF")),
])
def test_each_writer_sends_only_its_own_rules(home, task, template, foreign):
    prompt = writers.request(Home(home), task, template, 1, {}, {})
    assert not [word for word in foreign if word in prompt] and "orrery" not in prompt.lower()


def test_a_continued_chunk_is_cleaned_checked_and_appended():
    text, problem = writers.check("continue", REEL, CHUNK_ANSWER)
    assert problem is None and text.startswith("CHUNK the ship") and "```" not in text
    new = writers.apply("continue", REEL, text)
    assert new.startswith(REEL.rstrip()) and new.rstrip().endswith("HANDOFF: the boat turns toward the light")


@pytest.mark.parametrize("answer, words", [
    ("CHUNK a\nSHOT 5s: static\n__animal__ walks.", "wildcards"),
    ("CHUNK a\nSHOT 5s: static\nA {cat|dog} walks.", "choices"),
    ("SHOT 5s: static\nA cat walks.", "does not start with a CHUNK"),
    ("CHUNK a\nA cat walks.", "no SHOT"),
    ("CHUNK a\nSHOT 5s: static\nA.\nCHUNK b\nSHOT 5s: static\nB.", "2 chunks"),
    ("", "empty"),
])
def test_a_continued_chunk_that_does_not_fit_is_reported(answer, words):
    assert words in writers.check("continue", REEL, answer)[1]


def test_story_and_describe_write_a_shot_under_the_header(home):
    fl2va = "# a comment\n@h3 fl2va 16:9\nstyle: live-action\n\nSHOT 6s: static\nOld text.\nSFX: old\n"
    prompt = writers.request(Home(home), "story", fl2va, 1, {}, {})
    assert "Picture 1 is the first frame" in prompt and "SHOT 6s:" in prompt and "style: live-action" in prompt
    text, problem = writers.check("story", fl2va, "SHOT 6s: static\nThe cat crosses the room.\nSFX: soft paws")
    assert problem is None
    assert writers.apply("story", fl2va, text) == ("# a comment\n@h3 fl2va 16:9\nstyle: live-action\n\n"
                                                   "SHOT 6s: static\nThe cat crosses the room.\nSFX: soft paws\n")
    i2va = "@h3 i2va 16:9\n\nSHOT 5s: push in\nOld."
    assert "brings it to life" in writers.request(Home(home), "describe", i2va, 1, {}, {})
    assert writers.check("describe", i2va, "A cat.")[1] == "The answer has no SHOT line."


def test_describe_writes_an_image_prompt_for_a_still(home):
    krea = "# KREA 2 · quickstart\na photo of {a fox|a heron}\n: w832 h1216\n"
    assert "image prompts for Krea 2" in writers.request(Home(home), "describe", krea, 1, {}, {})
    text, problem = writers.check("describe", krea, 'Prompt: "A 35mm photograph of a grey cat on a white\nbed, soft window light."')
    assert problem is None and text == "A 35mm photograph of a grey cat on a white bed, soft window light."
    assert writers.apply("describe", krea, text) == f"# KREA 2 · quickstart\n{text}\n: w832 h1216\n"
    assert "screenplay" in writers.check("describe", krea, "SHOT 5s: static\nA cat.")[1]


def test_a_reel_that_repeats_forever_has_no_next_chunk(home):
    with pytest.raises(writers.WriterError, match="forever"):
        writers.request(Home(home), "continue", "@h3 t2va\nCHUNK a repeat forever\nSHOT 5s\nA.", 1, {}, {})
    with pytest.raises(writers.WriterError, match="CHUNK"):
        writers.request(Home(home), "continue", "@h3 t2va\nSHOT 5s\nA.", 1, {}, {})


def test_a_shot_writer_leaves_a_reel_alone(home):
    for task in ("story", "describe"):
        with pytest.raises(writers.WriterError, match="reel"):
            writers.request(Home(home), task, REEL, 1, {}, {})


def test_the_texts_can_be_edited_and_go_back_to_their_default(home):
    h = Home(home)
    assert writers.texts(h)["story"]["edited"] is False
    writers.save(h, "story", "Picture 1, Picture 2: write {seconds} seconds. {unknown} stays.")
    assert writers.texts(h)["story"]["edited"] is True
    assert "write 5 seconds. {unknown} stays." in writers.request(h, "story", "@h3 fl2va\n", 1, {}, {})
    writers.save(h, "story", None)
    assert writers.texts(h)["story"] == {"text": writers.default("story"), "default": writers.default("story"), "edited": False}
    with pytest.raises(ValueError, match="no writer text"):
        writers.save(h, "nope", "x")


def _write(monkeypatch, home, replies, **inputs):
    import json

    from orrery import comfy
    from orrery.comfy_write import OrreryWrite
    from orrery.llm import FakeBackend
    asked = []

    class Recording(FakeBackend):
        def complete(self, prompt, images=None):
            asked.append((prompt, images, self.seed, self.temperature))
            return super().complete(prompt, images)

    def llm_for(h, clip=None, seed=0, temperature=None):
        if replies is None:
            return None
        backend = Recording(replies)
        backend.seed, backend.temperature = seed, temperature
        return backend

    monkeypatch.setattr(comfy, "llm_for", llm_for)
    out = OrreryWrite().write(home=str(home), **inputs)
    return json.loads(out["ui"]["orrery_write"][0]), asked


def test_the_write_node_asks_once_and_hands_back_the_new_template(home, monkeypatch):
    result, asked = _write(monkeypatch, home, [CHUNK_ANSWER], task="continue", template="# my reel\n" + REEL, seed=3, idea=2)
    assert len(asked) == 1 and asked[0][1] is None and "Write clip 4" in asked[0][0]
    assert asked[0][2] == 5 and result["idea"] == 2  # the model samples at seed + idea
    assert asked[0][3] == 0.8  # the writers' own temperature: each idea a different one
    assert result["problem"] is None and result["text"].startswith("CHUNK the ship")
    assert result["template"].startswith("# my reel\n@h3 t2va") and result["template"].rstrip().endswith("toward the light")


def test_an_answer_that_does_not_fit_comes_back_as_an_idea_with_its_problem(home, monkeypatch):
    result, _ = _write(monkeypatch, home, ["CHUNK a\nSHOT 5s: static\n__animal__ walks."], task="continue", template=REEL, seed=3)
    assert "wildcards" in result["problem"] and "__animal__" in result["text"] and "__animal__" in result["template"]


def test_the_write_node_says_what_is_missing(home, monkeypatch):
    result, _ = _write(monkeypatch, home, None, task="continue", template=REEL, seed=1)
    assert "language model" in result["error"]
    result, asked = _write(monkeypatch, home, ["SHOT 5s: static\nA."], task="story", template="@h3 fl2va\nSHOT 5s\nA.", seed=1)
    assert "first and the last frame" in result["error"] and not asked
