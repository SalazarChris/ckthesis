# AF3 Configuration Builder — Practical Audit of File-Based Configuration Generation

**Scope:** the workflow that takes one open base job plus one input file and writes
one AF3 JSON configuration per input entry.

**Date:** 2026-10-29
**Branch / HEAD audited:** `main` @ `d4cd17d`
**Method:** source inspection traced from the two real entry points, plus execution of
the real CLI against the shipped fixtures in a throwaway temporary directory, plus
the existing automated suites (run, not merely read). No source, test, fixture, menu
or behaviour was modified by this audit; the only file added is this report.

Evidence labels used throughout: `VERIFIED` (executed and observed),
`SOURCE-CONFIRMED` (established from source only), `NOT SUPPORTED` (absent),
`BLOCKED` (could not be executed here). Claims are never upgraded from one class to
another.

---

## 1. Executive summary

The feature is one action with two front ends over a single service path, and it
works today. Five input kinds are offered — protein, DNA and RNA sequences, ligands
by SMILES, ligands by CCD code — and every one of them was driven through the real
console against the shipped fixtures, with the resulting JSON inspected on disk and
re-read by the builder's own importer.

**What the user must supply:** an open base job (a new job or an opened AF3 JSON), an
input file, an explicit statement of what that file contains, and an output folder.
Nothing else. Templates, MSA data, custom CCD, seeds, version and every other base
setting are inherited from the base job; the input file cannot carry them.

**What the application does:** reads the file through a kind-specific reader, builds
one independent `base + AddRecord(...)` specification per entry against a throwaway
clone of the base identity registry, validates the base and every generated variant
through the full rule catalogue, plans every write, and only then writes. The base
job is not modified, and no entry leaks into another entry's file.

**What comes out:** one directory per entry named after the base job and the entry's
key, containing `<job>__<key>.json` (whose internal `name` field matches the file
name), any external assets that entry references (copied into `assets/`), and one
`manifest.json` per run at the project level. A four-entry protein file therefore
produces **five files**: four configurations plus the manifest.

**Headline findings, in order of practical importance:**

1. `VERIFIED` — malformed, empty, duplicate and wrong-kind inputs refuse the whole
   run with the offending line numbers and write nothing. The refusal text is
   actionable, including a "these look like protein sequences / CCD codes" hint when
   sequence-like or code-like text is supplied in SMILES mode.
2. `VERIFIED` — existing-file collisions are all-or-nothing: a run that would
   replace a file with *different* content writes nothing at all, and a run whose
   bytes are identical re-reports those files as written without harm.
3. `VERIFIED` — DNA is the one input where one line does not mean one new entity:
   one DNA line becomes the input strand **plus its reverse-complement strand**, so
   two DNA lines produce four new entities across two files.
4. `VERIFIED` — a base job whose template or MSA is referenced **by path** is
   preserved into every output, with the referenced file copied into that variant's
   `assets/` folder and the path rewritten relative. `queryIndices`/`templateIndices`
   are carried through unchanged (they are 0-based).
5. `VERIFIED` — a base job that references a template or MSA path which no longer
   exists refuses the entire run before writing a byte, naming the missing file.
6. `VERIFIED (defect)` — a base JSON that carries an **inline** `templates[].mmcif`
   cannot be opened by this application at all
   (`sequences[0].protein template 0 has no mmcifPath`), even though the builder's
   own serializer produces exactly that shape for inline references. Not reachable
   from either GUI or CLI, which only attach templates by file path — but it means
   the builder cannot re-open some of its own output.
7. `SOURCE-CONFIRMED` — the batch action offers no overwrite/path policy choice,
   while the Generate page offers four overwrite policies and two path policies for
   the base export. The same job therefore has two different answers to "what happens
   to a file that already exists", depending on which screen you are on.

**Answering the eight definition-of-done questions directly:**

| Question | Short answer | Section |
|---|---|---|
| What files do I need? | Base job JSON (or a new job) + one list file. Nothing else is required. | §5 |
| What must each file contain? | Base: any AF3 input this builder can import. List: one record per line in the syntax of the chosen kind. | §6 |
| Which files do I select? | The base once (Open), then the list file in the batch action. | §3, §4 |
| What will the application do with them? | Parse → build one `base + entity` spec per entry → validate → plan → write atomically. | §8 |
| What outputs? | `<out>/<job>/<job>__<key>/<job>__<key>.json` per entry, per-variant `assets/`, one `<out>/<job>/manifest.json`. | §7, §8 |
| Which sources must remain available? | Nothing, once the run has completed — external MSA/template files are copied into the output. They must exist **during** the run. | §7 |
| How do I know the JSON is correct? | Structural: re-open each file in the builder, or run AF3's own parser over the folder. Neither proves the structure is biologically right. | §14 E |
| What can go wrong? | Wrong input kind, FASTA, duplicate entries, invalid residues, colliding output files, missing template/MSA path, output folder that is a file. | §10 |

---

## 2. Current workflow at a glance

The real flow, not an illustration. Both front ends take the same route after the
first two steps.

```
Base job open?  ── no ──▶  nothing to add to (both front ends require a job; the
        │                  Entities action reports "no project is open")
        │ yes
        ▼
Ask: what does the file contain?         ← the only thing that decides the reader
   1 protein   2 DNA   3 RNA   4 SMILES ligands   5 CCD-code ligands
        │
        ▼
Choose the input file                    ← console: numbered directory picker or typed path
        │                                   window: native Open dialog, kind-specific filter
        ▼
Read through the kind's reader           ← persistence/sequences.py
   (blank lines skipped; '#' comment only for SMILES/CCD; no FASTA, no wrapping)
        │
        ▼
Build one spec per entry                 ← batch_variants.specs_for_entries
   base + AddRecord(record of the chosen kind), ids from a throwaway
   clone of the base registry  (DNA: one line → two records)
        │
        ├── any entry unusable? ──▶ REFUSE the whole file, name every line  ──▶ stop
        ▼
Preview what was read                    ← console: "N entries read from <file>" + each entry
   (window asks for the folder first, then reviews)
        │
        ▼
Choose the output folder                 ← console default: <cwd>/generated_configurations
        │
        ▼
Plan                                     ← GenerationService.plan_input_batch
   1. gate the base job (blocking findings stop everything)
   2. expand: apply each spec to the same base  (independence is structural)
   3. validate base + every variant (full catalogue)
   4. transform each → wire document, job name = <job>__<key>
   5. resolve external resources under the path policy (CopyIntoAssets)
   6. decide each file's action under the overwrite policy (Fail)
        │
        ├── conflicts / missing resource / blocked base ──▶ nothing written ──▶ report
        ▼
Write (atomic per file)                  ← output/execute.py
   <out>/<job>/<job>__<key>/<job>__<key>.json
   <out>/<job>/<job>__<key>/assets/<copied resource>
   <out>/<job>/manifest.json
        │
        ▼
Report what was actually written         ← console prints one "Wrote <path>" per file
                                            window lists the same paths in a result box
```

Two deliberate asymmetries are visible in that diagram and are confirmed in the code:

- the **window** picks the destination folder *before* the review box, while the
  **console** prints the preview *before* asking for the folder;
- the window offers a review/confirm step the console does not, and the console
  offers a directory listing the window replaces with the native picker.

---

## 3. CLI workflow

Entry point: `python af3builder.py` → `configbuilder.app.cli.main` →
`ui.render.menus.MenuApp.run` (`configbuilder/ui/render/menus.py:498`).

### 3.1 Opening a base job

| Step | Screen | Input | Code |
|---|---|---|---|
| 1 | `JSON CONFIGURATION BUILDER` — `1. New job` / `2. Open a JSON file` / `0. Exit` | `2` | `_main_menu` (`menus.py:519`) |
| 2 | `AF3 JSON file to open:` preceded by a numbered listing of the current directory | the number of the file, or a full path, or `..`, or `0` to cancel | `_open_json_file` (`menus.py:551`) → `projects.import_json_commit` |
| 3 | Job loaded; `JOB MENU` is shown | — | `_job_menu` (`menus.py:584`) |

`1. New job` instead asks `Job name (blank generates one):` and starts an empty job
(`_new_job`, `menus.py:539`). An empty job has zero entities and is a legitimate base:
the batch then produces files containing exactly one entity each.

### 3.2 The generation menu path

| Step | Screen text | Input |
|---|---|---|
| 4 | `JOB MENU` — `1. Edit job configurations` … `7. Generate configurations from a file (sequences or ligands)` | `7` (`menus.py:616`) |
| 5 | `CONFIGURATION GENERATION FROM A FILE` — shows `Base job: <name>` and `Base entities: <n>`, action `1. Load an input file and generate configurations`, `0. Back` | `1` (`_file_menu`, `menus.py:1601`) |
| 6 | `What does the file contain?` — five numbered kinds (below) | `1`–`5` (`_generate_from_file`, `menus.py:1637`) |
| 7 | Directory listing + `<prompt>: ` — the prompt is kind-specific | number / full path / `..` / `0` (`_pick_path`, `menus.py:412`) |
| 8 | `N entries read from <path>:` then each entry, then a note naming the kind and saying the base is not modified and existing files are never replaced | — |
| 9 | `Output folder for the configurations [<cwd>/generated_configurations]: ` | a path, or blank to accept the default (`_ask_destination`, `menus.py:455`) |
| 10 | `Generating configurations...` then one `Wrote <path>` per file, then `Wrote N file(s) under <root>` | — |

The five kinds and their exact prompts (`MenuApp.FILE_KINDS` at `menus.py:1582`,
`_FILE_PROMPTS` at `menus.py:1593`, wording from `ui/present/strings.py:334-369`):

```
1. Protein sequences, one per line      → "Sequence file (.txt, one sequence per line): "
2. DNA sequences, one per line          → "Sequence file (.txt, one sequence per line): "
3. RNA sequences, one per line          → "Sequence file (.txt, one sequence per line): "
4. Ligands by SMILES, one per line, with an optional name first
                                        → "Ligand file (.smiles or .txt): "
5. Ligands by CCD code, one ligand per line (several codes make one multi-component ligand)
                                        → "CCD code file (.txt, one ligand per line): "
```

Observed behaviour beyond the happy path (`VERIFIED`):

- the kind question comes first and is the only thing that decides the reader;
- an unreadable file, an empty file, a duplicate entry or any invalid line refuses
  the run **before** the folder is asked for;
- after writing, the file menu is redrawn (so a second file can be processed without
  re-opening anything); `0` returns to the job menu, `0` again to the main menu;
- the base job is never saved, marked dirty or altered by this workflow.

### 3.3 The one caveat in the console

`_pick_path` builds its own listing from `os.getcwd()`, not from the input file's
folder, and it accepts a literal path. The listing therefore always starts at the
directory the builder was launched from, which is why typing the full path was the
reliable route during this audit. `SOURCE-CONFIRMED` (`menus.py:412-452`).

---

## 4. GUI workflow

Entry point: `python gui.py` → `configbuilder.ui.render.qt.application.main`
(the launcher re-executes `.venv`'s interpreter; see `DEPENDENCY_SETUP.md`).

| Step | Where | Control | Code |
|---|---|---|---|
| 1 | `File → Open` or the empty-window prompt | native Open dialog; the job loads into the same project service as the console | `main_window` / `state.import_json` |
| 2 | **Entities** page | button **`Generate configurations from file...`**, in the row under the four Add buttons, next to the note "One file in, one configuration per entry out; existing files are never replaced." | `pages/entities.py:268-274`, text `strings.py:463-472` |
| 3 | modal **Input type** box | five buttons, one per kind, plus Cancel (Cancel is the default button) | `dialogs/batch_input.py:choose_batch_kind` |
| 4 | native Open dialog | filter by kind: sequences `*.txt`, ligands `*.smiles *.txt` | `choose_batch_file` |
| 5 | native folder dialog | `Choose the output folder` | `choose_output_folder` |
| 6 | modal **Review the input file** box | `N entries read:`, `Input type: …`, up to 12 entries (`…and N more`), `Output folder: …`, file count, a note that the base is not modified; **Generate** / Cancel (Cancel is the default) | `confirm_batch_preview` |
| 7 | modal **Generated configurations** box | `N file(s) written:` + each path, or the service's own refusal incl. `- finding` lines, or `Nothing was written.` | `report_batch_run` |
| 8 | status note on the page | `Wrote N file(s) for the input file.` when the outcome is ok | `entities.py:379` |

The page method is `EntitiesPage.generate_from_file` (`pages/entities.py:353-381`); it
calls `state.inspect_input_file` (`qt/state.py:312`) for the preview and
`state.generate_input_configurations` (`qt/state.py:322`) for the write, which passes
the project's own policies explicitly — the same service calls the console makes.

Differences from the console, all confirmed:

| Aspect | Console | Window |
|---|---|---|
| Order of the destination question | after the preview | **before** the review box |
| File choice | numbered listing + typed path | native dialog with a kind filter |
| Confirmation before writing | none (the preview is the last look) | review box with Cancel as default |
| Failure text | `Nothing was written: <reason>` plus numbered conflicts/findings | same content inside a message box |
| Entry listing | every entry | first 12, then a remainder count |

`VERIFIED (automated, offscreen)` — the window path is covered by
`tests/gui/test_file_generation.py`, three of whose cases click the **real** button
and drive the **packaged** input-type, review and native file/folder dialogs with no
seams stubbed. **No human-operated GUI session was performed for this audit**; that
limitation is carried in §12.

The GUI also has a separate **Generate** page (`pages/generate.py`) that writes the
open job's *own* file. It is a different action with a different destination, but it
is the nearest thing on screen to the batch action and the two are worth
distinguishing when reading user reports.

---

## 5. What the user must provide

| Input or choice | Required? | Accepted values / format | Default | Where used |
|---|---|---|---|---|
| Base job | **Required** | A job opened from any AF3 JSON this builder can import, or a new empty job | none — both front ends refuse with "no project is open" | the configuration every output starts from |
| Input file | **Required** | text file; syntax depends on the kind (§6) | — | one record per entry |
| Input kind | **Required** | exactly five: protein / DNA / RNA sequence, SMILES ligand, CCD-code ligand | — (asked every time; never guessed) | selects reader **and** record builder |
| Output folder | **Required** | any path; created recursively if absent; may not be a file | console: `<cwd>/generated_configurations`; window: previous folder | destination root of all writes |
| Output naming | **Not user-supplied** | derived: `<slug(job)>__<key>` for the directory, file and internal `name` | automatic | filenames and AF3 `name` field |
| Model seeds | **Inherited** | whatever the base carries | base job | every output unchanged |
| Input version (v1–v4) | **Inherited** | base job | base job | every output unchanged |
| Custom CCD (`userCCD` / `userCCDPath`) | **Inherited, job-wide** | base job only; **no batch kind exists** | base job | every output unchanged |
| MSA (inline or `*Path`) | **Inherited, per base entity** | base job only; **not expressible per entry** | base job | preserved and, for paths, copied into each variant's `assets/` |
| Structural templates | **Inherited, per base protein** | base job only; **not expressible per entry** | base job | preserved; path-referenced mmCIFs copied per variant |
| Overwrite policy | **Not offered** | fixed to the project's setting (`Fail` for new/imported jobs) | `Fail` | whether an existing file stops the run |
| Path policy | **Not offered** | fixed to the project's setting (`CopyIntoAssets`) | `CopyIntoAssets` | whether external files are copied or referenced |
| Ligand name | Optional | first whitespace-delimited token of a SMILES line | `ligand_N` positional | output file name + manifest label (never in the JSON) |

**What happens if a required item is omitted:** no base job → both front ends report
that no project is open and nothing runs; no file → cancelled, nothing happens; no
kind → the question is re-asked (console) or Cancel aborts (window); no folder →
cancelled, nothing written; a blank console answer accepts the default folder.

**Is the application asking for too much?** No. It asks for exactly two pieces of
information the user must decide (which file, and what it holds) plus a destination.
Everything else is read from the base job. One could argue the kind question is
redundant for `.smiles` files, and it is — see §13 R3.

**Values required by AF3 that this workflow does not check:** CCD registry membership
of a code, chemical validity of a SMILES string (grammar only), whether template
indices describe a real correspondence, whether an MSA actually matches the sequence,
and whether the sequences are biologically sensible. All are the inference stage's or
the user's business (`SOURCE-CONFIRMED`, consistent with `manual_test_data/af3_builder/batch/README.md` §1).

---

## 6. Supported input types and exact file syntax

All readers live in `configbuilder/persistence/sequences.py`; builders and the single
kind→builder table in `configbuilder/app/batch_variants.py:96-190`.

### 6.1 Protein / DNA / RNA sequences

```
MVT
MVS
MVY
TEST
```

- one record per non-empty line; surrounding whitespace stripped; CRLF and LF both fine
  (`payload.splitlines()`);
- **no** comment syntax: a `#` line is an invalid sequence, reported with its line number;
- **no FASTA**: a `>header` line is an invalid sequence, and a *wrapped* record is read as
  several separate entries, so FASTA is not merely unsupported, it is actively unsafe
  to supply;
- alphabet check is the model's own (`SequenceText`, `configbuilder/model/values.py:42-44`):
  protein accepts **every uppercase letter A–Z** (not just the 20 standard residues),
  DNA accepts `ACGT` and RNA `ACGU`. Lowercase, digits, `-`, `*`, `>` and whitespace
  inside a line are refused. Because the protein alphabet is all capitals, `ATP`, `ZN`
  and `TEST` are all valid protein sequences — which is exactly why the input kind
  cannot be inferred from the text and must be chosen;
- duplicates (case-insensitive after strip/upper) refuse the file;
- DNA is constructed by the same application service the single-entity Add DNA form
  uses, so **one line = a duplex pair** (see §8.3);
- RNA is `FamilyBRecord` — the same record the RNA form builds.

### 6.2 SMILES ligands

```
# optional comment
ethanol CCO
acetic-acid CC(=O)O
c1ccccc1
```

- `name SMILES` (first whitespace splits) or a bare `SMILES`;
- blank lines and lines starting with `#` skipped; `#` inside a SMILES is not a comment;
- naming: the name is slugged and becomes the directory/file/key; a bare line gets
  `ligand_N` where N counts bare lines, so the third entry above is `ligand-1`;
- duplicate SMILES → refused (whole file); duplicate **names** → both survive as
  `x`, `x-2`, `x-3` in file order;
- notation is checked by `validation/smiles.py:notation_problem` — SMILES character
  set, balanced brackets, paired ring closures, unbracketed atoms from the organic
  subset. Chemistry (valence, aromaticity, perception) is **not** checked and is not
  claimed: RDKit is AF3's dependency, not this builder's.

### 6.3 CCD-code ligands

```
# one ligand per line; several codes on a line are ONE multi-component ligand
ATP
ZN
NAG NAG BMA MAN MAN
```

- tokens split on whitespace, comma or semicolon by `model.split_component_codes`;
- emits `"ccdCodes": [...]` and never `smiles` (the builder is `_code_record` →
  `ByCode`, `batch_variants.py:161-171`);
- code *shape* is checked; CCD registry membership is not looked up (no bundled CCD
  dictionary);
- the key is the codes joined with `-` (`…__nag-nag-bma-man-man`);
- duplicates of the same code list are refused.

### 6.4 Not input-file formats

Templates, MSA, PTMs, covalent bonds and custom CCD definitions **cannot** be supplied
per entry. They belong to the base job and are preserved into every output. There is no
sixth kind, and both front ends build their list from `INPUT_KINDS`, compared against
it by test, so no kind can be advertised that no service builds.

### 6.5 Required input-support matrix

| Category | Accepted syntax | Parser support | CLI accessible | GUI accessible | Output representation | Limitations |
|---|---|---|---|---|---|---|
| SMILES | `name SMILES` or bare `SMILES`; `#` comments; blanks ignored | `SUPPORTED` (`read_smiles_file` + `notation_problem`) | `SUPPORTED` — `VERIFIED` | `SUPPORTED` — `VERIFIED` (automated) | `"ligand": {"smiles": …}` | grammar only, not chemistry; BB `#`-only at line start; a name cannot contain a space |
| Standard CCD | one ligand per line of component code(s) | `SUPPORTED` (`read_code_file` + `ComponentCode`) | `SUPPORTED` — `VERIFIED` | `SUPPORTED` — `VERIFIED` | `"ligand": {"ccdCodes": [...]}` | no CCD registry lookup; codes are not validated against a dictionary |
| Custom CCD | **not a batch format** | `NOT SUPPORTED` | `NOT EXPOSED` | `NOT EXPOSED` | inherited `userCCD` / `userCCDPath` on the base | job-wide only; mutual exclusion enforced by the model, not by this workflow |
| Protein sequence | one per line, no comments, no FASTA | `SUPPORTED` | `SUPPORTED` — `VERIFIED` | `SUPPORTED` — `VERIFIED` | `"protein": {"id","sequence"}` | short fixtures are parser tests, not biology; no header/name line |
| DNA sequence | one per line | `SUPPORTED` | `SUPPORTED` — `VERIFIED` | `SUPPORTED` — `VERIFIED` | `"dna": {...}` **plus reverse complement** | one line produces two entities — surprising, see §11 |
| RNA sequence | one per line | `SUPPORTED` | `SUPPORTED` — `VERIFIED` | `SUPPORTED` — `VERIFIED` | `"rna": {"id","sequence"}` | no MSA/template per entry |
| Structural templates | **not a batch format** | `NOT SUPPORTED` as input | `N/A` | `N/A` | inherited `templates[]` on base proteins | inline-template documents cannot be re-imported (§12 D1) |
| MSA / other auxiliary files | **not a batch format** | `NOT SUPPORTED` as input | `N/A` | `N/A` | inherited `unpairedMsa`/`pairedMsa`/`*Path` | missing path refuses the whole run |
| FASTA | `>` headers / wrapped records | `NOT SUPPORTED` (and unsafe: wraps become entries) | refused — `VERIFIED` | refused (same service) | — | fixture `proteins_wrapped_fasta.txt` exists to pin the refusal |
| CCD codes chosen as **SMILES** | `atp ATP` | refused by the notation check | refused, line + hint — `VERIFIED` | refused (same service) | — | never silently converted |
| Sequences chosen as **SMILES** | one per line | refused + actionable hint | refused — `VERIFIED` | refused — `VERIFIED` | — | advice only; nothing is reinterpreted |

`tests/e2e/test_entity_batch_cli_subprocess.py` (`test_the_kind_menu_offers_exactly_the_supported_input_types`,
`test_notation_the_check_must_keep_is_generated_entry_by_entry`) and
`tests/gui/test_file_generation.py` pin the two kind lists against `INPUT_KINDS`.

---

## 7. Complete file-processing inventory

### 7.1 User-provided files

| File | Role | Selected by | Format | Read by | Parsed / transformed? | Modified? | In the output? | Needed after generation? |
|---|---|---|---|---|---|---|---|---|
| Base job JSON | the configuration every output starts from | user, via Open (console main menu `2`, window Open) | AF3 input JSON this builder can import | `ProjectService.import_json_commit` → `transform.from_wire` | parsed into the immutable model | **no** (verified by md5 before/after) | **copied field-by-field** into every output, plus one new entity | no |
| Sequence list (`.txt`) | candidate protein/DNA/RNA records | user, after choosing the kind | one sequence per line | `persistence.read_sequence_file` (`sequences.py:115`) | yes → `SequenceText` | no | only the chosen record's text, as entity data | no |
| SMILES list (`.smiles`/`.txt`) | candidate ligands | user | `name SMILES` / bare SMILES | `persistence.read_smiles_file` (`sequences.py:168`) | yes → `ByNotation` | no | the SMILES string; the name is only in the file name | no |
| CCD code list (`.txt`) | candidate ligands by component code | user | one ligand per line | `persistence.read_code_file` (`sequences.py:96`) | yes → `ByCode` | no | `ccdCodes` array | no |
| Template mmCIF | base protein's structural template | user, earlier — through the entity's Templates form (window: Advanced → Templates → *Edit templates…*; console: the templates menu during Add/Edit entity) | `.cif` / `.mmcif` parsed by gemmi or the bundled lexical scan | `persistence.mmcif.template_structure_problem` at attach time; then read again by the writer | validated, then **copied** | no | **`assets/<name>.cif` in every variant folder** + relative `mmcifPath` | **no** — the copy travels with the output |
| MSA `.a3m` (external) | base entity's alignment | user, earlier — via the alignment form | a3m text | `transform` resolves the requirement; writer copies it | copied | no | `assets/<name>.a3m` + relative `unpairedMsaPath` | **no** — the copy travels with the output |
| Inline MSA / inline userCCD | base entity data | embedded in the base JSON | text | importer | carried verbatim | no | the same text inline | no |

### 7.2 Files read internally by the run

| Resource | Why the run reads it | Code |
|---|---|---|
| `pyproject.toml` (indirect) | not read during generation; only the *checker* reads it | `tools/check_dependencies.py` |
| the base project's own in-memory model | source of every preserved field | `app/project_service.py` |
| validation rule catalogue | base gate + per-variant validation | `validation/catalogue.py`, `app/validation_service.py` |
| template/MSA source files named by the base | copied into each variant; a missing one aborts the run | `output/plan.py:resolve_resources_into`, `output/execute.py` |
| CCD/CIF fixtures | **never** read by this workflow — no CCD dictionary exists | — |

There is no database, no network access and no environment variable in this path.

### 7.3 Generated files

| Artifact | Written by | Purpose | Required for AF3? | Notes |
|---|---|---|---|---|
| `<out>/<job>/<job>__<key>/<job>__<key>.json` | `output/execute.py:execute` | one AF3 configuration | **yes** | atomic write (temp + `os.replace`), UTF-8, 2-space JSON |
| `<out>/<job>/<job>__<key>/assets/<file>` | same | external MSA / template the configuration points at | **yes**, if the document references it | byte copy, atomic; may be more than one file |
| `<out>/<job>/manifest.json` | same | project-side report of the run | **no** — never read by AF3 | one per run, not per variant; byte-deterministic for the same base and inputs (see below) |
| `.<name>.tmp` | `_atomic_write` | transient | no | removed on failure; a crash can leave one behind |
| `generated_configurations/` (default folder) | created on demand | default destination | no | `<cwd>/generated_configurations` when the console answer is blank |

**Manifest contents observed** (`VERIFIED`): `schema_version`, `builder_version`,
`project_name`, `base_fingerprint` (sha256 of the base document), `format_version`,
`contract_pin_record`, `path_policy`, `overwrite_policy`, `seed_set`, one entry per
variant (`key`, `label`, `declared_factors`, `applied_edits`, `file_name`,
`fingerprint`) and `validation_summary` (`finding_counts`, `skipped_rules`).
`manifest.run_info()` — timestamp, host, user, platform, pid — exists in
`output/manifest.py:145` but is **not** written, so the file on disk is fully
deterministic. That differs from the module docstring's description of `run_info` as
part of a run; the written artefact has no timestamps at all.

### 7.4 External dependencies during generation

| Needed to generate | Needed only for AF3 inference |
|---|---|
| Python 3.9+ **standard library** | AF3 itself, model weights, GPU drivers |
| nothing else for the core path | RDKit (SMILES → structure), the compiled CIF extension AF3 uses for `userCCD` |
| optionally **gemmi** for stricter template parsing at attach time (absent → the bundled lexical scan is used) | the university Linux environment and its data pipeline |

`VERIFIED`: generation ran with only the standard library plus gemmi present in the
project `.venv`; no network call occurred.

---

## 8. Input-to-output transformation

### 8.1 The rule

`VariantService.input_file_specs` (`app/variant_service.py:1136`) reads the file and
`batch_variants.specs_for_entries` (`batch_variants.py:440`) maps the kind to one
builder; each entry becomes

```
VariantSpec(key=<key>, label=<label>, edits=(AddRecord(<record>),))
```

`AddRecord` is the same edit a hand-made change uses, so a batch entry is not a special
case in the model. Independence is structural: `expansion.expand(base, specs)` applies
**every** spec to the **same** base object, so no entry can accumulate another's
entity. Identifiers are allocated from a *clone* of the base registry
(`project.configuration.identity.clone()`), which is then discarded — the base never
claims an id and the batch's ids never collide with the base's or with each other.

Fields: everything the base carries is retained (entities, seeds, version, dialect,
`userCCD`, MSA, templates, bonds, descriptions). The only additions are

- one `sequences[]` entry per record (DNA: two), and
- the top-level `name`, rewritten to `<slug(job)>__<key>` so it matches the file name.

Nothing is replaced or removed. `VERIFIED` — see §8.2/§8.3 for the exact documents.

Validation happens in three places, all before any write:

1. `_gate_base` — the base job through the gating tiers; blocking findings stop the run;
2. `ValidationService.validate_specs` — base first, then each variant against its own
   comparison data;
3. the planner's conflict/resource checks.

`VERIFIED`: after writing, all 14 generated documents from this audit were re-read by
`configbuilder.transform.from_wire` with **0 notes and 0 refusals**, i.e. the builder
can read its own output for every kind exercised.

### 8.2 Worked example — protein file against a four-entity base

Base `manual_test_data/af3_builder/batch/base_job_custom_ccd.json`:
`name = batch-base-with-ccd`, `modelSeeds = [7]`, `version = 3`, entities
protein `A`, ligand `B`/`E` (`ccdCodes ["ATP"]`), ligand `C` (`["ZN"]`),
ligand `D` (`smiles …`), and an inline `userCCD` definition.

Input `proteins_minimal.txt`: `MVT`, `MVS`, `MVY`, `TEST`.

Observed result — five files under the chosen folder:

```
out/batch-base-with-ccd/batch-base-with-ccd__batch-01/batch-base-with-ccd__batch-01.json
out/batch-base-with-ccd/batch-base-with-ccd__batch-02/batch-base-with-ccd__batch-02.json
out/batch-base-with-ccd/batch-base-with-ccd__batch-03/batch-base-with-ccd__batch-03.json
out/batch-base-with-ccd/batch-base-with-ccd__batch-04/batch-base-with-ccd__batch-04.json
out/batch-base-with-ccd/manifest.json
```

`batch-01` in full (unchanged fields elided in the comments):

```json
{
  "name": "batch-base-with-ccd__batch-01",        // base name + "__" + key
  "modelSeeds": [7],                              // unchanged
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKTAYIAKQRQISFVKSHFSRQ"}},   // unchanged
    {"ligand": {"id": ["B","E"], "ccdCodes": ["ATP"]}},               // unchanged
    {"ligand": {"id": "C", "ccdCodes": ["ZN"]}},                      // unchanged
    {"ligand": {"id": "D", "smiles": "CC(=O)Oc1ccccc1C(=O)O"}},       // unchanged
    {"protein": {"id": "F", "sequence": "MVT"}}                       // the ONE addition
  ],
  "userCCD": "data_MY_LIGAND\n…",                 // unchanged, byte-identical
  "dialect": "alphafold3",
  "version": 3
}
```

Identifiers allocated for the four entries were `F`, `G`, `H`, `I` — continuing after
the base's `A`,`B`/`E`,`C`,`D` — and the manifest records exactly those ids. No file
contains a second input record. The base file on disk was byte-identical before and
after (`VERIFIED`, md5).

### 8.3 The DNA exception

Input `dna_sequences.txt`: `ATGCATGC`, `GGCCTTAA` → two files, each with **two** new
entities, because DNA construction is the shared duplex builder:

```
"dna": {"id": "F", "sequence": "ATGCATGC"}   // the input strand
"dna": {"id": "G", "sequence": "GCATGCAT"}   // its reverse complement
```

So two DNA lines produce four new entities and six `sequences[]` entries in total.
This is the documented single-entity Add DNA behaviour reused, not a batch quirk — but
it is the one place where "one entry = one entity" is false and the user is not told
in the UI.

### 8.4 Ligand keys and names

| Kind | Key | Example output |
|---|---|---|
| SMILES, named | slug of the name | `…__ethanol`, `…__acetic-acid` |
| SMILES, bare | `ligand-N` from the reader's positional `ligand_N` | `…__ligand-1` |
| SMILES, duplicate names | deterministic `-2`, `-3` suffix in file order | `…__kinase-inhibitor`, `…__kinase-inhibitor-2` |
| CCD | codes joined with `-`, slugged | `…__atp`, `…__nag-nag-bma-man-man` |
| sequences | `batch_NN`, two digits, input order | `…__batch-01` |

The ligand name never appears inside the JSON: AF3 has no per-entity name field, so it
lives in the directory name, file name, manifest `label` and the console/window report.

### 8.5 Carried resources

`VERIFIED` with a base that references a template **by path**
(`manual_test_data/af3_builder/templates/template_fully_resolved.cif`):

```
out/base-template/base-template__batch-01/base-template__batch-01.json
out/base-template/base-template__batch-01/assets/template-fully-resolved.cif
… (one assets/ copy per variant)
```

and the document keeps the mapping verbatim:

```json
"templates": [{"mmcifPath": "assets/template-fully-resolved.cif",
               "queryIndices": [0, 1], "templateIndices": [0, 1]}]
```

The same holds for an external MSA (`unpairedMsaPath` → `assets/unpaired-query.a3m`),
and inline MSA text stays inline. `queryIndices`/`templateIndices` are **0-based**
(`model/values.py`), are not re-derived, are not validated against the template's real
residues (the builder never parses the template's contents for residue identity), and
are preserved as supplied.

---

## 9. Required and optional dependencies

| Layer | Requirement | Checked by |
|---|---|---|
| Core generation | Python 3.9+, standard library only (`pyproject.toml` `dependencies = []`) | `tools/check_dependencies.py` |
| Window | PySide6 ≥ 6.6 (`gui` extra) | same, plus an offscreen Qt smoke |
| Stricter template parsing | gemmi ≥ 0.6 (`templates` extra) — **optional**; without it the bundled lexical mmCIF scan is used and the capability is unchanged, only less strict | reported as `OPTIONAL`, never fatal |
| AF3 inference | **not installed, not needed, not attempted** | `check_dependencies.py` says so explicitly |

`VERIFIED`: `check_dependencies.py` reports 10/10 PASS and `Result: READY` in this
checkout, with gemmi present.

---

## 10. Validation and error-handling behaviour

Every row below was produced by running the real console in a temporary folder; the
quoted text is verbatim from the run.

| Condition | Result | Observed message (abridged) | Files written |
|---|---|---|---|
| Empty file, protein kind | **rejected** | `Nothing was written: the sequence file contains no sequences (only blank lines)` | 0 |
| Invalid residues in some lines | **rejected**, every bad line named | `2 of 3 protein sequences are invalid:` / `line 2: protein sequence contains characters outside its alphabet: ['1']` / `line 3: … ['-']` | 0 |
| FASTA header + wrapped record | **rejected** | `1 of 3 protein sequences are invalid: line 1: protein sequence contains characters outside its alphabet: [' ', '0', '>', '_', 'a', …]` — i.e. FASTA is caught by the alphabet, not by a FASTA parser | 0 |
| Duplicate ligand entries | **rejected**, whole file | `the file contains duplicate ligand entries: CCO...` | 0 |
| Duplicate names, different molecules | **accepted** | keys `kinase-inhibitor`, `kinase-inhibitor-2` | 3 (2 + manifest) |
| Invalid SMILES syntax | **rejected**, every bad line named | `line 3: 'C1CC' is not SMILES notation (ring-closure number 1 is opened but never closed)`; `line 4: 'this is not a smiles' … (it contains ' ', which is not a SMILES character)` | 0 |
| CCD codes in SMILES mode | **rejected** + hint | `line 7: 'ATP' is not SMILES notation …` then `These entries may be protein sequences rather than SMILES. Select the protein sequence input type …; if they are CCD codes, select the CCD code input type.` | 0 |
| Protein sequences in SMILES mode | **rejected** + hint | four `… is not SMILES notation …` lines + the same advice | 0 |
| Unknown kind token (API misuse) | **rejected** | `'<kind>' is not an input type this builder reads` | 0 |
| Output folder is an existing file | **rejected** | `could not create the directory '<path>\<job>': The system cannot find the path specified; the output directory '<path>' is a file` | 0 |
| Output folders do not exist (nested) | **created** | `Wrote 5 file(s) under <root>` | 5 |
| Rerun, identical bytes | **accepted, harmless** | every path reported as `Wrote …` again (`decide_action` treats identical content as an overwrite of the same bytes) | 5 (rewritten in place) |
| Rerun, one file has different bytes (policy `Fail`) | **rejected, all-or-nothing** | `Nothing was written: the plan has conflicts; nothing will be written` / `Conflict: <path> already exists with different content; delete or rename that file, or write the job to a different output folder` | 0 — and the tampered file was verified unchanged (md5) |
| Base references a template/MSA path that no longer exists | **rejected before writing** | `Nothing was written: resource source '<path>' is missing; nothing was written` | 0 |
| Base job has blocking validation findings | **rejected** | `… is not ready — blocking findings: …` (also pinned by `test_a_blocked_base_writes_nothing_and_reports_the_findings`) | 0 |
| Disk/permission failure *during* writing | **reported honestly, earlier files left in place** | `could not write '<path>': <reason>; N file(s) already written were left in place` | some |
| Base JSON cannot be imported | **rejected at Open**, project unchanged | `Could not open this JSON.` / `Reason: <reason>` / `The original file has not been modified.` | 0 |

**Stage separation.** Passing one stage is not passing the next, and the tooling keeps
them apart:

| Stage | What it proves | Where |
|---|---|---|
| input parsing | the lines are the kind's syntax | `persistence/sequences.py` |
| spec construction | the record is a valid model object | `app/batch_variants.py` |
| rule validation | the document satisfies the project's contract rules | `validation/catalogue.py` |
| structural JSON validity | the file parses as an AF3 document | AF3's own parser (offline substitute: `from_wire`) |
| file-content validation | the mmCIF template is a structure (gemmi/lexical) | `persistence/mmcif.py` |
| chemical validation | the molecule is chemically sensible | **nobody here** — AF3/RDKit |
| AF3 inference | the prediction works | **not attempted** |

**Partial-write claim, precisely.** Plan-level problems (conflicts, missing resource,
blocked base, bad input) abort before the first byte. A *filesystem* failure in the
middle of a multi-file run is not rolled back; each file is individually atomic and the
report names how many files were already written. The GUI/report text never claims a
write that did not happen.

---

## 11. Common user mistakes and confusing steps

Observed problems only; recommendations are in §13.

1. **A CCD code list given as SMILES.** The most likely first mistake, because both
   files are `.txt`/`.smiles` lists of short tokens. The refusal is good, but the user
   had to know the difference first. `VERIFIED`.
2. **A FASTA file.** Nothing in the UI says FASTA is unsupported; the user learns it
   from an alphabet error listing `'>'` and `'a'` as illegal — technically true,
   practically confusing. `VERIFIED`.
3. **DNA producing twice as many entities as lines.** Nothing in the preview says the
   duplex is built. `VERIFIED`.
4. **The kind question for a `.smiles` file.** A file whose extension already states
   the format is asked about anyway. Defensible (the extension decides nothing by
   design) but one extra click on the common path. `SOURCE-CONFIRMED`.
5. **A rerun after changing the base is refused, not updated.** With `Fail`, fixing a
   typo in the base and re-running the same file produces a wall of conflicts and no
   output; the user must delete the old folder or pick a new one. `VERIFIED`.
6. **Three different overwrite stories.** Console *save* asks a Y/N confirmation;
   the window's **Generate** page offers four overwrite and two path policies; the
   file-batch action offers none and always uses the project defaults. `VERIFIED`.
7. **Two "generate" actions.** `Entities → Generate configurations from file…` and the
   **Generate** page are adjacent in the user's mental model but write different
   things (per-entry configurations vs the open job's own file). `SOURCE-CONFIRMED`.
8. **The console file picker starts at the launch directory**, not the input folder,
   and lists subdirectories first, so `7)` may be a folder and `10)` the file the user
   wants. `VERIFIED` (the listing shifts as output folders appear).
9. **The window's CCD-kind file filter says "Ligand lists (\*.smiles \*.txt)"** —
   identical to the SMILES filter, because the filter is chosen by
   `kind.endswith("-sequence")`. Harmless, mildly misleading. `SOURCE-CONFIRMED`
   (`dialogs/batch_input.py:choose_batch_file`).
10. **Names are not in the JSON.** A user who opens an output looking for the ligand
    name will not find it. Documented in the batch README, not in the UI. `VERIFIED`.
11. **No per-entry template or MSA.** Users reasonably expect a column in the list file;
    there is none, and nothing in the UI says so. `SOURCE-CONFIRMED`.

---

## 12. Unsupported or incomplete functionality

| # | Item | Class | Evidence |
|---|---|---|---|
| U1 | Templates / MSA / PTMs / bonds / custom CCD as **per-entry** data | `NOT SUPPORTED` (by design) | `batch_variants.INPUT_KINDS` has five kinds; no column syntax exists; batch README §1 states it |
| U2 | FASTA input | `NOT SUPPORTED`, and unsafe if supplied | `parse_sequence_text` has no header handling; run refused |
| U3 | CCD registry membership check | `NOT SUPPORTED` | no CCD dictionary; `ComponentCode` checks shape only |
| U4 | Chemical validation of SMILES | `NOT SUPPORTED` (deliberate) | `validation/smiles.py` is a grammar check; RDKit belongs to AF3 |
| U5 | Overwrite / path policy choice inside the batch action | `NOT SUPPORTED` | neither `batch_input` dialogs nor `menus._generate_from_file` expose a policy; both pass `output_defaults()` |
| U6 | A human-operated GUI session for this audit | `BLOCKED` | no interactive display was used; the window evidence is the automated offscreen suite, three cases of which drive the real button and the packaged dialogs |
| U7 | AF3 inference verification of the outputs | `NOT ATTEMPTED` (out of scope, and the AF3 environment is separate) | AF3's own parser results are recorded in `tools/af3_validation/README.md`; this audit re-ran `from_wire` only |
| D1 | **A base JSON with inline `templates[].mmcif` cannot be opened** | `VERIFIED` defect | `from_wire` requires `mmcifPath` (`transform/from_wire.py:264-279`); the builder's own fixture `tests/fixtures/af3_pipeline/test04_protein_msa_template/…json` (produced by `generate_fixtures.test04` through `ReferenceInput(inline_text=…)`) is refused with `sequences[0].protein template 0 has no mmcifPath`. Both front ends attach templates by **path only**, so a hand-edited or API-generated inline-template base is the only way to hit it — but it means the builder cannot re-open some of its own output |
| D2 | Stale comment in a shipped fixture | `VERIFIED` documentation defect | `manual_test_data/af3_builder/batch/ligands_ccd_lookalike.smiles` still says the codes "are stored as SMILES text, so each output carries `smiles: ATP`"; the current code **refuses** that file (observed: `2 of 2 ligand entries are invalid …`) and `batch/README.md` correctly calls it a refusal fixture. The comment contradicts both the code and the README |
| D3 | A second, unexposed batch API | `SOURCE-CONFIRMED` | `VariantService.generate_from_file` (`variant_service.py:1269`) commits variants **into the project** instead of writing files; it has no UI caller (console and window both use `GenerationService`), but is still exercised by `generate_fixtures.py`, `run_all.py` and unit tests. Two batch semantics exist; the user only ever sees one |
| D4 | `run_info` documented as part of the manifest but not written | `SOURCE-CONFIRMED` | `output/manifest.py:145` defines it; `_plan_variants` encodes `manifest.data` only. The written manifest has no timestamp/host/user |

---

## 13. Prioritized recommendations

Ordered by practical benefit per unit of change. **Nothing here was implemented.**

**R1 — Offer the overwrite policy in the batch action (or state the rule).**
*What changes for the user:* after a base edit, re-running the same file could
"Replace the existing files" or "Write a numbered copy", matching the options the
Generate page already offers. *Backend effect:* none — `generate_input_batch` already
accepts `overwrite_policy`/`path_policy`; only the console prompt and one window
control are missing. *Output effect:* only which destination is chosen, never content.
Alternative, much cheaper: add one line to the preview ("existing files stop the run;
choose another folder to regenerate") so the refusal is predictable.

**R2 — Say that DNA builds a duplex, in the preview.**
*What changes:* the preview note for the DNA kind becomes "each entry becomes a DNA
entity and its reverse-complement strand", so 2 lines → 4 entities is expected.
*Backend/format effect:* none; string-only.

**R3 — Skip the kind question when the extension settles it, or pre-select it.**
*What changes:* a `.smiles` file preselects SMILES and the console asks "SMILES ligand
file? [Y/n]"; everything else still asks. *Backend effect:* none (the kind still
travels explicitly to the service, so no heuristic parsing appears). *Risk:* an
extension-based default is a heuristic, so it must remain an explicit confirmation.

**R4 — Make FASTA a recognised refusal, with the fix in the message.**
*What changes:* the error becomes "this looks like a FASTA file; batch input is one
sequence per line — split it, or add sequences one at a time in the entity form".
*Backend effect:* a header/wrap detector **for the message only** (still refused).
Alternatively accept FASTA properly — a larger change touching the reader, the docs and
the fixtures.

**R5 — Fix the inline-template import gap (D1).**
*What changes:* a base JSON that carries `templates[].mmcif` text can be opened, so the
builder can re-open its own output. *Backend effect:* `_import_references` gains an
inline branch producing the same `Inline`/`External` source type the writer already
uses; no wire-format change. Add the round-trip test that test04 currently lacks.

**R6 — Correct the stale fixture comment (D2)** and state in it what the code now does.
*What changes:* nothing functional; stops the pack contradicting itself.

**R7 — Retire or clearly mark the commit-based batch API (D3).**
*What changes:* maintainers stop wondering which batch is the product. *Backend
effect:* deleting `VariantService.generate_from_file`/`inspect_batch_file` requires
moving the fixture generators and `run_all.py` onto `GenerationService` first.

**R8 — One sentence in the batch README and the UI about what is *not* per-entry**
(templates, MSA, custom CCD, names). Cheapest possible fix for expectation number 11.

**R9 — Decide whether the manifest should carry `run_info` (D4)** and make the docstring
and the file agree, one way or the other.

---

## 14. Reproducible user walkthrough

### A. Before starting

- This checkout, with the local environment built (`setup_windows.bat`, then
  `check_dependencies.bat` → `Result: READY`).
- A **base job**: either an AF3 JSON this builder can open, or a new job with at least
  one entity. For the walkthrough below:
  `manual_test_data/af3_builder/batch/base_job_custom_ccd.json`.
- An **input file**, e.g. `manual_test_data/af3_builder/batch/proteins_minimal.txt`
  (`MVT`, `MVS`, `MVY`, `TEST`).
- An **empty output folder** (or a new path; missing folders are created).
- Nothing else. No AF3 installation, no network, no model weights.

### B. CLI

```
python af3builder.py
2                                  # Open a JSON file
<path to>base_job_custom_ccd.json  # or its listing number
7                                  # Generate configurations from a file (sequences or ligands)
1                                  # Load an input file and generate configurations
1                                  # Protein sequences, one per line
<path to>proteins_minimal.txt      # or its listing number
<empty or a path>                  # Output folder [<cwd>/generated_configurations]
0                                  # back to the job menu
0                                  # back to the main menu
0                                  # exit
```

Expected console text: `4 entries read from …` listing `MVT … TEST`, a note that each
entry becomes one new Protein entity and that the base is not modified, then
`Wrote <path>` five times and `Wrote 5 file(s) under <root>`.

The same walkthrough with kinds `2`/`4`/`5` and `dna_sequences.txt` /
`ligands_named.smiles` / `ligands_ccd_codes.txt` produces 3, 4 and 4 files
respectively (including the manifest).

### C. GUI

```
python gui.py
File → Open → base_job_custom_ccd.json
Entities tab → "Generate configurations from file..."
  Input type box        → "Protein sequences, one per line"
  Open dialog           → proteins_minimal.txt          (filter: Sequence lists)
  Folder dialog         → an empty folder
  Review box            → check "4 entries read", the kind, the destination → Generate
  Result box            → 4 configuration paths + manifest
```

Then check the status note under the Entities table (`Wrote 4 file(s) for the input
file.`).

### D. Outputs to expect

| Kind | File | New entities per output |
|---|---|---|
| protein (4 lines) | 4 JSON + 1 manifest | 1 protein each (`MVT`, `MVS`, `MVY`, `TEST`) |
| DNA (2 lines) | 2 JSON + 1 manifest | 2 DNA each (strand + reverse complement) |
| RNA (2 lines) | 2 JSON + 1 manifest | 1 `rna` each |
| SMILES (3 entries) | 3 JSON + 1 manifest | 1 `ligand.smiles` each |
| CCD (3 entries) | 3 JSON + 1 manifest | 1 `ligand.ccdCodes` each |

Layout: `<out>/<job-slug>/<job-slug>__<key>/<job-slug>__<key>.json` plus
`<out>/<job-slug>/manifest.json`; `assets/` appears only when the base references an
external MSA or template.

### E. Verifying success without AF3

1. **Count** the JSON files: one per entry, plus `manifest.json`.
2. **Open one** in the builder (`2` in the console, or File → Open). A file that opens
   is structurally readable by this application. Everything this audit generated
   re-imported with zero warnings.
3. **Diff one output against the base**: same `modelSeeds`, `version`, `dialect`,
   `userCCD`, same base entities in the same order, exactly one extra entity (none of
   the other entries' values).
4. **Check the manifest**: `variants[]` lists every key with its `file_name` and
   `fingerprint`; `seed_set` matches the base.
5. **Optionally, AF3's own parser**:
   `python tools/af3_validation/af3_validate.py <folder>` (needs
   `setup_validator.py` once). Documents whose base carries `userCCD` come back
   `UNVERIFIED` because AF3's compiled CIF extension is stubbed — that is a limitation
   of the checker, not a failure of the file.
6. What none of this proves: that the sequences are biologically meaningful, that the
   SMILES describes the intended molecule, that the template indices are a correct
   correspondence, or that inference will succeed.

### F. Common failures and what to do

| Message | Cause | Fix |
|---|---|---|
| `the sequence file contains no sequences (only blank lines)` | empty or comment-only file | check the file; sequences have no comment syntax |
| `line N: protein sequence contains characters outside its alphabet: ['>', …]` | FASTA or wrapped record | one sequence per line, no header |
| `'ATP' is not SMILES notation …` + hint | CCD codes opened in SMILES mode | choose the CCD code kind |
| `the file contains duplicate ligand entries: …` | the same SMILES twice | remove one, or use two names for two different molecules |
| `could not create the directory …; the output directory … is a file` | output path points at a file | choose a folder |
| `… already exists with different content; delete or rename that file, or write the job to a different output folder` | rerun after a base change | new folder, or remove the old one |
| `resource source '…' is missing` | the base's template/MSA path was moved/deleted | restore the file or re-attach the resource in the base job |
| `Could not open this JSON.` / `Reason: …` | unsupported or malformed base | fix the base; the project is left untouched |
| No `Wrote` lines, no error | every planned file already matched byte-for-byte and was reported as written | nothing to do; the outputs are current |

---

## 15. Evidence appendix

### 15.1 Source paths and the call chain

| Concern | Path | Key symbols (lines) |
|---|---|---|
| CLI entry | `af3builder.py` → `configbuilder/app/cli.py` | `main` |
| Console menus | `configbuilder/ui/render/menus.py` | `run` (498), `_main_menu` (519), `_new_job` (539), `_open_json_file` (551), `_job_menu` (584), choice `7` (616), `_pick_path` (412), `_ask_destination` (455), `FILE_KINDS` (1582), `_FILE_PROMPTS` (1593), `_file_menu` (1601), `_generate_from_file` (1637) |
| Console wording | `configbuilder/ui/present/strings.py` | `menu.job_actions` (81), `menu.file_*` (334-370), `gui.batch_*` (473-504) |
| GUI page | `configbuilder/ui/render/qt/pages/entities.py` | `batch_file_button` (268), `generate_from_file` (353) |
| GUI dialogs | `configbuilder/ui/render/qt/dialogs/batch_input.py` | `KIND_LABELS`, `choose_batch_kind`, `choose_batch_file`, `choose_output_folder`, `confirm_batch_preview`, `report_batch_run`, `_PREVIEW_ROWS` |
| GUI service bridge | `configbuilder/ui/render/qt/state.py` | `inspect_input_file` (312), `generate_input_configurations` (322) |
| Readers | `configbuilder/persistence/sequences.py` | `_numbered_lines` (56), `parse_sequence_text` (73), `parse_code_text` (85), `read_code_file` (96), `read_sequence_file` (115), `parse_smiles_text` (138), `read_smiles_file` (168) |
| Kind → builder table | `configbuilder/app/batch_variants.py` | `INPUT_KINDS` (96), `SEQUENCE_FAMILIES` (107), `BATCH_RECORD_BUILDERS` (178), `_name_key` (191), `_unique_key` (207), `ligand_specs_for_entries` (227), `_sequence_hint` (338), `ligand_code_specs_for_entries` (372), `specs_for_entries` (440), `batch_specs_for_sequences` (468) |
| Spec assembly | `configbuilder/app/variant_service.py` | `ligand_file_specs` (1059), `input_file_specs` (1136), `_batch_records_for_family` (1198), `inspect_input_file` (1214), `generate_from_file` (1269, commit-based, no UI caller) |
| Planning / writing | `configbuilder/app/generation_service.py` | `output_defaults` (282), `_plan_variants` (433), `plan_input_batch` (616), `generate_input_batch` (736) |
| Naming | `configbuilder/output/naming.py` | `slug` (37), `variant_directory_name` (61), `variant_file_name` |
| Action table | `configbuilder/output/plan.py` | `_versioned_path` (168), `decide_action` (182), `resolve_resources_into` |
| Executor | `configbuilder/output/execute.py` | `_atomic_write` (59), `execute` (86) — conflict/resource aborts before writes (95-119), `OSError` reporting (139-166) |
| Manifest | `configbuilder/output/manifest.py` | `build_manifest` (75), `run_info` (145) |
| Policies | `configbuilder/output/policies.py` | `OVERWRITE_POLICIES` (69), `PATH_POLICIES` (75); defaults `configbuilder/persistence/schema.py:49` |
| SMILES grammar | `configbuilder/validation/smiles.py` | `notation_problem` (61) |
| Template/MSA import | `configbuilder/transform/from_wire.py` | `_import_single_alignment` (252), `_import_references` (264) — `mmcifPath` required (278) |
| Template attach rules | `configbuilder/app/reference_validation.py` | `_file_problem`, `validate_reference`, `parse_pair_text` |
| Index semantics | `configbuilder/model/values.py`, `configbuilder/model/references.py` | `IndexPair` 0-based |
| Base generation (comparison) | `configbuilder/ui/render/qt/pages/generate.py` | `_build_scope_group` (172), policy combos (211-229) |

### 15.2 Executed commands and observed results

| Command | Result |
|---|---|
| `python af3builder.py` driven with scripted stdin, base = `base_job_custom_ccd.json`, kinds 1–5 against `proteins_minimal.txt`, `dna_sequences.txt`, `rna_sequences.txt`, `ligands_named.smiles`, `ligands_ccd_codes.txt` | exit 0 each; 5, 3, 3, 4, 4 files written; all JSON inspected |
| refusal runs (empty, invalid, FASTA, CCD-as-SMILES, lookalike, duplicates, unchecked syntax, protein-as-SMILES) | exit 0 each; every one refused with the messages quoted in §10; **0 files** written in every case |
| rerun into the same folder twice | identical bytes → reported as written again |
| rerun after appending one byte to one output | `Nothing was written: the plan has conflicts…`; tampered file unchanged (md5) |
| rerun with a nested new folder `out_nested/a/b` | directory tree created; 5 files written; base JSON md5 unchanged |
| base with external `unpairedMsaPath` | 4 JSON + 4 `assets/unpaired-query.a3m` + manifest; path rewritten to `assets/unpaired-query.a3m` |
| base with `templates[0].mmcifPath` | 4 JSON + 4 `assets/template-fully-resolved.cif`; indices `[0,1]/[0,1]` preserved |
| base with a template path that does not exist | `resource source … is missing; nothing was written`, 0 files |
| import of `tests/fixtures/af3_pipeline/test04_protein_msa_template/…json` | refused: `sequences[0].protein template 0 has no mmcifPath` (defect D1) |
| `from_wire` over all 14 generated documents | 14 accepted, 0 exceptions, 0 import notes |
| `tools/check_dependencies.py` (project `.venv`) | 10/10 PASS, `Result: READY`, exit 0 |

### 15.3 Tests run for this audit (all passed)

| Suite | Result | Relevance |
|---|---|---|
| `tests/e2e/test_entity_batch_cli_subprocess.py` + `tests/e2e/test_template_cli_subprocess.py` | **23 passed** | real console, kind selection, per-kind JSON, refusals, template attachment emitting `mmcifPath` |
| `tests/gui/test_file_generation.py` + `tests/gui/test_workflow_simplification.py` | **36 passed** (offscreen) | real Entities action, real button click + packaged dialogs, on-disk assertions, collision behaviour, base immutability |
| `tests/unit/app/test_batch_variants.py`, `tests/unit/persistence/test_sequence_files.py`, `tests/unit/validation/test_smiles_notation.py`, `tests/e2e/test_app_pipeline.py` | **135 passed, 1 skipped** | builders, readers, notation grammar, service pipeline |

Named cases quoted above: `test_the_protein_kind_writes_four_protein_configurations`,
`test_the_dna_and_rna_kinds_write_their_own_entity`, `test_the_ccd_kind_writes_component_codes`,
`test_a_sequence_file_in_smiles_mode_is_refused_with_advice`,
`test_a_ccd_code_in_a_smiles_file_is_refused_and_nothing_is_written`,
`test_the_kind_menu_offers_exactly_the_supported_input_types`,
`test_the_real_button_click_writes_the_files_through_the_packaged_dialogs`,
`test_an_existing_file_with_different_content_stops_the_whole_run`,
`test_generating_twice_leaves_the_base_job_identical`,
`test_a_custom_ccd_base_survives_in_every_generated_file`.

### 15.4 Where this audit's findings sit relative to existing documentation

`manual_test_data/af3_builder/batch/README.md` is accurate against the current code on
everything it covers (kinds, syntax, refusals, naming, output layout, the AF3 parser
caveat), and this audit's runs reproduced its claims. The gaps are the ones this report
adds: the inline-template import defect (D1), the stale fixture comment (D2), the
unexposed commit-based batch API (D3), the unwritten `run_info` (D4), the policy
asymmetry between the batch action and the Generate page (R1), and the DNA duplex not
being mentioned in the UI preview (R2).

---

## Closing separation of concerns

**The user must supply:** a base job (opened JSON or a new job), one input file in the
syntax of the chosen kind, the explicit statement of which kind it is, and an output
folder.

**The application creates automatically:** one directory and JSON per entry, the
internal `name` (`<job>__<key>`), all chain identifiers (continuing after the base's,
in file order), the manifest, the per-variant `assets/` copies of external resources,
the rewritten relative resource paths, any missing output directories, and the whole
`manifest.json`.

**Must remain available on disk during the run:** the base job JSON, the list file, and
every file the base references by path (template mmCIF, MSA `.a3m`). A missing
referenced file stops the run before any write.

**Can be moved with the output JSON:** each variant directory is self-contained —
`<job>__<key>/` holds its JSON and its `assets/`. The manifest is optional for
inference. The input list, the base JSON and the original template/MSA files are **not**
needed on the inference machine once generation has succeeded.

**Is required only later, on the AF3 inference server:** AF3 itself, model weights, GPU
drivers, RDKit for the SMILES entries, AF3's compiled CIF extension for `userCCD`, and —
for anything beyond structural acceptance — the actual inference run. None of it is
needed to produce or check the JSON files described here.

---

## 15. Status after the fix pass (post-audit appendix)

Everything above is the **as-found** audit of 2026-10-29 and is left as written. This
appendix records what changed afterwards; `docs/CONFIGURATION_GENERATION_FIX_REPORT.md`
is the authoritative account of the fixes, their tests and the remaining limitations.

| Item | As found (§12) | Now | Evidence |
|---|---|---|---|
| D1 inline `templates[].mmcif` | refused — the builder could not reopen its own output | **fixed**: `mmcif` and `mmcifPath` are both imported verbatim; both-fields and neither-field rows are refused with the location | console open → save → reopen preserved the text and `[1, 2]`; `tests/unit/transform/test_from_wire.py` |
| D2 stale fixture comment | contradicted the code | **fixed**: the comment now states the file is a refusal fixture | `manual_test_data/af3_builder/batch/ligands_ccd_lookalike.smiles` |
| D3 second batch API | two semantics, one exposed | **documented as legacy** in `VariantService`, with the user-facing workflow named; removal deferred (audit R7) | `configbuilder/app/variant_service.py` |
| D4 `run_info` | documented, never written | **documented as not written**, and pinned by a test that asserts the exact written key set | `configbuilder/output/manifest.py`, `tests/unit/output/test_manifest.py` |
| Index mapping (§11) | query length only | **validated**: duplicate query indices, template bounds against the full polymer sequence, chain count/kind, with the parser-absent case reported rather than guessed | `tests/unit/app/test_reference_validation.py`, `tests/unit/persistence/test_mmcif.py` |
| `userCCDPath` (§7.4) | not demonstrated | **verified and pinned**: copied into each output's `assets/`, path rewritten relative, survives a move, `userCCD` absent | `tests/e2e/test_app_pipeline.py` |
| Summary counts (§6.5 notes) | console counted the manifest as a file; the window could not count assets | **fixed**: one shared sentence counting configurations, manifests and copied assets, in both front ends | `tests/unit/app/test_batch_summary_counts.py`, `tests/gui/test_file_generation.py` |
| DNA duplex / overwrite wording | not explained before the write | **fixed**: one shared preview note, DNA-specific sentence included; identical bytes are described as rewritten, not skipped | `tests/gui/test_file_generation.py`, `tests/unit/ui/test_menu.py` |
| FASTA (U2) | unsupported, and the refusal was a wall of invalid-character errors | **still unsupported**, now diagnosed as FASTA with the supported shape and how to proceed | `tests/unit/app/test_batch_variants.py` |
| SMILES chemistry (U4) | grammar only | unchanged, and the docs keep saying so | — |
| Partial batch writes (§10) | earlier files left in place | **fixed**: files created by the failed run are removed again and empty directories cleaned up; a file the run *replaced* is kept and the error says so | `tests/unit/output/test_execute_atomicity.py` |

Recommendations §13 R1 (last sentence), R2, R4, R5, R6 and R9 are implemented; R3 (an
extension-based kind pre-selection) was deliberately not taken, because the explicit
kind question is what keeps content from being reinterpreted. R7 remains a separate
change: the legacy API is marked and documented instead of removed.
