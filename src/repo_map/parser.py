"""Minimal Tree-sitter setup for Python."""

from pathlib import Path

import tree_sitter_python
from tree_sitter import Language, Node, Parser, Tree

PYTHON = Language(tree_sitter_python.language())


def make_parser() -> Parser:
    return Parser(PYTHON)


def parse_bytes(source: bytes) -> Tree:
    return make_parser().parse(source)


def parse_file(path: Path) -> Tree:
    return parse_bytes(path.read_bytes())


def node_text(node: Node) -> str:
    """Source text of a node (Tree-sitter keeps the bytes it was given)."""
    assert node.text is not None
    return node.text.decode("utf-8")


def line_of(node: Node) -> int:
    """1-based line number; Tree-sitter rows start at 0."""
    return node.start_point.row + 1
