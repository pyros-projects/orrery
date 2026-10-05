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
    assert prompt.count("SCENE the lamp") == 2  # ×2: both clips, as they were made
    assert "Write clip 4, from the last clip ended as: the beam sweeps over the sea." in prompt
    assert "style: live-action, cinematic" in prompt and "@h3" not in prompt


@pytest.mark.parametrize("task, template, foreign", [
    ("continue", REEL, ("Krea", "Picture 1")),
    ("story", "@h3 fl2va\nSHOT 5s\nA.", ("Krea", "SCENE", "END ON")),
    ("describe", "a photo", ("SHOT", "SCENE", "H3")),
    ("describe", "@h3 i2va\nSHOT 5s\nA.", ("Krea", "SCENE", "END ON")),
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
    ("SHOT 5s: static\nA cat walks.", "does not start with a SCENE"),
    ("CHUNK a\nA cat walks.", "no SHOT"),
    ("CHUNK a\nSHOT 5s: static\nA.\nCHUNK b\nSHOT 5s: static\nB.", "2 scenes"),
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


def test_a_reel_that_repeats_forever_continues_after_its_first_play(home):
    """#342: no guardrail for a reel without end: the scene that repeats forever is read once."""
    writers.save(Home(home), "continue", "{chunks}\nWrite clip {next}.")
    prompt = writers.request(Home(home), "continue", "@h3 t2va\nCHUNK a repeat forever\nSHOT 5s\nA.", 1, {}, {})
    assert prompt.count("SCENE a") == 1 and prompt.endswith("Write clip 2.")


def test_continue_makes_a_screenplay_without_scenes_a_reel(home):
    """#334: no restriction in the menu; the screenplay is the first scene, the model writes the second."""
    prompt = writers.request(Home(home), "continue", "@h3 t2va\nSHOT 5s: static\nA fox sleeps.", 1, {}, {})
    assert "SCENE the start" in prompt and "A fox sleeps." in prompt and "Write clip 2" in prompt
    assert writers.apply("continue", "@h3 t2va\nSHOT 5s: static\nA fox sleeps.", "SCENE the hunt\nSHOT 5s: static\nIt runs.") == (
        "@h3 t2va\nSCENE the start\nSHOT 5s: static\nA fox sleeps.\n\nSCENE the hunt\nSHOT 5s: static\nIt runs.\n")
    with pytest.raises(writers.WriterError, match="image prompt"):
        writers.request(Home(home), "continue", "a photo of a fox", 1, {}, {})


def test_a_writer_without_its_pictures_writes_from_what_came_along(home):
    """#334: the story without frames imagines them; a prompt from an image without one writes from the prompt;
    a steer goes last."""
    story = writers.request(Home(home), "story", "@h3 fl2va\nSHOT 5s: static\nA fox.", 1, {}, {}, given=[])
    assert "No pictures came along this time. There is no first frame and no last frame this time: imagine them" in story
    assert "Picture 1 is" not in story.split("No pictures came along")[1]
    one = writers.request(Home(home), "story", "@h3 fl2va\nSHOT 5s: static\nA fox.", 1, {}, {}, given=["the first frame"])
    assert "Picture 1 is the first frame. There is no last frame this time: imagine it" in one
    describe = writers.request(Home(home), "describe", "a photo of a red fox in snow", 1, {}, {}, steer="as a woodcut", given=[])
    assert "Write the prompt from this one instead" in describe and "a photo of a red fox in snow" in describe
    assert describe.endswith("The direction, which outweighs everything above: as a woodcut.\n\n"
                             "Answer as asked above, with what you write alone.")
    assert "came along" not in writers.request(Home(home), "describe", "a fox", 1, {}, {}, given=["the picture"])  # as it expects


def test_a_prompt_from_an_image_on_a_reel_writes_from_its_head_and_goes_in_at_the_caret(home):
    """#334: no restriction; its shot cannot take the place of every scene, so the app puts it where the caret is.
    A story on a reel writes scenes between its start and its end instead (#343)."""
    prompt = writers.request(Home(home), "describe", REEL, 1, {}, {}, given=["the first frame"])
    assert "SHOT" in prompt and writers.at_caret("describe", REEL)
    assert not [t for t in ("continue", "story") if writers.at_caret(t, REEL)]
    assert not writers.at_caret("describe", "a photo of a fox")


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
    result, asked = _write(monkeypatch, home, ["SHOT 5s: static\nA."], task="story", template="@h3 fl2va\nSHOT 5s\nA.", seed=1,
                           steer="in the rain")
    assert result["text"] == "SHOT 5s: static\nA."  # no frames wired: written from what came along (#334)
    prompt, images, *_ = asked[0]
    assert images is None and "No pictures came along this time." in prompt and "The direction, which outweighs everything above: in the rain." in prompt


def test_continue_follows_a_loop_and_one_without_end(home):
    """A loop with ×1 plays through; one without end continues after its last scene's first end (#342)."""
    loop = "@h3 t2va\nCHUNK a\nSHOT 5s\nA.\nCHUNK b\nSHOT 5s\nB.\nGOTO: a ×1"
    writers.save(Home(home), "continue", "{chunks}\nWrite clip {next}.")
    prompt = writers.request(Home(home), "continue", loop, 1, {}, {})
    assert prompt.count("SCENE a") == 2 and "Write clip 5." in prompt
    endless = writers.request(Home(home), "continue", loop.replace(" ×1", ""), 1, {}, {})
    assert endless.count("SCENE a") == 1 and endless.count("SCENE b") == 1 and endless.endswith("Write clip 3.")


FILM = """@h3 t2va 16:9
style: live-action
SCENE one
SHOT 5s: static
A fox wakes.
SFX: birds
END ON: the fox stands
SCENE two repeat 2
SHOT 5s: static
The fox hunts.
SFX: grass
END ON: the fox pounces
SCENE three
SHOT 5s: static
The fox sleeps.
SFX: wind
END ON: the fox curls up
CUT TO: one
"""
NEW_SCENE = "SCENE the river\nSHOT 5s: static\nThe fox drinks.\nSFX: water"


def test_continue_after_any_scene_reads_the_reel_until_it_first_ends(home):
    """#342: the sheet picks the scene; its repeats count, and what follows it stays out."""
    writers.save(Home(home), "continue", "{chunks}\nWrite clip {next}, after {handoff}.")
    prompt = writers.request(Home(home), "continue", FILM, 1, {}, {}, opts={"after": 1})
    assert prompt.count("SCENE two") == 2 and "SCENE three" not in prompt
    assert prompt.endswith("Write clip 4, after the last clip ended as: the fox pounces.")
    assert writers.request(Home(home), "continue", FILM, 1, {}, {}, opts={"after": 0}).endswith("Write clip 2, after the last clip ended as: the fox stands.")
    with pytest.raises(writers.WriterError, match="no scene 9"):
        writers.request(Home(home), "continue", FILM, 1, {}, {}, opts={"after": 8})
    jumped = "@h3 t2va\nSCENE a\nSHOT 5s\nA.\nCUT TO: c\nSCENE b\nSHOT 5s\nB.\nSCENE c\nSHOT 5s\nC."
    with pytest.raises(writers.WriterError, match=r"SCENE 2 \(b\) does not play at this seed"):
        writers.request(Home(home), "continue", jumped, 1, {}, {}, opts={"after": 1})


def test_a_new_scene_replaces_the_scenes_after_it_or_goes_in_between(home):
    """#342: Replace drops the scenes after the one it continues, Insert keeps them after the new one."""
    replaced = writers.apply("continue", FILM, NEW_SCENE, {"after": 0})
    assert replaced.endswith("END ON: the fox stands\n\n" + NEW_SCENE + "\n") and "SCENE two" not in replaced
    inserted = writers.apply("continue", FILM, NEW_SCENE, {"after": 0}, insert=True)
    assert "END ON: the fox stands\n\n" + NEW_SCENE + "\n\nSCENE two repeat 2\n" in inserted and "CUT TO: one" in inserted
    assert writers.apply("continue", FILM, NEW_SCENE) == writers.apply("continue", FILM, NEW_SCENE, insert=True) == FILM + "\n" + NEW_SCENE + "\n"


def test_the_story_runs_from_a_scene_or_a_frame_to_a_scene_or_a_frame(home):
    """#343: its start and its end are a frame (imagined when it did not come), a scene as the reel plays it (from:
    with every clip up to its end), N scenes of S seconds between them."""
    h = Home(home)
    prompt = writers.request(h, "story", FILM, 1, {}, {}, opts={"from": 0, "to": 2, "scenes": 2, "seconds": 6})
    assert "You write 2 scenes" in prompt and "Every scene lasts 6 seconds" in prompt and "style: live-action" in prompt
    so_far, end = prompt.split("The reel so far")[1].split("The end:")
    assert "SCENE one" in so_far and "SCENE two" not in so_far and "where the last of these clips ends (the fox stands)" in so_far
    assert "a scene that begins with this shot" in end and "SHOT 5s: static\nThe fox sleeps." in end  # its first shot
    assert "SCENE three" not in end and "Picture" not in prompt
    from orrery.llm import PICTURES

    frames = writers.request(h, "story", FILM, 1, {}, {}, given=["the first frame"])
    assert f"The start: the first frame, this picture: {PICTURES}" in frames and "Picture 1 is the first frame." in frames
    assert "The end: the last frame, which did not come along this time: imagine it" in frames and "You write one scene" in frames
    with pytest.raises(writers.WriterError, match="needs a reel"):
        writers.request(h, "story", "@h3 fl2va\nSHOT 5s\nA.", 1, {}, {}, opts={"from": 0, "scenes": 2})


def test_the_story_s_scenes_are_counted_and_go_between_its_start_and_its_end():
    """#343: N scenes asked, N checked; Replace puts them in place of the scenes between, Insert after the start."""
    two = NEW_SCENE + "\n\nSCENE the den\nSHOT 5s: static\nThe fox returns.\nSFX: leaves"
    opts = {"from": 0, "to": 2, "scenes": 2}
    assert writers.check("story", FILM, two, opts) == (two, None)
    assert "1 scenes; 2 were asked for" in writers.check("story", FILM, NEW_SCENE, opts)[1]
    assert "A scene has no SHOT" in writers.check("story", FILM, "SCENE a\nSHOT 5s: static\nA.\nSCENE b\nB.", opts)[1]
    replaced = writers.apply("story", FILM, two, opts)
    assert "SCENE two" not in replaced and replaced.index("SCENE one") < replaced.index("SCENE the den") < replaced.index("SCENE three")
    inserted = writers.apply("story", FILM, two, opts, insert=True)
    assert inserted.index("SCENE the den") < inserted.index("SCENE two") < inserted.index("SCENE three")
    whole = writers.apply("story", FILM, two, {"scenes": 2})  # first frame to last frame: the whole reel
    assert whole.startswith("@h3 t2va 16:9\nstyle: live-action\n\n" + NEW_SCENE) and "SCENE one" not in whole
    fl2va = "@h3 fl2va 16:9\n\nSHOT 5s: static\nOld."
    assert writers.apply("story", fl2va, two, {"scenes": 2}) == "@h3 fl2va 16:9\n\n" + two + "\n"  # a screenplay: its shots go
    shot = "SHOT 5s: static\nNew."
    assert writers.apply("story", fl2va, shot, insert=True) == "@h3 fl2va 16:9\n\nSHOT 5s: static\nNew.\n\nSHOT 5s: static\nOld.\n"


def test_on_an_image_prompt_the_story_writes_keyframes_onto_a_grid(home):
    """#343: from the first frame to the picture the prompt makes, N keyframe prompts; one Roll renders them all."""
    krea = "# KREA 2 · kites\na photo of a {red|blue} kite over a beach\n: w832 h1216\n"
    prompt = writers.request(Home(home), "story", krea, 1, {}, {}, opts={"scenes": 3}, given=["the first frame"])
    assert "You write 3 image prompts for Krea 2" in prompt and "The start: the first frame, this picture: " in prompt
    assert "The end: the picture this prompt makes:\n\na photo of a red kite over a beach" in prompt
    assert "SHOT" not in prompt and "carry its story on" not in writers.request(
        Home(home), "story", krea, 1, {}, {}, opts={"scenes": 3}, prompt=True)  # the prompt is in it already
    answer = "Here they are:\n1. A photo of a boy with a kite.\n2. The kite {lifts} | rises.\n3. The kite flies high."
    text, problem = writers.check("story", krea, answer, {"scenes": 3})
    assert problem is None and text == "A photo of a boy with a kite.\nThe kite lifts , rises.\nThe kite flies high."
    assert writers.apply("story", krea, text, {"scenes": 3}) == (
        "# KREA 2 · kites\n$keyframe = {A photo of a boy with a kite.|The kite lifts , rises.|The kite flies high.}\n"
        "$keyframe\n: w832 h1216\n@grid $keyframe\n")
    assert "2 keyframes; 3 were asked for" in writers.check("story", krea, "A.\nB.", {"scenes": 3})[1]
    assert writers.apply("story", krea, "A kite.", {"scenes": 1}) == "# KREA 2 · kites\nA kite.\n: w832 h1216\n"


SHOT_A = "SHOT 4s: push in\nA fox runs through snow.\nSFX: crunching snow"
SHOT_B = "SHOT 4s: static\nA fox sleeps under a pine.\nSFX: wind"


def test_a_sheet_prepends_appends_replaces_or_inserts_its_takes_one_after_the_other():
    """#333: Prepend and Append copy the takes in, any number of them, in the order picked; Replace and Insert put them
    where the writer has a place; the caret gets the text alone."""
    fl = "@h3 t2va 16:9\nstyle: live-action\n\nSHOT 5s: static\nOld.\n"
    head = "@h3 t2va 16:9\nstyle: live-action\n\n"
    assert writers.place("describe", fl, [SHOT_A, SHOT_B], how="append")["template"] == f"{fl.rstrip()}\n\n{SHOT_A}\n\n{SHOT_B}\n"
    assert writers.place("describe", fl, [SHOT_A], how="prepend")["template"] == f"{head}{SHOT_A}\n\nSHOT 5s: static\nOld.\n"
    assert writers.place("describe", fl, [SHOT_B, SHOT_A], how="replace")["template"] == f"{head}{SHOT_B}\n\n{SHOT_A}\n"
    assert writers.place("describe", fl, [SHOT_A], how="insert")["template"] == f"{head}{SHOT_A}\n\nSHOT 5s: static\nOld.\n"
    assert writers.place("describe", REEL, [SHOT_A, SHOT_B], how="caret") == {"text": f"{SHOT_A}\n\n{SHOT_B}", "template": None}
    krea = "a photo of a fox\n: w832 h1216\n"
    assert writers.place("describe", krea, ["A fox."], how="prepend")["template"] == f"A fox.\n\n{krea}"
    assert writers.place("story", krea, ["A boy.\nA kite.", "A gull."], {"scenes": 2}, how="replace")["template"] == (
        "$keyframe = {A boy.|A kite.|A gull.}\n$keyframe\n: w832 h1216\n@grid $keyframe\n")  # every keyframe on the grid
    with pytest.raises(writers.WriterError, match="Select a take"):
        writers.place("describe", krea, ["  "])
    with pytest.raises(writers.WriterError, match="'how'"):
        writers.place("describe", krea, ["A fox."], how="somewhere")


def test_takes_go_in_as_a_choice_a_roll_picks_one_whole_take():
    """#333: one-line takes as {a|b}; shots as a binding and IF lines; scenes keep their SCENE lines, the binding in the
    head, so every scene picks the same take."""
    from orrery.h3 import compile_scene

    krea = "a photo of a fox\n: w832 h1216\n"
    assert writers.place("describe", krea, ["A red fox | snow.", "A fox, $5."], how="replace", choice=True)["template"] == (
        "{A red fox \\| snow.|A fox, \\$5.}\n: w832 h1216\n")
    assert writers.place("story", krea, ["A boy.\nA kite."], {"scenes": 2}, how="replace", choice=True)["template"] == (
        "{A boy.|A kite.}\n: w832 h1216\n")  # a choice of keyframes, no grid
    fl = "@h3 t2va 16:9\n\nSHOT 5s: static\nOld.\n"
    placed = writers.place("describe", fl, [SHOT_A, SHOT_B], how="replace", choice=True)["template"]
    assert placed.splitlines()[2:4] == ["$take = {1|2}", "IF $take is 1: SHOT 4s: push in"]
    rolled = {compile_scene(placed, seed, {}, {}).text for seed in range(8)}
    assert len(rolled) == 2 and all(("runs" in t) != ("sleeps" in t) for t in rolled)  # one whole shot each roll
    s1 = "SCENE the river\nSHOT 5s: static\nThe fox drinks.\nEND ON: the fox looks up"
    s2 = "SCENE the den\nSHOT 5s: static\nThe fox sleeps."
    out = writers.place("continue", FILM, [s1, s2], {"after": 0}, how="insert", choice=True)["template"]
    assert "style: live-action\n$take = {1|2}\nSCENE one" in out and "\nSCENE the river\nIF $take is 1: SHOT 5s: static\n" in out
    assert "IF $take is 2: The fox sleeps.\n\nSCENE two repeat 2" in out and "SCENE the den" not in out


def test_a_picture_with_the_screenplay_sent_along_joins_it(home):
    """#333: Prompt from image with the prompt sent along writes the next shot of that screenplay with who is in the
    picture, the picture after the screenplay; the 8B kept the picture's room otherwise (experiments/writer-framing)."""
    from orrery.llm import PICTURES

    fl = "@h3 t2va 16:9\nstyle: live-action\nSHOT 5s: static\nA badger steps onto a log in a misty forest."
    joined = writers.request(Home(home), "describe", fl, 1, {}, {}, "she joins it", ["the first frame"], True)
    assert joined.startswith("You write one more shot for a screenplay") and "A badger steps onto a log" in joined
    assert joined.index("A badger steps") < joined.index(PICTURES) and "take only them" in joined
    assert "carry its story on" not in joined and "The direction, which outweighs everything above: she joins it." in joined
    alone = writers.request(Home(home), "describe", fl, 1, {}, {}, "", ["the first frame"], False)
    assert alone.startswith(writers.default("describe_shot").strip()[:40]) and PICTURES not in alone
    gallery = writers.request(Home(home), "describe", fl, 1, {}, {}, "", ["a picture from the Gallery"], True)
    assert "Picture 1 is a picture from the Gallery." in gallery and "from this one instead" not in gallery
    text, problem = writers.check("describe", fl, "SHOT 5s: static\nShe steps onto the log. SFX: snow crunches")
    assert problem is None and text == "SHOT 5s: static\nShe steps onto the log.\nSFX: snow crunches"


def test_the_story_can_start_or_end_at_the_prompt_on_any_screenplay(home):
    """#343: no scenes needed. To the prompt: the scenes that lead into it, before it (Lucy gets up in the living room
    and walks into the forest); from the prompt: the scenes that go on from it, after it."""
    fl = "@h3 t2va 16:9\nstyle: live-action\nSHOT 5s: static\nA badger steps onto a log in a misty forest."
    into = {"from": "first_frame", "to": "prompt", "scenes": 3, "seconds": 10}
    prompt = writers.request(Home(home), "story", fl, 1, {}, {}, given=["the first frame"], prompt=True, opts=into)
    assert "You write 3 scenes" in prompt and "Every scene lasts 10 seconds" in prompt
    assert "The end: a screenplay that begins with this shot; your last scene leads into it:\n\nSHOT 5s: static\nA badger" in prompt
    assert prompt.count("A badger steps onto a log") == 1  # the prompt is the end, not sent twice
    scenes = "SCENE up\nSHOT 10s: static\nLucy wakes.\nSCENE out\nSHOT 10s: static\nLucy walks.\nSCENE in\nSHOT 10s: static\nLucy arrives."
    assert writers.check("story", fl, scenes, into)[1] is None
    before = writers.place("story", fl, [scenes], into, how="insert")["template"]
    assert before == f"@h3 t2va 16:9\nstyle: live-action\n\n{scenes}\n\nSCENE the start\nSHOT 5s: static\nA badger steps onto a log in a misty forest.\n"
    assert writers.place("story", fl, [scenes], into, how="replace")["template"] == before  # nothing in between
    on = {"from": "prompt", "to": "last_frame", "scenes": 1}
    assert "The start: this screenplay, as it rolls; your first scene goes on from where it ends" in writers.request(
        Home(home), "story", fl, 1, {}, {}, opts=on)
    after = writers.place("story", fl, ["SCENE on\nSHOT 5s: static\nIt goes on."], on, how="insert")["template"]
    assert after.endswith("misty forest.\n\nSCENE on\nSHOT 5s: static\nIt goes on.\n") and "SCENE the start" in after
    assert writers.place("story", FILM, [NEW_SCENE], {"from": "first_frame", "to": "prompt"}, how="insert")["template"].startswith(
        f"@h3 t2va 16:9\nstyle: live-action\n\n{NEW_SCENE}\n\nSCENE one")  # a reel: before its first scene
