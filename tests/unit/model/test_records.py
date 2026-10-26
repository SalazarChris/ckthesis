"""Unit tests for the four record families plus ModificationRecord,
ByCode/ByNotation, and Linkage (plan §7.4, §7.5; spec §7, MAP-005..009)."""

from __future__ import annotations

import pytest

from configbuilder.identity import EntityId, Multiplicity
from configbuilder.model import (
    AlignmentAutomatic,
    AlignmentBoth,
    AlignmentError,
    ByCode,
    ByNotation,
    ComponentCode,
    ComponentRecord,
    ComponentRepresentationError,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    Inline,
    LinkEndpoint,
    Linkage,
    ModificationRecord,
    Position,
    RecordError,
    ResidueRef,
    SequenceText,
    fold_representation,
)


def _multiplicity(value: str = "A") -> Multiplicity:
    return Multiplicity([value])


def _protein(text: str = "PEPTIDE") -> SequenceText:
    return SequenceText(text, "protein")


class TestFamilyARecord:
    def test_constructs_minimal(self):
        record = FamilyARecord(ids=_multiplicity(), sequence=_protein())
        assert record.ids == _multiplicity()
        assert record.sequence == _protein()

    def test_defaults_are_unobtrusive(self):
        record = FamilyARecord(ids=_multiplicity(), sequence=_protein())
        assert record.modifications == ()
        assert isinstance(record.alignment, AlignmentAutomatic)
        assert record.description is not None

    def test_requires_protein_sequence(self):
        with pytest.raises(RecordError):
            FamilyARecord(ids=_multiplicity(), sequence=SequenceText("ACGU", "rna"))

    def test_holds_modifications(self):
        modification = ModificationRecord(
            code=ComponentCode("TPO"), position=Position(3)
        )
        record = FamilyARecord(
            ids=_multiplicity(), sequence=_protein(), modifications=(modification,)
        )
        assert record.modifications == (modification,)

    def test_holds_alignment_case(self):
        record = FamilyARecord(
            ids=_multiplicity(),
            sequence=_protein(),
            alignment=AlignmentBoth(source=Inline("pairing")),
        )
        assert isinstance(record.alignment, AlignmentBoth)

    def test_rejects_foreign_alignment(self):
        with pytest.raises(AlignmentError):
            FamilyARecord(ids=_multiplicity(), sequence=_protein(), alignment="auto")  # type: ignore[arg-type]

    def test_requires_multiplicity_ids(self):
        with pytest.raises(RecordError):
            FamilyARecord(ids="A", sequence=_protein())  # type: ignore[arg-type]

    def test_is_immutable(self):
        record = FamilyARecord(ids=_multiplicity(), sequence=_protein())
        with pytest.raises(RecordError):
            record.sequence = _protein("OTHER")  # type: ignore[misc]

    def test_equality_by_value(self):
        one = FamilyARecord(ids=_multiplicity(), sequence=_protein())
        two = FamilyARecord(ids=Multiplicity(["A"]), sequence=SequenceText("PEPTIDE", "protein"))
        assert one == two
        assert hash(one) == hash(two)


class TestFamilyBRecord:
    def test_constructs_with_rna_sequence(self):
        record = FamilyBRecord(
            ids=_multiplicity("B"), sequence=SequenceText("ACGU", "rna")
        )
        assert record.sequence.text == "ACGU"

    def test_requires_rna_sequence(self):
        with pytest.raises(RecordError):
            FamilyBRecord(ids=_multiplicity("B"), sequence=_protein())

    def test_defaults_to_single_automatic(self):
        from configbuilder.model import SingleAutomatic

        record = FamilyBRecord(ids=_multiplicity("B"), sequence=SequenceText("ACGU", "rna"))
        assert isinstance(record.alignment, SingleAutomatic)

    def test_has_no_reference_field(self):
        assert not hasattr(FamilyBRecord(ids=_multiplicity("B"), sequence=SequenceText("ACGU", "rna")), "references")


class TestFamilyCRecord:
    def test_constructs_with_dna_sequence(self):
        record = FamilyCRecord(
            ids=_multiplicity("C"), sequence=SequenceText("ACGT", "dna")
        )
        assert record.sequence.text == "ACGT"

    def test_requires_dna_sequence(self):
        with pytest.raises(RecordError):
            FamilyCRecord(ids=_multiplicity("C"), sequence=_protein())

    def test_has_no_alignment_and_no_reference_field(self):
        """DOMAIN_MAPPING §6 note: the contract grants DNA neither; the type
        cannot hold what the contract does not grant."""
        record = FamilyCRecord(ids=_multiplicity("C"), sequence=SequenceText("ACGT", "dna"))
        assert not hasattr(record, "alignment")
        assert not hasattr(record, "references")

    def test_holds_modifications(self):
        modification = ModificationRecord(code=ComponentCode("5MC"), position=Position(2))
        record = FamilyCRecord(
            ids=_multiplicity("C"),
            sequence=SequenceText("ACGT", "dna"),
            modifications=(modification,),
        )
        assert record.modifications == (modification,)


class TestComponentRecord:
    def test_constructs_by_code(self):
        record = ComponentRecord(ids=_multiplicity("D"), representation=ByCode((ComponentCode("TPO"),)))
        assert record.representation.codes == (ComponentCode("TPO"),)

    def test_constructs_by_notation(self):
        record = ComponentRecord(
            ids=_multiplicity("D"), representation=ByNotation("C1=CC=CC=C1")
        )
        assert record.representation.text == "C1=CC=CC=C1"

    def test_representation_is_mutually_exclusive_by_construction(self):
        """MAP-406: exactly one representation; the field holds one case."""
        by_code = ByCode((ComponentCode("TPO"),))
        assert not isinstance(by_code, ByNotation)


class TestByCodeAndByNotation:
    def test_by_code_requires_at_least_one_code(self):
        with pytest.raises(ComponentRepresentationError):
            ByCode(())

    def test_by_code_rejects_foreign_codes(self):
        with pytest.raises(ComponentRepresentationError):
            ByCode(("TPO",))  # type: ignore[arg-type]

    def test_by_notation_requires_non_empty_text(self):
        with pytest.raises(ComponentRepresentationError):
            ByNotation("   ")

    def test_both_are_immutable(self):
        with pytest.raises(ComponentRepresentationError):
            ByCode((ComponentCode("TPO"),)).codes = ()  # type: ignore[misc]
        with pytest.raises(ComponentRepresentationError):
            ByNotation("x").text = "y"  # type: ignore[misc]


class TestFoldRepresentation:
    def test_dispatches_both_representations(self):
        by_code = ByCode((ComponentCode("TPO"), ComponentCode("MLZ")))
        by_notation = ByNotation("CCO")
        assert (
            fold_representation(by_code, lambda codes: codes, lambda text: text)
            == (ComponentCode("TPO"), ComponentCode("MLZ"))
        )
        assert (
            fold_representation(by_notation, lambda codes: codes, lambda text: text)
            == "CCO"
        )

    def test_raises_on_unknown_value(self):
        with pytest.raises(ComponentRepresentationError):
            fold_representation("TPO", lambda c: c, lambda t: t)  # type: ignore[arg-type]


class TestModificationRecord:
    def test_constructs_with_code_and_position(self):
        record = ModificationRecord(code=ComponentCode("TPO"), position=Position(7))
        assert record.code == ComponentCode("TPO")
        assert record.position == Position(7)

    def test_rejects_foreign_code_and_position(self):
        with pytest.raises(RecordError):
            ModificationRecord(code="TPO", position=Position(1))  # type: ignore[arg-type]
        with pytest.raises(RecordError):
            ModificationRecord(code=ComponentCode("TPO"), position=7)  # type: ignore[arg-type]

    def test_is_immutable(self):
        record = ModificationRecord(code=ComponentCode("TPO"), position=Position(7))
        with pytest.raises(RecordError):
            record.code = ComponentCode("MLZ")  # type: ignore[misc]

    def test_equality_and_hash(self):
        one = ModificationRecord(code=ComponentCode("TPO"), position=Position(7))
        two = ModificationRecord(code=ComponentCode("TPO"), position=Position(7))
        assert one == two
        assert hash(one) == hash(two)


class TestLinkage:
    def test_constructs_between_two_endpoints(self):
        a = LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG")
        b = LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(2), atom="C1")
        linkage = Linkage(a, b)
        assert linkage.a == a and linkage.b == b

    def test_requires_link_endpoints(self):
        with pytest.raises(RecordError):
            Linkage(("A", 1, "SG"), ("D", 2, "C1"))  # type: ignore[arg-type]

    def test_is_immutable(self):
        a = LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG")
        b = LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(2), atom="C1")
        linkage = Linkage(a, b)
        with pytest.raises(RecordError):
            linkage.a = b  # type: ignore[misc]

    def test_equality_and_hash(self):
        a = LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG")
        b = LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(2), atom="C1")
        assert Linkage(a, b) == Linkage(
            LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG"),
            LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(2), atom="C1"),
        )
        assert hash(Linkage(a, b)) == hash(Linkage(a, b))


class TestLinkEndpoint:
    def test_rejects_foreign_parts(self):
        with pytest.raises(RecordError):
            LinkEndpoint(entity="A", residue=ResidueRef(1), atom="SG")  # type: ignore[arg-type]
        with pytest.raises(RecordError):
            LinkEndpoint(entity=EntityId("A"), residue=1, atom="SG")  # type: ignore[arg-type]
        with pytest.raises(RecordError):
            LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="  ")  # type: ignore[arg-type]

    def test_repr_is_informative(self):
        endpoint = LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG")
        assert "A" in repr(endpoint) and "SG" in repr(endpoint)


def test_record_families_are_disjoint_types():
    """Families share machinery but not identity: no shared base adds
    capability (plan §2.1), and equality never crosses family lines."""
    a = FamilyARecord(ids=_multiplicity(), sequence=_protein())
    c = FamilyCRecord(ids=_multiplicity(), sequence=SequenceText("ACGT", "dna"))
    assert a != c
    assert not (a == c)
