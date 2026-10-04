"""Pure-layer tests for the DNA reverse complement (DNA duplex feature).

The complement lives in the model's value layer so every caller — the
service today, any future importer — receives the same orientation
guarantee: both strands are conventional 5'-to-3' sequences, so the
partner of a strand is its reverse complement, never a per-position
complement.
"""

from __future__ import annotations

import pytest

from configbuilder.identity import Multiplicity
from configbuilder.model import (
    DnaComplementError,
    FamilyCRecord,
    SequenceText,
    reverse_complement,
)


def test_reverse_complement_reverses_and_complements():
    # 5'-ATGC-3' partners with 5'-GCAT-3' — the reverse complement.
    partner = reverse_complement(SequenceText("ATGC", "dna"))
    assert partner.text == "GCAT"
    assert partner.family == "dna"


def test_reverse_complement_is_involution():
    sequence = SequenceText("GATTACA", "dna")
    assert reverse_complement(reverse_complement(sequence)).text == "GATTACA"


def test_result_is_a_fresh_value_type():
    original = SequenceText("ATGC", "dna")
    partner = reverse_complement(original)
    assert partner is not original
    assert original.text == "ATGC"  # untouched


def test_palindromic_strand_is_its_own_partner():
    # A reverse-complement palindrome produces an equal partner strand;
    # two AF3 DNA entities with equal sequences are still legal.
    assert reverse_complement(SequenceText("ATAT", "dna")).text == "ATAT"


@pytest.mark.parametrize("text,family", [("AUG", "rna"), ("PEPTIDE", "protein")])
def test_non_dna_family_is_refused(text, family):
    with pytest.raises(DnaComplementError):
        reverse_complement(SequenceText(text, family))


def test_non_sequence_input_is_refused():
    with pytest.raises(DnaComplementError):
        reverse_complement("ATGC")


def test_record_complement_keeps_identity_and_metadata():
    record = FamilyCRecord(
        ids=Multiplicity(["B"]),
        sequence=SequenceText("ATGC", "dna"),
        description=None,
    )
    partner = record.complement()
    assert [entity.value for entity in partner.ids] == ["B"]
    assert partner.sequence.text == "GCAT"
    assert partner.description == record.description
    assert partner.modifications == record.modifications
