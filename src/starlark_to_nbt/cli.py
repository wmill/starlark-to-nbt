from __future__ import annotations

import argparse
from pathlib import Path

from .model import BuildError
from .pipeline import build_file, write_build_outputs


def _arg_value(value: str):
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    for parse in (int, float):
        try:
            return parse(value)
        except ValueError:
            continue
    return value


def main() -> None:
    parser = argparse.ArgumentParser(prog="starlark-to-nbt")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build a Starlark structure")
    build.add_argument("source", type=Path)
    build.add_argument("--entry", default="build")
    build.add_argument("--arg", action="append", default=[], metavar="NAME=VALUE")
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--debug-dir", type=Path)
    args = parser.parse_args()

    props = {}
    for raw in args.arg:
        if "=" not in raw:
            parser.error(f"invalid --arg {raw!r}; expected NAME=VALUE")
        name, value = raw.split("=", 1)
        props[name] = _arg_value(value)
    try:
        result = build_file(args.source, args.entry, props)
        write_build_outputs(result, args.output, args.debug_dir)
    except BuildError as exc:
        parser.exit(1, f"{exc}\n")
