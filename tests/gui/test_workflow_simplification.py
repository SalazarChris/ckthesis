"""Stage 9: the workflow-simplification pass, driven through the real widgets.

The changes this module pins are deliberately small and user-facing:

- the standalone **JSON preview** destination and its Overview shortcut are
  gone (the document is still produced by the service and still saved through
  the existing path);
- the Entities workspace is one compact column: the selected entity's facts
  and its own advanced settings share it, and a family never shows a section
  that cannot apply to it;
- Variants opens on three explained choices and shows one workflow at a time,
  with a way back that commits nothing;
- Generate is four ordered steps with the scope as explained choices, and the
  advanced options stay collapsed without hiding conflicts or findings.

Every assertion reads a real widget, service state, or the files the existing
pipeline writes; none reads source text.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtWidgets import QGroupBox, QPlainTextEdit, QPushButton  # noqa: E402

from configbuilder.ui.present.strings import STRINGS  # noqa: E402
from configbuilder.ui.present.strings import text as _text  # noqa: E402


# -- navigation --------------------------------------------------------------


def test_json_preview_is_no_longer_a_destination(reviewed):
    """Four destinations; the JSON pane exists only as an internal view."""
    assert reviewed.sidebar_labels() == [
        _text("gui.tab_overview"),
        _text("gui.tab_entities"),
        _text("gui.tab_variants"),
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


# -- variants ----------------------------------------------------------------


def test_variants_opens_on_three_choices_and_nothing_else(reviewed):
    page = reviewed.variants_page
    assert page.current_path() == "choose"
    choices = [
        button.text()
        for button in page.findChildren(QPushButton)
        if button.property("role") == "choice"
    ]
    assert choices == [
        _text("gui.variants_one_title"),
        _text("gui.variants_series_title"),
        _text("gui.variants_batch_title"),
    ]
    assert page.one_page.isHidden()
    assert page.series_page.isHidden()
    assert page.batch_page.isHidden()


def test_variants_puts_the_creation_choices_above_the_existing_list(reviewed):
    """The first screen is the three choices; the list sits below them."""
    page = reviewed.variants_page
    assert page.splitter.widget(0) is page.workspace
    assert page.splitter.widget(1) is page.list_group
    # Nothing to list yet, so the empty list and its disabled actions are not
    # competing with the three choices.
    assert page.list_group.isHidden()

    assert reviewed.state.add_spec_with_edit(
        "v1", "Variant one", "sequence", "GGGGS", record_key="A"
    ).ok
    reviewed.refresh()
    assert not page.list_group.isHidden()


def test_leaving_a_variant_workflow_commits_nothing(reviewed):
    page = reviewed.variants_page
    base = reviewed.state.configuration

    page.series_choice_button.click()
    assert page.current_path() == "series"
    assert not page.series_page.isHidden()
    assert page.one_page.isHidden()

    # Fill in a plan but do not create it; leaving must not commit it.
    page.series_start.setValue(1)
    page.series_factor.setValue(2)
    page.series_levels.setValue(2)
    assert reviewed.state.specs == ()

    page.back_to_choices()

    assert page.current_path() == "choose"
    assert reviewed.state.specs == ()
    assert reviewed.state.configuration is base


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
    # Scope is explained, not a drop-down of three opaque strings.
    assert page.scope_all.isCheckable()
    assert page.scope_selected.isCheckable()
    assert page.scope_base.isCheckable()
    # Advanced stays one click away; conflicts and findings never do.
    assert page.advanced_section.is_expanded() is False
    assert not page.advanced_section.body.isAncestorOf(page.conflicts_list)
    assert not page.advanced_section.body.isAncestorOf(page.findings_view)


def test_generate_shows_the_variant_picker_only_for_the_selected_scope(reviewed):
    """The empty picker is not shown under scopes that never use it."""
    page = reviewed.output_page
    assert page._variant_row.isHidden()
    assert reviewed.state.add_spec_with_edit(
        "v1", "Variant one", "sequence", "GGGGS", record_key="A"
    ).ok
    reviewed.refresh()

    page.choose_scope("selected")
    assert not page._variant_row.isHidden()
    page.choose_scope("variants")
    assert page._variant_row.isHidden()


def test_generate_disables_a_scope_the_job_cannot_support(window):
    window.state.new_job("scope-job")
    assert window.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    window.refresh()
    page = window.output_page

    # No variants yet: only the base file can be written.
    assert page.scope_value() == "base"
    assert page.scope_available("base")
    assert not page.scope_available("variants")
    assert not page.scope_available("selected")
    assert page.scope_note_text() == _text("gui.output_scope_unavailable")

    # A variant makes both variant scopes available, and the page opens on
    # the scope that writes them all.
    assert window.state.add_spec_with_edit(
        "v1", "Variant one", "sequence", "GGGGS", record_key="A"
    ).ok
    window.refresh()

    assert page.scope_available("variants")
    assert page.scope_available("selected")
    assert page.scope_all.isChecked()
    assert page.scope_note_text() == ""
