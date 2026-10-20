"""Repository index: symbols, imports, call sites, references.

The module naming convention is fixed by the assignment and already implemented below:
`--root` points at a package directory, and its name is the top-level package.

    --root ../fastapi/fastapi
    fastapi/__init__.py              -> fastapi
    fastapi/applications.py          -> fastapi.applications
    fastapi/openapi/utils.py         -> fastapi.openapi.utils
"""

import builtins
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tree_sitter import Node

from repo_map.graph import CallGraph
from repo_map.model import CallSite, Import, Reference, Resolution, Symbol, SymbolKind
from repo_map.parser import line_of, node_text, parse_file

TargetKind = Literal["symbol", "module", "external"]
BUILTIN_NAMES = frozenset(dir(builtins))


@dataclass(frozen=True)
class Target:
    kind: TargetKind
    name: str


@dataclass(frozen=True)
class RawCall:
    expression: str
    parts: list[str] | None
    file: str
    line: int
    scope: str


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


def _same_node(left: Node, right: Node | None) -> bool:
    return right is not None and left.id == right.id


def _is_async_function(node: Node) -> bool:
    return any(child.type == "async" for child in node.children) or node_text(
        node
    ).lstrip().startswith("async ")


def _chain(node: Node) -> list[str] | None:
    if node.type == "identifier":
        return [node_text(node)]
    if node.type == "attribute":
        obj = node.child_by_field_name("object")
        attr = node.child_by_field_name("attribute")
        if obj is None or attr is None:
            return None
        left = _chain(obj)
        if left is None:
            return None
        return [*left, node_text(attr)]
    return None


def _target_names(node: Node, names: set[str]) -> None:
    if node.type == "identifier":
        names.add(node_text(node))
        return
    if node.type in ("attribute", "subscript"):
        return
    for child in node.named_children:
        _target_names(child, names)


def _parameter_names(node: Node | None) -> set[str]:
    names: set[str] = set()
    if node is None:
        return names
    for child in node.named_children:
        if child.type == "identifier":
            names.add(node_text(child))
            continue
        name_node = child.child_by_field_name("name")
        if name_node is None and child.type in ("list_splat_pattern", "dictionary_splat_pattern"):
            name_node = next(
                (item for item in child.named_children if item.type == "identifier"), None
            )
        if name_node is None:
            name_node = next(
                (item for item in child.named_children if item.type == "identifier"), None
            )
        if name_node is not None:
            names.add(node_text(name_node))
    return names


class RepoIndex:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._symbols: dict[str, list[Symbol]] = {}
        self._symbols_by_scope: dict[str, dict[str, str]] = {}
        self._scope_kind: dict[str, SymbolKind] = {}
        self._scope_parent: dict[str, str | None] = {}
        self._scope_file: dict[str, str] = {}
        self._scope_locals: dict[str, set[str]] = {}
        self._scope_params: dict[str, set[str]] = {}
        self._patched_attributes: dict[str, set[tuple[str, ...]]] = {}
        self._modules: set[str] = set()
        self._module_is_package: dict[str, bool] = {}
        self._module_by_file: dict[str, str] = {}
        self._imports: list[Import] = []
        self._module_imports: dict[str, list[Import]] = {}
        self._binding_cache: dict[tuple[str, str], Target | None] = {}
        self._raw_calls: list[RawCall] = []
        self._call_sites: list[CallSite] = []
        self._references: list[Reference] = []
        self._graph: CallGraph | None = None

    @classmethod
    def build(cls, root: Path) -> "RepoIndex":
        index = cls(root)
        for path in iter_python_files(root):
            module = module_name(root, path)
            file = relative_file(root, path)
            index._modules.add(module)
            index._module_is_package[module] = path.name == "__init__.py"
            index._module_by_file[file] = module
            tree = parse_file(path)
            index._add_symbol(Symbol(module, "module", file, 1), parent=None)
            index._collect_local_names(tree.root_node, index._scope_locals[module])
            index._collect(tree.root_node, module, file)
        for raw in index._raw_calls:
            index._call_sites.append(index._resolve_call(raw))
        index._references = index._collect_references()
        index._graph = CallGraph.from_call_sites(index._call_sites, index._symbols)
        return index

    def _add_symbol(self, symbol: Symbol, parent: str | None) -> None:
        self._symbols.setdefault(symbol.qualified_name, []).append(symbol)
        self._symbols_by_scope.setdefault(symbol.qualified_name, {})
        self._scope_kind[symbol.qualified_name] = symbol.kind
        self._scope_parent[symbol.qualified_name] = parent
        self._scope_file[symbol.qualified_name] = symbol.file
        self._scope_locals.setdefault(symbol.qualified_name, set())
        if parent is not None:
            self._symbols_by_scope.setdefault(parent, {})[
                symbol.qualified_name.rsplit(".", 1)[-1]
            ] = symbol.qualified_name

    def _collect(self, node: Node, scope: str, file: str) -> None:
        for child in node.named_children:
            if child.type == "decorated_definition":
                definition = self._decorated_definition(child)
                for sibling in child.named_children:
                    if not _same_node(sibling, definition):
                        self._collect(sibling, scope, file)
                if definition is not None:
                    self._collect_definition(definition, scope, file)
            elif child.type in ("function_definition", "class_definition"):
                self._collect_definition(child, scope, file)
            elif child.type in ("import_statement", "import_from_statement"):
                self._collect_import(child, scope, file)
            else:
                if child.type in ("assignment", "augmented_assignment"):
                    left = child.child_by_field_name("left")
                    if left is not None:
                        chain = _chain(left)
                        if chain is not None and len(chain) > 1:
                            self._patched_attributes.setdefault(scope, set()).add(tuple(chain))
                if child.type == "call":
                    function = child.child_by_field_name("function")
                    self._raw_calls.append(
                        RawCall(
                            expression=node_text(function)
                            if function is not None
                            else node_text(child),
                            parts=_chain(function) if function is not None else None,
                            file=file,
                            line=line_of(child),
                            scope=scope,
                        )
                    )
                self._collect(child, scope, file)

    @staticmethod
    def _decorated_definition(node: Node) -> Node | None:
        for child in node.named_children:
            if child.type in ("function_definition", "class_definition"):
                return child
        return None

    def _collect_definition(self, node: Node, scope: str, file: str) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = node_text(name_node)
        qualified_name = f"{scope}.{name}"
        if node.type == "class_definition":
            kind: SymbolKind = "class"
        elif self._scope_kind.get(scope) == "class":
            kind = "method"
        else:
            kind = "function"
        symbol = Symbol(
            qualified_name=qualified_name,
            kind=kind,
            file=file,
            line=line_of(node),
            is_async=node.type == "function_definition" and _is_async_function(node),
        )
        self._add_symbol(symbol, parent=scope)

        body = node.child_by_field_name("body")
        child_scope = "class" if node.type == "class_definition" else kind
        if node.type == "function_definition":
            parameters = _parameter_names(node.child_by_field_name("parameters"))
            self._scope_params[qualified_name] = parameters
            self._scope_locals[qualified_name] |= parameters
        if body is not None:
            self._collect_local_names(body, self._scope_locals[qualified_name])

        for child in node.named_children:
            if _same_node(child, name_node) or _same_node(child, body):
                continue
            self._collect(child, scope, file)
        if body is not None:
            self._collect_scope_body(body, qualified_name, child_scope, file)

    def _collect_scope_body(
        self, body: Node, scope: str, scope_kind: SymbolKind, file: str
    ) -> None:
        self._scope_kind[scope] = scope_kind
        self._collect(body, scope, file)

    def _collect_local_names(self, node: Node, names: set[str]) -> None:
        if node.type in (
            "function_definition",
            "class_definition",
            "lambda",
            "decorated_definition",
        ):
            return
        if node.type in ("assignment", "augmented_assignment"):
            left = node.child_by_field_name("left")
            if left is not None:
                _target_names(left, names)
        elif node.type in ("for_statement", "for_in_clause"):
            left = node.child_by_field_name("left")
            if left is not None:
                _target_names(left, names)
        elif node.type == "named_expression":
            left = node.child_by_field_name("name") or node.child_by_field_name("left")
            if left is not None:
                _target_names(left, names)
        elif node.type == "as_pattern":
            alias = node.child_by_field_name("alias")
            if alias is not None:
                _target_names(alias, names)
        for child in node.named_children:
            self._collect_local_names(child, names)

    def _collect_import(self, node: Node, scope: str, file: str) -> None:
        line = line_of(node)
        if node.type == "import_statement":
            for child in node.named_children:
                if child.type == "aliased_import":
                    module_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    if module_node is None or alias_node is None:
                        continue
                    module = node_text(module_node)
                    alias = node_text(alias_node)
                    has_alias = True
                elif child.type == "dotted_name":
                    module = node_text(child)
                    alias = module.split(".")[0]
                    has_alias = False
                else:
                    continue
                self._add_import(Import(module, None, alias, file, line, scope, has_alias))
            return

        module_node = node.child_by_field_name("module_name")
        module = node_text(module_node) if module_node is not None else ""
        for child in node.named_children:
            if _same_node(child, module_node):
                continue
            if child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node is None or alias_node is None:
                    continue
                self._add_import(
                    Import(
                        module, node_text(name_node), node_text(alias_node), file, line, scope, True
                    )
                )
            elif child.type in ("dotted_name", "identifier"):
                imported = node_text(child)
                self._add_import(
                    Import(module, imported, imported.split(".")[-1], file, line, scope)
                )
            elif child.type == "wildcard_import":
                self._add_import(Import(module, "*", "*", file, line, scope))

    def _add_import(self, import_: Import) -> None:
        self._imports.append(import_)
        if import_.scope == self._module_by_file.get(import_.file):
            self._module_imports.setdefault(import_.scope, []).append(import_)
        else:
            self._scope_locals.setdefault(import_.scope, set()).add(import_.alias)

    def _absolute_module(self, current_module: str, written: str) -> str:
        if not written.startswith("."):
            return written
        level = len(written) - len(written.lstrip("."))
        rest = written[level:]
        if self._module_is_package.get(current_module):
            current_package = current_module
        else:
            current_package = current_module.rsplit(".", 1)[0]
        parts = current_package.split(".") if current_package else []
        if level > 1:
            parts = parts[: max(len(parts) - (level - 1), 0)]
        base = ".".join(parts)
        return f"{base}.{rest}" if rest else base

    def _resolve_import(self, import_: Import, current_module: str) -> Target | None:
        if import_.name is None:
            module = import_.module
            if module in self._modules:
                if import_.has_alias:
                    return Target("module", module)
                top = module.split(".")[0]
                if top in self._modules:
                    return Target("module", top)
                return Target("external", top)
            return Target("external", module if import_.has_alias else module.split(".")[0])

        absolute = self._absolute_module(current_module, import_.module)
        if absolute in self._modules:
            return self._resolve_attr(absolute, import_.name)
        if absolute:
            return Target("external", f"{absolute}.{import_.name}")
        return None

    def _resolve_binding(self, module: str, name: str) -> Target | None:
        key = (module, name)
        if key in self._binding_cache:
            return self._binding_cache[key]
        self._binding_cache[key] = None
        if name in self._scope_locals.get(module, set()):
            return None
        target: Target | None = self._symbols_by_scope.get(module, {}).get(name)
        if target is not None:
            result: Target | None = Target("symbol", target)
        else:
            result = None
            for import_ in reversed(self._module_imports.get(module, [])):
                if import_.alias != name:
                    continue
                result = self._resolve_import(import_, module)
                break
        self._binding_cache[key] = result
        return result

    def _resolve_attr(self, module: str, attr: str) -> Target | None:
        full = f"{module}.{attr}"
        if full in self._modules:
            return Target("module", full)
        return self._resolve_binding(module, attr)

    def resolve(self, name: str) -> str | None:
        """Canonical qualified name for a query name, following imports and re-exports.

        "fastapi.FastAPI" -> "fastapi.applications.FastAPI"; None if the name is unknown.
        """
        if name in self._symbols:
            return name
        parts = name.split(".")
        if len(parts) < 2 or parts[0] != self.root.name:
            return None
        current = parts[0]
        kind: TargetKind = "module"
        for part in parts[1:]:
            if kind == "module":
                full = f"{current}.{part}"
                if full in self._modules:
                    current = full
                    continue
                target = self._resolve_binding(current, part)
                if target is None or target.kind == "external":
                    return None
                current = target.name
                kind = target.kind
            elif kind == "symbol":
                if part in self._scope_locals.get(current, set()):
                    return None
                full = f"{current}.{part}"
                if full not in self._symbols:
                    return None
                current = full
            else:
                return None
        return current

    def _lookup_name(self, scope: str, name: str) -> Target | None:
        current: str | None = scope
        first = True
        while current is not None:
            kind = self._scope_kind.get(current)
            if kind == "module":
                return self._resolve_binding(current, name)
            if kind != "class" or first:
                child = self._symbols_by_scope.get(current, {}).get(name)
                if child is not None:
                    return Target("symbol", child)
            if kind is None:
                return None
            current = self._scope_parent.get(current)
            first = False
        return None

    def _is_local(self, scope: str, name: str) -> bool:
        current: str | None = scope
        first = True
        while current is not None:
            kind = self._scope_kind.get(current)
            if kind == "module":
                return False
            if (kind != "class" or first) and name in self._scope_locals.get(current, set()):
                return True
            current = self._scope_parent.get(current)
            first = False
        return False

    def _is_parameter(self, scope: str, name: str) -> bool:
        current: str | None = scope
        while current is not None:
            kind = self._scope_kind.get(current)
            if kind == "module":
                return False
            if kind not in ("class", "module") and name in self._scope_params.get(current, set()):
                return True
            current = self._scope_parent.get(current)
        return False

    def _is_patched(self, scope: str, parts: list[str]) -> bool:
        current: str | None = scope
        chain = tuple(parts)
        while current is not None:
            if chain in self._patched_attributes.get(current, set()):
                return True
            current = self._scope_parent.get(current)
        return False

    def _self_class(self, scope: str) -> str | None:
        if self._scope_kind.get(scope) != "method":
            return None
        parent = self._scope_parent.get(scope)
        if parent is not None and self._scope_kind.get(parent) == "class":
            return parent
        return None

    def _resolve_call(self, raw: RawCall) -> CallSite:
        def site(
            resolution: Resolution, target: str | None = None, reason: str | None = None
        ) -> CallSite:
            return CallSite(
                expression=raw.expression,
                file=raw.file,
                line=raw.line,
                scope=raw.scope,
                resolution=resolution,
                target=target,
                reason=reason,
            )

        parts = raw.parts
        if not parts:
            return site("unresolved", reason="dynamic receiver")
        if self._is_patched(raw.scope, parts):
            return site("unresolved", reason="monkey patched")
        first = parts[0]
        if first == "self":
            class_name = self._self_class(raw.scope)
            if class_name is not None and len(parts) == 2:
                if parts[1] in self._scope_locals.get(class_name, set()):
                    return site("unresolved", reason="monkey patched")
                candidate = f"{class_name}.{parts[1]}"
                symbols = self._symbols.get(candidate, [])
                if any(symbol.kind in ("method", "function", "class") for symbol in symbols):
                    return site("internal", candidate)
            return site("unresolved", reason="not defined in class")
        if self._is_local(raw.scope, first):
            if len(parts) == 1:
                return site("unresolved", reason="local variable")
            if self._is_parameter(raw.scope, first):
                return site("unresolved", reason="dynamic receiver")
            return site("unresolved", reason="local variable")

        target = self._lookup_name(raw.scope, first)
        if target is None:
            if len(parts) == 1 and first in BUILTIN_NAMES:
                return site("external", f"builtins.{first}")
            return site("unresolved", reason="unknown name")
        if target.kind == "external":
            suffix = ".".join(parts[1:])
            return site("external", f"{target.name}.{suffix}" if suffix else target.name)

        current = target.name
        kind = target.kind
        for index, attr in enumerate(parts[1:], start=1):
            if kind == "module":
                full = f"{current}.{attr}"
                if full in self._modules:
                    current = full
                    continue
                found = self._resolve_binding(current, attr)
                if found is None:
                    return site("unresolved", reason="unknown name")
                current, kind = found.name, found.kind
                if kind == "external":
                    suffix = ".".join(parts[index + 1 :])
                    return site("external", f"{current}.{suffix}" if suffix else current)
            elif kind == "symbol":
                if attr in self._scope_locals.get(current, set()):
                    return site("unresolved", reason="monkey patched")
                full = f"{current}.{attr}"
                if full not in self._symbols:
                    return site("unresolved", reason="unknown name")
                current = full
            else:
                return site("unresolved", reason="dynamic receiver")
        if kind == "symbol":
            return site("internal", current)
        if kind == "module":
            return site("unresolved", reason="module is not callable")
        return site("unresolved", reason="dynamic receiver")

    def _collect_references(self) -> list[Reference]:
        results: list[Reference] = []
        for import_ in self._imports:
            module = self._module_by_file.get(import_.file)
            if module is None:
                continue
            target = self._resolve_import(import_, module)
            if target is None or target.kind == "external":
                continue
            results.append(
                Reference(target.name, "import", import_.file, import_.line, import_.scope)
            )
        for call in self._call_sites:
            if call.resolution == "internal" and call.target is not None:
                results.append(Reference(call.target, "call", call.file, call.line, call.scope))
        return results

    def definitions(self, qualified_name: str) -> list[Symbol]:
        """Usually one symbol; several if the name is defined in both branches of an `if`."""
        return list(self._symbols.get(qualified_name, []))

    def references(self, qualified_name: str) -> list[Reference]:
        return [reference for reference in self._references if reference.target == qualified_name]

    def callers(self, qualified_name: str) -> list[Symbol]:
        if self._graph is None:
            return []
        results: list[Symbol] = []
        for caller in self._graph.callers(qualified_name):
            results.extend(self.definitions(caller))
        return results

    def call_sites(self, qualified_name: str) -> list[CallSite]:
        """All calls whose scope is this symbol: internal, external, and unresolved."""
        return [call for call in self._call_sites if call.scope == qualified_name]

    def path(self, source: str, target: str) -> list[str] | None:
        if self._graph is None:
            return None
        return self._graph.shortest_path(source, target)
