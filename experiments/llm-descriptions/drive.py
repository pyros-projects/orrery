"""How well the language models describe gallery characters from their prompts (#131), and how many
they describe in one request before it breaks.

    uv run python experiments/llm-descriptions/drive.py [--models 4b,8b] [--counts 1,2,3,5,7,9] [--seeds 1,2,3]

Queues runs in the ComfyUI that is already running (:8188; never a second one): a CLIPLoader with the
model into the Orrery Prompt's clip, a reference screenplay whose CAST names N gallery characters (one
picture each) with `--who they are, briefly--`, an Orrery Refs reading the picks (so the pictures are
packed), and PreviewAny nodes for the text and the picks. The runs use a home of their own (a copy of
the gallery and the stored templates), so nothing lands in the real History. Each description is
scored against the character it should describe: its nationality, gender, signature colour, hair and
outfit, from what the creator rolled (the gallery's properties); a description that fits another
character better is a swap. Results go to results.json and the table below them to stdout.
"""

import argparse
import json
import re
import shutil
import time
import urllib.request
import uuid
from pathlib import Path

from orrery import pictures
from orrery.home import Home

HERE = Path(__file__).parent
SERVER = "http://127.0.0.1:8188"
PRESET = "krea/09_character_creator"
MODELS = {"4b": "qwen3vl_4b_bf16.safetensors", "8b": "qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors"}
STOP = {
        "a", "an", "the", "of", "with", "and", "in", "on", "at", "to", "over", "under", "into", "from", "its", "his",
        "her", "their", "one", "each", "whole", "that", "which", "across", "behind", "around", "below",
        "above", "tucked", "worn", "pulled", "hanging",
}


def call(path, body=None):
    req = urllib.request.Request(SERVER + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def test_home(root: Path) -> Path:
    """A home with the gallery and the stored templates of the real one, and nothing else."""
    real = Home(Path.home() / ".orrery")
    shutil.rmtree(root, ignore_errors=True)
    (root / "library").mkdir(parents=True)
    shutil.copy(real.galaxy_path, root / "galaxy.jsonl")
    shutil.copytree(real.templates_dir, root / "templates")
    return root


def characters(home: Path) -> list[dict]:
    """One picture each, of characters that differ in origin and colour."""
    lib = pictures.libraries(Home(home))["pictures/" + PRESET]
    stems = {}
    for e in lib.entries:
        for p in (e.prop("pictures") or "").splitlines():
            stems.setdefault(Path(p).stem, []).append(e.value)
    usable = []
    for e in lib.entries:
        props = dict(e.props)
        first = Path(props["pictures"].splitlines()[0])
        if len(stems[first.stem]) == 1 and all(props.get(k) for k in ("origin", "colour", "gender")):
            usable.append({"name": f"{PRESET}/{first.stem}", "file": str(first), **props})
    out, origins, colours = [], set(), set()
    for strict in (True, False):  # first the ones whose origin and colour no one before has, then the rest
        for c in usable:
            nation = c["origin"].split(" descent")[0]
            if c not in out and (not strict or (nation not in origins and c["colour"] not in colours)):
                out.append(c)
                origins.add(nation)
                colours.add(c["colour"])
    return out


def template(cast: list[dict]) -> str:
    names = [f"C{k + 1}" for k in range(len(cast))]
    lines = ["@h3 references 16:9", "CAST"]
    lines += [f"@{n} (image {c['name']}): --who they are, briefly--" for n, c in zip(names, cast, strict=True)]
    lines += ["SHOT 4s: static", ", ".join(f"@{n}" for n in names) + " stand side by side and look into the camera."]
    return "\n".join(lines)


def run(model: str, text: str, seed: int, home: Path) -> dict:
    graph = {"1": {"class_type": "CLIPLoader", "inputs": {"clip_name": model, "type": "minimax"}},
             "2": {"class_type": "OrreryPrompt", "inputs": {"template": text, "seed": seed, "target": "h3-base",
                                                            "home": str(home), "clip": ["1", 0]}},
             "3": {"class_type": "OrreryRefs", "inputs": {"picks": ["2", 1]}},
             "4": {"class_type": "PreviewAny", "inputs": {"source": ["2", 0]}},
             "5": {"class_type": "PreviewAny", "inputs": {"source": ["2", 1]}}}
    pid = call("/prompt", {"prompt": graph, "client_id": f"orrery-smoke-{uuid.uuid4().hex[:6]}"})["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(2)
        h = call(f"/history/{pid}").get(pid)
        if h and (h.get("status", {}).get("completed") or h.get("status", {}).get("status_str") == "error"):
            break
    outs = h.get("outputs", {})
    text_out = "".join(outs.get("4", {}).get("text", [""]))
    picks = json.loads("".join(outs.get("5", {}).get("text", ["{}"])) or "{}")
    error = None if h["status"].get("status_str") != "error" else json.dumps(h["status"].get("messages", []))[-600:]
    return {"text": text_out, "picks": picks, "seconds": round(time.time() - t0, 1), "error": error}


def keywords(phrase: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", phrase.lower()) if len(w) > 3 and w not in STOP}


GENDER = {"woman": r"\b(woman|girl|lady|female)\b", "man": r"\b(man|guy|boy|male|gentleman)\b",
          "nonbinary person": r"\b(person|nonbinary|non-binary|androgynous)\b"}


def fits(desc: str, c: dict) -> dict[str, bool]:
    d = desc.lower()
    nation = c["origin"].split(" descent")[0].lower()
    colour = c["colour"].lower().split("-")[-1]
    return {"origin": nation in d, "gender": bool(re.search(GENDER.get(c["gender"], r"$^"), d)),
            "colour": colour in d, "hair": bool(keywords(c.get("hair", "")) & keywords(d)),
            "outfit": bool(keywords(c.get("outfit", "")) & keywords(d))}


def score(result: dict, cast: list[dict]) -> list[dict]:
    """Each subject's description against its own character, and whether another fits it better."""
    picks, by_file = result["picks"], {c["file"]: c for c in cast}
    refs, files = picks.get("refs", []), picks.get("pictures", {})
    out = []
    for m in re.finditer(r"^<Subject (\d+)> = (.*?) of ((?:<Picture \d+>(?:, | and |, and )?)+)$", result["text"], re.MULTILINE):
        p = int(re.search(r"<Picture (\d+)>", m.group(3)).group(1))
        own = by_file.get(files.get(str(refs[p - 1])) if p - 1 < len(refs) else None)
        if own is None:
            continue
        desc = m.group(2).strip()
        mine = sum(fits(desc, own).values())
        best = max((sum(fits(desc, c).values()), c["file"]) for c in cast)
        out.append({"subject": int(m.group(1)), "desc": desc, "fits": fits(desc, own), "score": mine,
                    "swap": best[0] > mine and best[1] != own["file"], "unwritten": "who they are" in desc,
                    "form": bool(re.match(r"^(an?|the)\s", desc)) and not desc.endswith("."), "words": len(desc.split())})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--models", default="4b,8b")
    ap.add_argument("--counts", default="1,2,3,5,7,9")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--home", default="/tmp/orrery-smoke-home")
    a = ap.parse_args()
    home = test_home(Path(a.home))
    cast_all = characters(home)
    print(f"{len(cast_all)} characters that differ in origin and colour")
    results = []
    for key in a.models.split(","):
        for n in map(int, a.counts.split(",")):
            for seed in map(int, a.seeds.split(",")):
                cast = cast_all[(seed * 3) % len(cast_all):] + cast_all[:(seed * 3) % len(cast_all)]
                cast = cast[:n]
                r = run(MODELS[key], template(cast), seed, home)
                rows = score(r, cast)
                results.append({"model": key, "n": n, "seed": seed, **r, "scored": rows,
                                "cast": [{k: c.get(k) for k in ("name", "origin", "gender", "colour", "hair", "outfit")} for c in cast]})
                ok = sum(not x["unwritten"] for x in rows)
                print(f"{key} n={n} seed={seed}: {r['seconds']}s written {ok}/{n} "
                      f"traits {sum(x['score'] for x in rows)}/{5 * n} swaps {sum(x['swap'] for x in rows)} "
                      f"form {sum(x['form'] for x in rows)}/{len(rows)}{' ERROR' if r['error'] else ''}", flush=True)
                (HERE / "results.json").write_text(json.dumps(results, indent=1))
        call("/free", {"unload_models": True, "free_memory": True})  # the next model loads into a clean GPU


if __name__ == "__main__":
    main()
