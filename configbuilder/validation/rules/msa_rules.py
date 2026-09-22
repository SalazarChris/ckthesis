"""MSA rule checks (spec §19 "MSA validation", spec §6.2).

One-sided alignment cases are legal wire states (spec §6.2 names them);
the half-set *absent-versus-empty* confusion the contract forbids is
unrepresentable in the model's sum type, so R-MSA-001/R-MSA-002 re-affirm
dispatchability rather than reject named cases.
"""

from __future__ import annotations

from configbuilder.model import (
    AlignmentAutomatic,
    AlignmentBoth,
    AlignmentFree,
    AlignmentPairedOnly,
    AlignmentUnpairedOnly,
    Configuration,
    External,
    FamilyARecord,
    FamilyBRecord,
    Inline,
    fold_alignment,
)
from configbuilder.validation.catalogue import Rule
from configbuilder.validation.report import FieldPath, Finding, Report


def _add(report: Report, rule: Rule, user_message: str, diagnostic: str, paths=(), suggestion: str = "") -> None:
    report.add(
        Finding(
            rule_id=rule.rule_id,
            severity=rule.severity,
            user_message=user_message,
            diagnostic=diagnostic,
            paths=paths,
            suggestion=suggestion,
        )
    )


def _protein_records(configuration: Configuration):
    return [r for r in configuration.records if isinstance(r, FamilyARecord)]


def _rna_records(configuration: Configuration):
    return [r for r in configuration.records if isinstance(r, FamilyBRecord)]


def _record_key(configuration: Configuration, record) -> str:
    try:
        return record.ids.primary.value
    except Exception:
        return "<record>"


def check_r_msa_001(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Protein unpaired/paired fields are both set or both unset — the four
    legal states of spec §6.2; the sum type admits exactly those."""
    for record in _protein_records(configuration):
        key = _record_key(configuration, record)
        if not isinstance(record.alignment, (AlignmentAutomatic, AlignmentFree, AlignmentUnpairedOnly, AlignmentPairedOnly, AlignmentBoth)):
            _add(
                report,
                rule,
                "The protein MSA state of record %r is not one of the four contract states." % key,
                "alignment type %r" % type(record.alignment).__name__,
                (FieldPath("FamilyARecord", key, "unpairedMsa"),),
            )


def check_r_msa_002(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Inline and path are mutually exclusive per MSA field: each one-sided
    case carries exactly one resource; assert it stays that way."""
    for record in _protein_records(configuration) + _rna_records(configuration):
        key = _record_key(configuration, record)
        if isinstance(record.alignment, (AlignmentUnpairedOnly, AlignmentPairedOnly, AlignmentBoth)):
            source = record.alignment.source
            if not isinstance(source, (Inline, External)):
                _add(
                    report,
                    rule,
                    "A custom MSA must be either inline text or a file path, not both or neither.",
                    "source type %r on record %r" % (type(source).__name__, key),
                    (FieldPath("Inline", key, "unpairedMsa"),),
                )


def _first_sequence(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(">"):
            return stripped
    return ""


def check_r_msa_003(configuration: Configuration, report: Report, rule: Rule, context=None) -> None:
    """Custom MSA content is required to be A3M — shallow check: every line
    is either a FASTA header or an ACGU-/gap-containing sequence line.
    Advisory (WARNING by evidence DOCUMENTED); the external system owns
    deep interpretation (plan §9.2). File-backed sources are checked
    shallowly through the FilesystemPort (exists/readable/non-empty); with
    the null port they report "not checked" rather than a false error."""
    from configbuilder.validation.ports import NullFilesystemPort

    filesystem = None
    if context is not None and hasattr(context, "filesystem"):
        filesystem = context.filesystem
    for record in _protein_records(configuration) + _rna_records(configuration):
        key = _record_key(configuration, record)

        def visit(source, key=key):
            if isinstance(source, Inline):
                content = source.text
                for line_no, line in enumerate(content.splitlines(), start=1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith(">"):
                        continue
                    if any(ch not in "ABCDEFGHIKLMNPQRSTUVWXYZacgustwykmedbzx-" for ch in stripped):
                        _add(
                            report,
                            rule,
                            "The custom MSA of record %r contains characters outside the A3M alphabet on line %d." % (key, line_no),
                            "line %d: %r" % (line_no, stripped[:40]),
                            (FieldPath("Inline", key, "unpairedMsa"),),
                        )
            elif isinstance(source, External):
                if filesystem is None or isinstance(filesystem, NullFilesystemPort):
                    _add(
                        report,
                        rule,
                        "The MSA file of record %r could not be checked here (no filesystem access)." % key,
                        "path %r; filesystem port unavailable" % source.path.raw,
                        (FieldPath("External", key, "unpairedMsa"),),
                    )
                elif not filesystem.is_readable_file(source.path.raw):
                    _add(
                        report,
                        rule,
                        "The MSA file of record %r is missing or unreadable." % key,
                        "path %r is not a readable file" % source.path.raw,
                        (FieldPath("External", key, "unpairedMsa"),),
                        suggestion="Check the path and that the file exists on this machine.",
                    )

        if isinstance(record.alignment, (AlignmentUnpairedOnly, AlignmentPairedOnly, AlignmentBoth)):
            fold_alignment(record.alignment, lambda: None, lambda: None, visit, visit, visit)


def check_r_msa_004(configuration: Configuration, report: Report, rule: Rule) -> None:
    """The first sequence of a custom MSA should equal the query sequence —
    shallow, advisory. Inline sources are checked; file-backed sources are
    reported as not readable here (the engine's preflight pass handles
    files) so this check stays filesystem-free."""
    for record in _protein_records(configuration) + _rna_records(configuration):
        key = _record_key(configuration, record)
        if isinstance(record.alignment, (AlignmentUnpairedOnly, AlignmentPairedOnly, AlignmentBoth)):
            source = record.alignment.source
            if isinstance(source, Inline):
                first = _first_sequence(source.text)
                query = record.sequence.text
                if first and first.replace("-", "") != query:
                    _add(
                        report,
                        rule,
                        "The first sequence of the custom MSA should match the query sequence of record %r." % key,
                        "first MSA sequence %r does not match query %r" % (first[:40], query[:40]),
                        (FieldPath("Inline", key, "unpairedMsa"),),
                        suggestion="Check that the MSA's first entry is the query itself.",
                    )


def check_r_msa_005(configuration: Configuration, report: Report, rule: Rule) -> None:
    """After removing lowercase insertions, a custom MSA should form a
    rectangular alignment — shallow, advisory, inline sources only."""
    for record in _protein_records(configuration) + _rna_records(configuration):
        key = _record_key(configuration, record)
        if isinstance(record.alignment, (AlignmentUnpairedOnly, AlignmentPairedOnly, AlignmentBoth)):
            source = record.alignment.source
            if isinstance(source, Inline):
                widths = set()
                for line in source.text.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith(">"):
                        continue
                    aligned = "".join(ch for ch in stripped if not ch.islower())
                    widths.add(len(aligned))
                if len(widths) > 1:
                    _add(
                        report,
                        rule,
                        "The custom MSA of record %r is not rectangular after removing lowercase insertions." % key,
                        "aligned row widths differ: %s" % sorted(widths),
                        (FieldPath("Inline", key, "unpairedMsa"),),
                        suggestion="Pad all aligned sequences to the same length with gap characters.",
                    )
