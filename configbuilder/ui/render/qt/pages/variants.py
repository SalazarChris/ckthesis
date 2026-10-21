"""The Variants & Batch workspace: specs, quantity series and file batches.

One workspace, organised around the three things a user can want to do
(Stage 9). The page opens on a small **chooser** with three plainly worded
actions and one sentence each:

- **Create one variant** — a typed editor built from ``VariantService``'s own
  ``edit_options`` and entity choices; create and append changes through the
  service, preview the declared changes and the resulting JSON.
- **Create a quantity series** — the service plans the series as data first;
  the page shows that plan and only then offers the commit.
- **Create variants from a file** — the service previews the file first; the
  commit is the service's all-or-nothing batch.

Choosing one replaces the chooser with only that path's form and a *Back to
choices* action; nothing from the other two paths is on screen. Below, the
existing variants, the selected variant's declared changes / JSON, and the
secondary actions (add a change, rename, duplicate, remove) that act on the
selection. No wording here names an internal type: the page talks about
variants, entities and changes.

The base job is only ever read here. Nothing in this module builds a variant,
an edit, a record, a wire document or a JSON string: every mutation is a
pass-through on ``GuiState`` to an existing service method. A refusal is
shown with the service's own message and changes nothing. Validation is not
run here; variant creation and generation are not gated.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from configbuilder.app.results import MutationOutput
from configbuilder.model import (
    ComponentRecord,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
)
from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.qt.dialogs import (
    DuplicateVariantDialog,
    NewVariantDialog,
    RenameVariantDialog,
    VariantChangeDialog,
    VariantChangeEditor,
    confirm_variant_removal,
)
from configbuilder.ui.render.qt.models import (
    VariantRow,
    VariantTableModel,
    family_label,
    fixed_font,
)
from configbuilder.ui.render.qt.style import (
    heading_label,
    hint_label,
    page_title_label,
)

__all__ = ["VariantsPage"]

_FAMILY_BY_TYPE = {
    FamilyARecord: "protein",
    FamilyBRecord: "rna",
    FamilyCRecord: "dna",
    ComponentRecord: "ligand",
}

_SERIES_FAMILY_LABELS = (
    ("menu.family_protein", "protein"),
    ("menu.family_dna", "dna"),
    ("menu.family_ligand", "ligand"),
)

class VariantsPage(QWidget):
    """The one workspace for manual variants, quantity series and batches."""

    def __init__(self, state, notify=None, problems=None, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._notify = notify if notify is not None else (lambda message: None)
        self._problems = problems if problems is not None else (lambda message: None)
        self._selected_key = ""
        self._series_plan = None
        self._series_signature = None
        self._batch_signature = None
        # The one modal a test replaces: the removal confirmation.
        self.variant_confirmer = confirm_variant_removal
        self._build()

    # -- construction ------------------------------------------------------

    def _build(self) -> None:
        """The creation choices above, the existing variants below.

        The upper pane is either the three-choice chooser, one creation path,
        or the selected variant's details — never all of them at once. The
        three creation paths each open with a sentence saying what they do;
        the details pane shows the selected variant's declared changes,
        validation state and JSON. Selecting a variant brings that pane
        forward, so choosing a row never sends the user hunting for where its
        details went. The existing-variants list stays below the chooser, out
        of the way until there is something in it.
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._build_scrollable(body))

    def _build_scrollable(self, body):
        """The page's content, kept readable in a short window."""
        layout = body.layout()
        self._title = page_title_label(_text("gui.variants_title"))
        self._title.setWordWrap(True)
        self._base_label = QLabel()
        self._base_label.setWordWrap(True)
        self._base_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        note = hint_label(_text("gui.variants_intro"))
        session = QLabel(_text("gui.variants_session_note"))
        session.setWordWrap(True)
        layout.addWidget(self._title)
        layout.addWidget(self._base_label)
        layout.addWidget(note)
        layout.addWidget(session)

        # The choices come first: the page opens on the three ways to create
        # a variant, and the existing-variants list (with its edit actions)
        # sits underneath rather than dominating the first screen.
        self.splitter = QSplitter(Qt.Vertical)
        self.chooser_page = self._build_chooser()
        self.one_page = self._build_one_tab()
        self.series_page = self._build_series_tab()
        self.batch_page = self._build_batch_tab()
        self.details_page = self._build_details()
        self.workspace = QStackedWidget()
        self.workspace.setObjectName("variantsWorkspace")
        for page in (
            self.chooser_page,
            self.one_page,
            self.series_page,
            self.batch_page,
            self.details_page,
        ):
            self.workspace.addWidget(page)
        self.workspace.setCurrentWidget(self.chooser_page)
        self.list_group = self._build_list()
        self.splitter.addWidget(self.workspace)
        self.splitter.addWidget(self.list_group)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter, 1)
        # The list and the workspace tab both have useful minimum heights, so
        # the body keeps them and the page scrolls instead of clipping them.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(body)
        return scroll

    def _build_chooser(self):
        """The first screen: three actions, one sentence each, nothing else.

        Each button opens **only** its own workflow. The descriptions are the
        same registry wording the workflow itself opens with, so a user who
        picks a path is not surprised by different vocabulary on the next
        screen, and the base-job sentence states that nothing is created yet.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(heading_label(_text("gui.variants_choose_title")))
        layout.addWidget(hint_label(_text("gui.variants_choose_intro")))
        layout.addSpacing(4)
        self.one_choice_button = QPushButton(_text("gui.variants_one_title"))
        self.series_choice_button = QPushButton(_text("gui.variants_series_title"))
        self.batch_choice_button = QPushButton(_text("gui.variants_batch_title"))
        self.one_choice_button.clicked.connect(self.open_one_path)
        self.series_choice_button.clicked.connect(self.open_series_path)
        self.batch_choice_button.clicked.connect(self.open_batch_path)
        for button, hint_key in (
            (self.one_choice_button, "gui.variants_one_hint"),
            (self.series_choice_button, "gui.variants_series_hint"),
            (self.batch_choice_button, "gui.variants_batch_hint"),
        ):
            button.setProperty("role", "choice")
            button.setMinimumHeight(34)
            button.setAccessibleName(button.text())
            layout.addWidget(button)
            layout.addWidget(hint_label(_text(hint_key)))
            layout.addSpacing(6)
        layout.addStretch(1)
        return page

    def _path_header(self, title_key: str):
        """A path page's heading and its *Back to choices* action."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        back = QPushButton(_text("gui.variants_back"))
        back.setProperty("role", "quiet")
        back.clicked.connect(self.back_to_choices)
        layout.addWidget(back)
        layout.addWidget(heading_label(_text(title_key)), 1)
        return row, back

    # -- path navigation ---------------------------------------------------

    def open_one_path(self) -> None:
        """Show only the one-variant workflow."""
        self.workspace.setCurrentWidget(self.one_page)

    def open_series_path(self) -> None:
        """Show only the quantity-series workflow."""
        self.workspace.setCurrentWidget(self.series_page)

    def open_batch_path(self) -> None:
        """Show only the file-batch workflow."""
        self.workspace.setCurrentWidget(self.batch_page)

    def back_to_choices(self) -> None:
        """Return to the three choices; no plan is committed by leaving."""
        self.workspace.setCurrentWidget(self.chooser_page)

    def _show_details(self) -> None:
        """Show the selected variant's details, or the choices when none is."""
        if self.selected_key():
            self.workspace.setCurrentWidget(self.details_page)
        else:
            self.workspace.setCurrentWidget(self.chooser_page)

    def current_path(self) -> str:
        """Which lower pane is showing: choose, one, series, batch or details."""
        current = self.workspace.currentWidget()
        for name, page in (
            ("choose", self.chooser_page),
            ("one", self.one_page),
            ("series", self.series_page),
            ("batch", self.batch_page),
            ("details", self.details_page),
        ):
            if current is page:
                return name
        return ""

    def _build_actions(self):
        """The secondary actions, all acting on the selected variant.

        Creating a variant is *not* here: it is the first creation tab above,
        so the create action is not one button among five edit actions.
        """
        row = QWidget()
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(6)
        self.add_change_button = QPushButton(_text("gui.variants_add_change"))
        self.rename_button = QPushButton(_text("gui.variants_rename"))
        self.duplicate_button = QPushButton(_text("gui.variants_duplicate"))
        self.remove_button = QPushButton(_text("gui.variants_remove"))
        self.add_change_button.clicked.connect(self.add_change)
        self.rename_button.clicked.connect(self.rename_variant)
        self.duplicate_button.clicked.connect(self.duplicate_variant)
        self.remove_button.clicked.connect(self.remove_variant)
        # Two short rows rather than one long strip: four actions in a single
        # line forced the whole page wider than the window at 940 px.
        for column, button in enumerate(
            (self.add_change_button, self.rename_button, self.duplicate_button)
        ):
            layout.addWidget(button, 0, column)
        layout.addWidget(self.remove_button, 1, 0)
        layout.setColumnStretch(3, 1)
        return row

    def _build_list(self):
        group = QGroupBox(_text("gui.variants_list_group"))
        group.setMinimumHeight(190)
        layout = QVBoxLayout(group)
        layout.addWidget(hint_label(_text("gui.variants_list_hint")))
        layout.addWidget(self._build_actions())
        self.variant_model = VariantTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.variant_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setMinimumHeight(150)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        self._empty_label = QLabel(_text("gui.variants_none"))
        self._empty_label.setWordWrap(True)
        layout.addWidget(self.table)
        layout.addWidget(self._empty_label)
        return group

    def _build_details(self):
        """The selected variant's declared changes and resulting JSON."""
        page = QWidget()
        layout = QVBoxLayout(page)
        self.detail_title = QLabel(_text("gui.variants_no_selection"))
        self.detail_title.setWordWrap(True)
        layout.addWidget(self.detail_title)
        self.detail_tabs = QTabWidget()
        self.changes_list = QListWidget()
        self.changes_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.detail_tabs.addTab(self.changes_list, _text("gui.variants_tab_changes"))
        json_page = QWidget()
        json_layout = QVBoxLayout(json_page)
        self.json_note = QLabel()
        self.json_note.setWordWrap(True)
        self.json_view = QPlainTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setFont(fixed_font())
        self.json_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        json_layout.addWidget(self.json_note)
        json_layout.addWidget(self.json_view, 1)
        self.detail_tabs.addTab(json_page, _text("gui.variants_tab_json"))
        layout.addWidget(self.detail_tabs, 1)
        self.details_page = page
        return page

    def _build_one_tab(self):
        """Path 1: one variant, made from a single supported change."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        header, self.one_back = self._path_header("gui.variants_one_title")
        layout.addWidget(header)
        layout.addWidget(hint_label(_text("gui.variants_one_hint")))
        row = QHBoxLayout()
        self.new_button = QPushButton(_text("gui.variants_new"))
        self.new_button.setProperty("role", "primary")
        self.new_button.clicked.connect(self.new_variant)
        row.addWidget(self.new_button)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _build_series_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        header, self.series_back = self._path_header("gui.variants_series_title")
        layout.addWidget(header)
        # Explanations carry the sheet's shared hint role, exactly as the
        # other pages' helper text does.
        layout.addWidget(hint_label(_text("gui.variants_series_hint")))
        layout.addWidget(hint_label(_text("gui.variants_series_names")))
        body = QHBoxLayout()
        column = QVBoxLayout()
        column.addWidget(QLabel(_text("gui.variants_series_components")))
        self.series_components = QListWidget()
        self.series_components.setMinimumHeight(90)
        self.series_components.itemChanged.connect(self._invalidate_series)
        column.addWidget(self.series_components)
        body.addLayout(column, 2)
        form = QFormLayout()
        self.series_start = QSpinBox()
        self.series_start.setRange(1, 999)
        self.series_start.setValue(1)
        self.series_factor = QSpinBox()
        self.series_factor.setRange(1, 999)
        self.series_factor.setValue(2)
        self.series_levels = QSpinBox()
        self.series_levels.setRange(1, 100)
        self.series_levels.setValue(3)
        for spin in (self.series_start, self.series_factor, self.series_levels):
            spin.valueChanged.connect(self._invalidate_series)
        form.addRow(_text("gui.variants_series_start"), self.series_start)
        form.addRow(_text("gui.variants_series_factor"), self.series_factor)
        form.addRow(_text("gui.variants_series_levels"), self.series_levels)
        buttons = QHBoxLayout()
        self.series_preview_button = QPushButton(_text("gui.variants_series_preview"))
        self.series_create_button = QPushButton(_text("gui.variants_series_create"))
        self.series_preview_button.clicked.connect(self.preview_series)
        self.series_create_button.clicked.connect(self.create_series)
        self.series_create_button.setEnabled(False)
        buttons.addWidget(self.series_preview_button)
        buttons.addWidget(self.series_create_button)
        buttons.addStretch(1)
        body.addLayout(form, 1)
        layout.addLayout(body)
        # The two actions sit below the two columns, not in the form: a
        # QFormLayout aligns one label column and one field column for every
        # row, so a wide button row in the form widened the whole page.
        layout.addWidget(self._layout_widget(buttons))
        self.series_note = QLabel(_text("gui.variants_series_empty"))
        self.series_note.setWordWrap(True)
        layout.addWidget(self.series_note)
        self.series_table = QTableWidget(0, 2)
        self.series_table.setHorizontalHeaderLabels(
            [
                _text("gui.variants_series_col_multiplier"),
                _text("gui.variants_series_col_counts"),
            ]
        )
        self.series_table.verticalHeader().setVisible(False)
        self.series_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.series_table.setMinimumHeight(100)
        layout.addWidget(self.series_table)
        return page

    def _layout_widget(self, layout):
        widget = QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        return widget

    def _build_batch_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        header, self.batch_back = self._path_header("gui.variants_batch_title")
        layout.addWidget(header)
        layout.addWidget(hint_label(_text("gui.variants_batch_hint")))
        layout.addWidget(hint_label(_text("gui.variants_batch_family_note")))
        form = QFormLayout()
        self.batch_family = QComboBox()
        for label_key, family in _SERIES_FAMILY_LABELS:
            self.batch_family.addItem(_text(label_key), family)
        self.batch_family.currentIndexChanged.connect(self._invalidate_batch)
        self.batch_path = QLineEdit()
        self.batch_path.setReadOnly(True)
        self.batch_path.textChanged.connect(self._invalidate_batch)
        self.batch_browse = QPushButton(_text("gui.variants_batch_browse"))
        self.batch_browse.clicked.connect(self.browse_batch)
        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.batch_path, 1)
        path_layout.addWidget(self.batch_browse)
        form.addRow(_text("gui.variants_batch_family"), self.batch_family)
        form.addRow(_text("gui.variants_batch_path"), path_row)
        buttons = QHBoxLayout()
        self.batch_preview_button = QPushButton(_text("gui.variants_batch_preview"))
        self.batch_create_button = QPushButton(_text("gui.variants_batch_create"))
        self.batch_preview_button.clicked.connect(self.preview_batch)
        self.batch_create_button.clicked.connect(self.create_batch)
        self.batch_create_button.setEnabled(False)
        buttons.addWidget(self.batch_preview_button)
        buttons.addWidget(self.batch_create_button)
        buttons.addStretch(1)
        layout.addLayout(form)
        layout.addWidget(self._layout_widget(buttons))
        self.batch_note = QLabel(_text("gui.variants_batch_preview_empty"))
        self.batch_note.setWordWrap(True)
        layout.addWidget(self.batch_note)
        self.batch_table = QTableWidget(0, 1)
        self.batch_table.setHorizontalHeaderLabels(
            [_text("gui.variants_batch_col_entry")]
        )
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.batch_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.batch_table.setMinimumHeight(100)
        layout.addWidget(self.batch_table)
        layout.addWidget(hint_label(_text("gui.variants_batch_no_normalization")))
        return page

    # -- reading the page back --------------------------------------------

    @property
    def state(self):
        return self._state

    def selected_key(self) -> str:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return ""
        row = self.variant_model.row_at(indexes[0].row())
        return row.key if row is not None else ""

    def selected_spec(self):
        key = self.selected_key()
        for spec in self._state.specs:
            if spec.key == key:
                return spec
        return None

    # -- refresh -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-read specs, details and the two creation forms."""
        configuration = self._state.configuration
        if configuration is None:
            self.variant_model.set_rows(())
            self._base_label.setText(_text("menu.no_project"))
            self._empty_label.setVisible(False)
            self.list_group.setVisible(False)
            self._clear_details()
            self._refresh_series_components()
            self._update_actions()
            return

        specs = self._state.specs
        self._base_label.setText(
            _text("gui.variants_base") % configuration.metadata.name
            + "  ·  "
            + _text("gui.variants_base_detail")
            % (len(configuration.records), len(specs))
        )
        rows = [
            VariantRow(
                spec.key,
                spec.label,
                self._changes_text(spec.key),
            )
            for spec in specs
        ]
        self.variant_model.set_rows(rows)
        self._empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        # With nothing to list, the chooser is the whole page: an empty list
        # and five disabled actions above the choices only get in the way.
        was_visible = self.list_group.isVisible()
        self.list_group.setVisible(bool(rows))
        if rows and not was_visible:
            # Give the newly populated list a useful share of the page rather
            # than the collapsed height it had while it was hidden.
            self.splitter.setSizes([460, 300])
        self._restore_selection()
        self._refresh_details()
        self._refresh_series_components()
        self._update_actions()

    def _restore_selection(self) -> None:
        keys = {row.key for row in self.variant_model.rows}
        if self._selected_key not in keys:
            self._selected_key = ""
        if not keys:
            self.table.clearSelection()
            return
        position = self.variant_model.row_for_key(self._selected_key)
        if position < 0:
            self.table.clearSelection()
            return
        self.table.blockSignals(True)
        self.table.selectRow(position)
        self.table.blockSignals(False)

    def _update_actions(self) -> None:
        has_project = self._state.configuration is not None
        selected = bool(self.selected_key())
        self.new_button.setEnabled(has_project)
        for button in (
            self.one_choice_button,
            self.series_choice_button,
            self.batch_choice_button,
        ):
            button.setEnabled(has_project)
        for button in (
            self.add_change_button,
            self.rename_button,
            self.duplicate_button,
            self.remove_button,
        ):
            button.setEnabled(has_project and selected)

    # -- details -----------------------------------------------------------

    def _on_selection(self, *_args) -> None:
        self._selected_key = self.selected_key()
        self._update_actions()
        self._refresh_details()
        if self._selected_key:
            # Choosing a row is a request to look at that variant: show its
            # details so its changes are never 'somewhere else'.
            self._show_details()

    def _clear_details(self) -> None:
        self.detail_title.setText(_text("gui.variants_no_selection"))
        self.changes_list.clear()
        self.json_view.setPlainText("")
        self.json_note.setText("")

    def _refresh_details(self) -> None:
        spec = self.selected_spec()
        if spec is None:
            self._clear_details()
            return
        self.detail_title.setText("%s  ·  %s" % (spec.label, spec.key))
        self.changes_list.clear()
        for text_value in self._change_lines(spec.key):
            self.changes_list.addItem(QListWidgetItem(text_value))
        if not self.changes_list.count():
            item = QListWidgetItem(_text("gui.variants_changes_none"))
            item.setFlags(Qt.NoItemFlags)
            self.changes_list.addItem(item)
        self._refresh_json(spec.key)

    def _refresh_json(self, key: str) -> None:
        text, reason = self._state.preview_variant_json(key)
        if text is None:
            self.json_view.setPlainText("")
            self.json_note.setText(_text("gui.variants_json_unavailable") % reason)
            return
        self.json_view.setPlainText(text)
        self.json_note.setText("")

    # -- change rendering --------------------------------------------------

    def _changes_text(self, key: str) -> str:
        lines = self._change_lines(key)
        return "; ".join(lines) if lines else _text("gui.variants_no_changes")

    def _change_lines(self, key: str):
        lines = []
        for kind, described, record in self._state.spec_change_descriptions(key):
            lines.append(self._change_text(kind, described))
        return lines

    def _change_text(self, kind, described) -> str:
        record = described.get("record_key", "") or _text("gui.variants_no_changes")
        if kind == "SetSequence":
            return _text("gui.variant_change_sequence") % (
                record,
                described.get("text", ""),
            )
        if kind == "SetName":
            return _text("gui.variant_change_job_name") % described.get("job_name", "")
        if kind in ("SetJobDescription", "SetDescription"):
            presence = described.get("presence", {})
            if presence.get("form") == "Present":
                value = presence.get("value", "")
            elif presence.get("form") == "ExplicitEmpty":
                value = _text("gui.variant_value_empty")
            else:
                value = _text("gui.variant_value_unset")
            key = (
                "gui.variant_change_description"
                if kind == "SetDescription"
                else "gui.variant_change_job_description"
            )
            if kind == "SetDescription":
                return _text(key) % (record, value)
            return _text(key) % value
        if kind == "SetSeeds":
            return _text("gui.variant_change_seeds") % ", ".join(
                str(value) for value in described.get("seeds", ())
            )
        if kind == "AddModification":
            return _text("gui.variant_change_add_mod") % (
                described.get("code", ""),
                described.get("position", 0),
                record,
            )
        if kind == "RemoveModification":
            return _text("gui.variant_change_remove_mod") % (
                described.get("index", 0),
                record,
            )
        if kind in ("SetAlignment", "SetSingleAlignment"):
            return _text("gui.variant_change_alignment") % (
                record,
                self._alignment_text(described.get("alignment", {})),
            )
        if kind == "SetReferences":
            references = described.get("references", {})
            form = references.get("form", "")
            if form == "SearchAllowed":
                value = _text("gui.variant_route_search")
            else:
                value = _text("gui.variant_reference_count") % len(
                    references.get("items", ())
                )
            return _text("gui.variant_change_references") % (record, value)
        if kind == "SetComponentCount":
            return _text("gui.variant_change_count") % (
                record,
                described.get("count", 0),
            )
        if kind == "SetComponentRepresentation":
            representation = described.get("representation", {})
            if representation.get("form") == "ByCode":
                value = ", ".join(representation.get("codes", ()))
            else:
                value = representation.get("text", "")
            return _text("gui.variant_change_representation") % (record, value)
        if kind == "AddRecord":
            family = {
                "FamilyARecord": _text("menu.family_protein"),
                "FamilyBRecord": _text("menu.family_rna"),
                "FamilyCRecord": _text("menu.family_dna"),
                "ComponentRecord": _text("menu.family_ligand"),
            }.get(described.get("family", ""), described.get("family", ""))
            return _text("gui.variant_change_add_record") % (
                family,
                ", ".join(described.get("ids", ())),
            )
        if kind == "RemoveRecord":
            return _text("gui.variant_change_remove_record") % described.get(
                "record_key", ""
            )
        if kind in ("AddLinkage", "RemoveLinkage"):
            return _text("gui.variant_change_bond")
        if kind == "SetComponentDefinition":
            return _text("gui.variant_change_definition")
        if kind == "SetFormatTarget":
            return _text("gui.variant_change_version")
        return _text("gui.variant_change_unknown")

    def _alignment_text(self, alignment) -> str:
        form = alignment.get("form", "")
        if form == "Automatic":
            return _text("menu.msa_mode_auto")
        if form == "Free":
            return _text("menu.msa_mode_free")
        if form == "Provided":
            return _text("menu.msa_mode_provided")
        source = alignment.get("source", {})
        if source.get("form") == "inline":
            value = _text("gui.alignment_source_inline")
        else:
            value = _text("gui.alignment_source_file")
        return "%s (%s)" % (form, value)

    # -- manual variants ---------------------------------------------------

    def _record_by_key(self, key):
        configuration = self._state.configuration
        if configuration is None:
            return None
        for record in configuration.records:
            if record.ids.primary.value == key:
                return record
        return None

    def _family_by_key(self):
        configuration = self._state.configuration
        if configuration is None:
            return {}
        return {
            record.ids.primary.value: _FAMILY_BY_TYPE[type(record)]
            for record in configuration.records
            if type(record) in _FAMILY_BY_TYPE
        }

    def _entity_label(self, key) -> str:
        record = self._record_by_key(key)
        if record is None:
            return key
        return "%s  ·  %s" % (key, family_label(record))

    def _entity_options(self, families=None):
        options = []
        for choice in self._state.all_entity_choices():
            family = self._family_by_key().get(choice.value, "")
            if families is not None and family not in families:
                continue
            options.append((choice.value, self._entity_label(choice.value)))
        return tuple(options)

    def _component_options(self):
        options = []
        for choice in self._state.component_count_choices():
            options.append(
                (
                    choice.value,
                    "%s  ·  %s (%d)"
                    % (choice.value, _text("menu.family_ligand"), choice.detail or 1),
                )
            )
        return tuple(options)

    def _modifications_by_key(self, spec_key=None):
        rows = {}
        if spec_key is not None:
            for index, record_key, display in self._state.modification_choices(spec_key):
                rows.setdefault(record_key, []).append((index, display))
            return rows
        configuration = self._state.configuration
        if configuration is None:
            return rows
        for record in configuration.records:
            key = record.ids.primary.value
            for index, modification in enumerate(
                getattr(record, "modifications", ()) or ()
            ):
                rows.setdefault(key, []).append(
                    (
                        index,
                        "%s @ %s (%s)"
                        % (
                            key,
                            modification.position.value,
                            modification.code.value,
                        ),
                    )
                )
        return rows

    def _make_editor(self, spec_key=None):
        sequences = {}
        if spec_key is not None:
            expanded = self._state.preview_variant(spec_key)
            if expanded.ok:
                for record in expanded.variants[0].configuration.records:
                    if hasattr(record, "sequence"):
                        sequences[record.ids.primary.value] = record.sequence.text
        if not sequences and self._state.configuration is not None:
            sequences = {
                record.ids.primary.value: record.sequence.text
                for record in self._state.configuration.records
                if hasattr(record, "sequence")
            }
        return VariantChangeEditor(
            parent=None,
            options=self._state.edit_options(),
            entity_options=self._entity_options(),
            polymer_options=self._entity_options(("protein", "rna", "dna")),
            protein_options=self._entity_options(("protein",)),
            alignment_options=self._entity_options(("protein", "rna")),
            component_options=self._component_options(),
            family_by_key=self._family_by_key(),
            sequences_by_key=sequences,
            modifications_by_key=self._modifications_by_key(spec_key),
            template_filter=_text("gui.templates_file_filter"),
        )

    def new_variant(self) -> bool:
        if self._state.configuration is None:
            self._problems(_text("menu.no_project"))
            return False
        keys = [spec.key for spec in self._state.specs]
        dialog = NewVariantDialog(
            self,
            apply=self._create_variant,
            editor=self._make_editor(),
            existing_keys=keys,
            preview=self._preview_change,
        )
        if dialog.exec() == NewVariantDialog.Accepted:
            self._notify(_text("gui.variants_created"))
            self.refresh()
            self._show_details()
            return True
        return False

    def _create_variant(self, name, key, request):
        value, failure = self._prepare_value(request)
        if failure is not None:
            return MutationOutput(ok=False, message=failure)
        outcome = self._state.add_spec_with_edit(
            key, name, request.kind, value, record_key=request.record_key
        )
        if outcome.ok:
            self._selected_key = key
        return outcome

    def add_change(self) -> bool:
        spec = self.selected_spec()
        if spec is None:
            self._problems(_text("gui.variants_select_first"))
            return False
        dialog = VariantChangeDialog(
            self,
            apply=lambda request: self._add_change(spec.key, request),
            editor=self._make_editor(spec.key),
            key=spec.key,
            preview=self._preview_change,
        )
        if dialog.exec() == VariantChangeDialog.Accepted:
            self._notify(_text("gui.variants_change_added"))
            self._selected_key = spec.key
            self.refresh()
            return True
        return False

    def _add_change(self, key, request):
        value, failure = self._prepare_value(request)
        if failure is not None:
            return MutationOutput(ok=False, message=failure)
        return self._state.apply_variant_edit(
            key, request.kind, value, record_key=request.record_key
        )

    def _preview_change(self, request):
        """The service's own description of a proposed change, or refusal.

        Read-only: ``describe_change`` builds the edit through the same path
        the commit uses and describes it, so the dialog's preview cannot
        show something the service would refuse.
        """
        value, failure = self._prepare_value(request)
        if failure is not None:
            return None, failure
        described, failure = self._state.describe_variant_change(
            request.kind, value, record_key=request.record_key
        )
        if failure is not None:
            return None, failure
        return (
            "; ".join(
                self._change_text(row.get("kind", ""), row) for row in described
            ),
            None,
        )

    def _prepare_value(self, request):
        """The value the service takes, or a refusal from the service itself.

        Only ``add_entity`` needs a conversion: its records are built by
        ``VariantService.build_add_records`` (the same validated constructors
        the base path uses), never by this page.
        """
        if request.kind == "add_entity":
            family, text_value, representation_kind = request.value
            if family == "ligand":
                records, failure = self._state.build_add_records(
                    family,
                    "",
                    representation=text_value,
                    representation_kind=representation_kind,
                )
            else:
                records, failure = self._state.build_add_records(family, text_value)
            if failure is not None:
                return None, failure
            return records, None
        return request.value, None

    def rename_variant(self) -> bool:
        spec = self.selected_spec()
        if spec is None:
            self._problems(_text("gui.variants_select_first"))
            return False
        dialog = RenameVariantDialog(
            self,
            apply=lambda label: self._state.update_spec(spec.key, label=label),
            key=spec.key,
            label=spec.label,
        )
        if dialog.exec() == RenameVariantDialog.Accepted:
            self._notify(_text("gui.variants_renamed"))
            self._selected_key = spec.key
            self.refresh()
            return True
        return False

    def duplicate_variant(self) -> bool:
        spec = self.selected_spec()
        if spec is None:
            self._problems(_text("gui.variants_select_first"))
            return False
        keys = [candidate.key for candidate in self._state.specs]
        dialog = DuplicateVariantDialog(
            self,
            apply=lambda label, key: self._duplicate(spec.key, label, key),
            key=spec.key,
            label=spec.label,
            existing_keys=keys,
        )
        if dialog.exec() == DuplicateVariantDialog.Accepted:
            self._notify(_text("gui.variants_duplicated"))
            self.refresh()
            return True
        return False

    def _duplicate(self, key, label, new_key):
        outcome = self._state.duplicate_spec(key, new_key, label)
        if outcome.ok:
            self._selected_key = new_key
        return outcome

    def remove_variant(self) -> bool:
        spec = self.selected_spec()
        if spec is None:
            self._problems(_text("gui.variants_select_first"))
            return False
        question = _text("gui.variants_remove_question") % (spec.label, spec.key)
        if not self.variant_confirmer(self, question):
            return False
        outcome = self._state.remove_spec(spec.key)
        if not outcome.ok:
            self._problems(outcome.message or "")
            return False
        self._selected_key = ""
        self._notify(_text("gui.variants_removed"))
        self.refresh()
        return True

    # -- quantity series ---------------------------------------------------

    def _refresh_series_components(self) -> None:
        checked = self.checked_components()
        self.series_components.blockSignals(True)
        self.series_components.clear()
        for choice in self._state.component_count_choices():
            item = QListWidgetItem(
                "%s  ·  %d" % (choice.label, choice.detail or 1)
            )
            item.setData(Qt.UserRole, choice.value)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if choice.value in checked else Qt.Unchecked)
            self.series_components.addItem(item)
        self.series_components.blockSignals(False)

    def checked_components(self):
        checked = set()
        for row in range(self.series_components.count()):
            item = self.series_components.item(row)
            if item.checkState() == Qt.Checked:
                checked.add(item.data(Qt.UserRole))
        return checked

    def _series_values(self):
        return (
            tuple(
                self.series_components.item(row).data(Qt.UserRole)
                for row in range(self.series_components.count())
                if self.series_components.item(row).checkState() == Qt.Checked
            ),
            int(self.series_start.value()),
            int(self.series_factor.value()),
            int(self.series_levels.value()),
        )

    def _invalidate_series(self, *_args) -> None:
        if self._series_signature is None:
            return
        if self._series_values() != self._series_signature:
            self.series_create_button.setEnabled(False)
            self.series_note.setText(_text("gui.variants_series_stale"))

    def preview_series(self) -> bool:
        keys, start, factor, levels = self._series_values()
        if not keys:
            self._problems(_text("gui.variants_series_select"))
            return False
        rows, failure = self._state.quantity_series_plan(keys, start, factor, levels)
        if failure is not None:
            self._problems(failure)
            return False
        self._fill_series_table(rows)
        self._series_plan = rows
        self._series_signature = (keys, start, factor, levels)
        self.series_note.setText(_text("gui.variants_series_planned") % len(rows))
        self.series_create_button.setEnabled(True)
        return True

    def _fill_series_table(self, rows) -> None:
        self.series_table.setRowCount(0)
        for multiplier, counts in rows:
            row = self.series_table.rowCount()
            self.series_table.insertRow(row)
            self.series_table.setItem(row, 0, QTableWidgetItem(str(multiplier)))
            self.series_table.setItem(
                row,
                1,
                QTableWidgetItem(
                    ", ".join(
                        "%s: %d" % (key, count) for key, count in sorted(counts.items())
                    )
                ),
            )

    def create_series(self) -> bool:
        keys, start, factor, levels = self._series_values()
        if self._series_signature is None:
            self._problems(_text("gui.variants_series_empty"))
            return False
        if (keys, start, factor, levels) != self._series_signature:
            self._problems(_text("gui.variants_series_stale"))
            return False
        outcome = self._state.create_quantity_series(keys, start, factor, levels)
        if not outcome.ok:
            self._problems(outcome.message or "")
            return False
        self._notify(outcome.message or _text("gui.variants_series_created") % len(self._series_plan))
        self._series_plan = None
        self._series_signature = None
        self.series_create_button.setEnabled(False)
        self.series_table.setRowCount(0)
        self.series_note.setText(_text("gui.variants_series_empty"))
        self.refresh()
        self._show_details()
        return True

    # -- batch from file ---------------------------------------------------

    def browse_batch(self) -> str:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            _text("gui.variants_batch_preview"),
            "",
            _text("gui.variants_batch_file_filter"),
        )
        if path:
            self.batch_path.setText(path)
        return path

    def _invalidate_batch(self, *_args) -> None:
        self.batch_create_button.setEnabled(False)
        if self._batch_signature is not None:
            self.batch_note.setText(_text("gui.variants_batch_stale"))
            self._batch_signature = None

    def _batch_values(self):
        return (self.batch_path.text().strip(), self.batch_family.currentData() or "protein")

    def preview_batch(self) -> bool:
        path, family = self._batch_values()
        if not path:
            self._problems(_text("gui.variants_batch_preview_empty"))
            return False
        preview = self._state.inspect_batch_file(path, family=family)
        if not preview.ok:
            # A file the commit would refuse is shown with the entries that
            # were read, so the offending line is visible before anything is
            # created; the create button stays disabled.
            self._fill_batch_table(preview.entries)
            self.batch_create_button.setEnabled(False)
            self._batch_signature = None
            self.batch_note.setText(
                _text("gui.variants_batch_invalid") % len(preview.entries)
                if preview.entries
                else _text("gui.variants_batch_preview_empty")
            )
            self._problems(preview.message or _text("gui.variants_batch_empty"))
            return False
        self._fill_batch_table(preview.entries)
        self._batch_signature = (path, family)
        planned = (
            preview.planned if preview.planned is not None else len(preview.entries)
        )
        self.batch_note.setText(
            _text("gui.variants_batch_preview_title")
            % (len(preview.entries), planned)
        )
        self.batch_create_button.setEnabled(True)
        return True

    def _fill_batch_table(self, entries) -> None:
        self.batch_table.setRowCount(0)
        for entry in entries:
            row = self.batch_table.rowCount()
            self.batch_table.insertRow(row)
            self.batch_table.setItem(row, 0, QTableWidgetItem(entry))

    def create_batch(self) -> bool:
        path, family = self._batch_values()
        if self._batch_signature != (path, family):
            self._problems(_text("gui.variants_batch_stale"))
            return False
        outcome = self._state.generate_from_file(path, family=family)
        if not outcome.ok:
            self._problems(outcome.message or "")
            return False
        self._notify(outcome.message or _text("gui.variants_batch_created") % 0)
        self._batch_signature = None
        self.batch_create_button.setEnabled(False)
        self.batch_table.setRowCount(0)
        self.batch_note.setText(_text("gui.variants_batch_preview_empty"))
        self.refresh()
        self._show_details()
        return True
