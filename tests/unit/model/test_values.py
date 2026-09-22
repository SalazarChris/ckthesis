"""Unit tests for canonical value types (plan §7.2; spec §7, §8)."""

from __future__ import annotations

import pytest

from configbuilder.model import (
    ComponentCode,
    External,
    IndexPair,
    Inline,
    PathSpec,
    Position,
    ResidueRef,
    ResourceRefError,
    Seed,
    SequenceText,
    SequenceTextError,
    ValueTypeError,
    fold_resource,
)

UINT32_MAX = 2 ** 32 - 1


class TestIndexBasesAreDistinct:
    """DOMAIN_MAPPING §10's mixed-index risk, mitigated by nominal types."""

    def test_position_rejects_zero(self):
        with pytest.raises(ValueTypeError):
            Position(0)

    def test_position_rejects_bool(self):
        with pytest.raises(ValueTypeError):
            Position(True)

    def test_residue_ref_rejects_zero(self):
        with pytest.raises(ValueTypeError):
            ResidueRef(0)

    def test_index_pair_rejects_negative(self):
        with pytest.raises(ValueTypeError):
            IndexPair(-1, 0)

    def test_index_pair_accepts_zero_based_values(self):
        assert IndexPair(0, 0).query == 0

    def test_position_accepts_index_pair_rejects_value(self):
        assert Position(1).value == 1

    def test_types_are_not_interchangeable(self):
        assert Position(3) != ResidueRef(3)
        assert Position(3) != IndexPair(3, 3)
        assert ResidueRef(3) != IndexPair(3, 3)


class TestSeed:
    def test_range_is_uint32(self):
        assert Seed(0).value == 0
        assert Seed(UINT32_MAX).value == UINT32_MAX

    def test_rejects_below_range(self):
        with pytest.raises(ValueTypeError):
            Seed(-1)

    def test_rejects_above_range(self):
        with pytest.raises(ValueTypeError):
            Seed(UINT32_MAX + 1)

    def test_rejects_bool(self):
        with pytest.raises(ValueTypeError):
            Seed(True)


class TestSequenceText:
    def test_protein_alphabet(self):
        assert SequenceText("PEPTIDE", "protein").text == "PEPTIDE"

    def test_rna_alphabet(self):
        assert SequenceText("ACGU", "rna").text == "ACGU"

    def test_dna_alphabet(self):
        assert SequenceText("ACGT", "dna").text == "ACGT"

    def test_rna_rejects_t(self):
        with pytest.raises(SequenceTextError):
            SequenceText("ACGT", "rna")

    def test_dna_rejects_u(self):
        with pytest.raises(SequenceTextError):
            SequenceText("ACGU", "dna")

    def test_protein_rejects_lowercase(self):
        with pytest.raises(SequenceTextError):
            SequenceText("peptide", "protein")

    def test_rejects_empty(self):
        with pytest.raises(SequenceTextError):
            SequenceText("", "protein")

    def test_rejects_unknown_family(self):
        with pytest.raises(SequenceTextError):
            SequenceText("ACGU", "ligand")

    def test_family_is_part_of_equality(self):
        assert SequenceText("A", "protein") != SequenceText("A", "rna")

    def test_len_is_sequence_length(self):
        assert len(SequenceText("PEP", "protein")) == 3


class TestComponentCode:
    def test_accepts_plain_code(self):
        assert ComponentCode("TPO").value == "TPO"

    def test_rejects_forbidden_prefix(self):
        """spec §8.1: standalone AF3 rejects the CCD_ prefix (MAP-204)."""
        with pytest.raises(ValueTypeError, match="CCD_"):
            ComponentCode("CCD_TPO")

    def test_prefix_check_is_case_insensitive(self):
        with pytest.raises(ValueTypeError):
            ComponentCode("ccd_tpo")

    def test_strips_surrounding_whitespace(self):
        assert ComponentCode("  TPO ").value == "TPO"

    def test_rejects_empty(self):
        with pytest.raises(ValueTypeError):
            ComponentCode("   ")

    def test_rejects_non_string(self):
        with pytest.raises(ValueTypeError):
            ComponentCode(42)  # type: ignore[arg-type]


class TestResourceRefs:
    def test_inline_and_external_are_distinct(self):
        assert Inline("a3m-content") != External(PathSpec("file.a3m"))

    def test_path_spec_preserves_raw_path(self):
        assert PathSpec("../msas/query.a3m").raw == "../msas/query.a3m"

    def test_rejects_blank_path(self):
        with pytest.raises(ResourceRefError):
            PathSpec("   ")

    def test_rejects_non_string_path(self):
        with pytest.raises(ResourceRefError):
            PathSpec(42)  # type: ignore[arg-type]

    def test_rejects_non_string_inline(self):
        with pytest.raises(ResourceRefError):
            Inline(42)  # type: ignore[arg-type]

    def test_external_requires_path_spec(self):
        with pytest.raises(ResourceRefError):
            External("file.a3m")  # type: ignore[arg-type]

    def test_refs_are_immutable(self):
        with pytest.raises(ResourceRefError):
            Inline("x").text = "y"  # type: ignore[misc]
        with pytest.raises(ResourceRefError):
            External(PathSpec("x")).path = PathSpec("y")  # type: ignore[misc]

    def test_fold_covers_both_cases(self):
        assert (
            fold_resource(Inline("text"), lambda t: ("inline", t), lambda p: ("external", p.raw))
            == ("inline", "text")
        )
        assert (
            fold_resource(
                External(PathSpec("p.a3m")), lambda t: ("inline", t), lambda p: ("external", p.raw)
            )
            == ("external", "p.a3m")
        )

    def test_fold_raises_on_unknown(self):
        with pytest.raises(ResourceRefError):
            fold_resource("inline text", lambda t: t, lambda p: p)  # type: ignore[arg-type]


def test_index_pair_equality_and_hash():
    assert IndexPair(0, 2) == IndexPair(0, 2)
    assert IndexPair(0, 2) != IndexPair(2, 0)
    assert hash(IndexPair(1, 5)) == hash(IndexPair(1, 5))


def test_position_and_residue_ref_hash_by_value():
    assert hash(Position(7)) == hash(Position(7))
    assert hash(ResidueRef(7)) == hash(ResidueRef(7))
