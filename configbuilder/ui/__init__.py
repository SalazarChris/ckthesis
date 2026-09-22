"""Terminal wizard (plan §5.1, §16): the pure programmatic core.

``ui/steps`` is the navigation machine; ``ui/present`` is formatting
and label resolution; ``ui/render`` (Phase 11b) will attach terminals.
The direction inside ``ui`` is ``render → steps → present`` (plan
§5.3 rule 9), and ``ui`` imports ``app`` and ``model.traceability``
only (rule 6).
"""

from configbuilder.ui.present import (
    FindingCard,
    MINIMUM_WIDTH,
    format_findings,
    label,
    render_sequence_ruler,
    residue_at,
    severity_label,
)
from configbuilder.ui.steps import (
    Action,
    FieldSpec,
    ServiceCall,
    Step,
    StepId,
    WizardMachine,
    WizardView,
    build_steps,
    resolve_step_for_field_path,
    resolve_step_for_finding,
)

__all__ = [
    "Action",
    "FieldSpec",
    "FindingCard",
    "MINIMUM_WIDTH",
    "ServiceCall",
    "Step",
    "StepId",
    "WizardMachine",
    "WizardView",
    "build_steps",
    "format_findings",
    "label",
    "render_sequence_ruler",
    "resolve_step_for_field_path",
    "resolve_step_for_finding",
    "residue_at",
    "severity_label",
]
