"""Architecture test: the serializer stays a pure encoder (plan §11).

"The serializer contains no conditionals on field names. If a change
requires one, the change belongs in ``transform``." This test scans
``configbuilder/serialize`` for wire field-name literals (the tables in
``transform.mappings`` are the single source of that vocabulary) and for
``if`` statements whose test inspects string *values* — the encoder must
branch only on document structure, never on which field it is walking.
"""

from __future__ import annotations

import ast
from pathlib import Path

from configbuilder.transform.mappings import (
    DNA_FIELDS,
    LIGAND_FIELDS,
    PROTEIN_FIELDS,
    RNA_FIELDS,
    ROOT_FIELDS,
)

SERIALIZE_ROOT = Path(__file__).resolve().parents[2] / "configbuilder" / "serialize"


def _wire_field_names():
    names = set()
    for table in (ROOT_FIELDS, PROTEIN_FIELDS, RNA_FIELDS, DNA_FIELDS, LIGAND_FIELDS):
        for row in table:
            if row[1]:
                names.add(row[1])
    return names


def _parse(path):
    with open(path, "r", encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename=str(path))


def test_no_wire_field_names_in_serializer():
    """The encoder never mentions a wire field name; it walks structure."""
    wire_names = _wire_field_names()
    violations = []
    for path in sorted(SERIALIZE_ROOT.glob("*.py")):
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in wire_names:
                    violations.append("%s: literal %r" % (path.name, node.value))
    assert not violations, (
        "serialize/ mentions wire field names; encoding must be "
        "field-name-agnostic (plan §11): %s" % "; ".join(violations)
    )


def _string_compare_constants(compare):
    """Every string constant appearing as an operand of a Compare — on the
    left *or* among the comparators (``if 'x' == v`` and ``if v == 'x'``
    are the same violation), including inside tuple/set/list literals
    (``if v in ('x', 'y')``)."""
    operands = [compare.left, *compare.comparators]
    constants = set()
    for operand in operands:
        for node in ast.walk(operand):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                constants.add(node.value)
    return constants


def test_no_value_dependent_branches_in_serializer():
    """Every ``if`` in the encoder tests structure or encoding options —
    comparing string constants against field values is a transform
    concern that leaked into serialization."""
    violations = []
    for path in sorted(SERIALIZE_ROOT.glob("*.py")):
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                for sub in ast.walk(node.test):
                    if isinstance(sub, ast.Compare) and _string_compare_constants(sub):
                        violations.append(
                            "%s:%d: if compares against a string literal" % (path.name, node.lineno)
                        )
    assert not violations, (
        "serialize/ branches on string values; conditional policy belongs "
        "in transform (plan §11): %s" % "; ".join(violations)
    )


def test_detectors_have_teeth():
    """Positive control: a serialize module that mentioned a wire name or
    branched on one would be flagged — in either operand order."""
    wire_names = _wire_field_names()
    assert "unpairedMsa" in wire_names

    def _flagged(snippet):
        tree = ast.parse(snippet)
        return any(
            isinstance(node, ast.If)
            and any(
                isinstance(sub, ast.Compare)
                and _string_compare_constants(sub) & wire_names
                for sub in ast.walk(node.test)
            )
            for node in ast.walk(tree)
        )

    assert _flagged("if value == 'unpairedMsa':\n    pass")
    assert _flagged("if 'unpairedMsa' == value:\n    pass")
    assert _flagged("if value in ('unpairedMsa', 'other'):\n    pass")
    assert not _flagged("if value == 'not-a-wire-field':\n    pass")
