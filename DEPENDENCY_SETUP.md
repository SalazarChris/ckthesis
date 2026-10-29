# Windows dependency setup

For a normal Windows checkout, double-click **`setup_windows.bat`** once. It
uses Python from the Windows `py` launcher (or `python` on PATH), creates the
project-local `.venv`, installs the project plus its declared `[gui]` and
`[templates]` extras from `pyproject.toml`, and runs the diagnostic. Existing
virtual environments are reused, never deleted or recreated automatically.

Double-click **`check_dependencies.bat`** later to inspect the existing
`.venv`; it is read-only and never installs packages. Both scripts start in
their own project directory regardless of the Explorer working directory and
keep their final result visible until you press a key.

### Choosing a different Python

By default the setup uses the Windows `py` launcher (`py -3`), falling back to
`python` on `PATH`. If that interpreter cannot run the GUI (see Troubleshooting
below), point the setup at a different one instead of editing any file:

```powershell
setup_windows.bat "C:\path\to\python.exe"
# or, equivalently,
$env:PYTHON = "C:\path\to\python.exe"; .\setup_windows.bat
```

The override only selects the interpreter used to create `.venv`. If `.venv`
already exists it is left untouched and the setup says so; rename it yourself
first if you want it rebuilt with the other interpreter.

## If Python is missing

Install Python **3.9 or newer** from [python.org](https://www.python.org/downloads/windows/)
and enable the Windows Python Launcher (`py`) or the “Add Python to PATH”
option. Then double-click `setup_windows.bat` again. The setup checks the
selected interpreter against `requires-python` in `pyproject.toml` before it
creates an environment.

## Diagnostic statuses

`tools/check_dependencies.py` prints one status per check:

- **PASS** — requirement, import or safe startup check passed.
- **MISSING** — a required distribution, import, or project environment is
  absent; rerun `setup_windows.bat` after resolving the stated cause.
- **INCOMPATIBLE** — a Python/package version, import, or pip dependency
  consistency check failed. The detail points to the relevant environment or
  constraint.
- **OPTIONAL** — an optional package is absent or unusable. Gemmi is optional:
  the bundled mmCIF lexical structural check remains available, while Gemmi
  adds strict parsing of mmCIF structures.
- **WARNING** — a diagnostic could not be completed; read its detail and
  resolve the underlying environment issue. A required failure returns a
  nonzero exit code.

There is no separate log file; the complete report is printed in the command
window. The Python checker is read-only. It checks package metadata and imports,
`python -m pip check`, the actual CLI's EOF startup, and a short offscreen Qt
window/service/template-validation smoke test. It does not open a long-running
GUI session.

## Troubleshooting

**`ImportError: DLL load failed while importing QtWidgets` (or any Qt module).**
The environment installed, but this Python distribution cannot load PySide6's
Qt libraries. Conda-style builds are known to trigger it: their base directory
ships its own `ucrtbase.dll` / `msvcp140*.dll` / `vcruntime140*.dll`, which
shadow the Windows C runtime Qt needs. Everything else — the console builder,
`pip check`, the CLI smoke test — still passes, so this shows up as the single
INCOMPATIBLE **GUI/service smoke** row. Rebuild with a python.org build:

```powershell
Rename-Item .venv .venv.backup
setup_windows.bat "C:\path\to\python.org\python.exe"
```

**`pip install` hangs with no output.** The pip HTTP cache is usually corrupt.
Move it aside (it is only a cache; pip rebuilds it):

```powershell
Rename-Item "$env:LOCALAPPDATA\pip\cache" pip-cache.backup
```

then rerun `setup_windows.bat`. Verify afterwards with `pip index versions pip`
from inside `.venv`.

## Safe recovery and development

If setup reports that an existing `.venv` is damaged, it leaves it untouched.
First run `check_dependencies.bat` and read the complete error. If you have
confirmed you no longer need the environment, rename `.venv` to `.venv.backup`
yourself and then rerun the setup script. Do not remove it automatically or
before recovering any local work you need.

To activate the environment manually in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"  # add test-only tools when developing
python -m pytest -o addopts="" -q
```

Runtime features are declared once in `pyproject.toml`: the core builder has
no third-party runtime dependencies, `gui` installs PySide6, and `templates`
installs Gemmi. The Windows setup installs the two runtime extras together;
the `dev` and `analysis` extras are not needed to run the builder. The existing
`gui.py` launcher now prefers `.venv` and remains compatible with an older
`.venv-gui` environment.

This installation is only the local AF3 **JSON configuration builder**. It
does not install the AF3 inference server, GPU drivers, model weights, or any
university Linux environment; generated JSON is run in the separate inference
environment.
