# Stage 4 — Advanced entity settings for the AF3 JSON Builder GUI

Delivered: version-feature/readiness consistency, PTM (modification) editing,
per-entity MSA/alignment controls, protein template references, the job-level
custom CCD definition, a covalent-bond editor, and a single-call ligand edit —
all through the existing application services and the existing PySide6 window.

Scope note: this report describes Stage 4 only. No variant/spec editing,
quantity series, batch-from-file, bulk generation, cluster submission, analysis
pipeline, standalone ion family, JSON assembly in the GUI, or architecture
rework is included. Nothing was reset, stashed, cleaned, reverted or committed;
pre-existing working-tree changes (including the user's edits in
`pyproject.toml`, `menus.py`, `strings.py`, the earlier stages' GUI and tests)
were left in place and only narrowly extended.

---

## 1. Summary of delivered functionality

| Capability | Where it lives | How it works |
| --- | --- | --- |
| Advanced tab | `pages/advanced.py::AdvancedPage` | Shows the selected entity's Stage 4 settings and the job-level CCD/bond sections in one scrollable page. |
| Version-feature conflicts in readiness | `transform.used_version_features` → `app.ValidationService` → `R-VER-002` | Readiness, findings, JSON preview and save now refuse the same configuration for the same reason. |
| Modifications / PTMs | Advanced page + `ModificationFormDialog` | Table (code, Position (1-based residue number), residue echo), Add/Edit/Remove; each action calls the matching service method. |
| MSA / alignment | Advanced page + `AlignmentFormDialog` | Family-specific mode list, inline-or-file source with a file picker, automatic default preserved, no controls for DNA/ligands. |
| Protein templates | Advanced page + `TemplateEditorDialog` | Search allowed / none / explicit file list; multiple mmCIF files with 0-based index pairs. |
| Custom CCD definition | Advanced page (job scope) | None, inline CIF text, or external CIF path — exactly one; active representation shown; file picker for the path route. |
| Covalent bonds | Advanced page (job scope) + `BondFormDialog` | Two endpoints (entity picker, 1-based residue, atom name); add and confirmed removal through the service. |
| Atomic ligand edit | `ConfigurationService.update_component_record` | Representation and description are built and validated before the single commit; a refusal changes nothing. |
| Sequence-input hint | Entities forms | States that a plain, unwrapped sequence is required; nothing is normalized. |

Every write is a pass-through on `GuiState` to a `ConfigurationService` method.
The GUI allocates no identifier, renames nothing, invents no DNA partner,
builds no AF3 dictionary/bytes, evaluates no domain rule and never decides
readiness itself.

---

## 2. Files created and modified

### Created in Stage 4

| File | Purpose |
| --- | --- |
| `configbuilder/ui/render/qt/pages/advanced.py` | The Advanced page: entity-scoped modifications/alignment/templates and job-scoped CCD/bonds, with read-back accessors used by the tests. |
| `configbuilder/ui/render/qt/dialogs/advanced_forms.py` | `ModificationFormDialog`, `AlignmentFormDialog`, `TemplateEditorDialog`, `BondFormDialog`; a shared `_FormDialog` owns the apply/refusal/keep-open behaviour. |
| `tests/gui/test_advanced_settings.py` | 69 Stage 4 GUI tests (widgets driven for real, service state and serialized JSON asserted). |
| `docs/GUI_STAGE4_IMPLEMENTATION_REPORT.md` | This report. |

### Modified in Stage 4

| File | Change |
| --- | --- |
| `configbuilder/app/configuration_service.py` | Added `update_component_record(...)` and the shared `_representation_from(...)` helper used by both it and `set_representation`. No behaviour change to existing methods. |
| `configbuilder/app/version_features.py` | Re-exports `MSA_PATH_MIN_VERSION`, `TEMPLATE_PATH_MIN_VERSION`, `USER_CCD_PATH_MIN_VERSION` alongside the existing description constant, so the UI can *explain* thresholds without importing `transform`. |
| `configbuilder/app/validation_service.py` | Joins `used_version_features(configuration)` into the `ValidationContext` for base validation, variants and the status path — the same join pattern already used for variant inputs. |
| `configbuilder/transform/mappings.py` | Added `FEATURE_WORDS` / `feature_word(...)`; the version numbers themselves were already the single source of truth. Wire names remain confined to `transform`. |
| `configbuilder/transform/engine.py` | Made the former `_used_features` public as `used_version_features`, returning deterministic `(feature, minimum version, wording)` rows; the generation gate consumes the same function. |
| `configbuilder/transform/__init__.py` | Exports `used_version_features`. |
| `configbuilder/validation/engine.py` | `ValidationContext` carries `used_version_features`; `None` means the join did not happen and is reported as an explicit WARNING, never a silent pass. |
| `configbuilder/validation/rules/policy_rules.py` | `R-VER-002` compares the effective pin (pin version, or the minimum evidenced version for `Auto`) with the joined features; unset features never appear, so no false conflicts. Wording of a feature comes from the mapping layer. |
| `configbuilder/ui/present/strings.py` | New `gui.*` entries only (advanced page, forms, hints, confirmations, state labels). |
| `configbuilder/ui/render/qt/state.py` | Pass-throughs: `add_modification`, `update_modification`, `remove_modification`, `set_alignment`, `set_references`, `set_component_definition`, `clear_component_definition`, `add_linkage`, `remove_linkage`, `update_component_record`; each emits `project_changed` only on success. |
| `configbuilder/ui/render/qt/pages/entities.py` | Ligand edit is one `update_component_record` call; sequence add/edit forms carry the plain-unwrapped-sequence hint. |
| `configbuilder/ui/render/qt/dialogs/entity_forms.py` | Optional hint line on the sequence form (no normalization). |
| `configbuilder/ui/render/qt/dialogs/__init__.py`, `pages/__init__.py` | Export the new page, dialogs and confirmations. |
| `configbuilder/ui/render/qt/windows/main_window.py` | Adds the Advanced tab, connects entity selection to it, and refreshes it with the rest of the window. |
| `tests/unit/app/test_edit_guards.py` | 6 service-level atomic-ligand-edit tests. |
| `tests/unit/validation/test_rule_checks.py` | R-VER-002 tests: bare pin clean, description above pin, covering pin, unset field, active-path-only, external CCD below v3, missing join, Unverified. |
| `tests/unit/validation/test_no_pin_document_dependency.py` | Updated the two helpers to pass the real `used_version_features` join. |

Pre-existing modifications in these files (and elsewhere in the working tree,
for example `app/status.py`, `app/batch_variants.py`, `app/variant_service.py`,
`persistence/*`, `menus.py`, `pyproject.toml` and several older tests) belong to
the user/earlier stages and were not touched beyond the narrow additions above.

No dependency was added to `[project].dependencies`; PySide6 remains optional.

---

## 3. UI action → service method

| UI action | Service call (via `GuiState`) |
| --- | --- |
| Add modification | `ConfigurationService.add_modification(record_key, code, position)` |
| Edit selected modification | `update_modification(record_key, index, code=..., position=...)` |
| Remove selected modification | `remove_modification(record_key, index)` |
| Change alignment | `set_alignment(record_key, mode, inline_text=... / external_path=... / neither)` |
| Templates: search allowed | `set_references(record_key)` |
| Templates: explicit none | `set_references(record_key, references=())` |
| Templates: file list | `set_references(record_key, references=(ReferenceInput(...), ...))` |
| Custom CCD: apply | `set_component_definition(inline_text=... / external_path=...)` |
| Custom CCD: none/clear | `clear_component_definition()` |
| Add bond | `add_linkage(a_key, a_residue, a_atom, b_key, b_residue, b_atom)` |
| Remove bond | `remove_linkage(index)` |
| Ligand edit (representation and/or description) | `update_component_record(record_key, codes=/notation=, description=)` |

Readback is projection only: `alignment_state`, `reference_state` and the CCD
section read the model's own `Alignment*`, `SearchAllowed`/`Explicit` and
`component_definition` values. No page writes a record.

---

## 4. Version-feature conflicts and readiness (Stage 4B)

**Source of truth.** `transform/mappings.py` already declared
`MSA_PATH_MIN_VERSION = 2`, `TEMPLATE_PATH_MIN_VERSION = 2`,
`USER_CCD_PATH_MIN_VERSION = 3`, `DESCRIPTION_MIN_VERSION = 4` and
`PATH_FEATURE_MIN_VERSIONS`. `transform.engine.used_version_features` derives
the features a configuration *actually uses* from the same presence data that
gates emission, so validation cannot drift from generation.

**Design.** `ValidationContext.used_version_features` carries the mapping
layer's rows into validation (the same app-level join already used for variant
facts). `R-VER-002` compares them with the effective selection:

* pinned version → that version;
* `Auto` → the minimum evidenced version, exactly as the engine's own Auto
  semantics;
* `Unverified` → nothing to compare; `R-VER-001` already blocks, so R-VER-002
  stays silent rather than double-reporting;
* the join missing → an explicit WARNING ("could not be checked"), never a
  silent pass.

Features are only those the configuration uses: an unset description is never
a conflict, and an external path is checked only while that path mode is the
active one (`Inline` sources do not count). The finding is an ERROR naming the
feature, the current version and the minimum, and suggests raising the version
in Job Settings. No code changes the pin.

**Tests.** Eight service/validation tests (`tests/unit/validation/test_rule_checks.py`)
cover the branches above. The GUI regression
`test_a_version_feature_conflict_is_visible_and_clears_on_a_higher_version`
pins v1, sets an external MSA path through the real dialog, and asserts:
status not ready → `R-VER-002` in `status.blocking` → `show_json` returns no
document → the preview shows its service refusal. Selecting v2 clears the
finding and the preview then contains `unpairedMsaPath`. A second test proves
the pin is still exactly v1 after adding a template (never silently promoted).

---

## 5. Modifications / PTMs (Stage 4C)

* Table columns: modification code, **Position (1-based residue number)**, and
  the residue echoed from the record's own sequence via the shared
  `residue_at` presenter (`-` when past the end).
* Add opens the form at position 1; the residue echo updates as the spin box
  changes and says how long the chain is when the position is past its end.
* Edit and Remove address the selected row's **index in the record's own
  modification tuple**, not a row-derived identifier or a hard-coded position.
  Imported modifications are therefore editable and removable.
* Only polymer records (`FamilyARecord`, `FamilyBRecord`, `FamilyCRecord`)
  enable the controls; a ligand page says modifications need a polymer.
* A service refusal (unknown code, non-positive position, out-of-range
  position) is shown on the dialog's own line; the dialog stays open and the
  record is unchanged. Cancellation mutates nothing and does not mark the job
  dirty.
* Success goes through `project_changed`: table, details, readiness, findings,
  preview, dirty marker and status line refresh.

---

## 6. MSA / alignment (Stage 4D)

Supported modes, verified against `MenuApp._collect_msa_mode` and the model:

* Protein: Automatic, Unpaired only, Paired only, Both, Free.
* RNA: Automatic, Provided, Free.
* DNA and ligands: no alignment field; the page shows
  `gui.alignment_not_applicable` and no enabled editor.

`AlignmentFormDialog` receives the family's mode list from the page (never
invents one). Source radios (paste inline / choose file) appear only for modes
that carry a source; Automatic and Free hide them and send no source. The path
route shows a file picker; the inline route shows a fixed-font editor. The
dialog keeps both fields across a source-radio switch, so imported text is not
lost, and the page reads the model back without changing hidden data.
Automatic remains the default for a new protein/RNA because the page never
calls `set_alignment` until the user changes something. The UI explains what a
mode means without implying a computation happened, and states the external
path's minimum version. Refusals (a source-carrying mode with an empty inline
source, a service refusal) keep the prior state and the dialog open.

---

## 7. Protein templates / references (Stage 4E)

`TemplateEditorDialog` exposes the model's three routes — search allowed, none
(explicitly template-free), and an explicit list — as radios. In list mode each
row is one reference: a read-only mmCIF path filled by the file picker plus
editable 0-based `query:template` index pairs. Multiple references are kept in
the order added, because the service/model supports a list. `search` and `none`
map to the service's two distinct calls, so "no explicit references" is never
translated into a different state. The page displays the current state and the
version requirement; the central validation decides validity. Editing templates
does not touch alignment data (asserted by test).

---

## 8. Custom CCD definition (Stage 4F)

The section is job-scoped and visually separate from the ligand editor. Three
radios: No custom definition, Paste a CIF definition (multiline editor), Load
from a CIF file (read-only field + file picker). Apply sends exactly one
representation; "None" and the Clear button call `clear_component_definition`,
which removes the definition rather than storing an empty string. The page
shows the active representation (none / inline with line count / file path).
The external route's version-3 requirement is displayed; the pin is never
changed. Switching inline → file (or back) and applying leaves only the chosen
representation in the emitted JSON, and an unrelated refresh does not overwrite
text the user is typing.

---

## 9. Covalent bonds (Stage 4G)

The bonds table reads `configuration.linkages` in configuration order and
displays each endpoint as `id (family), residue N, atom X`. The add form uses
two endpoint rows, each with an entity combo populated from the current
records (visible identifiers — no internal key typing), a 1-based residue spin
box and an atom-name field. The service resolves both identifiers through the
registry and constructs the `Linkage`; the GUI never builds `bondedAtomPairs`.
Removal asks for confirmation naming both endpoints and is by the model's own
index. Endpoint refusals come back from the service (unknown id, unresolved
endpoint, atom rules) and are reported through the window's problem path;
imported bonds are listed and removable. The serialized output still comes
from the transform pipeline.

---

## 10. Ligand edit atomicity (Stage 4H)

**Did the issue exist?** Yes. Stage 3's edit path called
`set_representation(...)` and then `update_record(description=...)`; a refusal
of the second call left the first applied.

**Fix.** `ConfigurationService.update_component_record(record_key, codes=None,
notation=None, description=None)` builds and validates every requested part
first (`_representation_from`, `_presence`) and performs exactly one
`_commit`. `set_representation` now shares the same representation builder, so
the two entry points cannot diverge. Passing nothing is refused rather than
committing an unchanged record. Identifiers and multiplicity are untouched
(the record is replaced with `with_representation`/`with_description` only).
The Entities page calls the single method.

**Tests.** Service level: combined change, both-representations refusal leaves
the object identical, identifiers/multiplicity preserved, nothing-to-change
refused, polymer targeted as a ligand refused. GUI level: a refused form edit
leaves neither field applied and emits no change notification; an accepted one
applies both and emits exactly one.

**Deferred:** copy-count changes after creation remain unsupported — there is
no existing service operation for multiplicity, so the entity form keeps the
count read-only and this is not attempted by rewriting identifiers.

---

## 11. Sequence wrapping / FASTA decision (§12)

Evidence: `persistence/sequences.py` validates the family alphabet and rejects
characters outside it (`\n`, `>`, `\r` are not in any alphabet), and existing
model/service tests assert that refusal. The authoritative contract therefore
requires a plain, unwrapped sequence; it does not require FASTA support.

Decision: no normalization. The add and edit forms now state "Paste a plain
sequence — no FASTA header and no line breaks", and a wrapped paste still gets
the model's own refusal in the form. A GUI test asserts the hint and that a
wrapped paste changes nothing.

---

## 12. Refresh, dirty state and error presentation

* Every successful service call emits `GuiState.project_changed`; the window
  refreshes the Advanced page together with the entity table/details, overview
  readiness and findings, JSON preview, dirty marker and status line.
* Cancelled or refused actions emit nothing: the configuration object is
  unchanged, the job stays clean, and the tests assert both.
* Forms show service refusals inline and stay open; actions without a form
  (bond removal, CCD apply/clear) go through `MainWindow.report_problem`. No
  traceback is shown for an ordinary refusal.
* Record order and JSON order are untouched; the page never sorts records.

---

## 13. Commands and results

Measured on this working tree (Windows, Git Bash).

| Command | Result |
| --- | --- |
| `python -m pytest -o addopts="" -q tests/architecture` | **40 passed** |
| `python -m pytest -o addopts="" -q tests/unit/test_launchers.py` | **19 passed** |
| `python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py` | **5 passed** |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | **152 passed** in 15.7s |
| `python -m pytest -o addopts="" -q` | **13 failed, 1023 passed, 9 skipped** in 194.1s |
| `python -m ruff check --select E4,E7,E9,F configbuilder tests/gui` | 1 finding, **pre-existing** (`app/batch_variants.py`, unused `FamilyBRecord`, a user-modified file); none in any Stage 4 file |
| `python -m compileall -q configbuilder tests/gui` | exit 0 |

### Baseline vs current failing node IDs

Stage 3 ended at **13 failed, 1009 passed, 8 skipped**; the same 13 node IDs
fail now, sorted and unchanged — no regression and no test deleted or weakened:

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

These are the stale CLI/end-to-end scripts recorded by Stage 3; they were not
edited. The pass count rose by 14 (new service/validation tests) and the skip
count by one (the Stage 4 GUI module skips as a whole in an interpreter
without PySide6, like its siblings).

### GUI suite by module (152)

| Module | Tests |
| --- | --- |
| `test_advanced_settings.py` (Stage 4) | 69 |
| `test_entity_management.py` | 29 |
| `test_job_lifecycle.py` | 18 |
| `test_import_flow.py` | 11 |
| `test_window.py` | 8 |
| `test_entity_table.py` | 6 |
| `test_readiness.py` | 6 |
| `test_preview.py` | 5 |

The 69 Stage 4 tests cover: PTM list/add/edit/remove, 1-based echo, invalid and
out-of-range positions, refusal-keeps-dialog-open, cancel, imported
modifications, ligand has no PTMs; every protein and RNA mode, inline vs path,
source-less modes, switching without data loss, refusal, cancel, DNA/ligand
absence, alignment does not disturb templates; template defaults, one and two
files in order, explicit none vs search, pair parsing and refusal, protein-only,
cancel; CCD inline, external, switching both ways, clear, current-representation
display, no-representation refusal, refresh keeps typing; bond add/remove,
unknown endpoint, missing atom, cancel, imported bonds, preview; version
conflict visibility and resolution, pin never auto-raised; ligand atomicity
(success and rollback, one notification); sequence hints and wrapped-paste
refusal; and the four file-picker paths (CCD browse, cancelled CCD pick,
alignment browse, template add-file).

---

## 14. Known limitations / unverified behavior

* The GUI was exercised **offscreen only** (`QT_QPA_PLATFORM=offscreen`). This
  report does **not** claim a real display, DPI/font behavior, native file
  dialogs, PyInstaller packaging or the user's manual workflow were tested.
* Copy count after creation is still read-only (no supported service
  operation); this is unchanged from Stage 3.
* The full suite cannot run inside `.venv-gui` (pre-existing missing
  `hypothesis` in that environment); GUI tests run in `.venv-gui`, the rest in
  the core interpreter, as in previous stages.
* One pre-existing ruff finding remains in `configbuilder/app/batch_variants.py`
  (a user-modified file), deliberately not touched.
* The 13 stale end-to-end failures above remain; they predate this stage.

---

## 15. Manual verification checklist (Windows GUI)

1. Launch with `python gui.py`.
2. Create a job, add a protein, select it and open the **Advanced** tab.
3. Add, edit and remove a PTM; confirm the position label says 1-based, the
   residue echo tracks the position, and the JSON preview matches.
4. Change the protein MSA mode; confirm only the relevant text/file controls
   appear. Cancel one edit and confirm the previous mode is still shown
   (a new chain stays "automatic" until you change it).
5. Add a template file, add a second one, remove one, then switch to "Let
   AlphaFold search" and back; confirm imported references are preserved when
   you only change MSA.
6. Switch Custom CCD from inline to file (choose a `.cif`), apply, then Clear;
   confirm only one representation ever appears in the preview.
7. Add a covalent bond using the visible entity choices, then remove it and
   answer the confirmation; confirm the bond list and preview agree.
8. Set the version to 1 in Job Settings, add an external MSA or template path,
   and confirm readiness says blocked with a version finding and the preview
   explains the same refusal; raise the version explicitly and confirm it
   clears.
9. Edit a ligand (representation and description) successfully; then try an
   invalid code with a changed description and confirm nothing at all changed.
10. Save the JSON, reopen it, and inspect the final JSON Preview.
11. Cancel a dialog and confirm the job is not marked dirty and the preview is
    unchanged.

Do not claim Stage 4 is accepted until this checklist has been run on a real
display. Stage 5 has not been started.

---

## 16. Working-tree state

Branch `main`, HEAD `121baa8` ("Land the entity-editing hardening and menu
rework"). No `reset`, `clean`, `checkout --`, `restore`, `stash`, commit,
rebase or amend was run. `git status --short` at the end of the stage:

**Deleted (pre-existing, not by this stage):** `JSON_BUILDER_AUDIT_AND_FINALIZATION.md`.

**Modified, pre-existing from earlier stages/the user** (Stage 4 did not edit
these): `configbuilder/app/batch_variants.py`, `configbuilder/app/status.py`,
`configbuilder/app/variant_service.py`, `configbuilder/persistence/__init__.py`,
`configbuilder/persistence/sequences.py`, `configbuilder/ui/render/menus.py`,
`pyproject.toml`, `tests/unit/app/test_status.py`,
`tests/unit/ui/menu_flows.py`, `tests/unit/ui/test_audit_regressions.py`,
`tests/unit/ui/test_edit_hardening.py`, `tests/unit/ui/test_menu.py`,
`tests/unit/ui/test_mod_display.py`, `tests/unit/ui/test_numbered_flows.py`,
`tests/unit/variants/test_quantity_series.py`.

**Modified and extended by Stage 4** (each already carried earlier changes):
`configbuilder/app/configuration_service.py`,
`configbuilder/app/validation_service.py`,
`configbuilder/transform/__init__.py`, `configbuilder/transform/engine.py`,
`configbuilder/transform/mappings.py`, `configbuilder/ui/present/strings.py`,
`configbuilder/validation/engine.py`,
`configbuilder/validation/rules/policy_rules.py`,
`tests/unit/app/test_edit_guards.py`,
`tests/unit/validation/test_no_pin_document_dependency.py`,
`tests/unit/validation/test_rule_checks.py`.

**Untracked, pre-existing** (Stages 1–3 and the user): `RUNNING_THE_APPLICATION.md`,
`af3_analysis/`, `af3builder.py`, `gui.py`, `generated_jobs/`, `pytest-of-Chris/`,
`tests/analysis/`, `tests/unit/test_launchers.py`, `docs/` prompt and earlier
stage reports, and most of `configbuilder/ui/render/qt/`.
`configbuilder/app/version_features.py` is also untracked: created in Stage 3
for the description constant and extended in Stage 4 with the other three
thresholds.

**Untracked, created by Stage 4:**
`configbuilder/ui/render/qt/pages/advanced.py`,
`configbuilder/ui/render/qt/dialogs/advanced_forms.py`,
`tests/gui/test_advanced_settings.py` and this report. The rest of
`configbuilder/ui/render/qt/` (`application.py`, `models.py`, `state.py`, the
other pages/dialogs/windows, `tests/gui/*`) is the Stage 1–3 GUI, extended in
place by Stage 4 and left untracked because the whole directory is untracked.
