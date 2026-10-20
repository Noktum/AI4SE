from pathlib import Path

from repo_map.index import RepoIndex

RULES = Path(__file__).parent / "fixtures" / "rules_pkg"


def build() -> RepoIndex:
    return RepoIndex.build(RULES.resolve())


def internal_targets(index: RepoIndex, scope: str) -> set[str]:
    return {
        call.target
        for call in index.call_sites(scope)
        if call.resolution == "internal" and call.target is not None
    }


def unresolved_targets(index: RepoIndex, scope: str) -> list[tuple[str, str | None]]:
    return [
        (call.expression, call.reason)
        for call in index.call_sites(scope)
        if call.resolution == "unresolved"
    ]


def test_symbols_and_qualified_names():
    index = build()
    expected = {
        "rules_pkg": "module",
        "rules_pkg.target": "module",
        "rules_pkg.target.leaf": "function",
        "rules_pkg.target.Widget": "class",
        "rules_pkg.target.Widget.method": "method",
        "rules_pkg.target.Widget.helper": "method",
        "rules_pkg.target.outer": "function",
        "rules_pkg.target.outer.inner": "function",
        "rules_pkg.target.outer.caller": "function",
    }
    for qualified_name, kind in expected.items():
        symbols = index.definitions(qualified_name)
        assert symbols, qualified_name
        assert symbols[0].kind == kind
        assert symbols[0].file.startswith("rules_pkg/")
        assert symbols[0].line >= 1

    module = index.definitions("rules_pkg.target")[0]
    assert module.line == 1


def test_async_and_decorated_definitions_use_def_line():
    index = build()
    source = (RULES / "edges.py").read_text().splitlines()

    async_symbol = index.definitions("rules_pkg.edges.async_function")[0]
    assert async_symbol.is_async is True
    assert source[async_symbol.line - 1].lstrip().startswith("async def async_function")

    decorated = index.definitions("rules_pkg.edges.decorated")[0]
    assert decorated.is_async is False
    assert source[decorated.line - 1].lstrip().startswith("def decorated")


def test_duplicate_definitions_are_kept():
    index = build()
    branches = index.definitions("rules_pkg.edges.branch")
    assert len(branches) == 2
    assert len({symbol.line for symbol in branches}) == 2


def test_same_module_call():
    index = build()
    assert internal_targets(index, "rules_pkg.target.same_module") == {"rules_pkg.target.leaf"}


def test_nested_function_call():
    index = build()
    assert internal_targets(index, "rules_pkg.target.outer.caller") == {
        "rules_pkg.target.outer.inner"
    }
    assert internal_targets(index, "rules_pkg.target.outer") == {"rules_pkg.target.outer.caller"}


def test_all_import_forms_resolve_to_canonical_symbol():
    index = build()
    for scope in (
        "rules_pkg.imports.use_plain_import",
        "rules_pkg.imports.use_aliased_import",
        "rules_pkg.imports.use_absolute_symbol",
        "rules_pkg.imports.use_from_module",
        "rules_pkg.imports.use_from_symbol",
        "rules_pkg.deep.mod.use_parent_import",
    ):
        assert internal_targets(index, scope) == {"rules_pkg.target.leaf"}, scope


def test_reexport_chain():
    index = build()
    assert index.resolve("rules_pkg.leaf") == "rules_pkg.target.leaf"
    assert index.resolve("rules_pkg.hub.leaf") == "rules_pkg.target.leaf"
    assert index.resolve("rules_pkg.unknown") is None


def test_class_call_resolves_to_class_not_init():
    index = build()
    assert internal_targets(index, "rules_pkg.imports.use_class") == {"rules_pkg.target.Widget"}


def test_self_method_call():
    index = build()
    assert internal_targets(index, "rules_pkg.target.Widget.method") == {
        "rules_pkg.target.Widget.helper"
    }
    assert internal_targets(index, "rules_pkg.target.Widget.helper") == set()


def test_local_names_shadow_imported_symbol():
    index = build()
    assert internal_targets(index, "rules_pkg.shadow.parameter_shadow") == set()
    assert internal_targets(index, "rules_pkg.shadow.assignment_shadow") == set()
    assert internal_targets(index, "rules_pkg.shadow.attribute_shadow") == set()
    assert ("leaf", "local variable") in unresolved_targets(
        index, "rules_pkg.shadow.parameter_shadow"
    )
    assert ("obj.method", "dynamic receiver") in unresolved_targets(
        index, "rules_pkg.shadow.attribute_shadow"
    )


def test_cases_that_must_stay_unresolved():
    index = build()
    limits = "rules_pkg.limits"
    for scope in (
        f"{limits}.Child.use_super",
        f"{limits}.Child.use_self_inherited",
        f"{limits}.Child.use_cls",
        f"{limits}.use_getattr",
        f"{limits}.wildcard_import",
    ):
        assert internal_targets(index, scope) == set(), scope

    nested = f"{limits}.Child.nested_self"
    assert internal_targets(index, nested) == {f"{nested}.inner"}
    assert ("self.inherited", "not defined in class") in unresolved_targets(
        index, f"{nested}.inner"
    )


def test_references_include_imports_and_calls():
    index = build()
    references = index.references("rules_pkg.target.leaf")
    kinds = {(reference.kind, reference.scope) for reference in references}
    assert ("import", "rules_pkg") in kinds
    assert ("import", "rules_pkg.hub") in kinds
    assert ("import", "rules_pkg.imports") in kinds
    assert ("call", "rules_pkg.target.same_module") in kinds
    assert ("call", "rules_pkg.imports.use_from_symbol") in kinds
    assert ("call", "rules_pkg.edges.decorated") in kinds


def test_callers_and_decorator_scope():
    index = build()
    callers = {symbol.qualified_name for symbol in index.callers("rules_pkg.target.leaf")}
    assert "rules_pkg.target.same_module" in callers
    assert "rules_pkg.imports.use_from_symbol" in callers
    assert "rules_pkg.deep.mod.use_parent_import" in callers

    decorator_callers = {symbol.qualified_name for symbol in index.callers("rules_pkg.edges.deco")}
    assert decorator_callers == {"rules_pkg.edges"}


def test_shortest_paths():
    index = build()
    assert index.path("rules_pkg.target.outer", "rules_pkg.target.outer.inner") == [
        "rules_pkg.target.outer",
        "rules_pkg.target.outer.caller",
        "rules_pkg.target.outer.inner",
    ]
    assert index.path("rules_pkg.target.leaf", "rules_pkg.target.leaf") == ["rules_pkg.target.leaf"]
    assert index.path("rules_pkg.target.leaf", "rules_pkg.target.same_module") is None
