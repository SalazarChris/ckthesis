# Structural templates and entity batch generation — end-to-end verification

**Original verification date:** 2026-10-26
**Branch:** `main` (upstream `origin/main`, `https://github.com/SalazarChris/ckthesis.git`)
**Original scope (2026-10-26):** protein structural templates with residue-index
mappings, the then-current ligand batch workflow, and the retired variant UI.

**Follow-up status (2026-10-28):** later changes added explicit Protein, DNA,
RNA, SMILES and CCD input kinds to the same file-based configuration-generation
action. Historical statements below about sequence batches being unavailable
reflect the original run and are superseded by the dated addendum in §14.

This report distinguishes what was **executed** from what was only **inspected**.
Every "verified" claim below was produced by a run whose output was read back,
either through the real console (`python af3builder.py` with its prompts answered)
or through the desktop window's real widgets. Unit tests alone are never used to
claim an end-to-end pass.

---

## 1. Sources inspected

| Area | Files |
|---|---|
| Template model | `configbuilder/model/references.py` (`ReferenceRecord`, `Explicit`/`SearchAllowed`), `configbuilder/model/values.py` (`IndexPair`, `PathSpec`, `External`, `Inline`) |
| Template rules | `configbuilder/app/reference_validation.py` (`file_issue`, `parse_pair_text`, `validate_reference`), `configbuilder/validation/rules/template_rules.py` |
| Template serialization | `configbuilder/transform/engine.py` (`to_wire`), `configbuilder/transform/from_wire.py`, `configbuilder/transform/mappings.py` (`PROTEIN_FIELDS`, `PATH_FEATURE_MIN_VERSIONS`) |
| Console template flow | `configbuilder/ui/render/menus.py` `_chain_templates`, `_collect_references_for`, `_collect_template_list`, `_ask_template_file`, `_ask_template_pairs` |
| Desktop template flow | `configbuilder/ui/render/qt/pages/advanced.py` `edit_templates`/`_apply_templates`, `configbuilder/ui/render/qt/dialogs/advanced_forms.py` `TemplateEditorDialog` |
| Batch parsing | `configbuilder/persistence/sequences.py` (`read_smiles_file`, `read_code_file`, `read_sequence_file`) |
| Batch construction | `configbuilder/app/batch_variants.py` (`specs_for_entries`, `ligand_specs_for_entries`, `ligand_code_specs_for_entries`, `batch_specs_for_sequences`, `BATCH_RECORD_BUILDERS`) |
| Batch orchestration | `configbuilder/app/variant_service.py` (`input_file_specs`, `inspect_input_file`, `generate_from_file`), `configbuilder/app/generation_service.py` (`plan_input_batch`, `generate_input_batch`), `configbuilder/app/results.py` (`LigandBatchOutput`) |
| Batch front ends | `configbuilder/ui/render/menus.py` file-kind menu and generator; `configbuilder/ui/render/qt/pages/entities.py` `generate_from_file`; `configbuilder/ui/render/qt/dialogs/batch_input.py` |
| Output pipeline | `configbuilder/output/plan.py`, `output/execute.py`, `output/naming.py`, `output/policies.py` |
| Import | `configbuilder/app/project_service.py` `_prepare_import`, `import_json_preview`, `import_json_commit` |
| Prior decisions | `docs/LIGAND_VARIANT_GENERATION_AUDIT.md` |

---

## 2. Fixtures created

### Templates — `manual_test_data/af3_builder/templates/`

| Fixture | Content | Purpose |
|---|---|---|
| `template_fully_resolved.cif` | polymer `ACDEFG` (6 residues), chain A, residues 1–6, `CA` for all six | one-to-one mapping |
| `template_unresolved_residues.cif` | full polymer `ACQDEFG` (7 residues, 7 `_entity_poly_seq` rows), coordinates only for ASP4–GLY7 | unresolved-residue offset mapping |
| `template_empty.cif` | 0 bytes | the one invalid case the builder detects |
| `template_malformed.cif` | non-empty, no `_entity_poly`, truncated `_atom_site` | pins the no-parser limitation |
| `templates/README.md` | the above, mapped and explained | manual procedure |

The existing `minimal_template.cif` and `templates/with spaces/template with spaces.cif`
were **kept** and are documented alongside the new files.

### Batch — `manual_test_data/af3_builder/batch/`

| Fixture | Purpose |
|---|---|
| `ligands_named.smiles` | named, named, bare SMILES: names → file names |
| `ligands_duplicate_names.smiles` | two molecules, one name: deterministic `-2` |
| `ligands_duplicate_entries.smiles` | the same molecule twice: whole-file refusal |
| `ligands_empty.smiles` | comments only: "no entries" refusal |
| `ligands_ccd_lookalike.smiles` | `ATP`/`ZN` typed as entries: stored as SMILES text at the time of this run; **refused** since 2026-10-27 |
| `base_job_custom_ccd.json` | base with inline `userCCD`, ATP×2, ZN, aspirin, seeds `[7]`, version 3 |
| `README.md` | support matrix, expected outputs, manual procedure |

The pre-existing `batch/*.txt` and `batch/*.smiles` files were kept; their role is
now stated explicitly. Protein, DNA, and RNA fixtures are exercised through the
current CLI and GUI file-generation workflows.

---

## 3. Verified template mappings

### 3.1 Through the console (real process, prompts answered)

Command shape: `python af3builder.py` → `1` new job → `2`/`1` add protein →
sequence → `1` MSA default → `y` templates → `3` list → mmCIF path → pairs →
`n` another → `6` save → destination → `0` → `0`.

Fixture A (query `ACDEFG`, pairs `0:0,1:1,2:2,3:3,4:4,5:5`) wrote
`resolved.json`:

```json
"templates": [{
  "mmcifPath": "assets/template-fully-resolved.cif",
  "queryIndices": [0, 1, 2, 3, 4, 5],
  "templateIndices": [0, 1, 2, 3, 4, 5]
}]
```

Fixture B (query `DEFG`, pairs `0:3,1:4,2:5,3:6`) wrote `partial.json`:

```json
"templates": [{
  "mmcifPath": "assets/template-unresolved-residues.cif",
  "queryIndices": [0, 1, 2, 3],
  "templateIndices": [3, 4, 5, 6]
}]
```

Both arrays are the same length, pair residue by residue, and the second is
**not** `[0,1,2,3]`. The template file was copied to `<dir>/assets/…` next to the
JSON, and the JSON references the copy relatively.

Round trip: reopening `partial.json` (`2` on the main menu) and saving it as
`second.json` produced **identical** `sequences` (`mappings equal: True`).
Before the fix in §9 this was refused with
`Not applied: resource source 'assets/template-unresolved-residues.cif' is missing; nothing was written`.

Invalid fixture: `template_empty.cif` was refused at the file prompt —
`The template file '…' cannot be used: the file is empty. Enter another path or 0 to cancel.`
— the collection was cancelled, the job saved normally, and the protein carried
no `templates` field at all (nothing half-attached).

`template_malformed.cif` was **accepted** at the time of this run (a `templates`
entry was written), because no mmCIF parsing existed. That limitation was
closed on 2026-10-27: the file is now **refused** at the same prompt — see
`docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §2. The statement is kept here as
the record of what this run observed.

### 3.2 Through the desktop window (real widgets, offscreen)

The window was driven as a user drives it: New job → Entities → Add Protein →
select the entity → *Templates* → **Edit templates…**. The real
`TemplateEditorDialog` was used; only its modal `exec` loop was stood in for, and
its own file picker (`QFileDialog.getOpenFileName`) was answered with the fixture
path so `dialog.add_file()` and the pairs cell ran for real. **Save** then went
through `_FormDialog.accept` → `AdvancedPage._apply_templates` →
`ConfigurationService.set_references`, and the job was written with the window's
own `save_json`.

Results (assertions in `tests/gui/test_template_attachment.py`):

- A → `queryIndices [0,1,2,3,4,5]`, `templateIndices [0,1,2,3,4,5]`;
- B → `queryIndices [0,1,2,3]`, `templateIndices [3,4,5,6]`;
- the copy landed in `<dest>/assets/` and the reference is relative;
- reopen (preview + commit through `GuiState`) → re-save → byte-identical
  `templates` block;
- empty fixture → dialog stayed open with the service's message, job unchanged,
  saved JSON has no `templates`;
- malformed fixture → accepted (limitation; **now refused** — closed
  2026-10-27, `docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §2).

### 3.3 What the mapping means, and what the builder checks

AF3 template indices are positions in the **template's polymer sequence**.
`ACQDEFG` puts `DEFG` at 3–6 even though only those four residues are resolved.
The builder itself cannot derive this, and still does not: it cannot see that
`DEFG` is the resolved tail of `ACQDEFG`, because reading a template's own
residues is not something a structure check can decide for the user. At the time
of this run `reference_validation.py` checked only that the file exists, is a
regular `.cif`/`.mmcif`, is non-empty, and that each pair is two non-negative
integers whose query index is inside the target sequence. Since 2026-10-27 the
file's *content* is checked as well (readable mmCIF with structure in it), which
changes none of the above: the mapping is still user-supplied input, verified
here against fixtures a human can read.

---

## 4. Batch input contract (established from code, not assumed)

- `persistence.read_smiles_file` → `(line, name, smiles)`; `name SMILES` splits on
  the first whitespace, `#` at line start is a comment, blank lines are skipped.
- `batch_variants.ligand_specs_for_entries` builds one `base + AddRecord` spec per
  entry; the entry's name (slugged) becomes the spec key and therefore the output
  file name; duplicate names take `-2`, `-3` in file order; a name that cannot be
  slugged falls back to `ligand-NN`; duplicate **molecules** refuse the file.
- `generation.plan_input_batch` validates the base and each independent entry
  through the full catalogue before anything is written, then reuses the normal
  transform/plan/execute pipeline. Both front ends pass an explicit kind into
  `GenerationService.generate_input_batch`.
- The five supported kinds are protein sequence, DNA sequence, RNA sequence,
  ligand SMILES and standard CCD-code ligand. Each has a separate reader and
  builder; CCD codes are `ByCode` → `ccdCodes`, never interpreted as SMILES.
- Custom CCD definitions, ions, MSA and templates have no per-entry list-file
  syntax; they remain base-job data and are preserved in each output.

---

## 5. Support matrix (actual results)

| Category | Syntax | Parser | CLI | GUI | JSON validated |
|---|---|---|---|---|---|
| SMILES, named | `name SMILES` | Yes | Yes — real process, 3 files written | Yes — real Entities action | Yes |
| SMILES, bare | `SMILES` | Yes (auto `ligand_N`) | Yes | Yes | Yes |
| Duplicate names | same name twice | Yes (`-2`) | Yes — `kinase-inhibitor`, `kinase-inhibitor-2` | Same service | Yes |
| Duplicate molecules | same molecule twice | Refused (whole file) | Yes — refusal, nothing written | Yes | N/A |
| Empty file | comments/blanks only | Refused | Yes | Yes (refused before the folder question) | N/A |
| Standard CCD code in a file | One or more component codes per line | Yes — `ByCode` → `ccdCodes`; shape validated, no live CCD registry lookup | Yes — real CLI writes codes | Yes — Entities workflow writes codes | AF3 parser corpus accepts emitted shape |
| Custom CCD (job-wide) | `userCCD` in base JSON | Preserved | Yes — byte-equal `userCCD` in all 3 outputs | Yes | Builder validator: yes. AF3 parser: **UNVERIFIED** (its `userCCD` path needs the compiled CIF extension) |
| Ions / multi-copy ligands in base | `ccdCodes` | Preserved | Yes — `A,B,E,C,D` + one added id | Yes | Yes |
| Protein sequences | one per line | Yes | Yes — explicit protein kind, output JSON inspected | Yes — Entities workflow, output JSON inspected | AF3 parser corpus accepts the emitted shape |
| DNA sequences | one per line | Yes | Yes — explicit DNA kind, duplex JSON inspected | Yes — Entities workflow, duplex JSON inspected | AF3 parser corpus accepts the emitted shape |
| RNA sequences | one per line | Yes — `FamilyBRecord` | Yes — explicit RNA kind, output JSON inspected | Yes — Entities workflow, output JSON inspected | AF3 parser corpus accepts the emitted shape |
| MSA/template per entry | — | **Not supported** | N/A | N/A | Preserved from the base |

---

## 6. Batch results in detail

Base `base_job_custom_ccd.json` (`Entities: 4`, five identifiers, `modelSeeds [7]`,
`version 3`, inline `userCCD`) + `ligands_named.smiles`:

```
<out>/batch-base-with-ccd/batch-base-with-ccd__ethanol/batch-base-with-ccd__ethanol.json
<out>/batch-base-with-ccd/batch-base-with-ccd__acetic-acid/batch-base-with-ccd__acetic-acid.json
<out>/batch-base-with-ccd/batch-base-with-ccd__ligand-1/batch-base-with-ccd__ligand-1.json
<out>/batch-base-with-ccd/manifest.json
```

`Wrote 4 file(s) under …` — three configurations plus the manifest, matching the
files on disk. Every configuration carried ids `A`, `B`/`E`, `C`, `D` plus one
added ligand (`F`, `G`, `H` respectively), the same `userCCD` text, seeds `[7]`,
dialect `alphafold3`, version 3. No configuration contained another entry's
molecule. The base job on screen was unchanged (same configuration object) and
the fixtures were byte-identical afterwards.

`ligands_duplicate_names.smiles` → `…__kinase-inhibitor.json` (`CCO`) and
`…__kinase-inhibitor-2.json` (`c1ccccc1`).

`ligands_ccd_lookalike.smiles` → `…__atp.json` `{"smiles": "ATP"}` and
`…__zinc.json` `{"smiles": "ZN"}`; no `ccdCodes` on either added entry. (Since
2026-10-27 this file is **refused** — `ATP` is not SMILES grammar — and the same
applies to `ligands_unchecked_syntax.smiles`; nothing is written for either. See
`docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §3.)

`ligands_duplicate_entries.smiles` → `the file contains duplicate ligand entries: CCO...`;
`ligands_empty.smiles` → `the ligand file contains no entries (only blank lines or comments)`.
Neither created the output folder or wrote any file.

Validation: each written document is produced only after
`ValidationService.validate_specs` (base + every variant) reports no blocking
findings, and the same test suite re-reads every file with `json.load` and
asserts its entity structure — a parse failure or a structural surprise fails
the test. No file was written by a refused run.

---

## 7. Tests run (actual output)

| Suite | Command | Result |
|---|---|---|
| Core (everything but the GUI) | `python -m pytest tests -o addopts="" -q --ignore=tests/gui --basetemp=.pytest-tmp` | **1163 passed, 1 skipped** (3:39) |
| GUI (offscreen Qt), original run | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -o addopts="" -q --basetemp=.pytest-tmp` | **267 passed** (1:11); see §14 for the current-tree 279-test result |
| Batch + template front ends | `python -m pytest tests/e2e/test_template_cli_subprocess.py tests/e2e/test_entity_batch_cli_subprocess.py tests/e2e/test_variant_cli_subprocess.py -o addopts="" -q` | **12 passed** (real subprocesses) |
| Batch pack + readers, original run | `python -m pytest tests/e2e/test_entity_batch_cli_subprocess.py tests/e2e/test_variant_cli_subprocess.py tests/e2e/test_manual_test_data.py tests/unit/app/test_batch_variants.py -o addopts="" -q` | **61 passed**; see §14 for current focused/core/GUI counts |
| AF3's own input parser, original run | `python tools/af3_validation/run_all.py` | **PASS** — 13/13 positive, 8/8 negative, corpus 21 ACCEPTED + 2 UNVERIFIED, round trip 13/13 identical; the current 33-document result is in §14 |

Historical reference points from the audit were **core 1147 / 1 skipped, GUI 306,
batch 70 / 1 skipped**. The original verification later reported core **1163 / 1
skipped** and GUI **267** after removing the retired variant-catalogue tests;
this report records that state as historical. Current-tree counts are now **1,297
core passed / 1 skipped** and **279 GUI passed** (see §14). The differing counts
reflect changed and expanded test coverage, not a direct unchanged rerun of the
old suites. No assertion was weakened for the follow-up.

New coverage added in this task:

| File | Tests |
|---|---|
| `tests/e2e/test_template_cli_subprocess.py` | 4 — fixtures A and B, reopen/resave round trip, empty refusal |
| `tests/gui/test_template_attachment.py` | 5 — A, B, reopen, empty refusal, malformed limitation |
| `tests/e2e/test_entity_batch_cli_subprocess.py` | 3 — custom-CCD base, duplicate names, CCD-lookalike |
| `tests/gui/test_file_generation.py` | production Entities workflow, packaged-dialog click path, per-kind JSON output, custom-CCD base preservation and refusal paths |
| `tests/unit/transform/test_resource_path_rebase.py` | 5 — the import rebase and its boundaries |
| `tests/unit/app/test_batch_variants.py` (extended) | 4 — name slugging, duplicate names, CCD lookalike, ASCII ellipsis |

`--basetemp=.pytest-tmp` is required **in this environment**: the GUI launch tests
start `.venv-gui` as a child process, and that interpreter cannot write under
`%TEMP%` here (a `PermissionError` in the test's own site hook would otherwise
leave the child running until the 90 s timeout). The path is gitignored, and the
tests pass without the flag on a machine where the venv can write to its temp
directory.

---

## 8. Obsolete GUI navigation and wording

Removed: the **Variants & Batch** destination, `pages/variants.py` (1453 lines),
`dialogs/variant_forms.py` (961 lines), the variant page's models, menu entries,
tooltips, status strings and the `gui.variants_*` / `gui.tab_variants` registry
keys. The sidebar is now **Overview · Entities · Generate**.

The file-driven workflow is one action on **Entities**: `Generate ligand
configurations…`. It is the only control whose text contains "generate" on that
page. `grep -ri variant configbuilder/ui` now returns only internal service names
(`services.variants`, the `VariantService` type) and docstrings — no user-facing
text. Tests assert the absence: `test_the_sidebar_holds_the_three_destinations_in_order`,
`test_no_page_manages_an_in_memory_variant_list`, and a wording scan in
`test_the_only_entry_point_is_an_action_on_the_entities_page`.

Ordinary entity management is untouched: Add Protein/RNA/DNA/Ligand, Edit,
Delete, MSA, templates, PTMs, Custom CCDs and covalent bonds all remain, with
their suites passing.

---

## 9. Defects fixed

1. **`GeneratePage` crashed on construction** — `_on_control_changed` was removed
   with the scope picker but two signals were still connected to it
   (`AttributeError` on every window). Restored as a one-line invalidation hook.
2. **`MainWindow.refresh()` called the deleted variants page** —
   `self._variants.refresh()` raised `AttributeError` on the first refresh.
   Removed.
3. **A saved job could not be reopened and re-saved** (found while verifying the
   template round trip): the document's relative resource paths
   (`assets/<template>.cif`) were kept relative to the process's working
   directory, so the re-write failed with `resource source … is missing`.
   Fixed by `transform.from_wire.rebase_resource_paths`, called from
   `ProjectService._prepare_import` with the file's own folder. Absolute paths
   and inline text are untouched; `from_wire` stays a pure mapping (its tests
   still pin verbatim relative paths). Kept inside `transform` without importing
   `os`, because the architecture test forbids filesystem modules there.
4. **Duplicate-entry message printed a mojibake ellipsis** through the Windows
   console (`CCOâ€¦`): the ASCII `...` is used now.
5. **Stale registry text** — `gui.output_group_scope` asked "What do you want to
   generate?" and the intro promised a manifest the base-scope page never writes;
   both now describe the single base file, and dead keys
   (`gui.output_step1_hint`) and stale section comments were removed.

---

## 10. Limitations and blocked tests

- ~~**No mmCIF parsing.** Template attachment checks the path, extension,
  emptiness and pair syntax only.~~ **Closed 2026-10-27** for the part that can
  be decided without AF3: a template whose file is not readable mmCIF is now
  refused, and `template_malformed.cif` is refused rather than accepted (an
  established parser when installed, the bundled lexical scan otherwise). Still
  out of scope, and still the user's responsibility: chain identity, residue
  numbering, unresolution and bounds. See
  `docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §2.
- **Historical limitations (superseded 2026-10-28):** the original run did not
  validate SMILES notation or expose protein/DNA/RNA batch inputs through both
  interfaces. The follow-up added a notation-grammar check and explicit kind
  selection; current CLI/GUI results appear in §14 and the support matrix in the
  batch README.
- **Remaining chemistry/registry limits:** SMILES grammar is checked, but
  chemical validity (including valence and aromaticity) is not. CCD code shape
  is validated by the builder, but registry membership is not looked up.
- **AF3 inference was not run.** AlphaFold 3 itself was not executed, so nothing
  here is a claim about a structure prediction. What *was* run is AF3's own
  input parser (`tools/af3_validation`, §12): every document this workflow
  produced from a base without `userCCD` is `ACCEPTED` by
  `folding_input.Input.from_json`; the three from `base_job_custom_ccd.json` come
  back `UNVERIFIED` because AF3 parses `userCCD` with a compiled extension the
  tool stubs out — the documented limit, not a failure.
- **Interactive GUI testing was automated, not manual.** The tests drive the real
  PySide6 widgets offscreen through the production signal/service path. No human
  clicked a visible window in this environment; no claim is made about visual
  layout beyond the existing layout suites.
- The template index mapping is user input, so "the correct mapping was written"
  is verified against the fixture's declared sequence and coordinate rows, not
  against an AF3-computed mapping.

---

## 11. Run log

```
$ python -m pytest tests -o addopts="" -q --ignore=tests/gui --basetemp=.pytest-tmp
1163 passed, 1 skipped, 1 warning in 219.45s (0:03:39)

$ QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -o addopts="" -q --basetemp=.pytest-tmp
267 passed in 71.46s (0:01:11)

$ python -m pytest tests/unit/variants tests/unit/app/test_batch_variants.py \
      tests/unit/persistence/test_sequence_files.py -o addopts="" -q
12 passed in 7.96s

$ python tools/af3_validation/run_all.py
RESULT: PASS
  positive control : 13/13 accepted
  negative control : 8/8 rejected
  corpus           : ACCEPTED=21, UNVERIFIED=2, refused cases: none
  round trip       : 13/13 identical and accepted

$ python tools/af3_validation/af3_validate.py <batch output of a plain base>
summary: ACCEPTED=3

$ python tools/af3_validation/af3_validate.py <fixture A, B and C console outputs>
summary: ACCEPTED=3
```

---

## 12. Validation against AlphaFold 3's own parser

`tools/af3_validation` does not re-implement anything: it imports
`alphafold3.common.folding_input` from the official source tree and calls
`Input.from_json`. Four stages, all executed today:

| Stage | Result |
|---|---|
| Positive control — AF3's own 13 example JSON files | 13/13 ACCEPTED |
| Negative control — 8 deliberate corruptions | 8/8 REJECTED |
| Corpus — 21 documents from the builder's own services | 21 ACCEPTED, 2 UNVERIFIED |
| Round trip — each AF3 example imported and re-emitted by the builder | 13/13 identical and ACCEPTED |

`RESULT: PASS`. The two UNVERIFIED documents are the custom-CCD ones: AF3 parses
`userCCD` with its compiled `cif_dict` extension, which the tool stubs to raise,
so those are reported as unverified rather than counted as passes.

Documents from **this task's workflows**, validated individually after being
written by the real console:

| Output | Verdict |
|---|---|
| Fixture A job (`resolved.json`, query `ACDEFG`, template `[0..5]`) | ACCEPTED — `name='tpl-a' chains=A(6) seeds=[1]` |
| Fixture B job (`partial.json`, query `DEFG`, template `[3..6]`) | ACCEPTED — `name='tpl-b' chains=A(4) seeds=[1]` |
| Fixture C job (`refused.json`, the empty-template case) | ACCEPTED — `name='tpl-c' chains=A(6) seeds=[1]` |
| 3 ligand configurations on a plain protein base | 3/3 ACCEPTED — `A(22)` plus one ligand, chain ids `B`, `C`, `D` |
| 3 ligand configurations on `base_job_custom_ccd.json` | 3/3 UNVERIFIED (the base's `userCCD` field, same reason as above) |

A repair worth recording: the validator's artifacts under the OS temp directory
had been swept by a disk cleaner, leaving `alphafold3` and `etils` as
`__pycache__`-only skeletons. `python tools/af3_validation/setup_validator.py`
reported them as "already present" because it tests for the directory, then
failed with `ImportError: cannot import name 'folding_input'`. Removing the two
damaged directories and re-running the setup script rebuilt them; nothing in the
repository needed changing. The `setup_validator.py` "already present" check is
therefore a directory check, not an integrity check — a fresh corruption will
fail loudly at `load_parser`, which is what happened here.

---

## 14. Follow-up addendum — explicit input kinds and end-to-end coverage (2026-10-28)

The earlier report's support matrix in §5 and its limitation statements in §10
are historical: at that time the UI exposed SMILES only. The current action asks
for the intended input kind before opening a file, and both the CLI and GUI use
the shared `GenerationService.generate_input_batch` path.

| Kind | File syntax | Output entity | CLI | GUI |
|---|---|---|---|---|
| Protein | One protein sequence per non-empty line (`proteins_minimal.txt`: MVT/MVS/MVY/TEST) | `protein.sequence`; one added chain per output | Real CLI subprocess test reads output JSON | Real Entities page, with a real packaged-dialog/click test and per-kind file-output tests |
| DNA | One DNA sequence per line | `dna.sequence`; each input creates the normal two-strand DNA duplex in one independent output | Real CLI subprocess test reads JSON | Entities page workflow writes and inspects JSON |
| RNA | One RNA sequence per line | `rna.sequence` (`FamilyBRecord`) | Real CLI subprocess test reads JSON | Entities page workflow writes and inspects JSON |
| SMILES | `name SMILES` or bare notation | `ligand.smiles`; notation grammar checked, no chemical-validity claim | Real CLI subprocess tests | Entities page workflow writes JSON |
| Standard CCD | One or more component codes per line; each line one ligand | `ligand.ccdCodes` | Real CLI subprocess test | Entities page workflow writes JSON |
| Custom CCD | Job-wide `userCCD` / `userCCDPath`, not a candidate list | Preserved from the base in all outputs | Base preservation tested | Base preservation tested |

Exact supported syntax and limits are maintained in
`manual_test_data/af3_builder/batch/README.md`. FASTA is unsupported: sequences
are one line per record; headers and wrapped records are not parsed. Input kind
is explicit—`.txt` does not trigger auto-detection. Protein sequences of only a
few residues in the minimal fixture are parser/serialization test records, not
evidence of biological usefulness or inference quality.

Automated GUI checks use PySide6 widgets offscreen. The suite exercises the
production Entities action, calls the shared service, writes actual files,
inspects output JSON, and includes a test that clicks the real button while
using the packaged input-kind and review dialogs. No human-operated GUI session
was performed. No AF3 inference was run; AF3's own parser validation is
separate, with custom-CCD output remaining UNVERIFIED where the offline harness
cannot evaluate its compiled CIF parser.

**Follow-up verification results executed in this checkout:**

| Check | Command | Result |
|---|---|---|
| Focused parser/builders/real CLI/Qt generation | `python -m pytest tests/unit/persistence/test_sequence_files.py tests/unit/app/test_batch_variants.py tests/e2e/test_entity_batch_cli_subprocess.py tests/e2e/test_variant_cli_subprocess.py tests/gui/test_file_generation.py tests/gui/test_manual_test_data_gui.py -o addopts='' -q --basetemp=.pytest-tmp` | **97 passed, 1 skipped** |
| Full non-GUI suite | `python -m pytest tests -o addopts='' -q --ignore=tests/gui --basetemp=.pytest-tmp` | **1,297 passed, 1 skipped**, one existing Matplotlib/PyParsing deprecation warning |
| Full GUI suite | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -p no:cacheprovider --basetemp=.pytest-tmp -o addopts='' -q` | **280 passed**; repository-local basetemp is required for the GUI launcher subprocess tests in this Windows environment |
| AF3 input parser corpus | `python tools/af3_validation/run_all.py` | **PASS**: positive 13/13, negative 8/8, corpus 33 ACCEPTED + 2 UNVERIFIED, round-trip 13/13 |
| Direct four-record protein CLI smoke | Real `python af3builder.py` subprocess with a base carrying the custom-CCD test field removed only for official-parser compatibility; read each written JSON and call `af3_validate.check` | **PASS**: four files, sequences MVT/MVS/MVY/TEST, base seed/version/dialect/entities preserved, all four ACCEPTED by the official AF3 parser. With the original inline custom CCD retained, all four correctly produce **UNVERIFIED** because the harness lacks AF3's compiled CIF parser. |

The focused suite and full GUI suite were rerun after adding a packaged-dialog
click test for the four-line protein input. The current totals are 97 focused
passes (one skip) and 280 GUI passes; core remains 1,297 passed (one skip).
The direct parser smoke used a base without its inline custom CCD field because
the harness cannot verify that compiled-CIF path; a separate smoke with the
original base confirmed the expected UNVERIFIED result, not a builder failure.
A GUI run with the default `%TEMP%` had timed out earlier in the launcher test;
the full suite passed with repository-local `--basetemp=.pytest-tmp`. No AF3
inference or human-operated GUI session was performed.

---

## 13. Git

- Branch: `main`, remote `origin`
  (`https://github.com/SalazarChris/ckthesis.git`), upstream `origin/main`.
- Implementation commit: `a4a488c` ("Make the ligand-file workflow the variant
  service, and verify it end to end"), 290 files.
- This document, the terminology report and the implementation report were
  committed on top of it and pushed to `origin/main` together. The follow-up
  commit records the hashes, so `git log --oneline origin/main -3` shows the
  implementation first, then the documentation.
