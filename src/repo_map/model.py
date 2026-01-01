"""Basic data structures of the index.

You may add fields and new classes. The CLI relies only on the fields used in `cli.py`.
"""

from dataclasses import dataclass
from typing import Literal

SymbolKind = Literal["module", "class", "function", "method"]
ReferenceKind = Literal["import", "call", "other"]
Resolution = Literal["internal", "external", "unresolved"]


@dataclass(frozen=True)
class Symbol:
    qualified_name: str  # fastapi.applications.FastAPI.openapi
    kind: SymbolKind
    file: str  # path relative to the parent of --root: fastapi/applications.py
    line: int  # 1-based
    is_async: bool = False


@dataclass(frozen=True)
class Import:
    module: str  # as written: "json", "fastapi.routing", ".b", "..utils"
    name: str | None  # imported name for `from module import name`, None for `import module`
    alias: str  # the local name this import binds
    file: str
    line: int
    scope: str  # qualified name of the enclosing module, class or function


@dataclass(frozen=True)
class CallSite:
    expression: str  # the callee expression: "run_helper", "b.Formatter", "dependant.call"
    file: str
    line: int
    scope: str  # qualified name of the enclosing function, method, class or module
    resolution: Resolution
    target: str | None = None  # qualified name for internal and external calls
    reason: str | None = None  # why the call is unresolved


@dataclass(frozen=True)
class Reference:
    target: str  # qualified name of the referenced project symbol
    kind: ReferenceKind
    file: str
    line: int
    scope: str
