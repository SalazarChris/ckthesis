# Structural template fixtures

Structural templates for AF3 jobs: an mmCIF file plus the `query:template`
residue index pairs that say which query residue each template residue stands
for. Both index arrays are **0-based**; `queryIndices[n]` pairs with
`templateIndices[n]`, and the two arrays always have the same length.

Everything in this folder is for exercising the builder's **template path
workflow**. None of these files has been through AlphaFold 3, and attaching one
proves nothing about prediction quality.

> **What the builder checks, and what it does not.** There is no mmCIF parser
> in this project. Attaching a template checks that the path exists, is a
> regular file, ends in `.cif`/`.mmcif`, and is not empty, and that every
> `query:template` pair is two non-negative whole numbers whose query index is
> inside the target sequence. Nothing reads the template's own residues or
> coordinates — so the expected indices below are **the values the user
> supplies**, and the fixtures exist so those values can be checked against a
> file a human can read.

---

## Files

| File | Full polymer sequence | Resolved residues (coordinates) | Use it with a query of | Expected mapping |
|---|---|---|---|---|
| `template_fully_resolved.cif` | `ACDEFG` (6) | all six: ALA1…GLY6 | `ACDEFG` | `queryIndices [0,1,2,3,4,5]`, `templateIndices [0,1,2,3,4,5]` |
| `template_unresolved_residues.cif` | `ACQDEFG` (7) | last four: ASP4, GLU5, PHE6, GLY7 | `DEFG` | `queryIndices [0,1,2,3]`, `templateIndices [3,4,5,6]` |
| `template_empty.cif` | — | none (0 bytes) | any | refused: *"the file is empty"* |
| `template_malformed.cif` | none declared | a truncated `_atom_site` loop | any | **accepted** — see the limitation below |
| `minimal_template.cif` | one residue (ALA) | ALA1 | one-residue protein | `0:0` — the original smoke-test file |
| `with spaces/template with spaces.cif` | one residue | one | one-residue protein | `0:0` — proves a path containing spaces survives the dialogs |

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

### Fixture C — invalid input

Two files, because the builder has exactly one kind of "invalid" it can detect:

- `template_empty.cif` — a 0-byte file. **Rejected** at the file prompt with
  *"The template file '…' cannot be used: the file is empty. Enter another path
  or 0 to cancel."*; the template collection is cancelled and the entity keeps
  its previous template setting (nothing is half-attached).
- `template_malformed.cif` — non-empty text that is not a usable mmCIF at all
  (no `_entity_poly`, a truncated `_atom_site` loop). **Accepted**, because no
  mmCIF parsing happens. This is a documented limitation, not a pass: the
  builder stores and serialises the path without reading the structure.

Adding a real mmCIF parser (chain matching, resolution/offset detection, a
warning for template residues that are unresolved) would be new functionality
with a new dependency; it is deliberately out of scope here.

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
| `tests/e2e/test_template_cli_subprocess.py` | fixtures A and B, the save → reopen → save round trip, and fixture C's rejection, all through `python af3builder.py` |
| `tests/gui/test_template_attachment.py` | the same fixtures through the real `TemplateEditorDialog` and the window's own save, including the refusal and the accepted-malformed limitation |
| `tests/unit/app/test_reference_validation.py` | the pair rules themselves (syntax, query range, file checks) |
| `tests/unit/transform/test_from_wire.py` | template import: `queryIndices`/`templateIndices` → `IndexPair` tuples |
