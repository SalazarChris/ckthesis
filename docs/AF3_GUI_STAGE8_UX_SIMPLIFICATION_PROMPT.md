# Stage 8 — UX Simplification and Navigation Redesign for the AF3 JSON Builder GUI

## Objective

Improve the usability and visual clarity of the existing PySide6 AF3 JSON Builder GUI. This is a focused UX simplification stage, not a new biological-feature stage and not a rewrite of the application.

The user has manually launched the application and identified three concrete problems:

1. **Redundant job settings:** job name, model seeds, and JSON version can be edited on Overview, but a separate top-level Job Settings tab remains. The same concept appears in two places and adds unnecessary navigation.
2. **Generate & Output is too complicated:** too many options and details appear to be exposed together, making the basic workflow hard to understand.
3. **Variants & Batch is not intuitive:** users should not need to understand internal implementation terminology or infer which workflow to choose.

The attached screenshot shows the current dark-themed Overview page, including the duplicated settings navigation, large readiness/findings areas, and dense wide tables. Use the current repository as the source of truth for the actual implementation. The Stage 7 report is background evidence, not a substitute for inspecting current code.

## Mandatory workflow before editing

1. Inspect the current GUI implementation and the latest reports, especially:
   - `docs/GUI_STAGE7_FINAL_UX_AND_RELEASE_REPORT.md`
   - `docs/GUI_STAGE6_OUTPUT_GENERATION_IMPLEMENTATION_REPORT.md`
   - `docs/GUI_STAGE5_VARIANTS_BATCH_IMPLEMENTATION_REPORT.md`
   - `RUNNING_THE_APPLICATION.md`
   - `configbuilder/ui/render/qt/`
   - relevant GUI tests under `tests/gui/`
2. Run and record a targeted baseline before changes:
   - GUI test suite in `.venv-gui`
   - architecture tests
   - launcher tests
   - relevant variant/generation service tests
3. Inspect the current working tree and explicitly preserve all existing modifications and untracked user work. Do not reset, clean, stash, checkout, revert, or commit. Do not overwrite reports or unrelated files.
4. Write a short `docs/GUI_STAGE8_UX_PLAN.md` describing the proposed layout and user flows before implementation. Proceed with the implementation in the same task only after recording the plan; do not wait for user approval unless an unresolved choice could change core behaviour or remove an established capability.

## UX principles

Design for a scientific user who understands biology and the goal of creating AF3 inputs, but may not know the codebase or internal software terminology.

- Prefer plain language over internal names such as “spec”, “expansion”, “plan object”, or service/class names.
- Keep common actions visible and labelled. Never make an important workflow available only through an icon, a right-click menu, or an unexplained advanced control.
- Use a progressive-disclosure pattern: show the few decisions users need for the current task first; place uncommon options under a clearly labelled “Advanced options” section.
- Keep all existing biological rules, validation, entity identity, serialization and generation semantics inside the current services.
- Do not silently change defaults. Show the effective value and explain any meaningful consequence.
- Keep safe preview/confirmation before batch or filesystem writes.
- Do not add a new UI framework, animation system, or gratuitous decoration. Reuse the existing Qt Widgets architecture and central `style.py` design layer.
- Make labels, validation, warnings, cancellation and success feedback consistent across pages.
- Keep the design comfortable at normal Windows window sizes, maximized, and 125%/150% display scaling. Automated offscreen tests cannot replace a real manual usability check.

## Workstream A — Remove duplicate Job Settings navigation

### Required design

- Make **Overview the single place for editing job-wide settings**: job name, model seeds and JSON version.
- Remove the separate top-level **Job Settings** tab after verifying that all its functionality is available on Overview.
- Do not leave a duplicate second settings panel elsewhere in the main navigation.
- Keep Overview concise and scannable. Organize it approximately as:
  1. Job settings (name, seeds, version)
  2. Job summary (dialect, entity counts and relevant job facts)
  3. Readiness summary with the most important blocking issues
  4. Validation findings, in a compact panel that can expand/collapse or scroll when long
- Preserve the existing service-backed edit actions and default/custom indicators. Keep readiness derived from the validation service, not recalculated in Qt.
- Avoid oversized empty areas and enormous tables dominating the initial view. Use sensible size policies and a scroll area where needed. Do not hide blocking findings by default in a way users are unlikely to discover.
- Update all user-facing references, help text, accessibility names and navigation tests to match the new information architecture.

### Acceptance criteria

- Only one top-level navigation destination is responsible for job settings: Overview.
- Name, seeds and version can be changed from Overview using existing services.
- The displayed values, dirty marker, readiness, findings and JSON preview refresh consistently after accepted changes.
- Refused edits restore the service's current values and show an understandable problem message.
- No regression to New Job, Open JSON, Save JSON, import preview, validation or the CLI.

## Workstream B — Make Variants & Batch understandable

### Required information architecture

Retain one top-level **Variants & Batch** area, but structure it around what the user wants to accomplish. Do not expose internal class/service terminology.

The page should have three clearly labelled creation paths, each with a short explanatory sentence:

1. **Create a variant** — make one alternative configuration from the base job by selecting supported changes.
2. **Create a series** — repeat a supported parameter over a specified range or set of levels; show the planned result before creating it.
3. **Create variants from a file** — import a supported sequence/SMILES list, inspect the parsed records, preview the prospective variants, then confirm.

Use the actual capabilities of the existing services to determine which edit types/families and file formats are supported. Do not promise features that are not implemented.

### Existing variants list

- Make the base job and its role visually clear. Explain in plain language that variants derive from the base and that editing a variant must not silently mutate the base configuration.
- Show existing variants in a compact table/list with useful columns such as name, summary of changes and validation state. Adapt to the actual model; do not invent data.
- Make the primary actions obvious: create, inspect/preview, edit, duplicate and remove, where supported.
- Selecting a variant should display its declared changes and validation result without opening several unrelated screens.
- Put less common choices in secondary controls, not alongside every primary button.
- Use a guided dialog or step-by-step inline form for each creation path: choose input/change → show a concise summary → validate/preview → confirm creation.
- For quantity series and file batch creation, always show how many variants will be produced and any parse/validation issues before committing.
- Cancellation must leave the variant collection and base job unchanged.
- Use existing `VariantService`, `ValidationService` and `GenerationService` methods. Do not create a second variant engine in Qt and do not write JSON directly from the page.

### Acceptance criteria

- A non-programmer can distinguish creating one variant, making a series, and importing many variants from a file without needing an explanation of Python internals.
- All currently implemented variant and batch operations remain reachable.
- Invalid input and service refusals display actionable messages and preserve the dialog values for correction.
- Variants validate through the current service, and the base configuration remains unchanged by variant-only edits.
- File batches are previewed before commit and remain all-or-nothing according to existing service behaviour.
- Existing generation semantics and declared-change/drift validation are unchanged.

## Workstream C — Simplify Generate & Output

### Required user flow

Turn the page into a clear, progressive workflow with the following sequence. This may be implemented as a simple guided panel or wizard, provided it matches the current application style and remains easy to navigate backwards.

**Step 1: What do you want to generate?**

- Base job only.
- Selected variants.
- All variants.

Only show options genuinely supported by the existing generator. If the current service distinguishes a single JSON save from multi-variant generation, explain the difference in plain language rather than making both paths look identical.

**Step 2: Where should it go?**

- Choose the output folder using a file/folder picker.
- Show the effective folder and a readable summary of the intended directory/file structure.
- Keep safe default policies visible. Move uncommon path/overwrite policies into an “Advanced options” disclosure, but never silently choose a destructive overwrite policy.
- Explain the meaning of choices such as overwrite, skip or fail, using the vocabulary and semantics of the existing policies.

**Step 3: Review the plan**

- Show a concise summary of the number of jobs/files, destination, required assets, warnings and conflicts.
- Keep detailed file and asset tables available under collapsible details; do not remove visibility into conflicts or files that will be written.
- A conflict must be visible before execution, with an understandable consequence and a safe way to go back and change options.

**Step 4: Generate**

- Require explicit confirmation before executing filesystem writes.
- After execution, show success/failure per output item and the resulting paths, reusing service result objects.
- Provide a copy-path action where relevant.
- Handle cancellation, refusal and filesystem exceptions without traceback dialogs or silent failure.

Preserve the separate quick **Save JSON** action for a single JSON file. Do not force a simple single-file save through an unnecessarily complex multi-variant wizard.

### Acceptance criteria

- The most common generation path is understandable without reading documentation.
- A user can inspect what will be written before confirming.
- Conflicts and warnings are not hidden behind advanced disclosure if they affect safety or require a decision.
- Cancellation writes nothing; refused plans write nothing; successful execution uses the existing `GenerationService` and output planner.
- Asset copying/referencing, manifest generation, overwrite policy and path policy retain their existing service semantics.
- Existing clipboard/copy-path functionality works for both output files and assets.

## Workstream D — Visual consistency and small-screen behaviour

- Use the existing central stylesheet and shared label/widget patterns.
- Avoid redundant tabs, redundant settings displays, repeated descriptions and unnecessary large tables.
- Use one clear primary action per workflow section; visually demote secondary actions.
- Apply consistent spacing, heading hierarchy, button naming, table sizing and empty states.
- Long findings, variant lists, file plans and paths must remain readable and scrollable.
- Preserve keyboard tab order, visible focus, keyboard activation, and meaningful accessible names.
- Reuse status words and existing message registry conventions; do not scatter user-facing hard-coded wording across UI modules.

## Scope limits

- Do not add new scientific/biological capabilities.
- Do not change AF3 JSON structure or serialization.
- Do not change validation criteria, identifier allocation, variant expansion, batch atomicity, overwrite semantics or filesystem safety rules just to make the UI easier.
- Do not fix the 13 known stale CLI end-to-end failures as part of this task unless the baseline proves their status has changed; report baseline vs final test IDs.
- Do not package a new executable as part of this UX task.
- Do not rework the GUI wholesale if a focused layout change is sufficient.

## Tests to add/update

Use the project’s existing test conventions and Qt offscreen environment. Add behaviour-based tests rather than tests that assert widget implementation details wherever practical.

At minimum, cover:

1. Top-level tab list no longer contains Job Settings; Overview still exposes all settings.
2. Overview setting changes update the service-backed job state and all relevant views.
3. Variant page exposes the three distinct workflows with clear labels and preserves all previously supported operations.
4. Cancelling each variant/series/file-batch workflow changes neither the base nor the variants collection.
5. Series and batch previews report planned item counts and validation/parse problems before commit.
6. The base configuration remains unchanged when a variant is edited.
7. Generate & Output follows selection → destination → review → confirm → result, and uses the existing services.
8. Cancelled generation and refused plans perform no filesystem writes.
9. Conflicts remain visible before execution; advanced disclosure does not conceal blocking conflicts/warnings.
10. Asset paths can still be selected and copied.
11. Existing Stage 1–7 GUI, architecture, launcher, service, serialization and output tests pass at their previous baseline.

Run at least:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q tests/unit/test_launchers.py
python -m pytest -o addopts="" -q tests/unit/app tests/unit/variants tests/unit/output
python -m pytest -o addopts="" -q
```

Use the correct installed interpreter paths if the repository environment differs. Record exact commands and actual results. Compare full-suite failure IDs against the starting baseline; do not describe an unchanged failure as a new regression or claim a suite is green when it is not.

## Manual Windows validation required

After the automated tests, provide the user a compact manual checklist covering:

- Overview contains job settings once and is not overwhelmingly dense.
- Create one variant, preview it, cancel once, then commit another.
- Create a quantity series and confirm the planned count before creation.
- Import a small batch file and confirm that malformed input is visible before commit.
- Preview output, inspect conflicts, cancel and verify no files were written.
- Generate into a temporary folder and inspect the resulting JSON, assets and manifest.
- Verify readability at default size and maximized; check Windows 125%/150% scaling if available.

Do not claim manual verification has occurred unless a human actually performs it.

## Deliverables

1. `docs/GUI_STAGE8_UX_PLAN.md` — concise plan and information architecture before implementation.
2. Implement the focused redesign described above.
3. `docs/GUI_STAGE8_UX_IMPLEMENTATION_REPORT.md` including:
   - what changed and why;
   - exact created/modified file inventory;
   - before/after navigation description;
   - actual tests and results;
   - baseline comparison and known failures;
   - known UX limitations and the manual Windows checklist;
   - explicit statement of anything not tested.

## Final instruction

Implement Stage 8 only. Preserve the current working features and repository state. Do not automatically proceed to additional features, refactor unrelated code, clean untracked files, install packages into the core environment, or commit. Finish by summarizing the main usability changes, exact test results, and the user's required manual checks.
