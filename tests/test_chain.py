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


def test_ref2va_gets_the_last_three_seconds():
    """What video continuation wants (the H3 prompt builders' "last 3s")."""
    from orrery.chain import tail_start
    assert tail_start(120, 24.0) == 48
    assert tail_start(50, 24.0) == 0
