"""Stage 2: New Job, Job Settings and Save JSON.

These tests drive the window's real sequence — the service calls, the state
updates, the refresh seam — while answering its modal questions through the
assignable seams (``discard_confirmer``, ``overwrite_confirmer``,
``save_path_chooser``) and the conftest recorders. No test clicks a real
dialog, and none claims a desktop window was opened; what is asserted is the
integration with the services: which call is made, what is written, what is
*not* written, and what the state believes afterwards.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import QTabWidget  # noqa: E402

from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.dialogs import ImportPreviewDialog  # noqa: E402


def _write_job(path, name):
    """A minimal, valid AF3 JSON document for the import round trip."""
    document = {
        "name": name,
        "modelSeeds": [1],
        "sequences": [{"protein": {"id": "A", "sequence": "ACDE"}}],
        "dialect": "alphafold3",
        "version": 3,
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return str(path)


def _make_dirty(state):
    """A valid job whose live configuration differs from its saved snapshot."""
    state.services.projects.new("before-edit")
    state.services.configuration.add_record("protein", "ACDE")
    state.mark_saved()
    state.services.configuration.set_name("edited after the save")
    assert state.is_dirty
    return state


def _choose(window, destination):
    window.save_path_chooser = lambda parent, default: (str(destination), True)


# -- New Job ------------------------------------------------------------------


def test_new_job_is_created_by_the_project_service(window):
    state = window.state
    calls = []
    real_new = state.services.projects.new

    def recording_new(name=None):
        calls.append(name)
        return real_new(name)

    state.services.projects.new = recording_new
    assert window.new_job() is True
    assert calls == [None]
    assert state.project is not None
    # The service's own default policy supplies the starting values; the GUI
    # does not override or invent any of them.
    assert state.configuration.metadata.name == "Untitled job 1"
    assert tuple(state.configuration.seeds.values) == (1,)
    assert state.configuration.format_target.version_selection.version == 3
    assert state.source_path == ""
    assert state.is_dirty is False


def test_new_job_cancelled_at_the_prompt_keeps_the_current_job(window):
    state = _make_dirty(window.state)
    before_project = state.project
    before_configuration = state.configuration
    window.discard_confirmer = lambda parent: False
    assert window.new_job() is False
    assert state.project is before_project
    assert state.configuration is before_configuration


def test_new_job_proceeds_only_when_the_discard_is_accepted(window):
    state = _make_dirty(window.state)
    asked = []
    window.discard_confirmer = lambda parent: (asked.append(parent), True)[1]
    assert window.new_job() is True
    assert len(asked) == 1
    assert state.configuration.metadata.name == "Untitled job 1"
    assert state.is_dirty is False


def test_new_job_does_not_ask_when_nothing_is_unsaved(window):
    state = window.state
    state.new_job("clean-job")
    asked = []
    window.discard_confirmer = lambda parent: (asked.append(parent), False)[1]
    assert window.new_job() is True
    assert asked == []
    assert state.configuration.metadata.name == "Untitled job 1"


def test_closing_asks_about_unsaved_changes_and_cancel_keeps_the_window(window):
    state = _make_dirty(window.state)
    window.show()
    window.discard_confirmer = lambda parent: False
    assert window.close() is False
    assert window.isVisible()
    assert state.is_dirty
    window.discard_confirmer = lambda parent: True
    assert window.close() is True
    assert not window.isVisible()


def test_opening_prompts_before_replacing_unsaved_changes(window, tmp_path, monkeypatch):
    state = _make_dirty(window.state)
    path = _write_job(tmp_path / "other.json", "other-job")
    monkeypatch.setattr(
        ImportPreviewDialog, "exec", lambda self: ImportPreviewDialog.Accepted
    )
    before_project = state.project
    window.discard_confirmer = lambda parent: False
    assert window.offer_import(path) is False
    assert state.project is before_project
    assert state.configuration.metadata.name == "edited after the save"
    window.discard_confirmer = lambda parent: True
    assert window.offer_import(path) is True
    assert state.configuration.metadata.name == "other-job"
    assert state.source_path == path


# -- Job Settings -------------------------------------------------------------


def test_settings_show_the_values_in_use_and_name_the_defaults(window):
    state = window.state
    state.new_job()
    page = window.settings_page
    assert page.name_edit.text() == "Untitled job 1"
    assert page.name_state.text() == _text("gui.settings_default")
    assert page.seeds_edit.text() == "1"
    assert page.seeds_state.text() == _text("gui.settings_default")
    assert page.version_combo.currentData() == 3
    assert page.version_state.text() == "%s · %s" % (
        _text("menu.version_pinned") % 3,
        _text("gui.settings_default"),
    )
    page.name_edit.setText("my job")
    page.name_apply.click()
    assert state.configuration.metadata.name == "my job"
    assert page.name_state.text() == _text("gui.settings_custom")


def test_setting_applies_go_through_configuration_service(window, monkeypatch):
    state = window.state
    state.new_job("settings-job")
    seen = []
    real_set_name = state.services.configuration.set_name
    real_set_seeds = state.services.configuration.set_seeds
    real_set_target = state.services.configuration.set_format_target

    def spy_set_name(name):
        seen.append(("name", name))
        return real_set_name(name)

    def spy_set_seeds(seeds):
        seen.append(("seeds", seeds))
        return real_set_seeds(seeds)

    def spy_set_target(version=None, dialect="STANDALONE_AF3", evidence=None):
        seen.append(("version", version))
        return real_set_target(version=version, dialect=dialect, evidence=evidence)

    monkeypatch.setattr(state.services.configuration, "set_name", spy_set_name)
    monkeypatch.setattr(state.services.configuration, "set_seeds", spy_set_seeds)
    monkeypatch.setattr(state.services.configuration, "set_format_target", spy_set_target)

    page = window.settings_page
    page.name_edit.setText("renamed job")
    page.name_apply.click()
    page.seeds_edit.setText("7, 8")
    page.seeds_apply.click()
    page.version_combo.setCurrentIndex(page.version_combo.findData(4))
    page.version_apply.click()

    assert seen == [("name", "renamed job"), ("seeds", "7, 8"), ("version", 4)]
    assert state.configuration.metadata.name == "renamed job"
    assert tuple(state.configuration.seeds.values) == (7, 8)
    assert state.configuration.format_target.version_selection.version == 4
    assert state.is_dirty


def test_a_refused_setting_keeps_the_service_value_and_reports_it(window):
    state = window.state
    state.new_job("settings-job")
    page = window.settings_page
    page.name_edit.setText("   ")
    assert page.apply_name() is False
    assert state.configuration.metadata.name == "settings-job"
    assert page.name_edit.text() == "settings-job"
    assert window.last_problem_text()


# -- Save JSON ----------------------------------------------------------------


def test_save_needs_an_open_job(window):
    assert window.save_json() is False
    assert window.last_problem_text() == _text("menu.no_project")


def test_the_save_dialog_defaults_to_the_current_file(reviewed, tmp_path):
    window = reviewed
    destination = tmp_path / "default-name.json"
    seen = []

    def remember(parent, default):
        seen.append(default)
        return str(destination), True

    window.save_path_chooser = remember
    # No file is open yet: the service's own job name supplies the default.
    assert window.save_json() is True
    assert seen == [window.state.suggested_file_name()]
    seen.clear()
    assert window.save_json() is True  # identical bytes at the same path
    # Now the current file is the default.
    assert seen == [str(destination)]


def test_save_is_refused_for_an_incomplete_job_and_shows_the_findings(window, tmp_path):
    state = window.state
    state.new_job()
    destination = tmp_path / "never.json"
    _choose(window, destination)
    assert window.save_json() is False
    assert not destination.exists()
    assert state.source_path == ""
    # The refusal explains itself on the attempt, with the catalogue's own
    # wording — no permanent findings list is needed for that.
    message = window.last_problem_text()
    assert message.startswith(_text("gui.blocked_header_one"))
    assert len(message.splitlines()) > 1
    assert not hasattr(window.overview_page, "findings_model")


def test_a_valid_job_saves_through_plan_save_and_execute(reviewed, tmp_path, monkeypatch):
    window = reviewed
    destination = tmp_path / "job with spaces.json"
    _choose(window, destination)
    generation = window.state.services.generation
    recorded = {}
    real_plan = generation.plan_save

    def plan_spy(path, name=None, overwrite=False):
        recorded["arguments"] = (path, name, overwrite)
        plan = real_plan(path, name=name, overwrite=overwrite)
        recorded["plan"] = plan
        return plan

    real_execute = generation.execute

    def execute_spy(plan):
        recorded["executed"] = plan
        return real_execute(plan)

    monkeypatch.setattr(generation, "plan_save", plan_spy)
    monkeypatch.setattr(generation, "execute", execute_spy)

    assert window.save_json() is True
    assert recorded["arguments"] == (str(destination), None, False)
    assert recorded["executed"] is recorded["plan"]
    # The bytes on disk are exactly the reviewed plan's payload — the
    # serializer's output, not a second rendering of it.
    assert destination.read_bytes() == recorded["plan"].reviewed.entries[0].payload
    assert window.state.source_path == str(destination)
    assert window.state.is_dirty is False
    assert window.statusBar().currentMessage() == _text("menu.save_job_wrote") % str(
        destination
    )


def test_a_saved_file_reopens_through_the_import_preview_and_commit(reviewed, tmp_path):
    window = reviewed
    destination = tmp_path / "roundtrip.json"
    _choose(window, destination)
    assert window.save_json() is True
    state = window.state
    saved_name = state.configuration.metadata.name
    saved_ids = [record.ids.primary.value for record in state.configuration.records]

    state.new_job()
    assert state.preview_import(str(destination)).ok
    assert state.commit_import(str(destination)).ok
    assert state.configuration.metadata.name == saved_name
    assert [record.ids.primary.value for record in state.configuration.records] == saved_ids


def test_overwrite_is_confirmed_before_an_existing_file_is_replaced(
    reviewed, tmp_path, monkeypatch
):
    window = reviewed
    destination = tmp_path / "existing.json"
    destination.write_text("stale content", encoding="utf-8")
    _choose(window, destination)
    asked = []
    window.overwrite_confirmer = lambda parent, path: (asked.append(path), False)[1]
    assert window.save_json() is False
    assert asked == [str(destination)]
    assert destination.read_text(encoding="utf-8") == "stale content"
    assert window.statusBar().currentMessage() == _text("menu.save_cancelled")

    generation = window.state.services.generation
    overwrite_seen = {}
    real_plan = generation.plan_save

    def plan_spy(path, name=None, overwrite=False):
        overwrite_seen["overwrite"] = overwrite
        return real_plan(path, name=name, overwrite=overwrite)

    monkeypatch.setattr(generation, "plan_save", plan_spy)
    window.overwrite_confirmer = lambda parent, path: True
    assert window.save_json() is True
    assert overwrite_seen["overwrite"] is True
    assert destination.read_text(encoding="utf-8") != "stale content"


def test_save_cancelled_at_the_dialog_writes_nothing(reviewed, tmp_path):
    window = reviewed
    window.save_path_chooser = lambda parent, default: ("", False)
    assert window.save_json() is False
    assert list(tmp_path.iterdir()) == []
    assert window.statusBar().currentMessage() == _text("menu.save_cancelled")
    assert window.last_problem_text() == ""


def test_a_failed_save_reports_the_service_error_and_keeps_the_job_unsaved(
    reviewed, tmp_path
):
    window = reviewed
    state = window.state
    state.mark_saved()
    state.services.configuration.set_name("edited but not saved")
    assert state.is_dirty
    blocker = tmp_path / "out"
    blocker.write_text("not a directory", encoding="utf-8")
    _choose(window, blocker / "child.json")
    assert window.save_json() is False
    assert blocker.read_text(encoding="utf-8") == "not a directory"
    assert window.last_problem_text()
    assert state.is_dirty is True
    assert state.source_path == ""


def test_saving_the_same_bytes_to_the_same_path_is_reported_and_marks_saved(
    reviewed, tmp_path
):
    """A second save onto identical content follows the policy table's own action."""
    window = reviewed
    destination = tmp_path / "same.json"
    _choose(window, destination)
    assert window.save_json() is True
    window.state.services.configuration.set_name("edited again")
    assert window.state.is_dirty
    assert window.save_json() is True
    assert window.state.is_dirty is False
