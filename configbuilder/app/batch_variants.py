"""Batch variant generation — one base, one entity per variant.

The reusable operation behind "generate variants from a sequence file":
for each input sequence, create **one independent variant spec** equal
to ``base + AddRecord(<that sequence>)``. The base configuration is
never touched — ``AddRecord`` reserves the record's identifiers through
a *cloned* registry at expansion time (variants/edits.py), and
``expansion.expand`` applies every spec to the same base object — so
independence and base immutability are structural properties of the
existing variant architecture, not extra code here:

    Base ── + SEQ_A ──▶ Variant A
        └── + SEQ_B ──▶ Variant B        (never A → A+B → A+B+C)

Every record is built through the same validated constructors the
normal entity path uses (``SequenceText``, ``Multiplicity``,
``FamilyARecord``), and every identifier comes from the project's
``IdentityRegistry`` — allocated here from a *throwaway clone* of the
base registry (never committed to the base, so the base registry never
claims an identifier no record holds), then re-reserved by ``AddRecord``
inside each variant's own expansion-time clone. Ids are distinct across
the whole batch and from every base id; a later base edit that collides
with a reserved id is refused loudly at expansion, never renamed.

Validation of each sequence *text* happens at ``SequenceText``
construction — alphabet discipline stays in the model. All invalid
lines are reported together with their file line numbers.

The input is a list of ``(line_number, text)`` pairs — the
``persistence.read_sequence_file`` shape — so this module never touches
the filesystem (plan §5.3 rule 8) and stays testable without files.
"""

from __future__ import annotations

from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import (
    FamilyARecord,
    ModelError,
    SequenceText,
    SequenceTextError,
)
from configbuilder.variants import AddRecord, VariantSpec

__all__ = ["BatchError", "batch_specs_for_sequences"]


class BatchError(Exception):
    """The batch input itself is unusable (empty input, duplicates,
    invalid sequences). One summary so the user fixes the file once."""


def _protein_record(entity_value: str, text: str):
    """The record one sequence becomes. The family → builder table is the
    extension point: a future input kind (RNA, ligand representation)
    adds one builder here and nothing else changes."""
    return FamilyARecord(
        ids=Multiplicity([entity_value]), sequence=SequenceText(text, "protein")
    )


_RECORD_BUILDERS = {"protein": _protein_record}


def batch_specs_for_sequences(entries, registry: IdentityRegistry, key_prefix: str = "batch"):
    """Turn cleaned sequence entries into independent variant specs.

    ``entries`` is a sequence of ``(line_number, text)`` pairs;
    ``registry`` is a **clone** of the base registry used only to
    allocate this batch's identifiers. Returns the tuple of
    ``VariantSpec`` (each with exactly one ``AddRecord`` edit); raises
    ``BatchError`` when the batch as a whole is unusable.

    Naming: keys are ``<prefix>_NN`` and labels ``<prefix> NN`` —
    two-digit, deterministic, ordered by input position. No sequence
    text ever enters a name or a filename.
    """
    entries = tuple(entries)
    if not entries:
        raise BatchError("the sequence file contains no usable sequences")

    builder = _RECORD_BUILDERS.get("protein")
    if builder is None:  # unreachable today; guards the extension point
        raise BatchError("no record builder for batch sequence input")

    seen = set()
    duplicates = []
    for _, text in entries:
        if text in seen and text not in duplicates:
            duplicates.append(text)
        seen.add(text)
    if duplicates:
        raise BatchError(
            "the sequence file contains duplicate sequences: %s"
            % ", ".join("%s…" % text[:12] for text in duplicates)
        )

    failures = []
    specs = []
    for index, (line_number, text) in enumerate(entries, start=1):
        try:
            entity = registry.allocate(owner="batch_variant")
            record = builder(entity.value, text)
        except (ModelError, SequenceTextError) as error:
            failures.append("line %d: %s" % (line_number, error))
            continue
        spec = VariantSpec(
            key="%s_%02d" % (key_prefix, index),
            label="%s %d" % (key_prefix, index),
            edits=(AddRecord(record),),
        )
        specs.append(spec)
    if failures:
        raise BatchError(
            "%d of %d sequences are invalid:\n  %s"
            % (len(failures), len(entries), "\n  ".join(failures))
        )
    return tuple(specs)
