# AF3 Builder GUI — Final Layout Refinement Prompt (v3)

## Goal

Make a focused follow-up to the current PySide6 AF3 JSON Builder GUI. Start from the **actual current working tree**, including the workflow simplification already implemented. Do not restart the redesign or add unrelated features.

The user wants the app to feel minimal, straightforward and aesthetically pleasing. The remaining requests are:

1. Remove the visible JSON preview interface and replace any prominent Preview action with **Save JSON**.
2. Remove the persistent validation-findings section/list from Overview. Readiness should be small; warning messages must not dominate the UI.
3. Remove the oversized read-only sequence preview from the Entities workspace.
4. Make Alignment / MSA prominent and high in the selected entity's settings.
5. The entity table/list currently takes too much space. Move the *summary* of entities to Overview as a clickable summary that opens the Entities workspace. Replace the large table in Entities with a compact entity selector so entity selection/editing remains possible without a large list.
6. Give **Custom CCDs** and **Covalent Bonds** their own clearly visible, dedicated work areas inside the Entities destination. They must no longer be mixed indistinguishably into the selected entity's settings. They are job-wide configuration, not fields belonging to one selected entity.
7. Keep the existing simplified Variants and Generate workflows. Do not re-expand them into screens with every option visible at once.
8. Remove the Overview empty-state card that says to create or open an AF3 JSON to begin and contains an `Add Entity` button. This card is unwanted and must be removed completely, not merely restyled or moved. New/Open remain accessible from the existing FILE footer; entity creation belongs in the Entities workspace.

Keep the approved visual direction: dark charcoal surfaces, restrained turquoise accent, clear hierarchy, compact components, generous enough spacing, real Qt widgets, direct labels and no decorative clutter.

## Stage 0 — Inspect before editing

Inspect the current source and test baseline before touching files. At minimum review:

- `configbuilder/ui/render/qt/pages/overview.py`
- `configbuilder/ui/render/qt/pages/entities.py`
- `configbuilder/ui/render/qt/pages/advanced.py`
- `configbuilder/ui/render/qt/pages/variants.py`
- `configbuilder/ui/render/qt/pages/generate.py`
- `configbuilder/ui/render/qt/pages/preview.py`
- `configbuilder/ui/render/qt/windows/main_window.py`
- `configbuilder/ui/render/qt/state.py`
- `configbuilder/ui/render/qt/models.py`
- `configbuilder/ui/render/qt/style.py`
- `configbuilder/ui/present/strings.py`
- current GUI tests for overview, readiness, entities, advanced settings, generation, variants, navigation, launchers and strings.

Read the latest `docs/GUI_WORKFLOW_SIMPLIFICATION_REPORT.md` and any newer implementation report if present. Do not assume earlier reports perfectly describe the current tree. Record the actual current navigation, test results and changed files.

## Required design and behaviour

### 1. Overview: compact job controls, entity summary and readiness

**Job settings remain on Overview.** Do not reintroduce a separate Job Settings destination.

Keep job name, model seeds and JSON version editable on Overview through the current service-backed settings panel. Preserve Apply/refusal behaviour and default/custom indicators. Avoid duplicate implementations or cached values.

Replace the large entity table/list with a compact **Entities summary** card or group. It should show useful counts by family in plain language and one obvious action such as `Manage entities`. Clicking the summary/action must navigate to Entities. If family counts are separately clickable, they should open the same destination and select/filter the relevant family only if that can be done reliably without duplicating state. Do not invent data or activity history.

**Remove the empty-state prompt card entirely.** When no job is open, do not show the Overview card/panel that says `Create or open an AF3 JSON to begin` (or equivalent) and offers an `Add Entity` button. Do not replace it with another prominent empty-state card or another Add Entity action on Overview. New/Open are already available in the FILE footer; Add Entity belongs only in Entities, where an open job and entity context are managed. Once a job is created or opened, show the normal Overview layout. If the Overview is displayed with no open job, keep the area neutral/minimal without that card; do not disable or remove the global New/Open actions.

Remove the persistent `Validation findings` section/table from Overview entirely. Do not merely collapse it under another heading. Also remove the large readiness card/table layout and any persistent list of individual warnings.

Readiness itself may remain as a compact status line or small badge, for example `Ready` or `Not ready · 1 blocking issue`. It must be sourced from the existing validation service. Do not implement new rules or recompute readiness in the Qt layer.

If Save or Generate is blocked, users still need to understand why. Surface blocking reasons **contextually when the user attempts that action**, using a focused message/dialog with concise and actionable explanation. Do not globally display every warning all the time. Preserve navigation to the relevant field/entity if the existing finding metadata supports it. Never suppress a blocking error, bypass a validation gate or claim an operation succeeded if the service refused it.

Remove the prominent `Preview JSON` action. Replace that place with `Save JSON` only if there is no duplicate global Save button in the same visual region. Keep Save easy to find and route through the established safe save handler/service. Avoid duplicate Save buttons that compete with each other.

### 2. Entities: compact selector plus one workspace for entity and job-wide configuration

The existing entity table/list is too large for the main editing area. Remove the large table as the dominant left-side panel. **Do not remove the ability to select and manage any entity.** Replace the table with a compact searchable/drop-down entity selector at the top of the workspace (or another similarly compact, clearly labelled picker). The options must clearly distinguish IDs, family and relevant summary, including both strands of DNA duplexes and all IDs for multi-copy ligands. Keep Add Protein, Add RNA, Add DNA, Add Ligand, Edit and Delete actions easy to find.

Move a compact **entity summary** to Overview. Make it clickable to open the Entities workspace. Overview should not contain a full replacement entity table.

The Entities destination should have a simple, discoverable internal navigation structure, for example these labelled tabs/sections:

- `Entity settings`
- `Custom CCDs`
- `Covalent bonds`

Use the existing Qt layout patterns and shared style. Do not add these as new top-level sidebar destinations unless inspection shows a strong architectural reason; the user specifically asked for them to have their own place *inside Entities*.

#### Entity settings section

When an entity is selected, show its ID/family and compact relevant facts, not a large duplicated read-only sequence preview. For protein/RNA/DNA, show sequence length and a short summary if useful, but do not render the whole sequence in a large preview pane. The actual sequence remains accessible and editable in the existing Add/Edit dialog. For ligands, keep enough CCD/SMILES representation information and copy identifiers to identify the ligand.

Display settings relevant to the selected family only. Put **Alignment / MSA at the top of the settings**, immediately after the compact entity identity/summary, for protein and RNA. Keep mode and source controls together and show source/path inputs only for modes that require them. Keep protein templates immediately below MSA. PTMs/modifications should follow those groups. Do not change existing service defaults or alignment semantics. DNA must not show MSA/template controls; ligands must not show entity-level MSA/template controls. Keep descriptions and DNA partner information where relevant, but avoid a second full-length sequence display.

Preserve DNA service semantics exactly: adding DNA calls the existing service once; editing/deleting a duplex uses existing partner behaviour. Never derive complements or allocate IDs in GUI code.

#### Custom CCDs section

Create a visibly separate `Custom CCDs` area within Entities for the existing job-wide custom component definition functionality. It must be discoverable without selecting a particular entity and must say that it applies to the **whole job**. Preserve the existing mutual exclusion between inline `userCCD` and external `userCCDPath`, path/file picker behaviour, clear/reset behaviour, service refusal feedback and version-related explanation. Use the current service operations; do not assemble wire JSON in a widget.

#### Covalent Bonds section

Create a visibly separate `Covalent bonds` area within Entities for the existing job-wide linkage functionality. It must be discoverable without selecting an entity-specific settings panel and must say that bonds connect endpoints across the job's entities. Preserve the current typed endpoint model, service calls, validation and add/remove semantics. Make the endpoint controls understandable to non-programmers (entity, residue position, atom, second endpoint) and use entity choices supplied by the existing service/domain model. Do not introduce a parallel bond model or serialize `bondedAtomPairs` directly from the GUI.

Ensure the Custom CCDs and Covalent Bonds sections remain usable when there are zero entities; if a particular operation requires an entity, explain the prerequisite rather than silently doing nothing.

### 3. Save JSON and remove user-facing JSON preview

Remove the visible JSON Preview destination, redundant JSON-preview shortcut and any large raw JSON pane from ordinary navigation. Replace any primary job-action slot formerly used for preview with `Save JSON` where appropriate.

Keep the JSON generation/serialization services and internal preview method if they remain useful to the save pipeline, tests or diagnostics. Do not remove core capabilities just because their standalone visual screen is no longer desired. Do not write JSON directly from widgets. Preserve overwrite confirmation, cancellation, validation gates, atomic writing and error messages from the established save path.

**Important distinction:** keep the Generate page's **output-plan review**. It is not a raw JSON preview; it prevents users writing files before they have reviewed paths, assets, conflicts and warnings. Do not remove this safety step.

### 4. Remove persistent validation findings while retaining safety

- Remove the Overview `Validation findings` panel/table and any equivalent always-visible list from the main workspace.
- Keep only a compact readiness indication/count in the usual Overview view.
- On attempted Save/Generate, show a focused explanation of blocking issues if the service refuses the action. Messages should be concise, human-readable and specific enough to fix the problem.
- Preserve all service-side validation, report objects, severity and gates. Do not edit/remove validation rules as part of this visual request.
- Preserve warnings/conflicts in the **output plan review**, because users need them before generation.
- Update tests to prove findings are no longer persistent Overview content while invalid jobs remain blocked and the blocking explanation is available on demand.

### 5. Preserve the simplified Variants and Generate flows

Do not redesign these again except where necessary to accommodate the new simplified navigation or Save placement. Keep:

- Variants opening on the three choices (single variant, quantity series, batch from file), with only one workflow visible at a time and a clear `Back to choices` action.
- Preview-before-commit for series and file batches.
- Generate's four-step workflow: scope, destination, plan review, confirmation/execution.
- Advanced generation policies collapsed by default, with conflicts and important warnings visible during plan review.
- Stale-plan prevention and explicit confirmation before file writes.

No changes should make the pages more crowded or expose every advanced option at once.

## Visual hierarchy

- Overview: job settings, compact clickable entity summary, compact readiness. No permanent findings table, no giant readiness block, no raw JSON preview.
- Entities: compact entity picker plus clear internal areas for Entity settings, Custom CCDs and Covalent bonds.
- Entity settings: compact identity/facts → Alignment / MSA → Templates (where applicable) → PTMs → other relevant details.
- Custom CCD and bond tools are job-wide and labelled as such, clearly separated from selected entity settings.
- Use a single shared style/spacing system in `style.py`; do not scatter ad-hoc styles across pages.
- Preserve readable behaviour when the window is small; use scroll areas, sensible minimum sizes and layouts that do not clip key buttons.
- Ensure every important operation has a visible text label; do not rely solely on icons, tooltips or right-click menus.

## Architecture and safety constraints

- Preserve all pre-existing and uncommitted user work. Do not reset, stash, clean, revert, restore or commit.
- Reuse existing app services as the authority for configuration mutations, validation, ID allocation, variant state, generation, JSON encoding and file writes.
- Do not create a second configuration state or duplicate domain rules in the GUI.
- Do not change biological semantics, JSON schema, defaults, serialization ordering, output planning or validation policy to make a UI change easier.
- Do not remove or weaken tests to get a green suite.
- If inspection shows a requested change cannot be done safely through existing services, document the gap and propose the smallest service-level addition before implementing it. Do not silently mutate domain records directly.

## Tests to update/add

Add or update real widget/service-backed tests for:

1. Overview contains editable job settings, a compact clickable entity summary and compact readiness.
3. With no open job, the unwanted `Create or open an AF3 JSON to begin` card and its `Add Entity` button are completely absent; New/Open remain available from the FILE footer.
3. Overview has no persistent Validation findings section/table or raw JSON preview action.
4. Clicking Manage entities from the summary navigates to Entities.
5. Entity selection remains functional using the compact selector for all supported families, imported lone-strand DNA, DNA duplexes and multi-copy ligands.
6. Entities does not show a large full-sequence preview; Add/Edit sequence remains functional.
7. Alignment/MSA appears before templates and PTMs for protein/RNA; irrelevant controls stay hidden for DNA and ligands.
8. Custom CCDs have a dedicated, visible sub-area and continue to use existing service calls and `userCCD`/`userCCDPath` exclusion.
9. Covalent bonds have a dedicated, visible sub-area and continue using existing service calls/endpoint choices.
10. Custom CCD and bond areas can be opened with zero entities; operations that require entities explain the prerequisite.
11. Blocked Save/Generate remains blocked and gives concise reasons on demand, despite removing the permanent findings list.
12. Save uses the existing safe service path and respects overwrite/cancel behaviour.
13. The Generate plan review remains and still exposes conflicts/warnings before writing files.
14. Variants and Generate guided flows still pass their existing regression tests.
15. Existing architecture, strings, launcher, entity, PTM, alignment, template, custom CCD, bond, generation, persistence and golden-serialization tests continue to pass.

Run and report these commands (adjust shell syntax only if needed for the actual environment):

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv-gui\Scripts\python.exe -m pytest -o addopts="" -q tests/gui
python -m pytest -o addopts="" -q tests/architecture
python -m pytest -o addopts="" -q
python gui.py --help
```

Record exact results and compare full-suite failure node IDs with the current baseline. Identify known baseline failures separately from newly introduced failures. Do not claim manual display verification from offscreen tests.

## Manual Windows acceptance checklist

Include these items in the implementation report:

- Overview has job settings, a compact clickable entity summary and a compact readiness status only; no permanent findings table and no JSON preview button.
- With no job open, the `Create or open an AF3 JSON to begin` Overview card and its `Add Entity` button are completely absent; New/Open remain available in the FILE footer.
- Save JSON is easy to find and works via the safe save flow.
- Clicking the entity summary opens Entities.
- Entities has a compact entity selector; switching among protein, RNA, DNA duplex/lone strand and ligand updates the editor correctly.
- No oversized read-only sequence preview appears; sequence editing still works.
- Protein/RNA Alignment/MSA is immediately visible near the top; templates and PTMs are below it.
- Custom CCDs have a dedicated section and can be managed without selecting an entity.
- Covalent Bonds have a dedicated section and can be managed without hunting through entity fields.
- Custom CCD and covalent-bond areas remain understandable for an empty job.
- Variants stays guided and Generate retains plan review, warning/conflict visibility, confirmation and cancellation.
- Save/reopen round-trip works and output JSON remains unchanged in schema/order for the same configuration.
- Resizing and keyboard navigation remain usable.

## Deliverable and stop condition

Create `docs/GUI_FINAL_LAYOUT_REFINEMENT_REPORT.md` (replace/update the existing report only if appropriate; keep prior evidence/history if useful). Include:

- Before/after description for every requested change.
- How the Overview entity summary navigates to the compact entity picker/editor.
- The layout and scope of the Custom CCDs and Covalent Bonds areas.
- Exact files created/modified and why.
- Tests run, exact results, and baseline comparison.
- Any service/API gap or remaining limitations.
- Explicit separation between automated checks and manual visual checks.

Implement only this refinement. Do not start packaging work, new scientific features or another broad redesign. Stop after the report is complete and wait for review.
