"""The entity table is a read-only projection of the service's own records.

Two properties matter: the rows are the records the model holds (same
identifiers, same order), and nothing a view can do — including asking for a
sort — may reorder the configuration, because the configuration's order is
what a generated file inherits.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtCore import Qt  # noqa: E402

from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.models import EntityTableModel  # noqa: E402


def _keys(model):
    return [model.row_at(index).record_key for index in range(model.rowCount())]


def test_the_table_lists_every_record_in_configuration_order(filled, qapp):
    model = EntityTableModel()
    model.set_configuration(filled.configuration)
    assert model.rowCount() == len(filled.configuration.records)
    assert _keys(model) == ["A", "B", "C", "D", "E"]
    assert _keys(model) == [
        record.ids.primary.value for record in filled.configuration.records
    ]
    assert model.records == filled.configuration.records


def test_each_row_carries_the_records_own_data(filled, qapp):
    model = EntityTableModel()
    model.set_configuration(filled.configuration)
    protein = model.row_at(0)
    assert protein.family == _text("menu.family_protein")
    assert protein.summary == "20"
    assert protein.modifications == "1"
    assert protein.description == _text("gui.value_unset")
    assert protein.msa == _text("menu.msa_mode_auto")
    assert protein.templates == _text("menu.templates_search")

    given, partner = model.row_at(1), model.row_at(2)
    assert given.family == _text("menu.family_dna")
    assert given.summary == "4"
    # The two halves of the duplex point at each other, and neither invents an
    # MSA or template state it does not have.
    assert given.partner_key == "C"
    assert partner.partner_key == "B"
    assert given.msa == _text("menu.status_absent")
    assert given.templates == _text("menu.status_absent")
    assert given.modifications == _text("menu.status_none")

    ccd, smiles = model.row_at(3), model.row_at(4)
    assert ccd.family == _text("menu.family_ligand")
    assert ccd.summary == _text("gui.representation_ccd") % "ATP"
    assert smiles.summary == _text("gui.representation_smiles") % "CCO"


def test_a_copy_multiplicity_shows_every_identifier(filled, qapp):
    filled.services.configuration.add_record(
        "ligand", representation="NAG", representation_kind="ccd", copies=2
    )
    model = EntityTableModel()
    model.set_configuration(filled.configuration)
    row = model.row_at(model.rowCount() - 1)
    assert row.ids == "F, G"
    assert row.record_key == "F"


def test_asking_for_a_sort_never_reorders_the_configuration(filled, qapp):
    model = EntityTableModel()
    model.set_configuration(filled.configuration)
    before_rows = _keys(model)
    before_records = filled.configuration.records

    model.sort(0, Qt.AscendingOrder)

    assert _keys(model) == before_rows
    assert filled.configuration.records is before_records


def test_selecting_a_record_uses_the_registry_identifier(filled, qapp):
    model = EntityTableModel()
    model.set_configuration(filled.configuration)
    assert model.row_for_record_key("C") == 2
    assert model.row_for_record_key("Z") == -1


def test_the_window_table_is_the_service_model(window, filled):
    window.refresh()
    page_model = window.entities_page.model
    assert page_model.rowCount() == len(filled.configuration.records)
    assert _keys(page_model) == [
        record.ids.primary.value for record in filled.configuration.records
    ]
    assert window.entities_page.select_record("C") is True
    assert window.entities_page.select_record("Z") is False
