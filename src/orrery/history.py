"""The prompt history: every run of an Orrery Prompt as it resolved (when, the seed, the segment, the
template and dials, the picks and the prompt), so a lucky roll can be found and run again even when its
output was not kept. One JSON line per run in `prompt_history.jsonl` in the orrery home, the last
`KEEP` runs. The galaxy keeps what was saved; this keeps what was asked."""

import json
import time
import uuid

from orrery.home import Home, write_atomic

FILE = "prompt_history.jsonl"
KEEP = 2000  # runs kept; the file is trimmed back to this when it grows a quarter past it
FIELDS = ("seed", "target", "template", "preset", "edited", "params", "rng", "format", "text", "picks", "segment",
          "sweep")


def _path(home: Home):
    return home.root / FILE


def record(home: Home, data: dict) -> dict:
    """Append one run (the Orrery Prompt's picks data) and return the row."""
    row = {"id": uuid.uuid4().hex[:12], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
           **{k: data[k] for k in FIELDS if data.get(k) is not None},
           "issues": sum(1 for i in data.get("lint") or [] if i.get("severity") in ("warn", "error"))}
    path = _path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > KEEP * 1.25:
        write_atomic(path, "\n".join(lines[-KEEP:]) + "\n")
    return row


def _rows(home: Home) -> list[dict]:
    path = _path(home)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue  # a line cut short by a crash: the rest still reads
    return rows


def _matches(row: dict, query: str) -> bool:
    picks = " ".join(f"{p.get('label', '')} {p.get('value', '')}" for p in row.get("picks") or [])
    return query in f"{row.get('text', '')} {picks} {row.get('preset') or ''} {row.get('seed', '')}".lower()


def read(home: Home, limit: int = 50, offset: int = 0, query: str = "") -> dict:
    """Runs newest first, those whose prompt, picks, preset or seed contain `query`."""
    rows = list(reversed(_rows(home)))
    if query.strip():
        rows = [r for r in rows if _matches(r, query.strip().lower())]
    return {"runs": rows[offset:offset + limit], "total": len(rows)}


def log_lines(data: dict) -> list[str]:
    """The run for ComfyUI's log: what made it, every pick, and the prompt."""
    head = [f"seed {data.get('seed')}"]
    if data.get("segment") is not None:
        head.append(f"segment {data['segment']}")
    if data.get("preset"):
        head.append(f"@{data['preset']}{' (edited)' if data.get('edited') else ''}")
    if data.get("params"):
        head.append(f"dials {', '.join(f'${k} = {v}' for k, v in data['params'].items())}")
    lines = [f"[orrery] run · {' · '.join(head)}"]
    lines += [f"[orrery]   {p.get('label')} = {p.get('value')}" for p in data.get("picks") or []]
    lines.append("[orrery] prompt:")
    return [*lines, *(data.get("text") or "").splitlines()]
