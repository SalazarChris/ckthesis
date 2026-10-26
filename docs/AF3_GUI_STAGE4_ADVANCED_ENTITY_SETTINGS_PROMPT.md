# Stage 4 — Advanced Entity Settings, PTMs, Custom Components, Alignments, Templates and Bonds

## Role

You are implementing Stage 4 of an existing Python AlphaFold 3 JSON Builder desktop GUI. Work directly in the current repository and inspect the actual current code before changing anything. The user has completed Stages 1–3 and reports that the GUI launches and the current features work properly.

This is an incremental implementation task, **not a rewrite**. Preserve all currently working features, the CLI, the launcher scripts, the architecture boundaries, and the AF3 JSON contract.

## 1. Repository context and known starting point

The application is a Python package named `configbuilder`. The existing GUI is PySide6/Qt Widgets under:

- `configbuilder/ui/render/qt/`
- Existing GUI tests under `tests/gui/`
- Shared presentation strings under `configbuilder/ui/present/strings.py`

The GUI should continue to use the existing composition root and service bundle rather than constructing services independently in widgets. Existing services include `ConfigurationService`, `ValidationService`, `GenerationService`, `ProjectService`, and `VariantService`.

The Stage 3 implementation report says the following functionality is working and must be preserved:

- New/open/save job workflows from the earlier stages.
- Read-only JSON preview through `GenerationService.show_json()`.
- Validation/readiness and findings through existing services.
- Add, inspect, edit and delete proteins, RNA, DNA duplexes and ligands.
- DNA pairing and edits/deletes delegated to the current service/model; no DNA complement logic in GUI code.
- Ligand CCD-code XOR SMILES representation, creation-time copy count, and identifiers allocated by the identity service.
- Launcher scripts `gui.py` and `af3builder.py`.
- Existing serialization, validation, identifiers and model semantics owned by the core.

The prior Stage 3 report recorded:

- GUI suite: 83 passing tests in the PySide6 environment.
- Architecture suite: 40 passing tests.
- Unit launcher tests: 19 passing tests.
- Full core suite: 13 pre-existing end-to-end failures, 1009 passed, and 8 skipped at that point.
- The 13 known failure IDs were stale CLI/end-to-end scripts that predated the recent CLI menu changes. Do not change expected CLI behaviour or edit those tests just to make Stage 4 pass.

These figures are a **historical reported baseline, not a substitute for measuring the repository now**. Re-run the relevant tests before editing and record the actual baseline and working-tree state.

## 2. Stage 4 goal and boundaries

Implement the advanced settings that are already supported by the application services/model:

1. Surface model/version-feature compatibility conflicts in validation/readiness, so the GUI does not report a configuration as ready when JSON preview/save is blocked by a feature requiring a higher format version.
2. Support add/edit/remove of PTMs/modifications on supported polymer entities.
3. Support per-entity MSA/alignment configuration for protein and RNA, using existing supported modes and the current automatic default.
4. Support protein template/reference configuration, including file pickers where applicable.
5. Support root-level custom CCD definition via exactly one of inline definition or external path, with a clear/none option.
6. Support adding and removing covalent linkages through existing configuration-service methods.
7. Improve the reliability of editing ligand representation and description if the current two-call flow can partially apply one change when the other is refused. Fix this at the service/model boundary, not by directly mutating model records in the GUI.

The following are **out of scope** for this stage:

- Variant/spec editing, quantity series, batch-from-file, or bulk generation.
- AF3 cluster submission, remote execution or analysis-pipeline integration.
- A standalone ion entity family; ions remain ligand CCD codes.
- Direct construction or modification of JSON dictionaries/bytes in the GUI.
- Reworking the whole application architecture or replacing the CLI.
- Changing ligand multiplicity after creation unless an existing supported service operation already provides this capability and the repository contract/test suite clearly supports it. Do not directly rewrite identifiers to make that possible.

## 3. Mandatory safeguards

### Preserve the working tree

Before changes:

1. Run `git status --short`, `git branch --show-current`, and `git log -1 --oneline`.
2. Record the pre-existing modified and untracked files in your report.
3. Do **not** run `git reset`, `git clean`, `git checkout --`, `git restore`, `git stash`, or any command that discards or hides existing work.
4. Do not commit, rebase, or amend commits.
5. Do not overwrite the user's existing edits in `pyproject.toml`, `strings.py`, tests, docs, launchers, or any other file. Make narrow changes and review the final diff carefully.

### Re-read the actual contracts

Before implementing each feature, inspect the exact service signatures, model classes, result types, validation rules, relevant mapping/spec documentation, existing CLI flow and tests. Do not infer the interface from this prompt alone. The repository is the source of truth for API names and enums.

### Maintain layer ownership

- GUI widgets collect user input and render results only.
- All changes go through the existing application services, adding a service method only when a coherent operation is missing.
- The GUI must not allocate IDs, rename IDs, invent DNA partners, assemble AF3 wire dictionaries, serialize JSON itself, duplicate validation rules, or decide readiness independently.
- Keep JSON field mapping and byte encoding in the existing transformation/serialization pipeline.
- Show service-provided refusal/error messages in the existing GUI style; do not leak tracebacks to ordinary users.
- Keep PySide6 optional. Do not add it to core runtime dependencies.
- Respect the architecture tests and the project's supported Python syntax.
- Add fixed user-facing wording to the existing string registry, consistent with current tests and architecture rules.
- Preserve imported record order and the deterministic JSON output.

### No silent data changes

- Do not silently upgrade the pinned JSON version.
- Do not silently delete or drop unsupported fields.
- Do not silently normalize wrapped sequences, FASTA headers, or whitespace unless a documented existing contract explicitly requires it.
- Do not change MSA/template defaults without explicit user action.
- Make mutual exclusions explicit in the controls and in validation/refusal handling.

## 4. Stage 4A — Baseline and source-of-truth audit

Before implementation, inspect and document:

- `ConfigurationService` signatures and result shapes for `add_modification`, `update_modification`, `remove_modification`, `set_alignment`, `set_references`, `set_component_definition`, `clear_component_definition`, `add_linkage`, and `remove_linkage`.
- Model representations for modifications, alignment states, template/reference states, user CCD definition presence, `Linkage`, endpoints and identifier keys.
- How current CLI menus gather and label the same values.
- The source-of-truth mapping for each version-sensitive field, including the minimum version for entity descriptions, MSA paths, template paths and `userCCDPath`.
- Existing validation findings and rules that check version pins, model fields, custom CCD data and bonds.
- Existing tests for PTMs, alignments, templates, component definitions, bonds, version policy, generation refusal and deterministic output.
- Current GUI page/dialog conventions, state pass-through patterns, result-message handling, `project_changed` and refresh flow.

Run and record at least:

```powershell
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q
```

If a path/test does not exist, report that instead of silently substituting an unrelated test. Capture the exact failing core test IDs. If the working-tree baseline differs from the previous report, explain the difference without changing tests merely to hide it.

## 5. Stage 4B — Version-feature conflicts must agree with readiness

### Known issue from Stage 3

The Stage 3 report identified this behavior: an entity description can be set on a pinned version-3 job; the model retains the description and the GUI explains that descriptions require version 4, but the readiness service still reports the job ready while `GenerationService.show_json()` refuses to produce the document.

This is confusing and potentially dangerous. A job should not be labelled ready if its current configuration cannot pass the existing generation/serialization gate.

### Required behavior

1. Inspect the validation architecture and determine whether there is already a rule or reusable mechanism for version-feature minimums. Extend/reuse the correct existing mechanism; do not add a duplicate check in a Qt widget.
2. Audit the minimum-version requirements actually declared by the current mappings and transform path. At minimum examine the currently documented thresholds for entity description, MSA path, template path and external custom CCD path. Derive the required fields from the source of truth, not from hard-coded guesses in the GUI.
3. For a pinned version that is too low for a field actually present in the configuration, expose a clear blocking validation finding/status result that explains the field, current pin and minimum required version. This must make readiness, findings, JSON preview refusal and save refusal consistent.
4. Do not automatically alter the version. The user must explicitly change the version in Job Settings.
5. A field which is unset must not trigger a false conflict. A path-mode field should be checked only when the path mode is actually active. If the version selection is `Auto` or another supported target state, follow the project's existing semantics rather than treating every job as a pinned version.
6. Add focused tests at the validation/service level and a GUI regression test proving the status/finding appears after a user adds or changes a version-sensitive field, then clears when the user explicitly selects a compatible version.
7. Update rule-completeness/catalogue/mapping tests and documentation only as required by the repository's architecture. Do not bypass or weaken the architecture gates.

If repository inspection reveals that generation refusals arise through a more general mechanism than the current report describes, adapt to the actual design and document the choice. The goal is consistency, not a predetermined rule ID or class name.

## 6. Stage 4C — PTM / modification editor

Add a clear way to inspect, add, edit and remove modifications for supported polymer entities, reusing the existing `ConfigurationService` methods and model.

### UI behavior

- On the selected entity's detail/editor view, add a dedicated **Modifications / PTMs** table or section.
- Display the modification code and residue position, with a residue echo when the current shared sequence presenter supports it.
- Position labels must explicitly state **1-based position**.
- Provide Add, Edit and Remove actions. Edit/remove must target the modification that was selected, not a row-derived entity identifier or hard-coded position.
- Only show/enable PTM controls for entity families the current model/service supports. Do not allow ligand modifications or invent new entity capabilities.
- Reuse existing service checks and message results. A rejected code or position should be shown beside the form/action, leave the current modification unchanged, and keep the dialog open when correction is possible.
- On success, refresh the entity table/details, readiness, findings, JSON preview and dirty indicator through the existing `project_changed`/refresh path.
- Ensure that imported modifications already present on a record are editable and removable; do not support only modifications created in the GUI.

### Tests

Cover add/edit/remove; invalid and out-of-range positions; exact 1-based mapping; service refusal leaves state unchanged; cancellation mutates nothing; correct sequence residue echo; and the emitted JSON preview matches the existing serializer. Reuse current unit tests as references rather than duplicating their entire implementation.

## 7. Stage 4D — MSA / alignment controls

Add explicit alignment controls to the relevant per-entity editor.

### Required behavior

- Protein controls should expose exactly the supported protein alignment modes verified from the model/services (the current report lists Automatic, Free, Unpaired Only, Paired Only, and Both; verify actual names and behavior).
- RNA controls should expose exactly the supported RNA modes verified from the model/services (the current report lists Automatic, Free, and Provided; verify actual names and behavior).
- DNA has no alignment fields. Do not show a disabled or editable MSA field that suggests DNA accepts MSA configuration.
- Ligands do not have MSA controls.
- Preserve the existing default (reported as Automatic) for newly created entities and imported settings as represented by the model.
- If a selected mode accepts inline MSA text or an external path, show only the relevant source controls. Use file pickers for paths; do not force the user to type filesystem paths manually.
- Explain each mode with concise help text based on the actual model/CLI wording. Do not imply a computation happened merely because Automatic is selected.
- Use `ConfigurationService.set_alignment(...)` (or the actual current method) for every change. Do not edit record objects directly.
- Keep imported inline/path data intact when the user opens an editor without changing the mode. Do not silently clear data just because a conditional widget is hidden.
- Refusals must keep the prior state, and the UI should refresh only after success.

### Tests

Cover every supported protein and RNA mode, the required inline/path fields for each mode, automatic defaults, switching modes without accidental field loss, rejected paths/inputs, cancellation, no MSA controls for DNA/ligands, and preview/round-trip serialization for representative cases.

## 8. Stage 4E — Protein templates / references

Add a template/reference editor for protein entities only.

- First inspect the actual reference model and CLI workflow. The report describes `SearchAllowed` and `Explicit` states and `mmcifPath`; use the exact supported forms and do not invent a new schema.
- Provide a clear control for the supported default/search-allowed state and an explicit list/editor for reference mmCIF paths when supported.
- Use file pickers and allow users to add/remove multiple references only if the existing model/service supports multiple references.
- Preserve the distinction between “no explicit references / search allowed” and “explicit references” according to the domain model. Do not translate an empty table into a different state unless the existing contract defines it that way.
- Only call `ConfigurationService.set_references(...)` or the verified equivalent. Do not write `mmcifPath` into JSON from the GUI.
- Preserve existing MSA data while editing templates and vice versa.
- Explain version requirements in the UI but let the central validation/generation services determine whether the current configuration is valid.

Tests should cover defaults, one and multiple paths where supported, removing paths, preserving imported references, path/version validation and JSON preview/serialization.

## 9. Stage 4F — Root-level custom CCD component definitions

Implement the already-supported root-level custom component definition workflow. **Do not confuse this with a ligand entity's `ccdCodes` field.**

### Required controls

- A clearly labelled **Custom CCD definition** section separate from the ligand editor.
- Three user choices: None/Clear, Paste definition (inline content), or Load from file (external path), using the actual service semantics.
- Exactly one representation at a time: inline `userCCD` or external `userCCDPath`; never both.
- A multiline text editor for inline definitions and a file picker for path mode.
- Display the active mode and source so the user can tell which choice will be emitted.
- The current contract reports that external custom CCD paths need JSON version 3 or later. Verify from the source of truth and show a clear warning/finding when necessary, without silently changing the pin.
- Use `set_component_definition(...)` and `clear_component_definition()` (or their current equivalents); do not mutate configuration metadata directly.
- Handle an absent/empty selection according to the service's actual semantics. Do not guess that an empty string is the same as a clear operation.

Tests should cover inline definition, external path, switch inline → path and path → inline (including proving the old representation is not emitted), clear, service refusal, cancellation, version conflict, and serialized output through the existing pipeline.

## 10. Stage 4G — Covalent bonds / bonded atom pairs

Implement a UI for adding and removing covalent linkages through the existing service operations.

### UI behavior

- Add a dedicated Bonds / Covalent Linkages section or page rather than cramming bond editing into the sequence text box.
- Read and display existing linkages from the current model; imported bonds must be editable/removable.
- Each new linkage form must identify both endpoints using current registry identifiers and the supported residue and atom fields.
- Populate entity choices from current records; never ask users to supply internal record keys manually.
- Use the actual convention for residue indexing and atom identifiers discovered in existing models/tests. Label indexing clearly in the UI.
- Validate endpoint selections and required values before calling the service, but leave substantive structural validation to the existing service/validation layer.
- Use `ConfigurationService.add_linkage(...)` and `remove_linkage(...)` (or verified equivalents). Do not build `bondedAtomPairs` directly.
- Confirm removal if that is consistent with existing GUI destructive-action conventions. Cancellation must not mutate state.
- After success, refresh findings and JSON preview through the standard state change path.
- Render service-level validation findings clearly, including endpoint-specific problems where supported by `FieldPath`.

Tests should cover valid add/remove, invalid endpoint/key/position/atom refusals, cancelling removal, imported bond display and edits, refresh of preview/output, and deterministic serialization.

## 11. Stage 4H — Make ligand editing atomic where needed

The Stage 3 report says ligand editing currently calls `set_representation(...)` and then `update_record(...)` for a description change. These are two calls and may partially apply one field if the other is refused.

Inspect the current implementation and tests. If this partial-update risk still exists, introduce the smallest suitable service-level operation that updates the supported ligand fields as one logical transaction. It must:

- Validate all requested changes before committing any of them, or use an existing transactional immutable-model pattern.
- Keep identifiers and existing multiplicity intact.
- Not bypass the ID registry or mutate records from a Qt widget.
- Return the existing result type and clear failure message style.
- Leave the prior configuration exactly unchanged if any part is refused.
- Be covered by service-level and GUI tests for both success and rollback/no-partial-change.

Do not implement post-creation copy-count changes in this substage unless source inspection proves there is already a supported service operation. If there is no such operation, retain the read-only copy count and document it as a deferred limitation.

## 12. Sequence wrapping / FASTA question — do not silently normalize

The Stage 3 report notes that pasting a wrapped sequence with internal newline characters is refused by the current model alphabet check, and that no normalization was implemented.

For this stage:

1. Inspect the documented sequence-input contract and current model/service tests.
2. Do not silently strip line breaks, remove FASTA headers or normalize input in Qt.
3. If the current contract intentionally requires a single unwrapped sequence, add a concise form hint so users know to paste a plain sequence; preserve the existing service/model refusal for invalid input.
4. If the repo's authoritative specification explicitly requires FASTA/wrapped input support, propose and implement that normalization at the appropriate service/persistence boundary with dedicated tests. Do not infer this requirement from the fact that a text box is multiline.
5. State the conclusion and evidence in the implementation report.

## 13. UX and state refresh requirements

After every successful change, use the existing state notification/refresh mechanism so all of the following remain consistent:

- Selected entity and its details.
- PTM/modification table.
- MSA/templates state.
- Custom CCD mode.
- Bond list.
- Overview/job readiness and findings.
- JSON preview or the exact service refusal reason.
- Unsaved/dirty marker and status line.

A failed or cancelled operation must not dirty the project or refresh it as though a change succeeded. Preserve selection sensibly after refresh. Do not sort the underlying records or serialized order.

Keep modal forms consistent with Stage 3: understandable labels, file pickers, clear cancel/apply behavior, inline refusal messages, and no traceback dialog for normal service refusals. Use existing string-registry patterns.

## 14. Implementation order

Implement in small dependency-ordered chunks, with tests before moving to the next chunk:

1. Baseline audit and version-feature/readiness consistency.
2. Atomic ligand-edit safeguard, if needed by source inspection.
3. PTM CRUD.
4. MSA/alignment controls.
5. Protein template/reference controls.
6. Root-level custom CCD panel.
7. Covalent linkage editor.
8. UX polish, sequence-input hint/decision, full regression run, documentation.

It is fine to split one logical item into several focused commits internally, but do not create commits as part of this task.

## 15. Testing and acceptance criteria

Add automated tests using the existing GUI testing conventions and Qt offscreen setup. Do not rely solely on static tests or report claims. Test through real widgets/controllers where the project already does that, while asserting the final service/domain state and output.

At a minimum, prove:

- Every new or edited setting goes through the correct service.
- Each refusal/cancel leaves the configuration unchanged and does not incorrectly mark the job dirty.
- Successful changes refresh the GUI's visible state, readiness/findings and JSON preview.
- Version-feature conflicts are visible and block readiness/generation consistently; explicitly selecting a compatible version clears the conflict.
- PTM positions are 1-based and validated centrally.
- MSA modes are family-specific and preserve data unless the user explicitly changes it.
- Protein templates use supported reference states and preserve imported data.
- `userCCD` and `userCCDPath` are mutually exclusive in both the model and emitted JSON.
- Bonds use the service's endpoint/position conventions and the proper wire representation is still emitted centrally.
- Ligand edits are atomic where implemented and cannot partially apply.
- Existing DNA duplex behavior, ligand multiplicity behavior, save/open, JSON preview, the launcher and CLI are unchanged.
- Golden/deterministic JSON tests continue passing.
- Architecture tests remain passing, no new core runtime dependency is added, and all new fixed UI text follows the string-registry convention.

Run and report the appropriate targeted tests first, then:

```powershell
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q
python -m ruff check --select E4,E7,E9,F configbuilder tests/gui
python -m compileall -q configbuilder tests/gui
```

Adapt commands only when a path or tool is absent, and report that limitation plainly. Recompare the sorted full-suite failed test IDs against the freshly measured baseline. Report any pre-existing failures separately; do not modify stale unrelated tests just to obtain a green full-suite result.

## 16. Manual verification checklist for the user

Include a concise, non-programmer checklist in the report so the user can manually verify the running Windows GUI:

1. Launch using `python gui.py`.
2. Create a job, add a protein and open its advanced settings.
3. Add, edit and remove a PTM; verify the 1-based position and preview.
4. Change protein MSA mode and verify relevant path/text controls appear; leave the default unchanged once and confirm it remains automatic.
5. Add/remove a protein template reference.
6. Switch custom CCD from inline to file mode, then clear it; verify only the intended representation remains.
7. Add and remove a covalent linkage using visible entity choices.
8. Trigger a version-feature conflict and confirm readiness/finding/preview agree; explicitly raise the version and verify resolution.
9. Make a ligand edit that succeeds and, if possible, a refused edit proving no partial change occurs.
10. Save and reopen a representative JSON and inspect the final JSON Preview.
11. Verify a cancel operation does not change the model or dirty state.

Do not claim that a real display was manually tested by running only offscreen Qt tests.

## 17. Required deliverable

Create `docs/GUI_STAGE4_IMPLEMENTATION_REPORT.md` (or the repository's established report location if current docs use another consistent convention). Include:

1. Summary of implemented features and explicit out-of-scope items.
2. Exact files created and modified, including a note about any pre-existing modifications in those files.
3. Mapping from every new UI action to the service method it calls.
4. Validation/version-conflict design and tests.
5. PTM, MSA, template, custom CCD, and bond behavior.
6. Whether the ligand edit atomicity issue existed and exactly how it was handled.
7. The sequence wrapping/FASTA decision and source evidence.
8. Exact commands and test results, before/after failed test IDs, lint and compile results.
9. Known limitations and any unverified manual/platform behavior.
10. The manual checklist from §16.

Keep `docs/GUI_STAGE4_IMPLEMENTATION_REPORT.md` updated with only verified claims. Do not state that a real display, PyInstaller packaging, or user's manual workflow was tested unless it actually was.

## 18. Final response when finished

Summarize the implementation, list the report path, show the exact commands/tests and results, identify any remaining known failures/limitations, and explicitly remind the user to perform the manual GUI checklist before Stage 5.

**Do not begin Stage 5. Stop after Stage 4 and its report.**
