"""The pure step machine (plan §5.1, §5.3 rule 9, §16.1–§16.2).

Steps are values: named states with explicit entry conditions, the
fields visible in each state, the actions offered, and answers that
become ``ServiceCall`` data the *caller* performs. No terminal, no
streams, no environment (``ui/render`` does that) — which is what makes
the whole navigation model unit-testable without a terminal.
"""

from configbuilder.ui.steps.jump import (
    JUMP_TABLE,
    resolve_step_for_field_path,
    resolve_step_for_finding,
)
from configbuilder.ui.steps.machine import (
    STEP_IDS,
    STEP_ORDER,
    Action,
    FieldSpec,
    ServiceCall,
    Step,
    StepId,
    WizardMachine,
)
from configbuilder.ui.steps.registry import (
    apply_alignments,
    apply_answer,
    apply_components,
    apply_custom_chemistry,
    apply_files_paths,
    apply_job_details,
    apply_links,
    apply_molecules,
    apply_modifications,
    apply_reproducibility,
    apply_start,
    apply_variants,
    build_steps,
)
from configbuilder.ui.steps.view import WizardView

__all__ = [
    "Action",
    "FieldSpec",
    "JUMP_TABLE",
    "STEP_IDS",
    "STEP_ORDER",
    "ServiceCall",
    "Step",
    "StepId",
    "WizardMachine",
    "WizardView",
    "apply_alignments",
    "apply_answer",
    "apply_components",
    "apply_custom_chemistry",
    "apply_files_paths",
    "apply_job_details",
    "apply_links",
    "apply_molecules",
    "apply_modifications",
    "apply_reproducibility",
    "apply_start",
    "apply_variants",
    "build_steps",
    "resolve_step_for_field_path",
    "resolve_step_for_finding",
]
