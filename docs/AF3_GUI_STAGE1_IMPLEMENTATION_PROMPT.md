# Implementation Prompt: AF3 Builder GUI — Stage 1 (Review & Preview)

## Objective

Implement the **first useful, read-only milestone** of a PySide6 desktop GUI for the existing AlphaFold 3 JSON builder. The user is a beginner and needs a clear, approachable interface for reviewing an existing AF3 job without interacting with a command-line menu.

This is not a request to build the entire GUI. Do not implement job editing, entity creation/deletion, PTM editing, custom components, bonds, variant authoring, saving, bulk generation, AF3 execution or analysis in this stage.

## Repository context

The repository audit is the `GUI_AUDIT_REPORT.md` document provided alongside this prompt. Read it if it is present in the repository; otherwise use the attached/provided report rather than assuming that report file exists in the project. Inspect the current source before coding. The audited repository has:

- A service layer already responsible for jobs, configuration, variants, validation and generation.
- A frozen/immutable domain model.
- Centralized JSON transformation and serialization.
- A current architecture test that expects exactly ten top-level packages under `configbuilder/` and only `render` and `present` directly under `configbuilder/ui/`.
- A known test baseline of `13 failed, 990 passed, 1 skipped` at the audited working-tree revision. The report attributes the failures to outdated end-to-end input scripts and expectations; verify the current baseline instead of assuming it is unchanged.
- A known defect in the CLI's single-strand DNA choice. It must not be copied into the GUI. This Stage 1 GUI is read-only, so do not attempt a DNA behavior fix as part of this task.

Inspect the current files and tests to verify all names, signatures and result-object fields before using them. The audit is a map, not a substitute for reading code.

## Non-negotiable architecture rules

1. **Reuse the service layer.** The GUI must call the existing public services, especially the import preview/commit pair, `ValidationService` and `GenerationService.show_json`. Do not build a parallel application/domain layer.
2. **Do not construct AF3 JSON yourself.** Never assemble wire dictionaries or serialize JSON in the GUI. Use the existing transformation, validation and serialization services.
3. **Do not allocate or modify entity IDs in the GUI.** IDs, duplex pairing, validation rules and domain semantics stay in their existing authorities.
4. **Keep the command-line interface working.** Do not remove or redesign `MenuApp`.
5. **Preserve architecture boundaries.** Put Qt code inside `configbuilder/ui/render/qt/`. Do not create `configbuilder/gui/`, another top-level `configbuilder` package, or a new direct child of `configbuilder/ui/` without first stopping and explaining why the architecture tests must change.
6. **Keep the core dependency-free.** Add PySide6 as an optional GUI dependency, not to the core runtime dependencies. Use a Python 3.10+ environment for the GUI; do not raise the core's declared Python floor or remove Python 3.9 CI support for this stage.
7. **Avoid unrelated edits.** Do not refactor the services, fix the current CLI DNA bug, repair or delete the known stale end-to-end tests, rewrite documentation unrelated to the GUI, or change AF3 JSON behavior as part of this task. Report any blocker requiring such changes before taking it on.
8. **Do not discard user work.** Inspect `git status` and diffs first. Never reset, clean, stash, commit, or overwrite existing user changes. Preserve untracked and generated files.
9. **No silent error suppression.** Display service failures, import notes, validation findings and preview failures in readable form. Do not show raw tracebacks to the user.

## Stage 1 functionality

### A. Launchable desktop shell

Create a usable PySide6/Qt Widgets application with a `QMainWindow`, proper sizing, a simple visual hierarchy and a clean layout that remains usable when resized. Use ordinary Qt Widgets, not a web stack or QML.

Recommended overall layout:

- Header/toolbar: application name and `Open AF3 JSON…` action.
- Left navigation or compact tabs: `Overview`, `Entities`, `JSON Preview`.
- Main content area.
- Readiness/status area and validation findings section.
- Status bar showing the current source file or demo state.

Keep the UI calm and professional, appropriate for a scientific desktop tool. Prefer clear labels, whitespace, readable tables, monospace text for sequences and JSON, and plain-language errors. Avoid decorative features that do not help complete the workflow.

### B. Open an existing AF3 JSON safely

- Use a standard file picker.
- Call the existing `ProjectService.import_json_preview(path)` API.
- Present the existing import summary and all notes/warnings before committing.
- Provide clear `Import` and `Cancel` actions.
- Only call `ProjectService.import_json_commit(path)` after the user confirms.
- A cancelled or failed import must not replace the currently open in-memory project.
- Opening or previewing a file must not alter the source JSON on disk.
- Do not parse the JSON independently to populate the application state when the service already supplies the domain model and import result.

### C. Overview and entity table

After a successful import, show the data available from the current project model and status services:

- Job name.
- Model seeds.
- Dialect and selected/pinned version, where available.
- Total entity-record count and counts by family.
- Entity table showing true record IDs (including multiplicity where applicable), family, sequence length or representation summary, and useful available metadata.
- Modifications/PTM count where applicable.
- Protein MSA/template state where available; do not invent values for RNA, DNA or ligands.
- For DNA duplexes, make the two-strand relationship understandable without splitting, reordering or modifying the underlying records.

Render the entity table as a view/model over the existing configuration. Sorting the visible table must never reorder the underlying `configuration.records` collection.

### D. Validation readiness and findings

- Use the existing validation/status services (`ValidationService.status()` and `validate_base()` or their verified equivalents).
- Show a clear readiness summary and the full relevant findings list.
- Preserve severity and user-facing messages provided by the existing result objects.
- Where a finding identifies a record/entity, let the user select or highlight the corresponding row if this can be implemented simply.
- Display status/failure results rather than raw exceptions.
- Do not independently reimplement readiness logic or reinterpret validation rules.

### E. Read-only JSON preview

- Use `GenerationService.show_json(...)` and display its returned JSON text in a read-only, monospace editor.
- If the service refuses to produce a preview, display the exact useful reason/result details instead of crashing.
- The preview is the builder's generated/normalized JSON representation, not necessarily a byte-for-byte display of the original imported text formatting. Label it accordingly.
- Do not add a save, overwrite, generate-all or execute button in this stage.
- Do not write any file.

### F. Optional demo mode

If useful for designing/testing the shell, add a non-writing `--demo` mode that creates sample in-memory state through existing services. Do not hand-build AF3 wire dictionaries and do not write sample files to the repository. Demo mode must be clearly labelled as sample data.

## Recommended minimal structure

Keep the module count small; do not implement the full future GUI architecture prematurely. A reasonable starting point is:

```text
configbuilder/ui/render/qt/
    __init__.py
    __main__.py                 # optional: support python -m configbuilder.ui.render.qt
    application.py              # main() and QApplication setup
    state.py                    # lightweight session/controller state
    models.py                   # Qt table model(s) over existing records/findings
    windows/
        __init__.py
        main_window.py
    pages/
        __init__.py
        overview.py
        entities.py
        preview.py
    dialogs/
        __init__.py
        import_preview.py
```

Adapt this if the existing code suggests a smaller structure. Do not create all the pages from the audit's future-state design now. Avoid maintaining a second dirty flag or duplicated project state unless the actual service API requires it. Use the existing project as the state authority.

For GUI-specific labels, keep strings organized in one place. Reuse existing registered user-facing service messages and presentation helpers where appropriate.

## Packaging and Python compatibility

- Add PySide6 to a `[project.optional-dependencies]` GUI extra, not to core `dependencies`.
- Add a convenient GUI launcher only if it can be done without disrupting the existing CLI entry point.
- Keep the core's Python 3.9 syntax restrictions in mind for all new files under `configbuilder/`. The GUI should be run/tested on Python 3.10+.
- Do not assume the current project interpreter or a PySide6 installation; inspect them first.
- Prefer an isolated GUI virtual environment. Do not install into a global Python environment.
- Do not change the entire project's `requires-python` value for this milestone.
- If dependency markers/packaging metadata have an edge case on Python 3.9, document it and choose a solution that preserves core installation on Python 3.9 while making the GUI requirement clear.

## Tests and verification

Before coding:

1. Run `git status --short` and inspect the relevant diffs. Do not modify the user's pre-existing work.
2. Run and record the current baseline using:
   `python -m pytest -o addopts="" -q`
3. Inspect the relevant service result types and existing tests before wiring the UI.

Add GUI-specific tests where practical. Use Qt's offscreen platform so GUI tests do not require a visible desktop. At minimum verify:

- The main window can be created and closed cleanly.
- Opening a valid JSON goes through import preview and requires confirmation before commit.
- Cancelling import or supplying invalid JSON leaves the currently open project unchanged.
- The entity table displays the actual records/IDs from the service model.
- The readiness/findings view reflects service results rather than independently computed values.
- The JSON preview equals the text returned by the existing preview service.
- Reading/importing/previewing does not modify the source file on disk.
- The GUI does not break the existing CLI entry point or architecture tests.

Do not claim the whole suite is green if the documented baseline failures remain. Report existing failures separately from new failures. The GUI-specific tests must pass in an environment with the GUI extra installed; the core test suite must still be runnable without PySide6 installed.

Run at least:

```powershell
python -m pytest -o addopts="" -q
python -m pytest -o addopts="" -q tests/architecture
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -o addopts="" -q tests/gui
```

Adapt the GUI test path if the repository already has a different test convention. If an exact command is not applicable, explain why and run the correct equivalent.

## Acceptance criteria

Stage 1 is complete only when:

1. The application launches using documented steps on the chosen Python 3.10+ GUI environment.
2. A user can open a real AF3 JSON, inspect the import summary and explicitly confirm or cancel.
3. The window displays job information, entity rows, readiness, validation findings and a generated JSON preview through existing services.
4. Nothing in the Stage 1 GUI edits the in-memory job or writes/overwrites files.
5. No AF3 wire serialization, ID allocation, validation or variant logic is duplicated in GUI code.
6. Existing CLI functionality and architecture constraints are preserved.
7. The report clearly separates the old test baseline from any new failures and documents the exact verification commands and results.

## Out of scope for Stage 1

Do not implement any of the following yet:

- New job creation and editing controls.
- Adding, editing or deleting entities.
- Single-stranded DNA behavior or changes to the DNA service.
- PTM editing, custom CCD management, MSA/template editing or covalent-bond editing.
- Variant specification editor, quantity series, batch generation or generated job layouts.
- Save JSON, save project, overwrite flows or any filesystem write operation.
- AF3 server/cluster launch, result analysis or integration with `af3_analysis`.
- PyInstaller packaging, installer branding or elaborate themes.

These will be separate later stages after the read-only integration is reviewed.

## Required deliverables

1. The runnable Stage 1 GUI implementation.
2. GUI-specific tests.
3. A short `GUI_STAGE1_IMPLEMENTATION_REPORT.md` containing:
   - Files created/changed and the purpose of each.
   - Exact launch and dependency-install commands.
   - How the import-preview/commit path, status/findings and JSON preview are wired to existing services.
   - Baseline test result versus final test result, distinguishing old failures from new ones.
   - Any known limitations or decisions still needed before Stage 2.
4. A concise final summary. Do not proceed to editing/creation features until the user has reviewed this milestone.
