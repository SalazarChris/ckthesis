# AF3 builder — verification gap closure

**Date:** 2026-10-27. **Branch:** `main` (follow-up to the pushed end-to-end
verification, `522d36f`). This report closes the limitations that
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` and
`docs/LIGAND_VARIANT_GENERATION_IMPLEMENTATION_REPORT.md` left open, and it is
the document `docs/GATE_RECOVERY_IMPLEMENTATION_REPORT.md`,
`docs/GATE_AUDIT_AND_RECOVERY_REPORT.md`,
`docs/AF3_VARIANT_WORKFLOW_REFOCUS_REPORT.md` and
`docs/LIGAND_VARIANT_GENERATION_AUDIT.md` now point at.

The builder is an **input builder**: nothing in this report was produced by
running AlphaFold 3, and no AF3 inference was attempted. A generated document
is verified as a serialised AF3 JSON input that the project's own validation
accepts, never as a prediction.

---

## 1. What was re-verified, and against which baseline

Two changes were made to product behaviour (§2, §3); the rest of the work was
verification (§4, §5) and reporting. Every number below comes from a command
that was executed in this checkout on 2026-10-27.

| Suite | Command | Result |
|---|---|---|
| Core (everything but the GUI), historical run | `python -m pytest tests --ignore=tests/gui -p no:randomly` | **1285 passed, 1 skipped**, exit 0 (188.9 s); current-tree result appears in the 2026-10-28 addendum below |
| GUI, offscreen Qt, historical run | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -p no:cacheprovider --basetemp=.pytest-tmp -o addopts="" -q` | **270 passed**, exit 0 (58.7 s); current-tree result appears in the 2026-10-28 addendum below |
| Batch subsystem (historical, 2026-10-27) | `python -m pytest tests/unit/app/test_batch_variants.py tests/e2e/test_variant_cli_subprocess.py tests/e2e/test_entity_batch_cli_subprocess.py tests/gui/test_ligand_file_generation.py -p no:cacheprovider -o addopts="" -q` | **60 passed**, exit 0 (14.6 s); current follow-up counts are recorded in `docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14 |

### Why the counts differ from the recorded baseline

The audit recorded core **1147 passed / 1 skipped**, GUI **306 passed**, batch
subsystem **70 passed / 1 skipped**. None of those recorded numbers was
reproduced unchanged, and the differences are accounted for rather than
assumed:

* **Core: +138.** `tests/unit/validation/test_smiles_notation.py` (77 collected
  cases) and `tests/unit/persistence/test_mmcif.py` (31) are new this turn —
  108 cases — and the remaining 30 are net new cases inside existing modules
  (`tests/unit/app/test_reference_validation.py`,
  `tests/unit/app/test_batch_variants.py`,
  `tests/e2e/test_template_cli_subprocess.py`, …). Collection was checked for
  double-counting: 1286 node ids collected, 1286 unique, 1285 passed + 1
  skipped.
* **GUI counts are historical in this section.** The earlier 270 run predates
  the explicit-kind batch additions; the current GUI suite is 279 tests and
  passes in full with `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui
  -p no:cacheprovider --basetemp=.pytest-tmp -o addopts='' -q`. The current
  result, including the Windows temp-path workaround, is recorded in §14 of
  `docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md`. The older count
  explains the prior report only and is not a claim about the current tree.
**Historical batch result: 60.** The command at the time used the old GUI test
path and did not include `tests/unit/persistence/test_sequence_files.py`; those
counts describe the 2026-10-27 report run. The current follow-up focused result
includes persistence, batch builders, real CLI subprocesses and the Qt Entities
workflow, and is recorded in §14 of
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md`.

**No test was deleted, skipped or weakened to make the 2026-10-27 runs pass.**
The later current-tree test results are recorded separately in the follow-up
addendum. The historical working-tree diff removed seven test *functions* and
added seventeen, and every removal had a named replacement asserting the new
behaviour: e.g.
`test_a_malformed_template_is_accepted_and_that_is_a_known_limitation` →
`test_a_template_that_is_not_a_structure_is_refused_and_leaves_the_job_alone`;
`test_a_ccd_code_in_a_file_is_stored_as_smiles_text` →
`test_a_ccd_code_in_a_file_is_refused_and_nothing_is_written`; those old tests
asserted the defect that §2 and §3 close.

---

## 2. Structural templates: the file's content is now checked

**Status: fixed and verified** (the mapping itself remains the user's input —
see the limitation at the end of this section).

### The gap

`configbuilder/app/reference_validation.py` checked a template's *path* only:
existence, regular file, `.cif`/`.mmcif`, non-empty. Nothing read the file, so
`manual_test_data/af3_builder/templates/template_malformed.cif` — a truncated
`_atom_site` loop — was accepted and serialised as a template AF3 could not
read. Its sibling `template_no_records.cif` (a `data_` block, a title, no
records) had the same fate.

### What changed

* **`configbuilder/persistence/mmcif.py` (new).** `template_structure_problem`
  answers *is this file a structure at all?* in two tiers, strongest first:
  1. **gemmi**, the established mmCIF parser, when it is importable. It is
     reachable as the new optional `templates` extra in `pyproject.toml`
     (`gemmi>=0.6`); the core package and `[dev]` do not need it.
  2. **A bundled lexical scan**, always: a `data_` block, quoted values and
     `;` text fields, a value for every data item, every `loop_` row holding
     exactly as many values as the loop declares tags, and at least one
     structural category (`_atom_site`, `_entity_poly`, `_struct_asym`,
     `_entity`, `_pdbx_poly_seq_scheme`).

  The bundled tier is not a half-written parser standing in for a library: it
  implements the lexical rules that decide whether a file is readable at all,
  it names the defect with a line number, and it is what runs when gemmi is
  absent (the plan's §9.6 rule — an optional component may add strictness, never
  be required for a check). The two tiers agree on every committed fixture, so
  the verdict does not depend on whether the extra is installed. gemmi 0.6.5
  **is** installed in this environment, so both tiers were exercised here.
* **`reference_validation._file_problem`** now delegates the content question to
  that module (filesystem reading stays in `persistence`, per the dependency
  rules) and keeps the naming rules it owned. The user-facing wording is
  unchanged where it was already right: a missing file still says "the file does
  not exist", an empty one still says "the file is empty".
* **`tools/af3_validation/run_all.py`** wrote its own synthetic template as a
  bare tag list with no `loop_`, which the new check correctly refuses; the tool
  now emits a real `loop_` whose rows match its tags, and quotes the two values
  containing parentheses.

### Evidence

| Fixture | Verdict | Where it is asserted |
|---|---|---|
| `template_fully_resolved.cif` | accepted; `queryIndices [0..5]`, `templateIndices [0..5]` | `tests/e2e/test_template_cli_subprocess.py`, `tests/gui/test_template_attachment.py` |
| `template_unresolved_residues.cif` | accepted; four resolved residues map to their **polymer positions**, `templateIndices [3,4,5,6]` | same two modules (the mapping is read back out of the saved JSON) |
| `template_empty.cif` | refused: "the file is empty" | same |
| `template_malformed.cif` | refused, naming the loop and its line | `tests/unit/persistence/test_mmcif.py`, both end-to-end modules |
| `template_no_records.cif` | refused: no structural records | same |
| `with spaces/template with spaces.cif` | accepted, path survives the dialogs | `tests/gui/test_template_attachment.py` |

Both end-to-end modules drive a **real** path: the console one starts
`python af3builder.py` as a subprocess and answers its prompts; the GUI one opens
the shipped `TemplateEditorDialog`, adds the file, saves, and then saves the job
through the window. Each refusal is asserted to leave the job exactly as it was
(the same configuration object, the field still "let AlphaFold search", no
`templates` field written), so a failed attachment cannot half-modify a job.

### Limitation (unchanged, stated on purpose)

A parsed template proves the file **is a structure**, never that a mapping is
**biologically right**. `queryIndices`/`templateIndices` remain the user's own
values: chain identity, residue numbering, which residues are unresolved and the
template's true bounds are not derived here. The pack's fixtures exist so a human
can check those values against a file a human can read
(`manual_test_data/af3_builder/templates/README.md`).

---

## 3. SMILES: the grammar is checked, chemistry is not

**Status: partially implemented — closed as far as it can be without a chemistry
toolkit, and the remaining gap is now stated precisely instead of being implied
away.**

### What was claimed before, and what was true

The previous reports said "no chemistry validation of SMILES input". That was
accurate but incomplete: there was no *notation* check either, so `ATP` (a CCD
code), `MKTAYIAKQR` (a protein sequence) or a sentence typed into a ligand file
became `{"smiles": "..."}` and was serialised into a document AF3 would refuse.
`R-ENT-010` could only say "not checked" because no probe was wired.

### What changed

* **`configbuilder/validation/smiles.py` (new).** A grammar check, deliberately
  conservative: it refuses what *cannot* be SMILES and accepts everything it
  cannot rule out, so no user is blocked by a notation the check merely fails to
  understand. It enforces the SMILES character set, balanced parentheses and
  brackets, ring-closure numbers used exactly twice (including `%nn`) and never
  first, no bond symbol where an atom is needed, and unbracketed atoms drawn
  from the organic subset. Bracketed expressions (`[Zn+2]`, `[13CH4]`, `[nH]`,
  `[$1]`) are accepted as written.
* **`BundledChemistryProbe`** (`validation/ports.py`), wired in
  `ui/services.build_services`, so the shipped application has a probe. It
  implements the existing `ChemistryProbe` protocol and adds an optional
  `smiles_problem` that names the defect; `R-ENT-010` quotes it, so the finding
  reads "could not be parsed: it starts with a ring-closure number, …" instead of
  "could not be parsed". A probe without that method still works.
* **`app/batch_variants.ligand_specs_for_entries`** applies the same checker to
  every file entry, so a CCD code or a sequence in a ligand file is refused with
  its line number and nothing is written — one implementation for the file
  action and for a hand-typed ligand.

### What is still not checked (and must not be claimed)

Chemistry: valence, aromaticity, element vocabulary and perception. A
grammatical string that denotes no real molecule is written, and AF3's own RDKit
is what will judge it. No chemistry dependency was added; `rdkit`/`openbabel`
are not in the project and were not introduced for this. Nothing here is a
"chemically validated" label: a non-empty string that serialises is not
evidence, and the probe's own docstrings say so.

### Evidence

`tests/unit/validation/test_smiles_notation.py` (77 cases) covers the accepted
shapes (bracketed atoms, charges, isotopes, `%nn` rings, disconnected
components) and the refused ones (a CCD code, a sequence, a sentence, an
unbalanced bracket, an unpaired ring closure, a leading or trailing bond, a
leading ring digit, embedded whitespace). Positive controls live in
`manual_test_data/af3_builder/batch/ligands_notation_edges.smiles`, which the
console test drives end to end: `[Na+].[Cl-]`, `C%10CCCCCC%10`, `[2H]C([2H])…`,
`[13CH4]`, `C[C@H](N)C(=O)O` must all still produce files.

---

## 4. Protein, DNA and RNA batch generation: historical decision and current status

**Historical status when this report was first written (2026-10-27):** D2 had
narrowed that earlier workflow to ligands, so the sequence kinds were not exposed
in its UI. That was the accurate state at that time.

**Current status (2026-10-28 follow-up):** the user explicitly requested the
actual CLI and GUI paths for protein and DNA and asked to establish RNA support.
The shared batch service now exposes Protein sequence, DNA sequence, RNA sequence,
SMILES ligand and CCD-code ligand as five explicit input kinds. `.txt` content is
never auto-detected. The console and Qt Entities page route all five through
`GenerationService.generate_input_batch` and the same parser/build/validate/write
pipeline. The current support matrix is in
`manual_test_data/af3_builder/batch/README.md`.

The added builder maps protein → `FamilyARecord`, DNA → `FamilyCRecord`, and RNA
→ `FamilyBRecord`, preserving the model's family-specific JSON representation.
SMILES uses `ByNotation` and standard CCD uses `ByCode`. Custom CCD definitions
remain job-wide base state, not a candidate-list input. The console subprocess
tests and offscreen Qt tests inspect the generated files; the Qt suite also
clicks the production button and drives the packaged dialogs. These are automated
GUI checks, not a human-operated session.

FASTA is still unsupported (one sequence per non-empty line). The minimal
protein fixture tests parser and serialization behavior only; it does not imply
biological adequacy or useful AF3 predictions. No AF3 inference was run.

So a sequence file cannot be mistaken for a ligand file in either front end, and
no interface claims a capability it does not have.

**If RNA batch is wanted later** it is additive, not a rewrite: an `rna` entry in
`BATCH_RECORD_BUILDERS` producing the same `FamilyBRecord` the single-entity path
already builds, plus an action in the interface. It is not implemented because
nothing in the project requires it, and the support matrix in
`manual_test_data/af3_builder/batch/README.md` now says so explicitly.

---

## 5. GUI coverage: what is automated, and what is not

**Status: verified working within a defined scope.**

`tests/gui/test_file_generation.py` includes a test that replaces none of
the page's modal seams: it clicks the shipped button with `QTest.mouseClick`, so
the click→handler connection is real; it answers the two native `QFileDialog`
statics; and it presses the review box's own *Generate* button, so the box's
text and its `clickedButton` result are the shipped ones. The assertions are on
the files that reached the disk (two documents, each the base plus exactly one
ligand, unique identifiers, `assets/` beside them) and on the job being
unchanged. `tests/gui/test_template_attachment.py` does the same for the template
dialog and the window's own save.

**Not claimed:** no human-operated GUI session was performed. Every GUI run is
offscreen (Qt's `offscreen` platform). That leaves native dialog *appearance*,
DPI rendering, keyboard focus behaviour on a real display and macOS/Linux widget
differences unverified; the suite covers behaviour, not looks. A person following
the manual steps in `manual_test_data/af3_builder/README.md` is still the check
for those.

### An environment note that cost real time

The GUI launch tests run `gui.py` as a child process, which starts the
`.venv-gui` interpreter. On this machine that interpreter **cannot create files
under `%TEMP%`** (`PermissionError: [Errno 13]`, reproducible with a one-line
`open()`, while the same path succeeds from the plain project interpreter). With
pytest's default `tmp_path` — under `C:\Users\…\AppData\Local\Temp` — the launch
tests therefore hang: the child dies inside the test's `sitecustomize` hook,
never reaches its auto-close timer, and the parent waits on an inherited pipe
until the outer timeout. Running with `--basetemp=.pytest-tmp` (now the command
recorded in `.gitignore`, and the command the audit's baseline used) puts the
temporary files inside the checkout and everything passes. This is an
environment restriction, not a product defect: the GUI itself starts and closes
normally, and the same launch succeeds with a repo-local log path.

---

## 6. Regression results

All three suites in the table above passed with exit code 0 on the 2026-10-27
working tree. The statements in §§1, 6, 7, and 8 are historical snapshots from
that run; current follow-up suite results and support status are in §14 of
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md`. In addition, the
affected focused modules were run first
(`tests/e2e/test_template_cli_subprocess.py`,
`tests/gui/test_template_attachment.py`,
`tests/gui/test_file_generation.py`,
`tests/e2e/test_entity_batch_cli_subprocess.py`,
`tests/unit/app/test_reference_validation.py`,
`tests/unit/app/test_batch_variants.py`,
`tests/unit/persistence/test_mmcif.py`,
`tests/unit/validation/test_smiles_notation.py`, plus the architecture rules),
and the template/ligand GUI modules were re-run on their own (22 passed) before
the full GUI suite. The only red states seen after the product changes were the
environment hang described in §5 and the new check's first refusals of the
pack's own fixtures (§7), both diagnosed and re-run; nothing was left failing.

Specifically checked, and covered by the suites:

* previously accepted valid fixtures still attach, with their mappings intact;
* the malformed and no-record fixtures are refused, and the job is untouched;
* the ligand file action still produces one independent configuration per entry,
  base fields (seeds, version, dialect, `userCCD`, untouched entities and ids)
  preserved;
* duplicate names still get the deterministic `-2` suffix;
* the notation edges still produce files;
* no unrelated GUI functionality broke (270 passed, whole suite).

---

## 7. Files changed

**Product**

| File | Change |
|---|---|
| `configbuilder/persistence/mmcif.py` | **new** — mmCIF structure check: optional gemmi tier plus the bundled lexical scan; `template_structure_problem`, `structure_problem`, `library_available` |
| `configbuilder/validation/smiles.py` | **new** — SMILES notation grammar; `notation_problem`, `parses` |
| `configbuilder/app/reference_validation.py` | content of a template now judged by `persistence.mmcif`; naming rules unchanged |
| `configbuilder/validation/ports.py` | `BundledChemistryProbe` added (protocol unchanged) |
| `configbuilder/validation/__init__.py` | exports it |
| `configbuilder/validation/rules/entity_rules.py` | `R-ENT-010` quotes the probe's reason via an optional `smiles_problem` |
| `configbuilder/app/batch_variants.py` | each ligand entry's notation checked before a record is built |
| `configbuilder/ui/services.py` | wires `BundledChemistryProbe` in the shipped application |
| `pyproject.toml` | optional `templates` extra (`gemmi>=0.6`) |
| `tools/af3_validation/run_all.py` | its own synthetic template is now a real `loop_` |

**Fixtures**

`manual_test_data/af3_builder/templates/template_no_records.cif` (new),
`manual_test_data/af3_builder/batch/ligands_notation_edges.smiles` (new),
`templates/template_malformed.cif` (its header comment now states the refusal),
and the four manual-test READMEs (`af3_builder/README.md`,
`templates/README.md`, `batch/README.md`,
`entity_batch_generation/README.md`).

One finding worth recording: the two fixtures that were described as valid —
`templates/minimal_template.cif` and
`with spaces/template with spaces.cif` — each had two `_atom_site` rows with
**eleven** values under a loop that declares **ten** tags (an extra
`label_atom_id` two columns wide). No parser had ever read them, so nothing had
noticed. The rows were corrected rather than the width rule loosened; both files
are accepted, at the same `0:0` mapping as before.

**Tests**

`tests/unit/persistence/test_mmcif.py` and
`tests/unit/validation/test_smiles_notation.py` (new);
`tests/unit/app/test_reference_validation.py`, `tests/unit/app/test_batch_variants.py`,
`tests/unit/app/test_gate_recovery.py`,
`tests/e2e/test_template_cli_subprocess.py`,
`tests/e2e/test_entity_batch_cli_subprocess.py`,
`tests/e2e/test_variant_cli_subprocess.py`, `tests/e2e/test_manual_test_data.py`,
`tests/gui/test_template_attachment.py`,
`tests/gui/test_file_generation.py` (renamed and updated).

**Docs** — this report, plus status notes in
`docs/LIGAND_VARIANT_GENERATION_AUDIT.md`,
`docs/LIGAND_VARIANT_GENERATION_IMPLEMENTATION_REPORT.md`,
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md`,
`docs/AF3_VARIANT_WORKFLOW_REFOCUS_REPORT.md`,
`docs/AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md` and
`docs/GATE_RECOVERY_IMPLEMENTATION_REPORT.md`.

---

## 8. Remaining limitations

| Limitation | Classification |
|---|---|
| SMILES **chemistry** (valence, aromaticity, perception) is not checked | **not attempted by design** — AF3's RDKit decides; no chemistry dependency added |
| A grammatical notation that denotes no molecule is written | consequence of the above; stated in the pack README and in the probe's docstring |
| Template **mappings** are not derived or verified biologically; chain identity, residue numbering and unresolved residues are the user's input | **out of scope by design** — a structure check cannot decide it |
| Template's residues are not read to compute sequence identity or bounds | **unsupported** |
| Protein / DNA / RNA batch through a front end | **Implemented and verified** through explicit-kind CLI subprocesses and the PySide6 Entities workflow; the current suite results and support matrix are in `docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14 and `manual_test_data/af3_builder/batch/README.md` |
| A human-operated GUI session (native dialogs, DPI, focus on a real display) | **unverified — environment**; offscreen automated coverage only |
| `%TEMP%` writes from the `.venv-gui` interpreter | **environment restriction, worked around for verification** with `--basetemp=.pytest-tmp`; full GUI suite passed with that option |
| AF3 inference / prediction quality | **never attempted** — this project builds inputs |

---

## 9. Current-tree addendum (2026-10-28)

These checks were re-run in the current checkout after explicit input-kind
selection and support for protein, DNA, RNA, SMILES and CCD-code batches were
integrated. Counts below supersede §1's historical figures where relevant.

| Check | Executed result |
|---|---|
| Focused sequence/batch/CLI/GUI path | **97 passed, 1 skipped** across sequence persistence, batch record construction, CLI subprocesses, legacy SMILES CLI and GUI/manual-pack GUI tests |
| Full core (all except GUI) | **1,297 passed, 1 skipped**, with one Matplotlib/PyParsing deprecation warning |
| Full GUI (PySide6 offscreen) | **280 passed**; used repository-local pytest basetemp for this Windows environment |
| Official AF3 parser corpus | **PASS**: 13/13 positive examples accepted, 8/8 corruptions rejected, 33 corpus documents accepted, 2 custom-CCD documents unverified, 13/13 round trips accepted |
| Direct CLI protein smoke | Four written JSON outputs inspected; each preserves base settings/entities and adds only its matching protein sequence. With a temporary base copy omitting only `userCCD`, all four were accepted by the official AF3 parser; the original userCCD base correctly yields UNVERIFIED because the harness stubs AF3's compiled CIF parser. |

The focused, core, GUI and parser-corpus results are recorded with their full
commands in `docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14.
The direct smoke used a temporary base document without custom CCD so AF3's
parser could independently validate all four outputs. The separate direct run
with the original base did not pass that check: it was UNVERIFIED at AF3's
compiled `cif_dict` extension, as expected and documented. Neither run tests
AF3 inference or biological usefulness of these short sequences.

---

## 10. Manual check for a person at the keyboard

Templates (expect the malformed and no-record files to be refused):

1. `python af3builder.py` → `1` New job → name → `2` Add entity → `1` Protein →
   `ACDEFG` → keep the MSA setting → `y` for templates → `3` provide files.
2. Type the path to `manual_test_data/af3_builder/templates/template_malformed.cif`.
   Expect a refusal naming the loop and its line, and the template collection
   cancelled — the entity keeps its previous setting.
3. Repeat with `template_unresolved_residues.cif` and query `DEFG`, pairs
   `0:3,1:4,2:5,3:6`; save the job and check the `templates` block in §2's table.

Input batches (one document per entry; each input kind is explicit):

1. `python af3builder.py` → `2` Open a JSON file →
   `manual_test_data/af3_builder/batch/base_job_custom_ccd.json` → `7` Generate
   configurations from a file → `1` → choose the kind, e.g. `4` SMILES →
   `batch/ligands_named.smiles` → choose the destination.
2. Check the three ligand documents carry the unchanged base and one added
   ligand apiece. Repeat with Protein sequences (`1`) and
   `batch/proteins_minimal.txt`: four output JSONs should each carry the base
   plus exactly one of MVT/MVS/MVY/TEST. Each run also writes its manifest.
3. Open a sequence file in SMILES mode: expect a clear refusal with kind advice,
   no destination write, and the base job unchanged. Confirm the fixture pack
   itself remains unchanged.
