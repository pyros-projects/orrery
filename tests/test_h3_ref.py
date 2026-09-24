"""Ref2VA (full-reference) compiler tests. GUIDE_* strings are copied verbatim from the complete
example in the official full-reference guide (VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)."""

import re

from orrery.h3 import compile_scene
from orrery.library import Entry, Library

LIBS = {"animal": Library("animal", [Entry("fox")])}

SITCOM = """@h3 ref2va 16:9
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

SHOT 2s | cut
A close-up of LEO, sitting beside MAYA on the orange sofa in CAFE and holding DOG securely in his arms.
LEO (casual young male voice): He just likes cookies more than me.
He closes his mouth into an apologetic smile and strokes the dog's thick white fur.

SHOT 3s | cut
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
    src = """@h3 ref2va
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
    src = """@h3 ref2va
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
    src = """@h3 ref2va
summary: CAFE wakes up.
CAST
CAFE (image 1): the café, with a tall window
SHOT 5s | from image 2 (the café at dawn), push in, small, slow
CAFE fills with morning light.
SFX: a kettle hisses
SHOT 3s | cut, to image 3
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


def test_bracketed_sources_in_prose_become_labels():
    src = """@h3 ref2va
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
    src = """@h3 t2va
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


def test_flat_target_uses_cast_descriptions():
    src = """@h3 ref2va
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
    base = """@h3 ref2va
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
    src = """@h3 ref2va
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
    src = """@h3 ref2va
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


def test_refmods_are_described_but_not_loaded_yet():
    src = """@h3 t2va
CAST
MAYA (refmod maya_canon): a young blonde woman, in a light-pink shirt
SHOT 5s
MAYA waves.
SFX: wind
"""
    res = h3(src)
    assert "A young blonde woman, in a light-pink shirt, waves." in res.text
    assert any("maya_canon" in i.message and i.severity == "warn" for i in res.lint)


def test_reference_sources_outside_ref2va_warn():
    src = """@h3 t2va
CAST
MAYA (image 1): a woman, in pink
SHOT 5s
MAYA waves.
SFX: wind
"""
    assert any("ref2va" in i.message for i in h3(src).lint)


def test_word_count_is_linted_for_generation():
    src = """@h3 ref2va
summary: A waves.
CAST
A (image 1): the dancer, in red
SHOT 5s
A waves.
SFX: wind
"""
    assert any("350" in i.message for i in h3(src).lint)
