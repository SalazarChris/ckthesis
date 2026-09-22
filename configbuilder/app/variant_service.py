"""Variant spec editing (IMPLEMENTATION_PLAN.md §15): ``VariantService``.

``add_spec`` / ``update_spec`` / ``remove_spec`` / ``duplicate_spec``
maintain the project's spec list; ``preview`` expands a single spec
without committing it; ``expand`` materialises the whole set. Edit
failures (unknown record keys, identifier conflicts) come back as
failure reasons — never exceptions.
"""

from __future__ import annotations

from configbuilder.app.results import ExpandOutput, FailureReason, MutationOutput
from configbuilder.identity import EntityId, IdentityRegistry
from configbuilder.model import SequenceText
from configbuilder.variants import (
    EditError,
    VariantSpec,
    VariantSpecError,
    expand,
)

__all__ = ["VariantService"]


class VariantService:
    """Maintains the open project's variant specs."""

    def __init__(self, projects) -> None:
        self._projects = projects

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
