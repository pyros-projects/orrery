"""Anchors: the frames Orrery Refs last fetched for each sent image, kept in the orrery home."""
import numpy as np

from orrery import anchors
from orrery.home import Home


def test_anchors_round_trip_per_image_and_a_new_one_replaces_the_old(tmp_path):
    h = Home(tmp_path)
    assert anchors.stored(h) == set() and anchors.load(h, 3) is None
    frames = np.zeros((2, 8, 12, 3), dtype=np.float32)
    frames[1, ..., 1] = 1.0
    anchors.save(h, 3, frames)
    back = anchors.load(h, 3)
    assert back.shape == (2, 8, 12, 3) and back[1, 0, 0, 1] == 1.0 and back[0].max() == 0.0
    anchors.save(h, 3, frames[:1])
    assert anchors.load(h, 3).shape == (1, 8, 12, 3)
    anchors.save(h, 5, frames)
    assert anchors.stored(h) == {3, 5}
