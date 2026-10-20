# AF3 JSON Builder — Launcher Stage Implementation Report

Two root-level Python launchers (`af3builder.py`, `gui.py`) plus their tests
and a short run guide. No existing CLI or GUI architecture was changed: the
launchers delegate to the entry points that already exist, and every
pre-existing working-tree change was left exactly as found.

**Not verified here:** a real, interactive desktop window. See §6 — that is the
manual gate this stage stops at.

---

## 1. Files created / modified

### Created (all new; nothing existing was modified)

| File | Purpose |
| --- | --- |
| `af3builder.py` | Repository-root launcher for the console builder. A single delegation to `configbuilder.app.cli.main`; no menu, builder or service logic is duplicated. Importing it is side-effect free (the `__main__` guard starts the CLI). Needs no PySide6 and adds no dependency. |
| `gui.py` | Repository-root launcher for the optional PySide6 front end. Discovers the repository root from `Path(__file__).resolve().parent`, runs `<root>/.venv-gui/Scripts/python.exe -m configbuilder.ui.render.qt <args…>` with `subprocess` (an argument list, never `shell=True`), sets the child's working directory to the repository root, and propagates the child's exit code. If `.venv-gui` is missing it prints copyable setup commands and exits non-zero without launching or installing anything. On Windows it uses `Scripts/python.exe`; on other platforms it falls back to `bin/python`. |
| `tests/unit/test_launchers.py` | 19 focused tests for both launchers (§4). No PySide6, no display, no window; the subprocess call is injected. |
| `RUNNING_THE_APPLICATION.md` | Short user-facing run guide: the two commands, `--demo`, `.venv-gui` first-time setup, and the test commands. (No root README or existing usage doc was present, so a small dedicated file was created rather than rewriting anything.) |
| `docs/GUI_LAUNCHERS_IMPLEMENTATION_REPORT.md` | This report (placed beside the other GUI reports in `docs/`). |

### Modified

**None.** `git status --short` after the work shows the same tracked
modifications and untracked entries as the baseline snapshot, plus exactly the
four new files above. The GUI entry point
(`configbuilder/ui/render/qt/application.py`) was **not** touched: inspection
found no defect that blocked the wrapper, so no GUI change was necessary.

### Design notes (why the launchers look the way they do)

- **Delegation, not duplication.** `af3builder.py` imports the `cli` module and
  calls `cli.main()` at run time (not `from … import main`), so it delegates
  once and a monkeypatched `cli.main` is still observed. `gui.py` runs the
  existing module by name; it contains no GUI code.
- **Testable seams.** `gui.py` exposes small helpers — `repository_root()`,
  `gui_python()`, `build_command()`, `setup_commands()`,
  `missing_environment_message()` — and `main(argv=None, runner=None)` takes
  its subprocess callable as an injected parameter. That is what lets the tests
  assert the argv, the `cwd` and the exit code with nothing launched.
- **Honest failure.** A missing environment returns non-zero before any child
  starts; a child that fails is reported with its own diagnostic plus the
  install hint and its exact exit code. No silent interpreter fallback, no
  automatic install.

---

## 2. Exact commands

From the repository root:

```powershell
python af3builder.py                       # the console builder (no extras needed)
python gui.py                              # the desktop window (empty -> Open AF3 JSON…)
python gui.py --demo                       # built-in sample job, in memory only
python gui.py "C:\path\to\job with spaces.json"
python gui.py --help                       # the GUI launcher's own options
```

First-time `.venv-gui` setup (printed by `gui.py` when the environment is absent;
`pyproject.toml` declares the extra as `gui = ["PySide6>=6.6"]`):

```powershell
py -3.11 -m venv .venv-gui
.\.venv-gui\Scripts\python.exe -m pip install -e ".[gui]"
```

Verification form (repository layout may be distributed, but this checkout
already has a healthy `.venv-gui`).

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m configbuilder.ui.render.qt --demo
```

---

## 3. Was the packaging metadata checked first?

Yes. `pyproject.toml` declares the optional extra as
`gui = ["PySide6>=6.6"]` and the GUI entry point as
`[project.gui-scripts] af3-json-builder = "configbuilder.ui.render.qt.application:main"`.
The setup command offered by `gui.py` therefore installs `".[gui]"`, and the
launcher leaves `python -m configbuilder.ui.render.qt`, `configbuilder` and
`af3-json-builder` working unchanged (all three were re-run; §4). No `.bat`
file, shortcut, alias or packaging framework was added — none is required.

---

## 4. Tests and exact results

| Command | Result |
| --- | --- |
| `python -m pytest -o addopts="" -q tests/unit/test_launchers.py` | **19 passed** in 3.54s |
| `python -m pytest -o addopts="" -q tests/architecture` | **40 passed** in 6.50s |
| `$env:QT_QPA_PLATFORM = "offscreen"; .\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui` | **35 passed** in 1.09s |
| `python -m py_compile af3builder.py gui.py` | **COMPILE_OK** |

### Core suite, before vs after

```text
baseline: python -m pytest -o addopts="" -q   →  13 failed, 990 passed, 6 skipped, 1 warning in 117.58s
current : python -m pytest -o addopts="" -q   →  13 failed, 1009 passed, 6 skipped, 1 warning in 104.71s
```

- **No regressions.** `diff` of the sorted `FAILED` node ids from the two runs is
  **empty** — byte-for-byte the same 13 pre-existing stale end-to-end failures.
- **+19 passes** = exactly the new launcher tests. The 6 skips are unchanged
  (the audited baseline skip plus the five `tests/gui/` modules, which skip
  because PySide6 is not installed in the core environment — by design).

### Baseline vs current failing test IDs (identical)

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

These are the audited stale e2e keystroke/O default expectations. They were
**not** fixed or deleted; they are distinguished from regressions precisely by
the empty diff above.

### What the 19 launcher tests assert

| Group | Tests | Coverage |
| --- | --- | --- |
| `af3builder.py` | 5 | Importing the module in a real subprocess starts nothing; `main()` delegates to `cli.main` exactly once and propagates `0` and `4`; the module imports only stdlib/`__future__` + the one entry point; the real `python af3builder.py` reaches the menu and exits 0 on EOF. |
| `gui.py` command | 4 | `gui_python()` is `.venv-gui/Scripts/python.exe` (or `bin/python`); `build_command()` is `<python> -m configbuilder.ui.render.qt …`; a JSON path with spaces stays one element and `--demo` is not reordered; default `argv` is forwarded for `[]`, `--demo`, `--help`, spaced path. |
| `gui.py` launch | 3 | The child is run once from the repository root with `kwargs == {"cwd": root}` (no shell, no captured streams); exit codes `0/1/7` propagate; a failed child is reported with the install hint. |
| `gui.py` no environment | 2 | With no `.venv-gui`, an injected runner is **never called**, the message names the expected interpreter and both setup commands, and the exit is non-zero; `gui.py` imports only stdlib. |
| Real wrapper | 1 | `python gui.py --help`, skipped if `.venv-gui` is absent; exits 0 at argument parsing with no window. |

---

## 5. Non-interactive launcher checks actually run

```text
python gui.py --help
    → prints the GUI usage ("usage: af3-json-builder [-h] [--demo] [path]"), EXIT=0

printf '' | python af3builder.py
    → prints "JSON CONFIGURATION BUILDER" / "1. New job" menu, EXIT=0

printf '' | python -m configbuilder            → EXIT=0   (existing entry point still works)
.venv-gui\Scripts\python.exe -m configbuilder.ui.render.qt --help   → EXIT=0   (module path still works)
.venv-gui\Scripts\af3-json-builder.exe --help                       → EXIT=0   (console script still works)
```

The first two were also re-run directly and their exit codes confirmed. `gui.py
--help` exercises the launcher, the interpreter switch and the module path end
to end; `argparse` handles `--help` before any `QApplication` exists, so no
window opens. **No claim is made that a real interactive window was launched.**

---

## 6. Limitations and environment-specific issues

1. **No real window was opened by the agent.** Every GUI check here is either a
   `--help` round trip or a mocked subprocess. Whether the desktop window
   actually renders on this machine is the user's manual check (§7) — the
   launcher stage deliberately stops for it.
2. **Platform paths.** The Windows branch (`Scripts/python.exe`) was exercised
   on this checkout. The non-Windows branch (`bin/python`) is implemented and
   unit-tested through `os.name`, but was not run on a POSIX machine.
3. **`.venv-gui` already existed here** (PySide6 6.12.0 on CPython 3.11.15,
   pytest 9.1.1), so the "missing environment" path was verified with a
   hermetic temporary root, not by deleting the real environment. The
   environment was not modified.
4. **Core interpreter.** The core suite ran on the ambient interpreter
   (CPython 3.11.15) with PySide6 absent, as intended; the launcher tests need
   neither PySide6 nor a display.
5. Pre-existing environment note (unchanged, from the Stage 1 report): on this
   machine `pip`'s downloader has been observed to stall; `uv pip install` into
   the same virtual environment was used previously. The documented command
   remains `pip install -e ".[gui]"`.
6. The 13 pre-existing e2e failures remain and were intentionally left alone.

---

## 7. Manual verification checklist (for the user)

From the repository root `C:\Users\Chris\Desktop\THESISSP`:

1. `python af3builder.py` — the console menu appears; `0` exits cleanly.
2. `python gui.py` — **the desktop window opens** with the three tabs
   (Overview / Entities / Preview), the read-only notice, and an "Open AF3
   JSON…" toolbar action.
3. `python gui.py --demo` — the same window opens, labelled as the sample job,
   with a populated entity table and a JSON preview.
4. Close the window; the command returns, and the exit status is 0
   (`echo %ERRORLEVEL%` in cmd, or `$LASTEXITCODE` in PowerShell right after).
5. Optionally confirm the guard: temporarily rename `.venv-gui`, run
   `python gui.py`, and check it prints the setup commands and exits non-zero
   (rename back afterwards).

**Do not proceed to Stage 2 until you confirm step 2 (and ideally step 3)
succeeded.**
