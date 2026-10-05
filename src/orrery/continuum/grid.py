"""MiniMax H3's frame grid: 17k+5 frames at 24 fps, one frame in the first latent slot of every five
and four in the others, and the audio latent at 40 ticks a second.

Adapted from ComfyUI-H3-Continuum's temporal.py (MIT, see the package docstring).
"""

from dataclasses import dataclass
from fractions import Fraction

FPS = 24
AUDIO_LATENT_FPS = 40
FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
CONTEXT = 22  # the frames Orrery Continue pins: the one length Continuum validated with sound
DECODE_BLEND = 5  # the frames H3's VAE blends where two of its 17-frame decode pieces meet (a clip's last 5 are left unblended)
_TICKS_PER_FRAME = Fraction(AUDIO_LATENT_FPS, FPS)


def is_valid_frame_count(frames: int) -> bool:
    return frames >= 5 and frames % 17 == 5


def video_latent_t(frames: int) -> int:
    if not is_valid_frame_count(frames):
        raise ValueError(f"H3 frame counts are 17k+5; {frames} is not one")
    return 2 if frames <= 5 else (frames - 5) // 17 * 5 + 2


def pixel_frames_for_latent_t(latent_t: int) -> int:
    if latent_t < 1:
        raise ValueError("a video latent has at least one slot")
    return sum(FRAME_PER_TOKEN[i % 5] for i in range(latent_t))


def context_slots(frames: int) -> int:
    """The latent slots that hold the first `frames` frames (5 → 2, 22 → 7, 39 → 12)."""
    for slots in range(1, 256):
        if pixel_frames_for_latent_t(slots) == frames:
            return slots
        if pixel_frames_for_latent_t(slots) > frames:
            break
    raise ValueError(f"{frames} frames do not fill whole latent slots; use 5, 22 or 39")


def audio_latent_t(frames: int) -> int:
    return round(Fraction(frames) * _TICKS_PER_FRAME)


def audio_grid_offset(frames: int, audio_t: int) -> float:
    """How far the audio latent's end sits from the video's end, in ticks (rounding leaves up to ½)."""
    value = float(Fraction(audio_t) - Fraction(frames) * _TICKS_PER_FRAME)
    return 0.0 if abs(value) < 1e-9 else value


@dataclass(frozen=True)
class Window:
    """The last `context` frames of a clip: latent slots [video_start, video_stop), audio ticks
    [audio_start, audio_stop)."""

    video_start: int
    video_stop: int
    audio_start: int
    audio_stop: int
    grid_offset: float


def context_window(source_frames: int, audio_t: int, context: int = CONTEXT) -> Window:
    if not is_valid_frame_count(source_frames):
        raise ValueError(f"the clip has {source_frames} frames, which is off H3's 17k+5 grid")
    if context not in (5, 22, 39) or context > source_frames:
        raise ValueError(f"a {source_frames}-frame clip has no {context}-frame tail")
    stop = video_latent_t(source_frames)
    start = stop - context_slots(context)
    if start < 0 or start % len(FRAME_PER_TOKEN):
        raise ValueError("the tail does not start at the beginning of a latent cycle")
    offset = audio_grid_offset(source_frames, audio_t)
    if not -0.500001 <= offset <= 0.500001:
        raise ValueError(f"the audio latent is {offset:.3f} ticks off the picture's end")
    ticks = audio_latent_t(context)
    if audio_t < ticks:
        raise ValueError("the audio latent is shorter than the tail")
    return Window(start, stop, audio_t - ticks, audio_t, offset)
