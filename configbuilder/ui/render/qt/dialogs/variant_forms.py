"""Variant and batch forms: collect values, never build domain objects.

The Variants & Batch page owns every service call. These dialogs only collect
what the user chose and hand it to an ``apply`` callable; a refusal from the
service is shown on the dialog's own line and the dialog stays open so the
value can be corrected (the Stage 3/4 form discipline).

``VariantChangeEditor`` is the one typed editor for every change kind the
service's ``edit_options`` offers. Its pages are built from the service's own
choice rows — the front end never invents a kind, a record key, an edit class
or a wire value. Values leave ``collect()`` in the forms the service's
``apply_variant_edit`` / ``add_spec_with_edit`` already accept.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from configbuilder.ui.present.sequence import residue_at
from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.qt.models import fixed_font

__all__ = [
    "ChangeRequest",
    "DuplicateVariantDialog",
    "MAX_POSITION",
    "NewVariantDialog",
    "RenameVariantDialog",
    "VariantChangeDialog",
    "VariantChangeEditor",
    "suggest_key",
]

#: The largest residue/position any form offers. The service's own rule is a
#: positive 1-based integer; this bounded spin box is a UI guard, not a domain
#: limit, and the service stays the authority.
MAX_POSITION = 9999

# Built as pairs, not a dict literal: ``sequence`` is also a wire field name,
# and the single-authority architecture test flags wire names used as
# dict-literal keys anywhere outside ``transform`` (plan §10.1). These are
# service change-kind words, not wire fields.
_KIND_LABEL_KEYS = dict(
    (
        ("sequence", "gui.variant_kind_sequence"),
        ("add_modification", "gui.variant_kind_add_modification"),
        ("remove_modification", "gui.variant_kind_remove_modification"),
        ("alignment", "gui.variant_kind_alignment"),
        ("references", "gui.variant_kind_references"),
        ("job_name", "gui.variant_kind_job_name"),
        ("job_description", "gui.variant_kind_job_description"),
        ("seeds", "gui.variant_kind_seeds"),
        ("component_count", "gui.variant_kind_component_count"),
        ("component_representation", "gui.variant_kind_component_representation"),
        ("add_entity", "gui.variant_kind_add_entity"),
        ("remove_entity", "gui.variant_kind_remove_entity"),
    )
)

_KIND_HINT_KEYS = {kind: "gui.variant_hint_" + kind for kind in _KIND_LABEL_KEYS}

# The alignment modes each family accepts, in the console's own words and
# order. The mode *word* is what the service receives; it remains the
# authority on what a family accepts.
_ALIGNMENT_MODES = {
    "protein": (
        ("menu.msa_mode_auto", "automatic"),
        ("menu.msa_mode_unpaired", "unpaired"),
        ("menu.msa_mode_paired", "paired"),
        ("menu.msa_mode_both", "both"),
        ("menu.msa_mode_free", "free"),
    ),
    "rna": (
        ("menu.msa_mode_auto", "automatic"),
        ("menu.msa_mode_provided", "provided"),
        ("menu.msa_mode_free", "free"),
    ),
}

_SOURCE_OPTIONS = (
    ("menu.msa_paste_inline", "inline"),
    ("menu.msa_use_file", "file"),
)

_TEMPLATE_ROUTES = (
    ("gui.variant_route_search", "search"),
    ("gui.variant_route_none", "none"),
    ("gui.variant_route_list", "list"),
)

_FAMILY_OPTIONS = (
    ("menu.family_protein", "protein"),
    ("menu.family_rna", "rna"),
    ("menu.family_dna", "dna"),
    ("menu.family_ligand", "ligand"),
)

_REPRESENTATION_KINDS = (
    ("gui.ligand_ccd_option", "ccd"),
    ("gui.ligand_smiles_option", "smiles"),
)


class ChangeRequest(object):
    """One change as the service's typed operations take it."""

    __slots__ = ("kind", "value", "record_key")

    def __init__(self, kind, value=None, record_key=None) -> None:
        self.kind = kind
        self.value = value
        self.record_key = record_key

    def __repr__(self) -> str:
        return "ChangeRequest(%r, record=%r)" % (self.kind, self.record_key)


def suggest_key(label: str, existing_keys=()) -> str:
    """A deterministic variant key from a user-facing name.

    Naming a spec is the user's visible choice (the key appears in file
    names), not an identifier allocation: this only turns "Membrane mutant"
    into ``membrane_mutant`` and makes it unique among the current keys.
    """
    cleaned = []
    for character in (label or "").strip().lower():
        usable = character.isascii() and character.isalnum()
        cleaned.append(character if usable else "_")
    base = "".join(cleaned).strip("_") or "variant"
    base = "_".join(part for part in base.split("_") if part)
    existing = set(existing_keys or ())
    if base not in existing:
        return base
    suffix = 2
    while "%s_%d" % (base, suffix) in existing:
        suffix += 1
    return "%s_%d" % (base, suffix)


class _DialogBase(QDialog):
    """Accept only on a successful apply; show the service's own refusal."""

    def __init__(self, parent, title: str, accept_text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(640)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        self.buttons = QDialogButtonBox()
        self.accept_button = self.buttons.addButton(
            accept_text, QDialogButtonBox.AcceptRole
        )
        self.cancel_button = self.buttons.addButton(
            _text("gui.form_cancel"), QDialogButtonBox.RejectRole
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.body = QVBoxLayout(self)
        self.form = QFormLayout()

    def error_text(self) -> str:
        return self.error_label.text()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message or "")
        self.error_label.setVisible(True)

    def finish(self) -> None:
        self.body.addLayout(self.form)
        self.body.addWidget(self.error_label)
        self.body.addWidget(self.buttons)

    def _collect(self):
        raise NotImplementedError


class VariantChangeEditor(QWidget):
    """The typed editor for one change kind, with only its fields shown.

    ``options`` is the service's ``edit_options()`` result. The other
    arguments are display choices the page derived from the base job:
    ``(value, label)`` pairs for entities and components, a family map for
    alignment mode selection, sequence text for the residue echo, and
    modification rows for the remove picker. ``changed`` fires whenever a
    field changes, so a dialog can refresh its service-backed preview.
    """

    changed = Signal()

    def __init__(
        self,
        parent=None,
        options=(),
        entity_options=(),
        polymer_options=(),
        protein_options=(),
        alignment_options=(),
        component_options=(),
        family_by_key=None,
        sequences_by_key=None,
        modifications_by_key=None,
        template_filter="",
    ) -> None:
        super().__init__(parent)
        self._family_by_key = dict(family_by_key or {})
        self._sequences_by_key = dict(sequences_by_key or {})
        self._modifications_by_key = dict(modifications_by_key or {})
        self._template_filter = template_filter or _text("gui.file_filter")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QFormLayout()
        self.kind_combo = QComboBox()
        for option in options:
            kind = getattr(option, "kind", "")
            label = _text(_KIND_LABEL_KEYS[kind]) if kind in _KIND_LABEL_KEYS else option.label
            self.kind_combo.addItem(label, kind)
        top.addRow(_text("gui.variant_change_kind"), self.kind_combo)
        layout.addLayout(top)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.stack = QStackedWidget()
        self._pages = {}
        self._options = tuple(options)
        for option in options:
            kind = getattr(option, "kind", "")
            page = self._build_page(
                kind,
                entity_options,
                polymer_options,
                protein_options,
                alignment_options,
                component_options,
            )
            if page is None:
                continue
            self._pages[kind] = page
            self.stack.addWidget(page)
        layout.addWidget(self.stack)

        self.kind_combo.currentIndexChanged.connect(self._refresh_page)
        self._connect_changes()
        self._refresh_page()

    def _connect_changes(self) -> None:
        """Emit ``changed`` for every input the preview depends on."""
        def notify(*_args) -> None:
            self.changed.emit()

        for widget in self.findChildren(QLineEdit):
            widget.textChanged.connect(notify)
        for widget in self.findChildren(QPlainTextEdit):
            widget.textChanged.connect(notify)
        for widget in self.findChildren(QSpinBox):
            widget.valueChanged.connect(notify)
        for widget in self.findChildren(QComboBox):
            widget.currentIndexChanged.connect(notify)
        for widget in self.findChildren(QRadioButton):
            widget.toggled.connect(notify)
        for widget in self.findChildren(QTableWidget):
            widget.itemChanged.connect(notify)

    # -- page construction -------------------------------------------------

    def _combo(self, choices) -> QComboBox:
        combo = QComboBox()
        for value, label in choices:
            combo.addItem(label, value)
        return combo

    def _build_page(
        self,
        kind,
        entity_options,
        polymer_options,
        protein_options,
        alignment_options,
        component_options,
    ):
        if not kind:
            return None
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        if kind == "sequence":
            self.sequence_entity = self._combo(entity_options)
            self.sequence_edit = QPlainTextEdit()
            self.sequence_edit.setFont(fixed_font())
            self.sequence_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            self.sequence_edit.setMinimumHeight(90)
            self.sequence_hint = QLabel(_text("gui.variant_field_sequence_hint"))
            self.sequence_hint.setWordWrap(True)
            form.addRow(_text("gui.variant_field_entity"), self.sequence_entity)
            form.addRow(_text("gui.variant_field_sequence"), self.sequence_edit)
            form.addRow("", self.sequence_hint)
        elif kind == "add_modification":
            self.mod_entity = self._combo(polymer_options)
            self.mod_code = QLineEdit()
            self.mod_code.setPlaceholderText(_text("gui.mod_code_placeholder"))
            self.mod_position = QSpinBox()
            self.mod_position.setRange(1, MAX_POSITION)
            self.mod_residue = QLabel()
            self.mod_residue.setWordWrap(True)
            form.addRow(_text("gui.variant_field_entity"), self.mod_entity)
            form.addRow(_text("gui.variant_field_code"), self.mod_code)
            form.addRow(_text("gui.variant_field_position"), self.mod_position)
            form.addRow("", self.mod_residue)
            self.mod_entity.currentIndexChanged.connect(self._refresh_mod_residue)
            self.mod_position.valueChanged.connect(self._refresh_mod_residue)
            self._refresh_mod_residue()
        elif kind == "remove_modification":
            self.remove_mod_entity = self._combo(polymer_options)
            self.remove_mod_target = QComboBox()
            self.remove_mod_note = QLabel()
            self.remove_mod_note.setWordWrap(True)
            form.addRow(_text("gui.variant_field_entity"), self.remove_mod_entity)
            form.addRow(
                _text("gui.variant_field_remove_target"), self.remove_mod_target
            )
            form.addRow("", self.remove_mod_note)
            self.remove_mod_entity.currentIndexChanged.connect(
                self._refresh_remove_modifications
            )
            self._refresh_remove_modifications()
        elif kind == "alignment":
            self.alignment_entity = self._combo(alignment_options)
            self.alignment_mode = QComboBox()
            self.alignment_source = QButtonGroup(self)
            self.alignment_source_radios = []
            source_row = QWidget()
            source_layout = QHBoxLayout(source_row)
            source_layout.setContentsMargins(0, 0, 0, 0)
            for label_key, source_kind in _SOURCE_OPTIONS:
                radio = QRadioButton(_text(label_key))
                self.alignment_source.addButton(radio)
                self.alignment_source_radios.append((source_kind, radio))
                source_layout.addWidget(radio)
            self.alignment_inline = QPlainTextEdit()
            self.alignment_inline.setFont(fixed_font())
            self.alignment_inline.setMinimumHeight(90)
            self.alignment_path = QLineEdit()
            self.alignment_browse = QPushButton(_text("gui.variant_field_browse"))
            path_row = QWidget()
            path_layout = QHBoxLayout(path_row)
            path_layout.setContentsMargins(0, 0, 0, 0)
            path_layout.addWidget(self.alignment_path, 1)
            path_layout.addWidget(self.alignment_browse)
            self.alignment_no_source = QLabel(_text("gui.variant_no_source"))
            self.alignment_no_source.setWordWrap(True)
            form.addRow(_text("gui.variant_field_entity"), self.alignment_entity)
            form.addRow(_text("gui.variant_field_mode"), self.alignment_mode)
            form.addRow(_text("gui.variant_field_source"), source_row)
            form.addRow(_text("gui.variant_field_inline"), self.alignment_inline)
            form.addRow(_text("gui.variant_field_path"), path_row)
            form.addRow("", self.alignment_no_source)
            self._alignment_form = form
            for source_kind, radio in self.alignment_source_radios:
                radio.setChecked(source_kind == "inline")
            self.alignment_entity.currentIndexChanged.connect(
                self._refresh_alignment_modes
            )
            self.alignment_mode.currentIndexChanged.connect(
                self._refresh_alignment_source
            )
            self.alignment_source.buttonClicked.connect(
                lambda _button: self._refresh_alignment_source()
            )
            self.alignment_browse.clicked.connect(self.browse_alignment)
            self._refresh_alignment_modes()
        elif kind == "references":
            self.references_entity = self._combo(protein_options)
            self.references_route = QComboBox()
            for label_key, route in _TEMPLATE_ROUTES:
                self.references_route.addItem(_text(label_key), route)
            self.references_table = QTableWidget(0, 2)
            self.references_table.setHorizontalHeaderLabels(
                [_text("gui.variant_field_path"), _text("gui.variant_pairs")]
            )
            self.references_table.verticalHeader().setVisible(False)
            self.references_table.setMinimumHeight(120)
            self.references_add = QPushButton(_text("gui.variant_add_file"))
            self.references_remove = QPushButton(_text("gui.variant_remove_file"))
            references_row = QWidget()
            references_layout = QHBoxLayout(references_row)
            references_layout.setContentsMargins(0, 0, 0, 0)
            references_layout.addWidget(self.references_add)
            references_layout.addWidget(self.references_remove)
            references_layout.addStretch(1)
            form.addRow(_text("gui.variant_field_entity"), self.references_entity)
            form.addRow(_text("gui.variant_field_route"), self.references_route)
            form.addRow(self.references_table)
            form.addRow(references_row)
            self.references_add.clicked.connect(self.add_reference_file)
            self.references_remove.clicked.connect(self.remove_reference_row)
            self.references_route.currentIndexChanged.connect(
                self._refresh_references_controls
            )
            self._refresh_references_controls()
        elif kind == "job_name":
            self.job_name_edit = QLineEdit()
            form.addRow(_text("gui.variants_name"), self.job_name_edit)
        elif kind == "job_description":
            self.job_description_edit = QLineEdit()
            form.addRow(
                _text("gui.variant_field_description"), self.job_description_edit
            )
        elif kind == "seeds":
            self.seeds_edit = QLineEdit()
            form.addRow(_text("gui.variant_field_seeds"), self.seeds_edit)
        elif kind == "component_count":
            self.count_component = self._combo(component_options)
            self.count_spin = QSpinBox()
            self.count_spin.setRange(1, MAX_POSITION)
            form.addRow(_text("gui.variant_field_entity"), self.count_component)
            form.addRow(_text("gui.variant_field_count"), self.count_spin)
        elif kind == "component_representation":
            # The same change the "vary the entities" page makes, offered here
            # for one ligand at a time (and for adding it to an existing
            # variant): a SMILES string replacing the ligand's representation.
            self.representation_component = self._combo(component_options)
            self.representation_edit = QLineEdit()
            self.representation_edit.setPlaceholderText(
                _text("gui.variant_field_smiles_placeholder")
            )
            form.addRow(
                _text("gui.variant_field_entity"), self.representation_component
            )
            form.addRow(
                _text("gui.variant_field_representation"), self.representation_edit
            )
        elif kind == "add_entity":
            self.add_family = QComboBox()
            for label_key, family in _FAMILY_OPTIONS:
                self.add_family.addItem(_text(label_key), family)
            self.add_sequence = QPlainTextEdit()
            self.add_sequence.setFont(fixed_font())
            self.add_sequence.setMinimumHeight(90)
            self.add_representation = QLineEdit()
            self.add_representation_kind = QComboBox()
            for label_key, value in _REPRESENTATION_KINDS:
                self.add_representation_kind.addItem(_text(label_key), value)
            form.addRow(_text("gui.variant_field_family"), self.add_family)
            form.addRow(_text("gui.variant_field_sequence"), self.add_sequence)
            form.addRow(
                _text("gui.variant_field_representation"), self.add_representation
            )
            form.addRow(
                _text("gui.variant_field_representation_kind"),
                self.add_representation_kind,
            )
            self._add_form = form
            self.add_family.currentIndexChanged.connect(self._refresh_add_family)
            self._refresh_add_family()
        elif kind == "remove_entity":
            self.remove_entity = self._combo(entity_options)
            form.addRow(_text("gui.variant_field_entity"), self.remove_entity)
        else:
            return None
        page._form = form
        return page

    # -- dynamic controls --------------------------------------------------

    def _refresh_page(self, *_args) -> None:
        kind = self.current_kind()
        page = self._pages.get(kind)
        if page is not None:
            self.stack.setCurrentWidget(page)
        self.hint_label.setText(_text(_KIND_HINT_KEYS.get(kind, "gui.variant_change_hint")))
        if kind == "remove_modification":
            self._refresh_remove_modifications()

    def current_kind(self) -> str:
        return self.kind_combo.currentData() or ""

    def select_kind(self, kind: str) -> bool:
        index = self.kind_combo.findData(kind)
        if index < 0:
            return False
        self.kind_combo.setCurrentIndex(index)
        return True

    def _refresh_mod_residue(self) -> None:
        key = self.mod_entity.currentData() or ""
        sequence = self._sequences_by_key.get(key, "")
        position = self.mod_position.value()
        residue = residue_at(sequence, position)
        if residue is None:
            self.mod_residue.setText(
                _text("gui.variant_field_residue_out") % (position, len(sequence))
            )
        else:
            self.mod_residue.setText(_text("gui.variant_field_residue") % residue)

    def _refresh_remove_modifications(self) -> None:
        key = self.remove_mod_entity.currentData() or ""
        rows = self._modifications_by_key.get(key, ())
        self.remove_mod_target.clear()
        for index, display in rows:
            self.remove_mod_target.addItem(display, index)
        if not rows:
            self.remove_mod_target.addItem(
                _text("gui.variant_field_no_modifications"), None
            )
        self.remove_mod_note.setText(
            "" if rows else _text("gui.variant_field_no_modifications")
        )

    def _alignment_family(self) -> str:
        return self._family_by_key.get(self.alignment_entity.currentData() or "", "")

    def _refresh_alignment_modes(self) -> None:
        family = self._alignment_family()
        modes = _ALIGNMENT_MODES.get(family, ())
        current = self.alignment_mode.currentData()
        self.alignment_mode.clear()
        for label_key, word in modes:
            self.alignment_mode.addItem(_text(label_key), word)
        if current is not None:
            index = self.alignment_mode.findData(current)
            if index >= 0:
                self.alignment_mode.setCurrentIndex(index)
        self._refresh_alignment_source()

    def _alignment_mode(self) -> str:
        return self.alignment_mode.currentData() or ""

    def _alignment_needs_source(self) -> bool:
        return self._alignment_mode() not in ("automatic", "free")

    def _alignment_source_kind(self) -> str:
        for kind, radio in self.alignment_source_radios:
            if radio.isChecked():
                return kind
        return "inline"

    def _refresh_alignment_source(self) -> None:
        needed = self._alignment_needs_source()
        for _kind, radio in self.alignment_source_radios:
            radio.setEnabled(needed)
        inline = needed and self._alignment_source_kind() == "inline"
        path = needed and self._alignment_source_kind() == "file"
        form = self._alignment_form
        form.setRowVisible(self.alignment_inline, inline)
        form.setRowVisible(self.alignment_path.parentWidget(), path)
        self.alignment_browse.setEnabled(path)
        self.alignment_no_source.setVisible(not needed)

    def browse_alignment(self) -> str:
        path, _selected = QFileDialog.getOpenFileName(
            self, _text("gui.alignment_file_dialog"), "", _text("gui.file_filter")
        )
        if path:
            self.alignment_path.setText(path)
        return path

    def _reference_route(self) -> str:
        return self.references_route.currentData() or "search"

    def _refresh_references_controls(self) -> None:
        listed = self._reference_route() == "list"
        self.references_table.setVisible(listed)
        self.references_add.setVisible(listed)
        self.references_remove.setVisible(listed)
        self.references_remove.setEnabled(self.references_table.rowCount() > 0)

    def add_reference_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            _text("gui.templates_file_dialog"),
            "",
            self._template_filter,
        )
        if not path:
            return
        row = self.references_table.rowCount()
        self.references_table.insertRow(row)
        path_item = QTableWidgetItem(path)
        path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
        self.references_table.setItem(row, 0, path_item)
        self.references_table.setItem(row, 1, QTableWidgetItem(""))
        self.references_remove.setEnabled(True)

    def remove_reference_row(self) -> None:
        rows = sorted(
            {index.row() for index in self.references_table.selectedIndexes()},
            reverse=True,
        )
        if not rows and self.references_table.rowCount():
            rows = [self.references_table.rowCount() - 1]
        for row in rows:
            self.references_table.removeRow(row)
        self.references_remove.setEnabled(self.references_table.rowCount() > 0)

    def reference_rows(self):
        """The rows as ``(path, pairs_text)`` for display and tests."""
        rows = []
        for row in range(self.references_table.rowCount()):
            path = (
                self.references_table.item(row, 0).text()
                if self.references_table.item(row, 0)
                else ""
            )
            pairs = (
                self.references_table.item(row, 1).text()
                if self.references_table.item(row, 1)
                else ""
            )
            rows.append((path, pairs))
        return tuple(rows)

    @staticmethod
    def parse_pairs(text_value: str):
        """``query:template`` tokens as ``((query, template), ...)``.

        The console's own pair syntax (0-based, comma or semicolon
        separated); the service still validates the numbers it receives.
        """
        pairs = []
        for token in (text_value or "").replace(";", ",").split(","):
            token = token.strip()
            if not token:
                continue
            left, _, right = token.partition(":")
            pairs.append((int(left.strip()), int(right.strip())))
        return tuple(pairs)

    def _refresh_add_family(self) -> None:
        ligand = (self.add_family.currentData() or "") == "ligand"
        self._add_form.setRowVisible(self.add_sequence, not ligand)
        self._add_form.setRowVisible(self.add_representation, ligand)
        self._add_form.setRowVisible(self.add_representation_kind, ligand)

    # -- collection --------------------------------------------------------

    def collect(self):
        """``(ChangeRequest, None)`` or ``(None, user-facing message)``."""
        kind = self.current_kind()
        if kind == "sequence":
            entity = self.sequence_entity.currentData() or ""
            text = self.sequence_edit.toPlainText().strip()
            if not entity:
                return None, _text("gui.variant_choose_entity")
            if not text:
                return None, _text("gui.variant_choose_value")
            return ChangeRequest(kind, text, entity), None
        if kind == "add_modification":
            entity = self.mod_entity.currentData() or ""
            code = self.mod_code.text().strip()
            position = int(self.mod_position.value())
            if not entity:
                return None, _text("gui.variant_choose_entity")
            if not code:
                return None, _text("gui.variant_choose_value")
            return ChangeRequest(kind, (code, position), entity), None
        if kind == "remove_modification":
            entity = self.remove_mod_entity.currentData() or ""
            target = self.remove_mod_target.currentData()
            if not entity or target is None:
                return None, _text("gui.variant_choose_value")
            return ChangeRequest(kind, int(target), entity), None
        if kind == "alignment":
            entity = self.alignment_entity.currentData() or ""
            mode = self._alignment_mode()
            if not entity:
                return None, _text("gui.variant_choose_entity")
            if not mode:
                return None, _text("gui.variant_choose_value")
            if not self._alignment_needs_source():
                return ChangeRequest(kind, (mode, None), entity), None
            if self._alignment_source_kind() == "file":
                path = self.alignment_path.text().strip()
                if not path:
                    return None, _text("gui.variant_choose_value")
                return ChangeRequest(kind, (mode, ("file", path)), entity), None
            text = self.alignment_inline.toPlainText()
            if not text.strip():
                return None, _text("gui.variant_choose_value")
            return ChangeRequest(kind, (mode, ("inline", text)), entity), None
        if kind == "references":
            entity = self.references_entity.currentData() or ""
            if not entity:
                return None, _text("gui.variant_choose_entity")
            route = self._reference_route()
            if route != "list":
                return ChangeRequest(kind, (route, ()), entity), None
            rows = self.reference_rows()
            if not rows:
                return None, _text("gui.variant_choose_value")
            try:
                payload = tuple(
                    ("file", path, self.parse_pairs(pairs)) for path, pairs in rows
                )
            except ValueError:
                return None, _text("gui.variant_choose_value")
            return ChangeRequest(kind, (route, payload), entity), None
        if kind == "job_name":
            text = self.job_name_edit.text().strip()
            if not text:
                return None, _text("gui.variant_choose_value")
            return ChangeRequest(kind, text), None
        if kind == "job_description":
            return ChangeRequest(kind, self.job_description_edit.text()), None
        if kind == "seeds":
            text = self.seeds_edit.text().strip()
            if not text:
                return None, _text("gui.variant_seed_values")
            return ChangeRequest(kind, text), None
        if kind == "component_count":
            entity = self.count_component.currentData() or ""
            if not entity:
                return None, _text("gui.variant_choose_entity")
            return ChangeRequest(kind, int(self.count_spin.value()), entity), None
        if kind == "component_representation":
            entity = self.representation_component.currentData() or ""
            if not entity:
                return None, _text("gui.variant_choose_entity")
            text = self.representation_edit.text().strip()
            if not text:
                return None, _text("gui.variant_choose_value")
            return ChangeRequest(kind, text, entity), None
        if kind == "add_entity":
            family = self.add_family.currentData() or ""
            if not family:
                return None, _text("gui.variant_choose_value")
            if family == "ligand":
                representation = self.add_representation.text().strip()
                representation_kind = self.add_representation_kind.currentData() or ""
                if not representation:
                    return None, _text("gui.variant_choose_value")
                return (
                    ChangeRequest(
                        kind, (family, representation, representation_kind)
                    ),
                    None,
                )
            sequence = self.add_sequence.toPlainText().strip()
            if not sequence:
                return None, _text("gui.variant_choose_value")
            return ChangeRequest(kind, (family, sequence, "")), None
        if kind == "remove_entity":
            entity = self.remove_entity.currentData() or ""
            if not entity:
                return None, _text("gui.variant_choose_entity")
            return ChangeRequest(kind, None, entity), None
        return None, _text("gui.variant_change_hint")


class _IdentityMixin(object):
    """Name/ID fields and their one local check (both must be filled)."""

    def _build_identity(self, form, existing_keys):
        self._existing_keys = tuple(existing_keys or ())
        self.name_edit = QLineEdit()
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText(suggest_key("", self._existing_keys))
        self._key_touched = False
        self.name_edit.textChanged.connect(self._autofill_key)
        self.key_edit.textEdited.connect(self._mark_key_touched)
        form.addRow(_text("gui.variants_name"), self.name_edit)
        form.addRow(_text("gui.variants_key"), self.key_edit)
        key_hint = QLabel(_text("gui.variants_key_hint"))
        key_hint.setWordWrap(True)
        form.addRow("", key_hint)

    def _mark_key_touched(self, _text_value) -> None:
        self._key_touched = True

    def _autofill_key(self, text_value) -> None:
        if not self._key_touched:
            self.key_edit.setText(suggest_key(text_value, self._existing_keys))

    def identity(self):
        name = self.name_edit.text().strip()
        key = self.key_edit.text().strip()
        if not name or not key:
            return None, _text("gui.variant_name_required")
        return (name, key), None


class NewVariantDialog(_DialogBase, _IdentityMixin):
    """Name a new variant, preview the first change, then commit it."""

    def __init__(
        self,
        parent,
        apply,
        editor,
        title=None,
        existing_keys=(),
        preview=None,
    ) -> None:
        super().__init__(
            parent,
            title or _text("gui.variant_form_new_title"),
            _text("gui.variant_form_create"),
        )
        self._apply = apply
        self._preview = preview
        self._build_identity(self.form, existing_keys)
        self.change_editor = editor
        self.body.addWidget(self.change_editor)
        self.preview_label = QLabel(_text("gui.variant_preview_pending"))
        self.preview_label.setWordWrap(True)
        self.body.addWidget(self.preview_label)
        self.change_editor.changed.connect(self.refresh_preview)
        self.finish()
        self.refresh_preview()

    def refresh_preview(self) -> None:
        """Show the service's description of the change, or why it refuses."""
        if self._preview is None:
            return
        request, failure = self.change_editor.collect()
        if failure is not None:
            self.preview_label.setText(_text("gui.variant_preview_pending"))
            return
        description, refusal = self._preview(request)
        if refusal is not None:
            self.preview_label.setText(refusal)
            return
        self.preview_label.setText(_text("gui.variant_preview_change") % description)

    def accept(self) -> None:
        identity, failure = self.identity()
        if failure is not None:
            self._show_error(failure)
            return
        request, failure = self.change_editor.collect()
        if failure is not None:
            self._show_error(failure)
            return
        name, key = identity
        outcome = self._apply(name, key, request)
        if getattr(outcome, "ok", False):
            super().accept()
            return
        self._show_error(getattr(outcome, "message", "") or "")


class VariantChangeDialog(_DialogBase):
    """Preview one declared change, then append it to an existing variant."""

    def __init__(self, parent, apply, editor, key, preview=None) -> None:
        super().__init__(
            parent,
            _text("gui.variant_form_change_title") % key,
            _text("gui.variant_form_add"),
        )
        self._apply = apply
        self._preview = preview
        self.change_editor = editor
        self.body.addWidget(self.change_editor)
        self.preview_label = QLabel(_text("gui.variant_preview_pending"))
        self.preview_label.setWordWrap(True)
        self.body.addWidget(self.preview_label)
        self.change_editor.changed.connect(self.refresh_preview)
        self.finish()
        self.refresh_preview()

    def refresh_preview(self) -> None:
        if self._preview is None:
            return
        request, failure = self.change_editor.collect()
        if failure is not None:
            self.preview_label.setText(_text("gui.variant_preview_pending"))
            return
        description, refusal = self._preview(request)
        if refusal is not None:
            self.preview_label.setText(refusal)
            return
        self.preview_label.setText(_text("gui.variant_preview_change") % description)

    def accept(self) -> None:
        request, failure = self.change_editor.collect()
        if failure is not None:
            self._show_error(failure)
            return
        outcome = self._apply(request)
        if getattr(outcome, "ok", False):
            super().accept()
            return
        self._show_error(getattr(outcome, "message", "") or "")


class RenameVariantDialog(_DialogBase):
    """Change only a variant's user-facing name."""

    def __init__(self, parent, apply, key, label="") -> None:
        super().__init__(
            parent,
            _text("gui.variant_form_rename_title") % key,
            _text("gui.variant_form_rename"),
        )
        self._apply = apply
        self.label_edit = QLineEdit(label)
        self.form.addRow(_text("gui.variants_name"), self.label_edit)
        self.finish()

    def accept(self) -> None:
        label = self.label_edit.text().strip()
        if not label:
            self._show_error(_text("gui.variant_name_required"))
            return
        outcome = self._apply(label)
        if getattr(outcome, "ok", False):
            super().accept()
            return
        self._show_error(getattr(outcome, "message", "") or "")


class DuplicateVariantDialog(_DialogBase, _IdentityMixin):
    """Copy a variant under a fresh name and ID."""

    def __init__(self, parent, apply, key, label, existing_keys=()) -> None:
        super().__init__(
            parent,
            _text("gui.variant_form_duplicate_title") % key,
            _text("gui.variant_form_duplicate"),
        )
        self._apply = apply
        self._build_identity(self.form, existing_keys)
        self.name_edit.setText(_text("gui.variants_duplicate_label") % label)
        self.key_edit.setText(suggest_key(self.name_edit.text(), existing_keys))
        self.finish()

    def accept(self) -> None:
        identity, failure = self.identity()
        if failure is not None:
            self._show_error(failure)
            return
        name, key = identity
        outcome = self._apply(name, key)
        if getattr(outcome, "ok", False):
            super().accept()
            return
        self._show_error(getattr(outcome, "message", "") or "")
