"""Project lifecycle (IMPLEMENTATION_PLAN.md §15): ``new``, ``open``,
``save``, ``save_as``, ``is_dirty``.

Every operation returns a result object; user-caused problems are
findings or failure reasons, never exceptions. Filesystem access rides
exclusively on ``persistence`` (plan §5.3 rule 8).
"""

from __future__ import annotations

from typing import Optional

from configbuilder.app.results import FailureReason, LoadOutput, SaveOutput
from configbuilder.persistence import (
    FutureVersionError,
    OutputSettings,
    PersistenceError,
    Project,
    load as _load,
    save as _save,
)

__all__ = ["ProjectService"]


class ProjectService:
    """Owns the currently open project and its persistence."""

    def __init__(self, validate=None) -> None:
        self._project = None  # type: Optional[Project]
        self._path = None  # type: Optional[str]
        self._dirty = False
        self._validate = validate

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
        """Start a fresh project. Never fails: nothing exists to corrupt."""
        from configbuilder.model import Configuration, ConfigurationMetadata, SeedSet
        from configbuilder.identity import IdentityRegistry

        configuration = Configuration(
            metadata=ConfigurationMetadata(name),
            seeds=SeedSet([1]),
            records=(),
            identity=IdentityRegistry(),
        )
        self._project = Project(
            configuration=configuration,
            specs=(),
            settings=OutputSettings(),
        )
        self._path = None
        self._dirty = True
        return self._project

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
        when none is set — use ``save_as``)."""
        if self._project is None:
            return SaveOutput(ok=False, failure_reason=FailureReason.NOT_OPEN, message="no project is open")
        if self._path is None:
            return SaveOutput(
                ok=False,
                failure_reason=FailureReason.SAVE_WITHOUT_PATH,
                message="the project has no path yet; choose one with save_as",
            )
        return self.save_as(self._path)

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
