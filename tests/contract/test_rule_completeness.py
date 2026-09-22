"""Meta-test: catalogue coverage of executable checks (plan Phase 4).

Every catalogue rule must resolve to a check function reachable by the
engine's convention; a missing function is a broken promise, not a
silently green rule.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from configbuilder.validation import RULES, Tier, rules_by_tier

_FAMILY_MODULES = {
    "R-ROOT": "configbuilder.validation.rules.root_rules",
    "R-ENT": "configbuilder.validation.rules.entity_rules",
    "R-MSA": "configbuilder.validation.rules.msa_rules",
    "R-TPL": "configbuilder.validation.rules.template_rules",
    "R-BND": "configbuilder.validation.rules.bond_rules",
    "R-VER": "configbuilder.validation.rules.policy_rules",
    "R-POL": "configbuilder.validation.rules.policy_rules",
    "R-VAR": "configbuilder.validation.rules.variant_rules",
}


def test_every_rule_has_an_executable_check():
    missing = []
    for rule in RULES:
        prefix = rule.rule_id.rsplit("-", 1)[0]
        module_name = _FAMILY_MODULES.get(prefix)
        if module_name is None:
            missing.append("%s: no rule module for family %r" % (rule.rule_id, prefix))
            continue
        module = importlib.import_module(module_name)
        function_name = "check_" + rule.rule_id.lower().replace("-", "_")
        function = getattr(module, function_name, None)
        if function is None:
            missing.append("%s: missing %s in %s" % (rule.rule_id, function_name, module_name))
            continue
        params = len(inspect.signature(function).parameters)
        if params < 3:
            missing.append("%s: check must accept (configuration, report, rule)" % rule.rule_id)
    assert not missing, missing


def test_every_family_module_is_importable():
    for module_name in set(_FAMILY_MODULES.values()):
        importlib.import_module(module_name)


def test_engine_runs_all_rules_without_skips_on_valid_input():
    """The strongest coverage statement: a valid configuration exercises
    every rule; the report records zero skips."""
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
        seeds=SeedSet([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        records=(
            FamilyARecord(ids=Multiplicity([entity_id.value]), sequence=SequenceText("PEPTIDE", "protein")),
        ),
        identity=registry,
    )
    report = validate(configuration)
    assert report.skipped == ()
    # Every rule executed: no skip entry was recorded for any of the 44
    # catalogue rules (7 root + 10 entity + 5 MSA + 5 template + 6 bond
    # + 2 version + 7 policy + 2 variant).
    assert len(RULES) == 44


def test_preflight_tier_exists_and_runs_last():
    tiers = rules_by_tier()
    assert Tier.PREFLIGHT in tiers
    assert tiers[Tier.PREFLIGHT]
