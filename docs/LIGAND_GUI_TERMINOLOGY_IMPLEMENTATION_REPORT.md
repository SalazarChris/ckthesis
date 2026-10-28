# GUI terminology report — no variant interface, and one clear file action

**Original verification date:** 2026-10-26 · Companion to
`docs/LIGAND_VARIANT_GENERATION_IMPLEMENTATION_REPORT.md`.

The requirement was narrow and absolute: **the desktop window must contain no
user-facing reference to variants or variant generation**, and the file-driven
configuration generation must live under **Entities** as one action. This report
records what was on screen before, what is there now, and how a regression would
be caught.

---

## 1. What the window said before

| Where | Text |
|---|---|
| Sidebar destination | `Variants` (`gui.tab_variants`) — a fourth workspace with its own page |
| Page title / chooser | *Variants & Batch*; four "creation path" buttons: *Vary the entities in this job*, *Create one variant*, *Create a series*, *Create variants from a file* |
| Page body | a variant **list** (`v1`, `v2`…), *Set variant job name*, *Save variant and reset to base*, *Add entity*, *Edit entity*, *View all variants*, *Remove variant*, duplicate/rename dialogs |
| Target table | columns *Entity · Type · Summary · Instances · Can take*, the note `N variant(s) will be created`, `Unchanged: …` |
| Generate page | scope radios *Base job only* / *All variants* / *Selected variant*, a variant picker, and strings such as `gui.output_variant`, `gui.output_scope_needs_variant` |
| Dialogs | `DuplicateVariantDialog`, `NewVariantDialog`, `RenameVariantDialog`, `VariantChangeDialog` |
| Tooltips/status | `gui.variants_*` (about 200 registry entries) |

## 2. What the window says now

| Where | Text |
|---|---|
| Sidebar | `Overview` · `Entities` · `Generate` — three destinations, nothing else |
| Entities, action row | **`Generate configurations from file…`** — select one of the supported input kinds (protein, DNA, RNA, SMILES or CCD), choose a file and destination, review and generate. The open base job is not modified. |
| Entities, beside it | a hint: *"Each entry is added to the base job as one entity of the selected input type; nothing on this screen changes."* |
| Review box | *Review input file* — selected type and its parsed entries, output folder and file count, with a note that each entry becomes one additional entity while the base itself is not modified; buttons **Generate** / **Cancel** (Cancel is the default) |
| Result box | *Generated configurations* — `N file(s) written:` + the paths, or *"Nothing was written: <reason>"* with the plan's findings/conflicts |
| Status bar | `Wrote N file(s) for the input file.` |
| Generate page | step 1 is a sentence, not a picker: `One AF3 JSON file. No manifest.` — the page writes the open job's own file |

## 3. Registry changes (`configbuilder/ui/present/strings.py`)

**Removed** (≈470 lines, every one previously user-facing):

- the whole Stage 5 block: `gui.tab_variants`, `gui.variants_*` (chooser titles,
  target table headers, strategy labels, notes, list actions, dialogs),
  `gui.variant_*` companions, duplicate/rename/series/batch wording;
- the Generate page's scope block: `gui.output_group_scope` answers,
  `gui.output_variant`, `gui.output_scope_*` (needs-variant, unavailable,
  all/selected labels), `gui.output_kind_variant`, `gui.output_step1_hint`.

**Rewritten** so no string promises a choice that is gone:

| Key | Before | Now |
|---|---|---|
| `gui.output_group_scope` | "1. What do you want to generate?" | "1. What is written" |
| `gui.output_intro` | mentioned "the planned project folder…and the manifest" | "This page writes the open job's own AF3 JSON file and any external files it copies; Save JSON in the FILE footer writes the one file directly. A file of ligands is generated from the Entities page." |

**Added**: `gui.action_ligand_file`, `gui.action_ligand_file_hint`,
`gui.entity_ligand_note`, `gui.ligand_file_dialog`, `gui.ligand_file_filter`,
`gui.ligand_folder_dialog`, `gui.ligand_preview_{title,entries,row,more,destination,files,note,accept}`,
`gui.ligand_result_{title,written,errors,skipped,refused,nothing}`,
`gui.ligand_notice`, plus the console's `menu.ligand_*` block.

The console's job menu entry is `7. Generate configurations from a file (sequences or ligands)`;
its screen is `CONFIGURATION GENERATION FROM A FILE` with *Base job / Base entities*,
one action and `0. Back`. A following input-kind menu explicitly distinguishes
protein, DNA, RNA, SMILES and CCD-code files.

## 4. Wording rules applied

- **One word for the thing:** *entity* in the window (`Entity`, `Entities`, *Add
  Entity* is spelled as the existing *Add Protein / Add Ligand* family actions),
  *input entry* for one file record, *configuration* for an output file. The
  selected kind determines whether that entry is a sequence, SMILES notation
  or a CCD component code. "Variant" appears nowhere on screen.
- **The base is named as protected:** every screen of the workflow says the base
  job is not modified, because that is the property users worry about.
- **The write is named honestly:** the report lists the files that were written,
  and a refusal says `Nothing was written: …` — never a success message for a run
  that wrote nothing.
- **No ellipsis-only labels:** *Generate configurations from file…* opens a
  dialog flow, so it keeps the ellipsis; *Generate* in the review box commits the
  run and has none.
- **Sentence case for prose, title case for destinations**, as before; the new
  strings follow the existing registry style.

## 5. Internal names deliberately kept

`VariantService`, `services.variants`, `app/variant_service.py`,
`app/batch_variants.py`, `variants/` (specs, edits, expansion) and the
`VariantSpec` type are **not** renamed. They are the internal architecture the
generation pipeline is built on; renaming them would be a broad refactor with no
user-visible benefit (explicitly out of scope). What matters — and what is
asserted — is that none of them reaches a label, tooltip, title, message or
button.

Remaining occurrences of the word in the UI package were checked by
`grep -ri variant configbuilder/ui`: only `services.variants` lookups and
docstrings/param names (e.g. `inspect_ligand_file`'s "no variant, no file, no
write"). No registry key contains `variant`.

## 6. How a regression is caught

| Test | Assertion |
|---|---|
| `tests/gui/test_window.py::test_the_window_shows_its_destinations` | exactly Overview, Entities, Generate, in order, and `destination_pages()` matches |
| `tests/gui/test_mockup_shell.py::test_the_sidebar_holds_the_three_destinations_in_order` | the sidebar's own labels |
| `tests/gui/test_workflow_simplification.py::test_no_page_manages_an_in_memory_variant_list` | `variants_page` does not exist, `GuiState` has no `specs`/`add_spec_with_edit`, `gui.tab_variants` is not a key, and no key starts with `gui.variants_` |
| `...::test_the_ligand_file_action_lives_on_the_entities_page` | the button's text/tooltip are the registered ones, it is enabled and inside Entities, and no other button on that page says "generate" |
| `tests/gui/test_file_generation.py::test_the_only_entry_point_is_an_action_on_the_entities_page` | no visible button in the whole window contains "variant" |
| `tests/unit/ui/test_string_registry.py` | the registry meta-tests: every key is referenced where it is used, and no dangling key survives |
| `tests/gui/test_workflow_simplification.py::test_generate_offers_no_second_kind_of_output` | the Generate page has no variant picker, no `choose_scope`, and plans `scope="base"` only |

## 7. Console ↔ window parity

Both front ends call `GenerationService.generate_input_batch(path, root, kind,
<project overwrite policy>, <project path policy>)`, so they cannot disagree on
the selected reader, entity kind or output; the SMILES-only wrapper remains
available for callers that need only that case. The differences that remain are
interaction-only and stated here:

| Step | Console | Window |
|---|---|---|
| File selection | typed path or numbered directory listing | native open dialog |
| Preview | printed lines (count, entries, note) | one review box (count, up to 12 entries + "…and N more", folder, file count, note) |
| Confirmation | the destination prompt | **Generate** button, Cancel default |
| Result | `Wrote <path>` lines + total | result box with the same paths |

Neither front end keeps a variant list, and neither offers a second entry point.

## 8. What was **not** changed

- Entity management: Add Protein/RNA/DNA/Ligand, Edit, Delete, MSA modes,
  templates, PTMs, Custom CCDs, covalent bonds, the entity picker and its three
  work areas.
- The Generate page's plan → review → confirm → result sequence, its policies,
  asset copying and findings navigation.
- Import/export wording and the FILE footer actions.
- Any internal name (see §5).

## 9. Verification

**Historical result at the original cleanup commit:**
`QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -o addopts="" -q --basetemp=.pytest-tmp`
→ **267 passed**. Current suite counts and the explicit-kind extension are
recorded in `docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14.
- `grep -ri variant configbuilder/ui` → internal identifiers and docstrings only.
- `grep -n "gui.variants_" configbuilder/ui/present/strings.py` → no matches.

These results were re-run on the commit that carries the cleanup (`a4a488c`);
the full suite at that commit is **1430 passed, 1 skipped**.
- Every screen above was exercised by the tests named in §6, through the real
  widgets, not by reading source text.
