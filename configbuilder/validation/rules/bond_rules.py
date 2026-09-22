"""Ligand / bond rule checks (spec §19 "Ligand / bond validation", spec §13)."""

from __future__ import annotations

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
    try:
        return record.ids.primary.value
    except Exception:
        return "<record>"


def _records_by_id(configuration: Configuration):
    """Primary-ID -> record map for endpoint resolution."""
    result = {}
    for record in configuration.records:
        key = _record_key(configuration, record)
        result.setdefault(key, record)
        for entity_id in record.ids:
            result.setdefault(entity_id.value, record)
    return result


def check_r_bnd_001(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Ions are ligands with a CCD code: the model has no ion entity type;
    every ion-as-ligand ComponentRecord must use ByCode (CCD), not SMILES."""
    for record in configuration.records:
        if isinstance(record, ComponentRecord) and isinstance(record.representation, ByNotation):
            key = _record_key(configuration, record)
            notation = record.representation.text
            # Single-atom or simple ionic notations are the classic ion case;
            # the contract says ions are CCD-coded ligands, so flag SMILES
            # forms that look like bare ions.
            stripped = notation.strip()
            if stripped and all(ch.isalpha() for ch in stripped) and stripped.isupper() and len(stripped) <= 3:
                _add(
                    report,
                    rule,
                    "Ion %r is represented as a SMILES ligand; ions are CCD-coded ligands in this contract." % key,
                    "SMILES %r looks like an element symbol" % stripped,
                    (FieldPath("ByNotation", key, "smiles"),),
                    suggestion="Use the CCD component code for the ion instead, e.g. %r." % stripped.capitalize(),
                )


def check_r_bnd_002(configuration: Configuration, report: Report, rule: Rule) -> None:
    """A SMILES-only ligand cannot be a bond endpoint (MAP-807)."""
    by_id = _records_by_id(configuration)
    for linkage in configuration.linkages:
        for endpoint in (linkage.a, linkage.b):
            record = by_id.get(endpoint.entity.value)
            if isinstance(record, ComponentRecord) and isinstance(record.representation, ByNotation):
                key = _record_key(configuration, record)
                _add(
                    report,
                    rule,
                    "A SMILES-only ligand cannot take part in an explicit bond.",
                    "endpoint %r (residue %d, atom %r) belongs to SMILES ligand %r"
                    % (endpoint.entity.value, endpoint.residue.value, endpoint.atom, key),
                    (FieldPath("LinkEndpoint", endpoint.entity.value, "bond"),),
                    suggestion="Represent the ligand by CCD code to bond it explicitly.",
                )


def check_r_bnd_003(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Bond endpoints resolve to entity/residue/atom triples: the entity ID
    must resolve through identity, the residue must be 1-based within the
    target (for polymers: within sequence length; for ligands: residue 1)."""
    registry = configuration.identity
    by_id = _records_by_id(configuration)
    for linkage in configuration.linkages:
        for endpoint in (linkage.a, linkage.b):
            if not registry.resolve(endpoint.entity):
                _add(
                    report,
                    rule,
                    "Bond endpoint %r does not resolve to any entity in the input." % endpoint.entity.value,
                    "entity %r, residue %d, atom %r unresolved"
                    % (endpoint.entity.value, endpoint.residue.value, endpoint.atom),
                    (FieldPath("LinkEndpoint", endpoint.entity.value, "bond"),),
                )
                continue
            record = by_id.get(endpoint.entity.value)
            if isinstance(record, (FamilyARecord, FamilyBRecord, FamilyCRecord)):
                length = len(record.sequence)
                if not (1 <= endpoint.residue.value <= length):
                    _add(
                        report,
                        rule,
                        "Bond residue %d lies outside the %d-residue sequence of %r."
                        % (endpoint.residue.value, length, endpoint.entity.value),
                        "endpoint residue %d out of range 1..%d" % (endpoint.residue.value, length),
                        (FieldPath("LinkEndpoint", endpoint.entity.value, "bond"),),
                    )
            elif isinstance(record, ComponentRecord) and endpoint.residue.value != 1:
                _add(
                    report,
                    rule,
                    "A single-residue ligand uses residue 1 for a bond endpoint.",
                    "endpoint on ligand %r uses residue %d" % (endpoint.entity.value, endpoint.residue.value),
                    (FieldPath("LinkEndpoint", endpoint.entity.value, "bond"),),
                )


def check_r_bnd_004(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Bond residue IDs are 1-based (single-residue ligand uses residue 1)."""
    for linkage in configuration.linkages:
        for endpoint in (linkage.a, linkage.b):
            if endpoint.residue.value < 1:
                _add(
                    report,
                    rule,
                    "Bond residue positions are 1-based.",
                    "endpoint on %r uses residue %d" % (endpoint.entity.value, endpoint.residue.value),
                    (FieldPath("ResidueRef", endpoint.entity.value, "bond"),),
                )


def check_r_bnd_005(configuration: Configuration, report: Report, rule: Rule) -> None:
    """All explicit bonds are covalent: the model has one Linkage type; the
    check re-affirms the type of every stored linkage."""
    for linkage in configuration.linkages:
        if type(linkage).__name__ != "Linkage":
            _add(
                report,
                rule,
                "Only covalent bonds are supported by the explicit bond field.",
                "linkage of unexpected type %r" % type(linkage).__name__,
                (FieldPath("Linkage", linkage.a.entity.value, "bond"),),
            )


def check_r_bnd_006(configuration: Configuration, report: Report, rule: Rule) -> None:
    """Polymer-polymer covalent bonds through this field are unsupported
    (DOCUMENTED)."""
    by_id = _records_by_id(configuration)
    for linkage in configuration.linkages:
        left = by_id.get(linkage.a.entity.value)
        right = by_id.get(linkage.b.entity.value)
        if isinstance(left, (FamilyARecord, FamilyBRecord, FamilyCRecord)) and isinstance(
            right, (FamilyARecord, FamilyBRecord, FamilyCRecord)
        ):
            _add(
                report,
                rule,
                "A bond between two polymer chains (%r and %r) is not supported by the explicit bond field."
                % (linkage.a.entity.value, linkage.b.entity.value),
                "both endpoints resolve to polymers",
                (FieldPath("Linkage", linkage.a.entity.value, "bond"),),
            )
