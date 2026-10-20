# AF3 Builder — Workflow Simplification and Entity Workspace Refinement

## Mission

Refine the existing AF3 JSON Builder GUI so it follows the user's approved dark scientific-workbench visual direction while being simpler, less crowded, and easier for a non-programmer to understand.

This is a **focused UX redesign of existing functionality**, not a new feature stage and not a rewrite of the application. Inspect the current repository and the latest implementation reports before editing anything. The UI may have changed since earlier reports, so verify what is actually present rather than relying on old descriptions.

## User's explicit feedback

1. The standalone **JSON Preview** navigation/action is redundant. The user does not need a separate screen just to inspect raw JSON. Keep the ability to save valid AF3 JSON files; remove the redundant user-facing preview destination and any duplicate preview shortcuts. Do not remove or rewrite core serialization, generation, or validation services. Preserve internal preview functionality where needed by existing logic or tests unless evidence shows it is safe and appropriate to remove.
2. **Generate & Output** is too cramped and exposes too many options simultaneously. Make it a guided, straightforward process with progressive disclosure.
3. **Variants & Batch** is not intuitive and exposes too many options at once. Start from a small number of clearly described actions and reveal only the relevant form for the chosen workflow.
4. The **Entities** workspace has an oversized preview area that is unnecessary. Keep the useful selected-entity details, reduce or remove the oversized/duplicated preview, and make advanced settings available in the same entity workspace. Do not make users navigate to a separate top-level destination to find entity-specific MSA, templates, or PTMs.
5. Keep the overall approach minimalistic and straightforward. Use the existing visual-reference direction: charcoal/dark surfaces, restrained turquoise accent, consistent spacing and typography, readable controls, clear headings, and no decorative clutter.

## Phase 0 — Audit before changes

1. Read the current GUI code, `gui.py`, `af3builder.py`, the current design stylesheet, the latest Stage 5/6/7/8 or visual-reference implementation reports that exist, and relevant GUI/service tests.
2. Inspect the actual current main navigation, Entities workspace, Variants page, and Generate page. Map every visible control to the action/service it invokes.
3. Capture the current test baseline before editing:
   - Full GUI suite using the established GUI virtual environment and `QT_QPA_PLATFORM=offscreen`.
   - Architecture tests.
   - Launcher and string-registry tests.
   - Full core suite with the normal core interpreter.
4. Record the current failing test IDs and test counts. Treat the known CLI end-to-end failures as baseline only if the current run confirms that the exact failures remain.
5. Inspect `git status` and preserve all modified and untracked work. Do not reset, clean, stash, revert, or commit anything. Do not overwrite unrelated user work.
6. Write a brief implementation map in the final report. Do not stop at the audit; proceed with the focused work below unless a genuine blocker requires a human decision.

## Phase 1 — Simplify navigation and remove the redundant JSON Preview destination

### Required behaviour

- Remove the standalone **JSON Preview** top-level navigation item and its redundant navigation flow.
- Remove any Overview/toolbar shortcut whose only purpose is opening that same raw JSON preview, unless the audit demonstrates a distinct essential use. Do not remove the primary **Save JSON** action.
- Keep JSON generation and serialization under the existing service/serialization layer. The GUI must never hand-assemble the wire JSON or write JSON directly.
- Preserve validation feedback and the existing safe save path. Users must still understand why saving/generation is blocked without needing to inspect raw JSON.
- If JSON Preview is referenced by tests or service behaviour, update tests only to reflect the intentional removal of the user-facing screen. Do not delete useful tests for serialization correctness, byte determinism, or preview/service behaviour that remains relevant internally.
- Reassign any remaining navigation space logically; do not leave an empty tab, blank panel, or dead action.

### Navigation target

Use a compact left sidebar consistent with the approved mockup. Prefer these primary destinations, adapted to what actually exists:
- Overview
- Entities
- Variants
- Generate

New/Open/Save should stay easy to find through a consistent top toolbar or File menu. Do not create duplicate destinations for the same settings. If a separate Job Settings destination still exists while those settings are editable on Overview, remove that redundancy as part of this focused cleanup unless the current implementation has a documented reason to retain it.

## Phase 2 — Make the Entities workspace compact and complete

### Target layout

Use a simple master/detail workspace:
- **Entity list:** compact table/list with identifier(s), entity family, and a short useful summary. Keep Add, Edit, and Delete actions visible and labelled.
- **Selected entity panel:** displays useful details without a huge, duplicated preview area.
- **Advanced settings in context:** make PTMs/modifications, MSA/alignment settings, and protein templates directly accessible in the selected entity's workspace. Use clear internal tabs, collapsible sections, or a compact section layout; choose the option that best fits the existing widgets and keeps important settings discoverable.
- **Job-wide settings:** custom CCD definitions and covalent bonds apply to the job rather than only the selected entity. Keep them clearly marked as job-wide and accessible from the same general workspace, without misleadingly attaching them to one chain.

### Specific requirements

- Remove or substantially reduce the oversized preview/summary area called out by the user. Do not remove fields required to understand or edit the selected entity.
- Do not display the same long sequence or representation redundantly in multiple large widgets. A concise details view is sufficient; the actual editor remains available through a clearly labelled control or inline form.
- Do not make MSA/templates/PTMs discoverable only by switching to an unrelated top-level tab.
- Show controls conditionally by entity family: for example, protein MSA and templates for proteins, supported alignment options for RNA, and no irrelevant alignment/template controls for DNA or ligands.
- Keep DNA duplex semantics, service-owned identifier allocation, ligand CCD/SMILES exclusivity, multi-copy behaviour, and current validation intact.
- Keep all mutations routed through the existing application services. Never mutate domain records directly in widget code.
- Retain selection and refresh the table, selected details, readiness/findings, dirty status, and save/generation eligibility after successful operations.

## Phase 3 — Simplify Variants & Batch

The current page must not present every variant operation as a large wall of controls. Use progressive disclosure.

### First screen

Show a short introduction and no more than these three primary, clearly labelled starting choices (rename only if a better plain-language label fits the code's actual feature):

1. **Create one variant** — make one defined change to a copy of the base job.
2. **Create a quantity series** — vary a supported quantity over several levels.
3. **Create variants from a file** — use a sequence/SMILES input file to create multiple variants.

Use labelled buttons/cards with a brief description. Avoid icon-only actions and avoid exposing all subordinate inputs before the user chooses a path.

### Workflow after choosing

- Show only the controls relevant to that choice.
- Use plain-language labels; keep internal class names and technical edit vocabulary out of the normal user-facing flow where an existing friendly description is available.
- Keep explicit base-job/variant distinctions visible.
- Preview the intended changes or generated variant list before committing changes.
- For quantity series, show the planned levels/count before creation.
- For file batch, select a file, inspect/preview the parsed inputs and planned variants, and only then confirm creation.
- Keep existing cancellation, all-or-nothing batch behaviour, base immutability and variant drift/validation safeguards.
- Show existing variants in a compact table with name/key, concise description of changes, and validation status where supported. Put edit/remove/duplicate actions where they are discoverable but do not dominate the initial screen.
- Make it clear how to return to the variants list or cancel a wizard without committing changes.
- Do not invent new variant types or duplicate variant/business logic in the GUI.

## Phase 4 — Simplify Generate & Output

The Generate page currently feels cramped and too configurable at once. Restructure it into a focused, guided flow that preserves the existing plan/review/confirm/execute/result safety sequence.

### Suggested four-step flow

**Step 1: What do you want to generate?**
- Offer only supported choices based on the existing services: base job, selected variants, or all variants as appropriate.
- If a choice is impossible in the current state, disable it with a short explanation rather than offering a broken path.

**Step 2: Where should the files go?**
- Make the destination folder the main control, with a Browse button/file picker.
- Display the selected destination in a readable, selectable way; avoid letting a long path crush the layout.

**Step 3: Review the plan**
- Show a clear summary of what will be written and where.
- Show conflicts, warnings, skipped files, assets/resource handling, and any blocking problem before execution.
- Distinguish blocking conflicts from non-blocking information with both text and visual cues.
- Keep the plan based on the existing `GenerationService`/output planning objects. Do not invent a parallel planning engine.

**Step 4: Generate**
- Provide an explicit final action, then display success/failure results and useful output locations.
- Keep Cancel/Back actions clear and safe.
- Never write files before the user reaches the final confirmed action.

### Advanced options

- Move less-common existing choices—such as overwrite policy and resource/path handling—to a collapsed **Advanced options** section.
- Keep defaults visible or explain where they come from, and never silently change the existing service defaults.
- Keep conflicts and safety-relevant warnings visible even when Advanced options is collapsed.
- Do not remove valid capabilities merely to make the screen look simpler. Use progressive disclosure instead.
- Keep path-copy functionality useful, but do not add extra buttons that repeat the same action.

## Phase 5 — Visual consistency and usability

- Preserve and refine the existing shared stylesheet rather than adding scattered one-off styles or a new framework.
- Use restrained colour, consistent typography, clear group headings, moderate corner radii, aligned field labels, useful whitespace, and consistent button sizing.
- Minimize nested bordered groups/cards. Use a card only when it separates a meaningful task or information group.
- Avoid giant unused panels, tiny crowded controls, excessive explanatory paragraphs, and decorative elements that consume workspace.
- Make primary actions visually prominent but don't style every button as primary.
- Ensure the layout works at the normal window size and when maximized or resized; use splitters and scroll areas where justified.
- Preserve keyboard accessibility, focus visibility, labelled buttons, tooltips for genuinely non-obvious options, and readable long paths/sequence data.
- Do not fabricate recent activity, counts, saved state, success messages or other data. All displayed data must come from the current project or be labelled as explanatory sample/demo data.
- Match the reference mockup's visual language where practical, but favour clarity and actual usability over pixel-perfect replication that would cramp real forms.

## Architecture and data-integrity constraints

- Do not change the AF3 JSON contract or biological/domain rules as part of this UX task.
- Do not reimplement validation, readiness, identity allocation, variant expansion, output planning, serialization, or file writing in Qt widgets.
- Continue to call existing service methods and display their result messages.
- Do not reorder the underlying `configuration.records` merely to sort the visible entity list.
- Do not silently upgrade JSON versions, drop settings, or change defaults.
- Keep `python gui.py`, `python gui.py --demo`, JSON-path launching, and `python af3builder.py` working.
- Keep the core package runnable without PySide6.
- Do not add dependencies unless strictly necessary and justified.
- Do not install packages into the core environment without need.

## Testing requirements

Add or update tests for the intentional UX changes:

### Navigation
- JSON Preview is no longer a top-level GUI destination and no duplicate raw-preview shortcut remains.
- Save JSON remains discoverable and uses the existing save path.
- No dead navigation entry or blank page remains.
- Duplicate Job Settings navigation is removed if Overview already owns those controls.

### Entities
- The selected-entity workspace contains Details and the applicable advanced controls in-context.
- The oversized/duplicated preview is removed or meaningfully reduced.
- Selecting different entity families updates which settings are enabled/shown.
- Existing add/edit/delete, DNA duplex, ligand multiplicity, PTM, MSA, template, component, bond, validation, refresh and dirty-state tests continue to pass.

### Variants
- Initial screen presents the three primary choices without all workflows expanded at once.
- Each choice leads to the correct existing service workflow.
- Cancel returns without committing.
- Previews match the intended operations; the base remains unchanged.
- Batch remains all-or-nothing; quantity series creates exactly the reviewed plan.

### Generate
- Initial screen is not overcrowded; advanced options are collapsed by default if appropriate.
- Existing plan, conflicts, warnings and resource handling are shown before execution.
- Cancel/back never writes files.
- Confirm invokes the existing execution service exactly once.
- Output bytes and manifests remain consistent with service-level golden/contract tests.

### Regression
- Run the GUI suite using the established GUI environment and `QT_QPA_PLATFORM=offscreen`.
- Run architecture tests, launcher tests, string-registry tests and relevant app/output/variant service tests.
- Run the full core test suite in the established core interpreter.
- Compare current failing test IDs with the baseline captured before edits. Report new failures separately; do not weaken tests or delete baseline failures to claim success.
- Run launch smoke tests for the GUI launcher, `--demo`, a supplied JSON path, and the CLI launcher where practical.

## Required outputs

1. Implement the focused UX refinements in the existing application.
2. Create `docs/GUI_WORKFLOW_SIMPLIFICATION_REPORT.md` with:
   - what changed and why;
   - exact files created/modified;
   - before/after navigation outline;
   - screenshots, if the environment can genuinely capture them;
   - exact test commands and results;
   - baseline versus current failure comparison;
   - known limitations and a short manual Windows test checklist.
3. Do not claim a real-display visual check if all execution was offscreen. State clearly what still requires the user to check on Windows.
4. Stop after this scope is complete. Do not begin unrelated features, broad refactors, packaging, or analysis-pipeline changes.

## Manual acceptance checklist for the user

The report must include a concise checklist for:
- Open the GUI; confirm there is no JSON Preview navigation and Save remains easy to find.
- Add/select a protein; inspect Details and find PTMs, MSA and templates in the same workspace.
- Select DNA and ligand; verify irrelevant controls are not presented as applicable.
- Create one variant, a quantity series, and a file batch; verify each starts from a simple choice and provides a preview/confirmation.
- Generate to a temporary directory, inspect the plan/conflicts, cancel once and confirm no files are written; then generate successfully.
- Resize/maximize and verify spacing, labels and long paths remain readable.
- Confirm `python gui.py`, `python gui.py --demo`, and `python af3builder.py` still work.
