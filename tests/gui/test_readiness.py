"""The readiness view must be the service's answer, not a second opinion.

Each test compares what the window shows with the very same service result,
so a page that started deciding readiness for itself would fail here.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import QTableView  # noqa: E402

from configbuilder.ui.present.strings import blocking_verdict  # noqa: E402
from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.windows import MainWindow  # noqa: E402


def test_readiness_is_one_compact_line_from_the_service(reviewed, filled):
    status = filled.status()
    page = reviewed.overview_page
    assert status.ready
    assert page.verdict_text() == _text("gui.readiness_ok")
    assert page.readiness_state_text() == _text("gui.readiness_ready")
    # The verdict is the service's; the page adds only the summary card.
    assert not page.findChildren(QTableView)


def test_a_ready_job_says_ready(reviewed, filled):
    status = filled.status()
    assert status.ready
    assert reviewed.overview_page.verdict_text() == _text("gui.readiness_ok")


def test_a_blocking_job_says_how_many_findings_block_it(qapp, state):
    """An empty job cannot be generated, and the window says so."""
    state.services.projects.new("empty-job")
    main_window = MainWindow(state)
    status = state.status()
    assert not status.ready
    assert main_window.overview_page.verdict_text() == blocking_verdict(
        len(status.blocking)
    )
    main_window.close()


def test_the_blocking_verdict_is_pluralised():
    assert blocking_verdict(1) == "Not ready: 1 blocking finding."
    assert blocking_verdict(2) == "Not ready: 2 blocking findings."


def test_findings_are_not_persistent_overview_content(reviewed, filled):
    """The catalogue still reports, but Overview no longer carries a list."""
    populated = filled.validate_base().report
    assert populated.findings

    page = reviewed.overview_page
    assert not hasattr(page, "findings_model")
    assert not hasattr(page, "status_model")
    labels = {label.text() for label in page.findChildren(type(page._verdict))}
    assert "Validation findings" not in labels


def test_an_invalid_job_is_still_blocked_and_explained_on_demand(
    reviewed, filled, tmp_path
):
    """An out-of-range PTM is blocking; Save says so with the rule's wording."""
    filled.services.configuration.add_modification("A", "SEP", 999)
    reviewed.refresh()
    report = filled.validate_base().report
    assert "R-ENT-007" in {finding.rule_id for finding in report.blocking()}

    reviewed.save_path_chooser = lambda parent, default: (
        str(tmp_path / "blocked.json"),
        True,
    )
    assert not reviewed.save_json()
    assert not (tmp_path / "blocked.json").exists()
    assert _text("gui.blocked_header_one") in reviewed.last_problem_text()


def test_a_missing_msa_file_blocks_readiness_and_save(reviewed, filled, tmp_path):
    """The external-MSA preflight is the service's rule, not the page's.

    The window's readiness line and its Save both read ``ValidationService``,
    so a configured file that is not there is a blocking finding on the
    Overview and a refusal on the save attempt — the same rule, one wording.
    """
    missing = tmp_path / "absent.a3m"
    assert filled.services.configuration.set_alignment(
        "A", "unpaired", external_path=str(missing)
    ).ok
    reviewed.refresh()

    status = filled.status()
    assert not status.ready
    assert "R-MSA-006" in {finding.rule_id for finding in status.blocking}
    assert reviewed.overview_page.verdict_text() == blocking_verdict(
        len(status.blocking)
    )

    destination = tmp_path / "blocked.json"
    reviewed.save_path_chooser = lambda parent, default: (str(destination), True)
    assert not reviewed.save_json()
    assert not destination.exists()
    assert _text("gui.blocked_header_one") in reviewed.last_problem_text()


def test_the_status_bar_reports_the_imported_file(window, filled, tmp_path, monkeypatch):
    import json

    from configbuilder.ui.render.qt.dialogs import ImportPreviewDialog

    document = {
        "name": "jumped",
        "modelSeeds": [1],
        "sequences": [{"protein": {"id": "A", "sequence": "ACDEFGHIKLMNP"}}],
        "dialect": "alphafold3",
        "version": 3,
    }
    path = tmp_path / "jumped.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(
        ImportPreviewDialog, "exec", lambda self: ImportPreviewDialog.Accepted
    )
    assert window.offer_import(str(path)) is True
    assert window.source_text() == _text("gui.source_file") % str(path)
