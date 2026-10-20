# Stage 6 — Output Generation, Preflight Review and Validation UX for the AF3 JSON Builder GUI

## Role and objective

You are implementing **Stage 6** of an existing Python AlphaFold 3 JSON Builder desktop application built with PySide6 / Qt Widgets.

The earlier stages are intended to provide a GUI shell, job creation/opening/settings, entity management, advanced entity configuration, and a unified Variants & Batch workspace. **Do not assume every earlier stage has been completed exactly as planned. Inspect the current repository and the newest implementation reports first.** The user reports that the earlier GUI stages they have tried are working, but each stage still needs verification against the actual working tree.

This stage completes the GUI's **output generation workflow**: preview what the application plans to write, make output conflicts and choices understandable, and execute generation through the existing service layer. It must also improve validation/preflight feedback where needed so users can resolve problems before generating files.

This is an incremental implementation, not a rewrite. Reuse the existing `GenerationService`, `ValidationService`, output planners/policies, deterministic serializer and asset-resolution behavior. The GUI must not build AF3 JSON or manifest content itself.

## 1. Source-of-truth inspection — required before editing

Inspect the actual repository and current test/report baseline. At minimum, examine:

- The current GUI audit report and latest Stage 1–5 implementation reports, if present.
- `IMPLEMENTATION_PLAN.md`, `AUTHORITATIVE_SPEC.md`, `DOMAIN_MAPPING.md`, relevant output/serialization/validation documentation and user-added UX requirements.
- `configbuilder/ui/render/qt/` as it exists now: application startup, `GuiState`, main window/navigation, overview, entity workspace/forms, preview, variants/batch, dialogs, shared components, styling and string registry.
- `configbuilder/ui/services.py` and the current service bundle.
- `configbuilder/app/generation_service.py`: the exact signatures and result types for `show_json`, `plan_save`, `plan`, `plan_base` and `execute`, or their current equivalents.
- The current output-plan, output-execute, naming, manifest, policy and resource-resolution modules under `configbuilder/output/`.
- The current `ValidationService`, validation reports/findings, status model and validation rules.
- JSON serializer/transform modules and tests that define deterministic byte output and output paths.
- The existing save-one-file path implemented in earlier stages and the individual-variant save path, if present.
- Tests in `tests/gui/`, `tests/unit/output/`, `tests/unit/app/`, `tests/unit/validation/`, `tests/serialization/`, `tests/golden/`, relevant end-to-end tests and all architecture tests.
- The current launcher files (`gui.py`, `af3builder.py`) and their tests.

The earlier audit identified APIs with names such as `GenerationService.plan(...)`, `plan_base(...)`, `plan_save(...)`, `execute(...)`, plus output types and policies including overwrite behavior, path/resource policy, conflict lists, warnings and a manifest. These are audit findings, **not permission to assume exact current signatures**. Verify actual definitions and tests before use. Use real service/result types; never guess field names.

## 2. Preserve the working tree and measure baseline

Before edits:

1. Record `git status --short`, current branch and latest commit.
2. Record all modified tracked files and untracked files, including the user's ongoing work.
3. Run the relevant baseline test suites and capture exact failing test node IDs.
4. Do not overwrite, reset, clean, stash, restore or commit user changes.
5. Do not weaken, remove or skip tests just to obtain a green result.
6. Separate pre-existing failures from regressions created by this stage.

Use the current project/environment paths rather than assuming they still match examples. A useful baseline, adjusted only when needed and documented, is:

```powershell
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q
```

If a path or test module does not exist, report the discrepancy and inspect the actual current structure instead of silently substituting an unrelated command.

## 3. Stage scope

Deliver a coherent **Generate & Output** workflow that makes the existing backend planning and execution capabilities accessible and safe for a non-programmer.

### 3.1 Generate the configured base job and selected/all variants

Where the current services support these operations, provide:

- A clear entry point labelled **Generate outputs…** or **Generate all…**.
- An output-root folder picker.
- A scope selector for the base job, selected variants, or all eligible variants, but only where the existing generation service supports that scope.
- The real output layout and resource/asset handling defined by the current output planner.
- Any required overwrite/conflict policy choices exposed by the service, using simple user-facing labels and explanations.
- Any supported path/resource policy, such as copying required assets into the output tree versus referencing external resources, with a description of the practical consequences.
- A full **preflight plan** shown before files are written: planned file paths, directories, asset copies/references, conflicts, warnings, omissions or skipped items, and the number of outputs, wherever those details exist in the real plan/result objects.
- A deliberate confirmation/Generate action after the user has reviewed the plan.
- A post-execution result view showing what was written, skipped or refused and why, based on the service's result objects.

Do not implement an AF3 job runner, remote server connection, scheduler, supercomputer submission, SSH or cluster execution. This stage only prepares and writes output files using the project's existing local generation pipeline.

### 3.2 Preserve the existing Save JSON workflow

- Do not replace or bypass the existing one-file **Save JSON…** workflow.
- Keep single-file saving and generate-all output generation visibly distinct: explain which one saves one JSON file and which creates the planned output directory tree and associated resources/manifest.
- Route all saving and generation through existing planning and execution APIs. Never write JSON, manifests or copied assets directly from widgets.
- Preserve existing validation gates, deterministic serialization, atomic writing, naming, path policies, overwrite decisions and service-provided error messages.
- Preserve the established launcher commands `python gui.py` and `python af3builder.py`.

### 3.3 Preflight and validation UX

Make it easy to understand why generation is or is not possible:

- Show readiness, blocking errors, warnings and informational findings before the generation plan can be committed.
- If a plan is refused, show the service's reason and relevant validation findings; do not display a misleading successful or ready state.
- Link findings to the relevant page, entity or field where the available `FieldPath` / record-key information and current widgets support it. When a precise target cannot be resolved, show a clear fallback explanation rather than doing nothing.
- Avoid duplicate or contradictory summaries across Overview, JSON Preview, Variants & Batch and Generate & Output. Reuse shared validation presenters/components where appropriate.
- When a feature requires a JSON version above the current pin, or another model/service conflict prevents preview/generation, explain the conflict near the relevant field and in preflight. Do not silently upgrade version pins, discard entered data, or weaken validation.
- The service remains the authority for readiness, validation, plan conflicts and write policy; the UI may format/display results but must not recalculate these rules independently.

### 3.4 User-friendly output layout

The output page should make these questions answerable before clicking Generate:

1. Where will my files go?
2. Which base/variant jobs will be generated?
3. Which exact files and assets are planned?
4. Will anything be overwritten, skipped or refused?
5. Which warnings need attention?
6. What will happen when I click Generate?

Use a preview table/tree of the real plan if its data model supports it. Long paths should be readable or inspectable, not truncated beyond usefulness. Provide a copy-path action when appropriate. Do not make users inspect raw internal dataclasses or terminal logs to understand the plan.

## 4. UX and design requirements

Follow the user’s added design directive and make it part of implementation, not an afterthought.

### Overview

- Job-wide settings such as job name, seeds and JSON version should remain directly accessible on Overview, if already implemented by previous stages. If they are not implemented, record the gap and make only a small, well-justified change required for this workflow; do not silently redesign the entire application.
- Keep readiness and the most important findings easy to locate.

### Entity workspace

- Relevant entity configuration (sequence, modifications, MSA, templates, ligand representation, etc., depending on entity type and prior-stage delivery) should remain together in a discoverable workspace. Do not move advanced controls to unrelated dialogs merely to simplify output generation.

### Generate & Output workspace

- Use a clear sequence: **Choose destination and scope → Review plan → Confirm generation → Review results**.
- Disable actions that are genuinely unavailable and explain why; do not leave dead buttons.
- Keep output and destructive overwrite consequences clear. Confirmation must name the destination and the chosen policy/consequence when relevant.
- Use consistent typography, spacing, restrained colours, and existing components. This is not a request for an unrelated whole-app redesign.
- Support normal Windows window resizing and scaling. Avoid fixed geometry that makes paths/tables impossible to use.
- Use clear keyboard focus and accessible button labels; do not rely on colour alone to communicate error/success.

## 5. Implementation architecture and invariants

- Add or extend the existing GUI page/controller/state in the established GUI package; do not create an unnecessary new top-level package or framework.
- Route service calls through the existing `GuiState`/controller seam. Add only small pass-throughs where the services are not currently reachable.
- Keep all application rules in the domain/application/output layers.
- Never assemble AF3 wire dictionaries, serialized JSON, manifest contents or output payloads in Qt code.
- Never allocate/rename/release entity IDs or mutate canonical records directly in widgets.
- Never derive validation readiness independently from the service.
- Never bypass preflight planning and call lower-level file writes directly.
- Never execute a plan different from the one the user actually reviewed. If the service design requires replanning immediately before execution, detect and show a changed plan or new conflict and obtain renewed confirmation.
- Keep plan/execute sequencing consistent with the existing service contract, especially if a plan may become stale when filesystem contents change.
- Respect the service's overwrite policy, path policy, atomicity and failure semantics. Don't assume a multi-file operation is globally atomic unless implementation/tests prove it.
- Do not add PySide6 to the core runtime dependencies.
- Do not add another dependency unless necessary and justified.

## 6. Required implementation sequence

### Stage 6A — Audit the output plan and design the user flow

1. Inspect actual `GenerationService` methods, plan/result classes, file layout, manifest, resources, policies and tests.
2. Map each visible choice to a real supported service argument/value.
3. Sketch the output page flow and identify how existing job/variant selection maps to the planner.
4. Identify unresolved source or UX ambiguities. Do not guess about them.
5. Record the design briefly in the implementation report or a short design note before writing the output UI.

### Stage 6B — Destination, scope and plan preview

1. Add the destination picker and only the scope options supported by the actual service.
2. Add appropriate overwrite and resource/path policy controls.
3. Call the current plan/plan_base/plan-save APIs as needed through the controller seam.
4. Display the resulting output plan, files, conflicts, warnings and any resource-handling details.
5. Ensure cancelling or navigating away before execution writes nothing.

### Stage 6C — Explicit execute and result report

1. After user confirmation, execute through the existing `GenerationService.execute(...)` or verified equivalent.
2. Display result messages and per-file statuses from the returned service result.
3. Handle errors and partial outcomes truthfully; do not show “success” if any files were refused or skipped without explanation.
4. Refresh relevant status, previews and output summary if the existing state model needs it.

### Stage 6D — Validation UX integration

1. Improve generation-blocking feedback and links to relevant fields/pages using actual finding objects.
2. Ensure version-feature incompatibilities and variant validation are explained consistently where service results support this.
3. Keep Overview, entity workspace, variant workspace, JSON Preview and Generate & Output consistent without duplicating validation logic.
4. Do not alter domain validation rules unless the report identifies a genuine defect, the smallest appropriate correction is clear, and it has focused tests. Any substantive core change must be documented.

### Stage 6E — Regression verification

1. Add controller/GUI integration tests for the plan-preview-execute workflow.
2. Test refusal, cancellation, existing conflicts, overwrite/skip policy, invalid destination, write failure, and successful generation using temporary directories and injected/test filesystems where the existing architecture supports that.
3. Verify output JSON and manifests are produced by the existing pipeline and match expected golden/deterministic results.
4. Run focused, GUI, architecture, launcher and full core suites; compare failure IDs with baseline.
5. Produce the report and stop. Do not start Stage 7.

## 7. Testing and acceptance criteria

### Plan creation and preview

- Output root is selected using a native directory/file picker appropriate to the real service.
- Every displayed output path corresponds to the actual generated plan.
- Base job/variant scope maps correctly to the planner.
- The planned JSON, manifest and resource/asset operations match the service plan.
- Conflicts and warnings are visible before writing.
- Invalid plans are refused with a readable explanation.
- Cancelling the plan or confirmation writes nothing and changes no job/variant state.

### Execution

- A valid plan generates the expected directory and files through the existing execution service.
- Manifest and asset handling match existing output tests and policies.
- Fail/overwrite/skip and resource path options behave exactly as their service contracts define.
- File permissions, invalid paths, occupied destinations and other expected failures produce user-facing messages, not uncaught tracebacks.
- Any partial result is described accurately.
- A repeated deterministic output is consistent with the existing serializer/pipeline contract.
- Save JSON… still works as before and is not replaced with a direct file-writing shortcut.

### Validation

- Blocking findings genuinely block generation through the existing service.
- The GUI does not label blocked configurations as ready.
- Finding text/details match the underlying service/presenter.
- Where possible, a finding selects the associated entity/field; unsupported jump targets show an explicit fallback.

### Regressions and maintainability

- Stages 1–5 workflows still work, including `python gui.py`, `python gui.py --demo`, `python af3builder.py`, opening/importing a JSON, job settings, entity changes, advanced settings, variants and batch.
- The GUI never becomes dependent on a hidden current-working-directory assumption; file destination and project paths are handled as the application already defines.
- Architecture tests pass.
- No new core test failures versus the measured baseline.
- Core package still functions without PySide6 installed.

Use real widget/controller tests plus assertions about the actual service state and produced files. Static source-text checks alone are not adequate.

## 8. Manual Windows verification checklist

Include this checklist in the final report for the user to execute:

1. Run `python gui.py`.
2. Open a valid AF3 JSON and review the import preview.
3. Create or open a job with at least one protein and any relevant MSA/template or PTM settings from earlier stages.
4. Open Variants & Batch and create at least two distinct variants, if Stage 5 is present.
5. Open Generate & Output and choose a temporary output directory.
6. Review the planned tree, output paths, asset actions, manifest, warnings and conflicts.
7. Cancel once and confirm nothing was written.
8. Reopen the plan, confirm generation, and inspect the resulting JSON, assets and manifest.
9. Try the available conflict policy against a destination containing a file; verify the described behavior.
10. Attempt an invalid/incomplete configuration and verify the user receives a clear explanation.
11. Confirm `Save JSON…` still saves one valid file as before.
12. Resize the window and verify paths, tables and buttons remain usable.

Do not claim any manual step was completed by the agent if it was not actually performed on a real display.

## 9. Final report

Create `docs/GUI_STAGE6_OUTPUT_GENERATION_IMPLEMENTATION_REPORT.md`, or follow the repository’s current report naming/location convention. Include:

1. Summary of delivered functionality and deferred features.
2. Created/modified file inventory and why each changed.
3. Exact mapping from UI controls to actual service APIs and model/result fields.
4. Explanation of preflight planning, confirmation and execution behavior.
5. Output-tree, manifest and assets behavior, including policies and limitations.
6. Test commands, exact results, and comparison to baseline by failing node ID.
7. Any remaining blockers, limitations and decisions requiring the user.
8. The manual Windows checklist above.
9. A final `git status --short` inventory and confirmation that there were no resets, cleanup, stashes or commits.
10. Clearly distinguish automated verification, visual/manual testing, assumptions avoided and anything not verifiable.

## 10. Completion definition

Stage 6 is complete when a user can inspect a real generation plan, understand the destination and file/resource consequences, explicitly confirm execution, see accurate results, and rely on the existing validation/output pipeline to write files. Save JSON must continue to work, the core must remain independent of PySide6, and no new regressions may be hidden.

Implement **Stage 6 only**. Do not perform the final whole-application redesign or packaging stage yet. Stop after creating the report. If the actual APIs or current implementation differ from this prompt, adapt to the verified repository rather than copying assumptions from earlier reports, and document any required user decision.
