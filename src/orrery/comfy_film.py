"""Orrery Continue and Orrery Film: orrery continues a reel's clips itself, on Masked AV from
ComfyUI-H3-Continuum (see orrery.continuum, orrery.film, docs/plan-continuation.md).

Orrery Continue starts the clip's latent with the last 22 frames of the clip before, picture and
sound, under a noise_mask, and leaves what it did in the latent (for a scene AFTER: the input video,
the input video's last 22 frames, fitted to the canvas and encoded with the VAEs wired into it); the sampler copies the latent's
keys, so Orrery Film finds it in the sampled latent. Orrery Film trims those frames off the decoded
clip, keeps the take and joins the film. ComfyUI only (torch).
"""

import json
from pathlib import Path

from orrery import chain as chains
from orrery import film
from orrery.chain import DEFAULT_CHAIN
from orrery.continuum import masked
from orrery.continuum.grid import CONTEXT, pixel_frames_for_latent_t

KEY = "orrery_film"  # what Orrery Continue leaves in the latent for Orrery Film
TOLERANCE = 1e-2  # how far the pinned frames may move in the sampler (rounding; a lost mask moves them far)


def _output() -> Path:
    import folder_paths  # ComfyUI

    return Path(folder_paths.get_output_directory())


def _streams(latent: dict):
    samples = latent.get("samples") if isinstance(latent, dict) else None
    if not getattr(samples, "is_nested", False):
        raise ValueError("Orrery Continue and Orrery Film take MiniMax H3 latents (video and audio together).")
    video, audio = samples.unbind()[:2]
    return video, audio


def _drop_first_frame(conditioning):
    """The conditioning without first-frame keyframes: a continued clip starts with the clip before."""
    if conditioning is None:
        return None
    out, dropped = [], 0
    for tensor, meta in conditioning:
        meta = dict(meta)
        if keyframes := meta.get("minimax_keyframes"):
            kept = [k for k in keyframes if int(k.get("resolved_frame_index", 0)) != 0]
            dropped += len(keyframes) - len(kept)
            if kept:
                meta["minimax_keyframes"] = kept
            else:
                meta.pop("minimax_keyframes")
        out.append([tensor, meta])
    if dropped:
        print("[orrery] Orrery Continue: this clip starts with the last frames of the one before, so its "
              "first-frame image is left out.")
    return out


def _input_tail(chain: str, video, audio, vae, audio_vae) -> masked.Tail:
    """The tail of the input video (orrery.film.keep_input): its last 22 frames, fitted to this clip's
    canvas, and their sound, encoded as H3 encodes a clip, in the shape a rendered clip's tail has."""
    import av
    import comfy.audio
    import comfy.utils
    import torch

    path = chains.clip_file(_output(), chain, -1)
    if path is None:
        raise ValueError(f"This scene continues the input video, but the chain {chain!r} holds none: wire a Load "
                         "Video into the Orrery Prompt's video input.")
    if vae is None or audio_vae is None:
        raise ValueError("This scene continues the input video, so Orrery Continue encodes its last frames and sound: "
                         "wire the H3 video VAE into vae and the H3 audio VAE into audio_vae.")
    frames, dropped = chains.frames(path, [[-CONTEXT, -1]])
    if dropped or frames.shape[0] < CONTEXT:
        raise ValueError(f"The input video is shorter than the {CONTEXT} frames a scene continues from.")
    height, width = int(video.shape[-2]) * 16, int(video.shape[-1]) * 16
    frames = comfy.utils.common_upscale(frames.movedim(-1, 1), width, height, "lanczos", "center").movedim(1, -1)
    picture = vae.encode(frames)  # [1, 24, 7, h, w]
    with av.open(str(path)) as container:
        sound, rate = film._input_sound(container)
    ticks = round(CONTEXT / 24 * 40)
    vae_rate = getattr(audio_vae, "audio_sample_rate", 32000)
    if sound is None:
        sound, rate = torch.zeros((1, vae_rate * 2)).numpy(), vae_rate
    wave = torch.from_numpy(sound[:, -int(rate * 1.5):])[None]  # the last 1.5 s: more than the 22 frames need
    if rate != vae_rate:
        wave = comfy.audio.resample(wave, rate, vae_rate)
    sounds = audio_vae.encode(wave[:1].movedim(1, -1))[..., -ticks:]  # [1, 32, 2, 37]: the ticks at its end
    return masked.tail(picture.to(video.device, video.dtype), sounds.to(audio.device, audio.dtype), CONTEXT)


class OrreryContinue:
    """Continues a reel: from its second segment on, the clip's latent starts with the last 22 frames
    of the segment before (picture and sound), which a noise_mask keeps as they are."""

    CATEGORY = "orrery"
    FUNCTION = "pin"
    RETURN_TYPES = ("CONDITIONING", "LATENT")
    RETURN_NAMES = ("conditioning", "latent")
    OUTPUT_TOOLTIPS = (("The conditioning, without a first-frame image from the second segment on: the clip "
                        "starts with the one before."),
                       "Into the sampler's latent_image. Orrery Film reads what is pinned from the sampled latent.")
    DESCRIPTION = ("orrery's own reel continuation (Masked AV, from H3 Continuum): wire the Orrery Prompt's picks, "
                   "the latent of the H3 node (Reference to Video, Image to Video …) and, optionally, its "
                   "conditioning. Orrery Film after the decode keeps the clips.")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"picks": ("STRING", {"forceInput": True}),
                             "latent": ("LATENT", {"tooltip": "The H3 node's latent, as long as the Orrery Prompt's "
                                                              "length (it counts the 22 pinned frames)."})},
                "optional": {"conditioning": ("CONDITIONING",),
                             "vae": ("VAE", {"tooltip": "The H3 video VAE: it encodes the input video's last frames for "
                                                        "a scene AFTER: the input video."}),
                             "audio_vae": ("VAE", {"tooltip": "The H3 audio VAE: it encodes the input video's sound for "
                                                              "a scene AFTER: the input video."})}}

    @classmethod
    def IS_CHANGED(cls, **_):
        """Always run: the segment before can be rendered again while the picks stay the same."""
        return float("NaN")

    def pin(self, picks, latent, conditioning=None, vae=None, audio_vae=None):
        import torch
        from comfy.nested_tensor import NestedTensor

        data = json.loads(picks or "{}")
        segment, chain = int(data.get("segment") or 0), data.get("chain") or DEFAULT_CHAIN
        continues = data.get("continues", segment - 1 if segment else None)  # see Reel.before; -1 the input video
        info = {"chain": chain, "segment": segment, "continues": None if continues == -1 else continues,
                "test": bool(data.get("test")),
                "meta": {k: data.get(k) for k in ("seed", "take", "template", "preset", "picks", "chunk", "kept")}}
        if continues is None:  # the first clip, or a test scene: it starts afresh
            return conditioning, {**latent, KEY: info}
        video, audio = _streams(latent)
        if continues == -1:
            tail = _input_tail(chain, video, audio, vae, audio_vae)
        else:
            before = film.previous_tail(_output(), chain, segment, continues)
            tail = masked.Tail(torch.from_numpy(before.video).to(video.device, video.dtype),
                               torch.from_numpy(before.audio).to(audio.device, audio.dtype), before.grid_offset)
        video, audio = video.clone(), audio.clone()
        video_mask = torch.ones((video.shape[0], 1, *video.shape[2:]), dtype=torch.float32, device=video.device)
        audio_mask = torch.ones((audio.shape[0], 1, *audio.shape[2:]), dtype=torch.float32, device=audio.device)
        masked.pin(video, audio, video_mask, audio_mask, tail)
        return _drop_first_frame(conditioning), {**latent, "samples": NestedTensor((video, audio)),
                                                 "noise_mask": NestedTensor((video_mask, audio_mask)),
                                                 KEY: {**info, "tail": tail}}


class _Frames:
    """An IMAGE batch as uint8 frames, one at a time (a whole clip as uint8 would be large)."""

    def __init__(self, images):
        self.images = images

    def __len__(self):
        return int(self.images.shape[0])

    def __iter__(self):
        import torch

        for frame in self.images:
            yield (frame[..., :3].clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy()


class OrreryFilm:
    """Keeps a reel's clips: trims the 22 frames Orrery Continue pinned, stores the take (and the tail
    the next segment continues from) and joins the reel so far into one video."""

    CATEGORY = "orrery"
    FUNCTION = "keep"
    OUTPUT_NODE = True
    RETURN_TYPES = ("IMAGE", "AUDIO", "VIDEO")
    RETURN_NAMES = ("images", "audio", "film")
    OUTPUT_TOOLTIPS = ("This clip without the pinned frames.", "Its sound, cut at the same moment.",
                       "The reel so far, every segment's active take joined: for Save Video and Orrery Log.")
    DESCRIPTION = ("Keeps the clips Orrery Continue started, under output/<latent_path>/orrery_film: wire the "
                   "sampler's latent and the decoded images and audio.")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"samples": ("LATENT", {"tooltip": "The sampler's output latent (it carries what "
                                                               "Orrery Continue pinned)."}),
                             "images": ("IMAGE",), "audio": ("AUDIO",)}}

    def keep(self, samples, images, audio):
        import torch
        from comfy_api.latest import InputImpl

        info = samples.get(KEY) if isinstance(samples, dict) else None
        if info is None:
            raise ValueError("Orrery Film keeps clips Orrery Continue started: wire the sampled latent of the "
                             "latent that came out of Orrery Continue into samples.")
        segment, chain = info["segment"], info["chain"]
        video, audio_latent = _streams(samples)
        frames = pixel_frames_for_latent_t(int(video.shape[2]))
        pinned = info.get("tail")  # none for a clip that starts afresh
        trim = CONTEXT if pinned is not None else 0
        if pinned is not None:
            moved = masked.drift(video, audio_latent, masked.Tail(pinned.video.to(video), pinned.audio.to(audio_latent),
                                                                  pinned.grid_offset))
            if not moved <= TOLERANCE:
                raise ValueError(f"The sampler changed the {CONTEXT} frames Orrery Continue pinned (by up to "
                                 f"{moved:.3g}), so this clip does not continue the one before: it must keep the "
                                 "latent's noise_mask, as SamplerCustomAdvanced and KSampler do.")
        if images.shape[0] < frames:
            raise ValueError(f"The decoded clip has {images.shape[0]} frames, its latent {frames}: wire the "
                             "images decoded from these samples.")
        kept = images[trim:frames]
        wave, rate = audio["waveform"], int(audio["sample_rate"])
        start, count = masked.audio_span(trim, int(kept.shape[0]), rate)
        wave = wave[..., start:start + count]
        if wave.shape[-1] < count:
            wave = torch.nn.functional.pad(wave, (0, count - wave.shape[-1]))
        last = masked.tail(video, audio_latent, frames)
        tail = masked.Tail(last.video.float().cpu().numpy(), last.audio.float().cpu().numpy(), last.grid_offset)
        take = film.save_take(_output(), chain, segment, _Frames(kept), wave[0].float().cpu().numpy(), rate, tail,
                              info.get("meta") or {}, info.get("continues", segment - 1 if segment else None),
                              info.get("test", False))
        print(f"[orrery] Orrery Film: clip {segment + 1} kept, {kept.shape[0]} frames "
              f"({kept.shape[0] / 24:.2f} s); the film is {film.film_file(take)}")
        sound = {**audio, "waveform": wave.contiguous(), "sample_rate": rate}
        return kept, sound, InputImpl.VideoFromFile(str(film.film_file(take)))
