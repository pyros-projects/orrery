import json

import av
import pytest
from PIL import Image

from orrery.galaxy import (
    FACTORS,
    add_folder,
    delete,
    delete_folder,
    export,
    folders,
    media_path,
    move,
    rate,
    read_rows,
    rename_folder,
    row_id,
    thumbnail,
)
from orrery.home import Home


def image(tmp_path, name, size=(832, 1216)):
    path = tmp_path / name
    Image.new("RGB", size, "teal").save(path)
    return str(path)


def row(media, seed=1, template="aaaaaaaaaaaaaaaa", keys=("__animal__=fox",), rating=None):
    return {"ts": "2026-09-24T00:00:00+00:00", "media": media, "seed": seed, "target": "text",
            "template": template, "text": "a fox", "rating": rating,
            "picks": [{"label": "__animal__", "value": "fox", "keys": list(keys)}]}


def write_rows(home, rows):
    (home / "galaxy.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_rows_carry_stable_ids_and_come_newest_first(home, tmp_path):
    a, b = row(image(tmp_path, "a.png"), seed=1), row(image(tmp_path, "b.png"), seed=2)
    write_rows(home, [a, b])
    rows = read_rows(Home(home))
    assert [r["seed"] for r in rows] == [2, 1]
    assert rows[1]["id"] == row_id(a) and len(row_id(a)) == 12
    assert read_rows(Home(home))[0]["id"] == rows[0]["id"]


def test_an_empty_home_has_no_rows(home):
    assert read_rows(Home(home)) == []


def test_love_multiplies_every_pick_key(home, tmp_path):
    r = row(image(tmp_path, "a.png"), keys=("__animal__=fox", "{a|b}=a"))
    write_rows(home, [r])
    updated, weights = rate(Home(home), row_id(r), "love")
    assert updated["rating"] == "love"
    assert weights == {"__animal__=fox": FACTORS["love"], "{a|b}=a": FACTORS["love"]}
    assert Home(home).weights()["__animal__=fox"] == pytest.approx(1.5)
    assert read_rows(Home(home))[0]["rating"] == "love"


def test_rerating_replaces_the_old_factor_and_clearing_restores(home, tmp_path):
    r = row(image(tmp_path, "a.png"))
    write_rows(home, [r])
    Home(home).save_weights({"__animal__=fox": 2.0})
    rate(Home(home), row_id(r), "love")
    _, weights = rate(Home(home), row_id(r), "hate")
    assert weights["__animal__=fox"] == pytest.approx(1.0)
    _, weights = rate(Home(home), row_id(r), None)
    assert weights["__animal__=fox"] == pytest.approx(2.0)


def test_ratings_taken_back_leave_the_weight_as_it_was_whatever_their_number_and_order(home, tmp_path):
    """#257: twenty outputs with one pick, hated and cleared, left it at 104.86 when each step rounded to four places."""
    rows = [row(image(tmp_path, f"{i}.png", size=(8, 8)), seed=i) for i in range(20)]
    write_rows(home, rows)
    Home(home).save_weights({"__animal__=fox": 2.0})
    for r in rows:
        rate(Home(home), row_id(r), "hate")
    assert Home(home).weights()["__animal__=fox"] == pytest.approx(2.0 * 0.5 ** 20)  # no floor
    for r in rows:
        rate(Home(home), row_id(r), None)
    assert Home(home).weights() == {"__animal__=fox": 2.0}
    order = ["love", "hate", "like", "nope", "love", "hate", "like", "nope"] * 2
    for r, rating in zip(rows, order, strict=False):
        rate(Home(home), row_id(r), rating)
    forward = Home(home).weights()["__animal__=fox"]
    for r in rows:
        rate(Home(home), row_id(r), None)
    for r, rating in reversed(list(zip(rows, order, strict=False))):
        rate(Home(home), row_id(r), rating)
    assert Home(home).weights()["__animal__=fox"] == forward  # the same ratings, the other way round
    for r in rows:
        rate(Home(home), row_id(r), None)
    assert Home(home).weights() == {"__animal__=fox": 2.0}


def test_a_weight_back_at_one_leaves_the_file(home, tmp_path):
    r = row(image(tmp_path, "a.png"))
    write_rows(home, [r])
    rate(Home(home), row_id(r), "like")
    rate(Home(home), row_id(r), None)
    assert Home(home).weights() == {}


def test_rating_leaves_other_lines_untouched(home, tmp_path):
    lines = ['{"ts": "x", "media": null, "seed": 9, "picks": [], "rating": null, "extra": 1}',
             "not json at all", json.dumps(row(image(tmp_path, "a.png")))]
    (home / "galaxy.jsonl").write_text("\n".join(lines) + "\n")
    rate(Home(home), row_id(json.loads(lines[2])), "nope")
    out = (home / "galaxy.jsonl").read_text().splitlines()
    assert out[:2] == lines[:2]
    assert json.loads(out[2])["rating"] == "nope"
    assert not list(home.glob("*.tmp"))


def test_unknown_ratings_and_ids_are_rejected(home, tmp_path):
    r = row(image(tmp_path, "a.png"))
    write_rows(home, [r])
    with pytest.raises(ValueError):
        rate(Home(home), row_id(r), "meh")
    with pytest.raises(KeyError):
        rate(Home(home), "000000000000", "love")


def test_thumbnail_is_a_small_cached_webp(home, tmp_path):
    r = row(image(tmp_path, "a.png"))
    write_rows(home, [r])
    thumb = thumbnail(Home(home), row_id(r))
    assert thumb == home / "thumbs" / f"{row_id(r)}.webp"
    with Image.open(thumb) as im:
        assert im.format == "WEBP" and max(im.size) == 384
    mtime = thumb.stat().st_mtime_ns
    assert thumbnail(Home(home), row_id(r)).stat().st_mtime_ns == mtime


def clip(tmp_path, name="clip.mp4"):
    """48 frames at 24 fps: red, then green, then blue, a third each."""
    path = tmp_path / name
    with av.open(str(path), "w") as out:
        stream = out.add_stream("mpeg4", rate=24)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for i in range(48):
            color = (255, 0, 0) if i < 16 else (0, 255, 0) if i < 32 else (0, 0, 255)
            for packet in stream.encode(av.VideoFrame.from_image(Image.new("RGB", (64, 48), color))):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return str(path)


def test_video_thumbnail_is_the_frame_a_third_in(home, tmp_path):
    r = row(clip(tmp_path))
    write_rows(home, [r])
    with Image.open(thumbnail(Home(home), row_id(r))) as im:
        assert im.format == "WEBP"
        red, green, blue = im.convert("RGB").getpixel((im.width // 2, im.height // 2))
    assert green > 150 and red < 100 and blue < 100


def test_broken_and_missing_media_have_no_thumbnail(home, tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"\x00")
    rows = [row(str(broken), seed=1), row(str(tmp_path / "gone.png"), seed=2), row(None, seed=3)]
    write_rows(home, rows)
    for r in rows:
        with pytest.raises(KeyError):
            thumbnail(Home(home), row_id(r))
    assert media_path(Home(home), row_id(rows[0])) == broken
    assert [r["kind"] for r in read_rows(Home(home))] == ["none", "image", "video"]


def test_media_is_served_only_for_recorded_rows(home, tmp_path):
    r = row(image(tmp_path, "a.png"))
    write_rows(home, [r])
    assert media_path(Home(home), row_id(r)).name == "a.png"
    with pytest.raises(KeyError):
        media_path(Home(home), "../../etc/pa")


# --- folders, delete, export ---------------------------------------------------------------

def rows_by_id(home):
    return {r["id"]: r for r in read_rows(Home(home))}


def three(home, tmp_path):
    rs = [row(image(tmp_path, f"{n}.png", (32, 32)), seed=i) for i, n in enumerate("abc", 1)]
    write_rows(home, rs)
    return [row_id(r) for r in rs]


def test_move_sets_and_clears_a_folder_and_keeps_the_folder(home, tmp_path):
    a, b, c = three(home, tmp_path)
    assert move(Home(home), [a, b], " portraits / Demons ") == 2
    got = rows_by_id(home)
    assert got[a]["folder"] == got[b]["folder"] == "portraits/Demons" and "folder" not in got[c]
    move(Home(home), [a, b], "")
    assert "folder" not in rows_by_id(home)[a]
    assert folders(Home(home)) == [{"path": "portraits", "count": 0}, {"path": "portraits/Demons", "count": 0}]


def test_move_rejects_unknown_ids_no_ids_and_bad_folder_names(home, tmp_path):
    a, _, _ = three(home, tmp_path)
    with pytest.raises(KeyError):
        move(Home(home), [a, "000000000000"], "x")
    with pytest.raises(ValueError):
        move(Home(home), [], "x")
    for bad in ("a//b", "../up", "a/./b", "x" * 61, "tab\there"):
        with pytest.raises(ValueError):
            move(Home(home), [a], bad)
    assert "folder" not in rows_by_id(home)[a]


def test_folders_list_saved_and_used_ones_with_parents_and_own_counts(home, tmp_path):
    a, b, _ = three(home, tmp_path)
    add_folder(Home(home), "empty")
    move(Home(home), [a], "x/y/z")
    move(Home(home), [b], "x")
    assert folders(Home(home)) == [{"path": "empty", "count": 0}, {"path": "x", "count": 1},
                                   {"path": "x/y", "count": 0}, {"path": "x/y/z", "count": 1}]
    with pytest.raises(FileExistsError):
        add_folder(Home(home), "x/y")
    with pytest.raises(ValueError):
        add_folder(Home(home), " / ")


def test_renaming_a_folder_moves_its_subfolders_and_outputs(home, tmp_path):
    a, b, c = three(home, tmp_path)
    move(Home(home), [a], "a/b")
    move(Home(home), [b], "a/b/deep")
    move(Home(home), [c], "a/bb")
    add_folder(Home(home), "c")
    rename_folder(Home(home), "a/b", "c/b")
    got = rows_by_id(home)
    assert (got[a]["folder"], got[b]["folder"], got[c]["folder"]) == ("c/b", "c/b/deep", "a/bb")
    assert [f["path"] for f in folders(Home(home))] == ["a", "a/bb", "c", "c/b", "c/b/deep"]


def test_a_folder_cannot_move_into_itself_or_onto_another(home, tmp_path):
    a, b, _ = three(home, tmp_path)
    move(Home(home), [a], "a")
    move(Home(home), [b], "b")
    with pytest.raises(ValueError):
        rename_folder(Home(home), "a", "a/inside")
    with pytest.raises(FileExistsError):
        rename_folder(Home(home), "a", "b")
    with pytest.raises(KeyError):
        rename_folder(Home(home), "nope", "c")


def test_deleting_a_folder_moves_its_contents_up_one_level(home, tmp_path):
    a, b, c = three(home, tmp_path)
    move(Home(home), [a], "top/mid")
    move(Home(home), [b], "top/mid/low")
    move(Home(home), [c], "solo")
    delete_folder(Home(home), "top/mid")
    got = rows_by_id(home)
    assert (got[a]["folder"], got[b]["folder"]) == ("top", "top/low")
    delete_folder(Home(home), "solo")
    assert "folder" not in rows_by_id(home)[c]
    assert [f["path"] for f in folders(Home(home))] == ["top", "top/low"]
    with pytest.raises(KeyError):
        delete_folder(Home(home), "solo")


def test_delete_drops_rows_moves_files_to_the_trash_and_keeps_weights(home, tmp_path):
    a, b, c = three(home, tmp_path)
    rate(Home(home), a, "love")
    thumbnail(Home(home), a)
    (home / "trash").mkdir()
    (home / "trash" / "a.png").write_bytes(b"older")
    assert delete(Home(home), [a, b]) == 2
    assert list(rows_by_id(home)) == [c]
    assert sorted(p.name for p in (home / "trash").iterdir()) == ["a.png", "a_2.png", "b.png"]
    assert not (tmp_path / "a.png").exists() and (tmp_path / "c.png").exists()
    assert not (home / "thumbs" / f"{a}.webp").exists()
    assert Home(home).weights()["__animal__=fox"] == pytest.approx(1.5)


def test_delete_keeps_a_file_another_row_still_shows_and_forgives_a_missing_one(home, tmp_path):
    shared = image(tmp_path, "shared.png", (32, 32))
    rs = [row(shared, seed=1), row(shared, seed=2), row(str(tmp_path / "gone.png"), seed=3)]
    write_rows(home, rs)
    delete(Home(home), [row_id(rs[0]), row_id(rs[2])])
    assert (tmp_path / "shared.png").exists()
    assert list(rows_by_id(home)) == [row_id(rs[1])]


def test_export_writes_media_and_prompt_sidecar_pairs(home, tmp_path):
    a, b, _ = three(home, tmp_path)
    video = row(clip(tmp_path), seed=7)
    missing = row(str(tmp_path / "gone.png"), seed=8)
    rs = [json.loads(line) for line in (home / "galaxy.jsonl").read_text().splitlines()] + [video, missing]
    rs[0]["text"] = "  a fox in the snow\n"
    write_rows(home, rs)
    out = export(Home(home), [a, b, row_id(video), row_id(missing)], "fox set")
    assert out == {"path": str(home / "export" / "fox set"), "exported": 3, "skipped": 1}
    folder = home / "export" / "fox set"
    assert sorted(p.name for p in folder.iterdir()) == ["a.png", "a.txt", "b.png", "b.txt", "clip.mp4", "clip.txt"]
    assert (folder / "a.txt").read_text(encoding="utf-8") == "a fox in the snow\n"
    assert (folder / "a.png").read_bytes() == (tmp_path / "a.png").read_bytes()
    export(Home(home), [a], "fox set")
    assert (folder / "a_2.png").exists() and (folder / "a_2.txt").exists()


def test_export_names_are_one_plain_folder(home, tmp_path):
    a, _, _ = three(home, tmp_path)
    for bad in ("", "../x", "a/b", ".hidden", "x" * 81):
        with pytest.raises(ValueError):
            export(Home(home), [a], bad)
    assert not (home / "export").exists()
