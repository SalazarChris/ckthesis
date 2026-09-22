"""Record, seed, and linkage editing (IMPLEMENTATION_PLAN.md §15):
``ConfigurationService``.

Every mutation returns a ``MutationOutput``; user-caused problems come
back as failure reasons and findings, never exceptions. Records are
identified by their primary ``EntityId`` resolved through the
configuration's registry — never list position (plan §8.1.1, §12.1).
"""

from __future__ import annotations

from configbuilder.app.results import FailureReason, MutationOutput
from configbuilder.identity import (
    DuplicateIdError,
    EntityId,
    IdentityError,
    IdentityRegistry,
    Multiplicity,
)
from configbuilder.model import (
    AlignmentAutomatic,
    AlignmentBoth,
    AlignmentFree,
    AlignmentPairedOnly,
    AlignmentUnpairedOnly,
    ByCode,
    ByNotation,
    ComponentCode,
    ComponentRecord,
    ConfigurationError,
    Dialect,
    Explicit,
    External,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    FormatTarget,
    IndexPair,
    Inline,
    LinkEndpoint,
    Linkage,
    ModificationRecord,
    ModelError,
    PathSpec,
    Pinned,
    Position,
    ReferenceRecord,
    ResidueRef,
    SearchAllowed,
    SequenceText,
    SingleAutomatic,
    SingleFree,
    SingleProvided,
)

__all__ = ["ConfigurationService", "ReferenceInput"]

_FAMILY_TYPES = (FamilyARecord, FamilyBRecord, FamilyCRecord, ComponentRecord)


class ReferenceInput:
    """One structural-template reference, as the wizard supplies it:
    a source (inline text or an external path) and 0-based query/template
    index pairs."""

    __slots__ = ("inline_text", "external_path", "pairs")

    def __init__(self, inline_text=None, external_path=None, pairs=()) -> None:
        self.inline_text = inline_text
        self.external_path = external_path
        self.pairs = tuple(pairs)


class ConfigurationService:
    """Mutates the open project's configuration through validated
    constructors and identity-owned identifiers."""

    def __init__(self, projects, validate=None) -> None:
        self._projects = projects
        self._validate = validate

    # -- helpers ---------------------------------------------------------------

    def _project(self):
        return self._projects._require_project()

    def _configuration(self):
        project = self._project()
        return project.configuration if project is not None else None

    def _commit(self, configuration) -> MutationOutput:
        self._projects._replace_project(self._project().with_configuration(configuration))
        return self._findings_output()

    def _findings_output(self) -> MutationOutput:
        project = self._project()
        if self._validate is None or project is None:
            return MutationOutput(ok=True)
        return MutationOutput(ok=True, findings=self._validate(project.configuration).findings)

    def _not_open(self) -> MutationOutput:
        return MutationOutput(
            ok=False,
            failure_reason=FailureReason.NOT_OPEN,
            message="no project is open",
        )

    def _unknown_record(self, record_key) -> MutationOutput:
        return MutationOutput(
            ok=False,
            failure_reason=FailureReason.UNKNOWN_RECORD,
            message="no record is identified by %r; pick a record the registry knows" % (record_key,),
        )

    def _refused(self, message: str) -> MutationOutput:
        return MutationOutput(ok=False, failure_reason=FailureReason.NO_PATH, message=message)

    def _record_for(self, configuration, primary: EntityId):
        """The record whose primary identifier is ``primary``, or None."""
        try:
            multiplicity = configuration.identity.multiplicity_of(primary)
        except IdentityError:
            return None
        wanted = tuple(entity.value for entity in multiplicity)
        for record in configuration.records:
            if tuple(entity.value for entity in record.ids) == wanted:
                return record
        return None

    def _key(self, record_key):
        try:
            return EntityId(record_key), None
        except ValueError as error:
            return None, self._refused(str(error))

    # -- job details (§15 set_name; spec §15 job descriptions) -------------------

    def set_name(self, name: str) -> MutationOutput:
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        metadata = configuration.metadata
        return self._commit(
            configuration.with_metadata(metadata.__class__(name, metadata.description))
        )

    def set_job_description(self, description) -> MutationOutput:
        """Set or clear the job-level description (spec §15 naming factor).

        Pass a string to set it, ``None`` to clear it to ``Unset``; an
        empty string means explicitly empty (``ExplicitEmpty``) — the
        three presence states, never a bare contract distinction."""
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        if description is None:
            from configbuilder.model import Unset

            value = Unset()
        elif isinstance(description, str):
            from configbuilder.model import ExplicitEmpty, Present

            value = Present(description) if description else ExplicitEmpty()
        else:
            value = description  # already a Presence value
        return self._commit(configuration.with_job_description(value))

    def set_seeds(self, seeds) -> MutationOutput:
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        # A wizard field arrives as raw text ("1 2 3"); lists/tuples are
        # the programmatic form. Parse text here so the caller's answer
        # shape is the service's problem, not the user's (plan §16).
        if isinstance(seeds, str):
            parts = seeds.replace(",", " ").split()
            try:
                seeds = [int(part) for part in parts]
            except ValueError:
                return self._refused(
                    "seeds must be whole numbers separated by spaces or commas"
                )
        if isinstance(seeds, (int, tuple)):
            seeds = list(seeds) if isinstance(seeds, tuple) else [seeds]
        try:
            seed_set = configuration.seeds.__class__(list(seeds))
        except (ValueError, TypeError, ModelError) as error:
            return self._refused(str(error))
        return self._commit(configuration.with_seeds(seed_set))

    # -- records -----------------------------------------------------------------

    def add_record(self, family: str, sequence: str = "", representation="", copies: int = 1, description=None):
        """Add a record; identity allocates its identifiers (plan §8.1).

        ``family`` is ``"protein"`` / ``"rna"`` / ``"dna"`` / ``"ligand"``.
        ``copies`` > 1 reserves an ordered copy multiplicity (plan §8.2).

        A ``dna`` entry is a duplex (DNA duplex feature): the caller
        supplies one 5'-to-3' strand and this service commits **two**
        records — the given strand and its reverse complement — each with
        its own registry-allocated identifier. The complement is built
        here at the domain boundary, never in a front end.
        """
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        if family == "ligand":
            if not representation:
                return self._refused(
                    "a ligand record needs a representation: CCD code(s) or a SMILES notation"
                )
        elif family not in ("protein", "rna", "dna"):
            return self._refused("unknown family %r; use protein, rna, dna, or ligand" % (family,))
        elif not sequence:
            return self._refused("a %s record needs a sequence" % family)
        if isinstance(copies, str):  # a wizard field arrives as text
            try:
                copies = int(copies.strip() or "1")
            except ValueError:
                return self._refused("copies must be a whole number of at least 1")
        if not isinstance(copies, int) or copies < 1:
            return self._refused("copies must be a whole number of at least 1")

        if family == "dna" and copies != 1:
            return self._refused(
                "a DNA record is a duplex: the complementary strand is constructed "
                "automatically, so copies does not apply"
            )
        registry = configuration.identity.clone()
        records, failure = self._build_records(family, sequence, representation, copies, registry)
        if failure is not None:
            return failure
        if description is not None:
            records = tuple(record.with_description(self._presence(description)) for record in records)
        return self._commit(
            configuration.with_records(configuration.records + records).with_identity(registry)
        )

    def _build_records(self, family, sequence, representation, copies, registry: IdentityRegistry):
        """Build the record(s) with registry-allocated identifiers.

        Returns ``(records, None)`` or ``((), MutationOutput)``. Every
        family yields one record except DNA, which yields the duplex: the
        supplied strand plus its reverse complement, two distinct
        identifiers allocated back-to-back so the complement always sorts
        immediately after its partner. Both strands are conventional
        5'-to-3' sequences (DNA duplex feature); the direction lives in
        ``FamilyCRecord.complement`` / ``reverse_complement``, not here.
        """
        owner = "record"
        try:
            strands = 2 if family == "dna" else copies
            allocated = [registry.allocate(owner=owner) for _ in range(strands)]
            if family == "ligand":
                representation_value = self._ligand_representation(representation)
                if isinstance(representation_value, MutationOutput):
                    return (), representation_value
                ids = Multiplicity([entity.value for entity in allocated])
                return (ComponentRecord(ids=ids, representation=representation_value),), None
            text = SequenceText(sequence, family)
            if family == "protein":
                ids = Multiplicity([allocated[0].value])
                return (FamilyARecord(ids=ids, sequence=text),), None
            if family == "rna":
                ids = Multiplicity([allocated[0].value])
                return (FamilyBRecord(ids=ids, sequence=text),), None
            given = FamilyCRecord(ids=Multiplicity([allocated[0].value]), sequence=text)
            partner = given.complement()
            partner = FamilyCRecord(
                ids=Multiplicity([allocated[1].value]),
                sequence=partner.sequence,
                modifications=partner.modifications,
                description=partner.description,
            )
            return (given, partner), None
        except (ModelError, IdentityError, ValueError) as error:
            return (), self._refused(str(error))

    def _presence(self, description):
        """Normalize text into the description's Presence vocabulary —
        the same discipline as ``set_job_description``: empty text is
        *explicitly empty*, non-empty is *present*, non-strings pass
        through as an already-built Presence value."""
        if isinstance(description, str):
            from configbuilder.model import ExplicitEmpty, Present

            return Present(description) if description else ExplicitEmpty()
        return description

    def _ligand_representation(self, representation: str):
        text = representation.strip()
        if not text:
            return self._refused("a ligand representation cannot be empty")
        if " " in text or "," in text or ";" in text:
            # Multi-code entry: every whitespace/comma-separated token is a CCD code.
            try:
                codes = tuple(ComponentCode(token) for token in text.replace(",", " ").split())
            except ValueError as error:
                return self._refused(str(error))
            return ByCode(codes)
        try:
            code = ComponentCode(text)
        except ValueError:
            try:
                return ByNotation(text)
            except ValueError as error:
                return self._refused(str(error))
        return ByCode((code,))

    def update_record(self, record_key: str, sequence=None, description=None) -> MutationOutput:
        """Change a record's sequence and/or description, identified
        through the registry — never list position."""
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        primary, failure = self._key(record_key)
        if failure is not None:
            return failure
        record = self._record_for(configuration, primary)
        if record is None or not isinstance(record, _FAMILY_TYPES):
            return self._unknown_record(record_key)
        updated = record
        if sequence is not None:
            family = "protein"
            if isinstance(record, FamilyBRecord):
                family = "rna"
            elif isinstance(record, FamilyCRecord):
                family = "dna"
            try:
                updated = updated.with_sequence(SequenceText(sequence, family))
            except ValueError as error:
                return self._refused(str(error))
        if description is not None:
            updated = updated.with_description(self._presence(description))
        records = tuple(updated if existing is record else existing for existing in configuration.records)
        return self._commit(configuration.with_records(records))

    def remove_record(self, record_key: str) -> MutationOutput:
        """Remove a record and release its identifiers (identity-owned,
        plan §8.3). Linkages referencing the removed copies go with it."""
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        primary, failure = self._key(record_key)
        if failure is not None:
            return failure
        record = self._record_for(configuration, primary)
        if record is None:
            return self._unknown_record(record_key)
        released = tuple(configuration.identity.multiplicity_of(primary))
        released_values = {entity.value for entity in released}
        records = tuple(r for r in configuration.records if r is not record)
        linkages = tuple(
            linkage
            for linkage in configuration.linkages
            if linkage.a.entity.value not in released_values
            and linkage.b.entity.value not in released_values
        )
        registry = configuration.identity.clone()
        for entity in released:
            registry.release(entity)
        return self._commit(
            configuration.with_records(records).with_linkages(linkages).with_identity(registry)
        )

    # -- modifications (§15 add_modification) --------------------------------------

    def add_modification(self, record_key: str, code: str, position: int) -> MutationOutput:
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        primary, failure = self._key(record_key)
        if failure is not None:
            return failure
        record = self._record_for(configuration, primary)
        if record is None or not hasattr(record, "modifications"):
            return self._unknown_record(record_key)
        try:
            modification = ModificationRecord(ComponentCode(code), Position(int(position)))
        except (ValueError, TypeError) as error:
            return self._refused(str(error))
        updated = record.with_modifications(record.modifications + (modification,))
        records = tuple(updated if existing is record else existing for existing in configuration.records)
        return self._commit(configuration.with_records(records))

    def remove_modification(self, record_key: str, index: int) -> MutationOutput:
        """Remove one modification from a record by its position in the
        record's modification list; confirmation naming what is removed
        is the caller's job (plan §16.3: delete always confirms)."""
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        primary, failure = self._key(record_key)
        if failure is not None:
            return failure
        record = self._record_for(configuration, primary)
        if record is None or not hasattr(record, "modifications"):
            return self._unknown_record(record_key)
        modifications = tuple(record.modifications)
        if index < 0 or index >= len(modifications):
            return self._refused("no modification numbered %d on record %s" % (index + 1, record_key))
        updated = record.with_modifications(
            modifications[:index] + modifications[index + 1 :]
        )
        records = tuple(updated if existing is record else existing for existing in configuration.records)
        return self._commit(configuration.with_records(records))

    def set_representation(self, record_key: str, codes=None, notation=None) -> MutationOutput:
        """Set a component record's representation: CCD code(s) or a SMILES
        notation — exactly one, as vocabulary-level data (plan §16.4)."""
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        primary, failure = self._key(record_key)
        if failure is not None:
            return failure
        record = self._record_for(configuration, primary)
        if record is None or not hasattr(record, "representation"):
            return self._unknown_record(record_key)
        try:
            if codes is not None and notation is not None:
                return self._refused("choose codes or a notation, not both")
            if codes is not None:
                if isinstance(codes, str):
                    representation = ByCode((ComponentCode(codes),))
                else:
                    representation = ByCode(tuple(ComponentCode(code) for code in codes))
            elif notation is not None:
                representation = ByNotation(notation)
            else:
                return self._refused("a representation needs codes or a notation")
        except (ValueError, TypeError) as error:
            return self._refused(str(error))
        updated = record.with_representation(representation)
        records = tuple(updated if existing is record else existing for existing in configuration.records)
        return self._commit(configuration.with_records(records))

    # -- alignments and references (§15 set_alignment / set_references) ---------------

    def set_alignment(self, record_key: str, mode: str, inline_text=None, external_path=None) -> MutationOutput:
        """Set a polymer record's alignment mode.

        Protein records accept ``automatic`` / ``free`` / ``unpaired`` /
        ``paired`` / ``both``; RNA records accept ``automatic`` / ``free`` /
        ``provided``. Source-carrying modes need exactly one of
        ``inline_text`` / ``external_path``.
        """
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        primary, failure = self._key(record_key)
        if failure is not None:
            return failure
        record = self._record_for(configuration, primary)
        if record is None or not isinstance(record, (FamilyARecord, FamilyBRecord)):
            return self._unknown_record(record_key)
        source, failure = self._source(inline_text, external_path)
        if failure is not None:
            return failure
        try:
            if isinstance(record, FamilyARecord):
                alignment = self._protein_alignment(mode, source)
            else:
                alignment = self._rna_alignment(mode, source)
        except ValueError as error:
            return self._refused(str(error))
        if alignment is None:
            return self._refused(
                "unknown alignment mode %r for a %s record"
                % (mode, "protein" if isinstance(record, FamilyARecord) else "RNA")
            )
        updated = record.with_alignment(alignment)
        records = tuple(updated if existing is record else existing for existing in configuration.records)
        return self._commit(configuration.with_records(records))

    def _protein_alignment(self, mode: str, source):
        if mode == "automatic":
            return AlignmentAutomatic()
        if mode == "free":
            return AlignmentFree()
        if mode in ("unpaired", "unpaired_only"):
            return AlignmentUnpairedOnly(self._need(source, mode))
        if mode in ("paired", "paired_only"):
            return AlignmentPairedOnly(self._need(source, mode))
        if mode == "both":
            return AlignmentBoth(self._need(source, mode))
        return None

    def _rna_alignment(self, mode: str, source):
        if mode == "automatic":
            return SingleAutomatic()
        if mode == "free":
            return SingleFree()
        if mode == "provided":
            return SingleProvided(self._need(source, mode))
        return None

    def _need(self, source, mode: str):
        if source is None:
            raise ValueError("alignment mode %r needs a source (inline text or an external path)" % mode)
        return source

    def _source(self, inline_text, external_path):
        if bool(inline_text) == bool(external_path):
            message = (
                "choose exactly one of inline text or an external path"
                if inline_text
                else "this choice needs exactly one of inline text or an external path"
            )
            return None, self._refused(message)
        if inline_text:
            return Inline(inline_text), None
        return External(PathSpec(external_path)), None

    def set_references(self, record_key: str, references=None) -> MutationOutput:
        """Set a protein record's structural references.

        No argument: template search stays allowed (templates omitted).
        ``references=()``: explicitly template-free. A sequence of
        ``ReferenceInput``: an explicit reference list.
        """
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        primary, failure = self._key(record_key)
        if failure is not None:
            return failure
        record = self._record_for(configuration, primary)
        if record is None or not isinstance(record, FamilyARecord):
            return self._unknown_record(record_key)
        if references is None:
            reference_set = SearchAllowed()
        else:
            built = []
            for entry in references:
                source, failure = self._source(
                    getattr(entry, "inline_text", None), getattr(entry, "external_path", None)
                )
                if failure is not None:
                    return failure
                try:
                    pairs = tuple(IndexPair(int(q), int(t)) for q, t in entry.pairs)
                    built.append(ReferenceRecord(source, pairs))
                except (ValueError, TypeError) as error:
                    return self._refused(str(error))
            reference_set = Explicit(tuple(built))
        updated = record.with_references(reference_set)
        records = tuple(updated if existing is record else existing for existing in configuration.records)
        return self._commit(configuration.with_records(records))

    # -- components (§15 set_component_definition) ----------------------------------

    def set_component_definition(self, inline_text=None, external_path=None) -> MutationOutput:
        """Define the component chemistry inline or as an external file."""
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        source, failure = self._source(inline_text, external_path)
        if failure is not None:
            return failure
        return self._commit(configuration.with_component_definition(source))

    # -- linkages (§15 add_linkage / remove_linkage) ---------------------------------

    def add_linkage(self, a_key: str, a_residue: int, a_atom: str, b_key: str, b_residue: int, b_atom: str) -> MutationOutput:
        """Bond two addressable endpoints; both record keys must resolve
        through the registry (identity is the sole resolution authority)."""
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        registry = configuration.identity
        try:
            endpoint_a = LinkEndpoint(registry.resolve_strict(EntityId(a_key)), ResidueRef(int(a_residue)), a_atom)
            endpoint_b = LinkEndpoint(registry.resolve_strict(EntityId(b_key)), ResidueRef(int(b_residue)), b_atom)
            linkage = Linkage(endpoint_a, endpoint_b)
        except (IdentityError, ValueError, TypeError) as error:
            return MutationOutput(ok=False, failure_reason=FailureReason.UNKNOWN_RECORD, message=str(error))
        return self._commit(configuration.with_linkages(configuration.linkages + (linkage,)))

    def remove_linkage(self, index: int) -> MutationOutput:
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        if not isinstance(index, int) or not 0 <= index < len(configuration.linkages):
            return self._refused(
                "linkage index %r does not exist (%d linkages present)"
                % (index, len(configuration.linkages))
            )
        linkages = tuple(l for i, l in enumerate(configuration.linkages) if i != index)
        return self._commit(configuration.with_linkages(linkages))

    # -- format target (§15 set_format_target) ----------------------------------------

    def set_format_target(self, version=None, dialect="STANDALONE_AF3", evidence=None) -> MutationOutput:
        """Pin a format version with its human-supplied provenance.

        ``evidence`` cites the observation that justifies the pin (e.g. a
        ``PIN-nnn`` record the operator verified in the deployment log).
        The citation travels in the model; no runtime code reads any
        document to obtain it. An omitted or empty ``evidence`` records
        that no citation has been supplied yet (R-VER-002 reports it).
        ``version=None`` keeps the selection Unverified.
        """
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        try:
            selection = (
                Pinned(int(version), evidence=evidence or "")
                if version is not None
                else None
            )
            # ``dialect`` arrives as the member name ("STANDALONE_AF3");
            # ``Dialect``'s constructor takes the member *value*.
            member_value = getattr(Dialect, dialect, None) if isinstance(dialect, str) else None
            resolved = Dialect(member_value if member_value is not None else dialect)
            target = FormatTarget(version_selection=selection, dialect=resolved)
        except (ValueError, TypeError, ConfigurationError) as error:
            return self._refused(str(error))
        return self._commit(configuration.with_format_target(target))

    def unset_format_target(self) -> MutationOutput:
        configuration = self._configuration()
        if configuration is None:
            return self._not_open()
        return self._commit(configuration.with_format_target(FormatTarget()))
