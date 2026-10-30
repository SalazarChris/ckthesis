"""Stage 3: adding, inspecting, editing and deleting entities.

Every test here drives the window's own widgets and then reads the *service*
state: the record identifiers, sequences and descriptions that
``ConfigurationService`` holds, and the JSON preview that
``GenerationService.show_json`` produces. A test that only checked the page's
labels would not show that the mutation went through the service, and the
whole point of this stage is that the GUI never builds a record itself.

The two form dialogs are modal, so the helper functions below stand in for
their modal loop: they fill the **real** dialog's widgets and call the real
``accept``, which runs the page's ``apply`` callable and the dialog's own
refusal handling. Nothing is mocked except ``exec``.
"""

from __future__ import annotations

import json
import pathlib

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtWidgets import QDialog  # noqa: E402

from configbuilder.identity import EntityId, IdentityError  # noqa: E402
from configbuilder.model import (  # noqa: E402
    ByCode,
    ByNotation,
    ExplicitEmpty,
    Pinned,
    Present,
    Unset,
    reverse_complement,
)
from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.dialogs import (  # noqa: E402
    LigandFormDialog,
    SequenceFormDialog,
)
from configbuilder.ui.render.qt.dialogs.entity_forms import MAX_LIGAND_COPIES  # noqa: E402
from configbuilder.ui.render.qt.pages import entities as entities_module  # noqa: E402


# -- the two modal forms, driven through their real widgets -------------------


def _drive_sequence_form(
    monkeypatch, sequence=None, description=None, cancel=False, single_stranded=False
):
    """Answer the sequence form. Returns the dialogs the page built."""
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        if sequence is not None:
            dialog.sequence_edit.setPlainText(sequence)
        if description is not None:
            dialog.description_edit.setText(description)
        if single_stranded and dialog.single_radio is not None:
            dialog.single_radio.setChecked(True)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(SequenceFormDialog, "exec", fake_exec)
    return opened


def _drive_ligand_form(
    monkeypatch, kind="ccd", value=None, copies=None, description=None, cancel=False
):
    """Answer the ligand form: pick a radio, fill the fields, submit."""
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        (dialog.smiles_radio if kind == "smiles" else dialog.ccd_radio).setChecked(True)
        if value is not None:
            dialog.value_edit.setText(value)
        if copies is not None:
            dialog.copies_spin.setValue(copies)
        if description is not None:
            dialog.description_edit.setText(description)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(LigandFormDialog, "exec", fake_exec)
    return opened


def _answer_delete(monkeypatch, page, answer=True):
    """Answer the delete confirmation; returns the questions it was asked."""
    asked = []

    def confirmer(parent, message):
        asked.append(message)
        return answer

    monkeypatch.setattr(page, "delete_confirmer", confirmer)
    return asked


def _ids(window):
    return [record.ids.primary.value for record in window.state.configuration.records]


def _entry_ids(text):
    """The identifiers of the previewed document, in serialization order."""
    return [
        next(iter(entry.values()))["id"] for entry in json.loads(text)["sequences"]
    ]


@pytest.fixture
def job(window):
    """The window over a fresh, empty job — the state adds start from."""
    window.state.new_job()
    return window


@pytest.fixture
def page(job):
    return job.entities_page


# -- 1/2: add protein and RNA ------------------------------------------------


def test_adding_a_protein_uses_the_service_record_and_selects_it(page, monkeypatch):
    _drive_sequence_form(monkeypatch, sequence="ACDEFGHIK")
    assert page.add_protein() is True

    [record] = page.state.configuration.records
    assert record.ids.primary.value == "A"
    assert record.sequence.text == "ACDEFGHIK"
    # Nothing was supplied for the description, so it stays *unset* — not an
    # explicitly empty description, which is a different model value.
    assert isinstance(record.description, Unset)
    assert page.model.rowCount() == 1
    assert page.selected_record_key() == "A"
    # The facts card reports the length; the sequence itself is not rendered.
    assert page.detail_text("gui.entity_length") == _text(
        "gui.entity_length_value"
    ) % 9


def test_adding_an_rna_chain_registers_the_family_correctly(page, monkeypatch):
    _drive_sequence_form(monkeypatch, sequence="ACGUACGU")
    assert page.add_rna() is True

    [record] = page.state.configuration.records
    assert record.sequence.text == "ACGUACGU"
    assert record.sequence.family == "rna"
    assert page.detail_title().startswith("A")
    assert page.detail_text("gui.entity_length") == _text(
        "gui.entity_length_value"
    ) % 8
    row = page.model.row_at(0)
    assert row.family == _text("menu.family_rna")


# -- 3: add DNA, as the duplex the service builds -----------------------------


def test_adding_dna_shows_both_strands_the_service_built(page, monkeypatch):
    _drive_sequence_form(monkeypatch, sequence="ATGC")
    assert page.add_dna() is True

    assert _ids(page) == ["A", "B"]
    given, partner = page.state.configuration.records
    assert given.sequence.text == "ATGC"
    assert partner.sequence.text == "GCAT"
    assert page.model.rowCount() == 2
    # The pane names the other half from the model's own pairing, not from a
    # complement the GUI calculated.
    page.select_record("A")
    assert page.detail_text("gui.entity_partner_label") == _text("gui.entity_partner") % "B"
    page.select_record("B")
    assert page.detail_text("gui.entity_partner_label") == _text("gui.entity_partner") % "A"


def test_the_dna_form_explains_the_duplex_before_it_is_added(page, monkeypatch):
    opened = _drive_sequence_form(monkeypatch, sequence="ATGC")
    assert page.add_dna() is True
    assert opened[0].windowTitle() == _text("gui.dialog_add_dna")
    # The choice exists and defaults to the duplex, as the service does.
    assert opened[0].duplex_group is not None
    assert opened[0].paired_radio.isChecked()
    assert opened[0].duplex_selected() is True
    # One sequence in, two records out, and the form said so.
    assert len(page.state.configuration.records) == 2


def test_the_dna_form_can_add_a_single_strand(page, monkeypatch):
    """The console's own question, now in the window: one strand, one record."""
    _drive_sequence_form(monkeypatch, sequence="ATGC", single_stranded=True)

    assert page.add_dna() is True

    assert _ids(page) == ["A"]
    assert page.state.configuration.records[0].sequence.text == "ATGC"
    assert page.model.rowCount() == 1
    # A lone strand says so, rather than naming a partner it does not have.
    page.select_record("A")
    assert page.detail_text("gui.entity_partner_label") == _text("gui.entity_no_partner")


def test_only_dna_offers_the_duplex_choice(page, monkeypatch):
    """Protein and RNA have no complement; their forms carry no such control."""
    opened = _drive_sequence_form(monkeypatch, sequence="ACDE")
    assert page.add_protein() is True
    assert opened[0].duplex_group is None
    assert opened[0].duplex_selected() is True  # the service's default

    opened = _drive_sequence_form(monkeypatch, sequence="ACGU")
    assert page.add_rna() is True
    assert opened[0].duplex_group is None


# -- 4: editing DNA goes through the service's own propagation ----------------


def test_editing_a_strand_updates_its_partner_through_the_service(page, monkeypatch):
    _drive_sequence_form(monkeypatch, sequence="ATGC")
    page.add_dna()
    page.select_record("A")

    _drive_sequence_form(monkeypatch, sequence="AAGC")
    assert page.edit_selected() is True

    given, partner = page.state.configuration.records
    assert given.sequence.text == "AAGC"
    assert partner.sequence.text == reverse_complement(given.sequence).text
    assert _ids(page) == ["A", "B"]


def test_the_gui_module_computes_no_complement_of_its_own():
    """The complement exists in the model only; the page calls the service."""
    source = pathlib.Path(entities_module.__file__).read_text(encoding="utf-8")
    assert "reverse_complement" not in source
    assert "ATGC" not in source and "GCAT" not in source


# -- 5: deleting a duplex ------------------------------------------------------


def test_cancelling_a_dna_deletion_keeps_both_strands(page, monkeypatch):
    _drive_sequence_form(monkeypatch, sequence="ATGC")
    page.add_dna()
    page.select_record("A")
    asked = _answer_delete(monkeypatch, page, answer=False)

    assert page.delete_selected() is False
    assert _ids(page) == ["A", "B"]
    assert len(asked) == 1
    # The question names what else goes with the record.
    assert _text("gui.delete_duplex") % ("A", "B") == asked[0]


def test_confirming_a_dna_deletion_removes_the_pair(page, monkeypatch):
    _drive_sequence_form(monkeypatch, sequence="ATGC")
    page.add_dna()
    page.select_record("B")
    asked = _answer_delete(monkeypatch, page, answer=True)

    assert page.delete_selected() is True
    assert page.state.configuration.records == ()
    assert asked[0] == _text("gui.delete_duplex") % ("B", "A")
    assert page.model.rowCount() == 0


# -- 6: an imported lone strand is handled as the service defines it ----------


def _import(window, document, tmp_path):
    """Commit a document the way an approved import does."""
    path = tmp_path / "imported.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    window.state.commit_import(str(path))
    return window


def test_an_imported_lone_strand_gets_no_invented_partner(window, monkeypatch, tmp_path):
    _import(
        window,
        {
            "name": "lone",
            "modelSeeds": [1],
            "sequences": [{"dna": {"id": "A", "sequence": "ATGC"}}],
            "dialect": "alphafold3",
            "version": 3,
        },
        tmp_path,
    )
    page = window.entities_page
    assert _ids(window) == ["A"]
    page.select_record("A")
    assert page.detail_text("gui.entity_partner_label") == _text("gui.entity_no_partner")

    # Editing it changes only it: no partner exists to propagate to.
    _drive_sequence_form(monkeypatch, sequence="GGGG")
    assert page.edit_selected() is True
    assert _ids(window) == ["A"]
    assert window.state.configuration.records[0].sequence.text == "GGGG"

    # Deleting it removes only it.
    _answer_delete(monkeypatch, page, answer=True)
    assert page.delete_selected() is True
    assert window.state.configuration.records == ()


# -- 7/8: ligands -------------------------------------------------------------


def test_adding_a_ligand_by_ccd_code_records_the_code(page, monkeypatch):
    _drive_ligand_form(monkeypatch, kind="ccd", value="ATP")
    assert page.add_ligand() is True

    [record] = page.state.configuration.records
    assert isinstance(record.representation, ByCode)
    assert [code.value for code in record.representation.codes] == ["ATP"]
    assert len(record.ids) == 1
    # A ligand has no sequence, so the pane shows its representation instead.
    assert page.detail_text("gui.entity_representation") == _text("gui.representation_ccd") % "ATP"


def test_a_multi_component_ccd_ligand_keeps_every_component(page, monkeypatch):
    _drive_ligand_form(monkeypatch, kind="ccd", value="NAG NAG BMA")
    assert page.add_ligand() is True

    [record] = page.state.configuration.records
    assert [code.value for code in record.representation.codes] == ["NAG", "NAG", "BMA"]
    assert page.detail_text("gui.entity_representation") == (
        _text("gui.representation_ccd") % "NAG, NAG, BMA"
    )


def test_an_ion_like_ccd_code_is_a_ligand(page, monkeypatch):
    _drive_ligand_form(monkeypatch, kind="ccd", value="ZN")
    assert page.add_ligand() is True

    [record] = page.state.configuration.records
    assert isinstance(record.representation, ByCode)
    assert [code.value for code in record.representation.codes] == ["ZN"]
    assert page.model.row_at(0).family == _text("menu.family_ligand")


def test_adding_a_ligand_by_smiles_records_a_notation(page, monkeypatch):
    _drive_ligand_form(monkeypatch, kind="smiles", value="CCO")
    assert page.add_ligand() is True

    [record] = page.state.configuration.records
    assert isinstance(record.representation, ByNotation)
    assert record.representation.text == "CCO"


def test_the_representation_radios_are_mutually_exclusive(page, monkeypatch):
    opened = _drive_ligand_form(monkeypatch, kind="ccd", value="ATP")
    assert page.add_ligand() is True
    dialog = opened[0]

    assert dialog.ccd_radio.isChecked() is True
    assert dialog.smiles_radio.isChecked() is False
    # One group, so choosing one *is* unchoosing the other: the service's
    # "codes or a notation, not both" cannot be violated from this form.
    assert len(dialog.representation_group.buttons()) == 2
    dialog.smiles_radio.setChecked(True)
    assert dialog.ccd_radio.isChecked() is False
    assert isinstance(page.state.configuration.records[0].representation, ByCode)


def test_the_copy_spin_box_offers_a_bounded_whole_number(page, monkeypatch):
    opened = _drive_ligand_form(monkeypatch, kind="ccd", value="NAG", copies=3)
    assert page.add_ligand() is True
    dialog = opened[0]
    assert dialog.copies_spin.minimum() == 1
    assert dialog.copies_spin.maximum() == MAX_LIGAND_COPIES
    assert [entity.value for entity in page.state.configuration.records[0].ids.ids] == [
        "A",
        "B",
        "C",
    ]


# -- 9: multi-copy ligands ----------------------------------------------------


def test_a_multi_copy_ligand_shows_and_releases_every_identifier(page, monkeypatch):
    _drive_ligand_form(monkeypatch, kind="ccd", value="NAG", copies=2)
    assert page.add_ligand() is True
    row = page.model.row_at(0)
    assert row.ids == "A, B"
    assert row.record_key == "A"

    asked = _answer_delete(monkeypatch, page, answer=True)
    assert page.delete_selected() is True
    assert page.state.configuration.records == ()
    assert asked[0] == _text("gui.delete_copies") % ("A, B", 2)
    # Released through the service, so the identifiers are free again.
    identity = page.state.configuration.identity
    assert identity.is_taken("A") is False
    assert identity.is_taken("B") is False
    with pytest.raises(IdentityError):
        identity.multiplicity_of(EntityId("B"))


# -- 10: editing sequence, description and the version explanation ------------


def test_editing_a_description_keeps_the_unset_explicitly_empty_distinction(
    filled, reviewed, monkeypatch
):
    page = reviewed.entities_page
    assert isinstance(filled.configuration.records[0].description, Unset)
    page.select_record("A")

    _drive_sequence_form(monkeypatch, sequence="ACDEFGHIKLMNPQRSTVWY", description="")
    assert page.edit_selected() is True
    # Untouched text is passed as None, so an unset description stays unset.
    assert isinstance(page.state.configuration.records[0].description, Unset)

    _drive_sequence_form(monkeypatch, sequence="ACDEFGHIKLMNPQRSTVWY", description="tagged")
    assert page.edit_selected() is True
    assert page.state.configuration.records[0].description == Present("tagged")

    _drive_sequence_form(monkeypatch, sequence="ACDEFGHIKLMNPQRSTVWY", description="")
    assert page.edit_selected() is True
    assert isinstance(page.state.configuration.records[0].description, ExplicitEmpty)


def test_a_supplied_description_on_a_version_three_job_explains_itself(
    job, page, monkeypatch
):
    opened = _drive_sequence_form(monkeypatch, sequence="ACDEFG", description="tagged")
    assert page.add_protein() is True
    dialog = opened[0]

    # The form explained the version requirement before submitting anything.
    assert dialog.warning_text() == _text("gui.description_version_warning") % (3, 4)
    # The description is kept, and the version is untouched: nothing was
    # silently upgraded and nothing was silently discarded.
    assert page.state.configuration.records[0].description == Present("tagged")
    selection = page.state.configuration.format_target.version_selection
    assert isinstance(selection, Pinned)
    assert selection.version == 3
    # Readiness, findings and generation now tell one story (Stage 4): the
    # job is not ready, the version row names the version the description
    # needs, and the preview refuses with the readiness verdict instead of
    # reaching the transform's feature check.
    status = page.state.status()
    assert status.ready is False
    assert {finding.rule_id for finding in status.blocking} == {"R-VER-002"}
    assert "version 4" in status.field("version").message
    text, reason = page.state.preview_json()
    assert text is None
    assert "not ready" in reason
    assert "not ready" in job.preview_page.reason_text()

    # Raising the version is the user's explicit choice, and it clears the
    # conflict: the same job becomes ready and previews again.
    assert page.state.set_json_version(4).ok
    assert page.state.status().ready is True
    assert page.state.preview_json()[0] is not None


def test_the_version_explanation_stays_hidden_without_a_description(job, page, monkeypatch):
    opened = _drive_sequence_form(monkeypatch, sequence="ACDEFG")
    assert page.add_protein() is True
    assert opened[0].warning_text() == ""


# -- 11: a refused operation is reported, not applied -------------------------


def test_a_refused_sequence_shows_the_service_reason_and_changes_nothing(
    job, page, monkeypatch
):
    opened = _drive_sequence_form(monkeypatch, sequence="ACDEFG1")
    assert page.add_protein() is False

    # Nothing was added, nothing is dirty, and the box is still open with the
    # service's own sentence on it — no traceback, no silent discard.
    assert page.state.configuration.records == ()
    assert job.state.is_dirty is False
    assert opened[0].error_text()
    assert "alphabet" in opened[0].error_text()
    assert job.last_problem_text() == ""


def test_a_multi_line_paste_is_refused_by_the_checks_the_model_already_has(
    job, page, monkeypatch
):
    opened = _drive_sequence_form(monkeypatch, sequence="ACDEFG\nHIKLMN")
    assert page.add_protein() is False
    assert page.state.configuration.records == ()
    assert opened[0].error_text()


def test_a_ligand_that_is_neither_a_code_nor_a_notation_is_refused(
    job, page, monkeypatch
):
    opened = _drive_ligand_form(monkeypatch, kind="ccd", value="CCD_ATP")
    assert page.add_ligand() is False
    assert page.state.configuration.records == ()
    assert "must not start with" in opened[0].error_text()

    _drive_ligand_form(monkeypatch, kind="smiles", value="   ")
    assert page.add_ligand() is False
    assert page.state.configuration.records == ()


def test_a_refused_removal_is_reported_and_leaves_the_state_alone(
    job, page, monkeypatch
):
    _drive_sequence_form(monkeypatch, sequence="ACDEFG")
    page.add_protein()
    _answer_delete(monkeypatch, page, answer=True)

    # The record was released out of band (no refresh reaches the page), so
    # the service answers "no record is identified by ..." — the page must
    # report that answer instead of pretending the row vanished.
    job.state.services.configuration.remove_record("A")
    assert page.delete_selected() is False
    assert "no record is identified by 'A'" in job.last_problem_text()
    assert page.state.configuration.records == ()


# -- 12: cancelled dialogs change nothing -------------------------------------


def test_a_cancelled_add_does_not_touch_the_job(job, page, monkeypatch):
    _drive_sequence_form(monkeypatch, cancel=True)
    assert page.add_protein() is False
    _drive_ligand_form(monkeypatch, cancel=True)
    assert page.add_ligand() is False

    assert page.state.configuration.records == ()
    assert job.state.is_dirty is False
    assert page.model.rowCount() == 0


def test_a_cancelled_edit_leaves_the_record_exactly_as_it_was(
    filled, reviewed, monkeypatch
):
    page = reviewed.entities_page
    before = page.state.configuration.records
    page.select_record("A")
    _drive_sequence_form(monkeypatch, sequence="GGGGGGG", cancel=True)
    assert page.edit_selected() is False

    assert page.state.configuration.records == before
    assert reviewed.state.is_dirty is False


# -- 13: everything refreshes after a successful change -----------------------


def test_a_successful_add_refreshes_table_details_readiness_and_preview(
    job, page, monkeypatch
):
    overview = job.overview_page
    assert overview.entities_value_text() == "0"
    # An empty job has nothing to write, and the service says so.
    empty_text, empty_reason = page.state.preview_json()
    assert empty_text is None and empty_reason

    _drive_sequence_form(monkeypatch, sequence="ACDEFGHIK")
    assert page.add_protein() is True

    assert page.model.rowCount() == 1
    assert page.detail_text("gui.entity_length") == _text(
        "gui.entity_length_value"
    ) % 9
    # Readiness and the findings come from the validation service, and the
    # counts it reports now include the new record.
    status = job.state.status()
    assert status.ready is True
    assert overview.entities_value_text() == "1"
    assert overview.summary_text("menu.status_components") == "%d %s" % (
        1,
        _text("gui.family_protein"),
    )
    # The preview is the generation service's own text for the new job.
    text, reason = page.state.preview_json()
    assert reason is None
    assert _entry_ids(text) == ["A"]
    assert "ACDEFGHIK" in text
    assert job.state.is_dirty is True


# -- 14: order and untouched advanced data survive ----------------------------


def _advanced_document():
    return {
        "name": "advanced",
        "modelSeeds": [1],
        "sequences": [
            {
                "protein": {
                    "id": "A",
                    "sequence": "ACDEFGHIK",
                    "unpairedMsa": ">query\nACDEFGHIK",
                    "description": "kept",
                }
            },
            {"ligand": {"id": "B", "ccdCodes": ["ATP"]}},
        ],
        "dialect": "alphafold3",
        "version": 4,
    }


def test_an_unrelated_edit_preserves_order_and_the_advanced_data(window, monkeypatch, tmp_path):
    _import(window, _advanced_document(), tmp_path)
    page = window.entities_page
    assert _ids(window) == ["A", "B"]

    page.select_record("A")
    _drive_sequence_form(monkeypatch, sequence="ACDEFGHIKLMN")
    assert page.edit_selected() is True

    assert _ids(window) == ["A", "B"]
    document = json.loads(page.state.preview_json()[0])
    assert [next(iter(entry.values()))["id"] for entry in document["sequences"]] == ["A", "B"]
    protein = document["sequences"][0]["protein"]
    assert protein["unpairedMsa"] == ">query\nACDEFGHIK"  # not the GUI's business
    assert protein["description"] == "kept"
    assert document["sequences"][1]["ligand"]["ccdCodes"] == ["ATP"]


def test_deleting_one_entity_leaves_the_others_and_their_advanced_data(
    window, monkeypatch, tmp_path
):
    _import(window, _advanced_document(), tmp_path)
    page = window.entities_page
    page.select_record("B")
    _answer_delete(monkeypatch, page, answer=True)
    assert page.delete_selected() is True

    assert _ids(window) == ["A"]
    document = json.loads(page.state.preview_json()[0])
    protein = document["sequences"][0]["protein"]
    assert protein["unpairedMsa"] == ">query\nACDEFGHIK"
    assert protein["description"] == "kept"


def test_the_first_added_record_of_a_new_job_starts_at_a(job, page, monkeypatch):
    """Order is the configuration's, and identity is the registry's."""
    _drive_sequence_form(monkeypatch, sequence="ACDEFG")
    page.add_protein()
    _drive_sequence_form(monkeypatch, sequence="ACGU")
    page.add_rna()
    assert _ids(job) == ["A", "B"]
    assert _entry_ids(page.state.preview_json()[0]) == ["A", "B"]
