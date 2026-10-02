"""The continuation core taken from ComfyUI-H3-Continuum (MIT): H3's frame grid, the tail of a
clip and the masked prefix of the next one. numpy stands in for torch; the code only slices."""

import numpy as np
import pytest

from orrery.continuum import grid, masked


def test_the_h3_grid_counts_17k_plus_5_frames_one_and_four_frames_a_slot():
    assert [grid.is_valid_frame_count(f) for f in (5, 22, 141, 140)] == [True, True, True, False]
    assert grid.video_latent_t(141) == 42 and grid.video_latent_t(5) == 2
    assert grid.pixel_frames_for_latent_t(42) == 141
    assert {f: grid.context_slots(f) for f in (5, 22, 39)} == {5: 2, 22: 7, 39: 12}
    assert grid.audio_latent_t(141) == 235 and grid.audio_latent_t(22) == 37  # 40 Hz audio latent
    with pytest.raises(ValueError, match="17k\\+5"):
        grid.video_latent_t(140)


def test_the_context_window_is_the_last_22_frames_of_picture_and_sound():
    w = grid.context_window(141, 235, 22)
    assert (w.video_start, w.video_stop, w.audio_start, w.audio_stop) == (35, 42, 198, 235)
    with pytest.raises(ValueError, match="grid"):
        grid.context_window(140, 235, 22)


def latent(frames, h=3, w=4, fill=0.0):
    video = np.full((1, 24, grid.video_latent_t(frames), h, w), fill, dtype=np.float32)
    audio = np.full((1, 32, 2, grid.audio_latent_t(frames)), fill, dtype=np.float32)
    return video, audio


def test_the_tail_of_a_clip_is_its_last_slots_and_ticks():
    video, audio = latent(141)
    video[:, :, -7:] = 1.0
    audio[..., -37:] = 2.0
    tail = masked.tail(video, audio, 141)
    assert tail.video.shape == (1, 24, 7, 3, 4) and (tail.video == 1.0).all()
    assert tail.audio.shape == (1, 32, 2, 37) and (tail.audio == 2.0).all()
    assert tail.grid_offset == pytest.approx(0.0)


def test_a_clip_shorter_than_the_context_has_no_tail():
    video, audio = latent(5)
    with pytest.raises(ValueError, match="22"):
        masked.tail(video, audio, 5)


def test_the_next_clip_starts_with_the_tail_and_masks_hold_it():
    before = masked.tail(*latent(141, fill=0.5), 141)
    video, audio = latent(158)
    video_mask, audio_mask = np.ones((1, 1, *video.shape[2:]), np.float32), np.ones((1, 1, *audio.shape[2:]), np.float32)
    masked.pin(video, audio, video_mask, audio_mask, before)
    assert (video[:, :, :7] == 0.5).all() and (video[:, :, 7:] == 0).all()
    assert (audio[..., :37] == 0.5).all() and (audio[..., 37:] == 0).all()
    assert (video_mask[:, :, :7] == 0).all() and (video_mask[:, :, 7:] == 1).all()
    assert (audio_mask[..., :37] == 0).all() and (audio_mask[..., 37:] == 1).all()
    assert masked.drift(video, audio, before) == 0.0
    video[:, :, 3] += 0.25
    assert masked.drift(video, audio, before) == pytest.approx(0.25)


def test_a_tail_of_another_size_or_with_nan_is_refused():
    before = masked.tail(*latent(141, h=5), 141)
    video, audio = latent(158)
    masks = np.ones((1, 1, *video.shape[2:]), np.float32), np.ones((1, 1, *audio.shape[2:]), np.float32)
    with pytest.raises(ValueError, match="64×80"):  # the canvas, not the latent
        masked.pin(video, audio, *masks, before)
    video, audio = latent(141)
    video[0, 0, -1, 0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        masked.tail(video, audio, 141)


def test_the_new_clip_must_be_longer_than_what_it_pins():
    before = masked.tail(*latent(141), 141)
    video, audio = latent(22)
    masks = np.ones((1, 1, *video.shape[2:]), np.float32), np.ones((1, 1, *audio.shape[2:]), np.float32)
    with pytest.raises(ValueError, match="longer than the 22"):
        masked.pin(video, audio, *masks, before)


def test_trimming_the_pinned_frames_cuts_the_sound_at_the_same_moment():
    assert masked.audio_span(22, 136, 48000) == (44000, 272000)
    assert masked.audio_span(0, 141, 44100) == (0, 259088)
