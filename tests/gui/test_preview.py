"""The JSON pane shows exactly what ``GenerationService.show_json`` returns.

That is the whole point of the stage: the window must never format JSON
itself, and it must show the service's refusal reason when there is no
document to show.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.windows import MainWindow  # noqa: E402


def test_the_preview_equals_the_service_text(reviewed, filled):
    expected, reason = filled.preview_json(None)
    assert reason is None
    assert reviewed.preview_page.editor.toPlainText() == expected


def test_the_preview_is_the_document_the_builder_would_write(reviewed, filled):
    text = reviewed.preview_page.editor.toPlainText()
    document = json.loads(text)
    # The builder's own key order, and its own field values.
    assert list(document) == ["name", "modelSeeds", "sequences", "dialect", "version"]
    assert document["dialect"] == "alphafold3"
    assert document["version"] == 3
    assert document["name"] == "gui-fixture-job"
    assert len(document["sequences"]) == len(filled.configuration.records)


def test_the_editor_is_read_only(reviewed):
    assert reviewed.preview_page.editor.isReadOnly()


def test_a_refused_preview_shows_the_reason_and_writes_nothing(qapp, state):
    """A feature above the pinned version is a refusal, not a crash."""
    state.services.projects.new("too-new")
    state.services.configuration.add_record(
        "protein", "ACDEFGHIKLMNPQRSTVWY", description="chain header"
    )
    main_window = MainWindow(state)

    text, reason = state.preview_json(None)
    assert text is None
    assert reason
    assert main_window.preview_page.editor.toPlainText() == ""
    assert _text("gui.preview_unavailable") in main_window.preview_page.reason_text()
    assert reason in main_window.preview_page.reason_text()
    main_window.close()


def test_refreshing_the_preview_follows_the_service(reviewed, filled):
    """The button re-asks the service; it does not cache or reformat."""
    first = reviewed.preview_page.editor.toPlainText()
    filled.services.configuration.set_name("renamed-job")
    reviewed.preview_page.refresh()
    second = reviewed.preview_page.editor.toPlainText()
    assert second != first
    assert json.loads(second)["name"] == "renamed-job"
    assert second == filled.preview_json(None)[0]
