# AF3 Builder — Visual Reference Match and Minimalist Refinement

## Task

The earlier GUI redesign prompt has already been run. This is a **follow-up visual-fidelity pass**, not a request to rebuild the application or add a new feature stage. Use the supplied image `af3_builder_overview_reference.png` as the primary visual reference and adapt the existing PySide6/Qt Widgets application to match its layout, spacing, hierarchy and visual language as closely as practical.

The reference is a design target, not a source of biological rules or literal sample data. Prefer a clean, minimal, straightforward application. Add UI details only when they make a real task easier to understand or complete.

## Reference image setup

The user should place the supplied PNG in the repository at:

`docs/ui_reference/af3_builder_overview_reference.png`

If the image is supplied through the coding environment as an attachment instead, use that attached image. Do not assume the ChatGPT `/mnt/data` path exists on the user's machine. If no image is accessible, stop and ask for it rather than guessing that a screenshot was inspected.

## Mandatory first steps

1. Inspect the **current** repository, not earlier reports alone. Read the current GUI implementation, shared stylesheet, navigation, Overview, entity editor, variants workflow and output workflow.
2. Inspect the reference image and compare it to the actual current GUI. Write a short mismatch list before changing code.
3. Check the current Git status and preserve every pre-existing user modification. Do not reset, clean, stash, checkout, restore, rebase, amend or commit. Do not overwrite unrelated files.
4. Run and record focused baseline tests before editing. Distinguish the already-known legacy CLI end-to-end failures from any new failures.
5. Implement only this visual-refinement task. Do not add biological functionality or redesign service/domain logic.

## Visual direction

Reproduce the visual qualities of the supplied reference:

- A restrained dark scientific-workbench theme: deep charcoal/navy background, slightly lighter panels, subtle borders, readable off-white text and a muted turquoise/cyan accent.
- A stable left navigation rail with a small product identity at the top and clearly labelled destinations.
- A compact top bar with the current job name, an unsaved-changes indicator and common file actions.
- Clear page heading and one short explanatory sentence.
- Consistent spacing, alignment, typography, field heights, table row heights, border radii and button treatment.
- Information grouped in a small number of purposeful panels; avoid a border/card around every trivial label.
- Status labels that use words/icons as well as colour. Make keyboard focus and disabled states visible.
- Useful scrolling and sensible resizing. Do not rely on a fixed 1536×1024 window.
- Professional and minimal, not flashy: no decorative animation, visual clutter, excessive colours, gradients everywhere or extra frameworks.

Use the existing central Qt stylesheet/theme mechanism if one exists. Consolidate styling rather than adding unrelated per-widget stylesheets across pages. Preserve platform-native accessibility and normal Qt keyboard behaviour.

## Main-window navigation

Target these primary destinations:

1. Overview
2. Entities
3. Variants
4. Generate
5. JSON Preview

Use left-side navigation rather than the existing horizontal tab strip if this can be done cleanly in the present architecture. File actions such as New, Open and Save should have **one clear primary location** (preferably the top bar/File menu); do not duplicate the same commands in both the sidebar and toolbar just because they appear twice in the reference image.

Remove the separate top-level Job Settings destination if the same job settings are already editable on Overview. There should be one authoritative settings implementation and no confusing duplicate route. Reuse existing widgets/services; do not create competing settings state.

Do not remove working actions or break keyboard navigation. If replacing top-level tabs with a sidebar requires a significant architectural change, explain the smallest safe approach and implement it incrementally rather than rewriting the app.

## Overview page — match the reference closely

Use a responsive dashboard layout with these roles:

### Main column
- **Job settings panel:** editable job name, model seeds and JSON version, using the existing application services and existing default/automatic/custom indicators. Include only concise help text. Make version-feature incompatibilities visible before save/generation where the existing services provide enough information.
- **Compact entity summary:** total entity count and counts by the builder's actual supported families.
- **Readiness panel:** show the service's actual readiness verdict and blocking count. A clear action should lead to the corresponding actionable finding.
- **Validation findings:** show the most relevant findings without forcing a tall table on every launch. Include a clear way to view all findings and navigate to the related entity/field where supported.
- **Quick actions:** only meaningful, real actions (for example Add entity, Validate, Preview JSON, Save JSON), with one visually primary action. Do not provide duplicate actions that already have equally prominent buttons elsewhere.

### Secondary column or responsive supporting area
- A compact job summary (name, seeds, version, dialect, counts).
- Optional help or context only when it is real and useful.

### Accuracy rules
- Use the reference's composition and density, but **never hard-code** the example job name, ten seeds, version, counts, time stamps or validation finding.
- Derive every displayed value from the real current project/services.
- Do not show fictitious “Recent activity”, timestamps, user identity, execution status or project history unless the current application genuinely tracks that information. Omit the Recent activity panel if there is no real activity model; do not invent a history subsystem in this task.
- Do not present ion as a separate AF3 entity family. Follow the existing builder contract: ions are represented as ligand CCD codes. The summary may explain this if useful, but counts and labels must be accurate.
- Do not call a job “ready” based on UI heuristics; use the existing validation/readiness service.
- Ensure no redundant Job Settings top-level tab remains if Overview now contains the same editable fields.

## Other pages — apply the same design language

This task is not a full workflow rewrite, but the primary pages must look like parts of the same application.

### Entities
- Keep the entity list and selected-entity editor in one workspace, with clear selection state.
- Keep related entity settings discoverable in context: sequence/representation, descriptions, PTMs, MSA and templates as relevant to the selected family.
- Distinguish entity-specific settings from whole-job settings (such as root-level custom CCD definitions and cross-entity bonds).
- Avoid forcing users to visit unrelated top-level tabs to find settings for the selected entity.

### Variants
- Preserve existing working variant functionality.
- Make the three entry choices easy to understand: create a variant, create a quantity series, or create variants from a file.
- Keep explanatory text short. Show advanced or uncommon controls only when relevant to the chosen path.
- Clearly distinguish the base job from variants and preview edits before committing where supported.

### Generate
- Preserve the existing generation plan → review → confirm → execute → result sequence.
- Present the workflow as four clear steps: choose the base/variants, choose destination, review the output plan/conflicts, confirm generation and show results.
- Place uncommon overwrite/resource policy controls under a clearly labelled Advanced options section, retaining their actual defaults.
- Never hide blocking conflicts or warnings; do not simplify by removing safety checks.

### JSON Preview
- Keep the preview read-only and show the exact output from the existing generation/serialization service.
- Use readable monospace text, sensible padding and horizontal/vertical scrolling.

## Engineering constraints

- PySide6 / Qt Widgets only; do not add a new GUI framework.
- Preserve the existing application services, model, validation rules, identity allocation, output planning and serializer.
- Never assemble AF3 wire JSON directly from widgets.
- Never invent mock/sample data for a real project. Demo data may only appear in the explicit demo mode.
- Preserve `python gui.py`, `python gui.py --demo` and `python af3builder.py`.
- Keep the core usable without PySide6 installed.
- Maintain Python compatibility promised by the existing project configuration.
- Keep user-visible text in the current string registry if the architecture requires it.
- No unrequested biological rules, default changes, new persistence, or activity logging.
- No silent file overwrites, no automatic version upgrades, and no hidden mutation during rendering or refresh.
- Do not weaken/delete existing tests to make them pass. Record known pre-existing failures separately.

## Required testing

Add or adapt tests for:

1. Sidebar navigation reaches the correct actual page and each page can be opened without exception.
2. No duplicate top-level Job Settings page remains when settings are on Overview.
3. Overview fields read and write through the existing service; readiness and counts are service-backed.
4. Empty, valid and blocking-job states display correctly.
5. Job title/unsaved marker and common file actions remain correct.
6. Entity selection and entity advanced settings still correspond to the selected registry record.
7. Variant create/preview/cancel behaviour remains unchanged.
8. Output planning, conflicts, cancellation and execution remain safe and unchanged.
9. JSON preview still matches the existing service output exactly.
10. Existing launcher, architecture, string-registry and core tests remain intact.
11. Layout remains usable at different window sizes in Qt offscreen tests where testable.

Run the GUI tests in the GUI environment and the core suite in the core environment, because the core is intentionally allowed to omit PySide6. Compare full-suite failure node IDs with the baseline before reporting regressions.

## Visual acceptance criteria

The task is not complete just because tests pass. Verify the current application can be launched and that:

- The Overview looks recognisably close to the reference in composition, spacing and hierarchy.
- Left navigation replaces the crowded horizontal tabs, if this change is compatible with the present architecture.
- Job settings appear in only one primary destination.
- Panels do not become cramped at the normal window size; content scrolls where appropriate.
- The same styling is applied to modal dialogs and all pages.
- No labels clip, overlap or become unreadable; tables have sensible default column widths.
- Keyboard focus and disabled controls remain visible.
- No fake activity, fake values or placeholder controls appear for features the application does not support.

Use screenshots of the real application if available to compare it with the reference. Automated offscreen tests are not proof of visual quality. If no real display is available, explicitly report that visual acceptance remains for the user to perform on Windows.

## Deliverables

1. Implemented visual refinement in the existing application.
2. Updated/added automated tests.
3. `docs/GUI_VISUAL_REFERENCE_MATCH_REPORT.md` containing:
   - mismatch list found before changes;
   - files changed and why;
   - confirmed visual changes and any reference details intentionally omitted;
   - commands run and exact test results;
   - baseline-versus-current failing node IDs;
   - manual Windows checks still required;
   - any unresolved usability decisions.
4. A screenshot of the actual running Overview and, if practical, Entities, Variants and Generate pages. Do not include screenshots of mocked or static-image screens in place of the real app.

## Stop condition

Implement only this visual-reference refinement. Do not start another feature stage, package an executable, alter core biological semantics, or commit changes. Stop after tests, report and screenshots are ready for review.
