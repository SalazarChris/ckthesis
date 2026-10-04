"""Architecture tests for model/ (plan §5.3 rule 2, §7.3; spec §17)."""

from __future__ import annotations

import ast

from tests.architecture._scanner import PACKAGE_ROOT

MODEL_DIR = PACKAGE_ROOT / "model"


def _model_sources():
    for path in sorted(MODEL_DIR.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


class TestModelPurity:
    def test_model_imports_only_identity_and_itself(self):
        """§5.3 rule 2: model may import identity (EntityId, Multiplicity,
        IdentityRegistry) and its own submodules — nothing else from the
        project."""
        violations = []
        for path, tree in _model_sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("configbuilder") and not (
                            alias.name.startswith("configbuilder.identity")
                            or alias.name.startswith("configbuilder.model")
                        ):
                            violations.append(f"{path.name}: imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod.startswith("configbuilder") and not (
                        mod.startswith("configbuilder.identity")
                        or mod.startswith("configbuilder.model")
                    ):
                        violations.append(f"{path.name}: imports {mod}")
        assert violations == []

    def test_no_typing_optional_import_in_model(self):
        """§7.1: contract fields are total; Optional is not imported in model/."""
        violations = []
        for path, tree in _model_sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "") == "typing":
                    for alias in node.names:
                        if alias.name == "Optional":
                            violations.append(f"{path.name}: imports Optional")
        assert violations == []


def _enclosing_function_name(tree, target_node):
    """Name of the nearest enclosing FunctionDef, or None."""
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    node = target_node
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return None


class TestFoldsOnlyIsinstance:
    def test_isinstance_appears_only_in_fold_functions(self):
        """§17: fold dispatch over a sum type happens only inside ``fold_*``
        functions (and ``is_presence``). Constructors may still use isinstance
        to reject wrongly-typed arguments — that is validation, not dispatch."""
        violations = []
        for path, tree in _model_sources():
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "isinstance"
                ):
                    enclosing = _enclosing_function_name(tree, node)
                    if enclosing is None or not (
                        enclosing.startswith("fold_")
                        or enclosing == "is_presence"
                        or enclosing in ("__init__", "__eq__", "__hash__", "__reduce__")
                        or enclosing.startswith("_")  # private helpers of a type
                        or enclosing.startswith("with_")  # derivation helpers re-validate
                    ):
                        violations.append(
                            f"{path.name}:{node.lineno}: isinstance outside fold (in {enclosing!r})"
                        )
        assert violations == []


def _is_stateless_class(node):
    """True when the class declares no instance state (docstrings,
    annotations, and pass only): nothing to mutate, so no guard needed."""
    for stmt in node.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring
        if isinstance(stmt, (ast.AnnAssign, ast.Pass)):
            continue
        return False
    return True


class TestImmutabilityEnforcement:
    def test_every_stateful_class_enforces_immutability(self):
        """Model classes either declare ``__slots__`` or guard ``__setattr__``;
        stateless classes (errors, protocols) carry nothing to mutate."""
        violations = []
        for path, tree in _model_sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if _is_stateless_class(node):
                        continue
                    has_slots = any(
                        isinstance(stmt, ast.Assign)
                        and any(getattr(t, "id", None) == "__slots__" for t in stmt.targets)
                        for stmt in node.body
                    )
                    has_setattr_guard = "__setattr__" in [
                        item.name for item in node.body if isinstance(item, ast.FunctionDef)
                    ]
                    if not (has_slots or has_setattr_guard):
                        violations.append(
                            f"{path.name}: class {node.name} lacks __slots__ and __setattr__ guard"
                        )
        assert violations == []


def _imported_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


class TestTraceabilityCompleteness:
    def test_every_model_value_type_is_registered(self):
        """Plan §6.1: a completeness test asserts every canonical model *value*
        type appears in the traceability registry with mapping ids and a UI
        label. Error classes register their own labels but are checked in the
        registry's own unit tests, not here."""
        import configbuilder.model.traceability as traceability

        registered = {entry.internal_type for entry in traceability.registry_entries()}
        value_types = set()
        for path, tree in _model_sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if node.name.startswith("_") or node.name.endswith("Error"):
                        continue
                    # Only classes defined in model/ itself, not imported names.
                    if node.name in _imported_names(tree):
                        continue
                    value_types.add(node.name)
        missing = value_types - registered
        assert not missing, "unregistered model value types: %s" % sorted(missing)
