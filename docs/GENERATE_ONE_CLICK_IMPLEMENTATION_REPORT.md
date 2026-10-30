# Generate page — one-click implementation report

**Request:** simplify the GUI's Generate option, because a user who just wants
their job written should not have to work through a preview and a confirmation
first.

**Decisions taken before implementing:** the page rework *plus* a footer
shortcut, and a confirmation **only** when a write would replace an existing
file whose content differs.

---

## 1. What the page did before

Four numbered cards (scope → destination → review plan → generate), and this
sequence to produce one file:

1. click **Generate** in the sidebar,
2. click **Preview plan** — the primary button was *disabled* until then,
3. click **Generate files**,
4. confirm a modal restating the counts, folder and both policies.

Findings behind those four clicks:

| Finding | Evidence |
| --- | --- |
| The preview was a gate, not a choice | `generate()` returned early unless `preview_plan()` had set `self._plan` |
| The modal repeated the page | it named the destination, counts and policies that were already on screen; a new file is not destructive |
| Four cards for one file | Step 1 held a single sentence (`One AF3 JSON file. No manifest.`); Step 4's button was enabled by Step 3 |
| **The page never marked the job saved** | it called `paths.remember_save_directory(...)` but not `state.record_save(...)`, so after a successful write the header still said *Unsaved* and closing asked to discard, while `Ctrl+S` cleared that state |
| Two overlapping write routes | `Save` (dialog, any path) and Generate (folder, `<job>\<job>.json`) wrote the same configuration with different defaults and different saved-state behaviour |

## 2. What it does now

```
Generate output files
One AF3 JSON file for the open job, written to the folder below ...
Base job: thesis_job - 1 entities

┌ Where the file goes ───────────────────────────────────────────────┐
│ Output folder  [ Documents\AF3Builder\saved_jobs        ] [Choose…]│
│ Will write: C:\Users\…\saved_jobs\thesis-job\thesis-job.json       │
│ Options ▾   (if a file already exists · external files)            │
│ [ Save job ]   Writes the file named above now; an existing file   │
│                is never replaced without asking.                   │
│ Nothing has been written yet.                                      │
└────────────────────────────────────────────────────────────────────┘
┌ Result ────────────────────────────────────────────────────────────┐
│ Wrote 1 file(s), skipped 0, copied 1 file(s).                      │
│ …paths…                                                            │
│ [Preview plan] [Open folder]                                       │
│ Warnings, conflicts and findings   (only when there are any)       │
│ Plan details ▾   (Files / Assets tables, Copy selected path)       │
└────────────────────────────────────────────────────────────────────┘
```

- **One click writes the file.** `generate()` plans and executes in one action.
  `Preview plan` still exists, but nothing is gated on it.
- **The exact path is named before the click**, from
  `GenerationService.base_file_path()` — the same helper `plan_base()` builds
  its path from, so the promise and the write cannot drift.
- **The only question is a replacement.** An existing file is confirmed once,
  naming it, and only when the bytes differ. Identical bytes are rewritten
  silently (the result is the same file).
- **The re-plan guard is kept.** Immediately before writing, the page plans
  again and refuses if the plan changed (another program wrote a file, a folder
  appeared), so `execute` never writes bytes the user did not see.
- **A successful write adopts the file as the job's saved state**
  (`state.record_save(destination)`), which fixes the dirty-flag defect: the
  header says *Saved* and closing no longer warns about losing work that is on
  disk.
- **Refusals are unchanged in substance**: no folder, blocking validation
  findings (with the findings table and *Review configuration*), or a conflict
  under the default `Fail` policy write nothing and print the service's own
  message. The button stays enabled, because the retry is the same click.
- **`Save to folder` in the FILE footer** does the same write with no dialog
  and without visiting the page: it sets the page's destination to the shared
  output folder and calls the same `generate()`, so there is one planning rule,
  one replacement question, one write and one saved-state update. `Save`
  (Ctrl+S) still asks for a path; nothing about it changed.

## 3. Service-side change (small, and only what the page needed)

`ConfigurationPlan` gained `different_content` (default `False`), set by
`plan_base()` when an existing file would be overwritten with different bytes.
`decide_action` labels an identical file `overwrite` as well — rewriting the
same bytes is harmless — so the front end could not otherwise tell the two
apart without reading the file itself. The decision stays in the service; the
page only reads the flag.

`GenerationService.base_file_path(output_root)` and the module-level
`_base_paths()` give the page the destination it displays; `plan_base()` now
uses the same helper instead of repeating `<root>/<slug>/<slug>.json`.

## 4. Tests

Rewritten for the new contract (they previously pinned the preview gate):
`tests/gui/test_generate_output.py` — 25 tests covering one-click write, the
exact path label, no question for a new file, the replacement question and its
cancel, identical bytes, `Skip`/`Versioned`/`Fail`, a file created after a
preview, the re-plan guard, unwritable folder, blocked job, finding navigation,
assets, and both footer-shortcut cases.

Updated where the layout or action list deliberately changed:
`tests/gui/test_stage8_ux.py`, `tests/gui/test_workflow_simplification.py`,
`tests/gui/test_final_layout_refinement.py`, `tests/gui/test_window.py`,
`tests/gui/test_mockup_shell.py`, `tests/gui/conftest.py`.

Results on this machine (Windows, Python 3.11.15, PySide6 6.12, offscreen):

| Run | Tests passed |
| --- | --- |
| `tests/gui` (whole suite) | 306 |
| `tests/unit tests/architecture tests/contract tests/serialization` | 1136 |
| `tests/e2e` | 138 |

The GUI run used `--basetemp=<project folder>`. Without it the three launcher
tests hang **in this environment**: `%LOCALAPPDATA%\Temp` denies writes to the
venv interpreter, so the tests' auto-close `sitecustomize` hook cannot write
its log, the real window never closes, and `subprocess.run`'s timeout leaves the
grandchild holding the pipe. That is an environment/ACL problem, not a code
failure — the same tests pass with a writable base temp, and the non-launch
accessibility tests pass either way.

## 5. Files changed

- `configbuilder/ui/render/qt/pages/generate.py` — rewritten to the two-card,
  one-action page (most of the change is deletion).
- `configbuilder/ui/render/qt/windows/main_window.py` — `Save to folder`
  action, footer button, menu entry, `save_to_folder()`.
- `configbuilder/ui/render/qt/dialogs/messages.py` +
  `dialogs/__init__.py` — `confirm_generation` replaced by
  `confirm_replacement`.
- `configbuilder/app/generation_service.py` — `base_file_path`, `_base_paths`,
  `different_content` on the base plan.
- `configbuilder/app/results.py` — `ConfigurationPlan.different_content`.
- `configbuilder/ui/render/qt/state.py` — `base_destination()`.
- `configbuilder/ui/present/strings.py` — the page's wording; the removed keys
  are gone rather than left as dead vocabulary.
- `RUNNING_THE_APPLICATION.md`, `manual_test_data/af3_builder/README.md` —
  describe the one-click flow and the footer action.

## 6. Remaining limitations

1. **The footer shortcut writes to the remembered output folder**, not to a
   path it invents: to change that folder, use the Generate page (or the
   `AF3BUILDER_OUTPUT_ROOT` variable). That is deliberate — one shared rule.
2. **The batch route is untouched.** `Generate configurations from file…` on
   the Entities page still previews before writing, because it creates many
   files and a manifest and its confirmation carries real information.
3. **`Open folder` uses the desktop's file manager** (`QDesktopServices`); on a
   machine with no handler it does nothing and returns False.
4. **`THESIS_EXPANDED_DRAFT.md` still describes the four-step page.** It is the
   user's own draft (untracked), so it was left untouched; the figure it
   references needs re-capturing if that text is kept.
5. **Manual Windows check still recommended**: double-click `run_gui.cmd`,
   press **Save to folder** on a job, confirm the JSON appears under
   `Documents\AF3Builder\saved_jobs\<job>\` and the header says *Saved*.
