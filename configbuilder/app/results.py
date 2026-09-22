"""Result objects (IMPLEMENTATION_PLAN.md §15).

``app`` exposes the only API a front end needs, and every operation
returns a result object: user-caused problems are findings, not
exceptions. These types are plain data holders — the terminal wizard and
any other front end read them; nothing here raises for conditions the
user can fix.

The types are deliberately app-owned (plan §5.3 rule 6: ``ui`` imports
``app`` and ``model.traceability`` only, so layer types must not leak
into the result surface).
"""

from __future__ import annotations

from typing import Optional, Tuple

__all__ = [
    "FailureReason",
    "ConfigurationOutput",
    "ExpandOutput",
    "GenerationPlan",
    "LoadOutput",
    "MutationOutput",
    "PlanOutput",
    "SaveOutput",
    "VariantValidationOutput",
]


class FailureReason:
    """Stable, matchable reasons a service operation returned no value.

    A front end switches on these instead of parsing messages. The
    companion ``message`` is human-readable; ``rule_id`` names the
    blocking catalogue rule where the failure came from validation.
    """

    NOT_OPEN = "not_open"
    VALIDATION_BLOCKED = "validation_blocked"
    EXPANSION_FAILED = "expansion_failed"
    TRANSFORM_FAILED = "transform_failed"
    EMPTY_EXPANSION = "empty_expansion"
    SAVE_WITHOUT_PATH = "save_without_path"
    IO_ERROR = "io_error"
    CORRUPT_FILE = "corrupt_file"
    FUTURE_VERSION = "future_version"
    UNKNOWN_RECORD = "unknown_record"
    NO_PATH = "no_path"


class MutationOutput:
    """Outcome of a mutation (``ConfigurationService`` operations).

    ``findings`` carries what validation reports about the project after
    the change (empty when the service was built with validation
    disabled); ``unknown_record`` reports an edit aimed at a record key
    identity does not know — the user must pick a real record.
    """

    __slots__ = ("ok", "failure_reason", "message", "findings")

    def __init__(self, ok, failure_reason=None, message="", findings=()) -> None:
        self.ok = bool(ok)
        self.failure_reason = failure_reason
        self.message = message or ""
        self.findings = tuple(findings)

    def __repr__(self) -> str:
        if self.ok:
            return "MutationOutput(ok=True, findings=%d)" % len(self.findings)
        return "MutationOutput(ok=False, reason=%r, message=%r)" % (
            self.failure_reason,
            self.message,
        )


class SaveOutput:
    """Outcome of ``ProjectService.save`` / ``save_as``."""

    __slots__ = ("ok", "failure_reason", "message", "path")

    def __init__(self, ok, failure_reason=None, message="", path=None) -> None:
        self.ok = bool(ok)
        self.failure_reason = failure_reason
        self.message = message or ""
        self.path = path

    def __repr__(self) -> str:
        return "SaveOutput(ok=%r, path=%r)" % (self.ok, self.path)


class LoadOutput:
    """Outcome of ``ProjectService.open``.

    ``warnings`` carries schema-upgrade notices; ``findings`` the
    validation report computed at load (when a validator is installed);
    ``upgraded_from`` the schema version the file was migrated from.
    """

    __slots__ = ("ok", "failure_reason", "message", "project", "warnings", "findings", "upgraded_from")

    def __init__(self, ok, project=None, failure_reason=None, message="", warnings=(), findings=None, upgraded_from=None) -> None:
        self.ok = bool(ok)
        self.project = project
        self.failure_reason = failure_reason
        self.message = message or ""
        self.warnings = tuple(warnings)
        self.findings = findings
        self.upgraded_from = upgraded_from

    def __repr__(self) -> str:
        return "LoadOutput(ok=%r, warnings=%d)" % (self.ok, len(self.warnings))


class ConfigurationOutput:
    """Outcome of ``ValidationService.validate_base``."""

    __slots__ = ("ok", "failure_reason", "message", "report")

    def __init__(self, ok, report=None, failure_reason=None, message="") -> None:
        self.ok = bool(ok)
        self.report = report
        self.failure_reason = failure_reason
        self.message = message or ""

    def __repr__(self) -> str:
        return "ConfigurationOutput(ok=%r)" % self.ok


class VariantValidationOutput:
    """Outcome of ``ValidationService.validate_all``: base report, the
    per-variant reports, and the combined documents the checks ran on."""

    __slots__ = ("base_report", "variant_reports", "variant_documents", "base_document")

    def __init__(self, base_report, variant_reports=None, variant_documents=None, base_document=None) -> None:
        self.base_report = base_report
        self.variant_reports = dict(variant_reports or {})
        self.variant_documents = dict(variant_documents or {})
        self.base_document = base_document

    def __repr__(self) -> str:
        return "VariantValidationOutput(variants=%d)" % len(self.variant_reports)


class ExpandOutput:
    """Outcome of ``VariantService.expand`` / ``preview``."""

    __slots__ = ("ok", "failure_reason", "message", "variants")

    def __init__(self, ok, variants=(), failure_reason=None, message="") -> None:
        self.ok = bool(ok)
        self.variants = tuple(variants)
        self.failure_reason = failure_reason
        self.message = message or ""

    def __repr__(self) -> str:
        return "ExpandOutput(ok=%r, variants=%d)" % (self.ok, len(self.variants))


class ConfigurationPlan:
    """One planned input file, as plain data for review.

    ``payload_fingerprint`` is the SHA-256 of the exact bytes that will
    be written; ``action`` is ``create`` / ``overwrite`` / ``skip`` /
    ``conflict`` (plan §13.3).
    """

    __slots__ = ("variant_key", "path", "action", "payload_fingerprint")

    def __init__(self, variant_key, path, action, payload_fingerprint) -> None:
        self.variant_key = variant_key
        self.path = path
        self.action = action
        self.payload_fingerprint = payload_fingerprint

    def __repr__(self) -> str:
        return "ConfigurationPlan(%r, %s, %s)" % (self.variant_key, self.path, self.action)


class GenerationPlan:
    """Outcome of ``GenerationService.plan``.

    ``conflicts`` non-empty means nothing may be written; ``warnings``
    carries path-hazard notices for the user; ``manifest_data`` is the
    deterministic manifest payload (its ``run_info`` companion stays in
    ``output``'s hands until execution).
    """

    __slots__ = (
        "ok",
        "failure_reason",
        "message",
        "entries",
        "conflicts",
        "warnings",
        "manifest_data",
        "format_version",
        "project_name",
        "output_root",
    )

    def __init__(
        self,
        ok,
        entries=(),
        conflicts=(),
        warnings=(),
        manifest_data=None,
        format_version=None,
        project_name="",
        output_root="",
        failure_reason=None,
        message="",
    ) -> None:
        self.ok = bool(ok)
        self.entries = tuple(entries)
        self.conflicts = tuple(conflicts)
        self.warnings = tuple(warnings)
        self.manifest_data = manifest_data
        self.format_version = format_version
        self.project_name = project_name
        self.output_root = output_root
        self.failure_reason = failure_reason
        self.message = message or ""

    def __repr__(self) -> str:
        return "GenerationPlan(ok=%r, entries=%d, conflicts=%d)" % (
            self.ok,
            len(self.entries),
            len(self.conflicts),
        )


class PlanOutput:
    """Outcome of ``GenerationService.execute``."""

    __slots__ = ("ok", "failure_reason", "message", "written", "skipped", "copied_resources", "errors")

    def __init__(self, ok, written=(), skipped=(), copied_resources=(), errors=(), failure_reason=None, message="") -> None:
        self.ok = bool(ok)
        self.written = tuple(written)
        self.skipped = tuple(skipped)
        # Copied resource paths, like every other collection here, as a tuple.
        self.copied_resources = tuple(copied_resources)
        self.errors = tuple(errors)
        self.failure_reason = failure_reason
        self.message = message or ""

    def __repr__(self) -> str:
        return "PlanOutput(ok=%r, written=%d, errors=%d)" % (
            self.ok,
            len(self.written),
            len(self.errors),
        )
