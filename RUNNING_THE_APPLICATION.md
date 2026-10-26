# Running the AF3 JSON Builder

Two small launchers in the repository root start the application. Run them
from the repository root with the plain project interpreter.

## The console builder

```powershell
python af3builder.py
```

`af3builder.py` delegates to the existing console entry point
(`configbuilder.app.cli.main`, also published as `configbuilder` and
reachable as `python -m configbuilder`). The core builder has no runtime
dependencies, so this needs nothing installed beyond Python itself
(3.9 or newer).

## The desktop front end (optional)

The PySide6 GUI is optional and lives in its own environment, `.venv-gui`.
`gui.py` finds that environment, runs the existing GUI module in it, and
forwards your arguments unchanged.

```powershell
python gui.py                          # empty window -> "Open AF3 JSON..."
python gui.py --demo                   # built-in sample job (in memory only)
python gui.py "C:\path\to\job.json"    # offer a file for preview + confirm
python gui.py --help                   # the GUI launcher's own options
```

A JSON path containing spaces is fine: it is passed through as a single
argument. The GUI always starts with the repository root as its working
directory, even when `gui.py` is invoked by its full path from elsewhere.

### First-time setup of `.venv-gui`

If `.venv-gui` does not exist yet, `python gui.py` prints the exact commands
below and exits without starting anything (it never installs packages for
you):

```powershell
py -3.11 -m venv .venv-gui
.\.venv-gui\Scripts\python.exe -m pip install -e ".[gui]"
```

Then `python gui.py` works.

**Python and dependency facts, as `pyproject.toml` declares them:**

- the package supports Python **3.9 or newer** (`requires-python = ">=3.9"`);
- the core builder has **no** runtime dependencies;
- `PySide6>=6.6` is only in the optional `gui` extra, so the core and the
  console builder keep working with no GUI packages installed;
- Python 3.10+ is the **verified** interpreter for the GUI environment. On
  3.9 the PySide6 range resolves to 6.10.3 (6.11+ requires 3.10+), which is
  installable but not the combination the GUI suite is run against.

If the environment exists but cannot start the GUI (for example PySide6 is
missing), the launcher reports the failure with the child's own diagnostic
and its non-zero exit code — it does not fall back to another interpreter.

## A first tour of the desktop window

The window has a header with the product mark and name, the open job and whether
it has unsaved changes. Below it, a left sidebar is captioned **WORKSPACE** (the
four destinations) and **FILE** (**New · Open · Save**). There is one central
workspace; the destination you pick in the sidebar replaces it.

| Sidebar destination | What it is for |
| --- | --- |
| **Overview** | The job's name, model seeds and JSON version are edited here. Below them, a compact **Entities** card gives the record count, the per-family breakdown and a **Manage entities** action that opens the Entities workspace. Readiness is one line — `Ready` or `Not ready: 1 blocking finding.` — with a quiet **Validate job** action that re-reads the service verdict. There is no permanent findings table: a refusal explains itself when you attempt the save or generation. Saving the document is the labelled **Save** action in the FILE footer (Ctrl+S). |
| **Entities** | A compact drop-down lists every record as identity, family and a short summary (both DNA strands and every identifier of a multi-copy ligand are separate entries), with **Add Protein/RNA/DNA/Ligand**, **Edit entity** and **Delete entity** beside it. Three work areas sit below: **Entity settings** (compact facts — length or representation, description, DNA partner — then Alignment/MSA, templates and PTMs), **Custom CCDs** (the whole-job `userCCD`/`userCCDPath` definition) and **Covalent bonds** (whole-job endpoints across entities). The full sequence is edited in the Add/Edit dialog, never rendered as a large preview. |
| **Variants** | The page opens on three labelled choices — create one variant, create a quantity series, or create variants from a file. Choosing one shows only that workflow, with a *Back to choices* action, and each workflow previews its plan, levels or parsed entries before anything is created. Below: the existing variants, the selected variant's declared changes, its validation state and its JSON; the secondary actions (add a change, rename, duplicate, remove, validate) act on the selection. The base job stays untouched throughout. |
| **Generate** | Four numbered steps, top to bottom: what to generate (explained scope choices, with impossible ones disabled and explained), where the files go, review the plan (files, assets, conflicts, warnings and findings), then generate. The folder and overwrite/path policies sit behind an *Advanced options* disclosure whose defaults are safe; conflicts and warnings stay visible whichever way it is set. Nothing is written before the confirmation, and the result appears in the fourth step. |

Job-wide settings have exactly one home: the **Overview** page edits the job
name, model seeds and JSON version through the configuration service, and the
readiness verdict that depends on them sits directly beside them. There is no
separate Job Settings destination to keep in step.

The sidebar's FILE footer carries the three lifecycle actions (`New`, `Open`,
`Save`) with their full action labels in the tooltips and the standard
keyboard shortcuts (Ctrl+N, Ctrl+O, Ctrl+S). The menu bar itself is hidden, so
the same commands are not offered in two places. The header's pill says "Unsaved"
while the open job differs from what was last opened or saved and "Saved"
otherwise. The window title names the job and carries a `*` in the unsaved
state. `Save JSON…` writes one file; `Generate` writes the planned project
folder, its copied assets and the manifest. Both go through the same generation
service.

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
