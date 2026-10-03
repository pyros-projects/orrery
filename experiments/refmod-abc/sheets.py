"""Contact sheets of the A/B/C runs: one row per variant, five frames across one segment.

    python experiments/refmod-abc/sheets.py <ComfyUI output folder> <sheet.jpg> <segment> "<title>" \\
        A=abc_a C=abc_c late=abc_c_late35 ...

Each LABEL=LATENT_PATH row reads the active run of output/<latent_path>/orrery_film (Orrery Film's
store); a LABEL=FILE.mp4 row reads that clip instead (a Save Video file, the segment is then
ignored). The sheet shows five frames spread over the clip, from its first to its last, in the clip's
own shape. Needs av and Pillow (the dev dependencies).
"""

import json
import sys
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

SPOTS = (0.0, 0.25, 0.5, 0.75, 1.0)  # where in the clip: its first frame, a quarter … its last
W, LEFT, TOP = 320, 110, 44  # a landscape frame's width; a portrait one gets 5/8 of it


def frames(output: Path, latent_path: str, segment: int) -> list:
    if latent_path.endswith(".mp4"):
        clip = Path(latent_path) if Path(latent_path).is_absolute() else output / latent_path
    else:
        store = output / latent_path / "orrery_film"
        run = store / json.loads((store / "active.json").read_text())["run"]
        clips = json.loads((run / "clips.json").read_text())["clips"]
        clip = run / clips[segment]["folder"] / "video.mp4"
    with av.open(str(clip)) as video:
        decoded = [frame.to_image() for frame in video.decode(video=0)]
    last = len(decoded) - 1
    return [(round(s * last), decoded[round(s * last)]) for s in SPOTS]


def sheet(output: Path, path: Path, segment: int, title: str, rows: list[tuple[str, str]]) -> None:
    font, small = ImageFont.load_default(size=18), ImageFont.load_default(size=14)
    picked = [frames(output, latent_path, segment) for _, latent_path in rows]
    first = picked[0][0][1]
    w = W if first.width >= first.height else W * 5 // 8
    h = round(w * first.height / first.width)
    img = Image.new("RGB", (LEFT + w * len(SPOTS), TOP + 18 + h * len(rows)), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), title, fill="black", font=font)
    for k, (index, _) in enumerate(picked[0]):
        name = "last frame" if k == len(SPOTS) - 1 else f"frame {index}"
        draw.text((LEFT + k * w + 6, TOP - 4), name, fill="#555", font=small)
    for r, ((label, _), row) in enumerate(zip(rows, picked, strict=True)):
        y = TOP + 18 + r * h
        draw.text((10, y + h // 2 - 10), label, fill="black", font=font)
        for k, (_, frame) in enumerate(row):
            img.paste(frame.resize((w, h)), (LEFT + k * w, y))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=82)
    print(f"{path} ({path.stat().st_size // 1024} KB)")


def main() -> None:
    if len(sys.argv) < 6 or not all("=" in row for row in sys.argv[5:]):
        sys.exit(__doc__)
    output, path, segment, title = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    sheet(output, path, segment, title, [tuple(row.split("=", 1)) for row in sys.argv[5:]])


if __name__ == "__main__":
    main()
