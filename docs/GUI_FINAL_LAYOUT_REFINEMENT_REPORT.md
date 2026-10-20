# Final layout refinement (v3) — implementation report

This pass implements `docs/AF3_GUI_FINAL_LAYOUT_REFINEMENT_PROMPT_v3.md` on top of
the existing workflow-simplification work. It changes presentation and
navigation only; configuration, validation, serialization, output planning and
file writing all continue to run through the existing services.

## 1. Overview — before / after

| Before | After |
| --- | --- |
| Job settings, an entity count card, a large readiness card, a next-step card, a readiness **table** and a **Validation findings** table. | Job settings, a compact **Entities** card and one compact readiness line. The two tables and the next-step card are gone. |
| Findings could be selected to jump to an entity; every warning was permanently on screen. | Readiness is `Ready` or `Needs attention · Not ready: 1 blocking finding.` A quiet **Validate job** re-reads the service verdict. Blocking reasons appear when Save or Generate is attempted. |
| With no job open, configuration controls plus actions remained visible. | With no job open the page is title + one sentence + `No job is open. Use New or Open in the FILE footer to begin.` No summary card, no readiness card, no Add Entity action, no settings form. |
| Raw JSON had no destination (Stage 9) but the page still carried a primary **Validate job** action at its bottom edge. | No JSON preview action anywhere; **Save JSON** is the one visible save route in the FILE footer (Ctrl+S). No duplicate save button was added to Overview, so the two cannot compete. |

The Entities card is the navigation affordance: it shows the total, the
service's own per-family breakdown (`2 proteins · 2 DNA strands · 1 ligand`)
and the dialect, with **Manage entities** wired to
`entities_requested → MainWindow.show_page(entities_page)`. Family counts are
not separately clickable; that would need filtering state the page does not
own, which the prompt allows leaving out.

The verdict and counts are read from `ValidationService.status()` and its
`components` row; the page decides no domain rule and recomputes nothing.

## 2. Entities — compact picker and three work areas

**Before:** a wide three-column `QTableView` on the left, with a splitter to a
large right-hand column that opened with a read-only `QPlainTextEdit` showing
the full sequence or representation, followed by PTMs, MSA and templates, and
then the job-wide CCD and bond groups — all in the selected entity's column.

**After:**

- A single labelled drop-down (`Entity`) at the top. Each entry is
  `identity · family · summary`, for example `A · Protein · 17 residues`,
  `B · DNA · 4 residues`, `D, E · Ligand · CCD: ATP`. Both strands of a duplex
  and every identifier of a multi-copy ligand are distinct entries. The
  existing `EntityTableModel` still projects `configuration.records` in
  order; the picker is just a compact view over it.
- **Add Protein / Add RNA / Add DNA / Add Ligand** stay on their own row;
  **Edit entity** and **Delete entity** sit beside the picker. Every action
  keeps its existing service call, dialogs and confirmations.
- The selected entity's facts are compact: **Length** (`17 residues`) for a
  chain, **Representation** for a ligand, **Description**, and the DNA partner
  row only for DNA. There is no sequence text area anywhere on the page; the
  full sequence remains in the Add/Edit dialog.
- Three tabs: **Entity settings**, **Custom CCDs**, **Covalent bonds**.

`AdvancedPage` now composes one of three scopes (`entity`, `ccd`, `bonds`) and
the window creates one instance per work area. All three read the same
`GuiState`/services; there is no second configuration or cached domain state.
`MainWindow.advanced_page`, `.ccd_page` and `.bonds_page` expose them.

### Entity settings order

Inside the first tab: compact facts card → **Settings for this entity** →
Alignment/MSA → Templates → PTMs/modifications, then the job-wide sections are
absent. A ligand hides all three entity groups and keeps only its compact
facts; DNA shows PTMs but no MSA/templates. The redundant "This entity"
sub-heading was removed in this composition.

### Custom CCDs

Its own tab, outside the entity column, opening with `This applies to the
whole job, not to one selected entity.` The existing controls are unchanged:
none / inline CIF / CIF file, inline-vs-path mutual exclusion enforced by the
service, version note, active-definition line, Apply and Clear. No wire value
is assembled in the widget; `apply_ccd()` and `clear_ccd()` still call
`GuiState.set_component_definition` / `clear_component_definition`.

### Covalent bonds

Its own tab, with the same whole-job note. The existing typed endpoint form,
add/remove confirmation, table and service calls are unchanged. With zero or
one entity the **Add bond…** action is disabled and the area says
`Covalent bonds need at least two entities ...`; opening the tab itself works
with no entities, as required.

## 3. Save, preview and blocking explanations

- The standalone JSON preview destination and shortcut remain removed. The
  internal `PreviewPage` is still constructed for diagnostics/tests but is not
  a destination, not in the sidebar and has no button on Overview.
- Save remains in the FILE footer and File menu, using the existing chooser →
  overwrite confirmation → `plan_save` → `execute` path.
- `MainWindow._report_save_refusal` no longer jumps to Overview (which has no
  findings list). It builds a focused message from the plan's own findings:
  `1 blocking issue stops this action; nothing was written:` followed by the
  catalogue's `user_message` and suggestion (up to four, then "…and N more").
  The same message goes to the status bar; nothing is marked saved.
- Generate keeps its four-step plan review. A refused plan still shows the
  service message, its findings table, conflicts/warnings and a disabled
  Generate button; no files are written.

## 4. Files changed

Application:

- `configbuilder/ui/render/qt/pages/overview.py` — rewritten around settings,
  entity summary and one readiness line; removed both tables, the next-step
  card and the empty-state content.
- `configbuilder/ui/render/qt/pages/entities.py` — picker replaces the table;
  compact facts replace the sequence preview; three work-area tabs.
- `configbuilder/ui/render/qt/pages/advanced.py` — scope-aware composition,
  Alignment → Templates → PTMs order, job-wide tools separable; removed the
  duplicated bond prerequisite/description line.
- `configbuilder/ui/render/qt/windows/main_window.py` — creates the three
  AdvancedPage scopes, wires the summary navigation, hides the header pill
  with no job, and builds the on-demand blocking explanation.
- `configbuilder/ui/present/strings.py` — new picker/tab/summary/refusal
  wording; removed the now-unused findings/readiness copy; direct
  `Edit entity` / `Delete entity` labels.

Tests:

- `tests/gui/test_final_layout_refinement.py` (new) — the v3 behaviours listed
  below.
- Updated: `test_mockup_shell.py`, `test_final_ux.py`,
  `test_workflow_simplification.py`, `test_readiness.py`,
  `test_job_lifecycle.py`, `test_window.py`, `test_entity_management.py`,
  `test_advanced_settings.py`.

Docs and evidence:

- `RUNNING_THE_APPLICATION.md` — Overview and Entities tour corrected.
- `docs/GUI_FINAL_LAYOUT_REFINEMENT_REPORT.md` (this file).
- `.stage9_shots/capture.py` — captures the new tabs and no-job state.
- `docs/screenshots/overview_1360x860.png`, `overview_940x640.png`,
  `overview_no_job_1360x860.png`, `entities_protein_1360x860.png`,
  `entities_protein_940x640.png`, `entities_ccd_1360x860.png`,
  `entities_bonds_1360x860.png` (Variants/Generate captures refreshed too).

No service or domain change was needed. No pre-existing user work was reset,
stashed or committed.

## 5. Tests run

Environment: Windows, `.venv-gui` Python, `QT_QPA_PLATFORM=offscreen` for GUI
tests; base project interpreter for the full suite.

| Command | Result |
| --- | --- |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | **275 passed**, exit 0 |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/architecture` | **40 passed**, exit 0 |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py` | **5 passed**, exit 0 |
| `python -m pytest -o addopts="" -q` | **1032 passed, 13 failed, 16 skipped**, exit 1 |
| `python gui.py --help` | exit 0, correct usage text |

Baseline comparison: the previous full run was **1032 passed, 13 failed,
15 skipped**. This run has the **same 13 failing node IDs**, all in the legacy
`tests/e2e` terminal-menu scripts, and one extra skip because the new GUI test
module correctly skips under the base interpreter where PySide6 is absent:

- `tests/e2e/test_entity_lifecycle.py`: 3 failures
- `tests/e2e/test_menu_acceptance.py`: 10 failures

No new failures were introduced. The GUI suite, architecture rules, string
registry, app, output, validation and serialization suites are green.

New/updated assertions cover: no `QTableView`/findings list/JSON preview action
on Overview; no empty-state card or Add Entity action with no job while
New/Open remain; Manage entities navigation; picker entries for protein, RNA,
DNA duplex strands, imported lone DNA strand and multi-copy ligand IDs;
absence of `QPlainTextEdit` in the entity settings area; Alignment → Templates →
PTMs layout order; dedicated CCD/bond tabs outside the entity column; both
areas open with zero entities; blocked Generate keeps its plan review and
writes nothing; blocked Save explains itself and writes nothing.

## 6. Manual Windows acceptance checklist

- [x] Overview shows job settings, a compact entity summary and one readiness
      line; no permanent findings table and no JSON preview button.
      *(automated + screenshot `overview_1360x860.png`)*
- [x] With no job open, no begin-card or Add Entity action; New/Open remain in
      the FILE footer. *(automated + `overview_no_job_1360x860.png`)*
- [x] Save JSON is in the FILE footer and uses the established save path.
      *(automated lifecycle tests)*
- [x] Clicking Manage entities opens Entities. *(automated)*
- [x] The picker switches among protein, RNA, DNA duplex/lone strand and
      ligand, including multi-copy identifiers. *(automated)*
- [x] No oversized read-only sequence preview; Add/Edit still edits it.
      *(automated; no text area in the settings area)*
- [x] Alignment/MSA appears before templates and PTMs for protein/RNA; DNA and
      ligands hide the inapplicable groups. *(automated)*
- [x] Custom CCDs and Covalent bonds are dedicated, whole-job areas, usable
      with zero entities. *(automated + screenshots)*
- [x] Variants remains guided; Generate keeps plan review, warning/conflict
      visibility, confirmation and cancellation. *(existing regression suite)*
- [x] Save/reopen round-trip and output JSON ordering are unchanged.
      *(existing app/output/serialization suites)*
- [ ] Human check on a real desktop for DPI scaling, focus traversal and
      screen-reader names. These automated captures prove rendering and
      widget state, not a person's keyboard walk-through.

## 7. Limitations and notes

- The screenshots are automated `QWidget.grab()` captures using the Windows Qt
  platform and system fonts. The 1360×860 request is capped by the 1366×768
  desktop work area, so those files are **1088×688**; the 940×640 capture is
  exact. This is a capture limitation, not a layout regression.
- The entity summary opens Entities but does not filter by family; family
  count labels are therefore not separately clickable. The prompt permits
  this when reliable filtering would require duplicate state.
- No service/API gap was found: the picker reads `configuration.records`
  through the existing model, and both job-wide areas call the existing
  `GuiState` methods.
- No packaging, scientific-feature or broader redesign work was started.
