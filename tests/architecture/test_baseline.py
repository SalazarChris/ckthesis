"""Architecture tests: baseline guards (IMPLEMENTATION_PLAN.md §4.1, §21 Phase 0).

These tests keep the source tree importable on the Python 3.9.18 baseline:
no 3.10-only constructs anywhere in ``configbuilder``. They are static, so
they hold on any development interpreter (this checkout currently develops
on 3.11; CI runs the suite on 3.9 specifically).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from tests.architecture import _scanner

CONFIGBUILDER = _scanner.PACKAGE_ROOT


def _py_files():
    return sorted(CONFIGBUILDER.rglob("*.py"))


def test_python_version_is_at_least_3_9():
    assert sys.version_info >= (3, 9)


def test_no_match_statements():
    # ast.Match exists only on 3.10+; on the 3.9 baseline the construct is a
    # syntax error, so the parse itself would fail and absence of the node
    # type is implied.
    match_node = getattr(ast, "Match", None)
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if match_node is None:
            continue
        for node in ast.walk(tree):
            assert not isinstance(node, match_node), (
                f"{path}: 'match' statement requires 3.10 (plan §4.1)"
            )


def test_no_slots_dataclasses():
    for path in _py_files():
        text = path.read_text(encoding="utf-8")
        assert "slots=True" not in text, f"{path}: @dataclass(slots=True) requires 3.10 (plan §4.1)"


def test_no_pep604_union_syntax():
    # Only flag unions between annotation-shaped nodes; guard the isinstance
    # targets with getattr so this test itself runs on 3.9.
    name = getattr(ast, "Name", None)
    constant = getattr(ast, "Constant", None)
    subscript = getattr(ast, "Subscript", None)
    shaped = tuple(n for n in (name, constant, subscript) if n is not None)
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                annotationish = isinstance(node.left, shaped) and isinstance(node.right, shaped)
                assert not annotationish, (
                    f"{path}: PEP 604 union 'X | Y' requires 3.10; use typing.Union/Optional (plan §4.1)"
                )


def test_no_typealias_or_assert_never():
    for path in _py_files():
        text = path.read_text(encoding="utf-8")
        assert "TypeAlias" not in text, f"{path}: typing.TypeAlias requires 3.10 (plan §4.1)"
        assert "assert_never" not in text, f"{path}: typing.assert_never requires 3.10 (plan §4.1)"


def test_no_tomllib_import():
    for path in _py_files():
        text = path.read_text(encoding="utf-8")
        assert "tomllib" not in text, f"{path}: tomllib requires 3.11 and is not needed (plan §4.1)"


def test_no_exception_groups():
    for path in _py_files():
        text = path.read_text(encoding="utf-8")
        assert "except*" not in text, f"{path}: except* requires 3.11 (plan §4.1)"
