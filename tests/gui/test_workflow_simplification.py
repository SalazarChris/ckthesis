"""Stage 9: the workflow-simplification pass, driven through the real widgets.

The changes this module pins are deliberately small and user-facing:

- the standalone **JSON preview** destination and its Overview shortcut are
  gone (the document is still produced by the service and still saved through
  the existing path);
- the Entities workspace is one compact column: the selected entity's facts
  and its own advanced settings share it, and a family never shows a section
  that cannot apply to it;
- the Variants & Batch destination is retired: a file of ligands is one
  action on the Entities page, and no page presents an in-memory variant list;
- Generate is four ordered steps for the open job's own file, and the advanced
  options stay collapsed without hiding conflicts or findings.

Every assertion reads a real widget, service state, or the files the existing
pipeline writes; none reads source text.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
)

from configbuilder.ui.present.strings import STRINGS  # noqa: E402
from configbuilder.ui.present.strings import text as _text  # noqa: E402


# -- navigation --------------------------------------------------------------


def test_json_preview_is_no_longer_a_destination(reviewed):
    """Three destinations; the JSON pane exists only as an internal view."""
    assert reviewed.sidebar_labels() == [
        _text("gui.tab_overview"),
        _text("gui.tab_entities"),
        _text("gui.tab_output"),
    ]
    assert reviewed.preview_page not in reviewed.destination_pages()
    assert not hasattr(reviewed.overview_page, "preview_button")
    assert "gui.tab_preview" not in STRINGS
    # Saving is still the visible route to the document: the sidebar footer
    # offers it for the open job, and the action keeps its keyboard shortcut.
    file_menu = reviewed.menuBar().actions()[0].menu()
    actions = {
        action.text(): action
        for action in file_menu.actions()
        if not action.isSeparator()
    }
    assert actions[_text("gui.action_save")].isEnabled()
    assert _text("gui.file_action_save") in reviewed.file_action_texts()
    # One visible home for the file actions: the footer, not a menu strip
    # duplicating the same commands above the product header.
    assert reviewed.menuBar().isHidden()
    assert reviewed._save_action.shortcut() == QKeySequence(QKeySequence.Save)
    assert reviewed._save_action in reviewed.actions()


def test_every_remaining_destination_has_content(reviewed):
    """No blank page was left behind by removing the fifth destination."""
    for page in reviewed.destination_pages():
        reviewed.show_page(page)
        assert reviewed.current_page() is page
        assert page.layout() is not None
        assert page.sizeHint().width() > 0 and page.sizeHint().height() > 0


def test_the_overview_counts_a_duplex_as_two_dna_strands(window):
    """The status service counts chain records; the summary says so."""
    window.state.new_job("duplex-job")
    assert window.state.add_record("dna", sequence="ATGC").ok
    window.refresh()
    counts = window.overview_page.summary_text("menu.status_components")
    assert "2 DNA strands" in counts
    assert "duplexes" not in counts


# -- the entity workspace ----------------------------------------------------


def test_the_entity_workspace_shows_compact_facts_and_settings(reviewed):
    reviewed.entities_page.select_record("A")
    page = reviewed.entities_page

    # The selected entity's settings share the first work area with a compact
    # facts card; no large read-only sequence preview exists anywhere on it.
    settings_area = page.workspace.widget()
    assert settings_area.isAncestorOf(reviewed.advanced_page)
    assert not settings_area.findChildren(QPlainTextEdit)
    assert page.detail_text("gui.entity_length") == _text(
        "gui.entity_length_value"
    ) % 20


def _visible_groups(advanced):
    return tuple(
        group.isVisibleTo(advanced)
        for group in (
            advanced.modifications_group,
            advanced.alignment_group,
            advanced.templates_group,
        )
    )


def test_entity_details_hide_facts_the_family_does_not_have(reviewed):
    """A protein has no partner; DNA has no MSA or templates; a ligand no length."""
    page = reviewed.entities_page
    advanced = reviewed.advanced_page

    page.select_record("A")
    assert page._detail_rows["gui.entity_partner_label"][0].isHidden()
    assert not page._detail_rows["gui.entity_length"][0].isHidden()
    assert page._detail_rows["gui.entity_representation"][0].isHidden()
    assert advanced.alignment_group.isVisibleTo(advanced)

    page.select_record("B")  # DNA
    assert not page._detail_rows["gui.entity_partner_label"][0].isHidden()
    assert not advanced.alignment_group.isVisibleTo(advanced)
    assert not advanced.templates_group.isVisibleTo(advanced)

    page.select_record("D")  # CCD ligand
    assert page._detail_rows["gui.entity_length"][0].isHidden()
    assert not page._detail_rows["gui.entity_representation"][0].isHidden()
    assert not page._detail_rows["gui.col_description"][0].isHidden()
    assert not advanced.modifications_group.isVisibleTo(advanced)


def test_entity_settings_follow_the_selected_family(reviewed):
    """Only the sections a family can use are put on screen."""
    page = reviewed.entities_page
    advanced = reviewed.advanced_page

    page.select_record("A")  # protein
    assert _visible_groups(advanced) == (True, True, True)

    page.select_record("B")  # DNA
    assert _visible_groups(advanced) == (True, False, False)

    page.select_record("D")  # CCD ligand
    assert _visible_groups(advanced) == (False, False, False)
    assert advanced.family_note_text() == _text("gui.entity_ligand_no_settings")

    assert reviewed.state.add_record("rna", sequence="ACGUACGU").ok
    reviewed.refresh()
    page.select_record("F")  # RNA (the fixture holds A-E)
    assert _visible_groups(advanced) == (True, True, False)


# -- the retired variant workspace -------------------------------------------


def test_no_page_manages_an_in_memory_variant_list(reviewed):
    """The Variants & Batch destination is gone, and nothing replaced it.

    A file of ligands is processed in one pass; the specifications it produces
    are internal to the generation service, never a list the user edits.
    """
    assert not hasattr(reviewed, "variants_page")
    assert reviewed.destination_pages() == (
        reviewed.overview_page,
        reviewed.entities_page,
        reviewed.output_page,
    )
    assert not hasattr(reviewed.state, "specs")
    assert not hasattr(reviewed.state, "add_spec_with_edit")
    assert "gui.tab_variants" not in STRINGS
    assert not any(key.startswith("gui.variants_") for key in STRINGS)


def test_the_ligand_file_action_lives_on_the_entities_page(reviewed):
    """One button, beside Add/Edit/Delete, and it is the only entry point."""
    page = reviewed.entities_page
    assert page.ligand_file_button.text() == _text("gui.action_ligand_file")
    assert page.ligand_file_button.toolTip() == _text("gui.action_ligand_file_hint")
    assert page.ligand_file_button.isEnabled()
    assert page.isAncestorOf(page.ligand_file_button)
    generating = {
        button.text()
        for button in page.findChildren(QPushButton)
        if "generate" in button.text().lower()
    }
    assert generating == {_text("gui.action_ligand_file")}


# -- generate ----------------------------------------------------------------


def test_generate_is_four_ordered_steps(reviewed):
    page = reviewed.output_page
    titles = [group.title() for group in page.findChildren(QGroupBox)]
    assert titles == [
        _text("gui.output_group_scope"),
        _text("gui.output_group_destination"),
        _text("gui.output_group_plan"),
        _text("gui.output_group_generate"),
    ]
    # The scope is one explained sentence, not a picker: this page writes the
    # open job's own file and nothing else.
    assert not hasattr(page, "scope_all")
    assert not hasattr(page, "choose_scope")
    assert page._plan_arguments()["scope"] == "base"
    # Advanced stays one click away; conflicts and findings never do.
    assert page.advanced_section.is_expanded() is False
    assert not page.advanced_section.body.isAncestorOf(page.conflicts_list)
    assert not page.advanced_section.body.isAncestorOf(page.findings_view)


def test_generate_offers_no_second_kind_of_output(reviewed):
    """A ligand file is an Entities action, not a scope on this page."""
    page = reviewed.output_page
    hints = {
        label.text()
        for label in page.findChildren(QLabel)
        if label.property("role") == "hint"
    }
    assert _text("gui.output_scope_base_note") in hints
    assert not hasattr(page, "_variant_row")
    assert not hasattr(page, "variant_choice")
    assert not hasattr(page, "scope_note_text")
    assert page._plan_arguments() == {
        "output_root": page.destination.text(),
        "scope": "base",
        "only": None,
        "overwrite_policy": page._policy_name(page.overwrite_policy),
        "path_policy": page._policy_name(page.path_policy),
    }
