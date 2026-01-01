"""Command-line interface. The commands, arguments and JSON shape are the assignment contract."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from repo_map.index import RepoIndex
from repo_map.model import Reference, Symbol


class QueryError(Exception):
    pass


def symbol_json(symbol: Symbol) -> dict[str, Any]:
    return {
        "qualified_name": symbol.qualified_name,
        "kind": symbol.kind,
        "file": symbol.file,
        "line": symbol.line,
        "async": symbol.is_async,
    }


def reference_json(reference: Reference) -> dict[str, Any]:
    return {
        "kind": reference.kind,
        "file": reference.file,
        "line": reference.line,
        "scope": reference.scope,
    }


def resolve(index: RepoIndex, name: str) -> str:
    qualified_name = index.resolve(name)
    if qualified_name is None:
        raise QueryError(f"unknown symbol: {name}")
    return qualified_name


def sorted_symbols(symbols: list[Symbol]) -> list[dict[str, Any]]:
    unique = {(s.qualified_name, s.file, s.line): s for s in symbols}
    return [symbol_json(s) for _, s in sorted(unique.items())]


def run_definition(index: RepoIndex, args: argparse.Namespace) -> dict[str, Any]:
    qualified_name = resolve(index, args.symbol)
    return {
        "query": "definition",
        "input": args.symbol,
        "symbol": qualified_name,
        "results": sorted_symbols(index.definitions(qualified_name)),
    }


def run_references(index: RepoIndex, args: argparse.Namespace) -> dict[str, Any]:
    qualified_name = resolve(index, args.symbol)
    references = sorted(index.references(qualified_name), key=lambda r: (r.file, r.line, r.kind))
    return {
        "query": "references",
        "input": args.symbol,
        "symbol": qualified_name,
        "results": [reference_json(r) for r in references],
    }


def run_callers(index: RepoIndex, args: argparse.Namespace) -> dict[str, Any]:
    qualified_name = resolve(index, args.symbol)
    return {
        "query": "callers",
        "input": args.symbol,
        "symbol": qualified_name,
        "results": sorted_symbols(index.callers(qualified_name)),
    }


def run_callees(index: RepoIndex, args: argparse.Namespace) -> dict[str, Any]:
    qualified_name = resolve(index, args.symbol)
    sites = sorted(index.call_sites(qualified_name), key=lambda c: (c.file, c.line, c.expression))
    internal = [c.target for c in sites if c.resolution == "internal" and c.target]
    return {
        "query": "callees",
        "input": args.symbol,
        "symbol": qualified_name,
        "results": sorted_symbols([s for t in set(internal) for s in index.definitions(t)]),
        "external": [
            {"expression": c.expression, "target": c.target, "file": c.file, "line": c.line}
            for c in sites
            if c.resolution == "external"
        ],
        "unresolved": [
            {"expression": c.expression, "file": c.file, "line": c.line, "reason": c.reason}
            for c in sites
            if c.resolution == "unresolved"
        ],
    }


def run_path(index: RepoIndex, args: argparse.Namespace) -> dict[str, Any]:
    source = resolve(index, args.source)
    target = resolve(index, args.target)
    return {
        "query": "path",
        "source": source,
        "target": target,
        "path": index.path(source, target),
    }


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root",
        type=Path,
        required=True,
        help="package directory to analyze; its name is the top-level package",
    )

    parser = argparse.ArgumentParser(
        prog="repo-map",
        description="Query a Tree-sitter index of a Python package. Output is JSON on stdout.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    for name, run, help_text in [
        ("definition", run_definition, "where a symbol is defined"),
        ("references", run_references, "resolved references to a symbol"),
        ("callers", run_callers, "functions and methods that call a symbol"),
        ("callees", run_callees, "calls made from a function or method"),
    ]:
        command = commands.add_parser(name, parents=[common], help=help_text)
        command.add_argument("symbol", help="qualified name, e.g. fastapi.FastAPI")
        command.set_defaults(run=run)

    command = commands.add_parser(
        "path", parents=[common], help="shortest path in the approximate call graph"
    )
    command.add_argument("source")
    command.add_argument("target")
    command.set_defaults(run=run_path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        parser.error(f"--root is not a directory: {args.root}")

    try:
        index = RepoIndex.build(args.root.resolve())
        result = args.run(index, args)
    except QueryError as error:
        print(f"repo-map: {error}", file=sys.stderr)
        return 1
    except NotImplementedError as error:
        print(f"repo-map: not implemented yet: {error}", file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
