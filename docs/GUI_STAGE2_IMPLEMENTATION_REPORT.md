# AF3 Builder GUI — Stage 2 (Job Lifecycle) Implementation Report

New Job, a Job Settings page and Save JSON…, wired to the existing services.
The GUI still owns no domain logic: it picks values, asks questions and calls
`ProjectService`, `ConfigurationService`, `ValidationService` and
`GenerationService`. It assembles no wire document, serializes no JSON,
allocates no identifier, re-evaluates no rule and writes no file itself.

Stage 2 also inherits the verified launcher stage (`af3builder.py`,
`gui.py`), which the user confirmed opens the desktop window.

---

## 1. Files created / changed

### Created

| File | Purpose |
| --- | --- |
| `configbuilder/ui/render/qt/pages/settings.py` | `JobSettingsPage`: job name, model seeds, JSON version. Each row shows the value in use plus whether it is the application default (`gui.settings_default`) or changed (`gui.settings_custom`); Apply sends exactly one field to `ConfigurationService`. A refusal shows the service's message and restores the current values. |
| `configbuilder/ui/render/qt/dialogs/messages.py` | The lifecycle modals: `show_problem` (generic refusal), `confirm_discard` (Discard / Keep the job, Cancel is the default button), `confirm_overwrite` (reuses the console's `menu.overwrite_*` wording), `ask_save_path` (native `QFileDialog.getSaveFileName` with `DontConfirmOverwrite`, because the explicit confirmation below is the one overwrite decision the window makes). |
| `tests/gui/test_job_lifecycle.py` | 18 Stage 2 tests (§4). |
| `docs/GUI_STAGE2_IMPLEMENTATION_REPORT.md` | This report. |

### Changed (GUI)

| File | Change |
| --- | --- |
| `configbuilder/ui/render/qt/state.py` | `new_job()` (through `ProjectService.new`, then refresh signals), `mark_saved()` / `is_dirty` (a saved-snapshot comparison mirroring `MenuApp._has_unsaved` — see §3), `record_save(path)`, `suggested_file_name()`, the three settings pass-throughs (`set_job_name`, `set_seeds`, `set_json_version`), and `plan_save` / `execute` pass-throughs. `commit_import` now marks the imported content as saved (console parity), and `build_demo_state` marks the sample as saved. |
| `configbuilder/ui/render/qt/windows/main_window.py` | New Job / Save JSON actions (toolbar and File menu), the discard guard on New / Open / Close, the save sequence (`choose path → confirm overwrite → plan_save → execute → record_save`), `report_problem` / `last_problem_text` for non-import refusals, the settings page as a fourth tab, Save enabled only while a job is open, and `closeEvent`. Module docstring no longer claims the window never writes. |
| `configbuilder/ui/render/qt/dialogs/__init__.py` | Re-exports the new dialog helpers. |
| `configbuilder/ui/render/qt/pages/__init__.py` | Exports `JobSettingsPage`. |
| `configbuilder/ui/present/strings.py` | **18 new `gui.*` entries** (actions, settings page, discard/save/problem wording) and 4 updated values: `gui.window_title` ("AF3 JSON Builder"), `gui.readonly_notice` (now describes the Stage 2 scope), `gui.cli_description` ("desktop builder window"). Additive inside the file's pre-existing modification; no other wording changed. Saving reuses the console's own `menu.save_*`, `menu.overwrite_*`, `menu.job_created` and `menu.not_applied` entries. |

### Changed (tests)

| File | Change |
| --- | --- |
| `tests/gui/conftest.py` | The autouse `no_modal_boxes` fixture now also replaces `show_problem`, `confirm_discard` (proceeds), `confirm_overwrite` (confirms) and `ask_save_path` (cancels) — the same seam pattern Stage 1 used for `show_failure`. Tests that need another answer replace the attribute on the window. |
| `tests/gui/test_window.py` | The Stage 1 "no writing action" test becomes the Stage 2 action-surface test (New Job, Open, Save JSON, Quit; generate/execute/export/variant wording still absent), the tab test now expects four pages, and Save's enabled state has its own test. `test_the_read_only_notice_is_visible` is renamed to `test_the_editing_scope_notice_is_visible` (same assertion). |

### Not changed (deliberately)

The service layer, domain model, transform, serializer, output/executor,
`MenuApp`, the CLI, the launcher files and the DNA behaviour are exactly as
found. The pre-existing working-tree changes are untouched; `git status`
shows no new tracked-file modification beyond `ui/present/strings.py`.

---

## 2. How each action uses the existing services

**New Job** → `ProjectService.new(None)`: the service's default policy
supplies the automatic name (`Untitled job N`), the default seed set (`[1]`)
and the default version pin (3). The GUI does not override or invent any
default, and shows them on the settings page. `GuiState.new_job` then marks
the new job as the saved snapshot and emits the existing `project_changed` /
`source_changed` signals.

**Open AF3 JSON…** → unchanged Stage 1 sequence (preview → Import/Cancel →
`import_json_commit`). The unsaved-changes question now sits **between** the
accepted preview and the commit, so Cancel keeps the open job and a user who
abandons the preview is never asked about a replacement that will not happen.

**Job Settings** → `ConfigurationService.set_name` / `set_seeds` /
`set_format_target`. Text seeds and the version number are parsed by the
service (or not at all — the version list is the console's own
`SUPPORTED_VERSIONS`). A refusal's own message is reported and the fields are
re-read from the service. A blank seeds field is treated as *no change*,
matching the console's `_edit_seeds`.

**Save JSON…** →

1. `save_path_chooser` (native save dialog; default = current source path,
   else the job name in the console's own `name_with_underscores.json` form);
2. explicit overwrite confirmation when the destination exists;
3. `GenerationService.plan_save(destination, overwrite=…)` — the same
   validation gate, transform, encode and §13.3 action table the console
   uses;
4. refused plan → the service's message is reported; for
   `VALIDATION_BLOCKED` the Overview is refreshed and brought to the front so
   the blocking findings are what the user sees, with
   `menu.save_job_blocked` on the status line. **No success message is shown
   and nothing is marked saved unless `execute` reports success**;
5. `GenerationService.execute(plan)` — writes exactly the reviewed bytes;
6. `GuiState.record_save(path)` — current path updated, saved snapshot
   recorded, source label refreshed. JSON semantics are untouched: the file
   is the serializer's bytes, and the round-trip test re-opens them through
   the ordinary import flow.

**Close** → `closeEvent` asks the same discard question; Cancel keeps the
window and the job.

---

## 3. Architecture notes

- **One source of truth for the job.** `ProjectService` owns the project;
  `GuiState` holds only "which file is open", "is this the demo" and the
  saved-snapshot used for dirty tracking. The snapshot is the *last saved
  `Configuration` object*: the model is immutable, so holding it is a
  complete snapshot — exactly how `MenuApp` tracks unsaved changes.
  `ProjectService.is_dirty` could not be used: it is set by every mutation
  and reset only by `open()`, so a saved job would still read dirty. No
  service was modified to accommodate the GUI.
- **No second implementation of anything.** Version choices are imported
  from `ui.render.menus.SUPPORTED_VERSIONS` (same `ui/render` family, so the
  architecture rules hold and the two front ends cannot disagree about which
  versions may be pinned) instead of being re-typed. Saving wording is the
  console's.
- **Presentation discipline.** Every new sentence is a registered `gui.*`
  entry; the string-registry meta-test (no unregistered user-visible literal,
  no dead entry) passes unchanged.
- **Optional GUI.** The core package still imports no PySide6; the GUI
  modules skip in a PySide6-less environment. Nothing new was added to
  `[project].dependencies`.
- **Testability seams.** `problem_reporter`, `discard_confirmer`,
  `overwrite_confirmer` and `save_path_chooser` are window attributes,
  assigned at construction, so the offscreen tests answer the questions
  deterministically and assert on the service interaction, the exact argv of
  the plan call, the bytes on disk and the resulting state.

---

## 4. Tests and exact results

| Command | Result |
| --- | --- |
| `$env:QT_QPA_PLATFORM = "offscreen"; .\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui` | **54 passed** in 1.80s (was 35) |
| `python -m pytest -o addopts="" -q tests/unit/test_launchers.py` | **19 passed** |
| `python -m pytest -o addopts="" -q tests/architecture` | **40 passed** |
| `python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py tests/architecture/test_dependency_rules.py` | **13 passed** |
| `python -m ruff check --select E4,E7,E9,F configbuilder` (CI's own lint selection) | 1 finding, **pre-existing** (`app/batch_variants.py` unused `FamilyBRecord`, a user-modified file); none in the Stage 2 files |
| Offscreen startup: `QT_QPA_PLATFORM=offscreen .venv-gui\Scripts\python.exe -m configbuilder.ui.render.qt --demo` | process alive after 6 s, empty stderr/stdout, then stopped — no import or startup error with the new page and actions |

### GUI suite by module (54)

| Module | Tests | Covers |
| --- | --- | --- |
| `test_window.py` | 8 | Shell, four pages, exact action surface, Save enablement, notice, source line, demo labelling. |
| `test_import_flow.py` | 11 | Stage 1 open workflow, unchanged. |
| `test_entity_table.py` | 6 | Stage 1 entity projection, unchanged. |
| `test_readiness.py` | 6 | Stage 1 readiness/findings, unchanged. |
| `test_preview.py` | 5 | Stage 1 JSON preview, unchanged. |
| `test_job_lifecycle.py` | 18 | Stage 2 (§4 below). |

### Core suite, current vs pre-Stage 2 baseline

```text
pre-Stage 2 (after launchers): python -m pytest -o addopts="" -q → 13 failed, 1009 passed, 6 skipped
after Stage 2:                 python -m pytest -o addopts="" -q → 13 failed, 1009 passed, 7 skipped
```

- **No regressions.** The sorted `FAILED` node-id lists are identical
  (`diff` empty).
- The 13 are the audited stale end-to-end tests, left untouched:
  `tests/e2e/test_entity_lifecycle.py::test_every_family_survives_a_full_lifecycle`,
  `…::test_an_imported_document_is_editable_like_a_built_one`,
  `…::test_a_long_repeated_chain_of_operations_leaves_consistent_state`,
  `tests/e2e/test_menu_acceptance.py::test_a_blank_job_name_is_generated_by_the_service`,
  `…::test_add_every_entity_family`,
  `…::test_job_settings_change_name_seeds_and_version`,
  `…::test_invalid_job_settings_are_refused_in_the_users_terms`,
  `…::test_the_job_menu_numbering_is_stable_across_states`,
  `…::test_the_entity_modifications_submenu_adds_edits_and_removes`,
  `…::test_ptm_management_adds_edits_and_removes`,
  `…::test_a_ligand_carries_no_modifications_and_is_told_so`,
  `…::test_open_json_can_be_cancelled_at_the_confirm`,
  `…::test_an_opened_job_can_be_edited_and_saved`.
- The extra skip is the sixth `tests/gui/` module reporting "PySide6 is not
  installed" in the core environment (6 GUI modules + 1 audited baseline
  skip = 7). The core pass count is unchanged at 1009, which also confirms no
  GUI test leaked into the core run.

### What the 18 Stage 2 tests assert

| Group | Tests | Coverage |
| --- | --- | --- |
| New Job | 6 | The service's `new` is called once with the default name; the service's defaults survive (`Untitled job 1`, seeds `(1,)`, pin 3); the discard prompt cancels cleanly (same project object, same configuration object) or proceeds; no prompt when nothing is unsaved; Close refuses and keeps the window, then closes when discarding; Open asks after an accepted preview, Cancel keeps the job and Accept commits the new one. |
| Job Settings | 4 | Fields show the service values and name the defaults; each Apply reaches `set_name` / `set_seeds` / `set_format_target` with exactly the typed value and changes the service's configuration; a refused name keeps the value and reports the service's message. |
| Save JSON | 8 | Refused with no open job; refused for an incomplete job — no file created, `VALIDATION_BLOCKED` displayed, Overview brought forward with the findings; a valid job goes through `plan_save` → `execute` with the exact arguments and the file bytes equal the reviewed plan payload, path and dirty state updated, `Saved to …` shown; a saved file re-opens through preview/commit with the same name and record ids; overwrite refused leaves the old bytes and reports cancellation, accepted replaces them with `overwrite=True`; dialog cancellation writes nothing; a filesystem error (destination under an existing file) reports the executor's message and leaves the job dirty and un-sourced; the dialog default is the suggested name, then the current path. |

---

## 5. Known issues and decisions

1. **The discard prompt offers Discard / Keep, not Save.** The console's
   prompt can save-and-leave; the GUI's Save needs a destination dialog, so
   Stage 2 keeps the prompt to the two safe answers. The user can press Save
   JSON… first. A "Save and discard" route is a candidate for Stage 3.
2. **DNA single-strand defect unchanged.** `MenuApp`'s "single-stranded DNA"
   path still deletes by list position after the service committed a duplex.
   Stage 2 neither ports nor hides it (the GUI has no entity editing yet), and
   it remains a separate issue to fix on its own.
3. **No service change-notification** beyond the existing
   `project_changed`/`source_changed` signals. A job mutated outside this
   window would need a manual refresh; Stage 2 always mutates through the
   state, which emits.
4. **Typing can be replaced by a refresh.** If another action triggers a
   refresh while a settings field is being edited, the field is re-read from
   the service. Acceptable for one window with explicit Apply buttons;
   per-field dirty state would be the fix if it ever bites.
5. **`SUPPORTED_VERSIONS` lives in the console menu module.** Importing it is
   deliberate (single source, legal within `ui/render`); a future cleanup
   could move it beside `DEFAULT_VERSION` in `app/status.py` and re-export it
   from the menu.
6. **No real dialog or native file picker was exercised by the agent.** The
   tests inject the answers; the real modal path for the *import* dialog is
   exercised by the Stage 1 timer-click test, but the Stage 2 dialogs
   (discard, overwrite, save chooser, problem) are asserted through their
   seams and need the manual checklist below.
7. **Not implemented by instruction:** entity add/edit/delete, variants,
   batch generation, PTMs, templates, MSA editing and bulk output planning —
   Stages 3+.
8. Window geometry, last directory and last-opened file are still not
   remembered (Stage 1 limitation), and the demo job is still in-memory only.

---

## 6. Manual test steps (for review)

From the repository root:

```powershell
python gui.py
python gui.py --demo
```

1. **New Job** — with no job open, New Job starts `Untitled job 1`; the
   Overview shows the service's readiness rows and the Job Settings tab shows
   the automatic name, seeds `1` and version 3, each marked "Application
   default".
2. **Settings** — change the name (Apply), set seeds to `1 2 3` (Apply), set
   the version to 4 (Apply). The Overview job facts and the readiness rows
   follow; saving preview shows the new values.
3. **Save JSON…** — Save JSON…, choose a path, confirm; `Saved to …` appears
   and the status bar names the file. Open the file and check the `name`,
   `modelSeeds` and version fields are the edited ones.
4. **Validation refusal** — New Job (discard), then Save JSON… immediately:
   a message reports the refusal, the Overview tab is brought forward with
   the blocking findings, and no file appears at the chosen path.
5. **Overwrite** — Save to the same path again; answer No → the old file is
   untouched and the status line says the save was cancelled. Save again and
   answer Yes → the file is replaced.
6. **Unsaved-changes prompt** — change the job name without saving, then
   press New Job; the prompt appears. Keep the job → nothing changes; press
   it again and discard → the new job starts. Repeat for opening a file and
   for closing the window.
7. **Round trip** — save a job, New Job, then Open AF3 JSON… the saved file;
   the preview summary is shown, Import loads the same job.

Stop and review before Stage 3 (entity management) begins.
