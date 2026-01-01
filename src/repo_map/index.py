"""Repository index: symbols, imports, call sites, references.

The module naming convention is fixed by the assignment and already implemented below:
`--root` points at a package directory, and its name is the top-level package.

    --root ../fastapi/fastapi
    fastapi/__init__.py              -> fastapi
    fastapi/applications.py          -> fastapi.applications
    fastapi/openapi/utils.py         -> fastapi.openapi.utils
"""

from collections.abc import Iterator
from pathlib import Path

from repo_map.model import CallSite, Reference, Symbol


def iter_python_files(root: Path) -> Iterator[Path]:
    """All .py files under root, skipping hidden directories and __pycache__."""
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            continue
        yield path


def module_name(root: Path, path: Path) -> str:
    parts = [root.name, *path.relative_to(root).with_suffix("").parts]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def relative_file(root: Path, path: Path) -> str:
    """The `file` field of the output: relative to the parent of root, with forward slashes."""
    return path.relative_to(root.parent).as_posix()


class RepoIndex:
    @classmethod
    def build(cls, root: Path) -> "RepoIndex":
        raise NotImplementedError("RepoIndex.build")

    def resolve(self, name: str) -> str | None:
        """Canonical qualified name for a query name, following imports and re-exports.

        "fastapi.FastAPI" -> "fastapi.applications.FastAPI"; None if the name is unknown.
        """
        raise NotImplementedError("RepoIndex.resolve")

    def definitions(self, qualified_name: str) -> list[Symbol]:
        """Usually one symbol; several if the name is defined in both branches of an `if`."""
        raise NotImplementedError("RepoIndex.definitions")

    def references(self, qualified_name: str) -> list[Reference]:
        raise NotImplementedError("RepoIndex.references")

    def callers(self, qualified_name: str) -> list[Symbol]:
        raise NotImplementedError("RepoIndex.callers")

    def call_sites(self, qualified_name: str) -> list[CallSite]:
        """All calls whose scope is this symbol: internal, external, and unresolved."""
        raise NotImplementedError("RepoIndex.call_sites")

    def path(self, source: str, target: str) -> list[str] | None:
        raise NotImplementedError("RepoIndex.path")
