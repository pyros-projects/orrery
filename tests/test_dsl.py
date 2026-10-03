from collections import Counter

import pytest

from orrery.dsl import MissingLibrary, bindings, expand, expand_batch, override, wanted_libraries
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
    assert e.text in ("a " + pick.value, "an " + pick.value)  # a/an follows the pick
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
    t = "$hero = {owl|fox}\n  $place = {forest|city}\n$hero in the $place"
    out = override(t, {"hero": "a raven"})
    assert out == "$hero = a raven\n  $place = {forest|city}\n$hero in the $place"
    assert expand(out, 1, LIBS).text.startswith("a raven in the ")


def test_override_skips_empty_values_accepts_a_dollar_and_dsl():
    t = "$hero = {owl|fox}\n$hero"
    assert override(t, {"hero": "  "}) == t
    assert override(t, {"$hero": "__animal[feline]__"}) == "$hero = __animal[feline]__\n$hero"
    assert expand(override("$hero = __animal__\n$hero", {"hero": "__animal[feline]__"}), 3, LIBS).text in ("lynx", "ocelot")


def test_a_dial_set_to_an_entry_keeps_what_the_entry_carries():
    """#122: picking an entry in a dial's list keeps its properties and tags, and records the pick."""
    t = "$w = __weather__\nA street in $w; $w.sfx.\nIF $w[kind=rain]: Umbrellas."
    for s in range(5):
        x = expand(override(t, {"w": "summer rain"}), s, WEATHER)
        assert x.text == "A street in summer rain; rain drums on a tin roof. Umbrellas."
        assert [(p.label, p.value) for p in x.picks] == [("$w ← __weather__", "summer rain")]
    other = expand(override(t, {"w": "fog over the {river|harbour}"}), 1, WEATHER).text  # no entry: rolls as written
    assert other.startswith("A street in fog over the ") and other.endswith("; .")
    assert override("$w = __weather__(cold ones)", {"w": "summer rain"}).endswith("__(cold ones)")  # directions stay


# --- lora tags are opaque: LoRA file names may contain __ -------------------------------------

def test_lora_tags_are_not_expanded():
    e = expand("<lora:bf16__apply_to_fl2va__toward:1.00> a __animal__", 1, LIBS)
    assert e.text.startswith("<lora:bf16__apply_to_fl2va__toward:1.00> a")
    assert [p.label for p in e.picks] == ["__animal__"]


def test_a_choice_between_lora_tags_records_the_real_tags():
    e = expand("{<lora:a__b__:1.00>|<lora:c:0.50>}", 2, LIBS)
    [pick] = e.picks
    assert e.text in ("<lora:a__b__:1.00>", "<lora:c:0.50>") and pick.value == e.text
    assert pick.label == "{<lora:a__b__:1.00>|<lora:c:0.50>}" and pick.keys == (f"{pick.label}={e.text}",)



# --- history: $x~N ---------------------------------------------------------------------------

def test_history_asks_the_callback_and_falls_back_to_the_current_value():
    from orrery.dsl import Expander
    ex = Expander(1, LIBS)
    ex.bind("hero", "owl")
    assert ex.expr("$hero and $hero~1") == "owl and owl"
    ex.history = lambda name, back: {("hero", 1): "fox", ("hero", 2): "heron"}.get((name, back))
    assert ex.expr("$hero, $hero~1, $hero~2, $gone~1") == "owl, fox, heron, $gone~1"


# --- __name:N__ asks for at least N entries; expansion ignores the number -----------------------

def test_a_minimum_count_expands_like_the_plain_library():
    e = expand("a __animal:30__ in __style[x]:5__", 1, {**LIBS, "style": Library("style", [Entry("ink", ("x",))])})
    assert [p.label for p in e.picks] == ["__animal__", "__style[x]__"] and e.text.endswith(" in ink")


def test_wanted_libraries_with_their_minimum_and_context():
    from orrery.dsl import wanted_libraries
    t = "$a = __animal__\na __shoes:20__ on <lora:x__skip__y:1> __animal:5__\nnothing here"
    assert wanted_libraries(t) == {"animal": 5, "shoes": 20}


def test_directions_after_a_library_are_for_the_model_and_left_out():
    from orrery.dsl import library_directions
    e = expand("a __animal__(small ones only) here and __style:4__(inks)", 1, LIBS)
    assert "(" not in e.text and " here and " in e.text
    assert library_directions("__film__(30 words) and __film__ and __x:3__(bright)") == {"film": "30 words", "x": "bright"}


def test_libraries_in_folders_expand_and_are_wanted():
    from orrery.dsl import library_directions
    libs = {**LIBS, "film/genre": Library("film/genre", [Entry("noir")])}
    e = expand("a __film/genre__ film", 1, libs)
    assert e.text == "a noir film" and e.picks[0].label == "__film/genre__"
    assert wanted_libraries("__film/genre:5__ and __film/new_one__(dark)") == {"film/genre": 5, "film/new_one": 0}
    assert library_directions("__film/new_one__(dark)") == {"film/new_one": "dark"}


def _libs(**lists):
    return {name.replace("__", "/"): Library(name.replace("__", "/"), [Entry(v) for v in values])
            for name, values in lists.items()}


EIGHTIES = _libs(**{
    "80s__Women__80s_clothes": [
        "__80s/Women/80s_sports__",
        ("{|__80s/colors/80s_colors__ }__80s/Women/80s_shirts__, {|__80s/colors/80s_colors__ }"
         "{__80s/Women/80s_skirts__|__80s/Women/80s_pants__}"),
    ],
    "80s__Women__80s_sports": ["leg warmers and a leotard"],
    "80s__Women__80s_shirts": ["off-shoulder sweatshirt"],
    "80s__Women__80s_skirts": ["ra-ra skirt"],
    "80s__Women__80s_pants": ["acid-wash jeans"],
    "80s__colors__80s_colors": ["neon pink"],
})


def test_an_entry_is_a_template_itself_as_in_dynamic_prompts():
    seen = {expand("a woman in __80s/Women/80s_clothes__", seed, EIGHTIES).text for seed in range(60)}
    assert "a woman in leg warmers and a leotard" in seen
    assert "a woman in neon pink off-shoulder sweatshirt, neon pink ra-ra skirt" in seen
    assert "a woman in off-shoulder sweatshirt, acid-wash jeans" in seen
    assert not any("__" in s or "{" in s or "  " in s for s in seen)


def test_the_picks_record_every_level():
    labels = {p.label for p in expand("__80s/Women/80s_clothes__", 1, EIGHTIES).picks}
    assert "__80s/Women/80s_clothes__" in labels
    assert labels & {"__80s/Women/80s_sports__", "__80s/Women/80s_shirts__"}


def test_an_empty_option_keeps_the_spaces_of_the_others():
    """`{|red }car`: the optional-word idiom; everywhere else options are trimmed as before."""
    assert {expand("{|red }car", s, {}).text for s in range(20)} == {"car", "red car"}
    assert {expand("x {a | b} y", s, {}).text for s in range(20)} == {"x a y", "x b y"}


def test_a_library_that_comes_back_to_itself_is_an_error():
    libs = _libs(a=["__b__"], b=["__a__"])
    with pytest.raises(ValueError, match="a → b → a"):
        expand("__a__", 1, libs)


def test_a_missing_library_inside_an_entry_names_where_it_is_used():
    with pytest.raises(ValueError, match=r"__nope__.*__outfit__"):
        expand("__outfit__", 1, _libs(outfit=["__nope__ shoes"]))


def test_several_picks_from_a_library_are_expanded_too():
    text = expand("{2$$__outfit__}", 1, _libs(outfit=["{red|red} hat", "__shoe__"], shoe=["boots"])).text
    assert sorted(text.split(", ")) == ["boots", "red hat"]


def test_an_entry_comes_out_trimmed_whatever_its_braces_chose():
    libs = _libs(hair=["{|red} perm{|, and a clip}"])
    assert {expand("a __hair__.", s, libs).text for s in range(40)} == {
        "a perm.", "a red perm.", "a perm, and a clip.", "a red perm, and a clip."}


PEOPLE = {"people": Library("people", [
    Entry("Mara", props=(("gender", "female"), ("age", "30s"))),
    Entry("Ines", ("pilot",), props=(("gender", "Female"), ("age", "60s"))),
    Entry("Tomas", props=(("gender", "male"), ("age", "30s"))),
])}


def test_properties_filter_the_entries_a_pick_draws_from():
    seen = {expand("__people#gender:female__", s, PEOPLE).text for s in range(30)}
    assert seen == {"Mara", "Ines"}  # values match whatever their case
    assert {expand("__people#gender:female#age:30s__", s, PEOPLE).text for s in range(10)} == {"Mara"}


def test_properties_combine_with_tags_and_counts():
    assert expand("__people[pilot]#gender:female:2__", 1, PEOPLE).text == "Ines"


def test_the_pick_label_names_the_filter():
    assert expand("__people#age:60s__", 1, PEOPLE).picks[0].label == "__people#age:60s__"


def test_a_filter_nothing_matches_says_so():
    with pytest.raises(ValueError, match=r"__people#gender:robot__ matches no entry"):
        expand("__people#gender:robot__", 1, PEOPLE)


def test_a_filtered_library_is_still_wanted_by_its_name():
    assert wanted_libraries("__people#gender:female:3__(tall ones)") == {"people": 3}


def test_directions_stay_out_of_pick_labels_and_learned_keys():
    """Editing the directions must not rename a choice, or its learned weights would be lost."""
    libs = _libs(a=["apple"], b=["pear"])
    picks = expand("{__a__(round fruit)|__b__(long fruit)}", 1, libs).picks
    brace = picks[0]
    assert brace.label == "{__a__|__b__}" and "(" not in brace.value
    assert all("(" not in k for k in brace.keys)


def test_an_entry_that_ends_a_sentence_loses_its_period_when_the_line_goes_on():
    libs = _libs(pose=["Panicked run: hair flying, conveying fear."], place=["a wooded frisbee course."],
                 pause=["She waits..."])
    assert expand("doing __pose__ at __place__", 1, libs).text == (
        "doing Panicked run: hair flying, conveying fear at a wooded frisbee course.")
    assert expand("__pose__", 1, libs).text == "Panicked run: hair flying, conveying fear."
    assert expand("__place__. Then", 1, libs).text == "a wooded frisbee course. Then"
    assert expand("__pause__ now", 1, libs).text == "She waits... now"  # an ellipsis is meant
    assert expand("__place__ Then it rains.", 1, libs).text == "a wooded frisbee course. Then it rains."


def test_a_mid_sentence_entry_starts_with_a_small_article():
    libs = _libs(place=["A wooded frisbee course.", "Tokyo Tower at night."])
    seen = {expand("she runs at __place__", s, libs).text for s in range(20)}
    assert seen == {"she runs at a wooded frisbee course.", "she runs at Tokyo Tower at night."}
    assert expand("__place__", 3, _libs(place=["A wooded frisbee course."])).text == "A wooded frisbee course."


def test_dynamic_prompts_weights_are_read_too():
    """`{3::red|1::blue}` (Dynamic Prompts) weighs like orrery's `{red:3|blue}`."""
    counts = Counter(expand("{3::red|1::blue}", s, {}).text for s in range(400))
    assert set(counts) == {"red", "blue"} and 2.2 < counts["red"] / counts["blue"] < 4.2
    assert expand("{2::a|b}", 1, {}).picks[0].label == "{a|b}"
    assert set(expand("{2$$3::x|1::y|z}", 1, {}).text.split(", ")) <= {"x", "y", "z"}


WEATHER = {"weather": Library("weather", [
    Entry("heavy snow", props=(("kind", "snow"), ("sfx", "footsteps crunch in fresh snow"))),
    Entry("summer rain", props=(("kind", "rain"), ("sfx", "rain drums on a tin roof"))),
])}


def test_a_binding_reads_the_properties_of_its_pick():
    """Sound follows picture: $w.sfx belongs to the weather $w rolled."""
    seen = {expand("$w = __weather__\nA street in $w; $w.sfx.", s, WEATHER).text for s in range(20)}
    assert seen == {"A street in heavy snow; footsteps crunch in fresh snow.",
                    "A street in summer rain; rain drums on a tin roof."}
    assert expand("$w = __weather__\n[$w.missing]", 1, WEATHER).text == "[]"


def test_lines_and_choices_can_depend_on_a_property():
    t = "$w = __weather__\n? $w.kind=snow: Breath fogs in the cold.\nThe street is {? $w.kind=rain,drizzle: wet|dry}."
    seen = {expand(t, s, WEATHER).text for s in range(20)}
    assert seen == {"Breath fogs in the cold. The street is dry.", "The street is wet."}
    assert expand("$w = __weather__\n? $w.kind!=snow: Umbrellas.", 2, WEATHER).text in ("", "Umbrellas.")


POSES = {"pose": Library("pose", [
    Entry("backbend", props=(("kind", "bend"), ("loras", "@backbend(0.4-0.9) <lora:flex:1>"),
                             ("action", "$p arches into a {deep|full} backbend over __mat__"))),
]), "mat": Library("mat", [Entry("a blue mat"), Entry("a red mat")])}


def test_a_field_is_a_template_rolled_once_when_it_is_bound():
    """LoRAs and the action they belong to, in one entry: $p.loras and $p.action."""
    e = expand("$p = __pose__\n$p.action. Again: $p.action. $p.loras", 4, POSES)
    action = e.text.split(". ")[0]
    assert e.text.startswith(f"{action}. Again: {action}. <lora:backbend:0.")  # read twice, the same
    assert action.startswith("backbend arches into a ") and action.endswith(("blue mat", "red mat"))
    labels = [p.label for p in e.picks]
    assert labels[0] == "$p ← __pose__" and "<lora:backbend>" in labels and "{deep|full}" in labels
    t = "$p = __pose__\n? $p.kind=bend: Bent.\n__mat#kind:$p.kind__"  # conditions and filters read it as written
    assert expand(t, 1, {**POSES, "mat": Library("mat", [Entry("a yoga mat", props=(("kind", "bend"),))])}).text \
        == "Bent. a yoga mat"


def test_a_sweep_in_a_field_takes_its_first_strength_and_says_to_grid_the_binding():
    libs = {"pose": Library("pose", [Entry("split", props=(("loras", "<lora:split:0.5,1.0>"),))])}
    e = expand("$p = __pose__\n$p.loras", 1, libs)
    assert e.text == "<lora:split:0.5>" and "in $p.loras is a sweep" in e.warnings[0] and "@grid $p" in e.warnings[0]


def test_a_filter_can_depend_on_what_was_rolled_before():
    """Codie's dependent choice: the place follows the animal's habitat."""
    libs = {"animal": Library("animal", [Entry("a whale", props=(("habitat", "ocean"),)),
                                         Entry("a goat", props=(("habitat", "mountain"),))]),
            "place": Library("place", [Entry("a kelp forest", props=(("habitat", "ocean"),)),
                                       Entry("a scree slope", props=(("habitat", "mountain"),))])}
    seen = {expand("$a = __animal__\n$a in __place#habitat:$a.habitat__", s, libs).text for s in range(20)}
    assert seen == {"a whale in a kelp forest", "a goat in a scree slope"}
    kinds = {expand("$k = {ocean|mountain}\n__place#habitat:$k__", s, libs).text for s in range(20)}
    assert kinds == {"a kelp forest", "a scree slope"}


def test_hash_lines_are_comments_and_filters_are_not():
    libs = {"animal": Library("animal", [Entry("fox", props=(("size", "small"),)), Entry("bear", props=(("size", "big"),))])}
    template = "# quickstart: __missing__ rolls a library, $x = __animal__ binds one\n  # indented too\n$a = __animal#size:big__\n#$a = __animal#size:small__\na $a in the snow"
    assert expand(template, 1, libs).text == "a bear in the snow"


# --- how deep, and what comes back ------------------------------------------------------------

def test_many_choices_all_roll_and_a_choice_that_keeps_coming_back_stops_with_a_message():
    assert "{" not in expand(" ".join(["{x|y}"] * 500), 1, {}).text  # the old cap left braces 201+ as text
    loop = {"a": Library("a", [Entry("x {1$$__a__}")])}
    with pytest.raises(ValueError, match="still to roll"):
        expand("{1$$__a__}", 1, loop)


def test_a_field_reads_its_siblings_and_two_that_read_each_other_are_an_error():
    libs = {"p": Library("p", [Entry("bend", props=(("a", "A sees [$p.b]"), ("b", "B {is|was} $p")))])}
    e = expand("$p = __p__\n$p.a / $p.b", 3, libs)
    a, b = e.text.split(" / ")
    assert a == f"A sees [{b}]" and b in ("B is bend", "B was bend") and not e.warnings
    both = {"p": Library("p", [Entry("bend", props=(("a", "[$p.b]"), ("b", "[$p.a]")))])}
    with pytest.raises(ValueError, match=r"Fields read each other: \$p\.a → \$p\.b → \$p\.a"):
        expand("$p = __p__\n$p.a", 1, both)


def test_a_name_that_is_not_bound_stays_as_written_and_warns():
    e = expand("$a = $b\n$b = owl\n[$a] [$b] [$nope] [$nope.field] $5 off", 1, {})
    assert e.text == "[$b] [owl] [$nope] [] $5 off"
    assert [w.split(" is not bound")[0] for w in e.warnings] == ["$b", "$nope"]
    assert expand("$b = owl\n$a = $b\n[$a]", 1, {}).warnings == []


# --- second pass: bugs (docs/plan-dsl-2.md, phase 1) -------------------------------------------

def test_a_weighted_optional_keeps_its_space():
    assert {expand("a fox{ in the rain:3|:7}", s, {}).text for s in range(40)} == {"a fox", "a fox in the rain"}


def test_dynamic_prompts_joiner():
    assert expand("{2$$ and $$a|b|c}", 1, {}).text.count(" and ") == 1
    three = expand("{3$$ / $$__style__}", 1, LIBS)
    assert sorted(three.text.split(" / ")) == ["cyanotype", "gouache", "linocut"] and three.picks[0].value == three.text


def test_a_backslash_writes_the_character_as_it_is():
    e = expand("json \\{a|b\\} and \\__init__ and \\$HOME, one \\\\ and \\<lora:x:1> and \\@x(1)", 1, LIBS)
    assert e.text == "json {a|b} and __init__ and $HOME, one \\ and <lora:x:1> and @x(1)" and not e.picks and not e.warnings
    assert wanted_libraries("a \\__init__ and __animal__") == {"animal": 0}
    libs = {"sign": Library("sign", [Entry("a sign reading \\{OPEN\\}")])}
    assert expand("$s = __sign__\n$s, again $s", 1, libs).text == "a sign reading {OPEN}, again a sign reading {OPEN}"


# --- second pass: stable seeds (phase 2) -------------------------------------------------------

def test_a_choice_added_elsewhere_leaves_the_other_picks_of_a_seed_alone():
    libs = {**LIBS, "light": Library("light", [Entry(x) for x in ("dawn", "noon", "dusk", "night")])}
    for seed in range(30):
        before = expand("a __animal__ at __light__", seed, libs).picks
        after = expand("a {small|big} __animal__ at __light__, {0.4-0.9}", seed, libs).picks
        assert [(p.label, p.value) for p in before] == [(p.label, p.value) for p in after if p.label in ("__animal__", "__light__")]


def test_the_dice_of_before_stay_with_rng_1():
    """The single stream every run used until 2026-10-02 (outputs pinned from that code)."""
    t = "@rng 1\n$hero = __animal__\n$hero in {misty|frozen} __style__"
    assert [expand(t, s, LIBS).text for s in (1, 2, 3)] == ["owl in misty linocut", "ocelot in frozen cyanotype",
                                                            "heron in misty gouache"]
    assert "@rng" not in expand(t, 1, LIBS).text and expand(t, 1, LIBS).params.rng == 1


# --- second pass: one predicate language (phase 3) ---------------------------------------------

BEINGS = {"creature": Library("creature", [
    Entry("dragon", ("myth",), props=(("habitat", "mountain"), ("size", "huge"))),
    Entry("selkie", ("myth",), props=(("habitat", "sea"), ("size", "small"))),
    Entry("phoenix", ("myth", "bird"), props=(("habitat", "sky"), ("size", "large"))),
    Entry("otter", ("water",), props=(("habitat", "Sea"), ("size", "small"))),
    Entry("wren", ("bird",), props=(("habitat", "forest"), ("size", "tiny"))),
]), "place": Library("place", [Entry("a kelp forest", props=(("habitat", "sea"),)),
                               Entry("a crag", props=(("habitat", "mountain"),))])}


def seen(template):
    return {expand(template, s, BEINGS).text for s in range(80)}


def test_tags_and_properties_filter_in_one_bracket():
    assert seen("__creature[myth, !bird, habitat=sea]__") == {"selkie"}
    assert seen("__creature[size=small|tiny]__") == {"selkie", "otter", "wren"}  # a key's values
    assert seen("__creature[size!=small, !myth]__") == {"wren"}
    assert seen("$a = __creature[habitat=sea|mountain]__\n$a in __place[habitat=$a.habitat]__") == {
        "dragon in a crag", "selkie in a kelp forest", "otter in a kelp forest"}
    assert seen("__creature[myth]#size:small__") == {"selkie"}  # the old filter still adds up


def test_a_condition_takes_the_same_brackets_and_reads_tags_props_and_the_value():
    assert seen("$c = __creature__\n{? $c[myth, size=small|tiny]: small myth|other}") == {"small myth", "other"}
    assert {t for t in seen("$c = __creature__\n? $c[wren]: It sings.\n$c") if "sings" in t} == {"It sings. wren"}
    assert seen("$c = __creature[bird]__\n? $c[!myth]: no myth\n? $c[myth]: myth") == {"no myth", "myth"}


@pytest.mark.parametrize("now, then", [
    ("IF $a is fox: a fox line", "? $a[fox]: a fox line"),
    ("IF $a is not fox, owl: neither", "? $a[!fox, !owl]: neither"),
    ("IF $a is feline, heron: cat or heron", "? $a[feline|heron]: cat or heron"),
    ("if $a is heron: lower case", "? $a[heron]: lower case"),
    ("IF $a[feline, !lynx]: the ocelot", "? $a[feline, !lynx]: the ocelot"),
    ("{IF $a is owl: an owl | no owl}", "{? $a[owl]: an owl|no owl}"),
    ("{IF $a is not owl: no owl | an owl}", "{? $a[!owl]: no owl|an owl}"),
])
def test_if_reads_aloud_and_rolls_as_the_condition_it_means(now, then):
    for seed in range(12):
        a, b = (expand(f"$a = __animal__\n{line}\n$a", seed, LIBS) for line in (now, then))
        assert (a.text, a.picks) == (b.text, b.picks)


def test_if_compares_a_field_and_leaves_other_text_alone():
    from orrery.dsl import question

    assert question("IF $w.kind is rain, snow: SFX: rain") == "? $w.kind=rain,snow: SFX: rain"
    assert question("IF $w.kind is not rain: dry") == "? $w.kind!=rain: dry"
    assert question("If the door opens: run") == "If the door opens: run"  # no $binding: prose


# --- second pass: the template's own libraries, chance (phase 5) -------------------------------

CROWD = "@lib crowd\n  a few __animal__s\n  - a lone __animal__\n\nA meadow with __crowd__."


def test_a_template_brings_its_own_libraries():
    texts = {expand(CROWD, s, LIBS).text for s in range(40)}
    assert any(t.startswith("A meadow with a few ") for t in texts) and any("a lone " in t for t in texts)
    assert wanted_libraries(CROWD) == {"animal": 0}  # never asked of the language model
    shadow = "@lib animal\n  a unicorn\n__animal__"
    assert expand(shadow, 1, LIBS).text == "a unicorn" and expand(shadow, 1, LIBS).picks[0].keys == ("__animal__=a unicorn",)
    assert [expand(CROWD + "\n@grid __crowd__", 2, LIBS, cell=c).text.split(" with ")[1][:5] for c in range(2)] == ["a few", "a lon"]
    with pytest.raises(ValueError, match="no entries"):
        expand("@lib empty\na __empty__", 1, LIBS)


def test_a_screenplay_and_a_reel_have_their_own_libraries_too():
    from orrery.h3 import compile_scene

    h3 = "@h3 t2va\n@lib mood\n  calm\n  tense\nSHOT 5s: static\nA __mood__ street.\nSFX: wind"
    assert compile_scene(h3, 2, LIBS).scene.shots[0].items[0] in ("A calm street.", "A tense street.")
    reel = "@h3 t2va\n@lib mood\n  calm\nCHUNK a repeat 2\nSHOT 5s: static\nA __mood__ street."
    assert "calm" in compile_scene(reel, 2, LIBS, segment=1).text


def test_a_chance_adds_its_words_that_often_and_takes_its_space_along():
    hits = sum("in the rain" in expand("a fox {30% in the rain}.", s, {}).text for s in range(1000))
    assert 250 < hits < 350
    assert {expand("a fox {30% in the rain}.", s, {}).text for s in range(30)} == {"a fox.", "a fox in the rain."}
    assert {expand("a fox {30% in the rain}.", s, {}, {"{30% in the rain}=": 0.0}).text for s in range(10)} == {
        "a fox in the rain."}  # learned like a choice
    assert expand("{30% off|half price}", 1, {}).text in ("30% off", "half price")  # a choice, not a chance
    assert [expand("a fox {30% in the rain}\n@grid {30% in the rain}", 1, {}, cell=c).text for c in (0, 1)] == [
        "a fox in the rain", "a fox"]


def test_the_writers_keep_the_templates_own_libraries():
    from orrery.writers import apply

    assert apply("describe", "@lib mood\n  calm\na photo\n@size 832x1216\n", "A fox.") == \
        "@lib mood\n  calm\nA fox.\n@size 832x1216\n"


# --- second pass: globs and leftovers (phase 6) ------------------------------------------------

CLOTHES = {"clothing/hats": Library("clothing/hats", [Entry("beret"), Entry("fedora", ("winter",))]),
           "clothing/shoes": Library("clothing/shoes", [Entry(f"shoe {i}") for i in range(30)]),
           "clothing/winter/coats": Library("clothing/winter/coats", [Entry("parka", ("winter",))]),
           "scenes/features_a": Library("scenes/features_a", [Entry("tower")]), "scenes/other": Library("scenes/other", [Entry("x")])}


def test_a_glob_rolls_a_library_then_its_entry_and_learns_on_the_library():
    picked = [expand("__clothing/*__", s, CLOTHES).picks[0] for s in range(400)]
    hats = sum(p.keys[0].startswith("__clothing/hats__=") for p in picked)
    assert 150 < hats < 250  # each library as likely, however many entries it has
    assert picked[0].label == "__clothing/*__" and picked[0].keys[0].split("=")[1] == picked[0].value
    assert {expand("__clothing/**[winter]__", s, CLOTHES).text for s in range(40)} == {"fedora", "parka"}
    assert {expand("__scenes/features*__", s, CLOTHES).text for s in range(5)} == {"tower"}
    assert wanted_libraries("__clothing/*__ and __real__") == {"real": 0}
    with pytest.raises(ValueError, match="matches no library"):
        expand("__shoes/*__", 1, CLOTHES)


def test_a_grid_and_unique_run_through_a_globs_entries():
    texts = [expand("__clothing/**[winter]__\n@grid __clothing/**[winter]__", 1, CLOTHES, cell=c).text for c in range(2)]
    assert texts == ["fedora", "parka"]


def test_what_looks_like_syntax_but_rolled_nothing_warns():
    warnings = expand("a __my-list__ and {broken", 1, {}).warnings
    assert any("__my-list__ looks like a wildcard" in w for w in warnings) and any("{ or } is left over" in w for w in warnings)
    assert expand("a \\__my-list__ and \\{fine\\}", 1, {}).warnings == []
