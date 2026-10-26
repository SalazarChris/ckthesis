# Agent Task: Add Simple Python Launchers, Test Them, Then Continue the AF3 GUI in Gated Stages

## Goal

Make the existing AF3 JSON Builder easier to launch, without changing or replacing its existing CLI or GUI architecture. Add two small Python launchers in the repository root so I can run:

```powershell
python af3builder.py
python gui.py
```

After you implement and test these launchers, **STOP and ask me to launch the GUI manually**. Do not begin the next GUI feature stage until I explicitly confirm that the GUI launches successfully. After that confirmation, continue the GUI implementation from the existing Stage 1 Review & Preview window in the stages defined below.

The repository being discussed in the reports is `C:\Users\Chris\Desktop\THESISSP`, but always discover the actual repository root from the current workspace rather than hard-coding this path in application code.

---

# Part A — Inspect the current state before editing

1. Read the current `GUI_AUDIT_REPORT.md` and `GUI_STAGE1_IMPLEMENTATION_REPORT.md` if present, as well as `pyproject.toml`, `configbuilder/app/cli.py`, `configbuilder/ui/render/qt/application.py`, `configbuilder/ui/render/qt/__main__.py`, the Stage 1 GUI tests, and the relevant test configuration.
2. Inspect `git status --short` and the existing diffs **before editing**. The working tree already contains modified tracked files and untracked files belonging to prior work. Preserve every pre-existing change.
3. Verify how the current CLI and GUI are actually launched. Treat the reports as useful evidence, not as a substitute for inspecting the current code.
4. Do not reset, clean, checkout, stash, revert, or commit anything. Do not overwrite unrelated changes. Do not delete, rename, or reformat unrelated files.
5. Record the baseline test results before making changes. The previous audit reported 13 pre-existing end-to-end failures, 990 passes and 1 skip in the core run; the initial GUI report also recorded 35 GUI tests passing and 40 architecture tests passing. Re-measure the current workspace because it may have changed. Compare failing test IDs, not just totals.

# Part B — Add the two root-level launchers

Create these files in the repository root, next to `pyproject.toml`:

- `af3builder.py` — launches the existing CLI.
- `gui.py` — launches the existing PySide6 GUI using the repository's `.venv-gui` environment.

## `af3builder.py` requirements

- Delegate to the existing entry point, `configbuilder.app.cli.main`; do not duplicate the CLI menu or builder logic.
- Preserve the existing CLI behavior and exit code.
- Importing this module from a test must not launch the interactive CLI. Use a normal `if __name__ == "__main__":` guard.
- Do not require PySide6 or the GUI virtual environment.
- Do not introduce new runtime dependencies.
- `python af3builder.py` from the repository root must start the same CLI as the current supported command.

## `gui.py` requirements

- Launch the existing module `configbuilder.ui.render.qt` using `.venv-gui\Scripts\python.exe` on Windows.
- Forward all arguments unchanged. At minimum, these must work:

  ```powershell
  python gui.py
  python gui.py --demo
  python gui.py "C:\path\to\job with spaces.json"
  python gui.py --help
  ```

- Use `pathlib.Path(__file__).resolve().parent` to locate the repository root and `.venv-gui`; do not hard-code the user's absolute path.
- Set the child process working directory to the repository root, so the application starts consistently even if `gui.py` is invoked by its full path from another directory.
- Use `subprocess` with an argument list, not `shell=True`, string concatenation or manual quoting. A JSON path containing spaces must remain a single argument.
- Return/propagate the GUI process exit code.
- If `.venv-gui\Scripts\python.exe` does not exist, print clear, copyable setup commands and exit non-zero. The suggested commands should create the environment and install the optional GUI extra, for example:

  ```powershell
  py -3.11 -m venv .venv-gui
  .\.venv-gui\Scripts\python.exe -m pip install -e ".[gui]"
  ```

  Check the existing packaging metadata before finalizing the exact install command. Do not run the installation automatically from the launcher.
- If the environment exists but cannot start the GUI because PySide6 or another dependency is missing, surface a useful diagnostic and the failing exit code; do not silently fall back to another interpreter or install anything automatically.
- Do not edit the existing GUI application entry point just to make the wrapper work, unless inspection demonstrates a real defect. If a code change is necessary, keep it minimal and add a clear rationale.
- Keep `python -m configbuilder.ui.render.qt`, the existing `af3-json-builder` entry point, and the `configbuilder` CLI entry point working.
- Do not add a `.bat` file, shortcut, shell alias, or packaging framework unless the existing project shows it is required.

# Part C — Add and update tests for the launchers

Add focused automated tests in an appropriate existing test location (for example `tests/unit/test_launchers.py` or a suitable dedicated test module). Follow the repository's test naming and architecture conventions.

At minimum, test:

1. Importing `af3builder.py` does not start the CLI.
2. Running the CLI launcher's `main()` delegates once to `configbuilder.app.cli.main` and propagates its exit result correctly.
3. `gui.py` constructs the expected command using `.venv-gui\Scripts\python.exe -m configbuilder.ui.render.qt`.
4. GUI arguments are passed as individual arguments unchanged, including a JSON path with spaces and `--demo`.
5. The child process uses the repository root as its working directory.
6. The GUI launcher's exit code is propagated.
7. A missing GUI environment produces an actionable message and a non-zero result without trying to launch a child process.
8. The launchers can be tested without installing PySide6 into the core environment and without opening a real GUI window.

Use dependency injection or small testable helper functions where helpful, but avoid overengineering the launchers. Mock subprocess calls in unit tests; do not use a fake test that claims the real desktop GUI has opened.

Update documentation (prefer the existing README or relevant user-facing usage document if one exists; otherwise create a short `RUNNING_THE_APPLICATION.md`) with the two simple commands and the optional demo command. Keep existing documentation consistent and avoid rewriting unrelated material.

# Part D — Verify the launcher stage and report it

Run and report:

- The launcher unit tests.
- `python -m pytest -o addopts="" -q tests/architecture`.
- The Stage 1 GUI tests using the isolated GUI environment and `QT_QPA_PLATFORM=offscreen`.
- The core test suite using the existing core interpreter, without requiring PySide6.
- A comparison of current core failing test IDs against the pre-edit baseline.
- Syntax/compile checks for both launchers.
- A safe, non-interactive launcher check where practical (for instance `python gui.py --help` using the GUI environment); do not claim a full interactive GUI launch was verified by a mocked subprocess or offscreen-only test.

Do not automatically fix or delete unrelated pre-existing failing end-to-end tests. If any fail, distinguish the baseline failures from regressions and identify each test ID.

Create `GUI_LAUNCHERS_IMPLEMENTATION_REPORT.md` containing:

- Files created/modified and why.
- The exact commands to run the CLI, GUI and demo.
- Test commands and exact results.
- Baseline-vs-current failing test IDs.
- Any limitations or environment-specific issues.
- A clear manual verification checklist for me.

## Mandatory pause gate — do not skip

After Part D is complete:

1. Summarize the changes and show me the exact commands to run.
2. Ask me to run `python gui.py` and, optionally, `python gui.py --demo` from the project root.
3. **Stop work at this point. Do not implement job editing, job creation, saving or any other next-stage GUI feature until I explicitly confirm that the GUI opens successfully.**
4. Do not say that the GUI has been successfully launched by me; only I can confirm this manual check.

---

# Part E — Continue only after I confirm the GUI opens successfully

Once I explicitly confirm that the launcher works, continue implementation using the existing Stage 1 GUI. Do not rebuild the GUI from scratch and do not skip ahead to variants.

Before changing code again, re-check `git status --short`, review the current diff, read the launcher implementation report and re-run the relevant tests. Preserve all current work.

## Stage 2 — Job lifecycle: New Job, basic settings and Save JSON

Implement this stage only after the manual launch confirmation.

### Scope

1. Add a **New Job** action that creates a new job through the existing project/service layer. If the current job has unsaved changes, ask before discarding it.
2. Add a job-settings page or panel for the job name, model seeds and JSON version, using the existing `ConfigurationService` and model rules. Display defaults clearly; do not silently replace them. In particular, preserve the current code's intentional defaults unless the user changes them.
3. Add a **Save JSON…** action using the existing `GenerationService.plan_save(...)` and `GenerationService.execute(...)` workflow. The GUI must never build JSON dictionaries, serialize JSON independently, write JSON directly, allocate IDs or reimplement validation.
4. Show the existing validation/status information when saving is blocked, including the service's failure reason and relevant findings. Do not show a success message until the service reports success.
5. Use a native save dialog and an explicit overwrite confirmation where required by the existing output policies.
6. After a successful save, update the current path and saved/dirty state without changing JSON semantics.
7. Preserve the existing Stage 1 Open JSON preview-and-confirm workflow, entity table, findings, readiness panel and JSON preview.
8. Keep the GUI optional: the core package must remain installable and testable without PySide6.

### Safety and architecture constraints

- Re-read actual service signatures and result types before calling them; do not assume the audit's examples still match the current code.
- Keep Qt-specific implementation under the currently allowed GUI/render package unless architecture tests and the project plan justify a reviewed architecture change.
- Use the services and presentation helpers already available.
- Do not introduce a second source of truth for job state. If a session/controller is needed, make it a thin adapter over the existing service objects.
- Add a GUI change-notification/refresh seam only if needed for predictable view updates, and keep it small.
- Preserve record order in the underlying configuration. View sorting must not mutate job order.
- Handle cancel, invalid paths, permission errors, overwrite refusal, invalid configuration and window close without tracebacks or silent data loss.
- Do not change the DNA single-strand behaviour as part of this stage. The audit identified a real existing bug; do not port or hide it. Record it as a separate issue unless a narrowly scoped fix is essential to the feature being implemented, in which case add dedicated tests and explain the change.
- Do not implement entity addition/editing/deletion or variants in Stage 2. Those are later stages.

### Stage 2 tests and acceptance criteria

Add GUI tests (using the repository's existing PySide/offscreen approach) covering:

- New Job creates a job through the correct service.
- New Job/Open/Close prompts before discarding unsaved modifications, and Cancel preserves the current job.
- Settings update the underlying configuration through service calls.
- Save is refused for an incomplete job; no file is created and service findings are visible.
- A valid job saves through `plan_save`/`execute` and the output bytes equal the service/serializer's expected bytes.
- A GUI-saved JSON can be re-opened through the existing import preview/commit flow.
- Overwrite confirmation/cancellation behaves correctly.
- Save cancellation and filesystem errors are safe and understandable.
- Existing Stage 1 tests, architecture tests and launcher tests still pass.

Compare core failures against the baseline and report exact test IDs. Do not remove stale tests simply to get a green count; any repair of an outdated test must be justified against current service behaviour and done separately from GUI-specific behaviour.

Create `GUI_STAGE2_IMPLEMENTATION_REPORT.md` with changed files, architecture notes, tests, results, known issues and manual test steps. When Stage 2 is complete, stop and present the report for review before beginning Stage 3.

---

# Planned later stages — do not implement yet

After Stage 2 has been reviewed, continue one stage at a time when instructed:

- **Stage 3 — Entity management:** add and view protein, RNA, DNA and ligand entities; edit and delete entities; correctly represent DNA duplex partners and multi-copy ligands; preserve service validation and ID authority. The DNA single-strand defect must not be copied into the GUI.
- **Stage 4 — Advanced entity settings:** PTMs, custom CCD components, MSA, templates and covalent bonds, using existing service operations and field-level validation.
- **Stage 5 — Variants and batch generation:** use the existing spec-based variant services and batch preview/commit; validate each variant and protect the immutable base job.
- **Stage 6 — Generation and polish:** validated JSON preview, bulk output planning, conflicts/warnings, accessible validation feedback and jump-to-field interactions.
- **Stage 7 — Final testing and packaging:** real Windows manual testing, installation instructions, optional packaging decision, full regression review, and thesis documentation updates.

Never attempt all later stages in one unreviewed change. Complete the current stage, run tests, create its report, and stop for review.

# Final operating rules

- Think before coding. Inspect current source and tests first.
- Make surgical, reviewable changes.
- Do not overwrite or discard the user's pre-existing working-tree changes.
- Do not install packages automatically or alter the core environment.
- Do not claim tests ran unless they actually ran; include command output summaries.
- Do not claim a manual GUI launch succeeded until the user confirms it.
- Keep verified existing functionality distinct from new functionality and planned work.
