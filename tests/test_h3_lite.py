"""Ref2VA lite: `<Subject N> = …` definitions over the three base fields, the format people
write by hand for the MiniMax H3 Reference to Video node. `lite` in the @h3 header selects it
in any mode."""

from orrery.comfy import shape
from orrery.h3 import compile_scene
from orrery.library import Entry, Library

LIBS = {"animal": Library("animal", [Entry("fox")])}

HORROR = """@h3 ref2va 16:9 lite
style: live-action, cinematic body horror, photorealistic

CAST
HOST (image 1): the skinny and pretty woman
ENTITY: a gaunt humanoid figure, with long jointed limbs

SHOT 8s | push in, small, slow
HOST stands framed from the waist up. A pressure moves beneath her skin as ENTITY shifts inside HOST.
SFX: quiet room ambience; skin-like stretching sounds
MUSIC: N/A
"""


def h3(src, seed=1):
    return compile_scene(src, seed, LIBS, target="h3-base")


def test_definitions_then_the_three_base_fields():
    text = h3(HORROR).text
    assert text.startswith("<Subject 1> = the skinny and pretty woman of <Picture 1>\n"
                           "<Subject 2> = a gaunt humanoid figure, with long jointed limbs\n\n"
                           "integrated_multimodal_description: [Shot 1] Live-action, cinematic body horror, "
                           "photorealistic. <Subject 1> stands framed from the waist up.")
    assert "as <Subject 2> shifts inside <Subject 1>." in text
    assert "The camera pushes in with small amplitude at slow speed." in text
    assert "summary" not in text and "retention" not in text
    assert text.endswith("overall_soundscape: Quiet room ambience and skin-like stretching sounds.\n\n"
                         "non_diegetic_music: N/A")


def test_lite_needs_no_summary_and_has_no_errors():
    res = h3(HORROR)
    assert not [i for i in res.lint if i.severity == "error"]
    assert not any("summary" in i.message for i in res.lint)


def test_lite_works_in_text_modes_and_keeps_the_alignment_line():
    t2va = h3("@h3 t2va lite\nCAST\nCURATOR: a tall woman, in a black coat\nSHOT 5s\nCURATOR bows.\nSFX: x\n").text
    assert t2va.startswith("<Subject 1> = a tall woman, in a black coat\n\nintegrated_multimodal_description: "
                           "[Shot 1] <Subject 1> bows.")
    i2va = h3("@h3 i2va lite\nCAST\nCURATOR: a tall woman\nSHOT 5s\n<Picture 1> shows CURATOR.\nSFX: x\n").text
    assert i2va.startswith("<Subject 1> = a tall woman\n\nFor the target video, at 0.00 seconds")


def test_lite_dialogue_uses_the_subject_label():
    src = "@h3 ref2va lite\nCAST\nMAYA (video 1): a young woman\nvoice: audio 1\nSHOT 5s\nMAYA smiles.\nMAYA (warm voice): Hi.\nSFX: x\n"
    text = h3(src).text
    assert "<Audio 1> = the voice of <Subject 1>" in text
    assert "<Subject 1> (S1) says in a warm voice, using the voice timbre referenced from <Audio 1>: " \
           "<d>[English] Hi.</d>" in text


def test_lite_can_come_before_or_after_the_ratio():
    assert shape("@h3 ref2va lite 9:16\nSHOT 5s\nA.\n")[:2] == shape("@h3 ref2va 9:16 lite\nSHOT 5s\nA.\n")[:2]
    assert shape("@h3 ref2va lite 9:16\nSHOT 5s\nA.\n")[:2] == (768, 1344)
    assert h3("@h3 ref2va lite 9:16\nSHOT 5s\nA.\nSFX: x\n").scene.ratio == "9:16"


def test_the_picture_follows_the_head_noun_when_there_is_no_comma():
    src = "@h3 ref2va lite\nCAST\nVICTIM (image 1): an arrogant young man in an expensive suit\nSHOT 5s\nVICTIM waits.\nSFX: x\n"
    assert h3(src).text.startswith("<Subject 1> = an arrogant young man of <Picture 1> in an expensive suit\n")


def test_music_right_after_the_cast_is_music():
    res = h3("@h3 t2va lite\nCAST\nKEEPER: an old keeper\nMUSIC: a low cello drone\nSHOT 5s\nKEEPER waits.\nSFX: x\n")
    assert res.text.endswith("non_diegetic_music: A low cello drone.") and "MUSIC" not in res.text
