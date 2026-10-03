"""The DSL's newer forms: tag algebra, number ranges, LoRA strength ranges and the short `@name(…)`,
and the batch parameters `: grid` and `unique=` (orrery.batch)."""

import pytest

from orrery import batch
from orrery.dsl import expand, expand_batch, override, parse
from orrery.h3 import compile_scene
from orrery.library import Entry, Library
from orrery.loras import long_form
from orrery.sweep import runs

LIBS = {
    "creature": Library("creature", [
        Entry("dragon", ("myth",)), Entry("phoenix", ("myth", "bird")), Entry("heron", ("bird", "water")),
        Entry("otter", ("water",)), Entry("fox"),
    ]),
    "style": Library("style", [Entry("ink"), Entry("clay"), Entry("oil")]),
}


def rolled(template, seeds=range(60)):
    return {expand(template, s, LIBS).text for s in seeds}


# --- tag algebra ----------------------------------------------------------------------------

def test_tags_combine_all_none_and_either():
    assert rolled("__creature[myth,!bird]__") == {"dragon"}
    assert rolled("__creature[water|myth]__") == {"dragon", "phoenix", "heron", "otter"}
    assert rolled("__creature[bird,water|myth]__") == {"phoenix", "heron"}
    assert rolled("__creature[!myth,!water]__") == {"fox"}


def test_a_tag_choice_inside_a_brace_stays_one_option():
    assert rolled("{__creature[water|myth]__|plain}") <= {"dragon", "phoenix", "heron", "otter", "plain"}
    assert "plain" in rolled("{__creature[water|myth]__|plain}")


# --- number ranges --------------------------------------------------------------------------

def test_a_range_rolls_a_number_at_its_decimals_and_learns_per_bin():
    values = {float(t) for t in rolled("{0.4-0.9}")}
    assert values <= {0.4, 0.5, 0.6, 0.7, 0.8, 0.9} and len(values) > 3
    assert rolled("{2-6}") == {"2", "3", "4", "5", "6"}
    [pick] = expand("{0.40-0.90}", 3, LIBS).picks
    lo, hi = pick.keys[0].split("=")[1].split("–")
    assert pick.label == "{0.40-0.90}" and float(lo) <= float(pick.value) <= float(hi)  # 51 values, ten bins
    assert {float(t) for t in rolled("{-1-1}")} == {-1.0, 0.0, 1.0}


def test_learned_weights_steer_a_range():
    learned = {"{1-3}=" + v: 0.0 for v in ("1", "2")}
    assert {expand("{1-3}", s, LIBS, learned).text for s in range(20)} == {"3"}


def test_a_range_that_runs_backwards_says_so():
    with pytest.raises(ValueError, match="backwards"):
        expand("{0.9-0.4}", 1, LIBS)


# --- LoRAs ----------------------------------------------------------------------------------

def test_a_lora_strength_range_rolls_and_is_recorded():
    e = expand("a fox <lora:style_x:0.4-0.9>", 5, LIBS)
    [pick] = e.picks
    assert e.text == f"a fox <lora:style_x:{pick.value}>" and pick.label == "<lora:style_x>"
    assert 0.4 <= float(pick.value) <= 0.9 and pick.keys == (f"<lora:style_x>={pick.value}",)
    clip = expand("<lora:a:1.0:0.2-0.5>", 2, LIBS)
    assert clip.text.startswith("<lora:a:1.0:0.") and clip.picks[0].keys[0].startswith("<lora:a> clip=")


def test_the_short_form_is_a_lora_tag_and_sweeps_like_one():
    assert long_form("@ink(0.8) and @H3-Icy_v1.2(0.4-0.9:1.0)") == "<lora:ink:0.8> and <lora:H3-Icy_v1.2:0.4-0.9:1.0>"
    assert long_form("@include effects/x\n@h3 t2va\nmail@host(1)") == "@include effects/x\n@h3 t2va\nmail@host(1)"
    assert len(runs(long_form("a cat @style(0.5,0.7,1.0)"))) == 3
    assert expand("a cat @ink(0.8)", 1, LIBS).text == "a cat <lora:ink:0.8>"


# --- params ---------------------------------------------------------------------------------

def test_params_lines_add_up_and_a_grid_takes_the_rest_of_its_line():
    p = parse(": x8 seed=3\n: unique=__creature__ w832\n: grid __style__ × {dawn|noon}\n").params
    assert (p.count, p.seed, p.width, p.unique, p.grid) == (8, 3, 832, ["__creature__"], "__style__ × {dawn|noon}")


# --- grid -----------------------------------------------------------------------------------

GRID = "a __creature__ in __style__ at {dawn|noon}\n: grid __style__ × {dawn|noon}"


def test_a_grid_runs_every_combination_and_nothing_else_moves():
    found = batch.axes(GRID, LIBS)
    assert (batch.cells(found), batch.formula(found)) == (6, "3 × 2")
    texts = [expand(GRID, 7, LIBS, cell=c).text for c in range(6)]
    creature = texts[0].split()[1]
    assert texts == [f"a {creature} in {s} at {t}" for s in ("ink", "clay", "oil") for t in ("dawn", "noon")]
    assert {p.label for p in expand(GRID, 7, LIBS, cell=3).picks} == {"__creature__", "__style__", "{dawn|noon}"}  # picks as ever
    assert len(rolled(GRID)) > 6  # without a cell (Test, Rolls) the axes roll


def test_a_grid_axis_may_be_a_binding_or_a_filtered_library():
    t = "$hero = __creature[myth|water]__\n$hero at {dawn|noon}\n: grid $hero"
    assert [expand(t, 1, LIBS, cell=c).text.split()[0] for c in range(4)] == ["dragon", "phoenix", "heron", "otter"]


def test_a_grid_axis_dialed_to_one_value_is_a_grid_of_one():
    t = "$view = {front|side|back}\n__creature__, seen from the $view\n: grid $view"
    assert [expand(t, 4, LIBS, cell=c).text for c in range(3)] == [
        expand(override(t, {"view": v}), 4, LIBS, cell=0).text for v in ("front", "side", "back")]
    assert batch.axes(override(t, {"view": "side"}), LIBS)[0].options == ["side"]


def test_expand_batch_gives_every_cell_at_each_seed():
    rows = expand_batch(GRID, 10, 2, LIBS)
    assert [(r.seed, r.cell) for r in rows] == [(s, c) for s in (10, 11) for c in range(6)]


def test_a_screenplay_grids_too_and_so_does_one_clip_of_a_reel():
    h3 = "@h3 t2va\nSHOT 5s: static\nA __creature__ paints in __style__.\n: grid __style__"
    assert "in clay" in compile_scene(h3, 3, LIBS, cell=1).text
    reel = "@h3 text\nSCENE a\nSHOT 5s\nA fox.\nEND ON: the fox sits\nSCENE b\nSHOT 5s\nA heron in __style__.\n: grid __style__"
    first, second = (compile_scene(reel, 3, LIBS, segment=1, cell=c).text for c in (0, 1))
    assert first != second and "in clay" in second and "the fox sits" in first and "the fox sits" in second
    assert compile_scene(reel, 3, LIBS, segment=0, cell=1).text == compile_scene(reel, 3, LIBS, segment=0, cell=0).text
    with pytest.raises(ValueError, match="reel"):
        compile_scene(reel.replace(": grid __style__", ": unique=__style__"), 3, LIBS)


@pytest.mark.parametrize("template, words", [
    ("a __creature__\n: grid __style__", "doesn't use it"),
    ("a {0.4-0.9}\n: grid {0.4-0.9}", "neither one library"),
    ("$a = __style__\na __creature[myth]#k:$a__\n: grid __creature[myth]#k:$a__", "filters by a roll"),
    ("a __style__\n: grid $nope", "no binding"),
    ("a __nope__\n: grid __nope__", "no library"),
])
def test_a_grid_says_what_is_wrong(template, words):
    with pytest.raises(ValueError, match=words):
        expand(template, 1, LIBS, cell=0)


# --- unique ---------------------------------------------------------------------------------

def test_unique_never_repeats_within_a_batch_of_seeds_in_a_row():
    t = "$hero = __creature__\n$hero in __style__\n: x5 unique=$hero"
    for start in (0, 100, 12345):
        heroes = [expand(t, s, LIBS).text.split()[0] for s in range(start, start + 5)]
        assert sorted(heroes) == ["dragon", "fox", "heron", "otter", "phoenix"]
    nxt = [expand(t, s, LIBS).text.split()[0] for s in range(5, 10)]
    assert nxt == [expand(t, s, LIBS).text.split()[0] for s in range(5)]  # the order goes round


def test_unique_on_a_library_written_twice_takes_two_steps_per_seed():
    t = "__creature__ meets __creature__\n: unique=__creature__"
    seen = [w for s in (0, 1) for w in expand(t, s, LIBS).text.split(" meets ")]
    assert len(set(seen)) == 4


def test_unique_says_what_is_wrong():
    with pytest.raises(ValueError, match="doesn't use it"):
        expand("a __style__\n: unique=__creature__", 1, LIBS)
    with pytest.raises(ValueError, match="grid axis"):
        expand("a __style__\n: grid __style__\n: unique=__style__", 1, LIBS, cell=0)


# --- LoRAs in library entries ---------------------------------------------------------------

def one(value):
    return {"sets": Library("sets", [Entry(value)])}


def test_an_entry_writes_its_loras_as_the_template_does():
    rolled_ = expand("a fox __sets__", 3, one("<lora:ink:0.4-0.9> @grain(0.6)"))
    strength = rolled_.picks[1].value
    assert rolled_.text == f"a fox <lora:ink:{strength}> <lora:grain:0.6>" and 0.4 <= float(strength) <= 0.9
    assert [p.label for p in rolled_.picks] == ["__sets__", "<lora:ink>"] and not rolled_.warnings
    c = compile_scene("@h3 t2va\nLORA: __sets__\nSHOT 5s: static\nA fox.", 1, one("@ink(0.8) @grain(0.4)"))
    assert c.loras == "<lora:ink:0.8> <lora:grain:0.4>"


def test_a_sweep_in_an_entry_takes_its_first_strength_and_says_to_grid_instead():
    e = expand("a fox __sets__", 1, one("<lora:ink:0.5,1.0>"))
    assert e.text == "a fox <lora:ink:0.5>"
    [warning] = e.warnings
    assert "<lora:ink:0.5,1.0> in an entry of __sets__ is a sweep" in warning and "@grid __sets__" in warning
    assert expand("a fox __sets__", 1, one("<lora:ink:0-1;0.5>")).text.strip() == "a fox"  # its first strength is off
    assert expand("a fox <lora:ink:0.5,1.0>", 1, LIBS).warnings == []  # in the template it is a sweep, as ever
    h3 = compile_scene("@h3 t2va\nLORA: __sets__\nSHOT 5s: static\nA fox.", 1, one("<lora:ink:0.5,1.0>"))
    reel = compile_scene("@h3 t2va\nLORA: __sets__\nCHUNK a\nSHOT 5s\nA fox.", 1, one("<lora:ink:0.5,1.0>"))
    for compiled in (h3, reel):
        assert any("is a sweep" in i.message for i in compiled.lint) and compiled.loras == "<lora:ink:0.5>"


# --- @ directives (docs/plan-dsl-2.md, phase 4) ----------------------------------------------

def test_directives_say_what_the_colon_line_says():
    at = parse("a fox\n@grid __style__ × {dawn|noon}\n@unique $hero __creature__\n@size 832x1216\n@seed 100\n@batch 8").params
    colon = parse("a fox\n: grid __style__ × {dawn|noon}\n: unique=$hero unique=__creature__ w832 h1216 seed=100 x8").params
    assert at == colon
    g = "a __creature__ in __style__\n@grid __style__"
    assert [expand(g, 3, LIBS, cell=c).text.split(" in ")[1] for c in range(3)] == ["ink", "clay", "oil"]
    assert "@" not in expand("@size 832x1216\na fox\n@batch 2", 1, LIBS).text


@pytest.mark.parametrize("line, words", [("@size big", "width and the height"), ("@rng 3", "dice are 1"),
                                         ("@batch many", "takes a number")])
def test_a_directive_says_what_it_needs(line, words):
    with pytest.raises(ValueError, match=words):
        parse(f"a fox\n{line}")


def test_a_screenplay_and_the_writers_keep_directives_out_of_the_prose():
    from orrery.writers import apply

    h3 = compile_scene("@h3 t2va\n@size 832x1216\n@rng 1\nSHOT 5s: static\nA fox.", 1, LIBS)
    assert "@size" not in h3.text and "@rng" not in h3.text
    assert apply("describe", "# note\na photo\n@size 832x1216\n", "A fox in snow.") == "# note\nA fox in snow.\n@size 832x1216\n"


# --- LoRA strengths are values (phase 7) -----------------------------------------------------

def test_a_lora_strength_takes_a_choice_or_a_binding_and_learns_as_the_lora():
    e = expand("a fox <lora:ink:{0.5|0.7}> <lora:clay:{0.5|0.7}>", 3, LIBS)
    assert [p.label for p in e.picks] == ["<lora:ink>", "<lora:clay>"]  # not a `{0.5|0.7}` both would share
    assert e.text == f"a fox <lora:ink:{e.picks[0].value}> <lora:clay:{e.picks[1].value}>"
    assert expand("$s = {0.3|0.9}\n<lora:ink:$s>", 1, LIBS).text in ("<lora:ink:0.3>", "<lora:ink:0.9>")
    assert expand("<lora:my__file:{1.0}:{0.4}>", 1, LIBS).text == "<lora:my__file:1.0:0.4>"  # the name stays as written


def test_a_grid_over_a_lora_strength_is_a_lora_sweep():
    t = "a fox <lora:ink:{0.5|0.7|1.0}>\n@grid {0.5|0.7|1.0}"
    assert [expand(t, 1, LIBS, cell=c).text for c in range(3)] == ["a fox <lora:ink:0.5>", "a fox <lora:ink:0.7>",
                                                                   "a fox <lora:ink:1.0>"]
    assert batch.plan(t, LIBS) == {"runs": 3, "formula": "grid 3", "first": "{0.5|0.7|1.0}"}
