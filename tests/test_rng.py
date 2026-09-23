import pytest

from orrery.rng import Rng, weighted_pick


def test_same_seed_gives_same_sequence():
    a, b = Rng(42), Rng(42)
    assert [a.random() for _ in range(5)] == [b.random() for _ in range(5)]


def test_different_seeds_give_different_sequences():
    assert [Rng(1).random() for _ in range(3)] != [Rng(2).random() for _ in range(3)]


def test_values_are_in_unit_interval():
    rng = Rng(7)
    assert all(0.0 <= rng.random() < 1.0 for _ in range(1000))


def test_weighted_pick_follows_weights():
    rng = Rng(123)
    counts = [0, 0]
    for _ in range(20000):
        counts[weighted_pick([1.0, 3.0], rng)] += 1
    assert 0.22 < counts[0] / 20000 < 0.28


def test_weighted_pick_never_picks_zero_weight():
    rng = Rng(5)
    assert all(weighted_pick([0.0, 1.0, 0.0], rng) == 1 for _ in range(500))


def test_weighted_pick_rejects_all_zero_weights():
    with pytest.raises(ValueError):
        weighted_pick([0.0, 0.0], Rng(1))
