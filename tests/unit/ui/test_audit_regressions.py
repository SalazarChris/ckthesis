"""Regression pins for the 2026-10-03 JSON-builder audit.

One test per defect in ``JSON_BUILDER_AUDIT_AND_FINALIZATION.md`` section D.
Each test drives the *real* ``MenuApp`` over a ``ScriptedConsole`` (or the real
service for a service-level defect), so a fix is pinned at the interface the
user actually touches rather than at an internal helper.

The menu rework moved several routes. The pins below use the route that still
exists: PTM management and the per-record modifications submenu for BUG-001 /
BUG-002, the save action for BUG-007, and the service layer for the bond
residue prompt, whose menu flow the rework removed along with the rest of the
session/project management.

The defects covered here:

- BUG-001  a blank modification code crashed the session
- BUG-002  a non-numeric residue/position showed a raw Python message
- BUG-003  the JSON preview could show a document generation would refuse
- BUG-004  a record with more than one copy could not be edited or deleted
- BUG-005  "Back" in the quantity submenu silently discarded the entity
- BUG-006  a ligand was offered as a modification carrier
- BUG-007  there was no explicit save action
- BUG-008  the generate menu renumbered between states
- BUG-009  an invalid choice recursed instead of re-asking
- BUG-010  ``set_representation`` could let a model error escape
- BUG-011  ``execute`` wrote the last plan, not the plan it was handed
- BUG-013  a hint named an action the menu did not show
- BUG-016  the CCD submenu glued a multi-code ligand into one component
"""

from __future__ import annotations

import glob
import os
import re

from configbuilder.app.configuration_service import ConfigurationService
from configbuilder.app.generation_service import GenerationService
from configbuilder.app.project_service import ProjectService
from configbuilder.app.validation_service import ValidationService
from configbuilder.app.variant_service import VariantService
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"

# main 1 New job → name → job menu 2 Add entity → 1 Protein → sequence →
# default MSA → no templates; the unit ends at the job menu.
PROTEIN_JOB = ["1", "job", "2", "1", PROTEIN, "1", ""]
NEW_JOB = ["1", "job"]
LEAVE_DIRTY = ["0", "2", "0"]      # job: leave → discard → main: exit
LEAVE_CLEAN = ["0", "0"]

MENU_ACTIONS = (
    "1. Edit job configurations",
    "2. Add entity",
    "3. Edit entity",
    "4. Custom CCD management",
    "5. Post-translational modification management",
    "6. Save and show summary",
    "7. Generate configurations from a file (sequences or ligands)",
)


def run(script):
    console = ScriptedConsole(script)
    app = MenuApp(build_services(), console)
    status = app.run()
    return status, console.transcript


def _services():
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    projects.new("probe")
    return projects, configuration


# -- BUG-001 / BUG-010: the model's own error type must be caught -----------


def test_blank_modification_code_is_refused_not_raised():
    """BUG-001: ``ValueTypeError`` is not a ``ValueError``; a blank code
    used to escape ``add_modification`` as a traceback."""
    _, configuration = _services()
    configuration.add_record("protein", PROTEIN)
    outcome = configuration.add_modification("A", "", 5)
    assert outcome.ok is False
    assert "non-empty" in outcome.message


def test_blank_modification_code_through_the_menu_says_cancelled():
    """The PTM route (job menu 5 → add) refuses a blank code in words."""
    status, out = run(PROTEIN_JOB + ["5", "2", "1", "", "0"] + LEAVE_DIRTY)
    assert status == 0
    assert "Cancelled" in out
    assert "Traceback" not in out


def test_blank_ccd_representation_is_refused_not_raised():
    """BUG-010: same escape route through ``set_representation``."""
    _, configuration = _services()
    configuration.add_record("ligand", representation="ATP", copies=2)
    outcome = configuration.set_representation("A", codes="")
    assert outcome.ok is False
    assert "non-empty" in outcome.message


# -- BUG-002: integer prompts speak the user's language --------------------


def test_non_numeric_ptm_position_is_answered_in_user_terms():
    status, out = run(PROTEIN_JOB + ["5", "2", "1", "SEP", "abc", "0"] + LEAVE_DIRTY)
    assert status == 0
    assert "not a whole number" in out
    assert "invalid literal for int()" not in out


def test_a_non_numeric_linkage_residue_is_refused_not_raised():
    """BUG-002's bond route. The rework removed the menu's bond flow, so the
    old prompt cannot print a raw Python message any more; what must still
    hold is that the service wraps the bad residue into a refusal object
    instead of letting it escape."""
    _, configuration = _services()
    configuration.add_record("protein", PROTEIN)
    outcome = configuration.add_linkage("A", "abc", "CA", "A", 1, "CB")
    assert outcome.ok is False
    assert outcome.message and "Traceback" not in outcome.message


# -- BUG-003: the preview obeys the generation gate -----------------------


def test_json_preview_refuses_an_incomplete_job():
    services = build_services()
    services.projects.new("empty")
    text, error = services.generation.show_json()
    assert text is None
    assert error
    assert '"sequences"' not in (text or "")


def test_json_preview_of_a_ready_job_matches_the_written_file(tmp_path):
    """The preview and the file come from one serializer, so they agree
    byte for byte."""
    services = build_services()
    services.projects.new("preview")
    services.configuration.add_record("protein", PROTEIN)
    text, error = services.generation.show_json()
    assert error is None
    plan = services.generation.plan_base(str(tmp_path))
    assert plan.ok, plan.message
    assert services.generation.execute(plan).ok
    written = glob.glob(os.path.join(str(tmp_path), "**", "*.json"), recursive=True)
    assert len(written) == 1
    with open(written[0], "r", encoding="utf-8") as handle:
        assert handle.read() == text


# -- BUG-004: a multi-copy record is addressable --------------------------


def test_multi_copy_record_can_be_edited_and_deleted():
    projects, configuration = _services()
    configuration.add_record("ligand", representation="ATP", copies=3)
    record = projects.project.configuration.records[0]
    assert [entity.value for entity in record.ids.ids] == ["A", "B", "C"]

    assert configuration.update_record("A", description="energy currency").ok
    assert configuration.remove_record("A").ok
    assert projects.project.configuration.records == ()


def test_multi_copy_record_releases_every_identifier_on_delete():
    projects, configuration = _services()
    configuration.add_record("ligand", representation="ATP", copies=3)
    configuration.remove_record("A")
    assert sorted(projects.project.configuration.identity.assigned_values()) == []


def test_multi_copy_ligand_is_deletable_through_the_menu():
    """Job menu 3 → the 3-copy ligand → Delete → Yes; the empty list is
    announced."""
    status, out = run(
        NEW_JOB
        + ["2", "4", "1", "ATP", "3", ""]          # add ligand (blank description)
        + ["3", "1", "2", "1"]
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "(no entities)" in out


def test_multi_copy_record_can_carry_a_modification():
    projects, configuration = _services()
    configuration.add_record("protein", PROTEIN, copies=2)
    assert configuration.add_modification("A", "SEP", 5).ok
    record = projects.project.configuration.records[0]
    assert [mod.position.value for mod in record.modifications] == [5]


# -- BUG-005: a cancelled submenu is announced ----------------------------


def test_back_at_the_quantity_menu_says_nothing_was_added():
    status, out = run(NEW_JOB + ["2", "4", "1", "ATP", "0"] + LEAVE_CLEAN)
    assert status == 0
    assert "Cancelled" in out


def test_back_at_the_ligand_kind_menu_says_nothing_was_added():
    status, out = run(NEW_JOB + ["2", "4", "0"] + LEAVE_CLEAN)
    assert status == 0
    assert "Cancelled" in out


# -- BUG-006: only polymers are offered as modification carriers ----------


def test_ligand_is_not_offered_as_a_modification_carrier():
    status, out = run(
        NEW_JOB
        + ["2", "4", "1", "ATP", "1", ""]      # add ligand (blank description)
        + ["5", "2"]                    # PTM → add: the carrier picker is empty
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "ligands carry no post-translational modifications" in out


# -- BUG-007: an explicit save action exists and reports its path ---------


def test_save_action_writes_the_json_and_names_the_path(tmp_path):
    destination = tmp_path / "job.json"
    status, out = run(PROTEIN_JOB + ["6", str(destination)] + LEAVE_CLEAN)
    assert status == 0
    assert "Saved to " in out
    assert os.path.exists(destination)
    assert os.path.basename(destination) == "job.json"


def test_save_action_refuses_an_incomplete_job(tmp_path):
    destination = tmp_path / "empty.json"
    status, out = run(NEW_JOB + ["6", str(destination)] + LEAVE_CLEAN)
    assert status == 0
    assert "cannot be saved yet" in out
    assert not os.path.exists(destination)


def test_save_action_cancelled_writes_nothing(tmp_path):
    status, out = run(PROTEIN_JOB + ["6", "0"] + LEAVE_DIRTY)
    assert status == 0
    assert "Cancelled" in out
    assert not glob.glob(os.path.join(str(tmp_path), "**", "*.json"), recursive=True)


# -- BUG-008: the job menu keeps one fixed action list --------------------


def test_the_job_menu_keeps_its_numbering_with_and_without_variants():
    """The old Generate submenu renumbered between states (BUG-008). The
    reworked job menu is one static list; it must name the same seven
    actions whatever the job holds."""
    bare_status, bare = run(NEW_JOB + LEAVE_CLEAN)
    full_status, full = run(PROTEIN_JOB + LEAVE_DIRTY)
    assert bare_status == 0 and full_status == 0
    for label in MENU_ACTIONS:
        assert label in bare, label
        assert label in full, label

MENU_ACTIONS = (
    "1. Edit job configurations",
    "2. Add entity",
    "3. Edit entity",
    "4. Custom CCD management",
    "5. Post-translational modification management",
    "6. Save and show summary",
    "7. Generate configurations from a file (sequences or ligands)",
)


# -- BUG-009: re-ask by looping, never by recursing ----------------------


def test_many_invalid_choices_do_not_exhaust_the_stack():
    """200 invalid choices at the entity picker: a recursive re-ask would
    grow the stack once per keystroke."""
    status, out = run(PROTEIN_JOB + ["3"] + ["x"] * 200 + ["0"] + LEAVE_DIRTY)
    assert status == 0
    assert "Not a valid choice" in out


# -- BUG-011: execute writes the plan it was handed ----------------------


def test_execute_writes_the_plan_it_was_handed(tmp_path):
    """Two plans in a row: executing the first must write the first's bytes."""
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    variants = VariantService(projects, configuration)
    validation = ValidationService(projects)
    generation = GenerationService(projects, variants, validation=validation)

    projects.new("plans")
    configuration.add_record("protein", PROTEIN)

    first_root = os.path.join(str(tmp_path), "first")
    second_root = os.path.join(str(tmp_path), "second")
    first = generation.plan_base(first_root)
    assert first.ok, first.message
    second = generation.plan_base(second_root)
    assert second.ok, second.message

    # Plan a third, different document, then execute the *first* plan.
    configuration.update_record("A", sequence="MKTAYIAKQR")
    third = generation.plan_base(os.path.join(str(tmp_path), "third"))
    assert third.ok, third.message

    assert generation.execute(first).ok
    written = glob.glob(os.path.join(first_root, "**", "*.json"), recursive=True)
    assert len(written) == 1
    with open(written[0], "r", encoding="utf-8") as handle:
        body = handle.read()
    assert PROTEIN in body
    assert "MKTAYIAKQR" not in body


# -- BUG-013: hints name actions the menu actually shows -----------------


def test_the_leave_hint_names_an_action_the_menu_shows():
    """The old master menu's hint named "Open saved work" — an option that
    lived only on the start screen. The reworked builder's leave prompt must
    name the save the job menu really offers, and no recovery vocabulary may
    survive the rework."""
    from configbuilder.ui.present.strings import STRINGS

    assert "saved to a JSON file" in STRINGS["menu.leave_dirty"]
    assert "Save and show summary" in STRINGS["menu.job_actions"]
    for value in STRINGS.values():
        assert "Open saved work" not in value
        assert "Recover the last working copy" not in value
        assert "working copy" not in value


def test_the_main_menu_names_only_actions_it_shows():
    from configbuilder.ui.present.strings import STRINGS

    assert "Open a JSON file" in STRINGS["menu.main_actions"]
    assert "New job" in STRINGS["menu.main_actions"]


# -- BUG-016: the ligand "code(s)" route stays a list of codes ---------------


def _ligand_codes(services, representation, kind):
    """The component list the service stores for a typed ligand value."""
    from configbuilder.model import ByCode

    outcome = services.configuration.add_record(
        "ligand", representation=representation, representation_kind=kind)
    assert outcome.ok, outcome.message
    record = services.projects.project.configuration.records[0]
    assert isinstance(record.representation, ByCode)
    return [code.value for code in record.representation.codes]


def test_ccd_submenu_keeps_every_code_of_a_multi_component_ligand():
    """The ligand submenu promises "CCD code(s) - e.g. ATP, or several
    separated by spaces", and passes ``kind="ccd"``. That route read the whole
    text as ONE component, so the five-code glycan became a component named
    "NAG NAG BMA MAN MAN", which no CCD contains: the emitted file referenced
    a chemistry that does not exist. Every separator the submenu documents is
    pinned here."""
    services = build_services()
    services.projects.new("glycan")
    assert _ligand_codes(services, "NAG NAG BMA MAN MAN", "ccd") == [
        "NAG", "NAG", "BMA", "MAN", "MAN"]

    services = build_services()
    services.projects.new("comma")
    assert _ligand_codes(services, "NAG,NAG,BMA", "ccd") == ["NAG", "NAG", "BMA"]

    services = build_services()
    services.projects.new("semicolon")
    assert _ligand_codes(services, "HOH;NA;CL", "ccd") == ["HOH", "NA", "CL"]


def test_multi_component_ligand_reaches_the_wire_as_one_code_list():
    """The stored components must survive into ``ccdCodes`` -- one ligand
    entity holding a list, never several entities and never one glued code."""
    from configbuilder.transform import to_wire

    services = build_services()
    services.projects.new("glycan wire")
    _ligand_codes(services, "NAG NAG BMA MAN MAN", "ccd")
    document = to_wire(services.projects.project.configuration).document
    entries = [sequence["ligand"] for sequence in document["sequences"] if "ligand" in sequence]
    assert len(entries) == 1
    assert entries[0]["ccdCodes"] == ["NAG", "NAG", "BMA", "MAN", "MAN"]


def test_single_code_and_smiles_routes_are_unchanged():
    services = build_services()
    services.projects.new("single")
    assert _ligand_codes(services, "ATP", "ccd") == ["ATP"]

    services = build_services()
    services.projects.new("single implicit")
    assert _ligand_codes(services, "ATP", "") == ["ATP"]

    from configbuilder.model import ByNotation

    services = build_services()
    services.projects.new("smiles")
    outcome = services.configuration.add_record(
        "ligand", representation="CC(=O)Oc1ccccc1C(=O)O", representation_kind="smiles")
    assert outcome.ok, outcome.message
    record = services.projects.project.configuration.records[0]
    assert isinstance(record.representation, ByNotation)


def test_multi_component_glycan_can_be_bonded_residue_by_residue(tmp_path):
    """BUG-014 and BUG-016 together: the documented glycan workflow -- a
    multi-code ligand with one bond per CCD residue -- must validate, generate
    and carry all five codes plus all five bonds into the file. AF3 numbers a
    ligand's residues one per code, so residue 5 of a five-code ligand is real.

    This is the shape of AF3's own ``examples/rnaseb_glycosylated.json``.
    """
    import json

    services = build_services()
    services.projects.new("bonded glycan")
    configuration = services.configuration
    configuration.add_record("protein", PROTEIN)
    configuration.add_record("ligand", representation="NAG NAG BMA MAN MAN",
                             representation_kind="ccd")
    for residue in (1, 2, 3, 4, 5):
        outcome = configuration.add_linkage("A", 1, "ND2", "B", residue, "C1")
        assert outcome.ok, outcome.message

    plan = services.generation.plan_base(str(tmp_path))
    assert plan.ok, plan.failure_reason
    result = services.generation.execute(plan)
    assert result.ok, result.errors

    documents = []
    for path in glob.glob(os.path.join(str(tmp_path), "**", "*.json"), recursive=True):
        if os.path.basename(path) == "manifest.json":
            continue
        with open(path, "r", encoding="utf-8") as handle:
            documents.append(json.load(handle))
    assert len(documents) == 1
    document = documents[0]
    ligands = [entry["ligand"] for entry in document["sequences"] if "ligand" in entry]
    assert len(ligands) == 1
    assert ligands[0]["ccdCodes"] == ["NAG", "NAG", "BMA", "MAN", "MAN"]
    assert len(document["bondedAtomPairs"]) == 5
