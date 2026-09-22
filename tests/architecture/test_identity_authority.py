"""Architecture tests: single identifier authority (plan §18.7).

"assert no module other than ``identity`` allocates identifiers" — enforced
statically: only ``configbuilder.identity`` may reference the allocator or
construct ``EntityId``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scanner import iter_source_modules  # noqa: E402

AUTHORITY_PATTERN = "IdAllocator"


def test_allocator_is_referenced_only_within_identity():
    violations = []
    for source in iter_source_modules():
        if source.family == "identity":
            continue
        text = source.path.read_text(encoding="utf-8")
        if AUTHORITY_PATTERN in text:
            violations.append(source.module)
    assert not violations, f"IdAllocator referenced outside identity: {violations}"


def test_identity_imports_no_project_module():
    """§5.3 rule 1: identity imports nothing from other project modules."""
    from _scanner import family_of_target, imported_targets, within_project

    violations = []
    for source in iter_source_modules():
        if source.family != "identity":
            continue
        for target in imported_targets(source):
            if within_project(target) and family_of_target(target) != "identity":
                violations.append(f"{source.module} -> {target}")
    assert not violations, violations
