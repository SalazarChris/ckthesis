"""Session state for the Qt front end (Stage 2: job lifecycle).

The desktop window owns **no project state of its own**: the open job is
whatever ``ProjectService`` holds, and every operation below is a
pass-through to an existing service. There is deliberately no second copy of
the configuration — a duplicate would be one more thing to keep in sync.

Two pieces of information the services do not carry live here, and only
these two:

- which file the current job came from (for the window's status bar), and
  whether the job is the built-in sample instead (``--demo``);
- **whether the job has unsaved changes**, tracked exactly as the console
  menu tracks them (``ui.render.menus.MenuApp._has_unsaved``): the model is
  immutable, so holding the last saved ``Configuration`` object *is* a
  complete snapshot, and a job is dirty when the live configuration is not
  that object any more. ``ProjectService.is_dirty`` cannot be used for this:
  it is set by every mutation and reset only by ``open()``, so a saved job
  would still read dirty.

Nothing here raises for a user-caused problem: the service result objects are
returned unchanged so the caller can render ``failure_reason`` and
``message``.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from configbuilder.ui.services import build_services

__all__ = ["GuiState", "build_demo_state"]


class GuiState(QObject):
    """The window's view of the application services.

    ``project_changed`` fires after an import is committed (and only then),
    so pages refresh from the service's own model rather than from anything
    cached here. ``source_changed`` fires when the source path changes.
    """

    project_changed = Signal()
    source_changed = Signal()

    def __init__(self, services=None, source_path="", demo=False, parent=None) -> None:
        super().__init__(parent)
        self._services = services if services is not None else build_services()
        self._source_path = source_path or ""
        self._demo = bool(demo)
        # The configuration as of the last new job / open / save. The model is
        # immutable, so the object itself is the snapshot (see the module
        # docstring); ``None`` means "nothing to compare yet" and reads as
        # clean, exactly as the console menu's own snapshot does.
        self._saved_snapshot = None

    # -- the services and the open job ------------------------------------

    @property
    def services(self):
        """The wired service bundle (``ui.services.build_services``)."""
        return self._services

    @property
    def project(self):
        """The open project, or ``None``. The service is the authority."""
        return self._services.projects.project

    @property
    def configuration(self):
        """The open configuration, or ``None``. Never copied."""
        project = self.project
        return project.configuration if project is not None else None

    def has_project(self) -> bool:
        return self.project is not None

    @property
    def source_path(self) -> str:
        return self._source_path

    @property
    def is_demo(self) -> bool:
        return self._demo

    # -- the job lifecycle: new, open, save (Stage 2) ----------------------

    def new_job(self, name=None):
        """Start a fresh job through ``ProjectService.new`` and adopt it.

        ``name=None`` keeps the service's own default: the standard starting
        policy (automatic name, default seed set, default version pin) is the
        service's, never re-implemented here. The new job is the baseline for
        dirty tracking — it arrives already "saved" in that sense, exactly as
        the console menu treats a newly created job.
        """
        project = self._services.projects.new(name)
        self._source_path = ""
        self._demo = False
        self.mark_saved()
        self.project_changed.emit()
        self.source_changed.emit()
        return project

    def mark_saved(self) -> None:
        """Record the live configuration as the last-saved one (menu parity)."""
        project = self.project
        self._saved_snapshot = project.configuration if project is not None else None

    @property
    def is_dirty(self) -> bool:
        """True when the live configuration differs from the last save/open."""
        project = self.project
        if project is None or self._saved_snapshot is None:
            return False
        return project.configuration != self._saved_snapshot

    def record_save(self, path: str) -> None:
        """Adopt ``path`` as the current file after a successful save.

        Only the source label and the saved snapshot change: the job itself
        is the configuration the service already wrote.
        """
        self._source_path = path
        self._demo = False
        self.mark_saved()
        self.source_changed.emit()

    def suggested_file_name(self) -> str:
        """The save dialog's default name, in the console's own convention."""
        configuration = self.configuration
        name = "job"
        if configuration is not None:
            name = (configuration.metadata.name or "job").strip() or "job"
        return name.replace(" ", "_") + ".json"

    # -- job settings, through ConfigurationService (Stage 2) --------------

    def set_job_name(self, name: str):
        """Rename the job; the service validates and reports refusal."""
        outcome = self._services.configuration.set_name(name)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def set_seeds(self, seeds):
        """Set the model seeds; text is parsed by the service."""
        outcome = self._services.configuration.set_seeds(seeds)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def set_json_version(self, version):
        """Pin the JSON format version through the service's own rules."""
        outcome = self._services.configuration.set_format_target(version=int(version))
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    # -- entity management, through ConfigurationService (Stage 3) ---------

    def add_record(
        self,
        family,
        sequence="",
        representation="",
        copies=1,
        description=None,
        representation_kind="",
    ):
        """Add a record; the service validates and allocates identifiers.

        ``description=None`` leaves the record's description unset (the
        service distinguishes that from an explicitly empty value); pass
        ``""`` for an explicitly empty one. DNA adds the duplex — both
        records — exactly as the service defines it.
        """
        outcome = self._services.configuration.add_record(
            family,
            sequence=sequence,
            representation=representation,
            copies=copies,
            description=description,
            representation_kind=representation_kind,
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def update_record(self, record_key, sequence=None, description=None):
        """Change a record's sequence and/or description through the service.

        Either argument left as ``None`` keeps the record's existing value
        (and its exact description presence); DNA partner propagation is the
        service's own behaviour and is never redone here.
        """
        outcome = self._services.configuration.update_record(
            record_key, sequence=sequence, description=description
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def remove_record(self, record_key):
        """Remove a record through the service (a DNA duplex goes together)."""
        outcome = self._services.configuration.remove_record(record_key)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def set_representation(self, record_key, codes=None, notation=None):
        """Set a ligand's representation; exactly one form, as the service requires."""
        outcome = self._services.configuration.set_representation(
            record_key, codes=codes, notation=notation
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def update_component_record(self, record_key, codes=None, notation=None, description=None):
        """Change a ligand's representation and/or description as one edit.

        One service call, one commit: a refusal leaves the record exactly as
        it was, so a front end cannot half-apply a ligand edit (Stage 4).
        """
        outcome = self._services.configuration.update_component_record(
            record_key, codes=codes, notation=notation, description=description
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    # -- advanced entity settings, through ConfigurationService (Stage 4) -

    def add_modification(self, record_key, code, position):
        """Add a modification to a polymer record; the service validates it."""
        outcome = self._services.configuration.add_modification(
            record_key, code, position
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def update_modification(self, record_key, index, code=None, position=None):
        """Change one of a record's modifications, chosen by its own index."""
        outcome = self._services.configuration.update_modification(
            record_key, index, code=code, position=position
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def remove_modification(self, record_key, index):
        """Remove one of a record's modifications, chosen by its own index."""
        outcome = self._services.configuration.remove_modification(record_key, index)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def set_alignment(self, record_key, mode, inline_text=None, external_path=None):
        """Set a chain's alignment mode and, when it needs one, its source."""
        outcome = self._services.configuration.set_alignment(
            record_key, mode, inline_text=inline_text, external_path=external_path
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def set_references(self, record_key, references=None):
        """Set a protein's templates: search allowed, none, or a file list."""
        outcome = self._services.configuration.set_references(
            record_key, references=references
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def set_component_definition(self, inline_text=None, external_path=None):
        """Set the job's custom CCD definition (inline text XOR an external path)."""
        outcome = self._services.configuration.set_component_definition(
            inline_text=inline_text, external_path=external_path
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def clear_component_definition(self):
        """Remove the job's custom CCD definition."""
        outcome = self._services.configuration.clear_component_definition()
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def add_linkage(self, a_key, a_residue, a_atom, b_key, b_residue, b_atom):
        """Bond two endpoints; the service resolves both identifiers."""
        outcome = self._services.configuration.add_linkage(
            a_key, a_residue, a_atom, b_key, b_residue, b_atom
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def remove_linkage(self, index):
        """Remove the linkage at ``index`` (the model's own linkage order)."""
        outcome = self._services.configuration.remove_linkage(index)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    # -- variants and batch, through VariantService (Stage 5) --------------

    @property
    def specs(self):
        """The committed variant specs, in declared order (read-only)."""
        return tuple(self._services.variants.specs())

    def edit_options(self):
        """The change kinds the service supports, as its own choice rows."""
        return self._services.variants.edit_options()

    def all_entity_choices(self):
        """Every base record as a choice row (labels are the service's)."""
        return self._services.variants.all_entity_choices()

    def entity_choices(self, family):
        """The base's records of one family as choice rows."""
        return self._services.variants.entity_choices(family)

    def component_count_choices(self):
        """The component records whose copy count a variant can change."""
        return self._services.variants.component_count_choices()

    def modification_summary(self, key):
        """The expanded variant's modification rows for the remove picker."""
        return self._services.variants.modification_summary(key)

    def modification_choices(self, key):
        """Modification rows with their record key, for the remove picker."""
        return self._services.variants.modification_choices(key)

    def describe_spec_edits(self, key):
        """One spec's declared edits as plain described data."""
        return self._services.variants.describe_spec_edits(key)

    def spec_change_descriptions(self, key):
        """One spec's changes as ``(kind, described, record)`` rows."""
        return self._services.variants.spec_change_descriptions(key)

    def add_spec_with_edit(self, key, label, kind, value, record_key=None):
        """Create a spec and its first change in one service commit."""
        outcome = self._services.variants.add_spec_with_edit(
            key, label, kind, value, record_key=record_key
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def update_spec(self, key, label=None, edits=None):
        """Change a spec's label and/or declared edits (the service's own)."""
        outcome = self._services.variants.update_spec(key, label=label, edits=edits)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def remove_spec(self, key):
        """Remove one spec; cancellation is the caller's concern, not ours."""
        outcome = self._services.variants.remove_spec(key)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def duplicate_spec(self, key, new_key, new_label=""):
        """Copy one spec under a fresh key through the service."""
        outcome = self._services.variants.duplicate_spec(key, new_key, new_label)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def describe_variant_change(self, kind, value, record_key=None):
        """Preview one proposed change as described data (no commit)."""
        return self._services.variants.describe_change(
            kind, value, record_key=record_key
        )

    def apply_variant_edit(self, key, kind, value, record_key=None):
        """Append one declared change to an existing spec."""
        outcome = self._services.variants.apply_variant_edit(
            key, kind, value, record_key=record_key
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def preview_variant(self, key):
        """Expand one spec without committing anything (``ExpandOutput``)."""
        return self._services.variants.preview(key)

    def preview_variant_json(self, key):
        """The variant's JSON text through the generation pipeline."""
        return self._services.generation.show_json(key)

    def quantity_series_plan(self, keys, start, factor, levels):
        """The planned series as reviewable data; nothing is created."""
        return self._services.variants.quantity_series_plan(keys, start, factor, levels)

    def create_quantity_series(self, keys, start, factor, levels):
        """Commit the series the user reviewed (one spec per level)."""
        outcome = self._services.variants.create_quantity_series(
            keys, start, factor, levels
        )
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def inspect_batch_file(self, path, family="protein"):
        """Preview a batch input file without creating variants."""
        return self._services.variants.inspect_batch_file(path, family=family)

    def generate_from_file(self, path, family="protein"):
        """Commit an all-or-nothing batch from ``path``."""
        outcome = self._services.variants.generate_from_file(path, family=family)
        if outcome.ok:
            self.project_changed.emit()
        return outcome

    def build_add_records(self, family, sequence, representation="", representation_kind=""):
        """The records an add-entity change would add, built by the service."""
        return self._services.variants.build_add_records(
            family,
            sequence,
            representation=representation,
            representation_kind=representation_kind,
        )

    # -- saving, through the generation service (Stage 2) ------------------

    def plan_save(self, destination: str, name=None, overwrite: bool = False):
        """``GenerationService.plan_save`` — planning only, nothing written."""
        return self._services.generation.plan_save(
            destination, name=name, overwrite=overwrite
        )

    def output_policy_choices(self):
        """The generation policies a picker may offer (names, not objects)."""
        return self._services.generation.output_policy_choices()

    def output_defaults(self):
        """The project's own output settings, as policy names."""
        return self._services.generation.output_defaults()

    def plan_generation(
        self,
        output_root,
        scope="variants",
        only=None,
        overwrite_policy=None,
        path_policy=None,
    ):
        """``GenerationService.plan_selection`` — plan one scope, write nothing."""
        return self._services.generation.plan_selection(
            output_root,
            scope=scope,
            only=only,
            overwrite_policy=overwrite_policy,
            path_policy=path_policy,
        )

    def execute(self, plan):
        """``GenerationService.execute`` — writes exactly the reviewed plan."""
        return self._services.generation.execute(plan)

    # -- reading an AF3 JSON file (preview, then an explicit commit) ------

    def preview_import(self, path: str):
        """Parse ``path`` without installing it (``ImportPreview``).

        The current job is untouched whatever happens here, and the file on
        disk is only ever read.
        """
        return self._services.projects.import_json_preview(path)

    def commit_import(self, path: str):
        """Install the previously previewed file (``LoadOutput``).

        Call this **only** after the user confirmed the preview. A refusal
        (or a failed preview) leaves the open job exactly as it was.
        """
        outcome = self._services.projects.import_json_commit(path)
        if outcome.ok:
            self._source_path = path
            self._demo = False
            # The file's own content is the saved state (the menu does the
            # same after an import): nothing is "unsaved" until it is edited.
            self.mark_saved()
            self.project_changed.emit()
            self.source_changed.emit()
        return outcome

    # -- services the read-only pages read --------------------------------

    def preview_json(self, key=None):
        """``(text, None)`` or ``(None, reason)`` from ``show_json``.

        Display-only: the same ``to_wire`` → ``encode`` path a save uses, so
        what the window shows is what the builder would write. Refusals come
        back as a reason, never as an exception.
        """
        return self._services.generation.show_json(key)


def build_demo_state(services=None) -> GuiState:
    """A state holding a small **sample** job built through the services.

    Used by ``--demo`` and by the tests. Everything is created with the
    ordinary service calls — no wire structure is assembled here — and
    nothing is written to disk. The sample deliberately stays inside JSON
    version 3's feature set (no per-entity descriptions), so its JSON
    preview succeeds and demonstrates the normal path.
    """
    state = GuiState(services if services is not None else build_services(), demo=True)
    configuration = state.services.configuration
    projects = state.services.projects
    projects.new("sample-review-job")
    configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")
    configuration.add_record("protein", "GGGGSGGGGS")
    configuration.add_record("dna", "ATGC")
    configuration.add_record("rna", "ACGUACGU")
    configuration.add_record("ligand", representation="ATP", representation_kind="ccd")
    configuration.add_record("ligand", representation="CCO", representation_kind="smiles")
    configuration.add_modification("A", "SEP", 4)
    # The sample arrives as the last-saved state: closing the demo window
    # without touching it must not ask about unsaved changes.
    state.mark_saved()
    return state
