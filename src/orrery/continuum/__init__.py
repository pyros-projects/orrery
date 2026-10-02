"""Clip continuation for MiniMax H3, taken from ComfyUI-H3-Continuum.

Source: https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum at commit 1f6aec1, MIT License,
Copyright (c) 2026 ukr8b3g-cmyk (the license text is in THIRD_PARTY_NOTICES.md). Adapted: `grid`
from its temporal.py, `masked` from v3/masked_continuation.py, state.py (the tail) and media.py
(trim_audio). Only Continuum's Masked AV route is here: the previous clip's last 22 frames, picture
and sound, start the next clip's latent and ComfyUI's noise_mask holds them, so no model or layout
patch is needed. Shaped to orrery's style and to work on numpy arrays as well as torch tensors.
"""
