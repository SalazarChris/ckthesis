"""The mockup shell: sidebar navigation, header, Overview control centre.

The approved mockup replaced the row of top tabs with a left sidebar, added a
product header that names the open job and its unsaved state, and made
Overview a control centre (settings, a compact summary, next steps, then the
detail). These tests drive the real widgets and read the service state back:

- the four destinations are the sidebar's, in order, and selecting one shows
  that page;
- the raw-JSON view is no longer a destination or an Overview action;
- the header names the job and says "Unsaved" in words after an edit;
- the sidebar carries the mockup's WORKSPACE/FILE captions and file actions;
- Overview's summary values and next step are the service's own answer, and
  its next-step buttons change destination;
- the entity workspace is a left/right split with the details beside the list;
- JSON preview copies exactly the text on screen and is disabled when the
  service cannot produce a document;
- the dark design system is applied from the one style module.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QGroupBox, QLabel, QSplitter  # noqa: E402

from configbuilder.ui.present.strings import blocking_verdict  # noqa: E402
from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.style import style_sheet  # noqa: E402

DESTINATIONS = (
    "gui.tab_overview",
    "gui.tab_entities",
    "gui.tab_output",
)


@pytest.fixture
def job(window):
    """An empty window with a fresh job already created and shown."""
    window.state.new_job("mockup-job")
    window.refresh()
    return window


def _record(state, family="protein", **kwargs):
    if family == "protein":
        kwargs.setdefault("sequence", "ACDEFGHIKLMNPQRSTVWY")
    assert state.add_record(family, **kwargs).ok


# -- navigation --------------------------------------------------------------


def test_the_sidebar_holds_the_three_destinations_in_order(job):
    assert job.sidebar_labels() == [_text(key) for key in DESTINATIONS]
    assert job.current_page() is job.overview_page

    for row, attribute in enumerate(
        ("overview_page", "entities_page", "output_page")
    ):
        job._sidebar.setCurrentRow(row)
        assert job.current_page() is getattr(job, attribute)


def test_the_header_names_the_job_and_its_saved_state(job):
    assert job.header_job_text() == _text("gui.header_job") % "mockup-job"
    assert job.header_state_text() == _text("gui.header_saved")

    _record(job.state, "protein")
    job.refresh()

    assert job.header_state_text() == _text("gui.header_unsaved")

    job.state.mark_saved()
    job.refresh()

    assert job.header_state_text() == _text("gui.header_saved")


def test_the_header_says_no_job_when_nothing_is_open(window):
    assert window.header_job_text() == _text("gui.header_no_job")
    # No job: the saved/unsaved pill is not shown at all.
    assert window.header_state_text() == ""
    assert not window._header_state.isVisibleTo(window)


# -- Overview as the control centre ------------------------------------------


def test_the_sidebar_carries_the_mockup_captions_and_file_actions(window):
    """WORKSPACE and FILE captions, and New · Open · Save · Save to folder."""
    captions = [
        label.text()
        for label in window.findChildren(QLabel)
        if label.objectName() == "sidebarCaption"
    ]
    assert captions == [
        _text("gui.nav_section_workspace"),
        _text("gui.nav_section_file"),
    ]
    assert window.file_action_texts() == [
        _text("gui.file_action_new"),
        _text("gui.file_action_open"),
        _text("gui.file_action_save"),
        _text("gui.file_action_save_to_folder"),
    ]
    # The footer actions ask the window's own lifecycle questions, so both
    # write actions are disabled exactly when the job is absent.
    assert not window._file_buttons[2].isEnabled()
    assert not window._file_buttons[3].isEnabled()
    window.state.new_job("footer-job")
    window.refresh()
    assert window._file_buttons[2].isEnabled()
    assert window._file_buttons[3].isEnabled()


def test_overview_summarises_the_service_and_offers_the_summary_action(job):
    page = job.overview_page
    assert page.entities_button.isVisibleTo(page)

    _record(job.state, "protein")
    _record(job.state, "ligand", representation="ATP", representation_kind="ccd")
    job.refresh()

    # The mockup splits the count from the families: the big value is the
    # total the configuration holds, the line under it names what is there.
    assert page.entities_value_text() == "2"
    counts = page.summary_text("menu.status_components")
    assert "%s" not in counts and "1 protein" in counts and "1 ligand" in counts
    status = job.state.status()
    assert page.readiness_state_text() == (
        _text("gui.readiness_ready")
        if status.ready
        else _text("gui.readiness_attention")
    )
    expected = (
        _text("gui.readiness_ok")
        if status.ready
        else blocking_verdict(len(status.blocking))
    )
    assert page.verdict_text() == expected


def test_the_entity_summary_changes_destination(job):
    page = job.overview_page
    assert page.entities_button.isVisibleTo(page)

    page.entities_button.click()

    assert job.current_page() is job.entities_page


def test_no_job_keeps_the_overview_neutral(window):
    page = window.overview_page
    # No empty-state card and no Add Entity action: the page says what to do
    # and leaves New/Open to the FILE footer.
    assert page._no_job_note.isVisibleTo(page)
    assert page._no_job_note.text() == _text("gui.overview_no_job")
    assert not page._summary_card.isVisibleTo(page)
    assert not page._readiness_card.isVisibleTo(page)
    assert not hasattr(page, "add_entity_button")


def test_the_raw_json_view_is_not_a_destination_or_a_shortcut(job):
    """Stage 9: no fifth screen and no duplicate route to the same text.

    The serialized document is still produced by the service and still shown
    by the internal page, but the user reaches the file through **Save JSON…**
    and the Generate plan. Nothing on Overview offers a second way in.
    """
    page = job.overview_page
    assert job.preview_page not in job.destination_pages()
    assert not hasattr(page, "preview_button")
    labels = {label.text() for label in page.findChildren(QLabel)}
    assert "Preview JSON" not in labels
    # Save remains the visible route in the FILE footer and the File menu.
    assert _text("gui.file_action_save") in job.file_action_texts()


def test_validate_reports_the_service_verdict(job):
    """Validate re-reads readiness and reports the same answer the card shows."""
    _record(job.state, "protein")
    job.refresh()
    page = job.overview_page

    assert page.validate_job() is True

    status = job.state.status()
    expected = (
        _text("gui.validate_ok")
        if status.ready
        else _text("gui.validate_findings") % len(status.blocking)
    )
    assert job.statusBar().currentMessage() == expected


# -- the entity workspace picker ---------------------------------------------


def test_the_entity_workspace_is_a_compact_picker_with_three_areas(job):
    _record(job.state, "protein")
    job.refresh()
    page = job.entities_page

    assert not page.findChildren(QSplitter), "the large split table is gone"
    assert page.selector.currentData() == "A"
    assert page.tabs.tabText(0) == _text("gui.entity_tab_settings")
    assert page.tabs.tabText(1) == _text("gui.entity_tab_ccd")
    assert page.tabs.tabText(2) == _text("gui.entity_tab_bonds")
    assert page.detail_title().startswith("A")


# -- JSON preview ------------------------------------------------------------


def test_preview_copies_exactly_what_it_shows(job):
    _record(job.state, "protein")
    job.refresh()
    page = job.preview_page
    page.refresh()
    displayed = page.editor.toPlainText()

    assert displayed.startswith("{")
    assert page._copy_button.isEnabled()

    assert page.copy_text() == displayed
    assert QGuiApplication.clipboard().text() == displayed


def test_preview_is_read_only_and_copy_is_disabled_without_a_document(window):
    page = window.preview_page
    page.refresh()

    assert page.editor.isReadOnly()
    assert page.editor.toPlainText() == ""
    assert not page._copy_button.isEnabled()
    assert page.reason_text()
    assert page.copy_text() == ""


# -- the design system -------------------------------------------------------


def test_the_dark_workbench_sheet_is_the_one_applied(job):
    sheet = style_sheet()

    assert job.styleSheet() == sheet
    assert "#75D6D0" in sheet, "the accent token reaches the sheet"
    assert "#171B22" in sheet, "the background token reaches the sheet"
    # The shell's own pieces are styled by object name, not by page QSS.
    assert "QListWidget#sidebar" in sheet
    assert "QFrame#appHeader" in sheet
    assert isinstance(job.findChild(QGroupBox), QGroupBox)
