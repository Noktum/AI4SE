import json
from pathlib import Path

from repo_map.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_pkg"


def query(capsys, *args: str) -> dict:
    assert main([*args, "--root", str(FIXTURE)]) == 0
    return json.loads(capsys.readouterr().out)


def test_definition_and_reexport(capsys):
    result = query(capsys, "definition", "tiny_pkg.public_api")
    assert result["symbol"] == "tiny_pkg.a.public_api"
    assert result["results"] == [
        {
            "qualified_name": "tiny_pkg.a.public_api",
            "kind": "function",
            "file": "tiny_pkg/a.py",
            "line": 7,
            "async": False,
        }
    ]

    nested = query(capsys, "definition", "tiny_pkg.b.Formatter._wrap")
    assert nested["symbol"] == "tiny_pkg.b.Formatter._wrap"
    assert nested["results"][0]["kind"] == "method"
    assert nested["results"][0]["line"] == 13


def test_references(capsys):
    result = query(capsys, "references", "tiny_pkg.b.helper")
    assert [
        (item["kind"], item["file"], item["line"], item["scope"]) for item in result["results"]
    ] == [
        ("import", "tiny_pkg/a.py", 4, "tiny_pkg.a"),
        ("call", "tiny_pkg/a.py", 8, "tiny_pkg.a.public_api"),
        ("call", "tiny_pkg/b.py", 11, "tiny_pkg.b.Formatter.format"),
    ]


def test_callers(capsys):
    result = query(capsys, "callers", "tiny_pkg.b.helper")
    assert [item["qualified_name"] for item in result["results"]] == [
        "tiny_pkg.a.public_api",
        "tiny_pkg.b.Formatter.format",
    ]


def test_callees(capsys):
    result = query(capsys, "callees", "tiny_pkg.a.render")
    assert [item["qualified_name"] for item in result["results"]] == ["tiny_pkg.b.Formatter"]
    assert result["external"] == [
        {
            "expression": "json.dumps",
            "target": "json.dumps",
            "file": "tiny_pkg/a.py",
            "line": 13,
        }
    ]
    assert result["unresolved"] == [
        {
            "expression": "formatter.format",
            "file": "tiny_pkg/a.py",
            "line": 13,
            "reason": "local variable",
        }
    ]


def test_path(capsys):
    result = query(capsys, "path", "tiny_pkg.public_api", "tiny_pkg.b.normalize")
    assert result["path"] == [
        "tiny_pkg.a.public_api",
        "tiny_pkg.b.helper",
        "tiny_pkg.b.normalize",
    ]


def test_unknown_symbol(capsys):
    assert main(["definition", "tiny_pkg.missing", "--root", str(FIXTURE)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown symbol: tiny_pkg.missing" in captured.err
