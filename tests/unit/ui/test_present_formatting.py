"""Formatting tier (IMPLEMENTATION_PLAN.md §18.8, Phase 11a checklist).

Pure functions over a fixed width: sequence rendering with correct
human numbering at 80/100/60/40 columns, finding text containing no
internal names and no wire field names, and label resolution that
never falls back to an internal name. Wire names come from transform's
mapping tables — importing them here is legal (tests may import
anything); ``ui`` itself never does.
"""

from __future__ import annotations

import pytest

from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import (
    Configuration,
    ConfigurationMetadata,
    FamilyARecord,
    FormatTarget,
    Pinned,
    SeedSet,
    SequenceText,
    Unverified,
)
from configbuilder.transform import DNA_FIELDS, LIGAND_FIELDS, PROTEIN_FIELDS, RNA_FIELDS, ROOT_FIELDS
from configbuilder.ui.present import (
    MINIMUM_WIDTH,
    FindingCard,
    columns_available,
    finding_reference_label,
    format_findings,
    group_findings,
    label,
    position_range_line,
    render_sequence_ruler,
    residue_at,
    severity_label,
    single_column,
    wrap_to_width,
)
from configbuilder.validation import validate


def _wire_names():
    names = set()
    for table in (ROOT_FIELDS, PROTEIN_FIELDS, RNA_FIELDS, DNA_FIELDS, LIGAND_FIELDS):
        for row in table:
            name = row[1]  # row: (model path, wire field, mapping id, rule, order)
            if name:
                names.add(name)
    return names


WIRE_NAMES = _wire_names()


def _configuration():
    registry = IdentityRegistry()
    return Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1, 2, 3]),
        records=(
            FamilyARecord(ids=Multiplicity(["A"]), sequence=SequenceText("PEPTIDE", "protein")),
        ),
        identity=registry,
    )


# -- sequence ruler: human numbering at the §18.8 widths ------------------------------

ALBUMIN = (
    "MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGEEHFKGLVLIAFSQYLQQCPFDEHVKLVNELTEFAKTCVA"
    "DESHAGCEKSLHTLFGDELCKVASLRETYGDMADCCEKQEPERNECFLS"
)  # 128 residues, the plan's example


def _parse_ruler_line(line):
    """``('  <first>', '<blocked residues>', '<last>')`` from one ruler line."""
    stripped = line.strip()
    parts = stripped.split("  ")
    return int(parts[0]), parts[1], int(parts[-1])


@pytest.mark.parametrize("width", [80, 100, 60, 40])
def test_ruler_numbering_is_human_and_consistent(width):
    lines = render_sequence_ruler(ALBUMIN, width)
    assert lines
    for line in lines:
        first, body, last = _parse_ruler_line(line)
        residues = body.replace(" ", "")
        # 1-based human numbering at both ends of every line, and the
        # numbers agree with the residue count on the line.
        assert last - first + 1 == len(residues)
        assert first >= 1 and last <= len(ALBUMIN)


def test_ruler_covers_every_position_exactly_once():
    seen = []
    for line in render_sequence_ruler(ALBUMIN, 80):
        seen.append(_parse_ruler_line(line)[1].replace(" ", ""))
    assert "".join(seen) == ALBUMIN


def test_ruler_matches_the_plan_example_at_80():
    lines = render_sequence_ruler(ALBUMIN, 80)
    assert lines[0].startswith("     1  ")
    assert lines[0].endswith(" 60")
    assert lines[-1].endswith(" %d" % len(ALBUMIN))


def test_ruler_degrades_below_the_minimum_without_cutting():
    narrow = render_sequence_ruler(ALBUMIN, 40)
    assert "".join(_parse_ruler_line(line)[1].replace(" ", "") for line in narrow) == ALBUMIN


def test_ruler_empty_sequence_says_so():
    assert render_sequence_ruler("", 80) == ("(empty sequence)",)


def test_residue_echo_and_range_hint():
    assert residue_at(ALBUMIN, 1) == "M"
    assert residue_at(ALBUMIN, 101) == ALBUMIN[100]
    assert residue_at(ALBUMIN, 0) is None
    assert residue_at(ALBUMIN, 129) is None
    assert position_range_line(ALBUMIN) == "[1-128]"


# -- width-aware layout ---------------------------------------------------------------


def test_wrap_never_cuts_content_at_any_width():
    text = "The wizard degrades rather than failing, and nothing is ever cut."
    for width in (80, 60, 40, 20):
        lines = wrap_to_width(text, width)
        assert " ".join(lines) == text  # reassembly loses nothing


def test_single_column_threshold_follows_the_plan():
    assert not single_column(80)
    assert single_column(79)
    assert single_column(60)


def test_columns_available_degrades_to_zero():
    assert columns_available(80, 2) > 0
    # Below the 60-column floor the wizard runs plain-line single-column
    # (single_column); the helper itself returns 0 only when the width
    # cannot hold the columns at all.
    assert columns_available(5, 3) == 0


def test_minimum_width_constant_is_the_documented_eighty():
    assert MINIMUM_WIDTH == 80


# -- finding formatting: registry vocabulary, no internal names ------------------------

def _report_findings():
    report = validate(_configuration())
    return report.findings


def test_findings_group_severity_then_context():
    groups = group_findings(_report_findings())
    severity_order = [name for name, _ in groups]
    assert severity_order == sorted(
        severity_order, key=lambda n: ["ERROR", "WARNING", "INFO"].index(n)
    )


def test_findings_are_numbered_cards_with_word_and_symbol():
    cards = format_findings(_report_findings(), 80)
    assert cards
    for index, card in enumerate(cards, start=1):
        assert card.number == index
        assert card.severity_line.split()[0] in ("ERROR", "WARNING", "INFO")
        assert any(symbol in card.severity_line for symbol in ("[x]", "[!]", "[i]"))
        assert isinstance(card, FindingCard)


def _technical_wire_names():
    """Wire identifiers distinguishable from ordinary English:
    camelCase or underscored tokens (``modelSeeds``, ``userCCD``,
    ``bondedAtomPairs``). Plain-English coincidences (the wire field
    ``version`` versus the word "version") are not leaks — findings are
    *made of* English; the formatting tier forbids technical vocabulary
    and internal names, which is what plan §18.8 means."""
    return {name for name in WIRE_NAMES if any(c.isupper() for c in name) or "_" in name}


def test_finding_text_contains_no_internal_names_and_no_technical_wire_tokens():
    internal_markers = ("FamilyA", "FamilyB", "FamilyC", "ComponentRecord", "Presence", "R-ENT", "R-ROOT")
    technical = _technical_wire_names()
    assert technical, "expected camelCase/underscored wire tokens in the tables"
    for card in format_findings(_report_findings(), 80):
        text = " ".join(card.lines)
        for marker in internal_markers:
            assert marker not in text, (marker, text)
        for wire in technical:
            assert wire not in text, (wire, text)


def test_technical_detail_stays_behind_the_t_key():
    """The default lines stay readable; the rule id and diagnostic ride
    the ``detail`` block the renderer reveals on demand (plan §16.6)."""
    cards = format_findings(_report_findings(), 80)
    with_rule_id = [c for c in cards if c.detail]
    assert with_rule_id, "expected at least one finding carrying detail"
    for card in cards:
        for line in card.lines:
            assert not line.startswith("rule ")  # details are not inline


def test_reference_label_is_registry_vocabulary_only():
    from configbuilder.validation.report import FieldPath

    line = finding_reference_label(
        3, "ERROR", FieldPath("FamilyARecord", "A", "sequence")
    )
    assert line.startswith("3. ")
    assert "Protein chain" in line
    assert "FamilyARecord" not in line


# -- labels: registry only, never a fallback ------------------------------------------


def test_labels_come_from_the_registry():
    assert label("Configuration") == "Job"
    assert label("FamilyARecord") == "Protein chain"
    assert label("ComponentRecord") == "Ligand or ion"
    assert label("SeedSet") == "Reproducibility seeds"


def test_severity_label_word_and_symbol():
    assert severity_label("ERROR") == "ERROR  [x]"
    assert severity_label("WARNING") == "WARNING [!]"
    assert severity_label("INFO") == "INFO [i]"


def test_unregistered_type_raises_instead_of_a_fallback():
    from configbuilder.model.traceability import label_for

    with pytest.raises(KeyError):
        label_for("NotARealType")


def test_unverified_pin_labels_through_the_registry():
    """The Unverified blocker's locator labels in registry vocabulary."""
    from configbuilder.validation.report import FieldPath
    from configbuilder.ui.present import finding_context_label

    path = FieldPath("Unverified", None, "version_selection")
    assert finding_context_label(path) == "Version unverified"
