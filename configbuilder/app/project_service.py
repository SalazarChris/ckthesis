"""Project lifecycle (IMPLEMENTATION_PLAN.md §15): ``new``, ``open``,
``load_saved_work``, ``is_dirty``.

The workflow is JSON-first: what the user saves is generated AF3 JSON, and
the ``.cbproj`` working copy is this service's own autosave, never a
user-facing save target. Project-file save/save-as and the output-policy
setter were removed with that workflow (audit 2026-09-30); the internal
working copy is written by ``_commit_project`` and restored by
``load_saved_work``.

Every operation returns a result object; user-caused problems are
findings or failure reasons, never exceptions. Filesystem access rides
exclusively on ``persistence`` (plan §5.3 rule 8).
"""

from __future__ import annotations

import os

from configbuilder.app.results import FailureReason, ImportPreview, LoadOutput
from configbuilder.model import ModelError
from configbuilder.persistence import (
    FutureVersionError,
    OutputSettings,
    PersistenceError,
    Project,
    load as _load,
    save as _save,
    PROJECT_EXTENSION,
)

__all__ = ["ProjectService", "INTERNAL_PROJECTS_DIR"]


INTERNAL_PROJECTS_DIR = ".configbuilder"
"""Where working project files live, invisible to the user's workflow.

Users work exclusively with AF3 JSON files in their output destination;
the .cbproj working copy is the application's own resume mechanism,
kept out of the way in this internal directory under the current
working directory.
"""

WORKING_COPIES_KEPT = 50
"""How many working copies the internal store keeps.

The store is a *cache of recovery candidates*, not an archive: only
this application's own autosave files live here (never a user's
generated JSON, never an intentionally saved file), only the newest one
is ever restored, and pruning on a new job keeps the store from growing
without bound. Fifty sessions of slack is far more than the recovery
offer needs.
"""


class ProjectService:
    """Owns the currently open project and its persistence.

    Persistence discipline (the JSON-first workflow): the user-visible
    save action writes **AF3 JSON** through the generation pipeline into
    the output destination. The canonical .cbproj working copy is
    maintained silently in ``INTERNAL_PROJECTS_DIR`` — written on every
    committed change (``_commit_project``) — and ``load_saved_work``
    restores it on "Open saved work". No prompt, no path ritual.
    """

    def __init__(self, validate=None) -> None:
        self._project = None  # type: Optional[Project]
        self._path = None  # type: Optional[str]
        self._dirty = False
        self._validate = validate
        self._automatic_names = 0  # how many automatic job names this session minted

    # -- internal working copy ------------------------------------------------

    def _internal_path(self) -> str:
        import uuid

        root = os.path.join(os.getcwd(), INTERNAL_PROJECTS_DIR)
        os.makedirs(root, exist_ok=True)
        return os.path.join(root, "%s.cbproj" % uuid.uuid4().hex)

    def _commit_project(self) -> None:
        """Silently persist the working copy. Failures are swallowed by
        design: this is crash protection, not a user-visible action."""
        if self._project is None:
            return
        try:
            if self._path is None:
                self._path = self._internal_path()
            _save(self._project, self._path)
            self._dirty = False
        except OSError:
            pass

    def load_saved_work(self) -> LoadOutput:
        """Restore the most recent internal working copy, if any.

        Returns ``ok=False`` (``NO_SAVED_WORK``) when none exists — the
        user simply starts a new job — and also when the open job *is*
        that copy, with a message saying so: silently re-opening what the
        user is already editing looked like nothing happened. The restored
        project becomes the current one exactly as it was left.
        """
        import glob as _glob

        root = os.path.join(os.getcwd(), INTERNAL_PROJECTS_DIR)
        candidates = sorted(
            _glob.glob(os.path.join(root, "*.cbproj")), key=os.path.getmtime
        )
        if not candidates:
            return LoadOutput(
                ok=False,
                failure_reason=FailureReason.NO_SAVED_WORK,
                message="there is no saved work to reopen",
            )
        newest = candidates[-1]
        if self._project is not None and self._path == newest:
            return LoadOutput(
                ok=False,
                failure_reason=FailureReason.NO_SAVED_WORK,
                message=(
                    "the current job is already the most recent working copy; "
                    "it is kept up to date as you edit"
                ),
            )
        return self.open(newest)

    def _prune_working_copies(self) -> None:
        """Bound the internal store to the newest ``WORKING_COPIES_KEPT``
        working copies.

        Called when a new job starts, so the store cannot grow without
        bound across sessions. Only this application's own autosave files
        are candidates (``*.cbproj`` in ``INTERNAL_PROJECTS_DIR``): a
        failure to prune is ignored — recovery still works, the store is
        just larger than intended.
        """
        root = os.path.join(os.getcwd(), INTERNAL_PROJECTS_DIR)
        try:
            names = [
                name
                for name in os.listdir(root)
                if name.endswith(PROJECT_EXTENSION)
            ]
        except OSError:
            return
        if len(names) <= WORKING_COPIES_KEPT:
            return
        try:
            names.sort(
                key=lambda name: os.path.getmtime(os.path.join(root, name)),
                reverse=True,
            )
        except OSError:
            return
        for name in names[WORKING_COPIES_KEPT:]:
            try:
                os.remove(os.path.join(root, name))
            except OSError:
                pass

    # -- state ---------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._project is not None

    @property
    def is_dirty(self) -> bool:
        """True when the in-memory project differs from the last save."""
        return self._dirty

    @property
    def project(self):
        """The open project, or ``None``. Read-only for front ends."""
        return self._project

    @property
    def path(self):
        return self._path

    # -- operations (§15) ------------------------------------------------------

    def new(self, name: str = None) -> Project:
        """Start a fresh project. Never fails: nothing exists to corrupt.

        The job arrives with the standard defaults already applied (the
        policy in ``app/status.py``): a job name when the caller supplies
        one and an automatic ``config-NNN`` name otherwise, the project's
        default seed set, and the default format-version pin — so an
        export never needs a naming/seeding/version ritual first. Only the
        entities are genuinely the user's to supply; nothing here invents
        biological data. Every default stays editable: the job settings
        menu can change the name, the seeds, and the pin at any time, and
        ``Unverified`` remains the explicit refusal-to-pin state.
        """
        from configbuilder.model import Configuration, ConfigurationMetadata, FormatTarget, SeedSet
        from configbuilder.model.configuration import Pinned
        from configbuilder.identity import IdentityRegistry
        from configbuilder.app.status import (
            DEFAULT_SEED_VALUES,
            DEFAULT_VERSION,
            default_job_name,
        )

        self._prune_working_copies()
        job_name = (name or "").strip()
        if not job_name:
            self._automatic_names += 1
            job_name = default_job_name(self._automatic_names)
        configuration = Configuration(
            metadata=ConfigurationMetadata(job_name),
            seeds=SeedSet(list(DEFAULT_SEED_VALUES)),
            records=(),
            identity=IdentityRegistry(),
            format_target=FormatTarget(version_selection=Pinned(DEFAULT_VERSION)),
        )
        self._project = Project(
            configuration=configuration,
            specs=(),
            settings=OutputSettings(),
        )
        self._path = None
        self._dirty = True
        self._commit_project()
        return self._project

    # -- AF3 JSON import (§7 of the import feature; the same canonical model) --

    def import_json_preview(self, path: str) -> ImportPreview:
        """Parse and validate an AF3 JSON file **without installing it**.

        Returns the summary rows and any ImportNotes for the confirm
        screen; the current project is untouched whatever happens here.
        """
        from configbuilder.transform import WireImportError, from_wire

        try:
            with open(path, "r", encoding="utf-8") as handle:
                import json as _json

                document = _json.load(handle)
        except OSError as error:
            return ImportPreview(ok=False, failure_reason=FailureReason.IO_ERROR, message=str(error))
        except ValueError as error:
            return ImportPreview(
                ok=False,
                failure_reason=FailureReason.CORRUPT_FILE,
                message="the file is not valid JSON: %s" % (error,),
            )
        try:
            configuration, notes = from_wire(document)
        except WireImportError as error:
            return ImportPreview(ok=False, failure_reason=FailureReason.CORRUPT_FILE, message=str(error))
        except (ModelError, ValueError, TypeError) as error:
            return ImportPreview(ok=False, failure_reason=FailureReason.CORRUPT_FILE, message=str(error))
        return ImportPreview(ok=True, summary=self._import_summary(configuration), notes=notes)


    def import_json_commit(self, path: str) -> LoadOutput:
        """Install the previously previewed file as the current project.

        The file becomes the base configuration — a normal job, editable
        through every existing service, variant-able, and generatable;
        no "imported" special state exists. The original file is never
        modified (the import output goes through the normal generation
        naming, which derives its own path from the project name).
        """
        from configbuilder.transform import WireImportError, from_wire

        try:
            with open(path, "r", encoding="utf-8") as handle:
                import json as _json

                document = _json.load(handle)
        except OSError as error:
            return LoadOutput(ok=False, failure_reason=FailureReason.IO_ERROR, message=str(error))
        except ValueError as error:
            return LoadOutput(
                ok=False,
                failure_reason=FailureReason.CORRUPT_FILE,
                message="the file is not valid JSON: %s" % (error,),
            )
        try:
            configuration, notes = from_wire(document)
        except WireImportError as error:
            return LoadOutput(ok=False, failure_reason=FailureReason.CORRUPT_FILE, message=str(error))
        except (ModelError, ValueError, TypeError) as error:
            return LoadOutput(ok=False, failure_reason=FailureReason.CORRUPT_FILE, message=str(error))
        report = None
        if self._validate is not None:
            report = self._validate(configuration)
        self._project = Project(
            configuration=configuration,
            specs=(),
            settings=OutputSettings(),
        )
        # The imported file is not a project file, and the imported job is
        # the current one from this moment on: commit it to the internal
        # working copy immediately, so it survives a crash before the
        # user's next edit (the same promise every other mutation keeps).
        self._path = None
        self._dirty = True
        self._commit_project()
        return LoadOutput(
            ok=True,
            project=self._project,
            warnings=tuple(note.detail for note in notes),
            findings=report,
        )

    def _import_summary(self, configuration) -> dict:
        """Summary data for the confirm screen — plain data from the
        model; the UI renders wording ("app returns data, ui renders",
        plan §5.3 rule 6)."""
        from configbuilder.model.records import FamilyARecord, FamilyBRecord, FamilyCRecord, ComponentRecord

        records = configuration.records
        family_names = {
            FamilyARecord: "protein",
            FamilyBRecord: "rna",
            FamilyCRecord: "dna",
            ComponentRecord: "ligand",
        }
        families = {}
        for record in records:
            name = family_names.get(type(record), type(record).__name__)
            families.setdefault(name, []).append(record)
        return {
            "job_name": configuration.metadata.name,
            "seed_values": [seed.value for seed in configuration.seeds.seeds],
            "entity_count": len(records),
            "family_counts": {name: len(rows) for name, rows in sorted(families.items())},
            "record_ids": [record.ids.primary.value for record in records],
        }

    def open(self, path: str) -> LoadOutput:
        """Load a project file. Corruption, future versions, and IO
        problems are reported, never raised."""
        try:
            result = _load(path, validate=self._validate)
        except FutureVersionError as error:
            return LoadOutput(
                ok=False,
                failure_reason=FailureReason.FUTURE_VERSION,
                message=str(error),
            )
        except PersistenceError as error:
            return LoadOutput(
                ok=False,
                failure_reason=FailureReason.CORRUPT_FILE,
                message=str(error),
            )
        except OSError as error:
            return LoadOutput(
                ok=False,
                failure_reason=FailureReason.IO_ERROR,
                message=str(error),
            )
        self._project = result.project
        self._path = path
        self._dirty = False
        return LoadOutput(
            ok=True,
            project=result.project,
            warnings=tuple(result.warnings()) if callable(getattr(result, "warnings", None)) else (),
            findings=result.report,
            upgraded_from=result.upgraded_from,
        )

    # -- internal hooks used by the sibling services ---------------------------

    def _require_project(self):
        if self._project is None:
            return None
        return self._project

    def _replace_project(self, project: Project) -> None:
        self._project = project
        self._dirty = True

    def _specs(self):
        project = self._require_project()
        return project.specs if project is not None else ()

    def _with_specs(self, specs):
        project = self._require_project()
        if project is None:
            return None
        self._replace_project(project.with_specs(tuple(specs)))
        return project
