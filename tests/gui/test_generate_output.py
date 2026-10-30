"""The Generate page and the footer's one-click write, through real widgets.

Each test builds the job through the services, presses the page's own action
and then asserts on the files the existing pipeline actually wrote (or refused
to write). A test that only read a label would not prove that planning and
execution stayed in the application layer, or that a refusal left the disk
untouched.

The contract these tests pin:

- **Save job is one click.** No preview, no confirmation for a new file.
- **The only question is a replacement** — an existing file holding different
  bytes — and cancelling it writes nothing.
- **Identical bytes are not "a replacement"**: rewriting the same file is
  silent, because nothing changes.
- **A refusal writes nothing** and shows the service's own message.
- **Save to folder in the FILE footer** writes the same file without a save
  dialog, so the page never has to be visited.

The page writes the **open job's own file** — one JSON, no manifest, and no
choice of scope: a file of ligands is generated from the Entities page, not
here.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from configbuilder.ui.present.strings import text as _text  # noqa: E402

PROJECT = "output-job"
SLUG = "output-job"


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def outputs(window):
    """A valid base job shown by the window."""
    state = window.state
    state.new_job(PROJECT)
    assert state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    window.refresh()
    return window


@pytest.fixture
def blocked(window):
    """A base whose protein carries a modification at a position it lacks."""
    state = window.state
    state.new_job(PROJECT)
    assert state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    assert state.add_modification("A", "SEP", 99).ok
    window.refresh()
    return window


def _page(value):
    return value.output_page


def _select(combo, value):
    index = combo.findData(value)
    assert index >= 0, "no choice %r in %r" % (value, combo.count())
    combo.setCurrentIndex(index)


def _base_path(root):
    return os.path.join(str(root), SLUG, SLUG + ".json")


def _entries(page):
    return page.entries()


def _destinations(window):
    """The sidebar's destination labels, in order."""
    return window.sidebar_labels()


def _recorder():
    """A replacement confirmer that records its question and answers yes."""
    asked = []

    def confirm(_parent, message):
        asked.append(message)
        return True

    return asked, confirm


# -- the page as it opens ----------------------------------------------------


def test_the_page_offers_one_click_without_a_plan(outputs):
    window = outputs
    assert _text("gui.tab_output") in _destinations(window)
    assert window.current_page() is not _page(window)
    page = _page(window)
    assert page.plan_note_text() == _text("gui.output_plan_empty")
    # The action is available the moment a job is open: no preview first.
    assert page.generate_button.isEnabled()
    assert PROJECT in page._base_label.text()


def test_the_page_names_the_exact_file_before_the_click(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))

    assert page.destination_file() == _base_path(tmp_path)
    assert _base_path(tmp_path) in page.write_label.text()

    page.destination.setText("")
    assert page.destination_file() == ""
    assert page.write_label.text() == _text("gui.output_will_write_none")
    assert not page.generate_button.isEnabled()


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


def test_preview_still_exists_and_writes_nothing(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))

    assert page.preview_plan() is True

    rows = _entries(page)
    assert len(rows) == 1
    assert rows[0][0] == _text("gui.output_kind_base")
    assert rows[0][2] == _base_path(tmp_path)
    assert rows[0][3] == _text("gui.output_action_create")
    assert list(tmp_path.iterdir()) == []
    assert "nothing has been written" in page.plan_note_text()


def test_an_empty_destination_is_refused_without_planning(outputs):
    page = _page(outputs)
    page.destination.setText("")

    assert page.preview_plan() is False
    assert outputs.last_problem_text() == _text("gui.output_no_folder")
    assert page.generate() is False
    assert outputs.last_problem_text() == _text("gui.output_no_folder")


# -- one click ---------------------------------------------------------------


def test_save_writes_the_file_without_asking_anything(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    asked, page.replacement_confirmer = _recorder()

    assert page.generate() is True

    assert asked == []  # a new file is not a destructive act
    assert os.path.isfile(_base_path(tmp_path))
    with open(_base_path(tmp_path), encoding="utf-8") as handle:
        document = json.load(handle)
    assert document["name"] == SLUG
    assert any(
        entry["protein"]["sequence"] == "ACDEFGHIKLMNPQRSTVWY"
        for entry in document["sequences"]
        if "protein" in entry
    )
    assert not os.path.exists(os.path.join(str(tmp_path), SLUG, "manifest.json"))
    assert page.result_text().count(str(tmp_path)) >= 1
    assert page.plan_note_text() == _text("gui.output_plan_done")
    assert page.open_folder_button.isEnabled()


def test_a_successful_write_marks_the_job_saved(outputs, tmp_path):
    """Generating the file is what "saved" means, so the header must agree."""
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert outputs.state.is_dirty

    assert page.generate() is True

    assert outputs.state.is_dirty is False
    assert outputs.state.source_path == _base_path(tmp_path)


def test_changing_the_folder_writes_where_the_page_now_says(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path / "first"))
    assert page.preview_plan() is True
    page.destination.setText(str(tmp_path / "second"))

    assert page.generate() is True

    assert os.path.isfile(_base_path(tmp_path / "second"))
    assert not os.path.exists(str(tmp_path / "first"))


def test_changing_a_policy_applies_to_the_next_write(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is True
    _select(page.overwrite_policy, "Versioned")

    assert page.generate() is True
    assert os.path.isfile(_base_path(tmp_path))


def test_renaming_the_job_writes_the_new_file_name(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is True

    assert outputs.state.set_job_name("renamed job").ok

    assert page.generate() is True
    assert os.path.isfile(os.path.join(str(tmp_path), "renamed-job", "renamed-job.json"))


# -- the replacement question ------------------------------------------------


def test_replacing_a_changed_file_asks_once_and_names_it(outputs, tmp_path):
    target = _base_path(tmp_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("old bytes")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    _select(page.overwrite_policy, "Overwrite")
    asked, page.replacement_confirmer = _recorder()

    assert page.generate() is True

    assert len(asked) == 1
    assert target in asked[0]
    with open(target, encoding="utf-8") as handle:
        assert json.load(handle)["name"] == SLUG


def test_cancelling_the_replacement_writes_nothing(outputs, tmp_path):
    target = _base_path(tmp_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("old bytes")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    _select(page.overwrite_policy, "Overwrite")
    page.replacement_confirmer = lambda parent, message: False

    assert page.generate() is False

    with open(target, encoding="utf-8") as handle:
        assert handle.read() == "old bytes"
    assert page.plan_note_text() == _text("gui.output_replace_cancelled")


def test_identical_bytes_are_rewritten_without_a_question(outputs, tmp_path):
    """Writing the same file twice changes nothing, so nothing is asked."""
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.generate() is True
    asked, page.replacement_confirmer = _recorder()

    assert page.generate() is True

    assert asked == []
    with open(_base_path(tmp_path), encoding="utf-8") as handle:
        assert json.load(handle)["name"] == SLUG


# -- policies and conflicts --------------------------------------------------


def test_a_conflicting_file_refuses_the_whole_plan(outputs, tmp_path):
    target = _base_path(tmp_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("not generated")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))

    assert page.generate() is False

    assert page.conflicts_list.count() == 1
    assert target in page.conflicts_list.item(0).text()
    with open(target, encoding="utf-8") as handle:
        assert handle.read() == "not generated"


def test_skip_policy_keeps_the_existing_file_and_reports_it(outputs, tmp_path):
    target = _base_path(tmp_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("keep me")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    _select(page.overwrite_policy, "Skip")
    asked, page.replacement_confirmer = _recorder()

    assert page.generate() is True

    assert asked == []
    with open(target, encoding="utf-8") as handle:
        assert handle.read() == "keep me"
    assert _text("gui.output_skipped") in page.result_text()
    assert target in page.result_text()


def test_versioned_policy_writes_a_numbered_copy(outputs, tmp_path):
    target = _base_path(tmp_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("old bytes")
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    _select(page.overwrite_policy, "Versioned")
    asked, page.replacement_confirmer = _recorder()

    assert page.generate() is True

    assert asked == []
    versioned = os.path.join(os.path.dirname(target), "%s-1.json" % SLUG)
    assert os.path.isfile(versioned)
    with open(target, encoding="utf-8") as handle:
        assert handle.read() == "old bytes"


def test_a_file_created_after_the_preview_is_not_overwritten(outputs, tmp_path):
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    assert page.preview_plan() is True
    target = _base_path(tmp_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("outside change")

    assert page.generate() is False

    assert page.conflicts_list.count() == 1
    with open(target, encoding="utf-8") as handle:
        assert handle.read() == "outside change"


def test_a_plan_that_changes_mid_write_stops_generation(outputs, tmp_path, monkeypatch):
    """The re-plan before ``execute`` refuses bytes the user never saw."""
    page = _page(outputs)
    page.destination.setText(str(tmp_path))
    state = outputs.state
    original = state.plan_generation
    calls = []

    def planning(**kwargs):
        calls.append(kwargs)
        plan = original(**kwargs)
        if len(calls) == 2:
            # The second plan differs: pretend another file appeared after the
            # first, so the reviewed and the current plan disagree.
            plan.entries[0].action = "create"
            plan.entries[0].payload_fingerprint = "different"
        return plan

    monkeypatch.setattr(state, "plan_generation", planning)

    assert page.generate() is False

    assert outputs.last_problem_text() == _text("gui.output_plan_changed")
    assert not os.path.exists(_base_path(tmp_path))


def test_an_unwritable_destination_is_reported_not_raised(outputs, tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("file", encoding="utf-8")
    page = _page(outputs)
    page.destination.setText(str(blocker))

    assert page.generate() is False
    assert outputs.last_problem_text()
    assert _text("gui.output_result_errors") in page.result_text()
    assert blocker.read_text(encoding="utf-8") == "file"


# -- validation --------------------------------------------------------------


def test_a_blocked_base_shows_the_services_findings(outputs, tmp_path):
    state = outputs.state
    state.new_job("empty-job")
    outputs.refresh()
    page = _page(outputs)
    page.destination.setText(str(tmp_path))

    assert page.generate() is False

    assert page.findings_model.rowCount() > 0
    assert page.findings_note.text() == _text("gui.output_findings_note")
    assert page.plan_note_text().startswith(_text("gui.output_plan_refused") % "")
    assert not page.review_button.isHidden()
    assert list(tmp_path.iterdir()) == []


def test_a_finding_selection_jumps_to_its_entity(blocked, tmp_path):
    page = _page(blocked)
    page.destination.setText(str(tmp_path))
    assert page.generate() is False
    assert page.findings_model.rowCount() > 0

    page.findings_view.selectRow(0)

    assert blocked.current_page() is blocked.entities_page


def test_review_configuration_goes_to_overview(blocked, tmp_path):
    page = _page(blocked)
    page.destination.setText(str(tmp_path))
    assert page.generate() is False

    page.review_button.click()

    assert blocked.current_page() is blocked.overview_page


# -- the footer shortcut -----------------------------------------------------


def test_save_to_folder_writes_the_job_without_a_dialog(outputs):
    """The FILE footer's shortcut: no dialog, no page, the same file."""
    window = outputs
    asked = []

    def refuse_dialog(*_args, **_kwargs):
        asked.append(_kwargs)
        return ("", False)

    window.save_path_chooser = refuse_dialog

    assert window.save_to_folder() is True

    assert asked == []  # no save dialog was opened
    page = _page(window)
    target = page.destination_file()
    assert target and os.path.isfile(target)
    assert window.state.source_path == target
    assert window.state.is_dirty is False


def test_save_to_folder_is_disabled_without_a_job(window):
    window.refresh()
    assert not window._save_folder_action.isEnabled()
    assert not window._file_buttons[3].isEnabled()


# -- assets ------------------------------------------------------------------


def test_copied_assets_are_planned_written_and_referenced(outputs, tmp_path):
    msa = tmp_path / "chain-a.a3m"
    msa.write_text(">query\nACDEFG\n", encoding="utf-8")
    state = outputs.state
    assert state.set_alignment("A", "unpaired", external_path=str(msa)).ok
    outputs.refresh()
    page = _page(outputs)
    page.destination.setText(str(tmp_path / "out"))
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
