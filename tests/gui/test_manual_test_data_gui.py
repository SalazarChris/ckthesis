"""The manual test pack, driven through the desktop window.

The console tests for the same pack live in
``tests/e2e/test_manual_test_data.py``; this module pins that the window offers
exactly what the service supports — three RNA MSA modes, no paired side and no
RNA batch family — and that a path containing spaces survives the dialog, the
preview and the saved JSON.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import QDialog  # noqa: E402

from configbuilder.model import (  # noqa: E402
    External,
    SingleAutomatic,
    SingleProvided,
)
from configbuilder.ui.render.qt.dialogs import (  # noqa: E402
    AlignmentFormDialog,
    TemplateEditorDialog,
)
from configbuilder.ui.render.qt.pages import advanced as advanced_page  # noqa: E402

PACK = Path(__file__).resolve().parents[2] / "manual_test_data" / "af3_builder"
RNA_MSA = str(PACK / "msa" / "with spaces" / "rna query.a3m")
QUERY_RNA = "ACGUACGU"


def _pack(*parts) -> str:
    return os.path.join(str(PACK), *parts)


def _record(window, key):
    return next(
        record
        for record in window.state.configuration.records
        if record.ids.primary.value == key
    )


def _document(window):
    text = window.preview_page.editor.toPlainText()
    return json.loads(text) if text else None


@pytest.fixture
def rna_job(window):
    """The window over a fresh job holding one RNA record, selected."""
    window.state.new_job()
    assert window.state.add_record("rna", sequence=QUERY_RNA).ok
    window.refresh()
    assert window.entities_page.select_record("A")
    return window


def _answer_alignment(monkeypatch, mode, kind=None, text=None):
    """Fill the real dialog and accept it; only ``exec`` is replaced."""
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        assert dialog.select_mode(mode), mode
        if kind is not None:
            for candidate, radio in dialog.source_radios:
                radio.setChecked(candidate == kind)
        if text is not None:
            dialog.path_edit.setText(text)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(AlignmentFormDialog, "exec", fake_exec)
    return opened


def test_the_rna_dialog_offers_exactly_the_three_supported_modes(rna_job, monkeypatch):
    opened = _answer_alignment(monkeypatch, "automatic")
    assert rna_job.advanced_page.change_alignment()
    dialog = opened[0]
    assert dialog.mode_combo.count() == len(advanced_page._RNA_MODES)
    assert [word for _label, word in advanced_page._RNA_MODES] == [
        "automatic",
        "provided",
        "free",
    ]
    # The protein-only modes are not offered: no paired side exists for RNA.
    assert not dialog.select_mode("paired")
    assert not dialog.select_mode("both")
    assert not dialog.select_mode("unpaired")
    assert isinstance(_record(rna_job, "A").alignment, SingleAutomatic)


def test_a_provided_rna_msa_file_with_spaces_reaches_the_json(rna_job, monkeypatch):
    _answer_alignment(monkeypatch, "provided", kind="file", text=RNA_MSA)
    assert rna_job.advanced_page.change_alignment()

    alignment = _record(rna_job, "A").alignment
    assert isinstance(alignment, SingleProvided)
    assert isinstance(alignment.source, External)
    assert alignment.source.path.raw == RNA_MSA

    rna = _document(rna_job)["sequences"][0]["rna"]
    assert rna["unpairedMsaPath"] == RNA_MSA
    assert "unpairedMsa" not in rna
    assert "pairedMsa" not in rna and "pairedMsaPath" not in rna


def test_the_rna_provided_mode_accepts_inline_text_too(rna_job, monkeypatch):
    text = Path(_pack("msa", "rna", "query-rna.a3m")).read_text(encoding="utf-8")
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        assert dialog.select_mode("provided")
        for candidate, radio in dialog.source_radios:
            radio.setChecked(candidate == "inline")
        dialog.inline_edit.setPlainText(text)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(AlignmentFormDialog, "exec", fake_exec)
    assert rna_job.advanced_page.change_alignment()
    rna = _document(rna_job)["sequences"][0]["rna"]
    assert rna["unpairedMsa"] == text
    assert "unpairedMsaPath" not in rna


def test_free_rna_msa_emits_the_explicit_empty_field(rna_job, monkeypatch):
    _answer_alignment(monkeypatch, "free")
    assert rna_job.advanced_page.change_alignment()
    assert _document(rna_job)["sequences"][0]["rna"]["unpairedMsa"] == ""


def test_templates_are_offered_for_protein_only(window, monkeypatch):
    opened = []
    monkeypatch.setattr(
        TemplateEditorDialog, "exec", lambda self: opened.append(self) or QDialog.Rejected
    )

    window.state.new_job()
    assert window.state.add_record("rna", sequence=QUERY_RNA).ok
    window.refresh()
    assert window.entities_page.select_record("A")
    assert not window.advanced_page.edit_templates()
    assert opened == [], "RNA has no template editor"

    assert window.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    window.refresh()
    assert window.entities_page.select_record("B")
    window.advanced_page.edit_templates()
    assert len(opened) == 1, "the protein template editor is offered"


def test_the_ligand_workflow_has_no_family_chooser(window):
    """Ligands and small molecules only: no protein/DNA/RNA picker here.

    The other families keep their ordinary entity editors; this workflow
    loads a collection of candidate molecules and nothing else.
    """
    page = window.entities_page
    assert not hasattr(page, "batch_family")
    assert not hasattr(page, "batch_path")
    assert not hasattr(page, "batch_table")
    assert not hasattr(window, "variants_page")


def test_the_pack_ligand_file_generates_one_configuration_per_entry(window, tmp_path):
    """The pack's own ligand list, run through the real Entities action."""
    window.state.new_job()
    assert window.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    window.refresh()
    page = window.entities_page
    before = sorted(str(path) for path in PACK.rglob("*") if path.is_file())
    work = tmp_path / "generated"

    page.batch_kind_chooser = lambda parent: "ligand-smiles"
    page.batch_file_chooser = lambda parent, kind="": _pack(
        "batch", "ligands_valid.smiles"
    )
    page.batch_folder_chooser = lambda parent, start="": str(work)
    seen = []
    page.batch_previewer = (
        lambda parent, preview, root, kind="": seen.append((preview, root)) or True
    )
    reports = []
    page.batch_reporter = lambda parent, output: reports.append(output)

    page.generate_from_file()

    assert len(seen) == 1
    preview, root = seen[0]
    assert preview.ok and preview.planned == 3, preview.entries
    assert root == str(work)
    assert reports and reports[0].ok, reports and reports[0].errors
    names = sorted(
        name
        for _current, _directories, files in os.walk(str(work))
        for name in files
        if name.endswith(".json") and name != "manifest.json"
    )
    assert len(names) == 3, names
    assert any("ethanol" in name for name in names)
    assert any("acetic-acid" in name for name in names)
    # The pack is input only, and the job on screen is untouched.
    after = sorted(str(path) for path in PACK.rglob("*") if path.is_file())
    assert after == before
    assert [record.ids.primary.value for record in window.state.configuration.records] == [
        "A"
    ]
