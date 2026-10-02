"""Contact sheets of the A/B/C runs: one row per variant, five frames across one segment.

    python experiments/refmod-abc/sheets.py <ComfyUI output folder> <sheet.jpg> <segment> "<title>" \\
        A=abc_a C=abc_c late=abc_c_late35 ...

Each LABEL=LATENT_PATH row reads the active run of output/<latent_path>/orrery_film (Orrery Film's
store), and the sheet shows frames 0, 60, 120, 180 and the last of that segment's take. Needs av
and Pillow (the dev dependencies).
"""

import json
import sys
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

PICK = (0, 60, 120, 180, -1)
NAMES = ("frame 0", "frame 60", "frame 120", "frame 180", "last frame")
W, H, LEFT, TOP = 320, 180, 110, 44


def frames(output: Path, latent_path: str, segment: int) -> list:
    store = output / latent_path / "orrery_film"
    run = store / json.loads((store / "active.json").read_text())["run"]
    clips = json.loads((run / "clips.json").read_text())["clips"]
    with av.open(str(run / clips[segment]["folder"] / "video.mp4")) as video:
        decoded = [frame.to_image() for frame in video.decode(video=0)]
    return [decoded[i] for i in PICK]


def sheet(output: Path, path: Path, segment: int, title: str, rows: list[tuple[str, str]]) -> None:
    font, small = ImageFont.load_default(size=18), ImageFont.load_default(size=14)
    img = Image.new("RGB", (LEFT + W * len(PICK), TOP + 18 + H * len(rows)), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), title, fill="black", font=font)
    for k, name in enumerate(NAMES):
        draw.text((LEFT + k * W + 6, TOP - 4), name, fill="#555", font=small)
    for r, (label, latent_path) in enumerate(rows):
        y = TOP + 18 + r * H
        draw.text((10, y + H // 2 - 10), label, fill="black", font=font)
        for k, frame in enumerate(frames(output, latent_path, segment)):
            img.paste(frame.resize((W, H)), (LEFT + k * W, y))
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
