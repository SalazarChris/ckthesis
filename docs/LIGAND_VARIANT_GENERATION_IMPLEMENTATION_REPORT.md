# Ligand configuration generation — implementation report

**Date:** 2026-10-26 · **Branch:** `main` · Supersedes the plan in
`docs/LIGAND_VARIANT_GENERATION_AUDIT.md` (Phase 2 of that audit, decisions
D1–D4 approved).

---

## 1. What changed and why

The variant-generation service used to be a **variant manager**: a list of
in-memory specifications the user created, named, edited and finally exported.
Opening a file of molecules was one menu step among eight, and the write was a
second one. The approved decision was to make the service do one thing — *a file
of ligands in, one independent AF3 configuration per entry out* — and to stop
exposing variant management in either front end.

That is what was implemented:

- the console's variant submenu became **one** screen with **one** action;
- the desktop window lost its **Variants & Batch** destination entirely and
  gained one action on **Entities**;
- both front ends call the **same** application method
  (`GenerationService.generate_ligand_batch`), which plans, validates and writes
  in a single call, reusing the existing parser, spec builder, validator and
  writer;
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

The job menu entry is now `7. Generate ligand configurations from a file`, which
opens a screen showing the base job, its entity count, one action
(`1. Open ligand input file and generate configurations`) and `0. Back`.

Desktop: the **Variants & Batch** page (`pages/variants.py`), its dialogs
(`dialogs/variant_forms.py`), the variant list model, the sidebar destination and
every related string were deleted. The window is **Overview · Entities ·
Generate**.

---

## 3. Final user workflow

**Console**

```
job menu 7  →  LIGAND CONFIGURATION GENERATION
               Base job: <name>   Base entities: <n>
               1. Open ligand input file and generate configurations
               0. Back
```

After `1`: the input file path → a preview of the entries (count, each entry, or
the refusal) → the output folder → generation → one `Wrote <path>` line per file
and a total.

**Desktop**

Entities → **Generate ligand configurations…** →

1. the native open dialog (ligand lists, or all files);
2. a review box: how many entries were read, each `name  SMILES` pair, the output
   folder, how many files will be written, and the statement that the base job is
   not modified;
3. the folder picker;
4. the result box: the files actually written, or the refusal with its findings.

The action is disabled for nothing in particular — it reads the open job and
writes files; it never changes the job.

---

## 4. Input formats actually supported

The workflow accepts **ligand/small-molecule lists only** (decision D2):

| Syntax | Meaning |
|---|---|
| `name SMILES` | first whitespace splits them; the name names the output file |
| `SMILES` | auto-named `ligand_N`, so the file is `…__ligand-N.json` |
| blank line, line starting `#` | ignored |

`persistence.read_smiles_file` reads it; nothing else was added, and no new file
format exists. SMILES are **not** chemically validated (no parser is wired), so
malformed input is accepted with an advisory. A CCD code typed as an entry is
stored as SMILES text — the file format has no way to say "component code";
CCD/ion ligands belong to the base job (see
`manual_test_data/af3_builder/batch/README.md`).

Protein and DNA sequence batches remain implemented in
`VariantService.generate_from_file(family=…)` for API compatibility and unit
coverage, but **no front end offers them**; RNA has no batch reader and refuses.

---

## 5. Behaviour with several ligands

One file, N entries → N configuration files plus `manifest.json`, all under
`<chosen folder>/<job-slug>/`:

```
<folder>/<slug>/<slug>__<entry-name>/<slug>__<entry-name>.json
<folder>/<slug>/manifest.json
```

- **Add, not replace.** Each configuration is the base job plus exactly one new
  ligand entity — the semantics the audit found established and recommended
  keeping. Nothing is substituted into an existing ligand slot.
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

- `batch_variants.ligand_specs_for_entries` allocates identities from
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
| `configbuilder/ui/render/qt/pages/entities.py` | the action, its four modal seams and `generate_ligand_file()` |
| `configbuilder/ui/render/qt/dialogs/ligand_batch.py` | **new**: file picker, folder picker, review box, result box |
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

## 10. Manual testing procedure (a file of several small molecules)

1. `python af3builder.py` (console) or `python gui.py` (window).
2. Open a base job: the pack's
   `manual_test_data/af3_builder/batch/base_job_custom_ccd.json`
   (console `2` + path; window **Open**). Expect `Entities: 4` / four rows.
3. Console: `7` → `1` → the path to
   `manual_test_data/af3_builder/batch/ligands_named.smiles` →
   a scratch output folder.
   Window: **Entities** → **Generate ligand configurations…** → the same file →
   the same folder → review → **Generate**.
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

---

## 11. Remaining limitations

- Ligand files are SMILES lists: no CCD codes, custom CCDs, ions, MSA, templates
  or PTMs per entry; those are base-job properties and are preserved.
- No chemistry validation: malformed SMILES are stored with an advisory, and a
  CCD-looking token becomes a SMILES string.
- Output naming embeds the job name, so two different jobs with the same name
  into one folder collide — caught as a conflict, never overwritten.
- A `manifest.json` is written beside the configurations (the generation
  pipeline's own summary of the run). It is not an AF3 input file.
- Protein/DNA batch remains service-only; RNA batch does not exist.
- AlphaFold 3 was not *run*, but its own input parser was: every document this
  workflow wrote from a base without `userCCD` is `ACCEPTED` by
  `folding_input.Input.from_json` (`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md`
  §12). Documents from the custom-CCD base come back UNVERIFIED because AF3
  parses `userCCD` with a compiled extension the validation tool stubs out.
