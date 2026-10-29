# AF3 Configuration Generation — Fix Report

**Scope:** the fixes applied on top of `docs/CONFIGURATION_GENERATION_PRACTICAL_AUDIT.md`
(the audit is the *as-found* record and is unchanged except for an appended status
section). Everything here is either an executed test result or clearly labelled
inspection evidence.

**Date:** 2026-10-29
**Baseline audited at:** `main` @ `d4cd17d` (working tree already carried the
template-import work described in §2)
**Method:** source inspection of the current implementation, execution of the real
CLI and of the shared application services against the shipped fixtures, and the
project's own suites (`tests/`, excluding nothing except where noted).

---

## 1. Findings confirmed against the source

Each audit finding was re-checked in the code before it was touched.

| # | Audit finding | Confirmed as | Where |
|---|---|---|---|
| D1 | A base JSON with inline `templates[].mmcif` cannot be opened | **Confirmed.** `_import_references` required `mmcifPath`; AF3's own `Template.to_dict` can emit either field | `configbuilder/transform/from_wire.py` |
| F2 | `queryIndices`/`templateIndices` are carried without any bound check | **Confirmed.** `validate_reference` checked the pair shape and the *query* length only; the template's own residues were never read | `configbuilder/app/reference_validation.py` |
| F3 | External `userCCDPath` copying was never demonstrated | **Confirmed as a verification gap** (not a defect): the resource path is generic, but nothing asserted it for `userCCDPath` | `configbuilder/output/plan.py` §13.5 path |
| F4 | The console counts the manifest as a file; the window cannot count assets at all | **Confirmed.** The console printed `len(outcome.written)`; `LigandBatchOutput` did not carry `copied_resources` | `ui/render/menus.py`, `app/results.py` |
| F5 | Neither preview explains the DNA duplex or the overwrite policy's blast radius | **Confirmed.** Both said only "existing files are never replaced" | `ui/present/strings.py` |
| F6 | FASTA input produces a wall of "invalid character" errors | **Confirmed.** A `>` header was reported per line as characters outside the alphabet | `app/batch_variants.py` |
| F7 | Protein alphabet accepts A–Z, unverified against AF3 | **Confirmed, and correct.** AF3 checks `re.fullmatch(r'[A-Z]*', sequence)` in `alphafold3/common/folding_input.py`; the builder matches it exactly | `model/values.py` |
| D2 | Stale fixture comment | **Confirmed.** The comment claimed CCD-looking lines are stored as `smiles`; the code refuses them | `manual_test_data/af3_builder/batch/ligands_ccd_lookalike.smiles` |
| D3 | Two batch APIs | **Confirmed.** `VariantService.generate_from_file` commits specs; no front end calls it | `app/variant_service.py` |
| D4 | `run_info` documented as manifest content but never written | **Confirmed.** `build_manifest` returns it alongside `data`, and only `data` is encoded | `output/manifest.py` |
| F8 | A failed write part-way through a batch leaves earlier files | **Confirmed.** The executor wrote per-file atomically but kept everything already written | `output/execute.py` |

Nothing in the audit's §12 "unsupported" table was found to be mislabeled: FASTA is
still unsupported, SMILES is still grammar-checked only, and there is still no CCD
registry.

---

## 2. Defects fixed

### 2.1 Inline structural templates can be imported (audit D1, R5)

`transform/from_wire._import_references` now accepts **both** AF3 representations:

- `mmcif` — inline text, preserved verbatim as an `Inline` source (no file is
  created, no path is invented);
- `mmcifPath` — unchanged external/`External` source.

A row that sets **both** is refused with the offending location, matching AF3's own
`Only one of mmcif/mmcifPath can be set.`; a row with neither is refused too. A
failed import mutates nothing (the whole document is built or rejected as before).

Verified end to end through the real console (not just the service):
opened `tests/fixtures/af3_pipeline/test04_protein_msa_template/…json` (the builder's
own output, which carries inline `mmcif`), saved it to a new path, reopened it — the
`mmcif` text and `queryIndices`/`templateIndices` `[1, 2]` came back byte-identical.

**Consequence for the pipeline fixtures:** the fixture generator had been embedding
`">template\nACDEFGHIKL"` — a FASTA alignment — in the `mmcif` field, which is not
mmCIF and which no AF3 parser accepts. That constant is now a real ten-residue mmCIF
structure, and the three affected committed fixtures were regenerated
(`test03_protein_template`, `test04_protein_msa_template`,
`test20_comprehensive`). This is a fixture *correction*, and the byte-determinism
check (`generate_fixtures.py --check`, plus `tests/golden`) passes.

### 2.2 Template index mappings are validated against real sequences

`app/reference_validation.validate_reference` (used by every caller, including the
console prompt, the GUI form and the service API) now checks, in addition to the
existing shape/negative/query-bounds rules:

- **duplicate query indices** are refused, because AF3 builds its mapping with
  `dict(zip(queryIndices, templateIndices))` and would silently drop a pair;
- **template bounds** against the template's **full polymer sequence** — the one that
  includes residues without coordinates. `persistence/mmcif` reads that sequence
  through the installed parser (gemmi) and never infers it from atom coordinates, so
  the off-by-three error the check exists to prevent cannot be introduced here;
- a template with **no protein chain**, with **more than one protein chain**, or with
  a chain that declares **no residues** is refused with a message naming the cause;
- amino-acid identity is deliberately *not* compared: a homology template legitimately
  substitutes residues.

When the optional parser is absent the mapping cannot be read, so the bound check is
reported as unavailable rather than passed or guessed (`mmcif.index_check_available`,
and `DEPENDENCY_SETUP.md` installs gemmi in the recommended local setup).

**Fixture consequence:** the two "synthetic" templates
(`templates/minimal_template.cif` and its spaced-path copy) declared no polymer
records at all — so they declared no residues and were not structurally checkable.
They now declare a two-residue chain (`AG`) with `_entity_poly`, `_entity_poly_seq`
and `_struct_asym`, which makes them legitimate minimal templates for the existing
`0:0,1:1` path test. They remain explicitly non-biological; README and inventory sizes
and hashes were updated.

### 2.3 External `userCCDPath` travels with every generated configuration (F3)

Verified, then pinned by a test rather than changed: with the default
`CopyIntoAssets` policy each generated configuration gets `assets/my-ccd.cif` and
emits `"userCCDPath": "assets/my-ccd.cif"`; the path resolves relative to that
configuration's own file; moving the whole output directory leaves it working;
`userCCD` stays absent (mutually exclusive), and a base with inline `userCCD` still
serialises it. MSA and template copying are unchanged.

### 2.4 Generation summaries count roles, not plan rows (F4)

`app/results.batch_counts` counts **configurations**, **manifests**, **copied assets**
and the total, and `ui/present/strings.batch_summary` turns them into the one sentence
both front ends now print:

```
Generated 4 AF3 configurations. Wrote 1 manifest. Total output files: 5.
```

With external resources it adds `Copied 4 asset files.` and the total includes them.
The manifest is never described as a configuration, nothing is counted that was not
written, and a DNA record still counts as **one** configuration even though it holds
two strands. `LigandBatchOutput` now carries `copied_resources`, which is what made an
accurate total possible. The desktop's status-bar notice uses the same sentence, so the
status line cannot disagree with the report box.

### 2.5 The previews explain DNA duplexes and overwrite behaviour (F5)

Both previews now share one note (`strings.batch_preview_note`): what one entry
becomes, that the base is untouched, that existing files are never replaced, and that
**one** existing file with different content refuses the **whole** batch — with
"choose another output folder" as the safe recovery. For the DNA kind the note adds
that each entry becomes the strand supplied plus its reverse-complement strand, in one
configuration. The construction itself is unchanged.

The overwrite wording was also corrected where it was simply wrong: identical bytes are
**rewritten**, not skipped (the plan action is `overwrite`), so the "skipped"
message now describes only what the `Skip` policy does, and the "nothing was written"
branch no longer claims files "already existed with the same content".

### 2.6 File-input diagnostics (F6, F7)

- A line beginning with `>` now produces: *"this looks like a FASTA file, which the
  line-based sequence reader does not support: line N starts with '>' (…). Write one
  complete sequence per line with no header lines — copy each sequence record into its
  own line and load the file again."* The file is still refused whole; no header is
  stripped and nothing is reinterpreted.
- The protein alphabet was verified against upstream rather than assumed: AF3's chain
  constructor accepts `[A-Z]*` and maps anything outside the twenty standard residues
  to `UNK`. The builder accepts exactly that set, refuses lowercase/digits/punctuation
  the same way, and the reported `MVT`/`MVS`/`MVY`/`TEST` records remain valid.
- Input kinds stay explicit; no content heuristic reinterprets a file.

### 2.7 Documentation and stale fixtures (D2)

The `ligands_ccd_lookalike.smiles` comment now states what the code does (the file is a
**refusal** fixture; codes are never stored as `smiles`), and the batch README's FASTA,
overwrite, partial-write and summary passages were brought in line with the behaviour
above. The two synthetic templates' descriptions, the pack inventory (sizes and
SHA-256), and the affected "expected mapping" rows were updated.

### 2.8 Maintainability (D3, D4, F8)

- **Two batch APIs (D3):** kept, clearly marked as the *legacy* commit-based surface in
  `VariantService` with its distinct semantics spelled out, and with the note that the
  user-facing workflow is `GenerationService.generate_input_batch`. Removing it would
  mean rewriting the manual-test suite and the fixture generator for no user-visible
  gain; what matters is that both surfaces read and build through
  `app.batch_variants`, so a sequence cannot be read one way in one and another way in
  the other.
- **Manifest `run_info` (D4):** the module now documents the eleven fields that are
  actually written and states plainly that `run_info` is **not** written (a per-run
  timestamp would break the byte-reproducibility rule). A test pins both: the exact
  written key set, and that `run_info` exists for callers but is absent from the file.
- **Failed batch writes (F8):** `output.execute` now rolls back the part of a failed run
  that can be undone safely — files the run **created** are removed again, and the
  directories it made are removed when empty (including the implicitly created parents
  such as `<root>/<project>`, stopping at the output root). A file that already existed
  and was being replaced is **kept** (its old bytes cannot be restored) and the error
  says how many were left as rewritten. Nothing ever deletes a file that existed before
  the run, and per-file atomicity is unchanged.

---

## 3. Tests and actual results

Focused runs (each rerun after the change it covers):

| Suite | Result |
|---|---|
| `tests/unit/transform/test_from_wire.py`, `tests/unit/persistence/test_mmcif.py`, `tests/unit/app/test_reference_validation.py`, `tests/unit/ui/test_template_flow.py`, `tests/unit/app/test_batch_variants.py` | pass |
| `tests/gui/test_file_generation.py` (28) | pass |
| `tests/unit/app/test_batch_summary_counts.py` (new, 9) | pass |
| `tests/e2e/test_entity_batch_cli_subprocess.py`, `tests/e2e/test_menu_acceptance.py`, `tests/unit/ui` | pass |
| `tests/unit/output`, `tests/unit/app` | pass |
| `tests/golden` (fixture byte-determinism after regeneration) | pass |
| Full suite without the GUI: `python -m pytest tests --ignore=tests/gui` | **pass** |
| `tests/gui` minus `test_accessibility_and_launch.py` | **271 passed** |
| `tests/gui/test_accessibility_and_launch.py` | 7 of 11 pass; the 4 subprocess-launcher tests hang in this session (see §5) |

New coverage added by this pass:

- **Inline templates:** import of an inline-template document, save/reopen preservation
  of the `mmcif` text and the parallel index arrays, the both-fields rejection, the
  neither-field rejection, and (in `tests/unit/transform/test_from_wire.py`) a failed
  import leaving the open job untouched.
- **Index validation:** fully resolved fixture with a valid mapping, the
  unresolved-residue fixture with `templateIndices [3, 4, 5, 6]`, negative and
  out-of-range indices, template index beyond the full polymer sequence, unequal arrays,
  duplicate query indices, a structurally invalid template, and template preservation
  across save/reload.
- **Custom CCD:** `test_custom_ccd_path_is_copied_into_every_generated_configuration`
  (`tests/e2e/test_app_pipeline.py`) — asset copied, path rewritten relative, reference
  survives moving the directory, `userCCD` absent.
- **Summaries:** `tests/unit/app/test_batch_summary_counts.py` (roles, singular/plural
  wording, refused batch counts nothing, assets counted) and
  `tests/gui/test_file_generation.py::test_the_report_counts_configurations_apart_from_the_manifest`.
- **Preview wording:** the DNA-duplex/overwrite assertions in
  `test_the_preview_explains_the_dna_duplex_and_the_overwrite_policy`, plus the console
  variant in `tests/unit/ui/test_menu.py`.
- **FASTA and the protein alphabet:** the two FASTA diagnostics and the upstream-matched
  alphabet test in `tests/unit/app/test_batch_variants.py`.
- **Rollback:** `tests/unit/output/test_execute_atomicity.py` — a failed batch removes
  what it created, and a pre-existing file is left as rewritten rather than deleted.

Direct executions recorded for this report (not only unit tests):

- the console opened, saved and reopened the inline-template fixture; the `mmcif` text
  and both index arrays round-tripped exactly (§2.1);
- the console generated a DNA configuration and printed the shared sentence
  `Generated 1 AF3 configuration. Wrote 1 manifest. Total output files: 2.` with the
  `outputs/…` tree containing exactly `exp__batch-01.json` and `manifest.json`;
- `tools/af3_validation` and the pack were left untouched by these runs.

---

## 4. Files changed

**Behaviour**

- `configbuilder/transform/from_wire.py` — inline/external template import, both-fields
  refusal.
- `configbuilder/persistence/mmcif.py` — full polymer sequence and index-bound checks,
  pair-shape handling.
- `configbuilder/app/reference_validation.py` — duplicate-query and bound validation.
- `configbuilder/app/results.py` — `BatchCounts`, `batch_counts`, `copied_resources` on
  the batch outcome (and a corrected manifest docstring).
- `configbuilder/app/generation_service.py` — the outcome carries copied assets.
- `configbuilder/app/batch_variants.py` — FASTA diagnostic.
- `configbuilder/app/variant_service.py` — legacy batch surface marked and documented.
- `configbuilder/app/__init__.py` — exports the counter.
- `configbuilder/output/execute.py` — safe rollback of a failed run.
- `configbuilder/output/manifest.py` — documented fields vs. `run_info`.
- `configbuilder/ui/present/strings.py` — `batch_summary`, `batch_preview_note`, corrected
  overwrite/skip wording.
- `configbuilder/ui/render/menus.py`, `configbuilder/ui/render/qt/dialogs/batch_input.py`,
  `configbuilder/ui/render/qt/pages/entities.py` — the shared summary and note.

**Fixtures and docs**

- `manual_test_data/af3_builder/templates/minimal_template.cif` and
  `templates/with spaces/template with spaces.cif` — real polymer records added.
- `manual_test_data/af3_builder/batch/ligands_ccd_lookalike.smiles` — corrected comment.
- `manual_test_data/af3_builder/batch/README.md`, `manual_test_data/af3_builder/README.md`,
  `manual_test_data/af3_builder/templates/README.md`,
  `manual_test_data/af3_builder/INVENTORY.md`.
- `tests/fixtures/af3_pipeline/generate_fixtures.py` — real inline mmCIF constant, and the
  three regenerated committed fixtures.

**Tests**

- `tests/unit/persistence/test_mmcif.py`, `tests/unit/transform/test_from_wire.py`,
  `tests/unit/app/test_reference_validation.py`, `tests/unit/ui/test_template_flow.py`,
  `tests/gui/test_advanced_settings.py`, `tests/unit/ui/test_menu.py`,
  `tests/unit/app/test_batch_variants.py`, `tests/unit/output/test_manifest.py`,
  `tests/unit/output/test_execute_atomicity.py`, `tests/e2e/test_app_pipeline.py`,
  `tests/e2e/test_entity_batch_cli_subprocess.py`, `tests/golden/test_af3_pipeline_fixtures.py`,
  and the new `tests/unit/app/test_batch_summary_counts.py`.

- `docs/CONFIGURATION_GENERATION_PRACTICAL_AUDIT.md` — a status section appended
  (the as-found content is untouched).

---

## 5. Remaining limitations

- **Chemistry of SMILES is still not validated.** The check is the SMILES grammar
  (character set, brackets, ring closures, organic-subset atoms). Valence, aromaticity
  and perception remain AF3's (RDKit's) job; the builder does not depend on RDKit and
  does not claim chemistry. Unchanged by this pass, and stated as such in the READMEs.
- **No CCD registry.** Component codes are checked for shape only; membership is
  AF3-side.
- **FASTA remains unsupported.** It is now diagnosed instead of mis-reported; proper
  FASTA support (headers, wrapped records, names) was not implemented and is not
  advertised.
- **Template index checking needs the optional parser.** Without gemmi the mapping's
  bounds are not checked (and that is said, not implied). The recommended setup installs
  gemmi.
- **An overwritten file cannot be restored.** A failed batch undoes its own creations and
  says so; a file it replaced is left as rewritten, which is the honest limit of a
  per-file transaction.
- **The legacy commit-based batch API still exists** (documented, unused by both front
  ends). Retiring it is a separate change with its own test migration.
- **No AF3 inference was run.** This pass concerns JSON construction, resource packaging
  and import/export reliability; `tools/af3_validation` remains the structural check.
- **The reliable GUI evidence is the offscreen suite**, not a human session: the tests
  drive the real button and the packaged dialogs, but no interactive display was used.
- **Four launcher tests could not be completed in this session.**
  `tests/gui/test_accessibility_and_launch.py` starts the real window in a subprocess;
  the first four cases (`test_the_launcher_starts_the_demo_window_and_returns_cleanly`,
  both DPI variants and the spaces-in-path case) blocked for over six minutes each and
  were stopped, while the other 7 in the same file pass. Nothing in this pass touched the
  launcher (`gui.py`, `application.py` are unmodified), and the same suite passed in an
  earlier session, so this is recorded as an environment/session limitation rather than a
  regression — but it is **not** verified here.

---

## 6. User-facing workflow after the changes

Console — job menu → `7` → `1` → choose the kind → file → output folder:

```
What does the file contain?
  1. Protein sequences, one per line
  …
2
Sequence file (.txt, one sequence per line): C:\...\dna.txt

1 entries read from C:\...\dna.txt:
  - ATGC

Each DNA entry adds one new DNA entity to the base job: the strand you supplied plus
its reverse-complement strand, in one configuration.
The base job itself is not modified, and existing files are never replaced: if one
already exists with different content the whole batch is refused, so choose another
output folder instead.

Output folder for the configurations [...]: C:\...\out

Generating configurations...
Wrote C:\...\out\exp\exp__batch-01\exp__batch-01.json
Wrote C:\...\out\exp\manifest.json
Generated 1 AF3 configuration. Wrote 1 manifest. Total output files: 2.
Written under C:\...\out
```

Window — Entities → **Generate configurations from file…**: the same kind question, the
same review note (kind, entries, destination, DNA duplex, overwrite policy), and the
same sentence in both the result box and the status bar.

---

## 7. Blocked or needing a separate decision

- **Retiring `VariantService.generate_from_file` / `inspect_batch_file`** (audit R7):
  needs the manual-test suite and `generate_fixtures.py` moved onto
  `GenerationService` first. Left marked, not removed.
- **Exposing the overwrite/path policy inside the batch action** (audit R1, R3, R5-style
  usability work): the preview now states the rule, which was the cheap half; adding a
  picker is a UI decision for the operator, not a defect.
- **The four subprocess-launcher GUI tests** (§5) need an interactive display to
  complete; re-running them on a machine with a desktop is the remaining check for this
  pass.
