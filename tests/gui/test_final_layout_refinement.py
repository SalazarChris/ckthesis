"""The final layout refinement, driven through the real widgets.

These tests pin the v3 refinement:

- Overview is job settings, a compact clickable entity summary and one
  readiness line — no findings table, no status table, no empty-state card,
  no Add Entity action and no JSON preview action;
- Entities is a compact picker with three work areas, and the picker can reach
  every family, both DNA strands, an imported lone DNA strand and every
  identifier of a multi-copy ligand;
- Alignment/MSA comes before templates and PTMs, and the job-wide Custom CCDs
  and Covalent bonds live in their own visible areas;
- a blocked Save or Generate still explains itself on the attempt.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import (  # noqa: E402
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableView,
)

from configbuilder.ui.present.strings import text as _text  # noqa: E402


def _button_texts(page):
    return [button.text() for button in page.findChildren(QPushButton)]


def _label_texts(page):
    return [label.text() for label in page.findChildren(QLabel)]


# -- Overview ----------------------------------------------------------------


def test_overview_is_settings_summary_and_one_readiness_line(reviewed):
    page = reviewed.overview_page

    assert page.job_settings.isVisibleTo(page)
    assert page._summary_card.isVisibleTo(page)
    assert page._readiness_card.isVisibleTo(page)
    assert not page.findChildren(QTableView)
    assert "Validation findings" not in _label_texts(page)
    assert "Validation findings" not in _button_texts(page)
    assert "Preview JSON" not in _button_texts(page)
    assert "Save JSON" not in _button_texts(page)
    assert "Add Entity" not in _button_texts(page)
    assert page.entities_button.text() == _text("gui.overview_go_entities")


def test_overview_with_no_job_has_no_empty_state_or_add_entity(window):
    page = window.overview_page

    assert page._no_job_note.isVisibleTo(page)
    assert not page._summary_card.isVisibleTo(page)
    assert not page._readiness_card.isVisibleTo(page)
    assert "Add Entity" not in _button_texts(page)
    # New/Open stay available in the FILE footer.
    assert _text("gui.file_action_new") in window.file_action_texts()
    assert _text("gui.file_action_open") in window.file_action_texts()


def test_manage_entities_opens_the_entities_workspace(reviewed):
    page = reviewed.overview_page
    page.entities_button.click()

    assert reviewed.current_page() is reviewed.entities_page
    assert reviewed.entities_page.selector.count() == 5


# -- the compact entity picker ----------------------------------------------


def test_the_picker_reaches_every_family_and_multi_copy_ligands(reviewed):
    state = reviewed.state
    assert state.add_record("rna", sequence="ACGUACGU").ok
    assert state.add_record(
        "ligand", representation="ATP", representation_kind="ccd", copies=2
    ).ok
    reviewed.refresh()
    page = reviewed.entities_page

    entries = [
        page.selector.itemText(index) for index in range(page.selector.count())
    ]
    assert any(text.startswith("A ·") for text in entries)  # protein
    assert any(text.startswith("B ·") for text in entries)  # DNA given strand
    assert any(text.startswith("C ·") for text in entries)  # DNA partner
    assert any(text.startswith("D ·") for text in entries)  # CCD ligand
    assert any(text.startswith("E ·") for text in entries)  # SMILES ligand
    assert any(text.startswith("F ·") for text in entries)  # RNA
    copies = next(text for text in entries if text.startswith("G, H ·"))
    assert "CCD: ATP" in copies

    page.select_record("C")
    assert reviewed.advanced_page.record_key() == "C"
    assert page.detail_text("gui.entity_partner_label") == (
        _text("gui.entity_partner") % "B"
    )
    page.select_record("F")
    assert reviewed.advanced_page.record_key() == "F"
    assert page.detail_text("gui.entity_length") == _text(
        "gui.entity_length_value"
    ) % 8


def test_an_imported_lone_dna_strand_is_selectable(reviewed, tmp_path):
    document = {
        "name": "lone-strand",
        "modelSeeds": [1],
        "sequences": [{"dna": {"id": "Z", "sequence": "ATGC"}}],
        "dialect": "alphafold3",
        "version": 3,
    }
    path = tmp_path / "lone.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert reviewed.state.commit_import(str(path)).ok
    reviewed.refresh()

    page = reviewed.entities_page
    page.select_record("Z")
    assert page.selected_record_key() == "Z"
    assert page.detail_text("gui.entity_partner_label") == _text(
        "gui.entity_no_partner"
    )


def test_entity_settings_have_no_large_sequence_preview(reviewed):
    page = reviewed.entities_page
    page.select_record("A")

    settings_area = page.workspace.widget()
    assert not settings_area.findChildren(QPlainTextEdit)
    assert page.detail_text("gui.entity_length") == _text(
        "gui.entity_length_value"
    ) % 20
    # The sequence remains in the Add/Edit dialog, not on the page.
    assert "ACDEFGHIKLMNPQRSTVWY" not in _label_texts(settings_area)


# -- the order of the entity settings ---------------------------------------


def test_alignment_comes_before_templates_and_ptms(reviewed):
    reviewed.entities_page.select_record("A")
    reviewed.entities_page.tabs.setCurrentIndex(0)

    advanced = reviewed.advanced_page
    body = advanced.layout().itemAt(0).widget()
    layout = body.layout()
    assert layout.indexOf(advanced.alignment_group) < layout.indexOf(
        advanced.templates_group
    )
    assert layout.indexOf(advanced.templates_group) < layout.indexOf(
        advanced.modifications_group
    )

    # The same order holds for RNA, which has MSA and PTMs but no templates.
    reviewed.state.add_record("rna", sequence="ACGUACGU")
    reviewed.refresh()
    reviewed.entities_page.select_record("F")
    assert advanced.alignment_group.isVisibleTo(advanced)
    assert not advanced.templates_group.isVisibleTo(advanced)
    assert layout.indexOf(advanced.alignment_group) < layout.indexOf(
        advanced.modifications_group
    )


# -- job-wide work areas -----------------------------------------------------


def test_custom_ccds_and_bonds_are_separate_work_areas(reviewed):
    page = reviewed.entities_page
    assert page.tabs.count() == 3
    assert page.tabs.tabText(1) == _text("gui.entity_tab_ccd")
    assert page.tabs.tabText(2) == _text("gui.entity_tab_bonds")
    assert page.ccd_tab.isAncestorOf(reviewed.ccd_page)
    assert page.bonds_tab.isAncestorOf(reviewed.bonds_page)
    assert not page.workspace.isAncestorOf(reviewed.ccd_page)
    assert not page.workspace.isAncestorOf(reviewed.bonds_page)
    # Each area says that it belongs to the whole job.
    assert _text("gui.entity_job_wide") in _label_texts(page.ccd_tab)
    assert _text("gui.entity_job_wide") in _label_texts(page.bonds_tab)


def test_job_wide_areas_open_with_no_entities(window):
    window.state.new_job("empty-job")
    window.refresh()
    page = window.entities_page

    page.tabs.setCurrentIndex(1)
    assert window.ccd_page.ccd_apply_button.isEnabled()
    assert window.ccd_page.ccd_group.isVisibleTo(window.ccd_page)

    page.tabs.setCurrentIndex(2)
    assert window.bonds_page.add_bond_button.isEnabled() is False
    assert window.bonds_page._bond_notice.text() == _text("gui.bond_needs_entities")


# -- refusal explanations ----------------------------------------------------


def test_blocked_generate_keeps_the_plan_review_and_explains_itself(
    reviewed, tmp_path
):
    reviewed.state.services.configuration.add_modification("A", "SEP", 999)
    reviewed.refresh()
    page = reviewed.output_page
    page.destination.setText(str(tmp_path))

    assert page.preview_plan() is False
    assert "blocking" in page.plan_note.text()
    assert page.findings_model.rowCount() > 0
    assert not page.generate_button.isEnabled()
    assert list(tmp_path.iterdir()) == []
