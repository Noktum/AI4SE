"""Public smoke tests on FastAPI 0.141.1 (commit 95f8322).

They are not part of the default run. Clone FastAPI next to this repository and run

    uv run pytest -q -m fastapi

or point FASTAPI_ROOT at another checkout of the `fastapi/` package directory.
"""

import json
import os
from pathlib import Path

import pytest

from repo_map.cli import main

ROOT = Path(
    os.environ.get("FASTAPI_ROOT", Path(__file__).resolve().parents[2] / "fastapi" / "fastapi")
)

pytestmark = [
    pytest.mark.fastapi,
    pytest.mark.skipif(not ROOT.is_dir(), reason=f"FastAPI checkout not found at {ROOT}"),
]


def query(capsys, *args: str) -> dict:
    assert main([*args, "--root", str(ROOT)]) == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    ("name", "qualified_name", "file"),
    [
        ("fastapi.FastAPI", "fastapi.applications.FastAPI", "fastapi/applications.py"),
        ("fastapi.APIRouter", "fastapi.routing.APIRouter", "fastapi/routing.py"),
    ],
)
def test_definition_follows_reexport(capsys, name, qualified_name, file):
    result = query(capsys, "definition", name)
    assert result["symbol"] == qualified_name
    assert [(r["qualified_name"], r["file"]) for r in result["results"]] == [(qualified_name, file)]


def test_callers_of_get_openapi(capsys):
    result = query(capsys, "callers", "fastapi.openapi.utils.get_openapi")
    callers = {r["qualified_name"] for r in result["results"]}
    assert "fastapi.applications.FastAPI.openapi" in callers


def test_path_from_openapi_method(capsys):
    result = query(
        capsys,
        "path",
        "fastapi.applications.FastAPI.openapi",
        "fastapi.openapi.utils.get_openapi_path",
    )
    assert result["path"] == [
        "fastapi.applications.FastAPI.openapi",
        "fastapi.openapi.utils.get_openapi",
        "fastapi.openapi.utils.get_openapi_path",
    ]
