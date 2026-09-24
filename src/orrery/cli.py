"""The `orrery` command line."""

import argparse
import json
import sys

from orrery import manager
from orrery.comfy import h3_length
from orrery.dsl import MissingLibrary, bindings, expand_batch, override, parse
from orrery.h3 import compile_scene, count_chunks
from orrery.home import resolve_home
from orrery.llm import InvalidProposal, backend_for
from orrery.presets import (
    delete_preset,
    is_builtin,
    list_presets,
    load_preset,
    preset_meta,
    resolve_template,
    save_preset,
    tag_preset,
)


def _msg(err: Exception) -> str:
    """KeyError str() adds quotes; MissingLibrary has its own message."""
    if isinstance(err, KeyError) and not isinstance(err, MissingLibrary):
        return str(err.args[0])
    return str(err)


def _dials(template: str, pairs: list[str]) -> str:
    """`--set NAME=VALUE` pairs applied to the template's bindings."""
    values = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise KeyError(f"--set takes NAME=VALUE, not {pair!r}")
        values[name.strip().lstrip("$")] = value
    known = [name for name, _ in bindings(template)]
    for name in values:
        if name not in known:
            listed = ", ".join(f"${n}" for n in known) or "none"
            raise KeyError(f"there is no binding ${name} to set (this template has: {listed})")
    return override(template, values)


def _cmd_expand(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    try:
        template = _dials(resolve_template(home, args.template), args.set)
        params = parse(template).params
        seed = args.seed if args.seed is not None else (params.seed or 0)
        count = args.n if args.n is not None else (params.count or 1)
        rows = expand_batch(template, seed, count, home.libraries(), home.weights())
    except KeyError as err:
        print(f"orrery: {_msg(err)}", file=sys.stderr)
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
        scene = _dials(resolve_template(home, args.scene), args.set)
        chunks = count_chunks(scene)
        segments = [args.segment or 0] if args.segment is not None or not chunks else range(chunks)
        results = [compile_scene(scene, args.seed, home.libraries(), home.weights(), target=args.target,
                                 segment=k) for k in segments]
    except (KeyError, ValueError) as err:
        print(f"orrery: {_msg(err)}", file=sys.stderr)
        return 2
    whole_reel = len(results) > 1 or (chunks and args.segment is None)
    for n, result in enumerate(results, start=1):
        if args.json:
            print(json.dumps({
                "seed": args.seed,
                **({"segment": result.segment} if chunks else {}),
                "text": result.text,
                "loras": result.loras,
                "picks": {p.label: p.value for p in result.picks},
                "lint": [{"severity": i.severity, "message": i.message} for i in result.lint],
            }, ensure_ascii=False, indent=2))
        elif whole_reel:
            secs = result.scene.duration
            lora = f" · {result.loras}" if result.loras else ""
            print(f"{'' if n == 1 else chr(10)}# CHUNK {n}/{chunks} · {secs:.2f} s · {h3_length(secs)} frames{lora}\n")
            print(result.text)
        else:
            print(result.text)
        for issue in result.lint:
            print(f"{issue.severity}: {issue.message}", file=sys.stderr)
    return 1 if any(i.severity == "error" for r in results for i in r.lint) else 0


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
        print(f"orrery: {_msg(err)}", file=sys.stderr)
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
    template = resolve_template(home, args.template) if args.template else None
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


def _cmd_preset(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    try:
        if args.action == "list":
            for name in list_presets(home, tag=args.tag, folder=args.folder):
                meta = preset_meta(home, name)
                first = load_preset(home, name).strip().splitlines()[:1]
                title = meta.get("title") or (first[0][:60] if first else "")
                tags = meta.get("tags") or []
                label = f"@{name}" + (f"  [{', '.join(tags)}]" if tags else "")
                mark = "  (built-in)" if is_builtin(home, name) else ""
                print(label.ljust(44) + " " + title + mark)
        elif args.action == "show":
            print(load_preset(home, args.name), end="")
        elif args.action == "save":
            tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
            name = save_preset(home, args.name, resolve_template(home, args.template),
                               args.overwrite, tags)
            print(f"Saved @{name}")
        elif args.action in ("tag", "untag"):
            change = {"add": args.tags} if args.action == "tag" else {"remove": args.tags}
            tags = tag_preset(home, args.name, **change)
            print(f"@{args.name}: " + (", ".join(tags) or "(no tags)"))
        elif args.action == "rm":
            delete_preset(home, args.name)
            print(f"Removed @{args.name}")
    except (KeyError, FileExistsError, ValueError) as err:
        print(f"orrery: {_msg(err)}", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orrery", description=__doc__)
    parser.add_argument("--home", help="orrery home (default: $ORRERY_HOME or ~/.orrery)")
    sub = parser.add_subparsers(dest="command", required=True)

    ex = sub.add_parser("expand", help="expand a template (text or file) with seeded picks")
    ex.add_argument("template")
    ex.add_argument("--seed", type=int, help="first seed (default: the template's : seed=, else 0)")
    ex.add_argument("-n", type=int, help="number of consecutive seeds (default: : xN, else 1)")
    ex.add_argument("--json", action="store_true")
    ex.set_defaults(func=_cmd_expand)
    dial_help = "turn a dial: give binding $NAME a new expression (repeatable)"
    ex.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help=dial_help)

    co = sub.add_parser("compile", help="compile a screenplay (.orr) for a target model")
    co.add_argument("scene", help="screenplay file or text")
    co.add_argument("--target", choices=["h3-base", "flat"], default="h3-base")
    co.add_argument("--seed", type=int, default=0)
    co.add_argument("--json", action="store_true")
    co.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help=dial_help)
    co.add_argument("--segment", type=int, help="a reel's chunk, from 0 (default: print every chunk)")
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

    preset = sub.add_parser("preset", help="named templates, usable as @name everywhere")
    preset_sub = preset.add_subparsers(dest="action", required=True)
    p_list = preset_sub.add_parser("list", help="presets with tags and first line")
    p_list.add_argument("--tag")
    p_list.add_argument("--folder")
    p_show = preset_sub.add_parser("show", help="print a preset")
    p_show.add_argument("name")
    p_save = preset_sub.add_parser(
        "save", help="save a template (text, file, @preset or #hash from galaxy.jsonl)")
    p_save.add_argument("name")
    p_save.add_argument("template")
    p_save.add_argument("--overwrite", action="store_true")
    p_save.add_argument("--tags", help="comma-separated")
    for action in ("tag", "untag"):
        p_tag = preset_sub.add_parser(action, help=f"{action} a preset")
        p_tag.add_argument("name")
        p_tag.add_argument("tags", nargs="+")
    p_rm = preset_sub.add_parser("rm", help="delete a preset")
    p_rm.add_argument("name")
    preset.set_defaults(func=_cmd_preset)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
