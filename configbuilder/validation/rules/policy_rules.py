"""Version-selection and INFO-only policy rule checks (plan §10.3, spec §14,
spec §19 final section).

Policy rules (R-POL-*) always emit their informational finding: they exist
so a non-rule can never silently turn into a gate (plan §9.3).
"""

from __future__ import annotations

from configbuilder.model import (
    Auto,
    Configuration,
    Pinned,
    Unverified,
)
from configbuilder.validation.catalogue import Rule, Severity
from configbuilder.validation.report import FieldPath, Finding, Report


def _add(
    report: Report,
    rule: Rule,
    user_message: str,
    diagnostic: str,
    paths=(),
    suggestion: str = "",
    severity=None,
) -> None:
    report.add(
        Finding(
            rule_id=rule.rule_id,
            severity=severity if severity is not None else rule.severity,
            user_message=user_message,
            diagnostic=diagnostic,
            paths=paths,
            suggestion=suggestion,
        )
    )


def check_r_ver_001(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Generation is blocked until an explicit format version has been
    supplied (Unverified is the blocking state); the version is never
    inferred from documentation, examples, releases, or defaults."""
    if isinstance(configuration.format_target.version_selection, Unverified):
        _add(
            report,
            rule,
            "Generation is blocked: no format version has been verified against the deployment.",
            "version selection is Unverified (no explicit verified target supplied)",
            (FieldPath("Unverified", None, "version_selection"),),
            suggestion="Pin a version verified against the deployment, citing its evidence record.",
        )


def check_r_ver_002(configuration: Configuration, report: Report, rule: Rule) -> None:
    """A pin must carry its verification provenance in the model, and Auto
    must only span evidenced versions; the version is never silently raised
    and never inferred. The evidence reference (e.g. a ``PIN-nnn`` record)
    is supplied by the operator — the runtime does not read any document to
    obtain it. Wire-level feature comparison runs in transform; this rule
    checks the provenance that travels with the selection."""
    selection = configuration.format_target.version_selection
    if isinstance(selection, Pinned):
        # The pin itself is the operator's explicit choice; an evidence
        # reference is optional recorded provenance, never a condition for
        # generating output.
        pass
    elif isinstance(selection, Auto):
        if not selection.evidenced:
            _add(
                report,
                rule,
                "The automatic version selection includes no evidenced versions.",
                "Auto has an empty evidenced set",
                (FieldPath("Auto", None, "version_selection"),),
            )


def check_r_pol_001(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Seed-list uniqueness is project policy: report duplicates as INFO."""
    values = configuration.seeds.values
    seen = set()
    duplicates = sorted({v for v in values if v in seen or seen.add(v)})
    if duplicates:
        _add(
            report,
            rule,
            "The seed list contains duplicate values (allowed; uniqueness is a project policy, not a requirement).",
            "duplicated seed values: %s" % duplicates,
            (FieldPath("SeedSet", None, "modelSeeds"),),
        )


def check_r_pol_002(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Seed ordering is preserved as given; sorting is a project choice."""
    values = configuration.seeds.values
    if list(values) != sorted(values):
        _add(
            report,
            rule,
            "The seed list is not sorted (allowed; order is preserved exactly as given).",
            "seed order %s" % (list(values),),
            (FieldPath("SeedSet", None, "modelSeeds"),),
        )


def check_r_pol_003(configuration: Configuration, report: Report, rule: Rule) -> None:
    """The chain-ID allocation algorithm is a project choice; report the
    registry's allocation shape for transparency."""
    _add(
        report,
        rule,
        "Chain identifiers were allocated by the project's deterministic allocator (this is a project choice, not a contract rule).",
        "registry holds %d identifiers" % len(configuration.identity.order()),
    )


def check_r_pol_004(configuration: Configuration, report: Report, rule: Rule) -> None:
    """The fixed set of 10 seeds is a comparison policy."""
    count = len(configuration.seeds)
    if count != 10:
        _add(
            report,
            rule,
            "The project's comparison policy fixes 10 model seeds (not an AF3 requirement).",
            "seed count is %d" % count,
            (FieldPath("SeedSet", None, "modelSeeds"),),
        )


def check_r_pol_005(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Biological validity of a requested modification site is out of scope."""
    _add(
        report,
        rule,
        "The biological validity of requested modification sites is not checked (out of scope).",
        "INFO-only rule; spec §21 non-goals",
    )


def check_r_pol_006(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Scientific plausibility of a modification is out of scope."""
    _add(
        report,
        rule,
        "The scientific plausibility of modifications is not checked (out of scope).",
        "INFO-only rule; spec §21 non-goals",
    )


def check_r_pol_007(configuration: Configuration, report: Report, rule: Rule, context=None) -> None:
    """Seed-set stability across variants (spec §15 factor 2): a variant that
    changes the shared seed set is an experiment-design hazard — the seed
    sets stop being comparable. Reported per policy severity."""
    base_seeds = list(configuration.seeds.values)
    variant_seeds = getattr(context, "variant_seeds", None) if context is not None else None
    if not variant_seeds:
        _add(
            report,
            rule,
            "Seed-set stability is reported per variant as a project policy; no variants were provided.",
            "base seed set: %s" % (base_seeds,),
            (FieldPath("SeedSet", None, "modelSeeds"),),
        )
        return
    for key in sorted(variant_seeds):
        if list(variant_seeds[key]) != base_seeds:
            _add(
                report,
                rule,
                "Variant %r changes the seed set; the model sets will no longer be comparable."
                % key,
                "base %s vs variant %s" % (base_seeds, list(variant_seeds[key])),
                (FieldPath("SeedSet", key, "modelSeeds"),),
                suggestion="Keep the shared seed set identical across variants being compared.",
            )
    if not any(list(variant_seeds[key]) != base_seeds for key in variant_seeds):
        _add(
            report,
            rule,
            "The seed set is identical across all provided variants (comparable).",
            "base seed set: %s" % (base_seeds,),
            (FieldPath("SeedSet", None, "modelSeeds"),),
        )
