# AF3 Builder — Installation, Launchers and Output Separation: Implementation Report

Implementation of the approved changes in
[`AF3_BUILDER_INSTALLATION_AND_OUTPUT_AUDIT.md`](AF3_BUILDER_INSTALLATION_AND_OUTPUT_AUDIT.md).

Scope: make the builder usable by a non-technical Windows user — one application
folder, one separate output folder, double-clickable launchers, and save/generate
defaults that do not depend on the current working directory. No packaging
framework, installer, new dependency or AF3 inference component was added.

---

## 1. Implemented installation and output layout

```text
C:\Users\<user>\
    AF3Builder\                          <- the application (user-writable)
        af3builder.py, gui.py
        configbuilder\
        setup_windows.bat, check_dependencies.bat
        run_gui.cmd, run_console.cmd     <- new, double-clickable
        .venv\
        README.md, DEPENDENCY_SETUP.md, RUNNING_THE_APPLICATION.md, docs\

    Documents\AF3Builder\                <- generated user data, outside the app
        generated_configurations\        <- batch output + manifest.json + assets
        saved_jobs\                      <- one saved job JSON + assets
        preferences.json is NOT here
```

Preferences live at `%APPDATA%\AF3Builder\preferences.json` — per-user, writable,
outside both trees.

Nothing in the implementation creates output folders inside the repository, inside
`.venv`, or next to the launchers. Verified by inspection of the console run in §8.

## 2. Shared output-root resolution

New module: `configbuilder/app/paths.py`, public entry point `OutputPaths`
(`resolve_root()`, `root()`, `generated_configurations()`, `saved_jobs()`,
`save_directory()`, `batch_directory()`, `default_save_path()`,
`default_batch_root()`, `remember_save_directory()`, `remember_batch_directory()`).

Resolution order (`OutputPaths.resolve_root()`):

| # | Source | Failure behaviour |
| --- | --- | --- |
| 1 | `AF3BUILDER_OUTPUT_ROOT` | reported as a diagnostic, next source used |
| 2 | remembered `output_root` in preferences | silently skipped when unusable |
| 3 | `<home>\Documents\AF3Builder` | diagnostic, next source used |
| 4 | `%LOCALAPPDATA%\AF3Builder` | — |

Guarantees:

- **Never** `os.getcwd()` / `Path.cwd()`. Launching from `C:\Windows` gives the
  same defaults as launching from the application folder.
- `Path.home()` and `os.path.expanduser` are used, so a redirected Documents
  folder (`OneDrive`-redirected profiles included, via `USERPROFILE`) is honoured.
- Directories are created with `mkdir(parents=True, exist_ok=True)` and accepted
  only when they end up as writable directories; a path that exists as a *file*,
  a read-only volume or an unauthorised location moves to the next source.
- Spaces and non-ASCII characters are ordinary: nothing is shell-split here.
- An explicitly configured but unusable `AF3BUILDER_OUTPUT_ROOT` is a reported
  condition, not a silent fallback and not a hard crash (`OutputRoot.diagnostics`).
- The module imports nothing from the UI layer (architecture rule unchanged:
  `app` never imports `ui`), and `tests/architecture/test_dependency_rules.py`
  still passes.

`generated_configurations` and `saved_jobs` stay distinct: batch output and a
single saved job are different operations with different contents.

## 3. Preferences format and persistence

`configbuilder/app/paths.py:Preferences`, stored at
`%APPDATA%\AF3Builder\preferences.json` (fallback `~/.config/AF3Builder/…` when
`APPDATA` is unset):

```json
{
  "last_batch_directory": "D:\\AF3 out\\batch",
  "last_save_directory": "C:\\Users\\<user>\\Documents\\AF3Builder\\saved_jobs",
  "output_root": "D:\\AF3 out"
}
```

- Keys: `output_root`, `last_save_directory`, `last_batch_directory`.
- Reads tolerate a missing file, unreadable file, invalid JSON, non-object JSON and
  non-string values — each case returns the defaults. No user-caused problem raises.
- Writes **merge**: one preference changing cannot erase another, and unchanged
  values are not rewritten (an existing file keeps its timestamp).
- Writes are atomic (`mkstemp` + `os.replace`); a failed write returns `False` and
  changes nothing. Remembering a folder is never a condition for saving a file.
- A remembered directory is only reused while it still exists and is writable; it
  is never resurrected if the user deleted it.
- Initial dialog destination precedence: valid last-used directory for that
  operation → the matching subdirectory under the resolved root → the resolved
  root itself (documented safe fallback).

## 4. Launchers

New files in the application root: `run_gui.cmd`, `run_console.cmd`.

Both:

- `cd /d "%~dp0"` — the application folder comes from the launcher's own path, so a
  Desktop/Start-menu shortcut, Explorer and a terminal behave identically;
- use `%ROOT%\.venv\Scripts\python.exe` (never a hard-coded drive letter, username
  or `python` from `PATH`);
- forward all arguments (`%*`) to the existing `gui.py` / `af3builder.py` entry
  points — no duplicated Python start-up logic was introduced;
- print an actionable message naming the missing interpreter and pointing at
  `setup_windows.bat` when `.venv` is absent, and name the missing entry-point file
  when the launcher is not inside the application folder;
- keep failures visible: `run_gui.cmd` deliberately uses `python.exe`, not
  `pythonw.exe`, and both `pause` on a non-zero exit with the exit status.
- change the working directory **only** for imports and internal resources. Output
  locations still come from §2, so launching from elsewhere cannot redirect output
  into the application folder.

Desktop/Start-menu shortcuts are documented in `README.md` (Send to → Desktop,
rename, optional "Start in"). The setup script was left unchanged: creating
shortcuts from a `.bat` (through PowerShell/WScript) adds failure modes for no
benefit, so it is documented rather than automated.

## 5. Console save and generation defaults

`configbuilder/ui/render/menus.py`:

- `MenuApp` now takes the shared service (`paths=`), defaulting to `OutputPaths()`,
  so the console and the window cannot disagree.
- Batch generation previously defaulted to `os.path.join(os.getcwd(),
  "generated_configurations")`. It now offers `default_batch_root()` —
  `<output root>\generated_configurations`, or the last successful batch folder.
- Save previously offered `self._current_path or <bare job-name>.json` (a bare
  name lands in the terminal's directory). It now offers the source file when the
  job came from one (re-saving over it is the existing, confirmed convention) and
  otherwise a full path in `saved_jobs`.
- A once-per-session line reports the output folder in force and any diagnostic
  (an unusable `AF3BUILDER_OUTPUT_ROOT` is therefore visible, not guessed at).
- The chosen folder is remembered only after the write succeeded
  (`outcome.ok` / after `_write_json` returned True), so a cancelled save or a
  refused batch leaves the next default where it was.

Per-job/per-entry folder structure, `manifest.json`, asset copying, relative-path
rewriting and the collision policy are untouched.

## 6. GUI save and generation defaults

- `GuiState` (`configbuilder/ui/render/qt/state.py`) owns one `paths` attribute —
  the same service, replaceable in tests.
- **Save JSON…** (`main_window.py`) offers the source file if there is one,
  otherwise `<output root>\saved_jobs\<job>.json`. Previously a bare
  `suggested_file_name()` meant the process's working directory — the defect the
  audit found. The containing folder is remembered after a successful write.
- **Generate page** (`pages/generate.py`): the destination field is now
  **pre-filled** (not merely placeheld) with `save_directory()` — `saved_jobs`, or
  the last export folder. Still an ordinary editable field. `plan.output_root` is
  remembered after a successful generate.
- **Entities batch action** (`pages/entities.py`): the folder picker is opened at
  `batch_directory()` instead of an empty dialog, and the same folder is what the
  preview names, so what is shown is what is written. Remembered after success.
- File-**open** dialogs and input-file selection were deliberately not changed.

## 7. Documentation

- `README.md` (new): install location and why not `Program Files`, setup, launchers,
  Desktop/Start-menu shortcut, output tree, precedence of output locations, Save vs
  Generate, `manifest.json` is builder-side only, transfer layout to the Linux
  server, `check_dependencies.bat`, moving the folder.
- `RUNNING_THE_APPLICATION.md`: launchers, working-directory clarification, a new
  "Where saved and generated files go" table with the full precedence.
- `DEPENDENCY_SETUP.md`: launch after setup, output separation, and the
  move-the-folder recovery step (rerun `setup_windows.bat` from the new location
  because the editable install recorded the old absolute path — the launchers
  themselves need no edit).

## 8. Verification (focused, not a full-suite run)

New tests:

| File | Tests | Covers |
| --- | --- | --- |
| `tests/unit/app/test_paths.py` | 27 | priority order, env override (valid/invalid/empty), Documents unavailable → LOCALAPPDATA, malformed/missing/non-object preferences, merge-on-write, atomic write failure, remembered-dir reuse and disappearance, `saved_jobs` ≠ `generated_configurations`, spaces in paths, cwd independence |
| `tests/unit/ui/test_output_defaults.py` | 9 | console save prompt offers `saved_jobs`, blank answer writes there, cwd stays empty, cancelled save remembers nothing, batch prompt offers `generated_configurations`, batch default writes manifest + configurations, batch folder remembered |
| `tests/gui/test_output_defaults.py` | 10 | Generate page pre-filled with `saved_jobs`, cwd independence, successful export remembered, batch picker opened at `generated_configurations`, successful batch remembered, the two folders stay distinct, Save JSON full-path default |
| `tests/unit/test_launchers.py` (extended) | +9 | both launchers locate their own folder, use `.venv\Scripts\python.exe`, no machine-specific paths, message + pause on a missing environment, GUI uses a console Python |

Suites run and their actual results:

- `tests/unit/app/test_paths.py tests/unit/ui/test_output_defaults.py tests/unit/test_launchers.py` — **65 passed**
- `tests/gui/test_output_defaults.py tests/gui/test_job_lifecycle.py tests/gui/test_generate_output.py` — **48 passed**
- `tests/unit/ui tests/e2e/test_variant_cli_subprocess.py tests/e2e/test_entity_batch_cli_subprocess.py` — **149 passed**

Real console runs (`python af3builder.py`, launched from a temporary directory that
is *not* the repository, with `USERPROFILE`/`APPDATA`/`LOCALAPPDATA` pointed at a
temporary profile and no `AF3BUILDER_OUTPUT_ROOT`):

1. **Batch, accepting the default folder (blank answer).**
   Default offered: `…\home\Documents\AF3Builder\generated_configurations`.
   Output: three configurations plus `manifest.json`, summary
   `Generated 3 AF3 configurations. Wrote 1 manifest. Total output files: 4.`
   The launch directory stayed **completely empty**; the preference file was created
   at `AppData\Roaming\AF3Builder\preferences.json`.
2. **New job, Save.** The prompt defaulted to
   `…\Documents\AF3Builder\saved_jobs\Untitled_job_1.json` (a full path, not a bare
   file name). The save was then refused by the pre-existing completeness gate
   because the job had no entities — correctly, and nothing was written and no
   preference was recorded.
3. **Opened fixture, Save.** The default was the file that was opened, with the
   existing explicit overwrite confirmation; cancelling wrote nothing and remembered
   nothing. This is the retained convention (see §9).

The successful into-`saved_jobs` write is asserted by
`tests/unit/ui/test_output_defaults.py::test_accepting_the_save_default_writes_into_saved_jobs`,
which reads the written JSON back and checks its `name`.

AF3 transfer layout was not changed and is still covered by the existing batch/e2e
suites (per-configuration folder, `assets\`, relative references, `manifest.json`).

**Windows execution:** the commands above ran on Windows 10/11 with Git Bash and
CPython 3.11; `run_gui.cmd` / `run_console.cmd` were **not** executed
(no interactive double-click in this session). Their content is verified by
inspection and by the launcher tests, which assert folder resolution, interpreter
path, quoting and failure messages. Double-clicking either launcher remains a
manual step (§10).

## 9. Remaining limitations

- **Saving an opened job defaults to that same file**, not to `saved_jobs`. This
  keeps the long-standing "Save" meaning; the overwrite is always confirmed, and
  the `saved_jobs` default applies to a job that has no file yet. Documented in
  `RUNNING_THE_APPLICATION.md`.
- Editable install: moving the application folder still requires rerunning
  `setup_windows.bat` (documented). A relocation-proof install would mean changing
  the packaging architecture, which the audit excluded.
- No installer, no Start-menu registration by the setup script; both are documented
  manual steps by design.
- The GUI's "Generate" page destination is remembered in the same
  `last_save_directory` key as Save JSON: both are single-job writes, so one key is
  the honest model. Batch output has its own key.
- A protected/invalid `AF3BUILDER_OUTPUT_ROOT` is reported in the interface, not
  raised as an exception; a front end that ignores diagnostics (a script) will
  silently use the fallback by design.
- On a machine where neither Documents nor `%LOCALAPPDATA%` is writable, the
  resolver returns the intended Documents path and reports it; the subsequent write
  fails with the ordinary filesystem error.

## 10. Manual verification on Windows

1. Copy/clone the folder to `C:\Users\<you>\AF3Builder`.
2. Double-click `setup_windows.bat`; wait for `SETUP SUCCEEDED`.
3. Double-click `check_dependencies.bat`; expect `READY` and exit status 0.
4. Double-click `run_gui.cmd` from the application folder → the window opens.
5. Create a shortcut on the Desktop, set **Start in** to the application folder,
   double-click it → the same window opens.
6. `File → Save JSON…` on a job with at least one entity → the dialog opens at
   `Documents\AF3Builder\saved_jobs` with the job's file name.
7. Entities page → *Generate configurations from a file* → the folder picker opens
   at `Documents\AF3Builder\generated_configurations`.
8. Open a terminal in `C:\Windows`, run
   `"C:\Users\<you>\AF3Builder\run_console.cmd"`, generate a batch and accept the
   default → output still appears under `Documents\AF3Builder`.
9. Set `set AF3BUILDER_OUTPUT_ROOT=D:\AF3 out` and rerun → the interface reports
   `D:\AF3 out`; the same variable set to an invalid path reports the problem and
   continues with the standard folder.
10. Copy one `generated_configurations\<job>\<job>__<entry>\` folder to the Linux
    server and run AF3 against its JSON.

## 11. Commit

- Commit `6ebb2b6` — "Keep saved jobs and generated configurations out of the
  program folder" — on `main`.
- Pushed to `origin` (`https://github.com/SalazarChris/ckthesis.git`),
  `323a698..6ebb2b6`, fast-forward; `main` tracks `origin/main` with no divergence.
- Staged explicitly, file by file. Untracked thesis documents, `docs/screenshots/`,
  `docs/ui_referene/`, `docs/deep-research-report.md` and scratch JSON/text files
  (`1`, `test.json`, `Untitled_job_1.json`, `vg_probe.txt`) were left untouched and
  unstaged.
- No force-push, no reset, no unrelated published history rewritten.
