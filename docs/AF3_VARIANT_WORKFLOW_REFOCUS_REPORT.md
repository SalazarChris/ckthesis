# Variant workflow refocus — multi-ligand and small-protein inputs

Implementation and evidence report for the task "Refocus the entire variant
service on multi-ligand and small-protein workflows".

Repository state when this work started: branch `main`, commit `6254ada`
("Consolidate AF3 validation and generation safeguards"), pushed to
`origin/main`. The working tree already carried the gate-recovery and
manual-test-pack work described in
[GATE_RECOVERY_IMPLEMENTATION_REPORT.md](GATE_RECOVERY_IMPLEMENTATION_REPORT.md)
and [AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md](AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md);
nothing there was reverted, and this change builds on it.

Everything below was produced without running AlphaFold 3, submitting a job or
touching a prediction directory. Where a conclusion is about the builder, it is
backed by code and tests; where it would need AF3, it says so.

---

## 1. What was wrong with the original variant workflow

Found by reading the workflow end to end and by driving both front ends against
the new example (§3):

1. **The primary journey was not the first thing offered.** The desktop Variants
   page opened on three generic creation paths (one variant / quantity series /
   batch file) and the console's variant menu listed "Set variant job name"
   first. Neither offered the workflow that an existing multi-ligand AF3 input
   actually needs: *these are my entities — which should change?*
2. **No entity inspection.** Nothing showed what an opened file contains per
   entity: type, chain or molecule, how many copies, and what can legitimately
   be varied. The user had to open the entities pages and remember, then pick
   targets out of a combo box in a dialog.
3. **Ligand variance was partly unreachable.** The edit vocabulary has
   `SetComponentRepresentation`, but no front end offered it: the console's
   change menu and the desktop change editor stopped at copy count.
4. **Console change descriptions were placeholders.** `_list_variants` printed
   `edit.get("description", "unknown")` against a `describe_edit` payload that
   has no such key, so every variant preview read "unknown".
5. **The console could crash and mis-word refusals.** Generating variants to a
   folder raised `TypeError: not all arguments converted during string
   formatting` (a prompt without `%s`), and a non-numeric copy count surfaced
   Python's `invalid literal for int()` to the user.
6. **The console wrote with a different policy than the desktop.** Its plan was
   made without passing the project's policies, so it fell back to overwriting
   rather than the project's `Fail` default.
7. **Two renderers for one edit.** The desktop page owned the wording of every
   edit (`_change_text`, ~100 lines); the console had no equivalent, which is
   how (4) went unnoticed.
8. **No multi-entity action at all.** Selecting several records meant creating
   one variant per record through repeated dialogs, with no count, no
   "unchanged" statement and no explicit answer to "independent or combined?".

## 2. What changed

### Shared service (`configbuilder/app/variant_service.py`)

One new, small vocabulary used by both front ends — no second workflow:

| Piece | Purpose |
|---|---|
| `TARGET_STRATEGIES` | The strategies that vary **one entity**, and the families each supports. The single authority for both the picker's "can vary" column and the early refusal a wrong-family target gets. |
| `EntityRow` / `entity_table()` | One row per **record** (an entity definition, not a chain): key, family, copy count, sequence-or-molecule summary, the strategies it supports, and a family note. |
| `target_strategy_choices()` | Only the strategies some entity in *this* base can use. |
| `VariantChoice` label/detail | Wording-free data; each front end renders through its own registry. |
| `TargetPlan` / `plan_target_variants()` | What a selection **would** create: one independent spec per target, the described edits, the unchanged entities and the count. Nothing is committed. |
| `create_target_variants()` | All-or-nothing commit of that plan; a repeated key is refused, never renamed. |
| `component_representation` | New change kind (value: SMILES text), wired through `_edits_for_kind` into `SetComponentRepresentation`, so the existing vocabulary is finally reachable from both front ends. |

`_edits_for_kind` also refuses a copy count that is not a whole number in words,
and the two ligand kinds check the family before building an edit.

### Desktop (PySide6)

* New first creation path **"Vary the entities in this job"**
  (`pages/variants.py`): an entity table (entity, type, sequence/molecule,
  copies, can-vary), extended selection with *Select all* / *Clear selection*, a
  strategy combo, one value field, **Preview variants** and **Create variants**.
  The preview table lists one row per planned variant with its change, and the
  note states the count and which entities stay unchanged. Any control change
  invalidates the plan, so the created variants are the reviewed ones.
* The same `gui.variants_*` registry wording; the page's `_change_text` /
  `_alignment_text` now delegate to `ui/present/labels.change_text` (below).
* The change editor (`dialogs/variant_forms.py`) offers *Ligand representation
  (SMILES)* with an entity picker and a SMILES field, so "Add change…" and the
  target table can no longer diverge.
* The Open dialog's filter now lists `*.txt` as well as `*.json`; the format is
  decided by content, and the `.txt` example is selectable normally.

### Console

* Variant menu reordered so the primary workflow is first:
  `1 Vary the entities in this job`, then name / add entity / edit entity /
  save & reset / batch from file, plus two new actions:
  `7 Generate the variants to a folder` and `8 View all variants`.
* The vary flow prints the entity table, accepts `2,3` or `all`, asks the
  strategy by its own label, asks one value, prints the **plan** with the count,
  each variant's change and the unchanged entities, and only then commits.
* Generation writes through `GenerationService.plan_selection(scope="variants")`
  + `execute` with the **project's own policies passed explicitly** — the same
  pipeline the desktop uses, including validation, the manifest and assets.
* `View all variants` now describes each edit through the shared renderer.

### Shared wording (`configbuilder/ui/present/labels.py`)

`change_text(kind, described)` and `alignment_text(alignment)` moved here from
the desktop page; the page keeps thin delegates and the console calls the same
functions. One edit is worded one way whichever entry point shows it.

## 3. The new standalone example

**Path:** `manual_test_data/af3_builder/inputs/multi_ligand_small_protein_test.txt`
(raw AF3 JSON text, 602 bytes, SHA-256
`d35b09e3218ae3ee4584378d62ed6dd70435763312d7d2227907f122776f9132`).

| Entity | Family | Content | Copies |
|---|---|---|---|
| `A` | protein | `MKTAYIAKQRQISFVKSHFSRQ` | 1 |
| `B` | ligand | CCD `ATP` | **2** (`B`, `F`) |
| `C` | ligand | SMILES `CC(=O)Oc1ccccc1C(=O)O` | 1 |
| `D` | ligand | CCD `MG` | 1 |

Document-level fields: `name` `multi-ligand-small-protein`, `modelSeeds`
`[1, 2, 3]`, `dialect` `alphafold3`, `version` **3** (the builder's default and
the app's supported set 1–4). No external MSA, template or CCD files are
referenced, so the example is self-contained.

The `.txt` extension is deliberate: it proves the Open action decides by
content. `.json` inputs continue to work (both are exercised in
`tests/e2e/test_variant_multi_entity_workflow.py` and
`tests/gui/test_variant_multi_entity_e2e.py`).

**Schema validity vs science.** The document uses only fields the repository's
contract maps (`sequences[].protein.sequence`, `sequences[].ligand.ccdCodes`,
`sequences[].ligand.smiles`, `sequences[].*.id` incl. the list form for copies,
`modelSeeds`, `name`, `dialect`, `version`). It has **not** been validated
against an AlphaFold 3 runtime, and the sequences/molecules are illustrative.

## 4. The dummy/example collection

`manual_test_data/af3_builder/` — the established user-facing collection, with
[README.md](../../manual_test_data/af3_builder/README.md) (formats, inventory,
walkthroughs) and [INVENTORY.md](../../manual_test_data/af3_builder/INVENTORY.md)
(sizes + SHA-256). The new example was added **here**, not in a new directory.

| File | Tests |
|---|---|
| `inputs/multi_ligand_small_protein_test.txt` | **New.** Full AF3 input: multi-ligand + small protein, one ligand with two copies. The multi-entity variant workflow. |
| `batch/proteins_valid.txt` | Protein batch (3 entries, one per line). |
| `batch/proteins_wrapped_fasta.txt` | Invalid on purpose: FASTA header + wrapping is refused. |
| `batch/rna_sequences.txt` | RNA batch — not supported; demonstrates the refusal. |
| `batch/dna_sequences.txt` | DNA batch (2 entries). |
| `batch/ligands_valid.smiles` | SMILES batch: named, bare and commented lines. |
| `batch/ligands_unchecked_syntax.smiles` | Malformed SMILES that the builder accepts (no parser). |
| `batch/empty.txt`, `batch/invalid_sequence.txt` | Empty file; per-line invalid records. |
| `msa/protein/*.a3m`, `msa/rna/*.a3m`, `msa/with spaces/…` | Protein paired/unpaired MSA, RNA MSA, and a path containing spaces. |
| `templates/minimal_template.cif`, `templates/with spaces/…` | Template path workflow (synthetic mmCIF). |

Nothing was moved or deleted. `tests/` and the other fixture trees were left as
they are.

## 5. Validation results for the example and its variants

Run through the real services (`build_services()` → `projects.import_json_commit`):

* **The example:** imports cleanly at version 3; four records; seeds `[1,2,3]`.
  Validation of the base reports no blocking finding. The only advisories are
  the pre-existing `R-ENT-010` "SMILES not checked" warnings, because **no
  chemistry checker is wired** (documented limitation, not a new one).
* **A ligand-representation variant** (`C` → `CCO`): the generated document
  differs from the input in exactly `name` and `sequences[2].ligand.smiles`.
  Everything else — the protein, `B`'s two-copy ATP, `D`'s MG, `modelSeeds`,
  `version` — is byte-identical after re-serialisation (deep-equality assertion
  in `test_a_ligand_representation_change_leaves_every_other_entity_alone`).
* **A protein sequence variant** (`A` → `ACDEFGHIKL`): the ligands survive as
  shown in `test_a_small_protein_sequence_change_keeps_the_ligands`.
* **A copy-count variant** (`B` → 3): the identifier list becomes
  `["B", "F", <new>]` — the entity keeps its identity and the new copy gets a
  registry id.
* **A remove-entity variant** (`D`): only `D` disappears.
* **Blocking cases:** a ligand-only strategy aimed at the protein, a sequence
  change aimed at a ligand, an unknown key, an empty selection, a partially
  invalid selection, a repeated variant key and a non-numeric copy count are all
  refused with the entity named and nothing created.

Generated output went to temporary directories under `tmp_path`; the example
file is asserted byte-identical before and after every flow.

## 6. CLI end-to-end test

`tests/e2e/test_variant_cli_subprocess.py` starts the real process:

```
python af3builder.py            (cwd = tmp_path, answers on stdin)
```

The console's variant interface is menu-driven, so the test answers the prompts
a user sees (there is no variant flag to pass):

```
2                                  open a JSON file
<absolute path to the example>
7                                  the job menu's "Create variants based on this JSON"
1                                  "Vary the entities in this job"
2,3                                the ATP ligand and the SMILES ligand
2                                  "Ligand representation (SMILES)"
CCO                                the new value
y                                  create the planned variants
7                                  "Generate the variants to a folder"
<tmp>/out                          destination
0 0 0                              leave the variant menu, the job, the application
```

**Result:** exit 0, no traceback, stdout contains
`2 variant(s) will be created from the same base.` and
`Unchanged entities: A, D`; `<tmp>/out/multi-ligand-small-protein/` holds the two
variant JSON files and `manifest.json`. Each file changes its own ligand only
(the `B` variant still carries aspirin; the `C` variant still carries ATP); the
protein, `modelSeeds` and `version` are untouched; the example is unchanged.

Further subprocess tests cover the small-protein change (ligands preserved), an
ineligible target (explained, nothing written, no traceback) and a bad copy
count (`the copy count must be a whole number`, no `invalid literal`).

## 7. GUI end-to-end test

`tests/gui/test_variant_multi_entity_e2e.py` builds the real `MainWindow` and
drives it:

1. **Open** — `window.offer_import(path)`: the production preview → dialog →
   commit path, with `ImportPreviewDialog.exec` answered *Accepted* (the only
   stand-in; conftest already replaces the modal message boxes).
2. **Variants → "Vary the entities in this job"** — `open_targets_path()`.
3. **Select** — `select_target("C")` / `select_target("B")` on the entity table
   (extended selection, like Ctrl+click).
4. **Configure** — strategy *Ligand representation (SMILES)*, value `CCO`.
5. **Review** — `plan_targets()`: the plan table has one row per entity and the
   note reads `2 variant(s) will be created … Unchanged: A, D`.
6. **Create** — `create_targets()`: two specs, one edit each.
7. **Generate** — the Generate page: scope *All variants*, destination in
   `tmp_path`, `preview_plan()`, `generate()` (confirm replaced by the conftest
   stub, as for every GUI test that writes).
8. **Verify** — the files exist where the plan said, their JSON is asserted
   field by field (ligand changed, protein and other ligands preserved), the
   manifest lists exactly those variants, and the example is byte-identical.
9. **Invalid operation** — protein + a ligand strategy leaves the plan refused,
   the note names the entity, no spec is created, and the page still works
   afterwards with a valid value.

## 8. Cross-entry-point consistency

`test_the_desktop_and_the_console_write_the_same_variant` runs the **same**
scenario twice — once through the GUI page, once through a subprocess call of
the console — into two separate directories, then compares the generated JSON
documents for deep equality. They are identical, including the document `name`
(the variant's own file stem) and the identifier lists for the multi-copy ligand.

Both entry points share: `entity_table` / `target_strategy_choices` /
`plan_target_variants` / `create_target_variants`, `validate_all`, and
`GenerationService.plan_selection` + `execute`. There is exactly one
implementation of each step.

## 9. Test totals

| Run | Command | Result |
|---|---|---|
| Baseline core (before this change) | `python -m pytest -o addopts="" -q --ignore=tests/gui` | 1124 passed, 1 skipped |
| Baseline GUI (before this change) | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -p no:cacheprovider --basetemp=.pytest-tmp -o addopts="" -q` | 297 passed |
| **After — core** | same as baseline | **1147 passed, 1 skipped** (exit 0) |
| **After — GUI** | same as baseline | **306 passed** (exit 0) |
| Compile | `python -m compileall -q configbuilder` | clean |
| Lint (changed files) | `python -m ruff check --select E4,E7,E9,F <changed>` | All checks passed |

New tests: 19 service-level end-to-end (`tests/e2e/test_variant_multi_entity_workflow.py`),
4 real-CLI subprocess (`tests/e2e/test_variant_cli_subprocess.py`), 9 GUI
(`tests/gui/test_variant_multi_entity_e2e.py`). No test was deleted, skipped or
weakened. Six existing tests were updated because the console's variant menu
numbers changed (the primary workflow became option 1) — their assertions are
unchanged, only the key sequences were renumbered:
`tests/e2e/test_menu_acceptance.py` (3), `tests/e2e/test_entity_lifecycle.py` (1),
`tests/e2e/test_manual_test_data.py` (1), `tests/unit/ui/test_edit_hardening.py` (2),
`tests/unit/app/test_entry_point.py` (1). One GUI test asserted "three choices"
and now asserts the four creation paths, in order. One benign warning remains
(matplotlib's `enablePackrat` deprecation). The single skip is the pre-existing
Windows `chmod` readability test.

## 10. Usability findings and the fixes made

Findings from walking the workflow through both front ends against the example:

| # | Finding | Fix |
|---|---|---|
| 1 | The multi-ligand job is not the first choice offered anywhere | New first creation path in both front ends; console option 1 |
| 2 | No way to see what the opened file contains per entity | Entity table with type, content, copies, supported changes (both front ends) |
| 3 | Ligand representation could not be varied from any UI | New `component_representation` kind in the console menu and the desktop editor |
| 4 | Variant previews printed "unknown" for every edit (console) | Shared `change_text` renderer |
| 5 | Copy count typed as text produced `invalid literal for int()` | "the copy count must be a whole number (got 'many')" |
| 6 | Generating to a folder crashed the console with a traceback | Prompt format fixed (`%s` present); flow exercised by a subprocess test |
| 7 | Console generation ignored the project's overwrite policy | Policies passed explicitly; `Fail` is now honoured |
| 8 | "Independent or combined?" was never stated | The note and the README state it; combining is the explicit "Add change" on one variant |
| 9 | Selecting several targets meant repeated dialogs with no count | One action creates all, previewing the count first |
| 10 | `.txt` inputs were hidden by the Open filter | Filter lists `*.json *.txt` |

## 11. Limitations and remaining gaps

* **One strategy per action.** A single selection cannot mix families, because a
  strategy belongs to a family. Selecting the protein and a ligand with one
  strategy shows *"1 of 2 selected entities cannot take this change"* and names
  the entity. Run the action once per family, or create one variant and add the
  second change to it. This is deliberate — the alternative would be silently
  dropping a target — and is documented in the README walkthrough.
* **One value for the selection.** The target table applies the same new
  sequence/SMILES to every selected entity (each entity becomes its own
  variant). Per-entity values are made one at a time, or by editing a variant
  afterwards.
* **SMILES is not parsed.** No chemistry checker is wired: a malformed SMILES is
  stored and warned about (`R-ENT-010`), not refused. This is unchanged and
  unrelated to the workflow.
* **No docking, enumeration or optimisation** is offered or implied. The ligand
  operations are exactly "replace the representation (SMILES)", "change the copy
  count" and "remove the entity".
* **RNA batch generation is still unsupported** (no batch reader); the variant
  table does offer per-entity RNA changes (sequence, modifications, MSA,
  removal), which is a different operation.
* **AF3 runtime acceptance is unverified.** Everything here is about the
  builder's input contract, validation, JSON shape, asset handling and file
  writing. No inference was run.

## 12. Files changed

Application (scripts): `configbuilder/app/variant_service.py`,
`configbuilder/ui/present/labels.py`, `configbuilder/ui/present/strings.py`,
`configbuilder/ui/render/menus.py`, `configbuilder/ui/render/qt/pages/variants.py`,
`configbuilder/ui/render/qt/dialogs/variant_forms.py`,
`configbuilder/ui/render/qt/state.py`.

Tests and fixtures: `tests/e2e/test_variant_multi_entity_workflow.py` (new),
`tests/e2e/test_variant_cli_subprocess.py` (new),
`tests/gui/test_variant_multi_entity_e2e.py` (new),
`tests/e2e/test_menu_acceptance.py`, `tests/e2e/test_entity_lifecycle.py`,
`tests/e2e/test_manual_test_data.py`, `tests/unit/ui/test_edit_hardening.py`,
`tests/unit/app/test_entry_point.py`,
`tests/gui/test_workflow_simplification.py`,
`manual_test_data/af3_builder/inputs/multi_ligand_small_protein_test.txt` (new),
`manual_test_data/af3_builder/README.md`,
`manual_test_data/af3_builder/INVENTORY.md`.

Nothing was committed. `tools/af3_validation`, `af3_analysis` and
`generated_jobs` were not touched.
