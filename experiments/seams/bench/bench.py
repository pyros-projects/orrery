"""The seam bench (#360): one reel (reel.orr, four 5 s scenes) made with orrery, ComfyUI-H3-Continuum and
ComfyUI-H3-Motion-Context on identical settings, each film saved as an mp4 and measured with the seam meter.

Identical for all three: the H3 ref2va model, the 4-step turbo LoRA at 0.8, the Comfy Kitchen attention, dpmpp_2m_sde,
simple, 4 steps, 1024×576, 124 frames a clip, a 22-frame context, the same four clip texts (orrery compiles them, the
others get them as written), no reference pictures. Only how a tool continues and joins differs. Continuum's film is
saved twice, with its seam repair (Finalize Auto) and without (Off), from the same latents.

    uv run python experiments/seams/bench/bench.py [--seed 1] [--tools orrery,continuum,mc]

It queues on the running ComfyUI at 127.0.0.1:8188 (the GPU; ask before running) and reads orrery's home only to
compile the texts.
"""

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
HERE = Path(__file__).parent
OUTPUT = Path("/home/pyro/repos/comfy-ui/output")
W, H, LENGTH, CLIPS, FPS, CONTEXT = 1024, 576, 124, 4, 24, 22
MODELS = {"unet": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
          "clip": "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
          "vae": "minimax_h3_video_vae_int8_convrot.safetensors",
          "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
          "lora": "minimax/turbo/minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors"}


class Graph(dict):
    """An API prompt, built node by node: add() gives the node's id, out(id, n) a link to its n-th output."""

    def add(self, cls: str, **inputs) -> str:
        key = str(len(self) + 1)
        self[key] = {"class_type": cls, "inputs": inputs}
        return key


def out(node: str, slot: int = 0) -> list:
    return [node, slot]


def base(g: Graph) -> dict:
    """The models, the sampler and the steps every tool uses."""
    unet = g.add("UNETLoader", unet_name=MODELS["unet"], weight_dtype="default")
    attn = g.add("ModelAttentionBackend", model=out(unet), attention="comfy kitchen attention")
    model = g.add("LoraLoaderModelOnly", model=out(attn), lora_name=MODELS["lora"], strength_model=0.8)
    return {"model": out(model),
            "clip": out(g.add("CLIPLoader", clip_name=MODELS["clip"], type="minimax", device="default")),
            "vae": out(g.add("VAELoader", vae_name=MODELS["vae"])),
            "audio_vae": out(g.add("VAELoader", vae_name=MODELS["audio_vae"])),
            "sampler": out(g.add("KSamplerSelect", sampler_name="dpmpp_2m_sde")),
            "sigmas": out(g.add("BasicScheduler", model=out(model), scheduler="simple", steps=4, denoise=1.0))}


def sample(g: Graph, b: dict, conditioning: list, latent: list, seed: int) -> list:
    guider = g.add("BasicGuider", model=b["model"], conditioning=conditioning)
    noise = g.add("RandomNoise", noise_seed=seed)
    return out(g.add("SamplerCustomAdvanced", noise=out(noise), guider=out(guider), sampler=b["sampler"], sigmas=b["sigmas"],
                     latent_image=latent))


def decoded(g: Graph, b: dict, latent: list) -> tuple[list, list]:
    return out(g.add("VAEDecode", samples=latent, vae=b["vae"])), out(g.add("VAEDecodeAudio", samples=latent, vae=b["audio_vae"]))


def to_video(g: Graph, images: list, audio: list, prefix: str) -> None:
    video = g.add("CreateVideo", images=images, fps=float(FPS), audio=audio)
    g.add("SaveVideo", video=out(video), filename_prefix=prefix, format="mp4")


def r2v(g: Graph, b: dict, prompt) -> str:
    return g.add("MiniMaxH3ReferenceToVideo", clip=b["clip"], prompt=prompt, width=W, height=H, length=LENGTH,
                 ref_image_size="match", vae=b["vae"], audio_vae=b["audio_vae"])


# --- the tools -------------------------------------------------------------------------------

def orrery_runs(reel: str, seed: int, folder: str, keep: bool = False) -> list[Graph]:
    """One run a clip, as Roll queues them: Orrery Prompt (segment k) → Reference to Video → Orrery Continue → sampler →
    decode → Orrery Film. The last run saves the film; every run keeps its latent for the decode experiment."""
    runs = []
    for k in range(CLIPS):
        g = Graph()
        b = base(g)
        p = g.add("OrreryPrompt", template=reel, seed=seed, target="h3-base", preset="(none)", home="", params="",
                  segment=k, sweep="", take=0, chain=f"{folder}/orrery", shoot="")
        ref = r2v(g, b, out(p, 0))
        cont = g.add("OrreryContinue", picks=out(p, 1), latent=out(ref, 1), conditioning=out(ref, 0), vae=b["vae"],
                     audio_vae=b["audio_vae"])
        latent = sample(g, b, out(cont, 0), out(cont, 1), seed * 100 + k)
        if keep:  # needs Orrery Latent Keep (the seam meter pack) loaded
            g.add("OrreryLatentKeep", samples=latent, filename_prefix=f"{folder}/orrery/latent_{k}")
        images, audio = decoded(g, b, latent)
        film = g.add("OrreryFilm", samples=latent, images=images, audio=audio)
        if k == CLIPS - 1:
            g.add("SaveVideo", video=out(film, 2), filename_prefix=f"{folder}/orrery_film", format="mp4")
        runs.append(g)
    return runs


def mc_runs(texts: list[str], seed: int, folder: str) -> list[Graph]:
    """One run a clip, as Motion Context's README chains them: Load k → Motion Context → sampler → Save k+1 → decode →
    Trim → Chain Video (which merges the clips into merged.mp4)."""
    runs = []
    for k in range(CLIPS):
        g = Graph()
        b = base(g)
        ref = r2v(g, b, texts[k])
        load = g.add("MiniMaxH3MotionContextLoadLatent", latent_path=f"{folder}/mc", clip_index=k)
        mc = g.add("MiniMaxH3MotionContext", conditioning=out(ref, 0), vae=b["vae"], latent=out(ref, 1),
                   context_length=str(CONTEXT), audio_context_length=24, context_latent=out(load, 0), audio_vae=b["audio_vae"])
        latent = sample(g, b, out(mc, 0), out(ref, 1), seed * 100 + k)
        save = g.add("MiniMaxH3MotionContextSaveLatent", latent=latent, filename_prefix=f"{folder}/mc/clip", clip_index=k + 1)
        images, audio = decoded(g, b, latent)
        trim = g.add("MiniMaxH3MotionContextTrim", images=images, trim_frames=out(mc, 1), audio=audio, fps=float(FPS),
                     match_tail=True)
        g.add("MiniMaxH3MotionContextChainVideo", images=out(trim, 0), clip_index=out(save, 1), latent_path=out(save, 0),
              fps=float(FPS), audio=out(trim, 1), merge=True)
        runs.append(g)
    return runs


def continuum_run(texts: list[str], seed: int, folder: str) -> list[Graph]:
    """One run for the whole reel, as Continuum makes it: its Sampler V3.9 (List prompts, 4 chunks of 5 s, 22 frames),
    one decode of all chunks, then Finalize twice: with its seam repair and without."""
    g = Graph()
    b = base(g)
    cs = g.add("H3ContinuumSamplerV39", model=b["model"], clip=b["clip"], video_vae=b["vae"], sampler=b["sampler"],
               sigmas=b["sigmas"], sequence_prompt="\n---\n".join(texts), prompt_mode="List", chunks=CLIPS, chunk_seconds=5.0,
               aspect="Landscape 16:9", preset="Custom", custom_mp=round(W * H / 1e6, 3), continuity="Balanced — 22 frames",
               base_seed=seed, audio_continuity=True, diagnostics="Detailed Report", reroll_from_chunk="Auto",
               reroll_nonce=0, strict_compatibility=True, debug=False, show_preview=False, run_storage="Off", run_name="",
               reference_size="Match Output", project_id="", video_reference_size="Efficient - 0.4 MP",
               continuation_backend="Standard", generation_mode="Full Run", review_action="Continue / Next",
               take_group=0, take_revision_id="", take_action="Automatic", size_source="Manual", width=W, height=H,
               audio_vae=b["audio_vae"])
    images = out(g.add("VAEDecode", samples=out(cs, 0), vae=b["vae"]))
    audio = out(g.add("VAEDecodeAudio", samples=out(cs, 1), vae=b["audio_vae"]))
    g.add("PreviewAny", source=out(cs, 3))
    for name, sound, picture in (("repaired", "Auto", "Auto"), ("raw", "Off", "Off")):
        fin = g.add("H3ContinuumAssembleSeamV35", images=images, audio=audio, assembly_plan=out(cs, 2), exact_total_duration=True,
                    audio_seam=sound, video_seam=picture, buffer_backend="Auto", diagnostics="Detailed Report")
        g.add("PreviewAny", source=out(fin, 2))
        to_video(g, out(fin, 0), out(fin, 1), f"{folder}/continuum_{name}")
    return [g]


def onepass_run(seed: int, folder: str) -> list[Graph]:
    """The decode experiment: orrery's clips of this seed (kept with --keep) joined into one latent and decoded once,
    against Orrery Film's film of the same clips, each decoded on its own."""
    g = Graph()
    vae = out(g.add("VAELoader", vae_name=MODELS["vae"]))
    audio_vae = out(g.add("VAELoader", vae_name=MODELS["audio_vae"]))
    joined = out(g.add("OrreryLatentJoin", prefix=f"{folder}/orrery/latent_", clips=CLIPS, context_slots=7, context_ticks=37))
    images = out(g.add("VAEDecode", samples=joined, vae=vae))
    audio = out(g.add("VAEDecodeAudio", samples=joined, vae=audio_vae))
    to_video(g, images, audio, f"{folder}/orrery_onepass")
    return [g]


# --- queueing ----------------------------------------------------------------------------------

def call(path: str, body: dict | None = None):
    req = urllib.request.Request(COMFY + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def run(graph: Graph, label: str) -> dict:
    t = time.time()
    try:
        pid = call("/prompt", {"prompt": graph})["prompt_id"]
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"{label}: ComfyUI refused the prompt: {err.read().decode()[:2000]}") from err
    while True:
        time.sleep(2)
        h = call(f"/history/{pid}").get(pid)
        if not h:
            continue
        status = h.get("status", {})
        if status.get("completed"):
            print(f"  {label}: done in {time.time() - t:.0f} s", flush=True)
            return h
        if status.get("status_str") == "error":
            msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
            raise RuntimeError(f"{label}: {json.dumps(msgs)[:2000]}")


def texts_of(reel: str, seed: int) -> list[str]:
    """The four clip texts as orrery compiles them at this seed (what Orrery Prompt gives Reference to Video)."""
    out_ = []
    for k in range(CLIPS):
        res = subprocess.run(["uv", "run", "orrery", "compile", reel, "--seed", str(seed), "--segment", str(k), "--json"],
                             capture_output=True, text=True, check=True, cwd=HERE.parents[2])
        out_.append(json.loads(res.stdout)["text"])
    return out_


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--tools", default="orrery,continuum,mc")
    ap.add_argument("--keep", action="store_true", help="orrery: keep each clip's latent for the decode experiment")
    args = ap.parse_args()
    reel = (HERE / "reel.orr").read_text(encoding="utf-8")
    folder = f"seam_bench/s{args.seed}"
    texts = texts_of(reel, args.seed)
    (OUTPUT / folder).mkdir(parents=True, exist_ok=True)
    (OUTPUT / folder / "texts.json").write_text(json.dumps(texts, indent=1, ensure_ascii=False))
    plans = {"orrery": lambda: orrery_runs(reel, args.seed, folder, args.keep), "continuum": lambda: continuum_run(texts, args.seed, folder),
             "mc": lambda: mc_runs(texts, args.seed, folder), "onepass": lambda: onepass_run(args.seed, folder)}
    for tool in args.tools.split(","):
        print(f"{tool}:", flush=True)
        for i, graph in enumerate(plans[tool]()):
            h = run(graph, f"{tool} run {i + 1}")
            (OUTPUT / folder / f"{tool}_history_{i + 1}.json").write_text(json.dumps(h.get("outputs", {}), indent=1)[:200000])
