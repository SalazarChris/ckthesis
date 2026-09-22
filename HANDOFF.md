# OPERATIONAL HANDOFF — configbuilder (AF3 input builder)

**Status of this document:** every command and filename below was executed or verified
against this repository on the development machine (Windows, Python 3.11.15, 2026-09).
Claims are marked:

- **[Verified]** — executed/inspected in this repository during this handoff.
- **[Recommended]** — sensible practice that is *not* currently implemented in the repo.
- **[Unknown]** — needs manual verification on the target machine.

This document modifies nothing in the repository.

---

## 0. THE ONE-PARAGRAPH SUMMARY

`configbuilder` is a terminal wizard that builds validated, reproducible AlphaFold3
input JSON files. It is a pure-Python package (`configbuilder/`) with **zero runtime
dependencies**, a pytest suite under `tests/`, and a **console entry point**: after
`pip install -e .` you can type `configbuilder` (implemented in
`configbuilder/app/cli.py`, a thin delegation to the wizard; see §1.3 and
§4.B), or run it as `python -m configbuilder`. You can also run it as a library
from a Python one-liner/script (`run_wizard`). Tests run with
`python -m pytest` from the project root. The repository is **not a Git checkout**
(there is no `.git`), so it is moved by copying folders or a ZIP, not by cloning.

---

## 1. FIRST: INSPECT THE ACTUAL IMPLEMENTATION

### 1.1 Repository structure [Verified]

```
├─ configbuilder/            the application package
│  ├─ app/                   the five application services (Project/Configuration/
│  │                         Variant/Validation/Generation) + result types
│  ├─ identity/              identifier allocation & registry (chain letters A, B, …)
│  ├─ model/                 canonical records (polymer families, ligand), values
│  ├─ validation/            rule catalogue + rules (spec §19 matrix as data)
│  ├─ variants/              variant specs, edits, expansion
│  ├─ transform/             model → wire document (AF3 vocabulary) mapping
│  ├─ serialize/             byte-stable JSON encoder
│  ├─ output/                output planning, atomic execution, manifest
│  ├─ persistence/           .cbproj project-file encode/decode/store
│  ├─ ui/
│  │  ├─ steps/              pure step machine (14 wizard steps, no I/O)
│  │  ├─ present/            pure formatting + the wizard string registry
│  │  └─ render/             terminal renderers (plain, full-screen, guard), journal
│  └─ __init__.py
├─ tests/                    the pytest suite (unit, architecture, e2e, contract,
│                            golden, serialization, variant, negative, terminal)
├─ docs/CONTRACT_PIN.md      deployment evidence log (provenance documentation;
│                            never read at runtime)
├─ fixtures/                 golden fixtures + sample project files
├─ testdata/                 MSA JSON examples (reference data)
├─ .github/workflows/ci.yml  CI: tests on 3.9 for ubuntu+windows, ruff lint
├─ pyproject.toml            package + pytest configuration
├─ CHECKLIST.md              implementation status per phase
├─ AUTHORITATIVE_SPEC.md / IMPLEMENTATION_PLAN.md / DOMAIN_MAPPING.md
```

There is **no README**, **no `requirements*.txt`**, **no `setup.py`**, **no
`conftest.py`**, and **no `__main__.py`** anywhere in the package.

### 1.2 How imports work [Verified]

- `pyproject.toml` → `requires-python = ">=3.9"`, `dependencies = []` (stdlib only),
  optional extras: `fullscreen = ["prompt_toolkit>=3.0"]`, `dev = ["pytest>=7", "hypothesis>=6"]`.
- `[tool.pytest.ini_options] testpaths = ["tests"]` — running `pytest` with no
  arguments works **only from the project root**.
- Tests import `configbuilder...` directly. Because `tests/__init__.py` exists,
  pytest inserts the project root on `sys.path` when run from the root; the suite
  also passes under `python -m pytest`. Both verified: `python -m pytest` → 695 passed.
- The runtime **never reads** `docs/CONTRACT_PIN.md` (proven by
  `tests/unit/validation/test_no_pin_document_dependency.py`, including a
  byte-identical-output run with the doc present vs absent). Version evidence is
  supplied explicitly in the configuration: `Pinned(version, evidence="PIN-nnn")`,
  persisted in the project file, and mirrored into the manifest. The document is
  where the human records the observations those citations refer to.

### 1.3 Application entry points [Verified — with a gap to report]

| Mechanism | Status |
|---|---|
| `pyproject.toml` `[project.scripts]` declares `configbuilder = "configbuilder.app.cli:main"` | **Declared and implemented [Verified].** |
| `configbuilder/app/cli.py` (provides `main`) | **Exists [Verified]** — the top-level menu launcher; it composes the standard services into `ui.render.menus.MenuApp`, the free-navigation builder (base configuration + variants + export), with the guided wizard kept as menu option 8. |
| `python -m configbuilder` | **Works [Verified]** (`__main__.py` delegates to the same entry point). |
| `configbuilder` console command | **Works [Verified]** — shows the start screen (new experiment / load); the master menu then offers the Job Builder, Validation, Show JSON, Save/Load, Variants, Generate JSONs, the guided wizard, and the job summary. `0`/`q`/`quit`/`exit` leaves; EOF or Ctrl+C ends cleanly with status 0. |
| `python -m configbuilder.ui.render.wizard` | Not supported (no `__main__` guard). |
| Programmatic launch | **Works [Verified]** — see §4.B. |

**Reported, not fixed:** installing with `pip install -e .` *will succeed* and *will
create* a `configbuilder` command, but running that command fails with
`ModuleNotFoundError: No module named 'configbuilder.app.cli'`. Until `app/cli.py`
is written, the way to launch the wizard is the Python one-liner in §4.B. This is
the single largest gap between the declared packaging and the actual implementation.

### 1.4 Python version actually required [Verified]

- Declared floor: `>=3.9` (pyproject).
- The dev machine runs **3.11.15**; CI (.github/workflows/ci.yml) asserts
  `sys.version_info[:2] == (3, 9)` and runs the whole suite on 3.9 on
  ubuntu-latest and windows-latest.
- A static baseline gate (`compileall` over `configbuilder/`) passes, and
  `tests/architecture/test_baseline.py` bans 3.10-only syntax, so **Python 3.9.18
  is sufficient**. 3.11 also works. No 3.12-only features are used.
- During this handoff, an app-level service check (Phase 10/11 era) is
  3.9-syntax-clean per the compile gate.

---

## 2. DO NO HARM (what this document did)

Nothing in the repository was modified. Every discrepancy found (missing `cli.py`,
no Git metadata, no README) is reported here, not repaired.

---

## 3. PYTHON ENVIRONMENT

| Item | Value | Status |
|---|---|---|
| Python floor | `>=3.9` (3.9.18 OK; CI runs 3.9) | [Verified] |
| Runtime dependencies | **none** (stdlib only) | [Verified] |
| Optional dependency | `prompt_toolkit>=3.0` — enables the full-screen renderer; its absence silently selects the plain renderer | [Verified] |
| Test dependencies | `pytest>=7`, `hypothesis>=6` (the `dev` extra) | [Verified] |
| Virtual environment | Recommended, not required — nothing is installed outside pytest/hypothesis | [Recommended] |
| Packaging | `pip install -e .` works but the console script is broken (see §1.3); `pip install -e .[dev]` additionally provides pytest + hypothesis | [Verified] |

Notes:

- `hypothesis` is *optional at runtime of the suite*: several property tests skip or
  narrow when it is missing. CI installs it; a minimal machine without it still
  runs most of the suite. **[Unknown]** exactly which tests degrade — install the
  `dev` extra to be safe.
- **[Recommended but not currently implemented]** a `requirements-dev.txt` for
  pip-users who prefer it over extras; use `pip install -e .[dev]` instead.

---

## 4. DEVELOPMENT-MACHINE RUN GUIDE

### A. First-time setup [Verified commands]

From the project root (the folder containing `pyproject.toml`):

```bat
:: create the virtual environment (once)
python -m venv .venv

:: activate it — Windows (cmd)
.venv\Scripts\activate.bat

:: activate it — PowerShell
.venv\Scripts\Activate.ps1

:: upgrade pip and install the project in editable mode with test deps
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Linux equivalent: `python3 -m venv .venv && source .venv/bin/activate`, same pip lines.

Verification that setup is complete:

```bat
python -c "import configbuilder; print(configbuilder.__doc__)"
python -m pytest --collect-only -q
```

The first prints the package docstring; the second collects hundreds of tests with
no errors.

**[Recommended]** You can skip `pip install` entirely and run from the source tree
(imports resolve because of the root). In that case you still need
`pip install pytest hypothesis` in your venv for the suite.

### B. Normal application launch [Verified]

The primary launch command is the console entry point:

```bat
:: after pip install -e . (from any directory)
configbuilder
```

The library-style one-liner remains equivalent:

```bat
python -c "from configbuilder.ui.render.wizard import run_wizard; from configbuilder.ui.services import build_services; run_wizard(build_services())"
```

- **Where from:** anywhere, *provided* either (a) you are inside the project root
  in the venv you installed with `pip install -e .`, or (b) `configbuilder` is on
  `sys.path`. If you launch from a scratch directory while using the editable
  install, it works because the editable install puts the project root on `sys.path`.
- **What you should see [Verified]:** one `probe: renderer=… glyphs=… color=… size=… (reason)` line,
  then the interactive wizard starting at `Step 1 of 14 — Job`.
- **How you know it started:** the step header `Step 1 of 14` and the hint line
  `[Enter] accept default — n/p next/previous …` appear, and the prompt `> ` waits.
- **Non-TTY behaviour [Verified]:** run the same command with stdin piped
  (`echo q | python -c "…"`) and the wizard *refuses to start* with
  "No terminal is attached … nothing was started." and stops without hanging.
Through the console menu (`configbuilder` / `python -m configbuilder`), the
wizard runs via option `1`; the menu returns afterwards. Launched directly
with piped stdin, the wizard's guard status 3 is the session's return value.
[Verified: the menu ends with process exit 0 on quit words, EOF, and Ctrl+C.]

### C. Test suite [Verified commands]

```bat
:: the complete suite (from the project root) — 695 tests, ~10 s on the dev box
python -m pytest

:: one file
python -m pytest tests\unit\ui\test_step_machine.py

:: one test
python -m pytest "tests\unit\ui\test_step_machine.py::test_previous_is_never_blocked"

:: verbose (lists every test name)
python -m pytest tests\unit\ui -v

:: stop at the first failure
python -m pytest -x

:: architecture rules only (static checks: dependency rules, purity, baseline)
python -m pytest tests\architecture
```

`pyproject.toml` sets `addopts = "-q"`, so default output is quiet; add `-v` when
you want names. `testpaths = ["tests"]` means bare `pytest` also works from the root.

---

## 5. BASIC MANUAL TEST (smoke test)

**Important design fact first [Verified]:** generation requires an explicit, verified
format target in the configuration (`Pinned(version, evidence=...)`). With no pin —
or a pin without its evidence citation — a CONTRACT rule reports `ERROR` and
**generation is blocked by design**; no version is ever inferred. The full smoke
test below pins version 3 with evidence `PIN-001` through the wizard's advanced
action, so it needs no patching and no `docs/CONTRACT_PIN.md` at runtime. The
citation refers to a record a human adds to that document after probing the real
deployment (the repository's own Phase-0 task).

**Smoke test A — everything except generation (no patching, pure UI) [Verified flow]**

1. Launch the wizard (§4.B) in a terminal.
2. At `Step 1 of 14 — Job` type `new` and press Enter.
3. At `Job details` type a project name, e.g. `E2E Smoke Test` (a second optional
   description field appears; Enter accepts its empty default).
4. At `Step 3 of 14 — Molecule` enter the record fields directly:
   `rna`, then sequence `GGCC`, then Enter for the remaining optional fields.
   The header advances to `Step 4` (entry conditions gating the step machine work).
5. Press `a` (advanced), enter `3`, then `PIN-001` — this pins format version 3
   with its evidence citation. Press `v` (validate): the numbered findings list
   appears. (If you skip the evidence prompt with a blank line, validation
   reports `ERROR — the pinned version carries no verification evidence`:
   that ERROR is the designed behaviour, not a malfunction.)
6. Press `s` (save), enter a path such as `smoke.cbproj`, and check the file exists.
7. Exit with `q`.

**Smoke test B — full pipeline to files [Verified]** (the repository's own e2e does
exactly this; from a scratch directory):

```bat
python -c "import os, tempfile; from configbuilder.ui.render.console import ScriptedConsole; from configbuilder.ui.render.wizard import WizardSession; from configbuilder.ui.render.capabilities import Capabilities, GlyphSet, RendererKind; from configbuilder.ui.services import build_services; os.chdir(tempfile.mkdtemp()); caps=Capabilities(RendererKind.PLAIN, GlyphSet.UNICODE, False, 80, 24, ('t',)); script=['new','E2E Smoke Test','','rna','GGCC','','','','a','3','PIN-001','v']+['n']*8+['nob','sequence','A','AUUA','no A chain']+['n','out','y']; s=WizardSession(build_services(), ScriptedConsole(script), caps); print('exit:', s.run())"
```

Expected: `exit: 0`, transcript ends with `wrote out\e2e-smoke-test\manifest.json`,
and the two files in §6 exist. (The `ScriptedConsole` here feeds canned answers —
it is the same harness the automated e2e suite uses; interactively, a human types
the same answers.)

**What success looks like:** exit status 0; two JSON files under
`out\e2e-smoke-test\`; the transcript reporting `create` entries for the plan and
`wrote …` lines for the execution.

---

## 6. GENERATED OUTPUT [Verified]

- **Where:** you choose the output root at the generate step (`Output directory:`).
  It may be relative (resolved against the current working directory) or absolute.
- **Layout [Verified]:**
  ```
  <output_root>\<project-slug>\manifest.json
  <output_root>\<project-slug>\<project-slug>__<variant-key>\<project-slug>__<variant-key>.json
  ```
  The project slug is the job name lower-cased and hyphen/underscore-mangled
  (`E2E Smoke Test` → `e2e-smoke-test`). One directory per variant; the job `name`
  inside the JSON equals the derived directory name (a checked agreement).
- **Which file is the AF3 input:** the per-variant JSON — e.g.
  `out\e2e-smoke-test\e2e-smoke-test__nob\e2e-smoke-test__nob.json`. Verified top-level
  keys: `dialect`, `modelSeeds`, `name`, `sequences`, `version`. This is the file
  that would be submitted to the AF3 deployment.
- **Directory creation:** yes, automatically (executor creates parents).
- **Overwrite behaviour [Verified]:** the output planner applies the project's
  overwrite policy and reports each entry's action (`create`, `overwrite`, …).
  The wizard shows the plan and asks `Write these files? [y/N]:` before writing;
  a conflicting plan can refuse entirely. Writes are atomic (`.tmp` + replace).
- **The manifest** (`manifest.json`): provenance for the run. Verified keys:
  `base_fingerprint`, `builder_version`, `contract_pin_record`, `format_version`,
  `overwrite_policy`, `path_policy`, `project_name`, `schema_version`,
  `seed_set`, `validation_summary`, `variants`. **Everything except `run_info`
  is deterministic; `run_info` (not present in the deterministic payload)
  carries the wall-clock timestamp** — so do *not* byte-compare manifests
  between runs; do byte-compare the *variant* JSONs.
- **Manual inspection:** it is plain UTF-8 JSON — open in any editor, or
  `python -m json.tool <file>` to pretty-print and syntax-check.

---

## 7. WHAT MUST BE MOVED TO ANOTHER MACHINE

Classified from the actual tree [Verified]:

**MUST COPY — application**
```
configbuilder\           the entire package (all subpackages; ~30 modules)
docs\                    copy for documentation only — CONTRACT_PIN.md is not
                         read at runtime (§1.2); the app runs without it
pyproject.toml           needed for pip install -e . ; declares the package
```

**MUST COPY FOR TESTING**
```
tests\                   the whole suite (incl. tests\architecture\_scanner.py,
                         which the architecture tests import via sys.path)
fixtures\                golden fixtures (fixtures\golden\project\*), sample
                         projects (legacy_v0.cbproj, v1_compatibility.cbproj);
                         fixtures\golden\external\ is currently empty (by design)
.github\workflows\ci.yml only if you want the CI definition on the new machine
```

**OPTIONAL**
```
AUTHORITATIVE_SPEC.md, IMPLEMENTATION_PLAN.md, DOMAIN_MAPPING.md, CHECKLIST.md
testdata\                MSA JSON reference examples; referenced by no code or
                         test in the current tree [Verified] — reference material
```

**DO NOT COPY**
```
.venv\ venv\             recreate the environment on the target machine
__pycache__\             all of them (present throughout the tree)
.pytest_cache\ .hypothesis\
*.pyc
```

(Concretely: copying `configbuilder\`, `docs\`, `tests\`, `fixtures\`,
`pyproject.toml` is the minimal complete transfer; adding the four top-level
`.md` files and `testdata\` gives the full working context.)

---

## 8. MOVING TO ANOTHER WINDOWS MACHINE

**There is no Git repository here [Verified — `git rev-parse` fails: no `.git`]**,
so `git clone` is not available for this checkout. Options, most to least
appropriate:

1. **ZIP the needed folders** (respects §7's DO-NOT-COPY list). From the project
   root in PowerShell, an example producing a clean archive:
   ```powershell
   Compress-Archive -DestinationPath configbuilder-handoff.zip `
     -Path configbuilder, tests, fixtures, docs, testdata, pyproject.toml, *.md
   ```
   (`__pycache__` folders inside `configbuilder\` and `tests\` come along unless
   excluded first — PowerShell 7 supports `-Path` exclusions via staging;
   **[Recommended]** delete `__pycache__` folders before zipping, or clean them
   after extraction; they are harmless but noisy.)
2. **Direct folder copy** (USB/network share): copy the same set.
3. **If Git hosting is set up later [Recommended]:** `git init`, commit, push, and
   clone on machine B — currently impossible from this folder since it is not a
   repository.

Then on machine B:

```bat
:: install Python 3.9.18 from python.org (tick "Add to PATH")
python --version            :: must print 3.9.18

:: unpack the zip, cd into the folder, then:
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m pytest            :: expect the same pass count as machine A
```

---

## 9. MOVING TO A LINUX MACHINE

**The builder is intended to be Linux-portable [Verified by design and by CI]:**
CI runs the full suite on `ubuntu-latest` with Python 3.9; the architecture tests
confine every platform branch to `ui/render/platform.py`; the encoder forbids
platform-derived bytes; paths are joined with `os.path`; the plain renderer is
stdlib-only.

Setup/run on Linux:

```bash
python3.9 -m venv .venv        # or python3 -m venv .venv if 3.9 is default
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m pytest               # expect the same pass count
python -c "from configbuilder.ui.render.wizard import run_wizard; from configbuilder.ui.services import build_services; run_wizard(build_services())"
```

Portability notes, from inspection (nothing fixed, as instructed):

- **Path handling:** package code uses `os.path`/`pathlib` throughout; no
  hard-coded `C:\` or `/home/` exists in `configbuilder/` or `tests/` [Verified by
  scan]. Project-file paths *inside saved `.cbproj` files* are stored as given —
  a project saved on Windows with `C:\…\job.cbproj` will not resolve on Linux
  when reopened; reopen it from a re-saved neutral/relative path.
- **Line endings:** generated JSON is written by the project's own encoder with
  `\n`; Windows checkout clients do not alter file contents in a zip copy. Git
  `autocrlf` is not a factor here (no Git metadata).
- **Permissions:** nothing installs scripts outside the venv; no chmod needed.
  The editor route (`VISUAL`/`EDITOR`) differs by platform by design.
- **Environment variables:** see §12 — none are required; all are optional.
- **The state directory** (`session.json` journal) is `%LOCALAPPDATA%\configbuilder`
  on Windows vs `$XDG_STATE_HOME`/`~/.local/state/configbuilder` on POSIX —
  platform-appropriate by design, not a defect.

**Verdict:** the builder itself runs on Linux. The AF3 *deployment* is a separate
system (§10).

---

## 10. IMPORTANT: AF3 SERVER IS A SEPARATE SYSTEM

```
Machine A (Windows, dev)          Machine B (any)              University Linux
authoring/tests of the builder    builder testing              AF3 Server execution
needs: this repo + Python 3.9     needs: the same transfer     needs: NOTHING from
                                  + Python 3.9                 this repository
```

- The builder has **no dependency on any AF3 installation or source tree**
  [Verified: `dependencies = []`; no imports or path references to AF3 anywhere
  in `configbuilder/`].
- What moves to the university system: **only the generated per-variant JSON
  files** (e.g. `e2e-smoke-test__nob.json`), plus, if the deployment's operators
  want provenance, the `manifest.json`. Transfer with SFTP/scp; the JSON is UTF-8
  and `\n`-line-ended, so cross-platform transfer is safe.
- What does **not** move: `configbuilder\`, `tests\`, the venv — the AF3 server
  does not need the builder.
- The relationship runs the other way: after submitting a builder-generated input,
  humans record the acceptance observation in `docs/CONTRACT_PIN.md` on the builder
  side (§5); the operator then pins that version citing the record's Pin ID, which
  clears the designed generation block.

---

## 11. PATH / PORTABILITY CHECK [Verified by scan]

Scan of `configbuilder/` and `tests/` for `C:\`, `C:/Users/`, `/home/`, `/Users/`,
absolute machine paths: **no problematic hard-coded paths found.** Occurrences and
classifications:

| Occurrence | Classification |
|---|---|
| `docs/CONTRACT_PIN.md` resolved relative to the package file (`parents[3]`) | intentional (builder-owned doc; works from the source tree) |
| `testdata/adk_msa_data.json`, `testdata/ubiquitin_msa_data.json` filenames (reference data, unused by code) | test/reference data |
| `fixtures/golden/...`, `fixtures/projects/*.cbproj` in tests | test fixtures (relative paths from the project root) |
| Windows-vs-POSIX editor lists, `LOCALAPPDATA`, `XDG_STATE_HOME` in `ui/render/platform.py` | intentional platform handling (the one sanctioned branch point) |
| `os.path.expanduser("~")` fallbacks | intentional (documented defaults) |
| Output/project paths typed by the user at run time | configuration (user input, stored as given in `.cbproj`) |
| **[Verified]** one *transient* appearance in this handoff's own smoke commands (`AppData\Local\Temp`) | generated output (temp dirs), not in the repository |

Nothing needs changing; nothing was changed.

---

## 12. ENVIRONMENT VARIABLES [Verified by scan]

The application uses **no required environment variables**. Variables actually read
(in `configbuilder/ui/render/` only):

```
NAME:            TERM
Purpose:         terminal capability for renderer/colour selection
Required:        no (POSIX only; Windows ignores it)
Example value:   xterm-256color   (special value "dumb" disables colour)
Where:           configbuilder/ui/render/capabilities.py

NAME:            NO_COLOR
Purpose:         explicit colour disable (any non-empty value)
Required:        no
Example value:   1
Where:           configbuilder/ui/render/capabilities.py

NAME:            VISUAL / EDITOR
Purpose:         external editor offered in the long-text route
Required:        no (absence simply omits the editor option)
Example value:   notepad   /   vim
Where:           configbuilder/ui/render/longtext.py, longtext_io.py

NAME:            LOCALAPPDATA (Windows) / XDG_STATE_HOME (POSIX)
Purpose:         base of the wizard's session-journal state directory
Required:        no (falls back to the user home)
Example value:   (set by the OS)
Where:           configbuilder/ui/render/platform.py
```

The encoder deliberately reads nothing from the environment (no host, no time, no
locale) — that is what makes generated JSON byte-comparable across machines.

---

## 13. TEST DATA [Verified]

| Path | Purpose | Required for app? | Required for tests? | Safe to move? | Machine-specific? |
|---|---|---|---|---|---|
| `docs/CONTRACT_PIN.md` | deployment-evidence log consulted by validation rules | **yes** (runtime read) | yes | yes | no |
| `fixtures/golden/project/*` | byte-stable golden expectations (e.g. `minimal_protein_v3`, `comprehensive_families_v4`) | no | **yes** (golden tests) | yes | no |
| `fixtures/golden/external/` | reserved for probe inputs from real deployments | no | yes (currently empty by design) | yes | no |
| `fixtures/projects/legacy_v0.cbproj`, `v1_compatibility.cbproj` | project-file migration/compatibility fixtures | no | **yes** | yes | no |
| `fixtures/golden/build_fixture.py` | helper that (re)builds golden files | no | yes (regeneration tool) | yes | no |
| `testdata/adk_msa_data.json`, `testdata/ubiquitin_msa_data.json` | MSA JSON reference examples (protein/RNA/ligand shapes) | no | no (referenced by no current test) **[Verified]** | yes | no |
| `tests/` at large | the suite itself | no | **yes** | yes | no |

Custom-chemistry and MSA *files* are handled at run time via user-typed paths
(long-text routes), so no example files are mandatory.

---

## 14. CLEAN-MACHINE TEST (step by step)

Run this on a machine that has never seen the project:

```bat
:: 1. Install Python 3.9.18 (python.org installer, "Add to PATH" ticked)
python --version
::    expected: Python 3.9.18

:: 2. Obtain the repository (zip from §8), then unpack and enter it
cd configbuilder-handoff

:: 3. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate.bat

:: 4. Install dependencies
python -m pip install --upgrade pip
pip install -e ".[dev]"

:: 5. Run tests
python -m pytest
::    expected: 695 passed (dev machine count, Python 3.11; on 3.9 expect the
::    same count or a small documented variance — see §15)

:: 6. Launch the application (interactive, in a real terminal)
python -c "from configbuilder.ui.render.wizard import run_wizard; from configbuilder.ui.services import build_services; run_wizard(build_services())"
::    expected: probe line + "Step 1 of 14 — Job" + "> " prompt

:: 7. Perform the smoke test (§5, smoke test A steps 2-7)

:: 8. Generate example output (§5, smoke test B — patched-pin full pipeline)

:: 9. Inspect output
python -m json.tool out\e2e-smoke-test\e2e-smoke-test__nob\e2e-smoke-test__nob.json
python -m json.tool out\e2e-smoke-test\manifest.json
```

If all nine steps behave as annotated, the handoff is complete.

---

## 15. FAILURE DIAGNOSTICS

**`python` not found** — the installer's "Add to PATH" was not ticked, or you are
in a shell that predates the install. Check: `where python` (Windows) /
`which python3` (Linux). On Windows use `py -3.9` as an alternative launcher.

**Wrong Python version** — `python --version` must print 3.9.18 (or another ≥3.9).
Inside a venv, `python` is the venv's interpreter: activate first, then check.
CI's own assertion is `sys.version_info[:2] == (3, 9)`.

**`ModuleNotFoundError: No module named 'configbuilder'`** — the interpreter cannot
see the package. Two causes, verified on the dev machine (a scratch-cwd run fails
exactly this way): (a) your current directory is not the project root *and* you
did not `pip install -e .`; (b) the venv is not activated. Fix: activate the venv
and either `cd` to the project root or install editable. Check what the
interpreter sees: `python -c "import sys; print(sys.path)"` and
`pip show configbuilder`.

**Tests cannot discover/import the package** — you are not in the project root.
`pyproject.toml` sets `testpaths = ["tests"]`, and the suite's imports assume the
root is importable (the `tests` package + rootdir insertion). Run `python -m pytest`
from the root, not from a subfolder. If `tests/architecture` fails on
`_scanner` imports, the root is not on `sys.path` — again a cwd/install problem.

**Application starts but cannot find files** — two distinct cases: (1) *project
files* are opened by path you typed; relative paths resolve against your **current
working directory** — `cd` where you mean to be, or type absolute paths.
(2) The wizard claims it cannot find `docs/CONTRACT_PIN.md` evidence: that file
must sit three parents above the imported `configbuilder\` package
(source-tree layout). If you copied `configbuilder\` without `docs\`, validation
reports "version unverified" — restore the folder (§7).

**Tests pass on Machine A but fail on Machine B** — diagnostic sequence:
1. `python --version` on both machines (3.9 vs 3.11 differences surface here).
2. `pip show pytest hypothesis prompt_toolkit` on both — missing `hypothesis`
   narrows property tests; missing `prompt_toolkit` changes only renderer choice.
3. Confirm a complete transfer: does `python -m pytest --collect-only -q` count
   match? If fewer tests collect, folders from §7 are missing.
4. Windows path length: deep `fixtures\` + venv paths can exceed 260 chars on
   unconfigured Windows; enable long paths or move the tree shorter (e.g. `C:\dev`).
5. Antivirus/exclusive locks: delete stray `.pytest_cache` and `__pycache__` and rerun.
6. If only *golden/serialization* tests fail: check the two machines' Python
   versions — the encoder's output is version-stable by design, so a mismatch
   here indicates something real; capture the diff and compare byte-wise.

**Generated JSON differs between machines** — what to compare, in order:
1. **Which file:** compare *variant* JSONs only; manifests legitimately differ
   (`run_info` timestamp, §6).
2. Python patch versions (`python --version`) — the encoder is deterministic per
   the fixed policy, but pin and compare versions before doubting the tool.
3. The project inputs: same `.cbproj` / same wizard answers (a different seed
   set or variant label changes output legitimately).
4. Ordering: the encoder emits fixed key order; if you *manually* edited or
   re-serialized a file with another tool, ordering differences are yours, not the builder's.
5. Paths: the job `name` and directory naming derive from the project name —
   differing names indicate differing inputs.
6. Line endings: files are written `\n`; if you moved files via a text-mode FTP
   transfer, CRLF mangling is the transfer's fault — transfer binary.
7. Environment variables: none affect the encoder (§12) — if you suspect the
   environment, you are looking at the wrong cause.

---

## 16. EXACT COMMAND SUMMARY [Verified]

```text
# Check Python
python --version                         # expect 3.9.18 (or >=3.9; dev box: 3.11.15)

# Create environment
python -m venv .venv

# Activate environment — Windows
.venv\Scripts\activate.bat               # cmd   (PowerShell: .venv\Scripts\Activate.ps1)

# Activate environment — Linux
source .venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
pip install -e ".[dev]"

# Run tests
python -m pytest                         # full suite, from project root

# Run one test
python -m pytest "tests\unit\ui\test_step_machine.py::test_previous_is_never_blocked"

# Run application (interactive terminal)
python -c "from configbuilder.ui.render.wizard import run_wizard; from configbuilder.ui.services import build_services; run_wizard(build_services())"

# Generate/test example
python -c "...Smoke test B one-liner from section 5..."   # full pipeline to out\
python -m json.tool out\e2e-smoke-test\e2e-smoke-test__nob\e2e-smoke-test__nob.json

# Sanity checks
python -c "import configbuilder; print('ok')"
python -m pytest --collect-only -q
```

All of these were executed against this repository during this handoff (the
smoke-test one-liner is abbreviated here; copy it in full from §5).

---

## 17. FINAL TEST MATRIX

| Test | Machine | Command / Action | Expected Result |
|---|---|---|---|
| Python version | Windows (A) | `python --version` | 3.9.18 (dev box 3.11.15 also OK) |
| Environment setup | Windows (A) | §4.A block, then `pip show configbuilder` | editable install at project path |
| Unit tests | Windows (A) | `python -m pytest` | all pass (695 on dev box) |
| Application startup | Windows (A) | §4.B launch in a real terminal | probe line + `Step 1 of 14` |
| Smoke test | Windows (A) | §5 smoke A (author/validate/save) | findings incl. version-unverified ERROR; `.cbproj` saved |
| JSON generation | Windows (A) | §5 smoke B | exit 0; 2 JSON files under `out\` |
| Clean-machine test | Windows (B) | §14, all nine steps | identical annotations |
| Tests | Linux | §9 block, `python -m pytest` | all pass (CI-equivalent) |
| JSON portability | Linux | same project → generate → `diff` vs Windows variant JSON | byte-identical variant JSONs (not manifests) |
| AF3 submission | University Linux | upload variant JSON via normal submission path; then record observation in `docs/CONTRACT_PIN.md` | acceptance observed → pin recorded → generation unblocked by design |

---

## 18. SOURCING NOTES (what was verified vs assumed)

- Verified by execution: §4.A/§4.C commands, §4.B launch + piped-guard behaviour,
  §5 smoke flows (including the exact output tree and manifest keys in §6), the
  695-test count, single-test and `-x` invocations, the scratch-cwd
  `ModuleNotFoundError`, and the §14/§16 command surface.
- Verified by inspection: §1.1 tree, §1.2 import mechanics + pin-doc resolution,
  §1.3 entry-point gap, §3 dependency table, §7 classification, §9 portability,
  §11 path scan, §12 environment variables, §13 test data.
- Recommended but not implemented: `requirements-dev.txt`, a README, cleaning
  `__pycache__` before transfer, Git hosting for transfer.
- Unknown / requires manual verification on the target machine: exact hypothesis-
  degradation without the dev extra; pass-count variance on real 3.9; long-path
  behaviour on the specific Windows machine.
```
