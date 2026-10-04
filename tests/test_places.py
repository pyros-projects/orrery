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
