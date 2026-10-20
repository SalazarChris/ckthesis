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
- the variants page presents three explained creation paths, keeps every
  earlier operation reachable, and creating nothing changes nothing;
- series and file batches report their plan before anything is committed, and
  malformed input is visible first;
- editing a variant never touches the base configuration;
- Generate & Output runs select -> destination -> review -> confirm -> result,
  keeps conflicts visible while the advanced disclosure is collapsed, and
  writes nothing when it is cancelled or refused.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QDialog, QGroupBox, QLabel, QTabWidget  # noqa: E402

from configbuilder.ui.present.strings import blocking_verdict  # noqa: E402
from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.dialogs import (  # noqa: E402
    NewVariantDialog,
    VariantChangeDialog,
)

_TOP_LEVEL_TABS = (
    "gui.tab_overview",
    "gui.tab_entities",
    "gui.tab_variants",
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


def _check_components(page, components):
    for row in range(page.series_components.count()):
        item = page.series_components.item(row)
        item.setCheckState(
            Qt.Checked if item.data(Qt.UserRole) in components else Qt.Unchecked
        )


def _drive_new(monkeypatch, cancel=True):
    """Answer the new-variant dialog: cancelled, or with a sequence change."""
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        dialog.name_edit.setText("Variant one")
        dialog.key_edit.setText("v1")
        dialog.change_editor.select_kind("sequence")
        _select(dialog.change_editor.sequence_entity, "A")
        dialog.change_editor.sequence_edit.setPlainText("GGGGS")
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(NewVariantDialog, "exec", fake_exec)
    return opened


def _drive_change(monkeypatch, fill):
    def fake_exec(dialog):
        dialog.change_editor.select_kind("job_name")
        fill(dialog.change_editor)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(VariantChangeDialog, "exec", fake_exec)


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
    assert "stage8 renamed" in job.variants_page._base_label.text()
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


# -- Workstream B: three explained creation paths ----------------------------


def test_the_variants_page_opens_on_three_explained_paths(job):
    """Stage 9: a chooser first; one workflow at a time, with a way back."""
    page = job.variants_page
    assert page.current_path() == "choose"

    # Exactly the three primary choices, each with its own sentence.
    assert page.one_choice_button.text() == _text("gui.variants_one_title")
    assert page.series_choice_button.text() == _text("gui.variants_series_title")
    assert page.batch_choice_button.text() == _text("gui.variants_batch_title")
    hints = {
        label.text()
        for label in page.findChildren(QLabel)
        if label.property("role") == "hint"
    }
    for key in (
        "gui.variants_one_hint",
        "gui.variants_series_hint",
        "gui.variants_batch_hint",
    ):
        assert _text(key) in hints

    # Choosing one shows that workflow only; Back returns to the choices.
    for button, path in (
        (page.one_choice_button, "one"),
        (page.series_choice_button, "series"),
        (page.batch_choice_button, "batch"),
    ):
        button.click()
        assert page.current_path() == path
        page.back_to_choices()
        assert page.current_path() == "choose"
        assert page.one_page.isHidden()
        assert page.series_page.isHidden()
        assert page.batch_page.isHidden()

    # Every operation the earlier stages offered is still reachable.
    for method in (
        "new_variant",
        "add_change",
        "rename_variant",
        "duplicate_variant",
        "remove_variant",
        "preview_series",
        "create_series",
        "preview_batch",
        "create_batch",
        "validate_now",
    ):
        assert callable(getattr(page, method))
    assert page.new_button.text() == _text("gui.variants_new")
    for button in (
        page.add_change_button,
        page.rename_button,
        page.duplicate_button,
        page.remove_button,
    ):
        assert not button.isEnabled(), "no variant is selected yet"


def test_cancelling_the_one_variant_path_changes_nothing(job, monkeypatch):
    page = job.variants_page
    base = job.state.configuration
    _drive_new(monkeypatch, cancel=True)

    assert page.new_variant() is False

    assert job.state.specs == ()
    assert job.state.configuration is base


def test_a_series_preview_reports_its_count_and_commits_nothing(job):
    assert job.state.add_record(
        "ligand", representation="ATP", representation_kind="ccd", copies=2
    ).ok
    job.refresh()
    page = job.variants_page
    base = job.state.configuration
    choice = job.state.component_count_choices()[0]
    _check_components(page, {choice.value})
    page.series_start.setValue(1)
    page.series_factor.setValue(2)
    page.series_levels.setValue(3)

    assert page.preview_series() is True

    assert page.series_table.rowCount() == 3
    assert page.series_note.text() == _text("gui.variants_series_planned") % 3
    assert page.series_create_button.isEnabled()
    assert job.state.specs == (), "a preview creates nothing"
    assert job.state.configuration is base

    # Cancelling is the stale path: change a value and the commit is refused.
    page.series_factor.setValue(3)
    assert not page.series_create_button.isEnabled()
    assert page.create_series() is False
    assert job.state.specs == ()
    assert job.state.configuration is base

    # The same plan, previewed again, is the service's to commit.
    assert page.preview_series() is True
    assert page.create_series() is True
    assert len(job.state.specs) == 3
    assert job.state.configuration is base


def test_a_batch_preview_shows_entries_and_refuses_malformed_input(job, tmp_path):
    page = job.variants_page
    base = job.state.configuration
    good = tmp_path / "batch.txt"
    good.write_text("ACDEFG\nHIKLMN\n", encoding="utf-8")
    page.batch_path.setText(str(good))

    assert page.preview_batch() is True

    assert page.batch_table.rowCount() == 2
    assert page.batch_note.text() == _text("gui.variants_batch_preview_title") % (2, 2)
    assert page.batch_create_button.isEnabled()
    assert job.state.specs == (), "a preview creates nothing"
    assert job.state.configuration is base

    # Changing the input type after the preview refuses the commit.
    _select(page.batch_family, "dna")
    assert page.create_batch() is False
    assert job.state.specs == ()
    assert job.state.configuration is base

    # Malformed input is visible before anything is committed: digits are not
    # protein letters, so the file is refused whole with the service's message.
    bad = tmp_path / "bad.txt"
    bad.write_text("ACDEFG\nACD3FG\n", encoding="utf-8")
    page.batch_path.setText(str(bad))
    _select(page.batch_family, "protein")

    assert page.preview_batch() is False

    # The entries that were read stay visible; the problem is the file's, and
    # nothing was created from it.
    assert page.batch_table.rowCount() == 2
    assert page.batch_note.text() == _text("gui.variants_batch_invalid") % 2
    assert not page.batch_create_button.isEnabled()
    assert "line 2" in job.last_problem_text()
    assert job.state.specs == ()
    assert job.state.configuration is base


def test_editing_a_variant_leaves_the_base_configuration_untouched(job, monkeypatch):
    state = job.state
    assert state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    assert state.add_spec_with_edit("v1", "Variant one", "sequence", "GGGGS", record_key="A").ok
    job.refresh()
    page = job.variants_page
    base = state.configuration
    base_name = base.metadata.name

    page.table.selectRow(0)
    assert page.selected_key() == "v1"
    _drive_change(monkeypatch, lambda editor: editor.job_name_edit.setText("variant job"))

    assert page.add_change() is True

    spec = next(candidate for candidate in state.specs if candidate.key == "v1")
    assert len(spec.edits) == 2
    assert state.configuration is base
    assert state.configuration.metadata.name == base_name
    assert page.detail_status.text() == _text("gui.variants_status_header") % (
        page.row_status_text("v1")
    )


# -- Workstream C: the four-step generation flow -----------------------------


def test_the_generate_page_labels_its_steps_and_hides_advanced_options(job):
    """Stage 9: four numbered steps; the warnings live outside Advanced."""
    page = job.output_page
    titles = [group.title() for group in page.findChildren(QGroupBox)]
    for key in (
        "gui.output_group_scope",
        "gui.output_group_destination",
        "gui.output_group_plan",
        "gui.output_group_generate",
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

    page.destination.setText("C:/somewhere")
    section.toggle()

    assert section.is_expanded() is True
    assert not section.body.isHidden()

    section.toggle()

    assert section.is_expanded() is False
    assert section.body.isHidden()
    assert page.destination.text() == "C:/somewhere", "collapsing keeps values"


def test_generate_reviews_the_service_plan_then_writes_it(job, tmp_path):
    assert job.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    job.refresh()
    page = job.output_page
    page.destination.setText(str(tmp_path))
    assert page.choose_scope("base")
    assert not page.generate_button.isEnabled(), "no plan has been reviewed"

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

    # Cancel: the confirmation says no, and nothing is written.
    page.generation_confirmer = lambda parent, message: False
    assert page.generate() is False
    assert list(tmp_path.iterdir()) == []

    # Confirm: the reviewed plan's own paths appear on disk.
    asked = []
    page.generation_confirmer = (
        lambda parent, message: asked.append(message) or True
    )
    assert page.generate() is True

    assert asked and str(tmp_path) in asked[0]
    assert os.path.isfile(rows[0][2])
    assert _text("gui.output_written") in page.result_text()
    assert "Generation finished" in page.plan_note_text()


def test_a_refused_plan_and_a_conflict_write_nothing_while_collapsed(job, tmp_path):
    page = job.output_page
    page.destination.setText(str(tmp_path))

    # An empty job cannot be planned: the service's findings are shown and
    # nothing is created.
    assert page.preview_plan() is False
    assert page.findings_model.rowCount() > 0
    assert page.conflicts_list.count() == 0
    assert not page.generate_button.isEnabled()
    assert list(tmp_path.iterdir()) == []

    # A real conflict with the advanced options still collapsed.
    assert job.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    job.refresh()
    assert page.choose_scope("base")
    assert page.preview_plan() is True
    target = page.entries()[0][2]
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("not generated")

    assert page.preview_plan() is False

    assert page.advanced_section.is_expanded() is False
    assert page.conflicts_list.count() == 1
    assert page.conflicts_label.text() == _text("gui.output_conflicts") % 1
    assert target in page.conflicts_list.item(0).text()
    assert not page.generate_button.isEnabled()
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
    assert page.choose_scope("base")
    _select(page.path_policy, "CopyIntoAssets")

    assert page.preview_plan() is True

    assert page.advanced_section.is_expanded() is False
    assert page.resources_table.rowCount() == 1
    page.resources_table.selectRow(0)

    copied = page.copy_selected_path()

    assert copied == page.resource_rows()[0][2]
    assert QGuiApplication.clipboard().text() == copied
