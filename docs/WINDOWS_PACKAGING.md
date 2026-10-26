# Optional Windows packaging

**Status: documented, not built.** No executable was produced or run while
writing this document, and nothing in the repository depends on the recipe
below. Source launch (`python gui.py` with the `[gui]` extra) is the supported
installation method; this page exists so that a future shareable build can
follow a concrete, low-risk path instead of improvising one.

## What a packaged build would and would not change

- It bundles the **same** `configbuilder` package and the same
  `configbuilder.ui.render.qt.application:main` entry point. No application
  code changes.
- The core builder stays dependency-free; only the GUI environment needs
  PySide6.
- The tool remains local: no installer, no auto-update, no telemetry, no
  registry writes, no service installation.

## Prerequisites

```powershell
py -3.11 -m venv .venv-gui
.\.venv-gui\Scripts\python.exe -m pip install -e ".[gui]"
.\.venv-gui\Scripts\python.exe -m pip install pyinstaller
```

`pyinstaller` is a build-time tool. It is deliberately **not** added to
`pyproject.toml`: the project's dependency policy keeps packaging tools out of
the runtime contract.

## Recipe (one folder, recommended first attempt)

From the repository root, with `.venv-gui` active (or its interpreter used
directly):

```powershell
.\.venv-gui\Scripts\python.exe -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name "AF3 JSON Builder" `
  --collect-submodules configbuilder `
  --hidden-import configbuilder.ui.render.qt.application `
  --paths . `
  -m configbuilder.ui.render.qt.application
```

Notes on the flags:

- `--windowed` suppresses the console window (the GUI is a `gui-scripts`
  entry point for the same reason).
- `--collect-submodules configbuilder` matters because the pages, dialogs and
  models are imported lazily by module path in a few places; collecting the
  whole package avoids a missing-module failure at launch.
- `-m <module>` builds the module as the entry point. If the installed
  PyInstaller version rejects `-m`, create a three-line `entry.py` containing
  `from configbuilder.ui.render.qt.application import main` /
  `raise SystemExit(main())` and pass that file instead.
- The GUI reads its optional JSON path argument from the command line, so a
  `.exe` built this way accepts the same `path` / `--demo` / `--help`
  arguments as `python gui.py`.

Output lands in `dist\AF3 JSON Builder\`. That folder is self-contained; it
can be zipped and copied to another Windows machine.

## Verification a build would need (not performed)

Before anyone distributes a build, they should confirm on a clean Windows
machine without Python installed:

1. `AF3 JSON Builder.exe --help` prints the same usage as `python gui.py --help`.
2. `AF3 JSON Builder.exe --demo` opens the sample job and the window renders.
3. Opening an AF3 JSON through the file dialog previews and imports it.
4. Adding a protein, editing its MSA, and previewing JSON all work.
5. `Generate files` writes the project folder, copied assets and manifest to a
   chosen folder; a second run with the `Fail` policy refuses as documented.
6. `Save JSON…` writes one file and the title's `*` clears.
7. The executable starts from a directory other than the build root.
8. Antivirus/SmartScreen behaviour is understood (unsigned binaries are
   usually warned about; code signing is out of scope for this project).

Until those steps are actually performed, treat any bundled build as
unverified.

## Why this is not part of the delivered application

- The GUI already has a one-command install and launch story for a thesis
  environment (`py -3.11 -m venv`, `pip install -e ".[gui]"`, `python gui.py`).
- A packaging recipe that cannot be built and smoke-tested in this environment
  would be a claim without evidence; the project's reports deliberately avoid
  those.
- PyInstaller builds are interpreter- and PySide6-version sensitive; pinning
  them belongs with whoever owns the distribution machine, not with the
  application source.
