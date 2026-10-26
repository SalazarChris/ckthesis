# Stage 5 — Variants & Batch for the AF3 JSON Builder GUI

Delivered: one **Variants & Batch** workspace over the existing variant
services — manual spec-based variants with a typed editor and a
service-backed preview, per-variant validation, quantity series planned before
commit, file-based batches previewed before an all-or-nothing commit, and a
read-only JSON preview of each variant. The base job is never mutated by any
of it.

Scope note: this report describes Stage 5 only. The complete output-tree
generation (`GenerationService.plan`/`execute` with assets and manifest),
cluster submission, analysis integration, new AF3 fields and new variant
semantics are **not** included. No destructive Git command and no commit was
performed; pre-existing working-tree changes were left untouched.

---

## 1. What the user can do

| Area | Behaviour |
| --- | --- |
| Navigate | A **Variants & Batch** tab sits between Advanced and Job Settings. The base job's name, entity count and variant count stay visible at the top. |
| See variants | A table lists every committed spec in declared order: name, ID, declared changes, and validation state (Ready / Ready with warnings / Blocked (n) / Base blocked / Not validated). |
| Create | **New variant…** opens a form with a name, a unique ID, a change-kind picker built from `VariantService.edit_options()`, only the fields that kind needs, and a live **service-backed preview line** of the proposed change. |
| Inspect | Selecting a row shows its declared changes, its own findings, and its JSON (produced by `GenerationService.show_json(key)`). |
| Edit | **Add change…** appends one declared change without losing the existing ones; **Rename…** changes only the name. Both are separate service commits. |
| Duplicate | **Duplicate…** copies the spec (same edits, fresh key/name); the source is untouched. |
| Remove | **Remove…** asks for confirmation naming the variant and stating the base is unaffected; Cancel changes nothing. |
| Validate | **Validate all** re-runs `ValidationService.validate_all()` and refreshes every row and the selected findings. |
| Quantity series | A tab inside the workspace: check components, set start multiplier / factor / levels, **Preview series** shows the service plan (multiplier and resulting copy counts), then **Create series** commits it. |
| Batch from file | A tab inside the workspace: choose protein, DNA or ligand input, choose a file, **Preview file** shows the entries the service read, then **Create batch** commits. One invalid entry refuses the whole batch. |

The change kinds offered are exactly the service's: sequence, add/remove
modification, MSA/alignment, templates/references, job name, job description,
model seeds, component copy count, add entity, remove entity.

---

## 2. Files created and modified

### Created

| File | Purpose |
| --- | --- |
| `configbuilder/ui/render/qt/pages/variants.py` | The Variants & Batch page: base summary, spec table, details (changes/findings/JSON), quantity-series form and batch-file form. |
| `configbuilder/ui/render/qt/dialogs/variant_forms.py` | `VariantChangeEditor` (typed fields per change kind), `NewVariantDialog`, `VariantChangeDialog`, `RenameVariantDialog`, `DuplicateVariantDialog`, and the deterministic name→ID suggestion. |
| `tests/gui/test_variants_batch.py` | 38 GUI tests (widgets and dialogs driven for real; service state, expanded variants, validation reports and JSON asserted). |
| `docs/GUI_STAGE5_VARIANTS_BATCH_IMPLEMENTATION_REPORT.md` | This report. |

### Modified

| File | Change |
| --- | --- |
| `configbuilder/app/variant_service.py` | Extracted `_edits_for_kind` (one edit-construction path), added `add_spec_with_edit` (atomic create + first change), `describe_change` (service-backed preview with no commit), `modification_choices` (rows tagged with their record), and `inspect_batch_file` (family-aware read-only preview). Existing behaviour and messages preserved. |
| `configbuilder/app/batch_variants.py` | **Bug fix:** ligand batch records now use the model's `ByNotation` representation instead of `SequenceText(..., "ligand")`, which refused every ligand batch with "unknown sequence family". Removed an unused import. |
| `configbuilder/ui/render/qt/state.py` | `GuiState` pass-throughs for every spec/validation/series/batch operation; `project_changed` emits only on success. |
| `configbuilder/ui/render/qt/models.py` | `VariantRow` / `VariantTableModel` — a read-only projection of service data, in declared order. |
| `configbuilder/ui/render/qt/pages/__init__.py` | Exports `VariantsPage`. |
| `configbuilder/ui/render/qt/pages/variants.py` | The page itself (above). |
| `configbuilder/ui/render/qt/windows/main_window.py` | Adds the tab, includes the page in `refresh()`, and exposes `variants_page`. |
| `configbuilder/ui/render/qt/dialogs/variant_forms.py` | The dialogs/editor (above). |
| `configbuilder/ui/render/qt/dialogs/messages.py` | `confirm_variant_removal` using the existing destructive-confirmation shape (Cancel is the default). |
| `configbuilder/ui/render/qt/dialogs/__init__.py` | Exports the new dialogs and confirmation. |
| `configbuilder/ui/present/strings.py` | New `gui.*` entries only: page/table/dialog wording, change-kind labels and hints, field labels, series and batch wording, preview and status wording. |
| `tests/gui/conftest.py` | Defaults for the new dialogs (cancel) and the removal question (yes), so no offscreen test can hang; tests replace them when they assert. |
| `tests/gui/test_window.py` | The page-list assertion now includes the Stage 5 tab; the registry-driven "no later-stage action" check no longer treats *variant* wording as a future stage (it still excludes generate/execute/export). |
| `tests/unit/app/test_batch_variants.py` | Six service-level tests: ligand batch representation, `inspect_batch_file` for each family, unsupported family, and `add_spec_with_edit` success/atomic refusal/duplicate key. |
| `tests/unit/ui/test_string_registry.py` | Classified two pure separators (`"; "`, `"  ·  "`) as separators, like the separators already listed there. |

No core runtime dependency was added; PySide6 remains optional.

---

## 3. GUI action → service method

| UI action | Service method (through `GuiState`) |
| --- | --- |
| Change-kind list | `VariantService.edit_options()` |
| Entity / component choices | `all_entity_choices()`, `component_count_choices()` |
| Modification-to-remove list | `modification_choices(key)` (expanded variant rows with record keys) |
| Declared-changes text | `spec_change_descriptions(key)` → `describe_spec_edits` |
| Preview a proposed change | `describe_change(kind, value, record_key)` (no commit) |
| Create variant | `add_spec_with_edit(key, label, kind, value, record_key)` |
| Add change | `apply_variant_edit(key, kind, value, record_key)` |
| Rename | `update_spec(key, label=...)` |
| Duplicate | `duplicate_spec(key, new_key, new_label)` |
| Remove | `remove_spec(key)` |
| Add-entity value | `build_add_records(family, ...)` (service builds the records) |
| Validate all | `ValidationService.validate_all()` |
| Selected JSON | `GenerationService.show_json(key)` |
| Series preview | `quantity_series_plan(keys, start, factor, levels)` |
| Series commit | `create_quantity_series(keys, start, factor, levels)` |
| Batch preview | `inspect_batch_file(path, family)` |
| Batch commit | `generate_from_file(path, family)` |

The page never constructs a `VariantSpec`, an edit object, a record, a wire
dictionary or JSON text.

---

## 4. One discoverable workflow

Manual variants, series and batches share the tab. The top half is the
variant list and the selected variant's details (changes, findings, JSON); the
bottom half is one **Create more variants** group with two tabs, *Quantity
series* and *Batch from file*. Manual creation is the toolbar's
**New variant…**, next to Add change / Rename / Duplicate / Remove /
Validate all. The base summary is always on screen, and the variant table's
"Declared changes" column makes each variant's intent visible without opening
anything.

Both creation tabs are preview-first:

* **Quantity series** fills its table from `quantity_series_plan` and disables
  **Create series** until a plan exists; changing any value invalidates the
  plan and requires a new preview.
* **Batch from file** fills its table from `inspect_batch_file`; changing the
  file or input type invalidates the preview and disables **Create batch**.

---

## 5. Base immutability and transactions

* Spec mutations go through `ProjectService._with_specs`, which replaces the
  project wrapper but carries the **same immutable `Configuration` object**.
  Tests assert `state.configuration is before` after create, edit, duplicate,
  remove, series and batch operations.
* Expansion always starts from the base (`variants.expansion.expand`), never
  from a sibling; two variants with different sequence edits are shown to
  produce their own sequences, and the base keeps its original one.
* `add_spec_with_edit` builds and validates the first edit **before**
  `add_spec` commits, so a refused edit cannot leave an empty variant.
* `create_quantity_series` and `generate_from_file` roll back already-created
  specs if a later one is refused. The GUI relies on that; a colliding series
  and an invalid batch both leave the pre-existing spec set exactly as it was.
* No JSON dictionary or wire field is built in UI code; the JSON preview is
  `GenerationService.show_json`, the same transform/encode path a save uses.

---

## 6. Exact commands and results

Measured on this working tree (Windows, Git Bash, offscreen Qt).

| Command | Result |
| --- | --- |
| `python -m pytest -o addopts="" -q tests/architecture` | **40 passed** |
| `python -m pytest -o addopts="" -q tests/unit/test_launchers.py` | **19 passed** |
| `python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py` | **5 passed** |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | **190 passed** in 14.2s |
| `python -m pytest -o addopts="" -q` | **13 failed, 1029 passed, 10 skipped** in 103.6s |
| `python -m ruff check --select E4,E7,E9,F configbuilder tests/gui` | **All checks passed** |
| `python -m compileall -q configbuilder tests/gui` | exit 0 |
| `python gui.py --help` | usage printed, exit 0 |
| `python af3builder.py < /dev/null` | exit 0, console menu intact |

### Baseline and failing IDs

Stage 4 ended at **13 failed, 1023 passed, 9 skipped**. The same 13 node IDs
fail now (sorted list identical, `diff` empty); no test was weakened or
deleted and no new failure appeared. The pass count rose by six (the new
service tests); the skip count rose by one because the Stage 5 GUI module
skips as a whole in the core interpreter (no PySide6), like its siblings.

```text
tests/e2e/test_entity_lifecycle.py::test_a_long_repeated_chain_of_operations_leaves_consistent_state
tests/e2e/test_entity_lifecycle.py::test_an_imported_document_is_editable_like_a_built_one
tests/e2e/test_entity_lifecycle.py::test_every_family_survives_a_full_lifecycle
tests/e2e/test_menu_acceptance.py::test_a_blank_job_name_is_generated_by_the_service
tests/e2e/test_menu_acceptance.py::test_a_ligand_carries_no_modifications_and_is_told_so
tests/e2e/test_menu_acceptance.py::test_add_every_entity_family
tests/e2e/test_menu_acceptance.py::test_an_opened_job_can_be_edited_and_saved
tests/e2e/test_menu_acceptance.py::test_invalid_job_settings_are_refused_in_the_users_terms
tests/e2e/test_menu_acceptance.py::test_job_settings_change_name_seeds_and_version
tests/e2e/test_menu_acceptance.py::test_open_json_can_be_cancelled_at_the_confirm
tests/e2e/test_menu_acceptance.py::test_ptm_management_adds_edits_and_removes
tests/e2e/test_menu_acceptance.py::test_the_entity_modifications_submenu_adds_edits_and_removes
tests/e2e/test_menu_acceptance.py::test_the_job_menu_numbering_is_stable_across_states
```

These are the previously audited stale CLI/end-to-end scripts; they were not
edited.

**Two existing tests were updated for the new feature, deliberately and
narrowly:**

* `tests/gui/test_window.py::test_the_window_shows_its_pages` now expects the
  new Variants & Batch tab (the requested navigation change).
* `tests/gui/test_window.py::test_the_window_offers_exactly_the_stage_two_actions`
  no longer treats *variant* wording as a future stage (variants now exist);
  it still rejects generate/execute/export actions.
* `tests/unit/ui/test_string_registry.py` adds the two pure separators used by
  the variant list (`"; "`, `"  ·  "`) to its existing separator allow-list.
  No sentence or label was allow-listed; new wording is in the registry.

No assertion was removed, no test was deleted, and no failure was hidden.

### What the 38 Stage 5 GUI tests cover

Workspace/tab and base summary; create a sequence variant through the real
dialog (name→ID suggestion, one project-change notification, service spec and
preview JSON, base object identity); service-backed preview line and a refused
preview; invalid sequence keeps the dialog open with no spec and no change
notification; duplicate ID refused with no partial state; add change preserves
existing edits; rename preserves edits; duplicate copies edits and leaves the
source; remove Cancel/confirm and the confirmation's wording; cancel the new
dialog; PTM add (1-based position, base unchanged) and remove using the
expanded modification rows; alignment change (JSON field, base still
automatic) and DNA not offered as an alignment target; template change keeps
base references; component-count change leaves the base copy counts; add
entity (service-built, new identifier) and remove entity; blocked variant flies
its `R-ENT-007` finding and status; base-blocked rows/notes; Validate all;
series preview with no specs, commit with exact counts, duplicate-key rollback,
value-change invalidation, and the no-component guard; protein and ligand
batch preview→commit with the exact spec set, invalid batch leaves existing
specs only, changed family invalidates the preview, input file bytes unchanged,
preview emits no project change; one variant's edits never leak into another
or the base; change/status columns; selected JSON equals the service document;
batch and template file pickers.

---

## 7. Known limitations / deferred scope

1. **Saving one variant JSON is deferred.** `GenerationService.plan_save`
   plans the *base* configuration only; there is no variant-aware planning
   API to call. Adding one is a service change (variant validation + transform
   + wire naming), and it belongs with the next output-generation stage rather
   than being re-implemented in Qt. No JSON is written in the GUI.
2. **Variant specs are session-only.** The existing AF3 JSON save writes the
   base configuration; the GUI has no project-file save that would carry
   specs. `GuiState.is_dirty` therefore tracks the configuration only. This is
   stated on the page ("Variants belong to this session…").
3. **No per-edit removal.** A declared change can be appended (and the whole
   variant removed) but not individually deleted; the service can replace an
   edit tuple, but there is no user-facing edit to remove. Documented rather
   than guessed.
4. **No RNA batch reader.** `BATCH_RECORD_BUILDERS` supports protein, DNA and
   ligand; the family choices match that exactly, and `inspect_batch_file`
   refuses RNA with a clear message.
5. **Overview job settings remain read-only.** Stage 4 did not add direct
   editing of name/seeds/version to Overview; they are on Job Settings. This
   Stage 5 report records the gap rather than silently widening scope.
6. **Offscreen only.** No real Windows display, DPI/scaling, native file
   dialog, keyboard-navigation or packaging test was performed. The manual
   checklist below is the required verification.

---

## 8. Manual Windows checklist

1. Launch `python gui.py` (or double-click the launcher) and open **Variants &
   Batch**; the base job's name, entity count and `0 variants` are visible.
2. Click **New variant…**, type a name, choose *Sequence change*, pick a chain,
   paste a plain sequence. Confirm the preview line names the chain and
   sequence before you commit; click **Create variant**.
3. Confirm the row shows Ready, the change list names the sequence edit, and
   the JSON tab shows the new sequence. Confirm the Entities tab still shows
   the base sequence.
4. Select the variant and use **Add change…** for *Model seeds*; confirm both
   changes remain. Use **Rename…** and confirm the change list survives.
5. Use **Duplicate…**, then **Remove…** and click Cancel; the variant remains.
   Repeat and confirm; only that variant disappears.
6. Add a PTM to a chain in **Advanced**; create a variant with *Add a PTM* at a
   valid 1-based position and one at an out-of-range position. Confirm the
   second row is Blocked and its finding names the position, and Validate all
   agrees.
7. Open **Quantity series**, check a ligand, preview with start 1, factor 2,
   levels 3. Confirm the table's multipliers/counts and that nothing is in the
   list yet; create, then confirm three variants and unchanged base counts.
8. Open **Batch from file**, choose Protein, pick a two-line `.txt`, preview,
   then create. Confirm two variants and the base entity count unchanged.
   Repeat with a file containing an invalid line and confirm **no** variants
   are added and the message names the line.
9. Change the file type after a preview and confirm **Create batch** is
   disabled/refuses until you preview again. Cancel a creation and confirm the
   variant list is unchanged.
10. Resize the window narrower and shorter: tables should scroll, buttons stay
    reachable, the splitter should remain usable. Tab through the form fields;
    focus order should follow the visible fields, and Enter should not trigger
    a destructive action.
11. Save the base JSON through **File → Save JSON…**, reopen it, and confirm the
    base is intact. (Variants are session-only — see limitation 2.)
12. Confirm a refused operation never opens a traceback dialog; the service's
    message appears in the dialog or the window's problem box.

Do not claim Stage 5 is accepted until this checklist has been run on a real
display. The next stage (output generation, assets and manifest) has not been
started.

---

## 9. Working-tree statement

No `reset`, `clean`, `checkout --`, `restore`, `stash`, commit, rebase or
amend was run. Branch `main`, HEAD `121baa8`.

**Created by Stage 5:** `configbuilder/ui/render/qt/pages/variants.py`,
`configbuilder/ui/render/qt/dialogs/variant_forms.py`,
`tests/gui/test_variants_batch.py`,
`docs/GUI_STAGE5_VARIANTS_BATCH_IMPLEMENTATION_REPORT.md`.

**Modified by Stage 5:** `configbuilder/app/variant_service.py`,
`configbuilder/app/batch_variants.py`,
`configbuilder/ui/render/qt/state.py`, `configbuilder/ui/render/qt/models.py`,
`configbuilder/ui/render/qt/pages/__init__.py`,
`configbuilder/ui/render/qt/windows/main_window.py`,
`configbuilder/ui/render/qt/dialogs/__init__.py`,
`configbuilder/ui/render/qt/dialogs/messages.py`,
`configbuilder/ui/present/strings.py`, `tests/gui/conftest.py`,
`tests/gui/test_window.py`, `tests/unit/app/test_batch_variants.py`,
`tests/unit/ui/test_string_registry.py`.

**Pre-existing, untouched:** the modified files listed in the Stage 4 report
(`app/status.py`, `app/variant_service.py`'s earlier edits, `persistence/*`,
`menus.py`, `pyproject.toml`, older UI tests, etc.) and the untracked
`af3_analysis/`, `gui.py`, `af3builder.py`, `generated_jobs/`, `pytest-of-Chris/`,
`tests/analysis/`, `tests/unit/test_launchers.py`, earlier `docs/` reports and
the rest of `configbuilder/ui/render/qt/` (Stages 1–4).
