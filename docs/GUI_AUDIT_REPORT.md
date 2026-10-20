# GUI Audit Report — Adding a PySide6 Desktop Front End to the AF3 JSON Builder

**Audit date:** 2026-10-15
**Repository root:** `C:\Users\Chris\Desktop\THESISSP` (Git branch `main`, HEAD `121baa8`)
**Audited revision:** the working tree as-is, including 16 modified tracked files and 9 untracked
entries that were present before this audit began (see §2.3). Nothing in this audit modified,
created, deleted, renamed, reformatted or moved any application file; no dependency, environment,
Git or network state was changed.
**Scope:** audit and planning only. No GUI was implemented. Exactly one file was created:
this report.

---

## 1. Executive summary

The builder is in **much better shape for a GUI than the prompt assumed**. The command-line
front end is a thin driver over five already-decoupled application services
(`ProjectService`, `ConfigurationService`, `VariantService`, `ValidationService`,
`GenerationService`) that are wired once in `configbuilder/ui/services.py::build_services`
and reached through a single `Services` bundle. Every service returns **plain result objects**
rather than raising for user-caused problems (`configbuilder/app/results.py`), and every
user-facing string is already centralised in a 285-entry registry
(`configbuilder/ui/present/strings.py`). The domain is a frozen, immutable value model, so
"undo", "preview", "validate before save" and "edit a copy" are cheap in a GUI.

The builder also has **no existing GUI code and no GUI dependency**: a search for
`PySide6|PyQt|tkinter|wxPython|kivy` across the repository returns hits only in the audit prompt
itself.

Four findings dominate the planning:

1. **A real, reproduced defect sits exactly where a GUI would make it worse.**
   `MenuApp._add_dna_with_complement_choice` (`configbuilder/ui/render/menus.py:846`) implements
   "single-stranded DNA" by deleting DNA records *by list position* after the service has already
   committed the duplex. `ConfigurationService.remove_record` removes a **duplex pair**
   (`configbuilder/app/configuration_service.py:437`, proven in
   `tests/unit/app/test_dna_duplex.py::test_removing_one_strand_removes_the_duplex_and_releases_both_ids`).
   A scripted run of the real menu (evidence in §4, row "DNA single-strand option") shows that
   answering **"No — use only the supplied strand"** silently removes **every DNA entity in the
   job**, while the screen prints "Applied." and "Entity added.". This is a front-end bug, not a
   core bug — but a GUI that calls the same service must not reproduce it, so it must be fixed
   (Stage 0) or explicitly dropped from the GUI's first milestone.
2. **Several implemented capabilities have no front-end route at all.** `GenerationService.show_json`
   (a validated, byte-exact JSON preview), `ValidationService.validate_all` (variant validation),
   `VariantService.add_spec/apply_variant_edit/duplicate_spec/quantity_series_plan/create_quantity_series`,
   `ConfigurationService.add_linkage/remove_linkage` (covalent bonds), `set_job_description`, and
   `ProjectService.open` (the `.cbproj` project file) are all implemented and tested but are
   **not reachable from the current menu**. They are the best GUI material in the repository.
3. **PySide6 as currently published cannot be installed on the project's declared Python floor.**
   `pyproject.toml` declares `requires-python = ">=3.9"` and CI runs the suite on 3.9
   (`.github/workflows/ci.yml`), but PyPI metadata for the current PySide6 (6.12.0, released
   2026-10-08) states `Requires: Python <3.16, >=3.10`. This needs a human decision (§5, D1),
   because it changes the project's supported-interpreter contract or forces an older PySide6 pin.
4. **The repository enforces its architecture with tests, and those tests currently forbid a new
   sibling package.** `tests/architecture/test_layout.py::test_exactly_ten_top_level_packages`
   asserts the exact ten-package layout, and
   `tests/architecture/test_dependency_rules.py::test_no_module_imports_app_or_ui` forbids any
   non-`ui`, non-`app` module from importing `app` or `ui`. A naive `configbuilder/gui/` package
   therefore **fails two existing tests** and must be placed deliberately (§8).

Test baseline: `python -m pytest -o addopts="" -q` → **13 failed, 990 passed, 1 skipped, 1 warning
in 171.09 s** (1004 collected). All 13 failures are stale end-to-end keystroke scripts /
stale default expectations in the two e2e files that the working tree has already modified;
none is caused by this audit (§2.4).

Recommendation: **PySide6 + Qt Widgets is suitable**, with the caveat in §5 D1, and the GUI
should be built as a new subpackage under `configbuilder/ui/` that drives the existing services
— never a re-implementation of validation, identity, serialization or variant logic. The
recommended first milestone is a read-only "Review & Preview" window (§11): it exercises the
whole integration seam and needs no write path.

---

## 2. Repository baseline

### 2.1 Root and top-level structure

Root: `C:\Users\Chris\Desktop\THESISSP`.

```
AF3_Comparative_Structural_Analysis_SOP.md   SOP for the separate analysis pipeline
AF3_GUI_AUDIT_PROMPT.md                      the prompt this report answers
AF3_Oct4_10_Condition_JSON_Builder_Agent_Prompt.md
AUTHORITATIVE_SPEC.md                        the field-level contract (evidence-tagged)
DOMAIN_MAPPING.md                            MAP-nnn traceability mapping
IMPLEMENTATION_PLAN.md                       the architecture plan (§5 layout, §5.3 rules)
IMPLEMENTATION_MAP.md / IMPLEMENTATION_MAP_FULL.md
CHECKLIST.md / HANDOFF.md
JSON_BUILDER_AUDIT_AND_FINALIZATION.md       historical audit (describes a REMOVED front end)
THESIS_IMPLEMENTATION_CHAPTER.md
docs/            CONTRACT_PIN.md, PROJECT_AUDIT.md
configbuilder/   the application (10 packages, see §2.5)
af3_analysis/    a SEPARATE analysis pipeline (own CLI, own README, own tests)
tests/           the tracked suite (99 modules, 1004 tests collected)
fixtures/        golden/invalid/project fixtures
tools/af3_validation/   manual AF3 validator tooling (downloads the AF3 tarball)
build/, output/, generated_jobs/, testdata/   build output, sample generated jobs, data
.configbuilder/  git-ignored residue of a removed working-copy autosave
```

### 2.2 Entry points, packaging and dependency declarations

| Item | Evidence |
|---|---|
| Console entry point | `pyproject.toml` → `[project.scripts] configbuilder = "configbuilder.app.cli:main"` |
| Module entry point | `configbuilder/__main__.py` — delegates to `configbuilder.app.cli.main` |
| Composition root | `configbuilder/app/cli.py::main` → `build_services()` → `MenuApp(services, Console()).run()` |
| Service wiring | `configbuilder/ui/services.py::build_services`, class `Services` |
| CLI front end | `configbuilder/ui/render/menus.py::MenuApp` (1730 lines) |
| Second, separate entry point | `af3_analysis/__main__.py` + `af3_analysis/cli.py` — `python -m af3_analysis run\|inventory\|doctor\|template`; **not** declared as a console script |
| Declared Python | `requires-python = ">=3.9"`; local interpreter is **CPython 3.11.15** |
| Core runtime dependencies | `dependencies = []` — deliberately stdlib-only (comment cites plan §4) |
| Dev extra | `pytest>=7`, `hypothesis>=6` |
| Analysis extra | `numpy>=1.21`, `pandas>=1.3`, `biopython>=1.79`, `scipy>=1.7`, `matplotlib>=3.5`, `PyYAML>=5.4`, `freesasa>=2.1` |
| CI | `.github/workflows/ci.yml`: `suite` job matrix ubuntu+windows × {3.9, 3.11} (plus 3.12 on Linux); `smoke` job on 3.9; `lint` job = `ruff check --select E4,E7,E9,F configbuilder` (configbuilder only, deliberately) |
| Test config | `pyproject.toml` → `testpaths = ["tests"]`, `addopts = "-q"` |

Installed in the local environment (checked with `importlib`):

```
pytest 8.2.2   hypothesis 6.165.3   numpy 1.26.4   pandas 2.2.2   Bio 1.87
scipy 1.13.1   matplotlib 3.9.0     yaml 6.0.3
freesasa  MISSING        PySide6  MISSING
```

`PySide6` being absent is expected and is **not** installed by this audit.

Python-version constraints that a GUI must respect, all enforced statically by
`tests/architecture/test_baseline.py` over every file under `configbuilder/`: no `match`
statements, no `@dataclass(slots=True)`, no PEP 604 `X | Y` unions, no `typing.TypeAlias`, no
`assert_never`, no `tomllib`, no `except*`.

### 2.3 Git status (read-only; reported, never changed)

Branch `main`, HEAD `121baa8` ("Land the entity-editing hardening and menu rework").

Modified tracked files present **before** this audit:

```
configbuilder/app/batch_variants.py        configbuilder/app/status.py
configbuilder/app/variant_service.py       configbuilder/persistence/__init__.py
configbuilder/persistence/sequences.py     configbuilder/ui/present/strings.py
configbuilder/ui/render/menus.py           pyproject.toml
tests/unit/app/test_status.py              tests/unit/ui/menu_flows.py
tests/unit/ui/test_audit_regressions.py    tests/unit/ui/test_edit_hardening.py
tests/unit/ui/test_menu.py                 tests/unit/ui/test_mod_display.py
tests/unit/ui/test_numbered_flows.py       tests/unit/variants/test_quantity_series.py
```

Untracked entries: `AF3_Comparative_Structural_Analysis_SOP.md`, `AF3_GUI_AUDIT_PROMPT.md`,
`AF3_Oct4_10_Condition_JSON_Builder_Agent_Prompt.md`, `IMPLEMENTATION_MAP.md`,
`IMPLEMENTATION_MAP_FULL.md`, `THESIS_IMPLEMENTATION_CHAPTER.md`, `af3_analysis/`,
`generated_jobs/`, `tests/analysis/`.

Consequence for planning: **the source *and* its tests are mid-rework in the working tree**, so
the local test picture is a moving target. Any GUI work should start from a committed, green
baseline, or explicitly treat Stage 0 as "land the in-progress edit".

### 2.4 Tests actually run, and their exact result

Command (the one CI uses, with `addopts` cleared so the summary line prints):

```
python -m pytest -o addopts="" -q
```

Result, reproduced three times:

```
13 failed, 990 passed, 1 skipped, 1 warning in 171.09s (0:02:51)
```

1004 tests collected (`python -m pytest --collect-only -q`). The single skip is
`tests/unit/persistence/test_sequence_files.py:50` — "Windows cannot express a read-denied file
through chmod" (a platform skip, not a failure). `freesasa` being absent did **not** cause a
skip in this run.

The 13 failures, with the assertion location:

| Test | Location | What it asserts |
|---|---|---|
| `tests/e2e/test_entity_lifecycle.py::test_every_family_survives_a_full_lifecycle` | `:158` | entity family list after protein+RNA+DNA+ligand adds (observed 2 records, expected 5) |
| `tests/e2e/test_entity_lifecycle.py::test_an_imported_document_is_editable_like_a_built_one` | `:290` | job name `'ACDEFGHIK'` vs `'rich-import'` |
| `tests/e2e/test_entity_lifecycle.py::test_a_long_repeated_chain_of_operations_leaves_consistent_state` | `:371` | ids `['A','B','E']` vs `['A','C','D','E']` |
| `tests/e2e/test_menu_acceptance.py::test_a_blank_job_name_is_generated_by_the_service` | `:122` | `'Untitled job 1'` vs `'config-001'` |
| `tests/e2e/test_menu_acceptance.py::test_add_every_entity_family` | `:139` | entity family list |
| `tests/e2e/test_menu_acceptance.py::test_job_settings_change_name_seeds_and_version` | `:197` | seeds `[1]` vs `[1, 2, 3, 4]` |
| `tests/e2e/test_menu_acceptance.py::test_invalid_job_settings_are_refused_in_the_users_terms` | `:212` | expected `'Not applied'` in transcript |
| `tests/e2e/test_menu_acceptance.py::test_the_job_menu_numbering_is_stable_across_states` | `:231` | expected menu line `5. PTM management` |
| `tests/e2e/test_menu_acceptance.py::test_the_entity_modifications_submenu_adds_edits_and_removes` | `:287` | expected `'Modification added.'` |
| `tests/e2e/test_menu_acceptance.py::test_ptm_management_adds_edits_and_removes` | `:304` | expected `'Modification added.'` |
| `tests/e2e/test_menu_acceptance.py::test_a_ligand_carries_no_modifications_and_is_told_so` | `:318` | expected `'ligands carry no modifications'` |
| `tests/e2e/test_menu_acceptance.py::test_open_json_can_be_cancelled_at_the_confirm` | `:562` | expected `'JSON opened.'` absent |
| `tests/e2e/test_menu_acceptance.py::test_an_opened_job_can_be_edited_and_saved` | `:71` | `FileNotFoundError` on the output JSON |

**Baseline failures, not audit artefacts.** Inspected cause, verified by running one of them in
isolation: these two e2e modules carry **keystroke scripts that predate the working-tree menu
rework**. For example, `tests/e2e/test_entity_lifecycle.py:32` defines
`ADD_DNA = lambda sequence: ["2", "2", sequence]`, which supplies **no answer to the new DNA
complement question**, so the script runs out, `Console.prompt` raises `EOFError`, and
`MenuApp.run` catches it and prints `Interrupted — returning to the menu.`; later assertions
compare against old defaults (`config-001` automatic names, seeds `[1,2,3,4]`, old menu
numbering `5. PTM management`). The current code defaults are `Untitled job N`
(`configbuilder/app/status.py::AUTO_NAME_PREFIX`) and `(1,)`
(`configbuilder/app/status.py::DEFAULT_SEED_VALUES`).

Whether to repair or retire those e2e scripts is a **human decision** (§10, D6). They are not a
GUI blocker, but they are the repository's own end-to-end safety net for exactly the workflows a
GUI will re-expose, so their state matters for Stage 7.

### 2.5 Package layout (the ten fixed families)

`tests/architecture/test_layout.py` asserts exactly these ten top-level packages under
`configbuilder/`, and exactly two subpackages under `ui/`:

```
model  identity  validation  transform  serialize  variants  output  persistence  app  ui
ui/ -> render, present
```

| Layer | Responsibility | Representative symbols |
|---|---|---|
| `model` | frozen canonical value model | `Configuration`, `SeedSet`, `Dialect`, `FormatTarget`, `Pinned`/`Auto`/`Unverified`, `FamilyARecord`, `FamilyBRecord`, `FamilyCRecord`, `ComponentRecord`, `ModificationRecord`, `ByCode`, `ByNotation`, `Linkage`, `Present`/`Unset`/`ExplicitEmpty` |
| `identity` | the only identifier authority | `IdentityRegistry`, `IdAllocator`, `EntityId`, `Multiplicity`, `RenameMap`, `DuplicateIdError` |
| `validation` | 44-rule catalogue + engine | `validate`, `catalogue.RULES`, `Report`, `Finding`, `FieldPath` |
| `transform` | the only wire-document builder | `to_wire`, `from_wire`, `WireDocument`, `TransformResult`, `ROOT_FIELDS`/`PROTEIN_FIELDS`/… |
| `serialize` | the only byte encoder | `encode`, `encode_to_file` |
| `variants` | specs and edits | `VariantSpec`, `Variant`, `Lineage`, `expand`, `apply_edit`, `SetSequence`/`AddRecord`/… |
| `output` | planning and atomic writing | `OutputPlan`, `execute`, `OverwritePolicy`, `PathPolicy`, `slug` |
| `persistence` | project file (`.cbproj`) + sequence files | `save`, `load`, `Project`, `OutputSettings`, `SCHEMA_VERSION`, `read_sequence_file` |
| `app` | the only layer that joins stages | the five services + `results.py` + `status.py` |
| `ui` | the one front end | `render/menus.py`, `render/console.py`, `present/*` |

---

## 3. Current architecture and call-flow map

### 3.1 The one front end

```
console script / python -m configbuilder
        │
        ▼
configbuilder/app/cli.py :: main()            (composition root; the single legal importer of ui)
        │  build_services()  ← configbuilder/ui/services.py
        │      projects       = ProjectService()
        │      configuration  = ConfigurationService(projects)
        │      variants       = VariantService(projects, configuration)
        │      validation     = ValidationService(projects)
        │      generation     = GenerationService(projects, validation, variants)
        ▼
configbuilder/ui/render/menus.py :: MenuApp(services, Console()).run()
        │  main menu: 1 New job | 2 Open a JSON file | 0 Exit
        │  job menu:  1 Edit job configurations | 2 Add entity | 3 Edit entity
        │             4 Custom CCD management | 5 Post-translational modification management
        │             6 Save and show summary | 7 Create variants based on this JSON
        │             0 Return to main menu
        ▼
configbuilder/ui/render/console.py :: Console  (write_line / prompt / read_multiline)
                                     ScriptedConsole (test harness, transcript capture)
```

`MenuApp` holds only three pieces of state of its own: `_current_path` (last save/open path),
`_saved_snapshot` (a deep copy of the last saved configuration, used for the unsaved-changes
flag), and the variant pair `_variant_base` / `_variant_name`. Everything else lives in the
services.

### 3.2 Create → validate → write (the save path)

```
MenuApp._save_and_summary                       menus.py:1431
  ├── _say_summary(configuration)               menus.py:1399  → _summary_of() menus.py:88
  ├── _ask_destination(...)                     menus.py:453   (text path, empty = default)
  ├── overwrite confirmation when the file exists
  └── _write_json(destination, name, overwrite) menus.py:1461
        ├── GenerationService.plan_save(destination, name, overwrite)   generation_service.py:514
        │     ├── ValidationService.validate_base()      → validation.validate(configuration, ctx)
        │     ├── to_wire(configuration)                 → transform/engine.py:216
        │     ├── resolve_resources_into(...)            → output/plan.py (copy assets)
        │     ├── with_wire_job_name + with_emitted_resource_paths  (engine.py §13.2/§13.5)
        │     ├── encode(document)                       → serialize/encode.py:56
        │     └── decide_action(path, payload, policy, filesystem)  → output/plan.py
        └── GenerationService.execute(plan)              generation_service.py:646
              └── output/execute.py::execute → atomic per-file write (temp + fsync + os.replace)
```

The preview and the file are **the same bytes**: `show_json` and `plan_save` both run
`to_wire → encode`, which is why the JSON preview is trustworthy (§4, row "JSON preview").

### 3.3 Open / import a job

```
main menu 2 → MenuApp._open_json_file                         menus.py:545
  ├── ProjectService.import_json_preview(path)                project_service.py:139
  │     └── _prepare_import → json.load → transform.from_wire(document) → (configuration, notes)
  │           · directory path, unreadable file, invalid JSON and model refusals all become
  │             (FailureReason, message) pairs — never exceptions
  ├── confirm screen (summary rows + notes)
  └── ProjectService.import_json_commit(path)                 project_service.py:176
        └── installs the *previewed* parse result (consume-once pending import), validates it,
            and replaces the project. The original file is never modified.
```

`ProjectService.open(path)` (the `.cbproj` project-file reader, `persistence/store.py::load`) is
implemented and tested but has **no front-end route** since the menu rework; `ProjectService`'s
own docstring records that the former working-copy autosave and `load_saved_work` recovery were
removed deliberately.

### 3.4 Entity editing

All editing is `ConfigurationService`, keyed by **registry-resolved entity id** (never list
position):

| Action | Symbol | Notes |
|---|---|---|
| add | `add_record(family, sequence, representation, copies, description, representation_kind)` :223 | protein/RNA/DNA/ligand; `copies>1` reserves an ordered multiplicity; **DNA always commits two records** (strand + reverse complement) |
| edit sequence/description | `update_record(record_key, sequence, description)` :369 | a DNA strand edit propagates to its partner; a lone imported strand is edited alone |
| delete | `remove_record(record_key)` :437 | deleting either DNA strand removes the **pair** and releases both ids |
| PTMs | `add_modification` :488, `remove_modification` :510, `update_modification` :532 | any record with `modifications` (protein, RNA, DNA) |
| ligand representation | `set_representation(record_key, codes, notation)` :565 | exactly one of CCD codes / SMILES |
| MSA / alignment | `set_alignment(record_key, mode, inline_text, external_path)` :599 | protein: automatic/free/unpaired/paired/both; RNA: automatic/free/provided; DNA: none |
| templates | `set_references(record_key, references)` :683 | protein `mmcifPath` |
| user CCD | `set_component_definition` :721 / `clear_component_definition` :731 | inline text XOR external path |
| bonds | `add_linkage` :746 / `remove_linkage` :761 | **implemented, no menu route** |
| job settings | `set_name` :159, `set_seeds` :198, `set_job_description` :177 (no menu route), `set_format_target` :779, `unset_format_target` :807 (no menu route) | |

### 3.5 Variants — and an important structural fact

There are **two different "variant" mechanisms in the codebase, and the menu uses the shallower one**:

* **Save-as copy (what the menu does).** `MenuApp._variant_menu` (`menus.py:1495`) snapshots
  `_variant_base = project.configuration`, then runs the *ordinary* entity menus against the live
  project, names the working copy, and writes it with `plan_save(destination, name=...)`
  (`_save_variant_and_reset`, `menus.py:1636`). Then `_reset_variant` (`menus.py:1664`) calls
  `ProjectService._replace_project(project.with_configuration(self._variant_base))` to restore the
  base. The base is never mutated; no variant inherits another's changes.
* **Spec-based variants (what the services implement).** `VariantService.add_spec`,
  `update_spec`, `remove_spec`, `duplicate_spec`, `add_spec_from_factor`, `append_factor`,
  `apply_variant_edit`, `preview`, `expand`, `edit_options`, `entity_choices`,
  `all_entity_choices`, `build_add_records`, `modification_summary`, `quantity_series_plan`,
  `create_quantity_series` — the full §12 machinery (`VariantSpec`, `Lineage`, `expand`,
  `apply_edit`, drift rule `R-VAR-001`). The menu reaches it **only** through
  `generate_from_file` (batch generation from a sequence/SMILES file), plus read-only
  `specs()`, `spec_count()`, `describe_spec_edits()` for the "list variants" screen.

Verified by static call-site scan of `menus.py`: the only service calls the menu makes are
`projects.{new, project, is_open, _replace_project, import_json_commit}`,
`configuration.{add_record, update_record, remove_record, add_modification,
update_modification, remove_modification, set_representation, set_alignment, set_references,
set_component_definition, clear_component_definition}`,
`variants.{generate_from_file, specs, spec_count, describe_spec_edits}`,
`validation.status`, and `generation.{plan_save, execute}`. Notably **absent**: `show_json`,
`validate_all`, `plan`, `plan_base`, `add_spec`, `apply_variant_edit`, `add_linkage`,
`set_job_description`, `open`.

### 3.6 Analysis / execution: out of GUI scope

* `configbuilder/` contains **no** AF3 invocation, no cluster submission, no network code —
  confirmed by scanning for `subprocess|os.system|slurm|sbatch|ssh|paramiko|requests|urllib`
  (only `.github/workflows/ci.yml` and the separate packages/tools match).
* `af3_analysis/` is a **separate pipeline** (`python -m af3_analysis ...`, its own `README.md`,
  its own `tests/analysis/`, optional third-party stack) that consumes AF3 *outputs*. It shares
  only `configbuilder.serialize.encode`.
* `tools/af3_validation/` is a manual validation harness (its `setup_validator.py` downloads the
  AF3 tarball via `urllib`), not part of the application.

**Recommendation:** keep both outside the GUI's first milestones. A "hand off to AF3 / analyse
results" launcher is a legitimate later feature, but it is not this GUI's job to replace them.

---

## 4. Capability inventory

Status key: **verified** = implemented and demonstrated by a passing test or an inspection of the
running code; **partial** = implemented but with a gap (missing route, missing test, or a defect);
**missing** = not present; **unknown** = could not be verified.

| Capability | Status | Evidence (paths, symbols) | Test coverage | GUI implication |
|---|---|---|---|---|
| New job with defaults (name, seeds, version pin) | verified | `app/project_service.py::ProjectService.new:70`; `app/status.py` `DEFAULT_SEED_VALUES=(1,)`, `DEFAULT_VERSION=3`, `AUTO_NAME_PREFIX="Untitled job "` | `tests/unit/app/test_status.py`, `tests/unit/ui/test_menu.py::test_new_job_add_save_produces_a_valid_json` | Home screen: "New job" needs one optional name field; defaults must be *shown*, not silent |
| Open an AF3 JSON file (preview + confirm + commit) | verified | `project_service.py::import_json_preview:161`, `import_json_commit:183`; reader `transform/from_wire.py` | `tests/unit/transform/test_from_wire.py`, `tests/unit/app/test_work_preservation.py` | File picker → preview dialog → commit. Reuse `ImportPreview.summary`/`.notes` verbatim |
| Save to a user-chosen path | verified | `menus.py::_save_and_summary:1431`, `_write_json:1461`; `generation_service.py::plan_save:514` | `tests/unit/ui/test_audit_regressions.py::test_save_action_writes_the_json_and_names_the_path` | Save dialog + overwrite confirmation; blocked-save must show status rows **and** finding cards |
| JSON preview, byte-exact and validation-gated | verified (no UI route) | `app/generation_service.py::show_json:96` — same `to_wire → encode` path, gated by `validate_base` | `tests/unit/ui/test_audit_regressions.py::test_json_preview_refuses_an_incomplete_job`, `::test_json_preview_of_a_ready_job_matches_the_written_file` | Perfect GUI feature: a read-only JSON pane. Wire it, do not re-implement |
| Validation feedback (44 rules, 5 tiers) | verified | `validation/catalogue.py` (`ROOT`7, `ENT`10, `MSA`5, `TPL`5, `BND`6, `VER`2, `VAR`2, `POL`7), `validation/engine.py::validate`, `validation/report.py` (`Finding`, `FieldPath`, `Report.blocking()`) | `tests/unit/validation/*`, `tests/contract/test_rule_completeness.py` | Findings carry `user_message`, `severity`, `paths` (a `FieldPath` with `type_name`/`record_key`/`field`) → jump-to-field is directly supported |
| Status view ("what's missing") | verified | `app/status.py::build_status:349`, `ConfigurationStatus`, `FieldState.{DEFAULTED,PROVIDED,NONE,MISSING,INVALID}` | `tests/unit/app/test_status.py` | A "Job readiness" panel; states are data, wording stays in `ui` |
| Proteins (sequence, description) | verified | `FamilyARecord`; `add_record("protein", …)` | `tests/e2e/test_entity_lifecycle.py`, `tests/unit/ui/test_menu.py` | Add/Edit protein form |
| RNA (sequence, description) | verified | `FamilyBRecord`; `add_record("rna", …)` | as above | Add/Edit RNA form |
| DNA **duplex** (one input, two strands) | verified | `_build_records:273` builds the reverse complement; `values.py::reverse_complement`; partner edits/deletes propagate | `tests/unit/model/test_dna_complement.py`, `tests/unit/app/test_dna_duplex.py`, `tests/golden/test_af3_pipeline_fixtures.py::test_dna_duplex_builds_reverse_complement` | GUI shows one row per duplex with an explicit two-strand view |
| DNA **single strand** (decline the complement) | **partial / defective** | `menus.py::_add_dna_with_complement_choice:846` loops `records[1:]` and calls `remove_record`, which deletes the **whole duplex** (`configuration_service.py::remove_record:437`). Reproduced: scripted menu run with answer "2" → `records == []`; and after a prior duplex, `records == []` again | **no test covers the "no" answer** (`tests/unit/ui/menu_flows.py::DNA` uses `"1"` = yes; `tests/e2e/test_entity_lifecycle.py::ADD_DNA` supplies no answer) | **Fix in core/Stage 0 or omit from the GUI.** A GUI checkbox "also add the reverse-complement strand" must not reproduce this |
| Ligands by CCD code(s) | verified | `ByCode`, `configuration_service.py::_ccds:347` (space/comma/semicolon separated multi-component) | `tests/unit/ui/test_audit_regressions.py::test_ccd_submenu_keeps_every_code_of_a_multi_component_ligand`, `::test_multi_component_ligand_reaches_the_wire_as_one_code_list` | Ligand form: radio "CCD code(s)" with a multi-token text box |
| Ligands by SMILES | verified | `ByNotation`; `_ligand_representation(kind="smiles")` | `tests/unit/ui/test_audit_regressions.py::test_single_code_and_smiles_routes_are_unchanged` | Same form, radio "SMILES". Mutual exclusion is structural (`ByCode` XOR `ByNotation`) |
| Ions | verified as *representation*, no separate entity type | `mappings.py:MAP-405` — an ion is expressed through the same `ccdCodes` field; `DOMAIN_MAPPING.md:140` forbids a standalone `ion` key | `tests/unit/transform/test_to_wire.py` | GUI: no "Ion" family; ions are a CCD-code ligand (e.g. `ZN`). Label it in the UI so users are not surprised |
| Ligand copy count (`copies>1`) | verified | `Multiplicity` allocation in `_build_records`; `SetComponentCount` in `variants/edits.py` | `tests/unit/ui/test_audit_regressions.py::test_multi_copy_ligand_is_deletable_through_the_menu` | A "number of copies" spin box for ligands; one row showing a shared id list |
| PTMs / modifications | verified | `add_modification`/`update_modification`/`remove_modification`; `ModificationRecord(code, position)` (1-based) | `tests/unit/ui/test_numbered_flows.py`, `tests/unit/ui/test_mod_display.py`, `tests/unit/app/test_edit_guards.py` | Repeating table (code + position) per polymer; validation rule `R-ENT-007` covers out-of-range positions |
| Custom CCD / user-defined components | verified | `set_component_definition`/`clear_component_definition`; wire `userCCD` (inline) XOR `userCCDPath` (v≥3) | `tests/unit/transform/test_to_wire.py`, `tests/unit/validation/test_rule_checks.py` (`R-ROOT-007`) | A "Custom components" panel with inline-paste vs file-path choice and a clear mutual exclusion |
| MSA (automatic / free / inline / external path) | verified | `set_alignment`, `alignment.py` (`AlignmentAutomatic`, `AlignmentFree`, `AlignmentUnpairedOnly`, `AlignmentPairedOnly`, `AlignmentBoth`, `SingleProvided`) | `tests/unit/ui/test_menu.py::test_editing_a_protein_asks_for_its_msa_and_templates`, `tests/unit/transform/test_to_wire.py` | Per-chain "MSA" group: mode dropdown + conditional source field. Default stays `Automatic` (do not change it) |
| Templates (`mmcifPath`) | verified | `set_references`, `references.py` (`SearchAllowed`, `Explicit`), `MAP-211` | `tests/unit/validation/test_rule_checks.py`, `tests/unit/transform/test_to_wire.py` | Protein-only "Templates" list of file paths; empty = "search allowed" |
| Batch generation from a sequence/SMILES file | verified | `VariantService.generate_from_file:826` → `persistence.read_sequence_file` / `read_smiles_file` → `app/batch_variants.py::batch_specs_for_sequences` → `add_spec` (all-or-nothing) | `tests/unit/app/test_batch_variants.py` | A "Batch from file" wizard: choose family, pick file, preview via `inspect_sequence_file` (**service-only today**), then commit |
| Spec-based variant editor (per-factor edits) | verified (no UI route) | `variants/spec.py`, `variants/edits.py` (18 edit classes + `apply_edit`, `describe_edit`), `variants/expansion.py::expand`, `VariantService.edit_options`/`apply_variant_edit`/`modification_summary` | `tests/e2e/test_app_pipeline.py`, `tests/unit/app/test_variant_service_gaps.py`, `tests/unit/variants/*`, `tests/variant/*` | The richest GUI opportunity: a variant *table* with typed edit rows instead of the copy-and-edit menu |
| Quantity series | verified (no UI route) | `VariantService.quantity_series_plan:734`, `create_quantity_series:770` | `tests/unit/variants/test_quantity_series.py` | A "series" dialog: start × factor × levels, with the plan previewed before commit |
| Variant save-as copy + reset to base | verified | `menus.py::_variant_menu:1495`, `_save_variant_and_reset:1636`, `_reset_variant:1664` | `tests/e2e/test_app_pipeline.py`, `tests/e2e/test_entity_lifecycle.py` | Reuse the same semantics (immutable base snapshot) in the GUI |
| Variant validation incl. drift (R-VAR-001/002) | verified (no UI route) | `ValidationService.validate_all:91`, `context.base_document` + `variant_documents` + `variant_declared_changes` | `tests/unit/validation/test_variant_rules.py`, `tests/e2e/test_app_pipeline.py` | A per-variant green/red column in the variant table |
| Bulk generate to a job layout + assets + manifest | verified (no UI route) | `GenerationService.plan:138`, `plan_base:376`; `output/plan.py` (`resolve_resources_into`), `output/manifest.py`, `output/naming.py::variant_directory_name` | `tests/unit/output/test_plan.py`, `tests/unit/output/test_manifest.py`, `tests/e2e/test_app_pipeline.py` | A "Generate all" action producing `<root>/<slug>/<slug>.json` + `assets/` + `manifest.json`; currently only `plan_save` (single file) is reachable |
| Covalent bonds / `bondedAtomPairs` | verified (no UI route) | `configuration_service.py::add_linkage:746`/`remove_linkage:761`; `Linkage`, `LinkEndpoint`; `validation/rules/bond_rules.py` (R-BND-001..006) | `tests/unit/validation/test_rule_checks.py`, `tests/unit/ui/test_audit_regressions.py::test_multi_component_glycan_can_be_bonded_residue_by_residue` | Add later: a bonds table (endpoint A, residue, atom) × 2. Needs its own screen |
| Job description | verified (no UI route) | `configuration_service.py::set_job_description:177`; `ConfigurationMetadata.description` as a Presence value | `tests/unit/ui/test_p1_fixes.py` (presence semantics) | One text field; note it is **not emitted to the wire** |
| Per-entity `description` field (JSON v≥4) | verified | `mappings.py:MAP-206/306/356/404` `DESCRIPTION_MIN_VERSION=4`; Presence algebra keeps unset≠empty | `tests/unit/ui/test_p1_fixes.py::test_sequence_only_edit_omits_description_in_wire_json` | A description box whose blank state means *omitted*; if used with a v3 pin, `to_wire` raises a named `TransformError` — the GUI must surface it as a warning **at entry time** |
| Version pin / dialect | verified | `FormatTarget`, `Pinned`/`Auto`/`Unverified`; `Dialect.STANDALONE_AF3="alphafold3"` only; `transform/engine.py::_select_version:92` | `tests/unit/validation/test_no_pin_document_dependency.py`, `tests/unit/model/test_configuration.py` | Version dropdown 1–4 (`menus.py:SUPPORTED_VERSIONS=(1,2,3,4)`), read-only dialect label, and a plain-language explanation of the feature-minimum rule |
| Import notes (dialect differ, unknown fields, etc.) | verified | `transform/from_wire.py::_root_version:484` (note when the imported dialect differs), `WireImportError` | `tests/unit/transform/test_from_wire.py` | Show `LoadOutput.warnings` and `ImportPreview.notes` in the import dialog |
| Unsaved-changes tracking | verified | `MenuApp._saved_snapshot`/`_has_unsaved` (`menus.py:487`), `ProjectService.is_dirty` | `tests/unit/ui/*`, `tests/e2e/*` | Window title marker + "discard changes?" prompt on New/Open/Close |
| Last-working-copy recovery / autosave | **missing by design** | `project_service.py` docstring; no `load_saved_work`; `.configbuilder/` is git-ignored residue | `tests/e2e/test_entity_lifecycle.py` docstring: "the rework removed the internal working-copy/recovery store" | The GUI must add its own dirty-state guard; there is nothing to recover today |
| `.cbproj` project file save/open | verified (no UI route, undocumented for users) | `persistence/store.py::save/load`, `persistence/schema.py` (`SCHEMA_VERSION=1`, named `UPGRADES`, `FutureVersionError`), `ProjectService.open` | `tests/unit/persistence/test_round_trip.py`, `tests/contract/test_project_file_contract.py` | **Decision needed:** expose a real "Save project / Open project" pair (ideal for a GUI, keeps variant specs) or leave it unused. It preserves specs and presence that JSON cannot |
| Sequence/SMILES file reading | verified | `persistence/sequences.py::read_sequence_file`, `read_smiles_file`; `VariantService.inspect_sequence_file:810` | `tests/unit/persistence/test_sequence_files.py` | Preview-before-commit for the batch wizard |
| Deterministic bytes (golden-testable output) | verified | `serialize/encode.py::encode:61` (UTF-8, no BOM, `indent=2`, LF-only, one trailing newline, `sort_keys=False`); no clock/host/randomness | `tests/serialization/test_encode.py`, `tests/serialization/test_cross_process_determinism.py`, `tests/golden/*` | The GUI must **never** write JSON itself — always `plan_save`/`execute` |
| Single-writer discipline for wire fields | verified | `transform/mappings.py` is the only place wire names live; `tests/architecture/test_wire_field_confinement.py` | same file | A GUI must not assemble wire dicts; a read-only JSON pane goes through `show_json` |
| AF3 execution / cluster submission | **missing** (out of scope) | no `subprocess`/slurm/ssh in `configbuilder/` | — | Keep out of the GUI, or add a later "hand off" launcher |
| A GUI of any kind | **missing** | `PySide6|PyQt|tkinter|wxPython|kivy` matches only the audit prompt | — | This report is the plan |

---

## 5. JSON contract findings and discrepancies

### 5.1 What the implementation actually emits (verified)

The emitted key order is fixed by `transform/engine.py::to_wire`:

```
name, modelSeeds, sequences, bondedAtomPairs, userCCD, userCCDPath, dialect, version
```

* `dialect` is always `"alphafold3"` — enforced by a one-member enumeration
  (`model/configuration.py::Dialect`, `R-ROOT-001`). No other dialect can be produced.
* `version` is always supplied by the version selection, never inferred: `Unverified` raises a
  named `TransformError`; `Pinned(n)` emits `n`; `Auto(evidenced)` emits `min(evidenced)`.
* Each entity is a one-key object (`{"protein": {...}}`), and per-family fields come from the
  mapping tables with a minimum version per field
  (`MSA_PATH_MIN_VERSION=2`, `TEMPLATE_PATH_MIN_VERSION=2`, `USER_CCD_PATH_MIN_VERSION=3`,
  `DESCRIPTION_MIN_VERSION=4`).
* `id` may be a **string or a list** when a record carries a copy multiplicity — the tests
  normalise this (`tests/e2e/test_entity_lifecycle.py::identifiers`).
* Ligand representation is exactly one of `ccdCodes` (possibly several codes = one
  multi-component ligand) or `smiles` (`ByCode` XOR `ByNotation`, `MAP-406`).
* `userCCD` and `userCCDPath` are mutually exclusive (`EmissionRule.INLINE_XOR_PATH`,
  `R-ROOT-007`).
* DNA: a DNA entity carries no alignment/template fields at all; `FamilyCRecord` has no
  alignment attribute (`model/records.py` module docstring, `DNA_FIELDS`).
* Sizing check: `ROOT_FIELDS`/`PROTEIN_FIELDS`/`RNA_FIELDS`/`DNA_FIELDS`/`LIGAND_FIELDS` cover the
  whole contract; `engine.to_wire` copies any extra key deterministically at the end, but
  "there are none today".

### 5.2 Discrepancies and items needing a decision

| # | Item | Competing evidence | Status |
|---|---|---|---|
| **D1** | **PySide6 vs the declared Python floor** | `pyproject.toml`: `requires-python = ">=3.9"`; CI matrix includes 3.9. PyPI metadata for PySide6 6.12.0 (read 2026-10-15): `Requires: Python <3.16, >=3.10`, classifiers `Python :: 3.10 … 3.15` | **Decision required.** Options: (a) declare the GUI an extra that requires `>=3.10` and leave the core at 3.9; (b) raise the project floor to 3.10 and drop the 3.9 CI row; (c) pin an older PySide6 that still ships 3.9 wheels. Note the GUI's own code must still satisfy `tests/architecture/test_baseline.py` if it lives under `configbuilder/` |
| **D2** | **Default JSON version** | `AUTHORITATIVE_SPEC.md:69`: "JSON version: `4` when using current AF3 features"; builder `app/status.py::DEFAULT_VERSION = 3`, justified in its own docstring (v3 is the minimum covering the core fields; v4 adds only textual descriptions) | **Documented mismatch, code is deliberate.** Needs a one-line annotation in the GUI's version control, e.g. "starts at 3 (minimum for the fields in use); raise to 4 to use per-entity descriptions" |
| **D3** | **Does a pin require an evidence reference?** | `docs/CONTRACT_PIN.md`: "**No accepted observation has been recorded yet**… until an operator pins a version and cites an observation here as its `evidence`, configurations remain `Unverified` and generation is blocked". Code: `validation/rules/policy_rules.py::check_r_ver_002` explicitly treats the evidence reference as *optional, never a condition for generating*, and blocks only the `Unverified` state; `ProjectService.new` pins `Pinned(3)` for every new job | **Doc-vs-code discrepancy (docs stale).** No GUI decision needed beyond wording; do not re-introduce a hard evidence gate in the GUI |
| **D4** | **Seeds: one or ten?** | Code default `DEFAULT_SEED_VALUES = (1,)`, documented as a deliberate starting default with the 10-seed comparison policy left to the user (`check_r_pol_004` emits INFO); `AUTHORITATIVE_SPEC.md` §14 requires only "at least one"; `tests/e2e/test_menu_acceptance.py:197` still expects `[1,2,3,4]` | **Code and spec agree; an e2e test is stale.** The GUI should show the default *and* offer the 10-seed policy explicitly (never silently) |
| **D5** | **Single-stranded DNA support** | Service: `add_record("dna", …)` always builds the duplex and refuses `copies != 1`; import: a lone DNA chain is a legal, editable state (`tests/unit/app/test_dna_duplex.py::test_a_lone_strand_is_edited_on_its_own`); menu: offers "No — use only the supplied strand" but the implementation deletes the whole duplex (defect) | **Decision + fix.** Does the builder support single-stranded DNA at all? (AF3 does not pair strands itself.) Either implement it in the service (a `single_strand`/`duplex` flag or an explicit "remove partner" service call) or remove the option and say so |
| **D6** | **Stale e2e keystroke scripts** | 13 failures caused by scripts expecting the pre-rework menu (missing DNA complement answer, `config-001` names, seeds `[1,2,3,4]`, old menu numbering) while the working tree has already reworked `menus.py` | **Decision required** (§10). Repair or retire; do not let the GUI inherit a red suite |
| **D7** | **Stale documentation that contradicts the running application** | `docs/PROJECT_AUDIT.md:50-91,306,367` and `JSON_BUILDER_AUDIT_AND_FINALIZATION.md:83-87,125-353` describe `.cbproj` autosave, "Open saved work", "Recover the last working copy" and a different menu. `configbuilder/app/project_service.py` and `menus.py` docstrings say that machinery was removed; `tests/unit/ui/test_audit_regressions.py:341` asserts no recovery vocabulary remains in user-visible strings | **Docs stale; code is authoritative.** Trust only `configbuilder/`, `tests/`, `AUTHORITATIVE_SPEC.md` and `docs/CONTRACT_PIN.md` for behaviour |
| **D8** | **Is `userCCD`/`userCCDPath` plus a CCD-code ligand the same thing?** | No: `userCCD`/`userCCDPath` are *root-level* custom component definitions (`MAP-105/106`), while `ccdCodes` names existing CCD components per ligand entity (`MAP-402/405`). Both are implemented; both are version-sensitive (path form needs v3) | **Verified consistent.** The GUI must keep these two concepts visibly separate or users will conflate them |
| **D9** | **Ion as its own entity family** | `mappings.py:MAP-405` comment and `DOMAIN_MAPPING.md:140` both refuse a standalone `ion` key; `add_record` accepts only protein/RNA/DNA/ligand | **Verified consistent.** GUI offers four families |
| **D10** | **PTM residue-position convention** | `ModificationRecord` stores a 1-based `Position`; `R-ENT-007` checks range against the parent sequence; the UI echoes the residue (`ui/present/sequence.py::residue_at`, `render_sequence_ruler`) | **Verified consistent (1-based).** Any GUI entry field must say "1-based" |

---

## 6. GUI integration map

Proposed screen/action → existing function(s) → adapter/refactor → risk. "Direct" means the GUI
can call the service as-is; "thin adapter" means a small controller function in the GUI layer that
sequences services and shapes data for widgets; "refactor" means the core needs a change first.

| # | GUI action | Existing call(s) | Adapter / refactor | Risk |
|---|---|---|---|---|
| 1 | New job (optional name) | `ProjectService.new(name)` | Direct. Read back `status.build_status` for the defaulted rows | None |
| 2 | Open JSON (picker) | `ProjectService.import_json_preview(path)` | Direct; render `ImportPreview.summary` (dict) + `.notes` | Low |
| 3 | Confirm import | `ProjectService.import_json_commit(path)` | Direct (consume-once pending import already guards against file-in-between) | Low |
| 4 | Edit job name | `ConfigurationService.set_name(name)` | Direct | None |
| 5 | Edit job description | `ConfigurationService.set_job_description(text)` | Direct — **note: not emitted to the wire**; label accordingly | Low (user expectation) |
| 6 | Edit seeds | `ConfigurationService.set_seeds(values)` | Thin adapter for tokenising a text field into ints; surface `R-POL-001/002` INFO | Low |
| 7 | Edit version pin | `ConfigurationService.set_format_target(version=…, evidence=…)`, `unset_format_target()` | Thin adapter; pre-check the feature minimums (description ⇒ 4, path fields ⇒ 2/3) to give an in-form warning instead of a `TransformError` at save | Medium (silent-upgrade temptation) |
| 8 | Add protein / RNA | `add_record(family, sequence)` then optionally `set_alignment` / `set_references` | Thin adapter: one dialog collects sequence + MSA mode + templates (mirrors `MenuApp._add_entity`'s chaining, but as one form) | Low |
| 9 | Add DNA | `add_record("dna", sequence)` | **Refactor first** (D5): either add a single-strand path to the service or drop the option. Never delete records by position from the GUI | **High** |
| 10 | Add ligand (CCD or SMILES, copies) | `add_record("ligand", representation=…, representation_kind="ccd"|"smiles", copies=n)` | Direct — the `representation_kind` parameter exists precisely for a UI submenu | Low |
| 11 | Entity list / detail | `project.configuration.records`, `_FAMILY_OF_TYPE` style mapping, `app/status.py::_record_counts`, `ui/present/labels.py::with_record_label` | Thin adapter to build a table model from records (+ `record.ids.ids` for multiplicity) | Low |
| 12 | Edit entity sequence/description | `update_record(record_key, sequence, description)` | Direct; show the duplex partner notice from `outcome.message` | Low |
| 13 | Delete entity (confirm) | `remove_record(record_key)` | Direct; confirm text should name the duplex consequence | Low |
| 14 | PTM table per polymer | `add_modification` / `update_modification` / `remove_modification` | Thin adapter for the 1-based position field; reuse `ui/present/sequence.py::residue_at` for the echo | Low |
| 15 | Custom CCD panel | `set_component_definition(inline_text|external_path)`, `clear_component_definition()` | Thin adapter enforcing "exactly one of the two" (the service refuses both/neither) | Low |
| 16 | MSA per chain | `set_alignment(record_key, mode, inline_text, external_path)` | Thin adapter: mode dropdown gates the source field; keep `automatic` the default | Low–Medium (must not change defaults silently) |
| 17 | Templates per protein | `set_references(record_key, ReferenceInput(...))` | Thin adapter (list of paths / inline) | Low |
| 18 | Bonds table | `add_linkage(a_key, a_residue, a_atom, b_key, b_residue, b_atom)`, `remove_linkage(index)` | Thin adapter; needs its own screen | Medium (endpoint vocabulary) |
| 19 | Variant editor (spec-based) | `VariantService.edit_options()`, `entity_choices(family)`, `all_entity_choices()`, `build_add_records(...)`, `apply_variant_edit(key, kind, value, record_key)`, `add_spec/update_spec/remove_spec/duplicate_spec`, `preview(key)`, `modification_summary(key)`, `describe_spec_edits(key)` | Thin adapter: a table of `(spec, declared edits)` rows built from the already-UI-shaped `VariantChoice` values. **No new edit vocabulary in the GUI** | Medium (rich surface, but the service already exposes UI choice tables) |
| 20 | Quantity series | `quantity_series_plan(keys, start, factor, levels)` then `create_quantity_series(...)` | Direct sequence: preview the plan, then commit | Low |
| 21 | Batch from file | `inspect_sequence_file(path)` (preview) → `generate_from_file(path, family)` | Direct; preview-before-commit already exists | Low |
| 22 | Variant validation | `ValidationService.validate_all(only=keys)` | Direct; render per-variant reports | Low |
| 23 | Generate all (layout + assets + manifest) | `GenerationService.plan(output_root, overwrite_policy, path_policy, only)` → `execute(plan)` | Direct; surface `GenerationPlan.conflicts` and `warnings` | Medium (this path is not exercised by today's menu) |
| 24 | Save one JSON | `plan_save(destination, name, overwrite)` → `execute(plan)` | Direct — reuse exactly; never write bytes in the GUI | None |
| 25 | JSON preview | `GenerationService.show_json(key=None)` | Direct; read-only pane, monospace | None |
| 26 | Validation / status panel | `ValidationService.validate_base()`, `.status()`; `ui/present/findings.py::format_findings`, `labels.py` | Direct; the finding card formatter is already width-aware and free of internal names | None |
| 27 | Jump-to-field from a finding | `Finding.paths[i]` = `FieldPath(type_name, record_key, field)` + `ui/present/labels.py::finding_context_label` | Thin adapter: map `record_key` → the entity page and `field` → the widget | Low |
| 28 | Save/open a project file (`.cbproj`) | `persistence.save(path, project)`, `ProjectService.open(path)` | **Decision needed** (D7): expose it and specs survive round-trips; `FutureVersionError` is already handled | Medium |
| 29 | Unsaved-changes guard | `ProjectService.is_dirty`; `MenuApp._has_unsaved` semantics | Thin adapter in the GUI's window controller | Low |
| 30 | AF3 execution / analysis | none in `configbuilder/` | **Out of scope**; `af3_analysis` stays a separate CLI | N/A |

### 6.1 What the GUI must never do

* Never build a wire dict or JSON string (single-authority: `transform` + `serialize`; enforced by
  `tests/architecture/test_wire_field_confinement.py`).
* Never allocate, rename or resolve entity ids (single-authority: `identity`;
  `tests/architecture/test_identity_authority.py`).
* Never delete a record by list position, or by iterating a family slice (that is the D5 defect).
* Never re-derive ready/not-ready: read `ValidationService.status()` /
  `validate_base().report.blocking()`.
* Never raise a traceback to the user: every service returns a result object; render
  `FailureReason` + `message`.

---

## 7. Proposed screen-by-screen workflow and text wireframe

Design rules for a non-programmer user: forms with labelled fields, dropdowns for vocabulary that
already exists as an enumeration (`AlignmentAutomatic`, `ByCode|ByNotation`, `OverwritePolicy`,
version 1–4), checkboxes only for real booleans, file pickers instead of path typing, and error
text taken from the registered wording rather than new prose.

### 7.1 Text wireframe

```
┌─ AF3 JSON Builder ────────────────────────────────────────────────────────────┐
│ [New job…] [Open JSON…] [Open project…]           job: oct4-pou ⬤ unsaved      │
├───────────────┬───────────────────────────────────────────────┬───────────────┤
│ JOB TREE      │ MAIN PANEL                                    │ READINESS     │
│               │                                               │               │
│ ▾ Job         │  ┌ Entity: A (protein) ────────────────────┐  │ Name   OK     │
│   Name   oct4…│  │ Sequence  [ACDEFGHIKLMNPQRSTVWY       ] │  │ Seeds  DEF    │
│   Seeds  1    │  │ Descrip.  [                            ] │  │ Version PIN3  │
│   Version 3   │  │ MSA       [Automatic ▾]                  │  │ Entities 3 OK │
│ ▾ Entities(3) │  │           ( ) inline  ( ) file [Browse] │  │ PTM     none  │
│   A protein   │  │ Templates [Search allowed ▾] [+ Add…]    │  │ CCD     none  │
│   B protein   │  │ Modifications  code  pos  [Add]          │  │ ───────────   │
│   C ccdCodes  │  │   SEP @ 4     [Edit] [Remove]            │  │ READY         │
│ ▾ Variants(2) │  └──────────────────────────────────────────┘  │               │
│   v1 seq A→G  │  [Add protein] [Add DNA] [Add RNA] [Add ligand]│  [Validate]   │
│   v2 Δseed    │                                               │  [Show JSON]  │
├───────────────┴───────────────────────────────────────────────┴───────────────┤
│ 1. ERROR  Protein A: position 99 is outside the sequence (1..20)   [Go there] │
│ 2. INFO   Seed list is not sorted (allowed: order is preserved)               │
├───────────────────────────────────────────────────────────────────────────────┤
│ [Validate] [Preview JSON] [Generate all…] [Save JSON…] [Save project…]        │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Screens

1. **Home / Start.** Two large buttons — **New job** (single optional name field; all other
   defaults shown as text: seeds `1`, version `3`, dialect `alphafold3`) and **Open JSON…**
   (`QFileDialog`), plus **Open project…** if D7 resolves to exposing `.cbproj`. Recent files are
   *recommended GUI behaviour*, not existing functionality.
2. **Import preview (modal).** Rows from `ImportPreview.summary` (`job_name`, `seed_values`,
   `entity_count`, `family_counts`, per-record ids) and every `notes`/`warnings` line; buttons
   `Import` / `Cancel`. Nothing is installed until Import (`import_json_commit`).
3. **Job window (the hub).** Left: a tree (`Job`, `Entities`, `Variants`). Centre: a stacked
   panel per selected node. Right: the readiness panel from `ValidationService.status()`.
   Bottom: the findings strip from `validate_base()` rendered with
   `ui/present/findings.py::format_findings`.
4. **Job settings page.** Name; description (labelled "project-side only, not written to the JSON
   file"); seeds (a tag field + "use the 10-seed comparison set" button — explicit, never
   automatic); JSON version combo 1–4 with a one-line explainer and a live warning when a used
   feature needs a higher version.
5. **Entity list + editor.** Table columns: id(s), family, length, description, MSA/templates
   state, modifications count. Editor page per family:
   * *protein*: sequence (monospace, with the ruler from `render_sequence_ruler`), description,
     MSA group, templates list;
   * *rna*: sequence, description, MSA group (no templates);
   * *dna*: **one row per duplex** showing both strands (given 5'→3' and its reverse complement)
     with an explicit checkbox "include the reverse-complement strand" — once D5 is fixed;
   * *ligand*: radio "CCD code(s)" (with an "ATP" / "NAG NAG BMA MAN MAN" hint) or "SMILES",
     plus the copies spin box for CCD groups. Ions: a hint that ions are entered as CCD codes.
6. **PTM page.** Per polymer chain: a repeatable row table (CCD code, 1-based position) with
   Add/Edit/Remove; refused edits show the service message inline.
7. **Custom components page.** Radio: "None" / "Paste definition" (multi-line) / "Load from file"
   (picker); explains `userCCD` vs `userCCDPath` and the v≥3 requirement.
8. **Bonds page.** Two endpoint blocks (entity, residue, atom) with Add/Remove; a table below.
9. **Variants / Batch page** (one combined workflow, as requested).
   * Variant table: key, label, declared edits (`describe_spec_edits`), per-variant validation
     state (`validate_all`), name.
   * "New variant" wizard driven by `VariantService.edit_options()` — one dropdown of change
     kinds, then the family/record pickers from `entity_choices`/`all_entity_choices`.
   * "Quantity series": start, factor, levels → `quantity_series_plan` preview → commit.
   * "From file…": family (protein/DNA/ligand), file picker, preview from
     `inspect_sequence_file`, then `generate_from_file`.
   * "Save this variant as JSON" and "Save all variants as JSON" via `plan_save`.
10. **Preview page.** Read-only, monospace JSON from `show_json(key)`; a "Copy" button; the save
    path in a status line. If the job is not ready the pane shows the same reason a save would.
11. **Generate page.** Output root picker; overwrite policy (Fail / Overwrite / Skip) and path
    policy (CopyIntoAssets / reference) as dropdowns; the plan's files, conflicts and warnings
    listed *before* Generate; then `execute` and a per-file result list.
12. **Save / close.** Save-to-path with overwrite confirmation; a dirty marker and a
    "discard changes?" prompt on New, Open and window close (no autosave exists to fall back on).

---

## 8. Recommended minimal GUI module structure (and why it must look like this)

### 8.1 The constraint the architecture tests impose

* `tests/architecture/test_layout.py::test_exactly_ten_top_level_packages` asserts
  `configbuilder/`'s subdirectories are **exactly** `{model, identity, validation, transform,
  serialize, variants, output, persistence, app, ui}`, and
  `::test_ui_has_the_two_declared_subpackages` asserts `ui/`'s are **exactly** `{render, present}`.
* `tests/architecture/test_dependency_rules.py::test_no_module_imports_app_or_ui` forbids any
  module whose family is neither `app` nor `ui` from importing `app` or `ui`; the entry-point
  exception is named explicitly as `configbuilder.app.cli`.
* `tests/architecture/test_ui_purity.py` pins `ui`'s permitted dependencies to `app` +
  `model` + itself, forbids `present` from touching streams/environment, and
  `tests/architecture/test_dependency_rules.py::test_no_module_outside_ui_render_branches_on_platform`
  confines `sys.platform`/`os.name` references to `ui/render`.
* `tests/architecture/test_baseline.py` keeps every `configbuilder` file Python-3.9-syntax-safe.

**Therefore:** a new top-level `configbuilder/gui/` package would (a) fail the layout test and
(b) fail the dependency test as soon as it imports `app`, `ui.present` or a service. Placing Qt
code directly in `configbuilder/ui/`'s root would fail the two-subpackage test. The clean
answer, requiring **no test changes**, is a new subpackage *inside* an existing family —
`configbuilder/ui/render/qt/` — whose modules are family `configbuilder.ui.render` and therefore
entitled to import `app`, `model.traceability` and `ui.present`.

### 8.2 Recommended structure (one new directory, one new module)

```
configbuilder/ui/render/qt/
    __init__.py        re-exports the launch entry point (no logic)
    application.py     the composition root helper: build_services() + QApplication + MainWindow
    state.py           SessionState: the open project, dirty flag, current path, variant base
    models.py          QAbstractTableModel adapters over records / specs / findings / status rows
    windows/main_window.py     the shell: menus, toolbar, dock panels, status bar
    pages/home.py              New job / Open JSON / Open project
    pages/job_settings.py      name, description, seeds, version
    pages/entities.py          entity table + per-family editor forms
    pages/entity_forms.py      protein/rna/dna/ligand field groups (widgets only)
    pages/ptm.py               modification table
    pages/components.py        userCCD / userCCDPath
    pages/bonds.py             linkage table
    pages/variants.py          spec table + new-variant wizard + series + file batch
    pages/preview.py           show_json pane
    pages/generate.py          plan display + execute
    dialogs/import_preview.py  import summary + notes
    dialogs/confirm.py         overwrite / delete confirmations
    findings.py        finding → card widget (reuses ui.present.findings/labels)
```

Plus two small declarations outside the package:

* `pyproject.toml` → `[project.optional-dependencies] gui = [...]` (or a floor change, per D1).
* `[project.gui-scripts]` → e.g. `af3-builder-gui = "configbuilder.ui.render.qt.application:main"`
  (consider whether a `.pyw`-style launcher is wanted on Windows so no console window appears).

**If** you prefer a first-class, explicitly-named `configbuilder/gui` package (better for
readability and for a thesis chapter), it is viable — but it is then a **deliberate architecture
change**: `EXPECTED_FAMILIES` in `test_layout.py` and the allow-lists in
`test_dependency_rules.py` must be amended *in the same commit*, with the rationale recorded in
`IMPLEMENTATION_PLAN.md §23` (which the layout test itself cites as the place new modules are
justified). Do not do this silently: those tests are the repository's guardrail against duplicated
validation/serialization logic.

### 8.3 Rationale

* **Reuse, don't re-implement.** The services are already front-end agnostic; the GUI is a
  second *render* layer, exactly what `ui/` is for (`configbuilder/ui/__init__.py` calls
  `ui/render` "the one front end", and the architecture tests make a second top-level front end
  expensive).
* **Keep wording in one place.** `ui/present/strings.py` (285 entries, with an integrity test
  `test_string_registry.py`) should grow the GUI's few new strings, or the GUI gets its own
  registry beside it; do not scatter literals.
* **Keep `ui/present` pure.** Finding-card and label formatting stay reusable in both front ends;
  the Qt widgets live in `render/qt`.
* **No threading at first.** Every service call is pure CPU/fast IO on a small in-memory model;
  run them on the GUI thread and keep the UI simple. Only bulk generation over many variants
  might eventually want a worker.

---

## 9. Staged implementation plan

Stages are dependency-ordered. Each lists likely modules, dependencies, acceptance criteria and
the tests that should gate it. **Nothing here is implemented yet.**

### Stage 0 — Resolve blockers and define the seam (no GUI code)

* Fix or drop the DNA single-strand option (D5): preferred fix is a service-level path
  (e.g. an explicit "remove the partner" / `duplex=False` argument on `add_record`) with a test
  proving a lone strand survives, edit, save and reopen; alternative is to remove the option.
  The **existing** failing behaviour is a front-end bug (§4) and must not be ported.
* Decide D1 (Python floor / PySide6 pin), D6 (repair or retire the 13 stale e2e tests) and D7
  (expose `.cbproj` or not).
* Write down the GUI↔core seam: which page maps to which service call (this report's §6 is the
  draft) and the rule "no wire bytes, no id allocation, no readiness re-derivation in the GUI".
* Acceptance: the suite is green (or its remaining failures are documented and agreed); the seam
  list is reviewed; `PySide6` installs and imports on the chosen interpreter.
* Tests: `python -m pytest -o addopts="" -q`; plus a one-off `python -c "import PySide6; print(PySide6.__version__)"`
  and a `QApplication`-with-`QTimer`-quit smoke script.

### Stage 1 — Runnable shell over sample data

* `configbuilder/ui/render/qt/{application,state,models,windows/main_window}.py` plus a
  `--demo` flag that populates a `Configuration` with one protein, one DNA duplex and one ligand
  via the services (never hand-built wire data).
* Acceptance: the window opens and closes cleanly; the entity table shows the sample records with
  the correct ids and counts; no service state is mutated by mere display; the app exits with
  code 0.
* Tests: a pytest smoke test that constructs the window with the offscreen Qt platform
  (`QT_QPA_PLATFORM=offscreen`) and asserts the table row count matches the configuration; keep it
  out of `tests/architecture` (it is allowed to import the GUI).

### Stage 2 — New job, Open JSON, job settings, summary, Save

* `pages/home.py`, `pages/job_settings.py`, `pages/preview.py`, `dialogs/import_preview.py`,
  `dialogs/confirm.py`.
* Acceptance: new job → add nothing → Save is **refused** with the same explanation the CLI gives
  (status rows + finding cards) and writes no file; new job + one protein → Save writes bytes
  identical to the CLI's for the same configuration; Save is byte-identical across two runs
  (determinism); Open JSON of a file written by the GUI round-trips; the import preview matches
  the file's contents; the JSON pane content equals the saved file exactly.
* Tests: reuse `tests/unit/ui/test_audit_regressions.py::test_json_preview_of_a_ready_job_matches_the_written_file`
  as the model for a GUI equivalent; add a test asserting the GUI's saved bytes equal
  `encode(to_wire(configuration))`.

### Stage 3 — Entity add/edit/delete

* `pages/entities.py`, `pages/entity_forms.py`.
* Acceptance: each family can be added/edited/deleted; DNA shows and edits both strands together;
  deleting either strand removes the pair and releases both ids; a multi-copy ligand is one row
  and releases every id on delete; every refused edit shows the service's message and changes
  nothing (no traceback).
* Tests: mirror `tests/unit/app/test_dna_duplex.py`, `tests/unit/app/test_edit_guards.py`,
  `tests/unit/ui/test_audit_regressions.py` (multi-copy cases) through the GUI controller.

### Stage 4 — PTMs, custom components, MSA/templates, bonds

* `pages/ptm.py`, `pages/components.py`, `pages/bonds.py`.
* Acceptance: `SEP @ 4` round-trips to `ptmType`/`ptmPosition`; an out-of-range position produces
  the `R-ENT-007` finding with a jump-to-field action; inline vs file for `userCCD`/`userCCDPath`
  is enforced with the version warning; MSA/template defaults are unchanged unless the user
  changes them; a linkage reaches `bondedAtomPairs`.
* Tests: mirror `tests/unit/validation/test_rule_checks.py`, `tests/unit/transform/test_to_wire.py`,
  `tests/unit/ui/test_numbered_flows.py` (PTM paths), `tests/unit/ui/test_audit_regressions.py`
  (glycan bonding).

### Stage 5 — Variants and batch generation

* `pages/variants.py` (+ a controller in `state.py`).
* Acceptance: create/edit/delete/duplicate a spec through the typed-edit wizard; a variant never
  mutates the base (`Configuration` equality before/after); `validate_all` shows per-variant
  state; drift (`R-VAR-001`) blocks generation with a named reason; a quantity series commits
  exactly the previewed specs; a file batch is all-or-nothing; each variant saves to its own JSON.
* Tests: mirror `tests/e2e/test_app_pipeline.py`, `tests/unit/variants/test_quantity_series.py`,
  `tests/unit/app/test_batch_variants.py` at the controller level.

### Stage 6 — Validation UX, JSON preview polish, save robustness

* `findings.py`, `pages/generate.py`, better blocked-save screens, jump-to-field navigation.
* Acceptance: every `FieldPath` a rule emits resolves to a widget or a clearly-labelled fallback;
  overwrite/conflict handling matches `output/policies.py`; a filesystem refusal (reserved name,
  read-only directory) is reported as a message, not a traceback; the JSON pane and the file agree.
* Tests: mirror `tests/unit/output/test_execute.py`, `::test_execute_atomicity.py`,
  `tests/unit/ui/test_present_formatting.py`.

### Stage 7 — Regression, usability, packaging

* Acceptance: the tracked suite is green under both entry points; a Windows packaging route
  (PyInstaller or an `.[gui]` extra + console-less launcher) is chosen and documented; a short
  usability pass with a non-programmer covers New → 4 families → PTM → save → reopen → variant →
  batch → generate; the README/`THESIS_IMPLEMENTATION_CHAPTER.md` describe the GUI accurately.
* Tests: full suite on the chosen interpreter(s), plus one golden byte-comparison of a GUI-made
  job against a fixture under `fixtures/golden`.

---

## 10. Risks, unknowns and decisions requiring human review

**Decisions (blocking or shaping Stage 0/1)**

* **D1 — Python floor vs PySide6.** Raise the floor to 3.10 (and drop the 3.9 CI row), or keep 3.9
  and pin an older PySide6, or ship the GUI as a `>=3.10` extra. Evidence: PyPI metadata for
  PySide6 6.12.0; `pyproject.toml`; `.github/workflows/ci.yml`.
* **D5 — Single-stranded DNA.** Fix in the service, or remove the option. Evidence:
  `menus.py:846` + `configuration_service.py:437` + reproduced run.
* **D6 — the 13 stale e2e tests.** Repair (add the DNA complement answer, update defaults/menu
  numbering) or retire them. Evidence: §2.4.
* **D7 — expose `.cbproj`?** `persistence` can save/load a project file that *keeps variant specs
  and presence states*, which plain JSON cannot. Cheap in a GUI, currently undocumented for users.
* **D8 — GUI location.** `ui/render/qt/` (no test changes) vs. a new `configbuilder/gui` family
  (requires amending `test_layout.py` + `test_dependency_rules.py` + a plan §23 entry).
* **D9 — scope of "variants" in the GUI.** Ship the spec-based table (rich, service-supported) or
  first mirror the menu's save-as-copy workflow. The spec route is more capable and better tested
  at the service layer; it is also more work.

**Risks**

* **Silent-default traps.** `ProjectService.new` pins version 3 and one seed while
  `docs/CONTRACT_PIN.md` talks about an evidence-gated pin and the analysis SOP uses wider seed
  sets. If the GUI hides these, users will generate files they did not intend. Mitigation: show
  defaults as first-class fields with their provenance (`FieldState.DEFAULTED`).
* **Version-feature mismatch.** A description with a v3 pin raises `TransformError` at save time.
  Mitigation: pre-empt in the form (Stage 2/4).
* **Regression risk on golden bytes.** The repository gates output bytes with golden fixtures. Any
  GUI that influences ordering (e.g. a table that re-sorts records) can change output. Mitigation:
  the GUI must never reorder `configuration.records`; sorting belongs in the view only.
* **Testing a GUI without a display.** Qt needs `QT_QPA_PLATFORM=offscreen` on CI; the existing
  architecture tests must not be allowed to import Qt.
* **Working-tree churn.** The audit ran against a worked-on tree; committing that state (or not)
  changes the baseline for every later stage.

**Unknowns / not verifiable from the repository**

* Whether the *deployment* accepts a given JSON version: `docs/CONTRACT_PIN.md` records **no
  observation**, so this is genuinely unknown and is by design the operator's call.
* Whether the university's AF3 run consumed files built by *this* revision (the prompt says some
  files ran successfully; the repository contains `generated_jobs/*/VALIDATION_REPORT.md` and
  `output/oct4-pou/` artefacts, but I did not treat those reports as proof about this revision).
* Whether PySide6 will be installed on the target Windows machine and with which Qt platform
  plugins (packaging decision, Stage 7).
* Any user-facing expectation about mouse/keyboard-only operation, screen-reader support or DPI
  scaling — not specified anywhere in the repository.
* `freesasa` is not installed here; three `tests/analysis/*` modules use `importorskip`, so their
  real behaviour was not exercised (they did not skip in this run because their imports are
  `numpy`/`pandas`/`matplotlib` — but the SASA path is worth a second look during Stage 7).

**Deliberately not done in this audit** (per the constraints): no bug was fixed, no dependency
installed, no test modified, no Git state changed.

---

## 11. Recommended first implementation milestone

**"Review & Preview" — a read-only window over an existing job.**

Deliverable: `configbuilder/ui/render/qt/` with `application.py`, `state.py`, `models.py`,
`windows/main_window.py`, `pages/entities.py` (table only) and `pages/preview.py`; launched by an
opt-in extra so the core stays dependency-free.

Why this first:

1. It exercises the **entire integration seam** (services → adapter → widgets) without touching a
   single write path, so it cannot regress the JSON contract.
2. Its core features **already exist and are tested** at the service level —
   `GenerationService.show_json`, `ValidationService.status`, `validate_base`,
   `ui/present/findings.format_findings` — so the milestone is mostly wiring, and its failure modes
   are the cheap kind.
3. It immediately gives the user something real: open an existing AF3 JSON (including the
   `generated_jobs/` and `output/` artefacts in this repo), see its entities, PTMs, MSA/template
   state and validation status, and read the exact JSON that a save would produce.
4. It answers the biggest open UX questions (screen layout, how much detail a per-entity page
   needs, whether the readiness panel reads clearly) **before** any mutation code exists.

Concrete acceptance criteria:

* Opens an existing AF3 JSON through the same `import_json_preview` / `import_json_commit` pair the
  CLI uses, and displays every entity with its real id(s), family, length, MSA/template state and
  modification count.
* Shows the readiness panel and the full finding list for the open job, with a jump-to-entity
  action for findings that name a `record_key`.
* Shows a read-only JSON pane whose text equals the bytes a save would write
  (`show_json`), or the precise reason it cannot be shown, and writes nothing to disk.
* Adds no new dependency to the `configbuilder` core (the GUI stack is an extra), changes no
  architecture test, and leaves `python -m pytest -o addopts="" -q` at or better than the
  baseline recorded in §2.4.

---

## Appendix A — Verification commands used in this audit (all read-only)

```
git status --porcelain / git rev-parse --abbrev-ref HEAD / git log --oneline -5
python --version ; python -c "import importlib, ..."          # interpreter and dependency probe
python -m pytest -o addopts="" -q                             # 13 failed, 990 passed, 1 skipped
python -m pytest --collect-only -q                            # 1004 collected
python -m pytest -o addopts="" -q -rs                         # the skip's reason
python -c "<scripted MenuApp run over ScriptedConsole>"       # the DNA single-strand reproduction
```

The scripted-menu probes construct services in memory only; they read no user file and write
nothing to disk (confirmed by inspecting the scripts: neither calls a save action).

## Appendix B — Files read for this report (selection)

`pyproject.toml`; `.github/workflows/ci.yml`; `AUTHORITATIVE_SPEC.md` (contract/version sections);
`DOMAIN_MAPPING.md`; `docs/CONTRACT_PIN.md`; `configbuilder/{app/cli,__main__,ui/services,
ui/render/menus,ui/render/console,app/{project,configuration,variant,generation,validation}_service,
app/{results,status,batch_variants},model/{configuration,records},identity/registry,
transform/{engine,mappings,from_wire},serialize/encode,output/{execute,naming},
persistence/schema,validation/{report,catalogue},validation/rules/policy_rules,
variants/{spec,edits,expansion}}`; `tests/architecture/{_scanner,test_layout,test_dependency_rules,
test_ui_purity,test_baseline,test_suite_integrity}`; `tests/{unit/app/test_dna_duplex,
unit/ui/{test_menu,menu_flows},e2e/{test_entity_lifecycle,test_menu_acceptance}}`.
