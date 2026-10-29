# AF3 JSON Builder — Installation, Launching, Saving and Output Management Audit

**Type:** read-only practical audit. No source, launcher, setup script, configuration
file, fixture or existing document was modified; nothing was installed, executed or
benchmarked. The only artifact of this task is this report.

**Audit date:** 2026-10-29
**Branch / HEAD:** `main` @ `323a698` ("Import inline templates, check index mappings,
and report batch outputs honestly"), working tree carrying only the user's untracked
thesis and scratch files.

Evidence labels used throughout, as in the project's earlier audits:

- **SOURCE-CONFIRMED** — established by reading the current code/document.
- **ARTIFACT-CONFIRMED** — established by a file that exists on disk in this checkout.
- **UNVERIFIED** — would need runtime execution to settle; not executed here.
- **NOT FOUND** — the capability does not exist in the current tree.

---

## 1. Executive summary

The builder is a **source-run Python application**: a user gets a checkout, runs
`setup_windows.bat` once to create `.venv` and install the project with its `gui` and
`templates` extras, then starts either front end from a **terminal**:

```powershell
python af3builder.py     # console
python gui.py            # desktop window
```

There is no installer, no Start-menu entry, no desktop shortcut, and no launcher that
can be double-clicked to start the application. The two `.bat` files that *can* be
double-clicked are setup (`setup_windows.bat`) and diagnosis
(`check_dependencies.bat`) only. `.venv\Scripts\` does contain `configbuilder.exe` and
`af3-json-builder.exe` (console/GUI entry-point scripts), but nothing documents them,
and neither is created as a user-facing shortcut.

The **output story is the weakest part**, and it is not one story but three:

1. **The console's default output root is the current working directory**:
   `<cwd>/generated_configurations` for file-based generation, and a bare
   `<job-name>.json` (again resolved against the cwd) for saving a job. Where that
   lands therefore depends entirely on how the user opened the terminal. Started from
   `C:\Windows\System32` it is not writable at all; started from the repository it
   writes generated files into the source tree.
2. **The window has no default output folder at all.** The Generate page's output
   field starts empty and the folder pickers are called with no starting path, so the
   only "default" is whatever the native dialog remembers.
3. **`gui.py` forces the GUI's working directory to the repository root**
   (`cwd=str(root)`, `gui.py:156`). Since the task of choosing an output folder is
   deferred to a file dialog, the visible consequence is smaller than in the console —
   but a save dialog accepted without changing the folder writes `job.json` **and its
   `assets/` folder into the repository root**. Two such files are present in this
   checkout right now (`Untitled_job_1.json`, `test.json`), and a real generation tree
   sits in `output/` (both ARTIFACT-CONFIRMED).

The good news is that everything below the folder choice is already sound and
well-tested: generated names are deterministic slugs, each configuration directory is
self-contained, external MSA/template/CCD files are **copied into `assets/` beside the
JSON** with forward-slash relative references by default, re-opening a saved job
resolves those relative references against the JSON's own folder, and a failed run
rolls back what it created. The application has **no internal data files** to find at
runtime (all behaviour is Python code), so relocating the application folder does not
break resource lookup — only the editable-install path inside `.venv`, which a re-run
of `setup_windows.bat` repairs.

**Recommendation in one line:** keep the current source packaging, add one shared
"where do outputs go" policy (a `Documents\AF3Builder` tree, independent of the cwd),
and add two double-clickable launchers in the application folder. No installer, no
PyInstaller build, no architectural change.

---

## 2. Repository and audit scope

### 2.1 Repository state

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `323a698` — Import inline templates, check index mappings, and report batch outputs honestly |
| Modified tracked files | none (clean) |
| Untracked, user-owned | `THESIS_EXPANDED_DRAFT.md`, `docs/THESIS_*`, `docs/Thesis*`, `docs/screenshots/`, `docs/ui_referene/`, `.fix_root`, `1`, `test.json`, `Untitled_job_1.json`, `vg_probe.txt` |
| Ignored local output | `output/oct4-pou/…`, `generated_jobs/…`, `pytest-of-*/`, pip scratch dirs |

Nothing in the untracked set was read for behaviour; the two root-level JSONs and
`output/` are cited only as **artifacts** of where the application has written.

### 2.2 Files inspected

Launchers and setup: `af3builder.py`, `gui.py`, `setup_windows.bat`,
`check_dependencies.bat`, `tools/check_dependencies.py`.

Packaging: `pyproject.toml`, `.venv/pyvenv.cfg`,
`.venv/Lib/site-packages/__editable___configbuilder_0_1_0_finder.py`, `.venv/Scripts/`.

Path and output logic: `configbuilder/app/cli.py`,
`configbuilder/app/project_service.py`, `configbuilder/app/generation_service.py`,
`configbuilder/app/results.py`, `configbuilder/output/plan.py`,
`configbuilder/output/execute.py`, `configbuilder/output/naming.py`,
`configbuilder/output/policies.py`, `configbuilder/output/manifest.py`,
`configbuilder/persistence/schema.py`, `configbuilder/persistence/store.py`,
`configbuilder/transform/from_wire.py`,
`configbuilder/ui/present/strings.py`, `configbuilder/ui/render/menus.py`,
`configbuilder/ui/render/qt/application.py`,
`configbuilder/ui/render/qt/windows/main_window.py`,
`configbuilder/ui/render/qt/state.py`, `configbuilder/ui/render/qt/pages/generate.py`,
`configbuilder/ui/render/qt/pages/entities.py`,
`configbuilder/ui/render/qt/dialogs/batch_input.py`,
`configbuilder/ui/render/qt/dialogs/messages.py`.

Documentation: `RUNNING_THE_APPLICATION.md`, `DEPENDENCY_SETUP.md`,
`docs/WINDOWS_PACKAGING.md`, `manual_test_data/af3_builder/README.md`,
`docs/CONFIGURATION_GENERATION_PRACTICAL_AUDIT.md`,
`docs/CONFIGURATION_GENERATION_FIX_REPORT.md`.

### 2.3 Out of scope / not executed

No test suite, no `pytest`, no `setup_windows.bat`, no `pip`, no Qt window, no AF3
inference, no AF3 validation tool. Runtime claims that could only be settled by
launching are labelled **UNVERIFIED**.

---

## 3. Current CLI and GUI launch behaviour

### 3.1 The console (`python af3builder.py`)

| Question | Answer |
|---|---|
| Entry point | `af3builder.py:29-36` → `configbuilder.app.cli.main()` (`app/cli.py:31-32`) → `MenuApp(services, Console()).run()` |
| Uses `.venv`? | **Only if the user activates it or types `.venv\Scripts\python.exe`.** The file is a plain Python module; whatever interpreter runs it is the one used (SOURCE-CONFIRMED) |
| Locates the project relative to itself? | Yes for imports: Python puts the script's own directory on `sys.path`, so `python C:\…\AF3Builder\af3builder.py` works from any cwd (SOURCE-CONFIRMED) |
| Requires cwd = repository root? | **No for imports, yes for output defaults** — see §4 (SOURCE-CONFIRMED) |
| Launchable from Explorer / shortcut / other directory? | Technically yes (with an interpreter), but nothing in the repository offers a double-clickable CLI launcher (**NOT FOUND**) |
| Spaces / non-ASCII in paths | Not handled by `af3builder.py` at all (it takes no path arguments); they matter only inside the console's own prompts, which take text and support `~` expansion (`menus.py:465`) |
| Missing Python / missing library | The launcher is Python; without Python the double-click does nothing usable (there is no `.bat` wrapper). Missing libraries cannot happen for the console: the core package declares **no** runtime dependencies (`pyproject.toml:15`) |
| Errors visible? | Yes, in the terminal the user started |
| Moving the app folder | Imports still work if launched by its new path. The **editable-install mapping inside `.venv` keeps the old absolute path** (`.venv/Lib/site-packages/__editable___configbuilder_0_1_0_finder.py:9`: `MAPPING = {'configbuilder': 'C:\\Users\\Chris\\Desktop\\THESISSP\\configbuilder', …}`), so `.venv\Scripts\python.exe` stops importing the package until the editable install is re-run (ARTIFACT-CONFIRMED + SOURCE-CONFIRMED) |
| Shortcuts | **NOT FOUND** — no `.lnk`, no Start-menu registration, no documented procedure |

### 3.2 The window (`python gui.py`)

| Question | Answer |
|---|---|
| Entry point | `gui.py:134-166` → child process `<root>\.venv\Scripts\python.exe -m configbuilder.ui.render.qt <args>` (`gui.py:53,75-100,134`) |
| Uses `.venv`? | **Yes** — explicitly prefers `.venv`, falls back to a legacy `.venv-gui` (`gui.py:53,56,75-100`) |
| Locates resources relative to itself? | Yes: `repository_root()` is `Path(__file__).resolve().parent` (`gui.py:66-73`), never the cwd |
| Requires cwd = repository root? | No — the child is started with `cwd=str(root)` (`gui.py:156`), *forcing* the repository root regardless of where the user launched from |
| Launchable from Explorer / shortcut / other directory? | `python gui.py` needs a terminal. A shortcut to `pythonw.exe gui.py` or to `.venv\Scripts\af3-json-builder.exe` would work but is **undocumented and UNVERIFIED** |
| Spaces / non-ASCII | Handled correctly: arguments are forwarded as separate list elements, no shell (`gui.py:105-113`); the module docstring and tests claim spaces-in-path support |
| Missing environment / library | Prints copyable setup commands and exits `1` without starting anything (`gui.py:141-148`); a child failure prints the child's status plus the setup commands (`gui.py:159-166`) |
| Errors visible? | Yes, in the console for `python gui.py`. **A shortcut to `pythonw.exe` or to `af3-json-builder.exe` has no console**, so a startup failure there would be invisible (**risk, UNVERIFIED**) |
| Moving the app folder | `gui.py` still finds `.venv` (both are relative to the script). The venv's editable mapping is stale as above; `pyvenv.cfg`'s `home=` points at the *base* interpreter, not the project, so it survives |
| Shortcuts | **NOT FOUND** |

Note the **inconsistency**: `gui.py` pins cwd to the repository root, while
`python -m configbuilder.ui.render.qt` and `af3-json-builder.exe` inherit the caller's
cwd (`application.py:56-78` never changes it). Same application, three launches, two
different cwds — which matters only because some defaults are relative (§4).

### 3.3 `setup_windows.bat`

| Question | Answer |
|---|---|
| Working directory | `cd /d "%~dp0"` on the first line, with an explicit failure branch (`setup_windows.bat:3-4,110-112`) — correct for Explorer double-click from any folder |
| Interpreter | Explicit override argument or `PYTHON`, else `py -3`, else `python` (`:13-15,28-52`) |
| Environment | Creates `.venv` **in the repository root**, reuses an existing one, never deletes it (`:29-58`) |
| Install command | `"%VENV_PY%" -m pip install -e ".[gui,templates]"` (`:76`) — matches `pyproject.toml`'s `gui` and `templates` extras |
| Verification | Runs `tools\check_dependencies.py --root "%ROOT%"` and fails the script if it fails (`:80-81`) |
| Errors visible? | Yes — `pause` before exit (`:136-139`) keeps the window open on both success and failure |
| Global Python touched? | No: everything goes into `.venv` |
| Desktop/Start-menu shortcuts | **NOT FOUND** — the script creates none and documents none |

### 3.4 `check_dependencies.bat` and `tools/check_dependencies.py`

| Question | Answer |
|---|---|
| Working directory | `cd /d "%~dp0"` (`check_dependencies.bat:3`) |
| Interpreter | Prefers `.venv\Scripts\python.exe`, falls back to the legacy `.venv-gui` one, and refuses to guess another (`:6-7,11-18`) |
| Read-only? | Yes. The checker imports packages, runs `pip check`, starts the CLI at EOF and a short offscreen Qt smoke test; it installs nothing (SOURCE-CONFIRMED) |
| Root resolution | `project_root()` uses `Path(__file__).resolve().parent.parent` (`tools/check_dependencies.py:78-81`) — cwd-independent |
| Writes files? | No report file, no log: the report is printed and `pause`d (`:39-48` of the `.bat`). The doc says so explicitly |
| Shortcuts | Not needed — it is a double-clickable `.bat` already |

### 3.5 Everything that depends on the current working directory

Searching the runtime packages for `os.getcwd()` / `Path.cwd()` yields exactly **two**
hits, both in the console front end:

| Location | What it does | Practical consequence |
|---|---|---|
| `menus.py:424` | The console's file picker lists `os.getcwd()` | The "choose a file" list starts in the directory the terminal was opened in, not next to the user's data |
| `menus.py:1683` | `default = os.path.join(os.getcwd(), "generated_configurations")` | The console's generation default lands in the cwd |

Two further cwd dependencies are implicit:

| Location | What it does | Consequence |
|---|---|---|
| `menus.py:1526-1527` | Save default is `self._current_path` or `<job-name>.json` (relative) | With no current path, `plan_save` resolves it with `os.path.abspath` (`generation_service.py:965`) → **cwd** |
| `state.py:129-135` + `main_window.py:429` | The GUI's save-dialog default is the source path or `<job-name>.json` | Relative → the GUI's cwd, which `gui.py` pins to the repository root |

There are **no** relative reads of internal resources: the application ships no data
files (the only `Path`-relative fixtures are in `tools/`, and they are resolved against
`project_root()`). Nothing in `configbuilder/` reads `docs/`, a config file or a
settings file.

---

## 4. Current output-path matrix

Defaults below are from the source, not from labels.

| Workflow | Current default location | Destination selection | Depends on working directory? | Supporting assets | Collision behaviour |
|---|---|---|---|---|---|
| **Save/export current job** (window "Save JSON…", `main_window.py:411-455`; console "6 Save and show summary", `menus.py:1518-1560`) | The file it was opened from, else `<job-name>.json` — i.e. the cwd (GUI: the repository root) | Native save dialog (window) / typed path with `~` expansion (console) | **Yes** when the job has no source path (`generation_service.py:965`) | Under the default `CopyIntoAssets` policy, external templates/MSA/CCD are copied to `<save dir>/assets/` and the JSON references `assets/…` (`generation_service.py:977-1000`; `plan.py` asset naming) | Window asks "replace?" before planning; console asks too; with a confirmed overwrite the plan may replace (`generation_service.py:954-958`) |
| **File-based configuration generation** (console `7 → 1`; window Entities → "Generate configurations from file…") | Console: `<cwd>/generated_configurations`. Window: **no default** — empty field/folder dialog | Console: typed path or blank for default (`menus.py:1683`). Window: `QFileDialog.getExistingDirectory` with no start path (`dialogs/batch_input.py:94-98`, `pages/entities.py:355-386`) | **Console: yes. Window: no (folder is mandatory)** | Per-configuration `assets/` copies, relative forward-slash references (`plan.py:212-260`) | Default policy `Fail`: one existing file with different content refuses the whole batch before anything is written; identical bytes are rewritten |
| **Base-job generation** (window Generate page, `pages/generate.py`) | **No default** — the destination field is empty with a placeholder (`pages/generate.py:185-212`, `:394-403`) | Typed path or Browse (`pages/generate.py:394-404`) | No (mandatory field) | `assets/` copies as above | Same `Fail` policy; review-before-write |
| **Manifest** | Written **only** by a variant/batch run, at `<output_root>/<project-slug>/manifest.json` (`generation_service.py:562`) | No separate choice — it follows the run's output root | No (derived from the run) | — | Same policy as the run's files; byte-reproducible content, no timestamp (`output/manifest.py`) |
| **Dependency diagnostics** (`check_dependencies.bat`) | **Writes nothing**; prints a report and pauses | — | No (`project_root()` from `__file__`) | — | NOT APPLICABLE |
| **Logs / diagnostic files** | **NOT FOUND** — no log file, no report file, no crash dump is written anywhere by the application or the checker | — | — | — | — |
| **Internal state / preferences** | **NOT FOUND** — no `QSettings`, no config file, no last-used folder, no autosave (`.gitignore` still reserves `.configbuilder/`, but `project_service.py:1-9` records that the autosave was removed) | — | — | — | — |

Consequences worth stating plainly:

- **The console's default output is wherever the terminal happens to be.** Started
  from the repository root (as every document instructs), generation writes
  `<repo>/generated_configurations/…`; started from `C:\Windows\System32` it fails on
  permissions. Started from `Documents`, it writes there. Three launches, three answers.
- **The window requires an explicit folder**, so it cannot write into the repository
  *by default* — but nothing suggests a sensible, stable folder either, and the
  "where do my files go?" answer changes with whatever folder the native dialog
  remembers.
- **Saving is the sharper hazard**: a save accepted without typing a path writes the
  JSON *and* an `assets/` folder into the current directory — in the window's case the
  repository root. The two stray JSONs at the repository root are that signature.

---

## 5. Current setup and dependency behaviour

- **Python floor:** `requires-python = ">=3.9"` (`pyproject.toml:9`). The GUI is
  verified on 3.10+; the local `.venv` here is 3.11.15 (ARTIFACT-CONFIRMED).
- **Core dependencies:** none (`pyproject.toml:15`). The console needs only Python.
- **Optional extras:** `dev` (pytest, hypothesis), `analysis` (numpy, pandas, …),
  `templates` (gemmi), `gui` (PySide6) (`pyproject.toml:17-57`).
- **Entry points:** `configbuilder` → console (`pyproject.toml:59`);
  `af3-json-builder` → GUI (`:68`). Both land in `.venv\Scripts\` (ARTIFACT-CONFIRMED:
  `configbuilder.exe`, `af3-json-builder.exe`).
- **Setup script:** creates `.venv`, upgrades pip, `pip install -e ".[gui,templates]"`,
  runs the diagnostic, pauses (`setup_windows.bat:69-84`). It refuses to delete a broken
  environment and gives a rename-then-rerun recovery (`:54-59,98-102`).
- **Checker:** read-only; statuses PASS/MISSING/INCOMPATIBLE/OPTIONAL/WARNING; nonzero
  exit on a required failure (`DEPENDENCY_SETUP.md`; `tools/check_dependencies.py`
  `Report.exit_code`).
- **Isolation from AF3 inference:** explicit and correct — the setup installs the local
  builder only; no GPU stack, model weights or server software is mentioned or touched.
- **First-run experience for a non-technical user:** they must (1) obtain the folder,
  (2) find and double-click `setup_windows.bat`, (3) read a console window, (4) open a
  terminal and type `python gui.py`. Step 4 is where an ordinary Windows user stops.
  Every later launch repeats step 4. **There is no clickable application launcher.**

---

## 6. File-writing workflow inventory

Every write path goes through the same pipeline (`output/plan.py` decides, `execute`
writes atomically with a temp file + `os.replace`, and rolls back files it created if a
later write fails — `output/execute.py`).

| Workflow | Files written | Where |
|---|---|---|
| Save current job | 1 JSON (`<name>.json` or the chosen path) + `<dir>/assets/*` for each external resource | The chosen path |
| Base generation (window Generate) | `<output_root>/<project-slug>/<project-slug>.json` + `assets/` inside that project folder | `<output_root>` (user-chosen) |
| Batch / variant generation | `<output_root>/<project-slug>/<project-slug>__<key>/<project-slug>__<key>.json`, each with its own `assets/`, plus `<output_root>/<project-slug>/manifest.json` | `<output_root>` |
| `setup_windows.bat` | `.venv/` tree (plus pip caches elsewhere), nothing else in the project | Repository root |
| `check_dependencies.bat` | Nothing | — |
| Logs | **NOT FOUND** | — |

Whether the application can write **into the installation directory**: yes, in two
ways — `.venv` is created there by setup (by design), and a console/default save or
generation whose resolved default is the repository (or a cwd inside it) writes job
JSON and `assets/` there. Whether the *installation* folder is writable is not checked
anywhere: nothing refuses a location like `C:\Program Files\…`, where `.venv` creation
would fail (setup reports the pip/venv error, `setup_windows.bat:104-106,113-122`).

---

## 7. Application-root versus output-root analysis

| Concept | Current state | Evidence |
|---|---|---|
| **Application installation directory** | Only `gui.py` has one (`repository_root()` from `__file__`). The console has none: it is whatever directory the script happens to be in on `sys.path` | `gui.py:66-73`; `af3builder.py:29-36` |
| **Internal application resources** | **None at runtime** beyond Python modules. No data directory, no bundled model, no template files read by the app. Import-time location is Python's own `sys.path` | `grep` over `configbuilder/` for relative reads; `tools/check_dependencies.py` is the only root-aware reader |
| **Default output directory** | Console: cwd-derived (`generated_configurations` / bare filename). Window: none (mandatory choice) | `menus.py:1683`, `:1526`; `pages/generate.py:185-212`, `:394-403` |
| **Persistent preferences** | **NOT FOUND** | no `QSettings`, no config file |
| **Base for relative references inside an imported AF3 JSON** | The **JSON's own folder** — `rebase_resource_paths(document, dirname(abspath(path)))` before the model is built | `project_service.py:159-163`; `from_wire.py:535-580` |
| **Base for asset paths written into generated JSON** | The **output JSON's own folder**: `CopyIntoAssets` emits `assets/<slug>.<ext>`, always with forward slashes | `plan.py:220-281`, `_forward_slashes()` 142-145 |

So the code already separates "where the document lives" from "where the process runs"
**for reading resources** — the gap is that no such separation exists for **choosing
default destinations**. That is the single design defect worth fixing.

---

## 8. External resource and relative-path behaviour

| Resource | At import | At save/generate (default `CopyIntoAssets`) | After moving the files | Evidence |
|---|---|---|---|---|
| External structural template (`mmcifPath`) | Relative path resolved against the JSON's folder; content validated (structure, single protein chain, index bounds when gemmi is installed) | Copied to `<json dir>/assets/<slug>.cif`; JSON emits `assets/…` | Works: the reference is relative to the JSON, which travels with `assets/` | `from_wire.py:535-580`; `plan.py`; `reference_validation.py` |
| External MSA (`unpairedMsaPath` / `pairedMsaPath`) | Same rebasing | Copied into `assets/` per configuration | Works | `plan.py`; `to_wire` external requirements |
| External custom CCD (`userCCDPath`) | Same rebasing | Copied into `assets/`; `userCCD` stays absent (mutually exclusive) | Works — pinned by `tests/e2e/test_app_pipeline.py` (already in the suite) | `plan.py`; `to_wire` |
| Inline template (`mmcif`) / inline `userCCD` | Carried verbatim | Not copied (nothing external) | Works | `from_wire._import_references`; `transform/accessors.py` |
| A resource referenced with an **absolute** path | Kept absolute | Under `CopyIntoAssets` it is copied and rewritten relative — the travelling case. Under `AsGiven`/`RelativeToOutput` it stays absolute and does **not** travel | `AsGiven`/`RelativeToOutput` outputs break on another machine; the planner emits a warning | `plan.py:245-281` |

**Practical rule for the user:** generator default is the safe one; if the options are
ever exposed, `CopyIntoAssets` is the only choice that survives the transfer.

---

## 9. Recommended installed folder structure

**Recommendation: one portable application folder at a user-chosen location, with one
separate output tree in the user's Documents.** This is Option A's application
placement combined with Option B's output placement, and it is the smallest change to
what already exists.

```text
C:\Users\<user>\AF3Builder\                     <-- the ONE application folder
    af3builder.py            console entry
    gui.py                   window entry
    configbuilder\           the application package
    pyproject.toml
    setup_windows.bat        first-run setup (double-click)
    check_dependencies.bat   diagnosis (double-click)
    run_console.cmd          NEW: double-clickable console launcher
    run_gui.cmd              NEW: double-clickable window launcher
    .venv\                   created by setup; machine-local, not portable
    DEPENDENCY_SETUP.md, RUNNING_THE_APPLICATION.md

C:\Users\<user>\Documents\AF3Builder\           <-- the ONE output tree
    generated_configurations\
        <job-name>\
            manifest.json
            <job-name>\<job-name>.json          (base job, when generated)
            <job-name>__<entry>\<job-name>__<entry>.json
                              \assets\…
    saved_jobs\
        <job-name>.json
        assets\…
```

### Why this and not the alternatives

| Option | Verdict |
|---|---|
| **A — portable sibling folders** (`AF3Builder\` + `AF3Builder_Output\`) | Good if the user keeps both in a synced/portable location, but output next to the program invites "inside the app folder" clutter, and a folder copied from a USB stick is often read-only. Use only when the user explicitly wants a fully portable set. |
| **B — `%LOCALAPPDATA%` app + `Documents` output** | Installing the source into `%LOCALAPPDATA%` hides the application from the user, which makes "double-click `setup_windows.bat`" impossible to discover and makes support harder. **Output side is right; app side is wrong for this project.** |
| **C — user-selected installation** | Already implicit: the folder is a checkout the user unzips wherever they like. Keep it, but *document* the recommended default (`Documents\AF3Builder` is a poor app location because Documents is often synced; `C:\Users\<user>\AF3Builder` is better). |
| **Chosen hybrid** | App in a user-chosen, user-writable folder (never `Program Files`); outputs in `Documents\AF3Builder`. Portable if the user prefers sibling folders — the code change is one environment variable either way. |

### What belongs where

**Application folder:** the files above (source, `pyproject.toml`, the two `.bat`
setup/check scripts, the two new launchers, docs, `.venv`).

**Not in an ordinary user installation:** `tests/`, `tests/fixtures/`, `fixtures/`,
`docs/*PROMPT*`, `docs/*REPORT*`, `manual_test_data/` (optional; useful for a smoke
test), `generated_jobs/`, `output/`, `pytest-of-*/`, `pip-*` scratch dirs, the user's
`Untitled_job_1.json`/`test.json`, and the editable-install `.egg-info`.

**Output folder:** only generated artifacts — never source, never `.venv`.

**Protected locations:** if the app folder ends up under `C:\Program Files`, setup
cannot create `.venv` (no admin rights). The recommendation is therefore explicit:
install under the user's profile. A future guard could detect the path and refuse
early with that sentence; today the failure surfaces as a pip/venv error.

---

## 10. Recommended default output location and preference storage

1. **One resolver, used by both front ends.** A small `app/paths.py` (or a function in
   `ui/services.py`) exposing `default_output_root()` and `default_saved_jobs_dir()`,
   resolving in this order:
   1. the `AF3_BUILDER_OUTPUT` environment variable, if set;
   2. the value persisted in preferences (§10.3), if present and writable;
   3. `Path.home() / "Documents" / "AF3Builder"` (Windows resolves `Documents`
      correctly, including OneDrive redirection, via `Path.home()`);
   4. fallback `%LOCALAPPDATA%\AF3Builder` when `Documents` is unavailable.
   Never the cwd.

2. **Wire the defaults in three places:** the console's `menus.py:1683` default, the
   window Generate page's empty destination field (`pages/generate.py:185-212`, `:394-403`), and
   the batch folder picker's start path (`dialogs/batch_input.py:94-98`). The save
   dialogs (`main_window.py:429`, `menus.py:1526`) should default to
   `<saved_jobs>/<job-name>.json` when the job has no source path — not to a bare
   relative name.

3. **Preferences:** a single small JSON at
   `%APPDATA%\AF3Builder\settings.json` (roaming, tiny, survives updates) holding
   `last_output_root` and the two policy names. Written only on a *successful* run, read
   with a tolerant parser (a corrupt file must fall back to the default silently).
   Do **not** write preferences into the application folder: it may be read-only, and
   it makes the folder dirty for updates.

4. **Keep the current policy defaults** (`Fail` + `CopyIntoAssets`,
   `persistence/schema.py:49`): they are the safe, transferable combination.

5. **Do not change the generation layout.** `<root>/<slug>/…` with `assets/` beside each
   JSON is deterministic, self-contained and already verified; a `generated_configurations`
   folder is a *destination choice*, not a layout change.

---

## 11. Recommended launcher and shortcut behaviour

**Add two launchers to the application folder** (the smallest thing that removes the
terminal step):

```bat
@echo off
rem run_gui.cmd — double-click to open the window
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto :missing
start "" ".venv\Scripts\pythonw.exe" "gui.py" %*
exit /b 0
:missing
echo The local environment is missing. Double-click setup_windows.bat first.
pause
exit /b 1
```

and the analogous `run_console.cmd` using `.venv\Scripts\python.exe af3builder.py`
(console, so its window stays for interaction). Both `cd /d "%~dp0"` — the
cwd-independence `gui.py` already enforces, applied to the console as well.

Notes:

- **`pythonw.exe` hides startup errors.** Prefer `run_gui.cmd` with `pythonw.exe` only
  if `gui.py`'s precondition check is kept ahead of it (run it with `python.exe` first
  when `.venv` is missing, as above), or keep `python.exe` for the GUI launcher and
  accept a console window — the current GUI already prints diagnostics there.
- **Shortcuts (P3, optional):** a `create_shortcut.cmd` that calls PowerShell's
  `WScript.Shell` to drop a Desktop shortcut to `run_gui.cmd` with *Start in* = the
  application folder. No installer, no registry writes. Alternatively document
  "right-click `run_gui.cmd` → Send to → Desktop (create shortcut)".
- **Do not** create a shortcut to `.venv\Scripts\af3-json-builder.exe` or
  `configbuilder.exe`: their behaviour when launched with Explorer's cwd
  (`C:\Windows\System32`) is **UNVERIFIED**, and a shortcut without *Start in* would put
  any relative default there.
- **Do not** build a PyInstaller bundle as part of this work; `docs/WINDOWS_PACKAGING.md`
  already records it as documented-but-not-built, and it would not fix the path policy.

---

## 12. Practical installation, launch and saving walkthrough (current vs. recommended)

### As it works today

1. Copy the checkout to, say, `C:\Users\Anna\AF3Builder`.
2. Double-click `setup_windows.bat`; wait for *SETUP SUCCEEDED*; press a key.
3. Open PowerShell, `cd C:\Users\Anna\AF3Builder`, run `.\.venv\Scripts\python.exe gui.py`.
4. Build the job; **Save JSON…** → the dialog offers `job.json` in the repository root →
   pick `Documents\my-job.json` (and note that an `assets\` folder appears beside it).
5. Or **Entities → Generate configurations from file…** → pick the input type, the file,
   then a folder — the field is empty, so choose `Documents\AF3Builder\…`.
6. Find the outputs in that folder: `<job>\<job>__<entry>\<job>__<entry>.json` + `assets\`,
   plus `<job>\manifest.json`.

The console route is the same, except step 3 is `python af3builder.py` and step 6's
folder is *whatever the terminal's directory was*, typed by the user at the prompt.

### With the recommended changes

1. Same steps 1–2 (unchanged).
2. Double-click **`run_gui.cmd`** (or a Desktop shortcut to it).
3. Build the job; **Save JSON…** opens directly in
   `Documents\AF3Builder\saved_jobs\` with `my-job.json`.
4. **Generate configurations from file…** → choose an input type and a file; the folder
   field is pre-filled with `Documents\AF3Builder\generated_configurations` (still
   editable).
5. Launching from a shortcut, a terminal, or another directory produces the **same**
   default folder.

---

## 13. Confirmed defects and potential risks

Severity reflects practical user impact. "Confirm" = established from source/artifacts.

| # | Severity | Finding | Source | Current behaviour | User consequence | Recommended correction | Regression risk | Verification |
|---|---|---|---|---|---|---|---|---|
| R1 | **High** | The console's output root is the cwd (`<cwd>/generated_configurations`) | `menus.py:1683` | Depends on the terminal's directory; may be unwritable or inside the source tree | "My files went somewhere I do not know"; possible permission failure in `System32` | One `default_output_root()` (§10), never the cwd | Low — one default string changes; the user can still type any path | Run the console from three directories and confirm the offered default is identical in all three and outside the repo |
| R2 | **High** | The window's save dialog defaults to a bare relative name, and the GUI's cwd is pinned to the repository root (`cwd=str(root)`) | `gui.py:156`, `main_window.py:429`, `state.py:129` | Accepting the dialog writes `job.json` + `assets/` into the app folder | User data lands inside the program folder; an update/cleanup could lose it; artifacts `Untitled_job_1.json`, `test.json` already show it | Default to `<saved_jobs>/<job-name>.json`; stop pinning cwd once defaults do not need it | Low–Medium — the GUI cwd also affects the file-open dialog's start; change the default path first, revisit the cwd separately | Save a job without typing a path; confirm the file lands in `saved_jobs`, not the repo |
| R3 | **High** | Moving/renaming the application folder leaves the editable install pointing at the old absolute path | `.venv/…/__editable___configbuilder_0_1_0_finder.py:9` (ARTIFACT-CONFIRMED) | `.venv\Scripts\python.exe -m configbuilder…` fails to import after a move; `gui.py` cannot start the app | A copied/moved folder "stops working" with a traceback, and nothing tells the user to re-run setup | Document it in `DEPENDENCY_SETUP.md` ("after moving the folder, re-run `setup_windows.bat`") and have `gui.py`/the checker detect an import failure and print that sentence | Low if documentation-only; Medium if the launcher gains a pre-flight import check | Copy the folder, run `run_gui.cmd`, confirm the message names the fix; re-run setup in the copy and confirm it starts |
| R4 | **Medium** | No double-clickable application launcher exists (setup/check only) | **NOT FOUND** in root/`docs` | Every launch requires a terminal and the correct command | The step where a non-technical user stops; contradicts "double-click a file" expectation | Ship `run_gui.cmd` and `run_console.cmd` (§11) | Low — new files, existing launchers untouched | Double-click both from Explorer with an existing `.venv` and with none (expect the setup message) |
| R5 | **Medium** | The window's Generate page has **no** default destination | `pages/generate.py:185-212`, `:394-403` | Empty field; the user must browse every time | "Where should these go?" with no guidance; the chosen folder is forgotten next session | Pre-fill `default_output_root()` (editable) | Low — a pre-filled text field | Open the page on a fresh start; confirm the field is pre-filled and generation still writes there |
| R6 | **Medium** | No remembered last-used folder or preferences at all | no `QSettings`/config (**NOT FOUND**) | Folder choices are re-made every session | Repeated navigation; inconsistent destinations | `%APPDATA%\AF3Builder\settings.json` (§10.3), written on success only | Medium — new write path; must never block a run when unreadable | Corrupt the file deliberately; confirm the app still starts and falls back |
| R7 | **Medium** | `python -m configbuilder.ui.render.qt`, `af3-json-builder.exe` and `gui.py` give the GUI **three different cwds** | `application.py:56-78` vs `gui.py:156` | Relative defaults differ by launch method | Same app, different destination depending on how it was started | Make every launch use the resolved defaults (R1/R2), which removes the cwd's influence; then the difference is harmless | Low | Launch all three ways and compare the save dialog's initial folder |
| R8 | **Low** | `.venv\Scripts\configbuilder.exe` / `af3-json-builder.exe` exist but are undocumented and unverified when double-clicked | ARTIFACT-CONFIRMED; docs silent | Undiscoverable; their cwd when started from Explorer is unverified | A user who finds them may launch from `System32` | Either document them with *Start in* guidance or keep them as developer entry points and promote `run_*.cmd` | Low | Launch each once from Explorer and record cwd + first default |
| R9 | **Low** | Setup does not detect a protected installation folder | `setup_windows.bat:28-52` | `python -m venv .venv` fails with a raw error under `Program Files` | Confusing failure for a user who "installed" it like a normal program | One early check: if `%ROOT%` starts with `%ProgramFiles%`, print the "copy it under your user folder" instruction | Low | Copy the repo under `Program Files`, run setup, confirm the explicit message |
| R10 | **Low** | No top-level `README.md`; the install instructions live in two other files | **NOT FOUND** | A visitor sees spec/audit documents first | Discoverability | A short root `README.md` pointing at `DEPENDENCY_SETUP.md` and `RUNNING_THE_APPLICATION.md` | None | Read-only |
| R11 | **Low** | Generated output can be written inside the checkout (`output/`, `generated_configurations/`) | ARTIFACT-CONFIRMED (`output/oct4-pou`) + R1 | Source tree holds generated jobs | Confusion between code and data; accidental commits avoided only by `.gitignore` | R1's fixed default outside the tree; keep the `.gitignore` entries | None | Generate with a blank console answer; confirm the output is outside the repo |
| R12 | **Low (design)** | Save and Generate are different operations with different output shapes (one file vs. a project folder) | `generation_service.py:917` vs `:784` | A saved job is one JSON + `assets/`; a generated job is `<root>/<slug>/…` | "Where is my file?" ambiguity | Keep the shapes (they are correct) and state them in one sentence in the UI hint and in `RUNNING_THE_APPLICATION.md` | None | Read-only |

### Not defects (checked and working)

- Console and window share one generation pipeline; both refuse conflicts before
  writing; both copy assets by default.
- Relative resource references are resolved against the **JSON's** folder on import.
- A failed batch rolls back the files it created and never deletes a pre-existing file.
- The setup and checker scripts are cwd-independent and keep their result on screen.
- Nothing writes logs, telemetry, registry keys or autosave state.

### Hypotheses needing runtime confirmation

- The native folder dialog's starting folder when called with `""` (R5's "remembered
  folder") is Qt/Windows behaviour, not application state — **UNVERIFIED**.
- Whether `af3-json-builder.exe` starts correctly from Explorer, and with which cwd —
  **UNVERIFIED**.
- Whether a Desktop shortcut to `run_gui.cmd` inherits the script's `cd /d "%~dp0"` when
  *Start in* is unset — expected yes for a `.cmd`, **UNVERIFIED** here.

---

## 14. Prioritized implementation plan

Nothing below was implemented.

### P0 — Correctness and data safety

| Item | Change | Files | Expected behaviour | Regression risk |
|---|---|---|---|---|
| P0-1 | One `default_output_root()` / `default_saved_jobs_dir()` resolver; wire into the console generation default and both save defaults | new `configbuilder/app/paths.py` (or `ui/services.py`); `ui/render/menus.py:1683,1526`; `ui/render/qt/windows/main_window.py:429`; `ui/render/qt/state.py:129` | Defaults are stable and outside the app folder, whatever the cwd | Low; the user can still type any path. Tests that assert the old `<cwd>/generated_configurations` string must be updated (`tests/unit/ui`, `tests/e2e/test_entity_batch_cli_subprocess.py` prompts are path-typed, so likely unaffected) |
| P0-2 | Document (and detect) the moved-folder/editable-install failure | `DEPENDENCY_SETUP.md`, `gui.py` precondition message, `tools/check_dependencies.py` import check | A moved folder says "re-run setup_windows.bat" instead of a traceback | Low |

### P1 — Installation and launch reliability

| Item | Change | Files | Expected behaviour | Regression risk |
|---|---|---|---|---|
| P1-1 | `run_gui.cmd` + `run_console.cmd` in the app folder | new files; `RUNNING_THE_APPLICATION.md`, `DEPENDENCY_SETUP.md` | Double-click starts each front end from any cwd | Low |
| P1-2 | `setup_windows.bat`: refuse a protected install folder early | `setup_windows.bat` | Clear instruction instead of a venv error | Low |
| P1-3 | Document the two entry-point `.exe`s or leave them undocumented-but-marked developer-only | `RUNNING_THE_APPLICATION.md` | No user is surprised by `System32` defaults | None |

### P2 — Output usability

| Item | Change | Files | Expected behaviour | Regression risk |
|---|---|---|---|---|
| P2-1 | Pre-fill the Generate page destination and the batch folder picker | `ui/render/qt/pages/generate.py:185-212`, `:394-403`; `ui/render/qt/dialogs/batch_input.py:94-98`; `ui/render/qt/pages/entities.py:355-386` | One click fewer; the same folder every time | Low |
| P2-2 | `%APPDATA%\AF3Builder\settings.json` for last output folder + policies | new small module; `ui/services.py` | Choices persist between sessions | Medium — must tolerate a corrupt/missing file and never fail a run |
| P2-3 | One-line clarification of save vs. generate in the UI hint and the docs | `ui/present/strings.py`; `RUNNING_THE_APPLICATION.md` | "Save = one JSON; Generate = a project folder + manifest" | None |

### P3 — Optional distribution improvements

| Item | Change | Files | Expected behaviour | Regression risk |
|---|---|---|---|---|
| P3-1 | `create_shortcut.cmd` (Desktop/Start-menu `.lnk` to `run_gui.cmd`, *Start in* set) | new file | Clickable icon, no installer | Low |
| P3-2 | Consider PyInstaller only if portability without Python is required | `docs/WINDOWS_PACKAGING.md` recipe; not scheduled | A shareable folder | High effort; explicitly not needed for this user |

---

## 15. Source evidence

| Claim | Path | Lines / functions |
|---|---|---|
| Console launcher delegates to one entry point | `af3builder.py` | `main()` 29-36 |
| Console composition root (no cwd change) | `configbuilder/app/cli.py` | `main()` 31-32 |
| GUI launcher resolves its root from `__file__` | `gui.py` | `repository_root()` 66-73 |
| GUI prefers `.venv`, falls back to `.venv-gui` | `gui.py` | 53, 56, `gui_python()` 75-100 |
| GUI forces cwd = repository root | `gui.py` | `main()` 156 |
| GUI does not change cwd when started as a module | `configbuilder/ui/render/qt/application.py` | `main()` 56-78 |
| Console file picker starts at the cwd | `configbuilder/ui/render/menus.py` | `_pick_path()` 416-456, listing start `:424` |
| Console generation default = `<cwd>/generated_configurations` | `configbuilder/ui/render/menus.py` | 1683 |
| Console save default = current path or `<job>.json` | `configbuilder/ui/render/menus.py` | `_save_and_summary()` 1518-1560, default `:1526` |
| Window save default = source path or `<job>.json` | `main_window.py` / `state.py` | 429 / `suggested_file_name()` 129-135 |
| Window Generate destination has no default | `configbuilder/ui/render/qt/pages/generate.py` | `_build_destination_group()` 185-212, `browse_destination()` 394-403 |
| Folder chooser called with no start path | `configbuilder/ui/render/qt/dialogs/batch_input.py` | `choose_output_folder()` 94-98 |
| Batch action is on Entities and passes the chooser | `configbuilder/ui/render/qt/pages/entities.py` | `generate_from_file()` 355-386 |
| Save writes to an absolute destination (`abspath`) | `configbuilder/app/generation_service.py` | `plan_save()` 917, `abspath` 965 |
| Save copies resources into `<save dir>/assets/` | `configbuilder/app/generation_service.py` | 977-1000 |
| Batch layout and manifest path | `configbuilder/app/generation_service.py` | 562 (`manifest.json`), `plan_base()` 784, `generate_input_batch()` 736 |
| Directory/file naming convention | `configbuilder/output/naming.py` | `variant_directory_name()` 61-64, `variant_file_name()` 66-69 |
| Assets named `<slug>.<ext>`, forward slashes | `configbuilder/output/plan.py` | `_asset_name()` 155-166, `_forward_slashes()` 142-145, `resolve_resources_into()` 220-281 |
| Default policies `Fail` / `CopyIntoAssets` | `configbuilder/output/policies.py`, `configbuilder/persistence/schema.py` | 69-79 / `OutputSettings.__init__` 48 |
| Atomic per-file writes and rollback of created files | `configbuilder/output/execute.py` | `_atomic_write()` 69-88, `_roll_back()` 98-161 |
| Import rebases relative resource paths against the JSON's folder | `configbuilder/app/project_service.py`, `configbuilder/transform/from_wire.py` | 159-163 / `rebase_resource_paths()` 535-580 |
| No preferences / autosave | `configbuilder/app/project_service.py` | module docstring 1-9; no `QSettings` anywhere |
| Setup cd to its own directory, venv, install, pause | `setup_windows.bat` | 3-4, 28-52, 69-84, 136-139 |
| Checker prefers `.venv`, read-only, pauses | `check_dependencies.bat` | 3-4, 11-40, 47-49 |
| Checker's root resolution and offscreen smoke cwd | `tools/check_dependencies.py` | `project_root()` 78-81; subprocess `cwd=str(root)` 278, 315 |
| Extras and entry points | `pyproject.toml` | 9, 15, 17-57, 59, 68 |
| Editable install hard-codes the absolute project path | `.venv/Lib/site-packages/__editable___configbuilder_0_1_0_finder.py` | `MAPPING` line 9 |
| Real generated tree in the repository (artifact) | `output/oct4-pou/` | `manifest.json`, `oct4-pou.json`, `oct4-pou__sep5/`, `oct4-pou__v1/`, `oct4-pou__v2/` |
| Saved jobs at the repository root (artifact) | `Untitled_job_1.json`, `test.json` | — |

---

## Direct answers

**Where should the application live?**
In one user-chosen, user-writable folder under the user's profile — recommended
`C:\Users\<user>\AF3Builder` — never `C:\Program Files` and not inside a documents or
cloud-synced folder if that syncs large `.venv` content. The folder contains the
source, `pyproject.toml`, the two `.bat` utilities, the two new `run_*.cmd` launchers,
the docs and the machine-local `.venv`. Moving it is allowed but requires re-running
`setup_windows.bat`, because the editable install records an absolute path.

**Where should generated output files live?**
In one separate tree outside the application folder, recommended
`C:\Users\<user>\Documents\AF3Builder\` with `generated_configurations\` and
`saved_jobs\` inside it, resolved by a single application-level default (environment
variable → remembered preference → `Documents\AF3Builder` → `%LOCALAPPDATA%` fallback),
never from the current working directory. The folder stays editable so the user can put
it on a USB stick or a network share for the transfer.

**How can the user launch the application without navigating into its installation
directory?**
Today: they cannot without a terminal command (or by finding
`.venv\Scripts\af3-json-builder.exe`, which is undocumented). After P1: a double-click
on `run_gui.cmd` / `run_console.cmd` in the application folder, plus (optionally) a
Desktop or Start-menu shortcut to `run_gui.cmd` with *Start in* set to the application
folder. No installer or packaging framework is needed.

**Which exact files should be transferred to the university AF3 server?**
For each configuration to be run: **the generated JSON and its sibling `assets\`
folder**, keeping the relative layout (`<job>__<entry>.json` with `assets/…` beside it),
or the entire `<job>__<entry>\` directory. Use the default `CopyIntoAssets` policy so
every external MSA/template/CCD file is inside that folder. The builder does **not**
need to travel; `manifest.json` is a builder-side record and AF3 does not read it.
Do not transfer a JSON that still references paths outside its own folder
(`AsGiven`/`RelativeToOutput` outputs) unless those files are copied with the same
relative structure.

**Which supporting assets must accompany each JSON?**
Exactly the files its `unpairedMsaPath`, `pairedMsaPath`, `templates[].mmcifPath` and
`userCCDPath` fields name — by default all under `assets/` next to the JSON. Inline
`mmcif` / inline `userCCD` content travels inside the JSON and needs no file. An MSA
given inline (`unpairedMsa` text) is likewise inside the JSON.

**What should be changed before the installation and output experience can be
considered complete?**
1. A single application-level output-root resolver used by both front ends (P0-1), with
   the save dialogs defaulting into `saved_jobs` instead of a bare relative filename
   (P0-2/R2).
2. Pre-fill the window's Generate destination and the batch folder picker (P2-1).
3. Two double-clickable launchers plus a short shortcut recipe (P1-1, P3-1).
4. Remember the last-used output folder in `%APPDATA%\AF3Builder` (P2-2).
5. Document the moved-folder recovery and the protected-folder rule (P0-2, P1-2), and
   add a one-paragraph root `README.md` that points at the setup guide (R10).
6. One sentence in the UI and docs distinguishing "Save = one JSON" from
   "Generate = a project folder with a manifest" (R12).

Everything else — the generation layout, asset copying, relative-path rewriting,
collision policy, rollback and dependency tooling — is already sound and should be left
alone.
