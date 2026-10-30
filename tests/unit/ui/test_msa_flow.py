"""The console's three-way MSA flow, end to end through the real services.

Each test drives ``MenuApp`` with a scripted console, saves the job through
the generation path, and reads the JSON back. That is the user-visible
contract: the file must say exactly what the menu collected.
"""

from __future__ import annotations

import json

from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

SEQUENCE = "ACDEFGHIKL"


def _save(script, destination):
    console = ScriptedConsole(script + ["6", str(destination), "0", "0"])
    status = MenuApp(build_services(), console).run()
    assert status == 0
    assert "Traceback" not in console.transcript
    assert destination.exists(), console.transcript[-2000:]
    return json.loads(destination.read_text(encoding="utf-8")), console.transcript


def _protein_script(*answers):
    return ["1", "msa-job", "2", "1", SEQUENCE, *answers, "n"]


def test_default_choice_explains_search_and_omits_every_msa_field(tmp_path):
    document, transcript = _save(
        _protein_script("1"), tmp_path / "default.json"
    )
    assert "AlphaFold searches for the MSA at inference time" in transcript
    assert "Paired MSA file" not in transcript
    assert "Unpaired MSA file" not in transcript
    protein = document["sequences"][0]["protein"]
    for field in ("unpairedMsa", "unpairedMsaPath", "pairedMsa", "pairedMsaPath"):
        assert field not in protein


def test_no_msa_asks_for_no_paths_and_emits_explicit_empty_strings(tmp_path):
    document, transcript = _save(_protein_script("3"), tmp_path / "none.json")
    assert "AlphaFold will run MSA-free" in transcript
    assert "Paired MSA file" not in transcript
    assert "Unpaired MSA file" not in transcript
    protein = document["sequences"][0]["protein"]
    assert protein["unpairedMsa"] == ""
    assert protein["pairedMsa"] == ""
    assert "unpairedMsaPath" not in protein
    assert "pairedMsaPath" not in protein


def test_two_files_land_in_their_own_fields(tmp_path):
    paired = tmp_path / "paired.a3m"
    unpaired = tmp_path / "unpaired.a3m"
    paired.write_text(">paired\nACDEFGHIKL\n", encoding="utf-8")
    unpaired.write_text(">unpaired\nACDEFGHIKL\n", encoding="utf-8")
    document, transcript = _save(
        _protein_script("2", "2", str(paired), "2", str(unpaired)),
        tmp_path / "both.json",
    )
    assert "Paired and unpaired are separate files" in transcript
    protein = document["sequences"][0]["protein"]
    assert protein["pairedMsaPath"].endswith("paired.a3m")
    assert protein["unpairedMsaPath"].endswith("unpaired.a3m")
    assert protein["pairedMsaPath"] != protein["unpairedMsaPath"]
    assert "unpairedMsa" not in protein
    assert "pairedMsa" not in protein


def test_a_blank_side_keeps_the_valid_one_sided_cases(tmp_path):
    paired = tmp_path / "paired.a3m"
    unpaired = tmp_path / "unpaired.a3m"
    paired.write_text(">paired\nACDEFGHIKL\n", encoding="utf-8")
    unpaired.write_text(">unpaired\nACDEFGHIKL\n", encoding="utf-8")

    document, _ = _save(
        _protein_script("2", "2", str(paired), "3"), tmp_path / "paired-only.json"
    )
    protein = document["sequences"][0]["protein"]
    assert protein["pairedMsaPath"].endswith("paired.a3m")
    assert protein["unpairedMsa"] == ""
    assert "unpairedMsaPath" not in protein

    document, _ = _save(
        _protein_script("2", "3", "2", str(unpaired)), tmp_path / "unpaired-only.json"
    )
    protein = document["sequences"][0]["protein"]
    assert protein["unpairedMsaPath"].endswith("unpaired.a3m")
    assert protein["pairedMsa"] == ""
    assert "pairedMsaPath" not in protein


def test_missing_and_empty_files_are_reported_and_retried(tmp_path):
    missing = tmp_path / "missing.a3m"
    empty = tmp_path / "empty.a3m"
    empty.write_text("", encoding="utf-8")
    valid = tmp_path / "valid.a3m"
    valid.write_text(">q\nACDEFGHIKL\n", encoding="utf-8")

    document, transcript = _save(
        _protein_script("2", "2", str(missing), str(empty), str(valid), "3"),
        tmp_path / "retry.json",
    )
    assert "cannot be used: the file does not exist" in transcript
    assert "cannot be used: the file is empty" in transcript
    protein = document["sequences"][0]["protein"]
    assert protein["pairedMsaPath"].endswith("valid.a3m")
    assert "unpairedMsaPath" not in protein


def test_editing_and_keeping_the_default_leaves_an_existing_alignment_alone(tmp_path):
    services = build_services()
    services.projects.new("edit-job")
    services.configuration.add_record("protein", SEQUENCE)
    services.configuration.set_alignment(
        "A", "unpaired", inline_text=">q\nACDEFGHIKL\n"
    )
    destination = tmp_path / "edit.json"
    console = ScriptedConsole(
        ["3", "1", "1", "", "", "1", "n", "0", "0", "6", str(destination), "0", "0"]
    )
    assert MenuApp(services, console).run() == 0
    assert "The current MSA setting is kept unchanged." in console.transcript
    document = json.loads(destination.read_text(encoding="utf-8"))
    protein = document["sequences"][0]["protein"]
    assert protein["unpairedMsa"] == ">q\nACDEFGHIKL\n"
    assert protein["pairedMsa"] == ""


def test_rna_asks_for_one_file_and_writes_the_single_field(tmp_path):
    msa = tmp_path / "rna.a3m"
    msa.write_text(">q\nACGU\n", encoding="utf-8")
    console = ScriptedConsole(
        ["1", "rna-job", "2", "3", "ACGU", "2", "2", str(msa), "6", str(tmp_path / "rna.json"), "0", "0"]
    )
    assert MenuApp(build_services(), console).run() == 0
    document = json.loads((tmp_path / "rna.json").read_text(encoding="utf-8"))
    rna = document["sequences"][0]["rna"]
    assert rna["unpairedMsaPath"].endswith("rna.a3m")
    assert "pairedMsa" not in rna
    assert "Alignment source" in console.transcript
    assert "Alignment file: " in console.transcript
    assert "Paired side" not in console.transcript


def test_the_rna_file_choice_does_not_explain_paired_sides(tmp_path):
    """RNA has one MSA field; the explanation must match the question asked.

    Regression: the file-choice preamble was the protein wording ("paired and
    unpaired are separate files") even when the next prompt was the single
    ``RNA MSA file:``, which described a field RNA does not have.
    """
    msa = tmp_path / "rna.a3m"
    msa.write_text(">q\nACGU\n", encoding="utf-8")
    console = ScriptedConsole(
        ["1", "rna-job", "2", "3", "ACGU", "2", "2", str(msa), "6", str(tmp_path / "r.json"), "0", "0"]
    )
    assert MenuApp(build_services(), console).run() == 0
    assert "single MSA file" in console.transcript
    assert "Paired and unpaired are separate files" not in console.transcript


def test_skipping_templates_says_templates_not_msa(tmp_path):
    """Declining templates must not claim the MSA choice was ``No MSA``.

    Regression: the new-record skip message was the MSA-skip wording, so an
    entity created *with* a provided MSA ended by announcing that no MSA
    would be used.
    """
    paired = tmp_path / "p.a3m"
    unpaired = tmp_path / "u.a3m"
    paired.write_text(">query\nACDEFGHIKL\n", encoding="utf-8")
    unpaired.write_text(">query\nACDEFGHIKL\n", encoding="utf-8")
    _document, transcript = _save(
        _protein_script("2", "2", str(paired), "2", str(unpaired)),
        tmp_path / "skip.json",
    )
    assert "No templates will be used" in transcript
    assert "No MSA will be used" not in transcript
