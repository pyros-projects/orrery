"""Deterministic randomness that stays stable across Python versions.

Picks must be reproducible forever: the same template, libraries, weights and
seed always give the same result. `random.Random` and `random.choices` do not
promise that across versions, so orrery carries its own small PRNG
(mulberry32) and its own weighted pick.
"""

from collections.abc import Sequence

_MASK = 0xFFFFFFFF


class Rng:
    def __init__(self, seed: int) -> None:
        self._state = (seed * 2654435761) & _MASK

    def random(self) -> float:
        self._state = (self._state + 0x6D2B79F5) & _MASK
        t = self._state
        t = _imul(t ^ (t >> 15), t | 1)
        t = (t + _imul(t ^ (t >> 7), t | 61)) & _MASK ^ t
        return ((t ^ (t >> 14)) & _MASK) / 4294967296


def _imul(a: int, b: int) -> int:
    return (a * b) & _MASK


def weighted_pick(weights: Sequence[float], rng: Rng) -> int:
    """Return the index of one item, chosen with probability proportional to its weight."""
    total = sum(weights)
    if total <= 0:
        raise ValueError("weighted_pick needs at least one positive weight")
    x = rng.random() * total
    for i, w in enumerate(weights):
        if w <= 0:
            continue
        x -= w
        if x < 0:
            return i
    return max(i for i, w in enumerate(weights) if w > 0)
