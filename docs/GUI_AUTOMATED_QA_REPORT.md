# AF3 JSON Builder — Automated End-to-End QA Report

Date: 2026-10-21
Scope: builder verification only (no AF3 inference, cluster, network or thesis data).

## 1. Environment and revision

| Item | Value |
| --- | --- |
| Branch | `main` |
| HEAD | `e8bd15ac562b8722d6f3abb0f2b489d5e8120f7c` |
| Core interpreter | CPython 3.11.15 (64-bit, Windows) |
| GUI interpreter | `.venv-gui\Scripts\python.exe`, CPython 3.11.15 |
| Core pytest | 8.2.2 |
| GUI pytest | 9.1.1 |
| PySide6 | 6.12.0 |
| Qt platform | `windows` (real desktop) for screenshots; `offscreen` for the automated GUI suite |
| Display | 1536×864 physical, device pixel ratio 1.25, Segoe UI |
| Ruff | 0.16.9, default rules (the repository has no Ruff configuration) |

Commands were run from the repository root in Git Bash on Windows. The GUI
environment is the documented optional extra; the core package still imports
and tests without PySide6.

## 2. Starting working tree and protections

Before any edit, `git status --short` reported:

```text
 D JSON_BUILDER_AUDIT_AND_FINALIZATION.md
?? .stage8_shots/
?? .stage9_core_final.txt
?? .stage9_gui_final.txt
?? .stage9_shots/
?? af3_analysis/
?? docs/AF3_Comparative_Structural_Analysis_SOP.md
?? docs/AF3_GUI_AUTOMATED_END_TO_END_QA_PROMPT.md
?? docs/AF3_Oct4_10_Condition_JSON_Builder_Agent_Prompt.md
?? docs/IMPLEMENTATION_MAP.md
?? docs/IMPLEMENTATION_MAP_FULL.md
?? docs/JSON_BUILDER_AUDIT_AND_FINALIZATION.md
?? docs/THESIS_IMPLEMENTATION_CHAPTER.md
?? docs/screenshots/variants_probe.png
?? generated_jobs/
?? pytest-of-Chris/
?? tests/analysis/
```

These are pre-existing user changes. None was reset, cleaned, stashed,
restored, checked out, rebased, amended, deleted, or committed. The only
deletion in `git status` remains the pre-existing unstaged deletion of the
root audit file.

Scratch directories created for this QA (`.qa_launch`, `.qa_shots`,
`.qa_tmp`) were removed before the final status; no generated output remains
in the checkout.

## 3. Initial baseline

All commands below were run before any file was changed.

| Command | Result | Exit |
| --- | --- | --- |
| `python -m pytest -o addopts="" -q` | **1032 passed, 13 failed, 16 skipped** in 187.77 s | 1 |
| `python -m pytest -o addopts="" -q tests/architecture` | 40 passed in 11.80 s | 0 |
| `python -m pytest -o addopts="" -q tests/unit/test_launchers.py` | 19 passed in 2.00 s | 0 |
| `python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py` | 5 passed in 0.60 s | 0 |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | 275 passed in 107.55 s | 0 |
| `python -m compileall -q configbuilder tests/gui` | no output | 0 |
| `python gui.py --help` | usage printed | 0 |

The exact failing node IDs were:

```text
tests/e2e/test_entity_lifecycle.py::test_every_family_survives_a_full_lifecycle
tests/e2e/test_entity_lifecycle.py::test_an_imported_document_is_editable_like_a_built_one
tests/e2e/test_entity_lifecycle.py::test_a_long_repeated_chain_of_operations_leaves_consistent_state
tests/e2e/test_menu_acceptance.py::test_a_blank_job_name_is_generated_by_the_service
tests/e2e/test_menu_acceptance.py::test_add_every_entity_family
tests/e2e/test_menu_acceptance.py::test_job_settings_change_name_seeds_and_version
tests/e2e/test_menu_acceptance.py::test_invalid_job_settings_are_refused_in_the_users_terms
tests/e2e/test_menu_acceptance.py::test_the_job_menu_numbering_is_stable_across_states
tests/e2e/test_menu_acceptance.py::test_the_entity_modifications_submenu_adds_edits_and_removes
tests/e2e/test_menu_acceptance.py::test_ptm_management_adds_edits_and_removes
tests/e2e/test_menu_acceptance.py::test_a_ligand_carries_no_modifications_and_is_told_so
tests/e2e/test_menu_acceptance.py::test_open_json_can_be_cancelled_at_the_confirm
tests/e2e/test_menu_acceptance.py::test_an_opened_job_can_be_edited_and_saved
```

## 4. Workflow coverage matrix

Existing coverage was already broad. The tests below were inspected and run;
rows marked **new** are coverage added by this QA pass.

| Workflow | Tests | Filesystem side effects checked | Result |
| --- | --- | --- | --- |
| Launcher starts, forwards `--demo`, closes cleanly | **new** `tests/gui/test_accessibility_and_launch.py::test_the_launcher_starts_the_demo_window_and_returns_cleanly` | Real subprocess, real event loop, no file output | pass |
| Path with spaces reaches the GUI as one argument | **new** `...::test_a_json_path_with_spaces_reaches_the_window_as_one_argument` | JSON fixture in a spaced temp folder; no mutation | pass |
| DPI scale smoke 1.25 and 1.5 | **new** `...::test_the_launcher_starts_under_a_scaled_dpi` | Subprocess launch/close only | pass |
| No-job state, four destinations, no preview destination | `test_final_layout_refinement.py`, `test_mockup_shell.py`, `test_workflow_simplification.py` | none | pass |
| New job, cancel/discard, title/dirty state | `test_job_lifecycle.py`, `test_final_ux.py` | none | pass |
| Import preview Cancel/Import, invalid/missing file | `test_import_flow.py`, `test_preview.py` | source bytes read-only | pass |
| Save, blocked save, overwrite confirm, reopen/round-trip | `test_job_lifecycle.py`, `test_import_flow.py` | temp destination bytes, no write on refusal | pass |
| Protein/RNA/DNA/ligand add/edit/delete, DNA partners, copies | `test_entity_management.py`, `test_entity_table.py`, `test_final_layout_refinement.py` | none | pass |
| Picker: zero, every family, both DNA strands, lone DNA, multi-copy | `test_final_layout_refinement.py`, `test_entity_table.py` | imported lone strand fixture | pass |
| No GUI-built wire dictionaries, IDs or complements | `test_entity_management.py::test_the_gui_module_computes_no_complement_of_its_own` | static check | pass |
| PTMs, alignment/MSA, templates, custom CCDs, covalent bonds | `test_advanced_settings.py` (60 tests) | none; preview JSON read-only | pass |
| Layout order: MSA → templates → PTMs; CCD/bonds whole-job areas | `test_final_layout_refinement.py` | none | pass |
| Variants: choices, manual spec, series, batch files, duplicate/rename/remove | `test_variants_batch.py`, `test_stage8_ux.py` | temp batch files, base equality | pass |
| Generate: base/selected/all scopes, policies, conflicts, stale plan | `test_generate_output.py` (26 tests), `test_workflow_simplification.py` | temp output trees, manifest/assets | pass |
| Output correctness: all JSON parses, assets copied, manifest matches | **evidence run** §8; `test_generate_output.py` | temp output tree, 4 JSON parsed | pass |
| Minimum 940×640 and normal 1200×760 windows | **new** `...::test_every_destination_fits_at_the_minimum_and_normal_sizes` | none | pass |
| Tab focus stays on visible controls, excludes retired preview | **new** `...::test_tab_reaches_visible_controls_and_never_the_retired_preview` | none | pass |
| Accessible names for fields/actions | **new** `...::test_the_important_fields_and_actions_expose_accessible_names`, `...visible_buttons_all_carry_text_or_an_accessible_name` | none | pass |
| Escape cancels a form dialog | **new** `...::test_a_form_dialog_keeps_escape_as_a_safe_cancel` | none | pass |
| CLI full entity lifecycle and menu acceptance | `tests/e2e/test_entity_lifecycle.py`, `test_menu_acceptance.py` | temp working directories and saved JSON | pass (after script repair) |
| CLI DNA single-strand answer | **new** `test_entity_lifecycle.py::test_dna_can_be_added_as_one_supplied_strand` | none | pass |

## 5. Bugs found, fixes and regression tests

### D1 — “Single-stranded” DNA added zero entities (high impact)

The console offered *“No — use only the supplied strand”*, reported
“Applied. Entity added.”, and left the job empty. Reproduction over the
scripted menu:

```text
1 New job → Lone
2 Add entity → 2 DNA → ATGC → 2 No
resulting records: []
```

Cause: `ConfigurationService.add_record("dna", …)` always built the duplex,
and the menu then called `remove_record` on the partner. The service treats a
DNA removal as removing the pair, so both strands disappeared.

Minimal fix:

- `ConfigurationService.add_record(..., duplex=True)` gained an explicit
  keyword. `duplex=False` allocates and commits exactly the supplied lone
  strand; the default is unchanged, so every existing caller still creates a
  duplex.
- The console now makes one call with `duplex=add_complement` instead of
  add-then-delete.

Regression tests:

- `tests/unit/app/test_dna_duplex.py::test_duplex_false_commits_only_the_supplied_strand`
- `...::test_a_single_strand_edit_and_remove_need_no_partner`
- `tests/e2e/test_entity_lifecycle.py::test_dna_can_be_added_as_one_supplied_strand`

### D2 — Retired JSON Preview page was still visible and focusable

The preview page is no longer a destination, but it remained a visible child
of the main window. A Tab walk from the job name reached its **Refresh**
button and read-only editor even though no destination shows the page.

Fix: `MainWindow` now calls `self._preview.hide()` after construction.
Regression: `tests/gui/test_accessibility_and_launch.py::test_tab_reaches_visible_controls_and_never_the_retired_preview`
also asserts the page is not visible and none of its children receive focus.

### D3 — Overview forced a horizontal scrollbar at the supported minimum width

At 940×640 the overview content was 885 px wide inside a 700 px viewport
(horizontal range 185 px), caused by the unwrapped sentence “Open the entity
workspace to add, edit or remove entities.”

Fix: the hint label now wraps (`caption_label(..., wrap=True)`). Measured
after the fix: content 530 px, viewport 700 px, horizontal range 0.
Regression: the minimum-size test asserts the horizontal scrollbar is hidden.

### D4 — Job settings fields had no accessible names

`name_edit`, `seeds_edit` and `version_combo` are laid out in a `QGridLayout`
without buddy labels, so their visible labels were not exposed as accessible
names.

Fix: each field sets the same wording as its visible label via
`setAccessibleName`. Regression: `test_the_important_fields_and_actions_expose_accessible_names`.

### D5 — Generate intro pointed at a hidden File menu

The intro said “Save JSON in the File menu”, but the menu bar is hidden; the
visible route is the FILE footer. Wording changed to “FILE footer”.
Regression: `test_the_generate_intro_names_the_visible_save_route`.

## 6. CLI end-to-end outcome

All 13 failures were stale scripts, not domain defects. The separate new
single-strand test exposed D1. Scripts were updated to the current intended
menu, with their original assertions and end-to-end purpose preserved. No
test was skipped, xfailed, or loosened to a generic substring. Twelve
original node IDs pass unchanged; the import-confirm test was renamed to the
picker-cancel test because the confirm no longer exists (details below).

| Test | Stale expectation | Current intended behaviour / update |
| --- | --- | --- |
| `test_a_blank_job_name_is_generated_by_the_service` | `config-001` | The service names a blank job `Untitled job 1` (`app/status.py`). |
| `test_add_every_entity_family` | DNA add had no complement answer | DNA now asks yes/no; script answers `1` (duplex). |
| `test_job_settings_change_name_seeds_and_version` | seeds entered directly | Seeds now asks specific/generate first: `2 → 1 → "1 2 3 4"`. |
| `test_invalid_job_settings_are_refused_in_the_users_terms` | seeds direct; dirty exit | Seeds method added; neither refusal changes the job, so it exits cleanly. |
| `test_the_job_menu_numbering_is_stable_across_states` | `5. PTM management` | Label is `5. Post-translational modification management`. |
| `test_the_entity_modifications_submenu_adds_edits_and_removes` | `Modification added/updated/removed` | Current wording `Post-translational modification …`. |
| `test_ptm_management_adds_edits_and_removes` | no final return from PTM menu | One `0` returns from PTM management before leaving the job; wording updated. |
| `test_a_ligand_carries_no_modifications_and_is_told_so` | “ligands carry no modifications” | Current wording “ligands carry no post-translational modifications”. |
| `test_open_json_can_be_cancelled_at_the_confirm` | preview → confirm → commit | The CLI opens directly after the path is chosen. The test now cancels at the path picker (`0`) and still asserts no project is opened; renamed `..._at_the_picker`. |
| `test_an_opened_job_can_be_edited_and_saved` | extra input for the removed confirm | Removed the extra `1`; edit/save assertions unchanged. |
| `test_every_family_survives_a_full_lifecycle` | DNA/no complement, import confirm | Added complement answer and removed confirm input; full save/reopen/delete assertions unchanged. |
| `test_an_imported_document_is_editable_like_a_built_one` | import confirm | Removed confirm input; imported-field, identity and save assertions unchanged. |
| `test_a_long_repeated_chain_of_operations_leaves_consistent_state` | DNA/import confirm | Same two script corrections; invariants and JSON assertions unchanged. |

Additional CLI coverage added: `test_dna_can_be_added_as_one_supplied_strand`
regresses D1 at the shipped-menu level.

The import-confirm path is deliberately gone from the current CLI (the file
commits after selection), so the original node ID
`test_open_json_can_be_cancelled_at_the_confirm` no longer exists. Its
replacement, `test_open_json_can_be_cancelled_at_the_picker`, keeps the same
cancellation guarantee at the remaining decision point and still asserts that
no project is opened. The GUI still has its preview → Import/Cancel dialog,
covered unchanged by `tests/gui/test_import_flow.py`.

## 7. Final results

All commands were rerun after the last code change.

| Command | Result | Exit |
| --- | --- | --- |
| `python -m pytest -o addopts="" -q` | **1048 passed, 0 failed, 17 skipped** in 182.60 s | 0 |
| `python -m pytest -o addopts="" -q tests/e2e` | 64 passed in 1.16 s | 0 |
| `python -m pytest -o addopts="" -q tests/architecture` | 40 passed | 0 |
| `python -m pytest -o addopts="" -q tests/unit/test_launchers.py` | 19 passed | 0 |
| `python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py` | 5 passed | 0 |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | **286 passed** in 116.80 s | 0 |
| `python -m compileall -q configbuilder tests/gui tests/e2e` | no output | 0 |
| `python gui.py --help` | usage printed | 0 |
| `python -m ruff check configbuilder tests` | 1187 findings under Ruff defaults (no Ruff config in the repository) | 1 |
| `python -m ruff check .` | 2437 findings across the whole checkout, including untracked analysis/tools | 1 |

Compared with baseline:

- 12 of the 13 originally failing CLI e2e node IDs now pass unchanged; the
  13th was replaced by the picker-cancel test for the removed confirm step;
- +3 core tests (2 service DNA tests, 1 CLI single-strand test);
- +11 GUI tests (launch, scaled launch, minimum-size, focus, accessible names,
  dialog Escape, visible save route);
- the one additional skip is the new GUI module collected under the core
  interpreter (PySide6 intentionally absent there).

Ruff is reported separately. The repository has no Ruff configuration, so
default rules were used. On `configbuilder` + `tests` it reports 1187
findings, dominated by the project's existing style (`UP031` percent
formatting, `RUF059` unused unpacked names in old tests, import sorting).
The changed files carry 52 of those existing-pattern findings. The new
`tests/gui/test_accessibility_and_launch.py` passes Ruff cleanly, and the
new findings introduced during QA (unused variable, `subprocess.run` check
argument, unused `noqa`) were fixed rather than suppressed.

## 8. Output verification evidence

A dedicated run of two Generate tests with `--basetemp=.qa_tmp` produced:

```text
.qa_tmp/test_generate_writes_the_revie0/output-job/manifest.json
.qa_tmp/test_generate_writes_the_revie0/output-job/output-job__v1/output-job__v1.json
.qa_tmp/test_generate_writes_the_revie0/output-job/output-job__v2/output-job__v2.json
.qa_tmp/test_copied_assets_are_planned0/out/output-job/output-job.json
.qa_tmp/test_copied_assets_are_planned0/out/output-job/assets/chain-a.a3m
```

`json.loads` parsed **4 JSON documents** (base, two variants, manifest), each
with `dialect`, `modelSeeds`, `name`, `sequences`, `version`. The manifest’s
variant keys were `["v1", "v2"]` for project `output-job`. The copied asset
existed at `assets/chain-a.a3m` and the base document referenced the same
relative path. `.qa_tmp` was removed afterwards.

Additional automated filesystem evidence in `tests/gui/test_generate_output.py`:

- cancellation left the destination empty;
- a conflicting file refused the whole plan and changed nothing;
- Skip kept the existing bytes; Overwrite replaced them; Versioned wrote a
  numbered copy;
- a file created after preview stopped generation;
- an unwritable destination was reported, not raised;
- a stale plan could not execute after folder, policy or job changes.

## 9. Screenshot and layout smoke checks

Captured with the real `windows` Qt platform (not offscreen), system Segoe UI,
device pixel ratio 1.25, window exactly 940×640. All four pages were grabbed
and inspected: Overview, Entities, Variants, Generate. Page grabs were
875×653 device pixels, non-empty, and each page was visible. The overview
horizontal scrollbar was absent; the Generate page scrolled vertically as
designed.

Supplemental automated launch smoke passed at `QT_SCALE_FACTOR=1.25` and
`1.5` (subprocess started, event loop closed, exit 0).

Limitations: these checks prove rendering, dimensions and widget visibility;
they do **not** prove human visual quality, real 150 % Windows DPI layout, high
contrast, or screen-reader announcements. Those remain human checks.

## 10. Remaining failures and issues

| Category | Item |
| --- | --- |
| Defects | None reproduced and unresolved. D1–D5 are fixed and covered. |
| Stale tests | The 13 CLI e2e scripts were repaired; none remain failing. |
| Environment/platform | Real 150 % DPI and OS-level permission dialogs were not exercised; an unwritable destination was simulated in tests. |
| Human checks | Screen-reader semantics, visual polish/high contrast, and actual font rendering at other DPI settings require a person. |
| Lint | 1187 Ruff findings in `configbuilder` + `tests` and 2437 checkout-wide under default rules (no Ruff config). These are existing project style; the new QA module is clean. |
| Uncommitted user work | Pre-existing tree items listed in §2 remain untouched. |

## 11. Changed-file inventory

Modified:

- `RUNNING_THE_APPLICATION.md` — known-failures paragraph now matches reality.
- `configbuilder/app/configuration_service.py` — `duplex` option for DNA.
- `configbuilder/ui/present/strings.py` — Generate intro names the FILE footer.
- `configbuilder/ui/render/menus.py` — one-call single/duplex DNA add.
- `configbuilder/ui/render/qt/pages/overview.py` — wrapping entity-summary hint.
- `configbuilder/ui/render/qt/pages/settings.py` — accessible names.
- `configbuilder/ui/render/qt/windows/main_window.py` — hide retired preview.
- `tests/e2e/test_entity_lifecycle.py` — current menu scripts + single-strand test.
- `tests/e2e/test_menu_acceptance.py` — current menu scripts and wording.
- `tests/unit/app/test_dna_duplex.py` — lone-strand service tests.
- `tests/unit/ui/menu_flows.py` — corrected auto-name comment.

Added:

- `tests/gui/test_accessibility_and_launch.py`.
- `docs/GUI_AUTOMATED_QA_REPORT.md` (this report).

No reset, clean, stash, checkout, rebase, amend, or commit was performed.

## Readiness verdict

**Verified by automated tests** — the full core suite (1048 passed, 0 failed),
the GUI suite (286 passed), all 64 CLI end-to-end tests, architecture,
launchers, string registry, compilation, launcher help, launch smoke at two
DPI factors, minimum-size/focus/accessibility checks, and filesystem output
inspection all pass. Remaining limitations are the human-only checks named in
§10.
