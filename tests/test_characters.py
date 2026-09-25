import pytest

from orrery.dsl import expand
from orrery.home import BUILTIN_DIR, Home
from orrery.library import load_libraries

BUILTIN = load_libraries(BUILTIN_DIR)
SETS = sorted(n for n in BUILTIN if n.startswith("characters/") and n.count("/") == 1)


@pytest.mark.parametrize("name", sorted(BUILTIN))
def test_every_builtin_library_expands_clean(home, name):
    libs = Home(home).libraries()
    for seed in range(40):
        text = expand(f"__{name}__", seed, libs).text
        assert "__" not in text and "{" not in text and "$" not in text and "  " not in text, (seed, text)


@pytest.mark.parametrize("name", SETS)
def test_every_character_set_has_ten_people_with_gender_and_age(name):
    entries = BUILTIN[name].entries
    assert len(entries) == 10
    assert all(e.prop("gender") and e.prop("age") for e in entries), name


def test_the_sets_can_be_filtered_by_gender(home):
    libs = Home(home).libraries()
    for name in SETS:
        for gender in ("female", "male"):
            expand(f"__{name}#gender:{gender}__", 1, libs)  # every set has both


def test_the_curators_live_among_the_horror_characters(home):
    libs = Home(home).libraries()
    names = {expand("__characters/horror#role:curator__", s, libs).text.split(",")[0] for s in range(20)}
    assert names == {"Katamori Shizuka", "Katamori Reiji"}
    assert "curator" not in libs
