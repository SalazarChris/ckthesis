"""The front end's string registry (plan §18.7, §18.8; CHECKLIST 11a).

Every user-visible *chrome* string — action wording, fixed notices — is
data here, keyed, unique, and non-empty. Domain labels are NOT here: they
resolve through the model's traceability registry (plan §3), and finding
wording comes from the rule messages. The meta-test asserts the split: any
user-visible string in ``ui`` is either a registry label, a rule message, or
a member of this registry.

The registry is the meta-test's oracle in both directions: a string used by
``ui`` that is missing from here (and from the two domain sources) fails the
suite, and an entry nothing uses is dead vocabulary.
"""

from __future__ import annotations

__all__ = ["STRINGS", "text"]


STRINGS = {
    # The §16.3 action grammar's wording (keys 'n', 'p', 'e', 'd', 'v',
    # 's', 'q' are keystroke tokens, not display text).
    "action.next_step": "next step",
    "action.previous_step": "previous step",
    "action.edit_item": "edit an item",
    "action.delete_item": "delete an item",
    "action.validate_now": "validate now",
    "action.quit": "quit",
    # Fixed notices
    "sequence.empty": "(empty sequence)",
    # Fallback grouping context for findings whose rule emitted no locator.
    "finding.context.general": "General",
    # Console wording.
    "console.eof": "input stream closed",
    # The findings list's numbering template (shared by every screen).
    "jump.reference": "%d. %s — %s",

    # -- the builder's shared chrome -------------------------------------
    "menu.select_prompt": "Select: ",
    "menu.banner_title": "JSON CONFIGURATION BUILDER",
    "menu.back": "0. Back",
    "menu.exit": "0. Exit",
    "menu.invalid": "Not a valid choice: %r",
    "menu.interrupted": "Interrupted — returning to the menu.",
    "menu.choice_line": "%d. %s",
    "menu.applied": "Applied.",
    "menu.not_applied": "Not applied: %s",
    "menu.no_project": "No project is open.",
    "menu.need_whole_number": "%r is not a whole number — enter digits only (for example 12).",

    # -- the main menu: new job / open a JSON file ------------------------
    "menu.main_actions": (
        "1. New job\n"
        "2. Open a JSON file"
    ),
    "menu.ask_experiment": "Job name (blank generates one): ",
    "menu.job_created": "Started job %s.",

    # -- the job menu ----------------------------------------------------
    "menu.job_title": "JOB MENU",
    # The header block under the banner: the job's identity (name, seed set,
    # model target), its state (modifications, custom CCD, unsaved changes)
    # and the chains recorded so far — the work in progress, visible every
    # time the menu is drawn. One row template, so the colons line up.
    "menu.job_header_row": "%-13s : %s",
    "menu.job_header_label_name": "Name",
    "menu.job_header_label_seed": "Seed",
    "menu.job_header_label_model": "Model",
    "menu.job_header_label_modifications": "Modifications",
    "menu.job_header_label_ccd": "Custom CCD",
    "menu.job_header_label_changes": "Changes",
    "menu.job_header_model_value": "%s (JSON %s)",
    "menu.job_header_ccd_inline": "inline CIF, %d lines",
    # The one value the state rows share when there is nothing to report.
    "menu.job_header_none": "none",
    "menu.job_header_changes_unsaved": "unsaved",
    "menu.model_name": "AlphaFold 3",
    "menu.job_header_entities": "Entities (%d):",
    "menu.job_chain_line": "  Chain %s  %s",
    "menu.job_chain_mods": "  (modifications: %d)",
    "menu.job_actions": (
        "1. Edit job configurations\n"
        "2. Add entity\n"
        "3. Edit entity\n"
        "4. Custom CCD management\n"
        "5. PTM management\n"
        "6. Save and show summary\n"
        "7. Create variants based on this JSON"
    ),
    "menu.job_back": "0. Return to main menu",
    "menu.leave_title": "Save before leaving?",
    "menu.leave_dirty": (
        "This job has changes that have not been saved to a JSON file."
    ),
    "menu.leave_save": "Save and leave",
    "menu.leave_discard": "Leave without saving",
    "menu.leave_cancel": "Cancel",

    # -- edit job configurations -----------------------------------------
    "menu.builder_title": "EDIT JOB CONFIGURATIONS",
    "menu.current_settings": "Current name: %s",
    "menu.current_version": "Version: %s",
    "menu.current_seeds": "Model seeds: %s",
    "menu.config_actions": (
        "1. Job name\n"
        "2. Model seeds\n"
        "3. JSON version"
    ),
    "menu.ask_name": "New name: ",
    "menu.ask_seeds": "Seeds (space- or comma-separated integers): ",
    "menu.ask_version": "JSON version to use: ",
    "menu.version_unsupported": "Unsupported JSON version — choose one of %s.",

    # -- the configuration-status view (defaults + what is still required) --
    "menu.status_title": "Configuration status",
    "menu.status_line": "  %-14s %s",
    "menu.status_name": "Name",
    "menu.status_seeds": "Model seeds",
    "menu.status_version": "JSON version",
    "menu.status_components": "Entities",
    "menu.status_modifications": "Modifications",
    "menu.status_msa": "MSA",
    "menu.status_templates": "Templates",
    "menu.status_other": "Other",
    "menu.status_ok": "OK",
    "menu.status_missing": "MISSING",
    "menu.status_invalid": "INVALID",
    "menu.status_absent": "-",
    "menu.status_automatic": "(automatic)",
    "menu.status_provided": "(you provided this)",
    "menu.status_none": "none",
    "menu.status_ready": "  STATUS: READY",
    "menu.status_incomplete": "  STATUS: INCOMPLETE",
    "menu.version_unverified": "not set",
    "menu.version_pinned": "v%d",
    "menu.version_auto": "auto",

    # -- add entity ------------------------------------------------------
    "menu.add_entity_title": "ADD ENTITY",
    "menu.family_protein": "Protein",
    "menu.family_rna": "RNA",
    "menu.family_dna": "DNA",
    "menu.family_ligand": "Ligand",
    "menu.add_protein_prompt": "Protein sequence: ",
    "menu.add_rna_prompt": "RNA sequence: ",
    "menu.add_dna_prompt": "DNA sequence: ",
    "menu.add_ligand_value_prompt": "Ligand value: ",
    "menu.ligand_kind_menu": "Is this ligand given as a CCD code or a SMILES string?",
    "menu.ligand_kind_ccd": "CCD code(s) — e.g. ATP, or several separated by spaces",
    "menu.ligand_kind_smiles": "SMILES string — e.g. C(C)O",
    "menu.quantity_menu": "How many copies?",
    "menu.quantity_custom": "Custom quantity",
    "menu.quantity_custom_prompt": "Quantity: ",
    "menu.quantity_bad_value": "Enter a whole number of copies, at least 1.",
    "menu.add_cancelled": "Cancelled — nothing was added.",
    "menu.entity_added": "Entity added.",
    "menu.ask_msa_yn": "Add an MSA for this record? [y/N]: ",
    "menu.ask_templates_yn": "Add structural templates? [y/N]: ",
    "menu.msa_skip": "Skipped — edit the entity to set it later.",
    "menu.msa_skip_edit": "Skipped — the alignment is unchanged.",
    "menu.templates_skip_edit": "Skipped — the templates are unchanged.",
    "menu.msa_mode_menu": "MSA mode:",
    "menu.msa_mode_auto": "Automatic (search)",
    "menu.msa_mode_unpaired": "Unpaired only",
    "menu.msa_mode_paired": "Paired only",
    "menu.msa_mode_both": "Both",
    "menu.msa_mode_free": "Free (no MSA)",
    "menu.msa_mode_provided": "Provided (paste or file)",
    "menu.msa_source_menu": "MSA source:",
    "menu.msa_paste_inline": "Paste inline text",
    "menu.msa_use_file": "Use a file",
    "menu.msa_inline_header": "Paste the MSA, finish with a blank line:",
    "menu.ask_msa_path": "Path to the MSA file: ",
    "menu.templates_menu": "Templates:",
    "menu.templates_search": "Search allowed",
    "menu.templates_none": "Explicitly none",
    "menu.templates_list": "Provide a list",
    "menu.ask_ref_path": "Path to the template structure file: ",
    "menu.ask_ref_pairs": "Index pairs (query:template, comma-separated, 0-based; blank = none): ",

    # -- edit entity -----------------------------------------------------
    "menu.entity_editor_title": "EDIT ENTITY",
    "menu.entity_list_empty": "  (no entities)",
    "menu.no_entities_edit": "There are no entities to edit — add one first.",
    "menu.select_entity": "Select entity:",
    "menu.entity_action_title": "SELECTED ENTITY",
    "menu.selected_entity": "Entity: %s",
    "menu.entity_actions": "1. Edit\n2. Delete",
    "menu.entity_actions_polymer": (
        "1. Edit\n"
        "2. Delete\n"
        "3. Modifications"
    ),
    "menu.delete_confirm": "Delete \"%s\"?",
    "menu.delete_yes": "Yes, delete",
    "menu.delete_no": "No, go back",
    "menu.edit_sequence_prompt": "New sequence (blank keeps the current one): ",
    "menu.edit_desc_prompt": "New description (blank keeps the current one): ",
    "menu.removed": "Removed %r.",
    "menu.entity_list_header": "  %s  %s  %d residues",
    "menu.entity_list_ligand": "  %s  ligand  %s",
    "menu.entity_list_ligand_counted": "  %s  ligand  %s  x%d",
    "menu.entity_mod_row": "      %s at residue %s%s",
    "menu.ligand_by_code": "CCD %s",
    "menu.ligand_by_notation": "SMILES notation",

    # -- custom CCD management -------------------------------------------
    "menu.ccd_title": "CUSTOM CCD MANAGEMENT",
    "menu.ccd_actions": (
        "1. View the custom CCD definition\n"
        "2. Add a custom CCD definition\n"
        "3. Edit the custom CCD definition\n"
        "4. Remove the custom CCD definition"
    ),
    "menu.ccd_none": "No custom CCD definition is set for this job.",
    "menu.ccd_current": "Current custom CCD definition:",
    "menu.ccd_path": "File: %s",
    "menu.ccd_inline": "Inline CIF definition: %s",
    "menu.ccd_inline_lines": "Total lines: %d",
    "menu.ccd_source_menu": "How is the definition supplied?",
    "menu.ccd_set": "Custom CCD definition set.",
    "menu.ccd_removed": "Custom CCD definition removed.",
    "menu.ccd_confirm": "Remove the custom CCD definition?",
    "menu.paste_definition": "Paste the CIF definition, finish with a blank line:",
    "menu.ask_ccd_path": "Path to the CIF definition file: ",

    # -- PTM management --------------------------------------------------
    "menu.ptm_title": "PTM MANAGEMENT",
    "menu.ptm_actions": (
        "1. View modifications\n"
        "2. Add a modification\n"
        "3. Edit a modification\n"
        "4. Remove a modification"
    ),
    "menu.ptm_none": "No modifications are set on any entity yet.",
    "menu.ptm_record": "%s",
    "menu.mod_target_entity": "Which entity holds the modification:",
    "menu.no_modification_target": (
        "No protein, RNA, or DNA chain to modify yet — add one first "
        "(ligands carry no modifications)."
    ),
    "menu.ask_code": "Modification code (e.g. SEP): ",
    "menu.ask_position": "Position (1-based residue number): ",
    "menu.mod_cancelled": "Cancelled — nothing was added to this record.",
    "menu.modification_added": "Modification added.",
    "menu.modification_removed": "Modification removed.",
    "menu.ptm_updated": "Modification updated.",
    "menu.ptm_edit_code_prompt": "New modification code (blank keeps the current one): ",
    "menu.ptm_edit_position_prompt": "New position (blank keeps the current one): ",
    "menu.mod_remove_prompt": "Remove which modification?",
    "menu.no_mods_on_record": "This record carries no modifications.",
    "menu.mod_menu_title": "MODIFICATIONS ON THIS RECORD",
    "menu.mod_actions": (
        "1. Add a modification\n"
        "2. Edit a modification\n"
        "3. Remove a modification"
    ),

    # -- save and show summary -------------------------------------------
    "menu.summary_title": "JOB SUMMARY",
    "menu.summary_name": "Name: %s",
    "menu.summary_seeds": "Model seeds: %s",
    "menu.summary_version": "Version: %s",
    "menu.summary_entities": "Number of entities: %d",
    "menu.summary_breakdown": "Entity breakdown:",
    "menu.summary_protein": "- Proteins: %d",
    "menu.summary_dna": "- DNA:      %d",
    "menu.summary_rna": "- RNA:      %d",
    "menu.summary_ligand": "- Ligands:  %d",
    "menu.summary_other": "- Other supported types: %d",
    "menu.ask_save_path": "Save the JSON to (blank = %s): ",
    "menu.overwrite_confirm": "%s already exists. Overwrite it?",
    "menu.overwrite_yes": "Yes, overwrite",
    "menu.overwrite_no": "No, cancel",
    "menu.save_cancelled": "Cancelled — nothing was written.",
    "menu.save_job_blocked": "This job cannot be saved yet:",
    "menu.save_job_wrote": "Saved to %s",
    "menu.export_skipped": "Skipped (exists): %s",
    "menu.export_conflict": "Conflict: %s",
    "menu.card_line": "%d. %s — %s",
    "menu.finding_indent": "    ",

    # -- open a JSON file ------------------------------------------------
    "menu.ask_import_path": "AF3 JSON file to open: ",
    "menu.import_file_line": "File: %s",
    "menu.import_entities": "Entities: %d",
    "menu.job_family_header": "%s:",
    "menu.preview_seeds": "Seeds: %s",
    "menu.import_notes": "Fields this builder does not support for editing:",
    "menu.import_note_line": "  ! %s",
    "menu.import_confirm": "Open this JSON as the current job?",
    "menu.import_yes": "Open",
    "menu.import_no": "Cancel",
    "menu.import_failed": "Could not open this JSON.",
    "menu.import_reason": "Reason: %s",
    "menu.import_untouched": "The original file has not been modified.",
    "menu.import_loaded": "JSON opened. It is now a normal, editable job.",

    # -- file picking ----------------------------------------------------
    "menu.files_in": "Files in %s:",
    "menu.pick_hint": "Type a number to open or choose, a full path, or '..' to go up. 0 cancels.",
    "menu.pick_cannot_list": "Cannot list this directory.",

    # -- variants --------------------------------------------------------
    "menu.variant_title": "VARIANT MANAGEMENT",
    "menu.variant_base_job": "Base job: %s",
    "menu.variant_base_entities": "Base entities: %d",
    "menu.variant_current": "Current variant: %s",
    "menu.variant_actions": (
        "1. Set variant job name\n"
        "2. Add entity\n"
        "3. Edit entity\n"
        "4. Save variant and reset to base"
    ),
    "menu.variant_name_prompt": "Variant job name (blank keeps the current one): ",
    "menu.variant_named": "Variant job name set to %s.",
    "menu.ask_variant_path": "Save the variant JSON to (blank = %s): ",
    "menu.variant_saved": "Variant saved to %s",
    "menu.variant_reset": "Reset to the base job.",
}


def text(key: str) -> str:
    """The registered wording for ``key``. Unknown keys raise: a missing
    entry is a programming error, never a silent fallback (the same
    discipline the traceability registry applies to labels)."""
    try:
        return STRINGS[key]
    except KeyError:
        raise KeyError(
            "no string registered for %r; add it to ui/present/strings.py" % key
        )
