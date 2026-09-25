from orrery.home import Home
from orrery.uistate import (
    RECENT_MAX,
    forget,
    load_ui,
    rename_everywhere,
    set_favorite,
    set_quickstart,
    touch_recent,
)


def test_a_fresh_home_has_no_favorites_or_recents(home):
    assert load_ui(Home(home)) == {"favorites": [], "recent": [], "quickstart": True}


def test_favorites_toggle_on_and_off(home):
    h = Home(home)
    assert set_favorite(h, "krea/tiny", True) == ["krea/tiny"]
    set_favorite(h, "a", True)
    assert set_favorite(h, "krea/tiny", False) == ["a"]
    assert set_favorite(h, "a", True) == ["a"]
    assert load_ui(h)["favorites"] == ["a"]


def test_recent_is_newest_first_unique_and_capped(home):
    h = Home(home)
    for i in range(RECENT_MAX + 3):
        touch_recent(h, f"p{i}")
    recent = touch_recent(h, "p5")
    assert recent[0] == "p5" and recent.count("p5") == 1 and len(recent) == RECENT_MAX


def test_rename_and_forget_update_both_lists(home):
    h = Home(home)
    set_favorite(h, "old", True)
    touch_recent(h, "old")
    rename_everywhere(h, "old", "new")
    assert load_ui(h) == {"favorites": ["new"], "recent": ["new"], "quickstart": True}
    forget(h, "new")
    assert load_ui(h) == {"favorites": [], "recent": [], "quickstart": True}


def test_writes_leave_no_temp_files(home):
    set_favorite(Home(home), "x", True)
    assert sorted(p.name for p in home.iterdir() if p.is_file()) == ["ui.json"]


def test_quickstart_is_on_until_turned_off_and_survives_other_writes(home):
    h = Home(home)
    assert set_quickstart(h, False) is False
    set_favorite(h, "a", True)
    touch_recent(h, "a")
    rename_everywhere(h, "a", "b")
    forget(h, "b")
    assert load_ui(h)["quickstart"] is False
    assert set_quickstart(h, True) is True
