"""The places feature (#143): lands and settings for the creators, scenarios, and the film libraries of Surprise me."""

from orrery.h3 import CAMERA
from orrery.home import BUILTIN_DIR
from orrery.library import load_libraries

BUILTIN = load_libraries(BUILTIN_DIR)
CLIMATES = ("cold", "temperate", "hot", "tropical")
WATERS = ("no", "sea", "lake", "stream")


def entries(name):
    return BUILTIN[f"places/{name}"].entries


def test_the_lands_are_many_and_each_says_its_climate_water_ground_and_sound():
    """#144: the landscape creator's lands, at the creators' size."""
    lands = entries("terrain")
    assert len(lands) >= 75 and len({e.value for e in lands}) == len(lands)
    assert all(e.prop("climate") in CLIMATES and e.prop("wet") in WATERS for e in lands)
    assert all(e.prop("kind") and e.prop("detail") and e.prop("sfx") for e in lands)


def test_every_land_finds_a_season_a_sky_an_hour_and_twenty_signs_of_life():
    """The creator filters each pick by the one before; no land may leave a filter empty, and twenty lands of a
    kind in a row need not repeat their sign of life."""
    seasons, skies, hours, life = entries("season"), entries("weather"), entries("hour"), entries("life")
    for land in entries("terrain"):
        climate, wet = land.prop("climate"), land.prop("wet")
        mine = [s for s in seasons if s.prop("climate") == climate]
        assert mine, land.value
        for season in mine:
            for sky in [w for w in skies if w.prop("cold") in (season.prop("cold"), "any")]:
                assert [h for h in hours if h.prop("clear") in (sky.prop("clear"), "any")
                        and h.prop("climate") in (climate, "any")], (land.value, sky.value)
        water = "no" if wet == "no" else "yes"
        pool = [e for e in life if e.prop("climate") in (climate, "any") and e.prop("water") in ("any", wet, water)]
        assert len(pool) >= 20, (land.value, len(pool))


def test_every_sign_of_life_leaves_a_trace_and_every_sky_shows_up_close():
    """The detail view shows only the ground: the land's detail, the sky's `near` and the life's `trace`."""
    assert all(e.prop("trace") for e in entries("life"))
    assert all(e.prop("near") and e.prop("sfx") for e in entries("weather"))
    assert all(e.prop("light") for e in entries("hour"))


WORLDS = ("everyday", "fantasy", "cyberpunk", "scifi", "noir")
KINDS = ("room", "hall", "shop", "street", "vehicle", "ruin")


def test_every_world_has_thirty_settings_and_every_kind_of_them():
    """#145: the setting creator rolls a place of its world; a kind added to the filter never leaves it empty."""
    settings = entries("setting")
    assert len({e.value for e in settings}) == len(settings)
    for world in WORLDS:
        mine = [e for e in settings if e.prop("world") == world]
        assert len(mine) >= 30, world
        assert {e.prop("kind") for e in mine} == set(KINDS), world
    assert all(e.prop("inside") in ("yes", "no") for e in settings)
    assert all(e.prop("outside") and e.prop("detail") and e.prop("light") and e.prop("sfx") for e in settings)


def test_every_world_of_scenarios_goes_from_tame_to_abstract():
    """#150: eight worlds of scenarios at the creators' size, fifteen of each level, so `[wild=…]` never runs dry."""
    worlds = sorted(n.split("/")[1] for n in BUILTIN if n.startswith("scenarios/"))
    assert worlds == ["abstract", "dreamlike", "everyday", "fantasy", "festive", "fights", "pirates", "scifi"]
    for world in worlds:
        scenarios = BUILTIN[f"scenarios/{world}"].entries
        assert len({e.value for e in scenarios}) == len(scenarios) >= 60, world
        for level in ("tame", "odd", "wild", "abstract"):
            assert len([e for e in scenarios if e.prop("wild") == level]) >= 15, (world, level)


def test_every_genre_plays_and_peaks_and_every_hand_moves_the_camera_in_h3s_words():
    """#149: Surprise me reads a genre's manner, peak, music and sound, and a director's hand's camera."""
    genres, hands = BUILTIN["film/genres"].entries, BUILTIN["film/directing"].entries
    assert len({e.value for e in genres}) == len(genres) >= 30 and len({e.value for e in hands}) == len(hands) >= 30
    assert all(e.prop("manner") and e.prop("peak") and e.prop("music") and e.prop("sfx") for e in genres)
    assert all(e.prop("shot").split(",")[0] in CAMERA for e in hands)
