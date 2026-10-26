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

Supports multiple input types:
- Protein sequences (FASTA-like .txt files)
- Ligand SMILES strings
- DNA sequences

Each input type gets its own record builder, and the same spec
architecture is used for all — a batch entry is the same ``base +
AddRecord`` construction a hand-made change is, and it flows through the
same validation and generation pipeline.

Ligand files carry a name per entry (``name SMILES``), and that name is
kept: :func:`ligand_specs_for_entries` derives each spec's key from it, so
the generated file is named after the molecule the user named instead of a
positional ``batch_NN``. Names are slugged (``output.naming.slug``) because
a key becomes part of a path; duplicate names take a deterministic numeric
suffix in file order, and a name that cannot be slugged falls back to its
position.
"""

from __future__ import annotations

from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import (
    ByNotation,
    ComponentRecord,
    FamilyARecord,
    FamilyCRecord,
    ModelError,
    SequenceText,
    SequenceTextError,
)
from configbuilder.variants import AddRecord, VariantSpec

__all__ = [
    "BatchError",
    "batch_specs_for_sequences",
    "ligand_specs_for_entries",
    "BATCH_RECORD_BUILDERS",
]


class BatchError(Exception):
    """The batch input itself is unusable (empty input, duplicates,
    invalid sequences). One summary so the user fixes the file once."""


def _protein_record(entity_value: str, text: str):
    """The record one protein sequence becomes."""
    return FamilyARecord(
        ids=Multiplicity([entity_value]), sequence=SequenceText(text, "protein")
    )


def _dna_record(entity_value: str, text: str):
    """The record one DNA sequence becomes."""
    return FamilyCRecord(
        ids=Multiplicity([entity_value]), sequence=SequenceText(text, "dna")
    )


def _ligand_record(entity_value: str, smiles: str):
    """The record one ligand (SMILES) becomes.

    A ligand's representation is the model's ``ByNotation`` sum-type case,
    not a ``SequenceText``: SMILES is not a sequence alphabet, and wrapping
    it in one made every ligand batch refuse with "unknown sequence family".
    """
    return ComponentRecord(
        ids=Multiplicity([entity_value]),
        representation=ByNotation(smiles),
    )


# Extendable record builder table — add new input types here.
BATCH_RECORD_BUILDERS = {
    "protein": _protein_record,
    "dna": _dna_record,
    "ligand": _ligand_record,
}


#: Longest derived key base, leaving room for a ``-<n>`` disambiguation
#: suffix inside ``naming.MAX_SLUG_LENGTH``.
_MAX_KEY_BASE = 54


def _name_key(name: str, index: int, key_prefix: str) -> str:
    """``name`` as a path-safe key base, or the positional fallback.

    ``output.naming.slug`` is the one authority for a filesystem-safe
    token, so a key derived here is exactly what the output planner will
    accept. A name with no usable characters at all falls back to the
    entry's position (``ligand-01``), never to a silently empty key.
    """
    from configbuilder.output.naming import NameError, slug

    try:
        return slug(name, max_length=_MAX_KEY_BASE)
    except NameError:
        return "%s-%02d" % (key_prefix, index)


def _unique_key(base: str, used, key_prefix: str, index: int) -> str:
    """``base``, suffixed deterministically until it is unused in ``used``.

    Two entries that name the same molecule both survive: the second gets
    ``-2``, the third ``-3``. The suffix is appended in file order, so the
    same file always produces the same keys and file names.
    """
    candidate = base or "%s-%02d" % (key_prefix, index)
    if candidate not in used:
        used.add(candidate)
        return candidate
    suffix = 2
    while True:
        candidate = "%s-%d" % (base.rstrip("-")[:_MAX_KEY_BASE], suffix)
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix += 1


def ligand_specs_for_entries(entries, registry: IdentityRegistry, key_prefix: str = "ligand"):
    """One independent spec per ``(line_number, name, smiles)`` entry.

    This is ``persistence.read_smiles_file``'s shape, so the documented
    ``name SMILES`` format is honoured end to end: the name becomes the
    spec's key (slugged) and the generation summary's label. The record
    itself is the same ``ByNotation`` component the single-entity path
    builds; the name is never written into the AF3 document, which has no
    field for it.

    All-or-nothing: an invalid entry or a duplicate SMILES refuses the
    whole batch, every offending line named, and no spec is returned.
    """
    entries = tuple(entries)
    if not entries:
        raise BatchError("the ligand file contains no entries")

    seen = set()
    duplicates = []
    for _line_number, _name, smiles in entries:
        key = smiles.strip()
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        raise BatchError(
            "the file contains duplicate ligand entries: %s"
            % ", ".join("%s..." % value[:12] for value in duplicates)
        )

    failures = []
    specs = []
    used = set()
    for index, (line_number, name, smiles) in enumerate(entries, start=1):
        try:
            entity = registry.allocate(owner="batch_variant")
            record = _ligand_record(entity.value, smiles.strip())
        except (ModelError, SequenceTextError) as error:
            failures.append("line %d: %s" % (line_number, error))
            continue
        key = _unique_key(_name_key(name, index, key_prefix), used, key_prefix, index)
        label = name.strip() or "%s %d" % (key_prefix, index)
        specs.append(
            VariantSpec(key=key, label=label, edits=(AddRecord(record),))
        )
    if failures:
        raise BatchError(
            "%d of %d ligand entries are invalid:\n  %s"
            % (len(failures), len(entries), "\n  ".join(failures))
        )
    return tuple(specs)


def batch_specs_for_sequences(entries, registry: IdentityRegistry, family: str = "protein", key_prefix: str = "batch"):
    """Turn cleaned sequence entries into independent variant specs.

    ``entries`` is a sequence of ``(line_number, text)`` pairs;
    ``registry`` is a **clone** of the base registry used only to
    allocate this batch's identifiers. ``family`` is the entity family
    ("protein", "dna", or "ligand"). Returns the tuple of
    ``VariantSpec`` (each with exactly one ``AddRecord`` edit); raises
    ``BatchError`` when the batch as a whole is unusable.

    Naming: keys are ``<prefix>_NN`` and labels ``<prefix> NN`` —
    two-digit, deterministic, ordered by input position. No sequence
    text ever enters a name or a filename.
    
    Each variant is an independent ``base + AddRecord`` spec, identical
    in kind to a hand-created variant. All variants start from the same
    base configuration and are generated in parallel, never sequentially.

    Ligand batches keep their names: this function's ``(line, text)``
    shape has none, so ligand callers use
    :func:`ligand_specs_for_entries` instead (a ligand entry is identified
    by the name the user gave it, not by its position).
    """
    entries = tuple(entries)
    if not entries:
        raise BatchError("the sequence file contains no usable sequences")

    builder = BATCH_RECORD_BUILDERS.get(family)
    if builder is None:
        raise BatchError("no record builder for family %r" % family)

    seen = set()
    duplicates = []
    for _, text in entries:
        # For ligands, we check the SMILES; for sequences, we check the text.
        key = text if family == "ligand" else text.strip().upper()
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        raise BatchError(                "the file contains duplicate %s sequences: %s"
                % (family, ", ".join("%s..." % v[:12] for v in duplicates))
        )

    failures = []
    specs = []
    for index, (line_number, text) in enumerate(entries, start=1):
        try:
            entity = registry.allocate(owner="batch_variant")
            record = builder(entity.value, text.strip())
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
            "%d of %d %s sequences are invalid:\n  %s"
            % (len(failures), len(entries), family, "\n  ".join(failures))
        )
    return tuple(specs)
