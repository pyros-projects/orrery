"""Reels: one screenplay, one CHUNK per Motion Context clip. The head is the world and rolls
once; every segment rolls its chunk with its own seed, so a repeated chunk varies; `$x~N` is
x as it was N clips ago. `segment` (from 0) picks the clip to write."""

import re

import pytest

from orrery.h3 import compile_scene
from orrery.library import Entry, Library
from orrery.reel import split_reel

FOX = {"animal": Library("animal", [Entry("fox")])}
MANY = {"animal": Library("animal", [Entry(a) for a in ("fox", "heron", "owl", "lynx", "hare")])}

REEL = """@h3 t2va 16:9
style: live-action, cinematic
LORA: <lora:global:0.5>
$hero = __animal__

CHUNK the salon
LORA: <lora:first:1>
SHOT 5s | push in, slow
A $hero crosses a salon.
SFX: footsteps
HANDOFF: the $hero reaches the staircase

CHUNK
SHOT 4s | static
The $hero climbs the stairs.
SFX: creaking wood
SHOT 2s | cut
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
    with pytest.raises(ValueError, match="3 segments"):
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
    with pytest.raises(ValueError, match="5 segments"):
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
