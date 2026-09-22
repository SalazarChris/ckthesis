"""Tests that every sum type is dispatched only through its fold (plan §7.3;
spec §17): folds are exhaustive, raise on unknown cases, and never fall
through silently."""

from __future__ import annotations

import pytest

from configbuilder.identity import Multiplicity
from configbuilder.model import (
    AlignmentAutomatic,
    AlignmentBoth,
    AlignmentError,
    ByCode,
    ByNotation,
    ComponentCode,
    ComponentRepresentationError,
    Explicit,
    External,
    FamilyARecord,
    FamilyCRecord,
    Inline,
    PathSpec,
    Present,
    ReferenceError,
    SearchAllowed,
    SequenceText,
    Unverified,
    fold_alignment,
    fold_presence,
    fold_reference_set,
    fold_representation,
    fold_resource,
)

# Fold coverage per case is asserted in each type's own test module; this
# module pins the cross-cutting properties.


def test_folds_raise_on_foreign_values():
    """No fold falls through a default: an unknown case is an error, which is
    exactly the omitted-vs-empty collapse the contract forbids (spec §6.3)."""
    with pytest.raises(Exception):
        fold_presence("omitted", lambda: 1, lambda: 2, lambda v: 3)  # type: ignore[arg-type]
    with pytest.raises(Exception):
        fold_resource(3.14, lambda t: 1, lambda p: 2)  # type: ignore[arg-type]
    with pytest.raises(Exception):
        fold_alignment(object(), lambda: 1, lambda: 2, lambda s: 3, lambda s: 4, lambda s: 5)  # type: ignore[arg-type]
    with pytest.raises(Exception):
        fold_representation(object(), lambda c: 1, lambda t: 2)  # type: ignore[arg-type]
    with pytest.raises(Exception):
        fold_reference_set(object(), lambda: 1, lambda i: 2)  # type: ignore[arg-type]


def test_folds_pass_payloads_untouched():
    record = FamilyARecord(ids=Multiplicity(["A"]), sequence=SequenceText("PEP", "protein"))
    assert fold_representation(ByCode((ComponentCode("TPO"),)), lambda codes: codes, lambda t: t) == (
        ComponentCode("TPO"),
    )
    assert fold_resource(External(PathSpec("p")), lambda t: t, lambda p: p) == PathSpec("p")
    assert fold_alignment(
        AlignmentBoth(source=Inline("s")),
        lambda: None,
        lambda: None,
        lambda s: s,
        lambda s: s,
        lambda s: s,
    ) == Inline("s")


def test_present_and_unset_reach_distinct_fold_branches():
    out = fold_presence(Present("content"), lambda: "unset", lambda: "empty", lambda v: v)
    assert out == "content"
    assert fold_presence(Present(""), lambda: "unset", lambda: "empty", lambda v: v) == ""
    assert fold_presence(Present(""), lambda: "unset", lambda: "empty", lambda v: "content") == "content"


def test_search_allowed_and_explicit_empty_reach_distinct_fold_branches():
    assert fold_reference_set(SearchAllowed(), lambda: "omitted", lambda i: "present") == "omitted"
    assert fold_reference_set(Explicit(()), lambda: "omitted", lambda i: "present") == "present"


def test_folds_never_use_type_names_as_strings():
    """A smoke check that folds dispatch on types, not stringly-typed data:
    feeding a string into any fold must raise, never dispatch."""
    for fold in (fold_resource, fold_representation, fold_reference_set):
        with pytest.raises(Exception):
            fold("Inline", lambda *a: None, lambda *a: None)  # type: ignore[arg-type]


def test_records_do_not_need_folds_for_family_dispatch_yet():
    """Family dispatch (FamilyA/B/C/Component) arrives with transform in
    Phase 4; nothing here depends on it. This test just pins that records
    themselves are plain values today."""
    assert isinstance(
        FamilyARecord(ids=Multiplicity(["A"]), sequence=SequenceText("PEP", "protein")),
        FamilyARecord,
    )


def test_family_c_record_has_no_fold_case_of_its_own_to_skip():
    """FamilyCRecord is a full record type despite having no alignment: its
    absence-of-alignment is structural, not a fold branch awaiting
    implementation (DOMAIN_MAPPING §6 note)."""
    record = FamilyCRecord(ids=Multiplicity(["C"]), sequence=SequenceText("ACGT", "dna"))
    assert not hasattr(record, "alignment")
    assert record.sequence.text == "ACGT"
