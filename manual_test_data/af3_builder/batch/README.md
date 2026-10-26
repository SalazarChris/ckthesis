# Entity batch generation — fixtures and the real input contract

One file of ligands in, one independent AF3 JSON configuration per entry out:
each configuration is the open **base job** plus exactly one new ligand entity.
These files exist to drive that workflow by hand — and to pin what it actually
accepts, which is narrower than "a file of molecules".

Read `../README.md` first; this folder is the batch-specific detail. It holds
the whole batch collection: the sequence and ligand files this builder shipped
with, plus the ligand-workflow fixtures added for the refactor.

---

## 1. What the code really accepts

The reader is `configbuilder/persistence/sequences.py` (`read_smiles_file` /
`parse_smiles_text`), the record builders are
`configbuilder/app/batch_variants.py` (`ligand_specs_for_entries`), and both
front ends reach them through
`GenerationService.plan_ligand_batch` / `generate_ligand_batch`.

| Input | Accepted syntax | Notes |
|---|---|---|
| Named ligand | `ethanol CCO` | The **first whitespace** splits name from SMILES. The name becomes the output file name (slugged) and the summary label. |
| Bare ligand | `CCO` | Auto-named `ligand_N` by the reader, so the file is `…__ligand-N.json`. |
| Comment / blank line | `# …`, empty | Ignored. `#` is a comment **only** at the start of the line; a `#` inside a SMILES is text like any other. |
| Duplicate SMILES | two lines with the same molecule | **Refused** — whole file, the repeated value named. |
| Duplicate names | `x CCO` + `x c1ccccc1` | Both survive: the second key becomes `x-2` (then `-3`…), deterministically in file order. |
| CCD code as an entry | `atp ATP` | **Not a CCD entry.** Stored as the SMILES text `"ATP"`. See §3. |
| Anything per-entry besides SMILES: MSA, templates, PTMs, custom CCD | — | Not expressible in this format. They belong to the base job and are preserved. |

Nothing validates chemistry: SMILES are stored as text, and malformed input is
accepted with an advisory warning (`R-ENT-010`). That is pinned by
`ligands_unchecked_syntax.smiles` and `ligands_ccd_lookalike.smiles` in this
folder.

### Supported-input matrix (verified 2026-10-26)

"CLI" and "GUI" mean the real entry points were driven — `python af3builder.py`
with its prompts answered, and the desktop window's **Entities → Generate ligand
configurations…** action — and the JSON on disk was parsed and checked. A
service-level test is marked as such, never as an end-to-end pass.

| Input category | Actual syntax | Parser support | CLI tested | GUI tested | JSON validated |
|---|---|---|---|---|---|
| SMILES (named) | `name SMILES` | Yes | Yes (`tests/e2e/test_variant_cli_subprocess.py`, `tests/e2e/test_entity_batch_cli_subprocess.py`) | Yes (`tests/gui/test_ligand_file_generation.py`) | Yes — accepted by AF3's own parser |
| SMILES (bare) | `SMILES` | Yes, auto-named | Yes | Yes | Yes — accepted by AF3's own parser |
| Standard CCD code | `name ATP` | **No** — stored as SMILES text | Yes (output shows `"smiles": "ATP"`) | Same behaviour (same service) | Yes |
| Custom CCD (job-wide) | base JSON `userCCD` / `userCCDPath` | Preserved, not per entry | Yes (`base_job_custom_ccd.json`) | Yes — the base's own Custom CCDs tab feeds the same job | UNVERIFIED by AF3's parser (its `userCCD` path needs the compiled CIF extension); the field round-trips byte-identically |
| Ions / multi-copy ligands | base JSON `ccdCodes` | Preserved, not per entry | Yes (ZN and ATP×2 in the same run) | Yes | Yes |
| Protein sequences | one per line, `.txt` | Yes in the service (`batch_specs_for_sequences`); **no front end offers it** | Not exposed | Not exposed | Service-level tests only |
| DNA sequences | one per line, `.txt` | Yes in the service; **no front end offers it** | Not exposed | Not exposed | Service-level tests only |
| RNA sequences | — | **Not supported** — `BATCH_RECORD_BUILDERS` has no RNA builder, so `inspect_batch_file(family="rna")` and `generate_from_file(family="rna")` both refuse in those terms | Not reachable — no front end passes `family="rna"` | Not reachable | N/A |
| MSA / template per entry | — | **Not supported** in a batch file | N/A | N/A | Base-job MSA/templates are preserved |

Why protein/DNA have parser support but no route: the approved refactor narrowed
this feature to ligands and small molecules (decision D2) and the shared service
kept `generate_from_file(family=…)` for protein/DNA with its unit coverage. No
menu item or button calls those families any more; do not claim otherwise. The
same is true of the RNA refusal: it is a **service-level** guarantee
(`tests/unit/app/test_batch_variants.py`, `tests/e2e/test_manual_test_data.py`),
not something a user can reach and see.

---

## 2. Fixtures

### Ligand-workflow files

| File | Entries | Result |
|---|---|---|
| `ligands_named.smiles` | `ethanol CCO`, `acetic-acid CC(=O)O`, bare `c1ccccc1` | 3 configurations: `…__ethanol`, `…__acetic-acid`, `…__ligand-1`, plus `manifest.json` |
| `ligands_duplicate_names.smiles` | `kinase-inhibitor CCO`, `kinase-inhibitor c1ccccc1` | 2 configurations: `…__kinase-inhibitor`, `…__kinase-inhibitor-2` |
| `ligands_duplicate_entries.smiles` | `first CCO`, `second CCO` | Refused: *"the file contains duplicate ligand entries: CCO..."*; nothing written, no folder created |
| `ligands_empty.smiles` | comments only | Refused: *"the ligand file contains no entries (only blank lines or comments)"* |
| `ligands_ccd_lookalike.smiles` | `atp ATP`, `zinc ZN` | 2 configurations whose added ligand is `{"smiles": "ATP"}` / `{"smiles": "ZN"}` — **not** `ccdCodes` |
| `base_job_custom_ccd.json` | not a batch file — the base job | Protein `A`, ATP×2 (`B`,`E`), ZN (`C`), aspirin (`D`), inline `userCCD`, seeds `[7]`, version 3 |

### The pack's original input files

| File | Entries | What it is for |
|---|---|---|
| `ligands_valid.smiles` | `ethanol CCO`, `acetic-acid CC(=O)O`, `C1CCCCC1` | The plain "three named ligands" case, before the workflow fixtures existed |
| `ligands_unchecked_syntax.smiles` | `broken-ring C1CC`, `not-a-smiles this is not a smiles` | Deliberately malformed SMILES: accepted as text, advisory `R-ENT-010` only |
| `proteins_valid.txt` | 3 protein sequences | The protein-family reader (service level; no front end) |
| `proteins_wrapped_fasta.txt` | wrapped FASTA | **Not a FASTA reader** — every line is an entry, so wrapped records are separate (wrong) entries. Pins that the reader is line-based |
| `dna_sequences.txt` | `ATGCATGC`, `GGCCTTAA` | The DNA-family reader (service level; no front end) |
| `rna_sequences.txt` | `ACGUACGUACGU`, `GGGCCCAAAUUU` | Refused: there is no RNA batch builder |
| `invalid_sequence.txt` | `ACDEFGHIK`, `AC1DEFG`, `AC-GU` | Invalid residues: refused with the offending line numbers |
| `empty.txt` | 0 bytes | Refused as "no usable sequences" |

Batch entry files are one entry per line. The base JSON is ordinary AF3 input:
open it with the Open action (the `.json` extension is not special — content
decides).

### Expected output for `ligands_named.smiles` on `base_job_custom_ccd.json`

```
<out>/batch-base-with-ccd/batch-base-with-ccd__ethanol/batch-base-with-ccd__ethanol.json
<out>/batch-base-with-ccd/batch-base-with-ccd__acetic-acid/batch-base-with-ccd__acetic-acid.json
<out>/batch-base-with-ccd/batch-base-with-ccd__ligand-1/batch-base-with-ccd__ligand-1.json
<out>/batch-base-with-ccd/manifest.json
```

Every one of the three files keeps the base exactly as it was — ids
`A`, `B`/`E`, `C`, `D`, the same `userCCD` text, `modelSeeds: [7]`, `version: 3`
— and adds exactly one ligand: id `F`, `G` then `H` respectively (identifiers are
allocated for the whole file up front, so they never collide). No file contains
another entry's molecule.

---

## 3. Things people get wrong

* **A CCD code in a `.smiles` file is not a CCD ligand.** The reader has no way
  to say "this token is a component code", so `ATP` becomes the SMILES text
  `"ATP"`. AF3 will treat it as an invalid SMILES. Add CCD/ion ligands with
  **Add Ligand** (CCD mode) on the base job, where the base is then preserved in
  every generated file.
* **An `.txt` extension means nothing.** What matters is which reader the action
  uses — the ligand one — and whether each line fits the syntax above.
* **The output folder may already exist; the files may not.** An existing file
  with *different* content stops the whole run before anything is written
  (all-or-nothing). An identical file is not a conflict.
* **The name is not in the JSON.** AF3 has no per-entity name field, so the name
  appears in the file name and the summary only.
* **The base job is never modified.** Generating does not add the ligands to the
  open job, so the same file can be run into several folders.

---

## 4. Manual test procedure

Console (`python af3builder.py`):

1. `2` Open a JSON file → `base_job_custom_ccd.json` → expect
   `Name: batch-base-with-ccd`, `Entities: 4` (four definitions, five
   identifiers: the ATP ligand has two copies).
2. `7` *Generate ligand configurations from a file* → `1`.
3. The path to `ligands_named.smiles` → expect `3 entries read …` and the note
   that each is added to the base.
4. A scratch output folder → expect four `Wrote …` lines and
   `Wrote 4 file(s) under …`.
5. `0`, `0`, `0`.
6. Check the three JSON files: base entities and `userCCD` untouched, one added
   `"smiles"` entry each, names in the file names.

Window (`python gui.py`):

1. **Open** the same base JSON.
2. **Entities** → **Generate ligand configurations…**.
3. Pick `ligands_named.smiles`, then an empty folder; the review box lists the
   three entries and the destination.
4. **Generate** → the result box lists the written files; the status bar says how
   many.

Then repeat the refusal cases: `ligands_duplicate_entries.smiles` and
`ligands_empty.smiles` must both write nothing and say why (the console asks for
the folder only after a successful read, so an empty file never reaches that
prompt).

Assert the pack itself is unchanged afterwards (`git status` on this folder).

### Checking the output against AlphaFold 3's own parser

`python tools/af3_validation/af3_validate.py <folder>` runs AF3's
`folding_input.Input.from_json` over every document in a folder (run
`setup_validator.py` once first). With a base job that carries **no** `userCCD`,
the three ligand configurations above come back `ACCEPTED`; with
`base_job_custom_ccd.json` they come back `UNVERIFIED`, because AF3 parses the
`userCCD` field with a compiled extension this tool stubs out. See
`tools/af3_validation/README.md`.

---

## 5. Automated coverage

| Test | Covers |
|---|---|
| `tests/e2e/test_variant_cli_subprocess.py` | the real console: one configuration per entry, names in file names, base intact, duplicates/empty refused, no silent overwrite, malformed SMILES accepted |
| `tests/e2e/test_entity_batch_cli_subprocess.py` | this pack through the real console: base fields and `userCCD` preserved, distinct added identifiers, deterministic `-2` suffix, CCD-lookalike stored as SMILES |
| `tests/gui/test_ligand_file_generation.py` | the real Entities action: preview, cancel paths, per-entry independence, ids, collision refusal, report == files on disk, the `base_job_custom_ccd.json` base surviving |
| `tests/unit/app/test_batch_variants.py` | builders per family, duplicate/empty refusals, identity allocation, name→key slugging, the RNA refusal |
| `tests/unit/persistence/test_sequence_files.py` | the readers themselves (`name SMILES`, comments, blanks, `#` semantics, file errors) |
| `tests/e2e/test_app_pipeline.py` | the protein-family service path end to end (service-level, no menu) |
| `tests/e2e/test_manual_test_data.py` | this pack read through the service, including the invalid/empty/RNA refusals |

Generated output from these runs goes to `tmp_path` / scratch folders; nothing
generated is stored in the pack.
