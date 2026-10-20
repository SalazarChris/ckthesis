# Stage 6 — Output Generation, Preflight Review and Validation UX

Implementation report for the AF3 JSON Builder GUI (PySide6 / Qt Widgets).
Date of work: 2026-10-17. Branch: `main`, no commits were made.

Stage 6 only. The final UX/packaging/regression stage was **not** started.

---

## 1. Summary of delivered functionality

A new **Generate && Output** tab answers the six questions the prompt asks, in
the order a reviewer needs them: destination and scope, planned files, planned
assets, conflicts, warnings, and what Generate will do.

Delivered:

- **Output folder picker** (`QFileDialog.getExistingDirectory`) plus a typed
  path field; the plan's own absolute paths are shown, never a reconstructed
  guess.
- **Scope selector** with exactly the three scopes the service implements:
  all variants (with manifest), one selected variant (with manifest), and the
  base job's single file (no manifest).
- **Both policy families**, offered as the service's own closed sets with
  plain-language labels, one-line consequences and tooltips: four overwrite
  behaviours (`Fail`, `Skip`, `Overwrite`, `Versioned`) and three external-file
  behaviours (`CopyIntoAssets`, `RelativeToOutput`, `AsGiven`). Defaults are
  read from the open project's settings through the service.
- **Preview plan**: a Files table (kind / job / path / action), an Assets table
  (wire field / source / copied-to / path in JSON), a conflict list, a warning
  list and a findings table. Preview writes nothing.
- **Explicit confirmation** naming the file count, the destination and both
  policies in force; Cancel is the dialog's default button. Cancelling writes
  nothing and changes no job state.
- **Staleness protection**: any job change, destination change or policy change
  invalidates the held plan; Generate re-plans immediately before execution and
  refuses if the new plan differs from the reviewed one, showing the new plan.
- **Result tab** built only from the service's `PlanOutput`: written, skipped,
  copied (source → destination) and errors, with a partial outcome reported as
  partial and never as success.
- **Validation preflight**: a refused plan shows the service's message and the
  service's blocking findings; selecting a finding opens the entity it names,
  and a "Review configuration" button goes to Overview when no field-level
  jump is possible.
- **`Save JSON…` untouched**: still the one-file workflow from Stage 2, still
  routed through `plan_save`/execute, and the page's own intro wording states
  which action writes one file and which writes the planned tree.

Deliberately deferred (out of scope for Stage 6):

- Background generation / progress dialog. Execution runs on the UI thread
  through the existing service; jobs at the sizes this tool handles write in
  well under a second. Recorded as a limitation, not implemented.
- A remembered output folder across sessions (the project model has no such
  setting and no new persistence was invented).
- Any change to output layout, naming, manifest content or validation rules.
- Stage 7 redesign of the remaining pages.

---

## 2. Created / modified files

### Created

| File | Why |
| --- | --- |
| `configbuilder/ui/render/qt/pages/generate.py` | The whole page: destination, scope, policies, plan tables, asset table, conflicts/warnings/findings, confirmation, replan-before-execute, result view. No path, byte or manifest is constructed here. |
| `tests/gui/test_generate_output.py` | 24 GUI tests driving the real widgets and asserting on real files on disk (preview, refusal, scope, policies, staleness, conflicts, partial failure, assets, findings navigation). |
| `docs/GUI_STAGE6_OUTPUT_GENERATION_IMPLEMENTATION_REPORT.md` | This report. |

### Modified

| File | Change |
| --- | --- |
| `configbuilder/app/generation_service.py` | Added the front-end seam: `output_policy_choices()`, `output_defaults()` and `plan_selection(...)`, plus the private `_named_policy(...)` helper. `plan_selection` is the only new *behaviour*: it maps a picker scope + policy **names** onto the existing `plan(...)` / `plan_base(...)` calls, and refuses an unknown name instead of falling back silently. `plan`, `plan_base`, `plan_save`, `show_json` and `execute` are unchanged. |
| `configbuilder/app/results.py` | `FailureReason.INVALID_CHOICE` — the reason a bad scope/policy name is refused. `GenerationPlan.findings` (already present) is now populated on the `VALIDATION_BLOCKED` paths of `plan_base` as well, so the page can show causes rather than only a sentence. |
| `configbuilder/transform/engine.py` | (a) `used_version_features` is public and returns `(feature, min_version, wording)` rows so `app`/validation can explain a version-pin conflict with the same facts the emitter enforces. (b) `with_emitted_resource_paths` now rewrites **every** occurrence of a planned field, including a template entry's nested `mmcifPath`, and is copy-on-write instead of writing through a shallow copy. Without (b) the GUI's Assets tab could promise "the JSON will point at `assets/…`" while the written file still pointed at the original path. Both have focused unit tests. |
| `configbuilder/ui/present/strings.py` | 67 registered `gui.output_*` keys: page wording, policy labels and hints, column headers, action words, refusal/staleness/confirmation/result text. No string is built in a widget. |
| `configbuilder/ui/render/qt/dialogs/messages.py` | `confirm_generation(parent, message)` — asks, returns a bool, owns no logic. |
| `configbuilder/ui/render/qt/dialogs/__init__.py` | Exports `confirm_generation`. |
| `configbuilder/ui/render/qt/pages/__init__.py` | Exports `GeneratePage`; docstring updated for Stages 1–6. |
| `configbuilder/ui/render/qt/windows/main_window.py` | Builds the page, inserts the tab between Variants & Batch and Job Settings, refreshes it with every other page, and wires `record_activated → _show_entity` and `review_requested → _show_overview`. |
| `configbuilder/ui/render/qt/state.py` | Pass-through seam: `output_policy_choices()`, `output_defaults()`, `plan_generation(...)`, `execute(plan)`; `validate_all()` (already present) is used for the variant-findings fallback. |
| `tests/gui/test_window.py` | The tab-order assertion now includes Generate & Output. |
| `tests/unit/transform/test_to_wire.py` | Test that the emitted-path rewrite targets the field and leaves the source document untouched. |

No change was made to `configbuilder/output/*`, to the serializer, to
validation rules, to `plan_save`/`Save JSON…`, to the launchers, or to the
core dependency set (`PySide6` remains UI-extra only).

---

## 3. UI control → service API mapping

| Control | Service call | Result fields used |
| --- | --- | --- |
| Output folder (`destination` + `browse_destination`) | passed as `output_root` | `GenerationPlan.output_root` |
| Scope = All variants | `GuiState.plan_generation(scope="variants")` → `GenerationService.plan_selection` → `plan(output_root, overwrite_policy, path_policy, only=None)` | `entries`, `conflicts`, `warnings`, `manifest_data`, `reviewed`, `project_name` |
| Scope = Selected variant (`variant_choice`) | `plan_selection(scope="selected", only=[key])` → `plan(..., only=(key,))` | same; manifest describes only the written subset |
| Scope = Base job only | `plan_selection(scope="base")` → `plan_base(output_root, ...)` | `entries` (one), no manifest |
| Overwrite picker | names from `output_policy_choices()["overwrite"]`, default from `output_defaults()["overwrite"]`; converted by `_named_policy` into `OverwritePolicy` | plan `entries[*].action` = `create`/`overwrite`/`skip`/`conflict` |
| External-file picker | names from `output_policy_choices()["path"]`, default from `output_defaults()["path"]`; converted into `PathPolicy` | `reviewed.resources[*].planned_path`, `.emitted_path`, `.copied` |
| Files table | `plan.entries` (`ConfigurationPlan`) | `variant_key`, `path`, `action`, `payload_fingerprint` |
| Assets table | `plan.reviewed.resources` (`output.plan.ResourceEntry`) | `wire_field`, `raw_path`, `planned_path`, `emitted_path`, `copied` |
| Conflicts list | `plan.conflicts` (strings from `output.plan.conflict_message`) | — |
| Warnings list | `plan.warnings` (strings from the planner) | — |
| Findings table | `plan.findings`; for `VALIDATION_BLOCKED` with no attached findings, `validate_all().variant_reports[*].findings` where the report blocks | `Finding.code`, `severity`, `message`, `record_key` |
| "Review configuration" | `review_requested` → Overview tab | — |
| Copy selected path | the selected row's `path` (the plan's own string) → clipboard | — |
| Generate files | `confirm_generation(...)`, then `plan_generation(**same arguments)` for comparison, then `GuiState.execute(plan)` → `GenerationService.execute(generation_plan)` | `PlanOutput.ok`, `.written`, `.skipped`, `.copied_resources`, `.errors`, `.message` |
| Result tab | `PlanOutput` as above | — |
| Plan note / counts | `len(plan.entries)`, `sum(1 for r in plan.reviewed.resources if r.copied)`, `len(plan.warnings)` | — |

`FailureReason.INVALID_CHOICE` is rendered through the service's own `message`
inside the registered "Nothing can be written: %s" refusal line.

---

## 4. Preflight, confirmation and execution behaviour

1. **Preview** validates the destination field (non-empty) and, for the
   selected scope, that a variant is chosen — the only two checks the page
   performs itself, because they are about the page's own inputs. Everything
   else (open job, validation, expansion, layout, conflicts, warnings) is the
   service's answer.
2. A refused plan is rendered, not swallowed: the message appears in the plan
   note and in the problem box, the conflicts list shows the planner's strings,
   and blocking findings are listed with a jump target. Generate stays disabled.
3. A successful plan fills the four tables/lists and the note reads
   "N file(s) and M copied file(s) planned, with K warning(s) — nothing has been
   written yet." Generate is enabled only while the current control values equal
   the values the shown plan was built from.
4. **Invalidation**: `project_changed` (via `MainWindow.refresh → page.refresh`),
   any destination edit, any scope/variant change and any policy change clears
   the held plan, disables Generate and replaces the note with "The job changed
   since this plan was previewed…" (job change) or "The destination or an option
   changed…" (controls). The held plan is dropped, not merely hidden.
5. **Confirmation** names the file count, the absolute destination and both
   policies; Cancel is the default and returns without touching anything.
6. **Re-plan before execute**: immediately after confirmation the page plans
   again with the same arguments and compares the result with what was reviewed
   (`_same_plan`: ok/failure reason/message, conflicts, warnings and every
   `(path, action, payload_fingerprint)`). A difference — a file that appeared,
   a directory that vanished, a versioned suffix now taken — replaces the shown
   plan, disables Generate and reports "The destination changed since this plan
   was reviewed, so the new plan is shown." Only an identical plan reaches
   `execute`.
7. `execute` receives the reviewed `GenerationPlan` object itself (the plan
   carries its `output.OutputPlan` in `.reviewed`), so the bytes written are the
   bytes the plan fingerprinted. Nothing is re-derived in Qt.
8. After execution the page clears the plan, moves to the Result tab and shows
   written/skipped/copied/errors. Any error also raises the problem box, so a
   partial write can never look like a clean success.

---

## 5. Output tree, manifest, assets and policies

Layout is whatever the existing planner produces; the page only displays it:

```
<chosen folder>/
  <project-slug>/
    <project-slug>.json                 base job (base scope only)
    <project-slug>__<variant>.json      one file per variant
    manifest.json                       variant runs only, written last
    assets/<name>[-N].<ext>             only under CopyIntoAssets when a file is copied
```

- **Naming / case collisions**: unchanged, `output.naming.slug`,
  `variant_directory_name`, `variant_file_name`; the page shows the resulting
  path verbatim.
- **Manifest**: `manifest_data` is built by the service; the page displays only
  the note that `manifest.json` records the run and is written last. The base
  scope deliberately produces no manifest.
- **Resources**: with `CopyIntoAssets` the Assets tab shows source, copied-to
  destination and the path the JSON will carry; `Versioned`/`Skip`/`Overwrite`
  affect files exactly as their existing contracts define. Percent-free
  absolute Windows paths are surfaced by the planner as warnings and are shown.
- **Atomicity**: per-file atomic write is the existing `output.execute`
  behaviour; the GUI does not claim a multi-file transaction. A mid-run failure
  is reported as a partial result listing what was already written.
- **Overwrite consequences in the confirmation**: the dialog repeats the chosen
  policy in words ("Stop and write nothing", "Replace the existing file", …), so
  the destructive choice is named at the moment of consent.

---

## 6. Tests, commands and results

All commands were run on Windows (Git Bash) from the repository root.

Baseline (recorded before this stage's edits, and re-confirmed from
`docs/GUI_STAGE3/4/5` reports): the full suite carries **13 pre-existing
`tests/e2e` failures** whose node IDs are identical in the Stage 3, 4 and 5
reports. They exercise the older numbered terminal menus (`menu_flows`) and the
old auto-name/`config-001` wording; none of them touches generation, the output
planner or the Qt package.

Commands run for this stage:

```bash
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py
python -m pytest -o addopts="" -q tests/unit/app
QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q
```

Results:

| Scope | Result |
| --- | --- |
| `tests/gui` (offscreen, PySide6 venv) | **214 passed** (190 before this stage + 24 new) |
| `tests/architecture` + `test_launchers.py` + `test_string_registry.py` + `tests/unit/app` | **172 passed** |
| `tests/architecture` + `test_launchers.py` + `test_string_registry.py` (re-run after the final wording edit) | **64 passed** |
| full suite | **1030 passed, 13 failed, 11 skipped** (4 min 06 s) |

Full-suite failures, all pre-existing and unchanged (identical node IDs to the
Stage 3/4/5 baseline; none is in `tests/gui`, `tests/architecture`,
`tests/unit/app`, `tests/unit/output` or `tests/serialization`):

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

No core test failure was introduced; nothing was skipped, weakened or deleted.

What the 24 new GUI tests prove, by assertion on real state:

- *Plan surface*: tab reachable, no plan and no enabled Generate at rest;
  pickers offer exactly `output_policy_choices()` and preselect
  `output_defaults()`; preview yields the service's paths for both variants and
  the manifest for a variant run; selected scope plans only its variant; base
  scope plans one file and no manifest; empty folder and missing variant are
  refused with the registered wording; Generate without a preview is refused.
- *Execution*: a valid plan writes `<slug>__v1.json`, `<slug>__v2.json` and
  `manifest.json`; the written JSON carries the variant's edit and the manifest
  carries project name, ordered variant keys and the two policies; the
  confirmation text names the destination; Generate is disabled afterwards;
  cancelling the confirmation leaves the folder empty and the result tab
  untouched.
- *Staleness*: folder change, policy change and a job change each invalidate the
  plan, disable Generate and write nothing; a file created between preview and
  confirmation blocks execution, is shown as a conflict and is left intact.
- *Policies*: `Fail` refuses the whole plan on one conflicting file (other files
  not written); `Skip` keeps the old bytes and reports the path as skipped;
  `Overwrite` replaces it with valid generated JSON; `Versioned` plans and writes
  `<slug>__v1-1.json` and leaves the original alone.
- *Errors*: an output root that is a regular file produces a user-facing problem
  message and an Errors section, not a traceback, and the file is untouched.
- *Validation*: a blocked/empty base and a blocked variant show the service's
  findings with the right note; selecting a finding opens the Entities tab; the
  review button opens Overview.
- *Assets*: with an external MSA and `CopyIntoAssets`, the Assets tab shows
  source, destination and emitted path, the written JSON contains
  `assets/chain-a.a3m`, and the copy exists under the project folder.

Additional verification performed directly:

- `python -c "import configbuilder, configbuilder.app.generation_service"` in
  the **core** interpreter (PySide6 not installed there): prints
  `PySide6 in core env: False` / `core import ok` — the core package still runs
  without the GUI extra.

---

## 7. Remaining limitations and decisions

1. **Assets table shows wire field names** (`unpairedMsaPath`, `mmcifPath`,
   `userCCDPath`). That is what appears in the JSON and in validation text, so
   it is precise; a friendly per-field label would need new registry entries and
   a mapping in the UI, which would duplicate mapping knowledge. Left as is,
   documented here.
2. **Findings without a record key**: selecting such a row is inert. The
   explicit fallback is the always-visible "Review configuration" button
   (→ Overview) and the note text now tells the user both routes. A header-level
   finding has no entity to open; inventing a jump target would be wrong.
3. **Execution is synchronous** on the UI thread. For this tool's file counts
   this is imperceptible; a progress/cancel surface would be new machinery
   (worker thread + service cancellation contract) that Stage 6 does not add.
4. **The output folder is not remembered** across sessions. Persisting it would
   change the project model and the manifest contract; not done.
5. **No global atomicity** is claimed for a multi-file run; the result view
   reports exactly what the service reports and labels an errored run as
   partial. This matches the existing `output.execute` semantics.
6. **Decision for the user**: whether the Generate page should later offer
   "generate and open the folder" or a remembered default folder. Both are new
   behaviours beyond the stage scope; neither was implemented.
7. **Pre-existing e2e failures** (13) remain. They belong to the terminal-menu
   suite and are unrelated to Stage 6; repairing them means updating that
   suite's expectations to the redesigned menu, which is a separate task.

---

## 8. Manual Windows verification checklist

Not performed by the agent (no real display was used; all GUI runs were
offscreen). To confirm on a Windows desktop:

1. Run `python gui.py`.
2. Open a valid AF3 JSON and review the import preview.
3. Create or open a job with at least one protein and any MSA/template or PTM
   settings from earlier stages.
4. Open Variants & Batch and create at least two distinct variants.
5. Open Generate & Output and choose a temporary output directory with the
   folder picker.
6. Review the planned tree, output paths, asset actions, manifest, warnings and
   conflicts.
7. Cancel once and confirm nothing was written.
8. Reopen the plan, confirm generation, and inspect the resulting JSON, assets
   and manifest.
9. Try the conflict policy against a destination containing a file; verify the
   described behaviour (Fail refuses all, Skip keeps, Overwrite replaces,
   Versioned writes a numbered copy).
10. Attempt an invalid/incomplete configuration and verify the user receives a
    clear explanation with findings.
11. Confirm `Save JSON…` still saves one valid file as before.
12. Resize the window and verify paths, tables and buttons remain usable.

Also worth a glance while manual testing: `python gui.py --demo` and
`python af3builder.py` still start.

---

## 9. Working-tree state

`git status --short` at the end of this stage, verbatim (66 entries). The working
tree was already dirty when Stage 6 began; the line ending in
`GUI_STAGE6_OUTPUT_GENERATION_IMPLEMENTATION_REPORT.md` is this report and is
the only entry the report itself added.

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
?? docs/IMPLEMENTATION_MAP.md
?? docs/IMPLEMENTATION_MAP_FULL.md
?? docs/JSON_BUILDER_AUDIT_AND_FINALIZATION.md
?? docs/THESIS_IMPLEMENTATION_CHAPTER.md
?? generated_jobs/
?? gui.py
?? pytest-of-Chris/
?? tests/analysis/
?? tests/gui/
?? tests/unit/test_launchers.py
```

Notes on that inventory:

- The Qt front end is entirely untracked (`?? configbuilder/ui/render/qt/`,
  `?? tests/gui/`), so the Stage 6 files inside those directories are folded
  into the directory entries. The files this stage added are
  `configbuilder/ui/render/qt/pages/generate.py`,
  `tests/gui/test_generate_output.py` and this report; `git status --short
  --untracked-files=all` lists the first two individually.
- `tests/unit/ui/test_string_registry.py` was already modified by earlier GUI
  stages; Stage 6 only widened the registry it checks, and it passes.
- No file was reset, cleaned, restored, stashed or committed. Nothing outside
  the Stage 6 scope was edited, and user files (including
  `docs/AF3_GUI_STAGE7_…` and `generated_jobs/`) were left untouched.

---

## 10. Verification honesty

- **Automated verification performed**: all commands and results in §6, plus
  the core-import check. These run the real page widgets, the real service
  layer, the real planner and the real serializer, and assert on the bytes and
  files produced on disk in `tmp_path`.
- **Visual / manual verification not performed**: no human or screenshot review
  of the page on a real display. Layout, readability of long paths, DPI scaling
  and keyboard focus order are therefore *unverified*; the checklist in §8 is
  how to close that gap.
- **Assumptions avoided**: service signatures, plan/result field names, policy
  names and layout rules were read from the working tree
  (`app/generation_service.py`, `app/results.py`, `output/plan.py`,
  `output/policies.py`, `output/naming.py`) before use; no path or field was
  guessed from earlier reports.
- **Not verifiable in this environment**: behaviour on a machine without write
  permission on the chosen folder beyond the "destination is a file" case, real
  native file-dialog interaction, and Windows-specific long-path (>260 chars)
  handling — the latter is inherited from the existing writer, not added here.
