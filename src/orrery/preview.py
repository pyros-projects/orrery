"""The clip being sampled, as orrery's app shows it in the clip's box (#205, #209).

Two sources, both sent as `orrery.preview` to every open tab, so the tab that shows the reel gets
them whichever tab queued the run (ComfyUI sends its own previews to the queuing tab only):

- ComfyUI's own preview: the picture its global progress hook gets each step (Latent2RGB or a
  tiny VAE, as ComfyUI's live preview setting says), passed on as a still.
- The whole clip: when the model is wired through the Orrery Prompt, a wrapper around the sampler
  decodes each step's denoised estimate, all its frames, with the tiny VAE for the model's latents
  (taeh3 for MiniMax H3, from models/vae_approx; Latent2RGB without one) into a short animated WebP.

Written for orrery on ComfyUI's own previewers; KJNodes' Model Preview Override (GPL-3.0) gave the
idea, not the code.
"""

import base64
import io
import logging
import threading

log = logging.getLogger("orrery.preview")

EVENT = "orrery.preview"
MAX_EDGE = 384  # the long edge of a preview: the clip's box is no bigger
MAX_LATENT_FRAMES = 12  # latent frames decoded per step, spread over the clip (each is about 4 video frames)
FPS = 12
SPATIAL = 16  # MiniMax H3's VAE: one latent pixel is 16×16 video pixels


def _send(payload: dict) -> None:
    try:
        from server import PromptServer  # ComfyUI
    except ImportError:
        return
    PromptServer.instance.send_sync(EVENT, payload)  # no sid: every tab


def _b64(image, fmt: str = "JPEG", **save) -> str:
    buffer = io.BytesIO()
    image.save(buffer, fmt, **save)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# --- ComfyUI's own preview, to every tab ---------------------------------------------------

def forward_core_previews() -> None:
    """Wrap ComfyUI's progress hook once, so its preview picture also reaches every tab."""
    try:
        import comfy.utils  # ComfyUI
    except ImportError:  # the CLI and the tests
        return

    hook = comfy.utils.PROGRESS_BAR_HOOK
    if hook is None or getattr(hook, "_orrery", False):
        return

    def wrapped(value, total, preview_image, prompt_id=None, node_id=None):
        hook(value, total, preview_image, prompt_id, node_id)
        if preview_image is not None:
            try:  # ("JPEG", the picture, its largest size), as ComfyUI's previewers give it
                image = preview_image[1].copy()
                image.thumbnail((MAX_EDGE, MAX_EDGE))
                _send({"image": _b64(image.convert("RGB"), quality=80), "mime": "image/jpeg", "step": value, "total": total,
                       "prompt_id": prompt_id})
            except Exception as err:  # noqa: BLE001 - a preview never stops a run
                log.debug(f"[orrery] preview not passed on: {err}")

    wrapped._orrery = True
    comfy.utils.set_progress_bar_global_hook(wrapped)


# --- the whole clip, from a wrapper around the sampler ------------------------------------

_TINY: dict[str, object] = {}  # path → the tiny decoder (or None: it did not load); one at a time


def flat_decoder(sd):
    """A TAESD-style decoder, built from its checkpoint: the 2D taeh3 (a picture per latent frame), which
    ComfyUI's VAE cannot build. Its keys are module positions: `N.weight` a 3×3 conv, `N.conv.*` a block,
    and a position without weights the clamp (first), the ReLU after the first conv, or an upsample."""
    import torch
    from torch import nn

    class Clamp(nn.Module):
        def forward(self, x):
            return torch.tanh(x / 3) * 3

    class Block(nn.Module):
        def __init__(self, n_in, n_out):
            super().__init__()
            self.conv = nn.Sequential(nn.Conv2d(n_in, n_out, 3, padding=1), nn.ReLU(), nn.Conv2d(n_out, n_out, 3, padding=1),
                                      nn.ReLU(), nn.Conv2d(n_out, n_out, 3, padding=1))
            self.skip = nn.Conv2d(n_in, n_out, 1, bias=False) if n_in != n_out else nn.Identity()

        def forward(self, x):
            return torch.relu(self.conv(x) + self.skip(x))

    at: dict[int, dict] = {}
    for key, value in sd.items():
        position, _, name = key.partition(".")
        at.setdefault(int(position), {})[name] = value
    layers = []
    for i in range(max(at) + 1):
        weights = at.get(i)
        if weights is None:
            layers.append(Clamp() if i == 0 else nn.ReLU() if i == 2 else nn.Upsample(scale_factor=2))
        elif "conv.0.weight" in weights:
            n_out, n_in = weights["conv.0.weight"].shape[:2]
            layers.append(Block(n_in, n_out))
        else:
            n_out, n_in = weights["weight"].shape[:2]
            layers.append(nn.Conv2d(n_in, n_out, 3, padding=1, bias="bias" in weights))
    decoder = nn.Sequential(*layers)
    decoder.load_state_dict(sd)
    return decoder.eval().requires_grad_(False)


def _tiny(sd):
    """("tae", ComfyUI's VAE) for a temporal tiny VAE, ("tae2d", the decoder) for a flat one, else None."""
    if all(key.partition(".")[0].isdigit() for key in sd):
        return "tae2d", flat_decoder(sd)
    from comfy.sd import VAE

    vae = VAE(sd)
    if vae.first_stage_model is None:  # not a VAE ComfyUI knows
        return None
    vae.first_stage_model.show_progress_bar = False
    return "tae", vae


def _decoder(model_patcher):
    """The tiny VAE for the model's latents ("tae" or "tae2d"), else ("rgb", its latent format), else None."""
    latent_format = model_patcher.model.latent_format
    name = getattr(latent_format, "taesd_decoder_name", None)
    if name:
        import comfy.utils
        import folder_paths

        file = next((f for f in folder_paths.get_filename_list("vae_approx") if f.startswith(name)), None)
        path = file and folder_paths.get_full_path("vae_approx", file)
        if path:
            if path not in _TINY:
                _TINY.clear()
                try:
                    _TINY[path] = _tiny(comfy.utils.load_torch_file(path))
                except Exception as err:  # noqa: BLE001 - Latent2RGB then
                    log.warning(f"[orrery] {file} did not load for the live preview: {err}")
                    _TINY[path] = None
            if _TINY[path] is not None:
                return _TINY[path]
    if getattr(latent_format, "latent_rgb_factors", None) is not None:
        return "rgb", latent_format
    return None


def frames(decoder, video):
    """The clip's frames as PIL pictures from its latent [batch, channels, time, height, width]: up to
    MAX_LATENT_FRAMES of its latent frames, spread over the clip, scaled to about MAX_EDGE."""
    import numpy as np
    import torch
    from PIL import Image

    x = video[:1].float()
    if x.ndim == 4:
        x = x.unsqueeze(2)
    if x.shape[2] > MAX_LATENT_FRAMES:
        x = x[:, :, torch.linspace(0, x.shape[2] - 1, MAX_LATENT_FRAMES).round().long().to(x.device)]
    kind, it = decoder
    with torch.no_grad():
        if kind in ("tae", "tae2d"):
            scale = min(1.0, MAX_EDGE / (SPATIAL * max(x.shape[-2:])))
            if scale < 1:  # a smaller latent decodes faster and is all a preview needs
                x = torch.nn.functional.interpolate(x, scale_factor=(1, scale, scale), mode="trilinear")
            if kind == "tae":
                out = it.decode(x)[0]  # ComfyUI's VAE moves and casts it: [frames, h, w, rgb] in 0..1
            else:  # a picture per latent frame
                out = it.to(x.device)(x[0].movedim(1, 0)).movedim(1, -1)
        else:
            factors = torch.tensor(it.latent_rgb_factors, device=x.device, dtype=x.dtype)
            rgb = torch.nn.functional.linear(x[0].movedim(0, -1), factors.transpose(0, 1))  # [time, h, w, rgb] in -1..1
            if getattr(it, "latent_rgb_factors_bias", None) is not None:
                rgb = rgb + torch.tensor(it.latent_rgb_factors_bias, device=x.device, dtype=x.dtype)
            out = (rgb + 1) / 2
    array = (out.clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy()
    pictures = [Image.fromarray(np.ascontiguousarray(f)) for f in array]
    for picture in pictures:
        picture.thumbnail((MAX_EDGE, MAX_EDGE))
    return pictures


class _Sender:
    """Encodes and sends in a thread of its own, so sampling never waits; a newer step replaces one not sent yet."""

    def __init__(self):
        self._next, self._lock, self._wake = None, threading.Lock(), threading.Event()
        self._done = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def put(self, pictures, payload: dict) -> None:
        with self._lock:
            self._next = (pictures, payload)
        self._wake.set()

    def _run(self) -> None:
        while True:
            self._wake.wait()
            self._wake.clear()
            with self._lock:
                job, self._next = self._next, None
            if job is not None:
                pictures, payload = job
                try:
                    first, rest = pictures[0], pictures[1:]
                    image = _b64(first, "WEBP", save_all=True, append_images=rest, duration=round(1000 / FPS), loop=0,
                                 quality=70) if rest else _b64(first, quality=80)
                    _send({**payload, "image": image, "mime": "image/webp" if rest else "image/jpeg", "animated": bool(rest)})
                except Exception as err:  # noqa: BLE001 - a preview never stops a run
                    log.debug(f"[orrery] preview not sent: {err}")
            if self._done and self._next is None:
                return

    def close(self) -> None:
        self._done = True
        self._wake.set()


class _Wrapper:
    """Around the sampler (ComfyUI's OUTER_SAMPLE): the callback also previews the whole clip."""

    def __init__(self, node_id: str | None):
        self.node_id = node_id

    def __call__(self, executor, noise, latent_image, sampler, sigmas, denoise_mask=None, callback=None,
                 disable_pbar=False, seed=None, latent_shapes=None):
        from orrery import runs

        try:
            decoder = _decoder(executor.class_obj.model_patcher)
        except Exception as err:  # noqa: BLE001 - no preview, the run goes on
            log.warning(f"[orrery] no live preview: {err}")
            decoder = None
        if decoder is None:
            return executor(noise, latent_image, sampler, sigmas, denoise_mask, callback, disable_pbar, seed,
                            latent_shapes=latent_shapes)
        sender, prompt_id = _Sender(), runs.current_prompt()

        def previewing(step, x0, x, total_steps):
            if callback is not None:
                callback(step, x0, x, total_steps)
            try:
                video = x0
                if latent_shapes and len(latent_shapes) > 1:  # video and sound packed together (MiniMax H3): the video
                    import comfy.utils
                    video = comfy.utils.unpack_latents(x0, latent_shapes)[0]
                sender.put(frames(decoder, video), {"step": step + 1, "total": total_steps, "prompt_id": prompt_id,
                                                    "node": self.node_id})
            except Exception as err:  # noqa: BLE001 - a preview never stops a run
                log.debug(f"[orrery] preview skipped: {err}")

        try:
            return executor(noise, latent_image, sampler, sigmas, denoise_mask, previewing, disable_pbar, seed,
                            latent_shapes=latent_shapes)
        finally:
            sender.close()


def patched(model, node_id: str | None):
    """The model with orrery's preview around its sampler; the weights are shared, nothing loads again."""
    import comfy.patcher_extension

    m = model.clone()
    m.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.OUTER_SAMPLE, "orrery_preview", _Wrapper(node_id))
    return m
