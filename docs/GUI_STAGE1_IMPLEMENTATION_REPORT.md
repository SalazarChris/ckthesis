# AF3 Builder GUI — Stage 1 (Review & Preview) Implementation Report

Read-only PySide6 desktop shell over the existing service layer. It opens an
AF3 JSON through the services' own preview/commit pair, shows the job, its
entity records, the readiness/findings the validation service already
produced, and the JSON the builder would write. It edits nothing and writes
nothing.

---

## 1. Files created / changed

### Created — the front end (`configbuilder/ui/render/qt/`)

| File | Purpose |
| --- | --- |
| `__init__.py` | Package docstring and the `main` re-export. Explains why the front end lives under `ui/render` (the family the architecture rules already allow to reach `app` and `ui/present`). |
| `__main__.py` | `python -m configbuilder.ui.render.qt` → `application.main()`. |
| `application.py` | Launcher / composition root (the Qt analogue of `app/cli.py`): builds a `GuiState` (or the demo state), shows `MainWindow`, returns the exit code. `--demo` and an optional path argument; Qt's own switches are left to the environment. |
| `state.py` | `GuiState`: the window's view of `build_services()`. Pass-throughs to `ProjectService` (preview/commit), `ValidationService`, `GenerationService`; owns only "which file is open" and "is this the sample job". No dirty flag, no second copy of the configuration. Also `build_demo_state()`, which builds the sample job through the ordinary service calls. |
| `models.py` | Read-only  `QAbstractTableModel` projections: `EntityTableModel` (over `configuration.records`), `FindingsTableModel` (over `format_findings`), `StatusTableModel` (over `ConfigurationStatus.fields`). Family / MSA / template / version wording resolves through the existing string registry. |
| `windows/main_window.py` | The `QMainWindow`: Open/Quit actions, three tabs, status bar (read-only notice + current source file), and the preview → confirm → commit sequence (`offer_import`, `report_failure`). |
| `pages/overview.py` | Job facts, readiness rows and verdict, findings table, finding → entity jump (emits the registry identifier). |
| `pages/entities.py` | Entity table plus the selected record's details (sequence or representation, description, modifications, MSA, templates, DNA duplex partner). |
| `pages/preview.py` | Read-only monospace JSON pane with a Refresh button; shows the service's refusal reason when there is no document. |
| `dialogs/import_preview.py` | Dumb `ImportPreviewDialog` rendering the service's summary rows and notes, plus `show_failure` for a refused file. Performs no service call and no file access. |
| `pages/__init__.py`, `dialogs/__init__.py`, `windows/__init__.py` | Re-exports. |

### Created — GUI tests (`tests/gui/`)

`__init__.py`, `conftest.py` (offscreen platform, skip when PySide6 is absent,
no-modal-boxes guard, service-built fixtures `state`/`filled`/`window`/`reviewed`),
`test_window.py`, `test_import_flow.py`, `test_entity_table.py`,
`test_readiness.py`, `test_preview.py` — 35 tests, listed in §4.

### Changed (2 files, both additive)

| File | Change |
| --- | --- |
| `configbuilder/ui/present/strings.py` | 59 new `gui.*` registry entries (window chrome, column headers, table/section labels) as one block of 64 lines at the end of `STRINGS` (lines 351–414). Required by the string-registry meta-test: no new fixed sentence may appear anywhere else in `ui`. The file's other 61 added / 30 removed lines pre-date this stage (the menu rework: PTM, DNA-complement, seeds-method and variant wording). |
| `pyproject.toml` | New `gui` optional extra (`PySide6>=6.6`), deliberately not in `dependencies` and not in `dev`; new `[project.gui-scripts]` launcher `af3-json-builder` — 16 added lines in total. The existing `configbuilder` console script is unchanged. The file's other 14 added / 1 removed lines pre-date this stage (the `analysis` extra and the `af3_analysis*` package include). |

Nothing else was touched: the service layer, domain model, transform,
serializer, `MenuApp`, the stale end-to-end tests and the CLI DNA behaviour
are all exactly as found (see `git status` in §6).

---

## 2. Install and launch

**Corrected 2026-10-16.** This section first claimed "Python 3.10 or newer is
required for the GUI (PySide6 ships `cp310-abi3` wheels only)". That is true of
the *current* PySide6 release only: 6.12.0 states `Requires-Python
<3.16,>=3.10` and ships `cp310-abi3`. The declared range `PySide6>=6.6` also
admits releases that still accept 3.9 (6.6.x: `>=3.8`, `cp38-abi3`; 6.7–6.10.x:
`>=3.9`, `cp39-abi3`), so on a 3.9 interpreter the `gui` extra resolves to
PySide6 6.10.3 and installs — it does not fail. Python 3.10+ remains the
**recommended and verified** interpreter for the GUI (it resolves to 6.12.0);
one of the thirty-five GUI tests needs PySide6 6.11.2 or later, see
`GUI_STAGE1_REVIEW_REPORT.md` §1 and §4. The core package still installs and
runs on 3.9 with no dependencies at all.

```powershell
# one-time: an isolated GUI environment, from the repository root
py -3.11 -m venv .venv-gui
.venv-gui\Scripts\python.exe -m pip install -e ".[gui]"      # PySide6 comes from the gui extra

# launch (any of these)
.venv-gui\Scripts\python.exe -m configbuilder.ui.render.qt                 # empty window → "Open AF3 JSON…"
.venv-gui\Scripts\python.exe -m configbuilder.ui.render.qt --demo          # built-in sample job, labelled as sample
.venv-gui\Scripts\python.exe -m configbuilder.ui.render.qt C:\path\job.json
.venv-gui\Scripts\af3-json-builder.exe                                     # after the editable install above
```

All four were started in this environment (offscreen); see §5.

The console application is unaffected:

```powershell
python -m pytest -o addopts="" -q          # core suite, no PySide6 needed
configbuilder                              # the interactive menu, as before
```

---

## 3. How the window is wired to the existing services

**Opening a file.** `MainWindow.open_json` picks a path (or the launcher passes
one), then `MainWindow.offer_import`:

1. `GuiState.preview_import(path)` → `ProjectService.import_json_preview(path)`.
   A refusal shows `ImportPreview.message` and returns; the open job is
   untouched and the file is only ever read.
2. `ImportPreviewDialog` renders `ImportPreview.summary` (job name, seeds,
   entity count, per-family counts, record ids) and `ImportPreview.notes`,
   plus the service's own "the original file has not been modified" line.
3. Only `Import` reaches `GuiState.commit_import(path)` →
   `ProjectService.import_json_commit(path)`; `Cancel` and a failed commit both
   leave `services.projects.project` exactly as it was. There is no other write
   path anywhere in the package.

**Entity data.** `EntityTableModel.set_configuration(configuration)` projects
`configuration.records` in the order the model holds them (identifiers from
`record.ids`, family from the record type, length or ligand representation via
the model's own `fold_representation`). Sorting is switched off on the view, so
no interaction can reorder the records the generated file inherits. The DNA
partner comes from the model's own `duplex_partner`, and a strand with no
partner says so rather than inventing one. Ligands, RNA and DNA show `-` for
MSA/templates instead of a plausible-looking guess.

**Readiness and findings.** `GuiState.status()` is
`ValidationService.status()`; `StatusTableModel` shows those rows and the
verdict line reads `ConfigurationStatus.ready` (and `len(status.blocking)`)
unchanged. Findings come from `ValidationService.validate_base().report` and
are formatted by the shared `ui.present.findings.format_findings`, so numbering,
severity tokens and wording are the console's. A finding's
`FieldPath.record_key` drives `EntitiesPage.select_record`, i.e. selecting a
finding moves the entity table to that record's row.

**JSON preview.** `GuiState.preview_json()` is
`GenerationService.show_json(None)`; the returned text goes into a read-only
monospace `QPlainTextEdit` verbatim, and when the service returns a reason
instead of a document the reason is displayed in full. The pane is labelled as
the builder's generated/normalised representation, not the imported file's own
formatting. No save, overwrite, generate or execute control exists.

**What the GUI deliberately does not do:** no wire dictionary is assembled, no
JSON is serialized or reformatted, no entity identifier is allocated, no
validation rule is re-evaluated, and no file is written or modified.

---

## 4. Tests and results

### Baseline (before the GUI work, this working tree)The prompt documents `13 failed, 990 passed, 1 skipped`. The tree was
re-measured rather than assumed. The measurement was taken with the new
`tests/gui/` modules present, which skip when the extra is absent, so the
arithmetic is visible:

```
python -m pytest -o addopts="" -q
13 failed, 990 passed, 6 skipped, 1 warning
```

990 passes — unchanged from the audit, i.e. the GUI modules contribute
nothing to the core run; 6 skips — the audited single skip plus the five
`tests/gui/` modules reporting "the GUI extra (PySide6) is not installed".

The 13 are the audited end-to-end failures: 3 in `tests/e2e/test_entity_lifecycle.py`
and 10 in `tests/e2e/test_menu_acceptance.py` (stale expected menus/outputs). They
are pre-existing and were left untouched.

### Final results

```
python -m pytest -o addopts="" -q                            # core, PySide6 NOT installed
13 failed, 990 passed, 6 skipped, 1 warning in 152.68s

python -m pytest -o addopts="" -q tests/architecture
40 passed in 7.56s

$env:QT_QPA_PLATFORM = "offscreen"; .venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
35 passed in 1.04s
```

* **No new core failures.** The failure set is byte-for-byte the audited one
  (same 13 node ids); the pass count is unchanged at 990, which also shows the
  new test files add nothing to the core run.
* **New skips are the GUI modules, by design.** 990 passed + 5 skipped modules =
  the 5 files in `tests/gui/`, which call `pytest.importorskip("PySide6")` so
  the core suite still runs on a machine (and a Python) without the extra:
  `1 baseline skip + 5 GUI module skips = 6 skipped`.
* The GUI suite runs against the installed extra in the isolated 3.10+
  environment and needs no display.

### What the 35 GUI tests assert

| File | Tests | Coverage |
| --- | --- | --- |
| `test_window.py` | 7 | The window opens/closes; three read-only tabs; an empty state reports "no project" instead of failing; the only actions are Open and Quit (and no registered save/write/generate/execute/overwrite/export wording appears on any action); the read-only notice; the status bar's source line; `--demo` labels its data as sample. |
| `test_import_flow.py` | 11 | Preview changes nothing; the preview reports the file's own summary; the dialog shows the summary, the notes and the not-modified notice; the dialog's buttons really carry the accept/reject roles; the file is committed through the **real modal dialog**, clicked by a zero-delay timer (watchdog-guarded so a dead button fails instead of hanging); Cancel leaves the open project and the source path untouched; Import commits (and the pages follow); invalid JSON and a missing file are refused with the service's reason and leave the project untouched; the source file's bytes and mtime are identical after preview **and** commit. |
| `test_entity_table.py` | 6 | Rows equal `configuration.records` in order (same identifiers, same tuple identity); each row's family/summary/description/modifications/MSA/templates values; copy multiplicity shows every identifier; asking the model for a sort neither reorders the configuration nor the rows; `row_for_record_key`; the window's table is the service-backed model. |
| `test_readiness.py` | 6 | The status rows equal the service's own rows; a ready job says ready; a blocking job says how many findings block it; the findings table shows every service finding; a blocking `R-ENT-007` points at record `A` and the window selects that row; the status bar names the imported file. |
| `test_preview.py` | 5 | The pane equals `show_json`'s text; the text is the builder's document (key order, `dialect`, `version`, name, one entry per record); the editor is read-only; a refused preview shows the reason and displays nothing; Refresh re-asks the service rather than caching. |

---

## 5. Verification performed beyond pytest

* **The real modal import path.** `tests/gui/test_import_flow.py::test_the_real_modal_dialog_commits_when_import_is_clicked`
  runs `MainWindow.offer_import` through the ordinary modal `exec()` and
  presses the dialog's own Import button from a timer (2 s watchdog reject, so
  a broken button fails rather than hanging). The printed pass means the modal
  loop, the button roles and the commit all work together — the same path a
  user takes.
* **Launch, both entry points, offscreen.** `python -m configbuilder.ui.render.qt --demo`
  and the installed `af3-json-builder.exe --demo` were started; both stayed up
  with an empty stderr log until stopped. `af3-json-builder.exe --help` prints
  the launcher's usage (`path`, `--demo`).
* **Packaging.** `uv pip install -e . --no-deps` into the GUI environment
  registers `console_scripts: configbuilder = configbuilder.app.cli:main`
  (unchanged) and `gui_scripts: af3-json-builder = …qt.application:main`, and
  reports the `gui` extra. A `gui-scripts` entry means the packaged launcher
  runs under `pythonw.exe` — no console window — which is what the comment in
  `pyproject.toml` claims.
* **The CLI still works.** `python -m configbuilder` with EOF on stdin prints
  the normal menu and exits 0; nothing in `app/`, `ui/render/menus.py` or
  `ui/services.py` was touched.
* **Environment finding (not a project defect).** On this machine `pip`'s own
  downloader stalled indefinitely (PyPI's index page and the same wheel files
  fetch fine through plain HTTPS at ~1 MB/s, and pip hangs after
  `Looking up … in the cache`, both for `pip install` and for a trivial
  `pip download six`; `pip install --upgrade pip` hung for ten minutes). The
  documented command remains `pip install -e ".[gui]"`; here the same wheels
  were installed into the same virtual environment with
  `uv pip install --python .venv-gui\Scripts\python.exe PySide6 pytest`
  followed by
  `uv pip install --python .venv-gui\Scripts\python.exe -e . --no-deps`
  (PySide6 6.12.0, on CPython 3.11.15). Worth re-checking on a machine where
  pip behaves normally.
* **Python 3.9 packaging edge case (corrected 2026-10-16).** `requires-python`
  was left at `>=3.9` and CI's 3.9 job is untouched. This bullet originally
  claimed that `PySide6>=6.6` has no 3.9 wheels, so a 3.9 `pip install -e
  ".[gui]"` fails loudly with "no matching distribution". **That is wrong.**
  Verified against the PyPI metadata (2026-10-16) and by resolving the declared
  range with `uv pip compile`: 3.9 resolves to PySide6 6.10.3
  (`Requires-Python <3.15,>=3.9`, `cp39-abi3-win_amd64` wheel) and 3.11 resolves
  to 6.12.0, both successfully — a loud failure would need the constraint
  tightened to `PySide6>=6.11`. The real 3.9-era gap is behavioural, not a
  resolution failure: on PySide6 6.6.0–6.11.1 one GUI test fails (34 passed, 1
  failed) because `window.menuBar().actions()[0].menu()` returns an invalid
  wrapper there, while the window's File menu itself is alive and pops up
  normally. `GUI_STAGE1_REVIEW_REPORT.md` §1 and §4 record the measurements and
  the two minimal corrections (raise the floor to `>=6.11.2`, or bind the action
  in the test helper). `pip install .` and `pip install -e ".[dev]"` on 3.9
  continue to work unchanged, since the extra is opt-in and the core has no
  dependencies.

---

## 6. Working tree

```
$ git status --short
 M configbuilder/app/batch_variants.py          ← pre-existing (user's work, untouched)
 M configbuilder/app/status.py                  ← pre-existing
 M configbuilder/app/variant_service.py         ← pre-existing
 M configbuilder/persistence/__init__.py        ← pre-existing
 M configbuilder/persistence/sequences.py       ← pre-existing
 M configbuilder/ui/present/strings.py          ← pre-existing + 59 new gui.* entries (additive)
 M configbuilder/ui/render/menus.py             ← pre-existing
 M pyproject.toml                               ← pre-existing (analysis extra) + gui extra, gui-scripts
 M tests/unit/… (8 files)                       ← pre-existing
?? configbuilder/ui/render/qt/                  ← new (this stage)
?? tests/gui/                                   ← new (this stage)
?? (plus the pre-existing untracked docs, af3_analysis/, tests/analysis/, generated_jobs/)
```

No commit, reset, stash or cleanup was performed; the pre-existing changes and
untracked files are as found. Generated scratch (the `.venv-gui/` environment,
pip temp directories) is outside version control — `.gitignore` already covers
`.venv*/`.

---

## 7. Known limitations and decisions for Stage 2

1. **No change notification from the services.** Nothing in `app` emits a
   signal, so `GuiState` refreshes the pages explicitly: after a committed
   import (`project_changed`) and through the Refresh button. A job mutated by
   another front end in the same process would need a manual refresh. If Stage 2
   adds editing, the service layer gains one change-notification seam — the GUI
   should consume it, not poll.
2. **Import does not pair DNA strands.** The audited single-strand DNA
   behaviour is visible here: importing a document with one DNA strand yields
   one DNA record, while `add_record("dna", …)` yields the duplex pair. The GUI
   reports either faithfully (a strand with no partner says "no partner") and
   deliberately does not compensate. Fixing the DNA service is a separate task.
3. **Findings are shown as the console shows them.** The list is grouped and
   numbered by the shared presenter; technical detail (rule id, diagnostic,
   suggestion) is available as the row's tooltip and in the detail line under
   the table rather than in its own column. If reviewers want the rule id
   visible, that is a presentation change in `ui/present`, not a GUI change.
4. **One window, no session memory.** Window geometry, the last directory and
   the last opened file are not stored; no settings file is written (Stage 1
   writes nothing at all).
5. **The demo job is in-memory only.** `--demo` builds its sample through the
   services and never touches disk, so it cannot be used to produce a file.
6. **Untested by design:** nothing here exercises a real display, a real file
   dialog, or Windows packaging (PyInstaller) — out of scope for Stage 1.
