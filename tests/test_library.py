from orrery.library import Entry, Library, load_libraries, load_library, save_library


def test_plain_list_loads_with_default_weight_and_no_tags(tmp_path):
    p = tmp_path / "animal.yaml"
    p.write_text("- fox\n- heron\n")
    lib = load_library(p)
    assert lib.name == "animal"
    assert lib.entries == [Entry("fox"), Entry("heron")]
    assert lib.entries[0].weight == 1.0 and lib.entries[0].tags == ()


def test_entries_can_carry_tags_and_weight(tmp_path):
    p = tmp_path / "animal.yaml"
    p.write_text("- fox\n- {value: lynx, tags: [feline, wild], weight: 2}\n")
    lynx = load_library(p).entries[1]
    assert (lynx.value, lynx.tags, lynx.weight) == ("lynx", ("feline", "wild"), 2.0)


def test_mapping_form_carries_meta(tmp_path):
    p = tmp_path / "weather.yaml"
    p.write_text("meta: {generated_by: Qwen3.5-2B}\nentries:\n  - first snow\n")
    lib = load_library(p)
    assert lib.meta == {"generated_by": "Qwen3.5-2B"}
    assert lib.values() == ["first snow"]


def test_save_and_load_round_trip(tmp_path):
    lib = Library("feline", [Entry("lynx", ("wild",), 2.0), Entry("tabby cat")], {"generated_by": "x"})
    p = tmp_path / "feline.yaml"
    save_library(lib, p)
    assert load_library(p) == lib


def test_plain_library_saves_as_plain_list(tmp_path):
    p = tmp_path / "style.yaml"
    save_library(Library("style", [Entry("linocut")]), p)
    assert p.read_text().strip() == "- linocut"


def test_load_libraries_keys_by_file_stem(tmp_path):
    (tmp_path / "animal.yaml").write_text("- fox\n")
    (tmp_path / "style.yaml").write_text("- linocut\n")
    (tmp_path / "notes.txt").write_text("a plain wildcard file is a library too")
    (tmp_path / "readme.md").write_text("ignored")
    assert sorted(load_libraries(tmp_path)) == ["animal", "notes", "style"]


# --- folders and .txt, like z-explorer: __film/genre__ is library/film/genre.(yaml|txt) ----------

def test_libraries_live_in_folders_and_plain_text_files(tmp_path):
    from orrery.library import load_libraries
    (tmp_path / "film").mkdir()
    (tmp_path / "film" / "genre.txt").write_text("# genres\nnoir\n\n  western  \nsci-fi\n")
    (tmp_path / "film" / "moods.yaml").write_text("- tense\n- tender\n")
    (tmp_path / "style.txt").write_text("ink\n")
    (tmp_path / "style.yaml").write_text("- gouache\n")
    libs = load_libraries(tmp_path)
    assert set(libs) == {"film/genre", "film/moods", "style"}
    assert libs["film/genre"].values() == ["noir", "western", "sci-fi"] and libs["film/genre"].name == "film/genre"
    assert libs["style"].values() == ["gouache"]


def test_writing_a_library_makes_its_folder_and_retires_a_text_twin(tmp_path):
    from orrery.home import Home
    from orrery.library import Entry, Library
    home = Home(tmp_path)
    (home.library_dir / "film").mkdir(parents=True)
    (home.library_dir / "film" / "genre.txt").write_text("noir\n")
    assert home.library_file("film/genre") == home.library_dir / "film" / "genre.txt"
    home.write_library(Library("film/genre", [Entry("noir", ("dark",))]))
    assert home.library_file("film/genre") == home.library_dir / "film" / "genre.yaml"
    assert not (home.library_dir / "film" / "genre.txt").exists()
    home.write_library(Library("new/deep/list", [Entry("x")]))
    assert (home.library_dir / "new" / "deep" / "list.yaml").exists() and home.library_file("nope") is None
