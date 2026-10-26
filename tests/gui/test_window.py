"""The shell itself: it opens, it reads, and Stage 2 offers the lifecycle.

The action tests pin the *exact* action surface: New Job, Open, Save JSON
and Quit — and the continued absence of generate/execute/export wording,
which is what keeps later stages out of this window.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import QToolBar, QToolButton  # noqa: E402

from configbuilder.ui.present.strings import STRINGS  # noqa: E402
from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.state import build_demo_state  # noqa: E402
from configbuilder.ui.render.qt.windows import MainWindow  # noqa: E402


def test_the_window_can_be_created_and_closed(qapp, state):
    main_window = MainWindow(state)
    assert main_window.windowTitle() == _text("gui.window_title")
    main_window.show()
    assert main_window.isVisible()
    main_window.close()
    assert not main_window.isVisible()


def test_the_window_shows_its_destinations(qapp, state):
    """Overview, Entities, Generate — three, in order.

    Stage 8 removed the Job Settings tab (Overview owns those values) and
    Stage 9 removed the standalone JSON preview: the document is reached by
    saving it, so a fifth destination that only displayed raw text was
    redundant. The mockup shell replaced the top tab row with the left
    sidebar, so the destinations are read from the sidebar the user clicks.
    The Variants & Batch destination is gone too: a file of ligands is now an
    action on the Entities page, not a workspace of its own.
    """
    main_window = MainWindow(state)
    assert main_window.sidebar_labels() == [
        _text("gui.tab_overview"),
        _text("gui.tab_entities"),
        _text("gui.tab_output"),
    ]
    assert main_window.current_page() is main_window.overview_page
    assert main_window.destination_pages() == (
        main_window.overview_page,
        main_window.entities_page,
        main_window.output_page,
    )
    # The JSON view still exists for the serialization checks, but it is not
    # one of the pages the sidebar (or any action) can reach.
    assert main_window.preview_page not in main_window.destination_pages()
    # The entity's own settings are in the Entities workspace itself; there is
    # no second top-level destination for them.
    assert main_window.entities_page.workspace.isAncestorOf(
        main_window.advanced_page
    )
    # The one settings editor is Overview's panel; the accessor the lifecycle
    # tests use names that same widget, not a page of its own.
    assert main_window.settings_page is main_window.overview_page.job_settings
    main_window.close()


def test_an_empty_state_reports_no_project_rather_than_failing(window):
    """No job open: every page says so instead of raising."""
    assert window.state.project is None
    assert window.entities_page.model.rowCount() == 0
    assert window.overview_page.entities_value_text() == "0"
    assert window.overview_page._no_job_note.isVisibleTo(window.overview_page)
    assert window.preview_page.editor.toPlainText() == ""


def _menu_actions(window):
    """The actions the File menu really offers (its separators aside)."""
    file_menu = window.menuBar().actions()[0].menu()
    return [action for action in file_menu.actions() if not action.isSeparator()]


def test_the_window_offers_exactly_the_stage_two_actions(window):
    """New Job, Open, Save JSON and Quit — and nothing beyond this stage."""
    assert [action.text() for action in _menu_actions(window)] == [
        _text("gui.action_new_job"),
        _text("gui.action_open"),
        _text("gui.action_save"),
        _text("gui.action_quit"),
    ]
    # The same three actions sit in the sidebar's FILE footer, as the mockup
    # arranges them, with short labels and the full wording in each tooltip.
    assert window.file_action_texts() == [
        _text(key)
        for key in ("gui.file_action_new", "gui.file_action_open", "gui.file_action_save")
    ]
    # No toolbar bar: the header carries product identity only.
    assert window.findChild(QToolBar) is None
    assert all(button.text() for button in window.findChildren(QToolButton) if button.isVisibleTo(window))
    # Generate/execute/export wording still appears on no action: the bulk
    # output stage does not exist yet, and the check is driven by the
    # registry, so adding such an action fails this test rather than quietly
    # widening the window's job.
    not_yet = {
        STRINGS[key]
        for key in STRINGS
        if any(word in key for word in ("generate", "execute", "export"))
    }
    on_screen = {action.text() for action in window.findChildren(QAction)}
    assert not (on_screen & not_yet)


def test_save_needs_an_open_job(window):
    """Save JSON is offered only when there is something to save."""
    actions = {action.text(): action for action in window.findChildren(QAction)}
    assert not actions[_text("gui.action_save")].isEnabled()
    window.state.new_job()
    assert actions[_text("gui.action_save")].isEnabled()


def test_the_editing_scope_notice_is_visible(window):
    """The standing hint says what is true now, not what an earlier stage
    promised: no job yet, and nothing leaves the machine."""
    assert window.notice_text() == _text("gui.notice_no_job")


def test_the_status_bar_says_when_no_file_is_open(window):
    assert window.source_text() == _text("gui.source_none")


def test_demo_mode_labels_itself_as_sample_data(qapp):
    demo = build_demo_state()
    main_window = MainWindow(demo)
    assert demo.is_demo
    assert main_window.source_text() == _text("gui.demo_notice")
    # The sample job is reviewable straight away: every record is listed, and
    # the builder produces its JSON without complaint.
    assert main_window.entities_page.model.rowCount() == len(demo.configuration.records)
    assert main_window.preview_page.editor.toPlainText().startswith("{")
    main_window.close()
