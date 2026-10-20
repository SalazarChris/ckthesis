"""The application window: one shell over the pages, plus the job lifecycle.

What this window owns is navigation and the order of operations, never
domain work. The open job lives in ``ProjectService``; the pages re-read it
through :class:`~configbuilder.ui.render.qt.state.GuiState` whenever the
state says it changed.

Stage 2 adds the job lifecycle:

- **New Job** starts a fresh job through ``ProjectService.new`` — the
  service's own default policy supplies the name, seeds and version pin.
- **Save JSON…** asks for a destination, then runs the *generation service's*
  two-step workflow: ``plan_save`` (validate, transform, encode, decide the
  overwrite action) and then ``execute`` (write exactly the reviewed bytes).
  This window never assembles a wire document, never serializes JSON, never
  allocates an identifier and never writes a file itself.
- **Overview** hosts the one job-wide settings editor; it sends the job
  name, model seeds and JSON version to ``ConfigurationService``, which
  validates and may refuse. There is no second settings destination.

The shell is the approved mockup's: a captioned sidebar (WORKSPACE, then the
four destinations; FILE, then New · Open · Save) and a product header carrying
the job name and the "Unsaved"/"Saved" pill. The three lifecycle actions live
in the FILE footer and keep the standard Ctrl+N/Ctrl+O/Ctrl+S shortcuts; the
menu bar itself is hidden, so the same commands are not offered twice.

The standalone JSON preview destination was removed (Stage 9): the builder's
JSON is reached through **Save JSON…** and the Generate plan, and a read-only
copy of the same service text is kept as an internal, non-navigable view
(:attr:`preview_page`) for the window's own checks. It is not a destination
and never appears in the sidebar.

Unsaved changes are never discarded silently: New Job, opening another file
and closing the window all ask first (``confirm_discard``), and Cancel keeps
the job. Every modal is an assignable attribute, which is how the offscreen
tests answer it without a click.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from configbuilder.app.results import FailureReason
from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.qt.dialogs import (
    ImportPreviewDialog,
    ask_save_path,
    confirm_discard,
    confirm_overwrite,
    show_failure,
    show_problem,
)
from configbuilder.ui.render.qt.pages import (
    AdvancedPage,
    EntitiesPage,
    GeneratePage,
    OverviewPage,
    PreviewPage,
    VariantsPage,
)
from configbuilder.ui.render.qt.style import apply_style
from configbuilder.ui.render.qt.widgets import app_mark_pixmap, navigation_icon

__all__ = ["MainWindow"]


class MainWindow(QMainWindow):
    """The review, settings and save window over the current job."""

    def __init__(self, state, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self.setWindowTitle(_text("gui.window_title"))
        self.setMinimumSize(940, 640)
        # How a refusal reaches the user. The defaults are the modal boxes;
        # the tests replace them with recorders, because a modal waits for a
        # click that an offscreen test can never give. Whatever reports, the
        # refusal is also kept and shown on the status line.
        self.failure_reporter = show_failure
        self.problem_reporter = show_problem
        self.discard_confirmer = confirm_discard
        self.overwrite_confirmer = confirm_overwrite
        self.save_path_chooser = ask_save_path
        self._last_failure = ""
        self._last_problem = ""
        self._build()
        apply_style(self)
        self._state.project_changed.connect(self.refresh)
        self._state.source_changed.connect(self._refresh_source)
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build(self) -> None:
        self._new_action = QAction(_text("gui.action_new_job"), self)
        self._new_action.setShortcut(QKeySequence.New)
        self._new_action.triggered.connect(self.new_job)
        self._open_action = QAction(_text("gui.action_open"), self)
        self._open_action.setShortcut(QKeySequence.Open)
        self._open_action.triggered.connect(self.open_json)
        self._save_action = QAction(_text("gui.action_save"), self)
        self._save_action.setShortcut(QKeySequence.Save)
        self._save_action.triggered.connect(self.save_json)
        self._quit_action = QAction(_text("gui.action_quit"), self)
        self._quit_action.setShortcut(QKeySequence.Quit)
        self._quit_action.triggered.connect(self.close)
        # The menu bar is hidden, so the shortcuts must belong to the window
        # itself rather than only to a menu that is not on screen.
        for action in (
            self._new_action,
            self._open_action,
            self._save_action,
            self._quit_action,
        ):
            self.addAction(action)

        # The mockup has no menu strip, and the FILE footer is the one visible
        # home for New/Open/Save. Keep the actions (they carry the standard
        # keyboard shortcuts and the footer's tooltips) but not a second,
        # duplicated menu bar above the product header.
        file_menu = self.menuBar().addMenu(_text("gui.menu_file"))
        file_menu.addAction(self._new_action)
        file_menu.addAction(self._open_action)
        file_menu.addSeparator()
        file_menu.addAction(self._save_action)
        file_menu.addSeparator()
        file_menu.addAction(self._quit_action)
        self.menuBar().setVisible(False)

        self._overview = OverviewPage(
            self._state,
            notify=self._notify,
            problems=self.report_problem,
            parent=self,
        )
        self._advanced = AdvancedPage(
            self._state,
            notify=self._notify,
            problems=self.report_problem,
            parent=self,
            embedded=True,
            scope="entity",
        )
        # The job-wide tools are their own instances and their own work areas:
        # a custom CCD or a bond belongs to the job, not to the selected entity.
        self._ccd = AdvancedPage(
            self._state,
            notify=self._notify,
            problems=self.report_problem,
            parent=self,
            embedded=True,
            scope="ccd",
        )
        self._bonds = AdvancedPage(
            self._state,
            notify=self._notify,
            problems=self.report_problem,
            parent=self,
            embedded=True,
            scope="bonds",
        )
        # The entity workspace hosts a compact picker and three work areas:
        # the selected entity's settings, Custom CCDs and Covalent bonds.
        self._entities = EntitiesPage(
            self._state,
            notify=self._notify,
            problems=self.report_problem,
            advanced=self._advanced,
            ccd=self._ccd,
            bonds=self._bonds,
            parent=self,
        )
        self._variants = VariantsPage(
            self._state,
            notify=self._notify,
            problems=self.report_problem,
            parent=self,
        )
        self._output = GeneratePage(
            self._state,
            notify=self._notify,
            problems=self.report_problem,
            parent=self,
        )
        # The serialized document view is internal only since Stage 9: it is
        # not a destination, not in the sidebar and not reachable from any
        # button. Save JSON… is the user-facing route to the file itself.
        self._preview = PreviewPage(self._state, notify=self._notify, parent=self)
        self._build_shell()
        # The Overview's entity summary changes destination; nothing else
        # about it is special.
        self._overview.entities_requested.connect(
            lambda: self.show_page(self._entities)
        )

        self._output.record_activated.connect(self._show_entity)
        self._output.review_requested.connect(self._show_overview)
        # The Advanced tab always speaks about the entity selected on the
        # Entities tab: one selection, two views of it.
        self._entities.selection_changed.connect(self._advanced.show_record)

        self._notice = QLabel()
        self.statusBar().addWidget(self._notice, 1)
        self._source = QLabel()
        self.statusBar().addPermanentWidget(self._source)
        self._refresh_source()

    # -- the shell: sidebar, header, one stacked workspace ---------------

    #: The four destinations, in the order the sidebar shows them. The
    #: labels are the registry's page names, so the sidebar, the window and
    #: any test agree by construction.
    _DESTINATIONS = (
        ("gui.tab_overview", "_overview", "overview"),
        ("gui.tab_entities", "_entities", "entities"),
        ("gui.tab_variants", "_variants", "variants"),
        ("gui.tab_output", "_output", "generate"),
    )

    def _build_shell(self) -> None:
        """The mockup's frame: captioned sidebar, product header, one pane.

        The sidebar opens with WORKSPACE over the four working destinations and
        closes with FILE over the three lifecycle actions, exactly as the
        mockup arranges them. One destination is visible at a time; the header
        always says which job is open and whether it has unsaved changes.
        """
        panel = QWidget()
        panel.setObjectName("sidebarPanel")
        panel.setFixedWidth(200)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        panel_layout.addWidget(self._sidebar_caption("gui.nav_section_workspace"))

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setSelectionMode(QListWidget.SingleSelection)
        self._sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._sidebar.setIconSize(QSize(16, 16))
        self._sidebar.setFocusPolicy(Qt.StrongFocus)
        self._stack = QStackedWidget()
        for label_key, attribute, icon_name in self._DESTINATIONS:
            page = getattr(self, attribute)
            item = QListWidgetItem(navigation_icon(icon_name), _text(label_key))
            self._sidebar.addItem(item)
            self._stack.addWidget(page)
        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.setCurrentRow(0)
        panel_layout.addWidget(self._sidebar, 1)
        panel_layout.addWidget(self._sidebar_caption("gui.nav_section_file"))
        panel_layout.addLayout(self._build_file_actions())

        # One inset for every destination, so switching page does not shift the
        # content edge; the pages themselves carry no outer margin.
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._stack)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(panel)
        body_layout.addWidget(content, 1)

        # The header spans the whole window, as in the mockup: the product mark
        # sits at the window's top-left, above the sidebar's WORKSPACE caption.
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._build_header())
        central_layout.addWidget(body, 1)
        self.setCentralWidget(central)

    @staticmethod
    def _sidebar_caption(key: str) -> QLabel:
        """A sidebar section caption (WORKSPACE, FILE)."""
        caption = QLabel(_text(key))
        caption.setObjectName("sidebarCaption")
        return caption

    def _build_file_actions(self):
        """FILE: New · Open · Save, as the mockup's quiet footer row.

        The same three actions are in the File menu; the footer is the visible
        route, the menu is the familiar one. Both call the window's own
        lifecycle methods, so the unsaved-changes question is asked exactly
        once per attempt.
        """
        row = QHBoxLayout()
        row.setContentsMargins(14, 0, 14, 12)
        row.setSpacing(4)
        self._file_buttons = []
        for index, (action, key, handler) in enumerate(
            (
                (self._new_action, "gui.file_action_new", self.new_job),
                (self._open_action, "gui.file_action_open", self.open_json),
                (self._save_action, "gui.file_action_save", self.save_json),
            )
        ):
            if index:
                separator = QLabel("·")
                separator.setProperty("role", "caption")
                row.addWidget(separator)
            button = QToolButton()
            button.setObjectName("fileAction")
            button.setText(_text(key))
            button.setProperty("role", "fileAction")
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            button.setToolTip(action.text())
            button.setAccessibleName(action.text())
            button.clicked.connect(handler)
            row.addWidget(button)
            self._file_buttons.append(button)
        row.addStretch(1)
        return row

    def _build_header(self):
        """The mockup's header: mark, product name, job line, state pill."""
        header = QFrame()
        header.setObjectName("appHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(10)
        badge = QLabel()
        badge.setObjectName("appBadge")
        badge.setFixedSize(38, 38)
        badge.setAlignment(Qt.AlignCenter)
        badge.setPixmap(app_mark_pixmap(22))
        layout.addWidget(badge)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        product = QLabel(_text("gui.app_name"))
        product.setObjectName("appTitle")
        subtitle = QLabel(_text("gui.app_subtitle"))
        subtitle.setObjectName("appSubtitle")
        titles.addWidget(product)
        titles.addWidget(subtitle)
        layout.addLayout(titles)
        layout.addStretch(1)
        self._header_job = QLabel()
        self._header_job.setObjectName("headerJob")
        self._header_job.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._header_state = QLabel()
        self._header_state.setObjectName("statePill")
        self._header_state.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._header_job)
        layout.addWidget(self._header_state)
        return header

    def _refresh_header(self) -> None:
        """The header's job line and unsaved marker, in words, not colour.

        The marker is the mockup's pill: "Unsaved" while ``GuiState.is_dirty``
        says the job differs from the last open/save, "Saved" otherwise. The
        word carries the meaning; the accent only reinforces it.
        """
        project = self._state.project
        if project is None:
            self._header_job.setText(_text("gui.header_no_job"))
            self._header_state.setText("")
            self._header_state.setVisible(False)
            return
        self._header_state.setVisible(True)
        self._header_job.setText(
            _text("gui.header_job") % project.configuration.metadata.name
        )
        if project is not None and self._state.is_dirty:
            self._header_state.setText(_text("gui.header_unsaved"))
            self._header_state.setProperty("state", "dirty")
        else:
            self._header_state.setText(_text("gui.header_saved"))
            self._header_state.setProperty("state", "clean")
        # A dynamic property drives the sheet, so it must be re-polished.
        self._header_state.style().unpolish(self._header_state)
        self._header_state.style().polish(self._header_state)

    # -- the job lifecycle (Stage 2) ---------------------------------------

    def new_job(self) -> bool:
        """Start a fresh job; unsaved changes are never discarded silently."""
        if not self.confirm_discard_changes():
            return False
        project = self._state.new_job()
        self.statusBar().showMessage(
            _text("menu.job_created") % project.configuration.metadata.name, 8000
        )
        return True

    def confirm_discard_changes(self) -> bool:
        """Ask before throwing away unsaved edits.

        Returns True when it is safe to proceed (nothing is unsaved, or the
        user chose to discard) and False when the user kept the job.
        """
        if not self._state.has_project() or not self._state.is_dirty:
            return True
        return bool(self.discard_confirmer(self))

    def save_json(self) -> bool:
        """Save the open job as AF3 JSON through the generation service.

        The sequence mirrors the console's own save: choose a destination,
        confirm an existing file, plan, then execute. A refusal is reported
        with the service's reason (and its findings when validation blocked
        it) and nothing is marked saved; success updates the current path and
        the saved state only after ``execute`` reports it wrote the plan.
        """
        if not self._state.has_project():
            self.report_problem(_text("menu.no_project"))
            return False
        destination, accepted = self.save_path_chooser(
            self, self._state.source_path or self._state.suggested_file_name()
        )
        if not accepted or not destination:
            self.statusBar().showMessage(_text("menu.save_cancelled"), 8000)
            return False
        overwrite = os.path.exists(destination)
        if overwrite and not self.overwrite_confirmer(self, destination):
            self.statusBar().showMessage(_text("menu.save_cancelled"), 8000)
            return False

        plan = self._state.plan_save(destination, overwrite=overwrite)
        if not plan.ok:
            return self._report_save_refusal(plan)
        result = self._state.execute(plan)
        if not result.ok:
            message = "\n\n".join(str(error) for error in result.errors) or result.message
            self.report_problem(message)
            self._show_status_for_problem(message)
            return False
        for path in result.written:
            self.statusBar().showMessage(_text("menu.save_job_wrote") % path, 8000)
        for path in result.skipped:
            self.statusBar().showMessage(_text("menu.export_skipped") % path, 8000)
        self._state.record_save(destination)
        return True

    def _report_save_refusal(self, plan) -> bool:
        """Show why nothing was written, including the blocking findings.

        Readiness is a compact line now, so the reasons come to the user here,
        on the save attempt, instead of living in a permanent list on Overview.
        """
        if plan.failure_reason == FailureReason.VALIDATION_BLOCKED:
            message = self._blocking_message(plan)
        else:
            message = plan.message or ""
        for conflict in plan.conflicts:
            line = _text("menu.export_conflict") % conflict
            message = "%s\n\n%s" % (message, line) if message else line
        self.report_problem(message)
        self._show_status_for_problem(message)
        return False

    @staticmethod
    def _blocking_message(plan) -> str:
        """The blocking findings as a short, actionable explanation."""
        findings = tuple(getattr(plan, "findings", ()) or ())
        blocking = tuple(
            finding
            for finding in findings
            if getattr(getattr(finding, "severity", None), "name", "") == "ERROR"
        ) or findings
        if not blocking:
            return plan.message or ""
        header = (
            _text("gui.blocked_header_one")
            if len(blocking) == 1
            else _text("gui.blocked_header") % len(blocking)
        )
        lines = [header]
        for finding in blocking[:4]:
            lines.append(_text("gui.blocked_line") % finding.user_message)
            if finding.suggestion:
                lines.append(_text("gui.blocked_fix") % finding.suggestion)
        if len(blocking) > 4:
            lines.append(_text("gui.blocked_more") % (len(blocking) - 4))
        return "\n".join(lines)

    # -- the import path: preview, confirm, then commit --------------------

    def open_json(self) -> None:
        """Ask for a file, preview it, and commit only if the user imports."""
        from PySide6.QtWidgets import QFileDialog

        path, _selected = QFileDialog.getOpenFileName(
            self,
            _text("gui.open_dialog_title"),
            "",
            _text("gui.file_filter"),
        )
        if not path:
            return
        self.offer_import(path)

    def offer_import(self, path: str) -> bool:
        """Run the preview → confirm → commit sequence for ``path``.

        The unsaved-changes question comes **after** the preview is accepted
        and **before** the commit, so a Cancel keeps the open job exactly as
        it is, and a user who abandons the preview is never asked about a
        replacement that was not going to happen.

        Returns True when the file became the open job.
        """
        preview = self._state.preview_import(path)
        if not preview.ok:
            self.report_failure(preview.message)
            return False
        dialog = ImportPreviewDialog(self, path, preview)
        if dialog.exec() != ImportPreviewDialog.Accepted:
            return False
        if not self.confirm_discard_changes():
            return False
        outcome = self._state.commit_import(path)
        if not outcome.ok:
            self.report_failure(outcome.message)
            return False
        self.statusBar().showMessage(_text("menu.import_loaded"), 8000)
        return True

    # -- reporting ---------------------------------------------------------

    def report_failure(self, message: str) -> str:
        """Tell the user why a file was refused, in their terms.

        The service's own message is shown verbatim (never a traceback), the
        status line keeps it visible after the box is dismissed, and it stays
        readable through :meth:`last_failure_text` so a test can assert on it.
        """
        self._last_failure = message
        self.statusBar().showMessage(_text("menu.import_failed"), 8000)
        self.failure_reporter(self, message)
        return message

    def report_problem(self, message: str) -> str:
        """Tell the user why an action was refused, with the service's reason.

        The same contract as :meth:`report_failure` for everything that is
        not an import; the message is kept verbatim and readable through
        :meth:`last_problem_text`.
        """
        self._last_problem = message
        self.problem_reporter(self, message)
        return message

    def _notify(self, message: str) -> None:
        """A success line on the status bar (never a modal box)."""
        self.statusBar().showMessage(message, 8000)

    def _show_status_for_problem(self, message: str) -> None:
        first_line = (message or "").splitlines()[0] if message else ""
        self.statusBar().showMessage(_text("menu.not_applied") % first_line, 8000)

    # -- refresh and navigation -------------------------------------------

    def refresh(self) -> None:
        """Re-read every page from the services. Writes nothing."""
        self._save_action.setEnabled(self._state.has_project())
        self._file_buttons[2].setEnabled(self._state.has_project())
        self._overview.refresh()
        self._entities.refresh()
        self._advanced.refresh()
        self._ccd.refresh()
        self._bonds.refresh()
        self._variants.refresh()
        self._output.refresh()
        self._preview.refresh()
        self._refresh_source()
        self._refresh_title()
        self._refresh_notice()
        self._refresh_header()

    def _refresh_title(self) -> None:
        """Name the open job in the title bar and mark unsaved changes.

        The marker is text, not colour: the title reads "name* - AF3 JSON
        Builder" exactly while ``GuiState.is_dirty`` says the live
        configuration differs from the last save or open. Only an operation
        that actually recorded a save clears it.
        """
        project = self._state.project
        if project is None:
            self.setWindowTitle(_text("gui.window_title"))
            return
        name = project.configuration.metadata.name
        template = (
            "gui.window_title_dirty" if self._state.is_dirty else "gui.window_title_job"
        )
        self.setWindowTitle(_text(template) % name)

    def _refresh_notice(self) -> None:
        """The status bar's one standing hint, matched to the current state."""
        if not self._state.has_project():
            key = "gui.notice_no_job"
        elif self._state.is_dirty:
            key = "gui.notice_dirty"
        else:
            key = "gui.notice_job"
        self._notice.setText(_text(key))

    def _refresh_source(self) -> None:
        if self._state.is_demo:
            self._source.setText(_text("gui.demo_notice"))
        elif self._state.source_path:
            self._source.setText(_text("gui.source_file") % self._state.source_path)
        else:
            self._source.setText(_text("gui.source_none"))

    def _show_entity(self, record_key: str) -> None:
        """Follow a finding to the entity it names."""
        if self._entities.select_record(record_key):
            self.show_page(self._entities)

    def _show_overview(self) -> None:
        """Follow a generation refusal to the readiness view."""
        self._overview.refresh()
        self.show_page(self._overview)

    def show_page(self, page) -> None:
        """Bring one destination forward (the sidebar follows the workspace)."""
        index = self._stack.indexOf(page)
        if index >= 0:
            self._sidebar.setCurrentRow(index)

    def current_page(self):
        """The destination currently displayed."""
        return self._stack.currentWidget()

    def destination_pages(self):
        """The pages the sidebar can reach, in its own order."""
        return tuple(
            self._stack.widget(index) for index in range(self._stack.count())
        )

    def sidebar_labels(self):
        """The destination labels, in the sidebar's own order."""
        return [
            self._sidebar.item(row).text() for row in range(self._sidebar.count())
        ]

    # -- close -------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Closing is the third place unsaved changes must not vanish."""
        if self.confirm_discard_changes():
            event.accept()
        else:
            event.ignore()

    # -- page accessors (used by the window's own tests and callers) -------

    def source_text(self) -> str:
        """The status bar's source line as displayed."""
        return self._source.text()

    def notice_text(self) -> str:
        """The status bar's read-only notice as displayed."""
        return self._notice.text()

    def header_job_text(self) -> str:
        """The header's job line as displayed."""
        return self._header_job.text()

    def header_state_text(self) -> str:
        """The header's saved/unsaved marker as displayed."""
        return self._header_state.text()

    def file_action_texts(self):
        """The FILE footer's actions, in the order the sidebar shows them."""
        return [button.text() for button in self._file_buttons]

    def last_failure_text(self) -> str:
        """The last refusal's own message, as reported to the user."""
        return self._last_failure

    def last_problem_text(self) -> str:
        """The last non-import refusal's own message, as reported."""
        return self._last_problem

    @property
    def state(self):
        return self._state

    @property
    def overview_page(self):
        return self._overview

    @property
    def entities_page(self):
        return self._entities

    @property
    def settings_page(self):
        """The one job-wide settings editor: the panel Overview hosts.

        Stage 8 removed the separate Job Settings tab, so this accessor names
        the single remaining placement rather than a page of its own. A
        caller that used to read the tab now reads the same widget, backed by
        the same ``ConfigurationService``.
        """
        return self._overview.job_settings

    @property
    def ccd_page(self):
        """The job-wide Custom CCD work area hosted inside Entities."""
        return self._ccd

    @property
    def bonds_page(self):
        """The job-wide Covalent bonds work area hosted inside Entities."""
        return self._bonds

    @property
    def advanced_page(self):
        return self._advanced

    @property
    def variants_page(self):
        return self._variants

    @property
    def output_page(self):
        return self._output

    @property
    def preview_page(self):
        """The internal read-only JSON view (not a destination since Stage 9).

        It shows exactly what ``GenerationService.show_json`` returns and is
        refreshed with the window, but no sidebar item, Overview action or
        other route displays it: the user reads the document by saving it.
        The tests still read it back as the window's copy of the service text.
        """
        return self._preview
