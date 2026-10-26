"""Modal dialogs of the Qt front end (Stages 1-4).

Every dialog here renders wording and returns the user's answer: the import
preview renders a service result, the lifecycle dialogs (problem, discard,
overwrite, save chooser, removal confirmations) ask their one question, the
entity/advanced forms collect values for the page to submit, and the ligand
file dialogs ask their two paths and report the run. None performs a service
call or a file access of its own.
"""

from __future__ import annotations

from configbuilder.ui.render.qt.dialogs.advanced_forms import (
    AlignmentFormDialog,
    BondFormDialog,
    ModificationFormDialog,
    TemplateEditorDialog,
)
from configbuilder.ui.render.qt.dialogs.entity_forms import (
    LigandFormDialog,
    SequenceFormDialog,
)
from configbuilder.ui.render.qt.dialogs.import_preview import (
    ImportPreviewDialog,
    show_failure,
)
from configbuilder.ui.render.qt.dialogs.ligand_batch import (
    choose_ligand_file,
    choose_output_folder,
    confirm_ligand_preview,
    report_ligand_run,
)
from configbuilder.ui.render.qt.dialogs.messages import (
    ask_save_path,
    confirm_bond_removal,
    confirm_discard,
    confirm_entity_delete,
    confirm_generation,
    confirm_modification_removal,
    confirm_overwrite,
    show_problem,
)

__all__ = [
    "AlignmentFormDialog",
    "BondFormDialog",
    "ImportPreviewDialog",
    "LigandFormDialog",
    "ModificationFormDialog",
    "SequenceFormDialog",
    "TemplateEditorDialog",
    "ask_save_path",
    "choose_ligand_file",
    "choose_output_folder",
    "confirm_bond_removal",
    "confirm_discard",
    "confirm_entity_delete",
    "confirm_generation",
    "confirm_ligand_preview",
    "confirm_modification_removal",
    "confirm_overwrite",
    "report_ligand_run",
    "show_failure",
    "show_problem",
]
