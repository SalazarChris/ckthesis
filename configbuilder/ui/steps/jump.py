"""Jump-to-field resolution (plan §16.6, §18.8 step-machine tier).

``FieldPath`` is typed, so the step machine can compute which step and
prompt corresponds to a finding. Typing a finding's reference number
navigates there directly — the terminal equivalent of clicking an
error. The mapping covers every ``FieldPath`` variant the rules emit;
an unmapped type raises, so a new rule with a new locator type breaks
this table loudly instead of dead-ending the user (plan §16.6).
"""

from __future__ import annotations

from configbuilder.ui.steps.machine import StepId

__all__ = ["resolve_step_for_field_path", "resolve_step_for_finding", "JUMP_TABLE"]


# type_name -> step that prompts for that field (plan §16.1 step table).
# ``record_key`` narrows within the step (the molecules step edits the
# record the finding points at); ``field`` selects the prompt within it.
JUMP_TABLE = {
    # Root and metadata
    "Configuration": "validate",
    "ConfigurationMetadata": "job_details",
    "SeedSet": "reproducibility",
    "Dialect": "job_details",
    "FormatTarget": "job_details",
    "Unverified": "job_details",
    "Pinned": "job_details",
    "Auto": "job_details",
    # Records and their parts
    "Record": "molecules",
    "FamilyARecord": "molecules",
    "FamilyBRecord": "molecules",
    "FamilyCRecord": "molecules",
    "ComponentRecord": "components",
    "ModificationRecord": "modifications",
    "ComponentCode": "components",
    "ByCode": "components",
    "ByNotation": "components",
    "SequenceText": "molecules",
    "EntityId": "molecules",
    "Multiplicity": "molecules",
    "Position": "modifications",
    "ResidueRef": "links",
    "LinkEndpoint": "links",
    "Linkage": "links",
    # Alignments and references
    "AlignmentSource": "alignments",
    "AlignmentAutomatic": "alignments",
    "AlignmentFree": "alignments",
    "AlignmentUnpairedOnly": "alignments",
    "AlignmentPairedOnly": "alignments",
    "AlignmentBoth": "alignments",
    "SingleAutomatic": "alignments",
    "SingleFree": "alignments",
    "SingleProvided": "alignments",
    "ReferenceRecord": "alignments",
    "ReferenceSet": "alignments",
    "SearchAllowed": "alignments",
    "Explicit": "alignments",
    # Components and chemistry
    "ComponentDefinitionSource": "custom_chemistry",
    "Inline": "custom_chemistry",
    "External": "files_paths",
    "PathSpec": "files_paths",
    # Presence values resolve to the field's owning step through the
    # context; the job description is the one the rules locate directly.
    "Present": "job_details",
    "Unset": "job_details",
    "ExplicitEmpty": "job_details",
}


def resolve_step_for_field_path(field_path) -> StepId:
    """The step whose prompt owns this locator.

    Raises ``KeyError`` for a registered type the table does not map —
    a programming error to fix in the table, never a silent misjump.
    """
    return StepId(JUMP_TABLE[field_path.type_name])


def resolve_step_for_finding(finding) -> StepId:
    """The step for a finding's first locator, or the validate step for
    findings without one (plan §16.6: every finding resolves to a
    reachable prompt)."""
    paths = tuple(getattr(finding, "paths", ()) or ())
    if not paths:
        return StepId("validate")
    return resolve_step_for_field_path(paths[0])
