"""Property tests: presence preservation and index preservation (plan §10.1).

Phase 5 checklist: "presence-preservation + index-preservation property
tests (no arithmetic)". Every generation of the property strategies is
mapped onto a full ``to_wire`` run, and the emitted document is checked
against the canonical states that produced it:

- **Presence preservation** — a field is absent from the wire object iff
  the canonical state was ``Unset`` (or the family has no such field);
  an explicit-empty canonical state never emits as absent, and an absent
  field never emits as empty.
- **Index preservation** — template ``queryIndices``/``templateIndices``
  are exactly the stored 0-based pairs, in order, with no arithmetic
  applied (offsetting or 1-based shifting would break round-trips).

hypothesis is optional (plan §4: development-only); a seeded random
fallback keeps the properties verified when it is absent.
"""

from __future__ import annotations

import random

import pytest

from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import (
    AlignmentAutomatic,
    AlignmentBoth,
    AlignmentFree,
    AlignmentPairedOnly,
    AlignmentUnpairedOnly,
    Configuration,
    ConfigurationMetadata,
    Explicit,
    ExplicitEmpty,
    External,
    FamilyARecord,
    FormatTarget,
    IndexPair,
    Inline,
    PathSpec,
    Pinned,
    Present,
    ReferenceRecord,
    SearchAllowed,
    SeedSet,
    SequenceText,
    Unset,
)
from configbuilder.transform import to_wire

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAVE_HYPOTHESIS = True
except ImportError:  # pragma: no cover - exercised only without hypothesis
    HAVE_HYPOTHESIS = False

PROTEIN_MSA_FIELDS = ("unpairedMsa", "unpairedMsaPath", "pairedMsa", "pairedMsaPath")


# -- canonical state generators ---------------------------------------------------


def _alignment_case(rng):
    """One of the five AlignmentPairing cases with a fixed payload."""
    kind = rng.choice(
        [
            "automatic",
            "free",
            "unpaired_inline",
            "unpaired_path",
            "paired_inline",
            "paired_path",
            "both_inline",
            "both_path",
        ]
    )
    if kind == "automatic":
        return AlignmentAutomatic()
    if kind == "free":
        return AlignmentFree()
    if kind in ("unpaired_inline", "paired_inline", "both_inline"):
        source = Inline(">q\nPEPTIDE")
    else:
        source = External(PathSpec("query.a3m"))
    if kind.startswith("unpaired"):
        return AlignmentUnpairedOnly(source=source)
    if kind.startswith("paired"):
        return AlignmentPairedOnly(source=source)
    return AlignmentBoth(source=source)


def _reference_case(rng):
    """SearchAllowed or an Explicit set with an arbitrary 0-based index map."""
    if rng.random() < 0.3:
        return SearchAllowed()
    pairs = tuple(
        IndexPair(rng.randint(0, 999), rng.randint(0, 999))
        for _ in range(rng.randint(0, 6))
    )
    source = Inline(">t\nTEMPLATE") if rng.random() < 0.5 else External(PathSpec("t.cif"))
    return Explicit((ReferenceRecord(source=source, index_map=pairs),))


def _protein_case(rng):
    """A FamilyARecord drawing description/alignment/references states."""
    description = rng.choice([Unset(), ExplicitEmpty(), Present("annotated chain")])
    return FamilyARecord(
        ids=Multiplicity([rng.choice(["A", "AB"])]),
        sequence=SequenceText("PEPTIDE", "protein"),
        description=description,
        alignment=_alignment_case(rng),
        references=_reference_case(rng),
    )


def _wire(configuration):
    result = to_wire(
        Configuration(
            metadata=ConfigurationMetadata("property"),
            seeds=SeedSet([1]),
            records=(configuration,),
            identity=IdentityRegistry(),
        ).with_format_target(FormatTarget(version_selection=Pinned(4)))
    )
    return result.document["sequences"][0]["protein"]


# -- presence preservation ---------------------------------------------------------


def _assert_presence_preserved(record, protein):
    """Emitted-set-of-fields is exactly the Present-set of canonical states."""
    if isinstance(record.description, Unset):
        assert "description" not in protein
    else:
        assert "description" in protein
        if record.description is not None and not isinstance(record.description, Unset):
            expected = "" if isinstance(record.description, ExplicitEmpty) else record.description.value
            assert protein["description"] == expected

    alignment = record.alignment
    if isinstance(alignment, AlignmentAutomatic):
        for field in PROTEIN_MSA_FIELDS:
            assert field not in protein, field
    else:
        # At least one MSA field is emitted and the pairing shape holds:
        # both sides represented, empty side as the inline "".
        emitted = [field for field in PROTEIN_MSA_FIELDS if field in protein]
        assert emitted, "custom/MSA-free state must emit both sides"
        if isinstance(alignment, AlignmentFree):
            assert protein["unpairedMsa"] == "" and protein["pairedMsa"] == ""
        else:
            # Within a side inline xor path (spec §6.1): a side may omit
            # either field, so probe with .get — but the provided side is
            # non-empty in whichever form it chose.
            unpaired = protein.get("unpairedMsa", "") or protein.get("unpairedMsaPath", "")
            paired = protein.get("pairedMsa", "") or protein.get("pairedMsaPath", "")
            if not isinstance(alignment, AlignmentPairedOnly):
                assert unpaired, "unpaired side must carry content or a path"
            if not isinstance(alignment, AlignmentUnpairedOnly):
                assert paired, "paired side must carry content or a path"
        if isinstance(alignment, AlignmentPairedOnly):
            assert protein["unpairedMsa"] == ""
            assert "unpairedMsaPath" not in protein
        if isinstance(alignment, AlignmentUnpairedOnly):
            assert protein["pairedMsa"] == ""
            assert "pairedMsaPath" not in protein


def _random_case(rng):
    record = _protein_case(rng)
    protein = _wire(record)
    _assert_presence_preserved(record, protein)


def test_seeded_presence_preservation():
    rng = random.Random(20260921)
    for _ in range(120):
        _random_case(rng)


if HAVE_HYPOTHESIS:

    @settings(max_examples=50, deadline=None)
    @given(st.randoms(use_true_random=False))
    def test_hypothesis_presence_preservation(rng):
        _random_case(rng)


# -- index preservation ------------------------------------------------------------


def _random_index_case(rng):
    record = _protein_case(rng)
    protein = _wire(record)
    references = record.references
    if not isinstance(references, Explicit):
        assert "templates" not in protein
        return
    entry = protein["templates"][0]
    stored = references.items[0].index_map
    if not stored:
        assert "queryIndices" not in entry and "templateIndices" not in entry
        return
    # The parallel arrays are exactly the stored 0-based pairs, in order:
    # no offsetting, no 1-based shifting, no reordering (plan §10.1).
    assert entry["queryIndices"] == [pair.query for pair in stored]
    assert entry["templateIndices"] == [pair.template for pair in stored]
    assert all(0 <= value for value in entry["queryIndices"])
    assert all(0 <= value for value in entry["templateIndices"])


def test_seeded_index_preservation():
    rng = random.Random(20260922)
    for _ in range(120):
        _random_index_case(rng)


if HAVE_HYPOTHESIS:

    @settings(max_examples=50, deadline=None)
    @given(st.randoms(use_true_random=False))
    def test_hypothesis_index_preservation(rng):
        _random_index_case(rng)
