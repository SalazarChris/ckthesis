"""Unit tests for the Phase 1 rule catalogue (plan §9.1, §9.3)."""

from __future__ import annotations

import pytest

from configbuilder.validation.catalogue import (
    Evidence,
    RULES,
    Severity,
    Tier,
    TIER_ORDER,
    get_rule,
    rules_by_tier,
)


def test_rule_ids_are_unique():
    ids = [rule.rule_id for rule in RULES]
    assert len(ids) == len(set(ids))


def test_every_rule_has_summary_and_spec_ref():
    for rule in RULES:
        assert rule.summary.strip()
        assert rule.spec_ref.strip()


def test_non_promoted_items_are_info_only():
    """Spec §19's deliberately-not-promoted list can never become a gate."""
    for rule in RULES:
        if rule.rule_id.startswith("R-POL-"):
            assert rule.severity is Severity.INFO, rule.rule_id


def test_confirmed_documented_contract_rules_are_errors():
    """Plan §9.3: contract rules with evidence are ERROR and block generation.
    PREFLIGHT is the documented exception: the tier is advisory by design
    (plan §9.2), so its DOCUMENTED rows carry WARNING severity."""
    advisory_preflight = {"R-MSA-003", "R-MSA-004", "R-MSA-005"}
    for rule in RULES:
        if rule.tier.name == "PREFLIGHT" or rule.rule_id in advisory_preflight:
            continue
        if rule.evidence in (Evidence.CONFIRMED, Evidence.DOCUMENTED):
            assert rule.severity is Severity.ERROR, rule.rule_id


def test_unresolved_evidence_is_never_error_or_warning():
    for rule in RULES:
        if rule.evidence is Evidence.UNRESOLVED:
            assert rule.severity is Severity.INFO, rule.rule_id


def test_project_policy_rules_are_info_by_default():
    for rule in RULES:
        if rule.evidence is Evidence.PROJECT_POLICY:
            assert rule.severity is Severity.INFO, rule.rule_id


def test_version_rules_block_generation():
    """Plan §10.3: Unverified blocks; over-pin features error, never auto-raise."""
    assert get_rule("R-VER-001").severity is Severity.ERROR
    assert get_rule("R-VER-002").severity is Severity.ERROR


def test_engine_order_is_the_declared_tier_order():
    assert TIER_ORDER == (
        Tier.STRUCTURAL,
        Tier.RELATIONAL,
        Tier.CONTRACT,
        Tier.VARIANT,
        Tier.PREFLIGHT,
    )


def test_rules_by_tier_partitions_the_catalogue():
    grouped = rules_by_tier()
    total = sum(len(rules) for rules in grouped.values())
    assert total == len(RULES)
    for tier, rules in grouped.items():
        assert all(r.tier is tier for r in rules)


def test_known_sections_of_the_matrix_are_represented():
    ids = {r.rule_id for r in RULES}
    for section in (
        "R-ROOT-001",  # root-level
        "R-ENT-001",   # entity
        "R-MSA-001",   # msa
        "R-TPL-001",   # template
        "R-BND-001",   # ligand / bond
    ):
        assert section in ids


def test_get_rule_unknown_id_raises():
    with pytest.raises(KeyError):
        get_rule("R-NOPE-999")


def test_preflight_rules_default_to_warning_at_most():
    """Plan §9.2: preflight defaults to WARNING; the SMILES probe rule is the
    documented ERROR exception when a probe is available (plan §9.6)."""
    for rule in RULES:
        if rule.tier is Tier.PREFLIGHT and rule.rule_id != "R-ENT-010":
            assert rule.severity is Severity.WARNING, rule.rule_id
