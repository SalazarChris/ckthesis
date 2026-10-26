"""Stage 7: the final UX pass, driven through the real widgets.

Each test builds the job through the services and asserts on service state,
window chrome and the widgets the user actually sees — not on source text. The
Stage 7 changes these cover:

- Overview edits the job-wide values (name, seeds, version) through
  ``ConfigurationService``, and since Stage 8 it is the only place that does
  so — the Job Settings tab is gone;
- the window title names the open job and marks unsaved changes;
- the status bar's standing hint matches the current state;
- the selected entity's advanced settings live in the Entities workspace;
- the shared style sheet is applied;
- a planned asset path can be copied from the plan.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import QLabel  # noqa: E402

from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.style import hint_label, style_sheet  # noqa: E402


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def job(window):
    """An empty window with a fresh job already created and shown."""
    window.state.new_job("ux-job")
    window.refresh()
    return window


def _select(combo, value):
    index = combo.findData(value)
    assert index >= 0, "no choice %r in %r" % (value, combo.count())
    combo.setCurrentIndex(index)


# -- Overview edits the job-wide values --------------------------------------


def test_overview_edits_the_job_name_through_the_service(job):
    page = job.overview_page
    assert page.job_settings.name_edit.text() == "ux-job"

    page.job_settings.name_edit.setText("renamed job")
    assert page.job_settings.apply_name() is True

    assert job.state.configuration.metadata.name == "renamed job"
    assert job.settings_page.name_edit.text() == "renamed job"
    # The rename is an unsaved edit, and the title says so.
    assert job.windowTitle() == _text("gui.window_title_dirty") % "renamed job"


def test_overview_edits_seeds_and_version_through_the_service(job):
    page = job.overview_page

    page.job_settings.seeds_edit.setText("1, 2, 3")
    assert page.job_settings.apply_seeds() is True
    assert job.state.configuration.seeds.values == (1, 2, 3)
    assert job.settings_page.seeds_edit.text() == "1, 2, 3"

    _select(page.job_settings.version_combo, 4)
    assert page.job_settings.apply_version() is True
    assert job.state.configuration.format_target.version_selection.version == 4
    assert job.settings_page.version_combo.currentData() == 4


def test_a_refused_overview_edit_reports_and_restores_the_service_value(job):
    page = job.overview_page
    page.job_settings.name_edit.setText("   ")

    assert page.job_settings.apply_name() is False

    assert job.last_problem_text()
    assert job.state.configuration.metadata.name == "ux-job"
    assert page.job_settings.name_edit.text() == "ux-job"


def test_the_one_settings_editor_follows_the_service_without_a_second_copy(job):
    """A change made elsewhere reaches the editor — and there is only one."""
    assert job.state.set_job_name("from elsewhere").ok

    job.refresh()

    assert job.overview_page.job_settings.name_edit.text() == "from elsewhere"
    # ``settings_page`` names that same widget: no page of its own remains.
    assert job.settings_page is job.overview_page.job_settings


# -- window chrome -----------------------------------------------------------


def test_the_title_names_the_job_and_marks_unsaved_changes(job):
    assert job.windowTitle() == _text("gui.window_title_job") % "ux-job"

    assert job.state.add_record("protein", sequence="ACDEFG").ok
    job.refresh()

    assert job.windowTitle() == _text("gui.window_title_dirty") % "ux-job"


def test_a_recorded_save_clears_the_unsaved_marker(job):
    assert job.state.add_record("protein", sequence="ACDEFG").ok
    job.refresh()
    assert job.windowTitle().startswith("ux-job*")

    job.state.mark_saved()
    job.refresh()

    assert job.windowTitle() == _text("gui.window_title_job") % "ux-job"


def test_the_title_falls_back_to_the_application_name_without_a_job(window):
    assert window.windowTitle() == _text("gui.window_title")


def test_the_status_notice_follows_the_job_state(job):
    assert job.notice_text() == _text("gui.notice_job")

    assert job.state.add_record("protein", sequence="ACDEFG").ok
    job.refresh()
    assert job.notice_text() == _text("gui.notice_dirty")

    job.state.mark_saved()
    job.refresh()
    assert job.notice_text() == _text("gui.notice_job")


# -- the entity workspace ----------------------------------------------------


def test_the_entity_workspace_hosts_the_advanced_settings(reviewed):
    """Stage 9: the entity's settings are inside its single workspace column.

    There is no inner notebook to hunt through and no top-level Advanced tab:
    the details card and the advanced sections share one scroll surface beside
    the entity table.
    """
    page = reviewed.entities_page
    assert page.workspace.widget().isAncestorOf(reviewed.advanced_page)
    # Job-wide tools are their own work areas, not part of the entity column.
    assert not page.workspace.isAncestorOf(reviewed.ccd_page)
    assert not page.workspace.isAncestorOf(reviewed.bonds_page)
    assert page.ccd_tab.isAncestorOf(reviewed.ccd_page)
    assert page.bonds_tab.isAncestorOf(reviewed.bonds_page)
    assert page.tabs.count() == 3
    assert "Advanced settings" not in reviewed.sidebar_labels()


def test_the_workspace_follows_the_selected_entity(reviewed):
    reviewed.entities_page.select_record("A")

    assert reviewed.advanced_page.record_key() == "A"

    reviewed.entities_page.select_record("B")

    assert reviewed.advanced_page.record_key() == "B"


def test_the_workspace_can_edit_the_selected_entity(reviewed, monkeypatch):
    """A modification applied from the embedded tab reaches the service."""
    from PySide6.QtWidgets import QDialog

    from configbuilder.ui.render.qt.dialogs import ModificationFormDialog

    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        dialog.code_edit.setText("SEP")
        dialog.position_spin.setValue(6)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(ModificationFormDialog, "exec", fake_exec)
    reviewed.entities_page.select_record("A")
    page = reviewed.advanced_page

    assert page.add_modification() is True

    record = next(
        item
        for item in reviewed.state.configuration.records
        if item.ids.primary.value == "A"
    )
    positions = [item.position.value for item in record.modifications]
    assert positions == [4, 6], "the fixture's PTM plus the one added here"
    assert page.modification_rows()[-1] == ("SEP", "6", "G")


# -- presentation ------------------------------------------------------------


def test_the_window_carries_the_shared_style_sheet(window):
    assert window.styleSheet() == style_sheet()
    assert "QGroupBox" in window.styleSheet()
    assert hint_label("why").property("role") == "hint"


# -- copying a planned path --------------------------------------------------


def test_a_planned_asset_path_can_be_copied(reviewed, tmp_path):
    from PySide6.QtGui import QGuiApplication

    msa = tmp_path / "chain-a.a3m"
    msa.write_text(">query\nACDEFG\n", encoding="utf-8")
    assert reviewed.state.set_alignment("A", "unpaired", external_path=str(msa)).ok
    reviewed.refresh()
    page = reviewed.output_page
    page.destination.setText(str(tmp_path / "out"))
    _select(page.path_policy, "CopyIntoAssets")
    assert page.preview_plan() is True

    page.resources_table.selectRow(0)
    copied = page.copy_selected_path()

    assert copied == page.resource_rows()[0][2]
    assert QGuiApplication.clipboard().text() == copied
