# Stage 3 — Entity management for the AF3 JSON Builder GUI

Delivered: add / inspect / edit / delete for proteins, RNA, DNA and ligands in
the existing PySide6 desktop window, with every mutation routed through the
existing application services. Stage 4 (advanced entity settings), PTMs,
custom CCD, MSA/templates, covalent bonds, variants and batch generation are
**not** part of this change.

Scope note: this report describes only Stage 3. All pre-existing working-tree
changes (including the Stage 1/2 GUI, the launcher work and the user's own
edits) were left untouched — nothing was reset, stashed, cleaned, reverted or
committed.

---

## 1. Summary of delivered functionality

| Capability | Where it lives | How it works |
| --- | --- | --- |
| `Add Protein` / `Add RNA` / `Add DNA` / `Add Ligand` buttons | Entities page action row | Each opens a form dialog, then calls `ConfigurationService.add_record(...)` once through `GuiState`. |
| Sequence form (protein / RNA / DNA) | `dialogs/entity_forms.py::SequenceFormDialog` | Multiline sequence box + optional description. Never builds a record. |
| Ligand form | `dialogs/entity_forms.py::LigandFormDialog` | Two radios in one `QButtonGroup` (CCD **xor** SMILES), a bounded copies spin box, optional description. |
| Entity table | existing `EntityTableModel` (unchanged) | Rebuilt from `configuration.records` after every mutation; order preserved; sorting stays off. |
| Details pane | Entities page | Title, sequence **or** representation, description, modifications, MSA, templates, reverse-complement partner. |
| `Edit Selected…` | Entities page | Sequence chains: `update_record(record_key, sequence, description)`. Ligands: `set_representation(...)` and, when changed, `update_record(description=...)`. |
| `Delete Selected…` | Entities page + `confirm_entity_delete` | Names the identifier(s) and what else goes with the record (duplex partner, multi-copy identifiers), then `remove_record(record_key)`. |
| Refresh after every success | `GuiState.project_changed` → `MainWindow.refresh` | Table, details, readiness/findings, JSON preview, dirty indicator and status line all re-read from the services. |
| Version explanation | page → dialog warning line | A supplied per-entity description on a pinned version < 4 is **explained**, kept in the model, and never silently upgraded or dropped. |

Identity is always the registry's own primary identifier (`EntityRow.record_key`);
no action addresses a record by row number or list position.

---

## 2. Files created and modified

### Created

| File | Rationale |
| --- | --- |
| `configbuilder/app/version_features.py` | One re-export of `transform.mappings.DESCRIPTION_MIN_VERSION`. The GUI needs the number to *word* its warning but may not import a pipeline stage (plan §5.3 rule 6), and enforcement stays in `transform` / the generation gate. No rule is evaluated here. |
| `configbuilder/ui/render/qt/dialogs/entity_forms.py` | The two form dialogs. Deliberately dumb like the import dialog: they collect text/choices, hand them to an `apply` callable, show a refusal on their own error line and stay open. Shared `_ResultDialog` handles the accept/cancel buttons, the warning line and the refusal path. |
| `tests/gui/test_entity_management.py` | 29 Stage 3 tests (see §7). |
| `docs/GUI_STAGE3_IMPLEMENTATION_REPORT.md` | This report. |

### Modified

| File | Change and rationale |
| --- | --- |
| `configbuilder/ui/render/qt/state.py` | Four entity pass-throughs on `GuiState` — `add_record`, `update_record`, `remove_record`, `set_representation` — each calling the matching `ConfigurationService` method with unchanged arguments and emitting `project_changed` **only** on success. The window keeps no second copy of the configuration. |
| `configbuilder/ui/render/qt/pages/entities.py` | Rewritten around the Stage 3 actions: action row, details pane, add/edit/delete handlers, the delete confirmation sentence, the version warning, selection retention, plus two read-back accessors (`detail_title()`, `detail_text(key)`) and a `state` property so the pane can be asserted on without depending on widget order. |
| `configbuilder/ui/render/qt/dialogs/messages.py` | Added `confirm_entity_delete(parent, message)` — the delete question, Cancel as the default button. The wording is the page's (it knows what the record is); this function only asks. |
| `configbuilder/ui/render/qt/dialogs/__init__.py` | Exports the two forms and the delete confirmation. |
| `configbuilder/ui/render/qt/windows/main_window.py` | Wires `notify=self._notify` and `problems=self.report_problem` into the Entities page, so a refusal is reported in the window's existing style (`last_problem_text()`) and a success line goes to the status bar. |
| `configbuilder/ui/present/strings.py` | New `gui.*` entries only: action labels, dialog titles, form labels/hints, the DNA duplex and version-warning sentences, the three delete sentences, the entity-detail labels and the two form buttons. No wording was duplicated from `menu.*`. |
| `tests/gui/conftest.py` | Answers the new delete confirmation with "yes" by default (the established no-modal-hang pattern), so a Stage 3 test that does not care about the wording cannot hang; the Stage 3 tests replace it with a recorder when they assert on the sentence. |

Nothing was added to `[project].dependencies`; the core package still imports no
PySide6 and the GUI modules still skip without it.

---

## 3. How each entity type calls existing services

| Entity | GUI call | Notes |
| --- | --- | --- |
| Protein | `add_record("protein", sequence=..., description=None or text)` | `description` is `None` when the field is empty (unset) and the text when supplied. |
| RNA | `add_record("rna", sequence=..., description=...)` | Same path, family `rna`. |
| DNA | `add_record("dna", sequence=...)` — **once** | One call produces both strands; the GUI never computes a complement, never invents a chain id and never passes `copies`. |
| Ligand (CCD) | `add_record("ligand", representation=<text>, representation_kind="ccd", copies=N, description=...)` | Token splitting (spaces / commas / semicolons) follows the separator the service documents for one multi-component ligand; every token is validated by the service. |
| Ligand (SMILES) | `add_record("ligand", representation=<text>, representation_kind="smiles", copies=N, ...)` | The radio group makes "both at once" unrepresentable. |
| Edit — sequence chain | `update_record(record_key, sequence=..., description=...)` | Unchanged text is passed as `None`, so an unset description stays unset rather than being rewritten. |
| Edit — DNA strand | same as above | Partner propagation is the service's own behaviour. |
| Edit — ligand | `set_representation(record_key, codes=[...])` or `set_representation(record_key, notation=...)`, then `update_record(record_key, description=...)` if the description changed | The representation is read for the form through the model's own `fold_representation`. |
| Delete — any | `remove_record(record_key)` | Where `record_key` is the registry identifier of the selected row. |

An ion is a ligand represented by its CCD code (`ZN`, `NAG`, …): no separate
`ion` family was invented, and a hint says so on the ligand form.

---

## 4. DNA duplex handling (verified against the service)

* The form states, before submitting, that the entered sequence becomes one
  strand and that its reverse-complement partner is created as well
  (`gui.dna_add_hint`); the dialog title is "Add a DNA duplex".
* One service call produces two records with two registry-allocated
  identifiers, allocated back to back (`A`, then `B` for input `ATGC`).
* The details pane shows which strand is paired with which using the model's own
  `duplex_partner` — not a complement the GUI worked out. The
  `entities.py` module contains no complement logic and no `reverse_complement`
  import; a test asserts the module source stays that way.
* Editing a strand calls `update_record` and the service updates the partner;
  the test asserts the partner's new sequence equals the model's
  `reverse_complement` of the requested one, and the service reports
  "both strands of the DNA duplex were updated".
* Deleting either strand removes the pair (service semantics). The
  confirmation explicitly says so — "Entity B is one strand of a DNA duplex;
  removing it removes its partner A as well." — and Cancel leaves both intact.
* **Imported lone strand:** the pane says "No partner strand accompanies this
  DNA strand." and the record is edited and deleted on its own, exactly as the
  service's `duplex_partner`-based behaviour defines. No partner is invented.

## 5. Ligands, multi-component codes and copy counts

* CCD input accepts a code list: `NAG NAG BMA` becomes one ligand with three
  components (`ByCode`), which is the contract's multi-component
  representation; `ZN` is accepted as an ordinary ligand.
* The copy spin box is bounded `1 … 99` (`MAX_LIGAND_COPIES`); the service
  remains the authority on what it accepts.
* A multi-copy ligand's row shows every identifier the registry allocated
  ("A, B") and the row's `record_key` is the primary identifier. Deleting uses
  that key: the service releases the whole multiplicity, which a test confirms
  through `identity.is_taken(...)` and `multiplicity_of(...)`.
* **Copy count is not editable after creation.** There is no existing service
  operation for changing a record's multiplicity, so the form shows the count
  read-only with the explanation `gui.ligand_copies_fixed` instead of mutating
  the record directly. See §9 — this needs a decision.

---

## 6. Refresh, dirty state and error presentation

* Every successful mutation emits `GuiState.project_changed`, which the window
  connects to `refresh()`: table + details, readiness/findings, JSON preview and
  the source/dirty state all re-read from the services.
* Nothing is reimplemented in Qt: readiness comes from `validation.status()`,
  findings from the validation report, JSON from `generation.show_json()`.
* A refusal is shown on the form's own error line (the dialog stays open so the
  value can be corrected) and, for a removal, through the window's
  `report_problem` path; no traceback reaches the user. A cancelled dialog
  mutates nothing and leaves the job clean.
* Entity editing never writes a file and never autosaves; saving stays the
  Stage 2 `Save JSON…` workflow.

---

## 7. Tests and exact results

| Command | Result |
| --- | --- |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui/test_entity_management.py` | **29 passed** in 2.18s |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | **83 passed** (was 54; last run 4.08s) |
| `python -m pytest -o addopts="" -q tests/architecture` | **40 passed** in 9.90s |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/architecture` | **40 passed** in 8.38s |
| `python -m pytest -o addopts="" -q tests/unit/test_launchers.py` | **19 passed** in 1.87s |
| `python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py tests/architecture/test_dependency_rules.py` | **13 passed** in 4.68s |
| `python -m pytest -o addopts="" -q` (core interpreter, full tree) | **13 failed, 1009 passed, 8 skipped** (last run 152.48s) |
| `python -m ruff check --select E4,E7,E9,F configbuilder tests/gui` | 1 finding, **pre-existing** (`app/batch_variants.py` unused `FamilyBRecord`, a user-modified file); none in any Stage 3 file |
| `python -m compileall -q configbuilder/ui/render/qt configbuilder/app/version_features.py tests/gui` | clean |
| `python -m configbuilder < /dev/null` (console smoke) | exit **0**, menu intact |
| GUI startup smoke, real launcher path (empty launch and `--demo`, offscreen, loop stopped by a timer) | `main() returned 0` twice, no error output |
| `python gui.py --help` | usage printed, exit 0 |

### GUI suite by module (83)

| Module | Tests | Covers |
| --- | --- | --- |
| `test_entity_management.py` | **29** | Stage 3 (§ below) |
| `test_job_lifecycle.py` | 18 | Stage 2, unchanged |
| `test_import_flow.py` | 11 | Stage 1, unchanged |
| `test_window.py` | 8 | Stage 1 shell, unchanged |
| `test_entity_table.py` | 6 | Stage 1 projection, unchanged |
| `test_readiness.py` | 6 | Stage 1 readiness/findings, unchanged |
| `test_preview.py` | 5 | Stage 1 preview, unchanged |

### What the 29 Stage 3 tests cover

All drive the real widgets (the dialogs' modal loops are stood in for by
filling the real fields and calling the real `accept`) and then assert on the
service state and the serialized JSON:

1. Add protein — service-allocated identifier `A`, sequence, description left
   `Unset`, row selected, details show the sequence.
2. Add RNA — family, sequence, row label.
3. Add DNA — both strands created by the service; the paired relationship is
   displayed in both directions; the form explains the duplex.
4. Edit a DNA strand — the service-defined partner update is reflected; no
   complement logic exists in the GUI module.
5. Cancel a duplex deletion — both strands intact and the question names the
   partner; confirm — both removed.
6. Imported lone DNA strand — no invented partner, edited and deleted alone.
7. Ligand by CCD — single code, multi-component codes, ion-like `ZN`.
8. Ligand by SMILES, and the two representation radios are mutually exclusive.
9. Multi-copy ligand — every identifier shown, deletion removes the logical
   record and releases all identifiers through the service.
10. Edit sequence/description — unset vs explicitly empty distinction kept; a
    description on a version-3 job shows the warning, is kept, does not change
    the pin, and the preview shows the pipeline's own refusal reason.
11. Refused operations — service reason displayed, nothing mutated, job not
    dirty; a refused removal is reported through the window's problem path.
12. Cancelled add/edit dialogs mutate nothing and leave the job clean.
13. A successful add refreshes the table, the details pane, the readiness rows
    (counts now include the record) and the JSON preview.
14. Record order and JSON serialization order are unchanged by an unrelated
    edit, an unrelated delete preserves the other entity's imported
    `unpairedMsa`/`description`, and new records append in registry order.
15. Stage 1 and Stage 2 tests, launcher tests and architecture tests still pass
    (see the table above).

### Baseline vs current failing core test IDs

```text
Stage 3 baseline (measured before any edit):  python -m pytest -o addopts="" -q
    → 13 failed, 1009 passed, 7 skipped
Current:                                      python -m pytest -o addopts="" -q
    → 13 failed, 1009 passed, 8 skipped
```

* The sorted `FAILED` node-id lists are **identical** (`diff` empty) — no
  regressions, and no test was deleted or weakened.
* The one extra skip is the new `tests/gui/test_entity_management.py` module
  skipping in a PySide6-less interpreter, exactly like its six siblings. The
  GUI-venv run collects and executes all 83.
* The Stage 3 test module writes its temporary import files through pytest's
  own `tmp_path` fixture, like every other test in the suite, so running it
  leaves nothing in the repository.
* The 13 failures are the audited stale end-to-end tests, unchanged:
  `tests/e2e/test_entity_lifecycle.py::test_every_family_survives_a_full_lifecycle`,
  `…::test_an_imported_document_is_editable_like_a_built_one`,
  `…::test_a_long_repeated_chain_of_operations_leaves_consistent_state`,
  `tests/e2e/test_menu_acceptance.py::test_a_blank_job_name_is_generated_by_the_service`,
  `…::test_add_every_entity_family`,
  `…::test_job_settings_change_name_seeds_and_version`,
  `…::test_invalid_job_settings_are_refused_in_the_users_terms`,
  `…::test_the_job_menu_numbering_is_stable_across_states`,
  `…::test_the_entity_modifications_submenu_adds_edits_and_removes`,
  `…::test_ptm_management_adds_edits_and_removes`,
  `…::test_a_ligand_carries_no_modifications_and_is_told_so`,
  `…::test_open_json_can_be_cancelled_at_the_confirm`,
  `…::test_an_opened_job_can_be_edited_and_saved`.

### Environment limitations (not Stage 3 regressions)

* The **whole** tree cannot be run in `.venv-gui`: collection stops at
  `tests/variant/test_output_properties.py` because `hypothesis` is not
  installed in that environment (`NameError: name 'given' is not defined`).
  This is pre-existing; the GUI suite is therefore run in `.venv-gui` and the
  full suite in the core interpreter, which is how the earlier stages reported
  it too.
* `tests/analysis/*` skip without numpy, and
  `tests/unit/persistence/test_sequence_files.py::…` skips on Windows
  (chmod-based read denial) — both pre-existing and unrelated.

---

## 8. Verification honesty

* Everything above was executed in this session. The GUI tests are **offscreen**
  widget/controller tests: no human clicked the window and no real display was
  used, so nothing here should be read as a manual GUI test result. The
  checklist in §10 is for the user to carry out.
* No claim is made about Windows packaging, DPI, or the appearance of the new
  buttons/dialogs on a real screen — they were never rendered on one.

---

## 9. Deliberately deferred issues and gaps found (requests for review)

1. **Single-strand DNA.** The console's optional single-strand choice has a
   known defect (answering "No" can remove all DNA records). The GUI offers **no**
   single-strand path at all — DNA always goes through the duplex-creating
   service call — and the defect itself was left untouched, as instructed.
2. **Copy count cannot be changed after creation.** No service operation exists
   to change a record's multiplicity, so the ligand edit form shows the count
   read-only (`gui.ligand_copies_fixed`). I did not mutate the record directly
   or implement a workaround. If changing copies is required, it needs a new
   reviewed service operation (release old identifiers, allocate new ones,
   report collisions) — a Stage 4+ item.
3. **Version pin vs per-entity description.** A description supplied on a
   version-3 job is kept in the model and explained by the form, but readiness
   still reports the job ready while `show_json` refuses
   ("feature 'description' requires format version 4…"). The conflict is
   currently visible only on the preview page. Recommended: a validation/status
   row for "the model needs a higher version than the pin" (a service-side
   change; deliberately not invented in Qt).
4. **Multi-line paste with interior line breaks** is refused by the model's
   alphabet check ("protein sequence contains characters outside its
   alphabet: ['\n']"). The GUI shows that message and keeps the dialog open,
   and invents no normalization (the console behaves the same way). If
   FASTA-style wrapped input should be accepted, that is a reviewed
   service/model decision, not a GUI one.
5. **Ligand edit split across two calls.** The representation goes through
   `set_representation` and the description through `update_record`; a
   description change is skipped when the representation was already refused,
   but the two are not one atomic operation. A single "update component record"
   service call would be cleaner if one is ever added.
6. **Duplex detection is the model's adjacency-plus-complement rule.** Two
   independently added DNA entries produce two separate duplexes; deleting one
   no longer touches the other. This is inherited, documented behaviour and was
   not changed.

---

## 10. Manual verification checklist (no programming required)

Run everything from the repository root. If the first command prints setup
instructions, follow them once (it never installs anything for you).

1. **Start the window:** `python gui.py` (or `python gui.py --demo` for a
   pre-filled sample). The window opens on the Overview tab.
2. **New job:** toolbar → **New Job**.
3. **Add a protein:** Entities tab → **Add Protein** → paste
   `ACDEFGHIKLMNPQRSTVWY` → **Add**. The table shows one row with id `A`; the
   details pane below shows the sequence.
4. **Add RNA:** **Add RNA** → `ACGUACGU` → **Add**. A second row appears (`B`).
5. **Add DNA:** **Add DNA** → `ATGC` → **Add**. **Two** rows appear (`C` and
   `D`); select each in turn and confirm the details pane names the other as the
   reverse-complement partner and shows `GCAT` for the partner strand.
6. **Add a ligand:** **Add Ligand** → keep **CCD code(s)** selected → type
   `ATP` → **Add**. Now add a second one with `NAG NAG BMA` and a second with
   `ZN` (a metal ion is a ligand). Add a third with **SMILES** selected and
   `CCO` — note that selecting SMILES unselects the CCD option, so both can
   never be sent at once.
7. **Multi-copy ligand:** **Add Ligand** → `NAG`, copies `3` → **Add**. The row
   shows all three identifiers (e.g. `H, I, J`).
8. **Inspect:** click any row — the details pane follows the selection.
9. **Edit:** select the protein, **Edit Selected…**, change the sequence, add a
   short description, **Apply changes**. The table and details update. With the
   job pinned to JSON version 3 a note explains that per-entity descriptions are
   written from version 4 — the description is kept, not thrown away. Raise the
   version in **Job Settings** if you want it written out.
10. **Edit DNA:** select one strand, change its sequence, apply — **both**
    strands change together, as the window explains.
11. **Cancel a delete:** select a DNA strand, **Delete Selected…**, read the
    sentence naming the partner, press **Cancel** — nothing is removed.
12. **Delete:** repeat and press **Delete** — both strands go.
13. **Delete a multi-copy ligand:** select it, **Delete Selected…** — the
    question names every identifier that will be removed.
14. **Check the other views:** Overview shows the counts and readiness;
    JSON Preview shows the document (or the service's reason why it cannot be
    produced). The window title/status bar marks the job as having unsaved
    changes after any edit.
15. **Save and reopen:** toolbar → **Save JSON…**, choose a file, confirm, then
    **Open AF3 JSON…** and pick that file: the preview dialog appears, confirm,
    and every entity you added is back with the same identifiers and order.

If any step does not behave as described, the exact wording shown on screen (or
the status-bar message) is what to report.

---

## 11. Known limitations and recommended next steps for Stage 4

* **Stage 4 (advanced settings) is not implemented**, as instructed: no PTM
  editing beyond what already existed, no custom CCD component editing, no
  MSA/template controls, no covalent-bond editing, no variants, no quantity
  series, no batch-from-file. The details pane *displays* MSA/template state
  read-only, and a per-entity description is the only advanced field this stage
  can set.
* A per-entity description is the only field this stage can edit besides a
  sequence, a ligand representation and a copy count at creation.
* Entity editing is not undoable: there is no undo stack, matching the rest of
  the builder (Cancel-before-apply is the safety net).
* `MAX_LIGAND_COPIES = 99` is a UI bound, not a domain bound — the service
  accepts any whole number ≥ 1 (`add_record` reports its own refusal otherwise).
* Recommended Stage 4 work, in a sensible order:
  1. surface the version-pin/model conflict as a status row or finding (§9.3);
  2. a reviewed service operation for changing a ligand's representation and
     multiplicity as one atomic edit (§9.2);
  3. the advanced per-entity settings the audit lists (alignment sources,
     references, modifications, linkages, component definitions) reusing the
     same dialog + pass-through pattern established here;
  4. decide the FASTA-wrapped-paste question at the service boundary (§9.4).
