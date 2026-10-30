"""Console/desktop parity: the workflows the audit found console-only gaps in.

Each test drives the real ``MenuApp`` through the real services and reads the
saved JSON back, so the assertion is about what a user gets, not about an
internal call. The four areas covered are the ones the workflow audit listed as
missing or misleading in the console:

- covalent bonds (``bondedAtomPairs`` was GUI-only);
- ligand descriptions (the desktop form collected them, the console did not);
- inline MSA text and inline mmCIF templates (the desktop could, the console
  only took files);
- the delete confirmation (it named one record while removing two).
"""

from __future__ import annotations

import json

from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

PROTEIN = "ACDEFGHIKL"


def _save(script, destination):
    console = ScriptedConsole(script + ["6", str(destination), "0", "0"])
    status = MenuApp(build_services(), console).run()
    assert status == 0
    assert "Traceback" not in console.transcript
    assert destination.exists(), console.transcript[-2000:]
    return json.loads(destination.read_text(encoding="utf-8")), console.transcript


def _cif_lines(name="template"):
    """A real single-chain protein template, as lines a user would paste."""
    return [
        "data_%s" % name,
        "#",
        "_entity_poly.entity_id 1",
        "_entity_poly.type 'polypeptide(L)'",
        "_entity_poly.pdbx_strand_id A",
        "_entity_poly.pdbx_seq_one_letter_code ACDEFGHIKL",
        "#",
    ]


# -- covalent bonds ------------------------------------------------------------


def test_the_console_can_add_view_and_remove_a_covalent_bond(tmp_path):
    """``bondedAtomPairs`` is part of the AF3 contract, so the console needs it."""
    document, transcript = _save(
        [
            "1",
            "bond-job",
            "2",
            "1",
            PROTEIN,
            "1",
            "",  # protein A: default MSA, no templates
            "2",
            "4",
            "1",
            "ATP",
            "1",
            "",  # ligand B, blank description
            "8",  # job menu → covalent bonds
            "2",  # add a bond
            "1",
            "1",
            "SG",  # endpoint A: entity 1, residue 1, atom SG
            "2",
            "1",
            "C1",  # endpoint B: entity 2, residue 1, atom C1
            "0",  # back to the job menu
        ],
        tmp_path / "bonded.json",
    )

    assert "COVALENT BOND MANAGEMENT" in transcript
    assert "Covalent bond added." in transcript
    assert document["bondedAtomPairs"] == [[["A", 1, "SG"], ["B", 1, "C1"]]]


def test_the_console_lists_and_removes_the_bond_it_added(tmp_path):
    """The list is the service's linkages, numbered; removal takes that number."""
    services = build_services()
    services.projects.new("bond-job")
    services.configuration.add_record("protein", PROTEIN)
    services.configuration.add_record("ligand", representation="ATP")
    services.configuration.add_linkage("A", 1, "SG", "B", 1, "C1")

    # The project is already open, so the menu starts at the job screen.
    console = ScriptedConsole(["8", "1", "3", "1", "0", "0", "2", "0"])
    status = MenuApp(services, console).run()
    assert status == 0
    assert "A, residue 1, atom SG" in console.transcript
    assert "Covalent bond removed." in console.transcript


def test_a_bond_needs_two_entities_and_says_so():
    services = build_services()
    services.projects.new("one-entity")
    services.configuration.add_record("protein", PROTEIN)
    console = ScriptedConsole(["8", "2", "0", "0", "2", "0"])
    assert MenuApp(services, console).run() == 0
    assert "Add at least two entities before defining a bond." in console.transcript


# -- ligand descriptions -------------------------------------------------------


def test_a_ligand_description_is_collected_on_add(tmp_path):
    document, _transcript = _save(
        [
            "1",
            "described",
            "1",
            "3",
            "4",  # pin JSON version 4: only v4 writes a description
            "0",  # back to the job menu
            "2",
            "4",
            "1",
            "ATP",
            "2",
            "the energy currency",  # optional description
        ],
        tmp_path / "described.json",
    )
    ligand = document["sequences"][0]["ligand"]
    assert ligand["ccdCodes"] == ["ATP"]
    assert ligand["description"] == "the energy currency"


def test_a_ligand_description_can_be_edited_later():
    services = build_services()
    services.projects.new("edit-ligand")
    services.configuration.add_record("ligand", representation="ATP")
    console = ScriptedConsole(
        [
            "3",
            "1",  # edit entity → the only record
            "1",  # edit its fields
            "1",
            "ATP",  # keep the CCD representation
            "a new note",  # the description
            "0",
            "0",  # action screen → entity list
            "0",
            "2",
            "0",  # leave → discard → exit
        ]
    )
    assert MenuApp(services, console).run() == 0
    record = services.projects.project.configuration.records[0]
    assert record.description.value == "a new note"


# -- inline MSA ----------------------------------------------------------------


def test_an_inline_unpaired_msa_can_be_pasted_in_the_console(tmp_path):
    document, transcript = _save(
        [
            "1",
            "inline-msa",
            "2",
            "1",
            PROTEIN,
            "2",  # provide MSA sources
            "3",  # paired side: leave empty
            "1",  # unpaired side: paste inline text
            ">query",
            PROTEIN,
            "",  # a blank line finishes the paste
            "n",  # no templates
        ],
        tmp_path / "inline-msa.json",
    )

    protein = document["sequences"][0]["protein"]
    assert protein["pairedMsa"] == ""
    assert protein["unpairedMsa"].startswith(">query")
    assert "unpairedMsaPath" not in protein
    assert "Paste the alignment" in transcript


def test_an_inline_paired_side_is_kept_apart_from_the_unpaired_side(tmp_path):
    document, _ = _save(
        [
            "1",
            "inline-both",
            "2",
            "1",
            PROTEIN,
            "2",
            "1",
            ">paired",
            PROTEIN,
            "",  # paired side pasted
            "1",
            ">unpaired",
            PROTEIN,
            "",  # unpaired side pasted
            "n",
        ],
        tmp_path / "inline-both.json",
    )
    protein = document["sequences"][0]["protein"]
    assert protein["pairedMsa"].startswith(">paired")
    assert protein["unpairedMsa"].startswith(">unpaired")
    assert protein["pairedMsa"] != protein["unpairedMsa"]


# -- inline structural templates ----------------------------------------------


def test_an_inline_template_is_written_as_mmcif_not_a_path(tmp_path):
    document, transcript = _save(
        [
            "1",
            "inline-template",
            "2",
            "1",
            PROTEIN,
            "1",  # default MSA
            "y",  # use templates
            "3",  # provide the reference list
            "2",  # template 1: paste the mmCIF inline
            *_cif_lines(),
            "",  # a blank line finishes the paste
            "0:0,1:1",
            "n",  # no further templates
        ],
        tmp_path / "inline-template.json",
    )

    protein = document["sequences"][0]["protein"]
    template = protein["templates"][0]
    assert "mmcif" in template and "mmcifPath" not in template
    assert template["mmcif"].startswith("data_template")
    assert template["queryIndices"] == [0, 1]
    assert template["templateIndices"] == [0, 1]
    assert "Paste the mmCIF content" in transcript


def test_a_template_source_is_asked_once_per_template(tmp_path):
    """The file route still works, and the question is per template, not global."""
    cif = tmp_path / "t.cif"
    cif.write_text("\n".join(_cif_lines()) + "\n", encoding="utf-8")
    document, _ = _save(
        [
            "1",
            "file-template",
            "2",
            "1",
            PROTEIN,
            "1",
            "y",
            "3",
            "1",  # template 1: a file
            str(cif),
            "0:0",
            "n",
        ],
        tmp_path / "file-template.json",
    )
    template = document["sequences"][0]["protein"]["templates"][0]
    assert template["mmcifPath"].endswith("t.cif")
    assert "mmcif" not in template


# -- deletion consequences -----------------------------------------------------


def test_deleting_a_strand_names_its_partner_before_removing_it():
    services = build_services()
    console = ScriptedConsole(
        [
            "1",
            "duplex",
            "2",
            "2",
            "ATGC",
            "1",  # DNA duplex: strands A and B
            "3",
            "1",  # edit entity → record A
            "2",  # delete
            "1",  # yes
            "0",
            "2",
            "0",
        ]
    )
    assert MenuApp(services, console).run() == 0
    transcript = console.transcript
    assert "one strand of a DNA duplex" in transcript
    assert "its partner B" in transcript
    # The service's own result message is reported, not a bare "Removed".
    assert "the DNA duplex and its partner strand were removed" in transcript
    assert services.projects.project.configuration.records == ()


def test_deleting_a_multi_copy_ligand_names_every_identifier():
    services = build_services()
    console = ScriptedConsole(
        [
            "1",
            "copies",
            "2",
            "4",
            "1",
            "ATP",
            "3",
            "",  # three copies, blank description
            "3",
            "1",
            "2",
            "1",  # delete the ligand, confirmed
            "0",
            "2",
            "0",
        ]
    )
    assert MenuApp(services, console).run() == 0
    assert "multi-copy ligand with 3 identifiers" in console.transcript
    assert services.projects.project.configuration.records == ()


# -- custom CCD menu -----------------------------------------------------------


def test_the_ccd_menu_sets_and_removes_without_a_duplicate_edit():
    """``Add`` and ``Edit`` asked the same questions; there is now one action."""
    services = build_services()
    services.projects.new("ccd")
    services.configuration.add_record("protein", PROTEIN)
    console = ScriptedConsole(["4", "2", "1", "data_x", "#", "", "0", "0", "2", "0"])
    assert MenuApp(services, console).run() == 0
    transcript = console.transcript
    assert "1. View the custom CCD definition" in transcript
    assert "2. Set or replace the custom CCD definition" in transcript
    assert "3. Remove the custom CCD definition" in transcript
    assert "Edit the custom CCD definition" not in transcript
    assert "Custom CCD definition set." in transcript
