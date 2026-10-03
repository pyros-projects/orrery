"""Live smoke test of the language model over an API (#165): every path, against a real endpoint.

    uv run python experiments/api-llm/smoke.py gpt-6-luna [home]

The key comes from OPENAI_API_KEY (or the repo's untracked .env) and is never printed. It runs in a scratch
home of its own (never ~/.orrery), loads no model and needs no GPU. The pictures are two Krea characters
from the gallery (generated people, with what EXPORT: kept about them to compare against). Writes
results-<model>.json beside this file.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent.parent
PICTURES = [Path("/home/pyro/repos/comfy-ui/output/Krea2/krea2_00166_.png"),  # a 23-year-old woman, Fijian descent
            Path("/home/pyro/repos/comfy-ui/output/Krea2/krea2_00167_.png")]  # a 57-year-old man, Polish descent

model = sys.argv[1] if len(sys.argv) > 1 else "gpt-6-luna"
home_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.mkdtemp(prefix="orrery-api-"))
(home_dir / "library").mkdir(parents=True, exist_ok=True)
os.environ["ORRERY_HOME"] = str(home_dir)
if not os.environ.get("OPENAI_API_KEY") and (REPO / ".env").exists():
    for line in (REPO / ".env").read_text().splitlines():
        if line.startswith("OPENAI_API_KEY="):
            KEY = line.split("=", 1)[1].strip()
            break
else:
    KEY = os.environ.get("OPENAI_API_KEY", "")
os.environ.pop("OPENAI_API_KEY", None)  # the settings write it to the scratch home's .env, as the UI does

from orrery import comfy, endpoint, webapi  # noqa: E402
from orrery.home import Home  # noqa: E402

results: dict = {"model": model, "home": str(home_dir), "steps": {}}


def step(name):
    def wrap(fn):
        start = time.monotonic()
        try:
            out = fn()
            results["steps"][name] = {"seconds": round(time.monotonic() - start, 1), **out}
        except Exception as err:  # noqa: BLE001 - a smoke test reports and goes on
            results["steps"][name] = {"seconds": round(time.monotonic() - start, 1), "error": f"{type(err).__name__}: {err}"}
        print(f"\n=== {name} ({results['steps'][name]['seconds']} s)")
        print(json.dumps({k: v for k, v in results["steps"][name].items() if k != "seconds"}, indent=1,
                         ensure_ascii=False)[:2500])
        return fn
    return wrap


def call(fn, **args):
    status, body = webapi.call(fn, {"home": str(home_dir), **args})
    return {"status": status, "body": body}


@step("1 check: key, models, one answer")
def _():
    got = endpoint.check(endpoint.DEFAULT_URL, KEY, model)
    return {"ok": got["ok"], "answer": got.get("answer"), "error": got.get("error"), "models": len(got["models"]),
            "luna_sol": [m for m in got["models"] if "luna" in m or "sol" in m]}


@step("2 settings: a wrong key is refused, the right one saved to .env")
def _():
    wrong = call(webapi.llm_save, source="api", model=model, key="sk-wrong-0000")
    right = call(webapi.llm_save, source="api", model=model, key=KEY, entries=8)
    env = (home_dir / ".env").read_text()
    return {"wrong": wrong["status"], "wrong_error": wrong["body"].get("error"), "right": right["status"],
            "active": right["body"].get("active"), "key_shown_as_hint": right["body"].get("api", {}).get("key", "").startswith("…"),
            "key_in_yaml": KEY in (home_dir / "orrery.yaml").read_text(), "key_in_env_file": KEY in env,
            "env_mode": oct((home_dir / ".env").stat().st_mode & 0o777)}


TEMPLATE = ("a __fantasy_peoples__ __fantasy_trades__ in __haunted_places__(a place, 3 to 6 words, eerie), "
            "carrying __odd_heirlooms:6__")


@step("3 write now: three new libraries and a top-up, in parallel")
def _():
    (home_dir / "library" / "odd_heirlooms.yaml").write_text("- a cracked pocket watch\n- a ring of braided hair\n"
                                                               "- a key to no door\n")
    got = call(webapi.write_libraries, template=TEMPLATE)
    libs = Home(home_dir).libraries()
    return {**got, "libraries": {n: libs[n].values() for n in
                                 ("fantasy_peoples", "fantasy_trades", "haunted_places", "odd_heirlooms") if n in libs},
            "again": call(webapi.write_libraries, template=TEMPLATE)["body"]}


@step("4 run (text): a new library apart, then slot and enhance in one request")
def _():
    template = ("portrait of a __fantasy_peoples__ with __rain_moods__, --their face in one vivid sentence--\n"
                "> painterly, candlelit, more texture")
    text, picks, *_ = comfy.run_prompt(template, 7, "text", str(home_dir))
    lint = [i["message"] for i in json.loads(picks)["lint"]]
    return {"text": text, "lint": lint, "rain_moods": Home(home_dir).libraries().get("rain_moods").values()}


@step("5 run (h3): a slot that sees the previous clip's frames")
def _():
    import numpy as np
    from PIL import Image
    size = Image.open(PICTURES[0]).size
    frames = np.stack([np.asarray(Image.open(p).convert("RGB").resize(size), dtype="float32") / 255 for p in PICTURES])
    template = "@h3 t2va 9:16\nSHOT 5s: medium shot\n--what happens next, from the last frame on--\nSFX: a door creaks"
    text, picks, *_ = comfy.run_prompt(template, 3, "h3-base", str(home_dir), frames=frames)
    return {"text": text, "lint": [i["message"] for i in json.loads(picks)["lint"]]}


@step("6 write menu: describe, from a picture (Load Image)")
def _():
    webapi._input_picture = lambda name: {"a.png": PICTURES[0], "b.png": PICTURES[1]}.get(name)
    return call(webapi.write_idea, task="describe", template="a portrait", seed=1, frames={"first_frame": "a.png"})["body"]


@step("7 write menu: story between two frames (fl2va)")
def _():
    template = "@h3 fl2va 9:16\nSHOT 5s: medium shot\nA moment between them.\nSFX: room tone"
    return call(webapi.write_idea, task="story", template=template, seed=1,
                frames={"first_frame": "a.png", "last_frame": "b.png"})["body"]


@step("8 write menu: continue a reel")
def _():
    template = ("@h3 t2va 16:9\nSCENE arrival\nSHOT 5s: wide\nA lighthouse keeper climbs the stairs in a storm.\n"
                "SFX: wind, rain on glass\nSCENE the lamp\nSHOT 5s: close\nShe finds the lamp dark and a stranger's "
                "lantern burning in its place.\nSFX: a match strikes\n")
    return call(webapi.write_idea, task="continue", template=template, seed=1)["body"]


@step("9 orrery lib gen (CLI) through the endpoint")
def _():
    run = subprocess.run(["uv", "run", "orrery", "lib", "gen", "storm_omens", "-n", "6", "--yes"], cwd=REPO,
                         capture_output=True, text=True, env={**os.environ, "ORRERY_HOME": str(home_dir)}, timeout=300)
    return {"code": run.returncode, "out": run.stdout[-800:], "err": run.stderr[-400:]}


@step("10 a refused key: write now says so")
def _():
    endpoint.save_key(Home(home_dir), "OPENAI_API_KEY", "sk-wrong-0000")
    got = call(webapi.write_libraries, template="a __broken_lists__")
    endpoint.save_key(Home(home_dir), "OPENAI_API_KEY", KEY)
    return got


(HERE / f"results-{model}.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
print(f"\nresults: {HERE / f'results-{model}.json'}")
