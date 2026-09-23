"""H3 compiler tests. Golden alignment strings are copied verbatim from the
official guide (docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md, MiniMaxAI/MiniMax-H3)."""

import pytest

from orrery.dsl import MissingLibrary
from orrery.h3 import compile_scene
from orrery.library import Entry, Library

LIBS = {
    "animal": Library("animal", [Entry("fox")]),
    "camera": Library("camera", [Entry("static")]),
}

GUIDE_I2VA = ("For the target video, at 0.00 seconds into the target video, "
              "<Picture 1> (from [Shot 1]) is fully referenced.")
GUIDE_FL2VA_8S = ("How the reference pictures align with the target video — Picture 1 (from Shot 1) "
                  "aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) "
                  "aligns with the 8.00-second mark of the target video.")
GUIDE_L2VA_6S = ("How the reference pictures align with the target video — <Picture 1> "
                 "(from [Shot 1]) aligns with the 6.00-second mark of the target video.")

BAKER = """@h3 t2va 16:9
style: live-action, cinematic
SHOT 5s | push in, small, slow
A medium-wide shot frames a baker opening the shutters of a small street bakery before sunrise.
The middle-aged baker places a fresh loaf on the wooden counter.
BAKER (calm, slightly raspy voice): First batch of the morning.
SFX: wooden shutters scrape open over a quiet street; trays clink softly inside the bakery
SHOT 3s | cut
A close-up of steam rising from the sliced bread.
MUSIC: a soft acoustic-guitar pattern at a moderate tempo with a gentle fade at the end
"""


def h3(src, seed=1, libs=LIBS):
    return compile_scene(src, seed, libs, target="h3-base")


def errors(result):
    return [i.message for i in result.lint if i.severity == "error"]


def warnings(result):
    return [i.message for i in result.lint if i.severity == "warn"]


# --- golden: the four official guide cases -------------------------------------------------

def test_t2va_has_no_alignment_line_and_fields_in_order():
    text = h3(BAKER).text
    assert text.startswith("integrated_multimodal_description: [Shot 1] Live-action, cinematic, "
                           "a medium-wide shot frames a baker")
    assert text.index("\n\noverall_soundscape: ") < text.index("\n\nnon_diegetic_music: ")


def test_t2va_camera_voice_and_cut_follow_the_guide():
    text = h3(BAKER).text
    assert "The camera pushes in with small amplitude at slow speed." in text
    assert ("The baker with a calm, slightly raspy voice (S1) says: "
            "<d>[English] First batch of the morning.</d>") in text
    assert "[Shot 2] At 00:05.000, the camera cuts to a close-up of steam" in text


def test_i2va_alignment_line_is_byte_identical_to_the_guide():
    src = ("@h3 i2va\nSHOT 6s | truck right, small, slow\n"
           "The young woman shown in <Picture 1> remains beside the train window.\n"
           "SFX: rain ticks against the window\n")
    assert h3(src).text.startswith(GUIDE_I2VA + "\n\nintegrated_multimodal_description: [Shot 1] ")


def test_fl2va_alignment_line_is_byte_identical_to_the_guide():
    src = ("@h3 fl2va\nSHOT 8s | pull out, small, slow\n"
           "A cyclist begins in the framing of Picture 1 and settles into Picture 2.\n"
           "SFX: rain falls steadily on the pavement\n")
    r = h3(src)
    assert r.text.startswith(GUIDE_FL2VA_8S + "\n\n")
    assert r.text.endswith("non_diegetic_music: N/A")


def test_l2va_alignment_line_is_byte_identical_to_the_guide():
    src = ("@h3 l2va\nSHOT 6s | push in, small, slow\n"
           "A glass falls and settles into the arrangement established by <Picture 1>.\n"
           "SFX: the glass breaks\n")
    assert h3(src).text.startswith(GUIDE_L2VA_6S + "\n\n")


# --- mechanics ----------------------------------------------------------------------------

def test_timestamps_accumulate_shot_durations():
    src = ("@h3 t2va\nSHOT 4s\nA.\nSHOT 3.5s | cut\nB.\nSHOT 2s | cut\nC.\n"
           "SFX: wind\n")
    text = h3(src).text
    assert "[Shot 2] At 00:04.000, the camera cuts to b." in text
    assert "[Shot 3] At 00:07.500, the camera cuts to c." in text


def test_speaker_ids_follow_first_vocal_event_and_stay_stable():
    src = ("@h3 t2va\nSHOT 3s\nA room.\nWOMAN (low voice): Hi.\nMAN (bright voice): Hey.\n"
           "SHOT 3s | cut\nA door.\nWOMAN: Bye.\nSFX: steps\n")
    text = h3(src).text
    assert "The woman with a low voice (S1) says: <d>[English] Hi.</d>" in text
    assert "The man with a bright voice (S2) says: <d>[English] Hey.</d>" in text
    assert "The woman (S1) says: <d>[English] Bye.</d>" in text


def test_voiceover_uses_exact_phrase_and_lip_clause():
    src = "@h3 t2va\nSHOT 5s\nA man walks.\nMAN (deep voice, voiceover): I remember.\nSFX: steps\n"
    assert ("says in an off-screen voiceover: <d>[English] I remember.</d> "
            "while their lips remain completely closed.") in h3(src).text


def test_off_screen_speaker():
    src = "@h3 t2va\nSHOT 5s\nA forest.\nNARRATOR (calm voice, off-screen): Listen.\nSFX: wind\n"
    assert "(S1) says off-screen: <d>[English] Listen.</d>" in h3(src).text


def test_dialogue_language_tag_and_verbatim_words():
    src = "@h3 t2va\nSHOT 5s\nA café.\nWAITER: [German] Noch einen Kaffee?\nSFX: cups\n"
    assert "<d>[German] Noch einen Kaffee?</d>" in h3(src).text


def test_camera_static_and_modifier_order():
    src = "@h3 t2va\nSHOT 3s | static\nA.\nSHOT 3s | cut, pan left, slow, large\nB.\nSFX: x\n"
    text = h3(src).text
    assert "The camera holds a static shot." in text
    assert "The camera pans left with large amplitude at slow speed." in text


def test_unknown_camera_motion_is_a_lint_error():
    src = "@h3 t2va\nSHOT 5s | spin wildly\nA.\nSFX: x\n"
    assert any("spin wildly" in m for m in errors(h3(src)))


def test_transitions():
    src = "@h3 t2va\nSHOT 3s\nA.\nSHOT 3s | fade, static\nB night sky.\nSFX: x\n"
    assert "At 00:03.000, the shot fades to b night sky." in h3(src).text


def test_soundscape_sentences_and_silence():
    two = h3("@h3 t2va\nSHOT 5s\nA.\nSFX: rain falls; a door creaks\nSFX: thunder rolls\n")
    assert "overall_soundscape: Rain falls while a door creaks. Thunder rolls." in two.text
    silent = h3("@h3 t2va\nSHOT 5s\nA.\nSFX: silence\n")
    assert "overall_soundscape: N/A" in silent.text and not errors(silent)
    missing = h3("@h3 t2va\nSHOT 5s\nA.\n")
    assert any("SFX" in m for m in errors(missing))


def test_music_absent_is_na_and_mood_words_warn():
    assert h3("@h3 t2va\nSHOT 5s\nA.\nSFX: x\n").text.endswith("non_diegetic_music: N/A")
    moody = h3("@h3 t2va\nSHOT 5s\nA.\nSFX: x\nMUSIC: an epic sad score\n")
    assert any("epic" in m for m in warnings(moody))


def test_duration_outside_4_to_15_seconds_is_an_error():
    assert any("4–15" in m for m in errors(h3("@h3 t2va\nSHOT 3s\nA.\nSFX: x\n")))
    assert any("4–15" in m for m in errors(h3("@h3 t2va\nSHOT 16s\nA.\nSFX: x\n")))


def test_keyframe_anchor_warnings():
    assert warnings(h3("@h3 i2va\nSHOT 5s\nA woman.\nSFX: x\n"))
    assert warnings(h3("@h3 fl2va\nSHOT 3s\nPicture 1.\nSHOT 3s | cut\nPicture 2.\nSFX: x\n"))
    assert warnings(h3("@h3 l2va\nSHOT 5s\nA glass.\nSFX: x\n"))


def test_clip_weight_syntax_warns():
    assert any("weight" in m for m in warnings(h3("@h3 t2va\nSHOT 5s\nA (fox:1.3).\nSFX: x\n")))


def test_slots_expand_and_record_picks():
    src = "@h3 t2va\n$hero = __animal__\nSHOT 5s | __camera__\nA $hero sleeps.\nSFX: x\n"
    r = h3(src)
    assert "A fox sleeps." in r.text and "The camera holds a static shot." in r.text
    assert {p.label for p in r.picks} == {"$hero ← __animal__", "__camera__"}


def test_sentence_case_after_picks():
    src = "@h3 t2va\n$hero = __animal__\nSHOT 5s\nA forest. $hero steps onto a log.\nSFX: x\n"
    assert "Fox steps onto a log." in h3(src).text


def test_missing_library_raises():
    with pytest.raises(MissingLibrary):
        h3("@h3 t2va\nSHOT 5s\nA __weather__ day.\nSFX: x\n")


def test_flat_writer_is_style_plus_first_shot_prose():
    r = compile_scene(BAKER, 1, LIBS, target="flat")
    assert r.text == ("Live-action, cinematic, a medium-wide shot frames a baker opening the shutters "
                      "of a small street bakery before sunrise. The middle-aged baker places a fresh "
                      "loaf on the wooden counter.")
