"""Opening a file: preview first, commit only on an explicit Import.

The dialog is a real modal window, so the tests stand in for the human click
by replacing ``ImportPreviewDialog.exec`` on the class with a fixed answer.
Everything else — the service preview, the dialog's construction from that
preview, and the commit — is the production path.

The source file is checked before and after: previewing and importing must
never modify it.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QLabel  # noqa: E402

from configbuilder.ui.present.strings import blocking_verdict  # noqa: E402
from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.dialogs import ImportPreviewDialog  # noqa: E402

VALID_DOCUMENT = {
    "name": "gui-probe",
    "modelSeeds": [1, 2],
    "sequences": [
        {"protein": {"id": "A", "sequence": "ACDEFGHIKLMNPQRSTVWY"}},
        {"dna": {"id": "B", "sequence": "ATGC"}},
    ],
    "dialect": "alphafold3",
    "version": 3,
}


def _write(path, document):
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return str(path)


@pytest.fixture
def valid_json(tmp_path):
    return _write(tmp_path / "valid.json", VALID_DOCUMENT)


@pytest.fixture
def broken_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ this is not json", encoding="utf-8")
    return str(path)


def test_a_preview_alone_does_not_touch_the_open_job(filled, valid_json):
    """``preview_import`` reads the file and changes nothing in memory."""
    before = filled.configuration
    preview = filled.preview_import(valid_json)
    assert preview.ok
    assert filled.configuration is before


def test_the_preview_reports_what_the_file_contains(valid_json):
    from configbuilder.ui.render.qt.state import GuiState
    from configbuilder.ui.services import build_services

    state = GuiState(build_services())
    preview = state.preview_import(valid_json)
    assert preview.ok
    assert preview.summary["job_name"] == "gui-probe"
    assert preview.summary["seed_values"] == [1, 2]
    assert preview.summary["entity_count"] == 2
    assert preview.summary["record_ids"] == ["A", "B"]


def test_the_dialog_shows_the_summary_and_the_not_modified_notice(
    qapp, valid_json
):
    from configbuilder.ui.present.strings import text as _text
    from configbuilder.ui.render.qt.state import GuiState
    from configbuilder.ui.services import build_services

    state = GuiState(build_services())
    preview = state.preview_import(valid_json)
    dialog = ImportPreviewDialog(None, valid_json, preview)
    shown = "\n".join(
        widget.text()
        for widget in list(dialog.findChildren(QLabel))
        + list(dialog.findChildren(QAbstractButton))
    )
    assert _text("menu.import_untouched") in shown
    assert _text("menu.import_confirm") in shown
    assert "gui-probe" in shown
    assert _text("gui.import_accept") in shown
    assert _text("menu.import_no") in shown
    dialog.reject()
    assert dialog.result() == ImportPreviewDialog.Rejected


def test_the_dialog_buttons_carry_the_accept_and_reject_roles(qapp, valid_json):
    """What the window's flow relies on: Import accepts, Cancel does not.

    The other dialog tests stand in for the click by patching ``exec``; this
    one presses the real buttons, so a button wired to the wrong role would
    fail here rather than in a user's hands.
    """
    from configbuilder.ui.present.strings import text as _text
    from configbuilder.ui.render.qt.state import GuiState
    from configbuilder.ui.services import build_services

    preview = GuiState(build_services()).preview_import(valid_json)
    dialog = ImportPreviewDialog(None, valid_json, preview)
    buttons = {button.text(): button for button in dialog.findChildren(QAbstractButton)}
    buttons[_text("menu.import_no")].click()
    assert dialog.result() == ImportPreviewDialog.Rejected
    buttons[_text("gui.import_accept")].click()
    assert dialog.result() == ImportPreviewDialog.Accepted


def test_the_real_modal_dialog_commits_when_import_is_clicked(
    window, filled, valid_json, monkeypatch
):
    """The whole path with the real dialog: shown modally, then clicked.

    ``offer_import`` opens the dialog with the ordinary modal ``exec``; a
    zero-delay timer presses its Import button, exactly as a user would, so
    the modal loop itself is exercised rather than stepped over. The watchdog
    below rejects the dialog if the click never arrives, so a broken button
    fails this test instead of hanging the suite.
    """
    import configbuilder.ui.render.qt.dialogs.import_preview as dialog_module

    original_exec = dialog_module.ImportPreviewDialog.exec
    clicked = []

    def exec_with_a_click(dialog):
        def press():
            for button in dialog.findChildren(QAbstractButton):
                if button.text() == _text("gui.import_accept"):
                    clicked.append(button.text())
                    button.click()
                    return

        QTimer.singleShot(0, press)
        QTimer.singleShot(2000, dialog.reject)
        return original_exec(dialog)

    monkeypatch.setattr(ImportPreviewDialog, "exec", exec_with_a_click)
    assert window.offer_import(valid_json) is True
    assert clicked == [_text("gui.import_accept")]
    assert filled.source_path == valid_json
    assert filled.configuration.metadata.name == "gui-probe"


def test_a_cancelled_preview_leaves_the_open_job_alone(
    window, filled, valid_json, monkeypatch
):
    before = filled.configuration
    monkeypatch.setattr(
        ImportPreviewDialog, "exec", lambda self: ImportPreviewDialog.Rejected
    )
    assert window.offer_import(valid_json) is False
    assert filled.project.configuration is before
    assert filled.source_path == ""


def test_confirming_the_preview_imports_the_file(window, filled, valid_json, monkeypatch):
    monkeypatch.setattr(
        ImportPreviewDialog, "exec", lambda self: ImportPreviewDialog.Accepted
    )
    assert window.offer_import(valid_json) is True
    assert filled.configuration.metadata.name == "gui-probe"
    assert filled.source_path == valid_json
    # The document holds one DNA strand, so the import holds one: the service
    # does not invent a duplex partner while reading a file. (A strand added
    # through ``add_record`` does get its partner — that is the service's own
    # behaviour, and this stage neither copies nor changes it.)
    assert [record.ids.primary.value for record in filled.configuration.records] == [
        "A",
        "B",
    ]
    assert window.entities_page.model.row_for_record_key("B") == 1


def test_invalid_json_is_refused_without_replacing_the_open_job(
    window, filled, broken_json
):
    before = filled.configuration
    assert window.offer_import(broken_json) is False
    assert filled.project.configuration is before
    assert filled.source_path == ""
    # The service's own reason is what the user is told — no traceback.
    assert window.last_failure_text()


def test_a_missing_file_is_refused_without_replacing_the_open_job(window, filled, tmp_path):
    before = filled.configuration
    assert window.offer_import(str(tmp_path / "nope.json")) is False
    assert filled.project.configuration is before
    assert "nope.json" in window.last_failure_text()


def test_reading_a_file_never_modifies_it(window, filled, valid_json, monkeypatch):
    from pathlib import Path

    path = Path(valid_json)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    monkeypatch.setattr(
        ImportPreviewDialog, "exec", lambda self: ImportPreviewDialog.Accepted
    )
    assert window.offer_import(valid_json) is True
    after = (path.read_bytes(), path.stat().st_mtime_ns)
    assert after == before


def test_committing_makes_every_page_read_the_new_job(window, filled, valid_json, monkeypatch):
    from configbuilder.ui.present.strings import text as _text

    monkeypatch.setattr(
        ImportPreviewDialog, "exec", lambda self: ImportPreviewDialog.Accepted
    )
    window.offer_import(valid_json)
    records = filled.configuration.records
    assert window.entities_page.model.rowCount() == len(records)
    assert window.preview_page.editor.toPlainText().startswith("{")
    assert window.overview_page.verdict_text() in (
        _text("gui.readiness_ok"),
        blocking_verdict(len(filled.status().blocking)),
    )
