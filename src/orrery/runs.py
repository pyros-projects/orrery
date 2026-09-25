"""The picks of recent runs, by prompt and node, so that outputs saved by ordinary Save nodes can be
logged to the galaxy without an Orrery Log node: the node remembers its picks under the ComfyUI
prompt it runs in, and the browser reports what that prompt's Save nodes wrote."""

from collections import OrderedDict

LIMIT = 64  # recent (prompt, node) runs kept
_RUNS: "OrderedDict[tuple[str, str], str]" = OrderedDict()


def current_prompt() -> str | None:
    """The id of the ComfyUI prompt being executed, or None outside an execution."""
    try:
        from comfy_execution.utils import get_executing_context  # ComfyUI
    except ImportError:
        return None
    ctx = get_executing_context()
    return ctx.prompt_id if ctx else None


def remember(prompt_id: str, node_id, picks: str) -> None:
    _RUNS[(str(prompt_id), str(node_id))] = picks
    _RUNS.move_to_end((str(prompt_id), str(node_id)))
    while len(_RUNS) > LIMIT:
        _RUNS.popitem(last=False)


def recall(prompt_id: str, node_id) -> str | None:
    return _RUNS.get((str(prompt_id), str(node_id)))
