"""The prompt history: every run of an Orrery Prompt as it resolved (seed, picks, the prompt), so a
lucky roll can be found again when its output was not kept."""

from orrery import history
from orrery.home import Home


def run(seed, text="a fox in the snow", **extra):
    return {"seed": seed, "target": "text", "template": "0123456789abcdef", "preset": None, "params": {},
            "text": text, "picks": [{"label": "__animal__", "value": "fox", "keys": ["animal=fox"]}], "lint": [],
            **extra}


def test_every_run_is_kept_newest_first(home):
    h = Home(home)
    history.record(h, run(1))
    history.record(h, run(2, segment=3, preset="h3/night_watch"))
    got = history.read(h)
    assert got["total"] == 2 and [r["seed"] for r in got["runs"]] == [2, 1]
    newest = got["runs"][0]
    assert (newest["segment"], newest["preset"], newest["picks"][0]["value"]) == (3, "h3/night_watch", "fox")
    assert newest["ts"] and newest["id"] != got["runs"][1]["id"]


def test_a_run_keeps_what_its_enhance_lines_did(home):
    """#279: History shows the instruction, the passage before the rewrite, and how the rewrite came about."""
    h, enhanced = Home(home), [{"instruction": "make it moody", "before": "a fox in a field", "after": "a fox in fog", "kept": True}]
    history.record(h, run(1, text="a fox in fog", enhanced=enhanced))
    history.record(h, run(2))
    runs = history.read(h)["runs"]
    assert runs[1]["enhanced"] == enhanced and "enhanced" not in runs[0]


def test_search_finds_the_prompt_its_picks_and_its_preset(home):
    h = Home(home)
    history.record(h, run(1, text="a heron at dawn"))
    history.record(h, run(2, preset="loops/backrooms"))
    history.record(h, {**run(3), "picks": [{"label": "$storm", "value": "a heavy sea fog", "keys": []}]})
    assert [r["seed"] for r in history.read(h, query="heron")["runs"]] == [1]
    assert [r["seed"] for r in history.read(h, query="backrooms")["runs"]] == [2]
    assert [r["seed"] for r in history.read(h, query="SEA FOG")["runs"]] == [3]


def test_it_pages(home):
    h = Home(home)
    for s in range(7):
        history.record(h, run(s))
    page = history.read(h, limit=3, offset=3)
    assert page["total"] == 7 and [r["seed"] for r in page["runs"]] == [3, 2, 1]


def test_it_keeps_the_last_runs(home, monkeypatch):
    monkeypatch.setattr(history, "KEEP", 5)
    h = Home(home)
    for s in range(9):
        history.record(h, run(s))
    assert [r["seed"] for r in history.read(h)["runs"]][:5] == [8, 7, 6, 5, 4]
    assert history.read(h)["total"] <= 6
