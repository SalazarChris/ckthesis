# AF3 JSON Builder — Automated End-to-End QA and Regression Repair

## Objective

Perform a rigorous, reproducible automated verification of the current AF3 JSON Builder CLI and PySide6 GUI. Do not ask the user to click through the application manually. Use automated tests, real widget interactions, temporary files/directories, service-level assertions, launcher smoke tests, and output inspection.

The latest known report is `docs/GUI_FINAL_LAYOUT_REFINEMENT_REPORT.md`. It records 275 GUI tests passing, 40 architecture tests passing, and a core-suite result of 1032 passed / 13 failed / 16 skipped. The 13 failures were described as legacy terminal-menu end-to-end scripts. These are historical claims, not proof of the current working tree: re-run the commands and establish the current truth.

The current UI intentionally has four primary workspace destinations: Overview, Entities, Variants and Generate. The JSON Preview destination and Overview preview shortcut were removed. Saving remains available through the FILE footer / File menu. Overview contains a compact readiness line and entity summary. Entities uses a compact entity picker and separate areas for entity settings, Custom CCDs and Covalent Bonds. Keep these current UX decisions unless a test proves a real defect; do not reintroduce removed UI or unnecessary features.

## Safety constraints

1. Inspect the actual current repository and `git status --short` before editing. Record the branch, HEAD and existing modified/untracked files in your report.
2. Do not reset, clean, stash, restore, checkout, rebase, amend, or commit. Never overwrite or delete pre-existing user work.
3. Do not run real AlphaFold 3 inference, contact a cluster, submit jobs, or use network services. This is builder verification only.
4. Use temporary directories (`tmp_path` or equivalent) for all test outputs. Never write generated test data into the user's real `generated_jobs`, `output`, or thesis data directories.
5. Do not change the JSON contract, scientific/domain rules, default settings, serialization ordering, identity allocation, or output-planning policy just to make tests pass.
6. Never delete, skip, xfail, weaken, or broadly loosen a test to obtain a green result. Preserve the intention of existing tests.
7. Keep the core package usable without PySide6. Do not add the GUI dependency to core dependencies.
8. Do not claim a check passed unless you actually ran it. Include exact commands, exit codes and summaries. Separate automated widget tests, true end-to-end tests, launch smoke tests, and checks that remain impossible to prove automatically.
9. Do not stop after seeing existing tests pass. Inspect workflow gaps and add deterministic automated coverage where necessary.

## Phase 1 — Establish the current baseline

Before changing files:

- Read `RUNNING_THE_APPLICATION.md`, the latest GUI implementation/refinement reports, `pyproject.toml`, launcher scripts (`gui.py`, `af3builder.py`), and the relevant service and UI code.
- Record `git status --short`, current branch and HEAD. Distinguish pre-existing modifications from anything you create.
- Run and capture the results of:
  - `python -m pytest -o addopts="" -q`
  - `python -m pytest -o addopts="" -q tests/architecture`
  - `python -m pytest -o addopts="" -q tests/unit/test_launchers.py`
  - `python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py`
  - `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` (adapt only shell syntax for the actual platform)
  - `python -m compileall -q configbuilder tests/gui`
  - `python gui.py --help`
- Use the repository's actual interpreter paths if they differ. On Windows PowerShell, use `$env:QT_QPA_PLATFORM = "offscreen"` before the GUI test command.
- Save the complete failing node IDs for comparison with the reported 13 legacy CLI failures.

Do not use prior reports as a substitute for running these checks.

## Phase 2 — Audit coverage against complete user workflows

Inspect the existing tests and add end-to-end coverage for any missing transitions. Prefer current testing conventions, real Qt widgets, QtTest or the already-installed test tools. Do not add a new test framework unless it is genuinely needed and justified.

### A. Startup, navigation and job lifecycle

Automate these flows:

1. Start the GUI through its supported launcher/entry point and close it cleanly without hanging.
2. Test `python gui.py --help`, `python gui.py --demo`, and a JSON path argument including a path with spaces. Use watchdogs/timeouts for event loops.
3. Verify the no-job state has no obsolete begin-card, Add Entity action, JSON Preview destination, or duplicate Job Settings destination. New/Open/Save remain discoverable in their current location.
4. Create a new job, edit name/seeds/version, verify dirty/title state, cancel destructive actions, and verify the project is preserved.
5. Open a valid JSON file using the actual import-preview dialog; test Cancel and Import. Invalid JSON and missing paths must fail cleanly without replacing the current project.
6. Save a ready job, verify the destination bytes, reopen it, and verify semantic round-trip and stable IDs/order. For equivalent configurations, verify deterministic output bytes where the existing contract promises it.
7. Attempt a blocked save. Assert that a clear reason appears and no file is created/overwritten.

### B. Entity operations

Exercise the actual GUI controls and assert both service/domain state and resulting JSON:

- Add, select, edit and delete protein and RNA records.
- Add DNA via one service operation; verify both strands and their partner relationship. Edit either strand and verify service-defined partner behaviour. Test delete confirmation cancellation and confirmation. Imported lone DNA must remain a lone strand.
- Add a ligand using one CCD code, multiple CCD codes, SMILES, and multiple copies; verify IDs, representation exclusivity, selection and deletion.
- Verify failed operations preserve values and dirty state, and show a readable error rather than a traceback.
- Verify the picker handles zero records, multiple records, both duplex strands, lone DNA, and multi-copy identifiers.
- Assert no GUI code builds JSON wire dictionaries, allocates IDs itself, or computes DNA complements.

### C. Advanced settings

Use service-backed GUI interactions to test where supported:

- Add/edit/remove PTMs; valid and out-of-range positions; verify 1-based position semantics and readable findings/refusal messages.
- Change supported protein and RNA MSA/alignment modes, including source fields where applicable; ensure irrelevant fields clear or persist according to existing service semantics, not UI guesses.
- Add/edit/remove protein templates and verify exact path/reference semantics.
- Add, apply, replace and clear custom CCD definitions; verify inline vs file-path mutual exclusion and version compatibility behaviour.
- Add/remove covalent bonds; validate both endpoints and test insufficient entities / invalid endpoints. Cancel confirmations and assert no mutation.
- Test the current UI layout: Alignment/MSA appears before Templates and PTMs; Custom CCDs and Covalent Bonds are dedicated whole-job work areas; no unnecessary sequence preview or persistent validation-findings table is reintroduced.

### D. Variants and batch

Exercise the current guided workflow through real widgets:

- Opening Variants shows the three choices without all workflow forms displayed simultaneously.
- Back to choices cancels without committing changes.
- Create, rename, edit, duplicate, validate and remove a manual variant using the existing spec-based services.
- Verify base configuration equality before/after each variant workflow; variants must not drift into or mutate the base.
- Create a quantity series; compare the previewed plan with exactly what gets committed.
- Load sequence and SMILES batch files through temporary files; test valid, empty and malformed files, preview-before-commit and all-or-nothing failure semantics.
- Validate a variant and assert blocking failures prevent generation with an explanatory message.
- Test that selected-variant controls only appear when that scope is selected.

### E. Generate and output

Exercise the complete, filesystem-backed flow using a temporary directory:

1. Choose base-only, selected variant, and all supported variant scopes.
2. Choose a destination directory and supported path/overwrite policies.
3. Preview the plan; inspect expected JSON files, assets, manifest, warnings and conflicts.
4. Cancel confirmation and prove no output bytes/files changed.
5. Generate successfully; inspect output directories and parse every produced JSON file with `json.loads`.
6. Assert JSON payloads comply with the existing serializer/service output, ID ordering and resource paths. Verify copied assets exist where expected and manifest contents match the plan.
7. Create a real conflict at a temporary target; test Fail/Overwrite/Skip semantics as supported and prove files outside the target are untouched.
8. Change the job or relevant controls after plan preview; ensure a stale plan cannot be executed without re-planning/review.
9. Exercise permission/path errors where the current OS can represent them, otherwise document the platform limitation.

Do not call AF3 or analyze structural outputs.

### F. Layout, interaction and accessibility-adjacent checks that can be automated

Use Qt's widget APIs/QTest, not assumptions from screenshots:

- Launch at the normal and minimum supported sizes (including 940×640 if supported); resize/maximize and assert key controls remain visible or scrollable and not clipped.
- Ensure the sidebar navigation has exactly the intended destinations and action buttons have human-readable text/tooltips.
- Test keyboard focus movement through sidebar, form controls, dialogs and confirmation buttons. Ensure default/cancel actions are safe.
- Check accessible names/descriptions for important unlabeled controls where Qt supports those properties.
- If practical, run a subprocess smoke at `QT_SCALE_FACTOR=1.25` and `QT_SCALE_FACTOR=1.5`; record the method and result. These are supplemental and do not replace real Windows DPI testing.
- Capture real widget screenshots using an available Qt platform plugin (do not use the offscreen plugin for screenshots if it lacks system fonts). Verify dimensions and key widget visibility programmatically. Do not claim that image capture proves human visual quality or screen-reader compatibility.

## Phase 3 — Investigate the 13 legacy CLI end-to-end failures

The previous reports consistently list 13 failures in:

- `tests/e2e/test_entity_lifecycle.py` (3 tests)
- `tests/e2e/test_menu_acceptance.py` (10 tests)

They reportedly assert old numbered-menu input sequences/defaults, while the CLI menu has since changed. Re-run and inspect each failure against the current implementation.

- If a test script is stale, update its scripted responses and expected outputs to match current intended CLI behaviour, preserving the test's original end-to-end purpose.
- If a failure reveals a real defect, fix the smallest appropriate code path and add a regression assertion.
- Do not remove the tests, mark them xfail, loosen assertions to generic substrings, or change production defaults merely to satisfy outdated expectations.
- If any failure cannot be safely resolved in scope, leave it in place and document its evidence and reason.

## Phase 4 — Fix defects and rerun everything

After baseline and coverage audit:

- Fix only reproduced defects in the current GUI/CLI workflows or test fixtures needed to represent intended current behaviour.
- Keep changes surgical. Do not reorganize packages or restyle the entire UI as part of QA.
- After every fix, run the directly affected test first, then the relevant GUI or unit suite.
- At the end, rerun the baseline commands and all new end-to-end tests.
- Compare test node IDs before and after. Aim for a green full suite, but never hide unresolved failures.
- Run Ruff using the repository's configured scope and report any pre-existing findings separately.
- Check the final diff/file list and ensure no generated output or temporary test artefacts remain in the repository.

## Required deliverable

Create `docs/GUI_AUTOMATED_QA_REPORT.md` with:

1. Environment and exact revision (branch, HEAD, interpreter versions, installed GUI/test dependencies).
2. Starting working-tree status and protections taken for existing user edits.
3. Initial baseline results and exact failing node IDs.
4. Workflow coverage matrix: workflow, test file/test IDs, filesystem side effects checked, result.
5. Bugs found, reproduction evidence, minimal fixes and regression tests added.
6. CLI e2e test outcome: which were updated and why, with evidence that their original coverage remains.
7. Final exact commands, exit codes, pass/fail/skip counts and comparison to baseline.
8. Output verification evidence: temporary paths, parsed JSON count, assets/manifest checks, conflict/cancellation results.
9. Screenshot/layout smoke checks and their limitations.
10. Remaining failures and issues, clearly categorized as defects, stale tests, environment/platform limitations, or checks requiring a human.
11. Final changed-file inventory; explicitly confirm no reset/clean/stash/commit occurred.

End with a concise readiness verdict using one of:
- **Verified by automated tests** — supported by passing end-to-end evidence.
- **Partially verified** — key tests passed, with named gaps.
- **Not verified** — missing evidence or unresolved failures block the claim.

## Stop condition

Do not implement new biological features, add new UI concepts, redesign the theme, build an executable, or run AF3 inference. This task is QA and minimal defect repair only. After writing the report and verifying the final suite, stop and wait for user review.
