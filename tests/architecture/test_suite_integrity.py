"""Integrity of the suite itself: no test function may be silently shadowed.

A module-level ``def test_x`` that is defined twice means Python keeps the last
definition. pytest collects one test, the first body never executes, and nothing
anywhere reports a problem -- coverage disappears while the suite stays green.

That happened here: ``tests/serialization/test_encode.py`` defined
``test_encode_to_file_writes_exact_bytes`` at two places and only the second was
ever run, for an unknown number of commits.

This module is a test of the tests, so it deliberately imports nothing from
``configbuilder``: it parses the suite with ``ast`` and reasons about source
text only.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1]


def _test_modules():
    """Every ``test_*.py`` under ``tests/``, excluding bytecode caches."""
    return sorted(
        path
        for path in TESTS_ROOT.rglob("test_*.py")
        if "__pycache__" not in path.parts
    )


def _module_level_test_defs(path):
    """Yield ``(name, lineno)`` for each module-level ``def test_*``.

    Only module level counts. A ``def test_x`` nested inside another function,
    or defined inside a class, is a normal helper and is not collected as a
    duplicate test by pytest.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                yield node.name, node.lineno


def test_no_test_function_is_shadowed_by_a_later_definition():
    """No test module may define the same ``test_*`` name twice."""
    assert _test_modules(), "no test modules found; the discovery root is wrong"

    collisions = {}
    for path in _test_modules():
        seen = {}
        for name, lineno in _module_level_test_defs(path):
            if name in seen:
                collisions.setdefault(str(path.relative_to(TESTS_ROOT)), []).append(
                    "%s at lines %d and %d" % (name, seen[name], lineno)
                )
            else:
                seen[name] = lineno

    assert not collisions, (
        "module-level test functions are defined more than once, so the earlier "
        "body never runs: %s" % collisions
    )


def test_the_detector_would_catch_a_collision():
    """Guard the guard.

    If the AST walk above ever stopped finding module-level functions (a
    refactor of the helper, a change in how tests are written), the collision
    test would pass vacuously. Parse a synthetic module and require the two
    expected hits.
    """
    sample = (
        "def test_alpha():\n"
        "    pass\n"
        "\n"
        "def test_alpha():\n"
        "    pass\n"
        "\n"
        "class TestGroup:\n"
        "    def test_alpha(self):\n"
        "        pass\n"
        "\n"
        "def helper():\n"
        "    def test_alpha():\n"
        "        pass\n"
    )
    tree = ast.parse(sample)
    found = [
        (node.name, node.lineno)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    # Two module-level definitions: the class method and the nested function are
    # not module level, so they must not appear.
    assert [name for name, _ in found] == ["test_alpha", "test_alpha"]
    assert [lineno for _, lineno in found] == [1, 4]


def test_the_suite_actually_contains_test_functions():
    """A discovery failure would make the collision test vacuous."""
    total = sum(len(list(_module_level_test_defs(path))) for path in _test_modules())
    assert total > 500, "only %d module-level test functions found" % total
