"""Entity rule checks (spec §19 "Entity validation").

Sequence alphabets, ligand representations, and cross-record uniqueness.
Position-within-sequence is R-ENT-007 (relational); family membership of
records is already guaranteed by the model's separate family types, so
R-ENT-001 re-affirms it structurally.
"""

from __future__ import annotations

from configbuilder.identity import DuplicateIdError, EntityId, IdentityError, IdentityRegistry
from configbuilder.model import (
    ByCode,
    ByNotation,
    ComponentRecord,
    Configuration,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
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


def _record_key(configuration: Configuration, record) -> str:
    """The registry key naming this record: its primary entity ID."""
    try:
        return record.ids.primary.value
    except Exception:
        return "<record>"


def check_r_ent_001(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Entity families are exactly protein/RNA/DNA/ligand: re-affirmed by
    type membership of the four families."""
    for record in configuration.records:
        if not isinstance(record, (FamilyARecord, FamilyBRecord, FamilyCRecord, ComponentRecord)):
            _add(
                report,
                rule,
                "Every entity must be a protein, RNA, DNA, or ligand record.",
                "record of unexpected type %r" % type(record).__name__,
                (FieldPath("Record"),),
            )


def check_r_ent_002(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Entity IDs are unique across the input including copy multiplicity.

    This is the DuplicateIdError conversion point (CHECKLIST.md Phase 4):
    the registry raises DuplicateIdError for an explicit taken-ID
    assignment; the engine catches it here and converts it to a finding —
    the registry never silently renames, and raw identity exceptions never
    reach the UI.
    """
    registry = configuration.identity
    seen = {}
    for record in configuration.records:
        for entity_id in record.ids:
            if entity_id.value in seen:
                _add(
                    report,
                    rule,
                    "Entity identifier %r is used more than once; every copy needs its own ID."
                    % entity_id.value,
                    "identifier %r appears in records %r and %r"
                    % (entity_id.value, seen[entity_id.value], record.ids),
                    (FieldPath("EntityId", entity_id.value, "id"),),
                    suggestion="Rename one of the records so every identifier is unique.",
                )
            else:
                seen[entity_id.value] = record.ids
    # Also surface registry-level duplicate refusals that occurred during
    # interactive construction (e.g. the wizard called assign() and was
    # refused): they are converted at this boundary per plan §8.1.
    for value in sorted(getattr(registry, "_pending_duplicate_refusals", ())):
        _add(
            report,
            rule,
            "Entity identifier %r is already in use; it must be changed, not reused." % value,
            "registry refused a duplicate assignment of %r" % value,
            (FieldPath("EntityId", value, "id"),),
        )


def check_r_ent_003(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Entity IDs are uppercase alphabetic (already enforced by EntityId at
    construction; re-affirmed over every record)."""
    for record in configuration.records:
        for entity_id in record.ids:
            if not entity_id.value.isalpha() or not entity_id.value.isupper():
                _add(
                    report,
                    rule,
                    "Entity identifiers must be uppercase letters (A-Z).",
                    "identifier %r is not uppercase alphabetic" % entity_id.value,
                    (FieldPath("EntityId", entity_id.value, "id"),),
                )


def check_r_ent_004(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Protein sequence is one-letter amino-acid alphabetic."""
    for record in configuration.records:
        if isinstance(record, FamilyARecord):
            text = record.sequence.text
            if not text or not all(ch.isalpha() and ch.isupper() for ch in text):
                _add(
                    report,
                    rule,
                    "A protein sequence must contain only one-letter amino-acid codes (A-Z).",
                    "protein sequence of %r contains invalid characters" % _record_key(configuration, record),
                    (FieldPath("SequenceText", _record_key(configuration, record), "protein.sequence"),),
                )


def check_r_ent_005(configuration: Configuration, report: Report, rule: Rule) -> None:
    """RNA sequence uses A, C, G, U."""
    for record in configuration.records:
        if isinstance(record, FamilyBRecord):
            text = record.sequence.text
            if any(ch not in "ACGU" for ch in text):
                _add(
                    report,
                    rule,
                    "An RNA sequence may only contain A, C, G, and U.",
                    "RNA sequence of %r contains characters outside ACGU"
                    % _record_key(configuration, record),
                    (FieldPath("SequenceText", _record_key(configuration, record), "rna.sequence"),),
                )


def check_r_ent_006(configuration: Configuration, report: Report, rule: Rule) -> None:
    """DNA sequence uses A, C, G, T."""
    for record in configuration.records:
        if isinstance(record, FamilyCRecord):
            text = record.sequence.text
            if any(ch not in "ACGT" for ch in text):
                _add(
                    report,
                    rule,
                    "A DNA sequence may only contain A, C, G, and T.",
                    "DNA sequence of %r contains characters outside ACGT"
                    % _record_key(configuration, record),
                    (FieldPath("SequenceText", _record_key(configuration, record), "dna.sequence"),),
                )


def check_r_ent_007(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Modification positions lie within the parent sequence (1-based)."""
    for record in configuration.records:
        if isinstance(record, (FamilyARecord, FamilyBRecord, FamilyCRecord)):
            length = len(record.sequence)
            key = _record_key(configuration, record)
            for modification in record.modifications:
                if modification.position.value > length:
                    _add(
                        report,
                        rule,
                        "Modification at position %d lies beyond the end of the %d-residue sequence."
                        % (modification.position.value, length),
                        "position %d out of range for sequence of length %d on record %r"
                        % (modification.position.value, length, key),
                        (
                            FieldPath(
                                "ModificationRecord",
                                key,
                                "position[%d]" % modification.position.value,
                            ),
                        ),
                        suggestion="Choose a position between 1 and %d." % length,
                    )


def check_r_ent_008(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Modification codes must not carry the CCD_ prefix (spec §8.1)."""
    for record in configuration.records:
        if isinstance(record, (FamilyARecord, FamilyBRecord, FamilyCRecord)):
            key = _record_key(configuration, record)
            for modification in record.modifications:
                code = modification.code.value.upper()
                if code.startswith("CCD_"):
                    _add(
                        report,
                        rule,
                        "Modification codes must not start with 'CCD_'.",
                        "modification on record %r uses code %r" % (key, code),
                        (FieldPath("ComponentCode", key, "ptmType"),),
                        suggestion="Use the plain CCD identifier, e.g. %r." % code[4:],
                    )


def check_r_ent_009(configuration: Configuration, report: Report, rule: Rule) -> None:
    """A ligand has exactly one of CCD codes or SMILES: guaranteed by the
    ByCode/ByNotation sum type; re-affirmed over ComponentRecords."""
    for record in configuration.records:
        if isinstance(record, ComponentRecord):
            if not isinstance(record.representation, (ByCode, ByNotation)):
                _add(
                    report,
                    rule,
                    "A ligand needs exactly one of a component code or a SMILES string.",
                    "representation type %r" % type(record.representation).__name__,
                    (FieldPath("ComponentRecord", _record_key(configuration, record), "ligand"),),
                )


def check_r_ent_010(configuration: Configuration, report: Report, rule: Rule, context=None) -> None:
    """SMILES parses — with a probe: ERROR when it does not; without one:
    WARNING 'not checked' (plan §9.6)."""
    from configbuilder.validation.catalogue import Severity
    from configbuilder.validation.engine import ValidationContext
    from configbuilder.validation.ports import NullChemistryProbe

    probe = context.chemistry if isinstance(context, ValidationContext) else None
    for record in configuration.records:
        if isinstance(record, ComponentRecord) and isinstance(record.representation, ByNotation):
            key = _record_key(configuration, record)
            if probe is None or not probe.parses_smiles(record.representation.text):
                if probe is None or isinstance(probe, NullChemistryProbe):
                    # Probe-less runs report "not checked" as a WARNING —
                    # never as an ERROR (plan §9.6).
                    report.add(
                        Finding(
                            rule_id=rule.rule_id,
                            severity=Severity.WARNING,
                            user_message=(
                                "The SMILES notation of ligand %r was not checked: no chemistry checker is available."
                                % key
                            ),
                            diagnostic="SMILES text %r; probe unavailable" % record.representation.text,
                            paths=(FieldPath("ByNotation", key, "smiles"),),
                            suggestion="Install a chemistry checker to have SMILES validated.",
                        )
                    )
                else:
                    _add(
                        report,
                        rule,
                        "The SMILES notation of ligand %r could not be parsed." % key,
                        "SMILES text %r failed to parse" % record.representation.text,
                        (FieldPath("ByNotation", key, "smiles"),),
                    )
