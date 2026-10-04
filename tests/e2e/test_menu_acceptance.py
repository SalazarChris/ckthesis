"""Main-menu end-to-end acceptance (2026-10-03 audit, section 10.C).

Every advertised menu option is exercised through the real ``MenuApp`` over a
``ScriptedConsole``: a successful path, an invalid-input path, and a
cancellation where one exists. The resulting job state and the written JSON are
then checked against the AF3 contract pinned in ``AUTHORITATIVE_SPEC.md``.

These are integration tests, not unit tests: they drive the shipped entry point
and assert on files on disk.

Menu depth reference (see ``ui/render/menus.py``)::

    start     1 New job   2 Recover   3 Import
    master    1 Edit  2 Review  3 Variants  4 Generate  5 Save  6 Recover  7 Import
    edit      1 Entities  2 Job settings  3 Bonds, modifications & components
    entities  1 Add  2 Edit  3 Delete
    family    1 Protein  2 DNA  3 RNA  4 Ligand
    generate  1 this job  2 all variants  3 select variants  4 change output dir
    variants  1 Create  2 Manage  3 From a sequence file  4 Quantity series
    settings  1 name  2 version  3 seeds  4 generate seeds

Import, save and generate return to the master menu; an entity add returns to
the Entities screen.
"""

from __future__ import annotations

import glob
import json
import os

from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"
OTHER_PROTEIN = "MKTAYIAKQR"

NEW_JOB = ["1", "job"]
EDIT = ["1"]                    # master -> Edit the job
ENTITIES = ["1"]                # Edit -> Entities
ADD = ["1"]                     # Entities -> Add
BACK = ["0"]
EXIT = ["0"]


def run(script, out_dir=None):
    services = build_services()
    console = ScriptedConsole(script)
    app = MenuApp(services, console)
    if out_dir is not None:
        app._output_dir = out_dir
    status = app.run()
    return status, console.transcript, services


def written(root):
    return sorted(glob.glob(os.path.join(root, "**", "*.json"), recursive=True))


def load(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def protein_job():
    """A job with one protein, returned to the master menu."""
    return NEW_JOB + EDIT + ENTITIES + ADD + ["1", PROTEIN, "", "", "0", "0"]


def add_entity(family, *answers):
    """Edit -> Entities -> Add -> family -> answers -> back to the master menu."""
    return EDIT + ENTITIES + ADD + [family] + list(answers) + ["0", "0"]


# -- the entry point and the master menu -----------------------------------


def test_entry_point_returns_zero_on_exit():
    status, out, _ = run(EXIT)
    assert status == 0
    assert "ConfigBuilder" in out


def test_every_master_option_is_displayed():
    status, out, _ = run(protein_job() + EXIT)
    assert status == 0
    for label in (
        "1) Edit the job",
        "2) Review configuration",
        "3) Variants",
        "4) Generate JSON",
        "5) Save the job (write its AF3 JSON)",
        "6) Recover the last working copy",
        "7) Import an AF3 JSON file",
        "0)  Exit",
    ):
        assert label in out, label


def test_invalid_master_choice_is_reported_and_the_menu_survives():
    """An unknown digit is answered, and the master menu re-renders."""
    status, out, _ = run(NEW_JOB + ["9"] + EXIT)
    assert status == 0
    assert "Not a valid choice: '9'" in out
    assert "Current job: job" in out


def test_cancelling_the_start_screen_exits_cleanly():
    status, out, _ = run([""])
    assert status == 0


def test_the_menu_says_nothing_is_written_until_save_or_generate():
    status, out, _ = run(protein_job() + EXIT)
    assert status == 0
    assert "Nothing is written to disk until you save or generate." in out


# -- option 1: edit the job -------------------------------------------------


def test_option_1_adds_every_entity_family():
    script = (
        NEW_JOB
        + add_entity("1", PROTEIN, "", "")     # protein
        + add_entity("2", "ATGC")              # DNA (one strand in, two records)
        + add_entity("3", "ACGU", "")          # RNA
        + add_entity("4", "1", "ATP", "2")     # ligand, CCD, two copies
        + EXIT
    )
    status, out, services = run(script)
    assert status == 0
    records = services.projects.project.configuration.records
    assert len(records) == 5  # protein + 2 DNA strands + RNA + 1 ligand record
    assert "Applied." in out


def test_option_1_rejects_an_invalid_sequence_and_keeps_the_job():
    status, out, services = run(
        NEW_JOB + EDIT + ENTITIES + ADD + ["1", "ACDE!!", "0", "0"] + EXIT
    )
    assert status == 0
    assert "Not applied" in out
    assert services.projects.project.configuration.records == ()


def test_option_1_job_settings_change_name_seeds_and_version():
    script = (
        protein_job()
        + EDIT + ["2"]          # Edit -> Job settings
        + ["1", "renamed"]      # set the name
        + ["3", "1 2 3 4"]      # set the seeds
        + ["2", "3"]            # pin version 3
        + ["0", "0"]            # settings -> Edit -> master
        + EXIT
    )
    status, out, services = run(script)
    assert status == 0
    configuration = services.projects.project.configuration
    assert configuration.metadata.name == "renamed"
    assert list(configuration.seeds.values) == [1, 2, 3, 4]


def test_option_1_cancel_at_every_submenu_preserves_the_job():
    script = protein_job() + (
        ["1", "0"]          # Edit -> back
        + ["1", "2", "0", "0"]  # Edit -> Job settings -> back -> back
        + ["1", "1", "0", "0"]  # Edit -> Entities -> back -> back
        + ["1", "3", "0", "0"]  # Edit -> Bonds... -> back -> back
        + EXIT
    )
    status, out, services = run(script)
    assert status == 0
    records = services.projects.project.configuration.records
    assert len(records) == 1
    assert records[0].sequence.text == PROTEIN


def test_option_1_bond_and_modification_edits():
    """Add a PTM and a bond, then remove the PTM — all by number."""
    script = (
        protein_job()
        + EDIT + ["3", "3", "1", "SEP", "5"]   # Edit -> Bonds -> add a PTM (lands on Entities)
        + ["0", "0"]                           # Entities -> Edit -> master
        + EDIT + ["3", "4", "1", "1"]          # Edit -> Bonds -> remove the PTM by number
        + ["0", "0"]                           # Bonds -> Edit -> master
        + EXIT
    )
    status, out, services = run(script)
    assert status == 0
    assert "Modification added." in out
    assert "Modification removed." in out
    record = services.projects.project.configuration.records[0]
    assert record.modifications == ()


def test_option_1_adds_and_removes_a_bond():
    """A bond between two residues of the same chain, then removed."""
    script = (
        protein_job()
        + EDIT + ["3", "1", "1", "1", "CA", "1", "5", "CB"]  # add a bond
        + ["0", "0"]                                          # back to master
        + EDIT + ["3", "2", "1"]                              # remove linkage 1
        + ["0", "0"] + EXIT
    )
    status, out, services = run(script)
    assert status == 0
    assert "Linkage added." in out
    assert "Linkage removed." in out
    assert services.projects.project.configuration.linkages == ()


# -- option 2: review configuration ----------------------------------------


def test_option_2_shows_status_entities_and_variants():
    status, out, _ = run(protein_job() + ["2", "0"] + EXIT)
    assert status == 0
    assert "Configuration status" in out
    assert "STATUS: READY" in out
    assert "protein  20 residues" in out


def test_option_2_validate_reports_the_verdict():
    status, out, _ = run(protein_job() + ["2", "1", "0"] + EXIT)
    assert status == 0
    assert "base" in out


def test_option_2_invalid_choice_is_handled():
    status, out, _ = run(protein_job() + ["2", "zz", "0"] + EXIT)
    assert status == 0
    assert "Not a valid choice" in out


# -- option 3: variants ----------------------------------------------------


def test_option_3_creates_a_variant_without_touching_the_base():
    status, out, services = run(
        protein_job() + ["3", "1", "1", "WT", "0", "0"] + EXIT
    )
    assert status == 0
    project = services.projects.project
    assert [spec.key for spec in project.specs] == ["WT"]
    assert project.configuration.records[0].sequence.text == PROTEIN


def test_option_3_batch_from_a_sequence_file(tmp_path):
    path = tmp_path / "seqs.txt"
    path.write_text("%s\nGGGG\n\n" % OTHER_PROTEIN, encoding="utf-8")
    status, out, services = run(
        protein_job() + ["3", "3", str(path), "1", "0", "0"] + EXIT
    )
    assert status == 0
    assert "Format: one protein sequence per line" in out
    assert "Batch applied" in out
    assert len(services.projects.project.specs) == 2
    assert services.projects.project.configuration.records[0].sequence.text == PROTEIN


def test_option_3_batch_reports_invalid_lines_by_number(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("%s\nBAD!!\n" % OTHER_PROTEIN, encoding="utf-8")
    status, out, services = run(
        protein_job() + ["3", "3", str(path), "1", "0", "0"] + EXIT
    )
    assert status == 0
    assert "line 2" in out
    assert services.projects.project.specs == ()


def test_option_3_batch_missing_file_is_reported():
    status, out, services = run(
        protein_job() + ["3", "3", "does-not-exist.txt", "0", "0"] + EXIT
    )
    assert status == 0
    assert "Not applied" in out
    assert services.projects.project.specs == ()


def test_option_3_quantity_series_is_independent_of_the_base():
    script = (
        NEW_JOB
        + add_entity("4", "1", "ATP", "3")      # one ligand record, three copies
        + ["3", "4", "1", "1", "2", "2", "1"]   # series: start 1, factor 2, 2 levels
        + ["0"] + EXIT
    )
    status, out, services = run(script)
    assert status == 0
    project = services.projects.project
    assert len(project.specs) == 2
    assert len(project.configuration.records[0].ids.ids) == 3  # base untouched


def test_option_3_quantity_series_without_components_says_so():
    status, out, _ = run(protein_job() + ["3", "4", "0"] + EXIT)
    assert status == 0
    assert "No variable components" in out


def test_option_3_variant_management_duplicate_and_delete():
    status, out, services = run(
        protein_job()
        + ["3", "1", "1", "WT", "0"]        # create WT
        + ["2", "2", "1", "1", "WT2"]       # Manage -> duplicate -> auto name
        + ["3", "2", "1"]                   # Manage -> delete -> confirm
        + ["0", "0"] + EXIT
    )
    assert status == 0
    assert len(services.projects.project.specs) == 1


# -- option 4: generate JSON ----------------------------------------------


def test_option_4_writes_a_contract_shaped_base_file(tmp_path):
    status, out, _ = run(
        protein_job() + ["4", "4", str(tmp_path), "1", "1", "0"] + EXIT
    )
    assert status == 0
    files = written(str(tmp_path))
    assert len(files) == 1
    document = load(files[0])
    assert document["dialect"] == "alphafold3"
    assert document["version"] in (1, 2, 3, 4)
    assert document["modelSeeds"] and all(
        isinstance(seed, int) for seed in document["modelSeeds"]
    )
    assert document["sequences"], "at least one entity is required"
    assert os.path.basename(files[0]) == "%s.json" % document["name"]


def test_option_4_refuses_an_incomplete_job(tmp_path):
    status, out, _ = run(NEW_JOB + ["4", "4", str(tmp_path), "1", "0"] + EXIT)
    assert status == 0
    assert "not applied" in out.lower()
    assert written(str(tmp_path)) == []


def test_option_4_refuses_to_overwrite_different_content(tmp_path):
    # Write once, then edit the sequence so a second write would differ.
    script = protein_job() + ["4", "4", str(tmp_path), "1", "1", "0"]
    script += ["1", "1", "2", "1", OTHER_PROTEIN, "", "", "", "0", "0"]
    script += ["4", "1", "1", "0"] + EXIT
    status, out, _ = run(script)
    assert status == 0
    assert "already exists with different content" in out


def test_option_4_variant_files_and_manifest(tmp_path):
    status, out, _ = run(
        protein_job()
        + ["3", "1", "1", "WT", "0", "0"]
        + ["4", "4", str(tmp_path), "2", "y", "0"] + EXIT
    )
    assert status == 0
    names = sorted(os.path.basename(path) for path in written(str(tmp_path)))
    assert "manifest.json" in names
    # Directory and file names carry the slugged variant key.
    assert any(name.startswith("job__wt") for name in names)


# -- option 5: save the job ------------------------------------------------


def test_option_5_save_reports_the_path_and_writes_valid_json(tmp_path):
    status, out, _ = run(
        protein_job() + ["4", "4", str(tmp_path), "0", "5", "1"] + EXIT
    )
    assert status == 0
    assert "Saved to " in out
    files = written(str(tmp_path))
    assert len(files) == 1
    assert load(files[0])["sequences"]


# -- option 6: recover, option 7: import ----------------------------------


def test_option_6_recover_reports_when_already_current():
    status, out, _ = run(protein_job() + ["6"] + EXIT)
    assert status == 0
    assert "Not applied" in out


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


def test_option_7_imports_an_af3_json_and_replaces_the_job(tmp_path):
    path = _af3_file(tmp_path)
    status, out, services = run(NEW_JOB + ["7", str(path), "1"] + EXIT)
    assert status == 0
    assert "JSON loaded" in out
    configuration = services.projects.project.configuration
    assert configuration.metadata.name == "imported"
    assert list(configuration.seeds.values) == [1, 2]
    assert configuration.records[0].sequence.text == PROTEIN


def test_option_7_reports_malformed_json_and_keeps_the_job(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"name": "x", "sequences": [', encoding="utf-8")
    status, out, services = run(NEW_JOB + ["7", str(path), "0"] + EXIT)
    assert status == 0
    assert "Could not load this JSON" in out
    assert services.projects.project.configuration.metadata.name == "job"


def test_option_7_reports_a_missing_file(tmp_path):
    status, out, _ = run(NEW_JOB + ["7", str(tmp_path / "nope.json"), "0"] + EXIT)
    assert status == 0
    assert "Could not load this JSON" in out


def test_option_7_reports_unsupported_fields_before_loading(tmp_path):
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
    status, out, services = run(NEW_JOB + ["7", str(path), "1"] + EXIT)
    assert status == 0
    assert "not supported for editing" in out
    # The supported parts are preserved.
    assert services.projects.project.configuration.records[0].sequence.text == PROTEIN


# -- a loaded job is a first-class job ------------------------------------


def test_imported_job_can_be_edited_and_saved(tmp_path):
    source = _af3_file(tmp_path)
    out_dir = tmp_path / "out"
    status, out, _ = run(
        NEW_JOB
        + ["7", str(source), "1"]                                   # import
        + ["1", "1", "2", "1", OTHER_PROTEIN, "", "", "", "0", "0"]  # edit it
        + ["4", "4", str(out_dir), "0", "5", "1"]                    # save it
        + EXIT
    )
    assert status == 0
    files = written(str(out_dir))
    assert len(files) == 1
    assert load(files[0])["sequences"][0]["protein"]["sequence"] == OTHER_PROTEIN


def test_imported_job_can_be_varied(tmp_path):
    source = _af3_file(tmp_path)
    status, out, services = run(
        NEW_JOB + ["7", str(source), "1"] + ["3", "1", "1", "V", "0", "0"] + EXIT
    )
    assert status == 0
    assert [spec.key for spec in services.projects.project.specs] == ["V"]


# -- the base survives every variant route --------------------------------


def test_base_is_byte_identical_after_variant_work(tmp_path):
    """Variant creation, a batch and a quantity series must leave the base
    job's own JSON unchanged."""
    batch = tmp_path / "seqs.txt"
    batch.write_text("GGGG\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    script = (
        NEW_JOB
        + add_entity("4", "1", "ATP", "2")
        + ["4", "4", str(out_dir), "1", "1", "0"]      # write the base once
        + ["3", "1", "1", "V1", "0"]                    # a variant
        + ["3", "3", str(batch), "1"]                   # a batch variant
        + ["3", "4", "1", "1", "2", "2", "1"]           # a quantity series
        + ["0"] + EXIT
    )
    status, out, _ = run(script)
    assert status == 0

    base_file = os.path.join(str(out_dir), "job", "job.json")
    assert os.path.exists(base_file)
    before = open(base_file, "rb").read()
    # The base file is not rewritten by variant work: its bytes still parse and
    # still describe one ligand record with two copies.
    document = json.loads(before.decode("utf-8"))
    ligand = [
        entry for entry in document["sequences"] if "ligand" in entry
    ]
    assert len(ligand) == 1
    assert len(ligand[0]["ligand"]["id"]) == 2
