# Agent Task: Stage 3 — Entity Management for the AF3 JSON Builder GUI

## Goal

Extend the existing, working PySide6 desktop GUI with **basic entity management**: add, inspect, edit and delete proteins, RNA, DNA and ligands. Use the existing application services and data model. Do not rebuild the GUI and do not implement Stage 4 advanced settings or Stage 5 variants in this task.

The user has manually launched the GUI successfully and reports that Stage 2 (New Job, basic settings and Save JSON) works correctly. Treat this as permission to begin Stage 3, but independently inspect the current working tree and implementation before changing anything.

## Mandatory first step: inspect the actual repository state

Before editing:

1. Locate the repository root from the current workspace. Do not hard-code a machine-specific absolute path.
2. Read `GUI_AUDIT_REPORT.md`, `GUI_STAGE1_IMPLEMENTATION_REPORT.md`, `GUI_STAGE2_IMPLEMENTATION_REPORT.md` (or the report's actual current filename), the current GUI usage documentation, and the relevant source/tests if these files exist.
3. Inspect `git status --short` and all relevant diffs. The repository previously contained user changes and untracked files. **Preserve every pre-existing change.** Never reset, clean, checkout, stash, revert, or commit anything.
4. Inspect the current GUI state/controller, MainWindow, entity table/model, Stage 2 job lifecycle and dirty-state handling, actual service methods/result types, domain records and identifier model, DNA duplex logic, shared UI string registry, and current GUI test fixtures.
5. Run the existing baseline tests before edits where feasible: launcher tests, Stage 1/2 GUI tests using the GUI environment and offscreen Qt, architecture tests, and the core suite. Record exact failing test IDs. The earlier audit's 13 end-to-end failures are historical information only; re-measure the current tree.
6. Confirm actual method signatures and service result semantics by reading source. Do not rely solely on prior reports or assume a method exists.

Create no code changes until this reconnaissance is complete.

## Scope for this stage

Implement only the following:

- Add a protein entity.
- Add an RNA entity.
- Add a DNA sequence using the existing DNA-duplex creation behaviour.
- Add a ligand represented by CCD code(s) **or** SMILES, with a copy count where supported.
- Display all current entities and their meaningful basic properties.
- Select an entity and inspect its details.
- Edit an existing entity's sequence and/or supported description fields.
- Delete an entity with clear confirmation.
- Refresh all affected views after successful operations: entity table/details, job summary/readiness, validation findings, JSON preview and dirty/saved status.
- Add automated tests for all behaviour introduced.

Do **not** implement PTM editing, custom CCD component editing, MSA/template configuration controls, covalent bond editing, variants, quantity series, batch-from-file or bulk generation in this stage. These are later stages. Existing advanced data imported from an existing JSON must remain preserved when an unrelated entity is edited or deleted.

## Required UI behaviour

### 1. Entity list and actions

Add accessible, clearly-labelled controls for:

- `Add Protein`
- `Add RNA`
- `Add DNA`
- `Add Ligand`
- `Edit Selected`
- `Delete Selected`

If a single `Add Entity` wizard fits the current design better, it may offer the four supported families using a dropdown, but do not make users type a family name or raw JSON. Follow the current GUI style and reuse existing widgets/models where appropriate.

The entity table must be refreshed from the current `project.configuration.records` after each successful mutation. Preserve the underlying record order. Do not let view sorting or selection operations reorder the domain records or affect serialized JSON ordering. Maintain clear selection behaviour when a mutation refreshes the model.

Use registry-based/user-facing labels and the existing presentation helpers where they fit. Add new fixed UI strings to the appropriate shared string registry if required by architecture tests; do not scatter duplicate user-facing wording through the code.

### 2. Add protein and RNA

Use a form/dialog with:

- Sequence input, allowing paste of a multiline sequence; normalize only in ways the existing service/model already supports.
- An optional per-entity description only if it can be represented correctly by the current model and chosen JSON version. Preserve the distinction between an omitted description and an explicitly supplied value. Because emitted entity descriptions require JSON version 4, show a clear, non-destructive explanation when the current version cannot support a supplied description. Do not silently upgrade the job version or discard the description.
- Clear Add and Cancel actions.

Route all mutations through `ConfigurationService.add_record(...)` (or the actual existing service API discovered in the code). Do not assemble model records directly in the widget or controller unless the current service explicitly requires a typed input object.

Use the service result and existing validation/status flow to communicate success or refusal. Cancel must do nothing.

### 3. Add DNA — preserve the existing duplex semantics

The current service adds DNA as a duplex: one supplied sequence produces two DNA records, including the reverse-complement partner. The existing CLI's optional single-strand choice has a known defect: answering “No” can remove all DNA records. **Do not copy that UI path or offer a single-strand checkbox in this stage.** Do not attempt to fix the separate single-strand service/CLI defect as part of this feature.

The GUI must:

- Explain before adding DNA that the input sequence creates a strand and its reverse-complement partner.
- Call the existing DNA add service once with the supplied sequence.
- Show both resulting DNA records/chain IDs as created by the service, without inventing chain IDs or recomputing the complement in GUI code.
- Represent their partner relationship using existing model properties where available.
- Continue to display lone DNA strands faithfully when they come from an imported JSON; do not invent a partner for an imported single strand.

Editing: use `ConfigurationService.update_record(...)` and its existing duplex propagation semantics. If the selected strand belongs to a duplex, explain that editing its sequence updates the partner according to the service. Do not independently calculate or write the complementary sequence in the GUI.

Deleting: use `ConfigurationService.remove_record(record_key)` and its service semantics. Since deleting either member of a DNA duplex removes the pair, the confirmation dialog must explicitly say that both strands will be removed when the selected DNA record has a partner. Cancel must leave both records untouched.

### 4. Add ligands

Provide an explicit mutually exclusive choice between:

- **CCD code(s)** (accept the existing service's documented token format; allow multi-component code lists if supported), or
- **SMILES**.

Never allow both representations to be submitted simultaneously. Do not create a new standalone `ion` entity family: ions use CCD-code ligand representation in this builder. A hint may explain this to users.

Provide a bounded integer spin box for copy/multiplicity count, with the valid minimum and maximum derived from existing rules or a conservative validated range. Do not reimplement identifier allocation. Call the existing `add_record` service with the correct representation and `representation_kind` arguments as verified in source.

The table/details should display all identifiers belonging to a multi-copy ligand in the form the model/presenter expects. Deleting that ligand must use its record key and release all IDs through the service; never delete by list index or by iterating identifiers manually.

### 5. Edit and delete

Edit only basic fields supported in this stage:

- Protein: sequence and supported description field.
- RNA: sequence and supported description field.
- DNA: sequence and supported description field, respecting the model/service semantics for paired or lone imported strands.
- Ligand: CCD representation or SMILES and copy count only if the current service/model provides a supported operation for changing those fields. If there is no safe existing operation, do not mutate records directly or implement an unsafe workaround; document the gap and ask for a review in the report.

The audit identifies `ConfigurationService.update_record(record_key, sequence, description)` and `remove_record(record_key)` as existing routes. Confirm the signatures and result objects before use. Use registry-resolved record identifiers/keys; never use row numbers or list positions as entity identity.

Before deletion, show a confirmation that names the selected entity/IDs and explains consequences, including paired DNA or ligand multiplicity where appropriate. A rejected service operation must leave the GUI state and model unchanged and present its own failure message without a traceback.

### 6. Validation, refresh and data integrity

After every successful operation:

- Refresh from the authoritative service/project state.
- Recalculate displayed readiness/findings only by calling the existing validation/status services; do not recreate validation rules in Qt code.
- Refresh JSON preview through `GenerationService.show_json(...)`; do not build JSON dictionaries or serialize independently.
- Update the existing dirty/saved indicator so saving remains reliable.
- Preserve current Stage 1 import-preview/confirm/commit and Stage 2 New Job/settings/Save behaviours.
- If a mutation is refused or the user cancels, do not mark the job dirty and do not update the view as though a change happened.
- Catch and render expected service/filesystem/UI errors in the current user-facing style; never show a raw traceback for a routine refused action.

Do not add autosave or write files during entity editing. The user should save explicitly using the existing Stage 2 workflow.

## Architecture rules

- Reuse the existing service layer for all mutations and validation.
- Do not create wire JSON dictionaries, serialize JSON independently, write JSON directly, allocate/rename IDs, infer readiness, or reimplement biological/domain rules in the GUI.
- Keep Qt implementation inside the currently accepted GUI package location unless the audit and architecture tests justify a reviewed change. Do not alter architecture guard tests just to bypass their constraints.
- Keep the core installable/testable without PySide6; Qt remains an optional extra.
- Do not add an unnecessary dependency.
- Use the existing shared string registry/presentation helpers where required by architecture tests.
- Keep the CLI working and unchanged in behaviour.
- Follow the project's supported Python syntax. Do not introduce newer syntax forbidden by `tests/architecture/test_baseline.py`.
- Do not make unrelated cleanups or refactors.

## Testing requirements

Add tests to the current GUI test suite using the established offscreen Qt fixture pattern. Test behaviour via actual widget/controller actions and service state, not only helper-method mocks. Follow the existing no-modal-hang/watchdog pattern for modal dialogs.

At minimum, cover:

1. Add protein: service-backed record appears with the service-allocated identifier and correct sequence.
2. Add RNA: service-backed record appears correctly.
3. Add DNA: both strands created by the service appear; the paired relationship is displayed accurately.
4. Edit DNA sequence: service-defined partner update is reflected; no duplicate/manual complement implementation exists in the GUI.
5. Cancel DNA deletion leaves both strands intact; confirm deletion removes the duplex pair.
6. An imported lone DNA strand is shown without an invented partner and can be handled according to existing service semantics.
7. Add ligand via CCD; add multi-component CCD ligand if supported; ion-like CCD code is represented as a ligand.
8. Add ligand via SMILES; mutually exclusive representation controls prevent submitting CCD and SMILES together.
9. Multi-copy ligand displays every allocated ID and deleting it removes the logical record via the service.
10. Edit sequence/description through service calls; version 3 with a supplied per-entity description is handled without silent version upgrade, silent data loss or raw traceback.
11. Refused service operations display the service failure reason and do not mutate state.
12. Cancelled add/edit dialogs do not mutate the job or mark it dirty.
13. Successful changes refresh the entity table, details, readiness/findings and JSON preview.
14. The current record order and JSON serialization order remain unchanged except for the intended add/edit/delete operation.
15. Stage 1 import/preview tests, Stage 2 lifecycle/save tests, launcher tests and architecture tests still pass.

Do not use list indices to address records in tests for service actions; use domain keys/IDs. Add unit-level tests for thin adapters only where widget tests are unnecessarily expensive.

## Verification and baseline comparison

Run and report the exact commands and outcomes for:

- New Stage 3 GUI tests.
- All `tests/gui` tests in the GUI virtual environment using `QT_QPA_PLATFORM=offscreen`.
- `tests/architecture`.
- Launcher tests.
- The full core test suite with the core interpreter and no requirement for PySide6.
- Syntax/compile checks and the existing CLI smoke test.

Compare current failing core test IDs against the baseline measured at the start of this task. The audit previously documented 13 stale end-to-end failures, but do not assume those are still present. Clearly separate baseline failures from regressions. Do not delete or weaken tests merely to obtain a green count. Do not claim a graphical/manual test succeeded unless someone actually performed it.

## Deliverable

Create `GUI_STAGE3_IMPLEMENTATION_REPORT.md` in the appropriate existing documentation location. Include:

1. Summary of delivered functionality.
2. Exact files created and modified, with a rationale for each.
3. Description of how each entity type calls existing services.
4. DNA duplex and multi-copy ligand handling details.
5. Tests run with exact results and baseline-vs-current failing test IDs.
6. Any issues deliberately deferred, including the single-strand DNA defect and unsupported safe ligand-edit operations if applicable.
7. Manual verification checklist for a non-programmer, including sample steps for add/edit/delete and saving/reopening a JSON.
8. Known limitations and recommended next steps for Stage 4.

## Stop condition

Implement Stage 3 only. Run the tests, create `GUI_STAGE3_IMPLEMENTATION_REPORT.md`, summarize the result and **stop for review**. Do not begin Stage 4 advanced entity settings, PTMs, custom CCD, MSA/templates, covalent bonds, variants or batch generation in this task.

## Final operating rules

- Think before coding; inspect current source, diffs and test results first.
- Make small, reviewable changes and preserve all existing work.
- Do not install packages or modify the core environment automatically.
- Do not commit, reset, stash, clean or revert anything.
- Do not claim tests ran unless they actually ran.
- Clearly distinguish verified implementation from planned work and unresolved issues.
