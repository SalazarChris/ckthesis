# Running the AF3 JSON Builder

Two double-clickable launchers in the application folder start the application:
`run_gui.cmd` for the window and `run_console.cmd` for the text menu. For the
one-click Windows setup and dependency checker, see
[`DEPENDENCY_SETUP.md`](DEPENDENCY_SETUP.md): double-click
`setup_windows.bat` once, then `check_dependencies.bat` whenever you want a
readiness report. Both launchers find their own folder, so a shortcut, Explorer
and a terminal all start the same application; neither needs to be launched
from the repository root.

## The console builder

```powershell
run_console.cmd
# or, from a terminal in the folder:
python af3builder.py
```

`af3builder.py` delegates to the existing console entry point
(`configbuilder.app.cli.main`, also published as `configbuilder` and
reachable as `python -m configbuilder`). The core builder has no runtime
dependencies, so this needs nothing installed beyond Python itself
(3.9 or newer).

The text menu covers the same job a user can build in the window, including the
additions below; every action goes through the same services, so the two front
ends validate, save and generate identically.

- Adding DNA asks whether the strand is single- or double-stranded.
- Ligands accept an optional description, which can also be changed later.
- Alignments and structural templates can be read from a file **or** pasted
  inline, including a separate paired source for a `both` alignment.
- **Covalent bonds** (job menu `8`) lists, adds and removes `bondedAtomPairs`
  entries by entity, residue and atom.
- The custom CCD definition is set or replaced as one action, and its content is
  shown before you change it.

## The desktop front end (optional)

The PySide6 GUI is optional in project metadata. The Windows setup installs
all local runtime features into `.venv`; `gui.py` prefers that environment and
continues to fall back to a pre-existing `.venv-gui`. It runs the existing GUI
module and forwards your arguments unchanged.

```powershell
run_gui.cmd                            # the same as: python gui.py
python gui.py                          # empty window -> "Open AF3 JSON..."
python gui.py --demo                   # built-in sample job (in memory only)
python gui.py "C:\path\to\job.json"    # offer a file for preview + confirm
python gui.py --help                   # the GUI launcher's own options
```

A JSON path containing spaces is fine: it is passed through as a single
argument. The GUI starts with the application folder as its working directory,
even when `gui.py` is invoked by its full path from elsewhere; that is only so
imports and internal files resolve. Where **your** files are written is decided
by the output-folder rules below, never by the working directory.

### Manual GUI-only setup (optional)

A complete setup is available through `setup_windows.bat`. For an older or
GUI-only checkout, if neither `.venv` nor `.venv-gui` exists, `python gui.py`
prints the commands to create the complete local environment and exits without
starting anything (it never installs packages for you):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[gui,templates]"
```

Then `python gui.py` works.

**Python and dependency facts, as `pyproject.toml` declares them:**

- the package supports Python **3.9 or newer** (`requires-python = ">=3.9"`);
- the core builder has **no** runtime dependencies;
- `PySide6>=6.6` is only in the optional `gui` extra, so the core and the
  console builder keep working with no GUI packages installed;
- `gemmi>=0.6` is in the optional `templates` extra; the bundled lexical mmCIF
  structural check still works without it, with Gemmi adding parser validation;
- Python 3.10+ is the **verified** interpreter for the GUI environment. On
  3.9 the PySide6 range resolves to 6.10.3 (6.11+ requires 3.10+), which is
  installable but not the combination the GUI suite is run against.

If the selected environment exists but cannot start the GUI (for example
PySide6 is missing), the launcher reports the failure with the child's own
diagnostic and its non-zero exit code. It prefers `.venv` and only checks the
legacy `.venv-gui` path when `.venv` is absent.

## Where saved and generated files go

Both front ends use one output-folder service
(`configbuilder/app/paths.py`), so the destination offered by the console and by
the window is the same:

| Operation | Offered default |
| --- | --- |
| Save the open job | the file it came from; otherwise `<output root>\saved_jobs\<job>.json` |
| Generate the open job (Generate page) | `<output root>\saved_jobs` (or the folder the last export went to) |
| Generate configurations from a file (Entities) | `<output root>\generated_configurations` (or the last batch folder) |

The `<output root>` is resolved in this order: the `AF3BUILDER_OUTPUT_ROOT`
environment variable; the last-used output folder in
`%APPDATA%\AF3Builder\preferences.json`; `Documents\AF3Builder`; then
`%LOCALAPPDATA%\AF3Builder`. An `AF3BUILDER_OUTPUT_ROOT` that cannot be created
or written is reported in the interface and the next source is used — it is
never silently ignored, and no default ever falls back to the application
folder or the terminal's directory.

A chosen folder is remembered only after the save or generation actually
succeeded, so cancelling or a refused plan leaves the next default where it was.
Both folders stay distinct on purpose: `saved_jobs` holds one JSON per job,
`generated_configurations` holds the batch tree (one folder per entry, each with
its `assets\`, plus `manifest.json`). The manifest is a builder-side run report
that AF3 does not read.

## A first tour of the desktop window

The window has a header with the product mark and name, the open job and whether
it has unsaved changes. Below it, a left sidebar is captioned **WORKSPACE** (the
three destinations) and **FILE** (**New · Open · Save**). There is one central
workspace; the destination you pick in the sidebar replaces it.

| Sidebar destination | What it is for |
| --- | --- |
| **Overview** | The job's name, model seeds and JSON version are edited here. Below them, a compact **Entities** card gives the record count, the per-family breakdown and a **Manage entities** action that opens the Entities workspace. Readiness is one line — `Ready` or `Not ready: 1 blocking finding.` — with a quiet **Validate job** action that re-reads the service verdict. There is no permanent findings table: a refusal explains itself when you attempt the save or generation. Saving the document is the labelled **Save** action in the FILE footer (Ctrl+S). |
| **Entities** | A compact drop-down lists every record as identity, family and a short summary (both DNA strands and every identifier of a multi-copy ligand are separate entries), with **Add Protein/RNA/DNA/Ligand**, **Edit entity** and **Delete entity** beside it. The **Generate configurations from file…** action accepts explicitly selected protein, DNA, RNA, SMILES or standard CCD-code input, then previews and writes one independent AF3 JSON per entry without changing the open base job. Three work areas sit below: **Entity settings** (compact facts — length or representation, description, DNA partner — then Alignment/MSA, templates and PTMs), **Custom CCDs** (the whole-job `userCCD`/`userCCDPath` definition) and **Covalent bonds** (whole-job endpoints across entities). The full sequence is edited in the Add/Edit dialog, never rendered as a large preview. |

| **Generate** | One action. The output folder is pre-filled and the file it will produce is named above the button (`<folder>\<job>\<job>.json`), then **Save job** writes it — no preview step to complete first and no confirmation for a new file. The only question is a replacement: an existing file holding *different* content is confirmed once, naming the files; a file whose bytes are identical is rewritten silently. The overwrite and path policies sit behind an **Options** disclosure whose defaults are safe, and **Preview plan** is available (under the result) for anyone who wants to see the files, copied assets, warnings and conflicts first. After a write the result lists what was written and copied, **Open folder** shows it in Explorer, and **Plan details** expands the plan's own rows. A refusal (no folder, blocking findings, a conflict under the default `Fail` policy) writes nothing and explains itself. |

Job-wide settings have exactly one home: the **Overview** page edits the job
name, model seeds and JSON version through the configuration service, and the
readiness verdict that depends on them sits directly beside them. There is no
separate Job Settings destination to keep in step.

The sidebar's FILE footer carries the lifecycle actions (`New`, `Open`, `Save`,
`Save to folder`) with their full action labels in the tooltips and the
standard keyboard shortcuts (Ctrl+N, Ctrl+O, Ctrl+S). The menu bar itself is
hidden, so the same commands are not offered in two places. The header's pill
says "Unsaved" while the open job differs from what was last opened or saved
and "Saved" otherwise. The window title names the job and carries a `*` in the
unsaved state.

Two write actions, and they differ only in who chooses the path:

- **`Save`** (Ctrl+S) opens a save dialog so you pick the file. It remembers
  the folder you chose for the next time.
- **`Save to folder`** is the one-click route: it writes the job into the
  output folder exactly as the Generate page does
  (`<folder>\<job>\<job>.json`, plus any copied assets), with no dialog and
  without opening the Generate page. It uses the remembered output folder, so
  pick a different one on the Generate page when you want one.

Both go through the same generation service, ask the same single question when
an existing file would be replaced with different content, and mark the job
saved once the bytes are on disk. `Generate configurations from file…` on the
Entities page is the separate batch route: one configuration per input entry,
plus `manifest.json`, into `generated_configurations`.

The dark charcoal/turquoise look is applied from the one style module
(`configbuilder/ui/render/qt/style.py`); no page carries its own style sheet.

## Tests

```powershell
# core suite (no PySide6 needed)
python -m pytest -o addopts="" -q

# the launchers' own tests
python -m pytest -o addopts="" -q tests/unit/test_launchers.py

# architecture rules and the string registry
python -m pytest -o addopts="" -q tests/architecture tests/unit/ui/test_string_registry.py

# the GUI suite, in the isolated environment, with no display
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
```

The `tests/e2e` modules drive the current menu (including the DNA
complement question and the direct-open import flow), so they pass with the
rest: the core suite has no known failures. See
`docs/GUI_AUTOMATED_QA_REPORT.md` for the latest full-suite evidence.

## Trying it by hand

[`manual_test_data/af3_builder/`](manual_test_data/af3_builder/README.md) holds
small synthetic inputs (batch sequence/SMILES files, protein and RNA MSA files,
a template mmCIF, plus names containing spaces) and step-by-step walkthroughs for
both front ends. The RNA MSA section there is the one to read before touching
RNA alignment settings; `docs/AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md` is the
audit behind it.

## Packaging

Source launch is the supported method: the two commands above, plus the
`[gui]` extra, are the whole installation story. An optional PyInstaller
recipe for a shareable folder or `.exe` is documented — and explicitly marked
as not built or smoke-tested here — in
[`docs/WINDOWS_PACKAGING.md`](docs/WINDOWS_PACKAGING.md).
