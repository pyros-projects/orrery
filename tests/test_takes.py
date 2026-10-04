"""Takes at the line (#173): the request for one place, and the takes in a reply."""

from orrery import takes


def test_a_request_asks_for_n_different_takes_for_its_place():
    slot = takes.request("slot", "a small object", "A fox with [this part].", n=3, steer="darker", have=["a key"])
    assert "Write 3 different takes for [this part]" in slot and "directions exactly: a small object" in slot
    assert "Steer them: darker." in slot and "- a key" in slot and slot.endswith("JSON array of 3 strings, the takes.")
    entry = takes.request("library", "sky_kind", "under a [this part]", n=4, directions="weather words")
    assert "entry of the wildcard list __sky_kind__" in entry and "following these directions: weather words" in entry
    rewrite = takes.request("enhance", "make it moody", "A fox at dawn.", frames=2)
    assert rewrite.startswith("You write") and "The 2 images are frames" in rewrite and "The passage:\nA fox at dawn." in rewrite


def test_the_takes_come_out_of_an_array_or_an_object_holding_one():
    assert takes.parse('["a  key", "a coin", "a key"]', 3) == ["a key", "a coin"]  # one line each, each once
    assert takes.parse('{"takes": ["x", "y", "z", "w"]}', 3) == ["x", "y", "z"]
    assert takes.parse("no json at all", 3) == [] and takes.parse('{"a": 1}', 3) == []
    assert takes.marked("a b a", "a", 1) == "a b [this part]" and takes.marked("a b", "c") is None
