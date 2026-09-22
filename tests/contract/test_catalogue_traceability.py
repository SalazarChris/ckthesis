"""Contract meta-tests guarding the catalogue against spec drift.

Plan §9.7: every rule's ``spec_ref`` must resolve to a real section heading
in AUTHORITATIVE_SPEC.md — this turns contract drift into a test failure —
and every rule carries its DOMAIN_MAPPING.md cross-references.
"""

from __future__ import annotations

import re
from pathlib import Path

from configbuilder.validation.catalogue import RULES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPEC = (PROJECT_ROOT / "AUTHORITATIVE_SPEC.md").read_text(encoding="utf-8")

# Headings appear as "## 4. Top-Level AF3 Contract" / "### 5.1 Protein".
_HEADING_RE = re.compile(r"^#{2,3}\s+(?P<title>.+?)\s*$", re.MULTILINE)
TITLES = {m.group("title") for m in _HEADING_RE.finditer(SPEC)}

# Subsection bodies live under a numbered parent heading; allow a spec_ref to
# resolve either to an exact heading or to "<parent heading> / <subsection>"
# form used for deep citations.
_MAP_RE = re.compile(r"^MAP-\d+$")


def test_every_spec_ref_resolves_to_a_real_heading():
    for rule in RULES:
        assert rule.spec_ref in TITLES, (
            f"{rule.rule_id}: spec_ref {rule.spec_ref!r} is not a heading of AUTHORITATIVE_SPEC.md"
        )


def test_every_rule_carries_mapping_ids():
    for rule in RULES:
        assert rule.mapping_ids, f"{rule.rule_id}: missing MAP-### cross-references"
        for mapping_id in rule.mapping_ids:
            assert _MAP_RE.match(mapping_id), f"{rule.rule_id}: malformed mapping id {mapping_id!r}"


def test_mapping_ids_exist_in_domain_mapping():
    dm_text = (PROJECT_ROOT / "DOMAIN_MAPPING.md").read_text(encoding="utf-8")
    for rule in RULES:
        for mapping_id in rule.mapping_ids:
            assert mapping_id in dm_text, (
                f"{rule.rule_id}: {mapping_id} not found in DOMAIN_MAPPING.md"
            )


def test_expected_rule_count_per_matrix_section():
    """Coverage of the spec §19 matrix, checked by section identity counts."""
    by_prefix = {}
    for rule in RULES:
        prefix = rule.rule_id.split("-")[1]
        by_prefix[prefix] = by_prefix.get(prefix, 0) + 1

    assert by_prefix["ROOT"] == 7, by_prefix   # spec §19 root rows
    assert by_prefix["ENT"] == 10, by_prefix   # spec §19 entity rows
    assert by_prefix["MSA"] == 5, by_prefix    # spec §19 msa rows
    assert by_prefix["TPL"] == 5, by_prefix    # spec §19 template rows
    assert by_prefix["BND"] == 6, by_prefix    # spec §19 ligand/bond rows
    assert by_prefix["POL"] == 7, by_prefix    # deliberately-not-promoted list
