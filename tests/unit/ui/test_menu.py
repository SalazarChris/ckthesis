"""The free-navigation builder's end-to-end workflow (§20's journey).

The whole user story through the real services and the scripted console:
start a job, set seeds, add a protein, create a WT variant, grow it with
an edit through the factor picker, validate, and generate JSON — one job,
many JSONs. Every section is entered freely; nothing repeats a guided
sequence. The navigation itself lives in ``menu_flows`` so this file is
about behaviour, not keystrokes.
"""

from __future__ import annotations

import re
from pathlib import Path

from configbuilder.model import AlignmentUnpairedOnly, FamilyCRecord, Inline
from configbuilder.ui.render import menus as menus_module
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services
from tests.unit.ui.menu_flows import (
    BATCH_FLOW,
    DNA,
    MSA_EDIT,
    OPEN,
    PROTEIN,
    PROTEIN_SEQUENCE,
    PROTEIN_THEN_ENTITIES,
    RNA,
    SEEDS,
    run,
)


# -- the journey ---------------------------------------------------------------


def test_base_and_variant_generation_produces_json_files(tmp_path):
    status, out = run(
        OPEN
        + SEEDS
        + PROTEIN
        + [
            "3", "1", "1", "WT", "6", "Oct4_POU_WT", "0",  # Variants → create → custom name → job-name change → back
            "4", "4", str(tmp_path), "2", "y", "0",        # Generate JSON → set dir → all variants → write
            "0",                                           # exit
        ]
    )
    assert status == 0
    files = sorted(p.name for p in tmp_path.rglob("*") if p.suffix == ".json")
    assert files, out
    assert "Wrote " in out


def test_review_validate_reports_each_variant():
    status, out = run(
        OPEN
        + SEEDS
        + PROTEIN
        + [
            "3", "1", "1", "WT", "", "0",   # a variant with no edits yet (naming menu, skip changes)
            "2", "1", "0",                  # Review → validate → back
            "0",
        ]
    )
    assert status == 0
    # The per-variant report: base and every variant named with a status.
    assert "OK  WT" in out or "FAIL WT" in out


def test_review_shows_the_encoded_document():
    status, out = run(
        OPEN + SEEDS + PROTEIN + ["2", "2", "0", "0"]  # Review → JSON → back → exit
    )
    assert status == 0
    assert '"name"' in out or "Cannot build JSON" in out


def test_invalid_choices_never_terminate_the_application():
    status, out = run(OPEN + ["99", "x", "0"])
    assert status == 0
    assert "Not a valid choice: '99'" in out
    assert "Not a valid choice: 'x'" in out


# -- DNA duplex at the UI boundary: one sequence in, duplex out ------------


def test_dna_flow_collects_one_sequence_and_reports_a_duplex():
    """The front end asks once; the service silently builds two strands."""
    status, out = run(OPEN + DNA + ["0", "0"])
    assert status == 0
    # The UI never mentions complementing — the duplex is not its concern.
    assert "complement" not in out.lower()
    # Both strands reached the configuration (the status row counts them).
    assert "dna 2" in out


def test_invalid_dna_input_is_reported_and_discarded():
    status, out = run(OPEN + ["1", "1", "1", "2", "ATGX", "0", "0"])
    assert status == 0
    # The pipeline's own refusal, surfaced by the UI verbatim.
    assert "outside its alphabet" in out
    # And nothing was committed (a duplex would have shown up as two records).
    assert "dna 2" not in out


def test_cli_module_contains_no_complement_logic():
    """Requirement 7: no front end constructs the second strand."""
    import configbuilder.ui

    ui_root = Path(configbuilder.ui.__file__).parent
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in ui_root.glob("**/*.py")
    ).lower()
    for forbidden in ("complement", "reverse_complement"):
        assert forbidden not in sources, forbidden


# -- batch variants from a sequence file -------------------------------------


def test_variants_menu_offers_batch_generation():
    status, out = run(OPEN + BATCH_FLOW + ["", "0", "0"])
    assert status == 0
    assert "Generate variants from a sequence file" in out


def test_batch_generation_reports_the_generated_variants(tmp_path):
    seq_file = tmp_path / "seqs.txt"
    seq_file.write_text("MSTNPKP\nGKKIGYS\n", encoding="utf-8")
    status, out = run(
        OPEN
        + PROTEIN
        + BATCH_FLOW
        + [str(seq_file), "1", "0", "0"]  # confirm the detected entries
    )
    assert status == 0
    assert "Batch applied: 2 variants generated" in out
    # The variants menu lists the generated specs — they are plain variants.
    assert "batch_01" in out and "batch_02" in out


def test_batch_generation_reports_service_refusals_verbatim(tmp_path):
    status, out = run(
        OPEN + BATCH_FLOW + [str(tmp_path / "absent.txt"), "0", "0"]
    )
    assert status == 0
    assert "Not applied" in out
    assert "cannot be read" in out


def test_batch_ui_stays_thin_no_parsing_in_the_front_end():
    """Requirement 12: the Variants UI *invokes* the batch operation —
    it never reads files, parses sequences, or builds variants itself."""
    menus_source = Path(menus_module.__file__).read_text(encoding="utf-8")
    # no direct file opens (the service-dispatch ``projects.open(...)`` is
    # a method call, not a builtin): every open( is attribute access
    assert not re.search(r"(?<![.\w])open\(", menus_source)
    # and no import of the layers the batch flow must not touch
    # (model/records helpers are legal here; batch machinery is not)
    assert "from configbuilder.persistence" not in menus_source
    assert "from configbuilder.app.batch_variants" not in menus_source
    assert "from configbuilder.variants" not in menus_source
    assert "SequenceText(" not in menus_source
    assert "AddRecord(" not in menus_source


# -- MSA / structural templates in the free-navigation menu ---------------------
# An alignment or a set of templates belongs to one record, so it is asked for
# while that record is added or edited — never from an entry of its own, and
# never for a family that cannot carry it. PROTEIN_THEN_ENTITIES leaves the
# operator at the Entities screen.

def test_entities_menu_has_no_separate_msa_entry():
    """Three actions and nothing else: the record owns its alignment, so the
    screen offers no separate setting — typing the retired fourth choice is
    plainly not a choice."""
    status, out = run(OPEN + PROTEIN_THEN_ENTITIES + ["4", "0", "0", "0"])
    assert status == 0
    assert "Add an entity" in out
    assert "Edit an entity" in out
    assert "Delete an entity" in out
    assert "MSA / Templates" not in out
    assert "Not a valid choice: '4'" in out


def test_editing_a_protein_asks_for_its_msa_and_templates():
    status, out = run(
        OPEN
        + PROTEIN_THEN_ENTITIES
        + MSA_EDIT                                   # Edit → record 1 → keep sequence, keep description
        + ["y", "2", "2", "msa.a3m"]                # MSA: yes → unpaired → file → path
        + ["y", "2"]                                # templates: yes → explicitly none
        + ["0", "0", "0"]                           # back out to the master menu and exit
    )
    assert status == 0
    # Both settings land from the edit flow itself (the add already
    # reported its own "Applied.").
    assert out.split("Edit Entity", 1)[1].count("Applied.") == 2
    assert "Not applied" not in out
    assert "Add an MSA for this record?" in out
    assert "Add structural templates?" in out


def test_editing_a_dna_strand_is_never_asked_for_an_msa():
    """DNA carries neither alignment nor templates: the edit flow must not
    offer questions its record cannot answer — and the partner strand still
    moves with the edited one."""
    services = build_services()
    status, out = run(
        OPEN
        + ["1", "1", "1", "2", "ATGC", "0", "0"]         # add a DNA duplex
        + ["1", "1", "2", "1", "AAAA", "", "0", "0", "0"],  # edit strand A
        services=services,
    )
    assert status == 0
    assert "Add an MSA for this record?" not in out
    assert "Add structural templates?" not in out
    dna = sorted(
        record.sequence.text
        for record in services.projects.project.configuration.records
        if isinstance(record, FamilyCRecord)
    )
    assert dna == ["AAAA", "TTTT"]


def test_rna_is_asked_for_its_msa_but_never_for_templates():
    """RNA carries an alignment but no templates: adding one asks the MSA
    question and stops there — templates are a protein question."""
    status, out = run(OPEN + RNA + ["0"])
    assert status == 0
    assert "Add an MSA for this record? [y/N]" in out
    assert "Add structural templates?" not in out
    assert out.count("Applied.") == 1  # the record itself; the MSA was skipped

    status, out = run(
        OPEN + ["1", "1", "1", "3", "ACGU", "y", "1"] + ["0", "0", "0"]
    )
    assert status == 0
    assert "Add structural templates?" not in out
    assert out.count("Applied.") == 2  # the record and its automatic alignment


def test_variant_msa_change_reaches_protein_and_rna_chains():
    """The variant's alignment change belongs to the two chains that carry
    an MSA: a protein gets its paired/unpaired cases, an RNA the single one
    — chosen by number, with the family's own mode menu."""
    services = build_services()
    status, out = run(
        OPEN
        + ["1", "1", "1", "1", "ACDEFGHIKLMNPQRSTVWY", "", "", "0", "0"]  # protein A
        + ["1", "1", "1", "3", "ACGU", "", "", "0", "0"]                  # RNA B
        + ["3", "1", "1", "WT", "4", "2", "3", "2", "rna.a3m"]            # MSA → B → provided → file
        + ["0", "0"],
        services=services,
    )
    assert status == 0
    assert "1) A  protein" in out and "2) B  rna" in out
    assert "Provided (paste or file)" in out  # the RNA mode menu
    assert "Not applied" not in out
    assert [
        (type(edit).__name__, edit._record_key.value)
        for edit in services.projects.project.specs[0].edits
    ] == [("SetSingleAlignment", "B")]

    # The protein path still builds the protein case.
    services = build_services()
    status, out = run(
        OPEN
        + ["1", "1", "1", "1", "ACDEFGHIKLMNPQRSTVWY", "", "", "0", "0"]
        + ["3", "1", "1", "WT", "4", "1", "1", "0", "0"],  # MSA → record 1 → automatic
        services=services,
    )
    assert status == 0
    assert [
        type(edit).__name__ for edit in services.projects.project.specs[0].edits
    ] == ["SetAlignment"]


def test_variant_inline_msa_survives_the_variants_menu_redraw():
    """The paste route leaves the spec holding an inline resource, and the
    variant list describes every edit whenever it redraws. An inline MSA
    used to crash that redraw — including the reopened Variants menu — with
    an AttributeError inside the describe dispatch."""
    services = build_services()
    msa = ">s1\nACDE\n>s2\nFGHI"    # the pasted block
    status, out = run(
        OPEN
        + PROTEIN                          # one protein, back at the master menu
        + ["3", "1", "1", "WT"]            # Variants → create → custom name
        + ["4", "1", "2"]                  # MSA → the protein → unpaired only
        + ["1", msa, ""]                   # paste the MSA inline; a blank line ends it
        + ["0", "3", "0", "0"],            # back, reopen Variants, back, exit
        services=services,
    )
    assert status == 0
    assert "Not applied" not in out
    # The change line rendered on the create pass and again on the reopen.
    assert out.count("MSA of A") == 2
    edit = services.projects.project.specs[0].edits[0]
    assert type(edit).__name__ == "SetAlignment"
    assert isinstance(edit._alignment, AlignmentUnpairedOnly)
    # ``read_multiline`` keeps each line ending, but not the blank one.
    assert edit._alignment.source == Inline(msa + "\n")


def test_variant_msa_and_templates_refuse_chains_that_cannot_carry_them():
    """A DNA-only job carries neither setting: each change says which chain
    the setting lives on and stores nothing; templates stay protein-only
    for an RNA-only job too."""
    services = build_services()
    status, out = run(
        OPEN
        + ["1", "1", "1", "2", "ATGC", "0", "0"]           # a DNA-only job
        + ["3", "1", "1", "WT", "4", "5", "0", "0", "0"],  # create WT → MSA, then templates
        services=services,
    )
    assert status == 0
    assert "No protein or RNA chain to change" in out  # the alignment note
    assert "No protein chain to change" in out         # the template note
    assert "MSA mode:" not in out
    assert services.projects.project.specs[0].edits == ()

    services = build_services()
    status, out = run(
        OPEN
        + ["1", "1", "1", "3", "ACGU", "", "", "0", "0"]
        + ["3", "1", "1", "WT", "5", "0", "0", "0"],  # create WT → templates
        services=services,
    )
    assert status == 0
    assert "No protein chain to change" in out
    assert services.projects.project.specs[0].edits == ()


def test_invalid_msa_mode_reasks_and_recovers():
    """An unrecognized mode is reported and asked again — never guessed,
    never fatal; the next valid answer carries the flow."""
    status, out = run(
        OPEN
        + PROTEIN_THEN_ENTITIES
        + MSA_EDIT
        + ["y", "sideways", "2", "2", "msa.a3m"]   # MSA: bad mode → unpaired → file
        + ["n"]                                    # templates: no, keep what is there
        + ["0", "0", "0"]
    )
    assert status == 0
    assert "Not a valid choice: 'sideways'" in out
    assert out.split("Edit Entity", 1)[1].count("Applied.") == 1
    assert "Not applied" not in out
    # The edit flow's skip wording, not the add flow's advice to edit later.
    assert "the templates are unchanged" in out


def test_generate_screen_offers_the_job_itself_without_variants():
    """The job's own JSON is always the first action of the Generate screen,
    whether or not any variant exists."""
    status, out = run(OPEN + PROTEIN + ["4", "1", "2", "0", "0"])
    assert status == 0
    assert "Generate this job's JSON" in out
    assert "Change the output directory" in out


def test_blocking_generation_names_the_findings():
    """The generation refusal must show the actual blocking findings, not a
    bare verdict — the generation plan carries them for the UI."""
    services = build_services()
    services.projects.new("Blocked Demo")
    services.configuration.set_seeds([1])
    # No AF3 version + evidence pinned: the version CONTRACT rule blocks.
    generation_plan = services.generation.plan(str(Path("output")))
    assert not generation_plan.ok
    assert "blocking findings" in (generation_plan.message or "")
    assert generation_plan.findings, "refusal must carry the blocking findings"


# -- the directory-listing path picker ------------------------------------------
# Numbers open directories and choose files, ".." goes up, 0 cancels, and any
# typed text is taken as a literal path (the service layer validates it).


def test_picker_lists_and_selects_by_number(tmp_path, monkeypatch):
    (tmp_path / "seqs").mkdir()
    (tmp_path / "seqs" / "batch.txt").write_text("MSTNPKP\n")
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole(["2", "2"])  # 2 = seqs/ (.. is 1) → 2 = batch.txt
    app = menus_module.MenuApp(build_services(), console)
    chosen = app._pick_path("menu.ask_sequence_file")
    assert chosen == str(tmp_path / "seqs" / "batch.txt")


def test_picker_cancels_with_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole(["0"])
    app = menus_module.MenuApp(build_services(), console)
    assert app._pick_path("menu.ask_sequence_file") == ""


def test_picker_takes_typed_path_verbatim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole(["assets/msa.a3m"])  # not required to exist here
    app = menus_module.MenuApp(build_services(), console)
    assert app._pick_path("menu.ask_sequence_file") == "assets/msa.a3m"


def test_picker_bad_number_recovers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "s.txt").write_text("ACDE\n")
    console = ScriptedConsole(["99", "2"])  # out of range, then the file
    app = menus_module.MenuApp(build_services(), console)
    assert app._pick_path("menu.ask_sequence_file").endswith("s.txt")


# -- the integrated add flow: family → sequence → MSA? → templates? -------------

def test_add_flow_chains_msa_and_templates_onto_the_new_record():
    """One pass: family, sequence, then MSA, then templates — the record's
    §15 data is collected where the record is born, and everything lands
    through the same services."""
    status, out = run(
        OPEN
        + ["1", "1", "1", "1", PROTEIN_SEQUENCE,
           "y", "4", "1", ">s1\nACDE\n>s2\nFGHI", "",  # MSA: paired (menu 4), inline paste
           "y", "1",                                     # templates: search allowed (menu 1)
           "0", "0", "0"]
    )
    assert status == 0
    assert out.count("Applied.") == 3  # protein + alignment + references
    assert "Not applied" not in out
    # The chained prompts appeared in the add flow itself.
    assert "Add an MSA for this record?" in out
    assert "Add structural templates?" in out
    # The mode and source were chosen from numbered menus, not letters.
    assert "MSA mode:" in out
    assert "MSA source:" in out
