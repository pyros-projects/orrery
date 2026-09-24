"""Reels: one screenplay, one chunk per Motion Context clip. The whole reel expands once, so
bindings hold across clips; `segment` (Load Latent's clip_index) picks the chunk to write."""

import pytest

from orrery.h3 import compile_scene
from orrery.library import Entry, Library

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
    with pytest.raises(ValueError, match="3 chunks"):
        h3(REEL, segment=3)


def test_plain_scenes_take_loras_and_ignore_the_segment():
    src = "@h3 t2va\nCAST\nMAYA: a woman\nLORA: <lora:a:1>\nSHOT 5s\nMAYA waves.\nSFX: x\n"
    r = h3(src, segment=4)
    assert (r.loras, r.chunks) == ("<lora:a:1>", 0)
    assert not [i for i in r.lint if "CAST" in i.message] and "lora" not in r.text
