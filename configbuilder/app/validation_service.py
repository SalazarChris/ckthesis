"""Validation façade (IMPLEMENTATION_PLAN.md §15): ``ValidationService``.

``validate_base`` runs the full catalogue over the open configuration;
``validate_all`` additionally validates every expanded variant with the
drift and identity-stability checks wired up (the comparison data join
plan §9.6 requires); ``set_policy`` adjusts the adjustable severities.
"""

from __future__ import annotations

from configbuilder.app.results import FailureReason, ConfigurationOutput, VariantValidationOutput
from configbuilder.transform import to_wire
from configbuilder.validation import ValidationContext
from configbuilder.variants import expand, declared_changes

__all__ = ["ValidationService"]


class ValidationService:
    """Runs validation over the open project, base and variants."""

    def __init__(self, projects, filesystem=None, chemistry=None, run_preflight=True) -> None:
        self._projects = projects
        self._filesystem = filesystem
        self._chemistry = chemistry
        self._run_preflight = run_preflight

    def _configuration(self):
        project = self._projects._require_project()
        return project.configuration if project is not None else None

    def _context(self, base_document=None, variants=()):
        """The join point: validation stays independent of transform and
        variants (plan §5.3 rule 2), so ``app`` hands it the comparison
        data as plain values."""
        context = ValidationContext(
            filesystem=self._filesystem,
            chemistry=self._chemistry,
            run_preflight=self._run_preflight,
        )
        if base_document is not None:
            context.base_document = base_document
            context.variant_documents = {
                variant.key: to_wire(variant.configuration).document for variant in variants
            }
            context.variant_declared_changes = {
                spec.key: declared_changes(spec) for spec in self._projects._specs()
            }
            context.variant_registries = {
                variant.key: variant.configuration.identity for variant in variants
            }
            context.variant_seeds = {
                variant.key: list(variant.configuration.seeds.values) for variant in variants
            }
        return context

    def validate_base(self) -> ConfigurationOutput:
        configuration = self._configuration()
        if configuration is None:
            return ConfigurationOutput(
                ok=False,
                failure_reason=FailureReason.NOT_OPEN,
                message="no project is open",
            )
        report = self._projects._require_project() and None
        from configbuilder.validation import validate

        report = validate(configuration, self._context())
        return ConfigurationOutput(ok=not report.blocking(), report=report)

    def validate_all(self, only=None) -> VariantValidationOutput:
        """Validate the base and every expanded variant (§15 step 3).

        ``only`` (an iterable of keys) restricts the variant half to that
        subset — the subset-export route shares it. The base is always
        validated: every variant derives from it.

        The variant checks need wire documents; building them here costs
        one transform per variant, which ``GenerationService.plan``
        reuses instead of recomputing (its documents come from the same
        pure function, so the results are identical).
        """
        project = self._projects._require_project()
        if project is None:
            return VariantValidationOutput(
                ConfigurationOutput(
                    ok=False,
                    failure_reason=FailureReason.NOT_OPEN,
                    message="no project is open",
                )
            )
        from configbuilder.validation import validate

        base_report = validate(project.configuration, self._context())
        if base_report.blocking():
            return VariantValidationOutput(base_report)
        specs = project.specs
        if only is not None:
            keys = tuple(only)
            known = {spec.key for spec in specs}
            unknown = [key for key in keys if key not in known]
            if unknown:
                return VariantValidationOutput(
                    ConfigurationOutput(
                        ok=False,
                        failure_reason=FailureReason.UNKNOWN_RECORD,
                        message="no variant keyed %r exists" % (unknown[0],),
                    )
                )
            specs = tuple(spec for key in keys for spec in specs if spec.key == key)
        variants = expand(project.configuration, specs)
        base_document = to_wire(project.configuration).document
        variant_documents = {variant.key: to_wire(variant.configuration).document for variant in variants}
        # Each variant is validated against a context that carries only
        # its own comparison data and the base's: the engine runs one
        # ``validate`` call per variant configuration, and the VARIANT-
        # tier rules describe every document in the context they see. A
        # shared context would attribute sibling variants' differences
        # to each report (the batch-generation bug) — per-variant
        # contexts keep every report about its own variant.
        declared_by_key = {spec.key: declared_changes(spec) for spec in specs}
        variant_reports = {}
        for variant in variants:
            context = self._context()
            context.base_document = base_document
            context.base_registry = project.configuration.identity
            context.variant_documents = {variant.key: variant_documents[variant.key]}
            context.variant_declared_changes = {variant.key: declared_by_key[variant.key]}
            context.variant_registries = {variant.key: variant.configuration.identity}
            context.variant_seeds = {variant.key: list(variant.configuration.seeds.values)}
            variant_reports[variant.key] = validate(variant.configuration, context)
        return VariantValidationOutput(
            base_report,
            variant_reports,
            variant_documents,
            base_document,
        )

    def set_policy(self, **policy) -> None:
        """Adjust the adjustable severities (plan §9.4): ``run_preflight``
        is the switch the catalogue documents."""
        if "run_preflight" in policy:
            self._run_preflight = bool(policy["run_preflight"])
