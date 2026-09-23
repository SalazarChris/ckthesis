"""Project lifecycle (IMPLEMENTATION_PLAN.md §15): ``new``, ``open``,
``save``, ``save_as``, ``is_dirty``.

Every operation returns a result object; user-caused problems are
findings or failure reasons, never exceptions. Filesystem access rides
exclusively on ``persistence`` (plan §5.3 rule 8).
"""

from __future__ import annotations

import os
from typing import Optional

from configbuilder.app.results import FailureReason, ImportPreview, LoadOutput, SaveOutput
from configbuilder.output.naming import slug
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
        user simply starts a new job. The restored project becomes the
        current one exactly as it was left.
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
        return self.open(candidates[-1])

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

    def new(self, name: str = "Untitled project") -> Project:
        """Start a fresh project. Never fails: nothing exists to corrupt.

        The format target pins a default version so an export never needs
        a version/evidence ritual first; the job settings menu can change
        the pin at any time. ``Auto`` stays the upgrade path: pinning
        nothing keeps generation at the default, while a project that
        pins no version explicitly (Unverified) still refuses to export —
        that refusal is a statement, not a missing default."""
        from configbuilder.model import Configuration, ConfigurationMetadata, FormatTarget, SeedSet
        from configbuilder.model.configuration import Pinned
        from configbuilder.identity import IdentityRegistry

        configuration = Configuration(
            metadata=ConfigurationMetadata(name),
            seeds=SeedSet([1]),
            records=(),
            identity=IdentityRegistry(),
            format_target=FormatTarget(version_selection=Pinned(3)),
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
        self._path = None  # the imported file is not a project file
        self._dirty = True
        self._path = self._internal_path()
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

    def save(self) -> SaveOutput:
        """Write to the project's current path (``FailureReason.SAVE_WITHOUT_PATH``
        when none is set — use ``save_as`` or ``suggested_project_path``)."""
        if self._project is None:
            return SaveOutput(ok=False, failure_reason=FailureReason.NOT_OPEN, message="no project is open")
        if self._path is None:
            return SaveOutput(
                ok=False,
                failure_reason=FailureReason.SAVE_WITHOUT_PATH,
                message="the project has no path yet; choose one with save_as",
            )
        return self.save_as(self._path)

    def suggested_project_path(self) -> str:
        """A concrete default save path for the UI's save prompt.

        The project's current path when it has one ("blank keeps the
        current one"); otherwise ``<cwd>/<project-name-slug>.cbproj`` —
        the extension is the persistence layer's. An empty string when
        there is no open project or the name admits no slug; the caller
        then falls back to its existing behaviour (``save`` refuses, and
        says so).
        """
        project = self._project
        if project is None:
            return ""
        if self._path:
            return self._path
        try:
            base = slug(project.configuration.metadata.name)
        except NameError:
            return ""
        return os.path.join(os.getcwd(), base + PROJECT_EXTENSION)

    def save_as(self, path: str) -> SaveOutput:
        """Write to ``path`` and make it the project's path."""
        if self._project is None:
            return SaveOutput(ok=False, failure_reason=FailureReason.NOT_OPEN, message="no project is open")
        try:
            _save(self._project, path)
        except OSError as error:
            return SaveOutput(ok=False, failure_reason=FailureReason.IO_ERROR, message=str(error))
        self._path = path
        self._dirty = False
        return SaveOutput(ok=True, path=path)

    def set_output_policies(self, overwrite_policy=None, path_policy=None) -> SaveOutput:
        """Set the output policies (plan §16.4: explicit path policy and
        overwrite policy are advanced settings reachable from the wizard).

        Arguments are the policy names as data ("Fail", "Skip",
        "Overwrite", "Versioned"; "CopyIntoAssets", "RelativeToOutput",
        "AsGiven"); unknown names are refused, never guessed."""
        if self._project is None:
            return SaveOutput(ok=False, failure_reason=FailureReason.NOT_OPEN, message="no project is open")
        settings = self._project.settings
        overwrite = overwrite_policy if overwrite_policy is not None else settings.overwrite_policy
        path = path_policy if path_policy is not None else settings.path_policy
        from configbuilder.output import OverwritePolicy, PathPolicy
        from configbuilder.output.policies import OVERWRITE_POLICIES, PATH_POLICIES

        # The policy sets are closed (plan §13.3, §13.5); unknown names
        # are refused, never guessed.
        if overwrite not in (p.name for p in OVERWRITE_POLICIES):
            return SaveOutput(
                ok=False,
                failure_reason=FailureReason.NO_PATH,
                message="unknown overwrite policy %r; use one of %s"
                % (overwrite, ", ".join(p.name for p in OVERWRITE_POLICIES)),
            )
        if path not in (p.name for p in PATH_POLICIES):
            return SaveOutput(
                ok=False,
                failure_reason=FailureReason.NO_PATH,
                message="unknown path policy %r; use one of %s"
                % (path, ", ".join(p.name for p in PATH_POLICIES)),
            )
        from configbuilder.persistence import OutputSettings

        self._replace_project(
            self._project.with_settings(OutputSettings(overwrite, path))
        )
        return SaveOutput(ok=True, path=self._path)

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

    def _settings(self):
        project = self._require_project()
        return project.settings if project is not None else None

    def _with_settings(self, settings) -> None:
        project = self._require_project()
        if project is None:
            return
        self._replace_project(project.with_settings(settings))
