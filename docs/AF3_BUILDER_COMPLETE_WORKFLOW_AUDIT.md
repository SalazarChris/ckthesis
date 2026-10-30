# AF3 Configuration Builder — Complete Practical Workflow Audit

**Audit type:** static, evidence-based source inspection only.
**Automated tests were NOT executed during this audit.** No test suite, CI workflow,
validation suite, AF3 inference run, installation step or long-running harness was
invoked. Every statement below is either (a) read directly from the current source,
or (b) explicitly marked as unverified / requiring a run.

**Date of audit:** 2026-10-29

> **Status of the findings.** This document is the *as-found* record: it describes the
> application as it stood when it was written and is deliberately not rewritten. What has
> since been fixed, what was deliberately left unchanged, and the tests that demonstrate it
> are recorded in
> [`AF3_WORKFLOW_FIX_IMPLEMENTATION_REPORT.md`](AF3_WORKFLOW_FIX_IMPLEMENTATION_REPORT.md).
> Where the two disagree, the implementation report is the current state.

---

## 1. Executive summary

The builder is a local, dependency-free Python application with two front ends over one
service layer: a text menu (`configbuilder.ui.render.menus`) and a PySide6 window
(`configbuilder.ui.render.qt`). Both drive the same five services and the same
generation pipeline, and the generated artifact is a standard AF3 input JSON v3.

Practically:

- **Job lifecycle** (new, open/import with preview+confirm, rename, seeds, JSON version,
  save with a validation gate, unsaved-changes protection) is complete in both front ends
  and clearly implemented.
- **Entities** (protein, RNA, DNA, ligand by SMILES or CCD code, multi-copy ligands,
  per-entity description) are complete in both, with two real asymmetries: only the CLI
  can create a **single-stranded** DNA record, and only the GUI can set a **ligand
  description**.
- **File-based generation** (one configuration per input entry for five input kinds) is
  shared end-to-end through `GenerationService.plan_input_batch` /
  `generate_input_batch`, with an explicit input-kind question, a pre-write preview, a
  collision-refusing policy and a manifest. This is the most heavily shared workflow in
  the application.
- **Structural templates** exist in both front ends for path-based `mmcifPath` templates.
  Inline `mmcif` templates are **imported and round-tripped but cannot be authored or
  edited** in either front end. Template index checking is shallow by design in the CLI
  (non-negative + query-range) and handed to the service in the GUI.
- **MSA** is complete for protein (automatic/free/unpaired/paired/both) and RNA
  (automatic/free/provided), with inline and file sources. The GUI cannot supply two
  *different* files for the `both` mode even though the service supports it.
- **Covalent bonds (`bondedAtomPairs`) exist only in the GUI.** The console has no bond
  option at all.
- **Read-only JSON preview** is implemented (`PreviewPage`) and *unreachable*: the window
  constructs it, hides it, and no sidebar item, menu action or button shows it. The CLI
  never renders the JSON either. A user cannot inspect the exact bytes before writing.
- Two large modules are **dead code**: `pages/variants.py` (1453 lines) and
  `dialogs/variant_forms.py` (937 lines) are imported by nothing. `VariantService`'s
  spec/expansion surface is reachable only from tests, the fixture generator and two
  legacy paths; the only method either front end calls is `inspect_input_file`.
- The CLI's **Custom CCD** menu offers "Add" and "Edit" as two options that call the same
  method with the same behaviour; "Edit" does not pre-fill the current definition.
- The CLI's **entity delete** asks `Delete "A"?` and ignores the service's own message
  (`the DNA duplex and its partner strand were removed`), while the GUI names the partner
  strand before deleting. Deleting one DNA strand removes both in either front end.

Nothing in this audit was executed, so no behaviour is reported as runtime-verified.

---

## 2. Current repository and audit scope

| Item | Value |
| --- | --- |
| Branch | `main` |
| HEAD | `9baa3ab` — "Record the commit and push details in the implementation report" |
| Working tree | Untracked: thesis documents (`THESIS_EXPANDED_DRAFT.md`, `docs/THESIS_*`, `docs/Thesis*`), `docs/screenshots/`, `docs/ui_referene/`, `docs/deep-research-report.md`, scratch files `1`, `test.json`, `Untitled_job_1.json`, `vg_probe.txt`, and this report. **Also present: 18 tracked `docs/*_PROMPT.md` / report files showing as deleted in the working tree.** Those deletions were observed during the audit and were **not** made by it (nothing in this audit deleted or wrote any file except this report); they are left untouched for the user to review or restore. No other tracked file is modified, and nothing was staged. |
| Recent commits | `9baa3ab`, `6ebb2b6` (output-folder separation + launchers), `323a698` (inline templates, index mappings, honest batch reporting), `d4cd17d` (Windows setup + dependency check), `ef52de0` (explicit typed batch inputs) |
| Application entry points | `af3builder.py` → `configbuilder.app.cli:main`; `gui.py` → `python -m configbuilder.ui.render.qt`; console script `configbuilder`; GUI script `af3-json-builder` |
| Launchers | `run_console.cmd`, `run_gui.cmd` (double-clickable, resolve their own folder, use `.venv\Scripts\python.exe`) |
| Install / dependency setup | `setup_windows.bat`, `check_dependencies.bat`, `tools/check_dependencies.py` |
| Source size | `configbuilder/**` ≈ 28.9k lines; Qt layer ≈ 7.1k lines |
| Tests present | 118 test modules, ≈ 28.6k lines (`tests/unit` 63 modules, `tests/gui` 19, `tests/architecture` 10, `tests/e2e` 8, `tests/analysis` 7, `tests/variant` 4, `tests/contract` 3, `tests/serialization` 2, `tests/golden` 2) |

**Scope.** The builder's own purpose: building, editing, validating and generating AF3
JSON input configurations. `af3_analysis/` (the separate comparative-analysis package) and
`generated_jobs/` (research outputs) are out of scope except where the builder itself
touches them.

**Method.** Directory/line inventory, full read of both front ends' menu and control
trees, call-chain tracing into `configbuilder/app`, `configbuilder/validation`,
`configbuilder/transform`, `configbuilder/output`, `configbuilder/persistence`, plus
static reading of the test tree to map coverage. No module was imported or executed for
behavioural claims; the only code executed was read-only text extraction to list the rule
catalogue (45 `Rule(...)` records) and repository inventory.

Historical reports in `docs/` (e.g. `CONFIGURATION_GENERATION_FIX_REPORT.md`,
`GUI_AUTOMATED_QA_REPORT.md`, `TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md`) are
**historical evidence**. They predate or do not name the current HEAD, so their passing
results are not attributed to `9baa3ab` here.

---

## 3. Master inventory of user-facing options

Status vocabulary: **SOURCE-CONFIRMED** (source implements/dispatches it),
**PARTIALLY IMPLEMENTED**, **DUPLICATED**, **OBSOLETE OR UNREACHABLE**,
**UNVERIFIED** (source alone does not establish the outcome),
**POTENTIAL DEFECT**.

### 3.1 Console (CLI)

| ID | Interface | Section/menu | Exact option | Purpose | User input required | Handler/service | Main output | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C-01 | CLI main menu | main | `1. New job` | Start a fresh job | Job name (blank → automatic) | `MenuApp._new_job` → `ProjectService.new` | New empty job in memory | SOURCE-CONFIRMED |
| C-02 | CLI main menu | main | `2. Open a JSON file` | Load an AF3 JSON | Path (picker or typed) | `MenuApp._open_json_file` → `ProjectService.import_json_commit` | Job loaded, summary + notes | SOURCE-CONFIRMED |
| C-03 | CLI main menu | main | `0. Exit` | Leave (with unsaved prompt if dirty) | — | `MenuApp._main_menu` | Exit status 0 | SOURCE-CONFIRMED |
| C-04 | CLI job menu | Job | `1. Edit job configurations` | Job-level settings | — | `_edit_job_config_menu` | Submenu | SOURCE-CONFIRMED |
| C-05 | CLI job menu | Job | `2. Add entity` | Add protein/DNA/RNA/ligand | Family, then family-specific | `_add_entity_menu`, `_add_entity` | New record(s) | SOURCE-CONFIRMED |
| C-06 | CLI job menu | Job | `3. Edit entity` | List → select → edit/delete/(mods) | Entity choice | `_edit_entity_menu`, `_entity_action_menu` | Edited/removed record | SOURCE-CONFIRMED |
| C-07 | CLI job menu | Job | `4. Custom CCD management` | Job `userCCD` / `userCCDPath` | Inline CIF or path | `_custom_ccd_menu` → `set_component_definition` | CCD set/removed | SOURCE-CONFIRMED |
| C-08 | CLI job menu | Job | `5. Post-translational modification management` | PTMs across polymers | Entity, code, position | `_ptm_menu`, `_add_modification_to` | PTM added/edited/removed | SOURCE-CONFIRMED |
| C-09 | CLI job menu | Job | `6. Save and show summary` | Gate + write one JSON | Destination (default) + overwrite confirm | `_save_and_summary` → `plan_save`/`execute` | JSON file, summary block | SOURCE-CONFIRMED |
| C-10 | CLI job menu | Job | `7. Generate configurations from a file` | One config per input entry | Kind, file, output folder | `_file_menu`, `_generate_from_file` → `generate_input_batch` | N configs + `manifest.json` + assets | SOURCE-CONFIRMED |
| C-11 | CLI job menu | Job | `0. Return to main menu` | Leave, asking about unsaved changes | Save/discard/cancel | `_leave_job` | — | SOURCE-CONFIRMED |
| C-12 | CLI edit job | Edit job | `1. Job name` | Rename | New name | `_edit_job_config_menu` → `set_name` | Renamed | SOURCE-CONFIRMED |
| C-13 | CLI edit job | Edit job | `2. Model seeds` | Set seeds | Specific values **or** a count | `_edit_seeds` → `set_seeds` | New seed list | SOURCE-CONFIRMED |
| C-14 | CLI edit job | Edit job | `3. JSON version` | Pin input version | One of 1–4 (or auto) | `_set_version` → `set_format_target` | Pinned version | SOURCE-CONFIRMED |
| C-15 | CLI add entity | Add entity | `1. Protein` → sequence → MSA? → templates? | Add protein | Sequence, MSA choice, template choice | `_add_entity`, `_chain_msa`, `_chain_templates` | Protein record (+ alignment/refs) | SOURCE-CONFIRMED |
| C-16 | CLI add entity | Add entity | `2. DNA` → sequence → complement yes/no | Add DNA (duplex or lone strand) | Sequence + duplex answer | `_add_dna_with_complement_choice` → `add_record(duplex=…)` | One or two DNA records | SOURCE-CONFIRMED |
| C-17 | CLI add entity | Add entity | `3. RNA` → sequence → MSA? | Add RNA | Sequence + MSA choice | `_add_entity`, `_chain_msa` | RNA record | SOURCE-CONFIRMED |
| C-18 | CLI add entity | Add entity | `4. Ligand` → CCD or SMILES → value → copies | Add ligand | Kind, value, copy count | `_ligand_kind`, `_ask_quantity`, `add_record` | Ligand record(s) | SOURCE-CONFIRMED |
| C-19 | CLI entity | Selected entity | `1. Edit` | Edit fields (sequence/description; ligand representation) | New values (blank keeps) | `_edit_entity_fields` | Updated record; then MSA/template questions for polymers | SOURCE-CONFIRMED |
| C-20 | CLI entity | Selected entity | `2. Delete` | Remove record (with confirm) | Yes/No | `_delete_entity_key` → `remove_record` | Record(s) removed | **POTENTIAL DEFECT** — partner strand not named (F-05) |
| C-21 | CLI entity | Selected entity | `3. Modifications` (polymers) | Per-record PTMs | Code, position | `_record_mod_menu` | PTM list changed | SOURCE-CONFIRMED |
| C-22 | CLI MSA | Entity edit/add | MSA choice: keep / provide files / none | Alignment state | Files, or explicit none | `_collect_msa_choice`, `_ask_msa_file` → `set_alignment` | Alignment mode + source | SOURCE-CONFIRMED |
| C-23 | CLI MSA | Entity edit/add | Paired file + unpaired file prompts (protein) | Two independent sources | Up to two paths | `_chain_msa` → `set_alignment(paired_external_path=…)` | `both`/`paired`/`unpaired` | SOURCE-CONFIRMED |
| C-24 | CLI MSA | Entity edit/add | RNA MSA file prompt | Single A3M file | One path | `_chain_msa` (rna branch) | `provided` | SOURCE-CONFIRMED |
| C-25 | CLI templates | Entity add/edit | `Use structural templates …? [y/N]` | Route to template menu | y/N | `_chain_templates` | — | SOURCE-CONFIRMED |
| C-26 | CLI templates | Templates | `1. Let AlphaFold search for templates` | `SearchAllowed` state | — | `_collect_references_for` → `set_references` | No `templates` refs | SOURCE-CONFIRMED |
| C-27 | CLI templates | Templates | `2. No templates` | Explicit empty | — | `set_references(references=())` | `templates` behavior changed | SOURCE-CONFIRMED |
| C-28 | CLI templates | Templates | `3. Provide template mmCIF files and residue index pairs` | Path templates + mappings | Per template: CIF path + `q:t` pairs + another? | `_collect_template_list`, `_ask_template_file`, `_ask_template_pairs` | `mmcifPath` templates | SOURCE-CONFIRMED (path-only) |
| C-29 | CLI CCD | Custom CCD | `1. View the custom CCD definition` | Show current state | — | `_custom_ccd_menu` | Definition shown | SOURCE-CONFIRMED |
| C-30 | CLI CCD | Custom CCD | `2. Add a custom CCD definition` | Set definition | Inline CIF paste or file path | `_add_ccd_definition` | Definition set | SOURCE-CONFIRMED |
| C-31 | CLI CCD | Custom CCD | `3. Edit the custom CCD definition` | Intended: modify existing | Same prompts as Add | `_add_ccd_definition` | Identical to C-30 | **DUPLICATED** (F-06) |
| C-32 | CLI CCD | Custom CCD | `4. Remove the custom CCD definition` | Clear with confirm | Yes/No | `_remove_ccd_definition` → `clear_component_definition` | Cleared | SOURCE-CONFIRMED |
| C-33 | CLI PTM | PTM menu | `1. View modifications` | List PTMs | — | `_say_ptm_list` | List | SOURCE-CONFIRMED |
| C-34 | CLI PTM | PTM menu | `2. Add a modification` | Add PTM | Entity, code, position | `_ptm_add` → `add_modification` | PTM added | SOURCE-CONFIRMED |
| C-35 | CLI PTM | PTM menu | `3. Edit a modification` | Change code/position | Entity, modification, new values | `_ptm_edit` → `update_modification` | PTM updated | SOURCE-CONFIRMED |
| C-36 | CLI PTM | PTM menu | `4. Remove a modification` | Delete PTM | Entity, modification | `_ptm_remove` → `remove_modification` | PTM removed | SOURCE-CONFIRMED |
| C-37 | CLI save | Save | Destination prompt `blank = <path>` | Choose where to write | Path or blank | `_ask_destination`, `_write_json` | One JSON file | SOURCE-CONFIRMED |
| C-38 | CLI save | Save | Overwrite confirmation | Protect existing file | Yes/Cancel | `_ask_destination` + confirm | Overwrite or cancel | SOURCE-CONFIRMED |
| C-39 | CLI batch | File menu | `1. Load an input file and generate configurations` | Run batch | Kind → file → output folder | `_generate_from_file` → `generate_input_batch` | Configs + manifest + assets | SOURCE-CONFIRMED |
| C-40 | CLI batch | File menu | Kind: protein / DNA / RNA / ligand-SMILES / ligand-CCD | Declare file type | One of five | `FILE_KINDS` (menus.py:1621) | Reader choice | SOURCE-CONFIRMED |
| C-41 | CLI picker | Any path prompt | Numbered directory listing, `..`, full path, `0` cancel | Path picking | Number/path | `_pick_path`, `_picker_listing` | Path string | SOURCE-CONFIRMED |
| C-42 | CLI output | Batch prompt | `Output folder: <root>` note + diagnostic | Show resolved root | — | `_say_output_root` → `OutputPaths.resolve_root` | Informational | SOURCE-CONFIRMED |

**Not present in the console at all:** covalent bonds (`bondedAtomPairs`), any JSON
preview/export-as-text, a dedicated validate/review action, job description editing,
ligand description editing, entity copy-count editing after creation, FASTA input.

### 3.2 Desktop window (GUI)

Navigation: three sidebar destinations (**Overview**, **Entities**, **Generate**), a FILE
footer row (New · Open · Save) whose actions also carry Ctrl+N/O/S, plus a hidden menu bar
that exposes the same four actions (`gui.menu_file` → New/Open/Save/Quit).

| ID | Interface | Section/page | Exact control | Purpose | User input required | Handler | Main output | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G-01 | GUI shell | FILE footer + menu | **New** (`Ctrl+N`) | New job | Discard confirmation if dirty | `MainWindow.new_job` → `state.new_project` | Empty job | SOURCE-CONFIRMED |
| G-02 | GUI shell | FILE footer + menu | **Open** (`Ctrl+O`) | Open AF3 JSON | File + import preview accept | `MainWindow.open_json` → `offer_import` | Job loaded | SOURCE-CONFIRMED |
| G-03 | GUI shell | FILE footer + menu | **Save JSON…** (`Ctrl+S`) | Write one JSON | Destination + overwrite confirm | `MainWindow.save_json` → `plan_save`/`execute` | One JSON file (+assets) | SOURCE-CONFIRMED |
| G-04 | GUI shell | menu bar | **Quit** (`Ctrl+Q`) | Close window | Discard confirmation if dirty | `closeEvent` | Exit | SOURCE-CONFIRMED |
| G-05 | GUI Overview | readiness card | **Validate** button | Run validation, show findings | — | `OverviewPage.validate_job` → `state.validate` | Findings list | SOURCE-CONFIRMED |
| G-06 | GUI Overview | entity card | **Go to Entities** button | Switch destination | — | `OverviewPage.entities_button` | Entities page | SOURCE-CONFIRMED |
| G-07 | GUI Overview | Job details | Name field + **Apply** | Rename job | New name | `JobSettingsPanel.apply_name` → `set_name` | Renamed | SOURCE-CONFIRMED |
| G-08 | GUI Overview | Job details | Seeds field + **Apply** | Set seeds | Seed list text | `apply_seeds` → `set_seeds` | Seeds changed | SOURCE-CONFIRMED |
| G-09 | GUI Overview | Job details | JSON version combo + **Apply** | Pin version | 1–4 | `apply_version` → `set_format_target` | Version pinned | SOURCE-CONFIRMED |
| G-10 | GUI Entities | picker row | Entity drop-down | Select entity | Selection | `EntitiesPage.selector` | Details + settings shown | SOURCE-CONFIRMED |
| G-11 | GUI Entities | picker row | **Edit entity** | Edit selected record | Family-specific form | `edit_selected` → `_edit_sequence` / `_edit_ligand` | Record updated | SOURCE-CONFIRMED |
| G-12 | GUI Entities | picker row | **Delete entity** | Remove selected | Consequence-naming confirm | `delete_selected` → `remove_record` | Record removed | SOURCE-CONFIRMED |
| G-13 | GUI Entities | add row | **Add Protein** | Add protein | Sequence + description | `add_protein` → `SequenceFormDialog` | Protein record | SOURCE-CONFIRMED |
| G-14 | GUI Entities | add row | **Add RNA** | Add RNA | Sequence + description | `add_rna` | RNA record | SOURCE-CONFIRMED |
| G-15 | GUI Entities | add row | **Add DNA** | Add DNA | Sequence + description | `add_dna` → `add_record("dna", …)` with the service's **default `duplex=True`** | **Two** DNA records always | **POTENTIAL DEFECT** (F-01) |
| G-16 | GUI Entities | add row | **Add Ligand** | Add ligand | Representation kind, value, copies, description | `add_ligand` → `LigandFormDialog` → `add_record` | Ligand record(s) | SOURCE-CONFIRMED |
| G-17 | GUI Entities | file row | **Generate configurations from file...** | Batch generation | Kind → file → folder → preview accept | `EntitiesPage.generate_from_file` → `state.generate_input_configurations` | Configs + manifest + assets | SOURCE-CONFIRMED |
| G-18 | GUI Entities | tabs | **Entity settings** tab | Selected entity's own settings | — | `AdvancedPage(scope="entity")` | Settings groups | SOURCE-CONFIRMED |
| G-19 | GUI Entities | tabs | **Custom CCDs** tab | Job-wide CCD | Radio (none/inline/file), text, browse, Apply/Clear | `AdvancedPage(scope="ccd")` | `userCCD` / `userCCDPath` | SOURCE-CONFIRMED |
| G-20 | GUI Entities | tabs | **Covalent bonds** tab | Job-wide bonds | Endpoint A/B (entity, residue, atom) | `AdvancedPage(scope="bonds")`, `BondFormDialog` | `bondedAtomPairs` | SOURCE-CONFIRMED (GUI-only) |
| G-21 | GUI Advanced | Modifications group | **Add / Edit / Remove modification** | Per-entity PTMs | Code + residue (spin) | `add_modification`, `edit_selected_modification`, `remove_selected_modification` | Modified record | SOURCE-CONFIRMED |
| G-22 | GUI Advanced | Alignment group | **Change alignment** | MSA mode + source | Mode + inline text or file | `change_alignment` → `AlignmentFormDialog` → `set_alignment` | Alignment set | **PARTIALLY IMPLEMENTED** (F-02: one source only) |
| G-23 | GUI Advanced | Templates group | **Edit templates** | Template route/rows | Route + file rows + pairs text | `edit_templates` → `TemplateEditorDialog` → `set_references` | `mmcifPath` refs | **PARTIALLY IMPLEMENTED** (F-03: path-only) |
| G-24 | GUI Advanced | CCD group | **Apply / Clear** | Set/clear `userCCD(P)` | Inline text or file path | `apply_ccd`, `clear_ccd` | CCD set/cleared | SOURCE-CONFIRMED |
| G-25 | GUI Generate | step 1 | Scope note ("One AF3 JSON file. No manifest.") | Explain what is written | — | `_build_scope_group` | Informational | SOURCE-CONFIRMED |
| G-26 | GUI Generate | step 2 | Output folder field + **Choose folder...** | Destination | Folder (pre-filled `saved_jobs`) | `browse_destination` → `QFileDialog` | Path | SOURCE-CONFIRMED |
| G-27 | GUI Generate | step 2 | Advanced: overwrite policy combo | `Fail`/`Skip`/`Overwrite`/`Versioned` | Choice | `overwrite_policy` | Plan policy | SOURCE-CONFIRMED |
| G-28 | GUI Generate | step 2 | Advanced: path policy combo | `CopyIntoAssets`/`RelativeToOutput`/`AsGiven` | Choice | `path_policy` | Plan policy | SOURCE-CONFIRMED |
| G-29 | GUI Generate | step 3 | **Preview plan** | Plan + review tables | — | `preview_plan` → `state.plan_generation` | Entries/assets/findings tables | SOURCE-CONFIRMED |
| G-30 | GUI Generate | step 3 | **Copy selected path** | Clipboard | Row selection | `copy_selected_path` | Clipboard text | SOURCE-CONFIRMED |
| G-31 | GUI Generate | step 3 | **Review configuration** | Jump to Overview | — | `review_configuration` (emits `review_requested`) | Overview page | SOURCE-CONFIRMED |
| G-32 | GUI Generate | step 4 | **Generate files** | Write the reviewed plan | Confirm dialog | `generate` → `state.execute` | JSON file(s) + assets; result block | SOURCE-CONFIRMED |
| G-33 | GUI Internal | (hidden) | `PreviewPage` editor + **Copy** + **Refresh** | Read-only JSON view | — | `PreviewPage` | **Never displayed** | **OBSOLETE OR UNREACHABLE** (F-04) |

Dialogs (all "dumb" — render wording, return an answer, call no service):

| Dialog | Source | Used by |
| --- | --- | --- |
| `ImportPreviewDialog` | `dialogs/import_preview.py:38` | G-02 |
| `show_failure` | `dialogs/import_preview.py` | Import failure |
| `SequenceFormDialog` | `dialogs/entity_forms.py:105` | G-13/14/15, G-11 |
| `LigandFormDialog` | `dialogs/entity_forms.py:152` | G-16, G-11 |
| `ModificationFormDialog` | `dialogs/advanced_forms.py:114` | G-21 |
| `AlignmentFormDialog` | `dialogs/advanced_forms.py:164` | G-22 |
| `TemplateEditorDialog` | `dialogs/advanced_forms.py:308` | G-23 |
| `BondFormDialog` | `dialogs/advanced_forms.py:440` | G-20 |
| `choose_batch_kind` / `choose_batch_file` / `choose_output_folder` / `confirm_batch_preview` / `report_batch_run` | `dialogs/batch_input.py:65,78,94,101,154` | G-17 |
| `confirm_overwrite`, `confirm_discard`, `confirm_entity_delete`, `confirm_modification_removal`, `confirm_bond_removal`, `confirm_generation`, `ask_save_path`, `show_problem` | `dialogs/messages.py` | Save/delete/generate flows |

---

## 4. Workflow execution maps (end to end)

Notation: `file:line` refers to HEAD `9baa3ab`.

### 4.1 Start-up

- CLI: `af3builder.py:main` → `app/cli.py:main` → `build_services()` (`ui/services.py:46`)
  → `MenuApp(services, Console())` (`ui/render/menus.py:353`) → `run()`
  (`menus.py:526`). If a job is already open (a front end pre-built one) the job menu
  opens first; otherwise the main menu. Ctrl+C/EOF print `menu.interrupted` and return 0.
- GUI: `gui.py:main` → `.venv\Scripts\python.exe -m configbuilder.ui.render.qt` →
  `ui/render/qt/application.py` → `MainWindow(GuiState(...))`
  (`ui/render/qt/windows/main_window.py:84`). `GuiState` builds the same services and one
  `OutputPaths` (`state.py:47`). `gui.py` prefers `.venv` and falls back to `.venv-gui`;
  a missing environment prints setup instructions and exits 1 without starting anything.
- Dependency preflight: `check_dependencies.bat` → `tools/check_dependencies.py` with
  `--root` (and `--gui` for the legacy environment). **Read-only**: it installs nothing.
- AF3 inference is a **separate** environment. Neither entry point installs or needs it.

### 4.2 New job

`MenuApp._new_job` (`menus.py:567`) asks the name, calls `ProjectService.new`
(`app/project_service.py:70`), clears the remembered path, marks the job saved and prints
the created name. GUI: `MainWindow.new_job` (`main_window.py:396`) asks for discard
confirmation when dirty, then the same service call.

### 4.3 Open / import a JSON

CLI: `_open_json_file` (`menus.py:576`) → `ProjectService.import_json_commit`
(`project_service.py:194`). On failure it prints `Could not open this JSON.` + the
service's reason + `The original file has not been modified.`
GUI: `open_json` (`main_window.py:509`) → `offer_import` (`:523`):
`state.preview_import` → `ImportPreviewDialog` → `confirm_discard_changes` →
`state.commit_import`. Parsing/refusal lives in `transform/from_wire.py:from_wire`;
the commit path installs exactly the previewed document (`project_service.py:194`), and
the file itself is never modified. Fields the model does not carry come back as
`ImportNote` rows shown before the Import button.

### 4.4 Job settings

CLI `_edit_job_config_menu` (`menus.py:673`): `1` name → `set_name`
(`configuration_service.py:163`); `2` seeds → `_edit_seeds` (`menus.py:703`) offering
"specific values" or "generate N" → `set_seeds` (`:202`); `3` version → `_set_version`
(`menus.py:729`) → `set_format_target` (`:879`) limited to the supported versions.
GUI equivalent: `JobSettingsPanel.apply_name/apply_seeds/apply_version`
(`pages/settings.py:203,213,222`). Validation errors from the service are reported, not
raised.

### 4.5 Add entity (both front ends)

- Protein: CLI `_add_entity` (`menus.py:831`) → `add_record("protein", sequence)`
  (`configuration_service.py:227`) → `_chain_msa` (`menus.py:911`) → `_chain_templates`
  (`menus.py:980`). GUI: `SequenceFormDialog` → `state.add_record`.
- RNA: same, with the RNA/`provided` alignment branch.
- **DNA**: CLI `_add_dna_with_complement_choice` (`menus.py:877`) asks explicitly and
  calls `add_record("dna", sequence, duplex=<answer>)`. The service
  (`configuration_service.py:227`, docstring lines 233-242) commits **two** records for a
  duplex (the strand plus its reverse complement) and **one** for a lone strand. The GUI
  calls `add_record("dna", sequence=…)` with no `duplex` argument, so the default
  `duplex=True` applies and two records are always created (F-01).
- Ligand: CLI asks CCD/SMILES then the value then the copy count
  (`_ligand_kind`:823, `_ask_quantity`:810). GUI `LigandFormDialog` collects kind, value,
  copies **and a description**. `add_record` refuses a ligand with no representation and
  refuses `copies != 1` for DNA.

### 4.6 Edit / delete entity

- CLI `_edit_entity_fields` (`menus.py:1177`): for a ligand, kind + value →
  `set_representation` (`configuration_service.py:603`); for a polymer, sequence and
  description (blank keeps) → `update_record` (`:384`), then it *always* walks the MSA
  question and (protein) the templates question again.
- GUI `edit_selected` (`pages/entities.py:570`): `SequenceFormDialog` /
  `LigandFormDialog`; ligands go through the single-call
  `update_component_record` (`configuration_service.py:622`) so a refused code cannot
  half-apply; the description is passed only when it changed, preserving explicit-empty
  vs unset.
- Delete: CLI `_delete_entity_key` (`menus.py:1220`) asks `Delete "A"?` via
  `menu.delete_confirm`, then `remove_record` (`configuration_service.py:452`) and prints
  `Removed 'A'.`, **discarding `outcome.message`**. GUI `delete_selected`
  (`pages/entities.py:665`) builds `_delete_message` (`:679`) which *names* the partner
  strand (`gui.delete_duplex`) or the copy count (`gui.delete_copies`) before deleting.
  `remove_record` removes a duplex's partner and drops linkages that reference the
  removed identifiers.

### 4.7 MSA / alignment

`ConfigurationService.set_alignment` (`configuration_service.py:664`). Modes: protein
`automatic|free|unpaired|paired|both`; RNA `automatic|free|provided`. `automatic` and
`free` refuse any source; source-carrying modes need exactly one of `inline_text` /
`external_path`; `both` accepts an independent `paired_*` source and otherwise feeds both
sides from one source. CLI: `_collect_msa_choice`/`_ask_msa_file` (`menus.py:998,1007`)
collect up to two files for protein and one for RNA, validating existence, regular-file,
readability and non-emptiness (`_msa_file_problem`:1031) before committing. GUI:
`AlignmentFormDialog` (`advanced_forms.py:164`) offers the family's modes from the page
(`_PROTEIN_MODES`/`_RNA_MODES`, `pages/advanced.py:89-100`), shows inline *or* file
controls per mode, and `_apply_alignment` (`:857`) maps to exactly one `set_alignment`
call — so `both` is reachable but only with one shared source (F-02).

### 4.8 Structural templates

`ConfigurationService.set_references` (`configuration_service.py:780`), typed by
`ReferenceInput` (`:72`).
- CLI: `_collect_references_for` (`menus.py:1045`) → search / none / list;
  `_collect_template_list` (`:1065`) collects N complete definitions before committing
  anything, `_ask_template_file` (`:1100`) validates the file through
  `file_issue`, `_ask_template_pairs` (`:1112`) parses with
  `parse_pair_text(raw, sequence_length)` (`app/reference_validation.py:147`), which
  requires `query:template` digits and `query < sequence_length`. The CLI docstring states
  the builder has no mmCIF parser, so template indices are only checked as
  non-negative + query-range there (`menus.py:1065-1070`).
- GUI: `edit_templates` (`pages/advanced.py:876`) → `TemplateEditorDialog`
  (`advanced_forms.py:308`) with rows of *(file picked, pairs typed)* → `_apply_templates`
  (`:891`) → `ReferenceInput(external_path=…, pairs=parse_pairs(text))`
  (`pages/advanced.py:167` returns raw tokens; the **service** validates and its refusal
  is shown in the dialog).
- Inline `mmcif`: `from_wire._import_references` (`transform/from_wire.py:268-300`)
  accepts `mmcif` **or** `mmcifPath` and refuses both, refuses empty text, and refuses a
  row with neither. Neither front end can *author* an inline template: the CLI always
  writes a path, and the GUI's rows are file-picker only (F-03).
- Relative `mmcifPath` values are rebased to absolute paths against the input JSON's
  directory on import (`transform/from_wire.py:565-567`).

### 4.9 Custom CCD (`userCCD` / `userCCDPath`)

`set_component_definition` (`configuration_service.py:821`) stores one definition
(inline xor path); `clear_component_definition` (`:831`) removes it. CLI
`_custom_ccd_menu` (`menus.py:1268`) offers view/add/edit/remove; **Add and Edit are the
same call** (`:1302-1304`, F-06). GUI: `AdvancedPage.apply_ccd/clear_ccd`
(`pages/advanced.py:915,940`) with a three-way radio (none/inline/file). Import enforces
the mutual exclusion (`from_wire.py:479-493`) and rebases `userCCDPath`
(`:570-572`).

### 4.10 Covalent bonds

`add_linkage` (`configuration_service.py:846`) / `remove_linkage` (`:861`). Reachable only
from the GUI: `AdvancedPage.add_bond` → `BondFormDialog` (`advanced_forms.py:440`) with
endpoint (entity, 1-based residue, atom) pickers. **The console exposes no bond option**
(`grep -i bond configbuilder/ui/render/menus.py` → no match), so a bond can only be
created, listed or removed in the desktop window.

### 4.11 Save a single configuration

CLI `_save_and_summary` (`menus.py:1543`): prints the job summary, says the resolved
output root, takes a destination (blank = the file it came from, else
`<root>\saved_jobs\<job>.json`), then `_write_json` (`:1583`). The write path is
`GenerationService.plan_save` (`generation_service.py:917`) → the **gate**
(`_gate_base` → `ValidationService.validate_base(tiers=GATE_TIERS)`,
`validation_service.py:30,98`) → `to_wire` → `encode` → `output.plan`/`execute`.
A blocked job prints `This job cannot be saved yet:` plus the full status block
(`_say_status`, `menus.py:1772`) and writes nothing. An existing file triggers an explicit
overwrite confirmation first.
GUI `MainWindow.save_json` (`main_window.py:416`) does the same through
`state.save`/`plan_save`, shows the same refusal (`_blocking_message`, `:483`) and the
same `Save JSON…` semantics; the containing folder is remembered only after success.

### 4.12 Generate configurations from a file (the batch workflow)

Shared by construction:

1. **Kind** — CLI `FILE_KINDS` (`menus.py:1621`), GUI `KIND_LABELS`
   (`dialogs/batch_input.py:38`): `protein-sequence`, `dna-sequence`, `rna-sequence`,
   `ligand-smiles`, `ligand-ccd`. The question is asked *before* the file, deliberately:
   `app/batch_variants.py` docstring and `_add_entity_menu` reasoning.
2. **File** — CLI `_pick_path`; GUI `choose_batch_file` with a kind-dependent filter
   (sequences vs ligands).
3. **Preview** — `VariantService.inspect_input_file(path, kind)`
   (`app/variant_service.py:1214`) → `input_file_specs`; read-only, builds a thrown-away
   clone. CLI prints the count and entries; GUI opens `confirm_batch_preview`
   (`batch_input.py:101`) listing up to 12 entries, the kind, the destination, the planned
   file count and the shared `batch_preview_note`.
4. **Folder** — CLI prompt defaulted by `OutputPaths.default_batch_root()`
   (`app/paths.py:316`); GUI folder picker opened at the same value
   (`pages/entities.py:397`).
5. **Write** — `GenerationService.generate_input_batch`
   (`generation_service.py:736`) → `plan_input_batch` (`:616`) → `execute` (`:1046`).
   Result: one directory per entry named from the job and the entry
   (`<job>/<job>__<key>/<job>__<key>.json`), plus `manifest.json` for the run and any
   copied assets. Reporting uses the shared `batch_counts`/`batch_summary`
   (`app/results.py`, `ui/present/strings.py`), so the manifest is counted separately from
   configurations in both front ends.
6. **Base job** — never modified. Each configuration is `base + one entity`; the specs are
   independent (`AddRecord` per entry against the same base).

### 4.13 Generate the open job (GUI only)

`GeneratePage.generate` (`pages/generate.py:706`) → confirm → re-plan and compare
(`_same_plan`) → `state.execute`. Scope is fixed: "One AF3 JSON file. No manifest."
(`plan_base`, `generation_service.py:784`). The page reports written/skipped/copied/errors
from the service's `PlanOutput` (`_show_result`, `:757`). The CLI's nearest equivalent is
Save (C-09); there is no console page that plans before writing.

---

## 5. CLI-versus-GUI comparison

| Behaviour | CLI | GUI | Shared implementation? | Difference or gap |
| --- | --- | --- | --- | --- |
| New job | Yes (`_new_job`) | Yes (`new_job`) | `ProjectService.new` | Same |
| Open/import | Direct open after pick, then summary | Preview dialog → Import; unsaved prompt *after* preview | `import_json_preview`/`import_json_commit` | GUI adds an explicit review; both refuse with the service message. CLI has no preview step → **gap (review)** |
| Save | Yes, `plan_save` + gate | Yes, `plan_save` + gate | Yes | Same content discipline; identical refusal wording source |
| Destinations | `<root>\saved_jobs` / generated_configurations | Same | `app/paths.py` | Same |
| Overwrite | Confirmation prompt `menu.overwrite_confirm` | `confirm_overwrite` | `output.policies` | Same default (`Fail`); same question |
| Rename / seeds / version | `1/2/3` in Edit job | Job details + Apply | `set_name`, `set_seeds`, `set_format_target` | Same rules |
| Job description | **Absent** | **Absent** | `set_job_description` exists (`:181`) | Orphan service method (F-07) |
| Add protein/RNA | Yes (+MSA/templates chained) | Yes (settings edited afterwards) | `add_record` | CLI chains questions; GUI edits in the Advanced group |
| Add DNA single strand | Yes (`duplex` question) | **No** | `add_record(duplex=…)` | GUI always duplex (F-01) |
| Ligand description | **No** | Yes (`LigandFormDialog`) | `add_record(description=…)` | CLI cannot set or edit it (F-08) |
| Ligand copies after creation | No | No | — | Copies fixed at add time in both; GUI edit form shows them read-only |
| Delete entity | Yes; message ignores partner | Yes; names duplex partner / copy count | `remove_record` | CLI loses the service's duplex warning (F-05) |
| PTMs | Yes (job-wide + per entity) | Yes (per entity; job-wide CCD/bonds tabs) | `add/update/remove_modification` | Equivalent |
| MSA modes | All 5 protein / 3 RNA | Same list | `set_alignment` | Same |
| MSA sources | Paired **and** unpaired files independently (protein) | One source per change | `set_alignment(paired_external_path=…)` | GUI cannot send two distinct files (F-02) |
| MSA inline text | Not offered (files only; CCD uses paste) | Yes (`Aligned inline` editor) | `set_alignment(inline_text=…)` | CLI cannot paste an inline MSA (F-09) |
| Templates | Path rows + pairs, step-by-step | Path rows + pairs, table | `set_references` | Equivalent for paths |
| Inline `mmcif` template authoring | No | No | import supports it | Import/round-trip yes; authoring no (F-03) |
| Template index validation | `parse_pair_text` (shape + query range) then service | `parse_pairs` (split only) then service | service `_validate_pairs` | CLI pre-validates shape locally; GUI relies on the service and shows its refusal in the dialog — net rule set is the service's, so behaviour matches |
| Custom CCD | 4 options; Add ≡ Edit | 3-state radio + Apply/Clear | `set/clear_component_definition` | CLI duplicates Add/Edit (F-06) |
| Covalent bonds | **Not offered** | Full add/remove/list | `add_linkage`/`remove_linkage` | GUI-only capability (F-10) |
| Batch from file | Yes | Yes | `plan_input_batch`/`generate_input_batch`/`inspect_input_file` | The most shared flow; identical kind list, preview wording, folder default, counting |
| Plan-before-write of the base job | No (Save writes directly; refusal shown after) | Yes (`Preview plan` + tables) | `plan_base`/`execute` | CLI has no dry-run/review of the output (F-11) |
| Read-only JSON view | No | `PreviewPage` exists, **hidden** | `GenerationService.show_json` (`:226`) | Unreachable in the GUI; absent in the CLI (F-04) |
| Validation on demand | Only implicitly at save | Overview **Validate** button | `ValidationService.validate_all`/`validate_base` | CLI cannot inspect findings without attempting a save |
| Error display | Printed sentences + status line | Status bar + modal boxes | service messages | Both show the service's own text |
| Unsaved-changes protection | Prompt on leaving the job | Prompt on New/Open/Close | model dirty flag | Same intent |
| Output-count reporting | `batch_counts`/`batch_summary` | Same strings | `app/results.py` + `present/strings.py` | Aligned (recent fix) |

---

## 6. User-input requirements per workflow

Legend: **User** = must be supplied, **Inherited** = taken from the current job,
**Auto** = derived by the application, **Required but unchecked** = the builder does not
verify it and downstream AF3 may reject it, **Unsupported** = not accepted by this
workflow.

| Workflow | User | Inherited | Auto | Required but unchecked | Unsupported |
| --- | --- | --- | --- | --- | --- |
| New job | Name (optional) | — | Name (`Untitled job N` + slug), seeds `[1]`, version `auto` | Final AF3 acceptance | — |
| Open JSON | File path | — | Identity re-derived from `id` fields | Chemistry of a SMILES ligand beyond the bundled grammar probe | Unknown-but-tolerable root/entity fields are only *noted*, not modelled (`ImportNote`) |
| Rename | New name | — | Slug for the file name | — | — |
| Seeds | Digits, or a count | Current list as the default | Generated values | AF3's own preferred seed set | Whatever AF3 forbids is not checked |
| Version | `1`–`4` or auto | Current pin | Provenance (`Pinned`, `evidence=None`) | That a pin is *correct* for the deployment | Version 5+ (rejected) |
| Add protein | Sequence | — | Identifiers, chain ID from the registry | Biological validity; PTM sites' meaning | Non-alphabetic sequences refused |
| Add RNA | Sequence (A/C/G/U) | — | Identifier | Ribosomal/chemical plausibility | `T`-containing RNA refused |
| Add DNA | Sequence (A/C/G/T); CLI: duplex yes/no | — | Identifiers for both strands; reverse complement (CLI choice, GUI always) | — | Whichever is not selected in CLI (lone strand in GUI, F-01) |
| Add ligand (SMILES) | SMILES text; copies; GUI: description | — | Identifier(s), file-name key for batches | Real chemistry (the bundled probe is a grammar check only) | A missing representation is refused |
| Add ligand (CCD) | One or more component codes | — | Identifier(s) | **That the code exists in the CCD dictionary** (no dictionary is consulted) | Empty code refused |
| Edit entity | New sequence/description/representation | Current values as defaults | — | Same as above | Copy-count changes (both front ends) |
| Delete entity | Confirmation | Partner/copies resolved by the service | Identifier release | — | — |
| PTM add | Code + 1-based position | Entity list | — | **That the residue/PTM is chemically valid** (explicitly out of scope: R-POL-005/006) | Position beyond the sequence is refused (R-ENT-007) |
| MSA | Mode; file(s) or inline text | Current mode | Where the fields land | That the A3M is a *good* alignment (only shallow checks: R-MSA-003/004/005) | Paired/unpaired with a source for `automatic`/`free` |
| Templates | mmCIF path per template; `q:t` pairs; route | Current route/rows | Rebasing relative paths | **That indices map to the real residues of the template structure in the CLI** (no structural parse there); the service checks shape and query range | Inline `mmcif` authoring |
| Custom CCD | Inline CIF text **or** a file path | — | — | That the CIF content is well-formed beyond non-emptiness (`R-ROOT-007` covers only the XOR) | Both at once |
| Bonds (GUI) | Two endpoints (entity, residue, atom) | Entity list | — | That the atoms exist in the referenced component | SMILES-only ligand as an endpoint (R-BND-002) |
| Save | Destination | Source file or job name | File name from the job name (slug) | — | Fields the model cannot represent |
| Batch generate | Kind, file, folder | Base job + its entities | Keys/labels per entry, directory per entry, `manifest.json`, asset copies | Same per-kind questions as above | FASTA, duplicate entries, mixed entry kinds in one file |
| Generate (GUI) | Folder, policies | Job | `<job>/<job>.json` | — | Manifest (deliberately none) |
| Dependency check | — (double-click) | Project metadata | Statuses per check | Remote AF3 stack (out of scope by design) | AF3 inference environment |

---

## 7. Input-format support matrix

Readers live in `configbuilder/persistence/sequences.py` (documented in its module
docstring) and are the only file parsers for batch input.

| Kind | Accepted file | Per-line syntax | Blank lines | `#` comments | Duplicates | Named entries |
| --- | --- | --- | --- | --- | --- | --- |
| `protein-sequence` | `.txt` | one complete sequence per line; surrounding whitespace stripped | ignored | **not** comments — a `#` line is an invalid entry reported with its line number | refused (`duplicate protein sequences`) | no naming; keys are `batch_NN` |
| `dna-sequence` | `.txt` | one strand per line, 5'→3' | ignored | not comments | refused | no |
| `rna-sequence` | `.txt` | one sequence per line (A/C/G/U) | ignored | not comments | refused | no |
| `ligand-smiles` | `.smiles` or `.txt` | `NAME SMILES` (first whitespace splits) **or** a bare `SMILES` (name becomes `ligand_N`) | ignored | comments (skipped) | duplicate SMILES refused | yes: the name becomes the spec key (slugged) and the summary label |
| `ligand-ccd` | `.txt` | one ligand per line as component code(s); tokens split on whitespace, comma or semicolon → **one multi-component ligand** | ignored | comments (skipped) | duplicate entries refused | no |

Additional format rules, source-confirmed:

- Windows and Unix line endings both work (`splitlines()`).
- UTF-8 is required; a non-UTF-8 file is refused with `… is not UTF-8 text`.
- A directory given where a file is expected is refused with a path-specific message.
- **FASTA is not supported.** Any entry line starting with `>` triggers a dedicated
  refusal that names the header line and tells the user to write one sequence per line
  (`app/batch_variants.py`, the `headers` branch in `batch_specs_for_sequences`). Headers
  are never stripped.
- Sequences are validated by the model's alphabets (`SequenceText`), ligands by the
  bundled SMILES grammar (`validation/smiles.py:notation_problem`); the batch refuses
  whole-file if any line fails, naming every offending line.
- CCD codes are stored as `ccdCodes` (`ByCode`), never as a notation — the defect the
  earlier ligand-file flow had.

---

## 8. File-processing inventory

| Workflow | File/path or pattern | Role | Selected by user? | Reader/writer | Parsed, copied or referenced | Modified? | Required afterward? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Open JSON | `*.json` (AF3 input) | Source job | Yes | `persistence` (`load_project`) via `from_wire` | Parsed | **No** (`import_json_commit` documents this) | Only if the user keeps re-saving over it |
| Save job | `<dest>/<slug>.json` | Output | Yes (destination) | `output.execute` | Written | Created | For AF3 inference |
| Save job with external refs | `<dest>/assets/*` | Copied resources | No (policy) | `output.execute` (copy) | Copy + rewritten relative path | Created | Yes, with the JSON |
| Batch generate | `<root>/<job>/manifest.json` | Run report (builder-side; AF3 does not read it) | No | `output.manifest`/`execute` | Written | Created | Optional |
| Batch generate | `<root>/<job>/<job>__<key>/<job>__<key>.json` | One AF3 input per entry | No (derived) | `output.execute` | Written | Created | Yes |
| Batch generate | `<root>/<job>/<job>__<key>/assets/*` | Copied MSA/template/CCD resources | No | `output.execute` | Copied, JSON rewritten to a relative path | Created | Yes |
| Batch input | `.smiles` / `.txt` list | Entries | Yes | `persistence.read_*_file` | Parsed | No | Only for a re-run |
| Template attach | `*.cif` / `*.mmcif` | Template structure | Yes | `app/reference_validation.file_issue` (existence/readability) + `persistence/mmcif.py` (lexical, optional Gemmi) | Referenced (`mmcifPath`) or copied | No | Yes (or copied into `assets`) |
| Inline template | `mmcif` text in the JSON | Template structure | Only via import | `from_wire` | Parsed, kept inline | No | Travels inside the JSON |
| MSA attach | `.a3m` (protein/RNA) | Alignment | Yes | existence/readability check | Referenced (`unpairedMsaPath`/`pairedMsaPath`) or copied | No | Yes (or copied) |
| Inline MSA | text | Alignment | GUI only | `from_wire`/`to_wire` | Kept inline | No | Travels inside the JSON |
| Custom CCD | inline CIF text or `*.cif` path | `userCCD`/`userCCDPath` | Yes | `set_component_definition`; path rebased on import | Inline kept, path referenced/copied | No | Yes (or copied) |
| Job re-open | saved job JSON | Round trip | Yes | `from_wire` | Parsed | No | — |
| Preferences | `%APPDATA%\AF3Builder\preferences.json` | Remembered output folders | No | `app/paths.py` | Parsed/merged | Updated after a successful save/generate | Optional (defaults apply without it) |
| Dependency check | `pyproject.toml`, package metadata | Declared requirements | No | `tools/check_dependencies.py` | Parsed (read-only) | No | Yes for setup |
| Setup | `.venv`, editable install | Environment | No (one click) | `setup_windows.bat` | Created/installed | Yes (environment only) | Yes to run |

**What must remain available during generation:** every external resource referenced by the
current job (MSA files, template mmCIFs, CCD files) — the planner reads them to copy them.
**What must accompany the JSON to another machine:** with the default
`PathPolicy("CopyIntoAssets")`, the output's own `assets\` folder. With
`RelativeToOutput`/`AsGiven` the JSON keeps a path outside its folder, so the referenced
files must be copied with the same relative layout (documented in `README.md`). Inline
MSA, inline `mmcif` and inline `userCCD` need nothing else.
**Builder-only files:** `manifest.json`, `preferences.json`, the whole `.venv`, and the
input list.

---

## 9. Validation and error-handling matrix

Rule catalogue: 45 `Rule(...)` records in `configbuilder/validation/catalogue.py`
(tiers STRUCTURAL → RELATIONAL → CONTRACT → VARIANT → PREFLIGHT; severities
ERROR/WARNING/INFO). Save, preview and generation gate on
`GATE_TIERS = (STRUCTURAL, RELATIONAL, CONTRACT, PREFLIGHT)`
(`validation_service.py:30`); VARIANT rules only appear in the full-catalogue review.
`ConfigurationStatus.ready` is defined as "no blocking findings" from that same set
(`app/status.py:171`), so the readiness line and the save gate cannot disagree.

| Situation | Checked? | Where | Behaviour |
| --- | --- | --- | --- |
| Empty / whitespace name | Yes | R-ROOT-002; `set_name` | Refused with a message |
| No seeds / out-of-range seed | Yes | R-ROOT-004/005 | Blocking finding |
| Unknown entity family | Yes | R-ENT-001; `add_record` | Refused |
| Duplicate entity IDs | Yes | R-ENT-002 (identity registry) | Refused at allocation |
| Lowercase/non-alphabetic ID | Yes | R-ENT-003 | Finding |
| Protein alphabet (A–Z letters) | Yes | R-ENT-004 + `SequenceText` | Refused per line/file |
| RNA alphabet, DNA alphabet | Yes | R-ENT-005/006 | Refused |
| PTM position outside the sequence | Yes | R-ENT-007 | Refused |
| PTM code starting `CCD_` | Yes | R-ENT-008 | Refused |
| Ligand with both codes and SMILES, or neither | Yes | R-ENT-009 | Refused |
| Protein with only one of unpaired/paired MSA | Yes | R-ENT-010 | Blocking |
| Inline MSA **and** path set for one field | Yes | R-MSA-002 | Blocking |
| Templates on a non-protein chain | Yes | R-MSA-003 | Warning |
| External MSA file missing / unreadable / empty | Yes | R-MSA-006 + CLI `_msa_file_problem` | Refused before commit (CLI) / blocking (validation) |
| A3M shape plausibility | Shallow only | R-MSA-003/004/005 | Warning; explicitly advisory |
| Template with both `mmcif` and `mmcifPath` | Yes | R-TPL-002 + `from_wire` | Refused with an actionable message |
| Template row with neither | Yes | `from_wire._import_references` | Refused |
| Empty inline `mmcif` text | Yes | `from_wire` | Refused |
| Index arrays of unequal length | Yes | R-TPL-004 | Blocking |
| Negative / non-integer index | Yes | R-TPL-003, `parse_pair_text` | Refused |
| Negative/zero or out-of-range **query** index | Yes | R-TPL-003 + `parse_pair_text(sequence_length)` | Refused |
| **Template** index beyond the template's own residue count | **CLI: no** (no structural parse); GUI: service-level only | `menus.py:1065-1070`; `persistence/mmcif.py` | Not verified in the CLI; the mmCIF is only scanned lexically (Gemmi adds strictness when installed) |
| Template correspondence to the actual residues (unresolved residues) | Not established | — | Out of the current checks |
| More than 20 templates | Yes | R-TPL-005 | Blocking |
| SMILES grammar | Yes (bundled probe) | R-ENT-010 preflight via `validation/smiles.py` | Refused when clearly not SMILES |
| SMILES chemistry / real molecules | **No** | — | The probe is grammar only; the report says so |
| CCD code exists in a dictionary | **No** | — | No dictionary is consulted; downstream AF3 decides |
| Custom CCD XOR (`userCCD` vs `userCCDPath`) | Yes | R-ROOT-007 | Blocking |
| Custom CCD content well-formed CIF | No | — | Only non-emptiness is enforced |
| Bond endpoint resolvable to entity/residue/atom | Partial | R-BND-003 | Blocking only on shape/structure, not on the atom existing in the component |
| SMILES-only ligand as a bond endpoint | Yes | R-BND-002 | Refused |
| Polymer–polymer covalent bond | Yes | R-BND-006 | Refused as unsupported |
| Output file already exists | Yes | `output.policies` (`Fail` default) | Whole batch refused; `Skip`/`Overwrite`/`Versioned` available |
| Permission / filesystem failure mid-write | Partial | `output.execute` (atomic per-file writes) | Per-file errors reported; earlier files remain. **No batch transaction** |
| Malformed JSON / wrong dialect / unknown type | Yes | `transform/from_wire.py` | Refused with a reason; current job untouched |
| Unknown-but-tolerable field | Noted | `ImportNote` | Shown before Import; user decides |
| Non-UTF-8 or directory-as-file input list | Yes | `persistence/sequences.py` | Refused with a path-specific message |
| FASTA input | Yes (diagnosed) | `batch_variants` header branch | Refused with an explanatory message; headers are never stripped or reinterpreted |
| Duplicate entries in a batch file | Yes | `batch_variants` | Whole file refused |
| Empty file / no usable lines | Yes | readers + `BatchError` | Refused |
| A mislabelled file (e.g. sequences chosen as SMILES) | Diagnosed | `sequence_family_for` + refusal hints | Refused, with an advisory hint; never silently reinterpreted |
| User cancels at any prompt | Yes | `_select`/`_ask_destination`/dialog Cancel | Nothing written; base unchanged (documented "all-or-nothing" planning) |
| Save/generate with a job that fails the gate | Yes | `_gate_base` | Refused; status block printed (CLI) / refusal message (GUI) |

Input parsing, application validation, structural JSON validation, chemical validation and
AF3 inference are separate layers here: `persistence` parses text, `model` enforces
alphabets and shapes, `validation` applies the catalogue, `transform` produces wire JSON,
and nothing in this repository runs inference. JSON serialization success is **not**
evidence of chemical correctness or of a valid AF3 run.

---

## 10. External dependency and resource requirements

| Layer | Requirement | Evidence |
| --- | --- | --- |
| Core builder | Python ≥ 3.9, standard library only (`dependencies = []`) | `pyproject.toml:14` |
| GUI | `PySide6>=6.6` via the `gui` extra (3.10+ recommended) | `pyproject.toml:[project.optional-dependencies].gui` |
| Template strictness | `gemmi>=0.6` via the `templates` extra; a lexical mmCIF scan exists without it | `pyproject.toml` + `persistence/mmcif.py` |
| Development | `pytest>=7`, `hypothesis>=6` via `dev` | `pyproject.toml` |
| Comparative analysis (out of scope here) | `analysis` extra | `pyproject.toml` |
| External files at generation time | MSA `.a3m`, template `.cif/.mmcif`, custom CCD `.cif` | `output.plan`/`execute`, `PathPolicy` |
| AF3 inference | Model weights, GPU drivers, server software — **not** installed, not needed, and deliberately excluded | `README.md`, `setup_windows.bat` message |
| Optional local chemistry check | None; the bundled probe is a grammar check | `ui/services.py` comment, `validation/smiles.py` |

The dependency checker (`tools/check_dependencies.py`) reports PASS / MISSING /
INCOMPATIBLE / OPTIONAL / WARNING, is read-only, and returns non-zero when a required
check fails. It separates the local builder from the remote AF3 environment.

---

## 11. Known defects, inconsistencies and usability issues

Severity: **Critical** (invalid output / data loss), **High** (feature unreachable or
wrong in a supported case), **Medium** (confusing or inconsistent), **Low** (cosmetic or
documentation).

### F-01 — The GUI cannot create a single-stranded DNA entity (High, source-confirmed)
`EntitiesPage.add_dna` (`pages/entities.py:506`) → `_add_sequence("dna")` →
`state.add_record("dna", sequence=…)` with no `duplex` argument, so
`ConfigurationService.add_record`'s default `duplex=True` applies and **two** records are
created. The CLI asks (`_add_dna_with_complement_choice`, `menus.py:877`) and passes the
answer; `duplex=False` is a supported model state (the docstring calls it "the same lone
record an imported single-chain DNA entity produces"). Consequence: a GUI user cannot
produce a single-strand DNA job, and cannot predict the entity count. Minimal correction:
add the same two-option question (or a checkbox in `SequenceFormDialog` for DNA) and pass
`duplex` through `GuiState.add_record`.

### F-02 — The GUI cannot give protein `both`-mode MSAs two distinct sources (Medium)
`AlignmentFormDialog` collects one `(mode, source_kind, source_text)`
(`advanced_forms.py:299`) and `_apply_alignment` (`pages/advanced.py:857`) sends exactly
one source. `set_alignment` accepts `paired_inline_text`/`paired_external_path` and the CLI
collects both files (`menus.py:1007-1050`). Consequence: a paired alignment whose paired
side differs from the unpaired side cannot be expressed in the window. Minimal correction:
when the mode is `both`, show the second source pair (file/text) and pass it.

### F-03 — Inline `mmcif` templates are import-only (Medium)
`from_wire` round-trips inline templates correctly, but `TemplateEditorDialog` rows are
file-picker-only (`advanced_forms.py:382`) and the CLI always asks for a path
(`_ask_template_file`, `menus.py:1100`). Consequence: a user with an inline template can
keep it, but cannot author one, and editing an imported inline template in the GUI will
replace it with a path row if they accept the dialog. Minimal correction: allow a
paste-text row per template, or refuse-to-edit-loses-inline explicitly.

### F-04 — The read-only JSON view is unreachable, in both front ends (Medium)

`MainWindow` constructs `PreviewPage`, calls `.hide()` and documents that it "is not a
destination, not in the sidebar and not reachable from any button"
(`main_window.py:192-200,749`). The capability itself is wired —
`GuiState.preview_json` (`state.py:422-429`) calls
`GenerationService.show_json` (`generation_service.py:226`) and `PreviewPage.refresh`
renders it — but no control anywhere else calls it, and the CLI never prints the
document. Consequence: the user's only way to see the exact JSON is to write it to disk.
Minimal correction: a "Preview JSON" disclosure on the Generate page (and, optionally,
the same text in the console's summary).

### F-05 — CLI entity deletion drops the service's duplex warning (Medium)
`_delete_entity_key` (`menus.py:1220-1236`) asks `Delete "A"?` and prints
`Removed 'A'.`, ignoring `MutationOutput.message`. `remove_record` returns
`"the DNA duplex and its partner strand were removed"` and deletes both records; the GUI
names the partner first (`gui.delete_duplex`, `pages/entities.py:679`). Consequence: a
console user can remove two entities believing they removed one. Minimal correction: use
the service message (or the GUI's wording) in the confirmation and the result line.

### F-06 — `Add` and `Edit` custom CCD are the same action (Low, DUPLICATED)
`_custom_ccd_menu` (`menus.py:1300-1306`): choice `2` and choice `3` both call
`_add_ccd_definition()`, which never pre-fills the current inline text or path. Minimal
correction: pre-fill the current definition for `Edit` (or collapse to one option).

### F-07 — `set_job_description` is unreachable (Low)
Implemented at `configuration_service.py:181`, called by nothing in `configbuilder/ui`
(verified by call-site search). No front end offers a job-level description, and AF3's
textual description fields are version-gated (`DESCRIPTION_MIN_VERSION = 4`). Minimal
correction: either surface it in the Overview job details (with the v4 note the entity
form already uses) or remove the method.

### F-08 — Ligand descriptions cannot be set in the console (Medium)
The GUI's `LigandFormDialog` collects a description (`entity_forms.py:152`); the CLI's
`_add_entity` and `_edit_entity_fields` never pass one for ligands
(`menus.py:831-870, 1177-1210`). Since descriptions are only written in JSON v4, the
practical effect is a version-dependent difference between the two front ends. Minimal
correction: one optional prompt in the ligand add/edit flow.

### F-09 — The console cannot paste an inline MSA (Low)
`_chain_msa` only accepts file paths for protein/RNA (the multiline paste path exists for
custom CCD, `_add_ccd_definition`). The GUI offers inline text. Minimal correction:
reuse `read_multiline` for the MSA source, mirroring the CCD flow.

### F-10 — Covalent bonds exist only in the desktop window (High, feature gap)
`grep -i bond configbuilder/ui/render/menus.py` finds nothing; `add_linkage` /
`remove_linkage` are called only from `pages/advanced.py`. `bondedAtomPairs` is part of the
AF3 contract (R-BND-001..006), so the console cannot produce a job with explicit bonds at
all. Minimal correction: a job-level "Covalent bonds" submenu in the console mirroring the
GUI's add/remove, using the same service calls.

### F-11 — The console writes without a reviewable plan (Medium)
Save goes straight to `plan_save` + `execute` with no dry run; the only review surface is
the summary printed *before* the destination prompt (`_save_and_summary`). The GUI has
`Preview plan` with file/asset/finding tables. Consequence: in the console a blocking
finding is discovered only after choosing a file name. Minimal correction: print the plan
(entries, assets, conflicts) and ask for confirmation, as the batch flow already does.

### F-12 — Legacy batch API still `base + AddRecord` commit semantics (Medium, PARTIALLY IMPLEMENTED)
`VariantService.generate_from_file` (`variant_service.py:1287`) commits specs **into the
open project**, unlike `GenerationService.generate_input_batch`, which writes independent
files and never touches the base. Its docstring labels it legacy, and the UI does not call
it — only `tests/e2e/test_app_pipeline.py`, `tests/e2e/test_manual_test_data.py` and
`tests/fixtures/af3_pipeline/generate_fixtures.py` do. Risk: a maintainer could mistakenly
treat it as the workflow. Minimal correction: migrate those callers to the generation
service, or keep it and add a deprecation note where it is exercised.

### F-13 — Dead UI modules (Low, OBSOLETE OR UNREACHABLE)
`configbuilder/ui/render/qt/pages/variants.py` (1453 lines) and
`dialogs/variant_forms.py` (937 lines) are imported by nothing (verified by search across
`configbuilder/` and `tests/`). They describe a variant/spec authoring UI that no longer
exists in the shell (the sidebar has three destinations). Risk: misleading future work and
a false impression that variant authoring is user-facing. Minimal correction: delete them
in a focused commit, or move them under a clearly named `legacy/` with a note.

### F-14 — Stale documentation in code (Low)
- `cli.py` docstring still says the menu has "six goal-oriented actions (edit, review,
  variants, generate, open saved work, import)" and "There is one front end"; the console
  now has a seven-item job menu and no variants action, and there *are* two front ends.
- `gui.py` module docstring and `missing_environment_message` describe the GUI as living in
  its own `.venv-gui` environment, while `VENV_DIRECTORY = ".venv"` is the primary path and
  `setup_windows.bat` installs the `gui` extra into `.venv`.
Minimal correction: refresh both docstrings/messages to the current layout.

### F-15 — `CopyIntoAssets` is the default, but the policy is hidden behind one disclosure (Low)
The Generate page's two policies live in a collapsed "Advanced options" section
(`pages/generate.py:224-256`) with the safe defaults selected, and the batch flow exposes
no policy choice at all (it uses `output_defaults()`). A user who needs `AsGiven` (keep
absolute references) or `Overwrite` cannot reach either from the batch action, and the
console never offers any policy choice. Minimal correction: mention the batch's fixed
policy in its preview text (it partly does, via `batch_preview_note`) and, if needed, add a
policy prompt to the console's batch flow.

### F-16 — Repeated entity edits force the MSA/template questions again (Low)
`_edit_entity_fields` (`menus.py:1177-1215`) always calls `_chain_msa` and, for proteins,
`_chain_templates`. A user changing a description walks three extra screens. Minimal
correction: ask once ("change alignment/templates too?") before the chained questions.

### F-17 — Entity copy counts are immutable after creation (Low)
Both front ends set copies only in the add flow; the GUI's edit form passes
`copies_editable=False` (`pages/entities.py:632`). The service has no copy-change method.
Consequence: a wrong count means delete-and-re-add (which for DNA removes the duplex).
Minimal correction: an explicit `set_copies` service operation, or document the
delete-and-re-add route.

### F-18 — No batch-level transaction (Medium, accepted limitation)
`output.execute` writes per file with atomic semantics per file, but a failure partway
through a run leaves the files already written. Both front ends report per-file errors
honestly, and the plan is all-or-nothing *before* writing. Minimal correction: either
document the partial-write recovery in the user guide (partly done) or stage into a
temporary directory and move on success — the latter needs care not to delete user data.

---

## 12. Review of existing test coverage (static; **not executed**)

Coverage status uses the requested vocabulary. No suite was run for this audit.

| Area | Likely coverage | Status |
| --- | --- | --- |
| Rule catalogue & engine | `tests/unit/validation/test_catalogue.py`, `test_engine.py`, `test_rule_checks.py`, `test_identity_conversion.py` | Tests present; not run for this audit |
| SMILES grammar probe | `tests/unit/validation/test_smiles_notation.py` | Tests present; not run |
| Transform to/from wire (incl. inline templates) | `tests/unit/transform/test_from_wire.py`, `test_to_wire.py`, `test_mappings.py`, `test_resource_path_rebase.py` | Tests present; not run |
| Persistence round trip, corruption, versions | `tests/unit/persistence/test_round_trip.py`, `test_versions_and_corruption.py`, `test_mmcif.py` | Tests present; not run |
| Input file formats | `tests/unit/persistence/test_sequence_files.py` | Tests present; not run |
| Batch specs & counts | `tests/unit/app/test_batch_variants.py`, `test_batch_summary_counts.py`, `test_dna_duplex.py` | Tests present; not run |
| Paths / output defaults | `tests/unit/app/test_paths.py`, `tests/unit/ui/test_output_defaults.py`, `tests/gui/test_output_defaults.py` | Tests present; not run |
| Output planning/execution/manifest/naming | `tests/unit/output/*` | Tests present; not run |
| Console menu flows | `tests/unit/ui/test_menu.py`, `test_numbered_flows.py`, `test_msa_flow.py`, `test_template_flow.py`, `test_audit_regressions.py`, `test_p1_fixes.py` | Tests present; not run |
| GUI pages and shell | `tests/gui/*` (19 modules incl. `test_entity_management.py`, `test_advanced_settings.py`, `test_generate_output.py`, `test_template_attachment.py`, `test_file_generation.py`, `test_import_flow.py`) | Tests present; not run |
| End-to-end console runs | `tests/e2e/test_menu_acceptance.py`, `test_variant_cli_subprocess.py`, `test_entity_batch_cli_subprocess.py`, `test_template_cli_subprocess.py`, `test_app_pipeline.py`, `test_entity_lifecycle.py` | Tests present; not run |
| Manual test data as a contract | `tests/e2e/test_manual_test_data.py`, `tests/gui/test_manual_test_data_gui.py` | Tests present; not run |
| Architecture rules (layering, one entry point) | `tests/architecture/*` (10 modules) | Tests present; not run |
| Launchers & dependency diagnostics | `tests/unit/test_launchers.py`, `tests/unit/test_dependency_diagnostics.py` | Tests present; not run |
| Covalent bonds (GUI) | only indirectly (`tests/gui/test_advanced_settings.py`) | Coverage unclear from static inspection; no bond-specific module found by name |
| Console bond support | — | **No relevant test located** (the feature does not exist) |
| Single-stranded DNA via the GUI | `tests/unit/app/test_dna_duplex.py` covers the service; no GUI add-DNA duplex test found | Coverage unclear from static inspection |
| `both`-mode MSA with two distinct sources | CLI path likely in `tests/unit/ui/test_msa_flow.py`; no GUI equivalent apparent | Coverage unclear from static inspection |
| Inline-MMA round trip / authoring | import covered by `test_from_wire.py`/`test_mmCIF`; authoring does not exist | No relevant test located for authoring |
| Dead modules `pages/variants.py`, `dialogs/variant_forms.py` | no importing test found | **No relevant test located** (consistent with dead code) |
| Historical reports | `docs/CONFIGURATION_GENERATION_FIX_REPORT.md`, `docs/GUI_AUTOMATED_QA_REPORT.md`, `docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` | Previously reported passing; current commit not independently verified |

Highest-value *future* tests (not added here): a GUI add-DNA duplex-choice test, a
GUI `both`-MSA-two-sources test, a console bond flow (once it exists), a CLI delete-duplex
wording test, and a "save with no plan review" console test if the summary is upgraded.

---

## 13. Practical user walkthroughs

Every step uses the shipped labels. Behaviour not established statically is marked
**verify manually**.

### W-1 — Install, check, start
1. Put the folder under your profile, e.g. `C:\Users\<you>\AF3Builder` (not
   `C:\Program Files`).
2. Double-click **`setup_windows.bat`** → wait for `SETUP SUCCEEDED`.
3. Double-click **`check_dependencies.bat`** → expect `READY` and exit 0.
4. Double-click **`run_gui.cmd`** (window) or **`run_console.cmd`** (text menu).
   Failure to start prints the reason and waits for a key.
*Output/state:* `.venv` plus the installed package; nothing user-facing is written.

### W-2 — Create or open a job
- Console: `1. New job` → type a name (blank generates one). Or `2. Open a JSON file` →
  the numbered listing, a full path, or a folder then a file.
- Window: **New** (Ctrl+N) or **Open** (Ctrl+O) → the *Review the file before opening it*
  dialog → **Import**.
*Expected state:* the job name appears in the header/`JOB MENU`; entities are listed.
*Common failures:* `Could not open this JSON. Reason: …` plus `The original file has not
been modified.` (malformed file, unsupported dialect, an entity the model cannot
represent). Fields the builder does not model are listed as notes before Import.

### W-3 — Job settings
- Console: `1. Edit job configurations` → `1. Job name` / `2. Model seeds` (specific
  values or a count) / `3. JSON version`.
- Window: **Overview → Job details** → edit a field → **Apply**.
*Expected:* the header/summary reflects the change immediately. Version choices outside
1–4 are refused.

### W-4 — Add and edit entities
- Console: `2. Add entity` → `1. Protein` / `2. DNA` / `3. RNA` / `4. Ligand`. Protein and
  RNA then ask the MSA question and (protein) the template question. DNA asks the
  complement question. Ligand asks CCD-or-SMILES, the value, then the copy count.
  `3. Edit entity` → pick the entity → `1. Edit` / `2. Delete` / `3. Modifications`.
- Window: **Entities** → **Add Protein/RNA/DNA/Ligand**; **Edit entity** /
  **Delete entity** for the selected one; the settings groups below the details card.
*Expected:* one new entry in the picker/list per add (two for DNA duplex or a multi-copy
ligand). Blank answers keep current values when editing.
*Known gap:* in the window, **Add DNA** always creates the complementary strand (F-01).

### W-5 — Ligands by SMILES and by CCD code
SMILES: add a ligand, choose the SMILES option, type e.g. `CCO`, copies `1`.
CCD: choose the CCD option, type e.g. `ATP` or `NAG NAG BMA MAN MAN` for one
multi-component ligand.
*Expected inside the file:* a SMILES ligand becomes `"smiles": "CCO"`; a CCD ligand becomes
`"ccdCodes": ["ATP"]`. CDD codes are never stored as notation.
*Common failure:* text that is neither recognizable SMILES nor a plausible code — the CLI
asks again, the GUI shows the refusal in the form. No dictionary check exists, so a
mistyped but well-formed code is accepted here and rejected later by AF3.

### W-6 — Structural templates and MSA
Templates: select the protein → templates question/`Edit templates` → route:
*search* (no `templates` entries), *none* (explicit empty), or *list* → for each template,
choose an mmCIF file and type pairs such as `0:5,1:6,2:7` (0-based).
MSA: *Change alignment* → mode (`Let AlphaFold search…`, `Unpaired only`, `Paired only`,
`Both`, `No MSA…`; RNA: `Provided`) → inline text or file.
*Expected in the file:* `mmcifPath` plus `queryIndices`/`templateIndices`; `unpairedMsa`,
`pairedMsa`, or their `…Path` forms; RNA gets a single `unpairedMsa`/`…Path`.
*Common failures:* a missing/unreadable/empty MSA file is refused; pairs not shaped
`q:t`, or a query index beyond the sequence, are refused; a template row with both
`mmcif` and `mmcifPath` is refused.
*Limitation:* the console does not parse the mmCIF, so a **template** index that is out of
range for the structure itself is not caught there (see the validation matrix in §9).

### W-7 — File-based configuration generation
- Console: `7. Generate configurations from a file (sequences or ligands)` →
  `1. Load an input file and generate configurations` → choose the kind → choose the file →
  review the count/entries → accept the offered output folder (or type another).
- Window: **Entities → Generate configurations from file...** → kind → file → folder
  (pre-filled with `generated_configurations`) → review → accept.
*Prerequisites:* a base job with at least one entity; a text file in the format of §7.
*Expected output:* `<output root>\<job>\<job>__<entry>\<job>__<entry>.json` per entry, plus
`manifest.json`, plus `assets\` where external files were referenced, and a summary such as
`Generated 4 AF3 configurations. Wrote 1 manifest. Total output files: 5.`
*Common failures:* FASTA (explicit message), duplicate entries, an empty file, a line
outside the chosen kind's format (all named with line numbers), or an existing conflicting
output file (the whole batch is refused; choose another folder).
*Base safety:* the open job is never modified; the same run can be repeated from the same
base.

### W-8 — Save the finished configuration
- Console: `6. Save and show summary` → read the summary → accept the offered path or type
  one → confirm an overwrite if asked.
- Window: **Save JSON…** (Ctrl+S) → choose the destination → confirm if asked.
*Expected:* one JSON file, plus `assets\` when the job references external files. The CLI
prints `Saved to <path>`; the GUI shows the status line.
*Common failure:* a job that fails the gate prints `This job cannot be saved yet:` followed
by the status block (`MISSING`/`INVALID` rows and `STATUS: INCOMPLETE`) — fix the named
field and save again. Nothing is written.

### W-9 — Inspect findings and recover
- Window: **Overview → Validate** → the findings list (severity, where, message) or the
  readiness line `Ready — nothing blocks generation.`
- Console: attempt a save; the refusal prints the blocking findings.
*Expected:* each finding names the field and says what to fix. Fixing an entity and saving
again is the whole recovery loop.
*Note:* there is no JSON view to inspect before writing (F-04) — save to a scratch folder
to read the result.

### W-10 — Transfer to the inference server
Copy `generated_configurations\<job>\<job>__<entry>\` (the JSON **with** its `assets\`)
to the Linux environment. Do not copy a JSON whose paths point outside its own folder
unless those files are copied with the same relative layout. `manifest.json`, the
builder, `.venv` and the input list are not needed.

---

## 14. Prioritized recommendations

Each item: why, what changes, expected behaviour, main regression risk, focused
verification for a future implementation task. Nothing here was implemented.

### P0 — Correctness and data integrity
1. **F-05 — Name the DNA partner before a console delete.** *Why:* deleting one strand
   removes two records; the console currently does not say so, which risks unintended data
   loss. *Changes:* `menus._delete_entity_key` (use `outcome.message` / the GUI's wording).
   *After:* the confirmation and result name the partner and the copy count. *Risk:* a
   wording change could break tests asserting `menu.delete_confirm`/`menu.removed`.
   *Verify:* focused console test that deletes a duplex strand and asserts the wording;
   one test for a multi-copy ligand.
2. **F-01 — Let the GUI choose single- vs double-stranded DNA.** *Why:* the supported
   `duplex=False` model state is unreachable in the window; entity counts are surprising.
   *Changes:* `SequenceFormDialog` (DNA hint + duplex choice) and
   `EntitiesPage._add_sequence`/`GuiState.add_record` passing `duplex`. *After:* both
   front ends produce the same two shapes. *Risk:* the dialog is shared with protein/RNA (−
   keep the control DNA-only). *Verify:* a GUI test asserting one record for "single" and
   two for "duplex", plus the wire output.
3. **F-18 — Decide the batch partial-write contract.** *Why:* a mid-batch filesystem
   failure leaves earlier files. *Changes:* either document it firmly in the user guide or
   stage-then-move in `output/execute.py`. *After:* either honest documentation or a clean
   rollback that never deletes pre-existing files. *Risk:* aggressive cleanup could delete
   user data — prefer documentation unless staging is provably safe. *Verify:* an
   `output` unit test that injects a failure on the second file and asserts only files
   created by the run are considered.

### P1 — Core workflow completeness
4. **F-10 — Covalent bonds in the console.** *Why:* `bondedAtomPairs` is part of the
   contract and today only the window can produce it. *Changes:* a job-level bonds submenu
   in `menus.py` (add/remove/list) calling `add_linkage`/`remove_linkage`. *After:*
   equivalent capability in both front ends. *Risk:* new prompt flow could break console
   scripted tests — keep it off the numbered job menu used by existing tests if possible,
   or extend those tests deliberately. *Verify:* a console e2e script that adds a bond and
   reads the written JSON's `bondedAtomPairs`.
5. **F-04 — Make the generated JSON viewable before writing.** *Why:* users must write a
   file to see the document. *Changes:* surface `GenerationService.show_json` on the
   Generate page (a disclosure) and, optionally, print it in the console's summary.
   *After:* inspect-then-write in both front ends. *Risk:* large documents in a text widget;
   keep it read-only and lazily rendered. *Verify:* a GUI test asserting the view equals
   `show_json`.
6. **F-02 — Two sources for protein `both`-mode MSA.** *Why:* the service supports it and
   the console uses it. *Changes:* `AlignmentFormDialog` + `_apply_alignment`. *After:*
   `pairedMsa` and `unpairedMsa` can differ in the window. *Risk:* dialog layout/test
   churn. *Verify:* a GUI test that sets two files and asserts both wire fields.
7. **F-03 — Author inline templates (or make loss explicit).** *Why:* the format is
   supported on import but cannot be created, and editing can silently convert an inline
   template to a path row. *Changes:* a paste-text row in `TemplateEditorDialog` and an
   equivalent console option; or an explicit warning. *After:* no silent conversion.
   *Risk:* mmCIF text in a table cell is awkward; consider a per-row editor. *Verify:* a
   round-trip test (import inline → open editor → accept unchanged → still inline).

### P2 — Usability
8. **F-06 — Distinguish Add from Edit for custom CCD** (pre-fill the current definition).
9. **F-08 — Ligand description in the console** (one optional prompt; keep the v4 note).
10. **F-11 — Plan review before the console writes** (print entries/assets/conflicts and
    ask, as the batch flow does).
11. **F-09 — Inline MSA paste in the console** (reuse `read_multiline`, mirroring CCD).
12. **F-16 — One question instead of three on entity edit** ("also change alignment /
    templates?").
13. **F-15 — Make the batch's fixed overwrite/path policy visible** in the console's batch
    preview, and consider exposing the policy choice where it matters.
14. **F-14 — Refresh the stale docstrings/messages** (`cli.py`, `gui.py`,
    `missing_environment_message`).
15. **F-17 — Decide on copy-count editing** (add a service operation or document the
    delete-and-re-add route).

### P3 — Maintainability
16. **F-13 — Delete or quarantine the dead UI modules** `pages/variants.py` and
    `dialogs/variant_forms.py`. *Risk:* they may be referenced by documentation; check
    docs first. *Verify:* the full unit/GUI suites (they cannot regress if nothing imports
    them, but run the suites to prove it).
17. **F-12 — Retire or clearly demote `VariantService.generate_from_file`** by migrating
    the two e2e suites and the fixture generator to `GenerationService`. *Risk:* fixture
    generation changes → verify `tools/af3_validation/run_all.py` output stays identical.
18. **F-07 — Surface or remove `set_job_description`.**

---

## 15. Evidence appendix

Console front end — `configbuilder/ui/render/menus.py`
`_main_menu:546`, `_new_job:567`, `_open_json_file:576`, `_job_menu:613`, `_leave_job:650`,
`_edit_job_config_menu:673`, `_edit_seeds:703`, `_set_version:729`, `_add_entity_menu:796`,
`_ask_quantity:810`, `_ligand_kind:823`, `_add_entity:831`,
`_add_dna_with_complement_choice:877`, `_chain_msa:911`, `_chain_templates:980`,
`_collect_msa_choice:998`, `_ask_msa_file:1007`, `_msa_file_problem:1031`,
`_collect_references_for:1045`, `_collect_template_list:1065`, `_ask_template_file:1100`,
`_ask_template_pairs:1112`, `_edit_entity_menu:1125`, `_entity_action_menu:1142`,
`_edit_entity_fields:1177`, `_delete_entity_key:1220`, `_record_mod_menu:1237`,
`_custom_ccd_menu:1268`, `_add_ccd_definition:1315`, `_remove_ccd_definition:1346`,
`_ptm_menu:1367`, `_add_modification_to:1437`, `_edit_modification_on:1452`,
`_remove_modification_on:1478`, `_say_summary:1511`, `_save_and_summary:1543`,
`_write_json:1583`, `_file_menu:1640`, `_generate_from_file:1676`, `_say_status:1772`,
`FILE_KINDS:1621`, `_FILE_PROMPTS:1632`.

Wording registry — `configbuilder/ui/present/strings.py`
`menu.main_actions:58`, `menu.job_actions:87`, `menu.config_actions:110`,
`menu.add_entity_title:150`, `menu.ligand_kind_menu:165`, `menu.msa_choice_title:176`,
`menu.templates_menu:203`, `menu.ccd_actions:243`, `menu.ptm_actions:263`,
`menu.mod_actions:287`, `menu.file_kinds_title:349`, `menu.output_root_note:369`,
`gui.action_file_generation:469`, `gui.delete_duplex:598`, `gui.output_*:730-834`,
`gui.nav_section_workspace:887`.

Desktop front end
`windows/main_window.py`: `_build:108` (actions/shortcuts), `_build_shell:232`,
`_DESTINATIONS:226`, `_build_file_actions:298`, `new_job:396`,
`confirm_discard_changes:406`, `save_json:416`, `_report_save_refusal:465`,
`_blocking_message:483`, `open_json:509`, `offer_import:523`, `report_failure:551`,
`refresh:584`, `show_page:646`, `closeEvent:670`, `preview_page:749` (hidden).
`pages/entities.py`: `_build:192`, `_build_selector:213`, `generate_from_file:355`,
`add_protein:500`/`add_rna:503`/`add_dna:506`/`add_ligand:509`, `_add_sequence:532`,
`edit_selected:570`, `_edit_ligand:611`, `_apply_ligand_edit:641`, `delete_selected:665`,
`_delete_message:679`, `_description_warning:689`.
`pages/advanced.py`: `_PROTEIN_MODES:89`, `_RNA_MODES:96`, `change_alignment:825`,
`_modes_for:850`, `_apply_alignment:857`, `edit_templates:876`, `_apply_templates:891`,
`browse_ccd_file:919`, `apply_ccd:926`, `clear_ccd:950`, `parse_pairs:167`.
`pages/generate.py`: `_build:134`, `_build_scope_group:172`, `_build_destination_group:186`,
`_build_generate_group:238`, `_build_plan:262`, `browse_destination:400`,
`_apply_defaults:426`, `_default_destination:438`, `preview_plan:536`, `generate:706`,
`_show_result:757`, `copy_selected_path:696`.
`pages/settings.py`: `_build:81`, `apply_name:203`, `apply_seeds:213`, `apply_version:222`.
`pages/overview.py`: `_build:79`, `_build_readiness:140`, `validate_job:210`.
`pages/preview.py`: `_build:41`, `copy_text:72`, `refresh:81` (page hidden by the window).
`dialogs/`: `import_preview.ImportPreviewDialog:38`; `entity_forms.SequenceFormDialog:105`,
`LigandFormDialog:152`; `advanced_forms.ModificationFormDialog:114`,
`AlignmentFormDialog:164`, `TemplateEditorDialog:308`, `BondFormDialog:440`;
`batch_input.KIND_LABELS:47`, `choose_batch_kind:65`, `choose_batch_file:78`,
`choose_output_folder:94`, `confirm_batch_preview:101`, `report_batch_run:154`;
`messages.ask_save_path:132`.

Application services
`app/configuration_service.py`: `ReferenceInput:72`, `set_name:163`,
`set_job_description:181`, `set_seeds:202`, `add_record:227`, `_build_records:282`,
`update_record:384`, `remove_record:452`, `add_modification:503`,
`set_representation:603`, `update_component_record:622`, `set_alignment:664`,
`set_references:780`, `set_component_definition:821`, `clear_component_definition:831`,
`add_linkage:846`, `remove_linkage:861`, `set_format_target:879`.
`app/generation_service.py`: `show_json:226`, `output_policy_choices:269`,
`output_defaults:282`, `plan_selection:305`, `plan:376`, `plan_input_batch:616`,
`plan_ligand_batch:723`, `generate_input_batch:736`, `generate_ligand_batch:774`,
`plan_base:784`, `plan_save:917`, `execute:1046`, `_gate_base:122`.
`app/project_service.py`: `new:70`, `import_json_preview:172`, `import_json_commit:194`,
`open:262`.
`app/validation_service.py`: `GATE_TIERS:30`, `validate_configuration:79`,
`validate_base:98`, `status:108`, `validate_all:134`.
`app/variant_service.py`: `inspect_input_file:1214`, `generate_from_file:1287` (legacy).
`app/batch_variants.py`: `INPUT_KINDS:96`, `SEQUENCE_FAMILIES`, record builders
(`_protein_record`, `_dna_record`, `_rna_record`, `_ligand_record`, `_code_record`),
`ligand_specs_for_entries`, `sequence_family_for`, `batch_specs_for_sequences` (FASTA
header refusal, duplicate detection).
`app/paths.py`: `Preferences:85`, `OutputPaths:199`, `resolve_root:227`,
`saved_jobs:272`, `generated_configurations:268`, `save_directory:289`,
`batch_directory:303`, `default_save_path:312`, `default_batch_root:316`,
`remember_save_directory:322`, `remember_batch_directory:326`.
`app/status.py`: `ConfigurationStatus:154`, `ready:171`, field builders ~:255-341.
`app/results.py`: `MutationOutput:62`, `LoadOutput:88`, `ImportPreview:167`,
`FilePreview:189`, `GenerationPlan:250`, `BatchCounts:324`, `LigandBatchOutput:389`,
`PlanOutput:441`.
`app/version_features.py` (re-exports) and `transform/mappings.py:45-61`
(`MSA_PATH_MIN_VERSION=2`, `TEMPLATE_PATH_MIN_VERSION=2`, `USER_CCD_PATH_MIN_VERSION=3`,
`DESCRIPTION_MIN_VERSION=4`, `PATH_FEATURE_MIN_VERSIONS`).
`app/reference_validation.py`: `ReferenceIssue:76`, `parse_pair_text:147`,
`_validate_pairs:~180`.
`app/cli.py` (composition root), `af3builder.py`, `gui.py`, `build_services`
(`ui/services.py:46`).

Validation
`validation/catalogue.py`: `Tier`/`Severity`/`Evidence`, 45 `Rule(...)` records from
`R-ROOT-001` to `R-POL-007`.
`validation/rules/`: `root_rules.py`, `entity_rules.py`, `msa_rules.py`,
`template_rules.py`, `bond_rules.py`, `policy_rules.py` (`R-VER-*`, `R-POL-*`),
`variant_rules.py`; `validation/engine.py`, `validation/report.py`,
`validation/smiles.py`.

Transform / output / persistence
`transform/from_wire.py`: known-field tables `:78-94`, `ImportNote:100`,
`_import_references` (inline vs path, `:268-300`), ligand representation XOR `:329`,
`userCCD`/`userCCDPath` XOR `:479-493`, relative path rebasing `:565-572`.
`output/policies.py` (`OverwritePolicy`, `PathPolicy`, `Action`), `output/plan.py`,
`output/execute.py`, `output/manifest.py` (deterministic fields list),
`output/naming.py`.
`persistence/sequences.py` (module docstring = format contract; `parse_sequence_text`,
`parse_code_text`, `parse_smiles_text:138`, `read_sequence_file:115`, `read_code_file:96`,
`read_smiles_file:168`), `persistence/mmcif.py` (lexical scan + optional Gemmi),
`persistence/store.py`, `persistence/decode_model.py`/`encode_model.py`,
`serialize/encode.py`.

Tooling
`setup_windows.bat`, `check_dependencies.bat`, `tools/check_dependencies.py`,
`run_gui.cmd`, `run_console.cmd`, `README.md`, `DEPENDENCY_SETUP.md`,
`RUNNING_THE_APPLICATION.md`, `docs/AF3_BUILDER_INSTALLATION_AND_OUTPUT_AUDIT.md`,
`docs/AF3_BUILDER_INSTALLATION_OUTPUT_IMPLEMENTATION_REPORT.md`.

Commands used (read-only): `git branch/log/status`, `find`/`ls`/`wc`,
`grep -rn` for call-site and control enumeration, targeted `sed -n` windows, and one
read-only Python snippet that listed the rule catalogue's identifiers/tiers/severities.
No test runner, installer, server or AF3 command was executed.

---

## 16. Final summary

**What works according to the current implementation**

- One shared service layer drives both front ends; save, preview, generation and the
  readiness line all gate on the same rule tiers (`GATE_TIERS`), so the console and the
  window cannot disagree about whether a job can be written.
- Job lifecycle: new, rename, seeds (values or count), version pinning, import with a
  preview/confirm step, a gate that refuses to write an incomplete job, explicit overwrite
  confirmation, and unsaved-changes protection on every exit route.
- Entities: protein, RNA, DNA (duplex, and lone strand in the console), ligands by SMILES
  or one-or-more CCD codes, multi-copy ligands, per-entity descriptions (polymers and, in
  the window, ligands), PTMs with service-side position validation, and covalent bonds.
- File-based generation is fully shared: a single input-kind vocabulary, a read-only
  preview before any write, deterministic naming, a per-entry output directory with its
  own `assets\`, a manifest counted separately from configurations, base immutability, and
  a collision policy that refuses rather than silently overwriting.
- Validation: 45 catalogued rules across five tiers with ERROR/WARNING/INFO severities,
  including FASTA diagnosis, duplicate detection, alphabet checks, MSA/template
  mutual-exclusion rules, index-shape rules and preflight existence checks.
- Runtime independence: the core needs nothing but the standard library; PySide6 and Gemmi
  are extras; the AF3 inference stack is deliberately out of scope; setup and dependency
  checking are one-click and the checker is read-only.

**What is incomplete or potentially defective**

- F-01 GUI DNA always duplex (single-strand unreachable).
- F-02 GUI cannot send two distinct MSA sources for `both`.
- F-03 inline `mmcif` templates: import-only; editing can convert them to paths.
- F-04 the JSON preview exists and is unreachable; there is no way to read the document
  before writing.
- F-05 the console's entity delete silently removes a DNA partner and the copy set.
- F-06 CCD "Add" and "Edit" are the same call.
- F-07 `set_job_description` is dead; no UI offers a job description.
- F-08 no ligand description in the console.
- F-09 no inline MSA paste in the console.
- F-10 covalent bonds are GUI-only.
- F-11 the console writes without a reviewable plan.
- F-12 legacy `generate_from_file` still commits variants into the project.
- F-13 two dead UI modules (~2.4k lines) implying a UI that no longer exists.
- F-14 stale docstrings in `cli.py`, `gui.py`.
- F-15 batch output policy is neither shown nor selectable in the console.
- F-16 entity edit forces the MSA/template questions again.
- F-17 copy counts are immutable after creation.
- F-18 no batch-level transaction (per-file atomic writes only).

**What cannot be confirmed without running the application or tests**

- Any statement about on-screen layout, focus order, rendered wording or modal behaviour.
- That the GUI's `both`-mode alignment, template editor, bond form and batch dialogs
  produce the exact wire output claimed by their call chains.
- That the console's scripted flows still match the numbered prompts (menu numbering is
  read from strings, not from a run).
- That uninstalling Gemmi actually degrades template checking gracefully at runtime
  (the fallback is read from `persistence/mmcif.py`, not exercised).
- Whether any currently passing suite still passes at `9baa3ab`, and whether the
  historical reports' results apply to this commit.
- Actual AF3 acceptance of any generated document: no inference was run, and no AF3
  parser was invoked.

**Recommended next steps (smallest → largest)**

1. Console delete wording for duplex/copies (F-05) — one function, one focused test.
2. GUI DNA duplex choice (F-01) — one dialog control and one service argument.
3. Inline MSA paste in the console (F-09) and pre-filled CCD edit (F-06) — small,
   isolated, low-risk usability fixes.
4. Surface the JSON view (F-04) and the console plan review (F-11) — makes the output
   inspectable before it is written.
5. GUI two-source `both` MSAs (F-02) and inline-template authoring (F-03) — closes the two
   remaining contract-representation gaps.
6. Console covalent bonds (F-10) — the largest functional gap between the front ends.
7. Housekeeping: remove the dead variant UI modules (F-13), retire or demote the legacy
   batch API (F-12), refresh the stale docstrings (F-14).

**No source file, test, fixture, configuration or existing report was modified during this
audit.** This report is the only file created. The Git working tree was not reset, cleaned
or staged.
