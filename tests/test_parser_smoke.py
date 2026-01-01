from pathlib import Path

import pytest

from repo_map.cli import main
from repo_map.index import iter_python_files, module_name, relative_file
from repo_map.parser import line_of, node_text, parse_file

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_pkg"


def test_parses_function_definition():
    tree = parse_file(FIXTURE / "a.py")
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error

    functions = [n for n in tree.root_node.named_children if n.type == "function_definition"]
    names = [node_text(f.child_by_field_name("name")) for f in functions]
    assert names == ["public_api", "render"]
    assert line_of(functions[0]) == 7


def test_module_names_follow_root():
    names = [module_name(FIXTURE, path) for path in iter_python_files(FIXTURE)]
    assert names == ["tiny_pkg", "tiny_pkg.a", "tiny_pkg.b"]
    assert relative_file(FIXTURE, FIXTURE / "b.py") == "tiny_pkg/b.py"


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert "definition" in capsys.readouterr().out
