import json

import av
import pytest
from PIL import Image

from orrery.galaxy import FACTORS, media_path, rate, read_rows, row_id, thumbnail
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
