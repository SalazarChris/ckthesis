"""Tests for the identity-exception-to-finding conversion at the engine
boundary (CHECKLIST.md Phase 4; plan §8.1, §9.2).

The contract under test:
- ``identity.DuplicateIdError`` converts to an R-ENT-002 ERROR finding;
- the registry keeps its raise-based contract (nothing here changes that);
- raw identity exceptions never escape the engine into the UI layer;
- the meta-test pins the wiring so catalogue renames break loudly.
"""

from __future__ import annotations

import pytest

from configbuilder.identity import DuplicateIdError, IdentityError
from configbuilder.validation import (
    Severity,
    Tier,
    convert_identity_error,
    get_rule,
)


def test_duplicate_id_error_converts_to_r_ent_002():
    error = DuplicateIdError("identifier 'A' is already assigned in this registry")
    finding = convert_identity_error(error)
    assert finding.rule_id == "R-ENT-002"
    assert finding.severity is Severity.ERROR
    assert "already in use" in finding.user_message


def test_converted_finding_carries_diagnostic_and_suggestion():
    finding = convert_identity_error(DuplicateIdError("identifier 'B' is taken"))
    assert finding.diagnostic
    assert finding.suggestion


def test_unmappable_identity_errors_pass_through():
    """An unmappable identity error is a programming error: re-raised, not
    swallowed into a vague finding."""
    with pytest.raises(IdentityError):
        convert_identity_error(IdentityError("unmappable condition"))


def test_meta_r_ent_002_is_relational_error_with_identity_mappings():
    """The wiring target must stay RELATIONAL/ERROR with MAP-901/902: if the
    catalogue row changes, this conversion must be revisited."""
    rule = get_rule("R-ENT-002")
    assert rule is not None
    assert rule.tier is Tier.RELATIONAL
    assert rule.severity is Severity.ERROR
    assert "MAP-901" in rule.mapping_ids
    assert "MAP-902" in rule.mapping_ids


def test_meta_duplicate_id_error_is_documented_as_conversion_point():
    """The registry docstring and the catalogue row each carry half of the
    wiring promise; this meta-test keeps both in place."""
    import configbuilder.identity.registry as registry_module
    import configbuilder.validation.catalogue as catalogue_module

    assert "R-ENT-002" in (DuplicateIdError.__doc__ or "")
    rule = catalogue_module.get_rule("R-ENT-002")
    assert rule is not None
    registry_doc = registry_module.DuplicateIdError.__doc__ or ""
    assert "engine boundary" in registry_doc or "Phase 4" in registry_doc


def test_engine_boundary_converts_via_validate(monkeypatch):
    """End-to-end: a rule that hits a DuplicateIdError surfaces as an
    R-ENT-002 finding in the report, not as a raised exception."""
    from configbuilder.identity import IdentityRegistry, Multiplicity
    from configbuilder.model import (
        Configuration,
        ConfigurationMetadata,
        FamilyARecord,
        SeedSet,
        SequenceText,
    )
    from configbuilder.validation import validate

    registry = IdentityRegistry()
    entity_id = registry.allocate()
    configuration = Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1]),
        records=(
            FamilyARecord(ids=Multiplicity([entity_id.value]), sequence=SequenceText("PEP", "protein")),
        ),
        identity=registry,
    )

    def raising_rule(configuration, report, rule):
        raise DuplicateIdError("identifier 'A' is already assigned in this registry")

    import configbuilder.validation.rules.entity_rules as entity_rules

    monkeypatch.setattr(entity_rules, "check_r_ent_002", raising_rule)
    report = validate(configuration)
    converted = [f for f in report.findings if f.rule_id == "R-ENT-002"]
    assert len(converted) == 1
    assert converted[0].severity is Severity.ERROR
