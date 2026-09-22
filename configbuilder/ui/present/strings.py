"""The wizard's string registry (plan §18.7, §18.8; CHECKLIST 11a).

Every user-visible wizard *chrome* string — action wording, fixed
notices — is data here, keyed, unique, and non-empty. Domain labels are
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
    # Capability-probe reasons and the probe summary's fixed wording
    # (plan §16.7: the result is logged with its reason).
    "probe.reason.plain_override": "--plain override",
    "probe.reason.ascii_override": "--ascii override",
    "probe.reason.no_tty": "no TTY",
    "probe.reason.no_color": "NO_COLOR",
    "probe.reason.term": "TERM=%r",
    "probe.reason.narrow": "narrow width (%d)",
    "probe.reason.encoding": "console encoding is not UTF-8",
    "probe.reason.vt": "virtual-terminal processing unavailable",
    "probe.reason.floor": "width below the 60-column floor",
    "probe.reason.package_absent": "optional package absent",
    "probe.default_reason": "capable terminal",
    "probe.summary": "probe: renderer=%s glyphs=%s color=%s size=%dx%d (%s)",
    # Console and long-text route wording (plan §16.5).
    "console.eof": "input stream closed",
    "route.menu.paste": "Paste it here",
    "route.menu.file": "Read from a file on this machine",
    "route.none_available": "No input route is available for this field.",
    "route.menu.editor": "Open an editor",
    "route.paste.instructions": "Paste, then finish with a blank line:\n",
    "route.file.prompt": "File path: ",
    "route.choose": "Choose [%s]: ",
    "route.pairs.error": "expected two numbers, e.g. '0 4'",
    "route.file.none": "no path given",
    "route.file.read": "read %d bytes from %s",
    "route.file.error": "could not read %s: %s",
    "route.editor.complete": "editor round-trip complete",
    "route.editor.missing": "no editor found; use paste or read-from-file instead",
    "route.editor.launch_error": "could not launch editor %r: %s",
    "route.example.pairs": "0 4\n2 9",
    "crlf.crlf": "note: content uses CRLF (Windows) line endings; preserved byte-for-byte — validation will decide whether that is acceptable",
    "crlf.mixed": "note: content mixes CRLF and LF line endings; preserved byte-for-byte — validation will decide whether that is acceptable",
    "summary.crlf": "; CRLF line endings detected and preserved",
    "summary.mixed": "; mixed line endings detected and preserved",
    "summary.lines_suffix": "line%s",
    "summary.plural": "s",
    "summary.received": "received %d bytes, %d %s, shape %s",
    # The non-interactive guard (plan §16.7: a hang guard, not batch mode).
    "guard.header": "No terminal is attached (stdin/stdout are not a TTY), so the wizard cannot ask its questions. Nothing was started.",
    "guard.missing_header": "Inputs that would have been required, in order:",
    "guard.missing_none": "No further input was required at step %r.",
    "guard.footer": "Run the wizard in a terminal to author a configuration; this guard exists so a background run can never hang on a prompt.",
    "field.optional_suffix": " (optional)",
    # Plain-renderer chrome (plan §16.3, §16.6).
    "plain.hint": "[Enter] accept default · n/p next/previous · e edit · d delete · v validate · a advanced · ? help · s save · q quit",
    "plain.jump_hint": "Type a number to jump to that field; 't <number>' shows technical detail.",
    "plain.fields_header": "Fields on this step:",
    "plain.actions_hint": "Actions: n next · p previous · v validate · s save · q quit",
    "plain.no_findings": "No findings.",
    "plain.no_further_step": "No further step is available yet; validate to check the base.",
    "plain.validate_clean": "Validation ran; no blocking findings.",
    "plain.nothing_written": "Nothing written.",
    "plain.unsaved_marker": "(unsaved changes)",
    "plain.output_prompt": "Output directory: ",
    "plain.save_as_prompt": "Save as: ",
    "plain.quit_prompt": "Unsaved changes — save before quitting? [y/N]: ",
    "plain.write_prompt": "Write these files? [y/N]: ",
    "plain.header_separator": "— ",
    "plain.entry_prompt": "> ",
    "plain.advanced_version_prompt": "Format version to pin (blank to keep current): ",
    "plain.advanced_evidence_prompt": "Evidence reference for this version (e.g. PIN-001; blank if none): ",
    "plain.farewell": "Session ended. Nothing more will be asked.",
    "plain.detail_indent": "   ",
    "plain.technical_prefix": "t ",
    "plain.technical_title": "Technical detail - finding %s",
    "guard.fullscreen_missing": "The full-screen renderer requires the optional prompt_toolkit package.",
    "plain.header_join": " — ",
    "plain.list_indent": "  %s  %s",
    "plain.prompt_join": "%s%s%s: ",
    "plain.default_suffix": " [%s]",
    "plain.wrote": "wrote %s",
    "plain.conflict": "conflict: %s",
    "plain.warning": "warning: %s",
    "plain.error": "error: %s",
    "plain.not_applied": "not applied (%s)",
    "plain.unknown_service": "unknown service %r",
    "plain.unknown_operation": "unknown operation %r",
    "plain.could_not_apply": "could not apply: %s",
    "plain.saved": "saved",
    "plain.saved_to": "Project saved to %s",
    "plain.manifest_where": "Manifest and inputs are under %s (see manifest.json).",
    "plain.technical_rule": "rule %s",
    # Journal (plan §16.8).
    "journal.resume": "resume at step %r",
    "journal.for_project": "for %s",
    "journal.unsaved": "unsaved changes existed",
    "journal.offer_prompt": "Resume? [y/N]: ",
    "journal.size_cap": "journal entry exceeds the size cap",
    "journal.join": "; ",
    "plain.no_such_finding": "no finding numbered %r",
    "plain.cannot_generate": "Cannot generate: %s",
    "guard.list_item": "  - %s",
    "jump.reference": "%d. %s — %s",
    # -- the free-navigation menu (the interactive builder) ------------
    "menu.select_prompt": "Select: ",
    "menu.banner_rule": "============================================================",
    "menu.banner_title": "ConfigBuilder",
    "menu.back": "0)  Back",
    "menu.exit": "0)  Exit",
    "menu.invalid": "Not a valid choice: %r",
    "menu.interrupted": "Interrupted — returning to the menu.",
    "menu.current": "Current job: %s",
    "menu.entities": "Entities: %d",
    "menu.seeds": "Seeds: %s",
    "menu.variants": "Variants: %d",
    "menu.experiment": "Experiment: %s",
    "menu.base_entities": "Base entities: %d",
    "menu.currently": "Currently: %d %s(s)",
    "menu.none": "(none)",
    "menu.current_settings": "Current name: %s",
    "menu.current_version": "Version: %s",
    "menu.current_seeds": "Model seeds: %s",
    "menu.ask_name": "New name: ",
    "menu.ask_version": "AF3 version to pin: ",
    "menu.ask_evidence": "Evidence reference (e.g. PIN-001; blank if none): ",
    "menu.ask_seeds": "Seeds (space- or comma-separated integers): ",
    "menu.ask_count": "How many seeds to generate: ",
    "menu.seeds_generated": "Generated seeds: %s",
    "menu.ask_key": "Variant key (used in file names): ",
    "menu.ask_label": "Label shown to humans (blank keeps the key): ",
    "menu.ask_source": "Duplicate/edit which variant: ",
    "menu.ask_confirm": "Confirm? [y/N]: ",
    "menu.not_applied": "Not applied: %s",
    "menu.applied": "Applied.",
    "menu.no_project": "No project is open.",
    "menu.saved_to": "Saved to %s",
    "menu.loaded": "Loaded %s",
    "menu.load_failed": "Load failed: %s",
    "menu.no_autosave": "No autosave found.",
    "menu.autosaved": "Autosaved.",
    "menu.autosave_path": "Autosave: %s",
    "menu.outro_wizard": "Returning from the wizard.",
    "menu.ok": "  OK  %s",
    "menu.fail": "  FAIL %s",
    "menu.export_header": "Export Variants",
    "menu.export_ready": "%d variant(s) ready:",
    "menu.export_dir": "Output directory: %s",
    "menu.export_all": "  1) Export all variants",
    "menu.export_select": "  2) Select variants",
    "menu.export_change_dir": "  3) Change output directory",
    "menu.export_preview": "  4) Preview export",
    "menu.export_which": "Variant keys to export (comma-separated): ",
    "menu.export_no_selection": "No variants selected.",
    "menu.export_unknown": "No variant keyed %r.",
    "menu.export_written": "Wrote %s",
    "menu.export_conflict": "Conflict: %s",
    "menu.export_would_write": "  would write %s (%d bytes)",
    "menu.export_none": "No variants are defined yet.",
    "menu.export_dir_changed": "Output directory set to %s",
    "menu.preview_header": "Preview",
    "menu.preview_entities": "Entities:",
    "menu.preview_modifications": "Modifications: %s",
    "menu.preview_output": "Output: %s",
    "menu.preview_name": "Name: %s",
    "menu.preview_seeds": "Seeds: %s",
    "menu.preview_edit": "  - %s: %s",
    "menu.json_error": "Cannot build JSON: %s",
    "menu.editor_offer": "Open in editor? [y/N]: ",
    "menu.editor_done": "Editing finished.",
    "menu.base_label": "Base configuration",
    "menu.specs_header": "Variants:",
    "menu.specs_none": "No variants defined yet.",
    "menu.variant_actions": (
        "  1) Create variant\n"
        "  2) Edit variant\n"
        "  3) Duplicate variant\n"
        "  4) Delete variant\n"
        "  5) Preview variant\n"
        "  6) Generate JSON preview\n"
        "  7) Generate from sequence file"
    ),
    "menu.ask_sequence_file": "Sequence file (one sequence per line): ",
    "menu.batch_done": "Batch applied: %s",
    "menu.entity_actions": (
        "  1) Add\n"
        "  2) Edit\n"
        "  3) Delete\n"
        "  4) List details"
    ),
    "menu.entity_actions_extra": "  5) MSA / Templates",
    "menu.entity_actions_extra": "  5) MSA / Templates",
    "menu.msa_title": "MSA / Templates",
    "menu.msa_note": "MSA / templates apply to a record that already exists (add it first).",
    "menu.msa_record_prompt": "Record id (e.g. A): ",
    "menu.msa_actions": (
        "  1) Set protein MSA (unpaired/paired/both/automatic/free)\n"
        "  2) Set RNA MSA (automatic/free/provided)\n"
        "  3) Set structural templates"
    ),
    "menu.ask_msa_mode": "Mode: ",
    "menu.ask_msa_route": "Source - i) paste inline, e) external file path: ",
    "menu.ask_msa_path": "Path to the MSA file: ",
    "menu.msa_inline_header": "Paste the MSA, finish with a blank line:",
    "menu.ask_templates_route": (
        "Templates - n) search allowed, e) explicitly none, p) provide list: "
    ),
    "menu.ask_ref_path": "Path to the template structure file: ",
    "menu.ask_ref_pairs": "Index pairs (query:template, comma-separated, 0-based; blank = none): ",
    "menu.msa_actions_rna": (
        "  1) Set RNA MSA (automatic/free/provided)"
    ),
    "menu.export_empty_hint": "Nothing to export yet — create variants first (master menu, option 6).",
    "menu.factor_edits_note": "Edits (sequence changes etc.) are applied on top of the base — nothing is copied.",
    "menu.edit_field": "Edit which field? [sequence/description/name/seeds/format]",
    "menu.add_rna_prompt": "RNA sequence: ",
    "menu.add_dna_prompt": "DNA sequence: ",
    "menu.add_protein_prompt": "Protein sequence: ",
    "menu.add_ligand_prompt": "Ligand (CCD code or SMILES): ",
    "menu.ask_record": "Which record (letter): ",
    "menu.ask_sequence": "New sequence: ",
    "menu.ask_description": "New description (blank clears): ",
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
    "menu.alignment_set": "Alignment set.",
    "menu.references_set": "References set.",
    "menu.copied": "Duplicated to %r.",
    "menu.removed": "Removed %r.",
    "menu.unknown_record": "No record keyed %r.",
    "menu.entity_list_header": "  %s  %s  %d residues",
    "menu.entity_list_ligand": "  %s  ligand  %s",
    "menu.entity_list_empty": "  (no entities)",
    "menu.wizard_summary": "Job summary",
    "menu.summary_line": "  %-14s %s",
    "menu.summary_residues": "%d residues",
    "menu.summary_no_dna": "no DNA",
    "menu.summary_no_ptms": "no PTMs",
    # -- free-navigation builder (the MenuApp wording) --
    "menu.version_unverified": "not set",
    "menu.version_pinned": "v%d",
    "menu.version_auto": "auto",
    "menu.ligand_by_code": "CCD %s",
    "menu.ligand_by_notation": "SMILES notation",
    "menu.master_actions": (
        "  1) Job Builder\n"
        "  2) Validation\n"
        "  3) Show JSON\n"
        "  4) Save project\n"
        "  5) Load project\n"
        "  6) Variants\n"
        "  7) Generate JSONs\n"
        "  8) Guided wizard\n"
        "  9) Job summary"
    ),
    "menu.start_actions": (
        "  1) New experiment\n"
        "  2) Load a saved project"
    ),
    "menu.ask_experiment": "Experiment name: ",
    "menu.ask_path": "Project file path (blank keeps the current one): ",
    "menu.builder_title": "Job Builder",
    "menu.builder_actions": (
        "  1) Job Settings\n"
        "  2) Proteins\n"
        "  3) RNA\n"
        "  4) DNA\n"
        "  5) Ligands / Glycans\n"
        "  6) Bonded Atom Pairs\n"
        "  7) CCD / Custom Components\n"
        "  8) Delete Entity\n"
        "  9) Show Job Summary"
    ),
    "menu.settings_title": "Job Settings",
    "menu.settings_actions": (
        "  1) Set job name\n"
        "  2) Set AF3 version\n"
        "  3) Set model seeds\n"
        "  4) Generate model seeds"
    ),
    "menu.proteins_title": "Proteins",
    "menu.rna_title": "RNA",
    "menu.dna_title": "DNA",
    "menu.ligands_title": "Ligands / Glycans",
    "menu.pairs_title": "Bonded Atom Pairs",
    "menu.linkage_count": "Currently: %d linkage(s)",
    "menu.pairs_actions": (
        "  1) Add linkage\n"
        "  2) Remove linkage (1-based index)"
    ),
    "menu.ccd_title": "CCD / Custom Components",
    "menu.ccd_actions": (
        "  1) Set component definition (paste until blank line)\n"
        "  2) Add a modification to a record\n"
        "  3) Remove a modification"
    ),
    "menu.paste_definition": "Paste the CIF definition, finish with a blank line:",
    "menu.validation_title": "Validation",
    "menu.validation_actions": (
        "  1) Validate the base configuration\n"
        "  2) Validate all variants"
    ),
    "menu.finding_indent": "    ",
    "menu.card_line": "%d. %s — %s",
    "menu.variants_title": "Variants",
    "menu.numbered_spec": "  %d) %s — %s",
    "menu.spec_line": "%s — %s",
    "menu.created": "Created variant %r.",
    "menu.ask_factor": "Factor to change [sequence/job_name/job_description/seeds] (blank to stop): ",
    "menu.ask_factor_value": "New value: ",
    "menu.ask_show_json": "Show the JSON for this variant? [y/N]: ",
    "menu.export_actions": (
        "  1) Export all variants\n"
        "  2) Select variants\n"
        "  3) Change output directory\n"
        "  4) Preview export"
    ),
    "menu.ask_export_dir": "Output directory: ",
    "menu.export_warning": "Note: %s",
    "menu.export_action_line": "  %s  %s",
    "menu.ask_proceed": "Write these files? [y/N]: ",
    "menu.export_skipped": "Skipped (exists): %s",
    "menu.export_preview_note": "Nothing has been written yet.",
}


def text(key: str) -> str:
    """The wizard wording for ``key``. Unknown keys raise: a missing
    entry is a programming error, never a silent fallback (the same
    discipline the traceability registry applies to labels)."""
    try:
        return STRINGS[key]
    except KeyError:
        raise KeyError(
            "no wizard string registered for %r; add it to ui/present/strings.py" % key
        )
