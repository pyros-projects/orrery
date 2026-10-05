# Seams: how a film's joins compare with the inside of its clips

`measure.py` reads a film as Orrery Film stores it (each take's `video.mp4`, pinned frames trimmed, and `audio.npy`)
and compares every seam with the steps inside the clips: the picture's mean luma jump and pixel MAE between the last
frame of a clip and the first of the next, and the sound's sample step and 20 ms level change across the join. Each
seam value comes with its percentile among the steps inside the clips (p99: larger than 99% of them).

    uv run python experiments/seams/measure.py <output>/<reel>/orrery_film/<run>

Run on 2026-10-05 against ComfyUI-H3-Continuum's assembly, which repairs seams after decoding (sound aligned within
±20 ms, crossfaded over 10–60 ms, level matched; a brief luma pulse levelled), while orrery joins the clips as they are.

| Film | Seams | Picture (luma jump, pixel MAE) | Sound (step, 20 ms level) |
|---|---|---|---|
| `abc_c_late60`, 4 clips | 3 | p70–p91, p31–p79: within the clips' range | step **p99** at all three; level 8.6 dB (**p99**), 0.4 dB, 4.9 dB (**p97**) |
| `contortion_full_routine1`, 2 clips | 1 | p76, p28 | step **p96**; level 10.8 dB (**p94**) |
| `abc_refmods`, 7 clips | 6 | seams 3–6 jump hard (luma 25–39) | not a seam fault: clips 3–6 all continue clip 2, branches stored one after another |

The luma of the frames around each real seam flows on (86.8 86.9 86.8 | 86.4 86.1 86.0 …), with no pulse. So the
picture's seams are clean; the sound's are where orrery falls behind Continuum's assembled film: a click or a level
bump at the join. A small sample (four real seams); measure again after a fix.
