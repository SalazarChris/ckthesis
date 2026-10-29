# AF3 Builder — manual test pack

Small, synthetic input files for driving the **builder** by hand through both front
ends: the console menu (`python af3builder.py`) and the desktop window
(`python gui.py`). They cover ligand batch generation, external MSA files
(protein and RNA), and template files, including a directory whose name
contains spaces.

Read this first:

* **What these files prove.** That the builder parses them, stores them, shows
  them, validates them and writes them into an AF3 JSON in the way described
  below.
* **What they do not prove.** That AlphaFold 3 inference will produce a good
  model. The output corpus is checked with AF3's own input parser by
  `python tools/af3_validation/run_all.py` (the custom-CCD cases remain
  UNVERIFIED where the harness stubs AF3's compiled CIF parser). The
  sequences/SMILES/alignments are deliberately trivial and are not evidence of
  inference quality.

Every file is tiny, deterministic and synthetic. Do not read biological meaning
into any of it.

Paths below are relative to the repository root. The pack lives in
`manual_test_data/af3_builder/`.

---

## 1. Input formats the builder actually accepts

These are the rules the parsers enforce (`configbuilder/persistence/sequences.py`).
They are narrower than "FASTA" in general:

| Input | Accepted form |
|---|---|
| **SMILES ligand file** (`.smiles`, `.txt`) | One ligand per line: `<name> <SMILES>` or just `<SMILES>`. Lines starting with `#` and blank lines are ignored. The notation is checked against **SMILES grammar** (`validation/smiles.py`); this does not establish chemical validity (no chemistry toolkit is wired). A CCD code typed in SMILES mode is refused, never converted to `ccdCodes`. |
| **Standard CCD code file** (`.txt`) | Select CCD mode, then provide one ligand per line as one or more component codes (e.g. `NAG NAG BMA MAN MAN` is one multi-component ligand). Comments and blank lines are ignored. The output uses `ccdCodes`. |
| **Protein / DNA / RNA sequence file** (`.txt`) | Select the intended sequence kind explicitly. Each non-empty line is one record; alphabets are validated by `SequenceText`. No FASTA headers or wrapped records. Outputs use the corresponding `protein`, `dna` or `rna` JSON entity, one record per generated configuration. |
| **Custom CCD definition** | Not a candidate-list format. Add it through the base job's Custom CCD management (`userCCD` / `userCCDPath`); batch output preserves the base definition. |
| MSA file | A3M text: `>` header lines plus alignment rows; lowercase letters are insertions, `-` is a gap. |
| Template file | A readable `.cif` / `.mmcif` file containing a structure: the builder parses it (gemmi when installed, its own lexical scan otherwise) and refuses a file that is not mmCIF. It still never reads the template's own residues, so chains, resolution and bounds are the user's mapping to supply. |
| AF3 JSON input (Open) | **Content decides, not the extension.** `*.json` and `*.txt` both appear in the Open dialog's filter; a file is accepted when it parses as AF3 JSON for a supported version. `inputs/multi_ligand_small_protein_test.txt` is the `.txt` example. |

A **wrapped** FASTA file is not supported: the readers are line based, not
FASTA parsers. A `>` header is refused as an invalid sequence, and wrapped
sequence lines would be separate records. Use one sequence per non-empty line
and explicitly choose Protein, DNA or RNA sequence mode. A `.txt` extension
never chooses the input kind.

---

## 2. Inventory

| File | Purpose |
|---|---|
| `batch/ligands_valid.smiles` | **SMILES-mode input.** Two named ligands plus one bare SMILES: three entries and three configurations. |
| `batch/ligands_ccd_codes.txt` | **CCD-mode input.** Three ligands, including one multi-component code list. |
| `batch/ligands_unchecked_syntax.smiles` | **Deliberately malformed** notation; rejected with line-specific reasons. |
| `batch/ligands_notation_edges.smiles` | Notation-grammar positive control: bracketed atoms/charges, `%10` ring, isotopes, salt, stereocentre. |
| `batch/empty.txt` | Zero bytes — refused as "no entries". |
| `inputs/multi_ligand_small_protein_test.txt` | Base AF3 JSON input (not a batch file): protein, multi-copy ATP, aspirin SMILES and magnesium ion, JSON version 3. |
| `batch/proteins_minimal.txt` | Four minimal one-line protein records `MVT`, `MVS`, `MVY`, `TEST`; end-to-end CLI and GUI coverage. |
| `batch/proteins_valid.txt` | Three longer one-line protein sequences; additional end-to-end coverage. |
| `batch/proteins_wrapped_fasta.txt` | Invalid in sequence mode: FASTA header and wrapping are not accepted. |
| `batch/rna_sequences.txt` | Two RNA records; end-to-end RNA-kind coverage. |
| `batch/dna_sequences.txt` | Two DNA records; end-to-end DNA-kind coverage. |
| `batch/invalid_sequence.txt` | Valid/invalid sequence lines; invalid records reject the entire batch. |
| `msa/protein/unpaired-query.a3m` | Protein A3M whose first row is the query `ACDEFGHIKLMNPQRSTVWY`. |
| `msa/protein/paired-query.a3m` | A second A3M for the paired side of the `both` mode. |
| `msa/rna/query-rna.a3m` | RNA A3M whose first row is the query `ACGUACGU`. |
| `msa/with spaces/rna query.a3m` | The same RNA A3M under a directory **and** file name containing spaces. |
| `templates/minimal_template.cif` | A synthetic two-residue mmCIF (`AG`, with polymer records) for the template path workflow. Not a biological template. |
| `templates/with spaces/template with spaces.cif` | The same file with spaces in both the directory and the file name. |
| `templates/template_fully_resolved.cif` | Fixture A: six-residue polymer `ACDEFG`, coordinates for all six. Query `ACDEFG` → `0:0…5:5`. |
| `templates/template_unresolved_residues.cif` | Fixture B: seven-residue polymer `ACQDEFG`, coordinates only for `DEFG`. Query `DEFG` → `queryIndices [0,1,2,3]`, `templateIndices [3,4,5,6]`. |
| `templates/template_empty.cif` | Fixture C1: zero bytes — **refused** ("the file is empty"). |
| `templates/template_malformed.cif` | Fixture C2: a truncated `_atom_site` loop — **refused** (the loop's values cannot form rows of its three tags). |
| `templates/template_no_records.cif` | Fixture D: a `data_` block with a title and no atom or polymer records — **refused** (nothing for AF3 to read). |
| `templates/README.md` | The fixtures' sequences, resolved residues, expected mappings and why Fixture B maps to 3–6. |
| `batch/` | Batch input fixtures by category — ligand, protein, DNA, RNA, invalid and empty — with the support matrix and expected output names. See its `README.md`. |

`INVENTORY.md` lists the same files with SHA-256 checksums.

The pack is **input only**: the automated tests assert that running every flow
against it leaves the tree unchanged.

---

## 3. RNA MSA — what the builder does, exactly

This is the part of the pack people most often get wrong, so it is spelled out.

### 3.1 Modes

RNA offers exactly **three** modes in both front ends (`configuration_service.set_alignment`
accepts `automatic` / `free` / `provided` for an RNA record):

| Your choice (CLI) | Your choice (GUI) | Stored model value | JSON for `"rna"` |
|---|---|---|---|
| `1 Use the current/default MSA behavior` | Mode **Let AlphaFold search for MSAs automatically** | `SingleAutomatic` | no MSA field at all |
| `3 No MSA - run without alignment data` | Mode **No MSA - proceed without alignment data** | `SingleFree` | `"unpairedMsa": ""` |
| `2 Provide existing MSA file(s)` → `RNA MSA file:` | Mode **Provided (paste or file)** + *Paste inline text* or *Use a file* | `SingleProvided(Inline/External)` | `"unpairedMsa": "<a3m text>"` **or** `"unpairedMsaPath": "<path or asset>"` |

There are **no paired fields for RNA**. `"pairedMsa"` and `"pairedMsaPath"` are
protein-only: the builder never emits them for an RNA chain, and importing a JSON
that carries them on one drops the field and reports an import note
(`sequences[0].rna.pairedMsa`) instead of silently pretending to keep it.

### 3.2 Front-end difference (deliberate)

* **Console:** the `provided` choice collects a **file path only** (`RNA MSA file:`
  prompt). There is no inline paste in the console.
* **Desktop:** the `Provided` mode offers *either* inline text *or* a file, and
  refuses "both" or "neither".

Serialization, validation and output handling are shared, so the difference is
only how the text reaches the service.

### 3.3 Version and file handling

* An external MSA path needs input version **2 or later**; a new job pins 3, so
  it just works. If you pin 1, save is refused with a finding that names the
  required version (it never silently upgrades the job).
* The path may be absolute or relative to the JSON (AF3's rule).
* Under the default output policy **Copy into the output folder**, the file is
  copied to `assets/` next to the JSON and the JSON points at the copy, with the
  name slugged (`rna query.a3m` → `assets/rna-query.a3m`).
* Under **Use the paths exactly as entered** the path is emitted as given (with
  forward slashes), and nothing is copied. *Make paths relative to the output*
  also keeps the given path — it does not rewrite it relative.
* A missing, empty, unreadable or directory path is a **blocking** finding
  (`R-MSA-006`): save, preview and generation refuse and name the record.

### 3.4 Protein vs RNA, side by side

| | Protein | RNA |
|---|---|---|
| Fields | `unpairedMsa`/`unpairedMsaPath` **and** `pairedMsa`/`pairedMsaPath` | `unpairedMsa`/`unpairedMsaPath` only |
| Modes | automatic, free, unpaired, paired, both | automatic, free, provided |
| Paired side | yes (including a separate file) | no — the mode list has no paired/both |
| Templates | yes (`mmcifPath` + index pairs) | no — the template action is protein-only |
| Batch input | Protein, DNA and RNA: one sequence per line, explicit kind selection; CLI and Entities page both generate independent JSON configurations | not applicable — this column describes RNA MSA controls only |

### 3.5 Evidence

AF3's own documentation, vendored in this checkout at
`.freebuff/af3-validator/alphafold3-main/docs/input.md`, states: RNA chains take
`unpairedMsa` *or* `unpairedMsaPath` ("The file must be in the A3M format"), and
the RNA MSA section lists exactly three states (unset/null → automatic, `""` →
MSA-free, non-empty A3M → provided). The builder's three states mirror that list
one-for-one. The runtime also rejects an RNA chain carrying `pairedMsa`
(`folding_input.py` validates the RNA key set).

The two advisory content checks (first row equals the query, rectangular after
removing insertions) are documented for **protein** MSAs in that file; applying
them to RNA as well is this project's conservative choice, reported as a warning
and never blocking.

---

## 4. Walkthroughs

Run everything from the repository root. Use a scratch output folder you can
delete afterwards, e.g.:

```bash
mkdir -p /tmp/af3-manual        # Windows: mkdir C:\Temp\af3-manual
```

`python af3builder.py` starts the console; `python gui.py` starts the window (the
desktop front end needs the optional `.venv-gui` environment — see
[RUNNING_THE_APPLICATION.md](../../RUNNING_THE_APPLICATION.md)).

### Scenario 0 — generate configurations from a ligand file (both front ends)

**Goal:** open an existing AF3 input, select what kind of records the file
contains, then write one independent configuration per entry.

**Files:** `inputs/multi_ligand_small_protein_test.txt` is the base job — four
entity definitions (`A` protein `MKTAYIAKQRQISFVKSHFSRQ`, `B` ATP with **two
copies** (`B`, `F`), `C` aspirin as SMILES, `D` a magnesium ion) at JSON version 3.
`batch/ligands_valid.smiles` is the input: `ethanol CCO`, `acetic-acid CC(=O)O`
and one bare `C1CCCCC1`.

**Console** (`python af3builder.py`):

1. Main menu `2` (Open a JSON file) → the full path to the example. Expect
   `Name: multi-ligand-small-protein`, `Entities: 4`. It is raw AF3 JSON text, so
   the Open action reads it whatever the extension says; the `.txt` name is
   deliberate.
2. Job menu `7` (*Generate configurations from a file*) → `1` (the one
   action), then choose an input kind. For this ligand example choose `4` (SMILES).
3. At the file prompt give the path to `batch/ligands_valid.smiles`.
4. Expect `3 entries read from …`, the entries listed, and the note that each
   is **added** to the base job as a new ligand entity.
5. Give a scratch output folder. Expect three JSON files plus `manifest.json`.
6. Repeat with `1` (Protein sequence) and `batch/proteins_minimal.txt`; expect
   four independent protein configurations plus the manifest.
7. `0` back to the job menu, `0` to leave (the job itself was never changed),
   `0` to exit.

**Window** (`python gui.py`): **Open** the same file → **Entities** → **Generate
configurations from file…** → choose **SMILES**, pick `batch/ligands_valid.smiles`
→ pick an empty folder → review the listed entries and destination → **Generate**
→ the result box lists the files that were written. Repeat with **Protein
sequences** and `batch/proteins_minimal.txt` to produce four protein outputs.

**Expected layout** for an output folder `…/out`:

```
out/multi-ligand-small-protein/multi-ligand-small-protein__ethanol/multi-ligand-small-protein__ethanol.json
out/multi-ligand-small-protein/multi-ligand-small-protein__acetic-acid/multi-ligand-small-protein__acetic-acid.json
out/multi-ligand-small-protein/multi-ligand-small-protein__ligand-1/multi-ligand-small-protein__ligand-1.json
out/multi-ligand-small-protein/manifest.json
```

**Check it without AF3:** in each file the four base definitions are still
there (`A` protein, `B`/`F` ATP, `C` aspirin, `D` magnesium) and exactly **one**
new ligand entry carries `"smiles"`: `CCO`, `CC(=O)O` or `C1CCCCC1`. The files
never share a batch entry: the `ethanol` file does not contain acetic acid. The
opened input file is byte-for-byte unchanged.

**What this proves, and what it does not:** reading, per-entry independence,
validation, identifiers, JSON shape and file writing. The emitted documents are
also checked against AF3's official input parser by the separate validation
corpus (see `tools/af3_validation/README.md` and
`docs/TEMPLATE_AND_ENTITY_BATCH_END_TO_END_TEST_REPORT.md` §14). That is not an
AF3 inference run, and acceptance of a SMILES string as input syntax is not proof
of chemical validity or useful predictions.

**Names become file names.** `ethanol CCO` produces `…__ethanol.json`;
a bare SMILES has no name, so it gets a positional one (`…__ligand-1.json`).
Names are slugged (a name that cannot be slugged falls back to its position), and
two entries with the same name take `-2`, `-3` in file order. The name is **not**
written into the AF3 JSON — the schema has no field for it.

### Scenario 1 — the same file twice, and existing outputs

Run Scenario 0 twice into the same folder. The second run succeeds and reports
the same files as written (identical content is not a conflict). Now edit one of
those files by hand, or create one at the expected path with different bytes, and
run again: the run is **refused** with `already exists with different content`,
nothing is written — not even the entries that would have been new — and the
existing bytes are untouched. The fix is a different (or empty) output folder;
the builder never overwrites silently and never invents `-1` suffixes unless the
project's overwrite policy is explicitly *Write a numbered copy* on the Generate
page.

### Scenario 2 — CCD codes and custom CCD definitions

Choose **CCD code** as the input type to read a component-code file. A line such
as `ATP` becomes a ligand with `ccdCodes: ["ATP"]`; multiple component codes on
one line are one multi-component ligand. The same `ATP` text in SMILES mode is
**refused**, not reinterpreted. A custom CCD definition is different: it is
job-wide data, not a list of candidate ligands. Add it through **Custom CCDs**
(`userCCD` / `userCCDPath`); each output preserves that base definition. Ions
can likewise be added through CCD mode, either in the batch input or in the base
job.

`batch/ligands_unchecked_syntax.smiles` shows where the checks stop: broken
notation is refused with the defect named (a ring closure opened and never
closed; a line containing spaces), while a *grammatical* notation that no
chemist would accept is written, because valence and perception belong to
AF3's own parser (RDKit) and this builder does not depend on one.

### Scenario 3 — protein MSA, each user-provided mode

Console, for a protein whose sequence is `ACDEFGHIKLMNPQRSTVWY`
(the query in the pack's A3M files):

1. Job menu `2` → `1` Protein → sequence.
2. MSA choice `2` (*Provide existing MSA file(s)*). The console explains that
   paired and unpaired are separate files.
3. `Paired MSA file (blank = empty paired side):` → press Enter.
4. `Unpaired MSA file (blank = empty unpaired side):` →
   `manual_test_data/af3_builder/msa/protein/unpaired-query.a3m`.
5. Answer `n` to templates, then save with job menu `6`.

JSON: `"unpairedMsaPath": "<the path or assets/…>"` **and** `"pairedMsa": ""`;
no `unpairedMsa`, no `pairedMsaPath`.

Repeat with both questions answered (`paired-query.a3m` then
`unpaired-query.a3m`) to get the `both` state
(`unpairedMsaPath` + `pairedMsaPath`), and with MSA choice `3` for the
explicit-empty state (`unpairedMsa: ""`, `pairedMsa: ""`).

Window: Entities → select the protein → *Settings for this entity* →
**Change alignment…** → **Mode** `Unpaired only` / `Paired only` / `Both` /
`Let AlphaFold search for MSAs automatically` / `No MSA - proceed without alignment data`,
then *Use a file* + **Choose file…**. **Apply changes**.

### Scenario 4 — RNA MSA, each supported mode (compare with Scenario 3)

Console:

1. Job menu `2` → `3` RNA → `ACGUACGU`.
2. MSA choice `2`. The console now says: *RNA uses a single MSA file in A3M
   format; it has no paired side.*
3. `RNA MSA file:` → `manual_test_data/af3_builder/msa/with spaces/rna query.a3m`
   (type the path; the spaces are fine).
4. Answer nothing else (RNA has no template question), save with job menu `6`.

JSON for the chain:

```json
{ "rna": { "id": "A", "sequence": "ACGUACGU",
           "unpairedMsaPath": "assets/rna-query.a3m" } }
```

and `assets/rna-query.a3m` next to the saved JSON (default policy).

Also try MSA choice `1` (no MSA fields at all) and `3`
(`"unpairedMsa": ""`).

Window: Entities → **Add RNA** → select it → **Change alignment…** →

* Mode `Provided (paste or file)` + *Paste inline text* → paste the contents of
  `msa/rna/query-rna.a3m` → **Apply changes** → `"unpairedMsa": ">query\nACGUACGU\n…"`.
* Mode `Provided (paste or file)` + *Use a file* → the path with spaces →
  `"unpairedMsaPath": …`.
* Note what the dialog *does not* offer: no paired/both mode, and
  **Edit templates…** is absent (says templates are protein-only).

### Scenario 5 — protein template with mmCIF path

Console, protein whose sequence is `ACDEFGHIKLMNPQRSTVWY`:

1. Job menu `2` → `1` Protein → sequence → MSA `1` → templates `y`.
2. Templates menu `3` (*Provide template mmCIF files and residue index pairs*).
3. Template file → `manual_test_data/af3_builder/templates/with spaces/template with spaces.cif`.
   The builder only checks that it exists, is a regular `.cif` file and is not empty.
4. `query:template` pairs → `0:0,1:1` (0-based; query indices must address the
   target sequence).
5. `y` to another template, or `n` to finish. Save with `6`.

JSON: `"templates": [{"mmcifPath": "assets/template-with-spaces.cif",
"queryIndices": [0,1], "templateIndices": [0,1]}]` and the copied file under
`assets/`.

Window: select the protein → **Edit templates…** → route *Provide template
mmCIF files and residue index pairs* → **Add file…** → fill the pairs cell →
**Apply changes**.

**Caveat:** the mmCIF is synthetic. The builder checked the path only; whether
AF3 can parse this structure is unverified.

### Scenario 6 — output generation and asset copying

Both front ends: create the job with an external MSA (and/or template), then:

* **Console:** job menu `6` writes the JSON (and copies assets next to it under
  the default policy). That is the console's route to a file; the ligand batch is
  its only multi-file action.
* **Window:** **Generate** page → step 1 says exactly what is written, the open
  job's own AF3 JSON → *2. Where should the files go?* → **Choose folder...** →
  under **Advanced options** set *External files (MSA, templates)* to `Copy into
  the output folder` → **Preview plan** (shows the JSON, the assets to copy,
  warnings) → **Generate files**.

Expected layout for a base-only run into `/tmp/af3-manual`:

```
/tmp/af3-manual/<job-slug>/<job-slug>.json
/tmp/af3-manual/<job-slug>/assets/rna-query.a3m        # default policy
```

With *Use the paths exactly as entered* the JSON keeps your path, no `assets/`
folder appears, and a drive-letter/UNC path adds a portability warning.

### Scenario 7 — invalid and missing paths

1. Configure an RNA `provided` MSA with a path that does not exist. The console
   re-asks immediately (`The MSA file … cannot be used: …`); it never commits a
   broken alignment. If a job already carries such a path (e.g. the file was
   deleted afterwards), **save is refused** with
   `R-MSA-006` and nothing is written.
2. Do the same for a template: `The template file … cannot be used: the file does
   not exist.` — refused while configuring, so it cannot reach the JSON.
3. Batch: give `batch/empty.txt` (zero bytes) or a file of only comments —
   refused as "no entries" before a folder is even asked for. A duplicate
   molecule (`one CCO` twice) is refused with the repeated value named. Neither
   writes anything.

To reproduce the "deleted afterwards" case: configure the MSA with a real file,
save the project, delete the `.a3m`, then press Save again.

---

## 5. Checking a saved JSON without AF3

Open the file and look only at the keys below (or run the snippet). `.cbproj`
project files are not the AF3 input; the builder writes the AF3 JSON with **Save**
(or the Generate page).

```bash
python - <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
for entry in doc["sequences"]:
    (family, body), = entry.items()
    msa = {k: v for k, v in body.items() if "Msa" in k}
    print(family, body["id"], msa or "(no MSA fields)")
PY
```

What to look for:

| Scenario | Expected |
|---|---|
| RNA automatic | no `unpairedMsa` / `unpairedMsaPath` for the `rna` entry |
| RNA no-MSA | `"unpairedMsa": ""` |
| RNA provided file | `"unpairedMsaPath"` only; never `pairedMsa*` |
| RNA provided inline | `"unpairedMsa"` only |
| Protein unpaired | `unpairedMsaPath` + `"pairedMsa": ""` |
| Protein both | `unpairedMsaPath` + `pairedMsaPath` |
| Template | `templates[0].mmcifPath` + `queryIndices` / `templateIndices` |
| Any copied asset | path starts with `assets/` and the file exists next to the JSON |

---

## 6. Cleanup

Delete only the scratch folder you created (`/tmp/af3-manual`, `C:\Temp\af3-manual`).
The pack itself is never modified; if a walkthrough ever changes it, that is a bug —
the automated tests assert it stays byte-identical.

---

## 7. Limitations

* No AF3 verification of any kind. Runtime parsing, MSA search, template parsing
  and model quality are all out of scope.
* The `provided` RNA inline path is builder-verified only; whether AF3 accepts a
  particular A3M text is a runtime question (it re-parses the A3M later in its
  data pipeline).
* The advisory A3M checks (query first, rectangular) are protein-documented;
  applying them to RNA is a project choice.
* SMILES notation **is** checked for grammar, chemistry is **not**
  (`validation/smiles.py`: characters, balanced brackets, paired ring closures,
  unbracketed atoms from the organic subset). Whether a grammatical notation
  describes a real molecule — valence, aromaticity, perception — belongs to
  AF3's own RDKit parser, which this builder does not depend on.
  `batch/ligands_unchecked_syntax.smiles` and `batch/ligands_ccd_lookalike.smiles`
  are the refusal fixtures; `batch/ligands_notation_edges.smiles` is the
  positive control.
* A batch file cannot express CCD codes, custom CCDs or ions; those belong to
  the base job or the **Add Ligand** dialog (see Scenario 2).
* Protein, DNA and RNA batch processing is available through the explicit
  input-kind selection in both front ends and uses the shared batch service.
  The current support matrix and end-to-end tests are in
  `batch/README.md`; FASTA is not supported, and a `.txt` extension never picks
  an entity type by itself.
* The template mmCIFs are synthetic. The builder refuses a file that is not a
  readable mmCIF structure (its own lexical scan, plus gemmi when the
  `templates` extra is installed), but it still never reads the template's own
  residues: only path handling, structural validity and the serialized mapping
  are verified. `templates/README.md` states exactly what is and is not checked.

The full audit — including exact JSON fields, source citations and the test
results behind every claim above — is
`docs/AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md`.
