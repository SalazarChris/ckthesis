"""The front end's string registry (plan §18.7, §18.8; CHECKLIST 11a).

Every user-visible *chrome* string — action wording, fixed notices — is
data here, keyed, unique, and non-empty. Domain labels are
NOT here: they resolve through the model's traceability registry (plan
§3), and finding wording comes from the rule messages. The meta-test
asserts the split: any user-visible string in ``ui`` is either a
registry label, a rule message, or a member of this registry.

The registry is the meta-test's oracle in both directions: a string
used by ``ui`` that is missing from here (and from the two domain
sources) fails the suite, and an entry nothing uses is dead vocabulary
and fails too.
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
    "action.save_project": "save project",
    "action.quit": "quit",
    # Fixed notices
    "sequence.empty": "(empty sequence)",
    # Fallback grouping context for findings whose rule emitted no
    # locator (plan §16.6 still needs a group header).
    "finding.context.general": "General",
    # Console wording.
    "console.eof": "input stream closed",
    # The findings list's numbering template (shared by every screen).
    "jump.reference": "%d. %s — %s",
    # -- the free-navigation menu (the interactive builder) ------------
    "menu.select_prompt": "Select: ",
    "menu.banner_title": "ConfigBuilder",
    "menu.back": "0)  Back",
    "menu.exit": "0)  Exit",
    "menu.invalid": "Not a valid choice: %r",
    "menu.interrupted": "Interrupted — returning to the menu.",
    "menu.current": "Current job: %s",
    "menu.variants": "Variants: %d",
    "menu.work_held": "Working copy: kept automatically — re-open it any time with Open saved work",
    "menu.base_entities": "Base entities: %d",
    "menu.current_settings": "Current name: %s",
    "menu.current_version": "Version: %s",
    "menu.current_seeds": "Model seeds: %s",
    "menu.ask_name": "New name: ",
    "menu.ask_version": "AF3 version to pin: ",
    "menu.ask_seeds": "Seeds (space- or comma-separated integers): ",
    "menu.ask_count": "How many seeds to generate: ",
    "menu.seeds_generated": "Generated seeds: %s",
    "menu.ask_confirm": "Confirm? [y/N]: ",
    "menu.not_applied": "Not applied: %s",
    "menu.applied": "Applied.",
    "menu.no_project": "No project is open.",
    "menu.ok": "  OK  %s",
    "menu.warn": "  WARN %s",
    "menu.fail": "  FAIL %s",
    "menu.export_dir": "Output directory: %s",
    "menu.generate_title": "Generate JSON",
    "menu.generate_actions": (
        "  1) Generate this job's JSON\n"
        "  2) Generate all variant JSONs\n"
        "  3) Select variant JSONs to generate\n"
        "  4) Change the output directory"
    ),
    "menu.generate_actions_base": (
        "  1) Generate this job's JSON\n"
        "  2) Change the output directory"
    ),
    "menu.export_select_title": "Select variants to export",
    "menu.export_select_hint": "Type the numbers to export (e.g. 1 3), or 0 to cancel.",
    "menu.entity_editor_title": "Edit Entity",
    "menu.entities_title": "Entities",
    "menu.entity_menu_actions": (
        "  1) Add an entity\n"
        "  2) Edit an entity\n"
        "  3) Delete an entity"
    ),
    "menu.entity_no_fields": (
        "A ligand has no sequence, alignment, or templates; change it by "
        "deleting it and adding it again."
    ),
    "menu.choose_family": "Which kind of entity?",
    "menu.link_first_entity": "First record of the pair:",
    "menu.link_second_entity": "Second record of the pair:",
    "menu.mod_target_entity": "Which entity carries the modification:",
    "menu.export_written": "Wrote %s",
    "menu.export_conflict": "Conflict: %s",
    "menu.export_none": "No variants are defined yet.",
    "menu.export_dir_changed": "Output directory set to %s",
    "menu.preview_header": "Preview",
    "menu.preview_entities": "Entities:",
    "menu.preview_output": "Output: %s",
    "menu.preview_name": "Name: %s",
    "menu.preview_seeds": "Seeds: %s",
    "menu.json_error": "Cannot build JSON: %s",
    "menu.specs_header": "Variants:",
    "menu.specs_none": "No variants defined yet.",
    "menu.variant_actions": (
        "  1) Create a variant\n"
        "  2) Manage variants\n"
        "  3) Generate variants from a sequence file\n"
        "  4) Create a concentration/quantity series"
    ),
    "menu.series_component_menu": "Select the component to vary:",
    "menu.series_component_multiple": "Multiple components",
    "menu.series_start_prompt": "Starting multiplier: ",
    "menu.series_factor_prompt": "Multiplication factor: ",
    "menu.series_levels_prompt": "Number of levels: ",
    "menu.series_preview_title": "Concentration/Quantity Series Preview",
    "menu.series_preview_base": "Base:",
    "menu.series_preview_factor": "Factor: x%s    Levels: %s",
    "menu.series_preview_will": "Will create:",
    "menu.series_preview_row": "  %s: %s",
    "menu.series_preview_times": "x%s",
    "menu.series_confirm": "Create these variants?",
    "menu.count_component_prompt": "Select the component whose copy count changes:",
    "menu.count_value_prompt": "New copy count: ",
    "menu.series_yes": "Yes — create the series",
    "menu.series_no": "No / Cancel",
    "menu.series_created": "%d series variants created.",
    "menu.series_no_components": "No variable components (ligands/ions) in the current job.",
    "menu.series_bad_value": "Enter whole numbers (factor and levels at least 1, start at least 1).",
    "menu.manage_actions": (
        "  1) Edit variant\n"
        "  2) Duplicate variant\n"
        "  3) Delete variant\n"
        "  4) Preview variant\n"
        "  5) Generate JSON for variant"
    ),
    "menu.base_confirm": "Generate base JSON",
    "menu.base_generate": "Generate JSON",
    "menu.base_back": "Back",
    # -- variants: the entry screen's job picture and numbered flows -------
    "menu.job_family_header": "%s:",
    "menu.spec_entry": "  %d) %s — %s",
    "menu.spec_edits_line": "     %s",
    "menu.spec_add_record": "entity added",
    "menu.change_name": "job name → %s",
    "menu.change_description": "job description set",
    "menu.change_record_description": "record %s description set",
    "menu.change_seeds": "model seeds → %s",
    "menu.change_sequence": "sequence of %s",
    "menu.change_add_mod": "mod %s: %s @ %s",
    "menu.change_remove_mod": "modification #%d removed",
    "menu.change_alignment": "MSA of %s",
    "menu.change_references": "templates of %s",
    "menu.change_component_definition": "component definition set",
    "menu.change_format_target": "format target set",
    "menu.change_component_count": "Component %s copy count changed to x%s",
    "menu.change_component_representation": "ligand representation changed",
    "menu.change_remove_record": "entity %s removed",
    "menu.change_linkage": "linkage changed",
    "menu.change_generic": "%s",
    "menu.choice_line": "  %d) %s",
    "menu.select_entity": "Select entity:",
    "menu.delete_entity_title": "Select the entity to delete:",
    "menu.select_change": "What would you like to change?",
    "menu.entity_add_note": "Nothing to choose yet — add an entity first.",
    "menu.no_protein_target": "No protein chain to change — alignments and templates live on one.",
    "menu.name_menu": "Naming:",
    "menu.name_custom": "Enter a custom name",
    "menu.name_auto": "Generate name automatically",
    "menu.custom_name_prompt": "Variant name: ",
    "menu.delete_confirm": "Delete \"%s\"?",
    "menu.delete_yes": "Yes, delete",
    "menu.delete_no": "No, go back",
    "menu.preview_base_line": "Base job: %s",
    "menu.preview_change_line": "  %s",
    "menu.preview_changes": "Changes:",
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
    "menu.templates_menu": "Templates:",
    "menu.templates_search": "Search allowed",
    "menu.templates_none": "Explicitly none",
    "menu.templates_list": "Provide a list",
    "menu.template_path_prompt": "Path to the template structure file: ",
    "menu.template_pairs_prompt": "Index pairs (query:template, comma-separated, 0-based; blank = none): ",
    "menu.mod_code_prompt": "Modification code (CCD, e.g. SEP): ",
    "menu.mod_remove_prompt": "Remove which modification?",
    "menu.no_modifications": "This variant has no modification edits to remove.",
    "menu.new_name_prompt": "New job name: ",
    "menu.new_desc_prompt": "New job description: ",
    "menu.seeds_prompt": "Seeds (e.g. 1 2 3 4): ",
    "menu.add_entity_family": "Which entity type?",
    "menu.entity_seq_prompt": "%s sequence: ",
    "menu.ligand_value_prompt": "Ligand value (CCD code(s) or SMILES): ",
    "menu.ligand_kind_menu": "Is this ligand given as a CCD code or a SMILES string?",
    "menu.ligand_kind_ccd": "CCD code(s) — e.g. ATP, or several separated by spaces",
    "menu.ligand_kind_smiles": "SMILES string — e.g. C(C)O",
    "menu.family_protein": "Protein",
    "menu.family_rna": "RNA",
    "menu.family_dna": "DNA",
    "menu.family_ligand": "Ligand",
    "menu.batch_file_line": "File: %s",
    "menu.batch_detected": "Detected entries:",
    "menu.batch_entry_line": "  %d) %s",
    "menu.batch_what_now": "What would you like to do?",
    "menu.batch_create_all": "Create a variant for each entry",
    "menu.batch_cancel": "Cancel",
    "menu.ask_sequence_file": "Sequence file (one sequence per line): ",
    "menu.batch_done": "Batch applied: %s",
    "menu.msa_skip": "Skipped — edit the entity to set it later.",
    "menu.msa_skip_edit": "Skipped — the alignment is unchanged.",
    "menu.templates_skip_edit": "Skipped — the templates are unchanged.",
    "menu.ask_msa_yn": "Add an MSA for this record? [y/N]: ",
    "menu.ask_templates_yn": "Add structural templates? [y/N]: ",

    "menu.ask_msa_path": "Path to the MSA file: ",
    "menu.msa_inline_header": "Paste the MSA, finish with a blank line:",
    "menu.ask_ref_path": "Path to the template structure file: ",
    "menu.ask_ref_pairs": "Index pairs (query:template, comma-separated, 0-based; blank = none): ",

    "menu.files_in": "Files in %s:",
    "menu.pick_hint": "Type a number to open or choose, a full path, or '..' to go up. 0 cancels.",
    "menu.pick_cannot_list": "Cannot list this directory.",
    "menu.add_rna_prompt": "RNA sequence: ",
    "menu.add_dna_prompt": "DNA sequence: ",
    "menu.add_protein_prompt": "Protein sequence: ",
    "menu.add_ligand_value_prompt": "Ligand value: ",

    "menu.ask_sequence": "New sequence: ",
    "menu.ask_position": "Position (1-based residue number): ",
    "menu.ask_code": "Modification code (e.g. SEP): ",
    "menu.ask_atom_a": "Atom name on the first residue: ",
    "menu.ask_atom_b": "Atom name on the second residue: ",
    "menu.ask_residue_a": "Residue number on the first record: ",
    "menu.ask_residue_b": "Residue number on the second record: ",
    "menu.linkage_added": "Linkage added.",
    "menu.linkage_removed": "Linkage removed.",
    "menu.modification_added": "Modification added.",
    "menu.modification_removed": "Modification removed.",
    "menu.component_set": "Component definition set.",
    "menu.copied": "Duplicated to %r.",
    "menu.removed": "Removed %r.",
    "menu.entity_list_header": "  %s  %s  %d residues",
    "menu.entity_list_ligand": "  %s  ligand  %s",
    "menu.entity_list_empty": "  (no entities)",
    # The residue-numbered modification rows under an entity listing:
    # the label opens the block, each row names the CCD code at the
    # human (1-based) residue number, with the actual residue echoed
    # when the position is inside the sequence.
    "menu.entity_mod_row": "      %s at residue %s%s",
    # -- configuration status: what is defaulted, provided, or missing --
    # One row per piece of information the user should be able to see,
    # each marked by state, with automatic values saying so (§16 review).
    "menu.status_title": "Configuration status",
    "menu.status_line": "  %-14s %s",
    "menu.status_name": "Name",
    "menu.status_seeds": "Model seeds",
    "menu.status_version": "AF3 version",
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
    "menu.incomplete_header": "Configuration is incomplete.",
    "menu.incomplete_missing": "Missing required information:",
    "menu.incomplete_row": "  %s — %s",
    "menu.incomplete_hint": (
        "Your current work has been preserved.\n"
        "Add the missing information before generating the final JSON."
    ),
    # -- free-navigation builder (the MenuApp wording) --
    "menu.version_unverified": "not set",
    "menu.version_pinned": "v%d",
    "menu.version_auto": "auto",
    "menu.ligand_by_code": "CCD %s",
    "menu.quantity_menu": "How many copies?",
    "menu.quantity_custom": "Custom quantity",
    "menu.quantity_custom_prompt": "Quantity: ",
    "menu.entity_list_ligand_counted": "  %s  ligand  %s  x%d",
    "menu.ligand_by_notation": "SMILES notation",
    "menu.master_actions": (
        "  1) Edit the job\n"
        "  2) Review configuration\n"
        "  3) Variants\n"
        "  4) Generate JSON\n"
        "  5) Open saved work\n"
        "  6) Import an AF3 JSON file"
    ),
    "menu.start_actions": (
        "  1) New job\n"
        "  2) Open saved work\n"
        "  3) Import an AF3 JSON file"
    ),
    "menu.import_file_line": "File: %s",
    "menu.import_confirm": "Load this JSON as the current job?",
    "menu.import_yes": "Load",
    "menu.import_no": "Cancel",
    "menu.import_loaded": "JSON loaded. The job is now a normal, editable configuration.",
    "menu.import_notes": "Fields this builder does not support for editing:",
    "menu.import_note_line": "  ! %s",
    "menu.import_failed": "Could not load this JSON.",
    "menu.import_reason": "Reason: %s",
    "menu.import_untouched": "The original file has not been modified.",
    "menu.ask_experiment": "Job name (blank generates one): ",
    "menu.edit_sequence_prompt": "New sequence (blank keeps the current one): ",
    "menu.edit_desc_prompt": "New description (blank keeps the current one): ",
    "menu.mod_remove_entity": "Which entity holds the modification:",
    "menu.no_mods_on_record": "This record carries no modifications.",
    "menu.open_saved_loaded": "Recovered %s.",
    "menu.ask_import_path": "AF3 JSON file to import: ",
    "menu.builder_title": "Edit the job",
    "menu.builder_actions": (
        "  1) Entities (protein / DNA / RNA / ligand)\n"
        "  2) Job settings (name, seeds, version)\n"
        "  3) Bonds, modifications & custom components"
    ),
    "menu.review_title": "Review configuration",
    "menu.review_entities": "Entities: %d",
    "menu.review_actions": (
        "  1) Validate this job and its variants\n"
        "  2) Show the JSON for this job"
    ),
    "menu.settings_title": "Job Settings",
    "menu.settings_actions": (
        "  1) Set job name\n"
        "  2) Set AF3 version\n"
        "  3) Set model seeds\n"
        "  4) Generate model seeds"
    ),
    "menu.linkage_title": "Bonds, Modifications & Custom Components",
    "menu.linkage_count": "Currently: %d linkage(s)",
    "menu.linkage_actions": (
        "  1) Add a bond between two atoms\n"
        "  2) Remove a bond\n"
        "  3) Add a modification (PTM) to a record\n"
        "  4) Remove a modification\n"
        "  5) Set the custom component (userCCD) definition"
    ),
    "menu.linkage_index_prompt": "Which linkage (1-based number, 0 cancels): ",
    "menu.linkage_row": "  %d) %s",
    "menu.linkage_none": "There are no linkages to remove.",
    "menu.paste_definition": "Paste the CIF definition, finish with a blank line:",
    "menu.finding_indent": "    ",
    "menu.card_line": "%d. %s — %s",
    "menu.variants_title": "Variants",
    "menu.spec_line": "%s — %s",
    "menu.created": "Created variant %r.",
    "menu.ask_show_json": "Show the JSON for this variant? [y/N]: ",
    "menu.ask_export_dir": "Output directory: ",
    "menu.export_warning": "Note: %s",
    "menu.export_action_line": "  %s  %s",
    "menu.ask_proceed": "Write these files? [y/N]: ",
    "menu.export_skipped": "Skipped (exists): %s",
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
