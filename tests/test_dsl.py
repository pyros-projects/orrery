from collections import Counter

import pytest

from orrery.dsl import MissingLibrary, bindings, expand, expand_batch, override
from orrery.library import Entry, Library

LIBS = {
    "animal": Library("animal", [
        Entry("fox"), Entry("heron"), Entry("owl"),
        Entry("lynx", ("feline",)), Entry("ocelot", ("feline",)),
    ]),
    "style": Library("style", [Entry("linocut"), Entry("gouache"), Entry("cyanotype")]),
}


def test_same_seed_gives_same_text_and_picks():
    a = expand("a __animal__ in __style__", 5, LIBS)
    b = expand("a __animal__ in __style__", 5, LIBS)
    assert (a.text, a.picks) == (b.text, b.picks)


def test_library_pick_is_recorded_with_label_value_and_weight_key():
    e = expand("a __animal__", 5, LIBS)
    [pick] = e.picks
    assert pick.label == "__animal__"
    assert e.text == "a " + pick.value
    assert pick.keys == ("__animal__=" + pick.value,)


def test_seeds_explore_the_library():
    values = {expand("__animal__", s, LIBS).text for s in range(200)}
    assert values == {"fox", "heron", "owl", "lynx", "ocelot"}


def test_inline_choice_is_recorded_under_its_family():
    e = expand("{misty|frozen} forest", 3, LIBS)
    [pick] = e.picks
    assert pick.label == "{misty|frozen}"
    assert pick.value in ("misty", "frozen")
    assert e.text == pick.value + " forest"


def test_inline_static_weight_shifts_distribution():
    c = Counter(expand("{a|b:3}", s, LIBS).text for s in range(4000))
    assert 0.70 < c["b"] / 4000 < 0.80


def test_learned_weights_shift_distribution():
    w = {"__animal__=owl": 20.0}
    c = Counter(expand("__animal__", s, LIBS, weights=w).text for s in range(2000))
    assert c["owl"] / 2000 > 0.75


def test_binding_is_expanded_once_and_reused():
    e = expand("$hero = __animal__\n$hero meets $hero", 9, LIBS)
    hero = e.picks[0].value
    assert e.text == f"{hero} meets {hero}"
    assert e.picks[0].label == "$hero ← __animal__"


def test_multi_pick_draws_distinct_values():
    for s in range(50):
        values = expand("{2$$__style__}", s, LIBS).text.split(", ")
        assert len(values) == 2 and len(set(values)) == 2


def test_range_multi_pick_from_inline_options():
    counts = {len(expand("{1-2$$a|b|c}", s, LIBS).text.split(", ")) for s in range(100)}
    assert counts == {1, 2}


def test_nested_braces_resolve_inside_out():
    assert {expand("{a|{b|c}}", s, LIBS).text for s in range(200)} == {"a", "b", "c"}


def test_tag_filter_picks_only_tagged_entries():
    values = {expand("__animal[feline]__", s, LIBS).text for s in range(200)}
    assert values == {"lynx", "ocelot"}


def test_missing_library_names_the_library():
    with pytest.raises(MissingLibrary) as err:
        expand("a __weather__ day", 1, LIBS)
    assert err.value.name == "weather"


def test_enhance_line_is_recorded_not_inlined():
    e = expand("a __animal__\n> moody, cinematic", 1, LIBS)
    assert e.enhance == "moody, cinematic"
    assert "moody" not in e.text
    assert e.picks[-1].label == "> enhance"


def test_params_line_is_parsed():
    e = expand("a fox\n: x8 seed=100 w1216 h832", 1, LIBS)
    assert (e.params.count, e.params.seed, e.params.width, e.params.height) == (8, 100, 1216, 832)
    assert e.text == "a fox"


def test_body_lines_join_with_a_space():
    assert expand("a fox\nin snow", 1, LIBS).text == "a fox in snow"


def test_batch_uses_consecutive_seeds():
    batch = expand_batch("__animal__", 10, 3, LIBS)
    assert [e.seed for e in batch] == [10, 11, 12]
    assert batch[1].text == expand("__animal__", 11, LIBS).text


def test_articles_agree_with_the_picked_word():
    libs = {"c": Library("c", [Entry("axolotl")]), "d": Library("d", [Entry("fox")])}
    assert expand("a __c__ and an __d__", 1, libs).text == "an axolotl and a fox"
    assert expand("A __c__ sleeps", 1, libs).text == "An axolotl sleeps"


def test_article_exceptions():
    libs = {"u": Library("u", [Entry("unicorn")]), "h": Library("h", [Entry("hour-long nap")])}
    assert expand("a __u__, a __h__", 1, libs).text == "a unicorn, an hour-long nap"


# --- dials: a template's bindings are its parameters ------------------------------------------

def test_bindings_list_names_and_defaults_in_order():
    assert bindings("$a = x\n  $b = {y|z}\ntext $a") == [("a", "x"), ("b", "{y|z}")]


def test_override_replaces_a_binding_and_keeps_everything_else():
    t = "$hero = __animal__\n  $place = {forest|city}\n$hero in the $place"
    out = override(t, {"hero": "owl"})
    assert out == "$hero = owl\n  $place = {forest|city}\n$hero in the $place"
    assert expand(out, 1, LIBS).text.startswith("owl in the ")


def test_override_skips_empty_values_accepts_a_dollar_and_dsl():
    t = "$hero = __animal__\n$hero"
    assert override(t, {"hero": "  "}) == t
    assert override(t, {"$hero": "__animal[feline]__"}) == "$hero = __animal[feline]__\n$hero"
    assert expand(override(t, {"hero": "__animal[feline]__"}), 3, LIBS).text in ("lynx", "ocelot")
