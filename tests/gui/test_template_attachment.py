"""Structural templates through the real desktop widgets and the real writer.

The three committed fixtures in ``manual_test_data/af3_builder/templates`` are
driven here the way a user drives them: the protein entity is created through
the service, the **real** ``TemplateEditorDialog`` is opened by the Advanced
page, its file picker is answered with the fixture path, its pairs cell is
filled, and the dialog is accepted — which calls the service through the page,
exactly as a click does. The job is then saved through the window's own
``save_json`` and the JSON on disk is read back.

Pinned here:

- fixture A (six resolved residues) serialises ``queryIndices`` 0-5 and
  ``templateIndices`` 0-5;
- fixture B (full polymer ACQDEFG, coordinates only for DEFG) serialises
  ``queryIndices`` 0-3 with ``templateIndices`` **3-6**, not 0-3;
- both arrays are the same length and pair up residue by residue;
- the template file is copied beside the JSON and referenced relatively, and
  reopening that saved job keeps the mapping (import resolves the relative
  path against the file's own folder);
- the empty fixture is refused by the service, the dialog stays open with the
  service's own message, and the job keeps its previous template state;
- the malformed and structure-less fixtures are refused the same way: the
  service checks an attached template's mmCIF, so a broken structure is never
  attached and never serialised.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import QDialog, QTableWidgetItem  # noqa: E402

from configbuilder.model import Explicit, External, IndexPair  # noqa: E402
from configbuilder.ui.render.qt.dialogs import TemplateEditorDialog  # noqa: E402
from configbuilder.ui.render.qt.dialogs import advanced_forms  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "manual_test_data" / "af3_builder" / "templates"
RESOLVED = TEMPLATES / "template_fully_resolved.cif"
UNRESOLVED = TEMPLATES / "template_unresolved_residues.cif"
EMPTY = TEMPLATES / "template_empty.cif"
MALFORMED = TEMPLATES / "template_malformed.cif"
NO_RECORDS = TEMPLATES / "template_no_records.cif"

pytestmark = pytest.mark.skipif(
    not RESOLVED.exists() or not UNRESOLVED.exists(),
    reason="the committed template fixtures are missing",
)


# -- helpers -----------------------------------------------------------------


@pytest.fixture
def job(window):
    """A fresh job with the one protein selected on the Entities page."""
    window.state.new_job("template-job")
    window.refresh()
    return window


def _add_protein(window, sequence):
    assert window.state.add_record("protein", sequence=sequence).ok
    window.refresh()
    key = window.state.configuration.records[-1].ids.primary.value
    assert window.entities_page.select_record(key)
    return key


def _drive_templates(monkeypatch, files, pairs, route="list", accept=True):
    """Answer the real template editor: pick files, fill pairs, click Save."""
    opened = []
    chosen = list(files)
    monkeypatch.setattr(
        advanced_forms.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (chosen.pop(0) if chosen else "", "")),
    )

    def fake_exec(dialog):
        opened.append(dialog)
        assert dialog.select_route(route), route
        if files:
            dialog.table.setRowCount(0)
            for _path in files:
                dialog.add_file()
        for row in range(dialog.table.rowCount()):
            dialog.table.setItem(row, 1, QTableWidgetItem(pairs))
        if not accept:
            return QDialog.Rejected
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(TemplateEditorDialog, "exec", fake_exec)
    return opened


def _save(window, path):
    window.save_path_chooser = lambda parent, default: (str(path), True)
    window.overwrite_confirmer = lambda parent, target: True
    return window.save_json()


def _document(path):
    with open(str(path), encoding="utf-8") as handle:
        return json.load(handle)


def _templates(path):
    return _document(path)["sequences"][0]["protein"]["templates"]


def _pairs(text):
    return tuple(
        IndexPair(int(left), int(right))
        for left, right in (token.split(":") for token in text.split(","))
    )


# -- fixture A ---------------------------------------------------------------


def test_fixture_a_maps_six_residues_one_to_one_through_the_gui(job, tmp_path, monkeypatch):
    _add_protein(job, "ACDEFG")
    opened = _drive_templates(monkeypatch, [str(RESOLVED)], "0:0,1:1,2:2,3:3,4:4,5:5")

    assert job.advanced_page.edit_templates() is True

    assert len(opened) == 1
    record = job.state.configuration.records[0]
    assert isinstance(record.references, Explicit)
    reference = record.references.items[0]
    assert reference.source == External(reference.source.path)
    assert Path(reference.source.path.raw) == RESOLVED
    assert reference.index_map == _pairs("0:0,1:1,2:2,3:3,4:4,5:5")

    target = tmp_path / "job.json"
    assert _save(job, target) is True

    templates = _templates(target)
    assert len(templates) == 1
    assert templates[0]["queryIndices"] == [0, 1, 2, 3, 4, 5]
    assert templates[0]["templateIndices"] == [0, 1, 2, 3, 4, 5]
    assert len(templates[0]["queryIndices"]) == len(templates[0]["templateIndices"])
    # The template travelled with the job: the reference is relative to the
    # JSON and the file really is beside it.
    assert templates[0]["mmcifPath"].replace("\\", "/") == (
        "assets/template-fully-resolved.cif"
    )
    copied = tmp_path / "assets" / "template-fully-resolved.cif"
    assert copied.is_file()
    assert copied.read_bytes() == RESOLVED.read_bytes()


# -- fixture B: unresolved residues ------------------------------------------


def test_fixture_b_maps_the_resolved_tail_to_template_indices_3_to_6(
    job, tmp_path, monkeypatch
):
    """The reported defect: indices are positions in the FULL polymer."""
    _add_protein(job, "DEFG")
    _drive_templates(monkeypatch, [str(UNRESOLVED)], "0:3,1:4,2:5,3:6")

    assert job.advanced_page.edit_templates() is True

    target = tmp_path / "partial.json"
    assert _save(job, target) is True

    templates = _templates(target)
    assert templates[0]["queryIndices"] == [0, 1, 2, 3]
    assert templates[0]["templateIndices"] == [3, 4, 5, 6]
    assert templates[0]["templateIndices"] != [0, 1, 2, 3]
    assert len(templates[0]["queryIndices"]) == len(templates[0]["templateIndices"])

    # The fixture really is what the mapping says it is: seven polymer
    # residues, coordinates for the last four.
    polymer = UNRESOLVED.read_text(encoding="utf-8")
    assert "_entity_poly.pdbx_seq_one_letter_code ACQDEFG" in polymer
    residues = [
        line.split()[5]
        for line in polymer.splitlines()
        if line.startswith("ATOM ")
    ]
    assert residues == ["ASP", "GLU", "PHE", "GLY"]


def test_the_saved_partial_template_survives_reopening(job, tmp_path, monkeypatch):
    """Save → reopen → save again: the mapping and the reference survive."""
    _add_protein(job, "DEFG")
    _drive_templates(monkeypatch, [str(UNRESOLVED)], "0:3,1:4,2:5,3:6")
    first = tmp_path / "first.json"
    assert job.advanced_page.edit_templates() is True
    assert _save(job, first) is True

    state = job.state
    assert state.preview_import(str(first)).ok
    assert state.commit_import(str(first)).ok
    job.refresh()

    record = state.configuration.records[0]
    assert record.references.items[0].index_map == _pairs("0:3,1:4,2:5,3:6")
    # The import resolved the document's relative path against its folder, so
    # the copy beside the file is found again.
    assert Path(record.references.items[0].source.path.raw) == (
        tmp_path / "assets" / "template-unresolved-residues.cif"
    )

    second = tmp_path / "second.json"
    assert _save(job, second) is True

    assert _templates(second) == _templates(first)
    assert _templates(second)[0]["templateIndices"] == [3, 4, 5, 6]


# -- the invalid fixtures ----------------------------------------------------


def test_the_empty_template_is_refused_and_leaves_the_job_alone(
    job, tmp_path, monkeypatch
):
    key = _add_protein(job, "ACDEFG")
    before = job.state.configuration
    # The dialog is *accepted* — its Save button is pressed — and the service
    # refuses, which is the path a user takes.
    opened = _drive_templates(monkeypatch, [str(EMPTY)], "0:0")

    assert job.advanced_page.edit_templates() is False

    dialog = opened[0]
    assert "the file is empty" in dialog.error_text()
    assert dialog.result() != TemplateEditorDialog.Accepted
    # Nothing was half-attached: the same configuration object, and the record
    # still says "let AlphaFold search" (the field is omitted from the JSON).
    assert job.state.configuration is before
    assert job.state.configuration.records[0].references == type(
        job.state.configuration.records[0].references
    )()
    target = tmp_path / "refused.json"
    assert _save(job, target) is True
    protein = _document(target)["sequences"][0]["protein"]
    assert protein["id"] == key
    assert "templates" not in protein


@pytest.mark.parametrize(
    "template, fragment",
    (
        (MALFORMED, "the loop starting at line 9 declares 3 tags"),
        (NO_RECORDS, "no _atom_site, _entity_poly, _struct_asym or _entity records"),
    ),
)
def test_a_template_that_is_not_a_structure_is_refused_and_leaves_the_job_alone(
    job, tmp_path, monkeypatch, template, fragment
):
    """A truncated loop or a data block with no structure in it: refused.

    The dialog is accepted — Save is pressed — and the service refuses, which
    is the path a user takes. Nothing is half-attached, and the saved job
    carries no ``templates`` field.
    """
    key = _add_protein(job, "ACDEFG")
    before = job.state.configuration
    opened = _drive_templates(monkeypatch, [str(template)], "0:0")

    assert job.advanced_page.edit_templates() is False

    dialog = opened[0]
    assert "cannot be used" in dialog.error_text()
    assert fragment in dialog.error_text()
    assert dialog.result() != TemplateEditorDialog.Accepted
    assert job.state.configuration is before
    target = tmp_path / "refused.json"
    assert _save(job, target) is True
    protein = _document(target)["sequences"][0]["protein"]
    assert protein["id"] == key
    assert "templates" not in protein
