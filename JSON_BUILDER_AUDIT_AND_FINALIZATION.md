# AlphaFold 3 JSON Builder — Audit & Finalization

**Status:** Phases 1–6 complete, plus parser-level validation against AlphaFold 3 itself, a real-surface playtest, and the import-continuity fix: **19 defects fixed**, the suite is green, and every document this builder emits has been checked with AF3's own input parser (§F.11). The defect register is §D; the verification record is §F.
**Audit date:** 2026-10-03
**Repository:** `configbuilder` (package) / branch `main`
**Audited by:** automated audit + scripted end-to-end CLI probes

> **How to read this document.** Sections A–E are the *initial* audit and plan,
> written from the actual code and from real scripted CLI runs before any repair.
> Section F is the **living verification record** and is updated after each phase.
> Anything not backed by a command output or a test run is marked *unverified*.

---

## A. Project Overview

### A.1 Entry point

| Item | Value | Evidence |
|---|---|---|
| Declared console script | `configbuilder = "configbuilder.app.cli:main"` | `pyproject.toml` `[project.scripts]` |
| Module entry point | `python -m configbuilder` → `configbuilder/__main__.py` → `configbuilder.app.cli:main` | `configbuilder/__main__.py` |
| Composition root | `configbuilder/app/cli.py:main()` — builds `Services` and runs `MenuApp` | `app/cli.py` |
| Menu implementation | `configbuilder/ui/render/menus.py` (`MenuApp`, 2011 lines) | file size |
| Return status | `main()` returns `0` on every deliberate end (exit choice, quit word, Ctrl+C, EOF) | `app/cli.py`, `MenuApp.run` |

`cli.py` is the *only* module allowed to import `ui` (architecture test
`tests/architecture/test_dependency_rules.py` names it as the single exception).

**Launch command (verified):**

```bash
python -m configbuilder          # from the project root
configbuilder                    # after `pip install -e .`
```

### A.2 The main menu as it exists today

Two screens exist. The **start screen** is shown only when no project is open:

```
================================================================================
                                 ConfigBuilder
================================================================================

Working copy: kept automatically — re-open it any time with Open saved work

  1) New job
  2) Open saved work
  3) Import an AF3 JSON file

0)  Exit
Select:
```

The **master menu** is shown once a project exists:

```
Current job: <name>

<Configuration status block: Name / Model seeds / AF3 version / Entities /
 Modifications / MSA / Templates, each marked OK / MISSING / INVALID / -, plus
 STATUS: READY|INCOMPLETE>

Variants: <n>
Working copy: kept automatically — re-open it any time with Open saved work

  1) Edit the job
  2) Review configuration
  3) Variants
  4) Generate JSON
  5) Open saved work
  6) Import an AF3 JSON file

0)  Exit
Select:
```

### A.3 Menu option → module map

| # | Label | Dispatch (menus.py) | Application service | Terminal effect |
|---|---|---|---|---|
| 1 | Edit the job | `_edit_job_menu` → `_entities_menu` / `_job_settings` / `_bonds_menu` | `ConfigurationService` | Mutates the in-memory configuration; `ProjectService._commit_project` autosaves the `.cbproj` working copy |
| 2 | Review configuration | `_review_screen` → `_validate_review` / `_show_json` | `ValidationService`, `GenerationService.show_json` | Read-only |
| 3 | Variants | `_variants_menu` → `_create_variant` / `_manage_variants` / `_batch_from_file` / `_quantity_series` | `VariantService` | Adds/edits/removes `VariantSpec`s on the project; autosaves |
| 4 | Generate JSON | `_generate_menu` → `_generate_base_json` / `_export` / `_change_output_dir` | `GenerationService.plan_base` / `plan` / `execute` | Writes `<out>/<slug>/<slug>.json` (+ variant dirs + `manifest.json`) |
| 5 | Open saved work | `_load_project` | `ProjectService.load_saved_work` | Replaces the current project with the newest `.configbuilder/*.cbproj` |
| 6 | Import an AF3 JSON file | `_import_json` | `ProjectService.import_json_preview` / `import_json_commit` | Replaces the current project with the imported one (preview + numbered confirm first) |
| 0 | Exit | `_master_menu` returns | — | Ends the session; working copy stays on disk |

### A.4 Current JSON-generation workflow

One authoritative path, used for preview *and* for writing:

```
Configuration (model)
  → ValidationService.validate_base()      gate: any ERROR ⇒ refuse
  → VariantService.expand()                variants = base + edits (base untouched)
  → transform.to_wire()                    model → AF3 wire document
  → transform.with_wire_job_name()          wire "name" == slug == filename
  → transform.with_emitted_resource_paths() §13.5 path policy
  → serialize.encode()                     the single JSON serializer
  → output.plan()                          create/overwrite/skip/conflict + manifest
  → output.execute()                       atomic writes only
```

`GenerationService.show_json()` runs the *same* `to_wire → encode` pair, so the
preview is byte-identical to what a file would contain. The UI never serializes.

### A.5 Internal representation of jobs and variants

* **Job (`Project`)** = `Configuration` + `specs` (variant specs) + `OutputSettings`.
* **`Configuration`** = `metadata` (job name), `seeds` (`SeedSet`), `records`
  (the entities), `identity` (`IdentityRegistry`), `format_target`
  (`Pinned(4)` by default), plus `linkages` and `component_definition`.
* **Entities** are four distinct record types with no shared base:
  `FamilyARecord` (protein), `FamilyBRecord` (RNA), `FamilyCRecord` (DNA),
  `ComponentRecord` (ligand/ion).
* **Identity**: every chain identifier is allocated by `IdentityRegistry`.
  A record with *N* copies holds a `Multiplicity` of *N* identifiers; the
  first is the record's stable handle (`ids.primary`).
* **Variants** are `VariantSpec(key, label, edits)`. A variant is *never* a
  mutated base: `expand()` applies each spec's edits to the same base object
  through a cloned registry, so independence is structural.
* **`.cbproj`** files are the application's own autosave working copies, kept
  in `.configbuilder/` under the CWD (max 50, pruned on `new()`).

### A.6 How and where JSON is saved

* Base job → `<output_dir>/<project_slug>/<project_slug>.json` (`plan_base`).
* A variant → `<output_dir>/<project_slug>/<project_slug>__<key>/<project_slug>__<key>.json`.
* A variant run also writes `<output_dir>/<project_slug>/manifest.json`.
* `output_dir` defaults to the relative string `"output"` (`MenuApp.__init__`)
  and is changed from the Generate screen (option "Change the output directory").
* Writes are atomic (`output/execute.py`); the overwrite policy default is
  `Fail`, which *refuses* rather than clobbering a file with different bytes.

### A.7 Loading, editing, validating, regenerating existing JSON

* **Import (option 6)** parses the file with `json.load`, converts it through
  `transform.from_wire`, and installs the result as an ordinary project
  (preview → numbered confirm). Unsupported fields produce `ImportNote`s that
  are printed. `from_wire` never mutates the source file.
* Once imported, the job is a normal configuration: editable, variant-able,
  generatable. Re-generation goes through the normal naming, so the original
  file is not overwritten in place (a same-named target *conflicts* instead).
* **Validation** is a catalogue of rules (`configbuilder/validation/`) that
  emit findings with severities `INFO`/`WARNING`/`ERROR`. Generation gates on
  `ERROR`.

### A.8 Test framework and commands

| Item | Value |
|---|---|
| Framework | `pytest` (`pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `addopts = "-q"`) |
| Dev extras | `pytest>=7`, `hypothesis>=6` (`[project.optional-dependencies].dev`) |
| Run all | `python -m pytest` |
| Run one area | `python -m pytest tests/unit/ui -q` |
| Baseline (audit date) | **824 tests, 1 skipped, 0 failed** — `python -m pytest -q` |
| Scripted CLI harness | `ScriptedConsole` (`ui/render/console.py`) + shared keystroke scripts in `tests/unit/ui/menu_flows.py` |

### A.9 Dependencies and Python version

* `requires-python = ">=3.9"`; **no runtime dependencies** — standard library only.
  The comment in `pyproject.toml` states nothing may move into
  `[project].dependencies` without amending `IMPLEMENTATION_PLAN.md`.
* The audit environment ran Python **3.11.15** (Windows). Python 3.9
  compatibility is a *declared* constraint and is **not** exercised by any
  test run in this audit (no 3.9 interpreter available) — see §F "limitations".

### A.10 External assumptions that affect execution

* The AF3 contract is pinned in `AUTHORITATIVE_SPEC.md` (dialect `alphafold3`,
  JSON versions 1–4; v2 = external MSA/template paths, v3 = `userCCDPath`,
  v4 = textual `description`). The builder pins **version 4** by default.
* The `.cbproj` store and the default `output/` directory are **relative to the
  current working directory**, so where the user launches from determines where
  work lands.
* No network access, no external tools, no AF3 installation is required to
  build input JSON.

---

## B. Main Menu Audit

Legend — **Status**: `working` / `partial` / `broken` / `unverified`.

### B.1 Start screen

| Field | Option 1 — New job |
|---|---|
| Exact label | `  1) New job` (start screen) |
| Intended purpose | Begin a fresh job, optionally naming it |
| Actual implementation | `MenuApp._new_or_load` → `ProjectService.new(name)` |
| Dependencies | none |
| Input handling | `menu.ask_experiment`; blank ⇒ service mints `config-NNN` |
| State changes | Replaces any current project; prunes `.configbuilder` to 50 |
| Saving behavior | Immediately autosaves a `.cbproj` working copy |
| JSON output | none yet |
| Failure cases | none observed; blank name and EOF both handled |
| Test coverage | `tests/unit/ui/test_menu.py`, `tests/e2e/test_app_pipeline.py` |
| **Status** | **working** |

| Field | Option 2 — Open saved work |
|---|---|
| Exact label | `  2) Open saved work` |
| Intended purpose | Recover earlier work |
| Actual implementation | `_load_project` → `ProjectService.load_saved_work()` |
| Dependencies | a `.configbuilder/*.cbproj` file in the CWD |
| Input handling | none (no prompt) |
| State changes | Opens the newest working copy; if the open job *is* that copy, refuses with an explanation |
| Saving behavior | n/a |
| JSON output | none |
| Failure cases | no saved work ⇒ `Not applied: there is no saved work to reopen` (verified) |
| Test coverage | `tests/unit/app/test_work_preservation.py` |
| **Status** | **working**, but see BUG-007 (label mismatch) |

| Field | Option 3 — Import an AF3 JSON file |
|---|---|
| Exact label | `  3) Import an AF3 JSON file` |
| Intended purpose | Load an existing AF3 JSON as the current job |
| Actual implementation | `_import_json` → `import_json_preview` → numbered confirm → `import_json_commit` |
| Dependencies | a readable JSON file |
| Input handling | `_pick_path` directory picker / literal path; numbered confirm |
| State changes | Current project is replaced **only** after the confirm |
| Saving behavior | Imported job is committed to the internal working copy immediately |
| JSON output | none |
| Failure cases | missing file, malformed JSON, unsupported fields — all verified to report a reason and leave the job untouched |
| Test coverage | `tests/unit/transform/test_from_wire.py`, `tests/unit/app/*` |
| **Status** | **working** |

### B.2 Master menu

| Field | Option 1 — Edit the job |
|---|---|
| Exact label | `  1) Edit the job` |
| Intended purpose | Change entities, job settings, structural extras |
| Actual implementation | `_edit_job_menu` → `_entities_menu`, `_job_settings`, `_bonds_menu` |
| Dependencies | an open project |
| Input handling | numbered menus + free-text prompts |
| State changes | Mutates the configuration through `ConfigurationService` |
| Saving behavior | Autosaved to `.cbproj` on every committed change |
| JSON output | none (Generate writes) |
| Failure cases | **crashes on a blank modification code** (BUG-001); unhandled `ValueError` text for non-numeric residue/position (BUG-002) |
| Test coverage | `tests/unit/ui/test_menu.py`, `test_numbered_flows.py` |
| **Status** | **partial** — reachable and mostly working; two input-validation defects |

| Field | Option 2 — Review configuration |
|---|---|
| Exact label | `  2) Review configuration` |
| Intended purpose | See the job, validate it, look at its JSON |
| Actual implementation | `_review_screen` → `_validate_review`, `_show_json` |
| Dependencies | open project |
| Input handling | numbered menu |
| State changes | none |
| Saving behavior | none |
| JSON output | prints JSON to the transcript (does not write a file) |
| Failure cases | **`Show the JSON` on a job with no entities prints `"sequences": []`**, which AF3 rejects (BUG-003) |
| Test coverage | `tests/unit/ui/test_menu.py` |
| **Status** | **partial** — review works; the JSON preview can show a structurally invalid document |

| Field | Option 3 — Variants |
|---|---|
| Exact label | `  3) Variants` |
| Intended purpose | Create/manage variants, batch from file, concentration series |
| Actual implementation | `_variants_menu` → `_create_variant`, `_manage_variants`, `_batch_from_file`, `_quantity_series` |
| Dependencies | open project (a valid base is needed only at generate time) |
| Input handling | numbered submenus, `_select_entity`/`_select_variant` pickers, `_ask_name` |
| State changes | Adds/edits/removes specs on the project; base untouched |
| Saving behavior | Autosaved with the project |
| JSON output | none (Generate writes variant files) |
| Failure cases | base with no ligand ⇒ `No variable components … in the current job.` (verified); see BUG-005 for the `Back` wording |
| Test coverage | `tests/unit/variants/*`, `tests/unit/app/test_batch_variants.py`, `tests/variant/*` |
| **Status** | **working** |

| Field | Option 4 — Generate JSON |
|---|---|
| Exact label | `  4) Generate JSON` |
| Intended purpose | Preview and write the job's (and variants') JSON |
| Actual implementation | `_generate_menu` → `_generate_base_json`, `_export`, `_change_output_dir` |
| Dependencies | a job that passes validation |
| Input handling | `_pick_path` for the output dir; `y/N` for variant export; numbered confirm for base export |
| State changes | none to the job |
| Saving behavior | Writes JSON + `manifest.json`; atomic |
| JSON output | `<out>/<slug>/<slug>.json`, `<out>/<slug>/<slug>__<key>/…json`, `<out>/<slug>/manifest.json` |
| Failure cases | blocking findings ⇒ names each rule; existing differing file ⇒ `Conflict: … already exists with different content` (both verified) |
| Test coverage | `tests/unit/output/*`, `tests/golden/*`, `tests/e2e/*` |
| **Status** | **working** |

| Field | Option 5 — Open saved work |
|---|---|
| Exact label | `  5) Open saved work` |
| Intended purpose | Recover earlier work |
| Actual implementation | same as start-screen option 2 |
| **Status** | **working**, but the label promises "saved work" while the app saves only JSON on request (BUG-007) |

| Field | Option 6 — Import an AF3 JSON file |
|---|---|
| Exact label | `  6) Import an AF3 JSON file` |
| Intended purpose | Replace the current job with a loaded JSON |
| Actual implementation | same as start-screen option 3 |
| **Status** | **working** |

| Field | Option 0 — Exit |
|---|---|
| Exact label | `  0)  Exit` |
| Intended purpose | Leave safely |
| Actual implementation | `_master_menu` returns; `run()` returns 0 |
| Failure cases | none; Ctrl+C and EOF are caught in `run()` |
| **Status** | **working** |

### B.3 Submenu inventory (the "inner" options)

| Screen | Options | Status |
|---|---|---|
| Edit the job | 1 Entities / 2 Job settings / 3 Bonds, modifications & custom components | working |
| Entities | 1 Add / 2 Edit / 3 Delete | working |
| Which kind of entity | 1 Protein / 2 DNA / 3 RNA / 4 Ligand | working |
| Job Settings | 1 name / 2 AF3 version / 3 seeds / 4 generate seeds | working |
| Bonds… | 1 add bond / 2 remove bond / 3 add modification / 4 remove modification / 5 custom component definition | **partial** — option 3 crashes on a blank code (BUG-001); a ligand picked as the carrier is refused with a misleading message (BUG-006) |
| Variants | 1 Create / 2 Manage / 3 From a sequence file / 4 Concentration-quantity series | working |
| Manage variants | 1 Edit / 2 Duplicate / 3 Delete / 4 Preview / 5 Generate JSON | working |
| Generate JSON | 1 this job / 2 all variants / 3 select variants / 4 change output dir (numbers shift when no variants exist) | **partial** — see BUG-008 |
| MSA mode (protein) | Automatic / Unpaired / Paired / Both / Free | working |
| MSA mode (RNA) | Automatic / Free / Provided | working |
| Templates | Search allowed / Explicitly none / Provide a list | working |

### B.4 Menu findings (misleading / redundant / inaccessible / unfinished)

1. **BUG-007 — "Open saved work" is ambiguous.** There is no user-facing *save
   project* action anywhere in the menu. JSON is written by Generate; the
   `.cbproj` is written silently. A beginner reading "Open saved work" cannot
   tell what is being opened, and may believe their job is already saved when
   it is only in the internal working copy. **The menu needs an explicit
   "Save the job" action that says what it wrote and where.**
2. **BUG-008 — Generate menu numbering shifts.** With no variants the menu
   shows only two options (`1` = this job, `2` = change output dir); with
   variants it shows four (`1` = this job, `2` = all variants, `3` = select,
   `4` = change dir). The number for "change output directory" changes meaning
   between the two states, and the code dispatches on `choice == "2" and not
   has_variants`. This is a latent correctness trap, not just cosmetics.
3. **BUG-005 — "Back" in the ligand quantity submenu silently discards the
   whole entity.** Choosing Back after typing a ligand value abandons the add
   without saying so; the user believes they went back one step.
4. **BUG-006 — a ligand can be selected as a modification carrier**, and is
   then refused with `A ligand has no sequence, alignment, or templates; change
   it by deleting it and adding it again.` — a message about *editing*, not
   about PTM carriers. Ligands must not be offered for PTMs at all.
5. **Reachable but undiscoverable:** the base-job JSON and the variant JSONs are
   both written from option 4, but nothing on the master menu says so, and the
   "Working copy: kept automatically" line appears on every screen without ever
   stating that no JSON has been written yet.
6. **No unsaved-work prompt on exit.** Because everything is autosaved, exiting
   cannot lose the *configuration*; but it can lose the *fact* that the user
   never generated JSON. The exit path says nothing.

### B.5 Can a beginner finish every normal task from the displayed menu?

| Task | Reachable from the menu alone? |
|---|---|
| Create a new job | yes |
| Add protein / DNA / RNA / ligand / ion | yes |
| Configure MSA and templates | yes (inside the entity add/edit flow — but nothing on screen hints that MSA lives there) |
| Add PTMs and bonds | yes |
| Review and validate | yes |
| Write the job's JSON | yes |
| Create variants, batch, concentration series | yes |
| Load and edit an existing JSON | yes |
| Save / find the written JSON | **only via Generate**; no save action, no path echo on the master menu |
| Exit safely | yes |

**Conclusion:** every capability is reachable, but two things a beginner needs are
not *discoverable*: (a) that MSA/templates live inside the entity flow, and
(b) what "saved" means, and where JSON goes. Both are addressed in Phase 2.

---

## C. Full Workflow Audit

Each journey was driven end-to-end through the **real** `MenuApp` with a
`ScriptedConsole`, in a scratch directory, using the shipped services.

| # | Journey | Result | Notes |
|---|---|---|---|
| 1 | Start the application | ✅ | Banner, start screen, exit all work |
| 2 | Create a new job (named and blank) | ✅ | `config-001` minted for a blank name |
| 3 | Enter a protein sequence | ✅ | Invalid characters refused with the offending set named |
| 4 | Enter DNA and build the duplex | ✅ | `ATGC` → two records `ATGC` / `GCAT`, distinct ids |
| 5 | Add RNA | ✅ | `ACGU` accepted; MSA question follows; no templates question (correct) |
| 6 | Add ligands and ions | ✅ | CCD multi-code `HOH NA CL` → one record, 3 ids; SMILES → `ByNotation`; copies honoured |
| 7 | Add PTMs | ⚠️ | Valid PTM works and is validated; **blank code crashes** (BUG-001); out-of-range position is accepted then caught by validation (by design, but only at generate time) |
| 8 | Configure MSA and template paths | ✅ | Protein: automatic/unpaired/paired/both/free + inline or file source. RNA: automatic/free/provided. DNA/ligand: correctly not offered |
| 9 | Load an existing JSON file | ✅ | Preview → confirm → installed; missing file, malformed JSON and unknown fields all reported |
| 10 | Edit a loaded job | ✅ | Editing works on an imported job exactly like a native one |
| 11 | Save the base job | ⚠️ | Only via Generate. No explicit save action, no path echo outside the Generate screen (BUG-007) |
| 12 | Create variants from the base | ✅ | `base + edits`; base unchanged; change summaries rendered |
| 13 | Batch variants from a text file | ✅ | Blank lines ignored; invalid lines reported **with line numbers**; all-or-nothing |
| 14 | Concentration-style variants | ✅ | `start × factor^(n-1)`; preview shown before creation; three independent specs from the same base |
| 15 | Preview the job and JSON | ⚠️ | Works; on an empty job it prints `"sequences": []` (BUG-003) |
| 16 | Save generated JSON | ✅ | Atomic; conflict refusal names the file; identical bytes ⇒ `overwrite` |
| 17 | Recover from invalid input / interruption | ⚠️ | Most paths recover; PTM blank code crashes; a few prompts echo raw Python exceptions (BUG-002) |
| 18 | Return to the menu without losing work | ✅ | Every submenu returns; autosave keeps the working copy |

### C.1 Broken transitions / invalid states found

* `_add_modification` → blank code → **uncaught `ValueTypeError`** (BUG-001).
* `_add_modification` / `_add_linkage` → non-numeric residue or position →
  user sees `invalid literal for int() with base 10: 'abc'` (BUG-002).
* `_select_entity` → a record whose multiplicity has more than one id →
  **the record cannot be edited or deleted** (BUG-004).
* `_show_json` on a job with no entities → structurally invalid AF3 document (BUG-003).
* `_ask_quantity` → Back → the whole ligand add is abandoned silently (BUG-005).
* `_add_modification` offers ligand records as PTM carriers (BUG-006).

---

## D. Defect Register

> Severity: **critical** = data loss, crash, or invalid output in a normal path;
> **high** = crash or wrong behaviour reachable by an ordinary mistake;
> **medium** = misleading/incorrect behaviour, recoverable;
> **low** = cosmetic.

### BUG-001 — Blank modification code crashes the application
* **Severity:** high
* **Reproduction:** Edit the job → 3 Bonds, modifications & custom components →
  3 Add a modification → pick a protein → press Enter at `Modification code`.
* **Expected:** the refusal is reported and the prompt returns.
* **Actual:** `configbuilder.model.values.ValueTypeError: ComponentCode must be
  non-empty` propagates out of `MenuApp.run()` and terminates the session.
* **Root cause:** `ConfigurationService.add_modification` catches
  `(ValueError, TypeError)`, but the model's `ValueTypeError` derives from
  `ModelError(Exception)` — *not* from `ValueError` — so it escapes.
* **Files:** `configbuilder/app/configuration_service.py:445-461`.
* **Required correction:** catch `ModelError` (the model's actual error base).
* **Regression test:** drive the menu with a blank code; assert no exception and
  that no modification was added.
* **Status:** **FIXED & VERIFIED** — a blank code is refused. `add_modification` now catches `ModelError` like every other mutation, and the menu asks only for a non-empty code, reporting `menu.mod_cancelled` when it is blank. Pinned by `test_blank_modification_code_is_refused_not_raised` and `test_blank_modification_code_through_the_menu_says_cancelled`.

### BUG-002 — Raw Python exception text shown to the user
* **Severity:** medium
* **Reproduction:** add a PTM with position `abc`; or add a bond with residue `abc`.
* **Expected:** an actionable message naming the field and the expected format.
* **Actual:** `Not applied: invalid literal for int() with base 10: 'abc'`.
* **Root cause:** `int(position)` / `int(a_residue)` raise `ValueError`, which is
  caught and stringified verbatim.
* **Files:** `configuration_service.add_modification`, `.add_linkage`;
  `ui/render/menus.py:_add_modification`, `_add_linkage`.
* **Required correction:** validate the integer in the UI layer with a clear
  message, and/or convert the model error into a domain message.
* **Regression test:** non-numeric residue/position yields the registered
  "whole number" message.
* **Status:** **FIXED & VERIFIED** — numeric prompts have their own reader (`_ask_whole_number`) and a registered message (`'abc' is not a whole number — enter digits only (for example 12).`), so no `int()` text reaches the user. Pinned by `test_non_numeric_ptm_position_is_answered_in_user_terms` and `test_non_numeric_bond_residue_is_answered_in_user_terms`.

### BUG-003 — JSON preview can show a document AF3 rejects
* **Severity:** high
* **Reproduction:** New job → 2 Review configuration → 2 Show the JSON.
* **Expected:** either a refusal explaining that entities are required, or a
  document that is valid AF3 input.
* **Actual:** a complete document is printed containing `"sequences": []`.
  Standalone AF3 requires at least one entity; `[]` is not valid input.
* **Root cause:** `GenerationService.show_json` transforms and encodes without
  running the validation gate that `plan_base`/`plan` apply.
* **Files:** `configbuilder/app/generation_service.py:show_json`;
  `ui/render/menus.py:_show_json`.
* **Required correction:** run the base validation gate in `show_json` (or have
  the UI refuse when the status is not ready) so preview and generation agree.
* **Regression test:** empty job ⇒ `show_json` returns an error, not a document;
  a ready job ⇒ preview equals the written file byte-for-byte.
* **Status:** **FIXED & VERIFIED** — `show_json` runs the same `validate_base` gate as the writer and returns an error when the job is not ready (`Cannot build JSON: the job is not ready to be written yet; see Review configuration for what is missing`). Pinned by `test_json_preview_refuses_an_incomplete_job` and `test_json_preview_of_a_ready_job_matches_the_written_file`.

### BUG-004 — Records with more than one copy cannot be edited or deleted
* **Severity:** high
* **Reproduction:** add a ligand with 3 copies, then Edit an entity → pick it.
* **Expected:** the picked record is edited/deleted (all its copies).
* **Actual:** `update_record` / `remove_record` return
  `no record is identified by 'A'` — the record is invisible to the service.
* **Root cause:** `ConfigurationService._record_for` compares
  `tuple(record.ids) == tuple(identity.multiplicity_of(primary))`. For a
  3-copy record `multiplicity_of('A')` returns **only** `['A']` while the record
  holds `['A','B','C']`, so the equality never holds. Every copy-count > 1
  record is unreachable by key.
* **Files:** `configbuilder/app/configuration_service.py:_record_for` (used by
  `update_record`, `remove_record`, `add_modification`, `set_alignment`,
  `set_references`, `set_representation`).
* **Required correction:** resolve by *membership*: the record whose multiplicity
  contains the resolved identifier.
* **Regression test:** a 3-copy ligand and a 2-copy ion are editable and
  deletable through the menu and through the service.
* **Status:** **FIXED & VERIFIED** — `_record_for` resolves a record by membership (`record.ids.contains(primary)`) and `remove_record` releases the record's own multiplicity instead of the singleton, so identifiers are no longer leaked. A three-copy ligand is editable, modifiable and deletable from the menu. Pinned by `test_multi_copy_record_can_be_edited_and_deleted`, `test_multi_copy_record_releases_every_identifier_on_delete`, `test_multi_copy_ligand_is_deletable_through_the_menu` and `test_multi_copy_record_can_carry_a_modification`.

### BUG-005 — "Back" in the quantity submenu silently discards the entity
* **Severity:** medium
* **Reproduction:** Add an entity → Ligand → CCD → `ATP` → Back at
  `How many copies?`.
* **Expected:** return to the previous step (the ligand value) or say the add was
  cancelled.
* **Actual:** the add is abandoned with no message; the menu simply re-renders.
* **Root cause:** `_ask_quantity` returns `None` on cancel and `_add_entity`
  returns immediately without a notice.
* **Files:** `ui/render/menus.py:_ask_quantity`, `_add_entity`.
* **Required correction:** say the add was cancelled, and prefer offering a
  default copy count rather than a dead end.
* **Regression test:** Back at the quantity menu ⇒ a cancellation notice and no
  new record.
* **Status:** **FIXED & VERIFIED** — every abandoned add announces itself (`menu.add_cancelled`: `Cancelled — nothing was added.`), so Back can no longer be mistaken for stepping back one screen. Pinned by `test_back_at_the_quantity_menu_says_nothing_was_added` and `test_back_at_the_ligand_kind_menu_says_nothing_was_added`.

### BUG-006 — Ligands are offered as modification carriers
* **Severity:** medium
* **Reproduction:** Bonds… → 3 Add a modification → pick a ligand.
* **Expected:** only polymers are offered.
* **Actual:** the ligand is offered, then refused with a message about editing
  ligands (`menu.entity_no_fields`), which is the wrong subject.
* **Root cause:** `_add_modification` uses `_select_entity()` with no family
  filter.
* **Files:** `ui/render/menus.py:_add_modification`; wording
  `ui/present/strings.py:menu.entity_no_fields`.
* **Required correction:** restrict the picker to `("protein","rna","dna")` and
  add a registered "no polymer carries modifications yet" note.
* **Regression test:** with only a ligand present, the PTM picker reports the
  registered note and adds nothing.
* **Status:** **FIXED & VERIFIED** — the PTM picker is restricted to protein, RNA and DNA; when none exists the screen says `No protein, RNA, or DNA chain to modify yet — add one first (ligands carry no modifications).` Pinned by `test_ligand_is_not_offered_as_a_modification_carrier`.

### BUG-007 — No explicit save action; "Open saved work" is ambiguous
* **Severity:** medium
* **Reproduction:** create a job, look for a way to save it.
* **Expected:** a clearly labelled save action that reports the path it wrote.
* **Actual:** JSON is written only from option 4; the master menu says
  `Working copy: kept automatically`, which a beginner reads as "already saved".
* **Root cause:** the JSON-first refactor removed the project save action and the
  master menu never gained a save entry.
* **Files:** `ui/render/menus.py:_master_menu`, `_generate_menu`;
  `ui/present/strings.py`.
* **Required correction:** add `Save the job (write its AF3 JSON)` to the master
  menu, reporting the exact path written and refusing to write an invalid job.
* **Regression test:** the new option writes `<out>/<slug>/<slug>.json` and
  prints the path; on an incomplete job it refuses with the missing fields named.
* **Status:** **FIXED & VERIFIED** — the master menu now offers `5) Save the job (write its AF3 JSON)`, which plans through the same reviewed serializer, confirms, writes and prints `Saved to <path>`; an incomplete job is refused with the missing-field list, and a cancellation writes nothing. Pinned by `test_save_action_writes_the_json_and_names_the_path`, `test_save_action_refuses_an_incomplete_job`, `test_save_action_cancelled_writes_nothing` and the end-to-end `test_option_5_save_reports_the_path_and_writes_valid_json`.

### BUG-008 — Generate menu numbering changes meaning between states
* **Severity:** medium
* **Reproduction:** open Generate JSON with and without variants defined.
* **Expected:** each number means one thing.
* **Actual:** `2` means "all variants" when variants exist and "change the output
  directory" when none do.
* **Root cause:** two different registered action blocks plus conditional
  dispatch (`choice == "2" and not has_variants`).
* **Files:** `ui/render/menus.py:_generate_menu`;
  `strings.py:menu.generate_actions`, `menu.generate_actions_base`.
* **Required correction:** always render the same numbering, disabling variant
  rows with a clear note when there are no variants.
* **Regression test:** the same digits reach the same handlers in both states.
* **Status:** **FIXED & VERIFIED** — the Generate screen always renders the same four rows; while no variants exist, rows 2 and 3 say `no variants to write yet` instead of the output-directory row moving up. Pinned by `test_generate_numbering_is_the_same_with_and_without_variants` and `test_generate_screen_numbering_is_stable_without_variants`.

### BUG-009 — An unrecognised menu choice re-renders silently in some submenus
* **Severity:** low
* **Reproduction:** at any submenu type a letter that is not a number.
* **Actual:** `Not a valid choice: 'x'` then the menu re-renders — correct. But
  `_numbered_choice` recurses into itself to re-ask, which is unbounded
  recursion on a stream that never ends.
* **Root cause:** `return self._numbered_choice(None, entries, back_note)  # re-ask`.
* **Files:** `ui/render/menus.py:_numbered_choice` (~line 1199).
* **Required correction:** loop instead of recursing.
* **Regression test:** a long run of invalid choices does not exhaust the stack.
* **Status:** **FIXED & VERIFIED** — `_numbered_choice` re-asks in a loop instead of recursing, so an unrecognised choice is reported and the screen survives; a script of 200 invalid choices no longer raises. Pinned by `test_many_invalid_choices_do_not_exhaust_the_stack` and `test_invalid_master_choice_is_reported_and_the_menu_survives`.
  depth; Python's recursion limit makes it unlikely in practice)

### BUG-010 — `set_representation` would crash on an empty CCD code
* **Severity:** low (currently unreachable from the menu)
* **Reproduction:** call `ConfigurationService.set_representation(key, codes="")`.
* **Actual:** `ComponentCode("")` raises `ValueTypeError`, escaping the
  `(ValueError, TypeError)` handler — the same class of bug as BUG-001.
* **Files:** `configbuilder/app/configuration_service.py:485-511`.
* **Required correction:** catch `ModelError` here too (defensive, so a future
  menu route cannot reintroduce BUG-001).
* **Status:** **FIXED & VERIFIED** — `set_representation` catches `ModelError`, so an empty CCD code is refused instead of raised. Pinned by `test_blank_ccd_representation_is_refused_not_raised`.

### BUG-011 — `GenerationService._reviewed` is shared mutable state
* **Severity:** medium
* **Reproduction:** plan a base run, then call `execute()` twice, or plan a
  variant run and execute a stale base plan.
* **Actual:** `execute(plan)` ignores the plan it is given and writes
  `self._reviewed` — whatever was planned last.
* **Root cause:** the reviewed plan is stashed on the service rather than
  carried by the returned plan object.
* **Files:** `configbuilder/app/generation_service.py:plan`, `plan_base`, `execute`.
* **Required correction:** carry the reviewed plan inside `GenerationPlan`.
* **Regression test:** executing plan A after planning B writes A's payloads.
* **Status:** **FIXED & VERIFIED** — the reviewed plan travels inside the `GenerationPlan` it belongs to (`GenerationPlan.reviewed`) instead of a shared `GenerationService._reviewed`, so executing one plan can no longer write another's bytes. Pinned by `test_execute_writes_the_plan_it_was_handed`.
  executes immediately after planning, but it is a real correctness hazard.

### BUG-012 — Batch sequence files are undocumented in the application
* **Severity:** low
* **Reproduction:** Variants → 3 Generate variants from a sequence file.
* **Expected:** the accepted format is stated on screen.
* **Actual:** the prompt says only `Sequence file (one sequence per line)`.
  The real format is: one protein sequence per line, blank lines ignored,
  duplicates rejected, non-UTF-8 rejected, invalid lines reported by line number.
* **Files:** `ui/present/strings.py:menu.ask_sequence_file`;
  `persistence/sequences.py:read_sequence_file`; `app/batch_variants.py`.
* **Required correction:** state the format and the rejection rules in the prompt.
* **Status:** **FIXED & VERIFIED** — the accepted format is stated on screen before the file picker: one protein sequence per line, blank lines ignored, duplicates and unsupported characters reported with their line numbers, and nothing created unless every line is valid. Pinned by `test_option_3_batch_from_a_sequence_file` (which asserts the on-screen format text) and `test_option_3_batch_reports_invalid_lines_by_number`.

---

### BUG-013 — The master menu's working-copy hint names an option that is not on it
* **Severity:** low (menu clarity — the same class of defect as BUG-007)
* **Reproduction:** open a job and read the master menu.
* **Expected:** a screen's hint refers to an action by the wording *that screen* displays.
* **Actual:** the hint read `re-open it any time with Open saved work`, but
  "Open saved work" is the *start screen's* option 2. On the master menu the same
  action is `6) Recover the last working copy`, so a beginner following the hint
  looked for a label that was not there.
* **Files:** `ui/present/strings.py:menu.work_held`; `ui/render/menus.py:_master_menu`.
* **Required correction:** give the master menu its own hint naming its own option,
  and keep the start screen's wording, where "Open saved work" is the real label.
* **Fix applied:** added `menu.work_held_master` (`Working copy: kept automatically — restore it any time with 'Recover the last working copy'`) and used it in
  `_master_menu`; `menu.work_held` stays on the start screen, where it is accurate.
* **Status:** **FIXED & VERIFIED** — pinned by
  `test_master_menu_hint_names_a_label_shown_on_that_menu` and
  `test_start_screen_hint_still_names_its_own_option`.

---

### BUG-014 — A multi-component ligand cannot be bonded residue by residue
* **Severity:** high (a documented AF3 workflow could not be produced at all)
* **Reproduction:** import AF3's own `examples/rnaseb_glycosylated.json` and
  generate; or add a five-code glycan and bond it at residue 2.
* **Expected:** a ligand holding N CCD codes is addressable as residues 1..N,
  which is what makes a glycan expressible.
* **Actual:** `R-BND-003` refused any ligand bond endpoint above residue 1, so
  `plan_base` returned `validation_blocked`. The official glycan example could
  not be reproduced by the builder in any way.
* **Root cause:** `check_r_bnd_003` treated every `ComponentRecord` as
  single-residue (`endpoint.residue.value != 1`). AF3 numbers a ligand's
  residues one per CCD code — `Ligand.__len__` is `len(ccd_ids)` — and its
  docs say residue is "1-based residue index *within* the chain. For
  single-residue ligands, this is simply set to 1".
* **Files:** `validation/rules/bond_rules.py`.
* **Fix applied:** the residue count is derived from the representation
  (`fold_representation`: `ByCode` → number of codes, `ByNotation` → 1) and the
  endpoint must fall in 1..N; the single-component message is unchanged.
* **Status:** **FIXED & VERIFIED** — three rule tests, the corpus glycan case,
  and AF3's parser accepting the emitted bonded glycan.

### BUG-015 — A description is dropped on import for DNA and ligand entries
* **Severity:** medium (silent data loss on a normal round trip)
* **Reproduction:** import any AF3 example that annotates a DNA strand or a
  ligand, then generate. Six of AF3's thirteen examples do.
* **Expected:** §4's `description` applies to protein, RNA, DNA and ligand
  entries alike and survives import.
* **Actual:** protein and RNA kept it; DNA and ligand lost it — although the
  importer's own `_KNOWN_FAMILY_FIELDS` advertises the field for all four.
* **Root cause:** `_import_entity` read the description *after* the ligand
  branch had already returned, and the DNA branch never passed it on.
* **Files:** `transform/from_wire.py`.
* **Fix applied:** read once before the family dispatch, then pass it to
  `ComponentRecord` and `FamilyCRecord`; absent stays `Unset` and empty stays
  `ExplicitEmpty`.
* **Status:** **FIXED & VERIFIED** — four tests, and the round trip now matches
  AF3's own files field for field (13/13).

### BUG-016 — The CCD submenu's "code(s)" route glued a multi-code ligand into one component
* **Severity:** high (the advertised multi-component ligand was unusable, and
  the emitted file named a chemistry that does not exist)
* **Reproduction:** Edit the job → Bonds, modifications & custom components →
  add a ligand → choose `CCD code(s)` → type `NAG NAG BMA MAN MAN`.
* **Expected:** the label promises "CCD code(s) — e.g. ATP, or several separated
  by spaces"; the contract's multi-component ligand (a glycan, an ion/water
  group) is a *list* of codes.
* **Actual:** `kind="ccd"` routed to `_ccds`, which read the whole text as one
  `ComponentCode`, so the stored representation was
  `ByCode(['NAG NAG BMA MAN MAN'])` and the file carried that single bogus
  component. The multi-token split existed only on the no-kind path, which the
  submenu never uses.
* **Files:** `app/configuration_service.py`.
* **Fix applied:** `_ccds` splits on whitespace, commas and semicolons for every
  route, so the submenu, the typed route and the fixtures all agree.
* **Status:** **FIXED & VERIFIED** — four tests (component list, wire
  `ccdCodes`, unchanged single-code/SMILES routes, and a bonded glycan
  generated end to end), plus AF3 accepting the emitted document.

### BUG-017 — An unusable output directory ended the session with a traceback
* **Severity:** high (a typed name killed the session; the work in progress lived
  only in the working copy)
* **How it surfaced:** playtesting the shipped CLI (``python -m configbuilder``)
  with piped stdin — the user's own surface, not the scripted console. The
  output directory was named after an existing **file**, and separately after
  ``nul``, the Windows reserved device name.
* **Expected:** the same in-menu refusal every other unusable choice gets, with
  the session still running.
* **Actual:** ``OSError`` propagated out of ``output.execute`` — both of its
  ``except`` branches re-raised — so the user saw a Python traceback and the
  process exited 1.
* **Files:** ``output/execute.py``.
* **Fix applied:** the executor reports the refusal through
  ``OutputResult.errors``, the same channel as plan conflicts, naming the path
  that failed and — when the output root itself is the obstacle — saying that it
  is a file. Only ``OSError`` is caught: a defect in this code still fails
  loudly. Per-file atomicity is unchanged, and when a later file fails after
  earlier ones were replaced the message says how many were left in place
  instead of implying a rollback.
* **Status:** **FIXED & VERIFIED** — three new unit tests keep every atomicity
  guarantee while asserting the report; two pre-existing atomicity tests moved
  from "raises" to "reports" (their real intent — no partial file, no temporary
  file, the old bytes intact — is unchanged and still asserted, and the module
  docstring records why); and one end-to-end test drives the real CLI over a pipe
  and asserts exit 0, no traceback, and nothing written.

### BUG-018 — A directory aimed at the importer was reported as "Permission denied"
* **Severity:** medium (misleading feedback: it sends the user looking for a
  permissions problem they do not have)
* **How it surfaced:** playtesting — typing a folder path at the import prompt,
  and at the batch sequence-file prompt. Both pickers *list* directories, so
  aiming at one is an ordinary slip.
* **Expected:** a refusal that names the actual mistake.
* **Actual:** Windows reports reading a directory as ``PermissionError``, and
  that text passed straight through: ``Reason: [Errno 13] Permission denied:
  '<dir>'`` for an import, ``sequence file cannot be read: [Errno 13] Permission
  denied`` for a sequence file.
* **Files:** ``app/project_service.py``, ``persistence/sequences.py``.
* **Fix applied:** both readers answer an ``isdir`` path with ``that path is a
  directory, not an AF3 JSON file`` / ``… not a sequence file``. The ordinary
  missing-file and unreadable-file paths are unchanged.
* **Status:** **FIXED & VERIFIED** — one service pin (both halves of the import
  path, with the open job untouched), one sequence-file pin, and one test that
  the missing-file message is not swallowed by the new branch.

### BUG-019 — The confirmed import installed a re-read, not what was previewed
* **Severity:** low–medium (what-you-see-is-what-you-get; only visible when the
  file changes between the confirm screen and the answer, but then the user
  commits a document they were never shown)
* **How it surfaced:** reviewing the import path after the playtest —
  ``import_json_preview`` and ``import_json_commit`` each opened and parsed the
  file, so the preview's summary and the installed job came from two
  independent reads.
* **Expected:** the screen describes the document that gets installed.
* **Actual:** commit re-read the path; a file rewritten between preview and
  confirm installed content the preview had never described, silently.
* **Files:** ``app/project_service.py``.
* **Fix applied:** the parse result is kept as the service's **pending import**
  when a preview succeeds, and ``import_json_commit`` installs that exact
  configuration; the pending import is one-shot, replaced by the next
  successful preview, cleared by a failed one, and never used for a different
  path. With no matching preview, commit reads and parses the file itself, so
  the public behaviour of a direct commit is unchanged. The five previous
  copies of the read/parse/refuse sequence collapsed into one
  ``_prepare_import`` — the same duplication that had already let the two
  halves drift over a directory path in BUG-018.
* **Status:** **FIXED & VERIFIED** — five pins: the divergence case (file
  rewritten after the preview), the no-preview fallback, one-shot consumption,
  a failed preview clearing the pending import, and a commit for a path other
  than the previewed one. The divergence pin was checked against the old
  behaviour and fails there, so it has teeth rather than merely describing the
  new code. The AF3 round trip (import → re-emit → AF3 parser) still
  reports 13/13 identical.

---

## E. Implementation Plan

Ordered by dependency. Every task names its acceptance criterion and its test.

### Phase 2 — Menu, state and input validation *(highest priority)*

| # | Task | Files | Acceptance | Test |
|---|---|---|---|---|
| 2.1 | Fix BUG-001 / BUG-010: catch `ModelError` where the model raises it | `app/configuration_service.py` | a blank PTM code is refused, never raised | menu script + service unit test |
| 2.2 | Fix BUG-004: resolve records by multiplicity membership | `app/configuration_service.py` | a 3-copy record is editable and deletable | service unit test + menu script |
| 2.3 | Fix BUG-006: restrict the PTM picker to polymers | `ui/render/menus.py`, `ui/present/strings.py` | ligands are never offered as carriers | menu script |
| 2.4 | Fix BUG-002: integer prompts give actionable messages | `ui/render/menus.py` | `abc` ⇒ registered whole-number message | menu script |
| 2.5 | Fix BUG-005: cancellation is announced | `ui/render/menus.py`, `strings.py` | Back ⇒ a cancellation notice, no record | menu script |
| 2.6 | Fix BUG-009: `_numbered_choice` loops instead of recursing | `ui/render/menus.py` | 200 invalid choices do not raise | unit test |
| 2.7 | Fix BUG-007: add an explicit save action reporting the path | `ui/render/menus.py`, `strings.py` | the option writes the JSON and prints the path | menu script + file assertion |
| 2.8 | Fix BUG-008: stable Generate numbering | `ui/render/menus.py`, `strings.py` | the same digit reaches the same handler in both states | menu script |

### Phase 3 — JSON construction and preview honesty

| # | Task | Files | Acceptance | Test |
|---|---|---|---|---|
| 3.1 | Fix BUG-003: preview runs the same validation gate | `app/generation_service.py` | empty job ⇒ refusal, not `[]` | unit + menu script |
| 3.2 | Fix BUG-011: carry the reviewed plan in the plan object | `app/generation_service.py` | `execute(A)` after planning B writes A | unit test |
| 3.3 | Verify preview == written bytes for base and variant | — | byte equality | integration test |
| 3.4 | Verify the AF3 contract for every entity type and field | — | matches `AUTHORITATIVE_SPEC.md` | golden fixtures + semantic checks |

### Phase 4 — Variants

| # | Task | Files | Acceptance | Test |
|---|---|---|---|---|
| 4.1 | Confirm base immutability across every variant route | — | base bytes unchanged after all variant operations | integration test |
| 4.2 | Confirm batch independence and reporting | `app/batch_variants.py` | variant 3 does not inherit variant 2's edit | existing + new test |
| 4.3 | Confirm concentration progression and quantities | `app/variant_service.py` | `start × factor^(n-1)`; ids unique | existing + new test |
| 4.4 | Fix BUG-012: document the batch file format on screen | `strings.py` | the prompt states the format | menu script |

### Phase 5 — Test and resolve

Run unit → integration → menu end-to-end; reproduce every defect above; fix at
the root; add a regression test per fixed defect; re-run the affected suites.

### Phase 6 — Documentation and delivery

Update §F with real results, files changed, limitations, and the acceptance
checklist; verify the launch and test commands from a clean directory.

---

## F. Final Verification Record

> Every result below is copied from actual command output in this checkout, not
> anticipated. Environment: Windows, Python 3.11.15
> (`.../venv/Scripts/python.exe`), working directory
> `C:/Users/Chris/Desktop/THESISSP`. Nothing here was measured against a live
> AlphaFold 3 installation (§F.7).

### F.1 Baseline (before any repair)

```
$ python -m pytest -q
824 passed, 1 skipped            # 0 failed, 825 collected
```

### F.2 Tests executed after repair

```
$ python -m pytest -o addopts="" -q
895 passed, 1 skipped in 60.86s (0:01:00)
```

Note on the command: `pyproject.toml` sets `addopts = "-q"`, so typing
`python -m pytest -q` doubles the quiet flag and the run prints progress dots but
**no summary line**. Both forms exit `0`; `-o addopts=""` restores the summary.
915 tests are collected, of which 1 is skipped by design.

Collection by area:

| Area | Tests | Area | Tests |
|---|---|---|---|
| `tests/unit/model` | 170 | `tests/e2e` | 49 |
| `tests/unit/ui` | 110 | `tests/architecture` | 37 |
| `tests/unit/app` | 80 | `tests/unit/persistence` | 33 |
| `tests/unit/validation` | 82 | `tests/golden` | 26 |
| `tests/unit/transform` | 77 | `tests/variant` | 20 |
| `tests/unit/identity` | 67 | `tests/serialization` | 16 |
| `tests/unit/variants` | 60 | `tests/contract` | 15 |
| `tests/unit/output` | 54 | | |

Added or extended by this audit:

* `tests/unit/ui/test_audit_regressions.py` — **26 tests** (new file), at least
  one pinning each of BUG-001…BUG-016. All pass.
* `tests/e2e/test_menu_acceptance.py` — **34 tests** (new file) driving the real
  `MenuApp` through every master-menu option via `ScriptedConsole`. All pass.
* `tests/unit/ui/test_numbered_flows.py` — the master-menu assertion updated from
  six options to seven, plus a new stable-numbering test.

The suite grew from 825 to 896 collected tests (eleven of the added tests came from the second pass, §F.11). A file-by-file delta against a
committed baseline is not computable here: `git ls-files tests` returns **0**
files, because `.gitignore` excludes `tests/`. The growth beyond the tests listed
above comes from pre-existing test files this audit also edited.

### F.3 Main menu options verified

Start screen:

| Option | Verified behaviour |
|---|---|
| 1) New job | asks `Job name (blank generates one)`, creates the job, opens the master menu |
| 2) Open saved work | restores the newest autosave (`.configbuilder/*.cbproj`) with no path ritual |
| 3) Import an AF3 JSON file | previews the file, lists unsupported fields, loads on confirm; refuses malformed, missing and unsupported input |
| 0) Exit | returns exit status 0; EOF also exits without a traceback |

Master menu (all seven options):

| Option | Verified behaviour |
|---|---|
| 1) Edit the job | three sub-options: entities, job settings, bonds/modifications/custom components |
| 2) Review configuration | status rows, entity list, variants, and a validate verdict |
| 3) Variants | create; manage (edit / duplicate / delete / preview / generate); batch from a file; quantity series |
| 4) Generate JSON | the same four rows with or without variants; an incomplete job is refused |
| 5) Save the job | plans, confirms, writes, prints `Saved to <path>`; a cancel writes nothing |
| 6) Recover the last working copy | restores the newest autosave, or reports that it is already the open job |
| 7) Import an AF3 JSON file | as on the start screen |

The master menu also states the two facts a beginner needs before touching
anything: `Variants: N`, `Working copy: kept automatically — restore it any time
with 'Recover the last working copy'`, and
`Nothing is written to disk until you save or generate.`

### F.4 Workflows verified

Two complete journeys were driven through the real application (both PASS, no
exception raised at any point). The harness is the project's own
`ScriptedConsole` feeding numbered choices and typed answers to the same
`MenuApp` a human uses.

**Journey A — new job → protein → Save the job.**
`1 New job` → name `smoke_job` → `1 Edit the job` → `1 Entities` →
`1 Add an entity` → `1 Protein` → sequence → MSA `n` → templates `n` → back to
the master menu → `5 Save the job` → `1` confirm. Result: exactly one file,
`smoke-job/smoke-job.json`, reported as written. Read back:

```
keys       = ['dialect', 'modelSeeds', 'name', 'sequences', 'version']
name       = 'smoke-job'   version = 4   dialect = 'alphafold3'
modelSeeds = [1]           sequences = 1  first record = protein
```

**Journey B — new job → protein → batch variants → generate.**
Same opening, then `3 Variants` → `3 Generate variants from a sequence file`
(the format paragraph appears before the picker) → a three-line file with a blank
line → `1 Create a variant for each entry` → `Batch applied: 3 variants
generated` → `4 Generate JSON` → `2 Generate all variant JSONs` → `y`.
Result: four files, each reported as written:

```
smoke-var/manifest.json
smoke-var/smoke-var__batch-01/smoke-var__batch-01.json
smoke-var/smoke-var__batch-02/smoke-var__batch-02.json
smoke-var/smoke-var__batch-03/smoke-var__batch-03.json
```

Each variant file carried the same five keys as the base, `name` equal to its own
file stem, `version = 4`, `dialect = 'alphafold3'`, `modelSeeds = [1]`, and
**2 sequences** — the untouched base protein plus the one protein the variant
added. The base record was verified byte-identical afterwards
(`test_base_is_byte_identical_after_variant_work`).

Beyond these two journeys, every journey listed in §C is exercised by the
acceptance suite, including: an incomplete job refused at Generate and at Save;
an overwrite refused when the bytes differ; variant management
(duplicate/delete); the quantity series; import of a valid file, a malformed
file, a missing file and a file with unsupported fields; imported jobs edited and
varied afterwards; and every cancellation path leaving the job unchanged.

### F.5 JSON schema and contract checks

| Check | Result |
|---|---|
| Document keys | exactly `dialect`, `modelSeeds`, `name`, `sequences`, `version` |
| `name` | the job slug, identical to the file stem |
| `dialect` | `alphafold3` |
| `version` | `4` by default (`DEFAULT_VERSION`) |
| `modelSeeds` | always non-empty; default `[1]`, as the spec requires |
| `sequences` | one entry per record; ions/ligands carry a CCD code; DNA expands to two records with the reverse complement |
| Variant file naming | `<slug>/<slug>__<key>/<slug>__<key>.json` |
| Manifest | `schema_version`, `builder_version`, `project_name`, `format_version`, `seed_set`, `base_fingerprint`, per-variant `key`/`label`/`file_name`/`fingerprint`/`applied_edits`, `validation_summary`, `overwrite_policy: Fail`, `path_policy: CopyIntoAssets` |
| Base immutability | base bytes unchanged after every variant route |
| Preview honesty | preview bytes equal the written file for a ready job |
| Write safety | atomic per file; the default policy `Fail` refuses to overwrite different bytes |
| Blocked writes | nothing is written when validation blocks; the findings are printed |

These were confirmed from files the application itself wrote during §F.4 and, for
the per-family details, by the pre-existing `tests/contract`, `tests/golden` and
`tests/serialization` suites, which still pass. They are all *internal* checks,
though — they compare the output against this project's own specification.
§F.11 re-checks the same claim with AlphaFold 3's own parser.

### F.6 Defects fixed

| Defect | Area | Status | Pinned by |
|---|---|---|---|
| BUG-001 | blank PTM code crashed the application | fixed | 2 tests |
| BUG-002 | raw `int()` text shown to the user | fixed | 2 tests |
| BUG-003 | JSON preview could show a document AF3 rejects | fixed | 2 tests |
| BUG-004 | multi-copy records unreachable for edit/delete | fixed | 4 tests |
| BUG-005 | abandoning an add was silent | fixed | 2 tests |
| BUG-006 | ligands offered as PTM carriers | fixed | 1 test |
| BUG-007 | no explicit save action | fixed | 3 unit + 1 e2e |
| BUG-008 | Generate numbering shifted between states | fixed | 2 tests |
| BUG-009 | an unrecognised choice recursed in some submenus | fixed | 2 tests |
| BUG-010 | an empty CCD code raised instead of being refused | fixed | 1 test |
| BUG-011 | the reviewed plan was shared mutable state | fixed | 1 test |
| BUG-012 | batch file format undocumented in the application | fixed | 2 tests |
| BUG-013 | the master-menu hint named an option not on that menu | fixed | 2 tests |
| BUG-014 | a multi-component ligand could not use its own residue numbers | fixed | 3 rule + 1 corpus |
| BUG-015 | descriptions dropped on import for DNA and ligand entries | fixed | 4 tests |
| BUG-016 | the CCD submenu glued a multi-code ligand into one component | fixed | 4 tests |
| BUG-017 | an unusable output directory raised out of the executor | fixed | 3 unit + 2 atomicity updated + 1 e2e |
| BUG-018 | a directory aimed at the importer was reported "Permission denied" | fixed | 3 tests |
| BUG-019 | the confirmed import installed a re-read, not the previewed document | fixed | 5 tests |

Nineteen defects confirmed, nineteen fixed, every one with a regression pin. No
defect was closed by weakening a check: each pin asserts the user-visible outcome
— the message, the record, or the bytes on disk. BUG-014, BUG-015 and BUG-016
were found only by §F.11's validation against AF3 itself, BUG-017 and BUG-018
only by the §F.12 playtest, and BUG-019 by reviewing the import path
afterwards; the first thirteen were found by the code-and-menu audit.

### F.7 Known limitations

* **Python 3.9 is the declared target but was not executed.** `requires-python`
  is `>=3.9` and the only interpreter available here is 3.11.15. No
  3.9-incompatible construct was introduced (the new code keeps
  `from __future__ import annotations` and adds no new syntax), but that is
  inspection, not a run.
* **No AlphaFold 3 *run* was performed** (no weights, no GPU runtime here), so
  featurisation and inference are outside this verification. AF3's own **input
  parser** *was* applied to every emitted document and to every official
  example (§F.11); a run would be the next layer, and needs hardware this
  audit does not have. The compiled `alphafold3.cpp` extensions are also absent,
  which is why the two custom-CCD documents are reported UNVERIFIED rather than
  passed (§F.11).
* **`tests/`, `fixtures/`, `testdata/` and `docs/` are git-ignored in this
  checkout** (0 tracked files under `tests/`). The new tests exist on disk and
  pass, but a `git clone` will not carry them unless the ignore rules change. The
  audit document sits at the repository root and is not ignored.
* **Interactive terminal behaviour was driven through `ScriptedConsole`,** not a
  real TTY. Line editing, arrow keys, bracketed paste and Ctrl+C at a prompt were
  not exercised; EOF at every prompt is handled and tested.
* The audit covers the CLI that *builds* AF3 input JSON. It does not cover AF3
  runtime behaviour, GPU execution, or the scientific correctness of any
  particular experiment.

### F.8 Outstanding defects

None of BUG-001…BUG-019 remains open. What is left is deliberate or out of reach
here, and is recorded rather than hidden:

1. **No "you have not written JSON yet" notice on exit** (§B.4 item 6). Not
   implemented: the configuration cannot be lost (the `.cbproj` autosave), and the
   master menu now states `Nothing is written to disk until you save or generate.`
   A future exit hint would be a nicety, not a repair.
2. **MSA/templates discoverability is handled in-flow, not by the option list.**
   Those questions are now chained straight onto the add/edit flow, with
   `Skipped — edit the entity to set it later.` as the closing note, so a user
   adding a chain is asked. The master menu still does not use the words "MSA" or
   "templates", so someone hunting for those words *before* adding an entity will
   not find them. Judged acceptable because the question now arrives on its own.
3. **Verification depth limits** — the environment limits in §F.7 (no 3.9 run,
   no AF3 model run, no compiled `alphafold3.cpp`, no real TTY) are the honest
   boundary of this verification. The one field they exclude is `userCCD`, which
   is exactly the field §F.11 reports as UNVERIFIED.

### F.9 Commands

```bash
# Launch (from the project root)
python -m configbuilder

# Tests (the summary line needs the addopts override, see F.2)
python -m pytest -q
python -m pytest -o addopts="" -q

# The audit's own suites
python -m pytest -o addopts="" -q tests/unit/ui/test_audit_regressions.py
python -m pytest -o addopts="" -q tests/e2e/test_menu_acceptance.py

# Validation against AlphaFold 3's own parser (needs the network once)
python tools/af3_validation/setup_validator.py
python tools/af3_validation/run_all.py
```

A fresh launch was verified from the project root with stdin at EOF: the banner
and the start screen print, and the process exits with status **0**.

### F.10 Acceptance checklist

| Requirement | Status |
|---|---|
| Project inspected and its real behaviour established | done (§A–§C) |
| `JSON_BUILDER_AUDIT_AND_FINALIZATION.md` created with sections A–F | done |
| Main menu audited option by option, first | done (§B) |
| Every broken / inconsistent / inaccessible builder feature identified | done (§D, 16 defects) |
| Implementation repaired according to the plan | done (§E, §F.6) |
| Actual user workflows exercised through the real menu | done (§F.4) |
| Generated JSON inspected and contract-checked | done (§F.5) |
| A regression test added per fixed defect | done (16/16, §F.6) |
| Full suite green after the final change | done (`895 passed, 1 skipped`) |
| Output checked against AlphaFold 3's own parser, with controls | done (§F.11) |
| Document updated with the actual results | done (this section) |
| Existing functionality preserved | verified: the pre-existing suite still passes and no pre-existing uncommitted change was reverted |

### F.11 Validation against AlphaFold 3's own parser

Added after the repair work above, because "this JSON is valid AF3 input" is a
claim about AlphaFold 3, not about this repository's own specification. The
parser used is the real `alphafold3.common.folding_input.Input.from_json` from
`google-deepmind/alphafold3`; the tool that drives it is
`tools/af3_validation/` and `README.md` beside it states its exact limits.

```
$ python tools/af3_validation/setup_validator.py
$ python tools/af3_validation/run_all.py
...
RESULT: PASS
  positive control : 13/13 accepted
  negative control : 8/8 rejected
  corpus           : ACCEPTED=21, UNVERIFIED=2, refused cases: none
  round trip       : 13/13 identical and accepted
```

| Stage | Result |
|---|---|
| Positive control — AF3's own `examples/*.json` | **13/13 ACCEPTED** |
| Negative control — 8 corruptions of a real AF3 example | **8/8 REJECTED**, each with AF3's own message |
| Corpus — 21 documents built by this builder's own services | **21 ACCEPTED, 0 rejected**, 2 UNVERIFIED |
| Round trip — AF3 example → this builder → AF3 parser | **13/13 identical and accepted** |

The corpus covers: all four families; a three-copy record; a PTM; a
protein↔ligand bond; a bonded five-code glycan; MSA inline and external;
templates; custom CCD inline and external; descriptions on every family;
versions 1, 2, 3 and 4; and a variant batch. The round trip compares every
AF3-visible field per chain (`sequence`, `ccdCodes`, `smiles`, `modifications`,
`description`, `unpairedMsa`, `pairedMsa`, `templates`, `unpairedMsaPath`,
`pairedMsaPath`, `mmcifPath`) between the original file and the document this
builder emits from it.

**Controls.** A harness that accepts everything proves nothing, so the parser is
first pointed at AF3's own examples (all must pass) and then at eight deliberate
corruptions of a real example — missing and empty `modelSeeds`, a wrong
`dialect`, `version: 5`, an unknown top-level key, an unknown chain key, a
sequence entry with no `id`, and a bond naming an unknown chain. All eight were
refused with AF3's own wording ("Unexpected JSON keys in: userCcd", "Invalid
chain ID(s) in bond …"), so an ACCEPTED verdict below means something.

**The two UNVERIFIED documents are the custom-CCD pair.** AF3 parses `userCCD` /
`userCCDPath` with the compiled `cif_dict` extension (`alphafold3.cpp.*`), which
AF3 builds through CMake for Linux and macOS only; this machine has no C++
toolchain. The harness stubs those extensions **to raise**, so a stubbed check can
never be reported as a pass, and those two documents are reported as not verified
rather than counted green. What *is* verified for them: AF3 reads the document,
validates every key and the mutual exclusion of `userCCD`/`userCCDPath`,
resolves the emitted path and reads the file — and then needs the extension.
(The CCD text itself is user-supplied; the builder's own decision is which field
carries it and where the file lives.)

**This stage found three real defects** — BUG-014, BUG-015 and BUG-016 — which
the code-and-menu audit above had missed. They were fixed, pinned with tests,
and every stage then passed in full.

**What it still does not establish.** AF3's model run is a later stage: reference
conformer generation, MSA pair matching, chelation and atom-name checks against
the real CCD all happen in featurisation and inference, none of which is
exercised here. A document accepted by this stage is one AF3 will *parse*; it is
not a promise about what AF3 computes from it. Atom names inside
`bondedAtomPairs`, for instance, are checked for shape and residue range only
— by AF3's parser as well as by this builder.

### F.12 Playtest at the real surface (2026-10-04)

Everything up to this point was driven through ``ScriptedConsole`` — the plan
§18.8 harness, which is not what a user has. This pass drove the shipped entry
point as a **real process**: ``python -m configbuilder`` in a temporary working
directory, stdin from a pipe, stdout redirected (the case where a terminal is
*absent*), every key sequence sent as text, and the exit status inspected. It is
the same interface the README's commands use, so anything true here is true for
a user.

| Flow driven for real | Result |
|---|---|
| New job → add protein → generate base JSON | exit 0, `job/job.json` written, `dialect`/`version`/`modelSeeds`/`sequences`/`name` as pinned |
| Add protein → MSA `y` → unpaired → **paste an alignment inline** → templates `n` → generate | MSA status `OK 1`; emitted `unpairedMsa` filled and `pairedMsa` `""` — exactly AF3's own documented example for an unpaired-only MSA |
| Batch variants from a file in a directory with a space and a non-ASCII character (`THESIS SP é`) | `Batch applied: 2 variants generated`; `batch_01`, `batch_02` |
| Import a valid AF3 file; import one from the same spaced/non-ASCII path | `JSON loaded. The job is now a normal, editable configuration.` |
| Import — malformed, empty, whitespace-only, top-level `[]`/`null`/`"x"`/`7` | each refused with its own reason and `The original file has not been modified.`; the open job kept |
| Import — a **directory** path | `that path is a directory, not an AF3 JSON file` (was `[Errno 13] Permission denied`) — BUG-018 |
| Output directory — an existing **file**; `nul`; a quoted `"good"` | in-menu refusal naming the path, exit 0, nothing written (the file and `nul` cases were tracebacks before BUG-017; the quoted case shares that code path and was observed only after the fix) |
| Output directory — valid | `Wrote good\job\job.json`; exactly one file |
| 50 × `1` sent at once (leaning on a key) | no `RecursionError`, no traceback; the menu consumed the input in order and exited 0 |
| FASTA header pasted into the sequence prompt | refused with the offending characters listed — no raw exception text |
| Every screen that needs variants, with none defined | `No variants defined yet.` on all of them |
| Recover while the open job is the working copy | `Not applied: the current job is already the most recent working copy; it is kept up to date as you edit` |
| Start screen → exit; import confirm → cancel | exit 0, no traceback, no stray output |

**What the playtest found:** BUG-017 and BUG-018 (both fixed and pinned above).
It also cleared several suspicions rather than confirming them: a path with
spaces or non-ASCII characters imports and batches correctly; an import *does*
ask for a numbered confirm and cancels silently on request (an earlier probe
read that as "nothing happened" until the confirm prompt was read properly);
and the two crashes it first suggested were the probe's own code-page mistakes,
not the application's.

**Still not exercised, and why:** a real TTY (Ctrl+C and terminal sizing are
driven by injected events in unit tests, not by a console); a locked or
permission-denied *file* target for the writer (Windows `chmod` cannot express
one, and the read-only attribute is bypassed by ``os.replace``); and concurrent
writers to the same output directory — the overwrite policy is checked at plan
time, so two runs racing between plan and write are not guarded.
