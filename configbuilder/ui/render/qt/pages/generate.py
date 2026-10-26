"""The Generate & Output page: review the real plan, then write it.

The page owns no output rule. Every plan comes from
``GenerationService.plan_selection`` with the base scope — which delegates to
``plan_base``, the open job's own single file — and every write comes from
``GenerationService.execute`` handed the reviewed plan object itself. Nothing
here builds a path, a wire document or a file: the paths shown in the tables
are the plan's own strings, and the bytes written are the plan's own
payloads.

The sequence is the one a reviewer needs, labelled as four steps on the page:

1. **What is written** — the open job's configuration, one file;
2. **Where should the files go?** — the folder, and the two policies behind an
   *Advanced options* disclosure whose defaults are safe;
3. **Review the plan** — **Preview plan** shows the plan's files, assets,
   actions, warnings and conflicts; nothing is written. Conflicts and warnings
   are deliberately *outside* the disclosure, because they demand a decision;
4. **Generate files** asks for confirmation naming the destination and
   policies, re-plans to prove the reviewed plan is still current, and only
   then calls ``execute``; the result tab reports what was written, skipped,
   copied or refused.

A plan is invalidated whenever the job changes (``project_changed``) or a
control changes, so an executed plan is always the one the user just
reviewed. A refused plan shows the service's message and its findings; the
findings can be followed to the entity they name or back to Overview.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
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
    QRadioButton,
    QScrollArea,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from configbuilder.app.results import FailureReason
from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.qt.dialogs import confirm_generation
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
    """Plan, review and execute the existing output pipeline."""

    record_activated = Signal(str)
    review_requested = Signal()

    def __init__(self, state, notify=None, problems=None, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._notify = notify if notify is not None else (lambda message: None)
        self._problems = problems if problems is not None else (lambda message: None)
        # The one modal this page's own action asks; replaced by the tests.
        self.generation_confirmer = confirm_generation
        self._plan = None
        self._signature = None
        # True once a plan had been shown and then invalidated by a changed
        # control or job: the next Generate attempt can say *why* it needs a
        # fresh preview instead of the generic "preview first" line.
        self._stale = False
        self._defaults_token = None
        self._build()

    # -- construction ------------------------------------------------------

    def _build(self) -> None:
        """Four stacked steps: scope, destination, review, generate.

        Each step is one card with a numbered heading, so the order of
        operations is the order on screen. Setup controls are no longer side
        by side with the review panes: a long path or a large plan has the
        full width, the page scrolls instead of squeezing anything, and the
        write action sits *after* the review rather than beside the options.
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
        layout.addWidget(self._build_scope_group())
        layout.addWidget(self._build_destination_group())
        layout.addWidget(self._build_plan())
        layout.addWidget(self._build_generate_group())
        layout.addStretch(1)
        # One scroll surface: a short window scrolls the steps instead of
        # clipping a path, a plan table or the conflict list.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _build_scope_group(self):
        """Step 1: what this page writes — the open job's own file.

        The job is the unit: its configuration is written as
        ``<output>/<job>/<job>.json``, with the job's name inside the file
        matching the names outside it. A file of ligands is a different
        action with its own destination (Entities), so nothing here offers a
        second kind of output to choose between.
        """
        group = QGroupBox(_text("gui.output_group_scope"))
        layout = QVBoxLayout(group)
        layout.addWidget(hint_label(_text("gui.output_scope_base_note")))
        return group

    def _build_destination_group(self):
        """Step 2: the folder, then the policies behind one labelled disclosure."""
        group = QGroupBox(_text("gui.output_group_destination"))
        layout = QVBoxLayout(group)
        form = QFormLayout()

        self.destination = QLineEdit()
        self.destination.setPlaceholderText(
            _text("gui.output_destination_placeholder")
        )
        self.destination.setAccessibleName(_text("gui.output_destination"))
        self.destination.textChanged.connect(self._on_control_changed)
        self.browse_button = QPushButton(_text("gui.output_browse"))
        self.browse_button.clicked.connect(self.browse_destination)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.destination, 1)
        row_layout.addWidget(self.browse_button)
        form.addRow(_text("gui.output_destination"), row)
        layout.addLayout(form)
        layout.addWidget(hint_label(_text("gui.output_destination_hint")))

        # The two policies decide what happens to existing files and external
        # assets: real decisions, but not decisions the common case needs, so
        # they live one labelled click away — with the defaults already chosen
        # and a sentence saying they are safe.
        self.advanced_section = CollapsibleSection(
            _text("gui.output_advanced"), expanded=False
        )
        advanced = QFormLayout(self.advanced_section.body)
        self.overwrite_policy = QComboBox()
        self.path_policy = QComboBox()
        for combo in (self.overwrite_policy, self.path_policy):
            combo.currentIndexChanged.connect(self._on_control_changed)
        self.overwrite_policy.setAccessibleName(_text("gui.output_overwrite_policy"))
        self.path_policy.setAccessibleName(_text("gui.output_path_policy"))
        advanced.addRow(_text("gui.output_overwrite_policy"), self.overwrite_policy)
        advanced.addRow(_text("gui.output_path_policy"), self.path_policy)
        # The explanation of the defaults belongs with the options themselves:
        # collapsed, the disclosure is one line that says the defaults are safe.
        advanced.addRow(hint_label(_text("gui.output_advanced_hint")))
        layout.addWidget(self.advanced_section)
        layout.addStretch(1)
        return group

    def _build_generate_group(self):
        """Step 4: the write action, then the service's own result."""
        group = QGroupBox(_text("gui.output_group_generate"))
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.generate_button = QPushButton(_text("gui.output_generate"))
        self.generate_button.setProperty("role", "primary")
        self.generate_button.clicked.connect(self.generate)
        self.generate_button.setEnabled(False)
        row.addWidget(self.generate_button)
        row.addWidget(hint_label(_text("gui.output_write_hint")), 1)
        layout.addLayout(row)
        self.result_note = QLabel(_text("gui.output_result_empty"))
        self.result_note.setWordWrap(True)
        self.result_view = QPlainTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setFont(fixed_font())
        self.result_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.result_view.setMinimumHeight(110)
        layout.addWidget(self.result_note)
        layout.addWidget(self.result_view)
        self.result_section = group
        return group

    def _build_plan(self):
        """Step 3: preview, the plan itself, then every message it raises."""
        group = QGroupBox(_text("gui.output_group_plan"))
        layout = QVBoxLayout(group)
        layout.addWidget(hint_label(_text("gui.output_step3_hint")))
        header = QHBoxLayout()
        self.preview_button = QPushButton(_text("gui.output_preview"))
        self.preview_button.clicked.connect(self.preview_plan)
        header.addWidget(self.preview_button)
        header.addStretch(1)
        layout.addLayout(header)
        self.plan_note = QLabel(_text("gui.output_plan_empty"))
        self.plan_note.setWordWrap(True)
        layout.addWidget(self.plan_note)

        self.plan_tabs = QTabWidget()
        files_page = QWidget()
        files_layout = QVBoxLayout(files_page)
        self.entries_table = self._table(
            ("gui.output_col_kind", "gui.output_col_job", "gui.output_col_file", "gui.output_col_action"),
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

        action_row = QHBoxLayout()
        self.copy_button = QPushButton(_text("gui.output_copy_path"))
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_selected_path)
        action_row.addWidget(self.copy_button)
        action_row.addStretch(1)
        action_widget = QWidget()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_widget.setLayout(action_row)
        layout.addWidget(self.plan_tabs, 1)
        layout.addWidget(action_widget)
        layout.addWidget(self._build_messages())
        return group

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
        """Conflicts, warnings and blocking findings, never inside Advanced.

        Conflicts are labelled *blocking* and carry a warning colour in
        addition to the word; warnings say they are non-blocking. Neither
        list hides itself behind the advanced disclosure, because both demand
        a decision before Step 4.
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

    def _policy_name(self, combo) -> str:
        return combo.currentData() or ""

    def _on_control_changed(self, *_args) -> None:
        """Any control change voids the reviewed plan (it is never reused)."""
        self._invalidate_plan()

    def _current_signature(self):
        return (
            self.destination.text().strip(),
            self._policy_name(self.overwrite_policy),
            self._policy_name(self.path_policy),
        )

    # -- refresh -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the job and invalidate any plan from an earlier state."""
        configuration = self._state.configuration
        if configuration is None:
            self._base_label.setText(_text("menu.no_project"))
            self.preview_button.setEnabled(False)
            self._stale = False
            self._invalidate_plan(clear=True)
            self._defaults_token = None
            return

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
        had_plan = self._plan is not None
        self.preview_button.setEnabled(True)
        self._invalidate_plan(
            message_key="gui.output_plan_invalidated" if had_plan else None
        )

    def _invalidate_plan(self, message_key=None, clear: bool = True) -> None:
        if self._plan is not None:
            self._stale = True
        self._plan = None
        self._signature = None
        self.generate_button.setEnabled(False)
        if clear:
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
        if message_key is None and self._stale:
            message_key = "gui.output_stale"
        self.plan_note.setText(
            _text(message_key) if message_key is not None else _text("gui.output_plan_empty")
        )
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
        """Plan the current selection and show it; writes nothing."""
        if self._state.configuration is None:
            self._problems(_text("menu.no_project"))
            return False
        signature = self._current_signature()
        root = signature[0]
        if not root:
            self._problems(_text("gui.output_no_folder"))
            return False
        plan = self._state.plan_generation(**self._plan_arguments())
        self._signature = signature
        self._plan = plan
        self._show_plan(plan)
        if not plan.ok:
            self._problems(plan.message or "")
        return plan.ok

    def _show_plan(self, plan) -> None:
        """Render a service plan (successful or refused) without writing."""
        self._stale = False
        self.entries_table.setRowCount(0)
        self.resources_table.setRowCount(0)
        self.conflicts_list.clear()
        self.warnings_list.clear()
        self.findings_model.set_findings(())
        self.findings_note.setText("")
        self.review_button.setVisible(False)

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
            _text("gui.output_warnings") % len(plan.warnings)
            if plan.warnings
            else _text("gui.output_no_warnings")
        )
        self.warnings_label.setVisible(bool(plan.warnings) or not plan.ok)

        if not plan.ok:
            self.plan_note.setText(
                _text("gui.output_plan_refused") % (plan.message or "")
            )
            self.generate_button.setEnabled(False)
            self._fill_refusal_findings(plan)
            self._update_copy_button()
            return

        self._fill_entries(plan)
        self._fill_resources(plan)
        resources = plan.reviewed.resources if plan.reviewed is not None else ()
        copied = sum(1 for resource in resources if resource.copied)
        note = _text("gui.output_plan_ready") % (
            len(plan.entries),
            copied,
            len(plan.warnings),
        )
        self.plan_note.setText(note)
        self._stale = False
        self.generate_button.setEnabled(self._current_signature() == self._signature)
        self._update_copy_button()

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
        """Confirm, re-check the plan is unchanged, then execute it."""
        if self._plan is None or self._signature is None:
            self._problems(
                _text("gui.output_stale")
                if self._stale
                else _text("gui.output_need_plan")
            )
            return False
        if self._current_signature() != self._signature:
            self._problems(_text("gui.output_stale"))
            return False
        plan = self._plan
        if not plan.ok or plan.reviewed is None:
            self._problems(plan.message or "")
            return False

        question = _text("gui.output_confirm_question") % (
            len(plan.entries),
            plan.output_root,
            self.overwrite_policy.currentText(),
            self.path_policy.currentText(),
        )
        if not self.generation_confirmer(self, question):
            return False

        # The destination may have changed since the preview (another program
        # wrote a file, a folder appeared). Plan again and compare: executing
        # anything but the reviewed plan would write bytes the user never saw.
        refreshed = self._state.plan_generation(**self._plan_arguments())
        if not _same_plan(plan, refreshed):
            self._plan = refreshed
            self._signature = self._current_signature()
            self._show_plan(refreshed)
            self._problems(_text("gui.output_plan_changed"))
            return False

        result = self._state.execute(plan)
        self._show_result(result)
        self._plan = None
        self._signature = None
        self._stale = False
        self.generate_button.setEnabled(False)
        self.plan_note.setText(_text("gui.output_plan_done"))
        self.result_section.setVisible(True)
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
        if errors:
            self._problems(errors[0])
        else:
            self._notify(summary)

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
