import json

import av
import pytest
from PIL import Image

from orrery.galaxy import (
    FACTORS,
    add_collection,
    cards,
    collect,
    collections,
    collections_of,
    day_of,
    delete,
    delete_collection,
    export,
    media_path,
    rate,
    read_rows,
    rename_collection,
    row_id,
    thumbnail,
    tree,
    uncollect,
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


def test_collect_adds_a_collection_and_keeps_the_others(home, tmp_path):
    a, b, c = three(home, tmp_path)
    assert collect(Home(home), [a, b], " portraits / Demons ") == 2
    collect(Home(home), [a], "cats")
    got = rows_by_id(home)
    assert got[a]["collections"] == ["portraits/Demons", "cats"] and got[b]["collections"] == ["portraits/Demons"]
    assert "collections" not in got[c]
    assert uncollect(Home(home), [a], "cats") == 1
    assert rows_by_id(home)[a]["collections"] == ["portraits/Demons"]
    uncollect(Home(home), [a, b], "portraits/Demons")
    assert "collections" not in rows_by_id(home)[a]
    assert collections(Home(home)) == [{"path": "cats", "count": 0}, {"path": "portraits", "count": 0},
                                       {"path": "portraits/Demons", "count": 0}]  # emptied, still there


def test_collect_rejects_unknown_ids_no_ids_bad_names_and_the_sweeps_folder(home, tmp_path):
    a, _, _ = three(home, tmp_path)
    with pytest.raises(KeyError):
        collect(Home(home), [a, "000000000000"], "x")
    with pytest.raises(ValueError):
        collect(Home(home), [], "x")
    for bad in ("a//b", "../up", "a/./b", "x" * 61, "tab\there", "", "sweeps/mine", "sweeps"):
        with pytest.raises(ValueError):
            collect(Home(home), [a], bad)
    with pytest.raises(KeyError):
        uncollect(Home(home), [a], "never")
    assert "collections" not in rows_by_id(home)[a]


def test_collections_list_saved_and_used_ones_with_parents_and_own_counts(home, tmp_path):
    a, b, _ = three(home, tmp_path)
    add_collection(Home(home), "empty")
    collect(Home(home), [a], "x/y/z")
    collect(Home(home), [a, b], "x")
    assert collections(Home(home)) == [{"path": "empty", "count": 0}, {"path": "x", "count": 2},
                                       {"path": "x/y", "count": 0}, {"path": "x/y/z", "count": 1}]
    with pytest.raises(FileExistsError):
        add_collection(Home(home), "x/y")
    with pytest.raises(ValueError):
        add_collection(Home(home), " / ")


def test_a_folder_of_the_time_before_collections_is_a_collection_and_a_sweeps_folder_an_album(home, tmp_path):
    old, sweep, plain = (row(image(tmp_path, f"{n}.png", (32, 32)), seed=i) for i, n in enumerate("abc", 1))
    old["folder"], sweep["folder"] = "foxes/snow", "sweeps/$view 2026-10-04 16.28"
    write_rows(home, [old, sweep, plain])
    (home / "galaxy_folders.json").write_text(json.dumps(["kept", "sweeps/$s 2026-10-03 07.08"]))
    a, b, _ = (row_id(r) for r in (old, sweep, plain))
    assert collections_of(rows_by_id(home)[a]) == ["foxes/snow"] and collections_of(rows_by_id(home)[b]) == []
    assert [c["path"] for c in collections(Home(home))] == ["foxes", "foxes/snow", "kept"]
    collect(Home(home), [a, b], "best")  # a row that changes keeps its folder as a collection
    got = rows_by_id(home)
    assert "folder" not in got[a] and got[a]["collections"] == ["foxes/snow", "best"]
    assert got[b]["folder"] == "sweeps/$view 2026-10-04 16.28" and got[b]["collections"] == ["best"]


def test_renaming_a_collection_moves_its_collections_and_outputs(home, tmp_path):
    a, b, c = three(home, tmp_path)
    collect(Home(home), [a], "a/b")
    collect(Home(home), [b], "a/b/deep")
    collect(Home(home), [c], "a/bb")
    collect(Home(home), [c], "a/b")
    add_collection(Home(home), "c")
    rename_collection(Home(home), "a/b", "c/b")
    got = rows_by_id(home)
    assert (got[a]["collections"], got[b]["collections"], got[c]["collections"]) == (["c/b"], ["c/b/deep"], ["a/bb", "c/b"])
    assert [f["path"] for f in collections(Home(home))] == ["a", "a/bb", "c", "c/b", "c/b/deep"]


def test_a_collection_cannot_move_into_itself_or_onto_another(home, tmp_path):
    a, b, _ = three(home, tmp_path)
    collect(Home(home), [a], "a")
    collect(Home(home), [b], "b")
    with pytest.raises(ValueError):
        rename_collection(Home(home), "a", "a/inside")
    with pytest.raises(FileExistsError):
        rename_collection(Home(home), "a", "b")
    with pytest.raises(KeyError):
        rename_collection(Home(home), "nope", "c")


def test_deleting_a_collection_lets_its_outputs_go_and_moves_its_collections_up(home, tmp_path):
    a, b, c = three(home, tmp_path)
    collect(Home(home), [a], "top/mid")
    collect(Home(home), [b], "top/mid/low")
    collect(Home(home), [a, c], "solo")
    assert delete_collection(Home(home), "top/mid") == "top"
    got = rows_by_id(home)
    assert (got[a]["collections"], got[b]["collections"]) == (["solo"], ["top/low"])
    delete_collection(Home(home), "solo")
    got = rows_by_id(home)
    assert "collections" not in got[a] and "collections" not in got[c]
    assert len(got) == 3  # the outputs stay in the gallery
    assert [f["path"] for f in collections(Home(home))] == ["top", "top/low"]
    with pytest.raises(KeyError):
        delete_collection(Home(home), "solo")


def test_a_day_is_the_viewers_day():
    assert day_of("2026-10-04T23:30:00+00:00") == "2026-10-04"
    assert day_of("2026-10-04T23:30:00+00:00", 120) == "2026-10-05"  # two hours east of UTC: past midnight
    assert day_of("2026-10-04T00:30:00+00:00", -60) == "2026-10-03"
    assert day_of(None) == day_of("yesterday") == ""


def test_sweeps_and_reels_are_albums_and_a_reels_scenes_albums_inside_it():
    def r(n, ts, **more):
        return {"id": n, "ts": f"2026-10-04T10:{ts:02d}:00+00:00", "kind": "image", **more}
    rows = [r("s1", 50, folder="sweeps/$view 1"), r("s2", 49, folder="sweeps/$view 1"),
            r("lone", 48), r("c1", 47, chunks=3, segment=1, chain="reels/fox", chunk=0, kind="video"),
            r("c2", 46, chunks=3, segment=0, chain="reels/fox", chunk=0, kind="video"),
            r("c3", 45, chunks=3, segment=2, chain="reels/fox", chunk=1, kind="video"),
            r("one", 44, folder="sweeps/$view 2"),  # a sweep of one: the output itself
            r("old1", 43, chunks=2, segment=0, preset="pyro/routine", seed="7"), r("old2", 42, chunks=2, segment=1, preset="pyro/routine", seed="7")]
    top = cards(rows)
    assert [(c["kind"], c.get("key") or c["id"]) for c in top] == [
        ("album", "sweep:sweeps/$view 1"), ("row", "lone"), ("album", "reel:reels/fox"), ("row", "one"), ("album", "reel:pyro/routine|7")]
    sweep, reel = top[0], top[2]
    assert (sweep["count"], sweep["ids"], sweep["previews"], sweep["videos"]) == (2, ["s1", "s2"], ["s1", "s2"], 0)
    assert (reel["type"], reel["count"], reel["videos"], reel["ts"]) == ("reel", 3, 3, "2026-10-04T10:47:00+00:00")
    inside = cards([x for x in rows if x.get("chain") == "reels/fox"], "reel:reels/fox")
    assert [(c["kind"], c.get("key") or c["id"]) for c in inside] == [("album", "scene:reels/fox|0"), ("row", "c3")]
    assert [c["id"] for c in cards(rows[:2], "sweep:sweeps/$view 1")] == ["s1", "s2"]  # inside a sweep: the outputs
    many = [r(f"p{i}", 59 - i, folder="sweeps/big", kind="none" if i == 0 else "image") for i in range(12)]
    assert cards(many)[0]["previews"] == [f"p{i}" for i in range(1, 9)]  # eight pictures, none without a file


def test_the_tree_counts_every_output_its_pictures_its_videos_and_each_day():
    rows = [{"ts": "2026-10-04T10:00:00+00:00", "kind": "image"}, {"ts": "2026-10-04T11:00:00+00:00", "kind": "video"},
            {"ts": "2026-10-03T23:30:00+00:00", "kind": "image"}, {"ts": "2026-10-03T09:00:00+00:00", "kind": "none"}]
    assert tree(rows) == {"total": 4, "images": 2, "videos": 1, "days": [
        {"day": "2026-10-04", "total": 2, "images": 1, "videos": 1}, {"day": "2026-10-03", "total": 2, "images": 1, "videos": 0}]}
    assert [d["day"] for d in tree(rows, 60)["days"]] == ["2026-10-04", "2026-10-03"]
    assert tree(rows, 60)["days"][0]["total"] == 3  # 23:30 UTC is past midnight an hour east


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


def test_one_writer_at_a_time_for_the_log_and_the_weights(home, tmp_path):
    """#260: a run's outputs appended while a rating rewrote galaxy.jsonl were lost; both hold one lock now."""
    import threading

    from orrery.comfy import log_outputs
    from orrery.home import STATE

    r = row(image(tmp_path, "a.png"))
    write_rows(home, [r])
    done = {}
    with STATE:  # a rating (or a rename) is writing
        logger = threading.Thread(target=lambda: done.setdefault("log", log_outputs(Home(home), json.dumps({"seed": 2, "picks": []}), ["b.png"])))
        rater = threading.Thread(target=lambda: done.setdefault("rate", rate(Home(home), row_id(r), "love")))
        logger.start()
        rater.start()
        logger.join(0.3)
        rater.join(0.3)
        assert done == {}  # both wait
    logger.join(5)
    rater.join(5)
    assert set(done) == {"log", "rate"} and len(read_rows(Home(home))) == 2  # the logged row survived the rating


def test_writers_of_one_file_never_share_a_temp_file(tmp_path):
    """#260: every write went through `<name>.tmp`; two at once could replace each other's half-written file."""
    import threading

    from orrery.home import write_atomic

    path, errors = tmp_path / "galaxy.jsonl", []

    def write(k):
        try:
            for i in range(200):
                write_atomic(path, f"{k}-{i}\n" * 50)
        except Exception as err:  # noqa: BLE001 - what the test is about
            errors.append(err)

    threads = [threading.Thread(target=write, args=(k,)) for k in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    text = path.read_text()
    assert not errors and len(set(text.splitlines())) == 1 and len(text.splitlines()) == 50  # one write, whole
    assert [p.name for p in tmp_path.iterdir()] == ["galaxy.jsonl"]  # no temp file left behind
