"""Architecture test: wire field names appear only in ``transform``.

Exit criterion of Phase 5 (plan §10.1): "No other module builds a wire
structure. A test asserts no module other than ``transform`` contains a
wire field-name literal." Plan §18.7 lists the same assertion among the
standing architecture tests.

The precise invariant is about *structure building*: a wire field name is
a JSON object key, so this test flags wire names used as dict-literal keys
or subscripts outside ``transform``. String mentions in other positions
are legitimate — ``validation`` names the *field a finding points at*
through ``FieldPath``'s locator slot (plan line 826: "the wire/model field
within it"), and catalogue summaries quote field names in user guidance;
neither builds wire structure. Like the other architecture tests, the
scanner never imports the scanned code.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

from configbuilder.transform.mappings import (
    DNA_FIELDS,
    LIGAND_FIELDS,
    PROTEIN_FIELDS,
    RNA_FIELDS,
    ROOT_FIELDS,
)

CONFIGBUILDER_ROOT = Path(__file__).resolve().parents[2] / "configbuilder"

# A schema migration necessarily names the *retired* spellings it maps
# away from — its subject matter, like a validation finding naming the
# field it points at. One greppable anchor (plan §18.7 keeps exemptions
# documented); the fixture-generation script in tests mirrors the same
# map when building the legacy v0 fixture.
LEGACY_KEY_MAP_ANCHOR = "_LEGACY_KEY_MAP"
MODULES_WITH_DOCUMENTED_MENTIONS = frozenset(
    {"persistence" + os.sep + "schema.py"}
)
# Template-entry sub-fields are built inside transform's ``_templates_field``
# the same way modification entry sub-fields are built for its entries. They
# are not (yet) table rows, so they are listed here explicitly rather than
# collected from the tables.
TEMPLATE_ENTRY_FIELDS = frozenset(
    {"mmcif", "mmcifPath", "queryIndices", "templateIndices"}
)


def _wire_field_names():
    names = set()
    for table in (ROOT_FIELDS, PROTEIN_FIELDS, RNA_FIELDS, DNA_FIELDS, LIGAND_FIELDS):
        for row in table:
            if row[1]:
                names.add(row[1])
    return names | set(TEMPLATE_ENTRY_FIELDS)


def _iter_python_files():
    for path in sorted(CONFIGBUILDER_ROOT.rglob("*.py")):
        parts = path.relative_to(CONFIGBUILDER_ROOT).parts
        if parts[0] == "transform":
            continue
        yield path


def _structure_building_strings(tree):
    """String constants used as dict keys or subscripts in an AST."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    found.add(key.value)
        elif isinstance(node, ast.Subscript):
            for sub in ast.walk(node.slice):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    found.add(sub.value)
    return found


def _parse(path):
    with open(path, "r", encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename=str(path))


def test_wire_field_names_used_outside_transform():
    """No module other than ``transform`` builds wire structure."""
    wire_names = _wire_field_names()
    violations = []
    for path in _iter_python_files():
        relative = path.relative_to(CONFIGBUILDER_ROOT)
        used = _structure_building_strings(_parse(path))
        offending = sorted(used & wire_names)
        if offending and (
            str(relative) not in MODULES_WITH_DOCUMENTED_MENTIONS
            or LEGACY_KEY_MAP_ANCHOR not in path.read_text(encoding="utf-8")
        ):
            violations.append("%s: %s" % (relative, ", ".join(offending)))
    assert not violations, (
        "wire field-name literals used to build structure outside "
        "transform/ (plan §10.1 single-authority rule): %s" % "; ".join(violations)
    )


def test_wire_name_set_is_well_founded():
    """Positive control: the detector really fires inside ``transform``.

    If the mapping tables ever shrink to nothing, the exclusion above
    would become vacuous and silently stop guarding anything.
    """
    wire_names = _wire_field_names()
    assert len(wire_names) >= 20
    transform_dir = CONFIGBUILDER_ROOT / "transform"
    used = set()
    for path in sorted(transform_dir.rglob("*.py")):
        used |= _structure_building_strings(_parse(path))
    detected = sorted(used & wire_names)
    assert "unpairedMsa" in detected
    assert len(detected) >= 5
