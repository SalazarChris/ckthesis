"""Variant spec editing (IMPLEMENTATION_PLAN.md §15): ``VariantService``.

``add_spec`` / ``update_spec`` / ``remove_spec`` / ``duplicate_spec``
maintain the project's spec list; ``preview`` expands a single spec
without committing it; ``expand`` materialises the whole set. Edit
failures (unknown record keys, identifier conflicts) come back as
failure reasons — never exceptions.
"""

from __future__ import annotations

from configbuilder.app.results import (
    ExpandOutput,
    FailureReason,
    FilePreview,
    MutationOutput,
)
from configbuilder.identity import EntityId, IdentityRegistry
from configbuilder.model import ModelError, SequenceText
from configbuilder.model.records import (
    ComponentRecord,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
)
from configbuilder.variants import (
    EditError,
    VariantSpec,
    VariantSpecError,
    describe_edit,
    expand,
)

__all__ = ["ChoiceError", "VariantChoice", "VariantService"]


class ChoiceError(Exception):
    """A UI-facing choice payload is unusable (bad table shape, unknown
    template route). User-caused, so it surfaces as a refusal — never an
    exception escaping into a front end."""


class VariantChoice:
    """One numbered choice in a UI table: label (human wording, may
    carry the record key for orientation), ``kind`` discriminator, and
    the value the front end passes back. Plain data — no behaviour."""

    __slots__ = ("label", "kind", "value")

    def __init__(self, label, kind, value=None):
        self.label = label
        self.kind = kind
        self.value = value


class VariantService:
    """Maintains the open project's variant specs."""

    def __init__(self, projects, configuration=None) -> None:
        self._projects = projects
        self._configuration = configuration

    # -- helpers ---------------------------------------------------------------

    def _specs(self):
        return self._projects._specs()

    def _not_open(self):
        return MutationOutput(ok=False, failure_reason=FailureReason.NOT_OPEN, message="no project is open")

    def _find(self, key: str):
        for spec in self._specs():
            if spec.key == key:
                return spec
        return None

    @staticmethod
    def _validate_spec_value(key: str, label: str, edits):
        try:
            return VariantSpec(key=key, label=label, edits=tuple(edits)), None
        except (VariantSpecError, EditError) as error:
            return None, MutationOutput(
                ok=False, failure_reason=FailureReason.NO_PATH, message=str(error)
            )

    # -- spec CRUD (§15) ----------------------------------------------------------

    def add_spec(self, key: str, label: str, edits=()) -> MutationOutput:
        project = self._projects._require_project()
        if project is None:
            return self._not_open()
        if self._find(key) is not None:
            return MutationOutput(
                ok=False,
                failure_reason=FailureReason.NO_PATH,
                message="a variant keyed %r already exists; keys are unique" % (key,),
            )
        spec, failure = self._validate_spec_value(key, label, edits)
        if failure is not None:
            return failure
        self._projects._with_specs(self._specs() + (spec,))
        return MutationOutput(ok=True)

    def update_spec(self, key: str, label=None, edits=None) -> MutationOutput:
        project = self._projects._require_project()
        if project is None:
            return self._not_open()
        existing = self._find(key)
        if existing is None:
            return MutationOutput(
                ok=False,
                failure_reason=FailureReason.UNKNOWN_RECORD,
                message="no variant keyed %r exists" % (key,),
            )
        new_label = existing.label if label is None else label
        new_edits = existing.edits if edits is None else tuple(edits)
        spec, failure = self._validate_spec_value(key, new_label, new_edits)
        if failure is not None:
            return failure
        self._projects._with_specs(
            tuple(spec if s.key == key else s for s in self._specs())
        )
        return MutationOutput(ok=True)

    def remove_spec(self, key: str) -> MutationOutput:
        project = self._projects._require_project()
        if project is None:
            return self._not_open()
        if self._find(key) is None:
            return MutationOutput(
                ok=False,
                failure_reason=FailureReason.UNKNOWN_RECORD,
                message="no variant keyed %r exists" % (key,),
            )
        self._projects._with_specs(tuple(s for s in self._specs() if s.key != key))
        return MutationOutput(ok=True)

    def add_spec_from_factor(
        self, key: str, factor: str, value, label: str = "", record_key=None
    ) -> MutationOutput:
        """The wizard's guided factor picker (plan §16.4): the user picks
        a factor and supplies a value; the builder writes the edits.

        Factors are the declared-change vocabulary of spec §15
        (``_FACTOR_BY_EDIT``'s targets). The edit objects are built here
        in ``app`` — ``ui`` never constructs variant vocabulary."""
        project = self._projects._require_project()
        if project is None:
            return self._not_open()
        try:
            edit, failure = self._factor_edit(project, factor, value, record_key)
            if failure is not None:
                return self._refuse(failure)
        except (EditError, VariantSpecError, ValueError, TypeError) as error:
            return self._refuse(str(error))
        from configbuilder.model import SequenceTextError

        try:
            return self.add_spec(key, label or key, (edit,))
        except SequenceTextError as error:
            return self._refuse(str(error))

    @staticmethod
    def _edit_class(name: str):
        from configbuilder import variants as _v

        return getattr(_v, name)

    @staticmethod
    def _sole_polymer_key(project):
        polymers = [
            record.ids.primary.value
            for record in project.configuration.records
            if hasattr(record, "sequence")
        ]
        return polymers[0] if len(polymers) == 1 else None

    @staticmethod
    def _family_of_key(project, key: str) -> str:
        """The family alphabet of the record identified by ``key``
        (protein/rna/dna), from the record's own type — the picker never
        guesses an alphabet from the text."""
        for record in project.configuration.records:
            if record.ids.primary.value == key:
                family = {
                    "FamilyARecord": "protein",
                    "FamilyBRecord": "rna",
                    "FamilyCRecord": "dna",
                }.get(type(record).__name__)
                if family:
                    return family
        raise EditError("no record is identified by %r" % key)

    def _refuse(self, message: str) -> MutationOutput:
        return MutationOutput(ok=False, failure_reason=FailureReason.NO_PATH, message=message)

    def duplicate_spec(self, key: str, new_key: str, new_label: str = "") -> MutationOutput:
        """Copy an existing spec under a fresh key."""
        project = self._projects._require_project()
        if project is None:
            return self._not_open()
        existing = self._find(key)
        if existing is None:
            return MutationOutput(
                ok=False,
                failure_reason=FailureReason.UNKNOWN_RECORD,
                message="no variant keyed %r exists" % (key,),
            )
        if self._find(new_key) is not None:
            return MutationOutput(
                ok=False,
                failure_reason=FailureReason.NO_PATH,
                message="a variant keyed %r already exists; keys are unique" % (new_key,),
            )
        label = new_label or ("%s (copy)" % existing.label)
        spec, failure = self._validate_spec_value(new_key, label, existing.edits)
        if failure is not None:
            return failure
        self._projects._with_specs(self._specs() + (spec,))
        return MutationOutput(ok=True)

    # -- expansion (§15 preview / expand) ---------------------------------------------

    def duplicate_with_edits(self, key: str, new_key: str, new_label: str = "", edits=()) -> MutationOutput:
        """Duplicate an existing variant spec, optionally adding edits.

        The copy inherits the source's label and edit list (the project
        file's definition, §12.1) and then applies ``edits`` on top — the
        WT → T101P workflow: duplicate the base-like variant, then give
        the copy its distinguishing modification. Editing never touches
        the source spec or the base configuration.
        """
        source = self._find(key)
        if source is None:
            return self._refuse("no variant keyed %r exists" % (key,))
        inherited = tuple(source.edits) + tuple(edits or ())
        return self.add_spec(
            new_key,
            new_label if new_label else source.label,
            inherited,
        )

    def preview(self, key: str):
        """Expand one spec against the open base without committing.

        Returns an ``ExpandOutput``; the variant's configuration is fully
        materialised and the project's committed spec list is untouched.
        """
        project = self._projects._require_project()
        if project is None:
            return ExpandOutput(ok=False, failure_reason=FailureReason.NOT_OPEN, message="no project is open")
        spec = self._find(key)
        if spec is None:
            return ExpandOutput(
                ok=False,
                failure_reason=FailureReason.UNKNOWN_RECORD,
                message="no variant keyed %r exists" % (key,),
            )
        return self._expand_specs((spec,))

    def expand(self, only=None):
        """Expand every committed spec, in declared order (§12.2).

        ``only`` (an iterable of keys) restricts the expansion to those
        specs — the subset-export route. Unknown keys refuse; an empty
        ``only`` means "no keys selected", not "everything".
        """
        project = self._projects._require_project()
        if project is None:
            return ExpandOutput(ok=False, failure_reason=FailureReason.NOT_OPEN, message="no project is open")
        specs = self._specs()
        if only is None:
            return self._expand_specs(specs)
        keys = tuple(only)
        known = {spec.key for spec in specs}
        unknown = [key for key in keys if key not in known]
        if unknown:
            return ExpandOutput(
                ok=False,
                failure_reason=FailureReason.UNKNOWN_RECORD,
                message="no variant keyed %r exists" % (unknown[0],),
            )
        selected = tuple(spec for key in keys for spec in specs if spec.key == key)
        return self._expand_specs(selected)

    def _factor_edit(self, project, factor: str, value, record_key=None):
        """The picker's factor → edit conversion (plan §16.4).

        Factors are the declared-change vocabulary of spec §15
        (``_FACTOR_BY_EDIT``'s targets). Returns ``(edit, None)`` on
        success and ``(None, message)`` on refusal — the edit objects are
        built here in ``app``: ``ui`` never constructs variant vocabulary.
        """
        try:
            if factor == "sequence":
                target = record_key or self._sole_polymer_key(project)
                if target is None:
                    return None, "choose the record the sequence change applies to"
                # The alphabet is the *target record's family*, known from
                # the configuration — never guessed from the text.
                alphabet = self._family_of_key(project, target)
                text = SequenceText(value, alphabet)
                return self._edit_class("SetSequence")(EntityId(target), text), None
            elif factor == "job_name":
                return self._edit_class("SetName")(value), None
            elif factor == "job_description":
                # The edit vocabulary stores the job description as a
                # Presence value (the presence algebra, plan §7.4): a
                # picker string means "present with this text".
                from configbuilder.model.presence import Present

                return self._edit_class("SetJobDescription")(Present(value)), None
            elif factor == "seeds":
                return self._edit_class("SetSeeds")(
                    [int(part) for part in str(value).replace(",", " ").split()]
                ), None
            else:
                return None, (
                    "the factor %r is not offered by the picker yet; "
                    "extend add_spec_from_factor" % (factor,)
                )
        except (EditError, VariantSpecError, ValueError, TypeError) as error:
            return None, str(error)

    def append_factor(self, key: str, factor: str, value, record_key=None):
        """Add one factor edit to an existing spec, keeping its others.

        The variant-editing route behind "edit a variant" in a free-
        navigation UI: the conversion is the picker's (``_factor_edit``
        builds the edit) and ``update_spec`` commits the extended tuple,
        so a variant is grown without ever rebuilding it.
        """
        project = self._projects._require_project()
        if project is None:
            return self._not_open()
        existing = self._find(key)
        if existing is None:
            return MutationOutput(
                ok=False,
                failure_reason=FailureReason.UNKNOWN_RECORD,
                message="no variant keyed %r exists" % (key,),
            )
        edit, failure = self._factor_edit(project, factor, value, record_key)
        if failure is not None:
            return self._refuse(failure)
        from configbuilder.model import SequenceTextError

        try:
            return self.update_spec(key, edits=existing.edits + (edit,))
        except SequenceTextError as error:
            return self._refuse(str(error))

    # -- UI choice tables (§15 vocabulary as numbered menus; the UI never
    #    constructs edits itself — every table answers "what can this
    #    variant change" from the same authority the edits come from) -----

    def edit_options(self) -> "tuple[VariantChoice, ...]":
        """The change kinds a variant can make, as UI choices.

        Every option here maps onto ``_factor_edit`` or
        ``apply_variant_edit`` — nothing is offered that the service
        cannot perform.
        """
        return (
            VariantChoice("Sequence change", "sequence"),
            VariantChoice("Add a modification", "add_modification"),
            VariantChoice("Remove a modification", "remove_modification"),
            VariantChoice("MSA (alignment)", "alignment"),
            VariantChoice("Structural templates", "references"),
            VariantChoice("Job name", "job_name"),
            VariantChoice("Job description", "job_description"),
            VariantChoice("Model seeds", "seeds"),
            VariantChoice("Add a new entity", "add_entity"),
            VariantChoice("Remove an entity", "remove_entity"),
        )

    def entity_choices(self, family: str) -> "tuple[VariantChoice, ...]":
        """The base's records of one family, as choice rows.

        ``label`` is deliberately **data, not wording** (``app`` cannot
        import the UI's string registry): the front end renders the row
        through its own registered templates. ``value`` is the internal
        key — resolved here, never typed.
        """
        project = self._projects._require_project()
        if project is None:
            return ()
        type_by_family = {
            "protein": FamilyARecord,
            "rna": FamilyBRecord,
            "dna": FamilyCRecord,
            "ligand": ComponentRecord,
        }
        type_ = type_by_family.get(family)
        if type_ is None:
            return ()
        choices = []
        for record in project.configuration.records:
            if not isinstance(record, type_):
                continue
            key = record.ids.primary.value
            choices.append(VariantChoice(key, family, key))
        return tuple(choices)

    def all_entity_choices(self) -> "tuple[VariantChoice, ...]":
        """Every base record across families, as choice rows (the
        sequence-change target picker)."""
        project = self._projects._require_project()
        if project is None:
            return ()
        return tuple(
            VariantChoice(record.ids.primary.value, "entity", record.ids.primary.value)
            for record in project.configuration.records
        )

    def record_sequence_choices(self) -> "tuple[VariantChoice, ...]":
        """Polymer records as choice rows (remove-modification picker)."""
        return self.all_entity_choices()

    def build_add_records(self, family: str, sequence: str, representation=""):
        """The record(s) one add-entity edit adds: ``(records, None)`` or
        ``((), message)``.

        Construction is delegated to the configuration service's own
        ``_build_records`` — the same validated constructors, the same
        DNA-duplex rule, allocation from a **throwaway clone** of the
        base registry (the base never claims the ids; ``AddRecord``
        reserves them again inside each expansion). A DNA family add
        therefore yields the two-strand duplex, exactly like the base
        entity path.
        """
        project = self._projects._require_project()
        if project is None:
            return (), "no project is open"
        if self._configuration is None:
            return (), "entity adds need the configuration service"
        registry = project.configuration.identity.clone()
        records, failure = self._configuration._build_records(
            family, sequence, representation, 1, registry
        )
        if failure is not None:
            return (), failure.message or "refused"
        return tuple(records), None

    def modification_summary(self, key: str):
        """The named modifications of one variant's target record.

        Returns a list of ``(index, ``'code@position'``)`` pairs for the
        record the sequence change would target — the remove picker's
        data, so an index is never counted by hand.
        """
        project = self._projects._require_project()
        if project is None:
            return []
        spec = self._find(key)
        if spec is None:
            return []
        summary = []
        for index, edit in enumerate(spec.edits):
            if type(edit).__name__ != "AddModification":
                continue
            described = describe_edit(edit)
            summary.append(
                (index, "%s @ %s (%s)" % (
                    described.get("record_key", "?"),
                    described.get("position", "?"),
                    described.get("code", "?"),
                ))
            )
        return summary

    def apply_variant_edit(self, key: str, kind: str, value, record_key=None) -> MutationOutput:
        """Apply one menu-selected change kind to an existing spec.

        The menu passes the ``kind`` from ``edit_options``; the edit
        construction stays here, in ``app``. Kinds outside the table
        refuse — the UI can never invent an edit the vocabulary lacks.
        """
        project = self._projects._require_project()
        if project is None:
            return self._not_open()
        if kind in ("sequence", "job_name", "job_description", "seeds"):
            return self.append_factor(key, kind, value, record_key=record_key)
        if kind == "add_modification":
            code, position = value
            try:
                code_value, position_value = self._modification_values(code, int(position))
                edit = self._edit_class("AddModification")(
                    EntityId(record_key), code_value, position_value
                )
            except (EditError, ModelError, ValueError, TypeError) as error:
                return self._refuse(str(error))
            return self._append_edit(key, edit)
        if kind == "remove_modification":
            try:
                edit = self._edit_class("RemoveModification")(
                    EntityId(record_key), int(value)
                )
            except (EditError, ValueError, TypeError) as error:
                return self._refuse(str(error))
            return self._append_edit(key, edit)
        if kind == "alignment":
            try:
                alignment = self._alignment_case(value)
            except ChoiceError as error:
                return self._refuse(str(error))
            try:
                edit = self._edit_class("SetAlignment")(
                    EntityId(record_key), alignment
                )
            except (EditError, ValueError, TypeError) as error:
                return self._refuse(str(error))
            return self._append_edit(key, edit)
        if kind == "references":
            try:
                reference_set = self._reference_set_case(value)
            except ChoiceError as error:
                return self._refuse(str(error))
            try:
                edit = self._edit_class("SetReferences")(
                    EntityId(record_key), reference_set
                )
            except (EditError, ValueError, TypeError) as error:
                return self._refuse(str(error))
            return self._append_edit(key, edit)
        if kind == "add_entity":
            try:
                new_edits = tuple(
                    self._edit_class("AddRecord")(record) for record in value
                )
            except (EditError, ValueError, TypeError) as error:
                return self._refuse(str(error))
            existing = self._find(key)
            if existing is None:
                return MutationOutput(
                    ok=False,
                    failure_reason=FailureReason.UNKNOWN_RECORD,
                    message="no variant keyed %r exists" % (key,),
                )
            return self.update_spec(key, edits=existing.edits + new_edits)
        if kind == "remove_entity":
            try:
                edit = self._edit_class("RemoveRecord")(EntityId(record_key))
            except (EditError, ValueError, TypeError) as error:
                return self._refuse(str(error))
            return self._append_edit(key, edit)
        return self._refuse("unknown change kind %r" % (kind,))

    def _append_edit(self, key: str, edit) -> MutationOutput:
        existing = self._find(key)
        if existing is None:
            return MutationOutput(
                ok=False,
                failure_reason=FailureReason.UNKNOWN_RECORD,
                message="no variant keyed %r exists" % (key,),
            )
        return self.update_spec(key, edits=existing.edits + (edit,))

    @staticmethod
    def _modification_values(code: str, position: int):
        from configbuilder.model import ComponentCode, Position

        return ComponentCode(code), Position(position)

    @staticmethod
    def _alignment_case(value):
        from configbuilder.model import (
            AlignmentAutomatic,
            AlignmentBoth,
            AlignmentFree,
            AlignmentPairedOnly,
            AlignmentUnpairedOnly,
            External,
            Inline,
            PathSpec,
        )

        mode, source = value
        if mode == "automatic":
            return AlignmentAutomatic()
        if mode == "free":
            return AlignmentFree()
        if source is None:
            raise ChoiceError("mode %r carries an MSA source; none was given" % (mode,))
        if source[0] == "inline":
            payload = Inline(source[1])
        else:
            payload = External(PathSpec(source[1]))
        if mode == "unpaired":
            return AlignmentUnpairedOnly(payload)
        if mode == "paired":
            return AlignmentPairedOnly(payload)
        if mode == "both":
            return AlignmentBoth(payload)
        raise ChoiceError("unknown alignment mode %r" % (mode,))

    @staticmethod
    def _reference_set_case(value):
        from configbuilder.model import (
            Explicit,
            External,
            IndexPair,
            Inline,
            PathSpec,
            ReferenceRecord,
            SearchAllowed,
        )

        route, payload = value
        if route == "search":
            return SearchAllowed()
        if route == "none":
            return Explicit(())
        # payload is a list of (source_kind, text, pairs) rows
        records = []
        for source_kind, text, pairs in payload:
            if source_kind == "inline":
                source = Inline(text)
            else:
                source = External(PathSpec(text))
            index_map = tuple(IndexPair(int(q), int(t)) for q, t in pairs)
            records.append(ReferenceRecord(source, index_map))
        return Explicit(tuple(records))

    def describe_spec_edits(self, key: str):
        """Every edit of one spec as described data (``describe_edit``),
        in order — the preview's change list as plain data; the front end
        renders it through its own registered wording."""
        project = self._projects._require_project()
        if project is None:
            return []
        spec = self._find(key)
        if spec is None:
            return []
        return [describe_edit(edit) for edit in spec.edits]

    def spec_change_descriptions(self, key: str):
        """The variant list's change summaries as plain ``(kind,
        described, record)`` rows — no wording (``app`` cannot import
        the UI's string registry); the front end renders each row
        through its registered templates."""
        rows = []
        for described in self.describe_spec_edits(key):
            kind = described.get("kind", "")
            record = described.get("record_key", "") or ""
            rows.append((kind, described, record))
        return rows

    def inspect_sequence_file(self, path: str):
        """Read a sequence file for preview **only** — no variant is
        created. The same persistence reader the committed batch uses,
        so what the user confirms is exactly what would be created."""
        from configbuilder.persistence import PersistenceError, read_sequence_file

        try:
            entries = read_sequence_file(path)
        except PersistenceError as error:
            return FilePreview(ok=False, message=str(error))
        if not entries:
            return FilePreview(
                ok=False, message="the sequence file contains no sequences (only blank lines)"
            )
        return FilePreview(ok=True, entries=[text for _, text in entries])

    def generate_from_file(self, path: str) -> MutationOutput:
        """Batch-generate one independent variant per sequence in a file.

        ``path`` is a sequence-list ``.txt`` (one sequence per line;
        blanks ignored). The reading is persistence's (plan §5.3 rule 8:
        file IO is confined there); the spec construction is the batch
        module's; the commitment is ``add_spec``'s — so every generated
        variant is a plain ``base + AddRecord`` spec, identical in kind
        to a hand-created one, visible in the Variants menu, exportable,
        and editable afterwards. All-or-nothing: any invalid line or
        duplicate refuses the whole batch and commits nothing.
        """
        project = self._projects._require_project()
        if project is None:
            return self._not_open()
        from configbuilder.persistence import PersistenceError, read_sequence_file
        from configbuilder.app.batch_variants import BatchError, batch_specs_for_sequences
        from configbuilder.model import SequenceTextError

        try:
            entries = read_sequence_file(path)
        except PersistenceError as error:
            return self._refuse(str(error))
        if not entries:
            return self._refuse("the sequence file contains no sequences (only blank lines)")
        try:
            registry = project.configuration.identity.clone()
            specs = batch_specs_for_sequences(entries, registry)
        except (BatchError, SequenceTextError) as error:
            return self._refuse(str(error))
        # Commit through add_spec so every guarantee (unique keys,
        # persistence shape) is the standard route's.
        for spec in specs:
            outcome = self.add_spec(spec.key, spec.label, spec.edits)
            if not outcome.ok:
                # Roll back any already-added specs of this batch.
                for done in specs:
                    if done.key == spec.key:
                        break
                    self.remove_spec(done.key)
                return self._refuse(
                    "variant %r could not be created: %s" % (spec.key, outcome.message)
                )
        return MutationOutput(ok=True, message="%d variants generated" % len(specs))

    def _expand_specs(self, specs):
        project = self._projects._require_project()
        try:
            variants = expand(project.configuration, tuple(specs))
        except (EditError, VariantSpecError) as error:
            return ExpandOutput(
                ok=False,
                failure_reason=FailureReason.EXPANSION_FAILED,
                message=str(error),
            )
        return ExpandOutput(ok=True, variants=variants)
