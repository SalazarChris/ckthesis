# Entity batch generation — fixtures and the real input contract

One input file in, one independent AF3 JSON configuration per entry out: each
configuration is the open **base job** plus exactly one new entity of the type
the user chose. The user says what the file holds **before** the file is read —
the extension never decides. These files exist to drive that workflow by hand —
and to pin what it actually accepts, which is narrower than "a file of things".

Read `../README.md` first; this folder is the batch-specific detail. It holds
the whole batch collection: the sequence and ligand files this builder shipped
with, plus the workflow fixtures added for the refactor.

---

## 1. What the code really accepts

The workflow asks **what the file contains** first (console: *"What does the
file contain?"* with five numbered kinds; window: the **Input type** box with
five buttons), and that answer alone selects the reader and the record builder.
Readers live in `configbuilder/persistence/sequences.py`, the builders and the
single kind→builder table in `configbuilder/app/batch_variants.py`
(`specs_for_entries`, `INPUT_KINDS`), and both front ends reach them through
`GenerationService.plan_input_batch` / `generate_input_batch` — one path, so a
kind cannot mean different things in a preview and in a write.

| Kind (the choice the user makes) | Reader | Accepted syntax |
|---|---|---|
| `Protein sequences, one per line` | `read_sequence_file` | One amino-acid sequence per line; blanks skipped; no comments, no `>` headers, no wrapping. |
| `DNA sequences, one per line` | `read_sequence_file` | One nucleotide sequence per line; the same rules. |
| `RNA sequences, one per line` | `read_sequence_file` | One RNA sequence per line; the same rules. |
| `Ligands by SMILES…` | `read_smiles_file` | `name SMILES` or a bare SMILES; `#` comment lines and blanks ignored. |
| `Ligands by CCD code…` | `read_code_file` | One ligand per line as component code(s); a line's tokens are **one** ligand (`NAG NAG BMA MAN MAN` is a five-component glycan); `#` comments and blanks ignored. |

**SMILES specifics**

| Input | Accepted syntax | Notes |
|---|---|---|
| Named ligand | `ethanol CCO` | The **first whitespace** splits name from SMILES. The name becomes the output file name (slugged) and the summary label. |
| Bare ligand | `CCO` | Auto-named `ligand_N` by the reader, so the file is `…__ligand-N.json`. |
| Comment / blank line | `# …`, empty | Ignored. `#` is a comment **only** at the start of the line; a `#` inside a SMILES is text like any other. |
| Duplicate SMILES | two lines with the same molecule | **Refused** — whole file, the repeated value named. |
| Duplicate names | `x CCO` + `x c1ccccc1` | Both survive: the second key becomes `x-2` (then `-3`…), deterministically in file order. |
| CCD code in a **SMILES** file | `atp ATP` | **Refused, not converted.** `ATP` is not SMILES notation; the file is refused with its line number. Use the CCD code kind instead. |
| Anything per-entry besides the kind's own syntax: MSA, templates, PTMs, custom CCD | — | Not expressible in these formats. They belong to the base job and are preserved. |

**Sequence specifics.** Every non-empty line is one record, validated against
the family's own alphabet (`configbuilder.model.SequenceText`): an empty file,
an invalid residue symbol, a `#` line (sequences have **no** comment syntax) or a
duplicate sequence refuses the whole run with the offending line numbers. No
record is ever dropped silently, and a sequence is never reinterpreted as a
ligand (or the reverse).

FASTA is **not** a supported batch format, and the refusal now says so: a line
starting with `>` stops the whole file with *"this looks like a FASTA file,
which the line-based sequence reader does not support: line 1 starts with '>'
… Write one complete sequence per line with no header lines…"* instead of the
old wall of "characters outside its alphabet" complaints (every letter of a
header is outside it). `proteins_wrapped_fasta.txt` is the refusal fixture.
Headerless *wrapping* is still the trap it always was: each wrapped row is a
separate record, so one sequence can become several — write one complete
sequence per line.

**The `.txt` extension decides nothing.** `MVT`/`MVS`/`MVY`/`TEST` are valid
protein sequences *and* invalid SMILES, so which one they become is the user's
call, made before the file is read. If a user picks the SMILES kind and the
every-line-refused text is a valid sequence of one family, the refusal appends
an actionable hint (e.g. *"These entries may be protein sequences rather than
SMILES. Select the protein sequence input type…"*) — advice only: nothing is
reinterpreted automatically, and a protein hint also names the CCD kind, because
`ATP` is a valid protein sequence as well as a component code.

Notation is checked, chemistry is not. Every entry is parsed against SMILES'
own grammar (`configbuilder/validation/smiles.py`: the SMILES character set,
balanced brackets, paired ring-closure numbers, and unbracketed atoms from the
organic subset), so a component code, a protein sequence or a sentence is
**refused** with its line number and reason before anything is written. What is
still nobody's business here: whether a grammatical notation describes a real
molecule — valence, aromaticity and perception belong to AF3's own parser
(RDKit), which this builder does not depend on. `ligands_unchecked_syntax.smiles`
and `ligands_ccd_lookalike.smiles` are now *refusal* fixtures;
`ligands_notation_edges.smiles` is the positive control that keeps bracketed
atoms, charges, `%nn` rings and isotopes working.

A ligand typed by hand is checked by the same implementation through the
validation rule `R-ENT-010` (`BundledChemistryProbe` is what
`ui.services.build_services` wires), so the two doors cannot disagree.

### Supported-input matrix (verified 2026-10-28)

"CLI" and "GUI" mean the real entry points were driven — `python af3builder.py`
with its prompts answered (including the *What does the file contain?* kind
question), and the desktop window's **Entities → Generate configurations from
file…** action with its **Input type** box — and the JSON on disk was inspected
and validated. The CLI protein files were additionally accepted by AF3's own
`Input.from_json` parser in the direct smoke check; the broader parser corpus
also includes the generated categories except custom-CCD documents, which are
reported **UNVERIFIED** because AF3's compiled CIF parser is stubbed. A
service-level test is marked as such, never as an end-to-end pass.

| Input category | Actual syntax | Parser support | CLI tested | GUI tested | JSON validated |
|---|---|---|---|---|---|
| SMILES (named) | `name SMILES` | Yes | Yes (`tests/e2e/test_variant_cli_subprocess.py`, `tests/e2e/test_entity_batch_cli_subprocess.py`) | Yes (`tests/gui/test_file_generation.py`) | Yes — accepted by AF3's own parser |
| SMILES (bare) | `SMILES` | Yes, auto-named | Yes | Yes | Yes — accepted by AF3's own parser |
| SMILES notation the check must keep | `[Zn+2]`-style brackets, `%10`, `[2H]`, stereocentres, a disconnected salt | Yes, deliberately permissive | Yes — `ligands_notation_edges.smiles`, 6 configurations | Yes (same service) | Yes — accepted by AF3's own parser |
| Standard CCD code | `ATP`, `ZN`, `NAG NAG BMA MAN MAN` (CCD code kind) | Yes — `ByCode` → `ccdCodes`, never `smiles`; code shape is checked, CCD registry membership is not looked up | Yes (`tests/e2e/test_entity_batch_cli_subprocess.py`, `ligands_ccd_codes.txt`) | Yes (`tests/gui/test_file_generation.py`) | Yes — accepted by AF3's own parser (`input_batches` corpus case) |
| Bare ion as SMILES | `[Zn+2]`, `ZN` (SMILES kind) | Grammar accepts a bracketed ion; the **contract** refuses it (rule `R-BND-001`: ions are CCD-coded ligands) | Yes (refused, naming that rule) | Yes (same service) | N/A |
| Custom CCD (job-wide) | base JSON `userCCD` / `userCCDPath` | Preserved, not per entry | Yes (`base_job_custom_ccd.json`) | Yes — the base's own Custom CCDs tab feeds the same job | UNVERIFIED by AF3's parser (its `userCCD` path needs the compiled CIF extension); the field round-trips byte-identically |
| Ions / multi-copy ligands | base JSON `ccdCodes` | Preserved, not per entry | Yes (ZN and ATP×2 in the same run) | Yes | Yes |
| Protein sequences | one per line, `.txt` | Yes (`batch_specs_for_sequences`, family `protein`) | Yes — `proteins_minimal.txt` → 4 configurations (`tests/e2e/test_entity_batch_cli_subprocess.py`) | Yes (`tests/gui/test_file_generation.py`) | Yes — accepted by AF3's own parser (`input_batches` corpus case) |
| DNA sequences | one per line, `.txt` | Yes (one line constructs the same base-service DNA duplex) | Yes (`tests/e2e/test_entity_batch_cli_subprocess.py`) | Yes (`tests/gui/test_file_generation.py`) | Yes — accepted by AF3's own parser (`input_batches` corpus case) |
| RNA sequences | one per line, `.txt` | Yes — `FamilyBRecord`, the same RNA record the single-entity forms build | Yes (`tests/e2e/test_entity_batch_cli_subprocess.py`) | Yes (`tests/gui/test_file_generation.py`) | Yes — accepted by AF3's own parser (`input_batches` corpus case) |
| Sequences fed to the **SMILES** kind | one per line, `.txt` | Refused as notation, with the sequence hint appended | Yes — refused, naming the line (`tests/e2e/test_entity_batch_cli_subprocess.py`) | Yes — refused (`tests/gui/test_file_generation.py`) | N/A |
| CCD codes fed to the **SMILES** kind | `atp ATP` | Refused as notation — never stored as `smiles` | Yes (`tests/e2e/test_entity_batch_cli_subprocess.py`) | Yes (same service) | N/A |
| MSA / template per entry | — | **Not supported** in a batch file | N/A | N/A | Base-job MSA/templates are preserved |

**Which category is offered is the same five everywhere.** Both front ends
build their list from `batch_variants.INPUT_KINDS` — the console's
`MenuApp.FILE_KINDS` and the window's `dialogs/batch_input.KIND_LABELS` are
compared against it by test (`test_the_kind_menu_offers_exactly_the_supported_
input_types`, `test_the_kind_lists_match_the_services`) — so a kind can never be
advertised that no service builds, and a working kind can never be hidden.

RNA batch generation was not part of the earlier ligand-only Phase 2 request;
this follow-up explicitly required establishing its current support. The RNA
builder uses the model's `FamilyBRecord` and is verified through the shared
builder table, real CLI, real Qt page workflow, and AF3's input parser. Older
reports that call protein/DNA/RNA batch unavailable describe the state before
this follow-up and are superseded by the dated status updates in the current
implementation and end-to-end reports. No RNA inference-quality claim is made.

---

## 2. Fixtures

### Ligand-workflow files

| File | Entries | Result |
|---|---|---|
| `ligands_named.smiles` | `ethanol CCO`, `acetic-acid CC(=O)O`, bare `c1ccccc1` | 3 configurations: `…__ethanol`, `…__acetic-acid`, `…__ligand-1`, plus `manifest.json` |
| `ligands_duplicate_names.smiles` | `kinase-inhibitor CCO`, `kinase-inhibitor c1ccccc1` | 2 configurations: `…__kinase-inhibitor`, `…__kinase-inhibitor-2` |
| `ligands_duplicate_entries.smiles` | `first CCO`, `second CCO` | Refused: *"the file contains duplicate ligand entries: CCO..."*; nothing written, no folder created |
| `ligands_empty.smiles` | comments only | Refused: *"the ligand file contains no entries (only blank lines or comments)"* |
| `ligands_ccd_lookalike.smiles` | `atp ATP`, `zinc ZN` | **Refused**: *"2 of 2 ligand entries are invalid … 'ATP' is not SMILES notation"*; nothing written. The codes are never stored as notation — no output ever carries `"smiles": "ATP"` |
| `ligands_notation_edges.smiles` | aspirin, `[Na+].[Cl-]`, `C%10CCCCCC%10`, alanine, `[2H]C([2H])([2H])[2H]`, `[13CH4]` | 6 configurations, one per entry — the positive control for the notation check |
| `base_job_custom_ccd.json` | not a batch file — the base job | Protein `A`, ATP×2 (`B`,`E`), ZN (`C`), aspirin (`D`), inline `userCCD`, seeds `[7]`, version 3 |

### Input files

| File | Entries | What it is for |
|---|---|---|
| `ligands_valid.smiles` | `ethanol CCO`, `acetic-acid CC(=O)O`, `C1CCCCC1` | Named and bare SMILES, generated in **SMILES** mode. |
| `ligands_unchecked_syntax.smiles` | `broken-ring C1CC`, `not-a-smiles this is not a smiles` | Deliberately malformed notation: refused with each line's reason. |
| `ligands_ccd_codes.txt` | `ATP`, `ZN`, `NAG NAG BMA MAN MAN` | Standard CCD mode: three separate ligands, with the five tokens on the last line making one multi-component ligand. |
| `ligands_ccd_lookalike.smiles` | `atp ATP`, `zinc ZN` | CCD-looking values deliberately selected as **SMILES**; refused rather than reinterpreted. |
| `proteins_minimal.txt` | `MVT`, `MVS`, `MVY`, `TEST` | Four minimal protein records. In **Protein sequence** mode, generates four independent protein configurations; these are parser/serialization fixtures, not evidence of biological utility. |
| `proteins_valid.txt` | 3 longer protein sequences | Protein sequence-mode coverage through CLI and GUI. |
| `proteins_wrapped_fasta.txt` | FASTA header and wrapped sequence | FASTA/wrapping is not supported in batch mode. The header is **diagnosed as FASTA** (naming the line, the supported format and how to proceed) and the file is refused whole; no header is ever stripped or silently discarded. |
| `dna_sequences.txt` | `ATGCATGC`, `GGCCTTAA` | Two DNA input records in **DNA sequence** mode; each becomes one independent output containing its DNA duplex (the input strand plus the reverse complement), matching normal Add DNA construction. |
| `rna_sequences.txt` | `ACGUACGUACGU`, `GGGCCCAAAUUU` | Two RNA records in **RNA sequence** mode. |
| `invalid_sequence.txt` | `ACDEFGHIK`, `AC1DEFG`, `AC-GU` | Invalid sequence entries: the entire batch is refused with line numbers. |
| `empty.txt` | 0 bytes | Refused as having no usable entries. |

Batch entry files are one record per line (blank lines are ignored); the user
selects the record type before selecting a file. The extension does not choose
the parser. The base JSON is ordinary AF3 input: open it with the Open action
(the `.json` extension is not special — content decides).

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

* **A CCD code in a `.smiles` file is refused, not converted.** The reader has
  no way to say "this token is a component code", and the notation check will
  not pass `ATP` off as a molecule, so the file is refused with its line number.
  Add CCD/ion ligands with **Add Ligand** (CCD mode) on the base job, where the
  base is then preserved in every generated file.
* **A sequence file is not a ligand file.** Choose Protein, DNA or RNA sequence
  mode to construct those entity types. If the same content is opened in SMILES
  mode, it is refused with an actionable hint; no automatic conversion occurs.
* **An `.txt` extension means nothing.** The explicit input-type selection picks
  the parser; for example, `proteins_minimal.txt` is protein input only when the
  user selects Protein sequence mode.
* **Custom CCD is base-job data, not a candidate-list format.** It continues to
  use the job's Custom CCD management and `userCCD` / `userCCDPath` mechanism;
  batch outputs preserve the base's definition. No custom CCD input-file kind
  is advertised.
* **The output folder may already exist; existing paths are checked before the
  write.** A collision with a *different* content stops the whole run before
  any batch file is written (all-or-nothing), so one stale file can refuse a
  whole batch: choose another output folder, or delete/rename that one file.
  A file whose bytes are already identical is not a conflict — it is rewritten
  with the same bytes (the review shows the action), so byte-identical plans
  never stop a run.
* **A write that fails part-way leaves nothing of its own behind.** Files the
  run created are removed again, and the directories it made are removed when
  empty. A file that *already existed* and was being replaced is kept (its
  previous bytes cannot be restored) and the error says how many were left as
  rewritten. Nothing ever deletes a file that existed before the run.
* **The name is not in the JSON.** AF3 has no per-entity name field, so the name
  appears in the file name and the summary only.
* **The base job is never modified.** Each output is independently built from
  the unchanged base plus one selected input entity; no input record accumulates
  into a sibling output.

---

## 4. Manual test procedure

Console (`python af3builder.py`):

1. `2` Open a JSON file → `base_job_custom_ccd.json` → expect
   `Name: batch-base-with-ccd`, `Entities: 4` (four definitions, five
   identifiers: the ATP ligand has two copies).
2. `7` *Generate configurations from a file (sequences or ligands)* → `1`.
3. Choose an input kind (`1` Protein, `2` DNA, `3` RNA, `4` SMILES, `5` CCD),
   then provide the corresponding file path. The preview names the selected
   kind and lists what will be added to the base.
4. Provide a scratch output folder. The closing summary counts roles, not
   rows: *"Generated 3 AF3 configurations. Wrote 1 manifest. Total output
   files: 4."* for the three ligand entries, and *"Generated 4 AF3
   configurations. Wrote 1 manifest. Total output files: 5."* for four protein
   lines. Copied assets (an external template, MSA or custom-CCD file) are
   named separately and counted in the total.
5. `0`, `0`, `0`.
6. Inspect the JSONs: the base entities/settings and `userCCD` are preserved,
   and each file adds exactly one entity using the chosen AF3 representation.

Window (`python gui.py`):

1. **Open** the same base JSON.
2. **Entities** → **Generate configurations from file…**.
3. Select the input type, then its file, then an empty output folder; the review
   box shows the selected kind, records and destination.
4. **Generate** → the result box lists the files actually written; the status
   bar reports the count.

Repeat with Protein sequence + `proteins_minimal.txt`: expect four JSONs, each
containing the unchanged base plus one `protein.sequence` (`MVT`, `MVS`, `MVY`,
`TEST`). Repeat with DNA, RNA and CCD kinds for their respective fixtures. In
SMILES mode, `proteins_minimal.txt` and `ligands_ccd_lookalike.smiles` must be
refused with guidance and no output. Duplicate entries, empty files, invalid
sequences and `ligands_unchecked_syntax.smiles` likewise write nothing.
`ligands_notation_edges.smiles` remains the positive notation-grammar control.

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
| `tests/e2e/test_variant_cli_subprocess.py` | the legacy-compatible console SMILES path: one output per ligand, safe names, base intact, duplicates/empty refused, collision protection |
| `tests/e2e/test_entity_batch_cli_subprocess.py` | the actual console with explicit kind selection: SMILES, CCD, protein/DNA/RNA, mode-mismatch diagnostics, output JSON inspection |
| `tests/gui/test_file_generation.py` | the actual Entities action: kind/file/folder/preview dialogs, production page/service path, per-entry JSON outputs, errors and collision behavior |
| `tests/unit/app/test_batch_variants.py` | record builders, alphabets, duplicate/empty refusals, identity allocation, name→key slugging |
| `tests/unit/persistence/test_sequence_files.py` | readers (`name SMILES`, CCD lines, sequence whitespace/line endings, comments and I/O errors) |
| `tests/e2e/test_app_pipeline.py` | additional shared generation-service coverage |
| `tests/e2e/test_manual_test_data.py` | the fixture pack through the shared services, including invalid/empty refusals |

Generated output from these runs goes to `tmp_path` / scratch folders; nothing
generated is stored in the pack.
