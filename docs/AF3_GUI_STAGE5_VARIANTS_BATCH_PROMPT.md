# Stage 5 — Unified Variants, Quantity Series and Batch Workflow for the AF3 JSON Builder GUI

## Role and objective

You are implementing **Stage 5** of an existing Python AlphaFold 3 JSON Builder desktop application built with PySide6 / Qt Widgets.

Stages 1–3 have been implemented and the user reports that the GUI launches and its existing workflows work. Stage 4 is intended to add advanced entity settings, PTMs, MSA/templates, custom CCD definitions, covalent linkages, and handling for version-feature conflicts. **Do not assume Stage 4 is complete exactly as planned. Inspect the current repository and its latest implementation report first.**

Your task is to implement a user-friendly, reliable, integrated **Variants & Batch** workflow by reusing the existing variant and application services. This is an incremental implementation, not a rewrite.

The user also requires that the application be easy for non-programmers to navigate and visually polished. Treat user experience as a functional requirement, not as a final cosmetic task.

## 1. Required source-of-truth inspection

Before changing files, inspect the current repository and relevant documentation. At minimum, examine:

- `GUI_AUDIT_REPORT.md` or the current audit report, if present.
- The latest Stage 1, Stage 2, Stage 3 and Stage 4 implementation reports, especially the Stage 4 report if it exists.
- `IMPLEMENTATION_PLAN.md`, `AUTHORITATIVE_SPEC.md`, `DOMAIN_MAPPING.md`, and the applicable variant/validation/output documentation, when present.
- `configbuilder/app/variant_service.py` and the current definitions of `VariantService` and its result objects.
- `configbuilder/app/validation_service.py` and the actual `validate_all(...)` signature.
- `configbuilder/app/generation_service.py` and existing save/generation APIs.
- `configbuilder/app/batch_variants.py` and the sequence/SMILES file readers under persistence.
- The canonical variant specification, edit classes, edit application, expansion and lineage modules under `configbuilder/variants/`.
- Existing CLI variant/batch flows, for vocabulary and supported behavior only—not to recreate a console menu in the GUI.
- Existing tests under `tests/unit/variants/`, `tests/unit/app/`, `tests/e2e/`, `tests/gui/` and the architecture tests.
- The current GUI navigation, page conventions, `GuiState`, service bundle, refresh/change notification pattern, strings registry, dialogs and launcher tests.

The repository is the source of truth for function signatures, supported edit kinds, input families, model semantics, result types, error messages, and valid output behavior. Verify every API before calling it. Do not assume an example in this prompt exactly matches the current implementation.

## 2. Preserve the working tree and measure the baseline

Before edits:

1. Record `git status --short`, current branch and latest commit.
2. Record existing uncommitted changes and untracked files. Do not overwrite them.
3. Run relevant tests and record exact results and failing test IDs.
4. Do not use `git reset`, `git clean`, `git checkout --`, `git restore`, `git stash`, or any command that discards/hides user work.
5. Do not commit, rebase, amend or clean the working tree.
6. Do not repair unrelated CLI behavior or delete/weaken tests merely to obtain a green suite.

Useful baseline commands (adjust only if repository paths have genuinely changed; document any adjustment):

```powershell
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q
```

Use the actual current GUI environment path if it differs. If a named path does not exist, report that fact rather than silently substituting an unrelated test. The previous reports recorded 13 stale CLI/end-to-end failures, but these are historical figures: measure the baseline again and compare exact node IDs.

## 3. Scope of this stage

Implement these capabilities in one coherent user workflow:

1. A **Variants & Batch** workspace in the GUI.
2. Create, inspect, edit, duplicate and remove spec-based variants using the existing `VariantService` behavior.
3. Add declared changes through typed controls derived from the service's supported options; do not invent a separate GUI edit vocabulary.
4. Preview each variant's declared edits and resulting variant summary before applying/committing changes.
5. Validate one or more variants using existing validation services, including declared-change/drift checks.
6. Create quantity series through the existing planner and creation operation, showing the planned series before committing it.
7. Import sequences or SMILES from a file as a batch, with preview-before-commit and all-or-nothing semantics provided by the existing services.
8. Make manual variants, quantity series and file-based batch generation parts of the **same Variants & Batch workspace**. Users should not have to discover separate, unexplained features in distant menus. Use simple tabs, a mode selector or a step-based workflow inside the one workspace, whichever best fits the existing GUI.
9. Where the current service supports it, let the user save an individual variant JSON through existing save planning APIs. Do not directly write JSON in Qt code.
10. Make the immutability of the base configuration visible and preserve it: editing or generating one variant must not mutate the base or leak one variant's changes into another.

### Explicitly out of scope for this stage

- The complete output-directory generation workflow (`GenerationService.plan(...)` / `execute(...)` to produce the complete multi-variant output tree, assets and manifest) unless the repository's current Stage 4 plan explicitly included it. Keep that larger generate-all/output-layout workflow for the next stage.
- New AF3 schema fields, new biological capabilities or changes to variant semantics.
- Direct construction of JSON dictionaries, JSON strings or serialized bytes in widgets.
- Reimplementation of identity allocation, record mutation, validation, variant expansion or edit application in the GUI.
- AF3 execution, supercomputer/cluster submission, remote file transfer or analysis-pipeline integration.
- A new top-level Python package or GUI framework without a documented architecture reason.

## 4. UX and visual design requirements

The GUI is for users who may not know internal Python class names or AF3 schema vocabulary. A feature is not complete merely because a service call can be triggered.

### 4.1 Where the workflow belongs

- Add a clearly labelled **Variants & Batch** entry to the existing application navigation.
- Place manual variants, quantity series and file-based batch import inside this same workspace.
- Clearly distinguish the **base job** from its variant set. Keep the base summary visible or readily accessible in this workspace.
- Provide a clear overview of existing variant specs: human-readable label/name, declared edits, validation state, and any useful lineage/parent context supported by the model.
- Provide obvious actions such as **New variant**, **Duplicate**, **Remove**, **Validate**, **Quantity series**, **Batch from file**, and **Preview**. Enable/disable actions appropriately instead of letting users discover constraints through tracebacks.
- Keep relevant controls visible. Do not make essential actions accessible only via right-click, unexplained icons or deeply nested menus.

### 4.2 User-facing edit construction

- Populate change-kind dropdowns from the real `VariantService.edit_options()` (or verified equivalent).
- Populate entity/record choices from `entity_choices(...)`, `all_entity_choices()` or the verified equivalent.
- Show friendly labels, sequence/entity descriptions and relevant IDs where helpful. Do not ask the user to type a raw internal `record_key`, edit class, model class name or serialized JSON fragment.
- After the user selects a change type, show only the fields relevant to that type and explain them briefly.
- Where a value has a biological or indexing convention (for example, a residue position), label the convention explicitly and follow the existing service/model contract.
- Show a clear summary of proposed edits before saving/committing a variant. The preview must come from existing variant services where possible, not a separate GUI implementation of edit application.

### 4.3 Quantity series

- Use the existing planner and creation API. First show the calculated labels/names and counts, then offer an explicit **Create series** confirmation.
- Validate required values, bounds, and potentially excessive series sizes using existing service rules or a small UI input guard where appropriate.
- Never guess the semantics of `start`, `factor`, or `levels`; use the service/CLI explanation and current tests.

### 4.4 Batch from file

- Offer the input family/type choices actually supported by the current file reader and service. Verify the real supported formats; do not assume RNA/DNA/SMILES types merely because they appear biologically plausible.
- Use a file picker. Show the selected path and a preview using the existing `inspect_sequence_file(...)` or verified equivalent before generation.
- Explain how many items were found and how the service will treat them. Show line-level or item-level refusal information if the service provides it.
- Commit only after explicit user confirmation. Preserve all-or-nothing behavior: a malformed batch must not leave a partially-created variant set.
- Do not silently strip FASTA headers, normalize line breaks or alter sequence contents. Follow the authoritative file/input contract. If an input format limitation is confusing, explain it in the UI and report it; do not invent normalization.

### 4.5 Aesthetics, interaction and accessibility

- Follow the design-system direction already added to the current implementation prompt/report: consistent typography, spacing, restrained colours, aligned forms/tables, readable status indicators and purposeful whitespace.
- Prefer a clean, professional scientific desktop application over a cluttered dashboard full of decorative cards.
- Use concise labels, tooltips and short explanations for domain-specific controls.
- Give validation errors, warnings, informational messages and successful operations visually distinct but restrained treatments.
- Maintain usability at ordinary Windows window sizes and scaling. Avoid fixed widths that make the workflow unusable after resizing.
- Use confirmation dialogs for destructive operations; cancellation must have no effects.
- Preserve consistent button names and interaction patterns across Overview, Entities, advanced settings and Variants & Batch.
- Do not perform a full unrelated visual redesign in this stage. Improve this workspace and the shared components it uses, keeping the visual language consistent with existing pages.

### 4.6 Existing cross-page UX requirements

Preserve and respect the broader design requirements already supplied by the user:

- Overview should allow job-wide settings such as job name, model seeds and JSON version to be viewed and edited directly, not only through an extra settings window/page.
- Entity selection should expose relevant settings in one consistent workspace, including MSA/templates and PTMs after Stage 4, rather than forcing users to hunt through unrelated navigation.
- Existing entity, PTM, alignment, template, CCD and bond editing must keep working after navigation additions.
- Keep service/validation/model logic out of Qt widgets.

If Stage 4 did not yet implement any of these requirements, record the gap. Do not silently expand Stage 5 to fix unrelated missing Stage 4 functionality unless the fix is necessary for this workflow and is small, clearly documented, and tested.

## 5. Inspect and use existing variant service behavior

The earlier audit reported a richer service-based mechanism than the former CLI's save-as-copy flow. It identified APIs with names such as:

- `add_spec`, `update_spec`, `remove_spec`, `duplicate_spec`
- `add_spec_from_factor`, `append_factor`
- `apply_variant_edit`, `preview`, `edit_options`
- `entity_choices`, `all_entity_choices`, `build_add_records`
- `modification_summary`, `describe_spec_edits`
- `quantity_series_plan`, `create_quantity_series`
- `inspect_sequence_file`, `generate_from_file`
- `specs`, `spec_count`, `validate_all`

These are names observed in a previous audit, **not permission to assume signatures**. Read the current source and tests and call only the APIs and argument forms that actually exist. Check how service results signal refusal, warnings and success; present the existing message text wherever suitable.

### Required behaviors for spec-based variants

- Create a variant spec with a clear user label/name using the existing service.
- Add declared edits using supported edit choices and values.
- Edit an existing spec without silently losing its other declared edits.
- Duplicate a spec without sharing mutable state or causing unintended changes in the source spec.
- Remove a spec after a clear confirmation; cancellation changes nothing.
- Preview the declared edits and variant contents before saving/generating.
- Use the existing expansion/lineage behavior; do not construct `Variant` objects manually in widgets.
- Where a base snapshot is part of the existing implementation, keep it immutable during spec edits, preview, batch import and variant generation.
- Do not let a variant inherit changes from another variant unless the current domain contract explicitly declares that relationship.

### Validation and drift

- Use the current `ValidationService.validate_all(...)` or its verified equivalent.
- Show validation status on each variant row and detailed findings for a selected variant.
- If the service detects declared-change drift (for example existing `R-VAR-001`/`R-VAR-002` behavior), report it using the existing finding/result; never bypass it in UI code.
- A failed validation or refused preview must not mark the variant as ready or silently allow a blocked operation.
- After a successful edit/create/remove, refresh the spec list, selection, validation state, counts and any relevant preview through the established state signal/refresh seam.

## 6. Required implementation sequence

Work incrementally and keep each substage testable.

### Stage 5A — Service seam and UI design plan

1. Audit the actual current service APIs, data structures, result types, file formats and tests.
2. Draft a concise internal plan for the Variants & Batch workspace, including UI navigation, widget/page changes and mapping to existing service calls.
3. Identify mismatches between existing GUI state management and the required workflow.
4. Do not create new abstractions before demonstrating the existing seam is insufficient.
5. Record the source of truth for each input type, each edit kind and the transactional behavior of file batches.

### Stage 5B — Variant list and typed editor

1. Add the Variants & Batch workspace to existing navigation.
2. Show existing specs and their declared edits/validation summaries.
3. Add create, select, edit, duplicate and remove.
4. Build typed edit forms from service-supplied choices.
5. Add a human-readable preview/detail area for the selected spec.
6. Wire all operations through `GuiState`/the established service layer and update the rest of the GUI after mutations.

### Stage 5C — Validation and quantity series

1. Add selected/all variant validation using the actual service API.
2. Show per-variant state and selected-variant findings.
3. Add the quantity-series form using the existing plan function.
4. Display the planned series before commit, then create it only after an explicit action.
5. Handle service refusals inline, without tracebacks or partial changes.

### Stage 5D — File-based batch workflow

1. Add file selection and verified family/type choices.
2. Preview input via existing inspection functionality.
3. Explain the proposed generated variant set and any warnings.
4. Commit via the existing all-or-nothing service method after confirmation.
5. Verify that malformed or refused batches leave the existing project/spec set unchanged.

### Stage 5E — Save one variant and regression verification

1. If the existing UI/service supports saving one variant through `GenerationService.plan_save(...)` and `execute(...)`, expose that pathway using the existing APIs. Do not reimplement output naming, validation, resource handling, overwrite policy or JSON serialization.
2. Keep complete multi-variant output-tree generation, assets and manifest planning for the next output/generation stage unless the current implementation plan explicitly assigns it here.
3. Finish the acceptance tests below, run regression suites and write the implementation report.

At the end of each substage, run the narrow tests and inspect the diff before continuing. Do not stop after merely creating placeholders or a nonfunctional visual prototype: Stage 5 is expected to be functional.

## 7. Testing and acceptance criteria

Create or extend tests under the existing GUI test location and appropriate service/unit test locations. Do not weaken existing tests.

### UI and variant specs

- The Variants & Batch workspace is visible and reachable through normal navigation.
- Existing specs are displayed correctly, with user-facing labels and no raw model reprs.
- Creating, editing, duplicating and removing specs works through the actual widgets/controllers and existing services.
- Cancellation changes nothing.
- Failed/refused operations leave existing spec/base configuration state unchanged and display useful errors.
- Typed controls expose only valid service-supported edit kinds and relevant values.
- Variant summary/preview reflects the service's result.
- The base configuration remains equal to its original snapshot after edits/preview/variant creation, apart from explicitly intended base-job settings operations outside this workspace.
- One variant's edits do not leak into another.

### Validation

- Per-variant validation state reflects `validate_all` results.
- Findings and blocking reasons shown in the GUI match service results.
- Drift/invalid variants cannot be falsely shown as ready.
- Revalidation occurs when a spec is changed, duplicated, removed or a batch is committed.

### Quantity series

- The displayed preview matches exactly the series created by the service.
- Invalid values are rejected clearly.
- Cancel does not create specs.
- Successful creation yields the expected count and names based on actual service semantics.
- A refusal or error leaves pre-existing specs unchanged.

### File batch

- Valid supported files show a preview before any commit.
- Cancel does not mutate state.
- A valid batch creates exactly the previewed set.
- Invalid files/refusals leave no partial batch.
- Existing spec/base state is preserved.
- File contents are never modified.

### Saving and regression

- If saving an individual variant is implemented, its bytes are produced through the existing pipeline and obey overwrite/validation behavior.
- The GUI never writes wire JSON directly.
- Stages 1–4 behavior continues to pass its prior tests.
- `gui.py` and `af3builder.py` still launch as previously verified.
- Architecture tests pass.
- No new core failures appear compared to the measured baseline.
- Test module skips due to PySide6 not being installed in the core environment are expected if that is the established project policy; the full GUI suite must be run in the GUI environment.

Prefer tests of the actual widget/controller integration plus service-state assertions. Do not treat static source-text checks alone as sufficient proof that interactions work.

## 8. What the GUI must never do

- Never build an AF3 JSON dictionary or formatted JSON text itself.
- Never allocate, rename, resolve or release entity IDs directly.
- Never mutate immutable domain records or variant specs directly in widget code.
- Never reimplement variant expansion or declared-change/drift validation.
- Never silently modify the base configuration during variant operations.
- Never partially apply a file batch when the service contract promises all-or-nothing behavior.
- Never suppress validation errors just to make a button available.
- Never silently upgrade a JSON version or discard fields.
- Never change MSA/template defaults or normalize sequences/file input implicitly.
- Never add PySide6 to core runtime dependencies.
- Never alter or remove the user's unrelated uncommitted changes.

## 9. Final implementation report

Create `docs/GUI_STAGE5_VARIANTS_BATCH_IMPLEMENTATION_REPORT.md` (or the established documentation location if the project currently uses a different one). Include:

1. Summary of actual delivered behavior and any explicitly deferred scope.
2. All created and modified files with a reason for each change.
3. A mapping of each GUI operation to the actual existing service method(s).
4. How the UI merges manual variants, quantity series and file batch into a single discoverable workflow.
5. The variant base-immutability guarantees and any service transaction guarantees.
6. Test commands, exact outcomes and comparison with the pre-change baseline.
7. Exact remaining failing test IDs, distinguished from new failures.
8. Manual Windows usability checklist, including keyboard focus, resizing, legibility, navigation discovery, modal cancellation, and feedback after success/failure.
9. Known limitations and recommended next-stage scope (full generate-all output layout, assets and manifest via `GenerationService.plan`/`execute`, if not delivered in Stage 5).
10. Confirmation that no destructive Git commands or commits were performed and a concise final `git status --short` inventory.

## 10. Completion definition

Stage 5 is complete only when the user can use the GUI to manage service-supported variants, quantity series and file-based batches within one understandable workspace; inspect proposed changes before committing; validate variants; save a single variant through the supported output path if included; and all relevant tests pass at or better than the measured baseline with no new regressions.

Implement Stage 5 only. Do not begin the next generation/output stage after writing the report. Do not claim that real Windows visual/manual testing was completed unless it was actually performed. Stop and report any blocker that requires a user decision rather than guessing.
