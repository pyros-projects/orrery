import json

from orrery.chain import previous_clip


def chain(output, clips, latent_path="h3_context"):
    run = output / latent_path / "chain_video" / "run_1"
    run.mkdir(parents=True)
    (run.parent / "active.json").write_text(json.dumps({"run": "run_1"}))
    folders = [f"clip_{i:05d}_{'a' * 32}" for i in range(1, clips + 1)]
    for folder in folders:
        (run / folder).mkdir()
        (run / folder / "video.mp4").write_bytes(b"")
    (run / "clips.json").write_text(json.dumps({"settings": [], "clips": [{"folder": f, "frames": 120} for f in folders]}))
    return run, folders


def test_segment_n_continues_the_chains_clip_n(tmp_path):
    """Segments count from 0 and Chain Video's clip_index from 1: segment 2 follows clip 2."""
    run, folders = chain(tmp_path, 3)
    assert previous_clip(tmp_path, "h3_context", 2) == run / folders[1] / "video.mp4"


def test_the_first_segment_continues_nothing(tmp_path):
    chain(tmp_path, 3)
    assert previous_clip(tmp_path, "h3_context", 0) is None


def test_a_clip_not_yet_made_is_none(tmp_path):
    chain(tmp_path, 1)
    assert previous_clip(tmp_path, "h3_context", 4) is None


def test_without_a_chain_there_is_no_previous_clip(tmp_path):
    assert previous_clip(tmp_path, "h3_context", 1) is None


def test_a_latent_file_path_means_its_folder_as_in_motion_context(tmp_path):
    run, folders = chain(tmp_path, 1)
    assert previous_clip(tmp_path, "h3_context/clip.safetensors", 1) == run / folders[0] / "video.mp4"


def test_the_chain_cannot_point_outside_the_output_folder(tmp_path):
    (tmp_path / "out").mkdir()
    chain(tmp_path, 1, latent_path="elsewhere")
    assert previous_clip(tmp_path / "out", "../elsewhere", 1) is None


def test_the_model_sees_one_frame_a_second_and_the_last_one():
    """The last frame is where the next clip starts, so it is always among the stills."""
    from orrery.chain import still_indices
    assert still_indices(120, 24.0) == [0, 24, 48, 72, 96, 119]
    assert still_indices(97, 24.0) == [0, 24, 48, 72, 96]
    assert still_indices(1, 24.0) == [0]


def test_a_segments_own_clip_is_found_by_its_segment(tmp_path):
    """SEND: reads the sending segment's own clip: segment 0 is Chain Video's clip 1."""
    from orrery.chain import clip_file
    run, folders = chain(tmp_path, 3)
    assert clip_file(tmp_path, "h3_context", 0) == run / folders[0] / "video.mp4"
    assert clip_file(tmp_path, "h3_context", 2) == run / folders[2] / "video.mp4"
    assert clip_file(tmp_path, "h3_context", 3) is None


def test_sent_frames_past_the_clip_are_dropped_and_the_last_stands_in():
    from orrery.chain import frame_picks
    assert frame_picks(48, [[2, 2], [5, 5], [40, 40]]) == ([2, 5, 40], [])
    assert frame_picks(48, [[2, 2], [47, 48], [60, 60]]) == ([2, 47], [48, 60])
    assert frame_picks(48, [[60, 60], [70, 70]]) == ([47], [60, 70])


def test_negative_frames_count_back_from_the_end_of_the_clip():
    from orrery.chain import frame_picks
    assert frame_picks(48, [[-1, -1]]) == ([47], [])
    assert frame_picks(48, [[-3, -1]]) == ([45, 46, 47], [])
    assert frame_picks(48, [[44, -1]]) == ([44, 45, 46, 47], [])
    assert frame_picks(48, [[-100, -100]]) == ([47], [-100])
