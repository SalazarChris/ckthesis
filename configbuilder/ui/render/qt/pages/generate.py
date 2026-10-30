"""The Generate & Output page: one click writes the open job.

The page owns no output rule. Every plan comes from
``GenerationService.plan_selection`` with the base scope — which delegates to
``plan_base``, the open job's own single file — and every write comes from
``GenerationService.execute`` handed the plan object itself. Nothing here
builds a path, a wire document or a file: the paths shown are the service's own
strings, and the bytes written are the plan's own payloads.

One action, one file:

- the folder is pre-filled from the shared path service and the job's exact
  destination is named *before* the click (``GenerationService.base_file_path``,
  the same rule ``plan_base`` uses);
- **Save job** plans and writes in one step. A new file is written without any
  further question, because a new file is not a destructive act;
- the only question is a replacement: an existing file holding *different*
  bytes is confirmed once, naming the files. Identical bytes are rewritten
  silently, since the result is the same file;
- a refusal (no folder, blocking validation findings, a conflict under the
  default ``Fail`` policy) writes nothing, shows the service's own message and
  its findings, and leaves the job untouched;
- **Preview plan** stays available for anyone who wants to see the plan first,
  but nothing is gated on it, and the plan is always recomputed at write time —
  so the bytes written are the bytes the service just decided on;
- after a successful write the job adopts the file as its saved state, so the
  header stops calling the job unsaved.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.qt.dialogs import confirm_replacement
from configbuilder.ui.render.qt.models import FindingsTableModel, fixed_font
from configbuilder.ui.render.qt.style import (
    heading_label,
    hint_label,
    page_title_label,
)
from configbuilder.ui.render.qt.widgets import CollapsibleSection

__all__ = ["GeneratePage"]

# The service's policy names, mapped to registered wording. A name that is
# not in these maps (only possible if the service's closed set grows) is
# shown as the technical name itself rather than guessed at.
_OVERWRITE_LABELS = {
    "Fail": "gui.policy_overwrite_fail",
    "Skip": "gui.policy_overwrite_skip",
    "Overwrite": "gui.policy_overwrite_overwrite",
    "Versioned": "gui.policy_overwrite_versioned",
}

_OVERWRITE_HINTS = {
    "Fail": "gui.policy_overwrite_fail_hint",
    "Skip": "gui.policy_overwrite_skip_hint",
    "Overwrite": "gui.policy_overwrite_overwrite_hint",
    "Versioned": "gui.policy_overwrite_versioned_hint",
}

_PATH_LABELS = {
    "CopyIntoAssets": "gui.policy_path_copy",
    "RelativeToOutput": "gui.policy_path_relative",
    "AsGiven": "gui.policy_path_asgiven",
}

_PATH_HINTS = {
    "CopyIntoAssets": "gui.policy_path_copy_hint",
    "RelativeToOutput": "gui.policy_path_relative_hint",
    "AsGiven": "gui.policy_path_asgiven_hint",
}

_ACTION_KEYS = {
    "create": "gui.output_action_create",
    "overwrite": "gui.output_action_overwrite",
    "skip": "gui.output_action_skip",
    "conflict": "gui.output_action_conflict",
}

_SCOPE_BASE = "base"


class GeneratePage(QWidget):
    """Plan, write and report the open job's own file in one action."""

    record_activated = Signal(str)
    review_requested = Signal()

    def __init__(self, state, notify=None, problems=None, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._notify = notify if notify is not None else (lambda message: None)
        self._problems = problems if problems is not None else (lambda message: None)
        # The one modal this page's own action asks — and only when a write
        # would replace an existing file with different bytes. Replaced by the
        # tests.
        self.replacement_confirmer = confirm_replacement
        self._plan = None
        self._signature = None
        self._defaults_token = None
        self._last_directory = ""
        self._build()

    # -- construction ------------------------------------------------------

    def _build(self) -> None:
        """Two cards: where the file goes, then what happened.

        The destination and its one action sit together, because that is the
        whole decision. The plan tables, the copied assets and the findings
        live under the result, where a reader looks *after* the run, and the
        review that used to gate the button is an ordinary optional action.
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        title = page_title_label(_text("gui.output_title"))
        title.setWordWrap(True)
        intro = QLabel(_text("gui.output_intro"))
        intro.setWordWrap(True)
        self._base_label = QLabel()
        self._base_label.setWordWrap(True)
        self._base_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addWidget(self._base_label)
        layout.addWidget(self._build_output_group())
        layout.addWidget(self._build_result_group())
        layout.addStretch(1)
        # One scroll surface: a short window scrolls instead of clipping a
        # long path or a table.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _build_output_group(self):
        """The folder, the file it will produce, its options, and the action."""
        group = QGroupBox(_text("gui.output_group_output"))
        layout = QVBoxLayout(group)
        form = QFormLayout()

        self.destination = QLineEdit()
        # Pre-filled, not just placeheld: an accepted default must be a real
        # path. It is the shared output service's ``saved_jobs`` (or the folder
        # the last write went to), never the process's working directory.
        self.destination.setText(self._default_destination())
        self.destination.setPlaceholderText(
            _text("gui.output_destination_placeholder")
        )
        self.destination.setAccessibleName(_text("gui.output_destination"))
        self.destination.textChanged.connect(self._on_destination_changed)
        self.browse_button = QPushButton(_text("gui.output_browse"))
        self.browse_button.clicked.connect(self.browse_destination)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.destination, 1)
        row_layout.addWidget(self.browse_button)
        form.addRow(_text("gui.output_destination"), row)
        layout.addLayout(form)

        # The exact file, before the click — the service's own naming rule, so
        # the promise and the write cannot drift apart.
        self.write_label = QLabel(_text("gui.output_will_write_none"))
        self.write_label.setWordWrap(True)
        self.write_label.setProperty("role", "caption")
        self.write_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.write_label)
        layout.addWidget(hint_label(_text("gui.output_destination_hint")))

        # Real decisions, but not decisions the common case needs: one
        # labelled click away, with the safe defaults already chosen.
        self.advanced_section = CollapsibleSection(
            _text("gui.output_advanced"), expanded=False
        )
        advanced = QFormLayout(self.advanced_section.body)
        self.overwrite_policy = QComboBox()
        self.path_policy = QComboBox()
        for combo in (self.overwrite_policy, self.path_policy):
            combo.currentIndexChanged.connect(self._on_policy_changed)
        self.overwrite_policy.setAccessibleName(_text("gui.output_overwrite_policy"))
        self.path_policy.setAccessibleName(_text("gui.output_path_policy"))
        advanced.addRow(_text("gui.output_overwrite_policy"), self.overwrite_policy)
        advanced.addRow(_text("gui.output_path_policy"), self.path_policy)
        advanced.addRow(hint_label(_text("gui.output_advanced_hint")))
        layout.addWidget(self.advanced_section)

        action_row = QHBoxLayout()
        self.generate_button = QPushButton(_text("gui.output_save"))
        self.generate_button.setProperty("role", "primary")
        self.generate_button.clicked.connect(self.generate)
        action_row.addWidget(self.generate_button)
        action_row.addWidget(hint_label(_text("gui.output_write_hint")), 1)
        layout.addLayout(action_row)

        # One status line for the page: the refusal that stopped a write, or
        # the size of the plan that was just previewed. Never a second
        # confirmation of what the button already says.
        self.plan_note = QLabel(_text("gui.output_plan_empty"))
        self.plan_note.setWordWrap(True)
        layout.addWidget(self.plan_note)
        self._update_write_label()
        self._update_generate_button()
        return group

    def _build_result_group(self):
        """What was written, the optional review, and the plan's own detail."""
        group = QGroupBox(_text("gui.output_group_result"))
        layout = QVBoxLayout(group)
        self.result_note = QLabel(_text("gui.output_result_empty"))
        self.result_note.setWordWrap(True)
        layout.addWidget(self.result_note)
        self.result_view = QPlainTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setFont(fixed_font())
        self.result_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.result_view.setMinimumHeight(96)
        layout.addWidget(self.result_view)

        row = QHBoxLayout()
        self.preview_button = QPushButton(_text("gui.output_preview"))
        self.preview_button.clicked.connect(self.preview_plan)
        self.preview_button.setToolTip(_text("gui.output_preview_hint"))
        self.open_folder_button = QPushButton(_text("gui.output_open_folder"))
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self.open_folder)
        row.addWidget(self.preview_button)
        row.addWidget(self.open_folder_button)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(self._build_messages())
        self.details_section = CollapsibleSection(
            _text("gui.output_plan_details"), expanded=False
        )
        details = QVBoxLayout(self.details_section.body)
        details.addWidget(self._build_plan_tabs(), 1)
        copy_row = QHBoxLayout()
        self.copy_button = QPushButton(_text("gui.output_copy_path"))
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_selected_path)
        copy_row.addWidget(self.copy_button)
        copy_row.addStretch(1)
        details.addLayout(copy_row)
        layout.addWidget(self.details_section)
        return group

    def _build_plan_tabs(self):
        """The plan's own rows: files on one tab, external copies on the other."""
        self.plan_tabs = QTabWidget()
        files_page = QWidget()
        files_layout = QVBoxLayout(files_page)
        self.entries_table = self._table(
            (
                "gui.output_col_kind",
                "gui.output_col_job",
                "gui.output_col_file",
                "gui.output_col_action",
            ),
            stretch_column=2,
        )
        self.entries_table.itemSelectionChanged.connect(self._on_entries_selected)
        files_layout.addWidget(self.entries_table)
        self.plan_tabs.addTab(files_page, _text("gui.output_tab_files"))

        assets_page = QWidget()
        assets_layout = QVBoxLayout(assets_page)
        self.resources_table = self._table(
            (
                "gui.output_col_field",
                "gui.output_col_source",
                "gui.output_col_copy",
                "gui.output_col_emitted",
            ),
            stretch_column=1,
        )
        self.resources_table.itemSelectionChanged.connect(self._on_resources_selected)
        assets_layout.addWidget(self.resources_table)
        self.plan_tabs.addTab(assets_page, _text("gui.output_tab_assets"))
        return self.plan_tabs

    def _table(self, header_keys, stretch_column: int):
        table = QTableWidget(0, len(header_keys))
        table.setHorizontalHeaderLabels([_text(key) for key in header_keys])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(
            stretch_column, QHeaderView.Stretch
        )
        table.setMinimumHeight(110)
        return table

    def _build_messages(self):
        """Conflicts, warnings and blocking findings — always outside a fold.

        Both demand a decision before another attempt, so neither hides behind
        the details disclosure that the plan tables use.
        """
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(heading_label(_text("gui.output_group_warnings")))
        self.conflicts_label = QLabel()
        self.conflicts_label.setWordWrap(True)
        self.conflicts_note = QLabel(_text("gui.output_conflicts_blocking"))
        self.conflicts_note.setProperty("role", "warning")
        self.conflicts_note.setWordWrap(True)
        self.conflicts_list = QListWidget()
        self.conflicts_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.warnings_label = QLabel()
        self.warnings_label.setWordWrap(True)
        self.warnings_note = QLabel(_text("gui.output_warnings_nonblocking"))
        self.warnings_note.setProperty("role", "caption")
        self.warnings_note.setWordWrap(True)
        self.warnings_list = QListWidget()
        self.warnings_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.conflicts_list.setMaximumHeight(120)
        self.warnings_list.setMaximumHeight(120)
        self.findings_note = QLabel()
        self.findings_note.setWordWrap(True)
        self.findings_model = FindingsTableModel(self)
        self.findings_view = QTableView()
        self.findings_view.setModel(self.findings_model)
        self.findings_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.findings_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.findings_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.findings_view.verticalHeader().setVisible(False)
        self.findings_view.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch
        )
        self.findings_view.setMinimumHeight(90)
        self.findings_view.selectionModel().selectionChanged.connect(
            self._on_finding_selected
        )
        self.review_button = QPushButton(_text("gui.output_review"))
        self.review_button.clicked.connect(self.review_requested.emit)
        self.review_button.setVisible(False)
        for widget in (
            self.conflicts_label,
            self.conflicts_note,
            self.conflicts_list,
            self.warnings_label,
            self.warnings_note,
            self.warnings_list,
        ):
            widget.setVisible(False)
        layout.addWidget(self.conflicts_label)
        layout.addWidget(self.conflicts_note)
        layout.addWidget(self.conflicts_list)
        layout.addWidget(self.warnings_label)
        layout.addWidget(self.warnings_note)
        layout.addWidget(self.warnings_list)
        layout.addWidget(self.findings_note)
        layout.addWidget(self.findings_view)
        layout.addWidget(self.review_button)
        return group

    # -- destination and choices ------------------------------------------

    def browse_destination(self) -> str:
        """Ask for an output folder; the native dialog only chooses a path."""
        path = QFileDialog.getExistingDirectory(
            self,
            _text("gui.output_folder_dialog"),
            self.destination.text() or "",
        )
        if path:
            self.destination.setText(path)
        return path

    def _load_policy_choices(self) -> None:
        choices = self._state.output_policy_choices()
        for combo, names, labels, hints in (
            (self.overwrite_policy, choices["overwrite"], _OVERWRITE_LABELS, _OVERWRITE_HINTS),
            (self.path_policy, choices["path"], _PATH_LABELS, _PATH_HINTS),
        ):
            combo.blockSignals(True)
            combo.clear()
            for name in names:
                combo.addItem(_text(labels[name]) if name in labels else name, name)
                index = combo.count() - 1
                if name in hints:
                    combo.setItemData(index, _text(hints[name]), Qt.ToolTipRole)
            combo.blockSignals(False)

    def _apply_defaults(self) -> None:
        defaults = self._state.output_defaults()
        for combo, name in (
            (self.overwrite_policy, defaults["overwrite"]),
            (self.path_policy, defaults["path"]),
        ):
            index = combo.findData(name)
            if index >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)

    def _default_destination(self) -> str:
        """The folder this page offers first; ``\"\"`` if none can be resolved."""
        try:
            return str(self._state.paths.save_directory())
        except (OSError, ValueError):
            return ""

    def _policy_name(self, combo) -> str:
        return combo.currentData() or ""

    def _current_signature(self):
        return (
            self.destination.text().strip(),
            self._policy_name(self.overwrite_policy),
            self._policy_name(self.path_policy),
        )

    # -- the file this page would write -----------------------------------

    def destination_file(self) -> str:
        """The exact path **Save job** would create for the current folder."""
        root = self.destination.text().strip()
        if not root:
            return ""
        try:
            return self._state.base_destination(root) or ""
        except (OSError, ValueError):
            return ""

    def _update_write_label(self) -> None:
        path = self.destination_file()
        self.write_label.setText(
            _text("gui.output_will_write") % path
            if path
            else _text("gui.output_will_write_none")
        )

    def _update_generate_button(self) -> None:
        """One click is available whenever there is something to write."""
        self.generate_button.setEnabled(bool(self.destination_file()))

    def _on_destination_changed(self, *_args) -> None:
        """A new folder voids the plan shown, never the ability to write."""
        self._update_write_label()
        self._update_generate_button()
        self._clear_plan()

    def _on_policy_changed(self, *_args) -> None:
        self._clear_plan()

    # -- refresh -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the job: new name, new file, no plan from an earlier state."""
        configuration = self._state.configuration
        if configuration is None:
            self._base_label.setText(_text("menu.no_project"))
            self._defaults_token = None
        else:
            self._base_label.setText(
                _text("gui.output_base")
                % (configuration.metadata.name, len(configuration.records))
            )
            if self.overwrite_policy.count() == 0 or self.path_policy.count() == 0:
                self._load_policy_choices()
            token = (
                self._state.source_path,
                self._state.is_demo,
                configuration.metadata.name,
            )
            if token != self._defaults_token:
                self._apply_defaults()
                self._defaults_token = token
        self._update_write_label()
        self._update_generate_button()
        self._clear_plan()

    def _clear_plan(self) -> None:
        """Forget any displayed plan — the next write plans from scratch."""
        self._plan = None
        self._signature = None
        self.entries_table.setRowCount(0)
        self.resources_table.setRowCount(0)
        self.findings_model.set_findings(())
        self.findings_note.setText("")
        self.review_button.setVisible(False)
        self.conflicts_list.clear()
        self.warnings_list.clear()
        for widget in (
            self.conflicts_list,
            self.warnings_list,
            self.conflicts_label,
            self.conflicts_note,
            self.warnings_label,
            self.warnings_note,
        ):
            widget.setVisible(False)
        self.conflicts_label.setText("")
        self.warnings_label.setText("")
        self.plan_note.setText(_text("gui.output_plan_empty"))
        self._update_copy_button()

    # -- planning ----------------------------------------------------------

    def _plan_arguments(self):
        root, overwrite, path = self._current_signature()
        return {
            "output_root": root,
            "scope": _SCOPE_BASE,
            "only": None,
            "overwrite_policy": overwrite,
            "path_policy": path,
        }

    def preview_plan(self) -> bool:
        """Show the plan without writing it — optional, never a gate."""
        if self._state.configuration is None:
            self._problems(_text("menu.no_project"))
            return False
        if not self.destination.text().strip():
            self._problems(_text("gui.output_no_folder"))
            self.plan_note.setText(_text("gui.output_no_folder"))
            return False
        plan = self._state.plan_generation(**self._plan_arguments())
        self._plan = plan
        self._signature = self._current_signature()
        self._show_plan(plan)
        if plan.ok:
            self.plan_note.setText(
                _text("gui.output_plan_previewed")
                % (len(plan.entries), _copied_count(plan), len(plan.warnings))
            )
        else:
            self._problems(plan.message or "")
        return plan.ok

    def _show_plan(self, plan) -> None:
        """Render a service plan (successful or refused) without writing."""
        self._clear_plan_rows()
        for conflict in plan.conflicts:
            self.conflicts_list.addItem(conflict)
        self.conflicts_label.setText(
            _text("gui.output_conflicts") % len(plan.conflicts)
            if plan.conflicts
            else ""
        )
        self.conflicts_label.setVisible(bool(plan.conflicts))
        self.conflicts_note.setVisible(bool(plan.conflicts))
        self.conflicts_list.setVisible(bool(plan.conflicts))

        for warning in plan.warnings:
            self.warnings_list.addItem(warning)
        self.warnings_list.setVisible(bool(plan.warnings))
        self.warnings_note.setVisible(bool(plan.warnings))
        self.warnings_label.setText(
            _text("gui.output_warnings") % len(plan.warnings) if plan.warnings else ""
        )
        self.warnings_label.setVisible(bool(plan.warnings))

        if not plan.ok:
            self.plan_note.setText(
                _text("gui.output_plan_refused") % (plan.message or "")
            )
            self._fill_refusal_findings(plan)
            self._update_copy_button()
            return

        self._fill_entries(plan)
        self._fill_resources(plan)
        self._update_copy_button()

    def _clear_plan_rows(self) -> None:
        """Empty the plan surfaces without touching the status line."""
        self.entries_table.setRowCount(0)
        self.resources_table.setRowCount(0)
        self.conflicts_list.clear()
        self.warnings_list.clear()
        self.findings_model.set_findings(())
        self.findings_note.setText("")
        self.review_button.setVisible(False)
        for widget in (
            self.conflicts_list,
            self.warnings_list,
            self.conflicts_label,
            self.conflicts_note,
            self.warnings_label,
            self.warnings_note,
        ):
            widget.setVisible(False)
        self.conflicts_label.setText("")
        self.warnings_label.setText("")

    def _fill_entries(self, plan) -> None:
        for row, entry in enumerate(plan.entries):
            self.entries_table.insertRow(row)
            kind = _text("gui.output_kind_base")
            job = plan.project_name
            action = _text(_ACTION_KEYS.get(entry.action, "gui.output_action_conflict"))
            for column, value in enumerate((kind, job, entry.path, action)):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setData(Qt.UserRole, entry.path)
                self.entries_table.setItem(row, column, item)

    def _fill_resources(self, plan) -> None:
        resources = plan.reviewed.resources if plan.reviewed is not None else ()
        for row, resource in enumerate(resources):
            self.resources_table.insertRow(row)
            values = (
                resource.wire_field,
                resource.raw_path,
                resource.planned_path or "",
                resource.emitted_path or "",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 2) and value:
                    item.setData(Qt.UserRole, value)
                self.resources_table.setItem(row, column, item)

    def _fill_refusal_findings(self, plan) -> None:
        findings = tuple(plan.findings)
        self.findings_model.set_findings(findings)
        self.findings_note.setText(
            _text("gui.output_findings_note") if findings else ""
        )
        self.review_button.setVisible(bool(findings))

    # -- finding navigation ------------------------------------------------

    def _on_finding_selected(self, *_args) -> None:
        rows = self.findings_view.selectionModel().selectedRows()
        if not rows:
            return
        key = self.findings_model.record_key_at(rows[0].row())
        if key:
            self.record_activated.emit(key)

    def review_configuration(self) -> None:
        self.review_requested.emit()

    # -- path copying ------------------------------------------------------

    def _on_entries_selected(self, *_args) -> None:
        """One selection across both plan tables, so Copy means one thing."""
        if self.resources_table.selectionModel().hasSelection():
            self.resources_table.clearSelection()
        self._update_copy_button()

    def _on_resources_selected(self, *_args) -> None:
        if self.entries_table.selectionModel().hasSelection():
            self.entries_table.clearSelection()
        self._update_copy_button()

    def selected_path(self) -> str:
        """The path of the selected plan row: a file, or an asset's destination.

        Only the plan's own strings are returned — a file entry's path, or for
        an asset the planned copy's destination (falling back to the source it
        came from when the policy does not copy). Nothing is composed here.
        """
        rows = self.entries_table.selectionModel().selectedRows()
        if rows:
            item = self.entries_table.item(rows[0].row(), 0)
            return (item.data(Qt.UserRole) or "") if item is not None else ""
        rows = self.resources_table.selectionModel().selectedRows()
        if not rows:
            return ""
        row = rows[0].row()
        for column in (2, 1, 3):
            item = self.resources_table.item(row, column)
            if item is not None and item.text():
                return item.data(Qt.UserRole) or item.text()
        return ""

    def _update_copy_button(self) -> None:
        self.copy_button.setEnabled(bool(self.selected_path()))

    def copy_selected_path(self) -> str:
        path = self.selected_path()
        if not path:
            return ""
        QGuiApplication.clipboard().setText(path)
        self._notify(_text("gui.output_copied_path"))
        return path

    # -- execution ---------------------------------------------------------

    def generate(self) -> bool:
        """Plan and write in one action; ask only before replacing content."""
        if self._state.configuration is None:
            self._problems(_text("menu.no_project"))
            return False
        if not self.destination.text().strip():
            self._problems(_text("gui.output_no_folder"))
            self.plan_note.setText(_text("gui.output_no_folder"))
            return False

        plan = self._state.plan_generation(**self._plan_arguments())
        self._plan = plan
        self._signature = self._current_signature()
        self._show_plan(plan)
        if not plan.ok:
            # Refused: the service's message and findings, and no write.
            self._problems(plan.message or "")
            return False

        replaced = _replacement_paths(plan)
        if replaced and not self.replacement_confirmer(
            self, _replacement_question(replaced)
        ):
            self.plan_note.setText(_text("gui.output_replace_cancelled"))
            self._plan = None
            self._signature = None
            return False

        # The folder can change between the plan and the write (another
        # program writes a file, a directory appears). Plan once more and
        # compare: executing anything but the plan just reviewed would write
        # bytes the user never saw.
        refreshed = self._state.plan_generation(**self._plan_arguments())
        if not _same_plan(plan, refreshed):
            self._plan = refreshed
            self._show_plan(refreshed)
            self.plan_note.setText(_text("gui.output_plan_changed"))
            self._problems(_text("gui.output_plan_changed"))
            return False

        result = self._state.execute(plan)
        self._show_result(result)
        if result.ok:
            # Remembered only after a successful write, and adopted as the
            # job's saved state so the header stops reporting unsaved changes.
            self._state.paths.remember_save_directory(plan.output_root)
            written = list(result.written)
            if written:
                self._state.record_save(written[0])
            self.plan_note.setText(_text("gui.output_plan_done"))
        self._plan = None
        self._signature = None
        return bool(result.ok)

    def _show_result(self, result) -> None:
        written = list(result.written)
        skipped = list(result.skipped)
        copied = list(result.copied_resources)
        errors = list(result.errors)
        summary = _text("gui.output_result_summary") % (
            len(written),
            len(skipped),
            len(copied),
        )
        self.result_note.setText(
            _text("gui.output_result_partial") % errors[0] if errors else summary
        )
        sections = [summary]
        if written:
            sections.append(
                _text("gui.output_written") + "\n" + "\n".join(written)
            )
        if skipped:
            sections.append(
                _text("gui.output_skipped") + "\n" + "\n".join(skipped)
            )
        if copied:
            sections.append(
                _text("gui.output_copied")
                + "\n"
                + "\n".join(
                    "%s -> %s" % (source, destination)
                    for source, destination in copied
                )
            )
        if errors:
            sections.append(
                _text("gui.output_result_errors") + "\n" + "\n".join(errors)
            )
        self.result_view.setPlainText("\n\n".join(sections))
        self._last_directory = os.path.dirname(written[0]) if written else ""
        self.open_folder_button.setEnabled(bool(self._last_directory))
        if errors:
            self._problems(errors[0])
        else:
            self._notify(summary)

    def open_folder(self) -> bool:
        """Open the folder the last write landed in, in the desktop's file manager."""
        if not self._last_directory or not os.path.isdir(self._last_directory):
            return False
        return bool(
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_directory))
        )

    # -- reading the page back --------------------------------------------

    def plan_note_text(self) -> str:
        return self.plan_note.text()

    def result_text(self) -> str:
        return self.result_view.toPlainText()

    def entries(self):
        """The displayed plan rows as ``(kind, job, path, action)`` tuples."""
        rows = []
        for row in range(self.entries_table.rowCount()):
            rows.append(
                tuple(
                    self.entries_table.item(row, column).text()
                    for column in range(self.entries_table.columnCount())
                )
            )
        return tuple(rows)

    def resource_rows(self):
        rows = []
        for row in range(self.resources_table.rowCount()):
            rows.append(
                tuple(
                    self.resources_table.item(row, column).text()
                    for column in range(self.resources_table.columnCount())
                )
            )
        return tuple(rows)


def _copied_count(plan) -> int:
    """How many external files this plan would copy beside the output."""
    resources = plan.reviewed.resources if plan.reviewed is not None else ()
    return sum(1 for resource in resources if resource.copied)


def _replacement_paths(plan) -> tuple:
    """Existing files whose bytes this plan would replace with different ones.

    ``decide_action`` labels an existing identical file ``overwrite`` too — it
    is rewritten with the same bytes, which is harmless and must not be
    questioned. The service already worked that difference out
    (``ConfigurationPlan.different_content``), so the page asks about content
    that actually changes and stays silent when nothing does.
    """
    return tuple(
        entry.path
        for entry in plan.entries
        if entry.action == "overwrite" and entry.different_content
    )


def _replacement_question(paths) -> str:
    return _text("gui.output_replace_question") % (
        len(paths),
        "\n".join(paths),
    )


def _same_plan(first, second) -> bool:
    """True when two plans would write the same bytes to the same paths.

    Compares the review surface ``execute`` acts on: success/refusal, the
    refusal reasons, conflicts, warnings and every planned path with its
    action and payload fingerprint. A policy change is caught because it
    changes those paths/actions; a new filesystem conflict is caught because
    the action becomes ``conflict`` (or the plan is refused).
    """
    if first is second:
        return True
    if first is None or second is None:
        return False
    if (first.ok, first.failure_reason, first.message) != (
        second.ok,
        second.failure_reason,
        second.message,
    ):
        return False
    if tuple(first.conflicts) != tuple(second.conflicts):
        return False
    if tuple(first.warnings) != tuple(second.warnings):
        return False
    return tuple(
        (entry.path, entry.action, entry.payload_fingerprint) for entry in first.entries
    ) == tuple(
        (entry.path, entry.action, entry.payload_fingerprint) for entry in second.entries
    )
