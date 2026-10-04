"""The example workflows run as they load (#277): ComfyUI hands a node's saved widget values out by position, so each
orrery node in them saves as many values as it has widgets, each of its widget's kind. A new input shifts them; this
test says so before a user's Run does."""

import json
from pathlib import Path

import pytest

from orrery.comfy import NODE_CLASS_MAPPINGS

EXAMPLES = sorted((Path(__file__).parent.parent / "example_workflows").glob("*.json"))
CONTROLS = {"fixed", "increment", "decrement", "randomize"}


def widget_kinds(node_class) -> list[str]:
    """The kinds of a node's saved widget values in the frontend's order: required, then optional; an INT with
    control_after_generate saves its control right after it. Sockets (IMAGE, MODEL …, forceInput) save nothing."""
    types = node_class.INPUT_TYPES()
    kinds = []
    for section in ("required", "optional"):
        for spec in types.get(section, {}).values():
            kind, opts = spec[0], spec[1] if len(spec) > 1 else {}
            if opts.get("forceInput"):
                continue
            if isinstance(kind, list):
                kinds.append("COMBO")
            elif kind in ("STRING", "INT", "FLOAT", "BOOLEAN"):
                kinds.append(kind)
                if opts.get("control_after_generate"):
                    kinds.append("CONTROL")
    return kinds


def fits(kind: str, value) -> bool:
    return {"STRING": isinstance(value, str), "COMBO": isinstance(value, str), "CONTROL": value in CONTROLS,
            "INT": isinstance(value, int) and not isinstance(value, bool), "BOOLEAN": isinstance(value, bool),
            "FLOAT": isinstance(value, int | float) and not isinstance(value, bool)}[kind]


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_orrery_node_in_an_example_saves_its_widget_values_in_order(path):
    nodes = [n for n in json.loads(path.read_text(encoding="utf-8"))["nodes"] if n["type"] in NODE_CLASS_MAPPINGS]
    assert nodes, f"{path.name} has no orrery node"
    for node in nodes:
        kinds, values = widget_kinds(NODE_CLASS_MAPPINGS[node["type"]]), node.get("widgets_values") or []
        assert len(values) == len(kinds), f"{path.name}: {node['type']} {node['id']} saves {len(values)} values for {len(kinds)} widgets"
        wrong = [(i, k, v) for i, (k, v) in enumerate(zip(kinds, values, strict=True)) if not fits(k, v)]
        assert not wrong, f"{path.name}: {node['type']} {node['id']}: {wrong}"
