# AF3 Builder GUI — Stage 1 Review Report

**Reviewed revision:** the working tree as found — branch `main`, 16 modified tracked
files, 16 untracked entries (§2.4). Nothing was committed, stashed, discarded, reset or
cleaned; no package was installed into the core environment; no application or test
behaviour was changed. §6 lists exactly what this review edited.

**Date:** 2026-10-16. **Scope:** check `GUI_STAGE1_IMPLEMENTATION_REPORT.md` against the
tree, correct its Python/PySide6 compatibility statements, inventory the Stage 1
changes, re-run the GUI/architecture/core suites and compare the failures with the
documented baseline, and record minimal fixes for whatever is wrong. Stage 2 was not
started.

**Headline:** the Stage 1 code and tests behave as reported on the verified
interpreter (PySide6 6.12.0 / CPython 3.11.15): **35/35 GUI tests, 40/40 architecture
tests, and the core suite unchanged at the documented 13 failures.** Two claims in the
implementation report were wrong and are now corrected: the `gui` extra **does**
resolve and install on Python 3.9 (it is not rejected), and one GUI test — not the
application — fails on PySide6 6.6.0–6.11.1. Both are detail in §1 and §4.

---

## 1. Compatibility finding: Python 3.9 vs 3.11, latest PySide6 vs the declared range

### 1.1 What the project declares

| Item | Value (as found) |
| --- | --- |
| `requires-python` | `>=3.9` (unchanged; the core still needs nothing) |
| `gui` extra | `PySide6>=6.6` — an open range, not a pin, and not in `dependencies`/`dev` |
| `[project.gui-scripts]` | `af3-json-builder = "configbuilder.ui.render.qt.application:main"` |
| CI (`.github/workflows/ci.yml`) | test job installs `-e ".[dev]"` on 3.9, 3.11 (+3.12 on Linux); a 3.9 smoke job installs core `.`. CI never installs the `gui` extra and never mentions PySide6, so the extra cannot change CI either way. |

### 1.2 Upstream metadata (PyPI JSON API, read 2026-10-16)

| PySide6 release | `Requires-Python` | `win_amd64` wheel of the release |
| --- | --- | --- |
| 6.6.0 / 6.6.3.1 | `<3.13,>=3.8` | `PySide6-6.6.3.1-cp38-abi3-win_amd64.whl` |
| 6.7.3 | `<3.13,>=3.9` | `cp39-abi3` (Essentials) |
| 6.10.3 | `<3.15,>=3.9` | `pyside6-6.10.3-cp39-abi3-win_amd64.whl` |
| 6.11.0 / 6.11.1 / 6.11.2 | `<3.15,>=3.10` | `pyside6-6.11.2-cp310-abi3-win_amd64.whl` |
| **6.12.0 (latest)** | `<3.16,>=3.10` | `pyside6-6.12.0-cp310-abi3-win_amd64.whl` |

So "PySide6 requires Python 3.10+" is true **only of the current release**. The declared
range `>=6.6` still admits five minor series that accept Python 3.9.

### 1.3 Resolution: 3.9 does *not* fail — measured, not reasoned

```
$ printf 'PySide6>=6.6\n' | uv pip compile - --python-version 3.9  --python-platform windows
pyside6==6.10.3            (+ pyside6-addons, pyside6-essentials, shiboken6 6.10.3)   exit 0
$ printf 'PySide6>=6.6\n' | uv pip compile - --python-version 3.11 --python-platform windows
pyside6==6.12.0            (+ addons, essentials, pdf, webengine, shiboken6 6.12.0)   exit 0
```

On a 3.9 interpreter the range resolves to **PySide6 6.10.3** — the newest release whose
`Requires-Python` still covers 3.9 — and `pip install -e ".[gui]"` therefore installs
rather than failing. The implementation report's §5 bullet claiming a loud
"no matching distribution" failure on 3.9 was **wrong**, as was its §2 sentence
"Python 3.10 or newer is required for the GUI (PySide6 ships `cp310-abi3` wheels only)".
A loud failure would need the constraint tightened to `PySide6>=6.11`.

### 1.4 Consequence for the support contract

No change to the project's Python contract is warranted or made. `requires-python`
stays `>=3.9`; the core is untouched; the `gui` extra is opt-in and installs on 3.9
(PySide6 6.10.x) and on 3.10+ (current PySide6 6.12.0). Python 3.10+ remains the
recommended and the verified interpreter. The three wrong statements were corrected in
place — report §2, report §5, and the two `pyproject.toml` comments (§6).

### 1.5 Behavioural caveat on the declared floor (measured)

Version-specific behaviour was measured by installing each PySide6 release into a
throwaway target directory and running `tests/gui` against it (`PYTHONPATH` selects the
version; nothing in the repository was changed to do this):

| PySide6 | `tests/gui` | `window.menuBar().actions()[0].menu()` (chained) | same menu, action bound first | `findChild(QMenu)` |
| --- | --- | --- | --- | --- |
| 6.6.3.1 | 34 passed, 1 failed | invalid wrapper | alive | alive |
| 6.7.3 | 34 passed, 1 failed | invalid wrapper | alive | alive |
| 6.9.3 | 34 passed, 1 failed | invalid wrapper | alive | alive |
| 6.10.3 | 34 passed, 1 failed | invalid wrapper | alive | alive |
| 6.11.0 | 34 passed, 1 failed | invalid wrapper | alive | alive |
| 6.11.1 | 34 passed, 1 failed | invalid wrapper | alive | alive |
| 6.11.2 | **35 passed** | alive | alive | alive |
| 6.12.0 (verified env) | **35 passed** | alive | alive | alive |

The per-version wrapper cells were probed directly (with `shiboken6.isValid`) on
6.6.3.1, 6.10.3, 6.11.1, 6.11.2 and 6.12.0; for 6.7.3, 6.9.3 and 6.11.0 the column is
inferred from the suite result (the identical failure and message), not from a separate
probe. The suite column is a measurement on every row.

The single failure is always
`tests/gui/test_window.py::test_the_window_offers_no_writing_action`, raising
`RuntimeError: Internal C++ object (PySide6.QtWidgets.QMenu) already deleted` from its
`_menu_actions` helper. On the affected versions that message is misleading: the File
menu **is** alive and usable in the same process — `findChild(QMenu)` and the bound form
both return a valid menu with `['Open AF3 JSON…', 'Quit']`, and `menu.popup(...)` shows
it (checked on 6.6.3.1 and 6.10.3). Only the chained expression
`window.menuBar().actions()[0].menu()` hands back an invalid wrapper. PySide6 fixed
that between 6.11.1 and 6.11.2. **Conclusion: the application works on the whole
declared range; the test is what is version-fragile** (see §4, P2).

### 1.6 Not verifiable on this machine

* **A real Python 3.9 run.** `py -0` lists only 3.12 and CPython 3.11.15. The *resolution*
  result in §1.3 is verified; that the GUI then runs on 3.9 + PySide6 6.10.3 is **inferred**
  from the 6.10.3 measurements on 3.11 (34/35 in the suite, working menu), not from a 3.9
  execution.
* **A real `pip` run.** pip's downloader stalls on this machine (documented in the
  implementation report §5), so resolution was verified with `uv`'s resolver, which reads
  the same `Requires-Python` metadata pip uses. Same outcome expected from pip; not executed.

---

## 2. Exact Stage 1 inventory

Method: `git status --porcelain`, `git diff --stat`, and per-hunk inspection of the two
shared files (`git diff -U0 … | grep -E "^(@@|\+)"`). Line counts are physical lines.

### 2.1 Created — the front end `configbuilder/ui/render/qt/` (13 modules, 1 581 lines)

| File | Lines | Purpose |
| --- | --- | --- |
| `__init__.py` | 21 | Package docstring, `main` re-export; documents why the front end lives under `ui/render`. |
| `__main__.py` | 11 | `python -m configbuilder.ui.render.qt` → `application.main()`. |
| `application.py` | 66 | Composition root (Qt analogue of `app/cli.py`): `--demo`/path parsing, `GuiState`, `MainWindow`, event loop. |
| `state.py` | 137 | `GuiState`: the window's view of `build_services()`; owns only "which file is open"/"is this demo"; `build_demo_state()`. |
| `models.py` | 547 | Read-only `QAbstractTableModel` projections: entities, findings, status rows. |
| `windows/__init__.py` | 7 | Re-export. |
| `windows/main_window.py` | 181 | `QMainWindow`: File menu, toolbar, three tabs, status bar, preview→confirm→commit import. |
| `pages/__init__.py` | 14 | Re-export. |
| `pages/overview.py` | 221 | Job facts, readiness rows/verdict, findings table, finding→entity jump. |
| `pages/entities.py` | 188 | Entity table plus the selected record's details. |
| `pages/preview.py` | 77 | Read-only monospace JSON pane with Refresh. |
| `dialogs/__init__.py` | 14 | Re-export. |
| `dialogs/import_preview.py` | 97 | Dumb `ImportPreviewDialog` over the service's summary/notes; `show_failure`. |

### 2.2 Created — tests and session documents

| File | Lines | Purpose |
| --- | --- | --- |
| `tests/gui/__init__.py` | 5 | Marks the package; documents that the modules skip without the extra. |
| `tests/gui/conftest.py` | 107 | Offscreen platform, skip without PySide6, no-modal-boxes guard, fixtures `state`/`filled`/`window`/`reviewed`. |
| `tests/gui/test_window.py` | 97 | 7 tests: shell, tabs, empty state, the absence of any writing action, read-only notice, source line, demo labelling. |
| `tests/gui/test_import_flow.py` | 229 | 11 tests: preview/confirm/commit, real modal dialog driven by a watchdog timer, refusals, source file bytes+mtime unchanged. |
| `tests/gui/test_entity_table.py` | 102 | 6 tests: row order/identity vs `configuration.records`, per-row values, no reordering, `row_for_record_key`. |
| `tests/gui/test_readiness.py` | 97 | 6 tests: status rows == service rows, ready/blocked wording, findings table, finding→row jump, source line. |
| `tests/gui/test_preview.py` | 66 | 5 tests: pane text == `show_json`, read-only editor, refusal reason, Refresh re-asks. |
| `GUI_STAGE1_IMPLEMENTATION_REPORT.md` | 267 → 290 | The implementation report reviewed here (grown by 23 lines of corrections, §6). |
| `AF3_GUI_STAGE1_IMPLEMENTATION_PROMPT.md` | — | The Stage 1 work order (untracked, pre-existing at session start). |

### 2.3 Modified — what Stage 1 actually added to already-modified files

| File | Stage 1 change | Pre-existing change in the same file (not Stage 1) |
| --- | --- | --- |
| `configbuilder/ui/present/strings.py` | 64 added lines, lines 351–414: one blank line, a 4-line comment headed "the Qt desktop front end (Stage 1)", then **59 `gui.*` entries** (window chrome, tab titles, column headers, section labels, CLI help). No other line of the file is Stage 1's. | 61 added / 30 removed lines across the menu rework (PTM wording, DNA-complement wording, seeds-method wording, variant wording) — these match the already-modified `ui/render/menus.py`, `app/variant_service.py`, `app/batch_variants.py`, `persistence/sequences.py`. |
| `pyproject.toml` | 16 added lines: the 8-line `gui` extra block (5 comment + `gui = [`, `"PySide6>=6.6"`, `]`) and the 8-line `[project.gui-scripts]` block (5 comment + table header + `af3-json-builder` entry + blank). | 14 added / 1 removed: the `analysis` extra (13 lines) and `include = ["configbuilder*", "af3_analysis*"]`. |

**No other tracked file carries a Stage 1 hunk.** The other 14 modified files
(`app/batch_variants.py`, `app/status.py`, `app/variant_service.py`,
`persistence/__init__.py`, `persistence/sequences.py`, `ui/render/menus.py`, and eight
`tests/unit/**` files — 16 modified in total, 577 insertions/183 deletions overall) are
the pre-existing working-tree rework the audit already recorded (it measured "16 modified
tracked files and 9 untracked" before Stage 1; the count is still 16, with no new name).
Stage 1 added no new top-level package and no new direct child of `ui/`: the front end
sits under the already-allowed `ui/render`, which is why
`tests/architecture/test_layout.py` (exactly ten packages, `ui` = {`render`, `present`})
still passes.

### 2.4 Untracked entries (16, listed exactly)

* **Stage 1 code:** `configbuilder/ui/render/qt/`, `tests/gui/`.
* **Stage 1 documents:** `GUI_STAGE1_IMPLEMENTATION_REPORT.md`, `GUI_STAGE1_REVIEW_REPORT.md`
  (this report), `AF3_GUI_STAGE1_IMPLEMENTATION_PROMPT.md`.
* **Pre-existing:** `af3_analysis/`, `tests/analysis/`, `generated_jobs/`,
  `GUI_AUDIT_REPORT.md`, `AF3_GUI_AUDIT_PROMPT.md`,
  `AF3_Comparative_Structural_Analysis_SOP.md`,
  `AF3_Oct4_10_Condition_JSON_Builder_Agent_Prompt.md`, `IMPLEMENTATION_MAP.md`,
  `IMPLEMENTATION_MAP_FULL.md`, `THESIS_IMPLEMENTATION_CHAPTER.md`.
* **Scratch, not source:** `pytest-of-Chris/` — a pytest temporary root at the repository
  root holding `pytest-8/9/10` with `tmp_path` directories named after the `tests/gui`
  import-flow tests (timestamps 2026-10-16 00:29–00:33). It is not git-ignored, it is not
  Stage 1 code, and its contents are only throwaway test scratch. It is **left in place**
  rather than deleted, because this review was asked not to clean the working tree; safe to
  delete once confirmed by its owner.

### 2.5 Packaging surface

`pyproject.toml` still declares `dependencies = []`, `requires-python = ">=3.9"`, the
unchanged `configbuilder` console script, and the new `gui` extra + `af3-json-builder`
`gui-scripts` entry. `.gitignore` already covers `.venv*/`, and `__pycache__/` is ignored,
so the compiled files that appear inside the new untracked `qt/` and `tests/gui/`
directories are not part of the change set.

---

## 3. Test and import-path results (exact)

All commands run from the repository root on 2026-10-16. The core environment has no
PySide6; the GUI environment is `.venv-gui/` (CPython 3.11.15, PySide6 6.12.0, editable
install of this working tree).

### 3.1 Commands, exit statuses and counts

| Command | Exit | Result |
| --- | --- | --- |
| `python -m pytest -o addopts="" -q -rf` | 1 | `13 failed, 990 passed, 6 skipped, 1 warning in 108.65s` |
| `python -m pytest -o addopts="" -q tests/architecture` | 0 | `40 passed in 6.42s` |
| `QT_QPA_PLATFORM=offscreen .venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | 0 | `35 passed in 0.76s` |
| `python -m pytest -o addopts="" -q -rs tests/gui` (no PySide6) | 0 | `5 skipped`, each `the GUI extra (PySide6) is not installed` |
| `… --collect-only tests/gui` | 0 | 7 + 11 + 6 + 6 + 5 = **35**, matching the report's table |

The exit status is pytest's normal non-zero for a suite with failures; the core suite
status is unchanged by Stage 1 (it is red before and after, for the reasons in §4 P4).

### 3.2 The 13 core failures are byte-identical to the documented baseline

Baseline = the 13 node ids tabulated in `GUI_AUDIT_REPORT.md` §2.4. Compared as sets:
only-in-baseline = ∅, only-in-actual = ∅ (the two extra strings that regex finds in the
audit, `ADD_DNA` and `identifiers`, are prose references to helpers, not node ids).

```
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

`990 passed` is also unchanged from the audit, i.e. the five new GUI modules contribute
no passes to the core run. No stale test was edited and no application behaviour was
changed to accommodate one.

### 3.3 The skip arithmetic checks out

`1 + 5 = 6`: the audit's single platform skip
(`tests/unit/persistence/test_sequence_files.py:50` — "Windows cannot express a read-denied
file through chmod"; re-confirmed in isolation, `9 passed, 1 skipped`) plus the five
`tests/gui/**` modules, which call `pytest.importorskip("PySide6")` at
`test_window.py:11`, `test_import_flow.py:18`, `test_entity_table.py:13`,
`test_readiness.py:11`, `test_preview.py:14`. Collection therefore totals 1 009 items
(the audit's 1 004 + the 5 GUI modules).

### 3.4 Import paths and launch paths

| Check | Result |
| --- | --- |
| Import all 13 modules of `configbuilder.ui.render.qt` (offscreen) | OK; `configbuilder` resolves to the working tree (`C:\Users\Chris\Desktop\THESISSP\configbuilder\__init__.py`), PySide6 6.12.0 |
| `python -m configbuilder.ui.render.qt --help` | exit 0; usage `af3-json-builder [-h] [--demo] [path]` with the registry wording |
| `timeout 3 … -m configbuilder.ui.render.qt --demo` (offscreen) | exit 124 = still in the event loop after 3 s, **0 bytes** of output |
| `timeout 3 .venv-gui/Scripts/af3-json-builder.exe --demo` (offscreen) | exit 124 = still in the event loop, **0 bytes** of output |
| `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` | OK; `gui` extra `['PySide6>=6.6']`, `gui-scripts` and `scripts` as declared |

### 3.5 The suite against every PySide6 release in the declared range

See §1.5. Method: `uv pip install --target <scratch>` for each release, then
`PYTHONPATH=<scratch> … -m pytest tests/gui` — 6.6.3.1, 6.7.3, 6.9.3, 6.10.3, 6.11.0 and
6.11.1 give `1 failed, 34 passed`; 6.11.2 and 6.12.0 give `35 passed`. The repository was
not modified to run this, and nothing was installed into the core environment.

---

## 4. Problems found, and their minimal fixes

**P1 — Two compatibility statements were factually wrong. Status: corrected in place.**

* `GUI_STAGE1_IMPLEMENTATION_REPORT.md` §5, last bullet: "`PySide6>=6.6` has no 3.9
  wheels, so `pip install -e ".[gui]"` on 3.9 fails loudly …". Wrong — see §1.3.
* `GUI_STAGE1_IMPLEMENTATION_REPORT.md` §2, first paragraph: "Python 3.10 or newer is
  required for the GUI (PySide6 ships `cp310-abi3` wheels only)". Wrong for the declared
  range; true only of 6.11+ / the current 6.12.0.
* `pyproject.toml`, the two Stage 1 comment blocks: "PySide6 ships wheels for Python 3.10
  and later only" and "a 3.10-or-newer interpreter is required for it". Same error.

Fixed by rewriting those statements (§6); no constraint, script or support claim was
changed, because the corrected facts show the existing declaration is sound.

**P2 — `tests/gui/test_window.py::_menu_actions` is fragile on PySide6 6.6.0–6.11.1.
Status: measured and reproduced; NOT applied (out of this review's scope).**

`_menu_actions` reads the File menu with one chained expression:

```python
file_menu = window.menuBar().actions()[0].menu()        # invalid wrapper on <= 6.11.1
```

On those releases the returned wrapper is invalid (`shiboken6.isValid(...) is False`),
so `test_the_window_offers_no_writing_action` errors with "Internal C++ object (QMenu)
already deleted" — while the very same menu is alive and usable in that process through
`findChild(QMenu)` or through a bound action, and pops up with both entries (§1.5). It is
a PySide binding artefact of the chained call, fixed upstream in 6.11.2; it is **not** a
Stage 1 defect and not a stale test — the test's assertion is exactly right.

Minimal fix (keeps the assertion, keeps the declared floor at `>=6.6`):

```python
def _menu_actions(window):
    bar = window.menuBar()
    action = bar.actions()[0]          # bind the action before asking it for its menu
    file_menu = action.menu()
    return [a for a in file_menu.actions() if not a.isSeparator()]
```

Verified by injecting that replacement helper from a throwaway pytest plugin (repository
untouched): `tests/gui` gives **35 passed on 6.6.3.1, 6.10.3 and 6.11.1**, and is
unchanged at 35 passed on 6.12.0. The alternative fix is to raise the extra to
`PySide6>=6.11.2`, which would also make the suite green but would drop every
Python 3.9 installation; the helper fix is preferable because it widens nothing and
weakens nothing.

**P3 — Nothing else is wrong in the Stage 1 surface.** Checked and found consistent:
no write/save/generate/execute path exists in the new package, no wire field name or
unregistered sentence leaks into `ui` (the string-registry and wire-confinement
meta-tests pass), the layout/dependency rules hold with the front end under
`ui/render`, `dependencies` is still empty, the `configbuilder` console script and CLI
are unchanged, and both entry points start. The GUI tests' own coverage matches the
report's table (7/11/6/6/5).

**P4 — Pre-existing, deliberately untouched:** the 13 stale end-to-end failures
(the audit's D6: keystroke scripts written against the pre-rework menu) and the
uncommitted menu/variant/PTM work in 14 other tracked files. They are not Stage 1's and
no attempt was made to repair, skip or weaken them.

**P5 — Housekeeping observations, no action taken:** compiling the new package leaves
`__pycache__/` directories inside the untracked `qt/` and `tests/gui/` trees (git-ignored,
43 ignored directories in total); the untracked `pytest-of-Chris/` scratch root noted in
§2.4 sits in the repository root un-ignored though it is only test temp data; the scratch
environments and PySide6 target directories this review created live under `%TEMP%`
(`.venv-gui` remains where the implementation put it) and can be deleted at will. Nothing
was removed, because this review was asked not to clean the working tree.

---

## 5. Verified here vs not independently verifiable

| Claim | Status |
| --- | --- |
| 35 GUI tests pass in the GUI environment; 40 architecture tests pass; core suite unchanged at 13 failures | **Verified** (full re-run, exact counts in §3.1–3.2) |
| Core failure set identical to the documented baseline, no new failures | **Verified** (set comparison §3.2) |
| GUI modules skip cleanly without the extra, so the core suite runs on a PySide6-free environment | **Verified** (§3.1, §3.3) |
| `PySide6>=6.6` resolves on 3.9 to 6.10.3 and on 3.11 to 6.12.0 | **Verified** by resolution against PyPI metadata (§1.3) |
| The GUI itself works on PySide6 6.6.3.1 and 6.10.3 (dead test access notwithstanding) | **Verified** for the window's File menu (alive, correct entries, pops up); the rest of the suite is 34/35 there |
| The GUI runs on a real Python 3.9 interpreter | **Not verified** — no 3.9 interpreter on this machine (`py -0`: 3.12, 3.11.15) |
| `pip install -e ".[gui]"` end-to-end | **Not verified** — pip's downloader stalls on this machine (pre-existing environment fault); resolution checked with uv instead |
| Real display, native file dialog, Windows packaging | **Not verified by design** (out of Stage 1 scope, as the report states) |
| The 13 e2e failures are stale, not regressions | **Not re-derived here** — the audit's analysis is accepted; only the failure *set* was compared |

---

## 6. What this review changed, and what it left alone

**Edited (documentation only):**

1. `GUI_STAGE1_IMPLEMENTATION_REPORT.md`
   * §2 opening: replaced the "Python 3.10 or newer is required" paragraph with the
     corrected release/range statement and a pointer to this report.
   * §5 last bullet: replaced the "3.9 fails loudly" claim with the measured resolution
     result and the real (behavioural) 3.9-era caveat.
   * §1 changed-files table: the `strings.py` and `pyproject.toml` rows now give the
     Stage 1 line counts (64 lines of `gui.*` entries at 351–414; 16 lines of `gui`
     extra + `gui-scripts`) and state explicitly which parts of those diffs pre-date the
     stage.
2. `pyproject.toml`: the two Stage 1 comment blocks about PySide6 and the Python floor
   were rewritten (comment text only). Re-parsed with `tomllib`: `requires-python`,
   `dependencies`, the `gui` extra value, `[project.scripts]` and `[project.gui-scripts]`
   are all byte-identical to before this review.

**Left alone:** all application code, all tests (including the one described in §4 P2),
CI, `strings.py`, the 14 other modified tracked files, the untracked pre-existing
documents and directories, and every uncommitted change. No commit, stash, reset, clean,
`pip install` into the core environment, or dependency addition was performed. The only
installs made were PySide6 releases into throwaway `%TEMP%` target directories (for §1.5
and the §4 P2 verification) and the earlier `.venv-gui` environment, which is unchanged.

