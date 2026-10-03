"""Render a reel's segments on a running ComfyUI, one after the other, and log each run.

    python experiments/refmod-abc/render.py <api.json> <latent_path> <first-last> <results.json> \\
        [--set "OLD=>NEW" ...] [--host http://127.0.0.1:8188]

<api.json> is a workflow in ComfyUI's API format (Export (API) in the menu) with one Orrery Prompt.
Each run sets that prompt's segment, its latent_path (the store this variant renders into, under
output/<latent_path>/) and the Save Video prefix (refmod_abc/<latent_path>). --set replaces text in
the template, so a variant is a change of the screenplay, e.g.
--set "(refmod orrery_abc_salon)=>(refmod orrery_abc_salon at 0.5 from 35%)". For every run the
results file gets the status, the seconds, the peak VRAM (nvidia-smi) and the console lines of
orrery and the RefMod pack. It stops at the first run that fails.
"""

import copy
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


def call(host: str, path: str, body=None):
    req = urllib.request.Request(host + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read() or b"null")


class Peak(threading.Thread):
    """The highest VRAM nvidia-smi reports while it runs, in MiB."""

    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.running = 0, True

    def run(self):
        while self.running:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, check=False).stdout.split()
            self.peak = max([self.peak, *(int(v) for v in out if v.isdigit())])
            time.sleep(0.5)


def prepare(api: dict, segment: int, latent_path: str, edits: list[tuple[str, str]]) -> dict:
    api = copy.deepcopy(api)
    prompts = [node for node in api.values() if node["class_type"] == "OrreryPrompt"]
    if len(prompts) != 1:
        sys.exit("the workflow needs exactly one Orrery Prompt")
    inputs = prompts[0]["inputs"]
    inputs["segment"] = segment
    for old, new in edits:
        if old not in inputs["template"]:
            sys.exit(f"--set: {old!r} is not in the template")
        inputs["template"] = inputs["template"].replace(old, new)
    link = inputs.get("latent_path")
    if isinstance(link, list):  # a PrimitiveString feeds it
        api[str(link[0])]["inputs"]["value"] = latent_path
    else:
        inputs["latent_path"] = latent_path
    for node in api.values():
        if node["class_type"] == "SaveVideo":
            node["inputs"]["filename_prefix"] = f"refmod_abc/{latent_path}"
    return api


def render(host: str, api: dict, label: str) -> dict:
    seen = {e["t"] for e in call(host, "/internal/logs/raw")["entries"]}
    lines: list[str] = []

    def collect():
        for e in call(host, "/internal/logs/raw")["entries"]:
            if e["t"] not in seen:
                seen.add(e["t"])
                if any(k in e["m"] for k in ("[orrery]", "H3RefMod", "Error", "error", "Traceback")):
                    lines.append(e["m"].strip()[:300])

    sent = call(host, "/prompt", {"prompt": api, "client_id": "orrery-refmod-abc"})
    if sent.get("node_errors"):
        sys.exit(f"{label}: {json.dumps(sent['node_errors'])[:1500]}")
    pid, peak = sent["prompt_id"], Peak()
    peak.start()
    print(f"{label} queued", flush=True)
    while True:
        time.sleep(4)
        collect()
        history = call(host, f"/history/{pid}").get(pid)
        if history and history.get("status", {}).get("status_str") in ("success", "error"):
            break
    peak.running = False
    collect()
    status = history["status"]
    stamps = {m[0]: m[1].get("timestamp") for m in status.get("messages", []) if m[1].get("timestamp")}
    seconds = (max(stamps.values()) - stamps.get("execution_start", min(stamps.values()))) / 1000
    entry = {"run": label, "status": status["status_str"], "seconds": round(seconds, 1),
             "peak_vram_mib": peak.peak, "console": lines[-20:], "prompt_id": pid}
    if status["status_str"] == "error":
        entry["error"] = [m[1] for m in status.get("messages", []) if m[0] == "execution_error"]
    return entry


def main() -> None:
    args = sys.argv[1:]
    host, edits = "http://127.0.0.1:8188", []
    while "--set" in args:
        i = args.index("--set")
        old, _, new = args[i + 1].partition("=>")
        edits.append((old, new))
        del args[i:i + 2]
    if "--host" in args:
        i = args.index("--host")
        host = args[i + 1]
        del args[i:i + 2]
    if len(args) != 4:
        sys.exit(__doc__)
    api, latent_path, span, results = json.loads(Path(args[0]).read_text()), args[1], args[2], Path(args[3])
    first, _, last = span.partition("-")
    log = json.loads(results.read_text()) if results.exists() else []
    for segment in range(int(first), int(last or first) + 1):
        entry = render(host, prepare(api, segment, latent_path, edits), f"{latent_path}:{segment}")
        log.append(entry)
        results.write_text(json.dumps(log, indent=2, ensure_ascii=False))
        print(f"{entry['run']}: {entry['status']} in {entry['seconds']} s, peak {entry['peak_vram_mib']} MiB", flush=True)
        if entry["status"] != "success":
            sys.exit(f"{entry['run']} failed: {json.dumps(entry.get('error'))[:1500]}")


if __name__ == "__main__":
    main()
