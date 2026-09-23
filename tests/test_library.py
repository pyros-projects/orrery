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
    (tmp_path / "notes.txt").write_text("ignored")
    assert sorted(load_libraries(tmp_path)) == ["animal", "style"]
