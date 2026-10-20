# Stage 7 — Final UX, Visual Polish, Windows Launch/Packaging and Release Verification for the AF3 JSON Builder GUI

## Role and objective

You are implementing **Stage 7**, the final integration and quality stage for an existing Python AlphaFold 3 JSON Builder desktop application using PySide6 / Qt Widgets.

Earlier stages are intended to cover the GUI shell, job lifecycle/settings, entity management, advanced settings, variants/batch, and output generation. **Inspect the actual repository and latest implementation reports; do not assume any stage is complete just because its prompt exists.** The user has already requested a friendly, aesthetically pleasing interface. Their key interaction requirements are:

- The Overview should be a useful control centre, with job-wide settings such as name, model seeds and JSON version directly visible/editable instead of buried behind another window.
- Relevant entity settings should be accessible in a single, discoverable entity workspace. For example, users should be able to adjust MSA where they are editing the protein rather than searching through unrelated navigation.
- Features should be easy for non-programmers to find, with plain labels, visible actions and understandable feedback.
- The GUI must remain trustworthy: biological rules, identifiers, validation, variant operations, serialization and output generation remain in the existing application/service layers.

This stage is **not** a licence to rewrite the application or invent new biological features. First identify remaining UX gaps, then make a focused, consistent whole-app refinement, add only essential usability features, verify launchers and optionally document/package the app for Windows if the repository supports a safe path.

## 1. Source-of-truth audit before edits

Read the current repository, current GUI design and all available implementation reports. At minimum inspect:

- `GUI_AUDIT_REPORT.md` and the latest reports for Stages 1–6, if present.
- `IMPLEMENTATION_PLAN.md`, `AUTHORITATIVE_SPEC.md`, `DOMAIN_MAPPING.md`, README/user documentation and the design requirements added by the user.
- Every current GUI page/dialog, including Overview, job settings, entity workspace/forms, PTM/modification editing, custom components, MSA/templates, covalent bonds, Variants & Batch, JSON Preview and Generate & Output.
- The current `GuiState`, service/controller seam, main-window navigation, Qt model/view code, shared components, strings registry, styles and error-reporting patterns.
- The actual launcher files `gui.py` and `af3builder.py` and their tests.
- `pyproject.toml`, package entry points, dependency extras, `.gitignore`, README launch/setup instructions and any existing packaging/build configuration.
- Architecture rules/tests, unit tests, GUI tests, golden/contract tests, and the full-suite baseline.

Build a short **UX audit table** before editing, with columns: issue, evidence in current GUI, severity, proposed adjustment, affected files, acceptance check. Base every finding on the current implementation or user requirements; do not invent problems just to justify changes.

## 2. Preserve the working tree and measure baseline

Before any change:

1. Record `git status --short`, branch and latest commit.
2. Inventory pre-existing modified and untracked files. Treat all of them as user work.
3. Run current tests and record exact results/failing node IDs.
4. Do not reset, clean, stash, restore, overwrite, rebase, amend or commit.
5. Do not repair unrelated core/CLI defects or delete/weaken tests just to report a green suite.
6. If previous reports identify known failures, re-measure them now; historical results are not assumed to be current.

Use the actual current environment paths. A common verification sequence is:

```powershell
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q
```

Document any missing environment/dependency and do not silently switch to a different interpreter. The core environment must continue to work without PySide6 if that is still the project's declared dependency policy.

## 3. Stage scope

Deliver a final cohesive and usable desktop application, focusing on user experience, consistency, robust launch and truthful release instructions.

### 3.1 Whole-application UX and visual review

Review every top-level page and the most common dialogs. Improve the interface where evidence shows a problem:

- Consistent hierarchy for window title, page title, section headings, field labels, helper text and status messages.
- Consistent spacing, alignment, margins, form widths, row heights, typography, icon scale and button placement.
- Restrained, coherent colour usage. Reserve warning/error/success treatments for meaningful states; do not use colour as the only signal.
- Consistent labels and verbs for actions (for example Add, Apply changes, Cancel, Delete, Preview, Generate).
- Clear empty states, loading/busy states where relevant, no-selection states, success feedback and actionable refusal/error feedback.
- Consistent keyboard focus order, tab navigation, default/cancel buttons, shortcuts where useful, and confirmation dialogs for destructive actions.
- Sensible window resizing and splitter behavior. Long file paths, table content, and text previews must remain inspectable.
- Native Windows interactions for file/folder selection and expected dialogs.
- Avoid unhelpful fixed-size windows, large dead areas, overcrowded forms, tiny text, excessive decoration, gradients/animations that reduce clarity, and unnecessary modal pop-ups.

Do not add a new styling framework. Prefer standard Qt Widgets and a small, central style/helper layer (or existing styling mechanism) to keep visuals consistent.

### 3.2 Overview — direct job-wide editing

Verify and complete, if necessary, the user's requirement that Overview is a useful operational page rather than a passive report:

- The job name, model seeds and JSON version should be visible and directly editable on Overview through inline controls or a clearly embedded settings section.
- Keep current values and defaults explicit. Do not hide the one-seed default, automatically substitute ten seeds or silently change version pins.
- Explain version compatibility with relevant features using current service/validation information. Do not duplicate feature-version rules in the widgets.
- Keep readiness and priority findings close to the job settings, with links to the relevant section where supported.
- Preserve the distinction between in-memory edits and saving the JSON file. Saving remains an explicit action using the existing service pipeline.
- If these controls already exist elsewhere, avoid duplicate competing sources of state. Reuse a single authoritative state/service path and choose a layout that reduces navigation.

### 3.3 Entity workspace — discoverable entity-specific settings

Verify and complete, if necessary, the user's requirement that relevant settings live with the selected entity:

- A user selecting a protein should be able to find sequence/description, PTMs, MSA mode/source and templates in one coherent workspace.
- RNA should show only settings supported by the existing domain/service (such as its valid MSA options and PTMs, where applicable).
- DNA should explain the duplex relationship and expose only settings supported by the model/service. Do not invent a single-strand control unless the service has a correctly implemented and tested operation for it.
- Ligands should expose supported CCD/SMILES representation and copy-count behavior. If multiplicity cannot be edited safely in the service, explain the limitation rather than mutate IDs directly.
- Cross-entity settings such as root-level custom CCD definitions and bonds may remain in a dedicated, clearly labelled shared workspace if placing them in one entity panel would be misleading.
- Avoid forcing users to select an entity on one page, navigate elsewhere to make its common changes, and then return to check the outcome.
- Show relevant errors/warnings inline near the field and keep values available for correction after a refused operation.

Do not force every possible control into a single giant unstructured form. Use grouped sections, expandable panels, inner tabs or a split editor/list layout where it improves clarity. The guiding rule is **one discoverable editing workspace for the selected entity**, not “every field on screen at once.”

### 3.4 Variants & Batch and Generate & Output consistency

- Verify that the variant/spec workflow, quantity series, batch-from-file, validation, single-variant saving and full output generation fit the same visual language and use predictable interaction patterns.
- Keep the base job clearly distinguished from variants.
- Ensure plan → review → confirm → execute → results remains clear in Generate & Output.
- Avoid presenting multiple buttons with ambiguous overlapping meanings such as Save, Generate, Generate all and Export unless their differences are explained.
- Make overwrites, skipped items, output destinations and validation refusals understandable before the user commits.

### 3.5 Error handling and state consistency

- Review whether all refused service operations show plain-language messages and preserve the user's entered values where appropriate.
- Check unsaved-change prompts on New/Open/Close and make sure cancel leaves the current job untouched.
- Check that successful edits refresh dependent tables, details, readiness/findings, JSON preview and output/variant summaries as appropriate.
- Ensure the title/dirty indicator reflects actual changes and is not cleared by a failed or cancelled operation.
- Do not use generic “success” notices for operations that were skipped, partially refused or left blocking findings; reflect the actual service result.
- The GUI must not swallow exceptions silently. Catch expected user-facing/service/file errors, display useful messages, and retain diagnostic detail for testing/logging where the existing architecture supports it.

## 4. Windows launchers, setup and packaging

### 4.1 Preserve simple launch commands

The user expects these project-root commands to remain supported:

```powershell
python gui.py
python gui.py --demo
python af3builder.py
```

Also preserve any documented GUI file-path argument and `--help` behavior if currently supported. Verify that:

- `gui.py` reliably launches the app through the intended dedicated GUI environment or provides accurate setup guidance when it is missing.
- `af3builder.py` launches the existing CLI without changing its semantics.
- Argument forwarding is correct; unknown or malformed arguments result in a useful error/usage message rather than an unhelpful traceback.
- Paths containing spaces work.
- Launching from a working directory other than the repo root behaves predictably; either resolve paths relative to the launcher/project as intended or report the genuine limitation clearly.
- No launcher silently installs dependencies, modifies files or invokes destructive repository commands.
- Both launchers continue to be tested.

Inspect actual launcher code before changing it; do not assume previous versions of the files are still present.

### 4.2 Install instructions and optional package build

- Ensure the README or a dedicated setup guide explains the supported Python version(s), creation of the GUI virtual environment, dependency installation, normal GUI launch, demo launch, CLI launch, running tests and known environment constraints.
- Be accurate about dependency compatibility. Verify current `pyproject.toml` and actual dependency metadata before making claims about which Python versions can install a GUI extra.
- Keep PySide6 optional for the core/CLI if that is the declared architecture.
- If the repository already has a packaging approach or the app clearly needs a shareable Windows executable, inspect the available approach and propose the smallest maintainable path (for example, a documented optional PyInstaller recipe). Implement packaging only if it can be verified in the available environment without changing the core installation contract.
- Do not claim that a portable `.exe` was successfully built or smoke-tested unless it was actually built and run.
- Do not introduce auto-update, telemetry, remote services or extra frameworks.

If an executable bundle is not required or cannot be validated here, document source launch as the supported method and provide a complete optional packaging plan rather than adding fragile untested build machinery.

## 5. Accessibility and usability validation

Use automated tests plus a manual checklist. The automated suite must cover as much as possible of the interaction behavior; the coding agent must be honest about tests that require a real display.

Check at minimum:

- Window can be resized and maximized; core actions remain visible and accessible.
- Tables/form layouts do not depend on specific column widths or a single screen resolution.
- Field labels are associated with controls where supported, keyboard focus is visible and logical, and modal defaults are safe.
- Enter/Escape behavior makes sense for forms and confirmations; Delete never defaults to destructive confirmation.
- Errors are not conveyed by colour alone and include useful text.
- Long sequences, long file paths, multi-component CCD strings and JSON previews can be inspected without corrupting content.
- The interface remains understandable if there are no entities, no variants, no findings, many findings, a large variant set or a long output plan.
- No required feature is accessible only through an unexplained icon or right-click menu.
- Common tasks can be completed with minimal navigation: create/open job; adjust job settings; add/edit an entity and its MSA/template/PTM settings; create a variant; preview/validate; generate output; save/reopen JSON.

Do not state that you performed manual mouse/visual checks unless you actually displayed the GUI in a real interactive Windows session. If using offscreen Qt tests only, identify that limitation clearly.

## 6. Required implementation sequence

### Stage 7A — UX audit and stabilization plan

1. Inspect all current screens and reports.
2. Produce the UX audit table specified in Section 1.
3. Verify which earlier user requirements are satisfied and which are not.
4. Rank proposed fixes by user impact and regression risk.
5. Identify any underlying service gaps that cannot be solved in the view layer. Do not conceal them by making a control appear to work.

### Stage 7B — Focused whole-app refinement

1. Create or refine shared design tokens/styles and reusable components only where they reduce duplication.
2. Refine Overview for direct job-wide settings and readiness.
3. Refine the entity editing workspace so common relevant settings are discoverable in-context.
4. Refine variants/batch, preview, generation, dialogs and feedback for consistency.
5. Correct interaction/resize/focus issues confirmed by source review or tests.
6. Preserve application service boundaries and keep the domain behavior unchanged unless a separately justified, tested bug fix is essential.

### Stage 7C — Launchers and documentation

1. Verify the two launcher files and their automated tests.
2. Update setup instructions to match actual dependencies and environment handling.
3. Evaluate optional Windows packaging, implement only if appropriate and testable, otherwise document a precise optional path.
4. Confirm project-root launch commands continue to work.

### Stage 7D — Regression and usability verification

1. Add/adjust focused GUI tests for any new interaction or shared component.
2. Run the GUI suite in the GUI environment and architecture/launcher/string-registry suites.
3. Run the full core suite in its supported environment.
4. Compare failures by exact node ID with the measured baseline; investigate any newly introduced failures.
5. Run compile/lint checks using the repository's own configured tools and scope.
6. Run command-line smoke tests for GUI launcher (`--help`, `--demo` where practical) and CLI launcher.
7. Create a manual Windows visual/usability checklist and mark each item as **not run**, **automated only**, or **manually verified** truthfully.

### Stage 7E — Final documentation and handoff

1. Update the app README/setup guide with actual behavior and launch commands.
2. Update the thesis implementation documentation only where the repository already includes such documents and actual implemented features warrant a factual change; do not overstate completeness.
3. Provide final known limitations and deferred ideas.
4. Produce the final report and stop. Do not begin new feature development after the report.

## 7. Testing and acceptance criteria

### User interaction and layout

- Overview exposes job name, seeds and version through the authoritative existing service path.
- Relevant per-entity settings can be found and edited in the selected entity workspace without unexplained navigation; supported controls match the domain/service contract.
- PTM, MSA/template, custom CCD, bonds, variants/batch and output generation features remain functional if implemented in earlier stages.
- Shared labels/styles and interaction patterns are consistent across pages and dialogs.
- Window resizing, empty states, long text/path handling and keyboard focus behavior have meaningful tests where Qt supports them.
- Destructive operations require an explicit safe confirmation; Cancel never mutates state.
- Save/open, import preview/commit, unsaved-state handling and generation plan/execute retain their existing semantics.

### Application integrity

- All operations continue through existing services/controller pass-throughs.
- Qt code does not assemble wire JSON, allocate IDs, recalculate validation rules, edit immutable records directly or bypass output planners.
- Existing byte-deterministic output and golden/contract tests remain valid.
- The core package remains importable/testable without PySide6 according to the current dependency contract.
- `python gui.py`, `python gui.py --demo` and `python af3builder.py` work from the documented project location. `--help` remains accurate where supported.
- No new core test failures compared to baseline.
- No user work is lost or silently overwritten.

### Release readiness

- Documentation accurately specifies Python and dependency requirements, environment setup, launch commands, and test commands.
- Optional package/executable claims are supported by actual build and launch verification or clearly labelled as unverified instructions.
- Final test report identifies existing failures, new failures and skips separately.
- The app's limitations are transparent, including any unavailable service operations, packaging issues and any manual UI checks not completed.

## 8. Expected manual Windows checklist

Include the following checklist in the final report so the user can perform the real-display review:

1. Launch `python gui.py` and `python gui.py --demo`.
2. Launch `python af3builder.py` and confirm the CLI still opens.
3. Open an existing AF3 JSON, inspect the import summary and cancel once; verify that cancellation leaves the current job unchanged.
4. Create/open a job and edit the name, model seeds and JSON version directly from Overview.
5. Add a protein; find sequence, PTM, MSA and template controls within the entity workspace, where implemented.
6. Change an MSA mode/source, apply it and verify the view reflects the service result.
7. Add DNA, inspect its partner relationship, cancel deletion and then confirm deletion.
8. Add a ligand with multiple CCD codes/copies and verify identifiers are displayed correctly.
9. Create and validate a variant; preview its edits; verify the base job remains unchanged.
10. Preview the output plan, cancel once, then generate into a temporary directory.
11. Reopen a generated JSON and compare its content/behavior with the preview.
12. Trigger an invalid operation and confirm that the error is actionable, the dialog retains correction values where appropriate, and no partial state change occurs.
13. Resize/maximize the application and test keyboard navigation, field focus, long paths, long sequences and JSON preview readability.
14. Check that no important feature can only be found through an unexplained icon or hidden context menu.

Do not mark these items as passed unless the person or environment completing the report actually performed them.

## 9. Final report and deliverables

Create `docs/GUI_STAGE7_FINAL_UX_AND_RELEASE_REPORT.md` or the current established report location. Include:

1. A short UX audit table of observed issue, severity, action taken, and verification.
2. All created/modified files and the rationale for each.
3. Which user-requested layout changes are now implemented (Overview job settings; entity settings in-context; unified variants/batch; explicit generate/preview workflow).
4. Design choices and shared UI components/styles introduced.
5. Launcher behavior and exact supported commands.
6. Setup/documentation changes and verified Python/dependency requirements.
7. Packaging strategy and what was actually built and run versus only documented.
8. Test commands, exact results, failure IDs and comparison with baseline.
9. Exact known limitations, unimplemented service features and decisions still needed.
10. Manual Windows usability checklist with status clearly marked.
11. Final `git status --short` and confirmation that no reset, clean, stash, restore or commit was performed.
12. A concise recommendation for the user's final manual acceptance pass.

## 10. Completion definition

Stage 7 is complete when the existing feature set presents a consistent, polished and discoverable GUI; job-wide settings are directly accessible from Overview; supported settings for a selected entity are easy to find in its editing workspace; the two simple Python launchers remain reliable; documentation matches reality; automated tests show no new regressions; and remaining visual/manual verification is honestly identified.

Implement **Stage 7 only**. Do not add new biological or analysis features, do not redesign the domain model, and do not continue beyond the final report. If an issue cannot be solved safely in the UI layer, document the underlying service gap and stop rather than inventing behavior.
