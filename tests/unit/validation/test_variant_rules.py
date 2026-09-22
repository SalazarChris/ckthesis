"""Validation-level tests for the VARIANT tier (plan §9.2, §12.5).

The rules compare wire documents handed over as data through
``ValidationContext`` (plan §5.3 rule 2 keeps validation independent of
transform) — these tests drive them with hand-built documents so the
attribution logic is pinned without depending on the transform package.
"""

from __future__ import annotations

from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity
from configbuilder.model import (
    Configuration,
    ConfigurationMetadata,
    FamilyARecord,
    FamilyBRecord,
    SeedSet,
    SequenceText,
)
from configbuilder.validation.catalogue import Severity
from configbuilder.validation.engine import ValidationContext, validate


def _base():
    registry = IdentityRegistry()
    a = registry.allocate().value
    b = registry.allocate().value
    return Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        records=(
            FamilyARecord(ids=Multiplicity([a]), sequence=SequenceText("PEPTIDE", "protein")),
            FamilyBRecord(ids=Multiplicity([b]), sequence=SequenceText("GGCC", "rna")),
        ),
        identity=registry,
    )


# -- R-VAR-001: undrifted comparison -------------------------------------------


def test_declared_difference_attracts_no_drift_finding():
    base = _base()
    base_document = {"name": "job", "sequences": [{"protein": {"id": "A", "sequence": "PEPTIDE"}}]}
    variant_document = {"name": "job", "sequences": [{"protein": {"id": "A", "sequence": "MUTATED"}}]}
    context = ValidationContext(
        variant_documents={"mut": variant_document},
        base_document=base_document,
        variant_declared_changes={"mut": (("sequence", "A"),)},
        variant_registries={"mut": base.identity},
        variant_seeds={"mut": list(base.seeds.values)},
    )
    report = validate(base, context)
    assert [f for f in report.findings if f.rule_id == "R-VAR-001"] == []


def test_undeclared_difference_raises_the_drift_error():
    base = _base()
    base_document = {"name": "job", "sequences": [{"protein": {"id": "A", "sequence": "PEPTIDE"}}]}
    variant_document = {
        "name": "job",
        "modelSeeds": [9],
        "sequences": [{"protein": {"id": "A", "sequence": "PEPTIDE"}}],
    }
    context = ValidationContext(
        variant_documents={"mut": variant_document},
        base_document=base_document,
        variant_declared_changes={"mut": (("sequence", "A"),)},
        variant_registries={"mut": base.identity},
        variant_seeds={"mut": list(base.seeds.values)},
    )
    report = validate(base, context)
    drift = [f for f in report.findings if f.rule_id == "R-VAR-001"]
    assert len(drift) == 1
    assert drift[0].severity == Severity.ERROR
    assert "modelSeeds" in drift[0].diagnostic


def test_missing_context_is_a_warning_not_silently_green():
    report = validate(_base(), ValidationContext())
    drift = [f for f in report.findings if f.rule_id == "R-VAR-001"]
    assert len(drift) == 1
    assert drift[0].severity == Severity.WARNING
    assert "could not be checked" in drift[0].user_message


def test_seed_attribute_covers_a_declared_seeds_edit():
    base = _base()
    base_document = {"modelSeeds": [1, 2, 3]}
    variant_document = {"modelSeeds": [1, 2, 3, 4]}
    context = ValidationContext(
        variant_documents={"seeded": variant_document},
        base_document=base_document,
        variant_declared_changes={"seeded": (("seeds", None),)},
        variant_registries={"seeded": base.identity},
        variant_seeds={"seeded": [1, 2, 3, 4]},
    )
    report = validate(base, context)
    assert [f for f in report.findings if f.rule_id == "R-VAR-001"] == []


# -- R-VAR-002: identity stability ---------------------------------------------


def test_preserved_identifiers_stay_stable():
    base = _base()
    context = ValidationContext(
        variant_documents={"mut": {"name": "job"}},
        base_document={"name": "job"},
        variant_declared_changes={"mut": (("sequence", "A"),)},
        variant_registries={"mut": base.identity},
        variant_seeds={"mut": list(base.seeds.values)},
    )
    report = validate(base, context)
    assert [f for f in report.findings if f.rule_id == "R-VAR-002"] == []


def test_declared_removal_keeps_the_registry_stable():
    base = _base()
    registry = base.identity.clone()
    registry.release(EntityId("B"))
    context = ValidationContext(
        variant_documents={"trunc": {"name": "job"}},
        base_document={"name": "job"},
        variant_declared_changes={"trunc": (("records", "B"),)},
        variant_registries={"trunc": registry},
        variant_seeds={"trunc": list(base.seeds.values)},
    )
    report = validate(base, context)
    assert [f for f in report.findings if f.rule_id == "R-VAR-002"] == []


def test_undeclared_identifier_disappearance_is_an_error():
    base = _base()
    registry = base.identity.clone()
    registry.release(EntityId("B"))
    context = ValidationContext(
        variant_documents={"trunc": {"name": "job"}},
        base_document={"name": "job"},
        variant_declared_changes={"trunc": (("sequence", "A"),)},  # removal not declared
        variant_registries={"trunc": registry},
        variant_seeds={"trunc": list(base.seeds.values)},
    )
    report = validate(base, context)
    stability = [f for f in report.findings if f.rule_id == "R-VAR-002"]
    assert len(stability) == 1
    assert stability[0].severity == Severity.ERROR


def test_missing_registries_report_a_warning():
    report = validate(_base(), ValidationContext())
    stability = [f for f in report.findings if f.rule_id == "R-VAR-002"]
    assert len(stability) == 1
    assert stability[0].severity == Severity.WARNING


# -- R-POL-007: seed-set stability across variants ------------------------------


def _seeded_context(base, variant_seeds):
    return ValidationContext(
        variant_documents={"mut": {"name": "job"}},
        base_document={"name": "job"},
        variant_declared_changes={"mut": (("sequence", "A"),)},
        variant_registries={"mut": base.identity},
        variant_seeds={"mut": variant_seeds},
    )


def test_seed_set_change_is_reported_as_policy_finding():
    base = _base()
    report = validate(base, _seeded_context(base, [5]))
    seeds = [f for f in report.findings if f.rule_id == "R-POL-007"]
    assert any("seed set" in f.user_message and "mut" in f.user_message for f in seeds)
    assert all(f.severity == Severity.INFO for f in seeds)


def test_identical_seed_sets_report_comparable():
    base = _base()
    report = validate(base, _seeded_context(base, list(base.seeds.values)))
    seeds = [f for f in report.findings if f.rule_id == "R-POL-007"]
    assert any("comparable" in f.user_message for f in seeds)
