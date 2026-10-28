# AF3 parser validation

This tool checks the claim "the JSON this builder emits is valid AlphaFold 3
input" against **AlphaFold 3's own input parser** — not a reimplementation, not a
hand-written schema.

It is not part of the test suite: it needs the network (to fetch AF3) and a
parser run of its own. The defects it found are pinned in the ordinary suite
(`tests/unit/ui/test_audit_regressions.py`, `tests/unit/transform/test_from_wire.py`,
`tests/unit/validation/test_rule_checks.py`) so they cannot come back.

## Run it

```bash
python tools/af3_validation/setup_validator.py   # once: fetch AF3 + install deps
python tools/af3_validation/run_all.py           # the four-stage report
```

Both keep everything they download in the OS temp directory
(`%TEMP%/af3-validator`, or `$AF3_VALIDATOR_HOME`). Nothing is installed into
this project's environment and nothing is written inside the repository.

`run_all.py` exits `0` only when every stage passes.

## What it does

| Stage | What it proves |
|---|---|
| 1. Positive control | AF3's own `examples/*.json` (13 files) are ACCEPTED. If the harness cannot accept genuine AF3 input, nothing it says about this builder counts. |
| 2. Negative control | 8 deliberate corruptions of a real example — missing/empty `modelSeeds`, wrong `dialect`, `version: 5`, an unknown top-level key, an unknown chain key, a sequence entry with no `id`, a bond naming an unknown chain — are all REJECTED. A harness that accepts rubbish proves nothing. |
| 3. Corpus | 35 documents built by this builder's own services and serialization path, covering all four families, multi-copy records, PTMs, bonds, a bonded multi-code glycan, MSA (inline and external), templates, custom CCD (inline and external), descriptions on every family, versions 1–4, a variant batch and explicit file-input batches for protein, DNA, RNA and CCD ligands; 33 are ACCEPTED and 2 custom-CCD documents are UNVERIFIED because the compiled CIF parser is stubbed. |
| 4. Round trip | Each official example is imported by the builder, re-emitted through the builder's generation path, and compared field by field against the original, with AF3's parser as the judge on both sides. |

## The parser, and what is stubbed

The parser is `alphafold3.common.folding_input.Input.from_json` from the official
repository (`google-deepmind/alphafold3`). `etils` (path reads), `rdkit` (SMILES
ligands) and `zstandard` are the real PyPI packages, so SMILES validation and
every `*Path` field are genuine.

`alphafold3.cpp.*` — the compiled C++ extensions — are stubbed **to raise if
used**. AF3 builds them with CMake for Linux/macOS targets only, and this
project must not require a C++ toolchain to be audited. The JSON-validation path
never calls them except for one field: `userCCD` / `userCCDPath`, which is parsed
with `cif_dict.parse_multi_data_cif`.

Consequence: the two custom-CCD corpus documents are reported **UNVERIFIED**, not
passed. Everything up to and including the field's placement is checked (AF3 gets
as far as the CCD and then needs the extension); the CCD content itself is not,
here. `UNVERIFIED` is never counted as a pass, and `run_all.py` says so in its
report.

## What the results do and do not establish

Established: the emitted documents satisfy AF3's own parser — its key sets, its
type checks, its dialect/version rules, its chain, modification, bond and
seed rules, its path reads and its SMILES handling — and every AF3 example this
builder imports comes back out with the same content AF3 sees in the original.

Not established:

* **No model run, no featurisation.** `from_json` builds the validated input
  object. Reference conformer generation, MSA pair matching, bond feasibility
  against real CCD atoms and the rest happen later in AF3 and are not covered.
  A document accepted here is a document AF3 will parse, not one it will run.
* **`userCCD` content** needs the compiled CIF parser (above). The CCD text is
  also user-supplied: the builder's own decision is which field carries it and
  that the file it points at exists and is readable — both exercised here.
* **Semantic chemistry of atom names.** `bondedAtomPairs` atom names are checked
  for shape and residue range, not against the CCD's real atoms. AF3's parser is
  equally permissive here; a wrong atom name fails later, in featurisation.
* **Batch sequence scope.** Protein, DNA and RNA batch outputs in the corpus are
  accepted as AF3 input JSON; the parser result does not establish that minimal
  test sequences are biologically useful or that inference succeeds. The batch
  action requires an explicit kind, since `.txt` alone is ambiguous. FASTA and
  per-entry custom-CCD definition files are not supported.
* **AF3's documented limitation is respected, not re-tested.** Bonds between or
  within polymers are refused by this builder (`R-BND-006`) because AF3's docs
  say they are unsupported; AF3's *parser* accepts them, so parsing does not
  catch that — the builder is the stricter side, deliberately.
