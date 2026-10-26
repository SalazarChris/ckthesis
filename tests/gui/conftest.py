"""Fixtures for the GUI tests.

Two things matter here:

- **No display is required.** ``QT_QPA_PLATFORM`` is set to ``offscreen``
  before any ``QApplication`` exists, so the tests run in a plain terminal,
  in CI, and on a Windows box with no window open.
- **PySide6 is optional.** A module in this directory skips when the GUI extra
  is missing; the fixture below skips any test that somehow still asks for a
  ``QApplication``.

The state fixtures build their jobs through the ordinary services, the same
way the application does — a test that hand-built a configuration would not be
testing the integration this stage is about.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # the GUI extra is optional; absence must not fail collection
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - exercised only without the extra
    QApplication = None


@pytest.fixture(autouse=True)
def no_modal_boxes(monkeypatch):
    """Never let a test wait for a click.

    A refused file is reported through ``show_failure`` and every other
    refusal through ``show_problem`` — modal message boxes by default — and
    offscreen there is nobody to dismiss them. The Stage 2 questions are
    answered the same way: the discard prompt proceeds, the overwrite prompt
    confirms, and the save chooser cancels (tests that save replace the
    chooser on the window itself). The refusals are still readable through
    ``MainWindow.last_failure_text()`` / ``last_problem_text()``, which is
    what the tests assert on.
    """
    if QApplication is None:
        pytest.skip("the GUI extra (PySide6) is not installed")
    window_module = "configbuilder.ui.render.qt.windows.main_window"
    monkeypatch.setattr(window_module + ".show_failure", lambda parent, message: None)
    monkeypatch.setattr(window_module + ".show_problem", lambda parent, message: None)
    monkeypatch.setattr(window_module + ".confirm_discard", lambda parent: True)
    monkeypatch.setattr(
        window_module + ".confirm_overwrite", lambda parent, path: True
    )
    monkeypatch.setattr(
        window_module + ".ask_save_path", lambda parent, default: ("", False)
    )
    # The entity page's one modal question: answer "yes" by default, so a
    # stray click can never hang the suite; the Stage 3 tests replace this
    # answer with a recorder when they assert on the wording.
    monkeypatch.setattr(
        "configbuilder.ui.render.qt.pages.entities.confirm_entity_delete",
        lambda parent, message: True,
    )
    # The Advanced page's two questions and every Stage 4 form: same reason.
    # A test that drives a form replaces the stub with the real widgets.
    monkeypatch.setattr(
        "configbuilder.ui.render.qt.pages.advanced.confirm_modification_removal",
        lambda parent, message: True,
    )
    monkeypatch.setattr(
        "configbuilder.ui.render.qt.pages.advanced.confirm_bond_removal",
        lambda parent, message: True,
    )
    # The Generate & Output page's one question: answer "yes", so a stray
    # press can never hang; the Stage 6 tests replace it with a recorder.
    monkeypatch.setattr(
        "configbuilder.ui.render.qt.pages.generate.confirm_generation",
        lambda parent, message: True,
    )
    from PySide6.QtWidgets import QDialog

    from configbuilder.ui.render.qt.dialogs import (
        AlignmentFormDialog,
        BondFormDialog,
        LigandFormDialog,
        ModificationFormDialog,
        SequenceFormDialog,
        TemplateEditorDialog,
    )

    for dialog_class in (
        AlignmentFormDialog,
        BondFormDialog,
        LigandFormDialog,
        ModificationFormDialog,
        SequenceFormDialog,
        TemplateEditorDialog,
    ):
        # An un-driven form cancels: it can never wait for a click offscreen.
        monkeypatch.setattr(dialog_class, "exec", lambda self, *a, **k: QDialog.Rejected)


@pytest.fixture(scope="session")
def qapp():
    """The one ``QApplication`` for the whole session."""
    if QApplication is None:
        pytest.skip("the GUI extra (PySide6) is not installed")
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


@pytest.fixture
def state(qapp):
    """Fresh services and a fresh, empty GUI state."""
    from configbuilder.ui.render.qt.state import GuiState
    from configbuilder.ui.services import build_services

    return GuiState(build_services())


@pytest.fixture
def filled(state):
    """A job with one of every family, built through the services.

    Expected identifiers, in the order the configuration holds them:
    ``A`` (protein, with ``SEP`` at residue 4), ``B`` and ``C`` (the DNA
    duplex the service builds from one input strand), ``D`` (a CCD ligand)
    and ``E`` (a SMILES ligand).
    """
    configuration = state.services.configuration
    state.services.projects.new("gui-fixture-job")
    configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")
    configuration.add_record("dna", "ATGC")
    configuration.add_record("ligand", representation="ATP", representation_kind="ccd")
    configuration.add_record("ligand", representation="CCO", representation_kind="smiles")
    configuration.add_modification("A", "SEP", 4)
    return state


@pytest.fixture
def window(qapp, state):
    """The real main window over the empty state; closed after the test."""
    from configbuilder.ui.render.qt.windows import MainWindow

    main_window = MainWindow(state)
    yield main_window
    main_window.close()


@pytest.fixture
def reviewed(window, filled):
    """The window over the built job, refreshed as a committed import does.

    The service layer has no change notification of its own, so a job built
    directly through the services is shown by asking the window to refresh —
    exactly what ``GuiState.project_changed`` does after an import.
    """
    window.refresh()
    return window
