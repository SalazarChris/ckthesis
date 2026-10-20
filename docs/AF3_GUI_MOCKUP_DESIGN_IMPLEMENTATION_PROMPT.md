# AF3 JSON Builder GUI — Implement the Approved Conceptual Mockup

## Objective

Redesign the existing PySide6/Qt Widgets application to match the conceptual interface mockup the user approved in ChatGPT. The mockup is a **design reference**, not an asset to embed. Recreate its structure and visual character using native Qt widgets and the existing application architecture.

The desired product is a polished scientific desktop workbench: calm, precise, easy to navigate, visually cohesive, and usable by someone who does not know the internal Python architecture.

This is a UX/layout redesign of the existing functioning application—not a rewrite of the builder.

## First: inspect the current repository

Before editing files:

1. Read the latest GUI implementation reports, especially the Stage 7 final UX/release report and Stage 8 UX simplification report if present.
2. Inspect the actual current Qt pages, `MainWindow`, style layer, string registry, launcher scripts, service/state layer, GUI tests, and current `git status`.
3. Run targeted baseline tests and record the exact existing failures. The historical report recorded 13 stale terminal-menu end-to-end failures; verify whether they are still the current baseline rather than assuming.
4. Preserve all pre-existing user changes. Do not reset, clean, stash, revert or commit. Do not overwrite untracked files.
5. Produce a brief current-state-to-target mapping, then implement only the changes needed for the approved design. Do not stop at a plan unless there is a genuine blocker or a destructive/contract-level decision requiring the user.

## Approved target layout

### 1. Main application shell

Replace the crowded horizontal row of primary tabs with a **left navigation sidebar** and one central workspace.

Primary destinations, in this order:

1. **Overview**
2. **Entities**
3. **Variants**
4. **Generate**
5. **JSON preview**

The separate **Job Settings** top-level tab must be removed because job-wide settings are already editable on Overview. Do not remove the underlying service operations or settings functionality; Overview becomes their single normal home.

Create a restrained top application header with:

- Product name: **AF3 Builder**
- A small subtitle such as “Molecular input workspace”
- Current job name where a job exists
- A clear visible unsaved-change indicator
- Global **New Job**, **Open AF3 JSON**, and **Save JSON** actions in a sensible toolbar/menu arrangement

Keep familiar File menu behaviour. Global actions must not appear redundantly in multiple prominent locations. Ensure the interface does not become cramped at the current default window size.

### 2. Visual design system

Use the mockup's dark scientific-workbench style as the default visual target.

Suggested design tokens (adjust only where Qt/platform accessibility requires it):

- Main background: `#171B22`
- Raised panel/surface: `#222A34`
- Sidebar surface: `#1C222B`
- Primary accent: muted turquoise `#75D6D0`
- Main text: `#D7E0EA`
- Secondary text: `#9AA8B8`
- Borders/dividers: `#394351`

Rules:

- Keep the look restrained and professional; no gradients, animations, glossy effects, excessive cards, or decorative clutter.
- Use a consistent spacing scale around 4/8/12/16/24 px.
- Use consistent typography hierarchy: page title, section heading, field label, secondary/helper text.
- Use consistent control height, button padding, table row height, corner radius and border treatment.
- Prefer filled accent styling only for the primary action of a page. Secondary actions should be quieter.
- Validation states must be understandable by words and icons as well as colour; do not communicate status through colour alone.
- Make focus indication visible. Maintain readable contrast, including secondary labels and disabled controls.
- Reuse/refine the existing central `style.py` rather than scattering page-specific QSS.
- Keep all user-facing fixed text in the existing string registry if that remains the repository's established rule. Do not exempt files merely to bypass wording tests unless the file genuinely contains non-user-facing styling syntax.
- Do not add another GUI framework or large UI dependency.

### 3. Overview — job control centre

Overview should be the first page and the single normal home for job-wide settings.

At the top:

- Page title such as **Prepare your AF3 job**
- One short sentence explaining the page
- Inline editable job name
- Model seeds
- JSON version
- Make existing defaults and custom values visible and understandable
- Preserve explicit Apply/commit semantics if that is how the current service-backed editor works; do not introduce unsafe live mutations while typing

Below settings, show compact summary blocks for:

- Total entities and counts by family
- Readiness state

Then show:

- An actionable readiness/next-step area highlighting blocking issues first
- A concise validation findings area
- A clear way to select a finding and navigate to the entity/field it identifies when supported
- Links/actions to the main next steps when the user has no entities or a blocking finding

Do not reproduce the current large, dense status table as the visual centre of the page. Summarize routine states compactly and retain detailed findings in a table/list that can scroll or expand. Do not drop service-provided information.

Remove the separate Job Settings navigation destination and update all tests and user-facing documentation that depend on the old tab count.

### 4. Entities — one coherent editing workspace

Use a split layout similar to the mockup's professional editor:

- Entity list/table on the left
- Selected entity's details and settings on the right
- Visible, labelled **Add Protein**, **Add RNA**, **Add DNA**, **Add Ligand**, **Edit**, and **Delete** actions in a sensible toolbar/action row
- Selection and detail area remain visually connected; the selected entity must be obvious

For the selected entity, make related options discoverable in one workspace:

- Sequence or ligand representation
- Description where supported
- PTMs/modifications
- MSA controls where applicable
- Templates for proteins where applicable
- DNA duplex partner information
- Relevant advanced options

Use clearly named sections, inner tabs, or expanders only where they improve clarity. Do not hide routine MSA/PTM/template controls behind an unrelated top-level page. Hide or disable controls that do not apply to the selected entity family and explain why where useful.

Keep job-wide custom CCD definitions and covalent bonds clearly marked as **Whole job** settings because they do not belong to a single entity. Avoid presenting them as though they modify only the selected record.

Retain all existing safeguards around DNA duplex creation/edit/deletion, multi-copy ligands, identity allocation and service refusal feedback.

### 5. Variants — make the workflow obvious

The landing view should begin with three clearly explained options, not a dense panel of advanced controls:

1. **Create a variant** — manually describe changes relative to the base job
2. **Create a quantity series** — create planned levels/amounts with preview
3. **Create variants from a file** — import sequences or SMILES as supported

Below or alongside those actions, show existing variants in a clear table with understandable names/labels, declared changes and validation status.

Each creation workflow should guide the user through:

1. Choose the workflow
2. Enter only the inputs needed for that workflow
3. Preview proposed variants/changes
4. Validate and show clear errors/warnings
5. Confirm creation

Requirements:

- Make the base job and its variants visually distinct.
- Avoid exposing Python type names, edit-class names or internal service vocabulary to the user.
- Use the existing `VariantService` operations and typed edit options. Do not invent a second variant engine in widgets.
- Quantity series must show the planned result before commit.
- File batch must inspect/preview before commit and preserve all-or-nothing behaviour.
- Keep cancellation safe and ensure a preview does not mutate state.
- Do not silently change the base job when editing or generating a variant.

### 6. Generate — simplify output generation to a guided process

The Generate page should not display every output policy and every plan table as an equally prominent control at once.

Use a clear four-step experience:

**Step 1 — Choose what to generate**
- Base job, selected variants, or all variants, but only offer choices supported by the current generation services.
- Explain the selected scope in plain language.

**Step 2 — Choose destination**
- Use a directory picker.
- Show the selected path clearly and make long paths readable/copyable.

**Step 3 — Review the output plan**
- Show the planned folder/file structure, assets, manifest, conflicts and important warnings.
- Group detail sensibly and make it easy to inspect.
- Conflicts must be visible before confirmation.

**Step 4 — Confirm generation and inspect results**
- State clearly what will be created and where.
- Require confirmation before writing files.
- Show success/failure results per file or output item as supported.
- Preserve cancellation and overwrite policy semantics.

Put less-frequently-used output/path/overwrite settings inside a labelled **Advanced options** section, collapsed by default only if the defaults are safely visible and the choices are still discoverable. Never hide active conflicts, blocking failures or warnings required for an informed decision.

Do not write JSON, assets or manifests directly from the UI. Reuse the existing planning and execution pipeline and preserve atomicity, conflict handling, path policies and emitted bytes.

### 7. JSON preview

- Keep a clearly read-only preview of the exact normalized/generated JSON from the existing service.
- Use a comfortable monospace font and sensible padding.
- Preserve the distinction between an imported file's original formatting and the builder's output representation.
- Show the service's refusal reason if a preview cannot be generated.
- Keep copy/refresh actions labelled and discoverable.
- Do not implement another JSON serializer or silently alter content for display.

### 8. Responsive layout and interaction

- Sidebar and central content must resize sensibly; it must not consume excessive width.
- Overview and Generate should scroll instead of clipping their content at shorter window heights.
- Entity split-panel proportions should remain useful when resizing or maximizing.
- Use sensible minimum widths/heights, table column sizing and wrapping for long messages and paths.
- Ensure all visible actions have keyboard-accessible focus and clear labels; test reasonable tab order.
- Avoid icon-only primary actions. Icons can support text labels but must not replace them.
- Destructive actions require clear confirmation; Cancel must remain safe.
- Do not introduce persistence of UI state or autosave unless specifically justified and documented.

## Architecture and correctness constraints

- Preserve the service/domain/serialization separation.
- Route all mutations through existing services (or a reviewed minimal service-layer addition where genuinely required).
- Do not generate IDs, reconstruct wire dictionaries, recalculate validation policy, or serialize JSON in widgets.
- Do not sort/reorder the underlying configuration records for presentation purposes.
- Preserve the core package's no-PySide6 dependency contract; PySide6 stays in the GUI extra.
- Preserve `python gui.py`, `python gui.py --demo`, path forwarding, `python af3builder.py`, and the existing CLI.
- Preserve PTM positional conventions, DNA duplex semantics, ligand CCD/SMILES exclusivity, version constraints, variant drift checks, and generation conflict policies.
- Do not silently “fix” unrelated behaviour or delete/weaken tests to get green results.
- Keep every unrelated pre-existing modified/untracked file intact. No reset, clean, stash, revert, checkout, or automatic commit.

## Implementation sequence

1. Inspect current implementation and test baseline; write a brief proposed mapping from current screens to target screens.
2. Implement the left sidebar/main shell and remove the redundant Job Settings tab, moving nothing out of the service layer.
3. Apply the cohesive styling layer and polish Overview.
4. Refine the Entities split workspace and its advanced settings discoverability.
5. Simplify Variants into the three guided starting choices and preview/confirm flows.
6. Simplify Generate into the four-step process while preserving the existing plan/confirm/execute pipeline.
7. Refine JSON Preview and global actions.
8. Update affected tests, strings and `RUNNING_THE_APPLICATION.md` (or the currently authoritative application guide).
9. Run targeted GUI tests, architecture tests, launcher tests, string-registry tests, and the full suite. Compare failing test IDs to the baseline captured at the start.
10. Run launcher smoke checks. If a real desktop is available, inspect at default/maximized sizes; otherwise state clearly that visual checks remain for the user. Do not claim a real-display test if only offscreen Qt was used.

## Acceptance criteria

- Navigation matches the five destinations and no separate Job Settings tab remains.
- Job settings are editable from Overview and the existing settings service behavior is preserved.
- Overview is visually compact: settings, summary, readiness and findings have clear hierarchy without losing findings.
- Entity selection, details and relevant advanced settings are in one coherent workspace.
- Variants have three obvious entry points and each uses preview/validation/confirmation appropriately.
- Generate follows choose scope → destination → review plan → confirm/execute/results.
- JSON preview still reflects the existing service output exactly.
- Visual styling is consistent across main pages and dialogs, using the agreed dark-charcoal/turquoise design direction with readable contrast.
- All changed workflows have automated regression tests; test failures are reported honestly and compared with baseline.
- Launchers and CLI remain functional, and core import/runtime does not require PySide6.
- The report distinguishes verified automated behaviour from visual checks not performed on a real Windows desktop.

## Deliverables

Create `docs/GUI_MOCKUP_DESIGN_IMPLEMENTATION_REPORT.md` containing:

1. Current state and baseline test results before changes.
2. Files created and modified.
3. Description of how each target screen was implemented.
4. Test commands and exact results.
5. A before/after behaviour summary.
6. Known limitations and any design trade-offs.
7. A concise manual Windows acceptance checklist.

Implement the redesign, run the verification that is available, produce the report, and stop. Do not proceed to unrelated new features after this task.
