"""Queue a template on the ComfyUI that is already running, with the graph of a clip it made before.

    python experiments/refmod-abc/queue.py <clip.mp4> <template.orr> <segment>

The clip's metadata holds the workflow it was made with (Save Video stores it). This script takes
that graph, puts the template and the segment into its Orrery Prompt, wires the H3 video VAE into
Orrery RefMods' vae when it has none (sent RefMods need it), and posts it to :8188. Run it only on
the instance Pyro works in, after asking: a second ComfyUI freezes the machine.
"""

import json
import sys
import urllib.request

import av

URL = "http://127.0.0.1:8188"


def graph(clip: str) -> tuple[dict, dict | None]:
    with av.open(clip) as container:
        meta = dict(container.metadata)
    return json.loads(meta["prompt"]), json.loads(meta["workflow"]) if meta.get("workflow") else None


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    prompt, workflow = graph(sys.argv[1])
    template, segment = open(sys.argv[2]).read(), int(sys.argv[3])
    nodes = prompt.values()
    orrery = next(n for n in nodes if n["class_type"] == "OrreryPrompt")
    orrery["inputs"].update(template=template, segment=segment)
    vae = next(k for k, n in prompt.items() if n["class_type"] == "VAELoader" and "video" in n["inputs"]["vae_name"])
    for n in nodes:
        if n["class_type"] == "OrreryRefMods":
            n["inputs"].setdefault("vae", [vae, 0])
    body = {"prompt": prompt, "client_id": "orrery-experiment",
            **({"extra_data": {"extra_pnginfo": {"workflow": workflow}}} if workflow else {})}
    request = urllib.request.Request(f"{URL}/prompt", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as answer:
        print(json.loads(answer.read())["prompt_id"])


if __name__ == "__main__":
    main()
