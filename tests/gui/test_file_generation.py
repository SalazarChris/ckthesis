"""Generation from a file, driven through the real Entities page.

The workflow is one action on **Entities**: say what the file holds, choose
it, review what was read, choose the folder, generate. These tests drive
``EntitiesPage.generate_from_file`` over the page's five assignable modal
seams and then read the files the application service actually wrote, so a
page that only rendered a label would fail here.

Three of them go one link further and use the *packaged* dialogs instead of
the seams: the real button is clicked (so the click-to-handler connection is
exercised), the packaged input-type box and review box drive their own
buttons, and ``QFileDialog``'s two statics answer with the file and folder. No
human operated the GUI in these cases.

What is pinned:

- the action is the only entry point, and there is no variant page or list;
- **the kind is asked for, never guessed**: the same four-line protein file
  writes four protein configurations when the protein kind is chosen and is
  refused, with advice, when the SMILES kind is chosen;
- a cancelled picker, an empty file, a duplicate entry and a refused base all
  write nothing and change nothing;
- every entry becomes its **own** configuration — base + exactly one entity of
  the chosen kind — named after the entry's own name where it has one;
- protein, DNA, RNA, SMILES and CCD-code files each write their own entity
  representation (``protein``/``dna``/``rna``/``smiles``/``ccdCodes``);
- an existing file with different content stops the whole run (all-or-nothing)
  and is never replaced;
- the report lists the files that were actually written, not the planned ones.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QFileDialog,
    QMessageBox,
    QPushButton,
)

from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.dialogs import batch_input  # noqa: E402
from configbuilder.ui.render.qt.dialogs import (  # noqa: E402
    choose_batch_file,
    choose_batch_kind,
    choose_output_folder,
    confirm_batch_preview,
    report_batch_run,
)

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"


# -- helpers -----------------------------------------------------------------


@pytest.fixture
def base_job(window):
    """A valid base job: one protein and one CCD ligand, as the user left it."""
    state = window.state
    state.new_job("ligand-base")
    assert state.add_record("protein", sequence=PROTEIN).ok
    assert state.add_record(
        "ligand", representation="ATP", representation_kind="ccd"
    ).ok
    # The job as it would be after an import or save: clean, so a later test
    # can prove that generating files does not dirty it.
    state.mark_saved()
    window.refresh()
    return window


def _write_ligands(tmp_path, text, name="ligands.smiles"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _documents(root):
    """Every AF3 JSON the run wrote, by file name."""
    found = {}
    for current, _directories, files in os.walk(str(root)):
        for name in files:
            if name.endswith(".json") and name != "manifest.json":
                with open(os.path.join(current, name), encoding="utf-8") as handle:
                    found[name] = json.load(handle)
    return found


def _ligands(document):
    """The ligand entries of one written document."""
    return [entry["ligand"] for entry in document["sequences"] if "ligand" in entry]


def _records(window):
    return tuple(
        record.ids.primary.value for record in window.state.configuration.records
    )


class _Run:
    """The five seam answers plus what the page asked and was handed.

    ``kind`` is the answer the input-type seam would give, and the file seam
    records the kind it was asked for — that pairing is the point: the file
    question cannot happen before the kind question, and the kind cannot change
    between them.
    """

    def __init__(self, page, path, root, accept=True, kind="ligand-smiles"):
        self.page = page
        self.path = path
        self.root = root
        self.accept = accept
        self.kind = kind
        self.previews = []
        self.reports = []
        self.folders = []
        self.kinds = []
        self.file_kinds = []
        page.batch_kind_chooser = self._choose_kind
        page.batch_file_chooser = self._choose_file
        page.batch_folder_chooser = self._choose_folder
        page.batch_previewer = self._preview
        page.batch_reporter = self._report

    def _choose_kind(self, parent):
        self.kinds.append(True)
        return self.kind

    def _choose_file(self, parent, kind=""):
        self.file_kinds.append(kind)
        return self.path

    def _choose_folder(self, parent, start=""):
        self.folders.append(True)
        return self.root

    def _preview(self, parent, preview, output_root, kind=""):
        self.previews.append((preview, output_root, kind))
        return self.accept

    def _report(self, parent, output):
        self.reports.append(output)

    def generate(self):
        self.page.generate_from_file()
        return self.reports[-1] if self.reports else None


def _run(page, path, root, accept=True, kind="ligand-smiles"):
    return _Run(page, path, root, accept=accept, kind=kind).generate()


# -- the entry point ---------------------------------------------------------


def test_the_only_entry_point_is_an_action_on_the_entities_page(base_job):
    page = base_job.entities_page
    assert page.batch_file_button.text() == _text("gui.action_file_generation")
    assert page.isAncestorOf(page.batch_file_button)
    # The dialogs are the packaged ones until a test replaces them, and the
    # page owns the whole sequence: no second page, no list, no variant wording
    # anywhere the user can see.
    assert page.batch_file_chooser is choose_batch_file
    assert page.batch_folder_chooser is choose_output_folder
    assert page.batch_kind_chooser is choose_batch_kind
    assert page.batch_previewer is confirm_batch_preview
    assert page.batch_reporter is report_batch_run
    texts = {
        button.text().lower()
        for button in base_job.findChildren(QPushButton)
        if button.isVisibleTo(base_job)
    }
    assert not any("variant" in text for text in texts)


# -- refusals that came before any write -------------------------------------


def test_cancelling_the_file_picker_changes_nothing(base_job, tmp_path):
    page = base_job.entities_page
    before_records = _records(base_job)
    before_config = base_job.state.configuration
    run = _Run(page, "", str(tmp_path / "out"))

    assert run.generate() is None
    assert run.previews == []
    assert run.folders == [], "no folder question after a cancelled picker"
    assert _records(base_job) == before_records
    assert base_job.state.configuration is before_config
    assert list(tmp_path.iterdir()) == []


def test_an_empty_file_is_refused_before_a_folder_is_chosen(base_job, tmp_path):
    path = _write_ligands(tmp_path, "# a comment only\n\n   \n", name="empty.smiles")
    page = base_job.entities_page
    run = _Run(page, path, str(tmp_path / "out"))

    assert run.generate() is None
    assert run.folders == [], "the refusal comes before the folder question"
    assert base_job.last_problem_text() == (
        "the ligand file contains no entries (only blank lines or comments)"
    )
    assert list(tmp_path.iterdir()) == [tmp_path / "empty.smiles"]


def test_a_duplicate_entry_is_refused_with_the_files_own_message(base_job, tmp_path):
    path = _write_ligands(tmp_path, "first CCO\nsecond CCO\n", name="dupe.smiles")
    page = base_job.entities_page
    run = _Run(page, path, str(tmp_path / "out"))

    assert run.generate() is None
    assert run.folders == []
    assert base_job.last_problem_text().startswith(
        "the file contains duplicate ligand entries:"
    )
    assert list(tmp_path.iterdir()) == [tmp_path / "dupe.smiles"]


def test_a_missing_file_is_reported_not_raised(base_job, tmp_path):
    page = base_job.entities_page
    run = _Run(page, str(tmp_path / "nope.smiles"), str(tmp_path / "out"))

    assert run.generate() is None
    assert "cannot be read" in base_job.last_problem_text()
    assert run.folders == []


def test_the_review_box_lists_the_entries_and_the_destination(
    base_job, tmp_path, monkeypatch
):
    """The real dialog text, with only its modal loop stood in for."""
    path = _write_ligands(tmp_path, "ethanol CCO\nacetone CC(=O)C\n")
    page = base_job.entities_page
    preview = base_job.state.inspect_input_file(path)
    shown = []
    monkeypatch.setattr(
        QMessageBox, "exec", lambda self: shown.append(self.text()) or 0
    )

    work = tmp_path / "out"
    accepted = confirm_batch_preview(page, preview, str(work), "ligand-smiles")

    assert accepted is False, "an un-pressed box is a cancel"
    assert len(shown) == 1
    text = shown[0]
    assert _text("gui.batch_preview_entries") % 2 in text
    # The kind is stated in the box, from the shipped label.
    assert (
        _text("gui.batch_preview_kind") % _text("menu.file_kind_ligand_smiles")
        in text
    )
    assert "ethanol  CCO" in text
    assert "acetone  CC(=O)C" in text
    assert _text("gui.batch_preview_destination") % str(work) in text
    assert list(tmp_path.glob("out")) == []


def test_cancelling_the_review_writes_nothing(base_job, tmp_path):
    path = _write_ligands(tmp_path, "ethanol CCO\nacetone CC(=O)C\n")
    page = base_job.entities_page
    run = _Run(page, path, str(tmp_path / "out"), accept=False)

    assert run.generate() is None
    assert len(run.previews) == 1, "the review was shown"
    preview, root, kind = run.previews[0]
    assert preview.ok and len(preview.entries) == 2
    assert root == str(tmp_path / "out")
    assert kind == "ligand-smiles"
    assert not (tmp_path / "out").exists()


def test_a_blocked_base_writes_nothing_and_reports_the_findings(window, tmp_path):
    window.state.new_job("empty-base")
    window.refresh()
    path = _write_ligands(tmp_path, "ethanol CCO\n")
    run = _Run(window.entities_page, path, str(tmp_path / "out"))

    outcome = run.generate()

    assert outcome is not None and not outcome.ok
    assert not outcome.written
    assert outcome.plan is not None and not outcome.plan.ok
    assert not (tmp_path / "out").exists()
    assert window.state.configuration.records == ()


# -- generation --------------------------------------------------------------


def test_each_entry_becomes_its_own_configuration(base_job, tmp_path):
    """Three entries in, three files out, each base + exactly one ligand."""
    path = _write_ligands(
        tmp_path,
        "# named entries, then a bare SMILES\n"
        "ethanol CCO\n"
        "acetic-acid CC(=O)O\n"
        "C1CCCCC1\n",
    )
    before_records = _records(base_job)
    before_config = base_job.state.configuration
    page = base_job.entities_page
    work = tmp_path / "out"

    outcome = _run(page, path, str(work))

    assert outcome is not None and outcome.ok, outcome.errors
    documents = _documents(work)
    assert len(documents) == 3, sorted(documents)
    names = set(documents)
    assert any("ethanol" in name for name in names)
    assert any("acetic" in name for name in names)
    assert any("ligand" in name for name in names), "the bare entry is positional"

    smiles = set()
    added_ids = set()
    for document in documents.values():
        # Two base entities plus the one this file added: never two ligands
        # from the batch, and the batch entry never leaks between outputs.
        assert len(document["sequences"]) == 3
        ligands = _ligands(document)
        assert len(ligands) == 2, "the base CCD ligand plus this entry"
        assert ligands[0] == {"id": "B", "ccdCodes": ["ATP"]}
        assert set(ligands[1]) == {"id", "smiles"}
        smiles.add(ligands[1]["smiles"])
        added_ids.add(ligands[1]["id"])
        protein = next(
            entry["protein"] for entry in document["sequences"] if "protein" in entry
        )
        assert protein["sequence"] == PROTEIN
    assert smiles == {"CCO", "CC(=O)O", "C1CCCCC1"}
    # Identifiers are allocated for the whole file up front, so each output's
    # added entity has its own valid, unused identifier.
    assert added_ids == {"C", "D", "E"}

    # The job on screen is untouched: same configuration object, same records.
    assert base_job.state.configuration is before_config
    assert _records(base_job) == before_records
    assert [record.ids.primary.value for record in before_config.records] == ["A", "B"]


def test_the_report_lists_exactly_the_files_on_disk(base_job, tmp_path):
    path = _write_ligands(tmp_path, "ethanol CCO\nacetone CC(=O)C\n")
    page = base_job.entities_page
    work = tmp_path / "out"
    run = _Run(page, path, str(work))

    outcome = run.generate()

    assert outcome is not None and outcome.ok
    assert run.reports[-1] is outcome
    on_disk = sorted(
        os.path.join(current, name).replace("/", os.sep)
        for current, _directories, files in os.walk(str(work))
        for name in files
    )
    assert sorted(outcome.written) == on_disk
    assert len(outcome.written) == len(outcome.plan.entries)
    # The status bar says how many files were written, from the same outcome.
    assert base_job.statusBar().currentMessage() == _text("gui.batch_notice") % len(
        outcome.written
    )


def test_the_repair_report_never_claims_a_write_that_did_not_happen(
    base_job, tmp_path, monkeypatch
):
    """A refused plan is reported as a refusal, with its own message."""
    path = _write_ligands(tmp_path, "ethanol CCO\n")
    page = base_job.entities_page
    outcome = _Run(page, path, str(tmp_path / "out")).generate()
    assert outcome.ok

    shown = []
    monkeypatch.setattr(
        QMessageBox, "exec", lambda self: shown.append(self.text()) or 0
    )
    report_batch_run(page, outcome)

    assert shown and _text("gui.batch_result_written") % len(outcome.written) in shown[0]

    blocked = base_job.state.generate_input_configurations(
        path, str(tmp_path / "again")
    )
    assert blocked.ok, "identical content is not a conflict"

    page.state.services.projects.new("empty-again")
    refused = base_job.state.generate_input_configurations(
        path, str(tmp_path / "refused")
    )
    shown.clear()
    report_batch_run(page, refused)
    assert shown and "Nothing was written" in shown[0]
    assert not (tmp_path / "refused").exists()


def test_an_existing_file_with_different_content_stops_the_whole_run(
    base_job, tmp_path
):
    """All-or-nothing: the conflict is found before any file is written."""
    path = _write_ligands(tmp_path, "ethanol CCO\nacetone CC(=O)C\n")
    work = tmp_path / "out"
    target = work / "ligand-base" / "ligand-base__ethanol" / "ligand-base__ethanol.json"
    target.parent.mkdir(parents=True)
    target.write_text("someone else's bytes", encoding="utf-8")

    outcome = _run(base_job.entities_page, path, str(work))

    assert outcome is not None and not outcome.ok
    assert not outcome.written
    assert target.read_text(encoding="utf-8") == "someone else's bytes"
    written = [
        name
        for current, _directories, files in os.walk(str(work))
        for name in files
    ]
    assert written == ["ligand-base__ethanol.json"], "nothing else was created"
    assert outcome.plan is not None and not outcome.plan.ok
    assert str(target) in "".join(outcome.plan.conflicts)


def test_generating_twice_leaves_the_base_job_identical(base_job, tmp_path):
    path = _write_ligands(tmp_path, "ethanol CCO\n")
    page = base_job.entities_page
    before = base_job.state.configuration

    assert _run(page, path, str(tmp_path / "one")).ok
    assert _run(page, path, str(tmp_path / "two")).ok

    assert base_job.state.configuration is before
    assert _records(base_job) == ("A", "B")
    assert base_job.state.is_dirty is False
    first = _documents(tmp_path / "one")
    second = _documents(tmp_path / "two")
    assert first == second, "the same file produces the same documents"


# -- a base job that carries what a ligand file cannot say -------------------

BATCH_PACK = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    + os.sep
    + "manual_test_data"
    + os.sep
    + "af3_builder"
    + os.sep
    + "batch"
)


def test_a_custom_ccd_base_survives_in_every_generated_file(window, tmp_path):
    """The job's own CCD definition, ion and multi-copy ligand are kept."""
    from configbuilder.ui.render.qt.dialogs import ImportPreviewDialog

    base = os.path.join(BATCH_PACK, "base_job_custom_ccd.json")
    ligands = os.path.join(BATCH_PACK, "ligands_named.smiles")
    assert os.path.isfile(base) and os.path.isfile(ligands)
    with open(base, encoding="utf-8") as handle:
        custom_ccd = json.load(handle)["userCCD"]

    # Open the way the window does, with only the modal loop stood in for.
    original_exec = ImportPreviewDialog.exec
    import configbuilder.ui.render.qt.dialogs.import_preview as dialog_module

    def accept_once(dialog):
        return dialog_module.ImportPreviewDialog.Accepted

    ImportPreviewDialog.exec = accept_once
    try:
        assert window.offer_import(base) is True
    finally:
        ImportPreviewDialog.exec = original_exec

    records = [record.ids.primary.value for record in window.state.configuration.records]
    assert records == ["A", "B", "C", "D"]

    page = window.entities_page
    run = _Run(page, ligands, str(tmp_path / "out"))
    outcome = run.generate()

    assert outcome is not None and outcome.ok, outcome.errors
    documents = _documents(tmp_path / "out")
    assert len(documents) == 3
    added = set()
    for document in documents.values():
        assert document["userCCD"] == custom_ccd
        assert document["modelSeeds"] == [7]
        assert document["version"] == 3
        identifiers = []
        for entry in document["sequences"]:
            body = next(iter(entry.values()))
            value = body["id"]
            identifiers.extend(value if isinstance(value, list) else [value])
        assert identifiers[:5] == ["A", "B", "E", "C", "D"]
        added.add(identifiers[-1])
    assert added == {"F", "G", "H"}
    # The job on screen is still the base that was opened.
    assert [
        record.ids.primary.value for record in window.state.configuration.records
    ] == ["A", "B", "C", "D"]


# -- the packaged dialogs, and the real click -----------------------------------


def _answer_with_file_dialog(monkeypatch, path, root):
    """Let the *packaged* choosers run, answering the native statics."""
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (path, "")),
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *args, **kwargs: root)
    )


def _drives_boxes(monkeypatch, label_keys, seen):
    """Drive each packaged ``QMessageBox.exec`` by pressing one of its buttons.

    ``label_keys`` are tried in order for each box: the input-type box answers
the first label it has, the review box the next, and a box with none of them
    (the result report) is left unpressed, exactly as a user closing it would
    leave it. The boxes are the shipped ones — their text, buttons and
    ``clickedButton`` answers are their own. Only the human's mouse is stood in
    for, because nothing in this process can move one.
    """
    remaining = list(label_keys)

    def fake_exec(box):
        seen.append(box.text())
        for index, label_key in enumerate(remaining):
            wanted = _text(label_key)
            for button in box.buttons():
                if button.text() == wanted:
                    button.click()
                    del remaining[index]
                    return 0
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)


def test_the_real_button_click_writes_the_files_through_the_packaged_dialogs(
    base_job, tmp_path, monkeypatch
):
    """Click → handler → service → files, with the shipped dialogs in place.

    The other tests in this file replace the page's five modal seams; this one
    replaces none of them. It clicks the real button (so the click-to-handler
    connection is exercised), presses the packaged input-type box's *SMILES*
    button and the review box's own *Generate* button, and answers the two
    native file-dialog statics — so every box's text and its ``clickedButton``
    answer are the shipped ones.
    """
    page = base_job.entities_page
    path = _write_ligands(tmp_path, "ethanol CCO\nbenzene c1ccccc1\n")
    root = tmp_path / "out"
    boxes = []
    _answer_with_file_dialog(monkeypatch, path, str(root))
    _drives_boxes(
        monkeypatch,
        ["menu.file_kind_ligand_smiles", "gui.batch_preview_accept"],
        boxes,
    )

    assert page.batch_kind_chooser is choose_batch_kind
    assert page.batch_file_chooser is choose_batch_file
    assert page.batch_folder_chooser is choose_output_folder
    assert page.batch_previewer is confirm_batch_preview
    assert page.batch_reporter is report_batch_run

    QTest.mouseClick(page.batch_file_button, Qt.LeftButton)

    documents = _documents(root)
    assert sorted(documents) == [
        "ligand-base__benzene.json",
        "ligand-base__ethanol.json",
    ]
    # The input-type box, the review box, then the result box, in that order.
    assert len(boxes) == 3
    assert boxes[0] == _text("gui.batch_kind_prompt")
    assert _text("gui.batch_preview_entries") % 2 in boxes[1]
    assert (
        _text("gui.batch_preview_kind") % _text("menu.file_kind_ligand_smiles")
        in boxes[1]
    )
    assert str(root) in boxes[1]
    # Two configurations plus the run's own manifest.json.
    assert _text("gui.batch_result_written") % 3 in boxes[2]
    for document in documents.values():
        # The base's protein and CCD ligand, plus exactly one new ligand.
        assert len(_ligands(document)) == 2
        assert document["sequences"][0]["protein"]["id"] == "A"
    assert [
        record.ids.primary.value for record in base_job.state.configuration.records
    ] == ["A", "B"]


def test_the_real_button_and_packaged_dialogs_generate_protein_sequences(
    base_job, tmp_path, monkeypatch
):
    """The reported four-line file also traverses the shipped dialogs."""
    page = base_job.entities_page
    path = os.path.join(PACK, "proteins_minimal.txt")
    root = tmp_path / "protein-out"
    boxes = []
    _answer_with_file_dialog(monkeypatch, path, str(root))
    _drives_boxes(
        monkeypatch,
        ["menu.file_kind_protein", "gui.batch_preview_accept"],
        boxes,
    )

    QTest.mouseClick(page.batch_file_button, Qt.LeftButton)

    documents = _documents(root)
    assert len(documents) == 4, sorted(documents)
    found = set()
    for document in documents.values():
        sequences = document["sequences"]
        assert len(sequences) == 3
        assert sequences[0]["protein"]["sequence"] == PROTEIN
        assert sequences[1]["ligand"] == {"id": "B", "ccdCodes": ["ATP"]}
        added = sequences[-1]
        assert list(added) == ["protein"]
        assert set(added["protein"]) == {"id", "sequence"}
        found.add(added["protein"]["sequence"])
    assert found == {"MVT", "MVS", "MVY", "TEST"}
    assert len(boxes) == 3
    assert boxes[0] == _text("gui.batch_kind_prompt")
    assert _text("menu.file_kind_protein") in boxes[1]
    assert str(root) in boxes[1]
    assert _text("gui.batch_result_written") % 5 in boxes[2]
    assert [record.ids.primary.value for record in base_job.state.configuration.records] == ["A", "B"]


# -- the input kinds the action offers ----------------------------------------

PACK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "manual_test_data",
    "af3_builder",
    "batch",
)


def test_the_kind_is_asked_for_before_the_file(base_job, tmp_path):
    """Kind first, then file: the file cannot be read without the answer.

    ``.txt`` alone identifies nothing, so the page must not open a file before
    the user has said what is in it — and the kind the file question receives
    is the kind the preview and the write use.
    """
    page = base_job.entities_page
    path = _write_ligands(tmp_path, "ethanol CCO\n")
    run = _Run(page, path, str(tmp_path / "out"), kind="ligand-ccd")

    assert run.generate() is not None
    assert run.kinds == [True], "the kind was asked for"
    assert run.file_kinds == ["ligand-ccd"], "and passed to the file question"
    assert [kind for _preview, _root, kind in run.previews] == ["ligand-ccd"]


def test_a_cancelled_kind_question_touches_nothing(base_job, tmp_path):
    page = base_job.entities_page
    before = base_job.state.configuration
    run = _Run(page, _write_ligands(tmp_path, "ethanol CCO\n"), "", kind="")

    assert run.generate() is None
    assert run.file_kinds == [], "no file question after a cancelled kind"
    assert run.folders == []
    assert base_job.state.configuration is before


def test_four_protein_sequences_write_four_protein_configurations(base_job, tmp_path):
    """The reported problem, fixed: ``MVT/MVS/MVY/TEST`` as proteins.

    The same file in SMILES mode is refused (the test below); here the kind is
    protein, so each line becomes its own configuration whose added entity is
    a ``protein`` with that sequence — never a ligand, and never in ``smiles``
    or ``ccdCodes``.
    """
    page = base_job.entities_page
    path = os.path.join(PACK, "proteins_minimal.txt")
    work = tmp_path / "out"

    outcome = _run(page, path, str(work), kind="protein-sequence")

    assert outcome is not None and outcome.ok, outcome.errors
    documents = _documents(work)
    assert len(documents) == 4, sorted(documents)
    added = {}
    for document in documents.values():
        sequences = document["sequences"]
        # The base's protein and CCD ligand, plus exactly one new protein.
        assert len(sequences) == 3
        assert sequences[0]["protein"]["id"] == "A"
        assert sequences[1]["ligand"] == {"id": "B", "ccdCodes": ["ATP"]}
        new = sequences[2]
        assert list(new) == ["protein"], new
        assert set(new["protein"]) == {"id", "sequence"}
        added[new["protein"]["id"]] = new["protein"]["sequence"]
    assert sorted(added.values()) == ["MVS", "MVT", "MVY", "TEST"]
    assert len(set(added)) == 4, "one identifier per entry"
    # The base job is the same job afterwards, with the same records.
    assert [
        record.ids.primary.value for record in base_job.state.configuration.records
    ] == ["A", "B"]


def test_dna_and_rna_files_write_their_own_entity_representation(base_job, tmp_path):
    """DNA is ``dna``, RNA is ``rna``: the family follows the chosen kind."""
    page = base_job.entities_page
    for kind, fixture, family, sequences in (
        ("dna-sequence", "dna_sequences.txt", "dna", ["ATGCATGC", "GGCCTTAA"]),
        (
            "rna-sequence",
            "rna_sequences.txt",
            "rna",
            ["ACGUACGUACGU", "GGGCCCAAAUUU"],
        ),
    ):
        work = tmp_path / kind
        outcome = _run(page, os.path.join(PACK, fixture), str(work), kind=kind)

        assert outcome is not None and outcome.ok, outcome.errors
        documents = _documents(work)
        assert len(documents) == len(sequences), sorted(documents)
        written = []
        for document in documents.values():
            if family == "dna":
                strands = document["sequences"][-2:]
                assert [list(entry) for entry in strands] == [["dna"], ["dna"]]
                first, second = (entry["dna"]["sequence"] for entry in strands)
                assert second == first[::-1].translate(str.maketrans("ATGC", "TACG"))
                written.append(first)
            else:
                new = document["sequences"][-1]
                assert list(new) == [family], new
                written.append(new[family]["sequence"])
        assert sorted(written) == sorted(sequences)


@pytest.mark.parametrize(
    "payload,kind,expected_text",
    (
        ("AC1T\n", "protein-sequence", "outside its alphabet"),
        ("MVT\nMVT\n", "protein-sequence", "duplicate"),
        ("ACGT\nAC1T\n", "dna-sequence", "outside its alphabet"),
        ("", "rna-sequence", "no sequences"),
    ),
)
def test_invalid_empty_and_duplicate_sequences_are_refused(
    base_job, tmp_path, payload, kind, expected_text
):
    page = base_job.entities_page
    input_path = tmp_path / "sequence-input.txt"
    input_path.write_text(payload, encoding="utf-8")
    output_root = tmp_path / "out"
    run = _Run(page, str(input_path), str(output_root), kind=kind)

    assert run.generate() is None
    assert run.folders == [], "invalid sequence input must be refused before asking for an output folder"
    assert expected_text.lower() in base_job.last_problem_text().lower()
    assert not output_root.exists()
    assert [record.ids.primary.value for record in base_job.state.configuration.records] == ["A", "B"]


def test_a_ccd_code_file_writes_ccd_codes_not_smiles(base_job, tmp_path):
    """The identifier form: ``ccdCodes``, and several codes are one ligand."""
    page = base_job.entities_page
    path = os.path.join(PACK, "ligands_ccd_codes.txt")
    work = tmp_path / "out"

    outcome = _run(page, path, str(work), kind="ligand-ccd")

    assert outcome is not None and outcome.ok, outcome.errors
    documents = _documents(work)
    assert sorted(documents) == [
        "ligand-base__atp.json",
        "ligand-base__nag-nag-bma-man-man.json",
        "ligand-base__zn.json",
    ]
    codes = {}
    for name, document in documents.items():
        new = document["sequences"][-1]["ligand"]
        assert set(new) == {"id", "ccdCodes"}, name
        codes[name] = new["ccdCodes"]
    assert codes["ligand-base__atp.json"] == ["ATP"]
    assert codes["ligand-base__zn.json"] == ["ZN"]
    assert codes["ligand-base__nag-nag-bma-man-man.json"] == [
        "NAG",
        "NAG",
        "BMA",
        "MAN",
        "MAN",
    ]


def test_a_sequence_file_in_smiles_mode_is_refused_with_advice(base_job, tmp_path):
    """Not silently reinterpreted: refused, and told which kind would read it.

    ``MVT``/``MVY`` are the reported file. In SMILES mode every line is refused
    with its reason, then the refusal names the kinds that would take them — and
    nothing is written, no folder is asked for, and the job is unchanged.
    """
    page = base_job.entities_page
    path = os.path.join(PACK, "proteins_minimal.txt")
    run = _Run(page, path, str(tmp_path / "out"), kind="ligand-smiles")

    assert run.generate() is None
    assert run.folders == [], "no folder question after a refusal"
    message = base_job.last_problem_text()
    assert "not SMILES notation" in message
    assert "'MVT'" in message and "'TEST'" in message
    assert "may be protein sequences rather than SMILES" in message
    assert "protein sequence input type" in message
    assert run.reports == []
    assert not os.path.exists(str(tmp_path / "out"))
    assert [
        record.ids.primary.value for record in base_job.state.configuration.records
    ] == ["A", "B"]
