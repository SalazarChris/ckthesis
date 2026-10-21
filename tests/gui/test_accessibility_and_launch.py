"""Launch, minimum-size, keyboard and accessible-name checks.

These are the checks the earlier GUI suites did not make:

- the **supported launcher** really starts the window under its own event
  loop and returns cleanly, for ``--demo`` and for a JSON path containing
  spaces (the child is given a site hook that closes the event loop, so no
  person has to click anything);
- every destination still fits at the window's minimum 940x640 size;
- Tab moves through visible controls only — in particular it never reaches
  the retired JSON preview page;
- the important fields and actions expose accessible names, and the form
  dialogs keep Escape as a safe cancel.

The launch tests run real subprocesses in the GUI environment. The rest use
the ordinary offscreen ``window``/``reviewed`` fixtures.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtCore import QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QScrollArea,
)

from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.qt.dialogs import SequenceFormDialog

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "gui.py"

#: Closes the real event loop after the window has had time to appear. The
#: site hook runs before ``gui.py`` does, exactly as the GUI environment does.
_SITE_HOOK = textwrap.dedent(
    '''
    import json
    import os
    import sys

    # gui.py runs first and then starts the real GUI interpreter. Both load
    # this hook; only the child may touch the shared log files (Windows locks
    # them, and a failure here would leave the child without the auto-close).
    _launcher = os.path.basename(sys.argv[0]) == "gui.py"

    _argv_log = os.environ.get("AF3_QA_ARGV_LOG")
    if _argv_log and not _launcher:
        with open(_argv_log, "w", encoding="utf-8") as handle:
            json.dump(sys.argv[1:], handle)

    if os.environ.get("AF3_QA_AUTOCLOSE") == "1" and not _launcher:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialog

        # A path argument opens the import-preview dialog *before* the main
        # event loop starts, so the dialog must dismiss itself; a timer
        # scheduled only around QApplication.exec would never fire.
        _original_dialog_exec = QDialog.exec

        def _dialog_exec_then_reject(self):
            QTimer.singleShot(150, self.reject)
            return _original_dialog_exec(self)

        QDialog.exec = _dialog_exec_then_reject

        _original_exec = QApplication.exec

        def _exec_then_close(self):
            QTimer.singleShot(700, QApplication.quit)
            status = _original_exec()
            _windows_log = os.environ.get("AF3_QA_WINDOW_LOG")
            if _windows_log:
                with open(_windows_log, "w", encoding="utf-8") as handle:
                    json.dump(
                        [window.windowTitle() for window in QApplication.topLevelWidgets()],
                        handle,
                    )
            return status

        QApplication.exec = _exec_then_close
    '''
)


def _launch(arguments, tmp_path, extra_environment=None):
    """Run the supported launcher with the window's event loop auto-closing."""
    (tmp_path / "sitecustomize.py").write_text(_SITE_HOOK, encoding="utf-8")
    argv_log = tmp_path / "argv.json"
    window_log = tmp_path / "windows.json"
    environment = dict(os.environ)
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "PYTHONPATH": str(tmp_path),
            "AF3_QA_AUTOCLOSE": "1",
            "AF3_QA_ARGV_LOG": str(argv_log),
            "AF3_QA_WINDOW_LOG": str(window_log),
        }
    )
    environment.update(extra_environment or {})
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), *arguments],
        cwd=str(ROOT),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    argv = json.loads(argv_log.read_text(encoding="utf-8")) if argv_log.exists() else None
    windows = (
        json.loads(window_log.read_text(encoding="utf-8"))
        if window_log.exists()
        else []
    )
    return result, argv, windows


# -- the supported launcher --------------------------------------------------


def test_the_launcher_starts_the_demo_window_and_returns_cleanly(tmp_path):
    result, argv, windows = _launch(["--demo"], tmp_path)

    assert result.returncode == 0, result.stderr
    assert argv == ["--demo"]  # the launcher forwarded the option unchanged
    assert any("AF3 JSON Builder" in title for title in windows)
    assert "Traceback" not in result.stdout + result.stderr


@pytest.mark.parametrize("scale", ["1.25", "1.5"])
def test_the_launcher_starts_under_a_scaled_dpi(tmp_path, scale):
    """Supplemental only: DPI behaviour itself still needs a human check."""
    result, argv, windows = _launch(
        ["--demo"], tmp_path, {"QT_SCALE_FACTOR": scale}
    )

    assert result.returncode == 0, result.stderr
    assert argv == ["--demo"]
    assert any("AF3 JSON Builder" in title for title in windows)
    assert "Traceback" not in result.stdout + result.stderr


def test_a_json_path_with_spaces_reaches_the_window_as_one_argument(tmp_path):
    folder = tmp_path / "a folder with spaces"
    folder.mkdir()
    path = folder / "a job with spaces.json"
    path.write_text(
        json.dumps(
            {
                "name": "spaced",
                "modelSeeds": [1],
                "sequences": [{"protein": {"id": "A", "sequence": "ACDEFGHIK"}}],
                "dialect": "alphafold3",
                "version": 3,
            }
        ),
        encoding="utf-8",
    )

    result, argv, windows = _launch([str(path)], tmp_path)

    assert result.returncode == 0, result.stderr
    assert argv == [str(path)]  # still one element, not split on the spaces
    assert any("AF3 JSON Builder" in title for title in windows)
    assert "Traceback" not in result.stdout + result.stderr
    # The import preview is modal; the hook rejected it, but the window it
    # belongs to was created, so this proves the path reached the real window.


# -- the minimum window ------------------------------------------------------


def test_every_destination_fits_at_the_minimum_and_normal_sizes(reviewed, qapp):
    window = reviewed
    window.show()
    qapp.processEvents()

    assert window.minimumSize() == QSize(940, 640)
    for width, height in ((940, 640), (1200, 760)):
        window.resize(width, height)
        qapp.processEvents()
        assert window.size() == QSize(width, height)
        stack = window._stack
        assert stack.width() > 400 and stack.height() > 300

        for row in range(4):
            window._sidebar.setCurrentRow(row)
            qapp.processEvents()
            page = window.current_page()
            assert page.isVisibleTo(window), (width, row)
            assert page.width() <= stack.width(), (width, row)
            assert page.height() <= stack.height(), (width, row)

    # The Overview's long form scrolls vertically rather than widening.
    window.resize(940, 640)
    window._sidebar.setCurrentRow(0)
    qapp.processEvents()
    scroll = window.overview_page.findChild(QScrollArea)
    assert scroll is not None
    assert not scroll.horizontalScrollBar().isVisible()
    assert window.overview_page.job_settings.name_edit.width() >= 150

    window.close()


# -- keyboard focus ----------------------------------------------------------


def test_tab_reaches_visible_controls_and_never_the_retired_preview(reviewed, qapp):
    window = reviewed
    window.resize(940, 640)
    window.show()
    qapp.processEvents()

    assert not window._preview.isVisible()
    assert window._preview.findChild(QPlainTextEdit) is not None

    window.overview_page.job_settings.name_edit.setFocus()
    qapp.processEvents()
    seen = []
    for _ in range(14):
        focused = qapp.focusWidget()
        assert focused is not None
        assert focused.isVisibleTo(window)
        assert not window._preview.isAncestorOf(focused)
        seen.append(focused)
        QTest.keyClick(focused, Qt.Key_Tab)
        qapp.processEvents()

    assert len(set(seen)) >= 8
    assert window._file_buttons[2] in seen  # the Save action is reachable
    window.close()


def test_the_sidebar_has_a_real_focus_target(reviewed, qapp):
    window = reviewed
    window.show()
    qapp.processEvents()
    window._sidebar.setFocus()
    qapp.processEvents()

    assert qapp.focusWidget() is window._sidebar
    window.close()


# -- accessible names and safe dialog defaults -------------------------------


def test_the_important_fields_and_actions_expose_accessible_names(reviewed):
    window = reviewed
    settings = window.overview_page.job_settings

    assert settings.name_edit.accessibleName() == _text("gui.field_job_name")
    assert settings.seeds_edit.accessibleName() == _text("gui.field_seeds")
    assert settings.version_combo.accessibleName() == _text("gui.field_version")
    assert window._entities.selector.accessibleName() == _text("gui.entity_selector")

    for button in window._file_buttons:
        assert button.accessibleName() == button.toolTip()
        assert button.accessibleName()

    output = window.output_page
    assert output.destination.accessibleName() == _text("gui.output_destination")
    assert output.overwrite_policy.accessibleName() == _text(
        "gui.output_overwrite_policy"
    )
    assert output.path_policy.accessibleName() == _text("gui.output_path_policy")


def test_visible_buttons_all_carry_text_or_an_accessible_name(reviewed, qapp):
    window = reviewed
    window.show()
    qapp.processEvents()

    nameless = [
        type(button).__name__
        for button in window.findChildren(QAbstractButton)
        if button.isVisibleTo(window)
        and not button.text().strip()
        and not button.accessibleName().strip()
    ]
    assert nameless == []
    window.close()


def test_the_generate_intro_names_the_visible_save_route(reviewed):
    """The menu bar is hidden, so pointing at a "File menu" is a dead end."""
    intro = _text("gui.output_intro")

    assert "FILE footer" in intro
    assert "File menu" not in intro


def test_a_form_dialog_keeps_escape_as_a_safe_cancel(qapp):
    dialog = SequenceFormDialog(
        None,
        "Add a protein",
        "Add",
        lambda sequence, description: None,
        sequence="ACDEFGHIK",
    )
    cancel = dialog.cancel_button
    assert dialog._buttons.buttonRole(cancel) == QDialogButtonBox.RejectRole
    assert cancel.text() == _text("gui.form_cancel")

    dialog.show()
    qapp.processEvents()
    QTest.keyClick(dialog, Qt.Key_Escape)
    qapp.processEvents()

    assert dialog.result() == QDialog.Rejected
