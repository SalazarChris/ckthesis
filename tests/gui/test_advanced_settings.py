"""Stage 4: modifications, alignments, templates, custom CCD and bonds.

Every test drives the Advanced page's own widgets and then reads the *service*
state: the model record's modifications and alignment, the configuration's
references and component definition, its linkages, and the JSON that
``GenerationService.show_json`` produces. A test that only read the page's
labels would not show that the mutation went through ``ConfigurationService``,
and the whole point of this stage is that the page never builds a record, a
wire value or an identifier itself.

The four form dialogs are modal, so the helpers below stand in for the modal
loop: they fill the **real** dialog's widgets and call the real ``accept``,
which runs the page's ``apply`` callable and the dialog's own refusal handling.
Only ``exec`` (and the file pickers) are replaced — never the service.
"""

from __future__ import annotations

import json
import pathlib

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import QDialog, QTableWidgetItem  # noqa: E402

from configbuilder.app.configuration_service import ReferenceInput  # noqa: E402
from configbuilder.model import (  # noqa: E402
    AlignmentAutomatic,
    AlignmentBoth,
    AlignmentFree,
    AlignmentPairedOnly,
    AlignmentUnpairedOnly,
    Explicit,
    External,
    Inline,
    Pinned,
    SearchAllowed,
    SingleAutomatic,
    SingleFree,
    SingleProvided,
)
from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.dialogs import (  # noqa: E402
    AlignmentFormDialog,
    BondFormDialog,
    LigandFormDialog,
    ModificationFormDialog,
    SequenceFormDialog,
    TemplateEditorDialog,
)
from configbuilder.ui.render.qt.dialogs import advanced_forms  # noqa: E402
from configbuilder.ui.render.qt.models import family_label  # noqa: E402
from configbuilder.ui.render.qt.pages import advanced as advanced_page  # noqa: E402


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def job(window):
    """The window over a fresh, empty job — the Stage 4 actions start here."""
    window.state.new_job()
    return window


@pytest.fixture
def protein_job(job):
    """A job with one protein (``A``) selected on both entity views."""
    assert job.state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    assert job.entities_page.select_record("A")
    return job


@pytest.fixture
def mixed_job(job):
    """A job with a protein, an RNA, a DNA duplex and a CCD ligand."""
    state = job.state
    assert state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    assert state.add_record("rna", sequence="ACGUACGU").ok
    assert state.add_record("dna", sequence="ATGC").ok
    assert state.add_record(
        "ligand", representation="ATP", representation_kind="ccd"
    ).ok
    assert job.entities_page.select_record("A")
    return job


# -- dialog drivers: fill the real widgets, then submit ----------------------


def _drive_modification_form(
    monkeypatch, code=None, position=None, cancel=False, adjust=None
):
    """Answer the modification form. Returns the dialogs the page built."""
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        if adjust is not None:
            adjust(dialog)
        if code is not None:
            dialog.code_edit.setText(code)
        if position is not None:
            dialog.position_spin.setValue(position)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(ModificationFormDialog, "exec", fake_exec)
    return opened


def _drive_alignment_form(
    monkeypatch,
    mode=None,
    kind=None,
    text=None,
    path=None,
    cancel=False,
    paired_kind=None,
    paired_text=None,
    paired_path=None,
):
    """Answer the alignment form: a mode word and, when used, its source(s).

    The paired-side arguments drive the ``both`` mode's second source; leaving
    them out keeps the single-source behaviour every older test relies on.
    """
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        if mode is not None:
            assert dialog.select_mode(mode), mode
        if kind is not None:
            for candidate, radio in dialog.source_radios:
                radio.setChecked(candidate == kind)
        if text is not None:
            dialog.inline_edit.setPlainText(text)
        if path is not None:
            dialog.path_edit.setText(path)
        if paired_kind is not None:
            for candidate, radio in dialog.paired_radios:
                radio.setChecked(candidate == paired_kind)
        if paired_text is not None:
            dialog.paired_inline_edit.setPlainText(paired_text)
        if paired_path is not None:
            dialog.paired_path_edit.setText(paired_path)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(AlignmentFormDialog, "exec", fake_exec)
    return opened


def _drive_template_dialog(
    monkeypatch, route, files=(), pairs=None, cancel=False, inline=None
):
    """Answer the template editor: choose a route and pick files as a user does.

    The file picker is replaced, so the dialog's own ``add_file`` runs and the
    real ``QFileDialog`` never opens offscreen.
    """
    opened = []
    chosen = list(files)
    monkeypatch.setattr(
        advanced_forms.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (chosen.pop(0) if chosen else "", "")),
    )

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        assert dialog.select_route(route), route
        if files:
            dialog.table.setRowCount(0)
            for _path in files:
                dialog.add_file()
        if inline is not None:
            dialog.table.setRowCount(0)
            dialog.add_inline(inline)
        if pairs is not None:
            for row in range(dialog.table.rowCount()):
                dialog.table.setItem(row, 1, QTableWidgetItem(pairs))
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(TemplateEditorDialog, "exec", fake_exec)
    return opened


def _msa_a3m(tmp_path, name="msa.a3m"):
    """A real, readable MSA file.

    The external-MSA preflight check (``R-MSA-006``) reads the configured file
    before save or preview proceeds, so a test that wants the *serialization*
    behaviour of a path source has to point at a file that exists. A made-up
    name now refuses the whole document — that refusal is covered by
    ``tests/unit/app/test_gate_recovery.py``.
    """
    path = tmp_path / name
    path.write_text(">q\nACDE\n", encoding="utf-8")
    return str(path)


def _template_cif(tmp_path, name="template.cif"):
    """A real single-chain protein template: ten residues, so the mapping
    bounds these tests use (up to template index 9) address it."""
    path = tmp_path / name
    path.write_text(
        "data_template\n"
        "#\n"
        "_entity_poly.entity_id 1\n"
        "_entity_poly.type 'polypeptide(L)'\n"
        "_entity_poly.pdbx_strand_id A\n"
        "_entity_poly.pdbx_seq_one_letter_code ACDEFGHIKL\n"
        "#\n",
        encoding="utf-8",
    )
    return str(path)


def _drive_bond_dialog(monkeypatch, left=None, right=None, cancel=False):
    """Answer the bond form: two endpoints, each key/residue/atom.

    A key no record carries is added to the combo, because the combo offers
    only real identifiers and the ghost is how a test reaches the refusal
    path a user cannot reach by clicking.
    """
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        for controls, values in (
            ((dialog.left_key, dialog.left_residue, dialog.left_atom), left),
            ((dialog.right_key, dialog.right_residue, dialog.right_atom), right),
        ):
            if values is None:
                continue
            combo, spin, atom = controls
            key, residue, atom_name = values
            index = combo.findData(key)
            if index < 0:
                combo.addItem("a key no record carries", key)
                index = combo.count() - 1
            combo.setCurrentIndex(index)
            spin.setValue(residue)
            atom.setText(atom_name)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(BondFormDialog, "exec", fake_exec)
    return opened


def _drive_sequence_form(monkeypatch, sequence=None, description=None, cancel=False):
    """Answer the add/edit chain form (Stage 3's dialog, Stage 4's hint)."""
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        if sequence is not None:
            dialog.sequence_edit.setPlainText(sequence)
        if description is not None:
            dialog.description_edit.setText(description)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(SequenceFormDialog, "exec", fake_exec)
    return opened


def _drive_ligand_form(monkeypatch, kind="ccd", value=None, description=None):
    """Answer the ligand form the Entities page builds (Stage 3's route)."""
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        (dialog.smiles_radio if kind == "smiles" else dialog.ccd_radio).setChecked(True)
        if value is not None:
            dialog.value_edit.setText(value)
        if description is not None:
            dialog.description_edit.setText(description)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(LigandFormDialog, "exec", fake_exec)
    return opened


def _answer_removal(monkeypatch, page, attribute, answer=True):
    """Answer one removal confirmation; returns the questions it was asked."""
    asked = []

    def confirmer(parent, question):
        asked.append(question)
        return answer

    monkeypatch.setattr(page, attribute, confirmer)
    return asked


# -- reading the results -----------------------------------------------------


def _record(state, key):
    return next(
        record
        for record in state.configuration.records
        if record.ids.primary.value == key
    )


def _document(window):
    """The previewed JSON as a dict, or ``None`` when the service refused."""
    text = window.preview_page.editor.toPlainText()
    return json.loads(text) if text else None


def _entry(document, key):
    """The wire entry whose ``id`` is ``key``, in serialization order."""
    for entry in document["sequences"]:
        (body,) = entry.values()
        if body["id"] == key:
            return body
    raise AssertionError("no entry for %r in %r" % (key, document["sequences"]))


def _status_bar(window):
    return window.statusBar().currentMessage()


def _changes(state):
    """Record the state's own change notifications.

    Exactly one fires per successful mutation (that is what refreshes the
    pages), so a cancelled or refused action leaving this empty is proof that
    nothing was applied *and* that no page was told otherwise.
    """
    seen = []
    state.project_changed.connect(lambda: seen.append(1))
    return seen


# =============================================================================
# Stage 4C — modifications / PTMs
# =============================================================================


def test_the_modification_table_lists_the_entitys_own_modifications(
    reviewed, monkeypatch
):
    """The fixture's protein already carries SEP at 4, and it is editable."""
    reviewed.entities_page.select_record("A")
    page = reviewed.advanced_page
    assert page.modification_rows() == (("SEP", "4", "E"),)
    assert page.add_modification_button.isEnabled()
    assert page.remove_modification_button.isEnabled()


def test_the_modification_section_says_so_for_a_ligand(mixed_job, monkeypatch):
    """A ligand carries no modifications; no control pretends otherwise."""
    mixed_job.entities_page.select_record("E")
    page = mixed_job.advanced_page
    assert page.modification_rows() == ()
    assert not page.add_modification_button.isEnabled()
    assert not page.remove_modification_button.isEnabled()

    # Even a stray click cannot open a form that has no entity to edit.
    opened = _drive_modification_form(monkeypatch, code="SEP", position=1)
    assert not page.add_modification()
    assert opened == []


def test_the_position_column_is_labelled_one_based(protein_job):
    labels = [
        protein_job.advanced_page.modification_table.horizontalHeaderItem(column).text()
        for column in range(3)
    ]
    assert labels == [
        _text("gui.mod_form_code"),
        _text("gui.mod_form_position"),
        _text("gui.mod_col_residue"),
    ]
    # The wording must keep saying that the position is 1-based, whatever the
    # exact phrasing is (Stage 9 shortened it to keep the column readable).
    assert "1-based" in _text("gui.mod_form_position")
    assert "1-based" in _text("gui.mod_note")


def test_adding_a_modification_goes_through_the_service(protein_job, monkeypatch):
    """Add through the dialog; the model, the table and the JSON all move."""
    changes = _changes(protein_job.state)
    opened = _drive_modification_form(monkeypatch, code="SEP", position=3)
    assert protein_job.advanced_page.add_modification()
    assert len(changes) == 1, "one refresh for one successful change"

    assert [m.code.value for m in _record(protein_job.state, "A").modifications] == ["SEP"]
    assert [m.position.value for m in _record(protein_job.state, "A").modifications] == [3]
    assert protein_job.advanced_page.modification_rows() == (("SEP", "3", "D"),)
    assert _entry(_document(protein_job), "A")["modifications"] == [
        {"ptmType": "SEP", "ptmPosition": 3}
    ]
    assert _status_bar(protein_job) == _text("menu.modification_added")
    # The position the user chose is the one the model was asked for.
    assert opened[0].position_spin.value() == 3


def test_the_form_echoes_the_residue_at_the_chosen_one_based_position(
    protein_job, monkeypatch
):
    """Position 1 is the chain's first residue — never an index."""
    opened = _drive_modification_form(monkeypatch, code="SEP", position=1)
    protein_job.advanced_page.add_modification()
    assert opened[0].residue_label.text() == _text("gui.mod_residue_echo") % "A"
    assert protein_job.advanced_page.modification_rows() == (("SEP", "1", "A"),)


def test_the_echo_reports_a_position_past_the_end(protein_job, monkeypatch):
    opened = _drive_modification_form(monkeypatch, code="SEP", position=99)
    assert protein_job.advanced_page.add_modification()
    assert opened[0].residue_label.text() == _text(
        "gui.mod_residue_out_of_range"
    ) % (99, 20)


def test_an_out_of_range_position_blocks_readiness_and_the_preview(
    protein_job, monkeypatch
):
    """The service keeps the modification; validation, not the page, refuses."""
    _drive_modification_form(monkeypatch, code="SEP", position=99)
    assert protein_job.advanced_page.add_modification()

    status = protein_job.state.status()
    assert not status.ready
    assert "R-ENT-007" in {finding.rule_id for finding in status.blocking}
    assert _document(protein_job) is None
    assert protein_job.state.preview_json()[1]
    assert protein_job.advanced_page.modification_rows() == (("SEP", "99", "-"),)


def test_a_service_refusal_keeps_the_dialog_open_and_the_record_untouched(
    protein_job, monkeypatch
):
    """Position 0 is refused by the service; the form stays open with its words."""
    before = protein_job.state.configuration
    changes = _changes(protein_job.state)

    def widen(dialog):
        # The spin box starts at 1; widening it is how a test reaches the
        # service's own refusal for a position it cannot offer.
        dialog.position_spin.setRange(0, 9999)
        dialog.position_spin.setValue(0)

    opened = _drive_modification_form(
        monkeypatch, code="SEP", position=None, adjust=widen
    )
    assert not protein_job.advanced_page.add_modification()

    assert opened[0].result() != QDialog.Accepted
    assert "positive integer" in opened[0].error_text()
    assert protein_job.state.configuration is before
    assert protein_job.advanced_page.modification_rows() == ()
    assert changes == []


def test_cancelling_the_modification_form_changes_nothing(protein_job, monkeypatch):
    before = protein_job.state.configuration
    changes = _changes(protein_job.state)
    _drive_modification_form(monkeypatch, cancel=True)
    assert not protein_job.advanced_page.add_modification()
    assert protein_job.state.configuration is before
    assert changes == []


def test_editing_uses_the_selected_modification_its_own_index(
    protein_job, monkeypatch
):
    """Two modifications; the second row is edited and only it changes."""
    assert protein_job.state.add_modification("A", "SEP", 5).ok
    assert protein_job.state.add_modification("A", "TPO", 6).ok
    protein_job.entities_page.select_record("A")
    table = protein_job.advanced_page.modification_table
    assert table.rowCount() == 2
    table.selectRow(1)

    _drive_modification_form(monkeypatch, code="MLY", position=7)
    assert protein_job.advanced_page.edit_selected_modification()

    stored = [
        (m.code.value, m.position.value) for m in _record(protein_job.state, "A").modifications
    ]
    assert stored == [("SEP", 5), ("MLY", 7)]


def test_editing_without_a_selection_says_so_and_changes_nothing(protein_job):
    before = protein_job.state.configuration
    protein_job.entities_page.select_record("A")
    assert not protein_job.advanced_page.edit_selected_modification()
    assert protein_job.state.configuration is before
    assert protein_job.last_problem_text() == _text("gui.mod_select_first")


def test_removing_the_selected_modification_asks_then_calls_the_service(
    protein_job, monkeypatch
):
    assert protein_job.state.add_modification("A", "SEP", 7).ok
    protein_job.entities_page.select_record("A")
    page = protein_job.advanced_page
    page.modification_table.selectRow(0)
    asked = _answer_removal(monkeypatch, page, "modification_confirmer")

    assert page.remove_selected_modification()
    # The question names the code, the 1-based position and the entity.
    assert asked == [_text("gui.mod_delete_question") % ("SEP", 7, "A")]
    assert tuple(_record(protein_job.state, "A").modifications or ()) == ()
    assert page.modification_rows() == ()
    assert "modifications" not in _entry(_document(protein_job), "A")


def test_cancelling_the_removal_confirmation_changes_nothing(
    protein_job, monkeypatch
):
    assert protein_job.state.add_modification("A", "SEP", 7).ok
    protein_job.entities_page.select_record("A")
    page = protein_job.advanced_page
    page.modification_table.selectRow(0)
    _answer_removal(monkeypatch, page, "modification_confirmer", answer=False)

    before = protein_job.state.configuration
    changes = _changes(protein_job.state)
    assert not page.remove_selected_modification()
    assert protein_job.state.configuration is before
    assert page.modification_rows() == (("SEP", "7", "H"),)
    assert changes == []


def test_an_imported_modification_is_editable_and_removable(
    protein_job, monkeypatch
):
    """Modifications that came with the job are not second-class."""
    reviewed = protein_job  # the fixture's own SEP arrived through the service
    assert reviewed.state.add_modification("A", "SEP", 4).ok
    reviewed.entities_page.select_record("A")
    page = reviewed.advanced_page
    assert page.modification_rows() == (("SEP", "4", "E"),)

    page.modification_table.selectRow(0)
    _drive_modification_form(monkeypatch, code="TPO", position=4)
    assert page.edit_selected_modification()
    assert page.modification_rows() == (("TPO", "4", "E"),)

    page.modification_table.selectRow(0)
    _answer_removal(monkeypatch, page, "modification_confirmer")
    assert page.remove_selected_modification()
    assert page.modification_rows() == ()
    assert _entry(_document(reviewed), "A").get("modifications") is None


def test_the_modification_panel_follows_the_selected_entity(mixed_job):
    """One page for every family; the shown entity decides what it offers."""
    mixed_job.entities_page.select_record("B")  # RNA
    assert mixed_job.advanced_page.add_modification_button.isEnabled()
    mixed_job.entities_page.select_record("C")  # DNA
    assert mixed_job.advanced_page.add_modification_button.isEnabled()
    mixed_job.entities_page.select_record("E")  # ligand
    assert not mixed_job.advanced_page.add_modification_button.isEnabled()
    assert mixed_job.advanced_page.modification_rows() == ()


# =============================================================================
# Stage 4D — MSA / alignment
# =============================================================================


def test_a_new_protein_starts_on_the_automatic_default(protein_job):
    assert isinstance(_record(protein_job.state, "A").alignment, AlignmentAutomatic)
    assert _text("gui.alignment_state_automatic") in protein_job.advanced_page.alignment_label.text()


PROTEIN_MODES = [
    ("automatic", None, AlignmentAutomatic),
    ("free", None, AlignmentFree),
    ("unpaired", "inline", AlignmentUnpairedOnly),
    ("paired", "inline", AlignmentPairedOnly),
    ("both", "inline", AlignmentBoth),
]


@pytest.mark.parametrize("mode,kind,expected", PROTEIN_MODES)
def test_every_protein_alignment_mode_reaches_the_service(
    protein_job, monkeypatch, mode, kind, expected
):
    source = None if kind is None else ">query\nACDEFGHIKLMNPQRSTVWY"
    opened = _drive_alignment_form(monkeypatch, mode=mode, kind=kind, text=source)
    assert protein_job.advanced_page.change_alignment()

    alignment = _record(protein_job.state, "A").alignment
    assert isinstance(alignment, expected)
    if source is not None:
        assert isinstance(alignment.source, Inline)
        assert alignment.source.text == source
    # The offered modes are the console's own words, in its own order.
    assert opened[0].mode_combo.count() == len(PROTEIN_MODES)
    assert not opened[0].select_mode("provided")


RNA_MODES = [
    ("automatic", None, SingleAutomatic),
    ("free", None, SingleFree),
    ("provided", "inline", SingleProvided),
]


@pytest.mark.parametrize("mode,kind,expected", RNA_MODES)
def test_every_rna_alignment_mode_reaches_the_service(
    mixed_job, monkeypatch, mode, kind, expected
):
    mixed_job.entities_page.select_record("B")
    source = None if kind is None else ">query\nACGUACGU"
    opened = _drive_alignment_form(monkeypatch, mode=mode, kind=kind, text=source)
    assert mixed_job.advanced_page.change_alignment()

    alignment = _record(mixed_job.state, "B").alignment
    assert isinstance(alignment, expected)
    if source is not None:
        assert isinstance(alignment.source, Inline)
    assert opened[0].mode_combo.count() == len(RNA_MODES)
    assert not opened[0].select_mode("paired")


def test_an_inline_alignment_becomes_text_and_a_path_becomes_a_path_field(
    protein_job, monkeypatch, tmp_path
):
    _drive_alignment_form(monkeypatch, mode="unpaired", kind="inline", text=">q\nACDE")
    assert protein_job.advanced_page.change_alignment()
    assert _entry(_document(protein_job), "A")["unpairedMsa"] == ">q\nACDE"

    msa_path = _msa_a3m(tmp_path)
    _drive_alignment_form(monkeypatch, mode="unpaired", kind="file", path=msa_path)
    assert protein_job.advanced_page.change_alignment()
    body = _entry(_document(protein_job), "A")
    assert body["unpairedMsaPath"] == msa_path
    assert "unpairedMsa" not in body
    assert isinstance(_record(protein_job.state, "A").alignment.source, External)
    assert _text("gui.alignment_source_file") in protein_job.advanced_page.alignment_label.text()


def test_a_mode_without_a_source_sends_no_source_and_shows_no_source_controls(
    protein_job, monkeypatch
):
    opened = _drive_alignment_form(monkeypatch, mode="free")
    assert protein_job.advanced_page.change_alignment()
    assert opened[0]._collect() == ("free", "", "", "", "")
    assert not opened[0].source_row.isEnabled() or all(
        not radio.isEnabled() for _kind, radio in opened[0].source_radios
    )
    # A mode that carries no source writes the explicit "no MSA" empty string.
    assert _entry(_document(protein_job), "A")["unpairedMsa"] == ""


def test_switching_source_kind_keeps_the_imported_text_intact(
    protein_job, monkeypatch
):
    """Opening the form must not throw away the source the job already has."""
    assert (
        protein_job.state.set_alignment("A", "unpaired", inline_text=">q\nACDE").ok
    )
    protein_job.entities_page.select_record("A")
    opened = _drive_alignment_form(monkeypatch, mode="unpaired", cancel=True)
    assert not protein_job.advanced_page.change_alignment()

    dialog = opened[0]
    # The form opens on the job's own route and shows what it holds…
    assert dialog.current_mode() == "unpaired"
    assert dialog.current_source_kind() == "inline"
    assert dialog.inline_edit.toPlainText() == ">q\nACDE"
    # …and switching the route to a file does not clear that text behind the
    # user's back (nor fill the path field with it).
    for candidate, radio in dialog.source_radios:
        radio.setChecked(candidate == "file")
    assert dialog.inline_edit.toPlainText() == ">q\nACDE"
    assert dialog.path_edit.text() == ""


def test_a_source_carrying_mode_without_a_source_is_refused_in_the_form(
    protein_job, monkeypatch
):
    changes = _changes(protein_job.state)
    opened = _drive_alignment_form(monkeypatch, mode="unpaired", kind="inline", text="")
    assert not protein_job.advanced_page.change_alignment()
    assert "exactly one" in opened[0].error_text()
    assert isinstance(_record(protein_job.state, "A").alignment, AlignmentAutomatic)
    assert changes == []


def test_cancelling_the_alignment_form_changes_nothing(protein_job, monkeypatch):
    before = protein_job.state.configuration
    changes = _changes(protein_job.state)
    _drive_alignment_form(monkeypatch, cancel=True)
    assert not protein_job.advanced_page.change_alignment()
    assert protein_job.state.configuration is before
    assert changes == []


def test_dna_and_ligands_are_not_offered_alignment_controls(mixed_job):
    """DNA has no MSA field at all, so no control suggests otherwise."""
    for key in ("C", "D", "E"):
        mixed_job.entities_page.select_record(key)
        page = mixed_job.advanced_page
        assert not page.alignment_button.isEnabled()
        assert page.alignment_label.text() == ""
        assert "no alignment setting" in page._alignment_notice.text()
    mixed_job.entities_page.select_record("A")
    assert mixed_job.advanced_page.alignment_button.isEnabled()


def test_an_alignment_change_leaves_the_templates_alone(
    protein_job, monkeypatch, tmp_path
):
    assert protein_job.state.set_references(
        "A",
        references=(
            ReferenceInput(
                external_path=_template_cif(tmp_path, "t.cif"),
                pairs=((0, 0),),
            ),
        ),
    ).ok
    protein_job.entities_page.select_record("A")
    _drive_alignment_form(monkeypatch, mode="free")
    assert protein_job.advanced_page.change_alignment()

    references = _record(protein_job.state, "A").references
    assert isinstance(references, Explicit)
    assert len(references.items) == 1


# =============================================================================
# Stage 4E — protein templates / references
# =============================================================================


def test_a_new_protein_starts_with_search_allowed(protein_job):
    assert isinstance(_record(protein_job.state, "A").references, SearchAllowed)
    assert _text("gui.templates_state_search") in protein_job.advanced_page.templates_label.text()


def test_adding_a_template_file_writes_an_mmcif_path_through_the_service(
    protein_job, monkeypatch, tmp_path
):
    path = _template_cif(tmp_path)
    opened = _drive_template_dialog(
        monkeypatch, route="list", files=[path], pairs="0:1, 2:3"
    )
    assert protein_job.advanced_page.edit_templates()

    assert opened[0].current_route() == "list"
    templates = _entry(_document(protein_job), "A")["templates"]
    assert templates == [
        {"mmcifPath": path, "queryIndices": [0, 2], "templateIndices": [1, 3]}
    ]
    assert "1 provided" in protein_job.advanced_page.templates_label.text()
    assert protein_job.state.is_dirty


def test_two_template_files_are_kept_in_the_order_they_were_added(
    protein_job, monkeypatch, tmp_path
):
    first = _template_cif(tmp_path, "one.cif")
    second = _template_cif(tmp_path, "two.cif")
    _drive_template_dialog(
        monkeypatch, route="list", files=[first, second], pairs="0:0"
    )
    assert protein_job.advanced_page.edit_templates()
    templates = _entry(_document(protein_job), "A")["templates"]
    assert [item["mmcifPath"] for item in templates] == [first, second]


def test_the_explicit_no_template_state_is_distinct_from_search_allowed(
    protein_job, monkeypatch
):
    _drive_template_dialog(monkeypatch, route="none")
    assert protein_job.advanced_page.edit_templates()

    references = _record(protein_job.state, "A").references
    assert isinstance(references, Explicit)
    assert references.items == ()
    assert _entry(_document(protein_job), "A").get("templates") == []
    assert _text("gui.templates_state_none") in protein_job.advanced_page.templates_label.text()


def test_index_pairs_are_parsed_as_zero_based_query_template_pairs(
    protein_job, monkeypatch, tmp_path
):
    _drive_template_dialog(
        monkeypatch,
        route="list",
        files=[_template_cif(tmp_path, "t.cif")],
        pairs="0:5; 3:9",
    )
    assert protein_job.advanced_page.edit_templates()
    templates = _entry(_document(protein_job), "A")["templates"]
    assert templates[0]["queryIndices"] == [0, 3]
    assert templates[0]["templateIndices"] == [5, 9]


def test_a_pair_the_service_cannot_read_is_refused_and_keeps_the_dialog_open(
    protein_job, monkeypatch, tmp_path
):
    changes = _changes(protein_job.state)
    opened = _drive_template_dialog(
        monkeypatch,
        route="list",
        files=[_template_cif(tmp_path, "t.cif")],
        pairs="notanumber:1",
    )
    assert not protein_job.advanced_page.edit_templates()
    assert "not query:template" in opened[0].error_text()
    assert isinstance(_record(protein_job.state, "A").references, SearchAllowed)
    assert changes == []


def test_a_missing_template_file_is_refused_in_the_gui(
    protein_job, monkeypatch, tmp_path
):
    changes = _changes(protein_job.state)
    opened = _drive_template_dialog(
        monkeypatch,
        route="list",
        files=[str(tmp_path / "missing.cif")],
        pairs="0:0",
    )
    assert not protein_job.advanced_page.edit_templates()
    assert "the file does not exist" in opened[0].error_text()
    assert isinstance(_record(protein_job.state, "A").references, SearchAllowed)
    assert changes == []


def test_a_template_without_pairs_is_refused_in_the_gui(
    protein_job, monkeypatch, tmp_path
):
    changes = _changes(protein_job.state)
    opened = _drive_template_dialog(
        monkeypatch,
        route="list",
        files=[_template_cif(tmp_path)],
    )
    assert not protein_job.advanced_page.edit_templates()
    assert "At least one query:template pair is required" in opened[0].error_text()
    assert isinstance(_record(protein_job.state, "A").references, SearchAllowed)
    assert changes == []


def test_a_non_cif_template_file_is_refused_in_the_gui(
    protein_job, monkeypatch, tmp_path
):
    wrong = tmp_path / "template.txt"
    wrong.write_text("data_template\n", encoding="utf-8")
    opened = _drive_template_dialog(
        monkeypatch, route="list", files=[str(wrong)], pairs="0:0"
    )
    assert not protein_job.advanced_page.edit_templates()
    assert "must end in .cif or .mmcif" in opened[0].error_text()
    assert isinstance(_record(protein_job.state, "A").references, SearchAllowed)


def test_templates_are_only_offered_for_a_protein(mixed_job):
    for key in ("B", "C", "D", "E"):
        mixed_job.entities_page.select_record(key)
        assert not mixed_job.advanced_page.templates_button.isEnabled()
        assert mixed_job.advanced_page._templates_notice.text() == _text(
            "gui.templates_not_applicable"
        )
    mixed_job.entities_page.select_record("A")
    assert mixed_job.advanced_page.templates_button.isEnabled()


def test_cancelling_the_template_editor_changes_nothing(
    protein_job, monkeypatch, tmp_path
):
    path = _template_cif(tmp_path, "t.cif")
    assert protein_job.state.set_references(
        "A",
        references=(
            ReferenceInput(external_path=path, pairs=((0, 0),)),
        ),
    ).ok
    protein_job.entities_page.select_record("A")
    before = protein_job.state.configuration
    opened = _drive_template_dialog(monkeypatch, route="search", cancel=True)
    assert not protein_job.advanced_page.edit_templates()
    assert protein_job.state.configuration is before
    # The imported references were shown, unchanged, in the editor.
    assert opened[0].current_route() == "list"
    assert opened[0].entries() == (("file", path, "0:0"),)


# =============================================================================
# Stage 4F — the root custom CCD definition
# =============================================================================


def test_a_new_job_starts_with_no_custom_definition(protein_job):
    page = protein_job.ccd_page
    assert protein_job.state.configuration.component_definition is None
    assert page.ccd_mode() == "none"
    assert page.definition_mode() == "none"
    assert page.ccd_current_label.text() == _text("gui.ccd_active") % _text(
        "gui.ccd_active_none"
    )
    assert not page.ccd_clear_button.isEnabled()


def test_an_inline_definition_is_emitted_as_user_ccd(protein_job):
    page = protein_job.ccd_page
    page.choose_ccd_mode("inline")
    page.ccd_inline_edit.setPlainText("data_ATP\nloop_\n_atom.id\nN1\n")
    assert page.apply_ccd()

    document = _document(protein_job)
    assert "userCCD" in document
    assert "userCCDPath" not in document
    assert document["userCCD"].startswith("data_ATP")
    assert _text("gui.ccd_active_inline") % 4 in page.ccd_current_label.text()
    assert page.ccd_clear_button.isEnabled()
    assert protein_job.state.is_dirty


def test_an_external_definition_is_emitted_as_user_ccd_path(protein_job):
    page = protein_job.ccd_page
    page.choose_ccd_mode("file")
    page.ccd_path_edit.setText("ligand.cif")
    assert page.apply_ccd()

    document = _document(protein_job)
    assert document["userCCDPath"] == "ligand.cif"
    assert "userCCD" not in document
    # The path field's version requirement is stated, not enforced here.
    assert str(page.ccd_version_label.text()) == _text(
        "gui.ccd_path_version"
    ) % 3
    assert page.ccd_version_label.isVisibleTo(page)


def test_switching_between_inline_and_path_emits_only_one_representation(
    protein_job
):
    page = protein_job.ccd_page
    page.choose_ccd_mode("inline")
    page.ccd_inline_edit.setPlainText("data_X")
    assert page.apply_ccd()
    assert "userCCD" in _document(protein_job)

    page.choose_ccd_mode("file")
    page.ccd_path_edit.setText("x.cif")
    assert page.apply_ccd()
    document = _document(protein_job)
    assert document["userCCDPath"] == "x.cif"
    assert "userCCD" not in document, "the inline text must not survive a switch"

    page.choose_ccd_mode("inline")
    page.ccd_inline_edit.setPlainText("data_Y")
    assert page.apply_ccd()
    document = _document(protein_job)
    assert document["userCCD"] == "data_Y"
    assert "userCCDPath" not in document, "the path must not survive a switch"


def test_clearing_the_definition_removes_both_representations(protein_job):
    page = protein_job.ccd_page
    page.choose_ccd_mode("file")
    page.ccd_path_edit.setText("x.cif")
    assert page.apply_ccd()

    page.choose_ccd_mode("none")
    assert page.apply_ccd()  # "No custom definition" is the clear action
    assert protein_job.state.configuration.component_definition is None
    document = _document(protein_job)
    assert "userCCD" not in document and "userCCDPath" not in document
    assert page.ccd_current_label.text() == _text("gui.ccd_active") % _text(
        "gui.ccd_active_none"
    )


def test_the_clear_button_removes_an_existing_definition(protein_job):
    page = protein_job.ccd_page
    page.choose_ccd_mode("inline")
    page.ccd_inline_edit.setPlainText("data_X")
    assert page.apply_ccd()
    assert page.clear_ccd()
    assert protein_job.state.configuration.component_definition is None
    assert page.definition_mode() == "none"


def test_the_panel_shows_which_representation_the_job_carries(protein_job):
    page = protein_job.ccd_page
    page.choose_ccd_mode("file")
    page.ccd_path_edit.setText("x.cif")
    assert page.apply_ccd()
    assert page.definition_mode() == "file"
    assert page.ccd_current_label.text() == _text("gui.ccd_active") % (
        _text("gui.ccd_active_file") % "x.cif"
    )
    assert page.ccd_file_radio.isChecked()
    # The inline editor is not offered while the file route is the active one.
    assert not page.ccd_inline_edit.isVisibleTo(page)
    assert page.ccd_path_row.isVisibleTo(page)


def test_a_definition_that_names_no_representation_is_refused(protein_job):
    """Neither pasted text nor a file: the service's own refusal is shown."""
    page = protein_job.ccd_page
    page.choose_ccd_mode("inline")
    page.ccd_inline_edit.setPlainText("")
    before = protein_job.state.configuration
    changes = _changes(protein_job.state)
    assert not page.apply_ccd()
    assert "exactly one" in protein_job.last_problem_text()
    assert protein_job.state.configuration is before
    assert changes == []


def test_an_unrelated_refresh_keeps_a_definition_being_typed(protein_job):
    """A refresh must not overwrite the text the user is still writing."""
    page = protein_job.ccd_page
    page.choose_ccd_mode("inline")
    page.ccd_inline_edit.setPlainText("data_TYPING")
    protein_job.refresh()
    assert page.ccd_inline_edit.toPlainText() == "data_TYPING"


# =============================================================================
# Stage 4G — covalent linkages
# =============================================================================


def test_the_bond_section_asks_for_two_entities_first(job):
    assert job.state.add_record("protein", sequence="ACDEFG").ok
    page = job.bonds_page
    assert page.bond_rows() == ()
    assert not page.add_bond_button.isEnabled()
    assert page._bond_notice.text() == _text("gui.bond_needs_entities")

    assert job.state.add_record("ligand", representation="ATP", representation_kind="ccd").ok
    assert page.add_bond_button.isEnabled()
    assert page._bond_notice.text() == ""


def test_adding_a_bond_goes_through_add_linkage_and_emits_bonded_atom_pairs(
    mixed_job, monkeypatch
):
    changes = _changes(mixed_job.state)
    opened = _drive_bond_dialog(
        monkeypatch, left=("A", 3, "SG"), right=("E", 1, "OXT")
    )
    assert mixed_job.bonds_page.add_bond()
    assert len(changes) == 1

    # The form offered real identifiers, never a hand-typed internal key.
    offered = [
        opened[0].left_key.itemData(index)
        for index in range(opened[0].left_key.count())
    ]
    assert offered == ["A", "B", "C", "D", "E"]
    assert _document(mixed_job)["bondedAtomPairs"] == [
        [["A", 3, "SG"], ["E", 1, "OXT"]]
    ]
    protein = _record(mixed_job.state, "A")
    ligand = _record(mixed_job.state, "E")
    assert mixed_job.bonds_page.bond_pair_texts() == (
        _text("gui.bond_pair_text")
        % (
            _text("gui.bond_endpoint_text")
            % ("A (%s)" % family_label(protein), 3, "SG"),
            _text("gui.bond_endpoint_text")
            % ("E (%s)" % family_label(ligand), 1, "OXT"),
        ),
    )


def test_an_endpoint_the_registry_does_not_know_is_refused(
    mixed_job, monkeypatch
):
    changes = _changes(mixed_job.state)
    opened = _drive_bond_dialog(
        monkeypatch, left=("Z", 1, "SG"), right=("E", 1, "OXT")
    )
    assert not mixed_job.bonds_page.add_bond()
    assert "Z" in opened[0].error_text()
    assert mixed_job.state.configuration.linkages == ()
    assert changes == []


def test_an_endpoint_without_an_atom_name_is_refused(mixed_job, monkeypatch):
    opened = _drive_bond_dialog(monkeypatch, left=("A", 1, ""), right=("E", 1, "OXT"))
    assert not mixed_job.bonds_page.add_bond()
    assert "atom" in opened[0].error_text()
    assert mixed_job.state.configuration.linkages == ()


def test_cancelling_the_bond_form_changes_nothing(mixed_job, monkeypatch):
    before = mixed_job.state.configuration
    changes = _changes(mixed_job.state)
    _drive_bond_dialog(monkeypatch, cancel=True)
    assert not mixed_job.bonds_page.add_bond()
    assert mixed_job.state.configuration is before
    assert changes == []


def test_imported_bonds_are_listed_and_removable(mixed_job, monkeypatch):
    assert mixed_job.state.add_linkage("A", 2, "SG", "E", 1, "OXT").ok
    mixed_job.refresh()
    page = mixed_job.bonds_page
    assert len(page.bond_rows()) == 1
    assert "residue 2" in page.bond_rows()[0][0]

    page.bond_table.selectRow(0)
    asked = _answer_removal(monkeypatch, page, "bond_confirmer")
    assert page.remove_selected_bond()

    protein = family_label(_record(mixed_job.state, "A"))
    ligand = family_label(_record(mixed_job.state, "E"))
    assert len(asked) == 1
    assert "A (%s)" % protein in asked[0] and "E (%s)" % ligand in asked[0]
    assert "residue 2, atom SG" in asked[0] and "residue 1, atom OXT" in asked[0]
    assert mixed_job.state.configuration.linkages == ()
    # No linkages at all: the field is unset, never emitted as an empty list.
    assert "bondedAtomPairs" not in _document(mixed_job)


def test_cancelling_the_bond_removal_changes_nothing(mixed_job, monkeypatch):
    assert mixed_job.state.add_linkage("A", 2, "SG", "E", 1, "OXT").ok
    mixed_job.refresh()
    page = mixed_job.bonds_page
    page.bond_table.selectRow(0)
    _answer_removal(monkeypatch, page, "bond_confirmer", answer=False)

    before = mixed_job.state.configuration
    assert not page.remove_selected_bond()
    assert mixed_job.state.configuration is before
    assert len(page.bond_rows()) == 1


def test_removing_without_a_selection_says_so(mixed_job):
    assert mixed_job.state.add_linkage("A", 2, "SG", "E", 1, "OXT").ok
    mixed_job.refresh()
    assert not mixed_job.bonds_page.remove_selected_bond()
    assert mixed_job.last_problem_text() == _text("gui.bond_select_first")
    assert len(mixed_job.state.configuration.linkages) == 1


# =============================================================================
# Stage 4B — a version-sensitive field, seen from the window
# =============================================================================


def test_a_version_feature_conflict_is_visible_and_clears_on_a_higher_version(
    protein_job, monkeypatch, tmp_path
):
    """Readiness, the finding and the preview agree; the version then fixes it."""
    settings = protein_job.settings_page
    assert settings.version_combo.findData(1) >= 0
    settings.version_combo.setCurrentIndex(settings.version_combo.findData(1))
    assert settings.apply_version()

    # A real file, so the *version* finding is the only blocking one: the
    # missing-file preflight would otherwise refuse the same document and the
    # test could not tell the two apart.
    msa_path = _msa_a3m(tmp_path)
    _drive_alignment_form(monkeypatch, mode="unpaired", kind="file", path=msa_path)
    assert protein_job.advanced_page.change_alignment()

    status = protein_job.state.status()
    assert not status.ready
    conflict = [f for f in status.blocking if f.rule_id == "R-VER-002"]
    assert conflict, [f.rule_id for f in status.blocking]
    assert "version 1" in conflict[0].user_message
    assert "unpairedMsaPath" in conflict[0].user_message
    assert _document(protein_job) is None
    assert _text("gui.preview_unavailable") in protein_job.preview_page.reason_text()

    # Raising the version — the user's explicit choice — clears it.
    settings.version_combo.setCurrentIndex(settings.version_combo.findData(2))
    assert settings.apply_version()
    assert protein_job.state.status().ready
    assert _entry(_document(protein_job), "A")["unpairedMsaPath"] == msa_path


def test_the_version_is_never_changed_behind_the_users_back(
    protein_job, monkeypatch, tmp_path
):
    settings = protein_job.settings_page
    settings.version_combo.setCurrentIndex(settings.version_combo.findData(1))
    assert settings.apply_version()

    _drive_template_dialog(
        monkeypatch,
        route="list",
        files=[_template_cif(tmp_path, "t.cif")],
        pairs="0:0",
    )
    assert protein_job.advanced_page.edit_templates()

    assert isinstance(_record(protein_job.state, "A").references, Explicit)
    pinned = protein_job.state.configuration.format_target.version_selection
    # The pin is exactly what the user chose — never silently promoted.
    assert isinstance(pinned, Pinned) and pinned.version == 1
    assert protein_job.state.status().blocking, "still blocked, version untouched"
    assert not protein_job.state.status().ready
    assert protein_job.state.preview_json()[1]


# =============================================================================
# Stage 4H — a ligand edit is one service call, or none
# =============================================================================


def test_a_ligand_edit_is_one_call(mixed_job):
    """A representation change and a description change land together."""
    # A description is a v4 field, so the pin is raised the way a user would.
    assert mixed_job.state.set_json_version(4).ok
    before = _record(mixed_job.state, "E")
    outcome = mixed_job.state.update_component_record(
        "E", codes="ATP", description="adenosine triphosphate"
    )
    assert outcome.ok
    assert _record(mixed_job.state, "E") is not before
    body = _entry(_document(mixed_job), "E")
    assert body["ccdCodes"] == ["ATP"]
    assert body["description"] == "adenosine triphosphate"


def test_a_refused_ligand_edit_leaves_neither_field_applied(mixed_job):
    """The Stage 3 two-call route could half-apply; one call cannot."""
    before = mixed_job.state.configuration
    outcome = mixed_job.state.update_component_record(
        "E", codes="ATP", notation="CCO"
    )
    assert not outcome.ok
    assert mixed_job.state.configuration is before
    body = _entry(_document(mixed_job), "E")
    assert "description" not in body
    assert body["ccdCodes"] == ["ATP"]


def test_a_ligand_edit_refused_in_the_form_applies_no_part_of_it(
    mixed_job, monkeypatch
):
    """Typing a new description with a refused code changes nothing at all."""
    assert mixed_job.state.set_json_version(4).ok
    page = mixed_job.entities_page
    assert page.select_record("E")
    before = mixed_job.state.configuration
    changes = _changes(mixed_job.state)
    opened = _drive_ligand_form(monkeypatch, kind="ccd", value="", description="edited")

    assert not page.edit_selected()
    assert opened[0].result() != QDialog.Accepted
    assert opened[0].error_text()
    assert mixed_job.state.configuration is before
    body = _entry(_document(mixed_job), "E")
    assert body["ccdCodes"] == ["ATP"]
    assert "description" not in body
    assert changes == []


def test_a_ligand_edit_accepted_in_the_form_applies_both_fields(
    mixed_job, monkeypatch
):
    assert mixed_job.state.set_json_version(4).ok
    page = mixed_job.entities_page
    assert page.select_record("E")
    changes = _changes(mixed_job.state)
    _drive_ligand_form(monkeypatch, kind="smiles", value="CCO", description="ethanol")

    assert page.edit_selected()
    assert len(changes) == 1
    body = _entry(_document(mixed_job), "E")
    assert body["smiles"] == "CCO"
    assert body["description"] == "ethanol"


# =============================================================================
# §12 — the sequence-input contract: a hint, never a silent normalisation
# =============================================================================


def test_the_add_form_asks_for_a_plain_unwrapped_sequence(protein_job, monkeypatch):
    opened = _drive_sequence_form(monkeypatch, cancel=True)
    assert not protein_job.entities_page.add_protein()
    assert opened[0].hint_label.text() == _text("gui.sequence_add_hint")
    assert "no FASTA header" in opened[0].hint_label.text()
    assert "no line breaks" in opened[0].hint_label.text()


def test_the_edit_form_repeats_the_plain_sequence_requirement(
    protein_job, monkeypatch
):
    page = protein_job.entities_page
    assert page.select_record("A")
    opened = _drive_sequence_form(monkeypatch, cancel=True)
    assert not page.edit_selected()
    assert "no FASTA header and no line breaks" in opened[0].hint_label.text()


def test_a_wrapped_paste_is_still_refused_by_the_model(protein_job, monkeypatch):
    """Nothing is stripped or unwrapped: the model's own refusal is shown."""
    page = protein_job.entities_page
    assert page.select_record("A")
    opened = _drive_sequence_form(monkeypatch, sequence="ACDEFG\nHIKLMN")
    assert not page.edit_selected()
    assert opened[0].error_text()
    assert _record(protein_job.state, "A").sequence.text == "ACDEFGHIKLMNPQRSTVWY"
    assert "\n" not in _record(protein_job.state, "A").sequence.text


# =============================================================================
# File pickers: a path is chosen, never typed, and nothing is read here
# =============================================================================


def _picker(path):
    """Stand in for the platform file dialog's one static method."""

    class _Dialog:
        @staticmethod
        def getOpenFileName(*args, **kwargs):
            return (path, "")

    return _Dialog


def test_the_ccd_browse_button_puts_the_chosen_file_in_the_field(
    protein_job, monkeypatch
):
    """The CCD path control is filled from the picker, not by typing."""
    page = protein_job.ccd_page
    page.choose_ccd_mode("file")
    monkeypatch.setattr(advanced_page, "QFileDialog", _picker("chosen.cif"))

    assert page.browse_ccd_file() == "chosen.cif"
    assert page.ccd_path_edit.text() == "chosen.cif"
    # Choosing a file only fills the field; the service is called on Apply.
    assert protein_job.state.configuration.component_definition is None


def test_a_cancelled_ccd_pick_leaves_the_field_as_it_was(protein_job, monkeypatch):
    page = protein_job.ccd_page
    page.choose_ccd_mode("file")
    page.ccd_path_edit.setText("kept.cif")
    monkeypatch.setattr(advanced_page, "QFileDialog", _picker(""))

    assert page.browse_ccd_file() == ""
    assert page.ccd_path_edit.text() == "kept.cif"


def test_the_alignment_browse_button_fills_the_path_field(monkeypatch):
    dialog = AlignmentFormDialog(
        None,
        title="Alignment",
        accept_text="Save",
        apply=lambda *values: None,
        modes=(('menu.msa_mode_unpaired', "unpaired"),),
        mode="unpaired",
        source_kind="file",
    )
    monkeypatch.setattr(advanced_forms, "QFileDialog", _picker("msa.a3m"))

    dialog.browse()

    assert dialog.path_edit.text() == "msa.a3m"


def test_the_template_add_file_button_adds_a_row_for_the_chosen_file(monkeypatch):
    dialog = TemplateEditorDialog(
        None,
        title="Templates",
        accept_text="Save",
        apply=lambda *values: None,
        mode="list",
    )
    monkeypatch.setattr(advanced_forms, "QFileDialog", _picker("model.cif"))

    dialog.add_file()

    assert dialog.entries() == (("file", "model.cif", ""),)
    assert dialog.current_route() == "list"


# -- both-mode MSA: one source per side ---------------------------------------


def test_both_mode_can_give_each_side_its_own_source(protein_job, monkeypatch, tmp_path):
    """The paired side is no longer forced to reuse the unpaired file."""
    paired = _msa_a3m(tmp_path, "paired.a3m")
    unpaired_text = ">q\nACDE"
    _drive_alignment_form(
        monkeypatch,
        mode="both",
        kind="inline",
        text=unpaired_text,
        paired_kind="file",
        paired_path=paired,
    )

    assert protein_job.advanced_page.change_alignment()

    body = _entry(_document(protein_job), "A")
    assert body["unpairedMsa"] == unpaired_text
    assert body["pairedMsaPath"] == paired
    assert "pairedMsa" not in body
    record = _record(protein_job.state, "A")
    assert record.alignment.paired_source.path.raw == paired


def test_both_mode_without_a_paired_choice_still_reuses_the_unpaired_source(
    protein_job, monkeypatch
):
    """The default is the historical single-source behaviour, unchanged."""
    opened = _drive_alignment_form(
        monkeypatch, mode="both", kind="inline", text=">q\nACDE"
    )
    assert protein_job.advanced_page.change_alignment()
    assert opened[0].current_paired_kind() == "same"
    assert opened[0]._collect()[3:] == ("", "")
    body = _entry(_document(protein_job), "A")
    assert body["unpairedMsa"] == ">q\nACDE"
    assert body["pairedMsa"] == ">q\nACDE"


def test_the_form_reopens_with_both_sources_intact(protein_job, monkeypatch, tmp_path):
    """A stored paired side is shown again, not silently collapsed."""
    paired = _msa_a3m(tmp_path, "paired.a3m")
    assert protein_job.state.set_alignment(
        "A",
        "both",
        inline_text=">q\nACDE",
        paired_external_path=paired,
    ).ok
    protein_job.entities_page.select_record("A")
    opened = _drive_alignment_form(monkeypatch, mode="both", cancel=True)
    assert not protein_job.advanced_page.change_alignment()

    dialog = opened[0]
    assert dialog.current_mode() == "both"
    assert dialog.current_source_kind() == "inline"
    assert dialog.inline_edit.toPlainText() == ">q\nACDE"
    assert dialog.current_paired_kind() == "file"
    assert dialog.paired_path_edit.text() == paired


def test_the_paired_controls_appear_only_for_both_mode(monkeypatch):
    dialog = AlignmentFormDialog(
        None,
        title="Alignment",
        accept_text="Save",
        apply=lambda *values: None,
        modes=(('menu.msa_mode_unpaired', "unpaired"), ('menu.msa_mode_both', "both")),
        mode="unpaired",
        source_kind="inline",
    )
    assert not dialog.paired_block.isVisibleTo(dialog)
    dialog.select_mode("both")
    assert dialog.paired_block.isVisibleTo(dialog)
    assert [kind for kind, _radio in dialog.paired_radios] == ["same", "inline", "file"]


# -- inline mmCIF templates: authoring and preservation -----------------------


def test_an_inline_template_can_be_authored_in_the_window(protein_job, monkeypatch, tmp_path):
    content = pathlib.Path(_template_cif(tmp_path)).read_text(encoding="utf-8")
    _drive_template_dialog(monkeypatch, route="list", inline=content, pairs="0:1")

    assert protein_job.advanced_page.edit_templates()

    body = _entry(_document(protein_job), "A")
    template = body["templates"][0]
    assert "mmcif" in template and "mmcifPath" not in template
    assert template["mmcif"].startswith("data_template")
    assert template["queryIndices"] == [0]
    assert template["templateIndices"] == [1]


def test_accepting_the_dialog_does_not_turn_an_inline_template_into_a_path(
    protein_job, monkeypatch, tmp_path
):
    """The imported representation survives: no row, no silent conversion."""
    content = pathlib.Path(_template_cif(tmp_path)).read_text(encoding="utf-8")
    assert protein_job.state.set_references(
        "A", references=(ReferenceInput(inline_text=content, pairs=((0, 1),)),)
    ).ok
    protein_job.entities_page.select_record("A")

    opened = _drive_template_dialog(monkeypatch, route="list", pairs="0:1")
    assert protein_job.advanced_page.edit_templates()

    # The editor showed the inline template as an inline row…
    rows = opened[0].entries()
    assert len(rows) == 1 and rows[0][0] == "inline"
    assert rows[0][1].startswith("data_template")
    # …and saving kept it inline in the document.
    template = _entry(_document(protein_job), "A")["templates"][0]
    assert "mmcif" in template and "mmcifPath" not in template


def test_a_template_row_keeps_its_own_kind(monkeypatch):
    dialog = TemplateEditorDialog(
        None,
        title="Templates",
        accept_text="Save",
        apply=lambda *values: None,
        mode="list",
        entries=(("file", "model.cif", "0:1"), ("inline", "data_x\n#\n", "0:2")),
    )
    assert [row[0] for row in dialog.entries()] == ["file", "inline"]
    assert dialog.entries()[1][1].startswith("data_x")
