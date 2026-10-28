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

Supports multiple input types, named by :data:`INPUT_KINDS`:
- Protein sequences (one per line)
- DNA sequences (one per line)
- RNA sequences (one per line)
- Ligand SMILES strings (``name SMILES`` or a bare SMILES)
- Ligand CCD component codes (one ligand per line, one or more components)

Each input type gets its own record builder, and the same spec
architecture is used for all — a batch entry is the same ``base +
AddRecord`` construction a hand-made change is, and it flows through the
same validation and generation pipeline. :func:`specs_for_entries` is the
single place a kind becomes a builder, so a front end that offers a kind
cannot reach a construction that disagrees with the service.

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
    ByCode,
    ByNotation,
    ComponentCode,
    ComponentRecord,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    ModelError,
    SequenceText,
    SequenceTextError,
    split_component_codes,
)
from configbuilder.validation.smiles import notation_problem
from configbuilder.variants import AddRecord, VariantSpec

__all__ = [
    "BatchError",
    "batch_specs_for_sequences",
    "INPUT_KINDS",
    "SEQUENCE_FAMILIES",
    "ligand_code_specs_for_entries",
    "ligand_specs_for_entries",
    "sequence_family_for",
    "specs_for_entries",
    "BATCH_RECORD_BUILDERS",
]


#: What a file of entries can be. One token per kind, because *the user says
#: which kind they are loading*: the content of an arbitrary ``.txt`` file does
#: not identify an entity type (``MVT``/``MVY`` are protein sequences and also
#: look like words; ``ATP`` is a CCD code and also looks like a SMILES molecule
#: to nothing in particular). The label a user reads lives in the UI's string
#: registry; this tuple is the application's vocabulary and every front end
#: offers exactly these, so neither can invent a kind the services cannot
#: build.
INPUT_KINDS = (
    "protein-sequence",
    "dna-sequence",
    "rna-sequence",
    "ligand-smiles",
    "ligand-ccd",
)

#: The entity family each sequence kind builds. A sequence kind's record comes
#: from the same builder table as everything else; this mapping is the only
#: thing that turns "the user chose DNA" into ``FamilyCRecord``.
SEQUENCE_FAMILIES = {
    "protein-sequence": "protein",
    "dna-sequence": "dna",
    "rna-sequence": "rna",
}


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


def _rna_record(entity_value: str, text: str):
    """The record one RNA sequence becomes.

    ``FamilyBRecord`` is the model's RNA record — the same one the console and
    the desktop forms build for a single RNA entity, so a batch RNA entry and
    a hand-added one cannot differ in representation or serialisation.
    """
    return FamilyBRecord(
        ids=Multiplicity([entity_value]), sequence=SequenceText(text, "rna")
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


def _code_record(entity_value: str, codes):
    """The record one CCD-coded ligand becomes: ``ByCode``, never ``ByNotation``.

    A component code is an identifier (matched against CCD), so it is stored
    as ``ccdCodes`` in the document. Writing it as a SMILES string is the
    defect the audit found in the ligand-file workflow, and it is not
    repeated here: this builder cannot produce a notation.
    """
    return ComponentRecord(
        ids=Multiplicity([entity_value]), representation=ByCode(tuple(codes))
    )


# Extendable record builder table — add new input types here.
#
# One entry per entity family a file can carry. RNA is here for the same
# reason the other two are: the model has ``FamilyBRecord``, the serializer
# writes ``rna``, and a file of RNA sequences is the same "one independent
# configuration per entry" problem. A family absent from this table is a
# family no batch can build, and the refusal says so by name.
BATCH_RECORD_BUILDERS = {
    "protein": _protein_record,
    "dna": _dna_record,
    "rna": _rna_record,
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

    All-or-nothing: an entry whose notation is not SMILES, a value the model
    refuses, or a duplicate SMILES refuses the whole batch, every offending
    line named, and no spec is returned.

    The notation check is ``validation.smiles``' grammar: the same checker the
    validation rule uses, so a file entry and a hand-typed ligand are judged by
    one implementation. It refuses notation that is not SMILES (a component
    code, a protein sequence, a sentence) rather than storing it as text and
    serialising a document AF3 will refuse — what it does *not* claim is
    chemistry.
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
    refused_texts = []
    specs = []
    used = set()
    for index, (line_number, name, smiles) in enumerate(entries, start=1):
        notation = smiles.strip()
        problem = notation_problem(notation)
        if problem is not None:
            failures.append(
                "line %d: %r is not SMILES notation (%s)"
                % (line_number, notation, problem)
            )
            refused_texts.append(notation)
            continue
        try:
            entity = registry.allocate(owner="batch_variant")
            record = _ligand_record(entity.value, notation)
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
            "%d of %d ligand entries are invalid:\n  %s%s"
            % (
                len(failures),
                len(entries),
                "\n  ".join(failures),
                _sequence_hint(refused_texts),
            )
        )
    return tuple(specs)


#: How each sequence family is named to a user in a refusal. The model's
#: family token is lowercase; ``DNA``/``RNA`` are written the way AF3's own
#: documentation writes them.
_SEQUENCE_WORDS = {"protein": "protein", "dna": "DNA", "rna": "RNA"}


def _fits_family(text: str, family: str) -> bool:
    """Whether ``text`` is a valid sequence of ``family``, by the model's own
    alphabet rule — no second alphabet table lives in this module."""
    try:
        SequenceText(text, family)
    except SequenceTextError:
        return False
    return True


def sequence_family_for(texts):
    """The sequence family every text could be, or ``None``.

    Used only to *advise* a user who typed sequences into the SMILES kind: it
    never reinterprets an entry. The order matters, because a nucleotide string
    is also a valid protein string (the protein alphabet is every capital
    letter), so DNA and RNA are tested before protein and the most specific
    answer wins. Nothing here decides what will be built — the user chose the
    kind, and only the chosen kind builds anything.
    """
    texts = tuple(text.strip() for text in texts)
    if not texts or not all(texts):
        return None
    for family in ("dna", "rna", "protein"):
        if all(_fits_family(text, family) for text in texts):
            return family
    return None


def _sequence_hint(refused_texts) -> str:
    """The advice appended to a SMILES refusal, when the text *is* a sequence.

    A user who loads ``proteins.txt`` through the SMILES kind gets "not SMILES"
    for every line, which is true but not actionable. If every refused entry is
    a valid sequence of one family, the refusal names the kind that would read
    it. It never converts anything: the run still refuses, and the fix is the
    user's explicit choice of kind.

    A **protein** hint also names the CCD kind, because the two are genuinely
    indistinguishable from the text alone: the protein alphabet is every
    capital letter, so ``ATP`` and ``ZN`` are valid protein sequences as well
    as component codes. Saying "these look like protein sequences" over a code
    list would be a confident wrong answer, and a user following it would get a
    protein entity where a ligand was meant. Nucleotide strings are not
    plausible codes, so DNA/RNA hints are stated plainly.
    """
    family = sequence_family_for(refused_texts)
    if family is None:
        return ""
    word = _SEQUENCE_WORDS[family]
    if family == "protein":
        return (
            "\nThese entries may be protein sequences rather than SMILES. "
            "Select the protein sequence input type to process them as protein "
            "entities; if they are CCD codes, select the CCD code input type."
        )
    return (
        "\nThese entries look like %s sequences, not SMILES. "
        "Choose the %s sequence input type to process them as %s entities."
        % (word, word, word)
    )


def ligand_code_specs_for_entries(entries, registry: IdentityRegistry, key_prefix: str = "ligand"):
    """One independent spec per ``(line_number, text)`` CCD code entry.

    A code file is the *identifier* form of a ligand list, so each entry
    becomes a ``ComponentRecord`` whose representation is ``ByCode`` — the
    document gets ``ccdCodes``, never ``smiles``. A line's tokens are the
    components of **one** ligand (``NAG NAG BMA MAN MAN`` is one glycan), split
    by the same ``model.split_component_codes`` the entity form uses, so the
    two routes cannot disagree about a component boundary.

    Naming: the key is derived from the codes themselves (slugged, in order),
    which makes a rerun write the same file names. Duplicate code lists are
    refused like duplicate SMILES, and the key-collision suffix behaves the
    same way. All-or-nothing: one bad code refuses the whole file, every
    offending line named.
    """
    entries = tuple(entries)
    if not entries:
        raise BatchError("the CCD code file contains no entries")

    seen = set()
    duplicates = []
    for _line_number, text in entries:
        try:
            signature = tuple(code.value for code in _codes_of(text))
        except ModelError:
            continue  # reported per line below; not a duplicate question
        if signature in seen and signature not in duplicates:
            duplicates.append(signature)
        seen.add(signature)
    if duplicates:
        raise BatchError(
            "the file contains duplicate component codes: %s"
            % ", ".join("-".join(signature) for signature in duplicates)
        )

    failures = []
    specs = []
    used = set()
    for index, (line_number, text) in enumerate(entries, start=1):
        try:
            codes = _codes_of(text)
            entity = registry.allocate(owner="batch_variant")
            record = _code_record(entity.value, codes)
        except (ModelError, SequenceTextError) as error:
            failures.append("line %d: %s" % (line_number, error))
            continue
        written = "-".join(code.value for code in codes)
        key = _unique_key(_name_key(written, index, key_prefix), used, key_prefix, index)
        specs.append(
            VariantSpec(key=key, label=written, edits=(AddRecord(record),))
        )
    if failures:
        raise BatchError(
            "%d of %d CCD code entries are invalid:\n  %s"
            % (len(failures), len(entries), "\n  ".join(failures))
        )
    return tuple(specs)


def _codes_of(text: str):
    """The validated component codes of one line (raises the model's error)."""
    tokens = split_component_codes(text)
    if not tokens:
        raise ModelError("no component code on this line")
    return tuple(ComponentCode(token) for token in tokens)


def specs_for_entries(
    entries, registry: IdentityRegistry, kind: str, sequence_record_factory=None
):
    """The specs for one file's entries, by the kind the user chose.

    The single mapping from an input kind to its construction. Every caller —
    the preview, the console, the desktop page — goes through here, so a kind
    can never mean one thing in a preview and another in the write.

    Raises ``BatchError`` for an unknown kind: advertising a kind the services
    cannot build is a programming error, and it is refused loudly rather than
    silently treated as SMILES.
    """
    if kind == "ligand-smiles":
        return ligand_specs_for_entries(entries, registry)
    if kind == "ligand-ccd":
        return ligand_code_specs_for_entries(entries, registry)
    family = SEQUENCE_FAMILIES.get(kind)
    if family is None:
        raise BatchError("unknown input type %r" % (kind,))
    return batch_specs_for_sequences(
        entries,
        registry,
        family=family,
        record_factory=sequence_record_factory,
    )


def batch_specs_for_sequences(
    entries,
    registry: IdentityRegistry,
    family: str = "protein",
    key_prefix: str = "batch",
    record_factory=None,
):
    """Turn cleaned sequence entries into independent variant specs.

    ``entries`` is a sequence of ``(line_number, text)`` pairs;
    ``registry`` is a **clone** of the base registry used only to
    allocate this batch's identifiers. ``family`` is the entity family
    ("protein", "dna", "rna" or "ligand"). Returns the tuple of
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
        raise BatchError(
            "the file contains duplicate %s sequences: %s"
            % (family, ", ".join("%s..." % v[:12] for v in duplicates))
        )

    failures = []
    specs = []
    for index, (line_number, text) in enumerate(entries, start=1):
        try:
            if record_factory is None:
                entity = registry.allocate(owner="batch_variant")
                records = (builder(entity.value, text.strip()),)
            else:
                # Family-specific entity construction belongs to the shared
                # application service. DNA uses its established duplex rule,
                # so a single file record may contribute its two linked strands.
                records = tuple(record_factory(registry, text.strip()))
                if not records:
                    raise BatchError("no entity records were built for this line")
        except (BatchError, ModelError, SequenceTextError) as error:
            failures.append("line %d: %s" % (line_number, error))
            continue
        spec = VariantSpec(
            key="%s_%02d" % (key_prefix, index),
            label="%s %d" % (key_prefix, index),
            edits=tuple(AddRecord(record) for record in records),
        )
        specs.append(spec)
    if failures:
        raise BatchError(
            "%d of %d %s sequences are invalid:\n  %s"
            % (len(failures), len(entries), family, "\n  ".join(failures))
        )
    return tuple(specs)
