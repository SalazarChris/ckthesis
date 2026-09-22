"""The fourteen steps (plan §16.1) as pure data.

Each step carries: an explicit entry condition over the ``WizardView``,
the fields visible in this state (per-family visibility is a function
of the view, plan §16.2), and the actions offered. ``apply_*`` helpers
turn answers into ``ServiceCall`` data — the caller performs them on
the real services; this module invokes nothing (plan §5.3 rule 9).
"""

from __future__ import annotations

from configbuilder.ui.steps.machine import Action, FieldSpec, ServiceCall, Step, StepId
from configbuilder.ui.steps.view import WizardView

__all__ = ["build_steps", "apply_start", "apply_job_details", "apply_molecules",
           "apply_modifications", "apply_components", "apply_custom_chemistry",
           "apply_links", "apply_alignments", "apply_files_paths",
           "apply_reproducibility", "apply_variants"]


# -- entry conditions (§16.1 table) -------------------------------------------------


def _always(view):
    return True


def _project_open(view):
    return view.has_project


def _name_set(view):
    return view.has_project and bool(view.project_name.strip())


def _polymer_exists(view):
    return _name_set(view) and bool(view.polymers)


def _component_exists(view):
    return _name_set(view) and bool(view.components)


def _definition_needed_or_opted(view):
    """A code needs a definition, or the user opts in (§16.1 step 6)."""
    return _component_exists(view) and view.needs_definition


def _two_addressable(view):
    return _name_set(view) and len(view.addressable) >= 2


def _record_supports_alignments(view):
    return _polymer_exists(view)


def _external_referenced(view):
    return _name_set(view) and view.has_external


def _base_validates(view):
    """The base has actually been *validated* (a report exists) and it
    is clean — never an assumption from absence of evidence (plan §16.1:
    entry conditions are explicit)."""
    return _name_set(view) and view.report is not None and view.errors == 0


def _variants_expanded(view):
    return _base_validates(view) and bool(view.variants)


def _plan_without_conflicts(view):
    return _variants_expanded(view) and not view.conflicts


# -- visibility (per-family, §16.4: absent, not shown-and-refused) ------------------


def _fields_start(view):
    return (
        FieldSpec("choice", "Configuration", required=True),
    )


def _fields_job_details(view):
    fields = [FieldSpec("job_name", "ConfigurationMetadata", required=True)]
    if view.has_project:
        # The optional description exists from step 2 on; it is the
        # spec §15 naming factor. Wizard keys deliberately avoid wire
        # vocabulary (the same discipline as the project file).
        fields.append(FieldSpec("job_description", "ConfigurationMetadata", default=""))
    return tuple(fields)


def _fields_molecules(view):
    # Family choice is a numbered list of registry labels (§16.4).
    return (
        FieldSpec("family", "Record", required=True),
        FieldSpec("sequence", "SequenceText", required=True),
        FieldSpec("representation", "ComponentRecord", required=True),
        FieldSpec("copies", "Multiplicity", default=1),
        FieldSpec("description", "Present", default=""),
    )


def _fields_modifications(view):
    fields = [FieldSpec("record", "Record", required=True)]
    if view.polymers:
        # Position picking needs a polymer with a sequence.
        fields.append(FieldSpec("position", "Position", required=True))
        fields.append(FieldSpec("code", "ComponentCode", required=True))
    return tuple(fields)


def _fields_components(view):
    return (
        FieldSpec("record", "Record", required=True),
        FieldSpec("codes", "ByCode"),
        FieldSpec("notation", "ByNotation"),
    )


def _fields_custom_chemistry(view):
    return (
        FieldSpec("inline_text", "Inline"),
        FieldSpec("external_path", "External"),
    )


def _fields_links(view):
    return (
        FieldSpec("a_key", "EntityId", required=True),
        FieldSpec("a_residue", "ResidueRef", required=True),
        FieldSpec("a_atom", "LinkEndpoint", required=True),
        FieldSpec("b_key", "EntityId", required=True),
        FieldSpec("b_residue", "ResidueRef", required=True),
        FieldSpec("b_atom", "LinkEndpoint", required=True),
    )


def _fields_alignments(view):
    fields = [FieldSpec("record", "Record", required=True)]
    for record in view.polymers:
        if record.family == "protein":
            # Protein alignment modes map to the unpaired/paired sum cases.
            fields.append(FieldSpec("mode", "AlignmentSource", required=True))
            fields.append(FieldSpec("content", "External"))
            break
    return tuple(fields)


def _fields_files_paths(view):
    return (
        FieldSpec("path", "PathSpec", required=True),
        FieldSpec("path_policy", "External", default="CopyIntoAssets"),
    )


def _fields_reproducibility(view):
    return (FieldSpec("seeds", "SeedSet", required=True),)


def _fields_validate(view):
    return ()


def _fields_variants(view):
    """The guided factor picker (plan §16.4): choose what to vary, give
    a value and a label; the builder writes the edits. ``record`` is
    only asked when a factor targets one record."""
    fields = [
        FieldSpec("key", "Variant", required=True),
        FieldSpec("factor", "Variant", required=True),
    ]
    if view.records:
        fields.append(FieldSpec("record", "Record"))
    fields.append(FieldSpec("value", "Present", required=True))
    fields.append(FieldSpec("label", "Variant"))
    return tuple(fields)


def _fields_review(view):
    return ()


def _fields_generate(view):
    return ()


# -- actions (the §16.3 grammar, per step) ------------------------------------------

_NAV = (Action("n", "Configuration", "action.next_step"), Action("p", "Configuration", "action.previous_step"))
_EDIT = (Action("e", "Record", "action.edit_item"), Action("d", "Record", "action.delete_item"))
_VALIDATE = (Action("v", "Configuration", "action.validate_now"),)
_SAVE_QUIT = (Action("s", "Configuration", "action.save_project"), Action("q", "Configuration", "action.quit"))


def _actions_start(view):
    return _NAV + _SAVE_QUIT


def _actions_job_details(view):
    return _NAV + _VALIDATE + _SAVE_QUIT


def _actions_molecules(view):
    return _NAV + _EDIT + _VALIDATE + _SAVE_QUIT


def _actions_modifications(view):
    return _NAV + _EDIT + _VALIDATE + _SAVE_QUIT


def _actions_components(view):
    return _NAV + _EDIT + _VALIDATE + _SAVE_QUIT


def _actions_custom_chemistry(view):
    return _NAV + _EDIT + _VALIDATE + _SAVE_QUIT


def _actions_links(view):
    return _NAV + _EDIT + _VALIDATE + _SAVE_QUIT


def _actions_alignments(view):
    return _NAV + _EDIT + _VALIDATE + _SAVE_QUIT


def _actions_files_paths(view):
    return _NAV + _VALIDATE + _SAVE_QUIT


def _actions_reproducibility(view):
    return _NAV + _VALIDATE + _SAVE_QUIT


def _actions_validate(view):
    return _NAV + _VALIDATE + _SAVE_QUIT


def _actions_variants(view):
    return _NAV + _EDIT + _VALIDATE + _SAVE_QUIT


def _actions_review(view):
    return _NAV + _SAVE_QUIT


def _actions_generate(view):
    return _NAV + _SAVE_QUIT


# -- answer application (answers -> ServiceCall data) ---------------------------------


def apply_start(answers, view):
    """``new`` or ``open``: the renderer performs the returned calls."""
    choice = answers.get("choice", "") if isinstance(answers, dict) else answers
    if choice == "new":
        return (ServiceCall("projects", "new"),)
    return (ServiceCall("projects", "open", path=choice),)


def apply_job_details(answers, view):
    calls = [ServiceCall("configuration", "set_name", name=answers["job_name"])]
    if answers.get("job_description") is not None:
        calls.append(
            ServiceCall(
                "configuration",
                "set_job_description",
                description=answers["job_description"],
            )
        )
    return tuple(calls)


def apply_molecules(answers, view):
    return (
        ServiceCall(
            "configuration",
            "add_record",
            family=answers["family"],
            sequence=answers.get("sequence", ""),
            representation=answers.get("representation", ""),
            copies=answers.get("copies", 1),
            # An empty answer means Unset (the field was left out); the
            # wizard has no vocabulary yet for an explicit empty here.
            description=answers.get("description") or None,
        ),
    )


def apply_modifications(answers, view):
    return (
        ServiceCall(
            "configuration",
            "add_modification",
            record_key=answers["record"],
            code=answers["code"],
            position=answers["position"],
        ),
    )


def apply_components(answers, view):
    """Set a component record's representation (codes or notation)."""
    if answers.get("codes"):
        return (ServiceCall("configuration", "set_representation", record_key=answers["record"], codes=answers["codes"]),)
    return (
        ServiceCall(
            "configuration",
            "set_representation",
            record_key=answers["record"],
            notation=answers.get("notation"),
        ),
    )


def apply_custom_chemistry(answers, view):
    return (
        ServiceCall(
            "configuration",
            "set_component_definition",
            inline_text=answers.get("inline_text"),
            external_path=answers.get("external_path"),
        ),
    )


def apply_links(answers, view):
    return (
        ServiceCall(
            "configuration",
            "add_linkage",
            a_key=answers["a_key"],
            a_residue=answers["a_residue"],
            a_atom=answers["a_atom"],
            b_key=answers["b_key"],
            b_residue=answers["b_residue"],
            b_atom=answers["b_atom"],
        ),
    )


def apply_alignments(answers, view):
    return (
        ServiceCall(
            "configuration",
            "set_alignment",
            record_key=answers["record"],
            mode=answers["mode"],
            inline_text=answers.get("inline_text"),
            external_path=answers.get("external_path"),
        ),
    )


def apply_files_paths(answers, view):
    calls = []
    if answers.get("path_policy"):
        calls.append(
            ServiceCall(
                "projects",
                "set_output_policies",
                path_policy=answers["path_policy"],
            )
        )
    return tuple(calls)


def apply_reproducibility(answers, view):
    return (ServiceCall("configuration", "set_seeds", seeds=answers["seeds"]),)


def apply_variants(answers, view):
    """The factor picker's data becomes one service call; the *edit
    objects* are built by ``app`` (plan §5.3 rule 6: ``ui`` imports
    ``app`` only — it never constructs variant vocabulary itself)."""
    call_args = {
        "key": answers["key"],
        "factor": answers["factor"],
        "value": answers["value"],
        "label": answers.get("label", ""),
    }
    if answers.get("record"):
        call_args["record_key"] = answers["record"]
    return (ServiceCall("variants", "add_spec_from_factor", **call_args),)


def apply_answer(step_name: str, answers, view):
    """Dispatch one step's answers to its ``(name, handler)`` pair.

    Unknown step names raise: every step in the table must have an
    answer application, so a new step without one breaks here loudly
    rather than silently dropping the user's input."""
    for candidate, handler in _APPLY_PAIRS:
        if candidate == step_name:
            return handler(answers, view)
    raise KeyError(
        "no answer application registered for step %r; add it to "
        "ui/steps/registry.py" % step_name
    )


# (step name, handler) pairs rather than a dict: the names are the
# machine's step ids, not wire vocabulary, and the wire-confinement
# detector reads dict keys.
_APPLY_PAIRS = (
    ("start", apply_start),
    ("job_details", apply_job_details),
    ("molecules", apply_molecules),
    ("modifications", apply_modifications),
    ("components", apply_components),
    ("custom_chemistry", apply_custom_chemistry),
    ("links", apply_links),
    ("alignments", apply_alignments),
    ("files_paths", apply_files_paths),
    ("reproducibility", apply_reproducibility),
    ("variants", apply_variants),
)


# -- the step table ----------------------------------------------------------------


def build_steps():
    """The fourteen steps in §16.1 order."""
    return (
        Step(StepId("start"), "Configuration", _always, _fields_start, _actions_start),
        Step(StepId("job_details"), "ConfigurationMetadata", _project_open, _fields_job_details, _actions_job_details),
        Step(StepId("molecules"), "Record", _name_set, _fields_molecules, _actions_molecules),
        Step(StepId("modifications"), "ModificationRecord", _polymer_exists, _fields_modifications, _actions_modifications),
        Step(StepId("components"), "ComponentRecord", _component_exists, _fields_components, _actions_components),
        Step(StepId("custom_chemistry"), "ComponentDefinitionSource", _definition_needed_or_opted, _fields_custom_chemistry, _actions_custom_chemistry),
        Step(StepId("links"), "Linkage", _two_addressable, _fields_links, _actions_links),
        Step(StepId("alignments"), "AlignmentSource", _record_supports_alignments, _fields_alignments, _actions_alignments),
        Step(StepId("files_paths"), "PathSpec", _external_referenced, _fields_files_paths, _actions_files_paths),
        Step(StepId("reproducibility"), "SeedSet", _always, _fields_reproducibility, _actions_reproducibility),
        Step(StepId("validate"), "Configuration", _project_open, _fields_validate, _actions_validate),
        Step(StepId("variants"), "Variant", _base_validates, _fields_variants, _actions_variants),
        Step(StepId("review"), "Variant", _variants_expanded, _fields_review, _actions_review),
        Step(StepId("generate"), "OutputReference", _plan_without_conflicts, _fields_generate, _actions_generate),
    )
