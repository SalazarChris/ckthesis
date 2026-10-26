# AF3 JSON Builder — Independent Final Release Review (Read-Only)

## Purpose

Perform an independent, evidence-based review of the current AF3 JSON Builder repository after the automated end-to-end QA pass. The previous report is `docs/GUI_AUTOMATED_QA_REPORT.md` (or the uploaded `GUI_AUTOMATED_QA_REPORT.md`). It reports:

- core suite: 1048 passed, 0 failed, 17 skipped;
- GUI suite: 286 passed;
- CLI end-to-end suite: 64 passed;
- architecture suite: 40 passed;
- launcher tests: 19 passed;
- output verification: four JSON documents parsed, asset path checked, manifest checked;
- one functional defect fixed: single-stranded DNA addition;
- previously failing CLI menu scripts updated to match current interaction flow.

Do not accept those claims uncritically. Check the repository and gather your own evidence where practical.

## Strict mode: review only

- Do not modify source files, tests, documentation, configuration, dependencies, fixtures, screenshots, or generated outputs.
- Do not install or upgrade packages.
- Do not run `git reset`, `git clean`, `git checkout`, `git restore`, `git stash`, rebase, amend, or commit.
- Do not delete, rename, overwrite, reformat or move any file.
- Temporary test artifacts may be created only outside the tracked checkout or in pytest-managed temporary directories; remove only artifacts created by this review.
- Do not run automatic lint fixes or broad formatting commands.
- Do not claim to have tested a real display, screen reader or OS dialog unless it actually happened.

The working tree contains substantial pre-existing user work. `JSON_BUILDER_AUDIT_AND_FINALIZATION.md` was already deleted before the QA pass. Treat this and every untracked/pre-existing item carefully. Do not assume all changes relative to HEAD belong to the QA pass; correlate with the report's file inventory and state uncertainty.

## Review tasks

### 1. Establish the current state

Record:
- branch and HEAD;
- `git status --short`;
- `git diff --stat` and `git diff --check` results;
- current Python versions and whether the core interpreter has PySide6 installed;
- the currently available GUI test command and launcher commands.

Do not print secrets or unrelated personal data from files.

### 2. Audit the new DNA single-strand fix

Inspect `configbuilder/app/configuration_service.py`, `configbuilder/ui/render/menus.py`, and relevant unit/e2e tests.

Verify from code and tests that:
- the default `add_record("dna", ...)` behaviour is unchanged and produces a duplex;
- `duplex=False` creates exactly one supplied strand, without a hidden partner;
- a lone strand can be edited and removed without removing unrelated DNA records or requiring a partner;
- the CLI uses one service call and no longer adds a duplex and then removes a strand;
- existing GUI DNA creation still uses the default duplex behaviour;
- IDs remain registry-managed and no GUI or CLI code deletes entities by list position.

Report any ambiguity or semantic edge case; do not fix it.

### 3. Audit the repairs to the 13 old CLI failures

Inspect the edits to `tests/e2e/test_entity_lifecycle.py`, `tests/e2e/test_menu_acceptance.py`, and the related production paths. Confirm that tests were updated to current CLI prompts/defaults rather than weakened or removed. Verify their meaningful assertions still cover entity state, identities, saved JSON and round-trips. Confirm the renamed picker-cancellation test still ensures a cancelled open leaves the project unchanged.

Run the CLI end-to-end suite and report the exact result:

```powershell
python -m pytest -o addopts="" -q tests/e2e
```

### 4. Verify core, GUI and architectural regression suites

Run the following from the project root. Use the core Python for core tests and `.venv-gui` for GUI tests. Use the offscreen Qt platform for automated GUI tests.

```powershell
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q
python -m compileall -q configbuilder tests/gui tests/e2e
python gui.py --help
```

If any command differs from the report, investigate the specific discrepancy and report it. Do not adapt assertions merely to make the suite green.

### 5. Audit the quality and scope of the GUI tests

Inspect the tests for real assertions, not just screenshots or source-text matching. Confirm meaningful behavioural coverage for:
- launcher argument forwarding, `--demo`, paths with spaces;
- no-job Overview and absence of JSON Preview in navigation/focus;
- entity picker, family-appropriate fields and job-wide CCD/bond areas;
- PTMs/MSA/templates and service refusal paths;
- variant creation, quantity series, file batches and preservation of the base configuration;
- generation planning, cancellation, overwrite policies, conflict handling, stale-plan refusal, output assets and manifest consistency;
- save refusal (no file written), save/reopen round-trip and deterministic output;
- accessible names and visible keyboard focus where actually tested.

Flag tests that pass only due to overly broad mocks, automatic confirmation fixtures, or internal implementation assumptions. Distinguish a weakness from a definite defect.

### 6. Audit output evidence

Review the existing generation tests and report evidence. Where possible, rerun the focused generation/output tests in a fresh temporary test directory. Confirm that every generated JSON parses, manifest data corresponds to the generated variants, copied assets exist at the referenced paths, cancellation writes nothing, and conflicts leave existing files unchanged.

Do not invoke AlphaFold 3 inference, access a cluster, access the network, or use real thesis data for this review.

### 7. Check launch and packaging claims

Verify the actual launchers:
- `python gui.py --help`;
- a bounded launch/close smoke test for `python gui.py --demo`, if the existing tests can do it safely;
- `python af3builder.py` through a non-interactive EOF smoke test if supported.

Do not leave a GUI event loop hanging. Do not state that a PyInstaller executable exists or works: the previous report says packaging was documented but not built.

### 8. Do not overreact to lint output

The repository has no Ruff configuration and default Ruff reports many legacy findings. Do not run broad autofixes. Check only whether any obvious new correctness issue is present in the changed production code; report style debt separately from runtime correctness.

## Deliverable

Create `docs/AF3_GUI_FINAL_RELEASE_REVIEW_REPORT.md` (only this new report file may be created) with:

1. **Verdict:** ready for functional thesis use / ready with caveats / not ready, with reasoning.
2. Exact commands, results, exit codes and environment used.
3. Independent assessment of the DNA fix and CLI test repairs.
4. Results for the full core suite, GUI suite, CLI e2e suite, architecture tests and output verification.
5. Any defects or weak tests found, classified as confirmed, likely, or unverified.
6. A short prioritized list of remaining actions; do not propose broad rewrites.
7. A clear split between automated evidence and checks that need an actual human/OS interaction.
8. The final `git status --short`, confirming what was and was not changed by this review.

Do not change application code or tests. Stop after the report is complete.
