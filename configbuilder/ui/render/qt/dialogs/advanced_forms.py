"""Advanced-entity forms: modifications, alignment/MSA, templates, bonds.

Every dialog here follows the Stage 3 discipline: it collects values, shows a
service refusal on its own message line and keeps itself open so the value can
be corrected. Nothing here validates a domain rule, allocates anything, reads
a file or decides whether a mode is legal — the *page* supplies the choices
(from the model) and the `apply` callable, and the service answers.

The shared `_FormDialog` base owns the accept/cancel pair, the error line and
the submit path, so the forms below contain only their own fields.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from configbuilder.app.version_features import MSA_PATH_MIN_VERSION
from configbuilder.ui.present.sequence import residue_at
from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.qt.models import fixed_font

__all__ = [
    "AlignmentFormDialog",
    "BondFormDialog",
    "MAX_POSITION",
    "ModificationFormDialog",
    "TemplateEditorDialog",
]

#: The largest residue/atom position any form offers. The model's own rule is
#: "a positive integer, 1-based"; this is a bounded spin box, not a domain
#: limit, and the service/validation layer stays the authority.
MAX_POSITION = 9999

# The MSA source routes, as ``(registry key, kind)`` — the same two routes the
# console offers (``menu.msa_paste_inline`` / ``menu.msa_use_file``).
_SOURCE_OPTIONS = (
    ("menu.msa_paste_inline", "inline"),
    ("menu.msa_use_file", "file"),
)

# The three template routes, as ``(registry key, route word)``.
_TEMPLATE_ROUTES = (
    ("menu.templates_search", "search"),
    ("menu.templates_none", "none"),
    ("menu.templates_list", "list"),
)


class _FormDialog(QDialog):
    """Accept only on a successful apply; show the service's own refusal."""

    def __init__(self, parent, title: str, accept_text: str, apply) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(600)
        self._apply = apply
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        self._buttons = QDialogButtonBox()
        self.accept_button = self._buttons.addButton(
            accept_text, QDialogButtonBox.AcceptRole
        )
        self.cancel_button = self._buttons.addButton(
            _text("gui.form_cancel"), QDialogButtonBox.RejectRole
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._layout = QVBoxLayout(self)
        self._form = QFormLayout()

    def error_text(self) -> str:
        """The last refusal as displayed (empty when nothing was refused)."""
        return self.error_label.text()

    def finish_layout(self) -> None:
        """Add the form, the error line and the buttons (call last)."""
        self._layout.addLayout(self._form)
        self._layout.addWidget(self.error_label)
        self._layout.addWidget(self._buttons)

    def _collect(self):
        raise NotImplementedError

    def accept(self) -> None:
        outcome = self._apply(*self._collect())
        if getattr(outcome, "ok", False):
            super().accept()
            return
        self.error_label.setText(getattr(outcome, "message", "") or "")
        self.error_label.setVisible(True)


class ModificationFormDialog(_FormDialog):
    """Add or edit one modification: a code and a 1-based residue position."""

    def __init__(
        self,
        parent,
        title,
        accept_text,
        apply,
        code="",
        position=1,
        sequence="",
        hint="",
    ) -> None:
        super().__init__(parent, title, accept_text, apply)
        self._sequence = sequence or ""
        self.code_edit = QLineEdit(code)
        self.code_edit.setPlaceholderText(_text("gui.mod_code_placeholder"))
        self.position_spin = QSpinBox()
        self.position_spin.setRange(1, MAX_POSITION)
        self.position_spin.setValue(max(1, min(int(position), MAX_POSITION)))
        self._form.addRow(_text("gui.mod_form_code"), self.code_edit)
        self._form.addRow(_text("gui.mod_form_position"), self.position_spin)
        self.residue_label = QLabel()
        self.residue_label.setWordWrap(True)
        self._form.addRow("", self.residue_label)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setWordWrap(True)
            self._layout.addWidget(hint_label)
        self.finish_layout()
        self.position_spin.valueChanged.connect(self._refresh_residue)
        self._refresh_residue()

    def _refresh_residue(self) -> None:
        """Echo the residue at the chosen position (the console's own echo)."""
        position = self.position_spin.value()
        residue = residue_at(self._sequence, position)
        if residue is None:
            self.residue_label.setText(
                _text("gui.mod_residue_out_of_range")
                % (position, len(self._sequence))
            )
            return
        self.residue_label.setText(_text("gui.mod_residue_echo") % residue)

    def _collect(self):
        return (self.code_edit.text().strip(), self.position_spin.value())


class AlignmentFormDialog(_FormDialog):
    """Choose one alignment mode and, when it needs one, its single source.

    ``modes`` is a sequence of ``(registry label key, service mode word)``
    pairs supplied by the page — the family's legal modes, never a list this
    dialog invented. Source controls appear only for modes that carry a
    source, exactly as the service defines them (``automatic`` and ``free``
    take no source and refuse one).
    """

    def __init__(
        self,
        parent,
        title,
        accept_text,
        apply,
        modes,
        mode="",
        source_kind="",
        source_text="",
        hint="",
    ) -> None:
        super().__init__(parent, title, accept_text, apply)
        self.mode_combo = QComboBox()
        self._mode_words = []
        selected = 0
        for index, (label_key, word) in enumerate(modes):
            self.mode_combo.addItem(_text(label_key))
            self._mode_words.append(word)
            if word == mode:
                selected = index
        self.mode_combo.setCurrentIndex(selected)
        self._form.addRow(_text("gui.alignment_mode"), self.mode_combo)

        self.source_group = QButtonGroup(self)
        self.source_radios = []
        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        for label_key, kind in _SOURCE_OPTIONS:
            radio = QRadioButton(_text(label_key))
            self.source_group.addButton(radio)
            self.source_radios.append((kind, radio))
            source_layout.addWidget(radio)
        self._form.addRow(_text("gui.alignment_source"), source_row)
        self.source_row = source_row

        self.inline_edit = QPlainTextEdit(source_text if source_kind == "inline" else "")
        self.inline_edit.setFont(fixed_font())
        self.inline_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.inline_edit.setMinimumHeight(120)
        self._inline_label = QLabel(_text("gui.alignment_inline"))
        self._form.addRow(self._inline_label, self.inline_edit)

        self.path_edit = QLineEdit(source_text if source_kind == "file" else "")
        self.browse_button = QPushButton(_text("gui.alignment_browse"))
        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(self.browse_button)
        self._path_label = QLabel(_text("gui.alignment_path"))
        self._form.addRow(self._path_label, path_row)
        self.path_row = path_row

        self.hint_label = QLabel(hint or _text("gui.alignment_hint"))
        self.hint_label.setWordWrap(True)
        self.version_label = QLabel(
            _text("gui.alignment_path_version") % MSA_PATH_MIN_VERSION
        )
        self.version_label.setWordWrap(True)
        self._layout.addWidget(self.hint_label)
        self._layout.addWidget(self.version_label)
        self.finish_layout()

        default_kind = source_kind or "inline"
        for kind, radio in self.source_radios:
            radio.setChecked(kind == default_kind)
        self.browse_button.clicked.connect(self.browse)
        self.mode_combo.currentIndexChanged.connect(self._refresh_source_controls)
        self.source_group.buttonClicked.connect(
            lambda _button: self._refresh_source_controls()
        )
        self._refresh_source_controls()

    def browse(self) -> None:
        """Put a chosen alignment file in the path field (nothing is read)."""
        path, _selected = QFileDialog.getOpenFileName(
            self, _text("gui.alignment_file_dialog"), "", _text("gui.file_filter")
        )
        if path:
            self.path_edit.setText(path)

    def current_mode(self) -> str:
        """The service's mode word for the current selection."""
        return self._mode_words[self.mode_combo.currentIndex()]

    def select_mode(self, word: str) -> bool:
        """Select a mode by the service's own word; ``False`` if unknown."""
        if word not in self._mode_words:
            return False
        self.mode_combo.setCurrentIndex(self._mode_words.index(word))
        return True

    def current_source_kind(self) -> str:
        for kind, radio in self.source_radios:
            if radio.isChecked():
                return kind
        return "inline"

    def _source_needed(self) -> bool:
        return self.current_mode() not in ("automatic", "free")

    def _refresh_source_controls(self) -> None:
        """Show only the controls the chosen mode actually uses."""
        needed = self._source_needed()
        for _kind, radio in self.source_radios:
            radio.setEnabled(needed)
        show_inline = needed and self.current_source_kind() == "inline"
        show_path = needed and self.current_source_kind() == "file"
        self._form.setRowVisible(self._inline_label, show_inline)
        self._form.setRowVisible(self._path_label, show_path)
        self.browse_button.setEnabled(show_path)
        self.version_label.setVisible(show_path)
        # The mode explains what it will do, in the console's own words.
        self.hint_label.setText(_text(self._hint_key()))

    def _hint_key(self) -> str:
        mode = self.current_mode()
        if mode == "automatic":
            return "gui.alignment_hint_automatic"
        if mode == "free":
            return "gui.alignment_hint_free"
        return "gui.alignment_hint_source"

    def _collect(self):
        mode = self.current_mode()
        if not self._source_needed():
            return (mode, "", "")
        if self.current_source_kind() == "file":
            return (mode, "file", self.path_edit.text().strip())
        return (mode, "inline", self.inline_edit.toPlainText())


class TemplateEditorDialog(_FormDialog):
    """The protein template states: search allowed, none, or a file list.

    The three routes are the console's own (``menu.templates_search`` /
    ``menu.templates_none`` / ``menu.templates_list``). In list mode each row
    is one reference: an mmCIF file chosen with a file picker, plus its
    optional 0-based index pairs in the form the console asks for
    (``query:template``, comma separated).
    """

    def __init__(
        self, parent, title, accept_text, apply, mode="search", entries=(), hint=""
    ) -> None:
        super().__init__(parent, title, accept_text, apply)
        self.route_group = QButtonGroup(self)
        self.route_radios = []
        route_row = QWidget()
        route_layout = QVBoxLayout(route_row)
        route_layout.setContentsMargins(0, 0, 0, 0)
        for label_key, route in _TEMPLATE_ROUTES:
            radio = QRadioButton(_text(label_key))
            self.route_group.addButton(radio)
            self.route_radios.append((route, radio))
            route_layout.addWidget(radio)
            if route == mode:
                radio.setChecked(True)
        self._form.addRow(_text("gui.templates_mode"), route_row)
        self.route_row = route_row

        self.pairs_note = QLabel(_text("gui.templates_pairs_note"))
        self.pairs_note.setWordWrap(True)
        self._form.addRow("", self.pairs_note)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(
            [_text("gui.templates_col_file"), _text("gui.templates_col_pairs")]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(140)
        for path, pairs in entries:
            self._append_row(path, pairs)
        self.add_file_button = QPushButton(_text("gui.templates_add_file"))
        self.remove_file_button = QPushButton(_text("gui.templates_remove_file"))
        buttons_row = QWidget()
        buttons_layout = QHBoxLayout(buttons_row)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addWidget(self.add_file_button)
        buttons_layout.addWidget(self.remove_file_button)
        buttons_layout.addStretch(1)
        self.buttons_row = buttons_row
        self._form.addRow(self.table)
        self._form.addRow(buttons_row)

        if hint:
            hint_label = QLabel(hint)
            hint_label.setWordWrap(True)
            self._layout.addWidget(hint_label)
        self.finish_layout()

        self.add_file_button.clicked.connect(self.add_file)
        self.remove_file_button.clicked.connect(self.remove_selected)
        self.route_group.buttonClicked.connect(lambda _button: self._refresh_controls())
        self._refresh_controls()

    def _append_row(self, path="", pairs="") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        item = QTableWidgetItem(path)
        # A path is never typed: it comes from the file picker, so the cell
        # is read-only while the pairs cell stays editable in place.
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, item)
        self.table.setItem(row, 1, QTableWidgetItem(pairs))

    def add_file(self) -> None:
        """Add a reference row for a file the user picks."""
        path, _selected = QFileDialog.getOpenFileName(
            self,
            _text("gui.templates_file_dialog"),
            "",
            _text("gui.templates_file_filter"),
        )
        if path:
            self._append_row(path, "")

    def remove_selected(self) -> None:
        """Remove the selected rows (the last one when nothing is selected)."""
        rows = sorted(
            {index.row() for index in self.table.selectedIndexes()}, reverse=True
        )
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for row in rows:
            self.table.removeRow(row)

    def current_route(self) -> str:
        for route, radio in self.route_radios:
            if radio.isChecked():
                return route
        return "search"

    def select_route(self, route: str) -> bool:
        """Choose one template route; ``False`` when it is not a route."""
        for candidate, radio in self.route_radios:
            if candidate == route:
                radio.setChecked(True)
                self._refresh_controls()
                return True
        return False

    def _refresh_controls(self) -> None:
        listed = self.current_route() == "list"
        for row_widget in (self.pairs_note, self.table, self.buttons_row):
            row_widget.setVisible(listed)
        self.remove_file_button.setEnabled(self.table.rowCount() > 0)

    def entries(self):
        """The rows as ``(path, pairs_text)`` pairs, in display order."""
        rows = []
        for row in range(self.table.rowCount()):
            path = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            pairs = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
            rows.append((path, pairs))
        return tuple(rows)

    def _collect(self):
        route = self.current_route()
        if route != "list":
            return (route, ())
        return (route, self.entries())


class BondFormDialog(_FormDialog):
    """One covalent bond: two endpoints, each entity/residue/atom.

    ``choices`` is the page's own ``(entity key, display label)`` list built
    from the current records, so the user picks an entity by a real
    identifier and never types an internal key.
    """

    def __init__(
        self,
        parent,
        title,
        accept_text,
        apply,
        choices,
        left=None,
        right=None,
        hint="",
    ) -> None:
        super().__init__(parent, title, accept_text, apply)
        self.left_key, self.left_residue, self.left_atom = self._endpoint(
            _text("gui.bond_endpoint_a"), choices, left
        )
        self.right_key, self.right_residue, self.right_atom = self._endpoint(
            _text("gui.bond_endpoint_b"), choices, right
        )
        if hint:
            hint_label = QLabel(hint)
            hint_label.setWordWrap(True)
            self._layout.addWidget(hint_label)
        self.finish_layout()

    def _endpoint(self, label, choices, preselected):
        """One endpoint's three controls, added to the form."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        key_combo = QComboBox()
        for key, display in choices:
            key_combo.addItem(display, key)
        if preselected is not None:
            index = key_combo.findData(preselected)
            if index >= 0:
                key_combo.setCurrentIndex(index)
        residue_spin = QSpinBox()
        residue_spin.setRange(1, MAX_POSITION)
        atom_edit = QLineEdit()
        atom_edit.setPlaceholderText(_text("gui.bond_atom_placeholder"))
        layout.addWidget(key_combo, 2)
        layout.addWidget(residue_spin)
        layout.addWidget(atom_edit, 1)
        self._form.addRow(label, row)
        self._form.addRow("", QLabel(_text("gui.bond_columns_note")))
        return key_combo, residue_spin, atom_edit

    def _endpoint_values(self, key_combo, residue_spin, atom_edit):
        return (
            key_combo.currentData() or "",
            int(residue_spin.value()),
            atom_edit.text().strip(),
        )

    def _collect(self):
        left = self._endpoint_values(self.left_key, self.left_residue, self.left_atom)
        right = self._endpoint_values(
            self.right_key, self.right_residue, self.right_atom
        )
        return left + right
