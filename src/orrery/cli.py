"""The `orrery` command line."""

import argparse
import json
import sys
from pathlib import Path

from orrery import manager
from orrery.dsl import MissingLibrary, expand_batch
from orrery.h3 import compile_scene
from orrery.home import resolve_home
from orrery.llm import InvalidProposal, backend_for


def _read_template(arg: str) -> str:
    p = Path(arg)
    return p.read_text(encoding="utf-8") if p.is_file() else arg


def _cmd_expand(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    template = _read_template(args.template)
    try:
        rows = expand_batch(template, args.seed, args.n, home.libraries(), home.weights())
    except MissingLibrary as err:
        print(f"orrery: {err}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([
            {"seed": e.seed, "text": e.text, "picks": {p.label: p.value for p in e.picks}}
            for e in rows
        ], ensure_ascii=False, indent=2))
        return 0
    for e in rows:
        print(f"[{e.seed}] {e.text}")
        if e.picks:
            print("     " + " · ".join(f"{p.label}: {p.value}" for p in e.picks))
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    try:
        result = compile_scene(_read_template(args.scene), args.seed, home.libraries(),
                               home.weights(), target=args.target)
    except MissingLibrary as err:
        print(f"orrery: {err}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({
            "seed": args.seed,
            "text": result.text,
            "picks": {p.label: p.value for p in result.picks},
            "lint": [{"severity": i.severity, "message": i.message} for i in result.lint],
        }, ensure_ascii=False, indent=2))
    else:
        print(result.text)
    for issue in result.lint:
        print(f"{issue.severity}: {issue.message}", file=sys.stderr)
    return 1 if any(i.severity == "error" for i in result.lint) else 0


LIB_HELP = """LLM-powered wildcard libraries. Configure the model in <home>/orrery.yaml:

  models:
    library:
      backend: transformers
      path: /home/pyro/repos/comfy-ui/models/LLM/Qwen3.5-2B
      device: auto

or any OpenAI-compatible server (backend: openai, base_url, model).
The model only proposes; you see a diff and confirm before anything is written."""


def _confirm(args: argparse.Namespace, question: str = "Apply?") -> bool:
    if args.yes:
        return True
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes", "j", "ja")


def _cmd_lib(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    try:
        return _LIB_ACTIONS[args.action](home, args)
    except (InvalidProposal, RuntimeError, KeyError, FileExistsError) as err:
        print(f"orrery: {err.args[0] if isinstance(err, KeyError) else err}", file=sys.stderr)
        return 3


def _lib_list(home, args) -> int:
    user = {p.stem for p in home.library_dir.glob("*.yaml")} if home.library_dir.exists() else set()
    for name, lib in sorted(home.libraries().items()):
        if name not in user:
            mark = "builtin"
        elif lib.meta.get("generated_by"):
            mark = f"LLM: {lib.meta['generated_by']}"
        else:
            mark = ""
        print(f"__{name}__".ljust(22) + f"{len(lib.entries):>4}  {mark}")
    return 0


def _lib_show(home, args) -> int:
    lib = manager._library(home, args.name)
    weights = home.weights()
    for e in lib.entries:
        w = weights.get(f"__{lib.name}__={e.value}", 1.0)
        tags = f"  [{', '.join(e.tags)}]" if e.tags else ""
        print(f"  {e.value}".ljust(36) + f"×{w:.2f}{tags}")
    return 0


def _lib_gen(home, args) -> int:
    backend = backend_for(home, "library")
    template = _read_template(args.template) if args.template else None
    print(f"{backend.name} is writing __{args.name}__ …", file=sys.stderr)
    values = manager.propose_new(home, args.name, backend, template, args.n)
    print(f"__{args.name}__ (new)\n" + "\n".join(f"  + {v}" for v in values))
    if _confirm(args, "Create this library?"):
        manager.create_library(home, args.name, values, backend.name)
        print(f"Created __{args.name}__. Undo with: orrery lib undo")
    return 0


def _apply_proposal(home, args, backend, ops) -> int:
    print(manager.diff_text(args.name, ops))
    if ops.empty():
        return 0
    if _confirm(args):
        manager.apply_ops(home, args.name, ops, by=backend.name)
        print("Applied. Undo with: orrery lib undo")
    else:
        print("Discarded.")
    return 0


def _lib_more(home, args) -> int:
    backend = backend_for(home, "library")
    print(f"{backend.name} is generating …", file=sys.stderr)
    return _apply_proposal(home, args, backend, manager.propose_more(home, args.name, backend, args.n))


def _lib_edit(home, args) -> int:
    backend = backend_for(home, "library")
    print(f"{backend.name} is thinking …", file=sys.stderr)
    ops = manager.propose_edit(home, args.name, args.instruction, backend)
    return _apply_proposal(home, args, backend, ops)


def _lib_undo(home, args) -> int:
    action = manager.undo(home)
    print(f"Restored the state before: {action}" if action else "Nothing to undo.")
    return 0


_LIB_ACTIONS = {"list": _lib_list, "show": _lib_show, "gen": _lib_gen, "more": _lib_more,
                "edit": _lib_edit, "undo": _lib_undo}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orrery", description=__doc__)
    parser.add_argument("--home", help="orrery home (default: $ORRERY_HOME or ~/.orrery)")
    sub = parser.add_subparsers(dest="command", required=True)

    ex = sub.add_parser("expand", help="expand a template (text or file) with seeded picks")
    ex.add_argument("template")
    ex.add_argument("--seed", type=int, default=0)
    ex.add_argument("-n", type=int, default=1, help="number of consecutive seeds")
    ex.add_argument("--json", action="store_true")
    ex.set_defaults(func=_cmd_expand)

    co = sub.add_parser("compile", help="compile a screenplay (.orr) for a target model")
    co.add_argument("scene", help="screenplay file or text")
    co.add_argument("--target", choices=["h3-base", "flat"], default="h3-base")
    co.add_argument("--seed", type=int, default=0)
    co.add_argument("--json", action="store_true")
    co.set_defaults(func=_cmd_compile)

    lib = sub.add_parser("lib", help="LLM-powered wildcard libraries", description=LIB_HELP,
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    lib_sub = lib.add_subparsers(dest="action", required=True)
    lib_sub.add_parser("list", help="all libraries with entry counts")
    show = lib_sub.add_parser("show", help="entries with learned weights")
    show.add_argument("name")
    gen = lib_sub.add_parser("gen", help="generate a missing library with the LLM")
    gen.add_argument("name")
    gen.add_argument("--template", help="template or screenplay giving context")
    gen.add_argument("-n", type=int, default=12)
    more = lib_sub.add_parser("more", help="propose more entries in the same spirit")
    more.add_argument("name")
    more.add_argument("-n", type=int, default=8)
    edit = lib_sub.add_parser("edit", help='natural-language edit, e.g. "move all cats to a new list"')
    edit.add_argument("name")
    edit.add_argument("instruction")
    lib_sub.add_parser("undo", help="restore the state before the last change")
    for p in (gen, more, edit):
        p.add_argument("--yes", action="store_true", help="apply without asking")
    lib.set_defaults(func=_cmd_lib)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
