# Ligand configuration generation — implementation report

**Original implementation:** 2026-10-26 · **Current follow-up verification:** 2026-10-28

This report records the approved Phase 2 refactor (D1–D4). Subsequent changes
extended its file action to protein, DNA, RNA, SMILES and CCD-code input kinds;
the current tests, output checks and support matrix are recorded in
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14.

---

## 1. What changed and why

The variant-generation service used to be a **variant manager**: a list of
in-memory specifications the user created, named, edited and finally exported.
Opening a file of molecules was one menu step among eight, and the write was a
second one. The approved Phase 2 decision was to simplify the UI around file-based
configuration generation and stop exposing variant management in either front
end. The original approved scope was ligand-focused; a later follow-up extended the
same one-step workflow to explicitly selected protein, DNA, RNA, SMILES and CCD
input kinds.

That is what was implemented:

- the console's variant submenu became **one** screen with **one** action;
- the desktop window lost its **Variants & Batch** destination entirely and
  gained one action on **Entities**;
- both front ends call the **same** application method
  (`GenerationService.generate_input_batch`), which plans, validates and writes
  in a single call, reusing the existing parser, spec builder, validator and
  writer; the SMILES-only convenience method remains as a wrapper;
- the documented `name SMILES` column is now honoured: the name becomes the
  output file's name and the summary label instead of being discarded;
- a saved job whose external files were copied beside it can be reopened and
  re-saved (relative paths are resolved against the JSON's own folder on import).

Nothing about entity management, MSA/template handling, PTMs, custom CCDs or
covalent bonds was removed, and the shared protein/DNA/RNA batch code stays in
the service layer.

---

## 2. Obsolete menu options removed

Console, job menu `7` (was *Create variants based on this JSON*):

| Was | Now |
|---|---|
| 1 Vary the entities in this job | **removed** (decision D1) |
| 2 Set variant job name | removed |
| 3 Add entity | removed here; **kept** as job menu `2` |
| 4 Edit entity | removed here; **kept** as job menu `3` |
| 5 Save variant and reset to base | removed |
| 6 Generate variants from file | folded into the single action |
| 7 Generate the variants to a folder | folded into the single action |
| 8 View all variants | removed; the run reports the files it wrote |

The job menu entry is now `7. Generate configurations from a file (sequences or ligands)`,
which opens a screen showing the base job, its entity count, one action
(`1. Load an input file and generate configurations`) and `0. Back`. The next
menu explicitly asks whether the file contains protein, DNA, RNA, SMILES, or
CCD-code entries; `.txt` alone is never used to guess.

Desktop: the **Variants & Batch** page (`pages/variants.py`), its dialogs
(`dialogs/variant_forms.py`), the variant list model, the sidebar destination and
every related string were deleted. The window is **Overview · Entities ·
Generate**.

---

## 3. Final user workflow

**Console**

The job menu's file-generation action opens one simple screen, then the user
selects one of five explicit input kinds before choosing the file: Protein
sequence, DNA sequence, RNA sequence, SMILES ligand or CCD-coded ligand. The
service previews and validates records, asks for an output folder, then writes
one independent AF3 configuration per entry and reports actual paths. The
`.txt` extension never determines the type.

**Desktop**

Entities → **Generate configurations from file…** → choose input kind → native
file picker → review the selected kind and entries → choose/confirm the output
folder → generate → result dialog listing actual written files or actionable
errors.

The shared application method is `GenerationService.generate_input_batch`; the
open base is never modified. A custom CCD definition is not a batch-input kind:
it is job-wide `userCCD` / `userCCDPath` state retained from the base.

---

## 4. Input formats actually supported

The file-generation action supports five **explicitly selected** kinds. The
syntax is documented in
`manual_test_data/af3_builder/batch/README.md` and each kind uses one shared
reader/builder path:

| Kind | Format / output |
|---|---|
| Protein sequence | One protein sequence per non-empty line → `protein.sequence` |
| DNA sequence | One DNA sequence per non-empty line → the input strand and its reverse-complement `dna` strand in one output, through the normal Add DNA record constructor |
| RNA sequence | One RNA sequence per non-empty line → `rna.sequence` |
| SMILES ligand | `name SMILES` or bare SMILES → `ligand.smiles`; names are safe, deterministic output keys/summary labels, not AF3 fields |
| Standard CCD ligand | One or more CCD component codes per line → `ligand.ccdCodes` |

No FASTA headers/wrapping or custom-CCD definition files are batch formats. The
user's explicit kind, not a `.txt` extension or content heuristic, selects the
reader. The misrouted sequence/SMILES case is refused with an actionable hint;
there is no automatic reinterpretation.

SMILES entries are checked by the project's notation grammar (`validation/smiles.py`)
for characters, brackets, ring closures and allowed unbracketed atoms. This is
not chemical validation: no dependency or inference run establishes valence,
aromaticity or whether a grammatical string denotes a real molecule. A CCD code
or sequence entered in SMILES mode is refused with its line number. See
`docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §3 and
`manual_test_data/af3_builder/batch/README.md`.

Custom CCD remains job-wide: definitions are provided on the base as
`userCCD` / `userCCDPath` and retained in every output; they are not per-entry.

---

## 5. Behaviour with several ligands

One file, N entries → N configuration files plus `manifest.json`, all under
`<chosen folder>/<job-slug>/`:

```
<folder>/<slug>/<slug>__<entry-name>/<slug>__<entry-name>.json
<folder>/<slug>/manifest.json
```

- **Add, not replace.** Each configuration is the base job plus exactly one new
  entity of the explicitly selected input kind. Nothing is substituted into an
  existing entity slot.
- **Independent.** No configuration contains another entry's molecule; each is
  expanded from the same unchanged base.
- **Identifiers** are allocated for the whole file up front from a throwaway
  clone of the base registry, so every configuration's added entity has its own
  id that collides with nothing (`F`, `G`, `H` for three entries after a base
  holding `A`–`E`).
- **Names** are slugged for the path; duplicate names get `-2`, `-3` in file
  order; an unsluggable name falls back to `ligand-NN`. The name is never added
  to the AF3 document (the schema has no field for it).
- **All-or-nothing.** A malformed line, a duplicate molecule, an empty file, a
  base that fails validation, or an existing file with different content refuses
  the whole run and writes nothing. Re-running the identical file into the same
  folder succeeds and rewrites identical bytes; that is the established
  definition of "not a conflict".
- **No persistent list.** The specs built for the run are internal to the
  service, are never committed to the project, and disappear with it (decision
  D4). Repeating a run therefore does not hit "this key already exists".

---

## 6. Why the base and the variants stay independent

Structural, not defensive:

- `batch_variants.specs_for_entries` allocates identities from
  `configuration.identity.clone()` — the project's registry never claims an id no
  record holds;
- `variants.expand(configuration, specs)` applies every spec to **the same base
  object**, so `base + AddRecord` never chains (`A`, then `A+B`, then `A+B+C`);
- `AddRecord` re-reserves the id inside each variant's own expansion-time clone;
- the service never calls `add_spec`, so the open job is untouched — tests assert
  the configuration object is identical before and after, and that the window
  does not even become dirty.

---

## 7. Files changed

| File | Change |
|---|---|
| `configbuilder/app/batch_variants.py` | ligand specs from `(line, name, smiles)`; name → slugged key with deterministic duplicates; ASCII ellipsis in refusals |
| `configbuilder/app/variant_service.py` | `ligand_file_specs` (the one construction preview and generation share); `inspect_batch_file` keeps names; documented dead-name defect fixed |
| `configbuilder/app/generation_service.py` | `plan_ligand_batch` / `generate_ligand_batch`: read → specs → validate → plan → execute in one call |
| `configbuilder/app/validation_service.py` | `validate_specs(specs)`: the authoritative base+variants validation for specs that are never committed |
| `configbuilder/app/results.py` | `LigandBatchOutput` (plan, written, skipped, errors, ok) |
| `configbuilder/app/project_service.py` | import resolves the document's relative resource paths against its folder |
| `configbuilder/transform/from_wire.py` | `rebase_resource_paths` (string-only, no filesystem import) |
| `configbuilder/transform/__init__.py` | exports it |
| `configbuilder/ui/render/menus.py` | the one-screen ligand menu + one-step generation; variant submenu deleted |
| `configbuilder/ui/present/strings.py` | `menu.ligand_*`, `gui.ligand_*`, `gui.action_ligand_file*` added; ~470 lines of variant/scope/picker strings removed |
| `configbuilder/ui/present/labels.py` | variant labels removed |
| `configbuilder/ui/render/qt/pages/entities.py` | the action, its modal seams and `generate_from_file()` |
| `configbuilder/ui/render/qt/dialogs/batch_input.py` | file-kind/file/folder pickers, review box, result box |
| `configbuilder/ui/render/qt/pages/generate.py` | base-only scope; stale handler and scope picker removed |
| `configbuilder/ui/render/qt/state.py` | `inspect_ligand_file`, `generate_ligand_configurations`; all variant wrappers removed |
| `configbuilder/ui/render/qt/windows/main_window.py` | three destinations; stale `_variants.refresh()` removed |
| `configbuilder/ui/render/qt/widgets.py` | variant glyph removed |
| `configbuilder/ui/render/qt/models.py`, `dialogs/__init__.py`, `dialogs/messages.py`, `pages/__init__.py` | variant pieces removed, ligand pieces exported |
| `configbuilder/ui/render/qt/pages/variants.py`, `dialogs/variant_forms.py` | **deleted** |
| `.gitignore`, `pyproject.toml`, `.github/workflows/ci.yml` | track the suite, fixtures, docs and CI again; restore the `dev` extra and the pytest table |
| `manual_test_data/af3_builder/**` | the fixture packs (templates, entity batch), updated READMEs |
| `tests/**` | retired variant-page suites replaced by ligand/template/batch suites (list in the companion report) |

---

## 8. Tests run and results

| Suite | Result |
|---|---|
| Core — everything but the GUI (`pytest tests --ignore=tests/gui`) | **1163 passed, 1 skipped** |
| GUI (`tests/gui`, offscreen Qt) | **267 passed** |
| Front ends as real processes (`tests/e2e/test_template_cli_subprocess.py`, `test_entity_batch_cli_subprocess.py`, `test_variant_cli_subprocess.py`) | **12 passed** |
| Batch pack + readers (batch e2e + `test_manual_test_data.py` + `test_batch_variants.py`) | **61 passed** |
| AlphaFold 3's own input parser (`tools/af3_validation/run_all.py`) | **PASS** — 13/13 positive, 8/8 negative, corpus 21 accepted + 2 unverified, round trip 13/13 |

The single skip is the pre-existing Windows `chmod` readability test. The audit's
reference numbers (core 1147/1, GUI 306, batch 70/1) differ because the retired
interface took its suites with it: 38 Variants & Batch GUI tests and 9
variant-workflow GUI tests were deleted with the page, and the variant-menu/spec
tests went with the console flow. Replacements: 14 ligand-workflow GUI tests, 5
template GUI tests, 4 template CLI tests, 3 batch CLI tests, 16 unit tests. Core
therefore grew by 16 and GUI fell by 39; no remaining assertion was weakened to
make either suite pass, and no pre-existing failure was hidden.

Live checks performed besides the automated suites (records in
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md`): the console was run
as a real process against the fixture packs and the written JSON read back; the
window was driven offscreen through its real widgets and saved files inspected.

---

## 9. Git

- Branch `main`, remote `origin`
  (`https://github.com/SalazarChris/ckthesis.git`), upstream `origin/main`.
- Implementation commit: `a4a488c` ("Make the ligand-file workflow the variant
  service, and verify it end to end") — 290 files: the `configbuilder` changes
  above, the test suite and its fixtures, the manual test pack, the
  documentation and the CI workflow.
- The documentation commit that records the hashes in these reports follows it,
  and both were pushed together to `origin/main`; `git log --oneline origin/main`
  shows them in that order.

---

## 10. Manual testing procedure

1. `python af3builder.py` (console) or `python gui.py` (window).
2. Open a base job: the pack's
   `manual_test_data/af3_builder/batch/base_job_custom_ccd.json`
   (console `2` + path; window **Open**). Expect `Entities: 4` / four rows.
3. Console: `7` → `1` → `4` (SMILES) → the path to
   `manual_test_data/af3_builder/batch/ligands_named.smiles` → a scratch output
   folder. The `4` selects SMILES from the five-kind menu.
   Window: **Entities** → **Generate configurations from file…** → **Ligands by
   SMILES** → the same file → review and select a scratch folder → **Generate**.
4. Expect **three** configuration files named `…__ethanol.json`,
   `…__acetic-acid.json`, `…__ligand-1.json` plus `manifest.json`, and the report
   listing exactly those paths.
5. Open each file: the four base definitions (`A` protein, `B`/`E` ATP, `C` ZN,
   `D` aspirin) and the `userCCD` text are unchanged; one extra ligand entry
   carries `"smiles"`: `CCO`, `CC(=O)O`, `c1ccccc1`.
6. Run it again into the same folder → same files, no error. Edit one file's
   bytes, run again → refused, nothing written, the edited file untouched.
7. Replace the input with `ligands_duplicate_entries.smiles` or
   `ligands_empty.smiles` → a refusal naming the reason, and no output folder is
   created.
8. Confirm the job on screen is unchanged afterwards (still four entities) and
   that `git status` shows the pack untouched.

### Protein sequence regression

Use a minimal base with one protein entity, choose Protein sequences (`1` in the
console or **Protein sequences** in the window), and select
`manual_test_data/af3_builder/batch/proteins_minimal.txt`. Four outputs should be
written, each preserving the base and adding exactly one protein sequence:
`MVT`, `MVS`, `MVY`, or `TEST`. Inspect each `protein.sequence`; none of these
records should be serialized under `ligand.smiles` or `ligand.ccdCodes`. These
short strings verify parsing and serialization only, not biological usefulness
or AF3 prediction quality. The equivalent real CLI and offscreen-Qt flows are
automated in the batch tests listed in §9 and their results in
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14.

---

## 11. Remaining limitations

- The shared file action supports explicit protein, DNA, RNA, SMILES and
  standard CCD-code input kinds. Custom CCD definitions, ions, MSA, templates
  and PTMs are job-wide base properties preserved in each output, not per-entry
  file formats.
- ~~No chemistry validation: malformed SMILES are stored with an advisory, and a
  CCD-looking token becomes a SMILES string.~~ **Partly closed 2026-10-27:**
  notation that is not SMILES grammar (including a CCD-looking token) is now
  refused with the defect named, and the same checker is used by the file action
  and by the base-job rule `R-ENT-010`. Still open, and still not claimed:
  chemistry — a grammatical notation is written whether or not it denotes a real
  molecule (`docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §3).
- Output naming embeds the job name, so two different jobs with the same name
  into one folder collide — caught as a conflict, never overwritten.
- A `manifest.json` is written beside the configurations (the generation
  pipeline's own summary of the run). It is not an AF3 input file.
- Protein, DNA, RNA, SMILES and CCD batches are now available in both CLI and GUI
  and are exercised through end-to-end test paths. The GUI tests run the real Qt
  widgets offscreen; no human-operated interactive session was performed.
  FASTA and per-entry custom-CCD definitions remain unsupported; SMILES grammar
  checks are not chemical validation. See the current matrix and input contract
  in `manual_test_data/af3_builder/batch/README.md`.
- AlphaFold 3 inference was not run, but its own input parser was: the builder
  corpus currently reports 33 documents ACCEPTED and 2 custom-CCD documents
  UNVERIFIED by `folding_input.Input.from_json` because AF3 parses `userCCD`
  with a compiled extension the validation tool stubs out. Current test counts
  and parser results are recorded in
  `docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14.
