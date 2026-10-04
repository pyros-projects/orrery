"""Libraries the LLM makes on the fly: unknown __name__ gets created, __name:N__ topped up."""

import json

from orrery.autolib import ensure_libraries
from orrery.home import Home
from orrery.llm import FakeBackend


def test_an_unknown_library_is_created_with_the_default_count(home):
    backend = FakeBackend([json.dumps([f"shoe {i}" for i in range(12)])], name="qwen3vl_4b")
    notes = ensure_libraries(Home(home), "a model in __runway_shoes__", backend, default_n=12)
    lib = Home(home).libraries()["runway_shoes"]
    assert len(lib.entries) == 12 and lib.meta["generated_by"] == "qwen3vl_4b"
    assert notes == ["Created __runway_shoes__ with 12 entries (qwen3vl_4b); review it in Libraries."]
    assert "a model in __runway_shoes__" in backend.prompts[0] and "12" in backend.prompts[0]


def test_a_minimum_tops_up_an_existing_library_once(home):
    backend = FakeBackend([json.dumps(["lynx", "otter", "fox", "stoat"])])
    notes = ensure_libraries(Home(home), "a __animal:6__", backend, default_n=12)
    values = Home(home).libraries()["animal"].values()
    assert values[:3] == ["fox", "heron", "owl"] and len(values) == 6 and "fox" not in values[3:]
    assert notes == ["Added 3 entries to __animal__ (fake), now 6; review them in Libraries."]
    assert ensure_libraries(Home(home), "a __animal:6__", backend, default_n=12) == []


def test_nothing_happens_without_a_model_or_when_all_is_there(home):
    assert ensure_libraries(Home(home), "a __missing__", None, default_n=12) == []
    assert "missing" not in Home(home).libraries()
    backend = FakeBackend(["[]"])
    assert ensure_libraries(Home(home), "a __animal__ and __style__", backend, default_n=12) == []
    assert backend.prompts == []


def test_everything_the_template_asks_for_comes_from_one_call(home):
    reply = {"runway_shoes": [f"shoe {i}" for i in range(4)], "runway_hats": [f"hat {i}" for i in range(4)],
             "animal": ["lynx", "otter"]}
    backend = FakeBackend([json.dumps(reply)])
    notes = ensure_libraries(Home(home), "__runway_shoes__ and __runway_hats__ on an __animal:5__", backend, default_n=4)
    assert len(backend.prompts) == 1
    libs = Home(home).libraries()
    assert libs["runway_hats"].values() == [f"hat {i}" for i in range(4)] and len(libs["animal"].entries) == 5
    assert len(notes) == 3


def test_directions_reach_the_model_and_stay_with_the_library(home):
    backend = FakeBackend([json.dumps(["a long scene"] * 3 + ["another long scene", "a third one"])])
    ensure_libraries(Home(home), "SHOT 5s\n__film_scene__(at least 30 words, describe set and characters)", backend,
                     default_n=5)
    assert "at least 30 words, describe set and characters" in backend.prompts[0]
    assert Home(home).libraries()["film_scene"].meta["directions"] == "at least 30 words, describe set and characters"


def test_what_the_model_writes_waits_for_review(home):
    ensure_libraries(Home(home), "__runway_shoes__", FakeBackend([json.dumps(["mule", "boot"])]), default_n=2)
    ensure_libraries(Home(home), "__animal:5__", FakeBackend([json.dumps(["lynx", "otter"])]), default_n=2)
    libs = Home(home).libraries()
    assert libs["runway_shoes"].meta["pending"] is True
    assert libs["animal"].meta["pending_entries"] == ["lynx", "otter"]


def test_a_library_in_a_new_folder_gets_the_folder_too(home):
    ensure_libraries(Home(home), "__film/genre__", FakeBackend([json.dumps(["noir", "western"])]), default_n=2)
    assert (home / "library" / "film" / "genre.yaml").exists()
    assert Home(home).libraries()["film/genre"].values() == ["noir", "western"]


def test_a_list_with_directions_gets_only_its_directions(home):
    from orrery.autolib import Need, prompt_for
    prompt = prompt_for([Need("film/mood", 20, "__film/mood__", "at least one sentence, cinematic moods"),
                         Need("props", 12, "__props__")])
    mood = next(b for b in prompt.split("\n- ") if b.startswith("__film/mood__"))
    props = next(b for b in prompt.split("\n- ") if b.startswith("__props__"))
    assert "Directions: at least one sentence, cinematic moods" in mood and "1-4 words" not in mood
    assert "Used in" not in mood  # the template line would pull it toward a short phrase that fits the slot
    assert "1-4 words" in props  # the default style, only where there are no directions
    assert prompt.count("1-4 words") == 1


def test_the_context_leaves_out_the_directions_of_other_lists(home):
    from orrery.autolib import needs
    wanted = needs(Home(home), "a __genre__(like 'action film', 'documentary') scene of __props__", 12)
    props = next(n for n in wanted if n.name == "props")
    assert props.context == "a __genre__ scene of __props__"


def test_entries_of_any_length_are_kept_whole(home):
    saga = "Harry Potter and the Philosopher's Stone. " + "The boy who lived goes back to Hogwarts. " * 400
    ensure_libraries(Home(home), "__saga__", FakeBackend([json.dumps([saga.strip(), "b"])]), default_n=2)
    assert Home(home).libraries()["saga"].values()[0] == " ".join(saga.split())


def wildcards(body):
    """A fake endpoint's answer to a library request: four entries named after the list it asks for."""
    import re
    names = re.findall(r"- __([\w/]+)__:", body["messages"][0]["content"])
    return json.dumps({n: [f"{n} {i}" for i in range(4)] for n in names})


def test_an_endpoint_writes_each_library_in_a_request_of_its_own(home, fake_api):
    from orrery.autolib import needs, write_apart
    from orrery.llm import OpenAIBackend
    fake_api.answer = wildcards
    wanted = needs(Home(home), "__runway_shoes__ and __runway_hats__ on an __animal:5__", 4)
    notes = write_apart(Home(home), wanted, OpenAIBackend(fake_api.url, "gpt-5.4-mini"))
    asked = sorted(r["messages"][0]["content"].count("- __") for r in fake_api.requests)
    assert asked == [1, 1, 1] and len(notes) == 3
    libs = Home(home).libraries()
    assert libs["runway_hats"].values() == [f"runway_hats {i}" for i in range(4)] and len(libs["animal"].entries) == 5


def test_a_library_the_endpoint_fails_is_a_note_and_a_refused_key_an_error(home, fake_api):
    import pytest

    from orrery.autolib import needs, write_apart
    from orrery.llm import OpenAIBackend
    fake_api.answer = lambda body: "sorry" if "- __runway_hats__:" in body["messages"][0]["content"] else wildcards(body)
    wanted = needs(Home(home), "__runway_shoes__ and __runway_hats__", 4)
    notes = write_apart(Home(home), wanted, OpenAIBackend(fake_api.url, "gpt-5.4-mini"))
    assert "runway_shoes" in Home(home).libraries() and "runway_hats" not in Home(home).libraries()
    assert any(n.startswith("__runway_hats__ was not written: the model gave no usable JSON") for n in notes)
    fake_api.key = "sk-right"
    with pytest.raises(RuntimeError, match="HTTP 401"):
        write_apart(Home(home), needs(Home(home), "__runway_hats__", 4), OpenAIBackend(fake_api.url, "gpt-5.4-mini"))


def test_a_list_keyed_a_little_differently_still_lands_in_its_library(home):
    """#324: the model keyed `80s/80s_photographers` back as `80s/80s photographers`, and the list was lost."""
    from orrery.autolib import Need, lists_in

    need = lambda name: Need(name, 3, "", "", [], "")
    assert lists_in({"80s/80s photographers": ["miyako ishiuchi"]}, [need("80s/80s_photographers")]) == {"80s/80s_photographers": ["miyako ishiuchi"]}
    assert lists_in({"__Sky-Kind__": ["fog"], "moods": ["calm"]}, [need("sky_kind"), need("moods")]) == {"sky_kind": ["fog"], "moods": ["calm"]}
    assert lists_in({"weather": ["fog"], "moods": ["calm"]}, [need("sky_kind"), need("moods")]) == {"moods": ["calm"]}  # two asked: by name only
    assert lists_in({"entries": ["fog"]}, [need("sky_kind")]) == {"sky_kind": ["fog"]}  # one asked, one answered
    backend = FakeBackend([json.dumps({"Runway Shoes": [f"shoe {i}" for i in range(4)]})], name="qwen3vl_4b")
    ensure_libraries(Home(home), "a model in __runway_shoes:4__", backend)
    assert len(Home(home).libraries()["runway_shoes"].entries) == 4  # a run writing it keeps it too
