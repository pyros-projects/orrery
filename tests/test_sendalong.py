"""Send along (#335): what goes to the language model beside a request, as pictures told what they are."""

import json

import av
import pytest
from PIL import Image

from orrery import sendalong
from orrery.home import Home


def clip(path, n=48):
    """N frames at 24 fps: red, then green, then blue, a third each."""
    with av.open(str(path), "w") as out:
        stream = out.add_stream("mpeg4", rate=24)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for i in range(n):
            color = (255, 0, 0) if i < n // 3 else (0, 255, 0) if i < 2 * n // 3 else (0, 0, 255)
            for packet in stream.encode(av.VideoFrame.from_image(Image.new("RGB", (64, 48), color))):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return path


def test_the_sources_are_named_once_each_and_nothing_else():
    assert sendalong.parse(None) is None
    assert sendalong.parse(["prompt", "first_frame", "prompt", "gallery:abc"]) == ["prompt", "first_frame", "gallery:abc"]
    for bad in (["the moon"], ["gallery:"], "prompt", [3]):
        with pytest.raises(ValueError):
            sendalong.parse(bad)


def test_a_video_goes_as_four_stills_from_its_start_to_its_end(tmp_path):
    stills = sendalong.file_stills(clip(tmp_path / "rgb.mp4"))
    assert len(stills) == 4
    first, last = stills[0].getpixel((32, 24)), stills[-1].getpixel((32, 24))
    assert first[0] > 200 > first[2] and last[2] > 200 > last[0]  # red at the start, blue at the end
    assert len(sendalong.file_stills(clip(tmp_path / "short.mp4", n=3))) == 3  # a shorter one: every frame


def test_the_pictures_sent_along_are_told_what_they_are(home, tmp_path):
    frame = tmp_path / "first.png"
    Image.new("RGB", (40, 30), "orange").save(frame)
    picture, video = tmp_path / "gallery.png", clip(tmp_path / "gallery.mp4")
    Image.new("RGB", (40, 30), "teal").save(picture)
    (home / "galaxy.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (
        {"ts": "2026-10-05T10:00:00+00:00", "media": str(picture), "seed": 1, "text": "a"},
        {"ts": "2026-10-05T10:01:00+00:00", "media": str(video), "seed": 2, "text": "b"})))
    from orrery import galaxy

    ids = {r["media"]: r["id"] for r in galaxy.read_rows(Home(home))}
    sends = ["first_frame", "video", f"gallery:{ids[str(picture)]}", f"gallery:{ids[str(video)]}"]
    shown, labels, missing = sendalong.pictures(Home(home), sends, {"first_frame": frame}, clip(tmp_path / "input.mp4"))
    assert labels == ["the first frame", *[f"still {k} of 4 of the input video" for k in range(1, 5)],
                      "a picture from the gallery", *[f"still {k} of 4 of a video from the gallery" for k in range(1, 5)]]
    assert len(shown) == len(labels) and missing == []
    _, _, missing = sendalong.pictures(Home(home), ["last_frame", "video", "gallery:nope"], {}, None)
    assert missing == ["nothing is wired into the Orrery Prompt's last_frame", "nothing is wired into the Orrery Prompt's video",
                       "the gallery has no file for nope"]
