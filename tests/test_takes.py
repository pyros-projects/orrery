"""Takes at the line (#173): the request for one place, and the takes in a reply."""

from orrery import takes


def test_a_request_asks_for_n_different_takes_for_its_place():
    slot = takes.request("slot", "a small object", "A fox with [this part].", n=3, steer="darker", have=["a key"])
    assert "Write 3 different takes for [this part]" in slot and "directions exactly: a small object" in slot
    assert "Steer them: darker." in slot and "- a key" in slot and slot.endswith("JSON array of 3 strings, the takes.")
    rewrite = takes.request("enhance", "make it moody", "A fox at dawn.", frames=2)
    assert rewrite.startswith("You write") and "The 2 images are frames" in rewrite and "The passage:\nA fox at dawn." in rewrite


def test_a_library_still_to_be_written_is_asked_for_as_a_run_asks_with_the_steer_beside_its_directions():
    """#272: N entries from the lines that use it, its directions, the steer; those the sheet has are not new."""
    prompt, need = takes.for_library("A fox under a __sky_kind__ sky.\nA cat.", "sky_kind", 20, steer="stormy")
    assert "__sky_kind__: 20 entries." in prompt and "Used in: A fox under a __sky_kind__ sky." in prompt
    assert "A cat" not in prompt and "Steer them: stormy" in prompt
    prompt, need = takes.for_library("under a __sky_kind__", "sky_kind", 3, directions="weather words", have=["fog"])
    assert "Directions: weather words" in prompt and "3 NEW entries in the spirit of the existing ones [\"fog\"]" in prompt
    assert takes.library_entries('{"sky_kind": ["Fog", "low cloud", "hail", "sleet", "drizzle"]}', need) == ["low cloud", "hail", "sleet"]


def test_a_library_that_exists_offers_its_roll_at_the_seed_first_then_weighted_rolls():
    """#273: the roll the annotation shows (maybe cut short) first; then draws by weight times learned weight."""
    from orrery.library import Entry, Library

    lib = Library("hair", [Entry("bob cut"), Entry("a very long braided crown with ribbons woven through"), Entry("mohawk", weight=0),
                           Entry("buzz cut"), Entry("pigtails")])
    out = takes.rolled_entries(lib, {}, 7, 3, first="a very long braided…")
    assert out[0] == "a very long braided crown with ribbons woven through" and len(out) == 3 and "mohawk" not in out
    assert out == takes.rolled_entries(lib, {}, 7, 3, first="a very long braided…")  # the same seed, the same rolls
    assert "bob cut" not in takes.rolled_entries(lib, {}, 7, 5, skip=["Bob cut"])
    unlearned = {"__hair__=pigtails": 0.0, "__hair__=buzz cut": 0.0}
    assert set(takes.rolled_entries(lib, unlearned, 1, 9)) == {"bob cut", "a very long braided crown with ribbons woven through"}


def test_the_takes_come_out_of_an_array_or_an_object_holding_one():
    assert takes.parse('["a  key", "a coin", "a key"]', 3) == ["a key", "a coin"]  # one line each, each once
    assert takes.parse('{"takes": ["x", "y", "z", "w"]}', 3) == ["x", "y", "z"]
    assert takes.parse("no json at all", 3) == [] and takes.parse('{"a": 1}', 3) == []
    assert takes.marked("a b a", "a", 1) == "a b [this part]" and takes.marked("a b", "c") is None
