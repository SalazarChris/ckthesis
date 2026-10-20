"""Stage 5: the Variants & Batch workspace, driven through its real widgets.

Every test builds the job through the services and then drives the page's own
controls/dialogs; the assertions read the service state (specs, expanded
variants, validation reports, generated JSON) rather than only the labels the
page happens to show. A test that only read a label would not prove that a
change went through ``VariantService`` or that the base stayed untouched.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6", reason="the GUI extra (PySide6) is not installed")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QDialog  # noqa: E402

from configbuilder.app.variant_service import VariantChoice  # noqa: E402
from configbuilder.model import (  # noqa: E402
    AlignmentAutomatic,
    Explicit,
    SearchAllowed,
)
from configbuilder.ui.present.strings import text as _text  # noqa: E402
from configbuilder.ui.render.qt.dialogs import (  # noqa: E402
    DuplicateVariantDialog,
    NewVariantDialog,
    RenameVariantDialog,
    VariantChangeDialog,
)
from configbuilder.ui.render.qt.dialogs import variant_forms  # noqa: E402


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def variants(window):
    """A base with protein A, ligand B (2 copies) and ligand C (1 copy)."""
    state = window.state
    state.new_job()
    assert state.add_record("protein", sequence="ACDEFGHIKLMNPQRSTVWY").ok
    assert (
        state.add_record(
            "ligand", representation="ATP", representation_kind="ccd", copies=2
        ).ok
    )
    assert (
        state.add_record(
            "ligand", representation="NA", representation_kind="ccd", copies=1
        ).ok
    )
    window.refresh()
    return window


def _page(window):
    return window.variants_page


def _select(combo, value):
    index = combo.findData(value)
    assert index >= 0, "no choice %r in %r" % (value, combo.count())
    combo.setCurrentIndex(index)


def _gui_state(value):
    """The GuiState behind a window, or ``value`` itself when already one."""
    return value.state if hasattr(value, "state") else value


def _spec(value, key):
    state = _gui_state(value)
    return next(spec for spec in state.specs if spec.key == key)


def _expanded(value, key):
    state = _gui_state(value)
    outcome = state.preview_variant(key)
    assert outcome.ok, outcome.message
    return outcome.variants[0].configuration


def _variant_json(value, key):
    state = _gui_state(value)
    text, reason = state.preview_variant_json(key)
    assert text is not None, reason
    return json.loads(text)


def _entry(document, key):
    for entry in document["sequences"]:
        (body,) = entry.values()
        if body["id"] == key:
            return body
    raise AssertionError("no entry for %r in %r" % (key, document["sequences"]))


def _changes(state):
    seen = []
    state.project_changed.connect(lambda: seen.append(1))
    return seen


def _picker(path):
    class _Dialog:
        @staticmethod
        def getOpenFileName(*args, **kwargs):
            return (path, "")

    return _Dialog


# -- dialog drivers ----------------------------------------------------------


def _fill_sequence(editor, entity="A", text="GGGGS"):
    _select(editor.sequence_entity, entity)
    editor.sequence_edit.setPlainText(text)


def _fill_job_name(editor, name="mutant"):
    editor.job_name_edit.setText(name)


def _fill_modification(editor, entity="A", code="SEP", position=4):
    _select(editor.mod_entity, entity)
    editor.mod_code.setText(code)
    editor.mod_position.setValue(position)


def _fill_remove_modification(editor, entity="A", index=0):
    _select(editor.remove_mod_entity, entity)
    target = editor.remove_mod_target
    position = target.findData(index)
    assert position >= 0
    target.setCurrentIndex(position)


def _fill_alignment(editor, entity="A", mode="unpaired", kind="inline", text=">q\nACDE"):
    _select(editor.alignment_entity, entity)
    _select(editor.alignment_mode, mode)
    for source_kind, radio in editor.alignment_source_radios:
        radio.setChecked(source_kind == kind)
    if kind == "inline":
        editor.alignment_inline.setPlainText(text)
    else:
        editor.alignment_path.setText(text)


def _fill_references(editor, entity="A", route="search"):
    _select(editor.references_entity, entity)
    _select(editor.references_route, route)


def _fill_count(editor, entity="B", count=6):
    _select(editor.count_component, entity)
    editor.count_spin.setValue(count)


def _fill_add_entity(editor, family="protein", text="HHHH"):
    _select(editor.add_family, family)
    if family == "ligand":
        editor.add_representation.setText(text)
    else:
        editor.add_sequence.setPlainText(text)


def _fill_remove_entity(editor, entity="B"):
    _select(editor.remove_entity, entity)


def _drive_new(monkeypatch, name="Variant 1", kind="sequence", fill=None, key=None, cancel=False):
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        dialog.name_edit.setText(name)
        if key is not None:
            dialog.key_edit.setText(key)
        dialog.change_editor.select_kind(kind)
        if fill is not None:
            fill(dialog.change_editor)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(NewVariantDialog, "exec", fake_exec)
    return opened


def _drive_change(monkeypatch, kind, fill=None, cancel=False):
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        dialog.change_editor.select_kind(kind)
        if fill is not None:
            fill(dialog.change_editor)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(VariantChangeDialog, "exec", fake_exec)
    return opened


def _drive_rename(monkeypatch, label=None, cancel=False):
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        if label is not None:
            dialog.label_edit.setText(label)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(RenameVariantDialog, "exec", fake_exec)
    return opened


def _drive_duplicate(monkeypatch, label="Copy", key="copy", cancel=False):
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        if cancel:
            return QDialog.Rejected
        dialog.name_edit.setText(label)
        dialog.key_edit.setText(key)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(DuplicateVariantDialog, "exec", fake_exec)
    return opened


# =============================================================================
# Workspace and manual variants
# =============================================================================


def test_the_workspace_is_a_destination_and_shows_the_base(variants):
    page = _page(variants)
    assert _text("gui.tab_variants") in variants.sidebar_labels()
    assert variants.state.specs == ()
    assert _text("gui.variants_base") % "Untitled job 1" in page._base_label.text()
    assert page.variant_model.rowCount() == 0
    assert page.selected_key() == ""


def test_a_new_sequence_variant_goes_through_the_service(variants, monkeypatch):
    page = _page(variants)
    before = variants.state.configuration
    changes = _changes(variants.state)
    _drive_new(
        monkeypatch,
        name="Long loop",
        kind="sequence",
        fill=lambda editor: _fill_sequence(editor, text="GGGGS"),
    )

    assert page.new_variant() is True
    spec = _spec(variants.state, "long_loop")
    assert spec.label == "Long loop"
    assert [type(edit).__name__ for edit in spec.edits] == ["SetSequence"]
    assert variants.state.configuration is before, "the base must not change"
    assert len(changes) == 1
    assert page.variant_model.rowCount() == 1
    assert page.row_status_text("long_loop") == _text("gui.variants_status_ready")
    assert _entry(_variant_json(variants, "long_loop"), "A")["sequence"] == "GGGGS"
    base_text, base_reason = variants.state.preview_json()
    assert base_reason is None
    assert _entry(json.loads(base_text), "A")["sequence"] == "ACDEFGHIKLMNPQRSTVWY"


def test_the_new_variant_dialog_previews_the_service_description(
    variants, monkeypatch
):
    page = _page(variants)
    opened = _drive_new(
        monkeypatch,
        name="Previewed",
        kind="sequence",
        fill=lambda editor: _fill_sequence(editor, text="GGGGS"),
    )

    assert page.new_variant() is True
    preview = opened[0].preview_label.text()
    assert _text("gui.variant_preview_change").split(" %s")[0] in preview
    assert "Sequence of A" in preview
    assert "GGGGS" in preview


def test_a_refused_change_is_previewed_as_the_service_refusal(
    variants, monkeypatch
):
    """The preview shows the refusal before any spec exists."""
    page = _page(variants)
    changes = _changes(variants.state)
    opened = _drive_new(
        monkeypatch,
        name="Bad",
        kind="sequence",
        fill=lambda editor: _fill_sequence(editor, text="ACDE\nFGH"),
    )

    assert page.new_variant() is False
    assert "alphabet" in opened[0].preview_label.text().lower()
    assert variants.state.specs == ()
    assert changes == []


def test_an_invalid_new_variant_keeps_the_dialog_open_and_changes_nothing(
    variants, monkeypatch
):
    page = _page(variants)
    before = variants.state.configuration
    changes = _changes(variants.state)
    opened = _drive_new(
        monkeypatch,
        name="Bad",
        kind="sequence",
        fill=lambda editor: _fill_sequence(editor, text="ACDE\nFGH"),
    )

    assert page.new_variant() is False
    assert opened[0].result() != QDialog.Accepted
    assert opened[0].error_text()
    assert variants.state.specs == ()
    assert variants.state.configuration is before
    assert changes == []


def test_a_duplicate_variant_id_is_refused_without_partial_state(
    variants, monkeypatch
):
    page = _page(variants)
    assert variants.state.add_spec_with_edit(
        "taken", "Taken", "job_name", "taken job"
    ).ok
    before = variants.state.configuration
    _drive_new(
        monkeypatch,
        name="Other",
        key="taken",
        kind="job_name",
        fill=_fill_job_name,
    )

    assert page.new_variant() is False
    assert [spec.key for spec in variants.state.specs] == ["taken"]
    assert variants.state.configuration is before


def test_add_change_keeps_the_existing_declared_edits(variants, monkeypatch):
    page = _page(variants)
    assert variants.state.add_spec_with_edit(
        "v1", "V1", "sequence", "GGGGS", record_key="A"
    ).ok
    variants.refresh()
    page._selected_key = "v1"
    page.refresh()
    _drive_change(monkeypatch, "job_name", fill=_fill_job_name)

    assert page.add_change() is True
    edits = [type(edit).__name__ for edit in _spec(variants.state, "v1").edits]
    assert edits == ["SetSequence", "SetName"]
    assert _spec(variants.state, "v1").label == "V1"


def test_rename_keeps_every_edit(variants, monkeypatch):
    page = _page(variants)
    assert variants.state.add_spec_with_edit(
        "v1", "V1", "sequence", "GGGGS", record_key="A"
    ).ok
    variants.refresh()
    page._selected_key = "v1"
    page.refresh()
    _drive_rename(monkeypatch, label="Renamed")

    assert page.rename_variant() is True
    spec = _spec(variants.state, "v1")
    assert spec.label == "Renamed"
    assert len(spec.edits) == 1
    assert page.variant_model.row_at(0).label == "Renamed"


def test_duplicate_copies_the_edits_and_leaves_the_source_alone(
    variants, monkeypatch
):
    page = _page(variants)
    assert variants.state.add_spec_with_edit(
        "v1", "V1", "sequence", "GGGGS", record_key="A"
    ).ok
    variants.refresh()
    page._selected_key = "v1"
    page.refresh()
    _drive_duplicate(monkeypatch, label="Copy of V1", key="copy")

    assert page.duplicate_variant() is True
    assert [spec.key for spec in variants.state.specs] == ["v1", "copy"]
    assert _spec(variants.state, "v1").edits == _spec(variants.state, "copy").edits
    assert page.selected_key() == "copy"


def test_cancelling_removal_changes_nothing_and_confirming_removes_only_the_spec(
    variants, monkeypatch
):
    page = _page(variants)
    assert variants.state.add_spec_with_edit(
        "v1", "V1", "sequence", "GGGGS", record_key="A"
    ).ok
    variants.refresh()
    page._selected_key = "v1"
    page.refresh()
    before = variants.state.configuration
    asked = []

    def recorder(parent, message):
        asked.append(message)
        return False

    page.variant_confirmer = recorder
    assert page.remove_variant() is False
    assert variants.state.specs and variants.state.configuration is before

    page.variant_confirmer = lambda parent, message: True
    assert page.remove_variant() is True
    assert variants.state.specs == ()
    assert variants.state.configuration is before
    assert "V1" in asked[0] and "v1" in asked[0]


def test_cancelling_the_new_variant_dialog_changes_nothing(variants, monkeypatch):
    page = _page(variants)
    changes = _changes(variants.state)
    _drive_new(monkeypatch, cancel=True)
    assert page.new_variant() is False
    assert variants.state.specs == ()
    assert changes == []


# =============================================================================
# Typed changes: PTMs, alignment, templates, counts, entities
# =============================================================================


def test_a_variant_modification_is_1_based_from_the_editor(variants, monkeypatch):
    page = _page(variants)
    _drive_new(
        monkeypatch,
        name="PTM",
        kind="add_modification",
        fill=lambda editor: _fill_modification(editor, code="SEP", position=4),
    )

    assert page.new_variant() is True
    edit = _spec(variants.state, "ptm").edits[0]
    assert type(edit).__name__ == "AddModification"
    assert edit._modification.position.value == 4
    assert edit._modification.code.value == "SEP"
    expanded = _expanded(variants, "ptm")
    assert expanded.records[0].modifications[0].position.value == 4
    assert variants.state.configuration.records[0].modifications == ()


def test_removing_a_modification_uses_the_expanded_rows(variants, monkeypatch):
    page = _page(variants)
    assert variants.state.add_spec_with_edit(
        "v1", "V1", "add_modification", ("SEP", 4), record_key="A"
    ).ok
    variants.refresh()
    page._selected_key = "v1"
    page.refresh()
    _drive_change(
        monkeypatch,
        "remove_modification",
        fill=lambda editor: _fill_remove_modification(editor, index=0),
    )

    assert page.add_change() is True
    edits = _spec(variants.state, "v1").edits
    assert [type(edit).__name__ for edit in edits] == [
        "AddModification",
        "RemoveModification",
    ]
    assert edits[1]._index == 0


def test_an_alignment_change_is_declared_and_serialized(variants, monkeypatch):
    page = _page(variants)
    before_alignment = variants.state.configuration.records[0].alignment
    _drive_new(
        monkeypatch,
        name="MSA",
        kind="alignment",
        fill=lambda editor: _fill_alignment(editor, mode="unpaired", text=">q\nACDE"),
    )

    assert page.new_variant() is True
    body = _entry(_variant_json(variants, "msa"), "A")
    assert body["unpairedMsa"].startswith(">q")
    assert isinstance(variants.state.configuration.records[0].alignment, AlignmentAutomatic)
    assert before_alignment is not None


def test_alignment_offers_only_protein_and_rna_chains(variants):
    """DNA has no alignment field, so it is not a choice either."""
    state = variants.state
    assert state.add_record("dna", sequence="ATGC").ok
    variants.refresh()
    page = _page(variants)
    editor = page._make_editor()
    editor.select_kind("alignment")

    values = [
        editor.alignment_entity.itemData(index)
        for index in range(editor.alignment_entity.count())
    ]
    assert "A" in values
    assert "D" not in values  # the DNA strand
    assert "E" not in values  # its partner


def test_a_template_change_preserves_the_base_references(variants, monkeypatch):
    page = _page(variants)
    before = variants.state.configuration.records[0].references
    _drive_new(
        monkeypatch,
        name="Templates",
        kind="references",
        fill=lambda editor: _fill_references(editor, route="none"),
    )

    assert page.new_variant() is True
    edit = _spec(variants.state, "templates").edits[0]
    assert type(edit).__name__ == "SetReferences"
    assert isinstance(edit._references, Explicit)
    assert isinstance(variants.state.configuration.records[0].references, SearchAllowed)
    assert before is variants.state.configuration.records[0].references


def test_a_component_count_change_only_touches_its_variant(variants, monkeypatch):
    page = _page(variants)
    before_counts = [len(record.ids.ids) for record in variants.state.configuration.records]
    _drive_new(
        monkeypatch,
        name="More ATP",
        kind="component_count",
        fill=lambda editor: _fill_count(editor, entity="B", count=6),
    )

    assert page.new_variant() is True
    expanded = _expanded(variants, "more_atp")
    counts = {
        record.ids.primary.value: len(record.ids.ids)
        for record in expanded.records
        if hasattr(record, "ids")
    }
    assert counts["B"] == 6
    assert [
        len(record.ids.ids) for record in variants.state.configuration.records
    ] == before_counts


def test_adding_an_entity_builds_it_through_the_service(variants, monkeypatch):
    page = _page(variants)
    base_count = len(variants.state.configuration.records)
    _drive_new(
        monkeypatch,
        name="Extra chain",
        kind="add_entity",
        fill=lambda editor: _fill_add_entity(editor, family="protein", text="HHHH"),
    )

    assert page.new_variant() is True
    assert len(variants.state.configuration.records) == base_count
    expanded = _expanded(variants, "extra_chain")
    assert len(expanded.records) == base_count + 1
    added = expanded.records[-1]
    assert added.sequence.text == "HHHH"
    assert added.ids.primary.value not in {
        record.ids.primary.value for record in variants.state.configuration.records
    }


def test_removing_an_entity_is_declared_on_the_selected_record(variants, monkeypatch):
    page = _page(variants)
    _drive_new(
        monkeypatch,
        name="No ATP",
        kind="remove_entity",
        fill=lambda editor: _fill_remove_entity(editor, entity="B"),
    )

    assert page.new_variant() is True
    expanded = _expanded(variants, "no_atp")
    assert [record.ids.primary.value for record in expanded.records] == ["A", "D"]
    assert len(variants.state.configuration.records) == 3


# =============================================================================
# Validation status and findings
# =============================================================================


def test_a_blocked_variant_is_never_shown_as_ready(variants, monkeypatch):
    page = _page(variants)
    _drive_new(
        monkeypatch,
        name="Bad PTM",
        kind="add_modification",
        fill=lambda editor: _fill_modification(editor, position=999),
    )

    assert page.new_variant() is True
    status = page.row_status_text("bad_ptm")
    assert status.startswith(
        _text("gui.variants_status_blocked").split(" (")[0]
    )
    validation = variants.state.validate_all()
    report = validation.variant_reports["bad_ptm"]
    assert report.blocking()
    assert "R-ENT-007" in {finding.rule_id for finding in report.blocking()}
    # The findings view shows the service's own report for the selected spec.
    page._selected_key = "bad_ptm"
    page.refresh()
    assert page.findings_model.rowCount() == len(report.findings)


def test_a_base_block_shows_base_blocked_and_keeps_the_base_findings(
    window, monkeypatch
):
    window.state.new_job()  # no entities: the base itself blocks
    page = window.variants_page
    _drive_new(
        monkeypatch,
        name="Renamed",
        kind="job_name",
        fill=_fill_job_name,
    )

    assert page.new_variant() is True
    assert page.row_status_text("renamed") == _text("gui.variants_status_base_blocked")
    page._selected_key = "renamed"
    page.refresh()
    assert page.findings_note.text() == _text("gui.variants_findings_base")
    assert page.findings_model.rowCount() > 0


def test_validate_all_refreshes_from_the_service(variants):
    page = _page(variants)
    assert variants.state.add_spec_with_edit(
        "v1", "V1", "job_name", "renamed job"
    ).ok
    variants.refresh()
    assert page.validate_now() is True
    assert page.row_status_text("v1") == _text("gui.variants_status_ready")


# =============================================================================
# Quantity series
# =============================================================================


def _check_components(page, components):
    for row in range(page.series_components.count()):
        item = page.series_components.item(row)
        item.setCheckState(
            Qt.Checked if item.data(Qt.UserRole) in components else Qt.Unchecked
        )


def test_the_series_preview_matches_the_service_and_creates_nothing(
    variants, monkeypatch
):
    page = _page(variants)
    _check_components(page, {"B"})
    page.series_start.setValue(1)
    page.series_factor.setValue(2)
    page.series_levels.setValue(3)

    assert page.preview_series() is True
    assert variants.state.specs == ()
    assert page.series_table.rowCount() == 3
    assert page.series_table.item(2, 0).text() == "4"
    assert "B: 8" in page.series_table.item(2, 1).text()
    assert page.series_create_button.isEnabled()


def test_creating_the_series_uses_the_service_plan(variants):
    page = _page(variants)
    _check_components(page, {"B"})
    page.series_start.setValue(1)
    page.series_factor.setValue(2)
    page.series_levels.setValue(3)
    assert page.preview_series() is True

    assert page.create_series() is True
    assert [spec.key for spec in variants.state.specs] == [
        "series_1x",
        "series_2x",
        "series_4x",
    ]
    expanded = _expanded(variants, "series_4x")
    counts = {
        record.ids.primary.value: len(record.ids.ids)
        for record in expanded.records
    }
    assert counts["B"] == 8
    # The base still carries its original two copies.
    assert len(variants.state.configuration.records[1].ids.ids) == 2


def test_changing_values_after_the_preview_blocks_creation(variants):
    page = _page(variants)
    _check_components(page, {"B"})
    assert page.preview_series() is True
    page.series_factor.setValue(3)

    assert not page.series_create_button.isEnabled()
    assert variants.state.specs == ()
    assert page.create_series() is False
    assert variants.state.specs == ()


def test_a_series_whose_keys_collide_refuses_without_partial_creation(variants):
    page = _page(variants)
    _check_components(page, {"B"})
    page.series_levels.setValue(2)
    assert page.preview_series() is True
    assert page.create_series() is True
    assert [spec.key for spec in variants.state.specs] == ["series_1x", "series_2x"]

    # The same plan again collides on its first key: the service refuses and
    # rolls back, so the existing pair is exactly what remains.
    assert page.preview_series() is True
    assert page.create_series() is False
    assert [spec.key for spec in variants.state.specs] == ["series_1x", "series_2x"]


def test_the_series_needs_a_component(variants):
    page = _page(variants)
    _check_components(page, set())
    assert page.preview_series() is False
    assert variants.state.specs == ()
    assert variants.last_problem_text() == _text("gui.variants_series_select")


# =============================================================================
# Batch from file
# =============================================================================


def _batch_file(tmp_path, lines, name="batch.txt"):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_a_protein_batch_previews_then_commits_the_same_entries(
    variants, tmp_path
):
    page = _page(variants)
    path = _batch_file(tmp_path, ["ACDEFG", "HIKLMN"])
    page.batch_path.setText(path)
    page.batch_family.setCurrentIndex(page.batch_family.findData("protein"))

    assert page.preview_batch() is True
    assert variants.state.specs == ()
    assert page.batch_table.rowCount() == 2
    assert page.batch_table.item(1, 0).text() == "HIKLMN"
    assert page.batch_create_button.isEnabled()

    from pathlib import Path

    before_bytes = Path(path).read_bytes()
    assert page.create_batch() is True
    assert [spec.key for spec in variants.state.specs] == ["batch_01", "batch_02"]
    assert len(variants.state.configuration.records) == 3
    assert len(_expanded(variants, "batch_02").records) == 4
    assert Path(path).read_bytes() == before_bytes, "the input file is never rewritten"


def test_an_invalid_batch_is_refused_by_the_preview_and_by_the_commit(
    variants, tmp_path
):
    """An unusable entry is visible before the commit, and the whole set still
    commits atomically if it ever gets that far (Stage 8: the preview runs the
    same construction the commit does, against a discarded registry clone)."""
    page = _page(variants)
    assert variants.state.add_spec_with_edit(
        "existing", "Existing", "job_name", "job"
    ).ok
    variants.refresh()
    path = _batch_file(tmp_path, ["ACDEFG", "ACD EFG"])
    page.batch_path.setText(path)
    page.batch_family.setCurrentIndex(page.batch_family.findData("protein"))

    assert page.preview_batch() is False

    assert "line 2" in variants.last_problem_text()
    assert page.batch_table.rowCount() == 2, "the entries read are still shown"
    assert not page.batch_create_button.isEnabled()
    assert page.create_batch() is False
    assert [spec.key for spec in variants.state.specs] == ["existing"]


def test_cancelling_a_batch_creates_nothing(variants, tmp_path):
    page = _page(variants)
    path = _batch_file(tmp_path, ["ACDEFG"])
    page.batch_path.setText(path)
    page.batch_family.setCurrentIndex(page.batch_family.findData("protein"))
    assert page.preview_batch() is True

    # A changed file/type invalidates the preview; nothing may be committed.
    page.batch_family.setCurrentIndex(page.batch_family.findData("dna"))
    assert page.create_batch() is False
    assert variants.state.specs == ()


def test_a_ligand_smiles_batch_previews_and_commits(variants, tmp_path):
    page = _page(variants)
    path = _batch_file(
        tmp_path,
        ["first CCO", "CCC"],
        name="ligands.smiles",
    )
    page.batch_path.setText(path)
    page.batch_family.setCurrentIndex(page.batch_family.findData("ligand"))

    assert page.preview_batch() is True
    assert page.batch_table.rowCount() == 2
    assert page.create_batch() is True
    assert [spec.key for spec in variants.state.specs] == ["batch_01", "batch_02"]
    assert len(variants.state.configuration.records) == 3


def test_a_batch_preview_does_not_notify_a_project_change(variants, tmp_path):
    page = _page(variants)
    changes = _changes(variants.state)
    path = _batch_file(tmp_path, ["ACDEFG"])
    page.batch_path.setText(path)
    page.batch_family.setCurrentIndex(page.batch_family.findData("protein"))

    assert page.preview_batch() is True
    assert changes == []


# =============================================================================
# Base immutability and independence
# =============================================================================


def test_one_variants_edits_never_leak_into_another_or_the_base(
    variants, monkeypatch
):
    page = _page(variants)
    _drive_new(
        monkeypatch,
        name="First",
        key="first",
        kind="sequence",
        fill=lambda editor: _fill_sequence(editor, text="GGGGS"),
    )
    assert page.new_variant() is True
    _drive_new(
        monkeypatch,
        name="Second",
        key="second",
        kind="sequence",
        fill=lambda editor: _fill_sequence(editor, text="HHHHH"),
    )
    assert page.new_variant() is True

    assert _entry(_variant_json(variants, "first"), "A")["sequence"] == "GGGGS"
    assert _entry(_variant_json(variants, "second"), "A")["sequence"] == "HHHHH"
    assert variants.state.configuration.records[0].sequence.text == "ACDEFGHIKLMNPQRSTVWY"


def test_the_change_list_and_status_columns_describe_the_spec(variants, monkeypatch):
    page = _page(variants)
    _drive_new(
        monkeypatch,
        name="Described",
        kind="sequence",
        fill=lambda editor: _fill_sequence(editor, text="GGGGS"),
    )
    assert page.new_variant() is True
    row = page.variant_model.row_at(0)
    assert row.key == "described"
    assert row.label == "Described"
    assert "Sequence of A" in row.changes
    assert row.status == _text("gui.variants_status_ready")
    assert page.changes_list.count() == 1


def test_the_selected_variant_json_is_the_service_document(variants, monkeypatch):
    page = _page(variants)
    _drive_new(
        monkeypatch,
        name="Preview",
        kind="sequence",
        fill=lambda editor: _fill_sequence(editor, text="GGGGS"),
    )
    assert page.new_variant() is True
    page._selected_key = "preview"
    page.refresh()

    text, reason = variants.state.preview_variant_json("preview")
    assert reason is None
    assert page.json_view.toPlainText() == text


# -- file pickers ------------------------------------------------------------


def test_the_batch_picker_fills_the_path(variants, monkeypatch, tmp_path):
    page = _page(variants)
    path = _batch_file(tmp_path, ["ACDEFG"])
    monkeypatch.setattr("configbuilder.ui.render.qt.pages.variants.QFileDialog", _picker(path))
    assert page.browse_batch() == path
    assert page.batch_path.text() == path


def test_the_variant_reference_picker_adds_a_row(monkeypatch):
    editor = variant_forms.VariantChangeEditor(
        options=(VariantChoice("Templates", "references"),),
        protein_options=(("A", "A"),),
    )
    editor.select_kind("references")
    _fill_references(editor, route="list")
    monkeypatch.setattr(variant_forms, "QFileDialog", _picker("t.cif"))

    editor.add_reference_file()

    assert editor.reference_rows() == (("t.cif", ""),)
    request, failure = editor.collect()
    assert failure is None
    assert request.value == ("list", (("file", "t.cif", ()),))

def test_variant_reference_pairs_are_parsed_as_zero_based(monkeypatch):
    editor = variant_forms.VariantChangeEditor(
        options=(VariantChoice("Templates", "references"),),
        protein_options=(("A", "A"),),
    )
    editor.select_kind("references")
    _fill_references(editor, route="list")
    monkeypatch.setattr(variant_forms, "QFileDialog", _picker("t.cif"))
    editor.add_reference_file()
    editor.references_table.item(0, 1).setText("1:2, 3:4")

    request, failure = editor.collect()

    assert failure is None
    assert request.value == ("list", (("file", "t.cif", ((1, 2), (3, 4))),))
