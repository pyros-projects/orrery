"""Ref2VA (full-reference) compiler tests. GUIDE_* strings are copied verbatim from the complete
example in the official full-reference guide (VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)."""

import re

import pytest

from orrery.h3 import compile_scene
from orrery.library import Entry, Library

LIBS = {"animal": Library("animal", [Entry("fox")])}

SITCOM = """@h3 ref2va full 16:9
style: realistic multi-camera sitcom style with warm indoor lighting
summary: The target video shows MAYA eating a cookie in CAFE. LEO enters with DOG, which lunges toward the cookie. The three-shot exchange uses [audio 1] as the voice-timbre reference for MAYA and ends with a canned audience laugh.

CAST
CAFE (image 1): the coffee-shop environment, featuring an exposed brick wall, an orange tufted sofa with patterned pillows, a neon sign, and a wooden coffee table
keep: fully_preserved - the exposed brick wall, orange tufted sofa, patterned pillows, neon sign, and wooden coffee table are retained.
DOG (image 2, image 3, image 4): the fluffy white Samoyed, with thick white fur, pointed ears, a dark nose, and a curved tail
keep: fully_preserved - the Samoyed's thick white fur, pointed ears, dark nose, and curved tail are retained.
MAYA (video 1): the young blonde woman, with long blonde hair and a light-pink button-down shirt with rolled-up sleeves
voice: audio 1, containing a spoken English vocal layer
keep: fully_preserved - the blonde woman's identity, long hair, and light-pink shirt are retained.
LEO (video 2): the young man, with short wavy brown hair and a dark-grey hoodie with drawstrings
keep: fully_preserved - the young man's short wavy brown hair and dark-grey hoodie are retained.

SHOT 3s
A medium shot establishes CAFE. MAYA sits on the sofa holding a chocolate-chip cookie. From the left, LEO enters holding the leash of DOG. The dog lunges toward the cookie and pulls the leash taut. MAYA jerks her hand back.
MAYA (light annoyance): Hey! Watch your dog!
She closes her lips and guards the cookie while LEO pulls the dog back.
SFX: soft indoor coffee-shop room tone continues throughout the scene

SHOT 2s: cut
A close-up of LEO, sitting beside MAYA on the orange sofa in CAFE and holding DOG securely in his arms.
LEO (casual young male voice): He just likes cookies more than me.
He closes his mouth into an apologetic smile and strokes the dog's thick white fur.

SHOT 3s: cut
A close-up of MAYA in CAFE. Her annoyance softens as she looks toward the Samoyed.
MAYA (an amused cadence): Well, he has good taste at least.
She smiles and raises the cookie in a small toast-like gesture. A classic canned audience laugh begins immediately after the line and continues through the final frame.
"""

GUIDE_DEFINITIONS = """<Subject 1> is the coffee-shop environment in <Picture 1>, featuring an exposed brick wall, an orange tufted sofa with patterned pillows, a neon sign, and a wooden coffee table.
<Subject 2> is the fluffy white Samoyed in <Picture 2>, <Picture 3>, and <Picture 4>, with thick white fur, pointed ears, a dark nose, and a curved tail.
<Subject 3> is the young blonde woman in <Video 1>, with long blonde hair and a light-pink button-down shirt with rolled-up sleeves.
<Subject 4> is the young man in <Video 2>, with short wavy brown hair and a dark-grey hoodie with drawstrings.
<Audio 1> is the voice-timbre reference for <Subject 3> (S1), containing a spoken English vocal layer."""

GUIDE_SUMMARY = ("[reference generation + audio reference] The target video shows <Subject 3> eating a cookie "
                 "in <Subject 1>. <Subject 4> enters with <Subject 2>, which lunges toward the cookie. The "
                 "three-shot exchange uses <Audio 1> as the voice-timbre reference for <Subject 3> and ends "
                 "with a canned audience laugh.")

GUIDE_RETENTION = """<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - the exposed brick wall, orange tufted sofa, patterned pillows, neon sign, and wooden coffee table are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - the Samoyed's thick white fur, pointed ears, dark nose, and curved tail are retained.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - the blonde woman's identity, long hair, and light-pink shirt are retained.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - the young man's short wavy brown hair and dark-grey hoodie are retained.
<Audio 1>: reference - its vocal timbre guides the dialogue delivery of <Subject 3> without copying the original signal."""


def h3(src, seed=1):
    return compile_scene(src, seed, LIBS, target="h3-base")


def sections(text):
    names = re.findall(r"^(\w+):\n", text, re.MULTILINE)
    bodies = re.split(r"^\w+:\n", text, flags=re.MULTILINE)[1:]
    return names, {n: b.strip() for n, b in zip(names, bodies, strict=True)}


def errors(result):
    return [i.message for i in result.lint if i.severity == "error"]


def test_six_sections_in_the_guide_order():
    names, _ = sections(h3(SITCOM).text)
    assert names == ["subject_definitions", "summary", "retention_analysis", "detailed_description",
                     "overall_soundscape", "non_diegetic_music"]


def test_definitions_summary_and_retention_match_the_guide_example():
    _, s = sections(h3(SITCOM).text)
    assert s["subject_definitions"] == GUIDE_DEFINITIONS
    assert s["summary"] == GUIDE_SUMMARY
    assert s["retention_analysis"] == GUIDE_RETENTION
    assert s["non_diegetic_music"] == "N/A"


def test_detailed_description_opens_with_style_and_labels_every_mention():
    d = sections(h3(SITCOM).text)[1]["detailed_description"]
    lines = d.splitlines()
    assert lines[0] == "The target video uses a realistic multi-camera sitcom style with warm indoor lighting."
    assert lines[1].startswith("[Shot 1] A medium shot establishes <Subject 1>, the coffee-shop environment, "
                               "featuring an exposed brick wall,")
    assert lines[2].startswith("[Shot 2] At 00:03.000, ") and lines[3].startswith("[Shot 3] At 00:05.000, ")
    assert ("<Subject 3> (S1), the young blonde woman, with long blonde hair and a light-pink button-down "
            "shirt with rolled-up sleeves, sits on the sofa") in lines[1]
    assert "the leash of <Subject 2>, the fluffy white Samoyed, with thick white fur" in lines[1]
    assert ("<Subject 3> (S1) says with light annoyance, using the voice timbre referenced from <Audio 1>, "
            "<d>[English] Hey! Watch your dog!</d>") in lines[1]
    assert "a close-up of <Subject 4> (S2), sitting beside <Subject 3> on the orange sofa in <Subject 1>" in lines[2]
    assert "<Subject 4> (S2) says in a casual young male voice, <d>[English] He just likes cookies more than me.</d>" in lines[2]
    assert not re.search(r"\b(MAYA|LEO|DOG|CAFE)\b", d)


def test_the_guide_example_compiles_without_errors():
    assert errors(h3(SITCOM)) == []


def test_audio_labels_count_video_soundtracks_first():
    src = """@h3 ref2va full
summary: A and B play.
CAST
A (video 1 + audio): the dancer, in red
B (video 2): the drummer, in black
voice: audio 1
SHOT 5s
A dances while B drums.
B (low voice): Again.
SFX: drums pound
"""
    defs = sections(h3(src).text)[1]["subject_definitions"]
    assert "<Audio 2> is the voice-timbre reference for <Subject 2> (S1)." in defs
    assert "<Audio 1>" not in defs


def test_a_video_soundtrack_can_be_the_voice():
    src = """@h3 ref2va full
summary: A sings.
CAST
A (video 1 + audio): the singer, in silver
voice: video 1 audio
SHOT 5s
A sings on a rooftop.
A (clear voice): La la la.
SFX: wind hums
"""
    defs = sections(h3(src).text)[1]["subject_definitions"]
    assert "<Audio 1> is the voice-timbre reference for <Subject 1> (S1)." in defs


def test_frame_anchors_become_pictures_with_keyframe_completion():
    src = """@h3 ref2va full
summary: CAFE wakes up.
CAST
CAFE (image 1): the café, with a tall window
SHOT 5s: from image 2 (the café at dawn), push in, small, slow
CAFE fills with morning light.
SFX: a kettle hisses
SHOT 3s: cut, to image 3
Steam rises in CAFE.
"""
    _, s = sections(h3(src).text)
    assert "<Picture 2> is the first frame of [Shot 1], showing the café at dawn." in s["subject_definitions"]
    assert "<Picture 3> is the last frame of [Shot 2]." in s["subject_definitions"]
    assert s["summary"].startswith("[keyframe completion + reference generation] ")
    assert "<Picture 2> ([Shot 1] first frame): fully_preserved - the shot begins from <Picture 2>." in s["retention_analysis"]
    assert "[Shot 1] The shot begins from <Picture 2>." in s["detailed_description"]
    assert "The camera pushes in with small amplitude at slow speed." in s["detailed_description"]
    assert s["detailed_description"].rstrip().endswith("The shot ends on <Picture 3>.")


def test_after_video_continues_the_previous_clip():
    src = """@h3 ref2va full
summary: WASHER finishes the window.
CAST
WASHER (image 1): the window washer, in a red overall
SHOT 5s: after video 1, tracking, slow
WASHER climbs to the next pane.
SFX: wind
"""
    _, s = sections(h3(src).text)
    assert "<Video 1> is the preceding clip; [Shot 1] continues it from its final frame." in s["subject_definitions"]
    assert s["summary"].startswith("[video continuation + reference generation] ")
    assert ("<Video 1> (continuation source): fully_preserved - [Shot 1] picks up where <Video 1> ends, "
            "with its place, people, light and motion.") in s["retention_analysis"]
    assert "[Shot 1] The shot continues from the end of <Video 1>." in s["detailed_description"]
    assert "The camera tracks the moving subject at slow speed." in s["detailed_description"]


def test_after_video_outside_ref2va_is_flagged():
    result = compile_scene("@h3 t2va full\nSHOT 5s: after video 1\nA man waits.\nSFX: rain\n", 1, {})
    assert any("after video N" in i.message for i in result.lint)


def test_bracketed_sources_in_prose_become_labels():
    src = """@h3 ref2va full
summary: A moves like [video 1].
CAST
A (image 1): the dancer, in red
SHOT 5s
A copies the motion of [video 1].
SFX: shoes squeak
"""
    _, s = sections(h3(src).text)
    assert s["summary"].endswith("<Subject 1> moves like <Video 1>.")
    assert "the motion of <Video 1>." in s["detailed_description"]


def test_cast_names_expand_to_descriptions_in_base_modes():
    src = """@h3 t2va full
CAST
MAYA: a young blonde woman, in a light-pink shirt
SHOT 5s
MAYA waves. Then MAYA sits.
MAYA (warm voice): Hi.
SFX: wind
"""
    text = h3(src).text
    assert "[Shot 1] A young blonde woman, in a light-pink shirt, waves. Then the young blonde woman sits." in text
    assert "The young blonde woman (S1) says in a warm voice: <d>[English] Hi.</d>" in text
    assert "MAYA" not in text


def test_later_mentions_use_the_head_noun_even_without_a_comma():
    src = """@h3 t2va full
CAST
HOST: an adult human facing the camera
ENTITY: a compact humanoid alien with an elongated head and large dark eyes
SHOT 5s
HOST stands still. ENTITY moves inside HOST. ENTITY reaches the mouth.
SFX: breathing
"""
    text = h3(src).text
    assert ("An adult human facing the camera stands still. A compact humanoid alien with an elongated head "
            "and large dark eyes moves inside the adult human. The compact humanoid alien reaches the mouth.") in text


def test_flat_target_uses_cast_descriptions():
    src = """@h3 ref2va full
summary: DOG naps.
CAST
DOG (image 1): the fluffy white Samoyed, with a curved tail
SHOT 5s
DOG naps by the fire. DOG snores.
SFX: fire crackles
"""
    flat = compile_scene(src, 1, LIBS, target="flat").text
    assert flat == "The fluffy white Samoyed, with a curved tail, naps by the fire. The fluffy white Samoyed snores."


def test_ref2va_lint_advises_without_errors():
    base = """@h3 ref2va full
CAST
{cast}
SHOT 5s
A dances. B waits.
SFX: wind
"""
    res = h3(base.format(cast="A (image 12, photo 3): the dancer\nkeep: fully preserved\nB: the drummer\nvoice: audio 1\nkeep: whatever"))
    msgs = " ".join(i.message for i in res.lint)
    assert "summary:" in msgs
    assert "image 12" in msgs and "photo 3" in msgs
    assert "voice" in msgs and "never speaks" in msgs
    assert not errors(res)


def test_text_only_subjects_are_fine_in_ref2va():
    src = """@h3 ref2va full
summary: CAFE hums.
CAST
CAFE: the coffee-shop environment, featuring an exposed brick wall
SHOT 5s
CAFE hums with morning chatter.
SFX: cups clink
"""
    res = h3(src)
    assert "<Subject 1> is the coffee-shop environment, featuring an exposed brick wall." in res.text
    assert not any("CAFE" in i.message for i in res.lint)


def test_keep_is_forgiving():
    src = """@h3 ref2va full
summary: A B C D dance.
CAST
A (image 1): the dancer
keep: full
B (image 2): the drummer
keep: partially preserved - only the drum kit is kept
C (image 3): the singer
keep: weak: a vague resemblance
D (image 4): the bassist
keep: only the red bass
SHOT 5s
A, B, C and D play.
SFX: music plays
"""
    ret = sections(h3(src).text)[1]["retention_analysis"]
    assert "<Subject 1> (appears in [Shot 1]): fully_preserved - the defined appearance of the dancer is retained." in ret
    assert "<Subject 2> (appears in [Shot 1]): partially_preserved - only the drum kit is kept" in ret
    assert "<Subject 3> (appears in [Shot 1]): weak_reference - a vague resemblance" in ret
    assert "<Subject 4> (appears in [Shot 1]): fully_preserved - only the red bass" in ret


def test_refmods_are_described_and_listed_for_orrery_refmods():
    src = """@h3 t2va full
CAST
MAYA (refmod maya_canon): a young blonde woman, in a light-pink shirt
SHOT 5s
MAYA waves.
SFX: wind
"""
    res = h3(src)
    assert "A young blonde woman, in a light-pink shirt, waves." in res.text
    assert res.refmods == [{"name": "maya_canon", "member": "MAYA", "strength": 1.0, "from": 0.35}]
    assert not any("maya_canon" in i.message for i in res.lint)


REFMOD_TOUR = """@h3 ref2va 16:9
refmods: at 0.9 from 40%
CAST
SALON (refmod salon_canon at 0.5 from 20%): a grand salon, with a black piano
HALL (refmod hall_canon): a long hallway
GARDEN (refmod garden_canon, global): a walled garden
SHOT 5s
The camera crosses SALON toward the doors.
"""


def test_a_refmod_carries_its_strength_and_start_or_the_screenplay_defaults():
    mods = {m["name"]: m for m in h3(REFMOD_TOUR.replace("crosses SALON", "crosses SALON into HALL")).refmods}
    assert mods["salon_canon"] == {"name": "salon_canon", "member": "SALON", "strength": 0.5, "from": 0.2}
    assert (mods["hall_canon"]["strength"], mods["hall_canon"]["from"]) == (0.9, 0.4)


def test_a_clip_gets_the_refmods_of_the_members_it_names_and_the_global_ones():
    assert [m["name"] for m in h3(REFMOD_TOUR).refmods] == ["salon_canon", "garden_canon"]
    quiet = REFMOD_TOUR.replace("The camera crosses SALON toward the doors.", "The camera rests on the salon.")
    assert [m["name"] for m in h3(quiet).refmods] == ["garden_canon"]  # lowercase prose names no member


def test_refmod_syntax_problems_are_lint_not_failures():
    src = REFMOD_TOUR.replace("refmod hall_canon", "refmod hall_canon from 150%").replace(", global", ", everywhere")
    lint = [i.message for i in h3(src).lint]
    assert any("from 150%" in m for m in lint) and any('"everywhere"' in m for m in lint)


def test_reference_sources_outside_ref2va_warn():
    src = """@h3 t2va full
CAST
MAYA (image 1): a woman, in pink
SHOT 5s
MAYA waves.
SFX: wind
"""
    assert any("ref2va" in i.message for i in h3(src).lint)


def test_word_count_is_linted_for_generation():
    src = """@h3 ref2va full
summary: A waves.
CAST
A (image 1): the dancer, in red
SHOT 5s
A waves.
SFX: wind
"""
    assert any("350" in i.message for i in h3(src).lint)


def test_full_definitions_put_the_picture_after_the_head_noun():
    src = "@h3 ref2va full\nsummary: VICTIM waits.\nCAST\nVICTIM (image 1): an arrogant young man in an expensive suit\nSHOT 5s\nVICTIM waits.\nSFX: x\n"
    assert "<Subject 1> is an arrogant young man in <Picture 1>, in an expensive suit." in h3(src).text


def test_empty_sections_are_left_out():
    """H3 copes without them; an empty subject_definitions or a summary that is only its task prefix is noise."""
    bare = h3("@h3 ref2va full 2:3\nSHOT 5s: push in, slow\nA girl stretches in a living room.\nSFX: foley sound\n").text
    names, _ = sections(bare)
    assert names == ["detailed_description", "overall_soundscape", "non_diegetic_music"]
    cast = h3("@h3 ref2va full\nCAST\nA (image 1): a woman\nSHOT 5s\nA waits.\nSFX: wind\n").text
    names, _ = sections(cast)
    assert names == ["subject_definitions", "retention_analysis", "detailed_description", "overall_soundscape",
                     "non_diegetic_music"]
    summed = h3("@h3 ref2va full\nsummary: A waits.\nCAST\nA (image 1): a woman\nSHOT 5s\nA waits.\nSFX: wind\n").text
    assert sections(summed)[1]["summary"].startswith("[reference generation] ")


# --- lite by default, full on demand, keep: macros (2026-10-02) ------------------------------

KEEP_SRC = "@h3 {mode} 16:9{fmt}\nCAST\nKEEPER (image 1): an old lighthouse keeper, in a yellow coat\n{keep}SHOT 5s: static\nKEEPER waves.\nSFX: wind"


def keep_text(mode="ref2va", fmt="", keep=""):
    return compile_scene(KEEP_SRC.format(mode=mode, fmt=fmt, keep=keep), 1, {})


def test_lite_is_the_default_and_full_writes_the_guides_format():
    assert keep_text().text.startswith("<Subject 1> = an old lighthouse keeper of <Picture 1>")
    assert keep_text(fmt=" lite").text == keep_text().text
    assert keep_text(fmt=" full").text.startswith("subject_definitions:\n<Subject 1> is an old lighthouse keeper")


@pytest.mark.parametrize("keep, marker, reason", [
    ("all", "fully_preserved", "the old lighthouse keeper is retained as defined, in every detail."),
    ("face, hair", "partially_preserved", "only the face and hair of the old lighthouse keeper are retained"),
    ("face and outfit + body", "partially_preserved", "only the face, outfit, and build of the old lighthouse keeper"),
    ("style", "attribute_transfer", "only the style of the old lighthouse keeper carries over"),
    ("place", "fully_preserved", "is retained as a place"),
    ("loose", "weak_reference", "only a loose reference"),
    ("partial - only his face", "partially_preserved", "only his face"),  # the written form still works
])
def test_keep_macros_write_a_marker_and_a_reason(keep, marker, reason):
    from orrery.cast import parse_keep

    got_marker, got_reason = parse_keep(keep)
    assert got_marker == marker and reason in got_reason.replace("{who}", "the old lighthouse keeper")


def test_a_keep_line_always_brings_a_retention_block():
    for mode, fmt in (("ref2va", ""), ("ref2va", " full"), ("i2va", ""), ("i2va", " full"), ("t2va", "")):
        text = keep_text(mode, fmt, "keep: face\n").text
        assert "retention_analysis:\n" in text and "partially_preserved - only the face of the old lighthouse keeper" in text, (mode, fmt)
    assert "retention_analysis" not in keep_text().text  # without keep: lite writes none
    i2va = keep_text("i2va", "", "keep: face\n").text  # after the alignment line, which follows the definitions
    assert i2va.index("is fully referenced") < i2va.index("retention_analysis")
    with pytest.raises(ValueError, match="stands alone"):
        keep_text(keep="keep: all, face\n")


def test_a_summary_asks_for_full():
    lite = compile_scene("@h3 ref2va\nsummary: A waits.\nCAST\nA (image 1): a woman\nSHOT 5s\nA waits.\nSFX: wind\n", 1, {})
    assert any("add full" in i.message for i in lite.lint) and "A waits." not in lite.text.split("integrated")[0]


def test_a_member_no_shot_names_is_left_out_and_lint_says_so():
    src = """@h3 ref2va 16:9
CAST
MAYA (image 1): a young blonde woman, in a light-pink shirt
DOG (image 2): the fluffy white Samoyed
SHOT 5s
MAYA waves.
"""
    res = h3(src)
    assert "Samoyed" not in res.text and "pink shirt" in res.text
    assert any("DOG is in the CAST, but no shot" in i.message for i in res.lint)


def test_an_image_takes_at_and_from_and_the_picks_name_its_packed_place():
    src = """@h3 ref2va 2:3
CAST
EMMA (image 3 at 0.5 from 35%): a young woman in a red coat
TOM (image 5): a tall man
SHOT 5s: static
EMMA waves to TOM.
"""
    assert compile_scene(src, 1, LIBS, packed=True).images == [
        {"ref": 1, "image": 3, "member": "EMMA", "strength": 0.5, "from": 0.35}]
    assert h3(src).images[0]["ref"] == 3  # without Orrery Refs: the slot as wired
    bad = h3(src.replace("TOM (image 5)", "TOM (video 1 at 0.4)"))
    assert any("video 1 takes no at or from" in i.message for i in bad.lint)


def test_a_member_twice_in_one_cast_block_warns_and_the_first_counts():
    src = """@h3 ref2va 2:3
CAST
EMMA (image 1): a young woman in a red coat
EMMA (image 2): a young woman in a blue coat
SHOT 5s: static
EMMA waves.
"""
    res = h3(src)
    assert "red coat" in res.text and "blue coat" not in res.text
    assert any("EMMA is in the CAST twice" in i.message for i in res.lint)
