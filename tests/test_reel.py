"""Reels: one screenplay, one CHUNK per Motion Context clip. The head is the world and rolls
once; every segment rolls its chunk with its own seed, so a repeated chunk varies; `$x~N` is
x as it was N clips ago. `segment` (from 0) picks the clip to write."""

import re

import pytest

from orrery.h3 import compile_scene
from orrery.library import Entry, Library
from orrery.reel import ReelEnd, reel_path, split_reel

FOX = {"animal": Library("animal", [Entry("fox")])}
MANY = {"animal": Library("animal", [Entry(a) for a in ("fox", "heron", "owl", "lynx", "hare")])}

REEL = """@h3 t2va 16:9
style: live-action, cinematic
LORA: <lora:global:0.5>
$hero = __animal__

CHUNK the salon
LORA: <lora:first:1>
SHOT 5s: push in, slow
A $hero crosses a salon.
SFX: footsteps
HANDOFF: the $hero reaches the staircase

CHUNK
SHOT 4s: static
The $hero climbs the stairs.
SFX: creaking wood
SHOT 2s: cut
A landing with a tall window.
MUSIC: a slow cello line

CHUNK
SHOT 5s
A {red|blue} door opens.
SFX: a latch clicks
"""


def h3(src, seed=1, segment=0, libs=FOX):
    return compile_scene(src, seed, libs, target="h3-base", segment=segment)


def test_each_segment_writes_its_own_chunk():
    a, b = h3(REEL, segment=0), h3(REEL, segment=1)
    assert "crosses a salon" in a.text and "climbs the stairs" not in a.text
    assert "climbs the stairs" in b.text and "crosses a salon" not in b.text
    assert (a.chunks, b.chunks, b.segment) == (3, 3, 1)


def test_bindings_roll_once_for_the_whole_reel():
    for seed in range(6):
        heroes = {tuple(p.value for p in h3(REEL, seed, k, MANY).picks if p.label.startswith("$hero"))
                  for k in range(3)}
        assert len(heroes) == 1


def test_a_handoff_closes_one_chunk_and_opens_the_next():
    assert "The shot ends as the fox reaches the staircase." in h3(REEL, segment=0).text
    assert ("[Shot 1] Live-action, cinematic. The shot opens as the fox reaches the staircase. "
            "The camera holds a static shot. The fox climbs the stairs.") in h3(REEL, segment=1).text
    assert "staircase" not in h3(REEL, segment=2).text


def test_later_chunks_add_the_pinned_context_to_shot_1():
    assert h3(REEL, segment=0).scene.duration == 5
    b = h3(REEL, segment=1)
    assert b.scene.duration == pytest.approx(6 + 22 / 24)
    assert "[Shot 2] At 00:04.917, the camera cuts to a landing" in b.text
    assert h3(REEL.replace("$hero =", "context: 39\n$hero ="), segment=1).scene.duration == pytest.approx(6 + 39 / 24)
    assert h3(REEL.replace("$hero =", "context: 0\n$hero ="), segment=1).scene.duration == 6


def test_loras_are_the_global_ones_plus_the_chunk():
    assert h3(REEL, segment=0).loras == "<lora:global:0.5> <lora:first:1>"
    assert h3(REEL, segment=1).loras == "<lora:global:0.5>"
    assert "lora" not in h3(REEL, segment=0).text


def test_music_belongs_to_its_chunk():
    assert h3(REEL, segment=1).text.endswith("non_diegetic_music: A slow cello line.")
    assert h3(REEL, segment=2).text.endswith("non_diegetic_music: N/A")


def test_picks_belong_to_the_chunk_they_came_from():
    labels = lambda k: {p.label for p in h3(REEL, segment=k).picks}
    assert labels(2) == {"$hero ← __animal__", "{red|blue}"}
    assert labels(0) == {"$hero ← __animal__"}


def test_a_segment_past_the_end_is_a_clear_error():
    with pytest.raises(ValueError, match="3 clips"):
        h3(REEL, segment=3)


def test_plain_scenes_take_loras_and_ignore_the_segment():
    src = "@h3 t2va\nCAST\nMAYA: a woman\nLORA: <lora:a:1>\nSHOT 5s\nMAYA waves.\nSFX: x\n"
    r = h3(src, segment=4)
    assert (r.loras, r.chunks) == ("<lora:a:1>", 0)
    assert not [i for i in r.lint if "CAST" in i.message] and "lora" not in r.text


def test_lora_lines_keep_names_with_double_underscores():
    r = h3("@h3 t2va\nLORA: <lora:bf16__apply_to_fl2va__toward:1.00>\nSHOT 5s\nA.\nSFX: x\n")
    assert r.loras == "<lora:bf16__apply_to_fl2va__toward:1.00>"



# --- repeat and history ------------------------------------------------------------------------

LOOP = """@h3 t2va
$venue = {pool|garage|greenhouse|salt flat}
CHUNK intro
$n = {1|2|3|4|5|6|7|8|9}
SHOT 5s
Intro at the $venue, N$n.
SFX: x
HANDOFF: door $n opens
CHUNK walk repeat 3
$n = {1|2|3|4|5|6|7|8|9}
SHOT 5s
Walk at the $venue, N$n P$n~1 Q$n~2.
SFX: y
HANDOFF: door $n opens
CHUNK outro
SHOT 5s
Outro at the $venue, last P$n~1.
SFX: z
"""


def number(text, tag):
    m = re.search(rf"\b{tag}(\d)", text)
    return m and m.group(1)


def test_repeats_count_as_segments():
    assert split_reel(LOOP).segments == 5
    assert ["Intro" in h3(LOOP, segment=0).text, *("Walk at" in h3(LOOP, segment=k).text for k in (1, 2, 3)),
            "Outro" in h3(LOOP, segment=4).text] == [True] * 5
    with pytest.raises(ValueError, match="5 clips"):
        h3(LOOP, segment=5)


def test_the_world_holds_and_every_segment_rolls_its_chunk_anew():
    for seed in range(1, 6):
        texts = [h3(LOOP, seed, k).text for k in range(5)]
        assert len({re.search(r"at the (\w+ ?\w*),", t).group(1) for t in texts}) == 1
        assert len({number(t, "N") for t in texts[:4]}) > 1, seed


def test_history_looks_back_n_clips_and_clamps_at_the_first():
    for seed in range(1, 6):
        t = [h3(LOOP, seed, k).text for k in range(5)]
        n = [number(x, "N") for x in t]
        assert [number(t[k], "P") for k in (1, 2, 3)] == [n[0], n[1], n[2]]
        assert [number(t[k], "Q") for k in (1, 2, 3)] == [n[0], n[0], n[1]]
        assert number(t[4], "P") == n[3]


def test_a_repetition_opens_with_the_handoff_of_the_clip_before():
    t = [h3(LOOP, 2, k).text for k in range(4)]
    for k in (1, 2, 3):
        assert f"The shot opens as door {number(t[k - 1], 'N')} opens." in t[k]


def test_forever_repeats_without_end_and_chunks_after_it_warn():
    forever = LOOP.replace("repeat 3", "repeat forever")
    assert split_reel(forever).segments is None
    far = h3(forever, segment=57)
    assert "Walk at" in far.text and far.segment == 57
    assert any("never" in i.message for i in far.lint)
    assert h3(forever, 3, 9).text == h3(forever, 3, 9).text


def test_a_property_of_an_earlier_clip_is_read_with_its_history():
    """An endless tour: this clip opens the threshold the last one ended on ($thr~1.open)."""
    from orrery.library import Entry, Library
    libs = {"thr": Library("thr", [Entry("velvet curtains", props=(("open", "the curtains part"),)),
                                   Entry("mirrored doors", props=(("open", "the mirrored doors swing inward"),))])}
    src = ("@h3 t2va 16:9\nCHUNK the tour repeat forever\n$thr = __thr__\nSHOT 5s\n"
           "Opening: $thr~1.open. Ending before $thr.\nSFX: footsteps\n")
    for seg in (1, 2, 3):
        now = compile_scene(src, 5, libs, segment=seg).text
        before = compile_scene(src, 5, libs, segment=seg - 1).text
        ended = "velvet curtains" if "before velvet curtains" in before else "mirrored doors"
        assert ("the curtains part" if ended == "velvet curtains" else "the mirrored doors swing inward") in now


# --- SEND: frames of a clip as reference images for later clips -------------------------------

SEND_REEL = """@h3 ref2va 16:9 lite
style: live-action, cinematic
CAST
GIRL (image 1, image 3): the young woman, in a pink tracksuit

CHUNK the pose repeat 2
SHOT 5s: push in, slow
GIRL stretches on a mat.
SEND: frame 0 to image 3
SEND: frames 2, 5, 34-36 to image 4

CHUNK the walk
SHOT 4s: static
GIRL walks to the window.
"""


def ref2va(src, segment=0):
    return compile_scene(src, 1, {}, target="h3-base", segment=segment, packed=True)


def test_send_lines_belong_to_their_chunk_and_list_frames_in_order():
    from orrery.reel import Send
    reel = split_reel(SEND_REEL)
    assert reel.blocks[0].sends == [Send([[0, 0]], 3), Send([[2, 2], [5, 5], [34, 36]], 4)]
    assert not any("SEND" in line for block in reel.blocks for line in block.lines)
    assert reel.send_slots == [3, 4]


def test_a_sent_image_exists_from_the_segment_after_its_chunk_first_plays():
    reel = split_reel(SEND_REEL)
    assert reel.ready(0) == {}
    first = {3: {"segment": 0, "frames": [[0, 0]]}, 4: {"segment": 0, "frames": [[2, 2], [5, 5], [34, 36]]}}
    assert reel.ready(1) == first  # the chunk's second repetition still sends its first clip
    assert reel.ready(2) == first


def test_before_it_exists_a_sent_image_is_left_out_of_the_clip():
    before = ref2va(SEND_REEL, segment=0)
    assert before.refs == [1]
    assert "<Subject 1> = the young woman of <Picture 1>, in a pink tracksuit" in before.text
    assert "<Picture 2>" not in before.text
    after = ref2va(SEND_REEL, segment=2)
    assert after.refs == [1, 3, 4]  # image 4 is sent but named by nothing: it follows the ones the prompt uses
    assert "<Picture 1> and <Picture 2>" in after.text
    assert after.sends == {3: {"segment": 0, "frames": [[0, 0]]}, 4: {"segment": 0, "frames": [[2, 2], [5, 5], [34, 36]]}}
    assert after.send_slots == [3, 4]


def test_a_frame_anchor_on_a_sent_image_waits_for_it():
    full = SEND_REEL.replace(" lite", " full")
    later = full.replace("SHOT 4s: static", "SHOT 4s: from image 3, static")
    assert "<Picture 2> is the first frame of [Shot 1]" in ref2va(later, segment=2).text
    early = full.replace("SHOT 5s: push in, slow", "SHOT 5s: from image 3, push in, slow")
    assert "first frame" not in ref2va(early, segment=0).text


def test_a_bracket_before_its_image_exists_is_flagged():
    src = SEND_REEL.replace("GIRL stretches on a mat.", "GIRL stretches like in [image 3].")
    lint = [i.message for i in ref2va(src, segment=0).lint]
    assert any("[image 3]" in m and "SEND" in m for m in lint)


@pytest.mark.parametrize("line, words", [
    ("SEND: frames 5-2 to image 3", "5-2"),
    ("SEND: frames a, 2 to image 3", "a"),
    ("SEND: frame 0 to image 10", "1–9"),
    ("SEND: frame 0 to picture 3", "image N"),
    ("SEND: frame to image 3", "frame"),
    ("SEND: frame 0 to refmod", "refmod NAME"),
    ("SEND: every 0 frames to refmod jinx_look", "every 0 frames"),
])
def test_malformed_send_lines_are_clear_errors(line, words):
    with pytest.raises(ValueError, match=re.escape(words)):
        split_reel(SEND_REEL.replace("SEND: frame 0 to image 3", line))


def test_two_sends_to_one_image_warn_and_the_later_takes_over():
    src = SEND_REEL.replace("GIRL walks to the window.", "GIRL walks to the window.\nSEND: frame 9 to image 3")
    assert split_reel(src).ready(3)[3] == {"segment": 2, "frames": [[9, 9]]}
    lint = [i.message for i in ref2va(src, segment=2).lint]
    assert any("image 3" in m and "clip 4" in m and "(SCENE 2) takes over" in m for m in lint)


MOD_REEL = """@h3 t2va 16:9
CAST
JINX (refmod jinx_look): a young woman
CHUNK the outfit
SHOT 5s: static
JINX shows her outfit and walks out.
SEND: every 10 frames to refmod jinx_look
CHUNK the room
SHOT 5s: static
The empty room.
CHUNK the return
SHOT 5s: static
JINX slides back in.
"""


def test_frames_sent_to_a_refmod_become_it_from_the_clip_after():
    from orrery.reel import Send
    reel = split_reel(MOD_REEL)
    assert reel.blocks[0].sends == [Send([[0, -1]], None, refmod="jinx_look", step=10)]
    assert (reel.send_slots, reel.send_refmods) == ([], ["jinx_look"])
    first, _, back = (compile_scene(MOD_REEL, 1, {}, segment=s) for s in range(3))
    assert first.refmods == []  # its chunk has not played yet: nothing to bring back (and no ref2va needed)
    assert back.refmods == [{"name": "jinx_look", "member": "JINX", "strength": 1.0, "from": 0.0, "to": 1.0,
                             "sent": {"segment": 0, "frames": [[0, -1]], "step": 10}}]
    picked = split_reel(MOD_REEL.replace("every 10 frames", "frames 0, 24-48")).blocks[0].sends[0]
    assert (picked.frames, picked.step) == ([[0, 0], [24, 48]], 1)


def test_two_sends_to_one_refmod_warn_and_the_later_takes_over():
    src = MOD_REEL.replace("The empty room.", "The empty room.\nSEND: frame -1 to refmod jinx_look")
    assert split_reel(src).refmods_ready(2)["jinx_look"] == {"segment": 1, "frames": [[-1, -1]]}
    lint = [i.message for i in compile_scene(src, 1, {}, segment=2).lint]
    assert any("refmod jinx_look is filled by two SEND: lines" in m and "(SCENE 2) takes over" in m for m in lint)


def test_send_outside_a_chunk_or_outside_ref2va_is_an_error():
    head = SEND_REEL.replace("CAST\n", "SEND: frame 0 to image 5\nCAST\n")
    with pytest.raises(ValueError, match="inside a SCENE"):
        ref2va(head)
    plain = "@h3 ref2va 16:9\nSHOT 5s\nA fox.\nSEND: frame 0 to image 3\n"
    with pytest.raises(ValueError, match="inside a SCENE"):
        ref2va(plain)
    t2va = SEND_REEL.replace("@h3 ref2va 16:9 lite", "@h3 t2va 16:9")
    with pytest.raises(ValueError, match="@h3 references"):
        ref2va(t2va)


def test_without_a_cast_a_sent_image_still_reaches_the_refs():
    """ref_1 of every clip after the first is the first clip's frame 0, named in the prompt or not."""
    src = ("@h3 ref2va 2:3\nCHUNK a\nSHOT 5s\nA girl stretches.\nSEND: frame 0 to image 1\n"
           "CHUNK b\nSHOT 5s\nShe walks.\nCHUNK c\nSHOT 5s\nShe turns.\n")
    assert ref2va(src, segment=0).refs == []
    assert ref2va(src, segment=1).refs == [1] and ref2va(src, segment=2).refs == [1]
    assert "<Picture" not in ref2va(src, segment=1).text


def test_negative_frames_count_from_the_end_and_ranges_may_mix_signs():
    from orrery.reel import Send, parse_send
    assert parse_send("frame -1 to image 5") == Send([[-1, -1]], 5)
    assert parse_send("frames -24--1, 10--1, 3 to image 6") == Send([[-24, -1], [10, -1], [3, 3]], 6)
    with pytest.raises(ValueError, match="-1--5"):
        parse_send("frames -1--5 to image 6")


def test_for_segment_takes_numbers_ranges_and_a_plus():
    from orrery.reel import parse_send
    assert parse_send("frame 0 to image 5 for segment 4+").segments == [[4, None]]
    assert parse_send("frame 0 to image 5 for segments 4, 6, 7, 12").segments == [[4, 4], [6, 6], [7, 7], [12, 12]]
    assert parse_send("frame 0 to image 5 for segments 2, 4-8, 12+").segments == [[2, 2], [4, 8], [12, None]]
    assert parse_send("frame 0 to image 5").segments is None
    for bad, words in (("for segment 8-4", "8-4"), ("for segment x", '"x"'), ("for segments", "segment")):
        with pytest.raises(ValueError, match=re.escape(words)):
            parse_send(f"frame 0 to image 5 {bad}")


REANCHOR = """@h3 ref2va 16:9 lite
CAST
GIRL (image 1, image 3): the young dancer
CHUNK the old look repeat 4
SHOT 5s: static
GIRL dances.
SEND: frame 0 to image 3 for segments 1-4
CHUNK the new look
SHOT 5s: static
GIRL changes her outfit.
SEND: frame -1 to image 3 for segment 5+
CHUNK the finale repeat forever
SHOT 5s: static
GIRL bows.
"""


def test_an_image_exists_only_in_the_segments_its_send_lists():
    reel = split_reel(SEND_REEL.replace("SEND: frame 0 to image 3", "SEND: frame 0 to image 3 for segment 2+"))
    assert 3 not in reel.ready(1) and reel.ready(2)[3] == {"segment": 0, "frames": [[0, 0]]}
    picked = split_reel(SEND_REEL.replace("SEND: frame 0 to image 3", "SEND: frame 0 to image 3 for segments 1, 3"))
    assert [3 in picked.ready(t) for t in range(5)] == [False, True, False, True, False]


def test_several_sends_may_fill_one_image_in_different_segments():
    reel = split_reel(REANCHOR)
    assert reel.send_slots == [3]
    assert [reel.ready(t).get(3, {}).get("segment") for t in range(8)] == [None, 0, 0, 0, 0, 4, 4, 4]
    assert reel.ready(6)[3]["frames"] == [[-1, -1]]
    assert ref2va(REANCHOR, segment=0).refs == [1] and ref2va(REANCHOR, segment=6).refs == [1, 3]


def test_two_sends_claiming_one_segment_for_one_image_hand_over_to_the_later():
    clash = REANCHOR.replace("for segments 1-4", "for segments 1-5")
    assert [split_reel(clash).ready(t)[3]["segment"] for t in (4, 5, 6)] == [0, 4, 4]
    lint = [i.message for i in ref2va(clash, segment=5).lint]
    assert any("clip 6" in m and "(SCENE 2) takes over" in m for m in lint)
    assert not any("takes over" in i.message for i in ref2va(REANCHOR, segment=5).lint)


def test_a_listed_segment_before_the_frame_exists_is_flagged():
    src = SEND_REEL.replace("GIRL walks to the window.", "GIRL walks to the window.\nSEND: frame 0 to image 5 for segment 1+")
    lint = [i.message for i in ref2va(src, segment=0).lint]
    assert any("image 5" in m and "segment 1" in m for m in lint)


def test_a_held_image_exists_from_segment_0_within_its_for_list():
    reel = split_reel(SEND_REEL.replace("SEND: frame 0 to image 3", "SEND: frame 0 to image 3 for segment 2+"))
    assert reel.ready(0, held={3, 4}) == {4: {"held": True}}
    assert reel.ready(2, held={3})[3] == {"held": True}
    held = compile_scene(SEND_REEL, 1, {}, target="h3-base", segment=0, packed=True, held={3})
    assert held.refs == [1, 3] and "<Picture 1> and <Picture 2>" in held.text and held.sends == {3: {"held": True}}


def test_a_field_of_the_reels_head_is_the_same_in_every_clip():
    from orrery.h3 import compile_scene
    from orrery.library import Entry, Library

    libs = {"pose": Library("pose", [Entry("bend", props=(("action", "a {deep|full|slow|wide} backbend"),))])}
    reel = "@h3 t2va\n$p = __pose__\nCHUNK a repeat 4\nSHOT 5s: static\nShe holds $p.action."
    shown = {compile_scene(reel, 9, libs, segment=k).scene.shots[0].items[0].split(" holds ")[1] for k in range(4)}
    assert len(shown) == 1



# --- GOTO (docs/plan-dsl-2.md, phase 8) ------------------------------------------------------

GOTO_REEL = """@h3 t2va
CHUNK the gate
SHOT 5s: static
The keeper opens the gate.
CHUNK the stairs
SHOT 5s: tracking
The keeper climbs.
HANDOFF: the keeper reaches the landing
CHUNK the lamp
SHOT 5s: push in
The keeper lights the lamp.
HANDOFF: the beam sweeps the sea
GOTO: the stairs ×2
"""


def test_goto_loops_back_n_times_then_goes_on():
    reel = split_reel(GOTO_REEL)
    assert [b for b, _ in reel.walk()[0]] == [0, 1, 2, 1, 2, 1, 2] and reel.segments == 7
    assert split_reel(GOTO_REEL.replace("GOTO: the stairs ×2", "GOTO: 2 x1")).segments == 5  # a number, an x
    endless = split_reel(GOTO_REEL.replace(" ×2", ""))
    assert endless.segments is None and [b for b, _ in endless.walk(upto=6)[0]] == [0, 1, 2, 1, 2, 1]
    with pytest.raises(ValueError, match="no SCENE is called 'the cellar'"):
        split_reel(GOTO_REEL.replace("the stairs ×2", "the cellar"))


FILM_WORDS = {"@h3 t2va": "@h3 text", "CHUNK": "SCENE", "HANDOFF:": "END ON:", "GOTO:": "CUT TO:"}


def film(src: str) -> str:
    for old, new in FILM_WORDS.items():
        src = src.replace(old, new)
    return src


def test_the_film_words_compile_what_the_earlier_words_compile():
    for reel in (REEL, GOTO_REEL):
        assert split_reel(film(reel)).walk() == split_reel(reel).walk()
        for segment in range(3 if reel is REEL else 7):
            then, now = (compile_scene(src, 5, MANY, target="h3-base", segment=segment) for src in (reel, film(reel)))
            assert (now.text, now.picks, now.lint) == (then.text, then.picks, then.lint)


@pytest.mark.parametrize("then, now", [("CHUNK the turn repeat 3", "SCENE the turn ×3"),
                                       ("CHUNK the turn repeat 3", "SCENE the turn x3"),
                                       ("CHUNK the turn repeat forever", "SCENE the turn forever"),
                                       ("CHUNK repeat 2", "SCENE ×2")])
def test_a_scene_repeats_n_times_or_forever(then, now):
    blocks = [split_reel(f"@h3 t2va\n{head}\nSHOT 5s\nA fox.\n").blocks for head in (then, now)]
    assert [(b.title, b.repeat) for b in blocks[1]] == [(b.title, b.repeat) for b in blocks[0]]
    assert [(b.title, b.repeat) for b in split_reel("@h3 text\nSCENE the 4x4 room\nSHOT 5s\nA fox.\n").blocks] == [
        ("the 4x4 room", 1)]  # an x inside the title is no repeat


def test_a_jump_opens_on_the_handoff_before_it_and_its_line_stays_out_of_the_prose():
    clip = compile_scene(GOTO_REEL, 1, {}, target="h3-base", segment=3)  # the stairs again, after the lamp
    assert "The keeper climbs" in clip.text and "beam sweeps the sea" in clip.text and "GOTO" not in clip.text
    with pytest.raises(ReelEnd):
        compile_scene(GOTO_REEL, 1, {}, segment=7)


def test_a_goto_that_waits_on_a_roll_makes_each_seed_its_own_story():
    story = GOTO_REEL.replace("CHUNK the lamp\n", "CHUNK the lamp\n$w = {rain|clear}\n").replace(
        "GOTO: the stairs ×2", "? $w[rain]: GOTO: the stairs ×3")
    reel = split_reel(story)
    assert reel.jumps_on_rolls and reel.segments is None
    lengths = {len(reel_path(reel, seed, {}, None)[0]) for seed in range(40)}
    assert lengths <= {3, 5, 7, 9} and len(lengths) > 1  # every rain sends the keeper back, at most three times
    seed = next(s for s in range(40) if len(reel_path(reel, s, {}, None)[0]) == 5)
    assert compile_scene(story, seed, {}, segment=4).text and pytest.raises(ReelEnd, compile_scene, story, seed, {}, segment=5)


def test_several_gotos_the_first_that_holds_and_has_jumps_left():
    reel = split_reel(GOTO_REEL.replace("GOTO: the stairs ×2", "GOTO: the gate ×1\nGOTO: the stairs ×1"))
    assert [b for b, _ in reel.walk()[0]] == [0, 1, 2, 0, 1, 2, 1, 2]


def test_a_chunk_every_goto_jumps_past_is_flagged():
    src = GOTO_REEL.replace("GOTO: the stairs ×2", "GOTO: the gate") + "CHUNK the cellar\nSHOT 5s: static\nDark.\n"
    lint = [i.message for i in compile_scene(src, 1, {}, segment=0).lint]
    assert any("SCENE 4" in m and "never plays" in m for m in lint)


LEAVES = """@h3 ref2va 2:3
CAST
EMMA (refmod emma_canon): a young woman in a red coat
GARDEN (global): a small walled garden
CHUNK
SHOT 5s: static
EMMA waves and walks out of the frame.
HANDOFF: only the room is left
CHUNK
SHOT 5s: static
Nothing happens in the empty room.
HANDOFF: only the room is left
CHUNK
SHOT 5s: static
EMMA slides back into the frame, laughing.
"""


def test_a_chunk_without_a_member_leaves_its_definition_and_its_refmod_out():
    clips = [ref2va(LEAVES, segment=s) for s in range(3)]
    assert ["a young woman in a red coat" in c.text for c in clips] == [True, False, True]
    assert [[m["name"] for m in c.refmods] for c in clips] == [["emma_canon"], [], ["emma_canon"]]
    assert all("a small walled garden" in c.text for c in clips)  # global: in every clip


def test_a_sent_image_of_a_member_not_in_the_chunk_stays_out():
    src = LEAVES.replace("EMMA (refmod emma_canon)", "EMMA (image 3)").replace(
        "HANDOFF: only the room is left\nCHUNK\nSHOT 5s: static\nNothing", "HANDOFF: only the room is left\nSEND: frame 0 to image 3\nCHUNK\nSHOT 5s: static\nNothing", 1)
    clips = [ref2va(src, segment=s) for s in range(3)]
    assert [sorted(c.sends) for c in clips] == [[], [], [3]] and [c.refs for c in clips] == [[], [], [3]]


def test_a_sent_image_stays_out_where_the_chunks_cast_redefines_its_member_without_it():
    src = LEAVES.replace("EMMA (refmod emma_canon)", "EMMA (refmod emma_canon, image 3)").replace(
        "HANDOFF: only the room is left\nCHUNK", "HANDOFF: only the room is left\nSEND: frame 0 to image 3\n"
        "SEND: frame 0 to image 5\nCHUNK", 1).replace(
        "CHUNK\nSHOT 5s: static\nEMMA slides back",
        "CHUNK\nCAST\nEMMA (refmod emma_canon): a young woman in a red coat\nSHOT 5s: static\nEMMA slides back")
    back = ref2va(src, segment=2)
    assert sorted(back.sends) == [5] and back.refs == [5]  # image 3 is EMMA's no more; image 5 is nobody's: it goes along
    assert ref2va(src.replace("CAST\nEMMA (refmod emma_canon): a young woman in a red coat\n", ""), segment=2).refs == [3, 5]


def test_a_chunks_own_cast_replaces_the_member_for_that_clip():
    src = LEAVES.replace("CHUNK\nSHOT 5s: static\nEMMA slides back", (
        "CHUNK\nCAST\nEMMA (refmod emma_canon at 0.3, image 1 at 0.5): a young woman in a red coat\n"
        "SHOT 5s: static\nEMMA slides back"))
    first, _, back = (ref2va(src, segment=s) for s in range(3))
    assert [m["strength"] for m in first.refmods] == [1.0] and [m["strength"] for m in back.refmods] == [0.3]
    assert back.scene.cast[0].name == "EMMA"  # in her place: still <Subject 1>
    assert back.images == [{"ref": 1, "image": 1, "member": "EMMA", "strength": 0.5, "from": 0.0, "to": 1.0}]
    assert not any("twice" in i.message for i in back.lint)



def test_set_lines_turn_the_dials_in_the_head_and_per_chunk():
    src = LEAVES.replace("CAST\nEMMA (refmod emma_canon)", "SET: emma_canon(0.8)\nCAST\nEMMA (refmod emma_canon_Video, image 1)").replace(
        "EMMA slides back", "SET: image_1(0.5,0.35)\nSET: emma_canon_Video(0.4, 20%)\nEMMA slides back")
    first, _, back = (ref2va(src, segment=s) for s in range(3))
    assert [(m["strength"], m["from"]) for m in first.refmods] == [(0.8, 0.0)] and first.images == []
    assert [(m["strength"], m["from"]) for m in back.refmods] == [(0.4, 0.2)]
    assert back.images == [{"ref": 1, "image": 1, "member": "EMMA", "strength": 0.5, "from": 0.35, "to": 1.0}]
    assert "SET" not in back.text  # never prose


def test_a_picture_at_0_leaves_the_clip_so_not_even_the_text_encoder_sees_it():
    # Reference to Video shows its pictures to the text encoder too: at 0 Orrery Refs must not hand it on
    sent = LEAVES.replace("EMMA (refmod emma_canon)", "EMMA (refmod emma_canon, image 3)").replace(
        "HANDOFF: only the room is left\nCHUNK", "HANDOFF: only the room is left\nSEND: frame 0 to image 3\nCHUNK", 1)
    assert ref2va(sent, segment=2).refs == [3]
    back = ref2va(sent.replace("EMMA slides back", "SET: image_3(0)\nEMMA slides back"), segment=2)
    assert back.refs == [] and back.sends == {} and back.images == [] and "<Picture" not in back.text
    assert [m["name"] for m in back.refmods] == ["emma_canon"]  # the RefMod stays
    assert ref2va(sent.replace("image 3)", "image 3 at 0)"), segment=2).refs == []  # the CAST's own dial
    wired = ref2va(LEAVES.replace("EMMA (refmod emma_canon)", "EMMA (image 1)").replace(
        "EMMA slides back", "SET: image_1(0)\nEMMA slides back"), segment=2)
    assert wired.refs == [] and "<Picture" not in wired.text


def test_a_dial_can_stop_before_sampling_does():
    src = LEAVES.replace("EMMA (refmod emma_canon)", "EMMA (refmod emma_canon from 10% to 50%, image 1 to 30%)").replace(
        "EMMA slides back", "SET: emma_canon(1, 0%, 20%)\nEMMA slides back")
    first, _, back = (ref2va(src, segment=s) for s in range(3))
    assert [(m["from"], m["to"]) for m in first.refmods] == [(0.1, 0.5)]
    assert [(m["from"], m["to"]) for m in back.refmods] == [(0.0, 0.2)]  # SET wins over the CAST
    assert [(p["from"], p["to"]) for p in back.images] == [(0.0, 0.3)]
    head = ref2va(LEAVES.replace("CAST\n", "refmods: to 40%\nCAST\n", 1), segment=0)
    assert [m["to"] for m in head.refmods] == [0.4]
    wrong = ref2va(LEAVES.replace("EMMA (refmod emma_canon)", "EMMA (refmod emma_canon from 50% to 20%)"), segment=0)
    assert any("stops before it starts" in i.message for i in wrong.lint) and wrong.refmods[0]["to"] == 1.0


def test_a_set_line_written_wrong_or_naming_nothing_is_lint():
    lint = lambda line: [i.message for i in ref2va(LEAVES.replace("EMMA slides back", f"{line}\nEMMA slides back"), segment=2).lint]
    assert any("is not name(strength, start)" in m for m in lint("SET: image_1 at 0.5"))
    assert any("SET: image_4 is not a picture or a RefMod of the CAST" in m for m in lint("SET: image_4(0.5)"))
    assert any("takes numbers" in m for m in lint("SET: emma_canon(half)"))
