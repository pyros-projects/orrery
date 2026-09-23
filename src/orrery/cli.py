"""The `orrery` command line."""

import argparse
import json
import sys
from pathlib import Path

from orrery.dsl import MissingLibrary, expand_batch
from orrery.home import resolve_home


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
