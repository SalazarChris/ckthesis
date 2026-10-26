"""The ligand file workflow's dialogs: file, folder, review, result.

Four dumb steps, in the order the workflow asks them:

- :func:`choose_ligand_file` — the native open dialog for the input list;
- :func:`choose_output_folder` — the native folder dialog for the outputs;
- :func:`confirm_ligand_preview` — one box listing what was read and where
  it will be written, before anything is planned or written;
- :func:`report_ligand_run` — the outcome: the files that were written, or
  the service's own refusal.

Like every other dialog here they render wording and return an answer.
None of them reads a molecule, calls a service, decides a file name or
writes anything: the page owns that sequence, and the service owns every
decision behind it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from configbuilder.ui.present.strings import text as _text

__all__ = [
    "choose_ligand_file",
    "choose_output_folder",
    "confirm_ligand_preview",
    "report_ligand_run",
]

#: How many entries the review box lists before it summarises the rest. The
#: count is always exact; only the enumeration is capped, so a file of two
#: hundred molecules does not open a wall of text.
_PREVIEW_ROWS = 12


def choose_ligand_file(parent, start: str = "") -> str:
    """Ask for the ligand input file; ``""`` means the user cancelled."""
    path, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        _text("gui.ligand_file_dialog"),
        start,
        _text("gui.ligand_file_filter"),
    )
    return path or ""


def choose_output_folder(parent, start: str = "") -> str:
    """Ask for the output folder; ``""`` means the user cancelled."""
    return QFileDialog.getExistingDirectory(
        parent, _text("gui.ligand_folder_dialog"), start
    ) or ""


def confirm_ligand_preview(parent, preview, output_root: str) -> bool:
    """Show what was read and where it will go; returns True to continue.

    Cancel is the default button: the safe answer is the one a stray Return
    picks, and nothing has been planned or written at this point.
    """
    entries = list(preview.entries)
    shown = entries[:_PREVIEW_ROWS]
    lines = [
        _text("gui.ligand_preview_entries") % len(entries),
        "",
    ] + [_text("gui.ligand_preview_row") % entry for entry in shown]
    if len(entries) > len(shown):
        lines.append(_text("gui.ligand_preview_more") % (len(entries) - len(shown)))
    lines.extend(
        [
            "",
            _text("gui.ligand_preview_destination") % output_root,
            _text("gui.ligand_preview_files") % len(entries),
            _text("gui.ligand_preview_note"),
        ]
    )
    box = QMessageBox(parent)
    box.setWindowTitle(_text("gui.ligand_preview_title"))
    box.setText("\n".join(lines))
    proceed = box.addButton(
        _text("gui.ligand_preview_accept"), QMessageBox.AcceptRole
    )
    cancel = box.addButton(_text("gui.form_cancel"), QMessageBox.RejectRole)
    box.setDefaultButton(cancel)
    box.exec()
    return box.clickedButton() is proceed


def report_ligand_run(parent, output) -> None:
    """Report the run: files written, or the refusal's own message.

    ``output`` is the service's ``LigandBatchOutput`` — this function only
    lays out what it says, so a success message is never shown for a batch
    that wrote nothing, and the refusal names the file or finding that
    stopped it.
    """
    plan = output.plan
    lines = []
    if plan is not None and not plan.ok:
        lines.append(_text("gui.ligand_result_refused") % (plan.message or ""))
        lines.extend(plan.conflicts)
        for finding in plan.findings:
            lines.append("  - %s" % finding.user_message)
    elif output.written:
        lines.append(_text("gui.ligand_result_written") % len(output.written))
        lines.extend(output.written)
        if output.errors:
            lines.append("")
            lines.append(_text("gui.ligand_result_errors"))
            lines.extend(output.errors)
        skipped = len(plan.entries) - len(output.written) if plan is not None else 0
        if skipped > 0:
            lines.append("")
            lines.append(_text("gui.ligand_result_skipped") % skipped)
    else:
        lines.append(_text("gui.ligand_result_nothing"))
    box = QMessageBox(parent)
    box.setWindowTitle(_text("gui.ligand_result_title"))
    box.setText("\n".join(lines))
    box.exec()
