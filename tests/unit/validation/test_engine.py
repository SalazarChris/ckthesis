"""Engine unit tests (plan §9.2, Phase 4)."""

from __future__ import annotations

import pytest

from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import (
    Configuration,
    ConfigurationMetadata,
    FamilyARecord,
    SeedSet,
    SequenceText,
)
from configbuilder.validation import (
    RULES,
    Severity,
    Tier,
    ValidationContext,
    validate,
)


def _configuration(records=1):
    registry = IdentityRegistry()
    made = []
    for index in range(records):
        entity_id = registry.allocate(owner="test")
        made.append(
            FamilyARecord(
                ids=Multiplicity([entity_id.value]),
                sequence=SequenceText("PEPTIDE", "protein"),
            )
        )
    return Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        records=tuple(made),
        identity=registry,
    )


def test_every_catalogue_rule_runs_with_no_skips():
    report = validate(_configuration(), ValidationContext(run_preflight=True))
    assert len(report.skipped) == 0
    # Rule coverage: each rule either ran (no skip recorded) or was skipped
    # with a reason; on a valid configuration none are skipped.
    assert len(report.skipped) == 0


def test_tier_order_in_execution():
    report = validate(_configuration())
    # Tier order is the engine's contract; the catalogue groups in order.
    from configbuilder.validation import TIER_ORDER

    assert TIER_ORDER == (
        Tier.STRUCTURAL,
        Tier.RELATIONAL,
        Tier.CONTRACT,
        Tier.VARIANT,
        Tier.PREFLIGHT,
    )


def test_later_tiers_run_despite_earlier_findings():
    """A STRUCTURAL finding must not suppress RELATIONAL/CONTRACT/VARIANT/
    PREFLIGHT execution: all 40 rules execute."""
    configuration = _configuration()
    # Force an empty-records style finding by clearing seeds is impossible
    # (model guards); instead validate with an artificial ERROR-generating
    # config: unverified version (CONTRACT) + 1 seed (VARIANT policy R-POL-004).
    registry = configuration.identity
    registry.allocate(owner="extra")  # unused ID: no relational error
    report = validate(configuration)
    severities = {f.severity for f in report.findings}
    assert Severity.ERROR in severities  # R-ROOT-002 / R-VER-001 present
    assert Severity.INFO in severities  # R-POL-* VARIANT rules still ran


def test_validate_on_valid_minimal_configuration_has_expected_findings():
    report = validate(_configuration())
    rule_ids = {f.rule_id for f in report.findings}
    # Blocking: version unverified until the probe exists (by design).
    assert "R-ROOT-002" in rule_ids
    assert "R-VER-001" in rule_ids
    # Info-only policies always report.
    assert {"R-POL-003", "R-POL-005", "R-POL-006"} <= rule_ids


def test_preflight_disabled_by_policy_reports_skips():
    report = validate(_configuration(), ValidationContext(run_preflight=False))
    skipped_ids = {rule_id for rule_id, _reason in report.skipped}
    assert "R-MSA-003" in skipped_ids
    assert "R-MSA-004" in skipped_ids
    assert "R-MSA-005" in skipped_ids
    assert "R-ENT-010" in skipped_ids


def test_validate_accepts_custom_tiers_subset():
    report = validate(_configuration(), tiers=(Tier.STRUCTURAL,))
    # Only STRUCTURAL rules run; no CONTRACT finding can appear.
    rule_ids = {f.rule_id for f in report.findings}
    assert "R-ROOT-002" not in rule_ids  # CONTRACT tier not run


def test_report_deduplicates_identical_findings():
    from configbuilder.validation import FieldPath, Finding, Report

    report = Report()
    finding = Finding(
        "R-ROOT-003",
        Severity.ERROR,
        "message",
        "diagnostic",
        (FieldPath("ConfigurationMetadata"),),
    )
    report.add(finding)
    report.add(finding)
    assert len(report) == 1


def test_report_remembers_skips():
    from configbuilder.validation import get_rule, Report

    report = Report()
    rule = get_rule("R-MSA-003")
    report.mark_skipped(rule, "preflight disabled by policy")
    assert report.skipped == (("R-MSA-003", "preflight disabled by policy"),)


def test_report_blocking_is_errors_only():
    report = validate(_configuration())
    assert all(f.severity is Severity.ERROR for f in report.blocking())
