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
    assert notes == ["Created __runway_shoes__ with 12 entries (qwen3vl_4b)."]
    assert "a model in __runway_shoes__" in backend.prompts[0] and "12" in backend.prompts[0]


def test_a_minimum_tops_up_an_existing_library_once(home):
    backend = FakeBackend([json.dumps(["lynx", "otter", "fox", "stoat"])])
    notes = ensure_libraries(Home(home), "a __animal:6__", backend, default_n=12)
    values = Home(home).libraries()["animal"].values()
    assert values[:3] == ["fox", "heron", "owl"] and len(values) == 6 and "fox" not in values[3:]
    assert notes == ["Added 3 entries to __animal__ (fake), now 6."]
    assert ensure_libraries(Home(home), "a __animal:6__", backend, default_n=12) == []


def test_nothing_happens_without_a_model_or_when_all_is_there(home):
    assert ensure_libraries(Home(home), "a __missing__", None, default_n=12) == []
    assert "missing" not in Home(home).libraries()
    backend = FakeBackend(["[]"])
    assert ensure_libraries(Home(home), "a __animal__ and __style__", backend, default_n=12) == []
    assert backend.prompts == []
