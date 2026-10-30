"""Stage 8: the UX simplification pass, driven through the real widgets.

The three problems this stage fixes were reported after a launch of the
Stage 7 build: job-wide settings existed twice, Generate & Output showed every
option at once, and Variants & Batch did not say which workflow to choose.

These tests drive the pages' own widgets and assert on *service* state and on
the files the existing pipeline writes — never on source text — so a page that
only relabelled itself would fail here:

- the top-level navigation has one settings destination (Overview), and the
  Overview editor applies name, seeds and version through the services;
- an accepted edit refreshes the service-backed views, a refused one keeps the
  service's value and reports it;
- Generate & Output runs destination -> review -> confirm -> result for the
  open job's own file, keeps conflicts visible while the advanced disclosure
  is collapsed, and writes nothing when it is cancelled or refused;
- the ligand file workflow (an Entities action) has its own suite.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QDialog, QGroupBox, QLabel, QTabWidget  # noqa: E402

from configbuilder.ui.present.strings import blocking_verdict  # noqa: E402
from configbuilder.ui.present.strings import text as _text  # noqa: E402
_TOP_LEVEL_TABS = (
    "gui.tab_overview",
    "gui.tab_entities",
    "gui.tab_output",
)


# -- fixtures and helpers ----------------------------------------------------


@pytest.fixture
def job(window):
    """An empty window with a fresh job already created and shown."""
    window.state.new_job("stage8-job")
    window.refresh()
    return window


def _select(combo, value):
    index = combo.findData(value)
    assert index >= 0, "no choice %r in %r" % (value, combo.count())
    combo.setCurrentIndex(index)


def _top_labels(window):
    """The destination labels the sidebar shows, in order."""
    return window.sidebar_labels()


# -- Workstream A: Overview is the only settings destination -----------------


def test_only_overview_owns_the_job_settings(job):
    assert _top_labels(job) == [_text(key) for key in _TOP_LEVEL_TABS]
    assert job.settings_page is job.overview_page.job_settings
    assert job.overview_page.isAncestorOf(job.settings_page)

    page = job.overview_page.job_settings
    for widget in (
        page.name_edit,
        page.name_apply,
        page.seeds_edit,
        page.seeds_apply,
        page.version_combo,
        page.version_apply,
    ):
        assert widget.isEnabled()


def test_an_overview_change_refreshes_the_service_backed_views(job):
    assert job.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    job.refresh()
    page = job.overview_page
    page.job_settings.name_edit.setText("stage8 renamed")

    assert page.job_settings.apply_name() is True

    # The service is the authority, and the views that show the name refreshed
    # from it: the title's dirty marker, the two base labels, the JSON preview.
    assert job.state.configuration.metadata.name == "stage8 renamed"
    assert job.windowTitle() == _text("gui.window_title_dirty") % "stage8 renamed"
    assert "stage8 renamed" in job.output_page._base_label.text()
    assert "stage8 renamed" in job.preview_page.editor.toPlainText()

    # The verdict is still the validation service's own answer.
    status = job.state.status()
    expected = (
        _text("gui.readiness_ok")
        if status.ready
        else blocking_verdict(len(status.blocking))
    )
    assert page.verdict_text() == expected

    page.job_settings.seeds_edit.setText("4, 5")
    assert page.job_settings.apply_seeds() is True
    assert job.state.configuration.seeds.values == (4, 5)

    _select(page.job_settings.version_combo, 4)
    assert page.job_settings.apply_version() is True
    assert job.state.configuration.format_target.version_selection.version == 4


def test_a_refused_overview_change_keeps_the_service_value_and_reports(job):
    page = job.overview_page.job_settings
    page.name_edit.setText("   ")

    assert page.apply_name() is False

    assert job.last_problem_text()
    assert job.state.configuration.metadata.name == "stage8-job"
    assert page.name_edit.text() == "stage8-job"


# -- Workstream C: the four-step generation flow -----------------------------


def test_the_generate_page_is_one_action_and_hides_options_and_details(job):
    """Two groups: where the file goes, then what happened."""
    page = job.output_page
    titles = [group.title() for group in page.findChildren(QGroupBox)]
    for key in (
        "gui.output_group_output",
        "gui.output_group_result",
    ):
        assert _text(key) in titles
    headings = {
        label.text()
        for label in page.findChildren(QLabel)
        if label.property("role") == "heading"
    }
    assert _text("gui.output_group_warnings") in headings

    section = page.advanced_section
    assert section.header_text() == _text("gui.output_advanced")
    assert section.is_expanded() is False
    assert section.body.isHidden()
    assert section.body.isAncestorOf(page.overwrite_policy)
    assert section.body.isAncestorOf(page.path_policy)
    # Conflicts and warnings are deliberately outside the disclosure.
    assert not section.body.isAncestorOf(page.conflicts_list)
    assert not section.body.isAncestorOf(page.warnings_list)
    # The plan tables are one fold further down, below the action.
    details = page.details_section
    assert details.header_text() == _text("gui.output_plan_details")
    assert details.is_expanded() is False
    assert details.body.isAncestorOf(page.entries_table)

    page.destination.setText("C:/somewhere")
    section.toggle()

    assert section.is_expanded() is True
    assert not section.body.isHidden()

    section.toggle()

    assert section.is_expanded() is False
    assert section.body.isHidden()
    assert page.destination.text() == "C:/somewhere", "collapsing keeps values"


def test_generate_writes_the_service_plan_in_one_click(job, tmp_path):
    assert job.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    job.refresh()
    page = job.output_page
    page.destination.setText(str(tmp_path))
    assert page.generate_button.isEnabled(), "one click is available at once"

    # Preview is optional: it shows the service's own plan and writes nothing.
    assert page.preview_plan() is True
    rows = page.entries()
    plan = job.state.plan_generation(
        output_root=str(tmp_path),
        scope="base",
        only=None,
        overwrite_policy=page.overwrite_policy.currentData(),
        path_policy=page.path_policy.currentData(),
    )
    assert [row[2] for row in rows] == [entry.path for entry in plan.entries]
    assert "nothing has been written" in page.plan_note_text()
    assert list(tmp_path.iterdir()) == []

    # The click itself: no question for a file that does not exist yet.
    asked = []
    page.replacement_confirmer = (
        lambda parent, message: asked.append(message) or True
    )
    assert page.generate() is True

    assert asked == []
    assert os.path.isfile(rows[0][2])
    assert _text("gui.output_written") in page.result_text()
    assert page.plan_note_text() == _text("gui.output_plan_done")


def test_a_refused_write_and_a_conflict_leave_the_disk_alone(job, tmp_path):
    page = job.output_page
    page.destination.setText(str(tmp_path))

    # An empty job cannot be written: the service's findings are shown and
    # nothing is created. The button stays available for the retry.
    assert page.generate() is False
    assert page.findings_model.rowCount() > 0
    assert page.conflicts_list.count() == 0
    assert page.generate_button.isEnabled()
    assert list(tmp_path.iterdir()) == []

    # A real conflict with the options still collapsed.
    assert job.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    job.refresh()
    target = page.destination_file()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("not generated")

    assert page.generate() is False

    assert page.advanced_section.is_expanded() is False
    assert page.conflicts_list.count() == 1
    assert page.conflicts_label.text() == _text("gui.output_conflicts") % 1
    assert target in page.conflicts_list.item(0).text()
    with open(target, encoding="utf-8") as handle:
        assert handle.read() == "not generated"
    assert [
        os.path.join(root, name)
        for root, _directories, files in os.walk(str(tmp_path))
        for name in files
    ] == [target]


def test_an_asset_path_can_be_selected_and_copied_with_options_collapsed(
    job, tmp_path
):
    from PySide6.QtGui import QGuiApplication

    assert job.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    msa = tmp_path / "chain-a.a3m"
    msa.write_text(">query\nACDEFG\n", encoding="utf-8")
    assert job.state.set_alignment("A", "unpaired", external_path=str(msa)).ok
    job.refresh()
    page = job.output_page
    page.destination.setText(str(tmp_path / "out"))
    _select(page.path_policy, "CopyIntoAssets")

    assert page.preview_plan() is True

    assert page.advanced_section.is_expanded() is False
    assert page.resources_table.rowCount() == 1
    page.resources_table.selectRow(0)

    copied = page.copy_selected_path()

    assert copied == page.resource_rows()[0][2]
    assert QGuiApplication.clipboard().text() == copied
