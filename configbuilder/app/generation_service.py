"""Generation (IMPLEMENTATION_PLAN.md §15): ``GenerationService``.

The generation sequence is fixed in exactly one place, in this order:

1. Validate the base. Stop on ``ERROR``.
2. Expand variants.
3. Validate each variant, including the drift check.
4. Transform each variant.
5. Encode each wire document.
6. Build the output plan, including collision detection and the manifest
   payload.

Everything before ``execute`` is pure planning (plan §13.3): nothing is
written without a plan, and ``execute`` performs writes only — it does
not re-derive content, so what the user reviewed is exactly what is
written. The service returns result objects and writes nothing itself
(plan §5.3 rule 8: filesystem access is confined to ``output`` and
``persistence``).

Two wire-level agreements happen between steps 4 and 5, both through
``transform`` so wire vocabulary never leaks into ``app`` (plan §10.1):

- the job ``name`` field carries the same derived name the directory
  and filename use (plan §13.2) — via ``transform.with_wire_job_name``;
- external resource paths are rewritten to their emitted forms (§13.5
  path policies) — via ``transform.with_emitted_resource_paths``.

Validation (steps 1 and 3) runs on the semantic documents; the
rewrites happen afterwards, so the drift comparison never sees them.
The manifest joins the plan as an ordinary planned file (§13.1): same
overwrite policy, atomic write, part of the reviewed layout.
"""

from __future__ import annotations

import os

from configbuilder.app.results import (
    ConfigurationPlan,
    FailureReason,
    GenerationPlan,
    PlanOutput,
)
from configbuilder.output import (
    OverwritePolicy,
    PathPolicy,
    PlanEntry,
    build_manifest,
    plan as plan_output,
    slug as slug_name,
)
from configbuilder.output.execute import execute as execute_plan
from configbuilder.output.naming import (
    variant_directory_name,
    variant_file_name,
)
from configbuilder.output.plan import fingerprint
from configbuilder.persistence import OutputSettings
from configbuilder.serialize import encode
from configbuilder.transform import (
    TransformError,
    to_wire,
    with_emitted_resource_paths,
    with_wire_job_name,
)
from configbuilder.validation import Report
from configbuilder.variants import describe_edit

__all__ = ["GenerationService"]

_MANIFEST_FILE_NAME = "manifest.json"


class GenerationService:
    """Runs the fixed generation sequence; hands the reviewed plan to
    ``output`` for execution."""

    def __init__(self, projects, validation, variants, filesystem=None) -> None:
        self._projects = projects
        self._validation = validation
        self._variants = variants
        # An ``output.FileView`` (read-only) for planning; ``None`` means
        # the real filesystem — exactly ``plan``'s own default.
        self._filesystem = filesystem
        self._reviewed = None  # the OutputPlan behind the last successful plan()

    # -- the fixed sequence (§15) ------------------------------------------------

    def show_json(self, key: str = None):
        """The encoded JSON text for the base (``key=None``) or one variant.

        Display-only: it runs the same ``to_wire`` → ``encode`` path the
        export uses, so what the user sees is byte-for-byte what a file
        would contain (plan §15's single-serialization discipline). No
        state changes. Returns ``(text, None)`` on success or
        ``(None, message)`` when nothing can be shown.
        """
        project = self._projects._require_project()
        if project is None:
            return None, "no project is open"
        if key is None:
            selection = (("base", project.configuration),)
        else:
            previewed = self._variants.preview(key)
            if not previewed.ok:
                return None, previewed.message or "no variant keyed %r" % (key,)
            selection = tuple(
                (variant.key, variant.configuration)
                for variant in previewed.variants
            )
        try:
            for _name, configuration in selection:
                document = to_wire(configuration).document
                return encode(document).decode("utf-8"), None
        except TransformError as error:
            return None, str(error)
        return None, "nothing to show"

    def plan(self, output_root: str, overwrite_policy=None, path_policy=None, only=None) -> GenerationPlan:
        """Steps 1–6 in exactly this order. Nothing is written here.

        ``only`` (an iterable of variant keys) restricts the run to that
        subset — the selected-export route. The manifest and job names
        are derived from exactly the variants written, so a subset run is
        self-consistent.
        """
        project = self._projects._require_project()
        if project is None:
            return GenerationPlan(
                ok=False,
                failure_reason=FailureReason.NOT_OPEN,
                message="no project is open",
            )

        # Step 1: validate the base. Stop on ERROR.
        base_validation = self._validation.validate_base()
        if not base_validation.ok:
            return GenerationPlan(
                ok=False,
                failure_reason=FailureReason.VALIDATION_BLOCKED,
                message="the base configuration has blocking findings; generate cannot start",
                findings=tuple(base_validation.report.findings),
            )

        # Step 2: expand variants (the base is not implicitly included; §12.2).
        expansion = self._variants.expand(only=only)
        if not expansion.ok:
            return GenerationPlan(
                ok=False,
                failure_reason=expansion.failure_reason,
                message=expansion.message,
            )
        variants = expansion.variants
        if not variants:
            return GenerationPlan(
                ok=False,
                failure_reason=FailureReason.EMPTY_EXPANSION,
                message="there are no variants to generate; add a variant first",
            )

        # Step 3: validate every selected variant, including the drift check.
        # Runs on the semantic documents; the §13.2/§13.5 rewrites happen
        # afterwards, so the comparison data never contains them (attribution
        # by design).
        variant_validation = self._validation.validate_all(only=only)
        if variant_validation.base_report.blocking():
            return GenerationPlan(
                ok=False,
                failure_reason=FailureReason.VALIDATION_BLOCKED,
                message="the base configuration has blocking findings; generate cannot start",
                findings=tuple(variant_validation.base_report.findings),
            )
        combined = Report()
        combined.add_all(base_validation.report.findings)
        blocking_variants = sorted(
            key
            for key, report in variant_validation.variant_reports.items()
            if report.blocking()
        )
        for key in sorted(variant_validation.variant_reports):
            combined.add_all(variant_validation.variant_reports[key].findings)
        if blocking_variants:
            return GenerationPlan(
                ok=False,
                failure_reason=FailureReason.VALIDATION_BLOCKED,
                message="variant %s has blocking findings; nothing will be written"
                % ", ".join(blocking_variants),
            )

        # Step 4: transform each variant, applying the §13.2 name agreement.
        settings = project.settings or OutputSettings()
        overwrite = (
            OverwritePolicy(settings.overwrite_policy)
            if overwrite_policy is None
            else overwrite_policy
        )
        path_choice = (
            PathPolicy(settings.path_policy) if path_policy is None else path_policy
        )
        project_name = project.configuration.metadata.name
        project_slug = slug_name(project_name)

        try:
            base_result = to_wire(project.configuration)
            base_fingerprint = fingerprint(encode(base_result.document))
            documents = {}
            format_versions = {}
            requirements_by_key = {}
            for variant in variants:
                result = to_wire(variant.configuration)
                documents[variant.key] = with_wire_job_name(
                    result.document,
                    variant_directory_name(project_slug, variant.key),
                )
                format_versions[variant.key] = result.version
                requirements_by_key[variant.key] = result.external_resources
        except TransformError as error:
            return GenerationPlan(
                ok=False,
                failure_reason=FailureReason.TRANSFORM_FAILED,
                message=str(error),
            )

        # §13.5 resolution (a planning input to step 5): the emitted path
        # forms must be known before encoding, so a first pure planning pass
        # resolves them — same collision detection, same resource rows. The
        # final pass then decides actions from the real payload bytes.
        probe_plan = plan_output(
            {key: b"" for key in documents},
            output_root,
            project_name,
            overwrite_policy=overwrite,
            path_policy=path_choice,
            resources_by_variant=requirements_by_key,
            filesystem=self._filesystem,
        )
        emitted = {}
        for resource in probe_plan.resources:
            if (
                resource.emitted_path is not None
                and resource.raw_path != resource.emitted_path
            ):
                emitted.setdefault(resource.wire_field, {})[resource.raw_path] = (
                    resource.emitted_path
                )
        documents = {
            key: with_emitted_resource_paths(documents[key], emitted)
            for key in documents
        }

        # Step 5: encode each wire document (the serializer's fixed policy).
        payloads = {key: encode(documents[key]) for key in documents}

        # Step 6: the output plan — collision detection over real payloads
        # (resource rows resolve identically to the probe) and the manifest
        # payload (§13.6).
        planned = plan_output(
            payloads,
            output_root,
            project_name,
            overwrite_policy=overwrite,
            path_policy=path_choice,
            resources_by_variant=requirements_by_key,
            filesystem=self._filesystem,
        )

        variant_records = []
        for variant in variants:
            key = variant.key
            file_name = variant_file_name(project_slug, key)
            entry = _entry_by_file_name(planned, file_name)
            variant_records.append(
                {
                    "key": key,
                    "label": variant.label,
                    "declared_factors": list(variant.lineage.declared_factors),
                    "applied_edits": [
                        describe_edit(edit) for edit in variant.lineage.applied_edits
                    ],
                    "file_name": file_name,
                    "fingerprint": (
                        entry.payload_fingerprint if entry is not None else ""
                    ),
                }
            )
        manifest = build_manifest(
            project_name=project_name,
            base_fingerprint=base_fingerprint,
            format_version=max(format_versions.values()),
            variants=variant_records,
            seed_set=list(project.configuration.seeds.values),
            validation_report=combined,
            path_policy=path_choice,
            overwrite_policy=overwrite,
            format_target=project.configuration.format_target,
        )
        manifest_payload = encode(manifest.data)

        # The manifest joins the plan as an ordinary planned file (§13.1):
        # it lands at ``<output_root>/<project_slug>/manifest.json``, is
        # subject to the same overwrite policy, and is written atomically
        # by the same executor (§13.3, §13.4).
        manifest_path = os.path.join(output_root, project_slug, _MANIFEST_FILE_NAME)
        manifest_path, manifest_action, manifest_exists = _manifest_decision(
            manifest_payload, overwrite, self._filesystem, manifest_path
        )
        manifest_entry = PlanEntry(
            manifest_path, manifest_action, manifest_payload, manifest_exists
        )
        planned = _plan_with_manifest(planned, manifest_entry)

        self._reviewed = planned
        if planned.conflicts:
            return GenerationPlan(
                ok=False,
                failure_reason=FailureReason.NO_PATH,
                message="the plan has conflicts; nothing will be written",
                conflicts=tuple(planned.conflicts),
                warnings=tuple(planned.warnings),
                output_root=output_root,
                project_name=project_name,
            )

        # The review surface: every variant file plus the manifest (its
        # ``variant_key`` is None — the manifest summarises the run). What
        # the user reviewed is exactly what ``execute`` writes.
        variant_count = len(variant_records)
        entries = tuple(
            ConfigurationPlan(
                record["key"],
                entry.path,
                entry.action,
                entry.payload_fingerprint,
            )
            for record, entry in zip(variant_records, planned.entries[:variant_count])
        ) + (
            ConfigurationPlan(
                None,
                manifest_entry.path,
                manifest_entry.action,
                manifest_entry.payload_fingerprint,
            ),
        )
        return GenerationPlan(
            ok=True,
            entries=entries,
            conflicts=(),
            warnings=tuple(planned.warnings),
            manifest_data=manifest,
            format_version=max(format_versions.values()),
            project_name=project_name,
            output_root=output_root,
        )

    # -- execution (§15: writes only) --------------------------------------------

    def execute(self, generation_plan: GenerationPlan) -> PlanOutput:
        """Write what was reviewed. Nothing here re-derives content: the
        payloads live inside the plan ``plan()`` produced."""
        if generation_plan is None or not generation_plan.ok:
            return PlanOutput(
                ok=False,
                failure_reason=FailureReason.NO_PATH,
                message="execute needs a successful plan; run plan() first",
            )
        if self._reviewed is None:
            return PlanOutput(
                ok=False,
                failure_reason=FailureReason.NO_PATH,
                message="no reviewed plan is held; run plan() first",
            )
        planned = self._reviewed
        if planned.conflicts:
            return PlanOutput(
                ok=False,
                failure_reason=FailureReason.NO_PATH,
                message="the plan has conflicts; nothing was written",
                errors=tuple(planned.conflicts),
            )
        result = execute_plan(planned)
        written = tuple(
            outcome.path for outcome in result.outcomes if outcome.written
        )
        skipped = tuple(
            outcome.path for outcome in result.outcomes if not outcome.written
        )
        return PlanOutput(
            ok=not result.errors,
            written=written,
            skipped=skipped,
            copied_resources=tuple(result.copied_resources),
            errors=tuple(result.errors),
        )


# -- module helpers ------------------------------------------------------------------


def _entry_by_file_name(planned, file_name: str):
    """The planned entry whose file name matches ``file_name`` (paths are
    platform-joined, so compare the basename)."""
    for entry in planned.entries:
        if os.path.basename(entry.path) == file_name:
            return entry
    return None


def _manifest_decision(payload: bytes, overwrite_policy, filesystem, path):
    """The manifest follows the same §13.3 action table as any planned
    file — delegated to ``output.plan.decide_action``, the single home of
    that decision."""
    from configbuilder.output.plan import decide_action

    if filesystem is None:
        from configbuilder.output.plan import OsFileView

        filesystem = OsFileView()
    return decide_action(path, payload, overwrite_policy, filesystem)


def _plan_with_manifest(planned, manifest_entry):
    """The plan with the manifest entry appended (manifest last: it
    summarises the run, so it sorts after the variant directories)."""
    from configbuilder.output.plan import OutputPlan

    return OutputPlan(
        project_slug=planned.project_slug,
        output_root=planned.output_root,
        overwrite_policy=planned.overwrite_policy,
        path_policy=planned.path_policy,
        entries=tuple(planned.entries) + (manifest_entry,),
        resources=planned.resources,
        conflicts=planned.conflicts,
        warnings=planned.warnings,
    )
