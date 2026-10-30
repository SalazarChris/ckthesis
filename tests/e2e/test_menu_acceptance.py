"""Job-menu end-to-end acceptance for the reworked builder.

Every advertised menu option is exercised through the real ``MenuApp`` over a
``ScriptedConsole``: a successful path, an invalid-input path, and a
cancellation where one exists. The resulting job state and the JSON actually
written to disk are then checked against the AF3 contract pinned in
``AUTHORITATIVE_SPEC.md``.

These are integration tests, not unit tests: they drive the shipped entry
point and assert on files on disk.

Menu depth reference (see ``ui/render/menus.py``)::

    main     1 New job   2 Open a JSON file   0 Exit
    job      1 Edit job configurations   2 Add entity   3 Edit entity
             4 Custom CCD management      5 Post-translational modification
             management
             6 Save and show summary      7 Generate ligand configurations
    config   1 Job name  2 Model seeds → 1 specific / 2 generate  3 JSON version
             0 Back
    add      1 Protein   2 DNA (+ complement yes/no)   3 RNA   4 Ligand
             0 Back
    edit     1 Edit      2 Delete   (3 Modifications for a polymer)  0 Back
    CCD      1 View  2 Add  3 Edit  4 Remove  0 Back
    PTM      1 View  2 Add  3 Edit  4 Remove  0 Back
    ligands  1 Open ligand input file and generate configurations    0 Back

A dirty job never leaves silently: at the job menu ``0`` asks Save / Leave
without saving / Cancel first. Opening a JSON file commits it directly after
the path is chosen; the picker itself can still be cancelled with ``0``.
The ligand action reads the job and writes files; it never changes the job, so
a run always starts from exactly the base on screen.
"""

from __future__ import annotations

import glob
import json
import os

from configbuilder.model import External, Inline
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"
OTHER_PROTEIN = "MKTAYIAKQR"

# main 1 New job → name → the job menu
NEW_JOB = ["1", "job"]
# job 2 Add entity → family → that family's answers → job menu
ADD_PROTEIN = ["2", "1", PROTEIN, "1", ""]          # sequence, default MSA, templates no
ADD_RNA = ["2", "3", "ACGU", "1"]                   # sequence, default MSA
ADD_DNA = ["2", "2", "ATGC", "1"]                 # one strand in, yes to the complement: a duplex out
ADD_LIGAND = lambda value, quantity, description="": [
    "2", "4", "1", value, quantity, description
]
# job 3 Edit entity → pick → action … → 0 → 0 back to the job menu
LEAVE_DIRTY = ["0", "2", "0"]                      # job: leave → discard → main: exit
LEAVE_CLEAN = ["0", "0"]                           # job: leave → main: exit
EXIT = ["0"]


def run(script, monkeypatch=None):
    services = build_services()
    console = ScriptedConsole(script)
    app = MenuApp(services, console)
    status = app.run()
    return status, console.transcript, services


def written(root):
    return sorted(glob.glob(os.path.join(str(root), "**", "*.json"), recursive=True))


def load(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def protein_job():
    """A job with one protein, sitting at the job menu."""
    return NEW_JOB + ADD_PROTEIN


# -- the entry point and the main menu --------------------------------------


def test_entry_point_returns_zero_on_exit():
    status, out, _ = run(EXIT)
    assert status == 0
    assert "JSON CONFIGURATION BUILDER" in out


def test_main_menu_displays_its_options():
    status, out, _ = run(NEW_JOB + LEAVE_CLEAN)
    assert status == 0
    assert "1. New job" in out
    assert "2. Open a JSON file" in out
    assert "0. Exit" in out


def test_invalid_main_choice_is_reported_and_the_menu_survives():
    status, out, _ = run(["9", "0"])
    assert status == 0
    assert "Not a valid choice: '9'" in out
    assert "JSON CONFIGURATION BUILDER" in out


def test_cancelling_the_main_menu_exits_cleanly():
    status, out, _ = run([""])
    assert status == 0


def test_new_job_arrives_with_the_documented_defaults():
    status, out, services = run(NEW_JOB + LEAVE_CLEAN)
    assert status == 0
    assert "Started job job." in out
    configuration = services.projects.project.configuration
    assert configuration.metadata.name == "job"
    assert list(configuration.seeds.values) == [1]
    assert configuration.records == ()


def test_a_blank_job_name_is_generated_by_the_service():
    status, out, services = run(["1", ""] + LEAVE_CLEAN)
    assert status == 0
    assert services.projects.project.configuration.metadata.name == "Untitled job 1"


# -- add entity: every family, refusals and cancellations --------------------


def test_add_every_entity_family():
    status, out, services = run(
        NEW_JOB
        + ADD_PROTEIN
        + ADD_DNA                                  # two records
        + ADD_RNA
        + ADD_LIGAND("ATP", "2")                   # two copies
        + LEAVE_DIRTY
    )
    assert status == 0
    records = services.projects.project.configuration.records
    assert [type(record).__name__ for record in records] == [
        "FamilyARecord",
        "FamilyCRecord",
        "FamilyCRecord",
        "FamilyBRecord",
        "ComponentRecord",
    ]
    assert len(records[-1].ids.ids) == 2
    assert out.count("Entity added.") == 4
    assert "Traceback" not in out


def test_an_invalid_sequence_is_reported_and_nothing_is_added():
    status, out, services = run(NEW_JOB + ["2", "1", "ACDE!!"] + LEAVE_CLEAN)
    assert status == 0
    assert "Not applied" in out
    assert services.projects.project.configuration.records == ()


def test_add_cancellations_announce_themselves():
    status, out, services = run(
        NEW_JOB
        + ["2", "1", ""]                # protein: blank sequence
        + ["2", "4", "0"]               # ligand: back at the kind menu
        + ["2", "4", "1", "ATP", "0"]   # ligand: back at the quantity menu
        + LEAVE_CLEAN
    )
    assert status == 0
    assert out.count("Cancelled — nothing was added.") == 3
    assert services.projects.project.configuration.records == ()


def test_the_quantity_choice_is_recorded_and_shown():
    status, out, services = run(
        NEW_JOB + ADD_LIGAND("NA", "3") + ["6", "0"] + LEAVE_DIRTY
    )
    assert status == 0
    record = services.projects.project.configuration.records[0]
    assert [entity.value for entity in record.ids.ids] == ["A", "B", "C"]
    assert "x3" in out


# -- edit job configurations ------------------------------------------------


def test_job_settings_change_name_seeds_and_version():
    status, out, services = run(
        NEW_JOB
        + ["1"]                        # job → config
        + ["1", "renamed"]             # config 1: name
        + ["2", "1", "1 2 3 4"]       # config 2: seeds → method 1: specific values
        + ["3", "3"]                   # config 3: version
        + ["0"]                        # config → job
        + LEAVE_DIRTY
    )
    assert status == 0
    configuration = services.projects.project.configuration
    assert configuration.metadata.name == "renamed"
    assert list(configuration.seeds.values) == [1, 2, 3, 4]
    assert "Version: v3" in out


def test_invalid_job_settings_are_refused_in_the_users_terms():
    status, out, _ = run(
        NEW_JOB
        + ["1"]                        # job → config
        + ["3", "9"]                   # unsupported JSON version
        + ["2", "1", "not seeds"]     # seeds → specific values: the service refuses
        + ["0"]                        # config → job
        + LEAVE_CLEAN                  # neither refusal changed the job
    )
    assert status == 0
    assert "Unsupported JSON version" in out
    assert "Not applied" in out
    assert "Traceback" not in out


def test_the_job_menu_numbering_is_stable_across_states():
    """The job menu has one fixed action list — adding entities or variants
    never renumbers it."""
    _, bare, _ = run(NEW_JOB + LEAVE_CLEAN)
    _, full, _ = run(NEW_JOB + ADD_PROTEIN + ADD_LIGAND("ATP", "1") + LEAVE_DIRTY)
    for label in (
        "1. Edit job configurations",
        "2. Add entity",
        "3. Edit entity",
        "4. Custom CCD management",
        "5. Post-translational modification management",
        "6. Save and show summary",
        "7. Generate configurations from a file (sequences or ligands)",
        "0. Return to main menu",
    ):
        assert label in bare, label
        assert label in full, label


# -- edit entity: fields, deletion and its confirmation ---------------------


def test_an_entity_can_be_edited_and_another_deleted():
    status, out, services = run(
        NEW_JOB
        + ADD_PROTEIN
        + ADD_LIGAND("ATP", "1")
        + ["3", "1", "1", "MKTAYIAKQR", "kinase", "1", "", "0", "0"]
        + ["3", "2", "2", "1"]          # pick the ligand → Delete → Yes
        + ["0"]                         # picker → job menu
        + LEAVE_DIRTY
    )
    assert status == 0
    configuration = services.projects.project.configuration
    assert [record.ids.primary.value for record in configuration.records] == ["A"]
    assert configuration.records[0].sequence.text == "MKTAYIAKQR"
    assert "Removed 'B'." in out


def test_deleting_an_entity_can_be_cancelled_at_the_confirm():
    status, out, services = run(
        NEW_JOB
        + ADD_PROTEIN
        + ["3", "1", "2", "2"]          # Delete → No, go back
        + ["0", "0"]                    # action → picker → job
        + LEAVE_DIRTY
    )
    assert status == 0
    assert len(services.projects.project.configuration.records) == 1


def test_an_empty_job_says_there_is_nothing_to_edit():
    status, out, _ = run(NEW_JOB + ["3"] + LEAVE_CLEAN)
    assert status == 0
    assert "(no entities)" in out
    assert "There are no entities to edit" in out


# -- modifications: the per-record submenu and PTM management ----------------


def test_the_entity_modifications_submenu_adds_edits_and_removes():
    status, out, services = run(
        NEW_JOB
        + ADD_PROTEIN
        + ["3", "1", "3", "1", "SEP", "5", "0", "0", "0"]     # add → back to job
        + ["3", "1", "3", "2", "1", "", "7", "0", "0", "0"]   # edit row 1 → position 7
        + ["3", "1", "3", "3", "1", "0", "0", "0"]            # remove row 1
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "Post-translational modification added." in out
    assert "Post-translational modification updated." in out
    assert "Post-translational modification removed." in out
    record = services.projects.project.configuration.records[0]
    assert record.modifications == ()


def test_ptm_management_adds_edits_and_removes():
    status, out, services = run(
        NEW_JOB
        + ADD_PROTEIN
        + ["5", "2", "1", "TPO", "3"]                          # add to entity A
        + ["5", "3", "1", "1", "", "4"]                        # edit row 1 → position 4
        + ["5", "4", "1", "1"]                                 # remove row 1
        + ["0"]                                                  # PTM → job
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "Post-translational modification added." in out
    assert "Post-translational modification updated." in out
    assert "Post-translational modification removed." in out
    assert services.projects.project.configuration.records[0].modifications == ()


def test_a_ligand_carries_no_modifications_and_is_told_so():
    status, out, _ = run(
        NEW_JOB
        + ADD_LIGAND("ATP", "1")
        + ["5", "2"]                    # PTM → add → the carrier picker is empty
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "ligands carry no post-translational modifications" in out


# -- custom CCD management ---------------------------------------------------


def test_a_custom_ccd_definition_can_be_added_viewed_and_removed():
    status, out, services = run(
        NEW_JOB
        + ["4", "1"]                          # view: none yet
        + ["4", "2", "1", "data_probe", ""]   # add inline (blank line ends it)
        + ["4", "1"]                          # view: the definition
        + ["4", "3", "1"]                     # remove → Yes (set/replace is 2)
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "No custom CCD definition is set for this job." in out
    assert "Inline CIF definition: data_probe" in out
    assert "Total lines: 1" in out
    assert "Custom CCD definition removed." in out
    assert services.projects.project.configuration.component_definition is None


def test_a_custom_ccd_definition_can_be_a_file(tmp_path):
    cif = tmp_path / "probe.cif"
    cif.write_text("data_probe\n", encoding="utf-8")
    status, out, services = run(NEW_JOB + ["4", "2", "2", str(cif)] + LEAVE_DIRTY)
    assert status == 0
    assert "Custom CCD definition set." in out
    definition = services.projects.project.configuration.component_definition
    assert isinstance(definition, External)
    assert definition.path.raw == str(cif)


def test_an_inline_ccd_definition_is_kept_in_the_model(tmp_path):
    status, out, services = run(
        NEW_JOB
        + ["4", "2", "1", "data_probe", "loop_", ""]
        + LEAVE_DIRTY
    )
    assert status == 0
    definition = services.projects.project.configuration.component_definition
    assert isinstance(definition, Inline)
    assert definition.text.startswith("data_probe")


def test_the_ccd_source_menu_can_be_cancelled():
    status, out, services = run(NEW_JOB + ["4", "2", "0"] + LEAVE_CLEAN)
    assert status == 0
    assert services.projects.project.configuration.component_definition is None


# -- save and show summary ---------------------------------------------------


def test_save_reports_the_path_and_writes_a_contract_shaped_file(tmp_path):
    destination = tmp_path / "job.json"
    status, out, _ = run(protein_job() + ["6", str(destination)] + LEAVE_CLEAN)
    assert status == 0
    assert "JOB SUMMARY" in out
    assert "Saved to " in out
    document = load(destination)
    assert document["dialect"] == "alphafold3"
    assert document["version"] == 3
    assert document["modelSeeds"] == [1]
    assert document["sequences"][0]["protein"]["sequence"] == PROTEIN


def test_save_refuses_an_incomplete_job_and_writes_nothing(tmp_path):
    destination = tmp_path / "empty.json"
    status, out, _ = run(NEW_JOB + ["6", str(destination)] + LEAVE_CLEAN)
    assert status == 0
    assert "This job cannot be saved yet:" in out
    assert "STATUS: INCOMPLETE" in out
    assert not destination.exists()


def test_save_cancelled_writes_nothing(tmp_path):
    status, out, _ = run(protein_job() + ["6", "0"] + LEAVE_DIRTY)
    assert status == 0
    assert "Cancelled — nothing was written." in out
    assert written(tmp_path) == []


def test_save_overwrite_is_confirmed_before_replacing(tmp_path):
    destination = tmp_path / "job.json"
    status, out, _ = run(
        protein_job()
        + ["6", str(destination)]                       # first save
        + ADD_LIGAND("ATP", "1")                        # the job moves on
        + ["6", str(destination), "2"]                  # second save: No, cancel
        + ["6", str(destination), "1"]                  # third save: Yes, overwrite
        + LEAVE_CLEAN
    )
    assert status == 0
    assert "already exists. Overwrite it?" in out
    assert out.count("Cancelled — nothing was written.") == 1
    document = load(destination)
    assert len(document["sequences"]) == 2
    assert any("ligand" in entry for entry in document["sequences"])


def test_the_summary_reports_the_jobs_own_counts():
    status, out, _ = run(
        protein_job() + ADD_LIGAND("ATP", "2") + ["6", "0"] + LEAVE_DIRTY
    )
    assert status == 0
    assert "Number of entities: 2" in out
    assert "- Proteins: 1" in out
    assert "- Ligands:  1" in out


def test_leaving_with_unsaved_changes_asks_first_and_cancel_stays():
    status, out, services = run(
        NEW_JOB
        + ADD_PROTEIN
        + ["0", "3"]                    # leave → Cancel: the prompt is a choice
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "Save before leaving?" in out
    assert "This job has changes that have not been saved to a JSON file." in out
    assert len(services.projects.project.configuration.records) == 1


def test_leave_and_save_writes_the_file_then_returns_to_the_main_menu(tmp_path):
    destination = tmp_path / "leaving.json"
    status, out, _ = run(
        NEW_JOB + ADD_PROTEIN + ["0", "1", str(destination)] + ["0"]
    )
    assert status == 0
    assert "Saved to " in out
    assert load(destination)["sequences"][0]["protein"]["sequence"] == PROTEIN


# -- ligand configuration generation: one file in, one file per entry out ----


def test_a_ligand_file_writes_one_configuration_per_entry(tmp_path):
    """The job is the base; every entry becomes one independent file."""
    listing = tmp_path / "ligands.smiles"
    listing.write_text("ethanol CCO\nacetic-acid CC(=O)O\n", encoding="utf-8")
    output = tmp_path / "out"
    status, out, services = run(
        protein_job()
        + ["7", "1", "4", str(listing), str(output)]   # kind, file, then folder
        + ["0"]                                   # back to the job menu
        + LEAVE_CLEAN
    )
    assert status == 0
    assert "2 entries read" in out
    assert "Wrote" in out
    written_files = sorted(
        path.name for path in (output / "job").rglob("*.json")
    )
    assert written_files == [
        "job__acetic-acid.json",
        "job__ethanol.json",
        "manifest.json",
    ]
    document = load(str(output / "job" / "job__ethanol" / "job__ethanol.json"))
    assert document["sequences"][0]["protein"]["sequence"] == PROTEIN
    added = [
        entry["ligand"] for entry in document["sequences"] if "ligand" in entry
    ]
    assert [body["smiles"] for body in added] == ["CCO"]
    # the job on screen is the base: one record, no spec catalogue, unchanged
    configuration = services.projects.project.configuration
    assert len(configuration.records) == 1
    assert configuration.records[0].sequence.text == PROTEIN
    assert services.projects.project.specs == ()


def test_a_refused_ligand_file_writes_nothing(tmp_path):
    """A duplicate molecule refuses the file before a folder is even asked for."""
    listing = tmp_path / "duplicates.smiles"
    listing.write_text("one CCO\ntwo CCO\n", encoding="utf-8")
    output = tmp_path / "out"
    status, out, services = run(
        protein_job() + ["7", "1", "4", str(listing), str(output), "0"] + LEAVE_CLEAN
    )
    assert status == 0
    assert "duplicate ligand entries" in out
    assert "Nothing was written" in out
    assert not output.exists()
    assert len(services.projects.project.configuration.records) == 1


def test_the_file_workflow_offers_only_its_one_action():
    """The manual variant editor is not reachable from the job menu."""
    status, out, _ = run(protein_job() + ["7", "0"] + LEAVE_DIRTY)
    assert status == 0
    assert "CONFIGURATION GENERATION FROM A FILE" in out
    assert "1. Load an input file and generate configurations" in out
    for obsolete in (
        "Vary the entities in this job",
        "Set variant job name",
        "Save variant and reset to base",
        "View all variants",
        "Create variants based on this JSON",
    ):
        assert obsolete not in out, obsolete


# -- open a JSON file --------------------------------------------------------


def _af3_file(tmp_path, name="in.json", job="imported", seeds=(1, 2)):
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "name": job,
                "modelSeeds": list(seeds),
                "sequences": [{"protein": {"id": "A", "sequence": PROTEIN}}],
                "dialect": "alphafold3",
                "version": 4,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_open_json_reports_the_preview_and_replaces_the_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _af3_file(tmp_path)
    status, out, services = run(["2", str(path)] + LEAVE_CLEAN)
    assert status == 0
    assert "Name: imported" in out
    assert "Entities: 1" in out
    assert "Seeds: [1, 2]" in out
    assert "JSON opened. It is now a normal, editable job." in out
    configuration = services.projects.project.configuration
    assert configuration.metadata.name == "imported"
    assert list(configuration.seeds.values) == [1, 2]
    assert configuration.records[0].sequence.text == PROTEIN


def test_open_json_can_be_cancelled_at_the_picker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, out, services = run(["2", "0", "0"])
    assert status == 0
    assert "JSON opened." not in out
    assert services.projects.project is None


def test_open_json_reports_malformed_and_missing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    broken = tmp_path / "broken.json"
    broken.write_text('{"name": "x", "sequences": [', encoding="utf-8")
    status, out, _ = run(["2", str(broken), "0"])
    assert status == 0
    assert "Could not open this JSON." in out
    assert "The original file has not been modified." in out

    status, out, _ = run(["2", str(tmp_path / "nope.json"), "0"])
    assert status == 0
    assert "Could not open this JSON." in out


def test_open_json_reports_unsupported_fields_while_loading(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "extra.json"
    path.write_text(
        json.dumps(
            {
                "name": "extra",
                "modelSeeds": [1],
                "sequences": [
                    {"protein": {"id": "A", "sequence": PROTEIN, "weirdField": 1}}
                ],
                "dialect": "alphafold3",
                "version": 4,
                "extraTop": True,
            }
        ),
        encoding="utf-8",
    )
    status, out, services = run(["2", str(path)] + LEAVE_CLEAN)
    assert status == 0
    assert "not supported for editing" in out
    # the supported parts are preserved
    assert services.projects.project.configuration.records[0].sequence.text == PROTEIN


def test_an_opened_job_can_be_edited_and_saved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = _af3_file(tmp_path)
    destination = tmp_path / "out" / "saved.json"
    status, out, _ = run(
        ["2", str(source)]
        + ["3", "1", "1", OTHER_PROTEIN, "", "1", "", "0", "0"]
        + ["6", str(destination)]
        + LEAVE_CLEAN
    )
    assert status == 0
    assert load(destination)["sequences"][0]["protein"]["sequence"] == OTHER_PROTEIN
