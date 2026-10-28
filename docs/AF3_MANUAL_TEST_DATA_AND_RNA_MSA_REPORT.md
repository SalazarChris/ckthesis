# AF3 Builder — Manual Test Data and RNA MSA Audit

**Original audit:** 2026-10-25 · **Current status:** 2026-10-28 follow-up

The original MSA audit and its fixtures remain useful; batch support and tests
have since been expanded. The dated follow-up entries below and in §10 supersede
historic batch-availability claims.

---

## 1. Revision and working-tree protection

| Item | Value |
|---|---|
| Branch / HEAD (historical) | `main` at `347620f` — “Make MSA and template inputs complete and validated”; current verification results are in `docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14 |
| State inherited (historical) | the **gate-recovery implementation from the preceding task**, still uncommitted at the time; not a description of the current working tree |
| Protection | no `reset`, `clean`, `checkout`, `restore`, `stash`, rebase, amend or formatting sweep was run; nothing was committed or pushed |
| What the original audit changed in existing files | four targeted edits: console wording/menu call sites plus a pointer in `RUNNING_THE_APPLICATION.md`; later follow-up changes are documented separately in §10 and the current end-to-end report |
| AF3 inference / network | none. No cluster, no server, no download |

The remainder of this report records the original audit. Current batch fixtures,
syntax and test results are maintained in the batch README and the current
end-to-end report.

---

## 2. Files created and modified

Created:

| Path | Purpose |
|---|---|
| `manual_test_data/af3_builder/README.md` | fixture explanation, formats, RNA MSA reference, seven walkthroughs, JSON checks, cleanup |
| `manual_test_data/af3_builder/INVENTORY.md` | every file with size and SHA-256 |
| `manual_test_data/af3_builder/batch/*` (8 files) | batch inputs and their refusal cases |
| `manual_test_data/af3_builder/msa/*` (4 files) | protein MSA pair, RNA A3M, RNA A3M under a path with spaces |
| `manual_test_data/af3_builder/templates/*` (2 files) | synthetic mmCIF, also under a path with spaces |
| `tests/e2e/test_manual_test_data.py` | 26 fixture-driven tests across parser → service → JSON → output policy, plus two console end-to-end runs |
| `tests/gui/test_manual_test_data_gui.py` | 7 window-level tests (RNA modes, path with spaces, template restriction, batch family list, batch run) |
| `docs/AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md` | this report |

Modified:

| Path | Change |
|---|---|
| `configbuilder/ui/present/strings.py` | `menu.templates_skip_new` (new), `menu.msa_files_explained_rna` (new), `menu.variant_file_protein` reworded to “one sequence per line” |
| `configbuilder/ui/render/menus.py` | RNA uses its own file-choice explanation; a new record's template-skip message is the template wording |
| `tests/unit/ui/test_msa_flow.py` | two regression tests for the wording defects |
| `RUNNING_THE_APPLICATION.md` | three-line pointer to the pack and this report |

---

## 3. Test-data tree

```
manual_test_data/af3_builder/
├── README.md
├── INVENTORY.md
├── batch/
│   ├── proteins_valid.txt              3 protein sequences, one per line
│   ├── proteins_wrapped_fasta.txt      FASTA header + wrapped rows (refused)
│   ├── rna_sequences.txt               3 RNA sequences — no RNA batch reader
│   ├── dna_sequences.txt               2 DNA sequences
│   ├── ligands_valid.smiles            2 named + 1 bare SMILES, with a comment
│   ├── ligands_unchecked_syntax.smiles malformed notation (refused, per line)
│   ├── empty.txt                       zero bytes (refused)
│   └── invalid_sequence.txt            lines 2–3 invalid (refused, by line)
├── msa/
│   ├── protein/unpaired-query.a3m      A3M, first row = query
│   ├── protein/paired-query.a3m        A3M for the paired side
│   ├── rna/query-rna.a3m               A3M, first row = query (ACGUACGU)
│   └── with spaces/rna query.a3m       same content, spaces in dir and name
└── templates/
    ├── minimal_template.cif            synthetic one-residue mmCIF
    └── with spaces/template with spaces.cif
```

All content is synthetic, tiny and deterministic (14 fixtures, 1–12 lines each).
The pack is input only: `test_running_the_pack_writes_nothing_inside_it` compares
the tree (paths + sizes) before and after a full run and asserts no `assets/`
directory appears inside it.

---

## 4. RNA MSA behaviour matrix

Traced through the live code, not inferred from protein. Files:
`configbuilder/model/alignment.py`, `configbuilder/app/configuration_service.py`,
`configbuilder/transform/{accessors,mappings,engine}.py`,
`configbuilder/validation/rules/msa_rules.py`, `configbuilder/output/plan.py`,
`configbuilder/ui/render/qt/pages/advanced.py`, `configbuilder/ui/render/menus.py`.

### 4.1 The three states

| UI choice (console) | UI choice (window) | Service call | Stored model value | Exact JSON for `"rna"` |
|---|---|---|---|---|
| `1 Use the current/default MSA behavior` | Mode *Let AlphaFold search for MSAs automatically* | `set_alignment(key, "automatic")` | `SingleAutomatic` | no `unpairedMsa`, no `unpairedMsaPath` |
| `3 No MSA - run without alignment data` | Mode *No MSA - proceed without alignment data* | `set_alignment(key, "free")` | `SingleFree` | `"unpairedMsa": ""` |
| `2 Provide existing MSA file(s)` → `RNA MSA file:` | Mode *Provided (paste or file)* → *Paste inline text* or *Use a file* | `set_alignment(key, "provided", external_path=… \| inline_text=…)` | `SingleProvided(External \| Inline)` | `"unpairedMsaPath": "<path or assets/…>"` **or** `"unpairedMsa": "<a3m text>"` |

Emission is `RNA_FIELDS` in `configbuilder/transform/mappings.py` (MAP-307/
MAP-308) via `_rna_msa_value` in `accessors.py`; only those two fields exist for
RNA, and there is no paired key anywhere on the RNA path.

### 4.2 Contract evidence (primary source)

AF3's own `docs/input.md`, vendored in this checkout at
`.freebuff/af3-validator/alphafold3-main/docs/input.md`:

* §RNA: `"unpairedMsa": …, # Mutually exclusive with unpairedMsaPath` and
  `"unpairedMsaPath": … # Mutually exclusive with unpairedMsa` — the RNA example
  contains no paired field, unlike the protein example two sections above.
* §RNA: *“`unpairedMsa`: An optional multiple sequence alignment for this chain.
  This is specified using the A3M format.”* and *“`unpairedMsaPath`: … The file
  must be in the A3M format, and could be either plain text, or compressed using
  gzip, xz, or zstd.”* — path may be absolute or relative to the JSON.
* §RNA Multiple Sequence Alignment: exactly three states — unset/null (automatic,
  the recommended option), `""` (MSA-free), non-empty A3M (provided).
* §Protein Multiple Sequence Alignment: the “both set or both unset” rule and the
  paired/unpaired combinations — protein only.

And the runtime-side key check in
`.freebuff/af3-validator/alphafold3-main/src/alphafold3/common/folding_input.py`
(`RnaChain.from_dict`): the allowed key set is
`{id, sequence, modifications, description, unpairedMsa, unpairedMsaPath}` —
`pairedMsa` is rejected as an unknown key, and setting both the field and the
path raises “Only one of unpairedMsa/unpairedMsaPath can be set.”

The repository contract agrees: `AUTHORITATIVE_SPEC.md` §11 “RNA” — *“Only
`unpairedMsa`/`unpairedMsaPath` is supported”* — and DOMAIN_MAPPING MAP-307/308.

### 4.3 Everything else, per question

| Question | Answer (builder behaviour) | Evidence |
|---|---|---|
| Modes offered | automatic / provided / free, in **both** front ends | `_RNA_MODES` (GUI), `_chain_msa` (console); `set_alignment` accepts exactly those three for RNA |
| Controls shown | source controls appear only for `provided`; automatic/free refuse a source | `AlignmentFormDialog` + `set_alignment` |
| Inline vs path | GUI offers both; console offers **path only** | `_apply_alignment`; `_chain_msa` RNA branch |
| Format | A3M text. Inline content is checked shallowly by `R-MSA-003` (A3M alphabet, advisory) and `R-MSA-004`/`R-MSA-005` (query-first, rectangular after removing insertions — advisories) | `validation/rules/msa_rules.py` |
| File validation | missing / empty / unreadable / directory → **blocking** `R-MSA-006` (preflight), reported by readiness, save, preview and generation | same file; `validation/ports.OsFilesystemPort` |
| Version | external path needs version ≥ 2; at v1 save is refused naming the version | `mappings.MSA_PATH_MIN_VERSION`; verified in `test_an_external_msa_path_at_version_one_is_refused_by_name` |
| Output policy | `CopyIntoAssets` (default): copied to `assets/`, name slugged, JSON points at the copy. `AsGiven` / `RelativeToOutput`: the path is emitted as given (forward slashes), nothing copied, drive-letter/UNC paths warn | `output/plan.resolve_resources_into`; tests below |
| Paths with spaces | work end to end; the copy is slugged (`rna query.a3m` → `assets/rna-query.a3m`) | 4 tests, console + window |
| Import of `pairedMsa` on RNA | dropped, with import note `sequences[0].rna.pairedMsa` | `from_wire`; new test |
| AF3 runtime acceptance | **not verified** | — |

### 4.4 What is verified versus not

Verified here (no AF3): the UI choices, the stored model value, the exact keys
and values written, file/path validation, asset copying under each policy, the
version requirement, the import note, CLI/GUI parity of the rule set.

Not verified: that AF3 parses these specific A3M files, that its data pipeline
accepts them as alignments, that RNA MSA search/featurisation behaves as the
documentation promises, or anything about model output.

One runtime nuance worth knowing (read from the vendored source, not tested): AF3
treats an `unpairedMsa` string shorter than 256 characters as a **path** if a file
by that name exists, and then refuses with *“Set the unpaired MSA path using the
`unpairedMsaPath` field”*. The builder writes inline A3M text, which is never a
path in practice, but a hand-crafted document could hit it.

---

## 5. CLI and window: differences

| Capability | Console | Window | Assessment |
|---|---|---|---|
| RNA MSA modes | automatic / provided / free | same three | parity |
| RNA provided source | file only | inline text **or** file | deliberate: the console has no paste UI; both land in the same model value |
| Protein MSA | unpaired / paired / both / free / automatic, files only | same modes, inline or file | parity of modes; console offers no inline |
| Templates | protein only, several files with pairs | protein only, same dialog | parity |
| Batch input families | protein / DNA / ligand | protein / DNA / ligand (combo) | parity |
| Batch reader | one sequence per line; SMILES lines | same service call | parity |
| Save/Generate | job menu `6` writes JSON (+assets) | **Save** in FILE footer; **Generate** page for folder runs | different entry points, same services |
| Readiness/refusal wording | status rows + blocked-save message | Overview readiness line + blocking message | same findings from the same `ValidationService` |

No capability mismatch was found beyond the console's lack of an inline-MSA
prompt, which the README documents.

---

## 6. Test commands and results

Environment: Windows, Python 3.11.15, pytest 8.2.2, PySide6 6.12.0.

| Run | Command | Result |
|---|---|---|
| **Baseline** (immediately before this task, same tree) | `python -m pytest --ignore=tests/gui -p no:cacheprovider` | **1096 passed, 1 skipped** |
| **Baseline** GUI | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui --basetemp=.pytest-tmp -o addopts=""` | **290 passed** |
| After — core | `python -m pytest --ignore=tests/gui -p no:cacheprovider -o addopts=""` | **1124 passed, 1 skipped, 1 warning in 121.94 s** (exit 0) |
| After — GUI | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -p no:cacheprovider -o addopts="" --basetemp=.pytest-tmp` | **297 passed in 48.47 s** (exit 0) |
| New pack tests | `python -m pytest -o addopts="" -q tests/e2e/test_manual_test_data.py` | **26 passed** |
| New window tests | `… tests/gui/test_manual_test_data_gui.py` | **7 passed** |
| Console MSA flow | `… tests/unit/ui/test_msa_flow.py` | **9 passed** (7 existing + 2 regression) |
| Compilation | `python -m compileall -q configbuilder` | exit 0 |
| Lint (repo subset) | `ruff check --select E4,E7,E9,F configbuilder tests/e2e/test_manual_test_data.py tests/gui/test_manual_test_data_gui.py tests/unit/ui/test_msa_flow.py` | `All checks passed!` |

Delta: **+28 core tests** (26 pack + 2 console regressions) and **+7 window
tests**; no existing test changed expectation. The single skip is unchanged and
pre-existing: `tests/unit/persistence/test_sequence_files.py::test_unreadable_file_is_a_clear_persistence_error`
(`skipif(os.name == "nt")`).

Architecture and contract tests are inside the core run and pass. The GUI suite
needs `--basetemp` inside the workspace on this machine, because the launch tests
start `.venv-gui`, whose interpreter cannot write to `%LOCALAPPDATA%\Temp` here;
that is an environment limitation recorded in the gate-recovery report, not a
result of this task.

No failures were observed, so no test is labelled pre-existing/newly introduced/
indeterminate.

---

## 7. Defects found and fixed (minimal, wording only)

Each was demonstrated with a failing test first, then fixed; no biological or
input semantics were changed.

1. **RNA file choice explained paired sides.**
   *Observed:* choosing *Provide existing MSA file(s)* for an RNA chain printed
   “Paired and unpaired are separate files; leave one blank only when that side
   must be the empty string.”, then asked for a single `RNA MSA file:`.
   *Fix:* `menu.msa_files_explained_rna` — “RNA uses a single MSA file in A3M
   format; it has no paired side. Enter one file path.”
   *Test:* `test_the_rna_file_choice_does_not_explain_paired_sides`.

2. **Declining templates announced “No MSA will be used”.**
   *Observed:* after adding an entity *with* a provided MSA and answering `n` to
   `Use structural templates for this record?`, the console said “No MSA will be
   used - edit the entity to change this later.”
   *Fix:* new `menu.templates_skip_new` (“No templates will be used …”); the edit
   flow keeps `menu.templates_skip_edit`.
   *Test:* `test_skipping_templates_says_templates_not_msa`.

3. **Batch input label promised FASTA.**
   *Observed:* the console's batch file-type entry read “Protein sequences
   (FASTA-like .txt file)”, while the reader accepts only one sequence per line
   and has no header/wrapping support. A headerless wrapped file silently becomes
   several variants.
   *Fix:* “Protein sequences (one sequence per line, .txt file)”.
   *Test:* assertion in `test_console_protein_batch_creates_one_variant_per_entry`.

No defect was found in the RNA MSA data path itself: the model value, the two
emitted fields, the three states, the file validation and the asset copying all
behave as the contract describes.

---

## 8. Builder behaviour versus AF3 runtime

| Claim | Status |
|---|---|
| RNA has exactly `unpairedMsa` / `unpairedMsaPath`; no paired field | **Verified** in builder code and AF3's vendored documentation + key sets |
| Three RNA states map to unset / `""` / non-empty A3M | **Verified** (builder tests; documented) |
| External MSA paths are copied or emitted per policy | **Verified** (builder tests) |
| Missing/empty MSA file blocks save | **Verified** (builder tests) |
| A given A3M will be accepted by AF3 | **Unverified** — would need an AF3 run |
| The synthetic mmCIF is a usable template | **Unverified** — builder never parses mmCIF |
| A SMILES string is a valid molecule | **Unverified** — no parser is wired |
| Batch variants produce sensible models | **Out of scope** — sequences are synthetic |

The builder's two content advisories (query-first row, rectangular alignment) are
documented for **protein** MSAs in AF3's `input.md`. Applying them to RNA is a
project choice made earlier; it is advisory (WARNING) and never blocks. It is
listed below as a decision the reviewer may want to revisit.

---

## 9. Manual run checklist

Full steps, prompts and expected JSON are in
`manual_test_data/af3_builder/README.md` §4. Short form:

- [ ] Console: open a base job → job menu `7` → choose Protein sequences
      (`1`) → `batch/proteins_minimal.txt` → four independent protein outputs.
- [ ] Console: choose SMILES (`4`) → ligand batch from
      `batch/ligands_valid.smiles` → three independent ligand outputs.
- [ ] Console: protein with `msa/protein/unpaired-query.a3m` (blank paired side)
      → `unpairedMsaPath` + `pairedMsa: ""`.
- [ ] Console: protein with both A3M files → both path fields.
- [ ] Console: RNA with `msa/with spaces/rna query.a3m` → `unpairedMsaPath`
      only; console says “single MSA file”.
- [ ] Console: RNA MSA choice `1` (no fields) and `3` (`unpairedMsa: ""`).
- [ ] Console: protein template `templates/with spaces/template with spaces.cif`
      with pairs `0:0,1:1` → `templates[0].mmcifPath`.
- [ ] Window: Entities → Add RNA → Change alignment → Provided + inline text,
      then Provided + file (spaces) → same two JSON shapes.
- [ ] Window: confirm **Edit templates…** is absent/refused for RNA.
- [ ] Window: Entities → Generate configurations from file… → choose Protein
      sequences → `batch/proteins_minimal.txt`; verify four output files and one
      protein sequence added per output. RNA is offered as its own explicit kind.
- [ ] Window: Generate → Base job only → Copy into the output folder → Preview
      plan → Generate → `assets/rna-query.a3m` exists and the JSON points at it.
- [ ] Repeat with *Use the paths exactly as entered*: no `assets/`, path as given.
- [ ] Delete a configured `.a3m` and press Save → blocked with `R-MSA-006`.
- [ ] Choose `batch/proteins_wrapped_fasta.txt` in Protein sequence mode →
      refused, line 1 named; FASTA/wrapped input is unsupported.

---

## 10. Limitations and decisions needed

RNA batch is implemented as an explicit input kind and verified through the
real CLI and PySide6 Entities workflow. Current syntax and evidence are in
`manual_test_data/af3_builder/batch/README.md` and
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14.

1. ~~**SMILES parsing still does not exist.** `batch/ligands_unchecked_syntax.smiles`
   is accepted. Making invalid SMILES blocking needs a parser dependency
   (`rdkit`/`openbabel`) wired as a `ChemistryProbe`; that decision is unchanged
   from the gate-recovery report.~~ **Partly closed 2026-10-27.** The file is now
   refused, naming each line's defect: SMILES *grammar* (character set, balanced
   brackets, paired ring closures, unbracketed atoms from the organic subset) is
   checked by a bundled probe, so no dependency was taken on `rdkit`/
   `openbabel`. Still not checked, and still not claimed: chemistry — valence,
   aromaticity and perception stay with AF3's own parser. See
   `docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §3.
2. **RNA batch:** implemented as an explicit supported input kind, builds the
   model's RNA entity representation, and is covered by the real CLI and
   PySide6 Entities tests plus AF3 input-parser validation. Current syntax and
   scope are in `manual_test_data/af3_builder/batch/README.md`. This does not
   claim AF3 inference quality.
3. **RNA content advisories are protein-documented.** AF3 documents “first row =
   query” and “rectangular after removing insertions” under the protein section.
   The builder applies them to RNA as warnings. Decision: keep, or scope them to
   protein.
4. **No inline MSA in the console.** The GUI can paste A3M; the console can only
   take a path. Adding a paste prompt is a small UI change if desired.
5. **Template fixtures are deterministic test structures.** Content parsing,
   structure presence and residue-index mappings are covered by the template
   validation and attachment tests; they are not experimental structures or
   evidence of prediction quality.
6. **RNA inline MSA text can be mistaken for a path by AF3** when it is shorter
   than 256 characters and names an existing file (see §4.4). The builder cannot
   detect this; the README does not encourage such content.
