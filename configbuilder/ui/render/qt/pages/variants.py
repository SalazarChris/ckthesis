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
existing variants, the selected variant's declared changes / validation state
/ JSON, and the secondary actions (add a change, rename, duplicate, remove,
validate) that act on the selection. No wording here names an internal type:
the page talks about variants, entities and changes.

The base job is only ever read here. Nothing in this module builds a variant,
an edit, a record, a wire document or a JSON string: every mutation is a
pass-through on ``GuiState`` to an existing service method, and every status
comes from ``ValidationService.validate_all``. A refusal is shown with the
service's own message and changes nothing.
"""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, Qt
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
from configbuilder.ui.present.labels import alignment_text, change_text
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
    FindingsTableModel,
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
        self._validation = None
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
        self.targets_page = self._build_targets_tab()
        self.one_page = self._build_one_tab()
        self.series_page = self._build_series_tab()
        self.batch_page = self._build_batch_tab()
        self.details_page = self._build_details()
        self.workspace = QStackedWidget()
        self.workspace.setObjectName("variantsWorkspace")
        for page in (
            self.chooser_page,
            self.targets_page,
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
        self.targets_choice_button = QPushButton(_text("gui.variants_targets_title"))
        self.one_choice_button = QPushButton(_text("gui.variants_one_title"))
        self.series_choice_button = QPushButton(_text("gui.variants_series_title"))
        self.batch_choice_button = QPushButton(_text("gui.variants_batch_title"))
        self.targets_choice_button.clicked.connect(self.open_targets_path)
        self.one_choice_button.clicked.connect(self.open_one_path)
        self.series_choice_button.clicked.connect(self.open_series_path)
        self.batch_choice_button.clicked.connect(self.open_batch_path)
        for button, hint_key in (
            (self.targets_choice_button, "gui.variants_targets_hint"),
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

    def open_targets_path(self) -> None:
        """Show only the vary-entities workflow (the multi-ligand path)."""
        self._refresh_targets()
        self.workspace.setCurrentWidget(self.targets_page)

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
            ("targets", self.targets_page),
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
        self.validate_button = QPushButton(_text("gui.variants_validate"))
        self.add_change_button.clicked.connect(self.add_change)
        self.rename_button.clicked.connect(self.rename_variant)
        self.duplicate_button.clicked.connect(self.duplicate_variant)
        self.remove_button.clicked.connect(self.remove_variant)
        self.validate_button.clicked.connect(self.validate_now)
        # Two short rows rather than one long strip: five actions in a single
        # line forced the whole page wider than the window at 940 px.
        for column, button in enumerate(
            (self.add_change_button, self.rename_button, self.duplicate_button)
        ):
            layout.addWidget(button, 0, column)
        layout.addWidget(self.remove_button, 1, 0)
        layout.addWidget(self.validate_button, 1, 1)
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
        """The fourth tab: what the selected variant declares and validates to."""
        page = QWidget()
        layout = QVBoxLayout(page)
        self.detail_title = QLabel(_text("gui.variants_no_selection"))
        self.detail_title.setWordWrap(True)
        self.detail_status = QLabel()
        self.detail_status.setWordWrap(True)
        layout.addWidget(self.detail_title)
        layout.addWidget(self.detail_status)
        self.detail_tabs = QTabWidget()
        self.changes_list = QListWidget()
        self.changes_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.detail_tabs.addTab(self.changes_list, _text("gui.variants_tab_changes"))
        findings_page = QWidget()
        findings_layout = QVBoxLayout(findings_page)
        self.findings_note = QLabel()
        self.findings_note.setWordWrap(True)
        self.findings_model = FindingsTableModel(self)
        self.findings_view = QTableView()
        self.findings_view.setModel(self.findings_model)
        self.findings_view.setSelectionMode(QAbstractItemView.NoSelection)
        self.findings_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.findings_view.verticalHeader().setVisible(False)
        self.findings_view.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch
        )
        findings_layout.addWidget(self.findings_note)
        findings_layout.addWidget(self.findings_view, 1)
        self.detail_tabs.addTab(findings_page, _text("gui.variants_tab_findings"))
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

    def _build_targets_tab(self):
        """The everyday path: the entities you opened, each varied once.

        The table is the base job itself — one row per entity definition, with
        its copies and the strategies that entity can take — so the first
        decision ("which of these do I want to change?") is answered from the
        file the user opened rather than from a list of internal change kinds.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        header, self.targets_back = self._path_header("gui.variants_targets_title")
        layout.addWidget(header)
        layout.addWidget(hint_label(_text("gui.variants_targets_hint")))
        layout.addWidget(hint_label(_text("gui.variants_targets_independent")))
        self.targets_table = QTableWidget(0, 5)
        self.targets_table.setObjectName("targetsTable")
        self.targets_table.setHorizontalHeaderLabels(
            [
                _text("gui.variants_targets_col_entity"),
                _text("gui.variants_targets_col_type"),
                _text("gui.variants_targets_col_content"),
                _text("gui.variants_targets_col_copies"),
                _text("gui.variants_targets_col_can"),
            ]
        )
        self.targets_table.verticalHeader().setVisible(False)
        self.targets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.targets_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.targets_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.targets_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.targets_table.setMinimumHeight(120)
        self.targets_table.itemSelectionChanged.connect(self._invalidate_targets)
        layout.addWidget(self.targets_table, 1)
        select_row = QHBoxLayout()
        self.targets_all_button = QPushButton(_text("gui.variants_targets_select_all"))
        self.targets_none_button = QPushButton(_text("gui.variants_targets_select_none"))
        self.targets_all_button.setProperty("role", "quiet")
        self.targets_none_button.setProperty("role", "quiet")
        self.targets_all_button.clicked.connect(self.select_all_targets)
        self.targets_none_button.clicked.connect(self.select_no_targets)
        select_row.addWidget(self.targets_all_button)
        select_row.addWidget(self.targets_none_button)
        select_row.addStretch(1)
        layout.addWidget(self._layout_widget(select_row))
        form = QFormLayout()
        self.targets_strategy = QComboBox()
        self.targets_strategy.setObjectName("targetsStrategy")
        self.targets_strategy.currentIndexChanged.connect(self._invalidate_targets)
        self.targets_value = QLineEdit()
        self.targets_value.setObjectName("targetsValue")
        self.targets_value.textChanged.connect(self._invalidate_targets)
        self.targets_value_label = QLabel(_text("gui.variants_targets_value"))
        form.addRow(_text("gui.variants_targets_strategy"), self.targets_strategy)
        form.addRow(self.targets_value_label, self.targets_value)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.targets_plan_button = QPushButton(_text("gui.variants_targets_plan"))
        self.targets_create_button = QPushButton(_text("gui.variants_targets_create"))
        self.targets_plan_button.clicked.connect(self.plan_targets)
        self.targets_create_button.clicked.connect(self.create_targets)
        self.targets_create_button.setEnabled(False)
        buttons.addWidget(self.targets_plan_button)
        buttons.addWidget(self.targets_create_button)
        buttons.addStretch(1)
        layout.addWidget(self._layout_widget(buttons))
        self.targets_note = QLabel(_text("gui.variants_targets_plan_empty"))
        self.targets_note.setWordWrap(True)
        layout.addWidget(self.targets_note)
        self.targets_plan_table = QTableWidget(0, 3)
        self.targets_plan_table.setObjectName("targetsPlanTable")
        self.targets_plan_table.setHorizontalHeaderLabels(
            [
                _text("gui.variants_targets_col_variant"),
                _text("gui.variants_targets_col_target"),
                _text("gui.variants_targets_col_change"),
            ]
        )
        self.targets_plan_table.verticalHeader().setVisible(False)
        self.targets_plan_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.targets_plan_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.targets_plan_table.setMinimumHeight(100)
        layout.addWidget(self.targets_plan_table, 1)
        self._targets_plan = None
        return page

    # -- vary entities -----------------------------------------------------

    def target_rows(self):
        """The entity table as ``(key, type, content, copies, can vary)``."""
        rows = []
        for row in range(self.targets_table.rowCount()):
            rows.append(
                tuple(
                    self.targets_table.item(row, column).text()
                    for column in range(self.targets_table.columnCount())
                )
            )
        return tuple(rows)

    def selected_target_keys(self):
        """The entity keys selected in the table, in table order."""
        return tuple(
            self.targets_table.item(index.row(), 0).text()
            for index in self.targets_table.selectionModel().selectedRows()
        )

    def select_target(self, key, selected=True) -> bool:
        """Add one entity row to (or remove it from) the selection, by key."""
        for row in range(self.targets_table.rowCount()):
            item = self.targets_table.item(row, 0)
            if item is None or item.text() != key:
                continue
            index = self.targets_table.model().index(row, 0)
            flag = QItemSelectionModel.Select if selected else QItemSelectionModel.Deselect
            self.targets_table.selectionModel().select(
                index, flag | QItemSelectionModel.Rows
            )
            if selected:
                self.targets_table.scrollToItem(item)
            return True
        return False

    def select_all_targets(self) -> None:
        self.targets_table.selectAll()

    def select_no_targets(self) -> None:
        self.targets_table.clearSelection()

    def choose_target_strategy(self, kind: str) -> bool:
        """Check one strategy in the combo, exactly as a click does."""
        for index in range(self.targets_strategy.count()):
            if self.targets_strategy.itemData(index) == kind:
                self.targets_strategy.setCurrentIndex(index)
                return True
        return False

    def target_strategy_kind(self) -> str:
        return self.targets_strategy.currentData() or ""

    def set_target_value(self, value: str) -> None:
        self.targets_value.setText(value)

    def target_value_text(self) -> str:
        return self.targets_value.text()

    def _refresh_targets(self) -> None:
        """Re-read the entity table and the strategies this base supports."""
        rows = self._state.entity_table() if self._state.configuration else ()
        self.targets_table.setRowCount(0)
        for row, entity in enumerate(rows):
            self.targets_table.insertRow(row)
            values = (
                entity.key,
                _text("menu.family_%s" % entity.family),
                entity.summary,
                str(entity.copies),
                _text("gui.variants_targets_can") % len(entity.kinds)
                if entity.kinds
                else _text("gui.variants_targets_cannot"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(entity.note or "")
                self.targets_table.setItem(row, column, item)
        current = self.target_strategy_kind()
        self.targets_strategy.blockSignals(True)
        self.targets_strategy.clear()
        for choice in self._state.target_strategy_choices():
            self.targets_strategy.addItem(choice.label, choice.kind)
        self.targets_strategy.blockSignals(False)
        if current and not self.choose_target_strategy(current):
            self.targets_strategy.setCurrentIndex(0)
        elif current:
            self.choose_target_strategy(current)
        self._invalidate_targets()

    def _invalidate_targets(self, *_args) -> None:
        """Any control change makes the reviewed plan stale, so it is dropped."""
        self._targets_plan = None
        self.targets_plan_table.setRowCount(0)
        self.targets_note.setText(_text("gui.variants_targets_plan_empty"))
        self.targets_create_button.setEnabled(False)

    def plan_targets(self) -> bool:
        """Ask the service what the current selection would create."""
        if self._state.configuration is None:
            self._problems(_text("menu.no_project"))
            return False
        keys = self.selected_target_keys()
        if not keys:
            self._problems(_text("gui.variants_targets_select_first"))
            return False
        kind = self.target_strategy_kind()
        plan = self._state.plan_target_variants(keys, kind, self.target_value_text())
        self._targets_plan = plan
        self.targets_plan_table.setRowCount(0)
        for row, planned in enumerate(plan.rows):
            self.targets_plan_table.insertRow(row)
            changes = "; ".join(
                change_text(described.get("kind", ""), described)
                for described in planned.described
            )
            for column, value in enumerate(
                (planned.spec_key, planned.key, changes)
            ):
                self.targets_plan_table.setItem(row, column, QTableWidgetItem(value))
        if plan.ok:
            self.targets_note.setText(
                _text("gui.variants_targets_plan_ready")
                % (plan.count, ", ".join(plan.unchanged_keys) or _text("gui.variants_targets_none_unaffected"))
            )
        else:
            self.targets_note.setText(plan.message or _text("gui.variants_targets_plan_empty"))
        self.targets_create_button.setEnabled(bool(plan.ok and plan.count))
        return plan.ok

    def create_targets(self) -> bool:
        """Commit the reviewed plan; nothing is written until generation."""
        if self._targets_plan is None and not self.plan_targets():
            return False
        if self._targets_plan is None or not self._targets_plan.ok:
            return False
        plan = self._targets_plan
        outcome = self._state.create_target_variants(
            tuple(row.key for row in plan.rows),
            self.target_strategy_kind(),
            self.target_value_text(),
        )
        if not outcome.ok:
            self._problems(outcome.message or _text("menu.not_applied") % "")
            return False
        self._notify(_text("gui.variants_targets_created") % plan.count)
        self._invalidate_targets()
        if plan.spec_keys:
            self._selected_key = plan.spec_keys[0]
            self.refresh()
        return True

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

    def row_status_text(self, key) -> str:
        """The validation word displayed for one variant row."""
        for row in self.variant_model.rows:
            if row.key == key:
                return row.status
        return ""

    # -- refresh -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-read specs, validation, details and the two creation forms."""
        configuration = self._state.configuration
        if configuration is None:
            self._validation = None
            self.variant_model.set_rows(())
            self._base_label.setText(_text("menu.no_project"))
            self._empty_label.setVisible(False)
            self.list_group.setVisible(False)
            self._clear_details()
            self._refresh_series_components()
            self._refresh_targets()
            self._update_actions()
            return

        specs = self._state.specs
        self._validation = self._state.validate_all() if specs else None
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
                self._status_text(spec.key),
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
        self._refresh_targets()
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
        self.validate_button.setEnabled(has_project and bool(self._state.specs))

    def _status_text(self, key: str) -> str:
        validation = self._validation
        if validation is None:
            return ""
        if validation.failure_reason is not None:
            return _text("gui.variants_status_unavailable")
        base_report = validation.base_report
        if base_report is not None and base_report.blocking():
            return _text("gui.variants_status_base_blocked")
        report = validation.variant_reports.get(key)
        if report is None:
            return _text("gui.variants_status_unavailable")
        blocking = report.blocking()
        if blocking:
            return _text("gui.variants_status_blocked") % len(blocking)
        warnings = report.warnings()
        if warnings:
            return _text("gui.variants_status_warnings") % len(warnings)
        return _text("gui.variants_status_ready")

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
        self.detail_status.setText("")
        self.changes_list.clear()
        self.findings_model.set_findings(())
        self.findings_note.setText("")
        self.json_view.setPlainText("")
        self.json_note.setText("")

    def _refresh_details(self) -> None:
        spec = self.selected_spec()
        if spec is None:
            self._clear_details()
            return
        self.detail_title.setText("%s  ·  %s" % (spec.label, spec.key))
        self.detail_status.setText(
            _text("gui.variants_status_header") % self._status_text(spec.key)
        )
        self.changes_list.clear()
        for text_value in self._change_lines(spec.key):
            self.changes_list.addItem(QListWidgetItem(text_value))
        if not self.changes_list.count():
            item = QListWidgetItem(_text("gui.variants_changes_none"))
            item.setFlags(Qt.NoItemFlags)
            self.changes_list.addItem(item)
        self._refresh_findings(spec.key)
        self._refresh_json(spec.key)

    def _refresh_findings(self, key: str) -> None:
        validation = self._validation
        if validation is None:
            self.findings_model.set_findings(())
            self.findings_note.setText(_text("gui.variants_findings_none"))
            return
        if validation.failure_reason is not None:
            self.findings_model.set_findings(())
            self.findings_note.setText(
                _text("gui.variants_findings_unavailable") % (validation.message or "")
            )
            return
        base_report = validation.base_report
        if base_report is not None and base_report.blocking():
            findings = base_report.findings
            self.findings_model.set_findings(findings)
            self.findings_note.setText(_text("gui.variants_findings_base"))
            return
        report = validation.variant_reports.get(key)
        findings = report.findings if report is not None else ()
        self.findings_model.set_findings(findings)
        self.findings_note.setText(
            "" if findings else _text("gui.variants_findings_none")
        )

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
        """One edit, worded by the shared renderer.

        The wording lives in ``ui.present.labels.change_text`` so the
        console shows the same sentence for the same edit; this page
        keeps the method because its callers and tests already use it.
        """
        return change_text(kind, described)

    def _alignment_text(self, alignment) -> str:
        """The alignment phrase, from the same shared renderer."""
        return alignment_text(alignment)

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

    def validate_now(self) -> bool:
        if self._state.configuration is None:
            self._problems(_text("menu.no_project"))
            return False
        self.refresh()
        self._notify(_text("gui.variants_validated"))
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
