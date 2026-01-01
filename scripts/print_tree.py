"""Print the named nodes of a Python file's syntax tree.

    uv run python scripts/print_tree.py tests/fixtures/tiny_pkg/a.py

Each line shows `field: node_type [line:column]` (1-based line, 0-based column) and the
text of short leaf nodes. Anonymous nodes (punctuation, keywords) are skipped.
"""

import sys
from pathlib import Path

from tree_sitter import Node

from repo_map.parser import line_of, node_text, parse_file


def print_node(node: Node, field: str | None, depth: int) -> None:
    label = f"{field}: {node.type}" if field else node.type
    position = f"[{line_of(node)}:{node.start_point.column}]"
    text = f"  {node_text(node)!r}" if node.named_child_count == 0 else ""
    print(f"{'  ' * depth}{label} {position}{text}")
    for i, child in enumerate(node.children):
        if child.is_named:
            print_node(child, node.field_name_for_child(i), depth + 1)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: print_tree.py FILE.py")
    print_node(parse_file(Path(sys.argv[1])).root_node, None, 0)


if __name__ == "__main__":
    main()
