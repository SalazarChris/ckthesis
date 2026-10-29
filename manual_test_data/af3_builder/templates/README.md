# Structural template fixtures

Structural templates for AF3 jobs: an mmCIF file plus the `query:template`
residue index pairs that say which query residue each template residue stands
for. Both index arrays are **0-based**; `queryIndices[n]` pairs with
`templateIndices[n]`, and the two arrays always have the same length.

Everything in this folder is for exercising the builder's **template path
workflow**. None of these files has been through AlphaFold 3, and attaching one
proves nothing about prediction quality.

> **What the builder checks, and what it does not.** Attaching a template
> checks the path (exists, a regular file, ends in `.cif`/`.mmcif`), the file's
> *content* (non-empty, UTF-8, and readable as mmCIF: `persistence/mmcif.py`),
> and that every `query:template` pair is two non-negative whole numbers whose
> query index is inside the target sequence. The content check is an mmCIF
> parse with **gemmi** when that library is installed (the `templates` extra),
> and otherwise the bundled lexical scan: a `data_` block, a value for every
> data item, and every `loop_` row holding exactly as many values as the loop
> declares tags. Both refuse the same committed fixtures, so the verdict does
> not depend on the optional library.
>
> Nothing reads the template's own residues, coordinates or chain identity — so
> the expected indices below are **the values the user supplies**, and the
> fixtures exist so those values can be checked against a file a human can
> read. A parsed template proves the file is a structure, never that a mapping
> is biologically right.

> **Why the two synthetic files carry polymer records.** `minimal_template.cif`
> and its spaced-path copy are deliberately tiny, but they declare
> `_entity_poly`, `_entity_poly_seq` and `_struct_asym` for a two-residue chain
> (`AG`). The builder checks a template's index mapping against the template's
> *full polymer sequence*, and a file with atom rows alone declares no residues
> — so it can neither be checked nor be an AF3 template. They remain synthetic:
> never parsed by AlphaFold 3, not biological, no coordinates worth modelling.

---

## Files

| File | Full polymer sequence | Resolved residues (coordinates) | Use it with a query of | Expected mapping |
|---|---|---|---|---|
| `template_fully_resolved.cif` | `ACDEFG` (6) | all six: ALA1…GLY6 | `ACDEFG` | `queryIndices [0,1,2,3,4,5]`, `templateIndices [0,1,2,3,4,5]` |
| `template_unresolved_residues.cif` | `ACQDEFG` (7) | last four: ASP4, GLU5, PHE6, GLY7 | `DEFG` | `queryIndices [0,1,2,3]`, `templateIndices [3,4,5,6]` |
| `template_empty.cif` | — | none (0 bytes) | any | refused: *"the file is empty"* |
| `template_malformed.cif` | none declared | a truncated `_atom_site` loop | any | refused: *"the loop starting at line 9 declares 3 tags, and its values do not form complete rows of that size"* |
| `template_no_records.cif` | none declared | a `data_` block, a title, no records | any | refused: *"it has no _atom_site, _entity_poly, _struct_asym or _entity records"* |
| `minimal_template.cif` | `AG` (2) | ALA1, GLY2 | protein of two or more residues | `0:0,1:1` — the original smoke-test file |
| `with spaces/template with spaces.cif` | `AG` (2) | ALA1, GLY2 | protein of two or more residues | `0:0,1:1` — proves a path containing spaces survives the dialogs |

### Fixture A — `template_fully_resolved.cif`

Six-residue polymer `ACDEFG` (Ala-Cys-Asp-Glu-Phe-Gly) in chain A, residues
1–6, with a `CA` atom for every residue. Nothing is unresolved, so a
six-residue query maps one-to-one:

```json
{"queryIndices": [0, 1, 2, 3, 4, 5], "templateIndices": [0, 1, 2, 3, 4, 5]}
```

### Fixture B — `template_unresolved_residues.cif`

The **full** polymer is seven residues, `ACQDEFG`, declared by
`_entity_poly.pdbx_seq_one_letter_code` and by the seven rows of
`_entity_poly_seq`. Coordinates exist only for the last four (ASP4, GLU5,
PHE6, GLY7): ALA1, CYS2 and GLN3 are unresolved and have **no** `_atom_site`
rows. A four-residue query `DEFG` therefore maps to:

```json
{"queryIndices": [0, 1, 2, 3], "templateIndices": [3, 4, 5, 6]}
```

**Why `[3,4,5,6]` and not `[0,1,2,3]`?** AF3 template indices are positions in
the template's *polymer sequence*, not in the list of residues that happen to
have coordinates. `DEFG` is query residues 0–3, and in the template sequence
`ACQDEFG` those same residues sit at positions 3, 4, 5 and 6 — three residues
(ACQ) come before them, unresolved or not. Numbering from the first
coordinate-bearing residue would silently claim that the template's Asp is
residue 0, shifting every mapped residue by three positions and pairing the
query with the wrong part of the template.

The fixture is built so this is visible: `_entity_poly_seq` has seven rows,
`_atom_site` has four, and the first `ATOM` line says `ASP 4`.

### Fixtures C and D — invalid input

Three files, one per way a chosen file can fail to be a template:

- `template_empty.cif` — a 0-byte file. **Refused** at the file prompt with
  *"The template file '…' cannot be used: the file is empty. Enter another path
  or 0 to cancel."*; the template collection is cancelled and the entity keeps
  its previous template setting (nothing is half-attached).
- `template_malformed.cif` — non-empty text that is not readable mmCIF (a
  truncated `_atom_site` loop whose values cannot form rows of the three
  declared tags). **Refused** with the loop's line number.
- `template_no_records.cif` — lexically fine mmCIF with a `data_` block, a title
  and no atom or polymer records at all. **Refused**: AF3 would have no
  structure to read.

All three refusals leave the job exactly as it was — the same configuration
object, the field still "let AlphaFold search", and no `templates` field in a
saved file. What is deliberately *not* checked: whether the mapping is right
(the linker may match the wrong chain), whether the template's residues are
resolved, and whether its sequence is really the one the user means. Chain
matching and resolution/offset detection would be new biological semantics, not
structural validation.

---

## Manual testing

### Through the console

1. `python af3builder.py`
2. `1` New job → a name.
3. `2` Add entity → `1` Protein → the query sequence (`ACDEFG` for A, `DEFG`
   for B).
4. `1` for the MSA question (keep the setting).
5. `y` for *Use structural templates for this record?*
6. `3` *Provide template mmCIF files and residue index pairs*.
7. The fixture's full path, e.g.
   `…/manual_test_data/af3_builder/templates/template_unresolved_residues.cif`.
8. The pairs: `0:3,1:4,2:5,3:6` for B (or `0:0,1:1,2:2,3:3,4:4,5:5` for A).
9. `n` *Add another template?*
10. `6` *Save and show summary* → a destination, e.g.
    `C:\tmp\tpl-b\job.json`.
11. `0` to leave the job, `0` to exit.
12. Open the saved file. Expect (fixture B):

```json
"templates": [
  {
    "mmcifPath": "assets/template-unresolved-residues.cif",
    "queryIndices": [0, 1, 2, 3],
    "templateIndices": [3, 4, 5, 6]
  }
]
```

The template file is copied beside the JSON (`<dir>/assets/…`) because the
default path policy is *copy into the output folder*, and the JSON references
the copy relatively. Opening that JSON again (`2` on the main menu) and saving
it elsewhere must reproduce the same document: the import resolves the
relative path against the file's own folder.

### Through the desktop window

1. `python gui.py` (or `python gui.py --demo`).
2. **New** in the FILE footer → a name.
3. **Entities** → **Add Protein** → the query sequence.
4. With the entity selected, the *Templates* group → **Edit templates…**.
5. Choose *Provide template mmCIF files and residue index pairs*, **Add
   file…**, pick the fixture, type the pairs in the row's second cell
   (`0:3,1:4,2:5,3:6`), **Save**.
6. **Save JSON…** in the FILE footer → a destination outside the checkout.
7. Open the saved file: expect the block above. **Open…** that file again and
   save it under another name — the mapping must be unchanged.

### Recorded runs

Both front ends were driven against the fixtures while writing
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md`. Outputs were
written to throwaway folders (`<tmp>/resolved.json`, `<tmp>/partial.json`,
`<tmp>/first.json`, `<tmp>/second.json`, each with its own `assets/`
subfolder); nothing generated is stored in this pack. The pack stays input
only — `tests/gui/test_template_attachment.py` and
`tests/e2e/test_template_cli_subprocess.py` assert that its files are not
modified.

### Automated coverage

| Test module | What it drives |
|---|---|
| `tests/e2e/test_template_cli_subprocess.py` | fixtures A and B, the save → reopen → save round trip, and all three rejections (empty, malformed, no records), through `python af3builder.py` |
| `tests/gui/test_template_attachment.py` | the same fixtures through the real `TemplateEditorDialog` and the window's own save, including the three refusals and the untouched job |
| `tests/unit/persistence/test_mmcif.py` | the structure check itself over this pack, both tiers: the bundled scan and the installed parser, plus the lexical rules (loop width, a data item with no value, `;` text fields, quotes, comments) |
| `tests/unit/app/test_reference_validation.py` | the file and pair rules as the service enforces them (naming, contents, syntax, query range) |
| `tests/unit/transform/test_from_wire.py` | template import: `queryIndices`/`templateIndices` → `IndexPair` tuples |
