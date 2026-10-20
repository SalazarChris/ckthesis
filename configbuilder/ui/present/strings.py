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

__all__ = ["STRINGS", "blocking_verdict", "text"]


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
        "5. Post-translational modification management\n"
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
    "menu.seeds_method_title": "How do you want to set the model seeds?",
    "menu.seeds_method_menu": "Choose a method:",
    "menu.seeds_method_specific": "Enter specific seed values",
    "menu.seeds_method_generate": "Generate a number of seeds automatically",
    "menu.ask_seed_count": "How many model seeds do you want? ",
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
    "menu.add_dna_prompt": "DNA sequence (5' to 3'): ",
    "menu.dna_complement_question": "Do you want to add the complementary reverse-complement DNA strand?",
    "menu.dna_complement_menu": "Choose:",
    "menu.dna_complement_yes": "Yes - add the complementary strand (double-stranded DNA)",
    "menu.dna_complement_no": "No - use only the supplied strand (single-stranded DNA)",
    "menu.dna_complement_will_add": "The complementary strand will be added.",
    "menu.dna_complement_will_not_add": "Only the supplied strand will be used.",
    "menu.add_ligand_value_prompt": "Ligand value: ",
    "menu.ligand_kind_menu": "Is this ligand given as a CCD code or a SMILES string?",
    "menu.ligand_kind_ccd": "CCD code(s) — e.g. ATP, or several separated by spaces",
    "menu.ligand_kind_smiles": "SMILES string — e.g. C(C)O",
    "menu.quantity_direct_prompt": "How many copies of this ligand do you want? ",
    "menu.quantity_bad_value": "Enter a whole number of copies, at least 1.",
    "menu.add_cancelled": "Cancelled — nothing was added.",
    "menu.entity_added": "Entity added.",
    "menu.ask_msa_yn": "Use a multiple sequence alignment (MSA) for this record? [y/N]: ",
    "menu.ask_templates_yn": "Use structural templates for this record? [y/N]: ",
    "menu.msa_skip": "No MSA will be used - edit the entity to change this later.",
    "menu.msa_skip_edit": "No change - the alignment setting is unchanged.",
    "menu.templates_skip_edit": "No change - the template setting is unchanged.",
    "menu.msa_mode_menu": "MSA mode:",
    "menu.msa_mode_auto": "Let AlphaFold search for MSAs automatically",
    "menu.msa_mode_unpaired": "Unpaired only",
    "menu.msa_mode_paired": "Paired only",
    "menu.msa_mode_both": "Both",
    "menu.msa_mode_free": "No MSA - proceed without alignment data",
    "menu.msa_mode_provided": "Provided (paste or file)",
    "menu.msa_source_menu": "MSA source:",
    "menu.msa_paste_inline": "Paste inline text",
    "menu.msa_use_file": "Use a file",
    "menu.msa_inline_header": "Paste the MSA, finish with a blank line:",
    "menu.ask_msa_path": "Path to the MSA file: ",
    "menu.templates_menu": "Templates:",
    "menu.templates_search": "Let AlphaFold search for templates",
    "menu.templates_none": "No templates - proceed without template structures",
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
    "menu.ptm_title": "POST-TRANSLATIONAL MODIFICATION MANAGEMENT",
    "menu.ptm_actions": (
        "1. View modifications\n"
        "2. Add a modification\n"
        "3. Edit a modification\n"
        "4. Remove a modification"
    ),
    "menu.ptm_none": "No post-translational modifications are set on any entity yet.",
    "menu.ptm_record": "%s",
    "menu.mod_target_entity": "Which entity holds the post-translational modification:",
    "menu.no_modification_target": (
        "No protein, RNA, or DNA chain to modify yet — add one first "
        "(ligands carry no post-translational modifications)."
    ),
    "menu.ask_code": "Post-translational modification code (e.g. SEP): ",
    "menu.ask_position": "Position (1-based residue number): ",
    "menu.mod_cancelled": "Cancelled — nothing was added to this record.",
    "menu.modification_added": "Post-translational modification added.",
    "menu.modification_removed": "Post-translational modification removed.",
    "menu.ptm_updated": "Post-translational modification updated.",
    "menu.ptm_edit_code_prompt": "New modification code (blank keeps the current one): ",
    "menu.ptm_edit_position_prompt": "New position (blank keeps the current one): ",
    "menu.mod_remove_prompt": "Remove which post-translational modification?",
    "menu.no_mods_on_record": "This record carries no post-translational modifications.",
    "menu.mod_menu_title": "POST-TRANSLATIONAL MODIFICATIONS ON THIS RECORD",
    "menu.mod_actions": (
        "1. Add a post-translational modification\n"
        "2. Edit a post-translational modification\n"
        "3. Remove a post-translational modification"
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
    "menu.unknown_error": "unknown error",
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
    "menu.variant_title": "VARIANT GENERATION",
    "menu.variant_description": "Create alternative JSON configurations from this base job. You can make changes manually or supply an input file to generate multiple variants automatically.",
    "menu.variant_base_job": "Base job: %s",
    "menu.variant_base_entities": "Base entities: %d",
    "menu.variant_base_info": "Each variant starts from this base and can be edited independently.",
    "menu.variant_current": "Current variant: %s",
    "menu.variant_actions": (
        "1. Set variant job name\n"
        "2. Add entity\n"
        "3. Edit entity\n"
        "4. Save variant and reset to base\n"
        "5. Generate variants from file\n"
        "6. View all variants"
    ),
    "menu.variant_file_menu": "Choose file type for batch generation:",
    "menu.variant_file_protein": "Protein sequences (FASTA-like .txt file)",
    "menu.variant_file_dna": "DNA sequences (.txt file)",
    "menu.variant_file_ligand": "Ligand SMILES (.smiles or .txt file)",
    "menu.variant_choose_file": "Select input file:",
    "menu.variant_batch_success": "Successfully generated %d variants from %s.",
    "menu.variant_batch_failed": "Batch generation failed: %s",
    "menu.variant_batch_generating": "Generating variants...",
    "menu.variant_batch_no_variants": "No variants were generated.",
    "menu.variant_batch_info": "%d variants are now available in the variant list.",
    "menu.variant_list_title": "ALL VARIANTS",
    "menu.variant_list_empty": "No variants have been created yet.",
    "menu.variant_list_entry": "%d. %s (%s)",
    "menu.variant_list_back": "0. Back to variant generation",
    "menu.variant_preview_title": "Variant: %s",
    "menu.variant_preview_key": "Key: %s",
    "menu.variant_preview_edits": "Edits:",
    "menu.variant_name_prompt": "Variant job name (blank keeps the current one): ",
    "menu.variant_named": "Variant job name set to %s.",
    "menu.ask_variant_path": "Save the variant JSON to (blank = %s): ",
    "menu.variant_saved": "Variant saved to %s",
    "menu.variant_reset": "Reset to the base job.",

    # -- the Qt desktop front end (Stage 1: review & preview) -------------
    # The desktop shell's own chrome. Domain wording is never repeated
    # here: family, status, version, MSA/template and import wording all
    # come from the entries above, so the two front ends cannot drift.
    "gui.window_title": "AF3 JSON Builder",
    "gui.window_title_job": "%s - AF3 JSON Builder",
    "gui.window_title_dirty": "%s* - AF3 JSON Builder",
    "gui.tab_overview": "Overview",
    "gui.tab_entities": "Entities",
    "gui.action_open": "Open AF3 JSON…",
    "gui.section_job": "Job details",
    "gui.readiness_ok": "Ready — nothing blocks generation.",
    "gui.readiness_blocked": "Not ready: %d blocking findings.",
    "gui.readiness_blocked_one": "Not ready: 1 blocking finding.",
    "gui.readiness_ready": "Ready",
    "gui.readiness_attention": "Needs attention",
    "gui.findings_detail": "Technical detail: %s",
    "gui.col_number": "#",
    "gui.col_severity": "Severity",
    "gui.col_where": "Where",
    "gui.col_message": "Message",
    "gui.col_ids": "Entity ID(s)",
    "gui.col_family": "Family",
    "gui.col_summary": "Length / representation",
    "gui.col_description": "Description",
    "gui.dialect_label": "Dialect",
    "gui.counts_value": "Protein %d · RNA %d · DNA %d · Ligand %d",
    "gui.notice_no_job": (
        "Create a job or open an AF3 JSON to begin. Nothing leaves this computer."
    ),
    "gui.notice_job": (
        "Edits stay in memory until you save JSON or generate output. Nothing "
        "is uploaded."
    ),
    "gui.notice_dirty": (
        "Unsaved changes - save JSON or generate output to write them."
    ),
    "gui.source_file": "Source file: %s",
    "gui.source_none": "No file open.",
    "gui.demo_notice": "Sample data (demo mode) — no file is open and nothing is written.",
    "gui.open_dialog_title": "Open an AF3 JSON file",
    "gui.file_filter": "AF3 JSON files (*.json);;All files (*)",
    "gui.import_title": "Review the file before opening it",
    "gui.import_summary_title": "What this file contains",
    "gui.import_ids": "Entity IDs: %s",
    "gui.import_accept": "Import",
    "gui.entities_none": "This job has no entities.",
    "gui.entity_hint": (
        "Select an entity to see its details and its own settings beside the "
        "list. Add, edit or remove a record with the buttons above."
    ),
    "gui.entity_selector": "Entity",
    "gui.entity_selector_empty": "No entities yet",
    "gui.entity_choice_sequence": "%s · %s · %d residues",
    "gui.entity_choice_ligand": "%s · %s · %s",
    "gui.entity_tab_settings": "Entity settings",
    "gui.entity_tab_ccd": "Custom CCDs",
    "gui.entity_tab_bonds": "Covalent bonds",
    "gui.entity_job_wide": (
        "This applies to the whole job, not to one selected entity."
    ),
    "gui.entity_length": "Length",
    "gui.entity_length_value": "%d residues",
    "gui.entity_representation": "Representation",
    "gui.entity_partner": "Reverse-complement partner: %s",
    "gui.entity_no_partner": "No partner strand accompanies this DNA strand.",
    "gui.entity_modification_row": "%s at %d",
    "gui.templates_provided": "%d provided",
    "gui.preview_title": "Generated JSON (read-only)",
    "gui.preview_note": "This is the builder's generated JSON for the open job. It is normalized, so its layout may differ from the file you opened.",
    "gui.preview_unavailable": "No JSON can be shown yet.",
    "gui.preview_refresh": "Refresh",
    "gui.entity_details": "Selected entity",
    "gui.entity_details_hint": (
        "A compact summary. Use Edit to change the sequence or representation; "
        "the settings below apply to this entity alone."
    ),
    "gui.entity_settings": "Settings for this entity",
    "gui.entity_ligand_no_settings": (
        "A ligand has no PTMs, MSA or templates. Edit its representation with "
        "the Edit button above."
    ),
    "gui.entity_partner_label": "Reverse-complement partner",
    "gui.menu_file": "File",
    "gui.action_quit": "Quit",
    "gui.value_unset": "not set",
    "gui.value_empty": "(empty)",
    "gui.representation_ccd": "CCD: %s",
    "gui.representation_smiles": "SMILES: %s",
    "gui.cli_description": "Open an AF3 JSON file in the desktop builder window.",
    "gui.cli_help_path": "An AF3 JSON file to review; the window still asks you to confirm it.",
    "gui.cli_help_demo": "Start with built-in sample data instead of a file; nothing is written.",

    # -- the Qt desktop front end (Stage 2: the job lifecycle) ------------
    # New Job / Save JSON / the job-settings panel and their questions.
    # Saving reuses the console's own save, overwrite and cancellation
    # wording above, so both front ends say the same thing.
    "gui.action_new_job": "New Job…",
    "gui.action_save": "Save JSON…",
    "gui.section_settings": "Job settings",
    "gui.settings_apply": "Apply",
    "gui.settings_default": "Application default",
    "gui.settings_custom": "Changed — not the default",
    "gui.settings_name_applied": "Job name updated to %s.",
    "gui.settings_seeds_applied": "Model seeds updated.",
    "gui.settings_version_applied": "JSON version pinned to %d.",
    "gui.save_dialog_title": "Save the job as an AF3 JSON file",
    "gui.overwrite_title": "Replace an existing file",
    "gui.discard_title": "Unsaved changes",
    "gui.discard_question": "This job has unsaved changes. Discard them?",
    "gui.discard_accept": "Discard changes",
    "gui.discard_cancel": "Keep the job",
    "gui.problem_title": "The action could not be completed",

    # -- the Qt desktop front end (Stage 3: entity management) ------------
    # Add/edit/delete actions, their forms and their questions. Family,
    # sequence-alphabet and representation rules stay in the services; the
    # wording below explains, it never decides.
    "gui.action_add_protein": "Add Protein",
    "gui.action_add_rna": "Add RNA",
    "gui.action_add_dna": "Add DNA",
    "gui.action_add_ligand": "Add Ligand",
    "gui.action_edit_record": "Edit entity",
    "gui.action_delete_record": "Delete entity",
    "gui.dialog_add_protein": "Add a protein",
    "gui.dialog_add_rna": "Add an RNA chain",
    "gui.dialog_add_dna": "Add a DNA duplex",
    "gui.dialog_add_ligand": "Add a ligand",
    "gui.dialog_edit_protein": "Edit the selected protein",
    "gui.dialog_edit_rna": "Edit the selected RNA chain",
    "gui.dialog_edit_dna": "Edit the selected DNA strand",
    "gui.dialog_edit_ligand": "Edit the selected ligand",
    "gui.form_sequence": "Sequence",
    "gui.form_description": "Description (optional)",
    "gui.form_add": "Add",
    "gui.form_save": "Apply changes",
    "gui.form_cancel": "Cancel",
    "gui.sequence_add_hint": "Paste is fine; the sequence must contain only this family's letters — no FASTA header and no line breaks.",
    "gui.sequence_edit_hint": "The sequence is changed through the builder's own update operation; the record's other settings are preserved. Paste a plain sequence — no FASTA header and no line breaks.",
    "gui.dna_add_hint": "The sequence you enter becomes one strand; the builder also creates its reverse-complement partner, with its own identifier.",
    "gui.dna_edit_hint": "This strand belongs to a DNA duplex: changing its sequence updates its reverse-complement partner through the builder.",
    "gui.ligand_kind": "Representation",
    "gui.ligand_ccd_option": "CCD code(s)",
    "gui.ligand_smiles_option": "SMILES",
    "gui.ligand_value": "Codes or SMILES",
    "gui.ligand_copies": "Copies",
    "gui.ligand_copies_fixed": "The copy count is set when the ligand is created and cannot be changed afterwards.",
    "gui.ligand_form_hint": "An ion is a ligand represented by its CCD code (for example ZN).",
    "gui.description_version_warning": "This job is pinned to JSON version %d; per-entity descriptions are written from version %d. The description is kept, not discarded — raise the job's JSON version to include it.",
    "gui.delete_title": "Delete entity",
    "gui.delete_single": "Remove entity %s from the job?",
    "gui.delete_duplex": "Entity %s is one strand of a DNA duplex; removing it removes its partner %s as well.",
    "gui.delete_copies": "Entity %s is a multi-copy ligand with %d identifiers; removing it removes all of them.",
    "gui.delete_accept": "Delete",

    # -- the Qt desktop front end (Stage 4: advanced entity settings) -----
    # Modifications, alignment/MSA, templates, the job-level custom CCD
    # definition and covalent bonds. Mode words stay the service's own
    # ('automatic', 'free', ...); only the labels and explanations live here,
    # and the explanations describe the model, they never decide.
    "gui.adv_no_selection": (
        "Select an entity in the table above to edit its modifications, MSA "
        "and templates."
    ),
    "gui.adv_selected": "Selected entity: %s",
    "gui.adv_scope_entity": "This entity",
    "gui.adv_scope_job": "Whole job (all entities)",
    "gui.adv_scope_job_hint": (
        "A custom CCD definition and covalent bonds belong to the job, not to "
        "the selected entity; they apply to the generated file as a whole."
    ),

    "gui.section_modifications": "Modifications / PTMs",
    "gui.mod_columns": "Code · Position (1-based) · Residue",
    "gui.mod_note": "Modification positions are 1-based residue numbers counted from the chain's first residue.",
    "gui.mod_needs_polymer": "A ligand carries no modifications; select a protein, RNA or DNA chain.",
    "gui.mod_none": "No modifications on this entity.",
    "gui.mod_add": "Add…",
    "gui.mod_edit": "Edit…",
    "gui.mod_remove": "Remove…",
    "gui.mod_dialog_add": "Add a modification to entity %s",
    "gui.mod_dialog_edit": "Edit the selected modification on entity %s",
    "gui.mod_form_code": "Modification code",
    "gui.mod_form_position": "Position (1-based)",
    "gui.mod_col_residue": "Residue",
    "gui.mod_code_placeholder": "e.g. SEP",
    "gui.mod_residue_echo": "Residue at that position: %s",
    "gui.mod_residue_out_of_range": "Position %d is past the end of this chain (%d residues).",
    "gui.mod_delete_title": "Remove a modification",
    "gui.mod_delete_question": "Remove %s at residue %d from entity %s?",
    "gui.mod_select_first": "Select a modification in the list first.",

    "gui.section_alignment": "Alignment / MSA",
    "gui.alignment_current": "Current alignment: %s",
    "gui.alignment_button": "Change alignment…",
    "gui.alignment_dialog": "Alignment for entity %s",
    "gui.alignment_mode": "Mode",
    "gui.alignment_source": "Alignment source",
    "gui.alignment_inline": "Alignment text",
    "gui.alignment_path": "Alignment file",
    "gui.alignment_browse": "Choose file…",
    "gui.alignment_file_dialog": "Choose an alignment file",
    "gui.alignment_hint": "Choose how this chain's alignment is supplied.",
    "gui.alignment_hint_automatic": "AlphaFold searches for the alignment itself; the job stores none.",
    "gui.alignment_hint_free": "No alignment data: this chain is folded without one.",
    "gui.alignment_hint_source": "The alignment comes from what you provide here — paste text or choose a file, not both.",
    "gui.alignment_path_version": "An external alignment file is written as a path field, which needs input version %d or later.",
    "gui.alignment_state_automatic": "automatic (AlphaFold searches)",
    "gui.alignment_state_free": "no alignment",
    "gui.alignment_state_provided": "provided (%s)",
    "gui.alignment_source_inline": "inline text",
    "gui.alignment_source_file": "external file",
    "gui.alignment_not_applicable": "A %s entity has no alignment setting.",
    "gui.alignment_applied": "Alignment updated.",

    "gui.section_templates": "Templates",
    "gui.templates_current": "Current templates: %s",
    "gui.templates_button": "Edit templates…",
    "gui.templates_dialog": "Templates for entity %s",
    "gui.templates_mode": "Templates",
    "gui.templates_col_file": "mmCIF file",
    "gui.templates_col_pairs": "Index pairs (query:template, 0-based)",
    "gui.templates_pairs_note": "Index pairs map query residues to template residues and are 0-based; leave a cell blank for none.",
    "gui.templates_add_file": "Add file…",
    "gui.templates_remove_file": "Remove file…",
    "gui.templates_file_dialog": "Choose a template structure file",
    "gui.templates_file_filter": "mmCIF files (*.cif *.mmcif);;All files (*)",
    "gui.templates_hint_search": "AlphaFold searches for templates itself.",
    "gui.templates_hint_none": "No templates: AlphaFold will not search for any.",
    "gui.templates_hint_list": "One row per template file; pairs are query:template, 0-based.",
    "gui.templates_path_version": "An external template file is written as a path field, which needs input version %d or later.",
    "gui.templates_state_search": "search allowed (AlphaFold finds them)",
    "gui.templates_state_none": "none (explicitly template-free)",
    "gui.templates_not_applicable": "Only a protein can carry templates.",
    "gui.templates_applied": "Templates updated.",

    "gui.section_ccd": "Custom CCD definition",
    "gui.ccd_note": "One custom component definition applies to the whole job: paste CIF text, or point at a CIF file — never both.",
    "gui.ccd_option_none": "No custom definition",
    "gui.ccd_option_inline": "Paste a CIF definition",
    "gui.ccd_option_file": "Load from a CIF file",
    "gui.ccd_inline_label": "CIF definition text",
    "gui.ccd_path_label": "CIF definition file",
    "gui.ccd_browse": "Choose file…",
    "gui.ccd_file_dialog": "Choose a CIF definition file",
    "gui.ccd_file_filter": "CIF files (*.cif *.mmcif);;All files (*)",
    "gui.ccd_apply": "Apply",
    "gui.ccd_clear": "Clear",
    "gui.ccd_active": "Active definition: %s",
    "gui.ccd_active_none": "none",
    "gui.ccd_active_inline": "inline CIF text (%d lines)",
    "gui.ccd_active_file": "external file %s",
    "gui.ccd_path_version": "An external definition is written as a path field, which needs input version %d or later.",
    "gui.ccd_applied": "Custom CCD definition updated.",
    "gui.ccd_cleared": "Custom CCD definition cleared.",

    "gui.section_bonds": "Covalent bonds",
    "gui.bond_note": "Each bond names two endpoints as an entity, a 1-based residue and an atom name.",
    "gui.bond_none": "No covalent bonds are defined.",
    "gui.bond_columns": "First endpoint · Second endpoint",
    "gui.bond_add": "Add bond…",
    "gui.bond_remove": "Remove bond…",
    "gui.bond_dialog": "Add a covalent bond",
    "gui.bond_endpoint_a": "First endpoint",
    "gui.bond_endpoint_b": "Second endpoint",
    "gui.bond_entity": "Entity",
    "gui.bond_residue": "Residue (1-based)",
    "gui.bond_atom": "Atom name",
    "gui.bond_columns_note": "Entity · Residue (1-based) · Atom name",
    "gui.bond_atom_placeholder": "e.g. SG",
    "gui.bond_endpoint_text": "%s, residue %d, atom %s",
    "gui.bond_pair_text": "%s  <->  %s",
    "gui.bond_added": "Covalent bond added.",
    "gui.bond_removed": "Covalent bond removed.",
    "gui.bond_delete_title": "Remove a covalent bond",
    "gui.bond_delete_question": "Remove the bond between %s and %s?",
    "gui.bond_select_first": "Select a bond in the list first.",
    "gui.bond_needs_entities": "Add entities before defining a bond.",

    # -- the Qt desktop front end (Stage 5: variants and batch) ------------
    "gui.tab_variants": "Variants",
    "gui.variants_title": "Variants",
    "gui.variants_base": "Base job: %s",
    "gui.variants_base_detail": "%d entities  ·  %d variants",
    "gui.variants_none": (
        "No variants yet. Use one of the three options above to create the first "
        "one."
    ),
    "gui.variants_intro": (
        "A variant is an alternative version of the base job. Choose one of the "
        "three ways to create variants below; the base job is never changed by a "
        "variant."
    ),
    "gui.variants_session_note": (
        "Variants belong to this session; saving the job writes the base AF3 JSON."
    ),
    "gui.variants_col_label": "Variant",
    "gui.variants_col_key": "ID",
    "gui.variants_col_changes": "Declared changes",
    "gui.variants_col_status": "Validation",
    "gui.variants_new": "Create a variant…",
    "gui.variants_add_change": "Add change…",
    "gui.variants_rename": "Rename…",
    "gui.variants_duplicate": "Duplicate…",
    "gui.variants_remove": "Remove…",
    "gui.variants_validate": "Validate all",
    "gui.variants_select_first": "Select a variant in the list first.",
    "gui.variants_no_selection": (
        "Select a variant to see its declared changes, findings and JSON."
    ),
    "gui.variants_list_group": "Existing variants",
    "gui.variants_list_hint": (
        "Select a variant to see it below; the buttons act on the selected one."
    ),
    "gui.variants_status_header": "Validation: %s",
    "gui.variants_details": "Selected variant",
    "gui.variants_tab_changes": "Changes",
    "gui.variants_tab_findings": "Findings",
    "gui.variants_tab_json": "JSON preview",
    "gui.variants_changes_none": (
        "This variant declares no changes yet. Add one with Add change…."
    ),
    "gui.variants_findings_none": "No findings for this variant.",
    "gui.variants_findings_base": (
        "The base job blocks variant validation. Fix its findings on the "
        "Overview tab first; the base findings are shown here."
    ),
    "gui.variants_findings_unavailable": "Validation could not run: %s",
    "gui.variants_json_unavailable": "No JSON can be shown yet.\nReason: %s",
    "gui.variants_status_ready": "Ready",
    "gui.variants_status_warnings": "Ready (%d warnings)",
    "gui.variants_status_blocked": "Blocked (%d)",
    "gui.variants_status_base_blocked": "Base blocked",
    "gui.variants_status_unavailable": "Not validated",
    "gui.variants_created": "Variant created.",
    "gui.variants_removed": "Variant removed.",
    "gui.variants_renamed": "Variant renamed.",
    "gui.variants_change_added": "Change added to the variant.",
    "gui.variants_duplicated": "Variant duplicated.",
    "gui.variants_validated": "Variants validated.",
    "gui.variants_remove_title": "Remove a variant",
    "gui.variants_remove_question": (
        "Remove variant \"%s\" (%s)? The base job is not changed."
    ),
    "gui.variants_duplicate_title": "Duplicate a variant",
    "gui.variants_duplicate_label": "Copy of %s",
    "gui.variants_name": "Variant name",
    "gui.variants_key": "Variant ID (unique, used in file names)",
    "gui.variants_key_hint": (
        "Letters, digits, hyphens and underscores; it must be unique among variants."
    ),

    "gui.variant_form_new_title": "New variant",
    "gui.variant_form_create": "Create variant",
    "gui.variant_form_change_title": "Add a change to variant %s",
    "gui.variant_form_add": "Add change",
    "gui.variant_form_rename_title": "Rename variant %s",
    "gui.variant_form_rename": "Rename",
    "gui.variant_form_duplicate_title": "Duplicate variant %s",
    "gui.variant_form_duplicate": "Duplicate",
    "gui.variant_change_kind": "What changes",
    "gui.variant_change_hint": (
        "Choose one change; only the fields it needs are shown."
    ),
    "gui.variant_kind_sequence": "Sequence change",
    "gui.variant_kind_add_modification": "Add a PTM / modification",
    "gui.variant_kind_remove_modification": "Remove a PTM / modification",
    "gui.variant_kind_alignment": "MSA / alignment",
    "gui.variant_kind_references": "Templates / references",
    "gui.variant_kind_job_name": "Job name",
    "gui.variant_kind_job_description": "Job description",
    "gui.variant_kind_seeds": "Model seeds",
    "gui.variant_kind_component_count": "Component copy count",
    "gui.variant_kind_add_entity": "Add a new entity",
    "gui.variant_kind_remove_entity": "Remove an entity",
    "gui.variant_hint_sequence": (
        "Replace one chain's sequence in this variant only."
    ),
    "gui.variant_hint_add_modification": (
        "Add a modification at a 1-based residue position on a polymer chain."
    ),
    "gui.variant_hint_remove_modification": (
        "Remove an existing modification from this variant's expanded chain."
    ),
    "gui.variant_hint_alignment": (
        "Change how one protein or RNA chain's alignment is supplied."
    ),
    "gui.variant_hint_references": (
        "Change a protein's template references in this variant only."
    ),
    "gui.variant_hint_job_name": "Give this variant's generated job another name.",
    "gui.variant_hint_job_description": "Set a job description in this variant only.",
    "gui.variant_hint_seeds": "Replace the model seeds in this variant only.",
    "gui.variant_hint_component_count": (
        "Change one component's copy count in this variant only."
    ),
    "gui.variant_hint_add_entity": (
        "Add a protein, RNA, DNA duplex or ligand to this variant."
    ),
    "gui.variant_hint_remove_entity": "Remove one entity from this variant.",
    "gui.variant_field_entity": "Entity",
    "gui.variant_field_sequence": "Sequence",
    "gui.variant_field_sequence_hint": (
        "Paste a plain sequence - no FASTA header and no line breaks."
    ),
    "gui.variant_field_code": "Modification code",
    "gui.variant_field_position": "Position (1-based residue number)",
    "gui.variant_field_residue": "Residue at that position: %s",
    "gui.variant_field_residue_out": (
        "Position %d is past the end of this chain (%d residues)."
    ),
    "gui.variant_field_mode": "Mode",
    "gui.variant_field_source": "Source",
    "gui.variant_field_inline": "Alignment text",
    "gui.variant_field_path": "Template file",
    "gui.variant_field_browse": "Choose file…",
    "gui.variant_field_route": "Templates",
    "gui.variant_field_description": "Description",
    "gui.variant_field_seeds": "Model seeds (comma or space separated)",
    "gui.variant_field_count": "Copy count",
    "gui.variant_field_family": "Family",
    "gui.variant_field_representation": "Representation",
    "gui.variant_field_representation_kind": "Kind",
    "gui.variant_field_remove_target": "Modification to remove",
    "gui.variant_field_no_records": "The base job has no entity of this kind.",
    "gui.variant_field_no_modifications": (
        "This variant has no modifications to remove."
    ),
    "gui.variant_route_search": "Let AlphaFold search",
    "gui.variant_route_none": "No templates",
    "gui.variant_route_list": "Explicit files",
    "gui.variant_add_file": "Add file…",
    "gui.variant_remove_file": "Remove file…",
    "gui.variant_pairs": "Index pairs (query:template, 0-based)",
    "gui.variant_no_source": "This mode takes no file or text.",
    "gui.variant_preview_change": "Proposed change: %s",
    "gui.variant_preview_pending": (
        "Fill in the fields to preview this change before committing it."
    ),
    "gui.variant_choose_entity": "Choose an entity first.",
    "gui.variant_choose_value": "Fill in the value this change needs.",
    "gui.variant_name_required": "Give the variant a name and a non-empty ID.",
    "gui.variant_seed_values": "Enter at least one whole-number seed.",

    "gui.variants_one_title": "Create one variant",
    "gui.variants_choose_title": "Create variants",
    "gui.variants_choose_intro": (
        "Choose one way to start. Only that workflow's options are shown, and "
        "nothing is created until you review and confirm it."
    ),
    "gui.variants_back": "< Back to choices",
    "gui.variants_one_hint": (
        "Make one alternative configuration from the base job by choosing a "
        "supported change: a sequence, a copy count, an added entity, and so on."
    ),
    "gui.variants_no_changes": "No changes yet",
    "gui.variant_change_sequence": "Sequence of %s: %s",
    "gui.variant_change_job_name": "Job name: %s",
    "gui.variant_change_job_description": "Job description: %s",
    "gui.variant_change_seeds": "Model seeds: %s",
    "gui.variant_change_add_mod": "Add %s at position %d on %s",
    "gui.variant_change_remove_mod": "Remove modification #%d from %s",
    "gui.variant_change_alignment": "Alignment of %s: %s",
    "gui.variant_change_references": "Templates of %s: %s",
    "gui.variant_change_count": "Copy count of %s: %d",
    "gui.variant_change_add_record": "Add %s %s",
    "gui.variant_change_remove_record": "Remove entity %s",
    "gui.variant_change_description": "Description of %s: %s",
    "gui.variant_change_representation": "Representation of %s: %s",
    "gui.variant_change_bond": "Covalent bond change on this job",
    "gui.variant_change_definition": "Custom CCD definition change",
    "gui.variant_change_version": "JSON version change",
    "gui.variant_change_unknown": "A change this workspace cannot describe",
    "gui.variant_reference_count": "%d file(s)",
    "gui.variant_value_empty": "(empty)",
    "gui.variant_value_unset": "not set",

    "gui.variants_series_title": "Create a quantity series",
    "gui.variants_series_hint": (
        "Plan copy counts for the selected components at increasing multipliers. "
        "Each level becomes its own variant; the base job is not changed."
    ),
    "gui.variants_series_components": "Components to vary",
    "gui.variants_series_start": "Start multiplier",
    "gui.variants_series_factor": "Factor per level",
    "gui.variants_series_levels": "Levels",
    "gui.variants_series_preview": "Preview series",
    "gui.variants_series_create": "Create series",
    "gui.variants_series_col_multiplier": "Level multiplier",
    "gui.variants_series_col_counts": "Copy counts",
    "gui.variants_series_planned": (
        "%d variants planned. Review them, then create the series."
    ),
    "gui.variants_series_names": (
        "Each level becomes one variant named from its multiplier "
        "(series_1x, series_2x, ...)."
    ),
    "gui.variants_series_select": "Select at least one component to vary.",
    "gui.variants_series_stale": (
        "The values changed since the preview. Preview the series again before "
        "creating it."
    ),
    "gui.variants_series_created": "%d series variants created.",
    "gui.variants_series_empty": "Plan a series to see its variants here.",

    "gui.variants_batch_title": "Create variants from a file",
    "gui.variants_batch_hint": (
        "One variant per entry, all built from the same base. Nothing is created "
        "until you confirm; one invalid entry refuses the whole batch."
    ),
    "gui.variants_batch_family": "Input type",
    "gui.variants_batch_family_note": (
        "Protein and DNA files: one sequence per line. Ligand files: one SMILES "
        "per line, optionally preceded by a name. RNA has no batch reader."
    ),
    "gui.variants_batch_path": "Batch file",
    "gui.variants_batch_browse": "Choose file…",
    "gui.variants_batch_file_filter": (
        "Batch files (*.txt *.smiles);;All files (*)"
    ),
    "gui.variants_batch_preview": "Preview file",
    "gui.variants_batch_create": "Create batch",
    "gui.variants_batch_preview_title": (
        "%d entries read, %d variants planned - nothing has been created yet."
    ),
    "gui.variants_batch_invalid": (
        "%d entries were read, but this file cannot be used as it stands - "
        "nothing has been created."
    ),
    "gui.variants_batch_preview_empty": (
        "Choose a file and preview it before creating the batch."
    ),
    "gui.variants_batch_col_entry": "Entry",
    "gui.variants_batch_no_normalization": (
        "File contents are used exactly as read; no headers or line breaks are "
        "stripped or added."
    ),
    "gui.variants_batch_created": "%d variants created from the file.",
    "gui.variants_batch_stale": (
        "The file or input type changed since the preview. Preview it again "
        "before creating the batch."
    ),
    "gui.variants_batch_empty": "The file contains no usable entries.",

    # -- Generate & Output (Stage 6) --------------------------------------
    "gui.tab_output": "Generate",
    "gui.output_title": "Generate output files",
    "gui.output_intro": (
        "Review the plan first - nothing is written until you confirm. Save "
        "JSON in the File menu writes one file; this page writes the planned "
        "project folder, any copied assets and the manifest."
    ),
    "gui.output_base": "Base job: %s - %d entities, %d variants",
    "gui.output_group_scope": "1. What do you want to generate?",
    "gui.output_group_destination": "2. Where should the files go?",
    "gui.output_step1_hint": (
        "Choose one scope. The plan lists exactly what that choice writes."
    ),
    "gui.output_destination": "Output folder",
    "gui.output_destination_placeholder": "Choose a folder for the generated files",
    "gui.output_destination_hint": (
        "The project folder is created inside this folder; the exact files are "
        "listed in the plan you review before generating."
    ),
    "gui.output_advanced": "Advanced options",
    "gui.output_advanced_hint": (
        "The defaults are safe: an existing file with different content stops the "
        "run and writes nothing, and external files are copied so the output still "
        "works elsewhere."
    ),
    "gui.output_write_hint": "Nothing is written until you confirm the plan.",
    "gui.output_browse": "Choose folder...",
    "gui.output_folder_dialog": "Choose the output folder",
    "gui.output_scope_all_title": "All variants",
    "gui.output_scope_all_note": (
        "The base file, one file per variant and the manifest."
    ),
    "gui.output_scope_selected_title": "Selected variant",
    "gui.output_scope_selected_note": "That variant's file and the manifest.",
    "gui.output_scope_base_title": "Base job only",
    "gui.output_scope_base_note": "One AF3 JSON file. No manifest.",
    "gui.output_scope_unavailable": (
        "Create a variant on the Variants page to choose this."
    ),
    "gui.output_variant": "Which variant",
    "gui.output_overwrite_policy": "If a file already exists",
    "gui.output_path_policy": "External files (MSA, templates)",
    "gui.policy_overwrite_fail": "Stop and write nothing",
    "gui.policy_overwrite_fail_hint": (
        "A file holding different content is a conflict: the plan refuses and "
        "nothing is written. The recommended default."
    ),
    "gui.policy_overwrite_skip": "Keep the existing file",
    "gui.policy_overwrite_skip_hint": (
        "Existing files are left untouched and reported as skipped; new files "
        "are still written."
    ),
    "gui.policy_overwrite_overwrite": "Replace the existing file",
    "gui.policy_overwrite_overwrite_hint": (
        "Existing files are replaced atomically with the newly generated bytes."
    ),
    "gui.policy_overwrite_versioned": "Write a numbered copy",
    "gui.policy_overwrite_versioned_hint": (
        "A free numbered file name is chosen and shown in the plan; nothing "
        "existing is replaced."
    ),
    "gui.policy_path_copy": "Copy into the output folder",
    "gui.policy_path_copy_hint": (
        "External files are copied under assets/ and the JSON points at the "
        "copy, so the output still works on another machine."
    ),
    "gui.policy_path_relative": "Make paths relative to the output",
    "gui.policy_path_relative_hint": (
        "The JSON keeps relative paths; the files themselves are not copied."
    ),
    "gui.policy_path_asgiven": "Use the paths exactly as entered",
    "gui.policy_path_asgiven_hint": (
        "Paths are emitted unchanged. Absolute Windows paths will not resolve "
        "on another machine."
    ),
    "gui.output_preview": "Preview plan",
    "gui.output_generate": "Generate files",
    "gui.output_copy_path": "Copy selected path",
    "gui.output_copied_path": "The selected path was copied.",
    "gui.output_group_plan": "3. Review the plan",
    "gui.output_group_generate": "4. Generate files",
    "gui.output_step3_hint": (
        "Previewing shows the files, copied assets, warnings and conflicts. "
        "Nothing is written by a preview."
    ),
    "gui.output_conflicts_blocking": (
        "Blocking - nothing is written while these remain."
    ),
    "gui.output_warnings_nonblocking": (
        "Non-blocking - generation can still proceed."
    ),
    "gui.output_plan_empty": (
        "Choose a folder and preview the plan. Nothing is written until you "
        "confirm."
    ),
    "gui.output_plan_ready": (
        "%d file(s) and %d copied file(s) planned, with %d warning(s) - "
        "nothing has been written yet."
    ),
    "gui.output_plan_invalidated": (
        "The job changed since this plan was previewed. Preview the plan again."
    ),
    "gui.output_plan_done": (
        "Generation finished - see the Result tab for what was written."
    ),
    "gui.output_tab_files": "Files",
    "gui.output_tab_assets": "Assets",
    "gui.output_tab_messages": "Warnings and findings",
    "gui.output_stale": (
        "The destination or an option changed. Preview the plan again before "
        "generating."
    ),
    "gui.output_need_plan": "Preview the plan before generating.",
    "gui.output_scope_needs_variant": "Choose a variant to generate.",
    "gui.output_no_folder": "Choose an output folder first.",
    "gui.output_plan_refused": "Nothing can be written: %s",
    "gui.output_col_kind": "Planned item",
    "gui.output_col_job": "Job",
    "gui.output_col_file": "File",
    "gui.output_col_action": "Action",
    "gui.output_col_field": "Used for",
    "gui.output_col_source": "Source",
    "gui.output_col_copy": "Copied to",
    "gui.output_col_emitted": "Path in JSON",
    "gui.output_kind_base": "Base job",
    "gui.output_kind_variant": "Variant",
    "gui.output_kind_manifest": "Manifest",
    "gui.output_manifest_note": (
        "The manifest (manifest.json) records the run; it is written last."
    ),
    "gui.output_action_create": "Create",
    "gui.output_action_overwrite": "Replace",
    "gui.output_action_skip": "Keep existing",
    "gui.output_action_conflict": "Conflict",
    "gui.output_group_warnings": "Warnings, conflicts and findings",
    "gui.output_conflicts": "Conflicts (%d)",
    "gui.output_warnings": "Warnings (%d)",
    "gui.output_no_warnings": "No warnings.",
    "gui.output_findings_note": (
        "These findings blocked generation. Select one to open its entity, or "
        "review the configuration."
    ),
    "gui.output_findings_variants": (
        "These variant findings blocked generation. Select one to open its "
        "entity, or review the configuration."
    ),
    "gui.output_review": "Review configuration",
    "gui.output_group_result": "Result",
    "gui.output_result_empty": "Nothing has been generated yet.",
    "gui.output_result_summary": (
        "Wrote %d file(s), skipped %d, copied %d file(s)."
    ),
    "gui.output_result_partial": "Generation stopped with an error: %s",
    "gui.output_result_errors": "Errors",
    "gui.output_written": "Written",
    "gui.output_skipped": "Skipped",
    "gui.output_copied": "Copied",
    "gui.output_confirm_title": "Generate files?",
    "gui.output_confirm_question": (
        "Write %d file(s) to:\n%s\n\nIf a file exists: %s\n"
        "External files: %s"
    ),
    "gui.output_confirm_accept": "Generate",
    "gui.output_plan_changed": (
        "The destination changed since this plan was reviewed, so the new plan "
        "is shown. Review it and generate again."
    ),

    # -- the mockup shell (sidebar, header, page titles) ------------------
    # The approved mockup's chrome. The five destination names reuse the
    # tab_* entries above, so the sidebar and the window speak one vocabulary.
    "gui.app_name": "AF3 Builder",
    "gui.app_subtitle": "Molecular input workspace",
    "gui.header_job": "Job: %s",
    "gui.header_no_job": "No job open",
    "gui.header_unsaved": "Unsaved",
    "gui.header_saved": "Saved",
    "gui.nav_section_workspace": "WORKSPACE",
    "gui.nav_section_file": "FILE",
    "gui.file_action_new": "New",
    "gui.file_action_open": "Open",
    "gui.file_action_save": "Save",
    "gui.breadcrumb_overview": "WORKSPACE / OVERVIEW",
    "gui.overview_title": "Prepare your AF3 job",
    "gui.overview_intro": (
        "Configure the input, check readiness and review what will be generated."
    ),
    "gui.field_job_name": "JOB NAME",
    "gui.field_seeds": "MODEL SEEDS",
    "gui.field_version": "JSON VERSION",
    "gui.stat_entities": "ENTITIES",
    "gui.stat_readiness": "READINESS",
    "gui.stat_entities_none": "No entities yet",
    "gui.stat_no_job": "No job open",
    "gui.family_protein": "protein",
    "gui.family_proteins": "proteins",
    "gui.family_rna": "RNA",
    "gui.family_dna": "DNA strand",
    "gui.family_dna_plural": "DNA strands",
    "gui.family_ligand": "ligand",
    "gui.family_ligands": "ligands",
    "gui.dialect_caption": "Dialect: %s",
    "gui.overview_next_entities": "Add at least one entity",
    "gui.overview_next_entities_detail": (
        "The current job cannot be generated without at least one entity."
    ),
    "gui.overview_next_findings": "Review the blocking issues",
    "gui.overview_next_findings_detail": (
        "Save and Generate explain what blocks the job when you attempt them."
    ),
    "gui.overview_next_generate": "Review the output plan",
    "gui.overview_next_generate_detail": (
        "Nothing blocks generation - review the planned files and write them."
    ),
    "gui.overview_next_nojob_detail": (
        "Create a job or open an AF3 JSON file to begin."
    ),
    "gui.overview_go_entities": "Manage entities",
    "gui.overview_go_generate": "Open Generate",
    "gui.overview_validate": "Validate job",
    "gui.validate_ok": "Validation passed: no findings.",
    "gui.validate_findings": (
        "Validation found %d blocking issues; save and generate are blocked."
    ),
    "gui.overview_no_job": (
        "No job is open. Use New or Open in the FILE footer to begin."
    ),
    "gui.entity_summary_manage": "Manage entities",
    "gui.entity_summary_hint": (
        "Open the entity workspace to add, edit or remove entities."
    ),
    "gui.blocked_header": "%d blocking issues stop this action; nothing was written:",
    "gui.blocked_header_one": "1 blocking issue stops this action; nothing was written:",
    "gui.blocked_line": "• %s",
    "gui.blocked_fix": "  %s",
    "gui.blocked_more": "…and %d more.",
    "gui.preview_copy": "Copy JSON",
    "gui.preview_copied": "The JSON was copied to the clipboard.",
    "gui.preview_title_note": "Read-only",
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


def blocking_verdict(count: int) -> str:
    """The readiness verdict for ``count`` blocking findings.

    One place decides the singular/plural wording, so the card, the status
    line and the tests cannot drift into "1 blocking finding(s)".
    """
    if count == 1:
        return text("gui.readiness_blocked_one")
    return text("gui.readiness_blocked") % count
