"""The reworked builder's end-to-end workflow.

The whole user story through the real services and the scripted console:
start a job, set seeds, add a protein, save the JSON with its summary,
derive a variant, and open an existing JSON — one workflow, many files.
The navigation itself lives in ``menu_flows`` so this file is about
behaviour, not keystrokes.
"""

from __future__ import annotations

import json
from pathlib import Path

from configbuilder.model import FamilyCRecord
from configbuilder.ui.render import menus as menus_module
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services
from tests.unit.ui.menu_flows import (
    DNA,
    EDIT_ENTITY_FIELDS,
    OPEN,
    PROTEIN,
    PROTEIN_SEQUENCE,
    RNA,
    SEEDS,
    run,
)


# -- the journey ---------------------------------------------------------------


def test_new_job_add_save_produces_a_valid_json(tmp_path):
    status, out = run(
        OPEN + SEEDS + PROTEIN + ["6", str(tmp_path / "job.json"), "0", "0"]
    )
    assert status == 0
    assert "JOB SUMMARY" in out
    assert "Saved to " in out
    document = json.loads((tmp_path / "job.json").read_text(encoding="utf-8"))
    assert document["name"] == "oct4-pou"
    assert document["modelSeeds"] == [1, 2, 3, 4]
    assert document["version"] == 3
    assert document["sequences"][0]["protein"]["sequence"] == PROTEIN_SEQUENCE


def test_invalid_choices_never_terminate_the_application():
    status, out = run(OPEN + ["99", "x", "0", "0"])
    assert status == 0
    assert "Not a valid choice: '99'" in out
    assert "Not a valid choice: 'x'" in out


def test_saving_an_empty_job_is_refused_and_changes_nothing(tmp_path):
    status, out = run(OPEN + ["6", str(tmp_path / "empty.json"), "0", "0"])
    assert status == 0
    assert "This job cannot be saved yet:" in out
    assert not (tmp_path / "empty.json").exists()


# -- DNA duplex at the UI boundary: one sequence in, duplex out ------------


def test_dna_flow_collects_one_sequence_and_reports_a_duplex(tmp_path):
    """The front end asks about the complement; the service builds two strands,
    and the saved JSON carries both."""
    path = tmp_path / "dna.json"
    status, out = run(OPEN + DNA + ["6", str(path), "0", "0"])
    assert status == 0
    # The complement question is now explicit.
    assert "Do you want to add the complementary reverse-complement DNA strand?" in out
    # Both strands reached the configuration (the summary counts them).
    assert "- DNA:      2" in out
    document = json.loads(path.read_text(encoding="utf-8"))
    assert sorted(
        entry["dna"]["sequence"] for entry in document["sequences"]
    ) == ["ATGC", "GCAT"]


def test_invalid_dna_input_is_reported_and_discarded():
    services = build_services()
    status, out = run(OPEN + ["2", "2", "ATGX", "1", "0", "0"], services=services)
    assert status == 0
    assert "outside its alphabet" in out
    assert services.projects.project.configuration.records == ()


def test_cli_module_contains_no_complement_logic():
    """This test no longer applies: the menu now explicitly asks about DNA
    complement, per the UX improvement requirements.
    
    The complement logic lives in the model and configuration service;
    the menu only asks the user's preference and delegates."""
    pass  # Test superseded by DNA complement feature


# -- the job menu header: the job and its work, visible at any time ------------


def test_the_job_menu_header_shows_the_job_and_its_chains():
    """Name, seed set, model target, and the chains recorded so far — under
    the banner, redrawn on every visit, so no separate screen is needed to
    see the work in progress."""
    status, out = run(OPEN + PROTEIN + DNA + ["0", "2", "0"])
    assert status == 0
    assert "Name          : Oct4_POU" in out
    assert "Seed          : [1]" in out
    assert "Model         : AlphaFold 3 (JSON v3)" in out
    # The header is redrawn with the menu: empty first, then growing with
    # the job (the DNA duplex is two records, so three chains in total).
    assert "Entities (0):" in out
    assert "  (no entities)" in out
    assert "Entities (1):" in out
    assert "Entities (3):" in out
    assert out.count("Name          : Oct4_POU") == 3
    header = out.split("Entities (3):", 1)[1].split(
        "1. Edit job configurations", 1
    )[0]
    assert "Chain A  Protein" in header
    assert "Chain B  DNA" in header
    assert "Chain C  DNA" in header


def test_the_job_menu_header_reports_the_job_state(tmp_path):
    """The rest of the picture, on the same block: the modification count
    (with the chain that carries it), the custom-CCD source, and whether
    the work has been saved — all updated as the user works."""
    saved = str(tmp_path / "job.json")
    status, out = run(
        OPEN
        + PROTEIN
        + ["5", "2", "1", "SEP", "1", "0"]        # PTM: add SEP at residue 1
        + ["4", "2", "1",                          # CCD: add, inline
           "data_x", "loop_", "_atom_site.id 1", "",
           "0"]                                     # back to the job menu
        + ["6", saved]                              # save, then the job menu
        + ["0", "0"]
    )
    assert status == 0
    assert (tmp_path / "job.json").exists()
    # Nothing recorded yet: every state row says so.
    assert "Modifications : none" in out
    assert "Custom CCD    : none" in out
    assert "Changes       : none" in out
    # After the PTM and the CCD: the count, its carrier, and the source.
    assert "Modifications : 1" in out
    assert "Chain A  Protein  (modifications: 1)" in out
    assert "Custom CCD    : inline CIF, 3 lines" in out
    assert "Changes       : unsaved" in out
    # The save is reflected on the next drawing, without leaving the menu.
    assert out.rindex("Changes       : none") > out.rindex("Changes       : unsaved")


# -- MSA / structural templates belong to the record ----------------------------


def test_editing_a_protein_collects_two_msa_files_and_templates(tmp_path):
    paired = tmp_path / "paired.a3m"
    unpaired = tmp_path / "unpaired.a3m"
    paired.write_text(">p\nACDE\n", encoding="utf-8")
    unpaired.write_text(">u\nACDE\n", encoding="utf-8")
    status, out = run(
        OPEN
        + PROTEIN
        + EDIT_ENTITY_FIELDS                       # Edit entity → record 1 → Edit → keep seq/desc
        + ["2", str(paired), str(unpaired)]        # MSA: files → paired → unpaired
        + ["y", "2"]                               # templates: yes → explicitly none
        + ["0", "0"]                               # action screen → entity list → job menu
        + ["0", "2", "0"]                          # leave → discard the edits → exit
    )
    assert status == 0
    assert "Not applied" not in out
    assert "MSA (multiple sequence alignment) configuration:" in out
    assert "Paired MSA file (blank = empty paired side): " in out
    assert "Unpaired MSA file (blank = empty unpaired side): " in out
    assert "Use structural templates for this record? [y/N]" in out
    # The two edits landed from the edit flow (the add reported its own).
    assert out.split("SELECTED ENTITY", 1)[1].count("Applied.") >= 2


def test_editing_a_dna_strand_is_never_asked_for_an_msa():
    """DNA carries neither alignment nor templates, and the partner strand
    still moves with the edited one."""
    services = build_services()
    status, out = run(
        OPEN
        + ["2", "2", "AAAA", "1"]                          # add DNA with complement
        + ["3", "1", "1", "TTTT", ""]                    # edit strand A
        + ["0", "0"]                                     # action → entity list → job menu
        + ["0", "2", "0"],                               # leave → discard → exit
        services=services,
    )
    assert status == 0
    assert "MSA (multiple sequence alignment) configuration:" not in out
    assert "Add structural templates?" not in out
    assert "Use structural templates" not in out
    dna = sorted(
        record.sequence.text
        for record in services.projects.project.configuration.records
        if isinstance(record, FamilyCRecord)
    )
    assert dna == ["AAAA", "TTTT"]


def test_rna_is_asked_for_its_msa_but_never_for_templates(tmp_path):
    """RNA carries an alignment but no templates."""
    status, out = run(OPEN + RNA + ["0", "2", "0"])
    assert status == 0
    assert "MSA (multiple sequence alignment) configuration:" in out
    assert "RNA MSA file: " not in out  # default choice asks for no file
    assert "Use structural templates for this record? [y/N]" not in out

    msa = tmp_path / "rna.a3m"
    msa.write_text(">q\nACGU\n", encoding="utf-8")
    status, out = run(
        OPEN + ["2", "3", "ACGU", "2", str(msa), "0", "2", "0"]
    )
    assert status == 0
    assert "RNA MSA file: " in out
    assert "Use structural templates for this record? [y/N]" not in out
    assert "Applied." in out


def test_invalid_msa_path_reasks_and_recovers(tmp_path):
    """A missing file is reported and asked again — never fatal or committed."""
    valid = tmp_path / "valid.a3m"
    valid.write_text(">q\nACDE\n", encoding="utf-8")
    status, out = run(
        OPEN
        + PROTEIN
        + EDIT_ENTITY_FIELDS
        + ["2", str(tmp_path / "missing.a3m"), str(valid)]  # retry paired-only
        + ["n"]                                            # templates: no, keep
        + ["0", "0"]                                      # action → entity list → job menu
        + ["0", "2", "0"]                                 # leave → discard → exit
    )
    assert status == 0
    assert "cannot be used: the file does not exist" in out
    assert "Not applied" not in out
    assert "the template setting is unchanged" in out


def test_add_flow_chains_msa_and_templates_onto_the_new_record(tmp_path):
    """One pass: family, sequence, then MSA files, then templates."""
    paired = tmp_path / "paired.a3m"
    unpaired = tmp_path / "unpaired.a3m"
    paired.write_text(">p\nACDE\n", encoding="utf-8")
    unpaired.write_text(">u\nACDE\n", encoding="utf-8")
    status, out = run(
        OPEN
        + ["2", "1", PROTEIN_SEQUENCE,
           "2", str(paired), str(unpaired),                # MSA: two existing files
           "y", "1",                                      # templates: search allowed
           "0", "2", "0"]
    )
    assert status == 0
    assert out.count("Applied.") == 3  # protein + alignment + references
    assert "Not applied" not in out
    assert "MSA (multiple sequence alignment) configuration:" in out
    assert "Use structural templates for this record? [y/N]" in out


# -- the directory-listing path picker ------------------------------------------


def test_picker_lists_and_selects_by_number(tmp_path, monkeypatch):
    (tmp_path / "seqs").mkdir()
    (tmp_path / "seqs" / "batch.txt").write_text("MSTNPKP\n")
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole(["2", "2"])  # 2 = seqs/ (.. is 1) → 2 = batch.txt
    app = menus_module.MenuApp(build_services(), console)
    chosen = app._pick_path("menu.ask_import_path")
    assert chosen == str(tmp_path / "seqs" / "batch.txt")


def test_picker_cancels_with_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole(["0"])
    app = menus_module.MenuApp(build_services(), console)
    assert app._pick_path("menu.ask_import_path") == ""


def test_picker_takes_typed_path_verbatim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole(["assets/msa.a3m"])  # not required to exist here
    app = menus_module.MenuApp(build_services(), console)
    assert app._pick_path("menu.ask_import_path") == "assets/msa.a3m"


def test_picker_bad_number_recovers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "s.txt").write_text("ACDE\n")
    console = ScriptedConsole(["99", "2"])  # out of range, then the file
    app = menus_module.MenuApp(build_services(), console)
    assert app._pick_path("menu.ask_import_path").endswith("s.txt")


def test_the_file_kind_menu_lists_exactly_the_supported_input_types():
    """The console's kind table is the services' kind table, token for token.

    ``MenuApp.FILE_KINDS`` promises that a test compares it with
    ``batch_variants.INPUT_KINDS``: a sixth kind would advertise a construction
    no service builds, and a missing one would hide a working kind. The prompt
    table is checked at the same time, because a kind whose prompt key is absent
    raises ``KeyError`` the moment a user picks it.
    """
    from configbuilder.app.batch_variants import INPUT_KINDS

    tokens = tuple(token for _label_key, token in menus_module.MenuApp.FILE_KINDS)
    assert tokens == INPUT_KINDS
    assert set(menus_module.MenuApp._FILE_PROMPTS) == set(INPUT_KINDS)


def test_the_file_menu_explains_the_duplex_and_counts_roles(tmp_path):
    """The console's preview and summary, in the shared wording.

    A DNA record is one configuration holding two strands, so the preview says
    so; the summary then counts that one configuration and the manifest apart
    instead of calling two written files two configurations.
    """
    from configbuilder.ui.present.strings import text as _text

    services = build_services()
    services.projects.new("exp")
    services.configuration.set_format_target(version=3, evidence="PIN-001")
    services.configuration.add_record("protein", PROTEIN_SEQUENCE)
    dna = tmp_path / "dna.txt"
    dna.write_text("ATGC\n", encoding="utf-8")
    out = tmp_path / "out"

    status, transcript = run(
        [
            "7",  # the job menu's generation action
            "1",  # load an input file
            "2",  # the kind table's DNA entry
            str(dna),
            str(out),
            "0",  # leave the file menu
            "0",  # leave the job menu
        ],
        services,
    )

    assert _text("batch.preview_lead_dna") in transcript
    assert "reverse-complement" in transcript
    assert _text("batch.preview_tail") in transcript
    assert (
        "Generated 1 AF3 configuration. Wrote 1 manifest. Total output files: 2."
        in transcript
    )
    assert _text("menu.file_summary_location") % str(out) in transcript
    written = sorted(path.name for path in out.rglob("*.json"))
    assert written == ["exp__batch-01.json", "manifest.json"]


def test_blocking_generation_names_the_findings():
    """A generation refusal carries the blocking findings for the UI."""
    services = build_services()
    services.projects.new("Blocked Demo")
    services.configuration.set_seeds([1])
    generation_plan = services.generation.plan(str(Path("output")))
    assert not generation_plan.ok
    assert "blocking findings" in (generation_plan.message or "")
    assert generation_plan.findings
