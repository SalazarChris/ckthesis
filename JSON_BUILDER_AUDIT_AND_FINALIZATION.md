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
| 7 | Add PTMs | âš ï¸ | Valid PTM works and is validated; **blank code crashes** (BUG-001); out-of-range position is accepted then caught by validation (by design, but only at generate time) |
| 8 | Configure MSA and template paths | ✅ | Protein: automatic/unpaired/paired/both/free + inline or file source. RNA: automatic/free/provided. DNA/ligand: correctly not offered |
| 9 | Load an existing JSON file | ✅ | Preview → confirm → installed; missing file, malformed JSON and unknown fields all reported |
| 10 | Edit a loaded job | ✅ | Editing works on an imported job exactly like a native one |
| 11 | Save the base job | âš ï¸ | Only via Generate. No explicit save action, no path echo outside the Generate screen (BUG-007) |
| 12 | Create variants from the base | ✅ | `base + edits`; base unchanged; change summaries rendered |
| 13 | Batch variants from a text file | ✅ | Blank lines ignored; invalid lines reported **with line numbers**; all-or-nothing |
| 14 | Concentration-style variants | ✅ | `start Ã— factor^(n-1)`; preview shown before creation; three independent specs from the same base |
| 15 | Preview the job and JSON | âš ï¸ | Works; on an empty job it prints `"sequences": []` (BUG-003) |
| 16 | Save generated JSON | ✅ | Atomic; conflict refusal names the file; identical bytes ⇒ `overwrite` |
| 17 | Recover from invalid input / interruption | âš ï¸ | Most paths recover; PTM blank code crashes; a few prompts echo raw Python exceptions (BUG-002) |
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
| 4.3 | Confirm concentration progression and quantities | `app/variant_service.py` | `start Ã— factor^(n-1)`; ids unique | existing + new test |
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

> **Corrected by §G.** The `895 passed` figure above is stale. Now that `tests/`
> is under version control the count is reconcilable, and the actual result is
> **921 passed, 1 skipped, exit 0** (922 collected). Two regression tests were
> added later, and §G.13.3 records the reconciliation against the 895 figure as
> it stood before them.

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

> **Two items below were closed by §G and are kept as the state at the time.**
> Python 3.9 *has* since been executed: **921 passed, 1 skipped on 3.9.25**,
> but only after two real 3.9 defects were fixed (§G.2)
> (§G.13.6). And `tests/`, `fixtures/`, `docs/` are no longer git-ignored
> (§G.13.1, §G.13.4), so a clone now carries the suite. The "no AF3 run"
> limitation and the interactive-TTY limitation still stand.

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
| Batch variants from a file in a directory with a space and a non-ASCII character (`THESIS SP Ã©`) | `Batch applied: 2 variants generated`; `batch_01`, `batch_02` |
| Import a valid AF3 file; import one from the same spaced/non-ASCII path | `JSON loaded. The job is now a normal, editable configuration.` |
| Import — malformed, empty, whitespace-only, top-level `[]`/`null`/`"x"`/`7` | each refused with its own reason and `The original file has not been modified.`; the open job kept |
| Import — a **directory** path | `that path is a directory, not an AF3 JSON file` (was `[Errno 13] Permission denied`) — BUG-018 |
| Output directory — an existing **file**; `nul`; a quoted `"good"` | in-menu refusal naming the path, exit 0, nothing written (the file and `nul` cases were tracebacks before BUG-017; the quoted case shares that code path and was observed only after the fix) |
| Output directory — valid | `Wrote good\job\job.json`; exactly one file |
| 50 Ã— `1` sent at once (leaning on a key) | no `RecursionError`, no traceback; the menu consumed the input in order and exited 0 |
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

## G. Release Readiness and Reproducibility (2026-10-04, later pass)

> **Contents.** Subsections are numbered F.13.1-F.13.10 for historical continuity
> with the numbered change table in F.13.1; they belong to this section. G.2 and
> G.3 carry the Python 3.9 defects and the figures as they stood then; G.4 adds a
> shadowed test and the CI gap, and G.5 carries the final counts.

> **This section supersedes every numeric claim above that it contradicts.** It
> was written after the workspace was actually put under version control, a fresh
> clone was made, Python 3.9 was installed and the AlphaFold 3 parser suite was
> re-run. Where the earlier text says "895 passed, 1 skipped", "Python 3.9 was not
> executed", or "tests/ ... are git-ignored in this checkout", this section is the
> current record. Nothing in sections A-F was rewritten: the earlier text is kept
> so the difference between what was claimed and what is reproducible stays
> visible. The subsection numbers below are kept as F.13.x to avoid renumbering
> references inside this section.

Environment: Windows, CPython 3.11.15, working directory
`C:/Users/Chris/Desktop/THESISSP`, repository `main`. Python 3.9.25 was
downloaded with `uv` for the compatibility run.

#### F.13.1 What changed, and why

| # | Change | Reason (evidence) |
|---|---|---|
| 1 | Committed the nineteen defect repairs already sitting in the working tree (17 modified modules) as `00d862f` | `git status` showed them uncommitted; an accidental `git checkout`/`reset` would have destroyed the entire audit repair. Nothing was reverted or altered — the diff was committed verbatim. |
| 2 | Stopped ignoring `tests/`, `fixtures/` and `docs/` (`fcdb090`) | `git check-ignore -v` blamed `.gitignore:32-35`; `git ls-files tests` returned **0** files, so the suite the audit reports on existed in no clone. 143 files / 703 KB are now tracked. |
| 3 | Kept `testdata/` ignored, but anchored the rule as `/testdata/` | It holds 36 MB of MSA dumps (`adk_msa_data.json` 23.4 MB, `ubiquitin_msa_data.json` 12.0 MB) that no test, fixture or runtime module reads (HANDOFF.md records "referenced by no current test"). Root-anchoring keeps it from ever matching `tests/fixtures/`. |
| 4 | Tracked `AUTHORITATIVE_SPEC.md` and `DOMAIN_MAPPING.md` (`6a5619d`) | **Found by the fresh-clone check, not by inspection.** Collecting `tests/contract/test_catalogue_traceability.py` raised `FileNotFoundError` and pytest exited **2** before running one test, because that file reads both. They are test input, so they were tracked rather than the test weakened or skipped. |
| 5 | Kept `IMPLEMENTATION_PLAN.md`, `HANDOFF.md`, `CHECKLIST.md` untracked, now by explicit decision | They are read by nothing (verified by scanning `tests/`, `fixtures/`, `tools/`, `configbuilder/`). `.gitignore` now records the split and its reason instead of excluding everything by accident. |
| 6 | Added `.venv*/` to the ignore rules | So a convenience virtualenv such as `.venv39py39` can never be staged. No virtualenv, bytecode, generated result or dataset is tracked. |
| 7 | Added `.gitattributes` pinning LF for the two byte-compared fixture trees (`2e348af`) | A third fresh clone failed three golden tests: `core.autocrlf=true` (system default here) rewrote every LF fixture to CRLF, so the committed bytes could not equal the encoder's. Detail in §F.13.1.1. |
| 8 | Dropped the `staticmethod` wrapper on `describe_edit`'s seven attached helpers (`23df6c4`) | **DEFECT-PY39-1.** `staticmethod` objects are not callable before Python 3.10, so on the declared floor (3.9) 29 tests failed and variant alignment/template/description edits could not round-trip. Found by running 3.9 for the first time. §G.2.1. |
| 9 | Replaced `Path.glob("*/")` with `iterdir()` + `is_dir()` in the golden provenance guard; added three regression tests (`23df6c4`) | **DEFECT-PY39-2.** On 3.9 that glob also yields plain files, so `external/.gitkeep` was reported as a fixture with no `provenance.json`. §G.2.2. |
| 10 | Renamed a shadowed test in `tests/serialization/test_encode.py` and added `tests/architecture/test_suite_integrity.py` (`4e755d7`) | **DEFECT-SUITE-1.** Two module-level functions shared the name `test_encode_to_file_writes_exact_bytes`, so one body never ran. §G.4.1. |
| 11 | Added a `test` job running the full suite to `.github/workflows/ci.yml` (`4e755d7`) | **DEFECT-CI-1.** CI asserted Python 3.9 compliance without ever running the suite, which is why DEFECT-PY39-1 passed there. §G.4.2. |

Three of these changes are code or test **edits**, not tracking decisions: items 7,
8 and 9. Items 1-6 are Git and documentation housekeeping. No change was made to
`configbuilder/` for any purpose other than DEFECT-PY39-1, and each of the three
carries a regression pin (§G.2.1, §G.2.2).

#### F.13.1.1 Line endings: `.gitattributes` added, and why

A second defect was found the same way, and it is the more serious one for any
Windows user. `core.autocrlf` is `true` on this machine (set at **system**
scope), and the repository had no `.gitattributes`. Git therefore rewrote every
LF file to CRLF on checkout. Three tests failed in the fresh clone for that
reason alone, while the original checkout passed:

```console
$ .venv\Scripts\python -m pytest -o addopts="" -q     # in the clone
FAILED tests/golden/test_af3_pipeline_fixtures.py::test_committed_fixtures_match_a_fresh_run
FAILED tests/golden/test_golden_fixtures.py::test_every_project_fixture_matches_its_recipe
FAILED tests/golden/test_golden_fixtures.py::test_golden_files_follow_the_encoding_policy
3 failed, 911 passed, 1 skipped in 57.63s
=== EXIT: 1 ===
```

The assertions are byte-exact, and say so in their own messages:

```
E  AssertionError: golden.json
E  assert b'\r' not in b'{\r\n  "name": "comprehensive_families_v4",\r\n ...'

E  AssertionError: comprehensive_families_v4: golden bytes differ from a fresh
E  encode(to_wire()) run; review the diff and regenerate deliberately
E  assert b'{\n  "name"...sion": 4\n}\n' == b'{\r\n  "nam...": 4\r\n}\r\n'
E  At index 1 diff: b'\n' != b'\r'
```

Measured directly, on the same file in both trees:

```console
fixtures/golden/project/comprehensive_families_v4/golden.json
   original: 1212 bytes,  0 CR   |   clone: 1288 bytes, 76 CR
fixtures/golden/project/minimal_protein_v3/golden.json
   original:  217 bytes,  0 CR   |   clone:  233 bytes, 16 CR
tests/fixtures/af3_pipeline/test01_protein_minimal/.../test01-protein-minimal.json
   original:  238 bytes,  0 CR   |   clone:  256 bytes, 18 CR
```

So the repository was **not** reproducible on a default Windows Git install: the
committed golden fixtures could not match the encoder output after checkout, so
three tests could never pass there. The commit before this pass stored LF, which
is what made the original checkout pass; nothing recorded that requirement.

**Fix.** A new `.gitattributes` pins the two byte-compared trees, and only those:

```gitattributes
* text=auto eol=lf                       # default: normalise, never gain CR

fixtures/golden/**             -text     # golden.json vs a fresh encode()
tests/fixtures/af3_pipeline/** -text     # committed docs vs a fresh generation
```

`-text` disables all end-of-line conversion, so the bytes in the repository are
the bytes on disk on every platform. It is deliberately **not** applied to the
rest of the tree: `-text` also suppresses the `\\r\\n`-to-`\\n` cleanup at commit
time, and losing that on ordinary sources would trade one line-endings bug for
another. Verified per path with `git check-attr`:

```console
$ git check-attr text eol -- fixtures/golden/project/minimal_protein_v3/golden.json
...: text: unset | ...: eol: lf
$ git check-attr text eol -- configbuilder/app/cli.py
...: text: auto | ...: eol: lf
```

An earlier version of the file put the default **after** the specific rules. That
was wrong: gitattributes resolves per attribute with the **last matching line
winning**, so the default silently overrode `-text`. It was caught by reading
`git check-attr` output rather than assuming, and corrected by moving the default
first. The file records that ordering constraint in a comment.

Two further corrections were made while fixing this, both to avoid unnecessary
churn rather than to satisfy a test: an initial broader rule would have rewritten
`fixtures/projects/*.cbproj` and a `.txt` fixture from LF to CRLF for no benefit
(no test compares those bytes), so it was narrowed to the two trees above and the
index entries for those three files were restored to their committed bytes.

#### F.13.2 Exact commands and their real results

> Measured at `2e348af`, **before** the three regression tests of §G.2 and before
the two 3.9 defect fixes. The final figures are in §G.3.

```console
$ git status --porcelain=v1            # before any change: 17 M + 2 ??
$ git check-ignore -v tests fixtures testdata docs
.gitignore:32:tests/    tests
.gitignore:33:fixtures/ fixtures
.gitignore:34:testdata/ testdata
.gitignore:35:docs/     docs
$ git ls-files | ...                   # before: tests = 0 files
```

After the ignore correction:

```console
$ python -m pytest -q
...................................................                      [100%]
=== EXIT: 0 ===                        # 914 passed, 1 skipped (summary suppressed, see F.2)

$ python -m pytest -o addopts="" -q
914 passed, 1 skipped in 42.53s
=== EXIT: 0 ===

$ python -m pytest -o addopts="" --collect-only -q
915 tests collected in 1.06s
=== EXIT: 0 ===
```

The suite is **922 collected: 921 passed, 1 skipped, 0 failed, exit 0**. The
single skip is by design and names its platform reason:

```console
$ python -m pytest -o addopts="" -rs -q
SKIPPED [1] tests\unit\persistence\test_sequence_files.py:50:
    Windows cannot express a read-denied file through chmod
```

#### F.13.3 The audit's numbers, restated

> This table reconciles the pre-fix count (914) with the audit's original 895.
Both were superseded by 917 once the §G.2 regression tests were added; see §G.3.

| Claim in §F | Reproduced now | Note |
|---|---|---|
| "895 passed, 1 skipped" | **No** — actual is **914 passed, 1 skipped** | §F.2's note said a file-by-file delta "is not computable" while `tests/` was untracked. It is computable now, and the real total is higher: 915 collected, not 896. The earlier figure under-counted because it was never reconciled against a committed baseline. |
| "915 tests are collected, of which 1 is skipped" | **Yes** — 915 collected | This sentence in §F.2 was correct; the "895 passed" line above it was the stale one. |
| "Collection by area" table | Consistent | Per-file collection now matches: `tests/unit/model` 170, `tests/unit/ui` 110, `tests/unit/validation` 82, `tests/unit/app` 80, `tests/unit/transform` 77, `tests/unit/identity` 67, `tests/unit/variants` 60, `tests/unit/output` 54, `tests/e2e` 49, `tests/architecture` 37, `tests/unit/persistence` 35, `tests/golden` 26, `tests/variant` 20, `tests/serialization` 16, `tests/contract` 15. |
| `tests/unit/ui/test_audit_regressions.py` — 26 tests | **Yes** | 26 collected, all pass. |
| `tests/e2e/test_menu_acceptance.py` — 34 tests | **Yes** | 34 collected, all pass. |

Note on the documented command: `pyproject.toml` sets `addopts = "-q"`, so
`python -m pytest -q` doubles the flag and prints progress dots with **no
summary line**. It still exits **0**. `-o addopts=""` restores the summary.
Both forms were run in this pass.

#### F.13.4 Git tracking and the fresh-clone check

Before: `git ls-files` carried only `configbuilder/` (72 files), `pyproject.toml`
and `.github/`. Nothing else.

After (`git ls-files` at `6a5619d`):

| Path | Files |
|---|---|
| `tests/` | 125 (including 39 checked-in AF3 fixture documents) |
| `configbuilder/` | 72 |
| `fixtures/` | 11 |
| `tools/af3_validation/` | 4 |
| `docs/` | 2 (`CONTRACT_PIN.md`, `PROJECT_AUDIT.md`) |
| root | `AUTHORITATIVE_SPEC.md`, `DOMAIN_MAPPING.md`, `JSON_BUILDER_AUDIT_AND_FINALIZATION.md`, `pyproject.toml`, `.gitignore`, `.github/` |

**Fresh clone, actually performed** — `git clone --no-hardlinks` into a separate
directory outside the workspace, a seeded virtualenv, then `pip install -e ".[dev]"`
and the suite:

```console
# attempt 1 — FAILED, and this is the point of running it
$ git clone --no-hardlinks . %TEMP%\cb-freshclone
$ cd %TEMP%\cb-freshclone && uv venv --python 3.11 --seed .venv
$ .venv\Scripts\python -m pip install -e ".[dev]"
$ .venv\Scripts\python -m pytest -o addopts="" -q
ERROR collecting tests/contract/test_catalogue_traceability.py
FileNotFoundError: [Errno 2] No such file or directory:
  '.../cb-freshclone/AUTHORITATIVE_SPEC.md'
!!! Interrupted: 1 error during collection !!!
=== EXIT: 2 ===
```

That failure is what produced change 4 in §F.13.1. After tracking the two
contract documents, a **second, brand-new** clone was made (not a reuse of the
first, which its own checkout had already contaminated):

```console
$ git clone --no-hardlinks . %TEMP%\cb-freshclone2
$ cd %TEMP%\cb-freshclone2 && uv venv --python 3.11 --seed .venv
$ .venv\Scripts\python -m pip install -e ".[dev]"
$ .venv\Scripts\python -m pytest -o addopts="" -q
3 failed, 911 passed, 1 skipped in 57.63s
=== EXIT: 1 ===
```

**Do not read that run as a pass.** Collection worked this time, but three golden
tests failed on CRLF line endings — the defect recorded in §F.13.1.1.
A third clone was then made, after .gitattributes was added and the index line
endings were restored to the bytes the tests assert. That final run is the only
one worth quoting, and it is in §F.13.10.


#### F.13.5 Installation and launch, as documented

`pyproject.toml` declares no runtime dependencies, so installation is a bare
`pip install`. In a seeded 3.11 virtualenv, from a working directory that is not
the source tree:

```console
$ uv venv --python 3.11 --seed .venv
$ .venv\Scripts\python -m pip install "C:/Users/Chris/Desktop/THESISSP"
$ .venv\Scripts\python -m pip show configbuilder
Name: configbuilder    Version: 0.1.0    Requires:            # no dependencies
$ .venv\Scripts\python -c "import configbuilder, configbuilder.app.cli; print('import OK')"
import OK
$ .venv\Scripts\configbuilder.exe < NUL ; $LASTEXITCODE
  1) New job / 2) Open saved work / 3) Import an AF3 JSON file / 0) Exit
Select:  Interrupted — returning to the menu.
=== EXIT: 0 ===
$ .venv\Scripts\python -m configbuilder < NUL ; $LASTEXITCODE
(same start screen, same exit)
=== EXIT: 0 ===
```

Both documented entry points install, start, render the start screen and exit
**0** with stdin at EOF, from outside the source tree. `Requires:` is empty:
the claim that the core builder runs on the standard library alone holds for a
real install.

#### F.13.6 Python-version coverage

| Interpreter | Available | Suite run | Result |
|---|---|---|---|
| **3.9.25** | yes — downloaded with `uv` for this pass | **yes** | **921 passed, 1 skipped, exit 0** (final; see §G.5) |
| 3.11.15 | yes (project interpreter) | yes | 921 passed, 1 skipped, exit 0 |
| 3.12.7 | yes (Anaconda) | no | not exercised |
| 3.13.2 | yes (uv) | no | not exercised |

Python 3.9 is the declared floor (`requires-python = ">=3.9"`) and was the only
version §F.7 recorded as *not executed*. It has now been executed:

```console
$ uv venv --python 3.9 --seed .venv39py39
Downloaded cpython-3.9.25-windows-x86_64-none (21.7MiB)
$ .venv39py39\Scripts\python -c "import sys; print(sys.version)"
3.9.25 (main, Oct 31 2025, 22:56:13) [MSC v.1929 64 bit (AMD64)]
$ .venv39py39\Scripts\python -m pip install pytest hypothesis
$ .venv39py39\Scripts\python -m pytest -o addopts="" -q
921 passed, 1 skipped in 44.02s
=== EXIT: 0 ===
```

This is a run, not an inspection. The CI matrix (`.github/workflows/ci.yml`)
gates on 3.9 on Ubuntu and Windows, and now runs the suite rather than a
smoke test (§G.4.2); the local run agrees with it on Windows.

The figures in this subsection are the ones measured when it was written.
§G.5 carries the final counts after §G.4 recovered a shadowed test and added
three integrity tests: 922 collected, 921 passed, 1 skipped.

#### F.13.7 AlphaFold 3 parser validation, re-run

The tooling was preserved unchanged (`tools/af3_validation/`) and is now tracked
by Git for the first time. Re-run in this pass:

```console
$ python tools/af3_validation/setup_validator.py
AF3 source already present: %TEMP%\af3-validator\alphafold3-main
parser dependencies already installed: %TEMP%\af3-validator\site
ready: .../alphafold3/common/folding_input.py
dialect alphafold3, versions (1, 2, 3, 4)

$ python tools/af3_validation/run_all.py
RESULT: PASS
  positive control : 13/13 accepted
  negative control : 8/8 rejected
  corpus           : ACCEPTED=21, UNVERIFIED=2, refused cases: none
  round trip       : 13/13 identical and accepted
  NOTE: 2 corpus document(s) are UNVERIFIED, not passed
=== EXIT: 0 ===
```

Identical to §F.11, including both controls. Sample of the negative control's
own wording, which is what makes an ACCEPTED verdict meaningful:

```
REJECT  unsupported version 5      ValueError: AlphaFold 3 input JSON has unsupported version: 5, expected one of (1, 2, 3, 4).
REJECT  unknown top-level key      ValueError: Unexpected JSON keys in: userCcd
REJECT  sequence entry without an id  ValueError: ... sequences with unset IDs.
REJECT  bond naming an unknown chain  ValueError: Invalid chain ID(s) in bond [['Z', 1, 'CA'], ['A', 1, 'CA']]
```

**`userCCD` and `userCCDPath` remain UNVERIFIED** and are not counted as passes,
exactly as before:

```
UNVERIFIED user_ccd_inline_v3\case\case.json
      stubbed compiled extension needed: alphafold3.cpp.cif_dict.parse_multi_data_cif
UNVERIFIED user_ccd_external_v3\case\case.json
      stubbed compiled extension needed: alphafold3.cpp.cif_dict.parse_multi_data_cif
```

Nothing here was upgraded. The reason is unchanged and environmental: AF3 parses
those two fields through `alphafold3.cpp.cif_dict`, which AF3 ships CMake targets
for on Linux/macOS only, and this machine has no C++ toolchain. The harness stubs
that extension **to raise**, so a stubbed check can never report a pass. Parser
acceptance also still says nothing about featurisation or inference (§F.11).

#### F.13.8 Remaining limitations

1. **`userCCD` / `userCCDPath` — UNVERIFIED.** Unchanged, and now explicitly
   carried forward. Blocked on AF3's compiled CIF parser.
2. **No AF3 model run.** No weights, no GPU runtime. Featurisation, MSA pair
   matching, reference conformers and inference are outside every check here.
   Parser acceptance means "AF3 will parse this", never "AF3 will run this".
3. **Python 3.12 and 3.13 unexercised.** Interpreters exist; only 3.9 and 3.11
   were run. `requires-python` is `>=3.9`, so this is a coverage gap above the
   floor, not a breach of it.
   Note that the 3.9 run was not a formality: it exposed two real defects
   (§G.2), one of which broke variant editing on that interpreter. The 3.12/3.13
   gap should be treated as carrying the same risk until those interpreters are
   actually run, not assumed safe because 3.11 passes.
4. **No real TTY.** Interactive behaviour is driven through `ScriptedConsole`
   and piped stdin. Line editing, arrow keys, bracketed paste, terminal resizing
   and Ctrl+C at a prompt remain unexercised (§F.7, §F.12).
5. **Concurrent writers unguarded.** The output overwrite policy is checked at
   plan time, so two runs racing between plan and write are not protected.
6. **`IMPLEMENTATION_PLAN.md`, `HANDOFF.md` and `CHECKLIST.md` are untracked by
   decision.** A reader of a clone does not get them; the `§` citations in
   `configbuilder/` docstrings point at them. This is a documentation-completeness
   gap, not a reproducibility one — nothing reads them.
7. **`testdata/` is untracked** (36 MB, read by nothing). If it is ever needed as
   a fixture, it must be added deliberately.
8. **A sandbox-only note, not a project defect.** The first suite runs of this
   pass failed with 184 setup errors from Windows permission denials on temp
   directories, in the confined DSH session. A bundled ACL diagnostic
   (`diagnose-windows-sandbox-acl`) was run against `.pytest_cache` and returned
   `NOT_THIS_CLASS` / `nextAction: stop`: the ACLs were healthy and the denial
   came from the sandbox itself. No project code caused this and no project file
   was changed for it; the run under full access succeeded. Recorded because the
   raw transcript shows those errors.

#### F.13.9 Release checklist

Commands are run from the project root. `-o addopts=""` is required only to see
the summary line (§F.2); the exit code is the same either way. Every figure below
was re-measured at `23df6c4` with a clean working tree.

| # | Gate | Command | Status |
|---|---|---|---|
| 1 | Working tree clean, all repairs committed | `git status --porcelain` | **PASS** — empty at `23df6c4` |
| 2 | Suite in the working tree, 3.11.15 | `python -m pytest -o addopts="" -q` | **PASS** — 921 passed, 1 skipped, exit 0 |
| 3 | Suite with the summary suppressed | `python -m pytest -q` | **PASS** — exit 0 |
| 4 | Collection count | `python -m pytest -o addopts="" --collect-only -q` | **PASS** — 922 collected |
| 5 | Suite under the declared floor, 3.9.25 | `.venv39py39\Scripts\python -m pytest -o addopts="" -q` | **PASS** — 921 passed, 1 skipped, exit 0 (after G.2) |
| 6 | Suite in a fresh clone, 3.11.15 | `git clone --no-hardlinks .`, `pip install -e ".[dev]"`, pytest | **PASS** — 921 passed, 1 skipped, exit 0 |
| 7 | Suite in the same fresh clone, 3.9.25 | clone, `.venv39`, pytest | **PASS** — 921 passed, 1 skipped, exit 0 |
| 8 | Clone carries the suite and fixtures | `git ls-files` in the clone | **PASS** — 221 files, 125 under `tests/` |
| 9 | Clone is clean and fixtures are CR-free | `git status --porcelain`; byte inspection | **PASS** — empty; CR=0 |
| 10 | Install from a clean environment | `uv venv --python 3.11 --seed .venv`, `pip install <root>` | **PASS** — 0.1.0, no runtime dependencies |
| 11 | Both documented entry points start and exit cleanly | `configbuilder < NUL`; `python -m configbuilder < NUL` | **PASS** — exit 0 each |
| 12 | AF3 parser: controls, corpus, round trip | `python tools/af3_validation/setup_validator.py`; `python tools/af3_validation/run_all.py` | **PASS** — 13/13, 8/8, 21 accepted, 13/13 identical |
| 13 | `userCCD` / `userCCDPath` parser check | same | **UNVERIFIED** — needs AF3's compiled CIF parser |
| 14 | Python 3.12 / 3.13 | — | **NOT RUN** — coverage gap above the declared floor |
| 15 | AF3 model run / featurisation / inference | — | **OUT OF SCOPE** — no weights, no GPU runtime |
| 16 | Real TTY behaviour | — | **NOT RUN** — driven through `ScriptedConsole` and piped stdin only |
| 17 | CI actually runs the suite | `python -m pytest -o addopts="" -q` in `.github/workflows/ci.yml` | **PASS** — job added; validated by YAML parse and local run (§G.4.2) |
| 18 | No test silently shadowed | `tests/architecture/test_suite_integrity.py` | **PASS** — detector proven non-vacuous (§G.4.1) |

**Release recommendation.** The project is reproducible from a clone on the
declared Python floor: the suite, its fixtures, the two contract documents it reads
and the AF3 validation tooling all travel with the repository; the tree is clean;
the suite is green on **both 3.9.25 and 3.11.15**, in the working tree and in two
independent fresh clones; and both documented entry points install, start and exit
cleanly from outside the source tree.

Getting there required fixing two defects that this pass found by running Python
3.9 rather than reasoning about it (G.2), and one line-endings defect that only a
fresh Windows clone exposed (F.13.1.1). Before those fixes the "green on 3.9" claim
was **false**: 30 tests failed there.

It is **not** verified for AF3 featurisation or inference, and the two custom-CCD
documents remain **UNVERIFIED** rather than passed. Treat `userCCD`/`userCCDPath`
as untested, and treat Python 3.12/3.13 and real-TTY interaction as untested.

#### F.13.10 Final fresh-clone verification (the result that counts)

Run **after** `.gitattributes` (F.13.1.1) and after the index line endings were
restored to the bytes the tests assert. A third clone, from scratch, outside the
workspace:

```console
$ git clone --no-hardlinks . %TEMP%\cb-freshclone3
Cloning into 'C:\Users\Chris\AppData\Local\Temp\cb-freshclone3'...
done.
clone exit=0

$ git -C %TEMP%\cb-freshclone3 log --oneline -1
2e348af Pin line endings for the byte-exact fixtures in a .gitattributes

$ git -C %TEMP%\cb-freshclone3 status --porcelain
                                   # empty: the clone is clean

$ git -C %TEMP%\cb-freshclone3 ls-files | measure
221 tracked files, of which 125 are under tests/

$ # the fixtures arrive as the bytes the encoder emits
fixtures/golden/project/comprehensive_families_v4/golden.json   1212 bytes CR=0
fixtures/golden/project/minimal_protein_v3/golden.json            217 bytes CR=0
tests/fixtures/af3_pipeline/test01_protein_minimal/...json        238 bytes CR=0
fixtures/projects/legacy_v0.cbproj                               4758 bytes CR=0

$ uv venv --python 3.11 --seed .venv && .venv\Scripts\python -m pip install -e ".[dev]"
install exit=0

$ .venv\Scripts\python -m pytest -o addopts="" -q
........................................................................ [  7%]
... (13 progress lines) ...
921 passed, 1 skipped in 51.10s
=== FRESH CLONE EXIT: 0 ===
```

This is the pass that justifies the reproducibility claim. It is worth noting
how it was obtained: the first clone failed collection, the second failed three
golden tests, and each failure produced a real fix. A clone made after the first
fix would have been reported green only by skipping the re-run.

#### G.2 Python 3.9: two real defects, found by running it at last

Section F.7 recorded Python 3.9 as **not executed** and argued from inspection
that no 3.9-incompatible construct had been introduced. That reasoning was wrong.
Running the suite on **3.9.25** produced **30 failures** on the first attempt:

```console
$ uv venv --python 3.9 --seed .venv39py39
$ uv pip install --python .venv39py39\Scripts\python.exe -e ".[dev]" pytest hypothesis
$ .venv39py39\Scripts\python -m pytest -o addopts="" -q
30 failed, 884 passed, 1 skipped in 50.73s
=== EXIT: 1 ===
```

Every one of those 30 passed on 3.11.15 against the same working tree at the same
commit. They are not a 3.9 curiosity: they are two defects, one of which breaks a
shipping code path.

##### G.2.1 DEFECT-PY39-1 — `staticmethod` objects are not callable before 3.10

**Where.** `configbuilder/variants/edits.py`, the seven helpers attached to
`describe_edit` at the end of the module.

`describe_edit` is a *function*, not a class. It attaches its helpers to itself so
the dispatcher can reach them without adding seven public names to the module
namespace. They were attached through `staticmethod()`:

```python
describe_edit._alignment = staticmethod(_alignment)   # before
```

There is no bound-method descriptor on a function for `staticmethod` to
neutralise, and the `staticmethod` object only became callable **itself** in
Python 3.10. On 3.9 the call site in the dispatcher therefore raised:

```
configbuilder\variants\edits.py:741: in describe_edit
    return {**base, "alignment": describe_edit._alignment(edit._alignment)}
E   TypeError: 'staticmethod' object is not callable
```

**Impact on the declared floor.** 29 of the 30 failures came from this one family.
Anything that describes or persists a variant **alignment, template, description
or component representation** goes through these helpers, so on Python 3.9 those
variants could not be round-tripped at all. The affected suites were
`tests/unit/variants/test_edits.py`, `tests/unit/ui/test_menu.py`,
`tests/e2e/test_menu_acceptance.py` and 21 of the 26 tests in
`tests/golden/test_af3_pipeline_fixtures.py`.

`pyproject.toml` declares `requires-python = ">=3.9"` and
`.github/workflows/ci.yml` gates on 3.9 — but that job only installs, compiles,
imports and runs a pipeline smoke, none of which reaches `describe_edit`. So this
class of defect was invisible to the pipeline as written.

**Fix.** Assign the helpers bare. The namespace stays tidy, and this is what the
call sites always assumed:

```python
describe_edit._alignment = _alignment   # after
```

**Regression pin.** `test_describe_edit_helpers_are_plain_callables_not_staticmethods`
in `tests/unit/variants/test_edits.py` asserts each attached helper is *not* a
`staticmethod` and *is* the module-level function. It is deliberately written
against the attribute rather than by calling the helper, because a plain call
passes on 3.10+ even with the wrapper present and would prove nothing on the
interpreter that normally runs the suite here.

The pin was verified to be non-vacuous: the wrapper was temporarily restored, the
test **failed** with `AssertionError: _presence is wrapped in staticmethod; it is
not callable on Python 3.9`, and it passed again once the wrapper was removed.

##### G.2.2 DEFECT-PY39-2 — `Path.glob("*/")` also yields files on 3.9

**Where.** `tests/golden/test_golden_fixtures.py::test_every_golden_declares_provenance`.

On Python 3.9 `Path.glob("*/")` yields plain files as well as directories; pathlib
corrected that in 3.11. `fixtures/golden/external/` is legitimately empty and held
open by a `.gitkeep` placeholder, so the guard reported:

```
E   AssertionError: .gitkeep: external fixture without provenance.json
```

**Impact.** Test-only, and a false failure rather than a missed defect: the
directory is documented as reserved for deployment-observed fixtures that do not
exist yet (the Phase 0 probe is still pending). But it made the suite red on 3.9.

**Fix.** `iterdir()` plus an explicit `is_dir()` filter. The assertion that every
external fixture carries its `provenance.json` is unchanged, and a new test
(`test_external_placeholder_is_a_file_and_not_mistaken_for_a_fixture`) pins the
placeholder's nature so the guard cannot regress silently.

##### G.2.3 What the 3.9 run cost, and what it bought

| | Before (3.9.25) | After |
|---|---|---|
| Tests passing | 884 | **917** |
| Tests failing | 30 | **0** |
| Skipped | 1 | 1 |
| Suite exit code | 1 | **0** |
| 3.11.15, same commit | 914 passed, 0 failed | 917 passed, 0 failed |

The count rose from 914 to 917 because this pass added three regression tests (two
for DEFECT-PY39-1, one for DEFECT-PY39-2). Collection is 918.

Two process lessons, recorded because they are the reason this pass exists:

1. **"Compatible by inspection" was not evidence.** The audit stated that no
   3.9-incompatible construct had been introduced. One was present, and it was not
   new syntax but a runtime protocol change — exactly what inspection does not
   catch.
2. **A green CI job on 3.9 would not have caught it either.** The CI pipeline never
   calls the affected code. A version claim is only as good as the commands behind
   it; F.9 documents `python -m pytest`, and that is what had to be run.

#### G.3 Final verification numbers (supersede G.1 and F.13)

Everything below was measured at `23df6c4` with a clean working tree.

| Check | Command | Result |
|---|---|---|
| Collection | `python -m pytest -o addopts="" --collect-only -q` | 922 collected |
| Suite, 3.11.15 | `python -m pytest -o addopts="" -q` | **921 passed, 1 skipped**, exit 0 |
| Suite, 3.11, summary suppressed | `python -m pytest -q` | exit 0 |
| Suite, 3.9.25 | `.venv39py39\Scripts\python -m pytest -o addopts="" -q` | **921 passed, 1 skipped**, exit 0 |
| Fresh clone, 3.11.15 | clone + `pip install -e ".[dev]"` + pytest | **921 passed, 1 skipped**, exit 0 |
| Fresh clone, 3.9.25 | same clone, `.venv39`, pytest | **921 passed, 1 skipped**, exit 0 |
| Fresh clone contents | `git ls-files` | 221 files, 125 under `tests/` |
| Fresh clone cleanliness | `git status --porcelain` | empty |
| Fixture line endings in the clone | byte inspection | CR-free |
| Install and both entry points | `pip install <root>`; `configbuilder < NUL`; `python -m configbuilder < NUL` | exit 0 each |
| AF3 parser suite | `python tools/af3_validation/run_all.py` | PASS — 13/13, 8/8, 21 accepted, 13/13 identical |
| `userCCD` / `userCCDPath` | same | **UNVERIFIED** — needs AF3's compiled CIF parser |
| Python 3.12 / 3.13 | — | **NOT RUN** |
| AF3 featurisation / inference | — | **OUT OF SCOPE** — no weights, no GPU runtime |

The single skip is `tests/unit/persistence/test_sequence_files.py:50`, by design:
"Windows cannot express a read-denied file through chmod".

#### G.4 A shadowed test, and a CI job that could not see the 3.9 defect

Two further findings, both surfaced by work in this pass rather than by reading
code. The final counts in G.3 are superseded by G.5.

##### G.4.1 DEFECT-SUITE-1 — a test that had never run

`tests/serialization/test_encode.py` defined
`test_encode_to_file_writes_exact_bytes` **twice**, at lines 56 and 115:

```python
def test_encode_to_file_writes_exact_bytes(tmp_path):   # line 56
    target = tmp_path / "out.json"
    encode_to_file(_document(), target)
    raw = target.read_bytes()
    assert raw == encode(_document())
    assert b"\r" not in raw                  # <-- this never executed

...
def test_encode_to_file_writes_exact_bytes(tmp_path):   # line 115, wins
    target = tmp_path / "job.json"
    encode_to_file(_document(), target)
    assert target.read_bytes() == encode(_document())
    assert not (tmp_path / "job.json.bak").exists()
```

Python keeps the last definition, so pytest collected **one** test. The first
body never ran: the assertion that `encode_to_file` writes bytes containing no
CR — the file-write half of the LF encoding policy — had no coverage at all.

**Found by** running `ruff check --select E4,E7,E9,F tests` while deciding
whether to widen the lint gate. Ruff's `F811` (redefinition of an unused name)
pointed straight at it. It was not found by the audit, by the suite itself, or by
CI, and it could not have been: a shadowed test keeps the suite green.

**Fix.** Renamed to `test_encode_to_file_bytes_have_no_cr`. Assertions unchanged.
Collection for that file went 14 → 15, which is the recovered coverage.

**Regression pin.** A new `tests/architecture/test_suite_integrity.py` parses
every test module with `ast` and fails if any module-level `test_*` name is
defined twice. Two companion tests stop it from being vacuous:

* `test_the_detector_would_catch_a_collision` parses a synthetic module and
  requires exactly the two module-level definitions to be reported, while a
  class method and a nested function of the same name are ignored;
* `test_the_suite_actually_contains_test_functions` requires more than 500
  discovered test functions, so a broken discovery root cannot pass silently.

Verified non-vacuous by reintroducing the duplicate: the detector failed with
`test_encode_to_file_writes_exact_bytes at lines 56 and 125`, then passed once
it was removed.

The same scan over `configbuilder/` (**72 files**) reports **no** shadowed
module-level definitions, so this was confined to the test suite.

##### G.4.2 DEFECT-CI-1 — CI asserted a version it never exercised

`.github/workflows/ci.yml` opened with:

```
# The repository ships the application source only (no tests, no docs): the
# suite under tests/ is local development material (.gitignore).
```

That comment was true when written and false by the time it mattered. The job
installed, compiled, imported, started both entry points and ran a pipeline
smoke — **and never ran the suite**, in either language version.

The consequence is now measurable. The package passed CI on 3.9 while seven
helpers in `configbuilder/variants/edits.py` raised
`TypeError: 'staticmethod' object is not callable` on that same interpreter
(DEFECT-PY39-1, G.2.1). CI was green on the version that was broken. Nothing in
the pipeline called `describe_edit`.

**Fix.** A new `test` job runs the real suite:

```yaml
- name: Install package with dev extras
  run: python -m pip install -e ".[dev]"
- name: Full test suite
  run: python -m pytest -o addopts="" -q
```

across **3.9 and 3.11 on Ubuntu and Windows**, plus **3.12 on Ubuntu**. The
`smoke` and `lint` jobs are unchanged in substance and now carry a comment
explaining why the suite job exists, so it is not removed again as redundant.

**Verification of the workflow itself**, since a broken CI file fails silently
until it runs:

| Check | Result |
|---|---|
| YAML parses | OK — jobs `lint`, `smoke`, `test` |
| Every embedded `python -c` block compiles (`ast.parse`) | 5/5 OK |
| Embedded `shell: python` block compiles | 1/1 OK |
| `test` job installs `-e ".[dev]"` and runs pytest | confirmed by assertion on the parsed document |
| The job's exact commands, run locally on 3.9 | `pip install -e ".[dev]"` exit 0, then **921 passed, 1 skipped**, exit 0 |

The interpreter guard was also checked for direction: on 3.11 it accepts `3.11`
and **fails** `3.9`, so the assertion cannot pass on the wrong interpreter.

**What CI still does not cover, stated rather than implied:** the AF3 parser
validation needs the network and a fetched AlphaFold 3 checkout, so it remains a
manual step (`tools/af3_validation/`). The lint gate stays scoped to
`configbuilder`, because the same rule subset over `tests/` reports about 60
pre-existing findings (mostly unused imports in helpers) — test hygiene, not
shipped-code correctness, and a separate reviewable change.

#### G.5 Final counts, after G.4

| Check | Command | Result |
|---|---|---|
| Collection | `python -m pytest -o addopts="" --collect-only -q` | **922 collected** |
| Suite, 3.11.15 | `python -m pytest -o addopts="" -q` | **921 passed, 1 skipped**, exit 0 |
| Suite, 3.11, summary suppressed | `python -m pytest -q` | exit 0 |
| Suite, 3.9.25 | `.venv39\Scripts\python -m pytest -o addopts="" -q` | **921 passed, 1 skipped**, exit 0 |
| Fresh clone, 3.11.15 | clone + `pip install -e ".[dev]"` + pytest | **921 passed, 1 skipped**, exit 0 |
| Fresh clone, 3.9.25 | same clone, `.venv39`, pytest | **921 passed, 1 skipped**, exit 0 |
| Lint gate | `ruff check --select E4,E7,E9,F configbuilder` | All checks passed |
| AF3 parser suite | `python tools/af3_validation/run_all.py` | PASS; 13/13, 8/8, 21 accepted, 13/13 identical |
| `userCCD` / `userCCDPath` | same | **UNVERIFIED** — needs AF3's compiled CIF parser |

922 collected = 921 passed + 1 skipped. The skip is
`tests/unit/persistence/test_sequence_files.py:50`, by design.

The movement across this pass is worth reading as a whole, because each step was
a defect rather than a formatting change:

| Stage | Collected | Passed | What it exposed |
|---|---|---|---|
| Audit as written | 896 claimed | 895 claimed | unreproducible: `tests/` untracked |
| Tracked suite | 915 | 914 | 1 test silently shadowed; CRLF broke 3 clones |
| `.gitattributes` + clone | 918 | 917 | — |
| Python 3.9 actually run | 918 | 917 | 30 failures, 2 real defects fixed |
| G.4 shadowing fix + detectors | **922** | **921** | 1 recovered test, 3 new integrity tests |

---

## H. Entity-Editing Hardening (2026-10-08, later pass)

> **Contents.** H.1 method and scope; H.2 the seven defects found, each with its
> reproduction and its regression pin; H.3 the invariants that already held and
> are now pinned; H.4 files changed; H.5 tests added; H.6 commands and results;
> H.7 what was not tested; H.8 assessment.

> **Scope, stated first because it is the point of the pass.** The generated AF3
> JSON had already been run through AlphaFold 3 (§F.11, §G.5). This pass
> therefore changed **no** schema, encoder, contract or generation logic: it
> hardened the *editor*. Every change below is one of three things — a refusal
> where the code used to raise, an index that addressed the wrong row, or a pin
> on a guarantee that was already true but unrecorded. §H.6 shows the AF3 parser
> suite reporting the same figures as §G.5, which is what "the JSON did not move"
> means in evidence rather than in prose.

Environment: Windows, CPython 3.11.15, repository `main` at `52b7b1d`, the pass
left uncommitted (7 modified modules, 4 test files added — §H.4).

### H.1 Method

The audit worked the interaction model rather than the code alone, because that
is where this program is actually interpreted:

1. **Read the state model first.** `model/records.py` and
   `identity/registry.py` for how a record and its identifiers are held, then
   the four mutation surfaces: `app/configuration_service.py` (the base job),
   `app/variant_service.py` (the specs), `variants/edits.py` (`apply_edit` — what
   a committed spec becomes) and `ui/render/menus.py` (2 161 lines: the largest
   file, and the only path a human takes).
2. **Fuzz the service layer**, where a crash has no menu to hide it: random
   add/edit/remove chains over every family at `ConfigurationService`, then over
   `VariantService` and expansion.
3. **Reproduce each candidate at the menu**, over `ScriptedConsole`, driving the
   shipped `MenuApp` — five of the seven defects bite only through a menu, and
   the fuzzer alone could not have shown that.
4. **Falsify every new test against the pre-fix tree**: `git archive HEAD` into a
   scratch directory, copy the new test files in, run. **18 of the 30 new unit
   and lifecycle tests fail there.** The 12 that pass are deliberate locks on
   behaviour that was already correct (§H.3); a test that cannot fail is not a
   fix.

### H.2 Defects found

Seven, all of the same shape: an operation the model cannot perform for the
chosen record, or an index computed in the wrong list, escaping either as a
Python exception out of a menu or as a silent wrong-row edit.

#### BUG-020 — A sequence change aimed at a ligand ended the session
* **Severity:** medium (a traceback exits the program; the user loses the run)
* **How it surfaced:** service fuzzing. `ComponentRecord` has no `with_sequence`;
  `update_record(key, sequence=...)` reached it anyway.
* **Expected:** a refusal naming the family, state unchanged.
* **Actual:** `AttributeError` out of `ConfigurationService.update_record`. The
  same class of defect the modification and alignment setters already guarded
  against; only the sequence setter was missing the check.
* **Files:** `app/configuration_service.py`.
* **Fix applied:** the setter refuses a non-polymer record in the user's own
  vocabulary (`a ligand record has no sequence to change; its representation is
  changed instead`), via a small `_FAMILY_WORD` table. Ligand *descriptions*
  still edit normally (the guard is about the sequence field only). The variant
  flow's twin picker was wrong in the same way — it offered ligands for a
  sequence change and then refused — so its `_family_of_key` now says "record 'A'
  is a ligand; only a protein, RNA or DNA chain carries a sequence or an MSA"
  instead of the misleading "no record is identified by 'A'", and the picker
  itself no longer offers one (`menu.no_polymer_target`).
* **Regression tests:** `test_a_sequence_change_on_a_ligand_is_refused_not_raised`,
  `test_a_sequence_change_on_a_multi_copy_ligand_is_refused_too`,
  `test_a_description_change_on_a_ligand_still_works` (the guard is narrow),
  `test_a_variant_sequence_aimed_at_a_ligand_says_so`,
  `test_the_variant_sequence_picker_does_not_offer_a_ligand`.
* **Status:** **FIXED & VERIFIED** — fails pre-fix, passes after; the refusal
  leaves representation and identifier untouched.

#### BUG-021 — A wrong-alphabet variant sequence killed the session
* **Severity:** medium (traceback from an ordinary typo at a prompt)
* **How it surfaced:** menu playthrough of Variants → change → sequence, answering
  `ACDEFG` for an RNA chain.
* **Expected:** the alphabet refusal the model already words, as a result object.
* **Actual:** `SequenceTextError` escaped `apply_variant_edit`. The factor table
  caught `(EditError, VariantSpecError, ValueError, TypeError)`, and
  `SequenceTextError` derives from `ModelError` — which derives from
  `Exception`, **not** from `ValueError`. The narrower catch looked complete and
  was not.
* **Files:** `app/variant_service.py`.
* **Fix applied:** the factor conversion catches `ModelError` as well; the two
  now-redundant `from configbuilder.model import SequenceTextError` wrappers
  around `add_spec`/`update_spec` were deleted rather than left to rot.
* **Regression tests:** `test_a_variant_sequence_in_the_wrong_alphabet_is_refused_not_raised`,
  `test_append_factor_refuses_a_wrong_alphabet_too` (the direct route),
  `test_a_wrong_alphabet_at_the_variant_sequence_prompt_is_refused_not_raised`
  (the menu route).
* **Status:** **FIXED & VERIFIED** — and the spec's edits are still `()` after the
  refusal, so the bad answer left no residue.

#### BUG-022 — Review → Validate died on a variant that cannot expand
* **Severity:** medium (the reporting path is where a worried user goes)
* **How it surfaced:** a project holding a spec that can no longer expand — the
  shape an older build or a hand-edited project file leaves behind. `expand()`
  raises `EditError` for it.
* **Expected:** the base report (already computed) plus the reason the variant
  half is missing.
* **Actual:** the `EditError` escaped `ValidationService.validate_all`, so the
  whole session went down from the Review menu.
* **Files:** `app/validation_service.py`, `app/results.py`,
  `ui/render/menus.py`.
* **Fix applied:** `validate_all` catches `(EditError, VariantSpecError)` and
  returns a `VariantValidationOutput` carrying `failure_reason="expansion_failed"`
  and the refusal's own wording; the menu prints the base verdict, then says the
  variant half was not applied and why. The two new fields default to `None`/`""`,
  so every existing constructor call and every reader keeps its meaning.
* **Regression tests:** `test_validate_all_reports_an_unexpandable_variant_instead_of_raising`,
  `test_preview_and_generation_refuse_the_unexpandable_variant_cleanly` (the same
  spec through preview, `plan` and `show_json` — refusals, never raises),
  `test_modification_summary_is_empty_when_the_variant_cannot_expand`,
  `test_review_validate_reports_an_unexpandable_variant_instead_of_raising`.
* **Status:** **FIXED & VERIFIED.**

#### BUG-023 — `RemoveModification` aimed at a record with no modification list
* **Severity:** medium (same traceback shape, and it is reachable from a stored
  spec, not only from a fresh edit)
* **How it surfaced:** fuzzing `apply_edit` directly, then confirming the earlier
  composition guard: every sibling case in `apply_edit` checks the record's
  family first — `RemoveModification` did not.
* **Expected:** an `EditError`, which is what every caller of `apply_edit`
  already handles.
* **Actual:** `AttributeError` reading `.modifications` on a `ComponentRecord`,
  escaping through expansion.
* **Files:** `variants/edits.py`, `app/variant_service.py`.
* **Fix applied:** the family check the sibling edits use, naming the expected
  carrier ("polymer record"); plus a guard at composition time in
  `VariantService` (`_modification_target_failure`) so a ligand is refused where
  the user composes the edit, not later during expansion.
* **Regression tests:** `test_remove_modification_on_a_non_polymer_is_an_editerror`,
  `test_a_modification_edit_aimed_at_a_ligand_is_refused_when_composed`,
  `test_the_variant_modification_picker_does_not_offer_a_ligand`.
* **Status:** **FIXED & VERIFIED.**

#### BUG-024 — Removing the second of two modifications at one position removed the first
* **Severity:** high (silent data loss: the wrong modification disappears and the
  user is told the operation succeeded)
* **How it surfaced:** reading the base flow's modification picker against the
  model, which permits two modifications at one position (and an imported AF3
  file can carry it).
* **Expected:** the row the user picked is the modification that goes.
* **Actual:** the picker's payload was the **position**, and the removal looked
  the index up with `next(i for i, mod in ... if mod.position.value == chosen)` —
  the first match. Two modifications at position 5: picking the second removed
  the first.
* **Files:** `ui/render/menus.py`.
* **Fix applied:** the row's payload is the modification's own index
  (`enumerate`), so the payload *is* the address `remove_modification` takes; the
  position stays in the label where the user reads it. `menu.no_modifications`
  reworded to match.
* **Regression tests:** `test_removing_the_second_of_two_modifications_at_one_position_removes_it`,
  `test_two_modifications_at_one_position_are_removed_row_by_row` (end to end,
  asserting the surviving row).
* **Status:** **FIXED & VERIFIED** — both fail pre-fix ('TPO', 5) != ('SEP', 5).

#### BUG-025 — The variant remove-modification picker removed a different row than it showed
* **Severity:** high (same silent wrong-row deletion, on the variant side, and it
  could delete the *base's* modification)
* **How it surfaced:** following the index from the picker into
  `RemoveModification`, which indexes the **expanded** record's list.
* **Expected:** the offered index addresses the row the user sees.
* **Actual:** `modification_summary` numbered this *spec's own* `AddModification`
  edits from 0, while the edit applied against the expanded record — whose list
  also holds the base's modifications, ahead of them. As soon as the base
  carried any modification the two numberings differed, and the mismatch
  deleted the base's PTM while keeping the one the user had chosen.
* **Files:** `app/variant_service.py`.
* **Fix applied:** the summary is read off the expansion
  (`preview(key).variants[0]`), one row per modification of each record, labelled
  `"<record> @ <position> (<code>)"`; `[]` when the variant cannot expand.
* **Regression tests:** `test_modification_summary_indices_address_the_expanded_record`
  (base PTM at 3, variant adds TPO at 5, the picker must offer 0 and 1 — then the
  applied index removes exactly the offered row and the base never moves),
  `test_the_variant_modification_picker_lists_the_expanded_record`,
  `test_the_variant_removes_the_modification_row_it_showed`.
* **Status:** **FIXED & VERIFIED.**

#### BUG-026 — Variants → Add a new entity crashed for protein, RNA and DNA
* **Severity:** high (any user taking that route for the three polymer families
  got a traceback; only the ligand family worked)
* **How it surfaced:** sweeping every menu option and family through the
  acceptance suite — the variant flow carries its own add-entity implementation,
  and it had drifted from the base flow's.
* **Expected:** the same prompts the base add flow shows, from the same source.
* **Actual:** `self._ask(_text("menu.entity_seq_prompt") % family)` — `_ask`
  takes a **registry key**, and it was handed an already-formatted display
  string, so the registry raised by design:
  `KeyError: "no string registered for 'dna sequence: '; add it to
  ui/present/strings.py"`. The `menu.entity_seq_prompt` key it named had never
  existed.
* **Files:** `ui/render/menus.py`, `ui/present/strings.py`.
* **Fix applied:** both flows now ask through the same registered per-family
  prompts (`menu.add_protein_prompt` / `menu.add_rna_prompt` /
  `menu.add_dna_prompt`); the never-registered `menu.entity_seq_prompt` is
  deleted. The base flow's own table also named a string that does not exist for
  the ligand entry (`menu.add_ligand_prompt`) — unreachable today because the
  ligand branch returns first, and corrected rather than left as a trap for the
  next reordering.
* **Regression tests:**
  `test_option_3_variant_add_entity_for_every_family` (4 cases: all four
  families, through the real menu, asserting the prompt shown, the edits
  recorded and that the variant *materialises* the added record while the base
  keeps exactly one).
* **Status:** **FIXED & VERIFIED** — pre-fix that test reports 3 failed, 1 passed
  (`KeyError: "no string registered for 'dna sequence: '"`), which is also the
  proof that the ligand family was the only route that worked.

### H.3 Invariants verified, not changed

These were already true. They are listed because the pass checked them against
running code and pinned them where no test did:

| Invariant | How it was checked |
|---|---|
| Every identifier is unique and the registry agrees with the records | `assert_invariants()` in the lifecycle suite (walks every id of every record, then compares against `identity.assigned_values()`) |
| A removed identifier is retired, never reused | add A, add B, add C, remove B, add D → `['A', 'C', 'D']`; an imported `["A","B"]` multi-id record removed → the new protein takes `D`, not `A` or `B` |
| Cancellation changes nothing | add/edit/delete/modify/bond cancellations, alone and interleaved with real operations, compared with `==` against the configuration captured before the script |
| A cancelled add reserves no identifier | cancelling, then a real add, yields `['A']` and a registry holding only `A` |
| Modifications stay on the record they were added to | add/remove/re-add, then an entity edit and a reload |
| An imported document is editable like a built one | import a document with multi-id records, MSA, templates, a bond, `userCCD` and a SMILES ligand; edit, add, remove, save, reload |
| Variants never mutate the base | base → V1 → edit base → V2 → save; V1 still expands to its own declaration, the base holds only the user's edits |
| The UI's state is the serialised state | the generated file's ids and sequences are compared with the live model in five tests, including after a refusal to overwrite |
| Saving never destroys another file | the second save finds the previous file and refuses (policy `Fail`), saying how to proceed, while the model moves on |
| Serialisation did not move | 13 AF3 example documents imported and re-emitted **byte-identical**, and accepted by AF3's own parser (§H.6) |

### H.4 Files changed

| File | Why |
|---|---|
| `configbuilder/app/configuration_service.py` | BUG-020: the sequence setter refuses a non-polymer, with `_FAMILY_WORD` for the wording |
| `configbuilder/app/variant_service.py` | BUG-021 (`ModelError` in the factor table, two redundant wrappers deleted); BUG-020/023 composition guards (`_family_of_key`, `_modification_target_failure`); BUG-025 (`modification_summary` reads the expansion) |
| `configbuilder/variants/edits.py` | BUG-023: the family check every sibling case already had |
| `configbuilder/app/validation_service.py` | BUG-022: an unexpandable variant is reported, not raised |
| `configbuilder/app/results.py` | BUG-022: `VariantValidationOutput.failure_reason` / `.message`, both defaulted |
| `configbuilder/ui/render/menus.py` | BUG-024 (the row index is the payload); BUG-026 (registered prompts in the variant add-entity); polymer-only variant pickers; the Review → Validate refusal is printed, not raised |
| `configbuilder/ui/present/strings.py` | `menu.no_polymer_target` added; the never-registered `menu.entity_seq_prompt` removed; `menu.no_modifications` reworded to what the picker now lists |
| `tests/e2e/test_menu_acceptance.py` | 4-case variant add-entity acceptance test (BUG-026) |
| `tests/unit/app/test_edit_guards.py` *(new)* | 12 service-layer pins, one per defect plus the guards' narrowness |
| `tests/unit/ui/test_edit_hardening.py` *(new)* | 10 menu-level pins |
| `tests/e2e/test_entity_lifecycle.py` *(new)* | 8 lifecycle/workflow tests (recipes from the task: repeated operations, import, variants, cancellation, save/reload) |

No other module was touched. In particular the encoder, the contract, the
validator, the planner and `to_wire` are untouched; the diff is
7 modules / ~250 lines, all of it refusals, indices and messages.

### H.5 Tests added

34 in total (30 in the three new files, 4 cases in the acceptance file).
Collection: **956** (922 before), passed **955**, skipped 1 (by design).

* **Entity lifecycle** — `test_add_remove_readd_edit_then_save_writes_the_model_it_shows`,
  `test_every_family_survives_a_full_lifecycle`,
  `test_an_imported_document_is_editable_like_a_built_one`,
  `test_a_long_repeated_chain_of_operations_leaves_consistent_state`,
  `test_cancel_interleaved_with_real_operations_changes_nothing`,
  `test_cancelling_every_operation_leaves_the_configuration_identical`,
  `test_cancelled_entity_adds_do_not_reserve_identifiers`.
* **Modifications** — `test_modification_lifecycle_add_remove_readd_and_reload`,
  `test_two_modifications_at_one_position_are_removed_row_by_row`,
  `test_removing_the_second_of_two_modifications_at_one_position_removes_it`,
  `test_modification_summary_indices_address_the_expanded_record`.
* **Identifiers** — the registry/record walk in `assert_invariants()` plus the
  retirement assertions above (add A/B/C, remove B, add D; imported A/B removed).
* **State safety** — the cancellation pins, the refusal pins (BUG-020/021/023),
  and `test_preview_and_generation_refuse_the_unexpandable_variant_cleanly`.
* **Integration** — the import, variant-isolation and long-chain tests above,
  `test_option_3_variant_add_entity_for_every_family` (4 cases), and the two
  variant-index pins (BUG-025).

### H.6 Commands and results

| Check | Command | Result |
|---|---|---|
| Full suite | `python -m pytest -o addopts="" -q` | **955 passed, 1 skipped**, exit 0 |
| Collection | `python -m pytest -o addopts="" --collect-only -q` | 956 collected (922 + 34) |
| New tests | `python -m pytest tests/unit/app/test_edit_guards.py tests/unit/ui/test_edit_hardening.py tests/e2e/test_entity_lifecycle.py -o addopts="" -q` | **30 passed**, exit 0 — run twice in a row, and nothing is written into the checkout (three tests that used to leave `output/<job>/` in the working directory were given `tmp_path` + `monkeypatch.chdir`) |
| Falsification | `git archive HEAD` → scratch dir, new tests copied in, `python -m pytest … -q` | **18 failed, 12 passed** — every defect pin reproduces against the pre-fix tree |
| BUG-026, pre-fix | same scratch, `-k variant_add_entity` | **3 failed, 1 passed**: `KeyError: "no string registered for 'dna sequence: '"` |
| Lint (CI's own gate) | `ruff check --select E4,E7,E9,F configbuilder` | All checks passed |
| Python-floor source gate | `ast.parse(…, feature_version=(3, 9))` over every shipped module | all modules parse as 3.9 |
| AF3 parser suite | `python tools/af3_validation/run_all.py` | **PASS** — positive 13/13, negative 8/8, corpus ACCEPTED=21 UNVERIFIED=2, round trip **13/13 identical**, exit 0 |

### H.7 What was not tested

* **No live-TTY playtest.** Every fix was verified through `ScriptedConsole` and
  the service layer. §F.12 is the model for a hand-driven session; this pass did
  not repeat it, so the wording of the new refusals has not been read off a real
  terminal.
* **Python 3.9 was not executed here.** This machine currently has 3.11.15 and
  3.12 and no 3.9 (the `.venv39` of §G is gone). The floor is covered by the
  syntax gate above and by the CI matrix, not by a local run of the new tests.
* **The exploratory fuzzers are not shipped.** They live in the audit's scratch
  directory; the durable pins are the 34 tests listed in §H.5. The long chains
  are fixed recipes, not randomised menu scripts, so an unvisited sequence of
  six or more operations could still hide something — the invariants are
  therefore asserted directly as well (identity registry vs records, every
  linkage endpoint resolves, no traceback in the transcript).
* **`userCCD` / `userCCDPath`** remain UNVERIFIED (they need AF3's compiled CIF
  parser); unchanged by this pass, and unchanged in count from §G.5.
* **Concurrency and the filesystem edge cases** of §F.7 (two builders sharing an
  output directory, permissions, a raced plan) were not revisited.

### H.8 Assessment

**READY WITH MINOR RISKS.**

Every defect the audit could reproduce is fixed and pinned by a test that fails
without the fix; the seven crash-shaped paths now refuse, explain and return to
the menu with the state untouched; cancellation, identifier retirement, import
parity, variant isolation, the save-refuses-to-destroy guarantee and
byte-identical serialisation were *verified* rather than assumed; the suite is
green on the development interpreter, the lint gate is green, and the AF3 parser
figures are identical to §G.5, which is the evidence that the working JSON did
not move.

It is not **READY** outright because of the two limitations in §H.7 that a
reviewer cannot talk away: the fixes were exercised through the scripted console
rather than by hand at a real terminal, and the declared interpreter floor was
verified by a syntax gate and CI rather than executed on this machine.

---

## I. Menu Rework (2026-10-11)

> **Contents.** I.1 scope and method; I.2 the new menu map; I.3 flows removed;
> I.4 implementation changes; I.5 tests reworked; I.6 commands and results;
> I.7 what was not tested; I.8 assessment.

Environment: Windows, CPython 3.11.15, repository `main` at `52b7b1d` with the
§H pass still uncommitted; this pass also left uncommitted.

### I.1 Scope and method

The pass replaced the session/project-management front end with one job
workflow built around AF3's own concepts. The instruction was the menu itself:
a main menu that starts a job or opens an existing AF3 JSON, a job menu with
editing, entity, custom-CCD, PTM, save and variant operations, and no separate
"masters", working copies, review screens or generation menus. "Variants" are
copies of the job saved under their own name, not a stored spec catalogue, and
the JSON file on disk is the only persistence — the internal `.cbproj` working
copy and its autosave/recovery machinery were removed with the rework.

The method was the same as §H's: read the model and services first, then rework
the UI layer, then drive the shipped `MenuApp` over `ScriptedConsole` for every
advertised option (success, refusal, cancellation), and finish with the AF3
parser suite to prove the emitted JSON did not move. Everything the rework
stopped exposing but the application still supports (batch variants, quantity
series, linkage editing, the validation service) kept its service-level tests.

### I.2 The new menu map

| Screen | Options |
|---|---|
| main | 1 New job · 2 Open a JSON file · 0 Exit |
| job | 1 Edit job configurations · 2 Add entity · 3 Edit entity · 4 Custom CCD management · 5 PTM management · 6 Save and show summary · 7 Create variants based on this JSON · 0 Return to main menu |
| edit job | 1 Job name · 2 Model seeds · 3 JSON version · 0 Back |
| add entity | 1 Protein · 2 DNA · 3 RNA · 4 Ligand (quantity menu for ligands; MSA/templates chained onto the new record) |
| edit entity | pick an entity → 1 Edit · 2 Delete · (3 Modifications for a polymer) · 0 Back |
| per-record modifications | 1 Add · 2 Edit · 3 Remove · 0 Back |
| Custom CCD | 1 View · 2 Add · 3 Edit · 4 Remove · 0 Back |
| PTM | 1 View · 2 Add · 3 Edit · 4 Remove · 0 Back |
| variants | 1 Set variant job name · 2 Add entity · 3 Edit entity · 4 Save variant and reset to base · 0 Back |

A new job arrives with the standard defaults already applied: a name, the
default seed set, and a **version-3 pin** (`status.DEFAULT_VERSION = 3`).
Version 3 is the minimum that covers the builder's core fields; a job that uses
a per-chain or job-level description must raise the pin to 4, which the
job-settings menu offers and the transform engine names as a requirement rather
than silently upgrading.

Leaving a dirty job is never silent: the job menu asks Save / Leave without
saving / Cancel first. Leaving the variant editor always restores the base job.

### I.3 Flows removed (and what remains)

| Removed from the menu | What remains |
|---|---|
| Working copy, autosave, recovery, "Open saved work" | Nothing to recover: a job is resumed by opening its JSON. `ProjectService.import_json_preview/commit` is the only load path. |
| Review configuration / Validate screens | `ValidationService` is unchanged and still gates every save and export. |
| Variant-spec catalogue (create/manage/batch/series UI) | `VariantService` is unchanged at the service layer, including `generate_from_file`, `quantity_series_plan`, `create_quantity_series`, expansion and `modification_summary`; the UI's variants are save-as copies. |
| Bonds / linkages menu | `ConfigurationService.add_linkage/remove_linkage` unchanged and covered at the service layer. |
| Generate JSON menu and output-directory setting | Replaced by "Save and show summary", which writes to an explicit path through `GenerationService.plan_save`. Bulk generation (`plan`/`plan_base`) remains for the services and AF3 tooling. |
| Quantity-series planner and JSON preview screens | Service operations (`quantity_series_*`, `show_json`) remain, with their service-level tests. |

### I.4 Implementation changes

| File | Why |
|---|---|
| `configbuilder/ui/render/menus.py` | Rewritten around the main/job/submenus above. `_record_mod_menu` implemented (entity → Modifications) and the PTM add/edit/remove flows factored into helpers shared by both routes (`_add_modification_to`, `_edit_modification_on`, `_remove_modification_on`, `_select_modification_target`); save through `plan_save`; variants as snapshot/reset; unsaved-change leave prompt; no working-copy or inspection of the deleted store. |
| `configbuilder/ui/present/strings.py` | Registry rewritten to the new chrome: every key the UI uses is present, every entry is used, and no recovery vocabulary remains. |
| `configbuilder/app/status.py` | `DEFAULT_VERSION` 4 → 3, with the description/version-4 rule documented. |
| `configbuilder/app/generation_service.py` | `plan_save(destination, name, overwrite)`: explicit-path save through the same validation gate and serializer; `name` overrides the wire name for variant saves; a bare/missing destination is normalized so `dirname()` is never empty. |
| `configbuilder/app/project_service.py` | Working-copy autosave/recovery removed; import preview/commit retained. |
| `configbuilder/app/configuration_service.py`, `results.py`, `validation_service.py`, `variant_service.py`, `variants/edits.py` | §H's hardening retained unchanged by this pass (except `clear_component_definition` / `update_modification` service support used by the new CCD/PTM menus). |
| `tools/af3_validation/setup_validator.py` | Installs `msgpack`, which current AF3 `main` imports from its chemical-component constants (the documented setup failed without it). |
| `tools/af3_validation/run_all.py` | The `descriptions_all_families` corpus case pins version 4 explicitly — descriptions are a v4 feature and the builder now defaults to 3, so the case must raise the pin exactly as a user would. |
| `docs/CONTRACT_PIN.md` | Unchanged content; see I.7 for the environment note. |

### I.5 Tests reworked

The menu-driven suites were rewritten against the new routes; the service-level
pins and the AF3 tooling were left to judge the JSON.

| File | Change |
|---|---|
| `tests/e2e/test_menu_acceptance.py` | Rewritten: 39 tests, every advertised option through the real menu — main/job/config/add/edit, modifications (both routes), CCD (inline/file/cancel), PTM, save (path, refusal, cancellation, overwrite confirmation, summary), variants (name, isolation, reset, two in a row), import (preview, confirm, malformed, missing, unsupported fields, edit and save), and the dirty-leave prompt. |
| `tests/e2e/test_entity_lifecycle.py` | Rewritten: 8 tests. Reopening is now "open the JSON"; variants are save-as copies; cancellation and identifier-retirement invariants retained. |
| `tests/unit/ui/test_audit_regressions.py` | Reworked: 26 tests. BUG-001/002/007 pins moved to the surviving routes (PTM, save); BUG-003/013 reworded for the rework; the bond-residue pin is service-level because the menu no longer parses residues; BUG-004/005/006/008/009/011/016 retained. |
| `tests/unit/ui/test_edit_hardening.py` | Reworked: 7 tests. BUG-024 (wrong-row removal) pinned on the PTM route and again inside a variant; BUG-021 (wrong alphabet) pinned at the new variant editor; a ligand edit asks for its representation; cancellation identity retained. |
| `tests/unit/variants/test_quantity_series.py` | 17 tests. The series/preview **menu** pins were retired (the UI no longer exposes them); the add-time quantity UI pin was rewritten to the new navigation, and every service-level series test remains. |
| `tests/unit/app/test_entry_point.py`, `test_status.py`, `test_work_preservation.py`, `tests/e2e/test_app_pipeline.py`, `tests/unit/ui/menu_flows.py`, `test_menu.py`, `test_mod_display.py`, `test_p1_fixes.py`, `test_numbered_flows.py` | Updated earlier in the rework for the new menu, defaults and save API. |
| `tests/unit/validation/test_no_pin_document_dependency.py` | The installed-package check reads the banner from the string registry instead of the old literal (`ConfigBuilder` → `menu.banner_title`); it had been passing only because the interpreter's editable install pointed at a stale clone. |

Six menu-level pins were retired with the removed flows (three variant-catalogue
tests in §H's file, three series/preview tests); each retired behavior that
still exists at the service layer keeps its pin there, and §H's
`test_edit_guards.py` is untouched.

### I.6 Commands and results

| Check | Command | Result |
|---|---|---|
| Full suite | `python -m pytest -o addopts="" -q` | **923 passed, 1 skipped** (924 collected), exit 0 |
| Lint (CI's own gate) | `ruff check --select E4,E7,E9,F configbuilder` | All checks passed |
| Python-floor source gate | `ast.parse(…, feature_version=(3, 9))` over every shipped module | all modules parse as 3.9 |
| Compile | `python -m compileall -q configbuilder` | ok |
| AF3 parser suite | `python tools/af3_validation/run_all.py` | **PASS** — positive 13/13, negative 8/8, corpus ACCEPTED=21 UNVERIFIED=2, round trip **13/13 identical**, exit 0 |
| Real console entry | `configbuilder` fed a keystroke pipe in a scratch directory | exit 0; built a job, wrote `PipeJob.json` (`name=pipejob`, `version=3`, `modelSeeds=[1]`), left cleanly |
| Real module entry | `python -m configbuilder < /dev/null` | exit 0, menu shown |

### I.7 What was not tested

* **No live-TTY playtest.** Every route was exercised through `ScriptedConsole`
  or a piped stdin; the new wording has not been read off a real terminal.
* **Python 3.9 was not executed here.** The floor is covered by the syntax gate
  and CI's matrix.
* **`userCCD` / `userCCDPath` remain UNVERIFIED** (they need AF3's compiled CIF
  parser), unchanged from §G.5/§H.
* **The UI-run features retired by the rework** — bond editing, batch variants,
  quantity series, JSON preview, working-copy recovery — are now covered only
  at the service layer. If any of them is wanted back in the menu, it needs its
  own pass and pins.
* **Environment repairs made while verifying, recorded because they affect
  reproducibility:** the AF3 validator's temp cache (outside the repository) had
  been partially deleted by the OS temp cleaner, so it was rebuilt from scratch;
  the venv's editable install of `configbuilder` pointed at an old
  `%TEMP%\cb-freshclone` left by §H's falsification step and was repointed at
  this checkout (which is how the banner assertion above surfaced). Neither
  touches the repository's shipped code.

### I.8 Assessment

**READY WITH MINOR RISKS.** The reworked menu is coherent end to end: every
advertised option has a success path, a refusal path and (where one exists) a
cancellation pinned through the shipped `MenuApp`; the suite is green; the lint
and interpreter-floor gates are green; the real console entry builds and writes
a valid AF3 file; and AF3's own parser accepts every document the builder emits
(21 accepted, 13/13 round trips byte-identical). The remaining risk is the one
named in §H and repeated here: verification is scripted rather than
hand-played, and the rework intentionally narrowed the menu, so the features it
stopped exposing now rely on their service tests alone.

