"""Architecture test: MAP-004 is a lightweight traceability anchor.

Design clarification (project record): ``Record`` / MAP-004 identifies the
minimal common interface shared by the record families. It is a
traceability reference, not a central domain object:

- ``Configuration`` (MAP-001) remains the root aggregate; records are one
  component of it alongside seeds, linkages, component definitions, and
  format targeting.
- ``Record`` carries only identity and descriptive metadata (plan §7.4).
  It must not acquire fields or behaviour merely because it has a mapping
  identifier; family capabilities live on the family types (MAP-005..008).
- Nothing outside ``model`` may depend on the ``Record`` protocol; other
  modules dispatch over the concrete families.
- MAP-004 implies no persistence representation, workflow role, or
  additional abstraction layer.

Like the other architecture tests, this scanner never imports the scanned
code.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "configbuilder"

# The protocol's complete allowed member surface (plan §7.4: "identity and
# descriptive metadata only").
ALLOWED_PROTOCOL_MEMBERS = frozenset({"ids", "description"})

# ``model/__init__`` re-exports the protocol for typing use inside the
# model package's own public surface; every other import of ``Record``
# outside model/ would make unrelated code depend on the abstraction.
ALLOWED_IMPORTERS = frozenset({
    Path("model") / "__init__.py",
})


def _parse(path: Path) -> ast.Module:
    with open(path, "r", encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename=str(path))


def _iter_python_files():
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        yield path.relative_to(PACKAGE_ROOT), path


def _find_record_class(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Record":
            return node
    return None


def test_record_protocol_stays_minimal():
    """MAP-004 gains no fields or behaviour: the protocol declares only
    ``ids`` and ``description`` and defines no methods of its own."""
    records_path = PACKAGE_ROOT / "model" / "records.py"
    record_cls = _find_record_class(_parse(records_path))
    assert record_cls is not None, "Record protocol disappeared from model/records.py"

    members = set()
    methods = []
    for node in record_cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            members.add(node.target.id)
        elif isinstance(node, ast.FunctionDef):
            methods.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    members.add(target.id)

    unexpected = members - ALLOWED_PROTOCOL_MEMBERS
    assert not unexpected, (
        "Record protocol acquired members beyond the minimal common "
        "abstraction (MAP-004 is a traceability anchor, not a domain "
        "object): %s" % sorted(unexpected)
    )
    assert not methods, (
        "Record protocol defines behaviour; family capabilities belong on "
        "the family types: %s" % methods
    )


def test_no_module_outside_model_depends_on_record_protocol():
    """The Record protocol has no import fan-in outside ``model``.

    Anything needing record behaviour must use the concrete family types
    (``FamilyARecord`` / ``FamilyBRecord`` / ``FamilyCRecord`` /
    ``ComponentRecord``), so unrelated parts of the application can never
    grow a dependency on the common abstraction.
    """
    violations = []
    for relative, path in _iter_python_files():
        if relative in ALLOWED_IMPORTERS or relative.parts[0] == "model":
            continue
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.ImportFrom) and node.module:
                target = ".".join(node.module.split(".")[:2])
                if target != "configbuilder.model":
                    continue
                imported = {alias.asname or alias.name for alias in node.names}
                if "Record" in imported:
                    violations.append(str(relative))
    assert not violations, (
        "modules outside model/ import the Record protocol; dispatch over "
        "the concrete family types instead: %s" % sorted(violations)
    )


def test_record_protocol_is_a_protocol_not_a_base_class():
    """Families share machinery, not identity: no family inherits from
    ``Record``, so the abstraction cannot accrete capability through
    inheritance."""
    records_path = PACKAGE_ROOT / "model" / "records.py"
    tree = _parse(records_path)
    record_cls = _find_record_class(tree)
    assert record_cls is not None

    protocol_only = {"Protocol"}
    bases = {
        base.id
        for base in record_cls.bases
        if isinstance(base, ast.Name)
    }
    assert bases <= protocol_only, (
        "Record must remain a plain typing.Protocol, not part of an "
        "inheritance chain: bases=%s" % sorted(bases)
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.endswith("Record") and node.name != "Record":
            base_names = {
                base.id for base in node.bases if isinstance(base, ast.Name)
            }
            assert "Record" not in base_names, (
                "%s inherits from the Record protocol; families own their "
                "fields and share no type identity with MAP-004" % node.name
            )
