"""LoRA sweeps: a tag with several strengths runs once per strength; swept LoRAs combine, solo
LoRAs take turns, 0 means off and identical runs run once."""

import pytest

from orrery import sweep


def models(source):
    """Each run as {lora name: model strength or None}."""
    tags = sweep.tags(source)
    return [{t.name: (None if run[t.text] is None else run[t.text][0]) for t in tags} for run in sweep.runs(source)]


def test_strengths_are_lists_and_ranges_with_a_step():
    assert sweep.values("0.5,0.6,0.7") == [0.5, 0.6, 0.7]
    assert sweep.values("0-1;0.1") == [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    assert sweep.values("-1-1;0.5") == [-1.0, -0.5, 0.0, 0.5, 1.0]
    assert sweep.values("0, 0.5-1;0.25") == [0.0, 0.5, 0.75, 1.0]
    assert sweep.values("0-1;0.3") == [0.0, 0.3, 0.6, 0.9]


@pytest.mark.parametrize("spec, words", [
    ("0.5-1", "step"), ("1-0;0.1", "backwards"), ("0-1;0", "step"), ("strong", '"strong"'), ("0-1000;0.0001", "too many"),
])
def test_bad_strengths_are_clear_errors(spec, words):
    with pytest.raises(ValueError, match=words):
        sweep.values(spec)


def test_only_tags_with_a_list_a_range_solo_or_the_macro_sweep():
    tags = sweep.tags("a cat <lora:a:0.5,1.0:solo> <lora:b:0.8> <lora:c:test> <lora:d:0.4:0.7>")
    assert [(t.name, t.model, t.clip, t.solo) for t in tags] == [("a", [0.5, 1.0], None, True),
                                                                   ("c", [1.0, 0.7, 0.5], None, True)]
    assert sweep.runs("a cat <lora:b:0.8>") == []


def test_swept_loras_combine_the_first_changing_slowest():
    assert models("<lora:a:0.5,1.0><lora:b:0.3,1>") == [{"a": 0.5, "b": 0.3}, {"a": 0.5, "b": 1.0},
                                                         {"a": 1.0, "b": 0.3}, {"a": 1.0, "b": 1.0}]
    assert sweep.formula("<lora:a:0.5,1.0><lora:b:0.3,1>") == "2 × 2"


def test_solo_loras_take_turns_with_the_others_off():
    src = "<lora:AmateurHour_01_rank16:0.5,1.0:solo><lora:AmateurHour_H3_000017500:0.5,1.0:solo>"
    assert models(src) == [{"AmateurHour_01_rank16": 0.5, "AmateurHour_H3_000017500": None},
                           {"AmateurHour_01_rank16": 1.0, "AmateurHour_H3_000017500": None},
                           {"AmateurHour_01_rank16": None, "AmateurHour_H3_000017500": 0.5},
                           {"AmateurHour_01_rank16": None, "AmateurHour_H3_000017500": 1.0}]
    assert sweep.formula(src) == "2 + 2"


def test_combined_loras_run_with_every_solo_turn():
    src = "<lora:c:0.2,0.4><lora:a:0.5:solo><lora:b:0.7,0.9:solo>"
    assert models(src) == [{"c": 0.2, "a": 0.5, "b": None}, {"c": 0.4, "a": 0.5, "b": None},
                           {"c": 0.2, "a": None, "b": 0.7}, {"c": 0.4, "a": None, "b": 0.7},
                           {"c": 0.2, "a": None, "b": 0.9}, {"c": 0.4, "a": None, "b": 0.9}]
    assert sweep.formula(src) == "2 × (1 + 2)"


def test_zero_is_off_and_identical_runs_run_once():
    src = "<lora:a:0,1:solo><lora:b:0,1:solo>"
    assert models(src) == [{"a": None, "b": None}, {"a": 1.0, "b": None}, {"a": None, "b": 1.0}]
    assert sweep.formula(src) == "2 + 2"


def test_the_macro_is_three_strengths_in_their_own_turn():
    assert models("<lora:H3-Icy-real-v1_000004200:test>") == [{"H3-Icy-real-v1_000004200": v} for v in (1.0, 0.7, 0.5)]


def test_a_clip_list_pairs_with_the_model_list():
    tags = sweep.tags("<lora:s:0.5,1.0:1.0>")
    assert [run[tags[0].text] for run in sweep.runs("<lora:s:0.5,1.0:1.0>")] == [(0.5, 1.0), (1.0, 1.0)]
    assert len(sweep.runs("<lora:s:0.5,1.0:0.5,1.0>")) == 4


def test_a_run_writes_concrete_tags_and_leaves_off_ones_out():
    src = "a cat <lora:a:0.5,1.0:solo> and <lora:b:0.8> <lora:c:0.3,0.6:solo>\nLORA: <lora:d:0,0.5>\nSHOT 5s"
    runs = sweep.runs(src)
    assert sweep.apply(src, runs[1]).splitlines()[0] == "a cat <lora:a:0.5> and <lora:b:0.8>"
    assert sweep.apply(src, runs[3]).splitlines()[0] == "a cat <lora:a:1> and <lora:b:0.8>"
    assert "LORA:" not in sweep.apply(src, runs[0])  # d at 0 is off, and its line goes with it
    assert sweep.apply(src, runs[1]).splitlines()[1] == "LORA: <lora:d:0.5>"
    assert sweep.apply("<lora:s:0.5,1.0:1.0> x", sweep.runs("<lora:s:0.5,1.0:1.0> x")[0]) == "<lora:s:0.5:1> x"


def test_the_same_tag_twice_is_one_lora():
    src = "<lora:a:0.5,1.0> then <lora:a:0.5,1.0>"
    assert len(sweep.runs(src)) == 2
    assert sweep.apply(src, sweep.runs(src)[1]) == "<lora:a:1> then <lora:a:1>"


def test_a_run_records_each_swept_lora_as_a_pick():
    src = "<lora:a:0.5,1.0:solo><lora:b:0.5:solo>"
    picks = sweep.picks(src, sweep.runs(src)[0])
    assert picks == [{"label": "<lora:a>", "value": "0.5", "keys": ["<lora:a>=0.5"]},
                     {"label": "<lora:b>", "value": "off", "keys": ["<lora:b>=off"]}]


def test_an_off_tag_leaves_one_space_between_what_stood_on_either_side():
    src = "a cat on a roof <lora:a:0.5,1.0:solo><lora:b:0.5,1.0:solo> at night <lora:c:0,1> and more"
    runs = sweep.runs(src)
    texts = {sweep.apply(src, r) for r in runs}
    assert "a cat on a roof <lora:b:0.5> at night and more" in texts
    assert "a cat on a roof <lora:a:1> at night <lora:c:1> and more" in texts
    assert sweep.apply("<lora:a:0,1> starts", sweep.runs("<lora:a:0,1> starts")[0]) == "starts"
    assert sweep.apply("ends <lora:a:0,1>", sweep.runs("ends <lora:a:0,1>")[0]) == "ends"
