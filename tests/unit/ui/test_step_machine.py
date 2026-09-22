"""Step-machine tier (IMPLEMENTATION_PLAN.md §18.8, Phase 11a checklist).

Direct calls, no terminal: reachability of every step, entry
conditions, field visibility per family, which service calls an answer
produces, and jump-to-field resolution from every ``FieldPath`` variant
the rules actually emit.
"""

from __future__ import annotations

import pytest

from configbuilder.ui.steps import (
    STEP_IDS,
    STEP_ORDER,
    Action,
    FieldSpec,
    ServiceCall,
    StepId,
    WizardMachine,
    WizardView,
    apply_alignments,
    apply_components,
    apply_custom_chemistry,
    apply_job_details,
    apply_links,
    apply_molecules,
    apply_modifications,
    apply_reproducibility,
    apply_start,
    apply_variants,
    build_steps,
    resolve_step_for_field_path,
    resolve_step_for_finding,
)


def _empty():
    return WizardView()


def _named():
    return WizardView(has_project=True, project_name="My Job")


def _with_records():
    return WizardView(
        has_project=True,
        project_name="My Job",
        records=(
            _Row("protein", "A", "PEPTIDE"),
            _Row("rna", "B", "GGCC"),
            _Row("ligand", "C", ""),
        ),
        seeds=(1, 2, 3),
    )


class _Row:
    """One view record row: family, primary identifier, sequence."""

    def __init__(self, family, entity, sequence) -> None:
        self.family = family
        self.entity = entity
        self.sequence = sequence


# -- the table -----------------------------------------------------------------


def test_fourteen_steps_in_plan_order():
    steps = build_steps()
    assert [s.id.name for s in steps] == [
        "start",
        "job_details",
        "molecules",
        "modifications",
        "components",
        "custom_chemistry",
        "links",
        "alignments",
        "files_paths",
        "reproducibility",
        "validate",
        "variants",
        "review",
        "generate",
    ]
    assert len(STEP_ORDER) == 14 and len(STEP_IDS) == 14


def test_every_step_title_resolves_through_the_registry():
    for step in build_steps():
        assert step.title  # a non-empty registry label, never an internal name


def test_every_fieldspec_label_resolves_through_the_registry():
    view = _with_records()
    for step in build_steps():
        for field in step.fields(view):
            assert field.prompt_label


def test_every_action_description_resolves_through_the_registry():
    view = _with_records()
    for step in build_steps():
        for action in step.actions(view):
            assert action.description


# -- entry conditions (the §16.1 table) ---------------------------------------------


def test_start_is_always_enterable():
    machine = WizardMachine()
    assert machine.can_enter(StepId("start"), _empty())


def test_job_details_requires_project_open():
    machine = WizardMachine()
    assert not machine.can_enter(StepId("job_details"), _empty())
    assert machine.can_enter(StepId("job_details"), _named())


def test_molecules_requires_name_set():
    machine = WizardMachine()
    assert not machine.can_enter(StepId("molecules"), WizardView(has_project=True))
    assert machine.can_enter(StepId("molecules"), _named())


def test_modifications_requires_a_polymer():
    machine = WizardMachine()
    ligand_only = WizardView(
        has_project=True,
        project_name="job",
        records=(_Row("ligand", "C", ""),),
    )
    polymer = WizardView(
        has_project=True,
        project_name="job",
        records=(_Row("protein", "A", "PEPT"),),
    )
    assert not machine.can_enter(StepId("modifications"), ligand_only)
    assert machine.can_enter(StepId("modifications"), polymer)


def test_components_requires_a_component_record():
    machine = WizardMachine()
    assert not machine.can_enter(StepId("components"), _named())
    assert machine.can_enter(StepId("components"), _with_records())


def test_custom_chemistry_needs_a_definition_or_opt_in():
    machine = WizardMachine()
    without = WizardView(has_project=True, project_name="job", records=(_Row("ligand", "C", ""),))
    needing = WizardView(
        has_project=True,
        project_name="job",
        records=(_Row("ligand", "C", ""),),
        needs_definition=True,
    )
    assert not machine.can_enter(StepId("custom_chemistry"), without)
    assert machine.can_enter(StepId("custom_chemistry"), needing)


def test_links_needs_two_addressable_endpoints():
    machine = WizardMachine()
    one = WizardView(has_project=True, project_name="job", records=(_Row("protein", "A", "PEPT"),))
    two = WizardView(
        has_project=True,
        project_name="job",
        records=(_Row("protein", "A", "PEPT"), _Row("ligand", "C", "")),
    )
    assert not machine.can_enter(StepId("links"), one)
    assert machine.can_enter(StepId("links"), two)


def test_alignments_needs_a_supporting_record():
    machine = WizardMachine()
    assert not machine.can_enter(StepId("alignments"), _named())
    assert machine.can_enter(StepId("alignments"), _with_records())


def test_files_paths_needs_an_external_resource():
    machine = WizardMachine()
    assert not machine.can_enter(StepId("files_paths"), _with_records())
    assert machine.can_enter(
        StepId("files_paths"),
        WizardView(has_project=True, project_name="job", has_external=True),
    )


def test_validate_needs_project_and_variants_need_clean_base():
    machine = WizardMachine()
    assert machine.can_enter(StepId("validate"), _named())

    dirty = WizardView(
        has_project=True,
        project_name="job",
        records=(_Row("protein", "A", "PEPT"),),
        report=_FakeReport(errors=2),
    )
    clean = WizardView(
        has_project=True,
        project_name="job",
        records=(_Row("protein", "A", "PEPT"),),
        report=_FakeReport(errors=0),
    )
    assert not machine.can_enter(StepId("variants"), dirty)
    assert machine.can_enter(StepId("variants"), clean)


def test_review_and_generate_require_expansion_then_conflict_freedom():
    machine = WizardMachine()
    expanded = WizardView(
        has_project=True,
        project_name="job",
        variants=("wt",),
        report=_FakeReport(errors=0),
    )
    conflicted = WizardView(
        has_project=True,
        project_name="job",
        variants=("wt",),
        conflicts=("plan conflict: overwrite refused",),
        report=_FakeReport(errors=0),
    )
    assert machine.can_enter(StepId("review"), expanded)
    assert not machine.can_enter(StepId("generate"), conflicted)
    assert machine.can_enter(StepId("generate"), expanded)


class _FakeFinding:
    def __init__(self, severity) -> None:
        self.severity = severity


class _FakeSeverity:
    def __init__(self, name) -> None:
        self.name = name


class _FakeReport:
    def __init__(self, errors=0, warnings=0) -> None:
        self.findings = (
            [_FakeFinding(_FakeSeverity("ERROR")) for _ in range(errors)]
            + [_FakeFinding(_FakeSeverity("WARNING")) for _ in range(warnings)]
        )


# -- navigation ------------------------------------------------------------------


def test_machine_starts_at_step_one_of_fourteen():
    machine = WizardMachine()
    assert machine.current.id == StepId("start")
    assert machine.position == 1
    assert machine.count == 14


def test_forward_navigation_skips_gated_steps():
    machine = WizardMachine()
    view = _with_records()
    machine.goto(StepId("job_details"), view)
    step = machine.next(view)
    assert step.id == StepId("molecules")  # next gated-in step


def test_previous_is_never_blocked():
    machine = WizardMachine()
    view = _with_records()
    # The honest gate: variants needs a performed, clean validation.
    clean = WizardView(
        has_project=True,
        project_name="My Job",
        records=view.records,
        seeds=view.seeds,
        report=_FakeReport(errors=0),
    )
    machine.goto(StepId("variants"), clean)
    # Plan order: validate(11) -> variants(12) -> review(13); backward
    # from variants is validate, and never an error.
    assert machine.previous(clean).id == StepId("validate")
    machine.goto(StepId("start"), clean)
    assert machine.previous(clean) is None  # already first, not an error


def test_goto_refuses_gated_steps_but_never_blocks_backward():
    machine = WizardMachine()
    view = _empty()
    assert machine.goto(StepId("generate"), view) is False
    assert machine.current.id == StepId("start")
    machine.goto(StepId("job_details"), _named())
    assert machine.previous(view).id == StepId("start")


def test_revisiting_a_step_reevaluates_its_condition():
    machine = WizardMachine()
    good = _named()
    assert machine.goto(StepId("molecules"), good)
    # The condition no longer holds (view changed) — the machine does not
    # keep a stale green state.
    assert machine.goto(StepId("molecules"), _empty()) is False


def test_steps_reachable_lists_enterable_steps():
    machine = WizardMachine()
    reachable = machine.steps_reachable(_with_records())
    names = {step_id.name for step_id in reachable}
    assert "start" in names and "job_details" in names and "molecules" in names
    assert "components" in names
    assert "generate" not in names


# -- visibility (per family, §16.4: absent, not shown-and-refused) -------------------


def test_modifications_shows_position_only_with_a_polymer():
    step = next(s for s in build_steps() if s.id.name == "modifications")
    keys_without = [f.key for f in step.fields(_named())]
    keys_with = [f.key for f in step.fields(_with_records())]
    assert "position" not in keys_without
    assert "position" in keys_with


def test_alignments_visibility_depends_on_protein_presence():
    step = next(s for s in build_steps() if s.id.name == "alignments")
    protein_view = WizardView(
        has_project=True,
        project_name="job",
        records=(_Row("rna", "B", "GGCC"),),
    )
    assert all(f.key != "mode" for f in step.fields(protein_view))
    assert any(f.key == "mode" for f in step.fields(_with_records()))


def test_job_details_shows_description_only_after_project_exists():
    step = next(s for s in build_steps() if s.id.name == "job_details")
    assert [f.key for f in step.fields(_empty())] == ["job_name"]
    assert [f.key for f in step.fields(_named())] == ["job_name", "job_description"]


def test_validate_review_generate_ask_no_fields():
    view = _with_records()
    for name in ("validate", "review", "generate"):
        step = next(s for s in build_steps() if s.id.name == name)
        assert step.fields(view) == ()


# -- answers become service calls -------------------------------------------------


def test_apply_start_returns_new_or_open_calls():
    calls = apply_start("new", _empty())
    assert calls == (ServiceCall("projects", "new"),)
    calls = apply_start("some/project.cbproj", _empty())
    assert calls == (ServiceCall("projects", "open", path="some/project.cbproj"),)


def test_apply_job_details_sets_name_and_optional_description():
    calls = apply_job_details({"job_name": "Widget"}, _named())
    assert calls == (ServiceCall("configuration", "set_name", name="Widget"),)
    calls = apply_job_details(
        {"job_name": "Widget", "job_description": "the run"}, _named()
    )
    assert len(calls) == 2
    assert calls[1] == ServiceCall(
        "configuration", "set_job_description", description="the run"
    )


def test_apply_molecules_passes_family_vocabulary():
    calls = apply_molecules(
        {"family": "protein", "sequence": "PEPT", "copies": 1}, _named()
    )
    assert calls == (
        ServiceCall(
            "configuration",
            "add_record",
            family="protein",
            sequence="PEPT",
            representation="",
            copies=1,
            description=None,
        ),
    )


def test_apply_modifications_targets_the_record():
    calls = apply_modifications({"record": "A", "code": "TPO", "position": 5}, _with_records())
    assert calls == (
        ServiceCall("configuration", "add_modification", record_key="A", code="TPO", position=5),
    )


def test_apply_components_chooses_codes_or_notation():
    codes = apply_components({"record": "C", "codes": ("ATP", "MG")}, _with_records())
    assert codes == (
        ServiceCall("configuration", "set_representation", record_key="C", codes=("ATP", "MG")),
    )
    notation = apply_components({"record": "C", "notation": "CC(=O)O"}, _with_records())
    assert notation == (
        ServiceCall("configuration", "set_representation", record_key="C", notation="CC(=O)O"),
    )


def test_apply_links_addresses_endpoints_by_key():
    calls = apply_links(
        {
            "a_key": "A",
            "a_residue": 3,
            "a_atom": "SG",
            "b_key": "C",
            "b_residue": 1,
            "b_atom": "N1",
        },
        _with_records(),
    )
    assert calls == (
        ServiceCall(
            "configuration",
            "add_linkage",
            a_key="A",
            a_residue=3,
            a_atom="SG",
            b_key="C",
            b_residue=1,
            b_atom="N1",
        ),
    )


def test_apply_alignments_carries_mode_and_content():
    calls = apply_alignments(
        {"record": "A", "mode": "unpaired", "external_path": "msa.a3m"}, _with_records()
    )
    assert calls == (
        ServiceCall(
            "configuration",
            "set_alignment",
            record_key="A",
            mode="unpaired",
            inline_text=None,
            external_path="msa.a3m",
        ),
    )


def test_apply_reproducibility_sets_seeds():
    calls = apply_reproducibility({"seeds": (1, 2, 3)}, _named())
    assert calls == (ServiceCall("configuration", "set_seeds", seeds=(1, 2, 3)),)


def test_apply_variants_delegates_the_factor_picker():
    """The picker's data becomes one service call; the *edit objects*
    are built in ``app`` (plan §5.3 rule 6 — ui never constructs
    variant vocabulary)."""
    calls = apply_variants(
        {"key": "wt", "factor": "sequence", "record": "A", "value": "MUT", "label": "wild type"},
        _named(),
    )
    assert calls == (
        ServiceCall(
            "variants",
            "add_spec_from_factor",
            key="wt",
            factor="sequence",
            value="MUT",
            label="wild type",
            record_key="A",
        ),
    )


def test_apply_custom_chemistry_routes_inline_or_file():
    inline = apply_custom_chemistry({"inline_text": "data_lig\n..."}, _with_records())
    assert inline[0].args["inline_text"] == "data_lig\n..."
    external = apply_custom_chemistry({"external_path": "lig.cif"}, _with_records())
    assert external[0].args["external_path"] == "lig.cif"


# -- jump-to-field from every FieldPath variant (§16.6) -------------------------------


def _field_path(type_name, key=None, field=""):
    from configbuilder.validation.report import FieldPath

    return FieldPath(type_name, key, field)


def test_every_emitted_field_path_resolves_to_a_step():
    """Every FieldPath shape the rules emit (surveyed from
    ``configbuilder/validation/rules``) resolves to a step."""
    emitted = [
        ("Auto", None, "version_selection"),
        ("ByNotation", "C", "smiles"),
        ("Configuration", None, ""),
        ("Configuration", None, "records"),
        ("Configuration", "A", ""),
        ("ConfigurationMetadata", None, "name"),
        ("EntityId", None, "id"),
        ("EntityId", "A", "id"),
        ("EntityId", "A", ""),
        ("LinkEndpoint", "A", "bond"),
        ("Linkage", "A", "bond"),
        ("Pinned", None, "version_selection"),
        ("ReferenceRecord", "A", "templates"),
        ("ReferenceSet", "A", "templates"),
        ("ResidueRef", "A", "bond"),
        ("SeedSet", None, "seeds"),
        ("Unverified", None, "version_selection"),
        # The remaining registered types the rules may locate directly.
        ("ModificationRecord", "A", ""),
        ("ComponentRecord", "C", ""),
        ("FamilyARecord", "A", ""),
        ("FamilyBRecord", "B", ""),
        ("FamilyCRecord", "A", ""),
        ("ComponentDefinitionSource", None, ""),
        ("Inline", None, ""),
        ("External", None, ""),
        ("PathSpec", None, ""),
        ("Present", None, ""),
        ("AlignmentSource", "A", ""),
        ("SearchAllowed", "A", ""),
    ]
    for type_name, key, field in emitted:
        step_id = resolve_step_for_field_path(_field_path(type_name, key, field))
        assert step_id.name in STEP_ORDER, (type_name, step_id)


def test_finding_without_paths_resolves_to_validate():
    class _Finding:
        paths = ()

    assert resolve_step_for_finding(_Finding()) == StepId("validate")


def test_unmapped_registered_type_raises_loudly():
    from configbuilder.validation.report import FieldPath

    # A registered type the table does not map must raise, not misjump.
    with pytest.raises(KeyError):
        resolve_step_for_field_path(_field_path("TraceabilityEntry", None, ""))
