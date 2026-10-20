"""Stage 6: the Generate & Output page, driven through its real widgets.

Each test builds the job through the services, previews the page's plan and
then asserts on the files the existing pipeline actually wrote (or refused to
write). A test that only read a label would not prove that planning and
execution stayed in the application layer, that the reviewed plan is the one
executed, or that a refusal left the disk untouched.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import QTabWidget  # noqa: E402

from configbuilder.ui.present.strings import text as _text  # noqa: E402

PROJECT = "output-job"
SLUG = "output-job"


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def outputs(window):
    """A valid base with two spec-based variants, shown by the window."""
    state = window.state
    state.new_job(PROJECT)
    assert state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    assert state.add_spec_with_edit(
        "v1", "Variant one", "sequence", "GGGGS", record_key="A"
    ).ok
    assert state.add_spec_with_edit(
        "v2", "Variant two", "job_name", "second name"
    ).ok
    window.refresh()
    return window


@pytest.fixture
def blocked(window):
    """A base whose only variant carries a blocking PTM position."""
    state = window.state
    state.new_job(PROJECT)
    assert state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    assert state.add_spec_with_edit(
        "bad", "Bad PTM", "add_modification", ("SEP", 99), record_key="A"
    ).ok
    window.refresh()
    return window


def _page(value):
    return value.output_page


def _select(combo, value):
    index = combo.findData(value)
    assert index >= 0, "no choice %r in %r" % (value, combo.count())
    combo.setCurrentIndex(index)


def _variant_dir(root, key):
    return os.path.join(str(root), SLUG, "%s__%s" % (SLUG, key))


def _variant_path(root, key):
    name = "%s__%s" % (SLUG, key)
    return os.path.join(_variant_dir(root, key), name + ".json")


def _manifest_path(root):
    return os.path.join(str(root), SLUG, "manifest.json")


def _base_path(root):
    return os.path.join(str(root), SLUG, SLUG + ".json")


def _entries(page):
    return page.entries()


def _destinations(window):
    """The sidebar's destination labels, in order."""
    return window.sidebar_labels()


# -- the plan surface --------------------------------------------------------


def test_the_output_page_is_reachable_and_starts_without_a_plan(outputs):
    window = outputs
    assert _text("gui.tab_output") in _destinations(window)
    assert window.current_page() is not _page(window)
    page = _page(window)
    assert page.plan_note_text() == _text("gui.output_plan_empty")
    assert not page.generate_button.isEnabled()
    assert PROJECT in page._base_label.text()


def test_the_policy_pickers_offer_exactly_the_services_closed_sets(outputs):
    page = _page(outputs)
    choices = outputs.state.output_policy_choices()
    assert tuple(
        page.overwrite_policy.itemData(index)
        for index in range(page.overwrite_policy.count())
    ) == choices["overwrite"]
    assert tuple(
        page.path_policy.itemData(index)
        for index in range(page.path_policy.count())
    ) == choices["path"]
    defaults = outputs.state.output_defaults()
    assert page.overwrite_policy.currentData() == defaults["overwrite"]
    assert page.path_policy.currentData() == defaults["path"]


def test_preview_shows_the_service_plan_and_writes_nothing(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))

    assert page.preview_plan() is True

    assert page.generate_button.isEnabled()
    rows = _entries(page)
    assert len(rows) == 3
    paths = [row[2] for row in rows]
    assert _variant_path(tmp_path, "v1") in paths
    assert _variant_path(tmp_path, "v2") in paths
    assert _manifest_path(tmp_path) in paths
    kinds = [row[0] for row in rows]
    assert kinds.count(_text("gui.output_kind_variant")) == 2
    assert kinds.count(_text("gui.output_kind_manifest")) == 1
    actions = {row[3] for row in rows}
    assert actions == {_text("gui.output_action_create")}
    assert list(tmp_path.iterdir()) == []
    assert "nothing has been written" in page.plan_note_text()


def test_selected_scope_plans_only_the_chosen_variant(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.choose_scope("selected")
    _select(page.variant_choice, "v1")

    assert page.preview_plan() is True

    rows = _entries(page)
    assert [row[2] for row in rows] == [
        _variant_path(tmp_path, "v1"),
        _manifest_path(tmp_path),
    ]
    assert all("__v2" not in row[2] for row in rows)


def test_selected_scope_without_a_variant_is_refused(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.choose_scope("selected")
    page.variant_choice.setCurrentIndex(-1)

    assert page.preview_plan() is False
    assert outputs.last_problem_text() == _text("gui.output_scope_needs_variant")
    assert list(tmp_path.iterdir()) == []


def test_base_scope_plans_one_file_and_no_manifest(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.choose_scope("base")

    assert page.preview_plan() is True

    rows = _entries(page)
    assert len(rows) == 1
    assert rows[0][0] == _text("gui.output_kind_base")
    assert rows[0][2] == _base_path(tmp_path)
    assert not os.path.exists(_manifest_path(tmp_path))


def test_an_empty_destination_is_refused_without_planning(outputs):
    page = _page(outputs)
    page.destination.setText("")

    assert page.preview_plan() is False
    assert outputs.last_problem_text() == _text("gui.output_no_folder")
    assert not page.generate_button.isEnabled()


def test_generate_needs_a_reviewed_plan(outputs):
    page = _page(outputs)

    assert page.generate() is False
    assert outputs.last_problem_text() == _text("gui.output_need_plan")


# -- execution ---------------------------------------------------------------


def test_generate_writes_the_reviewed_plan_and_the_manifest(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is True
    question = []
    page.generation_confirmer = lambda parent, message: question.append(message) or True

    assert page.generate() is True

    assert question and str(tmp_path) in question[0]
    assert os.path.isfile(_variant_path(tmp_path, "v1"))
    assert os.path.isfile(_variant_path(tmp_path, "v2"))
    assert os.path.isfile(_manifest_path(tmp_path))
    with open(_variant_path(tmp_path, "v1"), encoding="utf-8") as handle:
        variant = json.load(handle)
    assert variant["name"] == "%s__v1" % SLUG
    assert any(
        entry["protein"]["sequence"] == "GGGGS"
        for entry in variant["sequences"]
        if "protein" in entry
    )
    with open(_manifest_path(tmp_path), encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert manifest["project_name"] == PROJECT
    assert [item["key"] for item in manifest["variants"]] == ["v1", "v2"]
    assert manifest["overwrite_policy"] == "Fail"
    assert manifest["path_policy"] == "CopyIntoAssets"
    assert page.result_text().count(str(tmp_path)) >= 3
    assert "Generation finished" in page.plan_note_text()
    assert not page.generate_button.isEnabled()


def test_cancelling_the_confirmation_writes_nothing(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is True
    page.generation_confirmer = lambda parent, message: False

    assert page.generate() is False

    assert list(tmp_path.iterdir()) == []
    assert page.result_text() == ""
    assert page.result_note.text() == _text("gui.output_result_empty")


def test_changing_the_folder_invalidates_the_plan(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path / "first"))
    assert page.preview_plan() is True
    page.destination.setText(str(tmp_path / "second"))

    assert page.generate() is False

    assert outputs.last_problem_text() == _text("gui.output_stale")
    assert page.plan_note_text() == _text("gui.output_stale")
    assert not page.generate_button.isEnabled()
    assert list(tmp_path.iterdir()) == []


def test_changing_a_policy_invalidates_the_plan(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is True
    _select(page.overwrite_policy, "Overwrite")

    assert page.generate() is False
    assert outputs.last_problem_text() == _text("gui.output_stale")
    assert list(tmp_path.iterdir()) == []


def test_a_job_change_invalidates_a_held_plan(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is True

    assert outputs.state.update_spec("v1", label="Renamed").ok

    assert not page.generate_button.isEnabled()
    assert page.plan_note_text() == _text("gui.output_plan_invalidated")
    assert page.generate() is False
    assert list(tmp_path.iterdir()) == []


# -- policies and conflicts --------------------------------------------------


def test_a_conflicting_file_refuses_the_whole_plan(outputs, tmp_path):
    os.makedirs(os.path.dirname(_variant_path(tmp_path, "v1")), exist_ok=True)
    with open(_variant_path(tmp_path, "v1"), "w", encoding="utf-8") as handle:
        handle.write("not generated")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))

    assert page.preview_plan() is False

    assert page.conflicts_list.count() == 1
    assert _variant_path(tmp_path, "v1") in page.conflicts_list.item(0).text()
    assert not page.generate_button.isEnabled()
    with open(_variant_path(tmp_path, "v1"), encoding="utf-8") as handle:
        assert handle.read() == "not generated"
    assert not os.path.exists(_variant_path(tmp_path, "v2"))
    assert not os.path.exists(_manifest_path(tmp_path))


def test_skip_policy_keeps_the_existing_file_and_reports_it(outputs, tmp_path):
    os.makedirs(os.path.dirname(_variant_path(tmp_path, "v1")), exist_ok=True)
    with open(_variant_path(tmp_path, "v1"), "w", encoding="utf-8") as handle:
        handle.write("keep me")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    _select(page.overwrite_policy, "Skip")

    assert page.preview_plan() is True
    rows = {row[2]: row[3] for row in _entries(page)}
    assert rows[_variant_path(tmp_path, "v1")] == _text("gui.output_action_skip")

    assert page.generate() is True
    with open(_variant_path(tmp_path, "v1"), encoding="utf-8") as handle:
        assert handle.read() == "keep me"
    assert os.path.isfile(_variant_path(tmp_path, "v2"))
    assert os.path.isfile(_manifest_path(tmp_path))
    assert _text("gui.output_skipped") in page.result_text()
    assert _variant_path(tmp_path, "v1") in page.result_text()


def test_overwrite_policy_replaces_a_changed_file(outputs, tmp_path):
    os.makedirs(os.path.dirname(_variant_path(tmp_path, "v1")), exist_ok=True)
    with open(_variant_path(tmp_path, "v1"), "w", encoding="utf-8") as handle:
        handle.write("old bytes")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    _select(page.overwrite_policy, "Overwrite")

    assert page.preview_plan() is True
    rows = {row[2]: row[3] for row in _entries(page)}
    assert rows[_variant_path(tmp_path, "v1")] == _text("gui.output_action_overwrite")

    assert page.generate() is True
    with open(_variant_path(tmp_path, "v1"), encoding="utf-8") as handle:
        document = json.load(handle)
    assert document["name"] == "%s__v1" % SLUG


def test_versioned_policy_writes_a_numbered_copy(outputs, tmp_path):
    os.makedirs(os.path.dirname(_variant_path(tmp_path, "v1")), exist_ok=True)
    with open(_variant_path(tmp_path, "v1"), "w", encoding="utf-8") as handle:
        handle.write("old bytes")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    _select(page.overwrite_policy, "Versioned")

    assert page.preview_plan() is True
    paths = [row[2] for row in _entries(page)]
    versioned = os.path.join(
        os.path.dirname(_variant_path(tmp_path, "v1")), "%s__v1-1.json" % SLUG
    )
    assert versioned in paths

    assert page.generate() is True
    assert os.path.isfile(versioned)
    with open(_variant_path(tmp_path, "v1"), encoding="utf-8") as handle:
        assert handle.read() == "old bytes"


def test_a_file_created_after_the_preview_stops_generation(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is True
    os.makedirs(os.path.dirname(_variant_path(tmp_path, "v1")), exist_ok=True)
    with open(_variant_path(tmp_path, "v1"), "w", encoding="utf-8") as handle:
        handle.write("outside change")

    assert page.generate() is False

    assert outputs.last_problem_text() == _text("gui.output_plan_changed")
    assert page.conflicts_list.count() == 1
    assert not page.generate_button.isEnabled()
    with open(_variant_path(tmp_path, "v1"), encoding="utf-8") as handle:
        assert handle.read() == "outside change"
    assert not os.path.exists(_variant_path(tmp_path, "v2"))


def test_an_unwritable_destination_is_reported_not_raised(outputs, tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("file", encoding="utf-8")
    page = _page(outputs)
    page.destination.setText(str(blocker))

    assert page.preview_plan() is True
    page.generation_confirmer = lambda parent, message: True

    assert page.generate() is False
    assert outputs.last_problem_text()
    assert _text("gui.output_result_errors") in page.result_text()
    assert blocker.read_text(encoding="utf-8") == "file"


# -- validation --------------------------------------------------------------


def test_a_blocked_base_shows_the_services_findings(outputs):
    state = outputs.state
    state.new_job("empty-job")
    outputs.refresh()
    page = _page(outputs)
    page.destination.setText(str(os.getcwd()))

    assert page.preview_plan() is False

    assert page.findings_model.rowCount() > 0
    assert page.findings_note.text() == _text("gui.output_findings_note")
    assert page.plan_note_text().startswith(_text("gui.output_plan_refused") % "")
    assert not page.generate_button.isEnabled()
    assert not page.review_button.isHidden()


def test_blocked_variants_show_variant_findings(outputs, tmp_path):
    state = outputs.state
    assert state.add_spec_with_edit(
        "bad", "Bad PTM", "add_modification", ("SEP", 99), record_key="A"
    ).ok
    outputs.refresh()
    page = _page(outputs)
    page.destination.setText(str(tmp_path))

    assert page.preview_plan() is False

    assert page.findings_model.rowCount() > 0
    assert page.findings_note.text() == _text("gui.output_findings_variants")
    assert not page.generate_button.isEnabled()
    assert list(tmp_path.iterdir()) == []


def test_a_finding_selection_jumps_to_its_entity(blocked, tmp_path):
    page = _page(blocked)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is False
    assert page.findings_model.rowCount() > 0

    page.findings_view.selectRow(0)

    assert blocked.current_page() is blocked.entities_page


def test_review_configuration_goes_to_overview(blocked, tmp_path):
    page = _page(blocked)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is False

    page.review_button.click()

    assert blocked.current_page() is blocked.overview_page


# -- assets ------------------------------------------------------------------


def test_copied_assets_are_planned_shown_written_and_referenced(outputs, tmp_path):
    msa = tmp_path / "chain-a.a3m"
    msa.write_text(">query\nACDEFG\n", encoding="utf-8")
    state = outputs.state
    assert state.set_alignment("A", "unpaired", external_path=str(msa)).ok
    outputs.refresh()
    page = _page(outputs)
    page.destination.setText(str(tmp_path / "out"))
    assert page.choose_scope("base")
    _select(page.path_policy, "CopyIntoAssets")

    assert page.preview_plan() is True

    resources = page.resource_rows()
    assert len(resources) == 1
    assert resources[0][0] == "unpairedMsaPath"
    assert resources[0][1] == str(msa)
    assert resources[0][2].endswith("assets" + os.sep + "chain-a.a3m") or resources[
        0
    ][2].endswith("assets/chain-a.a3m")
    assert resources[0][3].replace("\\", "/") == "assets/chain-a.a3m"

    assert page.generate() is True

    with open(_base_path(tmp_path / "out"), encoding="utf-8") as handle:
        document = json.load(handle)
    protein = next(
        entry["protein"] for entry in document["sequences"] if "protein" in entry
    )
    assert protein["unpairedMsaPath"] == "assets/chain-a.a3m"
    copied = os.path.join(str(tmp_path / "out"), SLUG, "assets", "chain-a.a3m")
    assert os.path.isfile(copied)
    assert page.result_text().count("chain-a.a3m") >= 2
