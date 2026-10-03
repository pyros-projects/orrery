"""A strength per RefMod: orrery biases H3's attention to a RefMod's tokens (issue #30), and to a
picture's: its reference latents and the vision tokens its text encoder left in the text (#61).

H3 packs text, references and the video into one sequence, and every DiT block attends over all of
it, so a reference has no weight of its own to turn down (the RefMod pack's `strength` only blurs
it, which keeps its layout). Here the logits from the video's and the audio's queries to a RefMod's
keys get `log s` added, so the RefMod gets about `s` times its share of attention: 1 leaves it as
it is, 0.5 halves it.

No dense mask: one more dimension per head carries the bias. The target's queries hold `c` there,
a RefMod's keys `log(s)·√D'/c`, every other row 0, and the queries are scaled by `√(D'/D)`, so

    q'·k'/√D' = q·k/√D + log s

comes out of the usual attention kernel. D' = D + 8 keeps the head size a multiple of 8, and `c`
balances the two values so int8 kernels see no outliers. The heads go through in groups, so the
wider copies stay small.

orrery wraps two names of `comfy.ldm.minimax.model` when its nodes load and leaves ComfyUI's files
alone: `MiniMaxH3Model._forward` notes the strengths of the payload's refs, and the module's
`optimized_attention` applies them. Without a strength other than 1, H3 runs untouched.

Reference to Video also shows a picture to Qwen, and its vision block (tag 0 in the payload's
`text_token_tags`) stays in the text every block attends to: those rows get the picture's `log s` too.
The prompt Qwen read after the picture keeps what it saw.
"""

import math

KEY = "orrery_strength"  # on a block of the conditioning's minimax_refs (orrery.comfy_refmods)
PICTURE = "orrery_picture"  # on a picture's block with a strength: its N in <Picture N> (comfy_refmods)
OPTION = "orrery_ref_strengths"  # in transformer_options while H3 runs: plan() of the payload's refs
VISION = "orrery_vision_strengths"  # and vision() of its pictures
PAD = 8
HEADS_AT_ONCE = 8
FLOOR = 1e-4  # the smallest strength: log(1e-4) ≈ -9.2 hides a RefMod all but completely


def plan(refs) -> list[tuple[float, int]] | None:
    """(strength, packed segments) for each ref block, in the order H3 packs them (PackedLayout); None
    when every strength is 1."""
    out = []
    for block in refs or ():
        kind, audio = block.get("kind"), int(block.get("ref_audio_t") or 0)
        segments = {"image": 1, "audio": int(audio > 0), "video": 1 + int(audio > 0),
                    "video_audio": 1 + int(audio > 0)}.get(kind, 0)
        out.append((float(block.get(KEY, 1.0)), segments))
    return out if any(s != 1.0 for s, _ in out) else None


def vision(refs, tags) -> list[tuple[int, int, float]] | None:
    """(start, stop, strength) in the text for the vision block of each picture with a strength other
    than 1: the Nth run of tag 0 in `tags` for <Picture N>, as Reference to Video shows the pictures
    first, in order, then the videos. None when there is none."""
    wanted = {int(b[PICTURE]): float(b.get(KEY, 1.0)) for b in refs or ()
              if b.get(PICTURE) and float(b.get(KEY, 1.0)) != 1.0}
    if not wanted or tags is None:
        return None
    runs = _runs(tags.reshape(-1).tolist() if hasattr(tags, "reshape") else list(tags))
    return [(*runs[n - 1], s) for n, s in sorted(wanted.items()) if n <= len(runs)] or None


def _runs(tags: list) -> list[tuple[int, int]]:
    """(start, stop) of each run of tag 0, in order."""
    out, start = [], None
    for i, tag in enumerate([*tags, 1]):
        if int(tag) == 0 and start is None:
            start = i
        elif int(tag) != 0 and start is not None:
            out.append((start, i))
            start = None
    return out


def rows(segments, refs_plan, pictures=None) -> tuple[list[tuple[int, int]], list[tuple[int, int, float]]]:
    """From the layout's (start, stop, kind) table: the query rows to bias (the target audio and video)
    and the key rows of each RefMod with a strength other than 1, with `log s`; `pictures` (vision())
    adds the rows of their vision blocks in the text."""
    packed = [(a, b) for a, b, kind in segments if kind in ("ref_img", "ref_audio")]
    keys, i = [], 0
    for strength, n in refs_plan:
        if strength != 1.0:
            keys += [(a, b, math.log(max(strength, FLOOR))) for a, b in packed[i:i + n]]
        i += n
    text = next((a for a, _, kind in segments if kind == "text"), 0)
    keys += [(text + a, text + b, math.log(max(s, FLOOR))) for a, b, s in pictures or ()]
    return [(a, b) for a, b, kind in segments if kind in ("audio", "video")], keys


def columns(biases: list[float], head_dim: int) -> tuple[float, dict[float, float], float]:
    """(the queries' value c, each bias's key value, the scale √(D'/D) for the queries), with
    c · key / √D' = bias."""
    wide = head_dim + PAD
    c = math.sqrt(max((abs(b) for b in biases), default=0.0) * math.sqrt(wide)) or 1.0
    return c, {b: b * math.sqrt(wide) / c for b in biases}, math.sqrt(wide / head_dim)


def _extra(seq: int, spans, value, device, dtype):
    import torch

    col = torch.zeros(seq, device=device, dtype=dtype)
    for span in spans:
        col[span[0]:span[1]] = value(span)
    return col


def _attention(original, container):
    import torch

    cache: dict = {}
    fallback: list = []  # set once the backend turns the wider heads down: PyTorch's attention takes them

    def run(qn, kn, vn, n, args, kwargs):
        if not fallback:
            try:
                return original(container(qn), container(kn), container(vn), n, *args, **kwargs)
            except Exception as err:  # noqa: BLE001 - a kernel that only takes head sizes it was built for
                fallback.append(err)
                print(f"[orrery] RefMod strengths: this attention backend takes no head size {qn.shape[-1]} "
                      f"({type(err).__name__}), so the clips with one run PyTorch's attention.")
        out = torch.nn.functional.scaled_dot_product_attention(qn, kn, vn)
        return out.transpose(1, 2).reshape(1, qn.shape[2], -1)

    def attention(q, k, v, heads, *args, transformer_options=None, **kwargs):
        options = transformer_options or {}
        refs_plan, pictures, layout = options.get(OPTION), options.get(VISION), options.get("minimax_h3_layout")
        shape = q.peek().shape if isinstance(q, container) else None
        segments = getattr(layout, "segments", None)
        if not refs_plan or shape is None or len(shape) != 4 or not segments or shape[2] != segments[-1][1]:
            return original(q, k, v, heads, *args, transformer_options=transformer_options, **kwargs)
        qt, kt, vt = q.take(), k.take(), v.take()  # [1, heads, seq, dim]
        _, n_heads, seq, dim = qt.shape
        key = (id(layout), tuple(refs_plan), tuple(pictures or ()), seq, dim, qt.device, qt.dtype)
        if key not in cache:
            cache.clear()
            queries, keys = rows(segments, refs_plan, pictures)
            c, values, scale = columns([b for _, _, b in keys], dim)
            cache[key] = (_extra(seq, queries, lambda _: c, qt.device, qt.dtype).view(1, 1, seq, 1),
                          _extra(seq, keys, lambda span: values[span[2]], qt.device, qt.dtype).view(1, 1, seq, 1),
                          scale)
        qcol, kcol, scale = cache[key]
        outs = []
        for h0 in range(0, n_heads, HEADS_AT_ONCE):
            h1 = min(n_heads, h0 + HEADS_AT_ONCE)
            n = h1 - h0
            pad = qt.new_zeros(1, n, seq, PAD - 1)
            qn = torch.cat([qt[:, h0:h1] * scale, qcol.expand(1, n, seq, 1), pad], dim=-1)
            kn = torch.cat([kt[:, h0:h1], kcol.expand(1, n, seq, 1), pad], dim=-1)
            vn = torch.cat([vt[:, h0:h1], qt.new_zeros(1, n, seq, PAD)], dim=-1)
            out = run(qn, kn, vn, n, args, {**kwargs, "transformer_options": transformer_options})
            outs.append(out.reshape(1, seq, n, dim + PAD)[..., :dim])
        return torch.cat(outs, dim=2).reshape(1, seq, n_heads * dim)

    return attention


def _forward(original):
    def forward(self, x, timestep, context, transformer_options=None, *args, minimax_payload=None, **kwargs):
        options = {} if transformer_options is None else transformer_options
        payload = minimax_payload or {}
        refs_plan = plan(payload.get("refs"))
        pictures = vision(payload.get("refs"), payload.get("text_token_tags")) if refs_plan else None
        for name, value in ((OPTION, refs_plan), (VISION, pictures)):
            if value:
                options[name] = value
            else:
                options.pop(name, None)
        return original(self, x, timestep, context, options, *args, minimax_payload=minimax_payload, **kwargs)

    return forward


def install() -> str:
    """Wrap H3 in this ComfyUI: "on", or why the strengths are off (outside ComfyUI, or H3 is not as
    orrery expects); without them RefMods still work, at full strength. orrery's boot banner says which."""
    try:
        import comfy.ldm.minimax.model as h3
        from comfy.ldm.modules.attention import AttentionTensorContainer
    except Exception:  # noqa: BLE001 - not inside ComfyUI, or no H3 in it
        return "no H3 in this ComfyUI"
    if getattr(h3, "_orrery_refbias", False):
        return "on"
    model = getattr(h3, "MiniMaxH3Model", None)
    if not callable(getattr(h3, "optimized_attention", None)) or not callable(getattr(model, "_forward", None)):
        return "H3 is not as orrery expects: comfy.ldm.minimax.model changed"
    h3.optimized_attention = _attention(h3.optimized_attention, AttentionTensorContainer)
    model._forward = _forward(model._forward)
    h3._orrery_refbias = True
    return "on"
