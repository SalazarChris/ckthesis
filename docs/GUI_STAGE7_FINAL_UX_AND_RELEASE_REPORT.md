# Stage 7 — Final UX, Windows Launch/Packaging and Release Verification

Report for the AF3 JSON Builder desktop application (PySide6 / Qt Widgets).
Work date: 2026-10-17. Branch `main`; nothing was committed, reset, stashed or
cleaned. Stage 7 only — no new biological or analysis features.

---

## 1. UX audit (evidence → action → verification)

Every row is based on the working tree as found at the start of this stage,
not on earlier reports.

| # | Issue | Evidence in the current GUI | Severity | Action taken | Files | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Job-wide settings were read-only on Overview | `pages/overview.py` `_JOB_ROWS` rendered name/seeds/version as `QLabel`s; editing required the separate Job Settings tab | **High** (explicit user requirement) | Extracted the settings form into a reusable `JobSettingsPanel` and embedded it on Overview; the tab now uses the same class | `pages/settings.py`, `pages/overview.py`, `windows/main_window.py` | `tests/gui/test_final_ux.py` (4 tests) |
| 2 | Entity-specific settings lived on a different top-level tab | `windows/main_window.py` added seven tabs; `AdvancedPage` was tab #3, coupled to the Entities selection by a signal | **High** (explicit user requirement) | Entities is now a workspace: table + inner tabs **Details** / **Advanced settings**, the latter hosting the same `AdvancedPage` instance; the top-level Advanced tab is gone | `pages/entities.py`, `windows/main_window.py` | `tests/gui/test_final_ux.py` (3 tests), `tests/gui/test_window.py` |
| 3 | Job-scoped CCD/bonds sat among entity settings with no scope marker | `pages/advanced.py` `_build()` stacked modification/alignment/template/CCD/bond groups identically | Medium | Added "This entity" and "Whole job (all entities)" headings plus a one-line explanation of why CCD/bonds are job-scoped | `pages/advanced.py`, `strings.py` | `tests/gui/test_advanced_settings.py` (all 63 still pass) |
| 4 | No shared visual layer; default Qt group boxes, headers and buttons throughout | No `setStyleSheet` anywhere in `configbuilder/ui/render/qt` before this stage | Medium | One central `style.py`: QSS for group boxes, headers, buttons, inputs, tables, tabs, and two label roles (hint, heading). Neutral/translucent only — no hard colours | `style.py`, `windows/main_window.py`, `application.py` | `tests/gui/test_final_ux.py::test_the_window_carries_the_shared_style_sheet` |
| 5 | Window title never named the job and never showed unsaved changes | One `setWindowTitle` call at construction; `GuiState.is_dirty` only consulted by the discard prompt | Medium | Title reads `name - AF3 JSON Builder`, gaining a `*` while `is_dirty` is true; refreshed from the same state every page refresh | `windows/main_window.py`, `strings.py` | 3 tests in `test_final_ux.py` |
| 6 | The status-bar hint was factually wrong in the finished app | `gui.readonly_notice` = "…variants and generation are later stages." | **High** (misleading release text) | Replaced with three state-matched hints: no job / clean job / unsaved changes | `windows/main_window.py`, `strings.py` | `test_window.py`, `test_final_ux.py` |
| 7 | Overview could not fit a short window | Three groups plus two tables with 170 px / 160 px minimum heights in a plain vertical layout | Medium | Page content is inside a `QScrollArea` (resizable, frameless), so small windows scroll instead of squeezing tables | `pages/overview.py` | GUI suite passes; resize behaviour not visually checked (see §10) |
| 8 | "Copy selected path" only knew the Files table | `GeneratePage.selected_path` read `entries_table` only | Low | Copy now covers asset rows too (destination, else source, else emitted path) and the two tables share one selection | `pages/generate.py` | `test_final_ux.py::test_a_planned_asset_path_can_be_copied` |
| 9 | Two placements of job-wide settings could drift | The form existed once (Job Settings) and would have been copied for Overview | Medium (design risk) | One implementation (`JobSettingsPanel`), two placements, both refreshing from `ConfigurationService`; no cached copies | `pages/settings.py`, `pages/overview.py` | `test_the_two_placements_share_one_source_of_truth` |

Not changed, deliberately: domain rules, identifiers, validation, variant
operations, serialization, the output planner, launchers' semantics, and the
core dependency set.

---

## 2. Created / modified files

### Created

| File | Rationale |
| --- | --- |
| `configbuilder/ui/render/qt/style.py` | The single style/metrics layer: `style_sheet()`, `apply_style(widget)`, `hint_label()`, `heading_label()`. Roles only, no per-page styling. |
| `tests/gui/test_final_ux.py` | 13 GUI tests for Overview editing, title/dirty, notice, workspace composition, style application and asset-path copying. |
| `docs/WINDOWS_PACKAGING.md` | Optional PyInstaller recipe, explicitly marked **not built or run**; includes the verification a real build would need. |
| `docs/GUI_STAGE7_FINAL_UX_AND_RELEASE_REPORT.md` | This report. |

### Modified

| File | Change |
| --- | --- |
| `configbuilder/ui/render/qt/pages/settings.py` | Form extracted to `JobSettingsPanel` (with a `title_key` so a placement can name its group); `JobSettingsPage` is now a thin named subclass, so all existing accessors/tests keep working. |
| `configbuilder/ui/render/qt/pages/overview.py` | Embeds the settings panel; read-only job rows reduced to dialect + component count (the values that are not editable); readiness hint added; content wrapped in a scroll area; `notify`/`problems` plumbed from the window. |
| `configbuilder/ui/render/qt/pages/entities.py` | Becomes the entity workspace: actions row, vertical splitter (table above, `QTabWidget` below), Details tab always present, Advanced settings tab when the window supplies the page. |
| `configbuilder/ui/render/qt/pages/advanced.py` | Two scope headings and a job-scope hint around the existing groups; no behavioural change. |
| `configbuilder/ui/render/qt/pages/generate.py` | Asset rows participate in copy-path; one selection across the two plan tables. |
| `configbuilder/ui/render/qt/windows/main_window.py` | Constructs `AdvancedPage` once and hands it to `EntitiesPage`; removes the top-level Advanced tab; applies the style sheet; refreshes title and notice on every refresh. |
| `configbuilder/ui/render/qt/application.py` | Applies the style sheet to the `QApplication` so dialogs opened from the window match. |
| `configbuilder/ui/present/strings.py` | New/changed wording: window title forms, three status notices, readiness hint, entity workspace hint, Details tab label, scope headings, `gui.tab_advanced` now reads "Advanced settings". The stale `gui.readonly_notice` entry is removed. |
| `tests/gui/test_window.py` | Tab list updated to six top-level tabs, with an assertion that the Advanced settings tab is now inside the Entities workspace; notice assertion updated. |
| `tests/unit/ui/test_string_registry.py` | The wording meta-test now skips `style.py` by filename, with a comment: Qt style-sheet syntax is renderer configuration, not displayed text. Every actual label still has to be registered. |
| `RUNNING_THE_APPLICATION.md` | Rewritten for the finished app: accurate Python/dependency facts, a tab-by-tab tour, test commands, known pre-existing failures, packaging pointer. |

Not touched: `configbuilder/output/*`, `transform/*`, `validation/*`,
`persistence/*`, `gui.py`, `af3builder.py`, `pyproject.toml`.

---

## 3. User-requested layout changes now implemented

1. **Overview is the control centre.** Name, model seeds and JSON version are
   edited in place through `ConfigurationService` (`set_job_name`,
   `set_seeds`, `set_json_version`), with the same automatic/custom markers as
   the Job Settings tab. The readiness verdict and the findings are directly
   below, and a finding still opens the entity it names.
2. **Entity settings are in-context.** Selecting an entity on the Entities tab
   fills both the Details tab (sequence/representation, description, partner,
   MSA/template summary) and the Advanced settings tab (PTMs, MSA mode/source,
   templates) — the latter for the same record, driven by the existing
   selection signal. A job-wide CCD definition and covalent bonds remain in
   that tab, clearly headed as belonging to the whole job.
3. **Variants & Batch and Generate & Output are untouched** functionally and
   now share the app's style; the plan → review → confirm → execute → result
   sequence is unchanged.
4. **One less navigation step**: seven top-level tabs became six.

---

## 4. Design choices and shared components

- **`JobSettingsPanel`** — the only implementation of the job-wide form.
  Two placements (Overview, Job Settings tab) read and write the same service.
  A refusal reports through the window's problem path and the panel restores
  the service's current values (existing behaviour, preserved).
- **`style.py`** — a small QSS layer plus two label constructors. Group boxes
  get a 6 px radius and a translucent neutral border; headers are semibold;
  buttons/inputs get consistent padding and a 20 px minimum height; tables get
  alternating rows and subtle gridlines; tabs get uniform padding. Hint labels
  are italic via a `role` property; headings are semibold. **No colour carries
  meaning**: states are words ("Ready", "Not ready", "Conflict", "Keep
  existing") and the QSS uses only `rgba(128,128,128,…)` neutrals, so light and
  dark Windows themes both stay legible.
- **Quantity over decoration** — no icons were added, no animations, no new
  framework. The existing `QSplitter`/`QTabWidget`/`QGroupBox` vocabulary is
  reused.
- **Empty/failure states** were audited, not rewritten: Entities, Variants,
  Overview, Preview and Generate already had service-derived "nothing here"
  text and actionable refusals; the audit found no page that silently does
  nothing.

---

## 5. Launchers — behaviour and verified commands

`gui.py` and `af3builder.py` were **not modified**; they were re-read and
re-verified.

| Command | Behaviour | Verification |
| --- | --- | --- |
| `python gui.py` | Runs `<repo>/.venv-gui/Scripts/python.exe -m configbuilder.ui.render.qt` with the repo root as cwd; missing environment prints copyable setup commands and exits 1 | `tests/unit/test_launchers.py` (passes) |
| `python gui.py --demo` | Same, forwarding `--demo`; the app builds in-memory sample data | Launcher forwarding covered by tests; the window itself was not opened on a display (see §10) |
| `python gui.py "C:\path with spaces\job.json"` | Path forwarded as one argv element; the window offers the import preview | Covered by launcher tests |
| `python gui.py --help` | Prints the GUI's own usage | **Run here**: exit 0 from the repo root *and* from `/tmp` via the full path |
| `python af3builder.py` | Delegates once to `configbuilder.app.cli.main`, returns its status | `tests/unit/test_launchers.py` (passes); not run interactively here |

No launcher installs anything, edits files or runs destructive commands.

---

## 6. Setup and documentation changes

The repository has no `README`; `RUNNING_THE_APPLICATION.md` is the established
setup/launch document, and it is the one that was updated. It now states what
`pyproject.toml` actually declares:

- `requires-python = ">=3.9"`; core `dependencies = []`;
- `PySide6>=6.6` only in the `[gui]` extra;
- Python 3.10+ is the *verified* GUI interpreter; on 3.9 the range resolves to
  PySide6 6.10.3, which is installable but not the tested combination.

Verified in this environment: the core interpreter has **no** PySide6 installed
(`find_spec("PySide6") is None`) and runs the full suite (1030 passed), so the
core-without-GUI contract still holds. `.gitignore` already excludes `build/`,
`dist/` and `.venv*/`, so the documented packaging paths would not pollute a
commit even if a build were run.

---

## 7. Packaging

**Source launch is the supported method.** No executable was built, run,
copied or claimed. `docs/WINDOWS_PACKAGING.md` documents one optional
PyInstaller recipe (windowed, `--collect-submodules configbuilder`, module
entry point), the build-time-only PyInstaller install, and the eight checks a
real build would have to pass on a clean machine. PyInstaller was **not**
added to `pyproject.toml`, and no bundling machinery was committed.

---

## 8. Test commands, results and baseline comparison

Run from the repository root (Git Bash), offscreen for Qt:

```bash
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py
python -m pytest -o addopts="" -q tests/unit/app
QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q
python gui.py --help
```

| Scope | Result |
| --- | --- |
| `tests/gui` | **227 passed** (214 before this stage + 13 new) |
| `tests/architecture` + `test_launchers.py` + `test_string_registry.py` + `tests/unit/app` | **172 passed** |
| `tests/architecture` + `test_launchers.py` + `test_string_registry.py` (standalone) | **64 passed** |
| full suite (core interpreter, no PySide6) | **1030 passed, 13 failed, 12 skipped** |
| `python gui.py --help` from repo root / from `/tmp` | exit 0 / exit 0 |

The 13 failures are the same node IDs measured at the start of Stage 6 and
recorded in the Stage 3/4/5/6 reports — the older numbered **terminal menu**
suite, unrelated to the Qt application:

```
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

No new failure appeared; nothing was skipped, weakened or deleted to reach
these numbers. Skips went from 11 to 12 only because `tests/gui` gains one
more module-level skip when PySide6 is absent.

**One check was changed, deliberately:** `tests/unit/ui/test_string_registry.py`
now excludes `configbuilder/ui/render/qt/style.py` from the
"every fixed string must be registered" scan, by filename and with a comment.
A stylesheet is not displayed wording; every label the user reads still has to
come from the registry, and the "no dead registry entries" half of the test is
untouched.

What the 13 new GUI tests prove (assertions on service state, window chrome and
the widgets, not on source text):

- Overview applies name, seeds and version through the service, and the Job
  Settings tab reflects the same values afterwards;
- a refused blank name reports and restores the service's current name;
- a change made elsewhere appears in both placements after `refresh()`;
- the title names the job, gains `*` on an unsaved edit, clears when a save is
  recorded, and falls back to the app name with no job;
- the status notice moves no-job → clean → dirty → clean;
- the Entities workspace's tabs are exactly Details + Advanced settings, the
  advanced tab **is** `window.advanced_page`, and no top-level tab is called
  "Advanced settings";
- selecting a row drives the advanced tab (A → B), and a PTM added from the
  embedded tab reaches the service and the table;
- the window carries the shared sheet and hint labels carry their role;
- a planned asset's destination can be selected and copied to the clipboard.

---

## 9. Known limitations and decisions still needed

1. **13 pre-existing terminal-menu e2e failures.** They assert the old
   numbered menu and the old `config-001` auto-name; fixing them means
   rewriting that suite's expectations, which is a separate task and was not
   done silently here.
2. **No real-display verification.** All GUI runs were offscreen. Fonts, DPI
   scaling (125% / 150%), dark theme, multi-monitor placement, focus rings and
   actual mouse behaviour are **unverified**; §10 is the checklist.
3. **Style sheet on dark Windows themes** is designed to be safe (neutrals
   only, no hard-coded text colours) but has not been seen on a dark desktop.
4. **The Advanced settings tab is a compromise placement.** Entity PTM/MSA/
   template controls sit beside the entity table as required, but the
   job-wide custom CCD and bonds live in the same tab under a "Whole job"
   heading — they belong to no single entity, and a dedicated job tab would
   reintroduce the extra navigation this stage removed. If the user prefers a
   separate "Job-wide" tab, that is a layout decision for them, not a service
   gap.
5. **Overview and Job Settings are two widget instances** of one panel class.
   They share the service as the single source of truth (proved by a test),
   but an in-progress, unapplied text edit in one is not mirrored live into the
   other; it appears after Apply + refresh. Making the two placements literally
   the same widget would require moving the tab into Overview, which the
   repository's page structure does not support.
6. **No packaging artifact.** PyInstaller was not installed or run; the
   recipe is documentation only.
7. **No new biological capabilities** were added, and none was needed.

---

## 10. Manual Windows usability checklist — status

None of these were performed on a real display by this agent. "Automated
equivalent" names the offscreen test that covers the same behaviour, which is
not the same as a visual check.

| # | Check | Status |
| --- | --- | --- |
| 1 | Launch `python gui.py` and `python gui.py --demo`; window renders | **Not run.** `--help` verified; launchers tested; no display used. |
| 2 | Launch `python af3builder.py`; CLI opens | **Not run** (delegation covered by tests). |
| 3 | Open an AF3 JSON, inspect the import summary, cancel once; job unchanged | **Not run** (automated: `tests/gui/test_import_flow.py`). |
| 4 | Edit name, seeds and JSON version from Overview | **Not run visually** (automated: 4 tests in `test_final_ux.py`). |
| 5 | Add a protein; find sequence, PTM, MSA and template controls in the entity workspace | **Not run visually** (automated: workspace tests, `test_advanced_settings.py`). |
| 6 | Change an MSA mode/source, apply, verify the view reflects it | **Not run** (automated: alignment tests). |
| 7 | Add DNA, inspect the partner relationship, cancel deletion then confirm it | **Not run** (automated: `test_entity_management.py`). |
| 8 | Add a ligand with multiple CCD codes/copies; identifiers correct | **Not run** (automated: entity tests). |
| 9 | Create/validate a variant; preview its edits; base unchanged | **Not run** (automated: `test_variants_batch.py`). |
| 10 | Preview the output plan, cancel once, then generate into a temp folder | **Not run** (automated: `test_generate_output.py`). |
| 11 | Reopen a generated JSON and compare with the preview | **Not run** (automated: generated bytes asserted). |
| 12 | Trigger an invalid operation; error actionable, values retained, no partial change | **Not run** (automated: refusal tests across suites). |
| 13 | Resize/maximize; keyboard navigation, focus, long paths/sequences/JSON readable | **Not run.** Scroll areas and splitters exist; focus order and DPI unverified. |
| 14 | No important feature only behind an icon or hidden context menu | **Not run visually.** Source review found every action as a labelled button, menu item or tab; no icon-only or right-click-only actions. |

---

## 11. Working-tree state

`git status --short` at the end of this stage, verbatim (68 entries). The
working tree was already dirty when Stage 7 began; this stage added
`configbuilder/ui/render/qt/style.py`, `tests/gui/test_final_ux.py`,
`docs/WINDOWS_PACKAGING.md` and this report (the Qt front end and `tests/gui`
are untracked directories, so their files appear under the directory entry).

```
 D JSON_BUILDER_AUDIT_AND_FINALIZATION.md
 M configbuilder/app/batch_variants.py
 M configbuilder/app/configuration_service.py
 M configbuilder/app/generation_service.py
 M configbuilder/app/results.py
 M configbuilder/app/status.py
 M configbuilder/app/validation_service.py
 M configbuilder/app/variant_service.py
 M configbuilder/persistence/__init__.py
 M configbuilder/persistence/sequences.py
 M configbuilder/transform/__init__.py
 M configbuilder/transform/engine.py
 M configbuilder/transform/mappings.py
 M configbuilder/ui/present/strings.py
 M configbuilder/ui/render/menus.py
 M configbuilder/validation/engine.py
 M configbuilder/validation/rules/policy_rules.py
 M pyproject.toml
 M tests/unit/app/test_batch_variants.py
 M tests/unit/app/test_edit_guards.py
 M tests/unit/app/test_status.py
 M tests/unit/transform/test_to_wire.py
 M tests/unit/ui/menu_flows.py
 M tests/unit/ui/test_audit_regressions.py
 M tests/unit/ui/test_edit_hardening.py
 M tests/unit/ui/test_menu.py
 M tests/unit/ui/test_mod_display.py
 M tests/unit/ui/test_numbered_flows.py
 M tests/unit/ui/test_string_registry.py
 M tests/unit/validation/test_no_pin_document_dependency.py
 M tests/unit/validation/test_rule_checks.py
 M tests/unit/variants/test_quantity_series.py
?? RUNNING_THE_APPLICATION.md
?? af3_analysis/
?? af3builder.py
?? configbuilder/app/version_features.py
?? configbuilder/ui/render/qt/
?? docs/AF3_Comparative_Structural_Analysis_SOP.md
?? docs/AF3_GUI_AUDIT_PROMPT.md
?? docs/AF3_GUI_LAUNCHERS_AND_NEXT_STAGES_PROMPT.md
?? docs/AF3_GUI_STAGE1_IMPLEMENTATION_PROMPT.md
?? docs/AF3_GUI_STAGE3_ENTITY_MANAGEMENT_PROMPT.md
?? docs/AF3_GUI_STAGE4_ADVANCED_ENTITY_SETTINGS_PROMPT.md
?? docs/AF3_GUI_STAGE5_VARIANTS_BATCH_PROMPT.md
?? docs/AF3_GUI_STAGE6_OUTPUT_GENERATION_PROMPT.md
?? docs/AF3_GUI_STAGE7_FINAL_UX_PACKAGING_REGRESSION_PROMPT.md
?? docs/AF3_Oct4_10_Condition_JSON_Builder_Agent_Prompt.md
?? docs/GUI_AUDIT_REPORT.md
?? docs/GUI_LAUNCHERS_IMPLEMENTATION_REPORT.md
?? docs/GUI_STAGE1_IMPLEMENTATION_REPORT.md
?? docs/GUI_STAGE1_REVIEW_REPORT.md
?? docs/GUI_STAGE2_IMPLEMENTATION_REPORT.md
?? docs/GUI_STAGE3_IMPLEMENTATION_REPORT.md
?? docs/GUI_STAGE4_IMPLEMENTATION_REPORT.md
?? docs/GUI_STAGE5_VARIANTS_BATCH_IMPLEMENTATION_REPORT.md
?? docs/GUI_STAGE6_OUTPUT_GENERATION_IMPLEMENTATION_REPORT.md
?? docs/GUI_STAGE7_FINAL_UX_AND_RELEASE_REPORT.md
?? docs/IMPLEMENTATION_MAP.md
?? docs/IMPLEMENTATION_MAP_FULL.md
?? docs/JSON_BUILDER_AUDIT_AND_FINALIZATION.md
?? docs/THESIS_IMPLEMENTATION_CHAPTER.md
?? docs/WINDOWS_PACKAGING.md
?? generated_jobs/
?? gui.py
?? pytest-of-Chris/
?? tests/analysis/
?? tests/gui/
?? tests/unit/test_launchers.py
```

Confirmed: no `git reset`, `clean`, `stash`, `restore`, `checkout`, `rebase`,
`amend` or `commit` was run at any point in this stage, and no user file was
overwritten. The ` D JSON_BUILDER_AUDIT_AND_FINALIZATION.md` deletion was
present before this stage began and was left as found.

---

## 12. Recommended final manual acceptance pass

On a real Windows desktop, with `.venv-gui` installed:

1. `python gui.py --demo` → confirm the window renders at the default size and
   maximised; check the group-box borders, header weight, button padding and
   tab spacing read as one design.
2. Repeat with Windows in **dark mode** and at **125% / 150% scaling**; confirm
   text stays legible and no table column collapses.
3. On Overview, rename the job, set seeds `1, 2, 3`, pin version 4; confirm the
   title shows `name*` and the readiness rows update without a second click.
4. Add a protein, switch to the **Advanced settings** inner tab, add a PTM,
   change the MSA to a file, and confirm the Details tab's MSA line matches.
5. Tab through the Entities workspace with the keyboard: table → inner tabs →
   each control; confirm the inner tab switch is reachable without the mouse.
6. Run the Generate & Output flow from Stage 6 against a folder containing one
   conflicting file; copy an asset path from the Assets table.
7. Close with unsaved changes, cancel, and confirm nothing was lost; then close
   and discard, and confirm the prompt is gone next launch (nothing persisted).

If any of those fail, the likely places are `style.py` (metrics) and
`pages/entities.py` (splitter proportions) — both are single, small files to
adjust.
