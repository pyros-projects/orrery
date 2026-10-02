"""Masked AV continuation: the last 22 frames of a clip, picture and sound (its tail), start the next
clip's latent, and ComfyUI's noise_mask keeps the sampler off them. The conditioning stays as it is.

Adapted from ComfyUI-H3-Continuum's v3/masked_continuation.py, state.py and media.py (MIT, see the
package docstring). It only slices and copies, so numpy arrays work as well as torch tensors; moving
tensors to the right device and dtype is the caller's job.
"""

from dataclasses import dataclass

from orrery.continuum.grid import CONTEXT, FPS, context_window, pixel_frames_for_latent_t


@dataclass(frozen=True)
class Tail:
    video: object  # [1, 24, 7, H/16, W/16]
    audio: object  # [1, 32, 2, 37]
    grid_offset: float

    @property
    def size(self) -> str:
        return f"{self.video.shape[-1] * 16}×{self.video.shape[-2] * 16}"


def _copy(x):
    return x.clone() if hasattr(x, "clone") else x.copy()


def _finite(x) -> bool:
    """No NaN or Inf, for numpy and torch alike: x - x is 0 exactly where x is finite."""
    return bool((x - x == 0).all())


def _check(video, audio) -> None:
    if video.ndim != 5 or audio.ndim != 4 or video.shape[0] != 1 or audio.shape[0] != 1:
        raise ValueError("an H3 latent is one clip: video [1, 24, T, H, W] and audio [1, 32, 2, T]; got "
                         f"{tuple(video.shape)} and {tuple(audio.shape)}")
    if video.shape[1] != 24 or tuple(audio.shape[1:3]) != (32, 2):
        raise ValueError(f"not an H3 latent: video {tuple(video.shape)}, audio {tuple(audio.shape)}")


def tail(video, audio, frames: int, context: int = CONTEXT) -> Tail:
    """The last `context` frames of a clip's latent, which holds `frames` frames; copied."""
    _check(video, audio)
    held = pixel_frames_for_latent_t(int(video.shape[2]))
    if held != frames:
        raise ValueError(f"the latent holds {held} frames, not {frames}")
    w = context_window(frames, int(audio.shape[-1]), context)
    v, a = _copy(video[:, :, w.video_start:w.video_stop]), _copy(audio[..., w.audio_start:w.audio_stop])
    if not (_finite(v) and _finite(a)):
        raise ValueError("the clip's last frames hold NaN or Inf values, so nothing can continue from them")
    return Tail(v, a, w.grid_offset)


def pin(video, audio, video_mask, audio_mask, before: Tail) -> None:
    """Start a new clip's latent with the tail of the clip before, in place, and zero the masks over
    it (0 keeps, 1 generates)."""
    _check(video, audio)
    slots, ticks = int(before.video.shape[2]), int(before.audio.shape[-1])
    if tuple(before.video.shape[-2:]) != tuple(video.shape[-2:]):
        size = f"{video.shape[-1] * 16}×{video.shape[-2] * 16}"
        raise ValueError(f"the clip before is {before.size} and this one {size}: a clip continues at the "
                         "size of the one before (or Restart the reel).")
    if video.shape[2] <= slots or audio.shape[-1] <= ticks:
        frames = pixel_frames_for_latent_t(int(video.shape[2]))
        raise ValueError(f"the clip has {frames} frames; it must be longer than the {CONTEXT} it continues "
                         "from.")
    video[:, :, :slots] = before.video
    audio[..., :ticks] = before.audio
    video_mask[:, :, :slots] = 0
    audio_mask[..., :ticks] = 0


def drift(video, audio, before: Tail) -> float:
    """How far a sampled clip's start moved from the tail it was pinned with: 0 when the mask held."""
    slots, ticks = int(before.video.shape[2]), int(before.audio.shape[-1])
    return float(max(abs(video[:, :, :slots] - before.video).max(), abs(audio[..., :ticks] - before.audio).max()))


def audio_span(trim_frames: int, kept_frames: int, sample_rate: int) -> tuple[int, int]:
    """(first sample, samples) of the sound that goes with the frames kept after `trim_frames`."""
    return round(trim_frames / FPS * sample_rate), round(kept_frames / FPS * sample_rate)
