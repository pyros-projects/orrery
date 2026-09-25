import json

import pytest

from orrery.autolib import Need
from orrery.llm import FakeBackend
from orrery.slots import fill, request, slots, write


def test_a_slot_is_directions_between_double_dashes():
    text = "SHOT 5s\n--what WASHER does next--\nA man --and a dog-- walk."
    assert slots(text) == ["what WASHER does next", "and a dog"]


def test_dashes_that_are_punctuation_are_no_slot():
    assert slots("a -- b -- c\n---\nwell-known") == []


def test_a_slot_asked_twice_is_written_once():
    assert slots("--a view-- then --a view--") == ["a view"]


def test_fill_puts_the_written_text_where_each_slot_stands():
    text = "[Shot 1] --what happens next--. The camera holds."
    assert fill(text, {"what happens next": "He lets go of the rope"}) == "[Shot 1] He lets go of the rope. The camera holds."


def test_an_unanswered_slot_falls_back_to_its_directions():
    """A run that fails would leave a gap in the Motion Context chain; directions are better than nothing."""
    assert fill("A --quiet street at dawn--.", {}) == "A quiet street at dawn."


def test_the_request_shows_the_prompt_and_the_directions_of_each_slot():
    prompt = request([], ["what <Subject 1> does next"], "[Shot 1] --what <Subject 1> does next--.", frames=0)
    assert "[Shot 1] [slot 1]." in prompt
    assert '"slot 1": what <Subject 1> does next' in prompt
    assert "frames" not in prompt


def test_with_frames_the_request_says_they_are_the_clip_it_continues():
    prompt = request([], ["what happens next"], "--what happens next--", frames=5)
    assert "5 images" in prompt and "continue" in prompt


def test_one_request_writes_libraries_and_slots_together(tmp_path):
    from orrery.home import Home
    home = Home(tmp_path)
    wanted = [Need("mood", 3, "", "one sentence each")]
    prompt = request(wanted, ["what happens next"], "--what happens next-- in __mood__", frames=0)
    assert "__mood__: 3 entries" in prompt and '"slot 1"' in prompt
    backend = FakeBackend([json.dumps({"mood": ["A hush.", "A storm.", "A sigh."], "slot 1": "He waits"})])
    texts, notes = write(home, wanted, ["what happens next"], backend.complete(prompt), backend)
    assert texts == {"what happens next": "He waits"}
    assert home.libraries()["mood"].values() == ["A hush.", "A storm.", "A sigh."]
    assert any("Created __mood__" in n for n in notes)


def test_a_reply_without_json_is_no_answer_at_all(tmp_path):
    from orrery.home import Home
    from orrery.llm import InvalidProposal
    with pytest.raises(InvalidProposal):
        write(Home(tmp_path), [], ["what happens next"], "I cannot see the video.", FakeBackend([]))
