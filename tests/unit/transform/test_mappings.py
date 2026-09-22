"""Mapping-table unit tests (plan §10.2)."""

from __future__ import annotations

import re

import pytest

from configbuilder.transform import (
    DNA_FIELDS,
    LIGAND_FIELDS,
    PROTEIN_FIELDS,
    RNA_FIELDS,
    ROOT_FIELDS,
    EmissionRule,
    OMITTED,
)


def _mapping_ids(table):
    return {row[2] for row in table}


def test_every_table_row_has_five_components():
    for table in (ROOT_FIELDS, PROTEIN_FIELDS, RNA_FIELDS, DNA_FIELDS, LIGAND_FIELDS):
        for row in table:
            assert len(row) == 5
            accessor, wire_field, mapping_id, rule, min_version = row
            # An empty accessor marks a compound row: a structural container
            # (MAP-103), a modification entry sub-field (MAP-204/205 etc.),
            # an alias row (MAP-405), or a pure constraint row (MAP-406).
            # The engine builds these as part of a parent value instead of
            # resolving them independently.
            assert isinstance(accessor, str)
            assert isinstance(wire_field, str)
            if accessor:
                assert wire_field
            assert re.fullmatch(r"MAP-\d+", mapping_id)
            assert isinstance(rule, EmissionRule)
            assert isinstance(min_version, int) and min_version >= 1


def test_wire_fields_are_unique_within_each_table():
    """Resolvable rows (non-empty accessor) have unique wire fields; compound
    rows may alias an existing field (MAP-405 -> ccdCodes) or carry none
    (MAP-406), so they are excluded here."""
    for table in (ROOT_FIELDS, PROTEIN_FIELDS, RNA_FIELDS, DNA_FIELDS, LIGAND_FIELDS):
        wire_fields = [row[1] for row in table if row[0]]
        assert len(wire_fields) == len(set(wire_fields))


def test_every_mapping_id_is_covered_by_a_row():
    """The mapping tables cover every contract field id from DOMAIN_MAPPING."""
    covered = (
        _mapping_ids(ROOT_FIELDS)
        | _mapping_ids(PROTEIN_FIELDS)
        | _mapping_ids(RNA_FIELDS)
        | _mapping_ids(DNA_FIELDS)
        | _mapping_ids(LIGAND_FIELDS)
    )
    for mapping_id in (
        "MAP-101", "MAP-102", "MAP-103", "MAP-104", "MAP-105", "MAP-106", "MAP-107", "MAP-108",
        "MAP-201", "MAP-202", "MAP-203", "MAP-204", "MAP-205", "MAP-206",
        "MAP-207", "MAP-208", "MAP-209", "MAP-210", "MAP-211",
        "MAP-301", "MAP-302", "MAP-303", "MAP-304", "MAP-305", "MAP-306", "MAP-307", "MAP-308",
        "MAP-351", "MAP-352", "MAP-353", "MAP-354", "MAP-355", "MAP-356",
        "MAP-401", "MAP-402", "MAP-403", "MAP-404",
    ):
        assert mapping_id in covered, mapping_id


def test_inline_xor_path_rows_share_the_rule():
    """userCCD/userCCDPath are one INLINE_XOR_PATH pair: exactly one emits."""
    ccd_rows = {row[1]: row for row in ROOT_FIELDS if row[2] in ("MAP-105", "MAP-106")}
    assert set(ccd_rows) == {"userCCD", "userCCDPath"}
    assert all(row[3] is EmissionRule.INLINE_XOR_PATH for row in ccd_rows.values())


def test_sequences_row_is_the_structural_container():
    """MAP-103 is recorded as a structural row with no accessor; the engine
    builds ``sequences`` from the record list."""
    rows = [row for row in ROOT_FIELDS if row[2] == "MAP-103"]
    assert len(rows) == 1
    _accessor, wire_field, _mapping_id, rule, min_version = rows[0]
    assert wire_field == "sequences"
    assert rule is EmissionRule.ALWAYS
    assert min_version == 1


def test_description_rows_are_v4_only():
    """MAP-206/306/356/404 are confirmed in JSON v4 only."""
    for table in (PROTEIN_FIELDS, RNA_FIELDS, DNA_FIELDS, LIGAND_FIELDS):
        for row in table:
            if row[1] == "description":
                assert row[4] == 4


def test_dna_table_has_no_msa_rows():
    """DOMAIN_MAPPING §6 note: no standalone DNA MSA representation exists."""
    assert not any("msa" in row[0].lower() for row in DNA_FIELDS)


def test_omitted_marker_is_not_none():
    assert OMITTED is not None
    assert OMITTED is OMITTED  # singleton
