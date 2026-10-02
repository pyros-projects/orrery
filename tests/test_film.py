"""Orrery Film's store: one take per segment of a reel, the tail the next segment continues from,
and the film of them all, in the shape Chain Video keeps, so the readers take either."""

import json
import os

import av
import numpy as np
import pytest

from orrery import chain, film
from orrery.continuum.masked import Tail

SR = 48000


def frames(n, w=64, h=48, shade=0):
    out = np.zeros((n, h, w, 3), dtype=np.uint8)
    out[..., 0] = shade
    out[..., 1] = (np.arange(n) * 4 % 256)[:, None, None]
    return out


def tail(fill=0.0):
    return Tail(np.full((1, 24, 7, 3, 4), fill, np.float32), np.full((1, 32, 2, 37), fill, np.float32), 0.25)


def take(out, segment, n=24, w=64, fill=0.0):
    sound = np.sin(np.linspace(0, 400, round(n / 24 * SR), dtype=np.float32))[None].repeat(2, 0) * 0.1
    return film.save_take(out, "h3_context", segment, frames(n, w=w, shade=40 * segment), sound, SR, tail(fill),
                          {"seed": 7})


def active_run(out):
    root = out / "h3_context" / film.STORE
    return root / json.loads((root / "active.json").read_text())["run"]


def decoded(path):
    with av.open(str(path)) as c:
        count = sum(1 for _ in c.decode(c.streams.video[0]))
    with av.open(str(path)) as c:
        samples = sum(f.samples for f in c.decode(c.streams.audio[0]))
    return count, samples


def test_a_reel_keeps_one_take_per_segment_and_a_film_of_them_all(tmp_path):
    take(tmp_path, 0, n=24)
    t1 = take(tmp_path, 1, n=48)
    listed = chain.listing(tmp_path, "h3_context")
    assert (listed["width"], listed["height"]) == (64, 48)
    assert [(c["segment"], c["frames"]) for c in listed["clips"]] == [(0, 24), (1, 48)]
    assert chain.clip_file(tmp_path, "h3_context", 1) == t1 / "video.mp4"
    assert json.loads((t1 / "meta.json").read_text())["seed"] == 7
    count, samples = decoded(active_run(tmp_path) / "film.mp4")
    assert count == 72 and abs(samples - 3 * SR) <= 2048  # AAC pads a frame or two
    assert decoded(t1 / "video.mp4")[0] == 48


def test_rendering_a_segment_again_drops_the_ones_after_it(tmp_path):
    first = [take(tmp_path, s) for s in range(3)]
    again = take(tmp_path, 1, n=41)
    assert [(c["segment"], c["frames"]) for c in chain.listing(tmp_path, "h3_context")["clips"]] == [(0, 24), (1, 41)]
    assert again != first[1] and first[1].is_dir() and first[2].is_dir()  # older takes stay on disk
    assert decoded(active_run(tmp_path) / "film.mp4")[0] == 65


def test_segment_0_starts_a_new_run(tmp_path):
    take(tmp_path, 0)
    take(tmp_path, 1)
    before = active_run(tmp_path)
    take(tmp_path, 0, n=30)
    assert active_run(tmp_path) != before and before.is_dir()
    assert [c["frames"] for c in chain.listing(tmp_path, "h3_context")["clips"]] == [30]


def test_a_segment_continues_only_the_one_before_it(tmp_path):
    with pytest.raises(film.FilmError, match="segment 0"):
        take(tmp_path, 1)
    take(tmp_path, 0)
    with pytest.raises(film.FilmError, match="segment 1"):
        film.previous_tail(tmp_path, "h3_context", 2)
    with pytest.raises(film.FilmError, match="64×48"):
        take(tmp_path, 1, w=96)


def test_the_tail_comes_back_as_it_was_stored(tmp_path):
    take(tmp_path, 0, fill=0.5)
    back = film.previous_tail(tmp_path, "h3_context", 1)
    assert back.video.shape == (1, 24, 7, 3, 4) and (back.video == 0.5).all()
    assert back.audio.shape == (1, 32, 2, 37) and back.grid_offset == 0.25


def test_the_readers_follow_the_store_written_last(tmp_path):
    ours = take(tmp_path, 0)
    theirs = tmp_path / "h3_context" / "chain_video" / "run_x"
    (theirs / "clip_00001_x").mkdir(parents=True)
    (theirs / "clip_00001_x" / "video.mp4").write_bytes((ours / "video.mp4").read_bytes())
    (theirs / "clips.json").write_text(json.dumps({"settings": [64, 48, "24", SR, 2],
                                                   "clips": [{"folder": "clip_00001_x", "frames": 24}]}))
    (theirs.parent / "active.json").write_text(json.dumps({"run": "run_x"}))
    clips_json = active_run(tmp_path) / "clips.json"
    os.utime(clips_json, (1, 1))
    assert chain.clip_file(tmp_path, "h3_context", 0) == theirs / "clip_00001_x" / "video.mp4"
    os.utime(theirs / "clips.json", (0, 0))
    os.utime(clips_json, (5, 5))
    assert chain.clip_file(tmp_path, "h3_context", 0) == ours / "video.mp4"
