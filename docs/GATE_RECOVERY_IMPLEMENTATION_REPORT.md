# Gate Recovery — Implementation Report

**Date:** 2026-10-25
**Branch:** `main` at `347620f` (`origin/main` is the same commit)
**Scope:** Implementation of the decisions approved in
`docs/GATE_AUDIT_AND_RECOVERY_REPORT.md` §12 (version, external MSA, SMILES,
variant enforcement, readiness/gate consistency, manifest, tests/CI).
**Constraint honoured throughout:** no AF3 run, result directory, completion
marker, log, ranking score or prediction status is consulted anywhere in the
builder, and none was reintroduced.

---

## 1. Initial Git state (Phase 0)

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `347620f` — “Make MSA and template inputs complete and validated” |
| `origin/main` | `347620f` (identical: no ahead/behind) |
| Preceding GUI-sync/push task | **Already completed and pushed** — the branch is in sync with `origin/main` and the working tree carries no new commits |
| Recent commits | `347620f`, `84198f6`, `28e0534`, `85a606a` (the gate-removal commit), `ea6eec3`, `e8bd15a` |
| Uncommitted work inherited | 20 modified tracked files (`configbuilder/app/*`, `configbuilder/validation/*`, `configbuilder/ui/*`, `.gitignore`) — the partial restoration described in the audit |
| Ignored/untracked work inherited | `tests/`, `docs/`, `fixtures/`, `.github/`, `AUTHORITATIVE_SPEC.md`, `DOMAIN_MAPPING.md`, `RUNNING_THE_APPLICATION.md`, `THESIS_EXPANDED_DRAFT.md`, `tools/af3_validation/README.md` |

Nothing was discarded, reset, stashed or reverted. No conflict with other work
was found: the modified files were exactly the partial restoration the audit
examined, and they were extended rather than replaced.

---

## 2. Changes implemented

### 2.1 Version validation — one authoritative rule

* `configbuilder/model/configuration.py` now owns the version set:
  `SUPPORTED_INPUT_VERSIONS = (1, 2, 3, 4)` and `DEFAULT_INPUT_VERSION = 3`,
  exported through `configbuilder.model`. `app/status.DEFAULT_VERSION` reads the
  model constant instead of repeating `3`, so the console prompt, the GUI picker
  and the availability rule can no longer disagree.
* **R-VER-001 alone** owns “an explicit version has been selected”
  (`Unverified` is the blocking state). Its wording no longer asks for
  deployment evidence; it names the supported versions.
* **R-ROOT-002** was rewritten to the meaning its summary always claimed: the
  selected version is *supported* (`Pinned`, or `Auto` resolving to the minimum
  evidenced version). It returns silently on `Unverified`, so one missing
  selection produces **one** finding.
* Catalogue summaries for both rules updated to match the behaviour.
* `DEFAULT_INPUT_VERSION` is still pinned on a new job and preserved through
  open/edit/save (`_select_version` and serialisation untouched apart from
  reading the shared constants).

### 2.2 External MSA validation — new blocking preflight

* New rule **`R-MSA-006`** (`Tier.PREFLIGHT`, `Severity.ERROR`, spec §11 “MSA
  Contract”): every configured external MSA file must be an existing, readable,
  non-empty **regular** file.
  * Covers protein `unpaired` / `paired` / `both` (both sides, deduplicated when
    one file feeds both) and RNA `provided`.
  * `automatic` and `free` carry no source and are never reported, so MSA search
    and no-MSA configurations stay valid; paired-only and unpaired-only
    configurations stay supported.
  * With no filesystem port the rule reports “not checked” as a **WARNING**
    (`NullFilesystemPort`), never a false error.
* The file half was **moved out of `R-MSA-003`**, which now checks inline content
  only; the two rules no longer double-report and cannot drift apart.
* New production port **`OsFilesystemPort`** (`validation/ports.py`):
  `os.path.isfile` + non-zero size + `os.access(R_OK)`, wrapped so any `OSError`
  answers `False`. It reads no content and creates nothing.
* `build_services()` wires it, so **CLI and GUI** refuse save, preview and
  generation for a missing/empty/readable-denied/directory path, and the
  Overview readiness line reports the same finding.

### 2.3 Production SMILES validation

* `R-ENT-010` now calls the chemistry port defensively: a parser that **raises**
  on malformed notation produces this rule's blocking finding naming the
  failure (`type(error).__name__: message`) instead of crashing the CLI or GUI.
  A parse refusal is an ERROR; a missing probe still downgrades to the documented
  WARNING “not checked”.
* **No parser is wired in production.** See §8.1: no SMILES parser exists in the
  project's dependency set, and adding one is a dependency decision this report
  hands back rather than takes.

### 2.4 Variant-generation enforcement

* `GenerationService` accepts an optional `validation` service and gains:
  * `_gate_base()` — `GATE_TIERS` over the base, run **before** any expansion in
    `plan()`, `plan_base()`, `plan_save()` and `show_json()`;
  * `_variant_validation()` / `_variant_gate()` — the full catalogue
    (`ValidationService.validate_all(only=…)`), i.e. `R-VAR-001` drift and
    `R-VAR-002` identity stability, run **before** any document is transformed
    or written;
  * a refusal returns `FailureReason.VALIDATION_BLOCKED` with the findings and a
    `refused_scope` of `"base"` or `"variant"`, so no partial batch is produced
    and the UI can label the findings.
* Variant previews run the same variant gate. The Variants page keeps its
  page-level full-catalogue review; generation no longer trusts it to be the
  only enforcement.
* The base job is **not** required to have been executed: the comparison inputs
  are wire documents built in memory.

### 2.5 Readiness and gate consistency

* `ValidationService.GATE_TIERS = (STRUCTURAL, RELATIONAL, CONTRACT, PREFLIGHT)`
  is now the single definition of “this configuration can be written”.
  `status()`, `plan_save()`, `show_json()`, `plan()` and `plan_base()` all run it
  through the same `validate_configuration()` call and the same context join.
* The audited defect — `status.ready == False` while `plan_save` succeeded on a
  real blocking chemistry finding — is fixed and pinned by
  `test_blocking_chemistry_finding_agrees_between_status_and_save`.
* `VARIANT` is deliberately **not** in the gate tiers: readiness describes the
  base job, variants are enforced on their own path (and on their own page).
* Advisory findings (INFO/WARNING) still do not block — pinned by
  `test_advisory_warnings_do_not_block_a_valid_save`.

### 2.6 Validation report in generated manifests

* `GenerationService` passes the **combined** report (base findings, then each
  variant's, in key order) to the manifest builder as `validation_report`.
* When no validator is wired the report is `None`, so `validation_summary` stays
  empty rather than claiming a clean run.
* The stale golden manifest fixture was regenerated through the sanctioned
  generator (`fixtures/` → `tools`-independent fixture builder), and golden tests
  pass byte-for-byte.

### 2.7 UI feedback (same rules, both front ends)

* Overview regained one compact readiness line plus a quiet *Validate job*
  action, both reading `ValidationService.status()` — no list, no page-local
  logic.
* Save and Generate on the GUI render the blocking findings from the plan
  (`gui.blocked_header*`, `gui.output_findings_*`), including the
  `refused_scope == "variant"` wording.
* The console's blocked save/preview path names the same findings
  (`menu.save_job_blocked` + status rows).
* The Variants page shows the full-catalogue verdict per variant (drift,
  identity, its own findings). Preflight MSA findings are base-level: they make
  the readiness line say *“Not ready: N blocking finding(s)”* and appear with
  their own message in the save/generate refusal — there is no per-record MSA
  row on Overview, and none was invented.

### 2.8 Tests and CI

* `.gitignore` no longer excludes `tests/`, `fixtures/`, `docs/` or `.github/`
  wholesale; the header comment records why and what stays out
  (`af3_analysis/`, `generated_jobs/`, `.stage*`, `pytest-of-*/`,
  `.pytest-tmp/`, `/testdata/`, planning documents).
* The CI workflow exists again at `.github/workflows/ci.yml` — byte-identical
  to the one `85a606a` deleted — and runs the suite without the optional `gui`
  extra (GUI modules self-skip when PySide6 is absent).
* `pyproject.toml` regained the two things the same commit stripped from it,
  without which that workflow cannot run on a fresh clone:
  * `[project.optional-dependencies] dev = ["pytest>=7", "hypothesis>=6"]`
    (CI installs `-e ".[dev]"`);
  * `[tool.pytest.ini_options] testpaths = ["tests"]`, `addopts = "-q"`
    (CI's `-o addopts=""` override now refers to an option that exists again).
* The suite itself is present and green (see §6). It is **not yet committed** —
  see §7.3.

---

## 3. Gates restored, consolidated, or deliberately retained

| Gate / check | Status | Where |
|---|---|---|
| Explicit version selected (`Unverified` blocks) | **Consolidated** into `R-VER-001` only | `rules/policy_rules.py` |
| Selected version is supported | **Restored as a real check** (`R-ROOT-002`) | `rules/root_rules.py` |
| External MSA file usable | **New blocking preflight** (`R-MSA-006`) | `rules/msa_rules.py`, `ports.OsFilesystemPort` |
| Inline A3M shape / rectangularity | **Retained**, file half removed (now `R-MSA-006`) | `rules/msa_rules.py` |
| SMILES parses (with a real checker) | **Restored as blocking**, exception-safe | `rules/entity_rules.py` |
| SMILES “not checked” without a checker | **Retained** as advisory WARNING | `rules/entity_rules.py` |
| Variant drift `R-VAR-001` / identity `R-VAR-002` | **Restored at generation** (`validate_all` before writes/preview) | `app/generation_service.py` |
| Readiness == gate | **Restored** via one `GATE_TIERS` definition | `app/validation_service.py`, `app/status.py` |
| Manifest validation summary | **Restored** (real report, empty when unwired) | `app/generation_service.py` |
| AF3 execution / result-directory / completion-marker / log / ranking gates | **Absent — not reintroduced** | — |

---

## 4. Confirmation that AF3 execution-success requirements are absent

* No rule reads a result directory, prediction, completion marker, log, ranking
  score or execution flag. `test_no_hidden_execution_status_gate` scans the
  source of every rule implementation for those markers.
* `GenerationService` docstrings and `GATE_TIERS` state the contract: every gate
  tier is decidable in-process from the configuration and the shallow ports.
* A repository-wide grep of `configbuilder/` finds the words “prediction”,
  “executed” and “AF3 run” only in docstrings that say they are **not**
  consulted, plus one unrelated UI comment about a plan being “executed” (i.e.
  written).
* Regression tests pin the outcome: a valid JSON is created, saved, reopened and
  turned into variants with no prediction anywhere on disk
  (`test_valid_json_saves_without_any_af3_run`,
  `test_variant_generation_needs_no_prior_af3_run`,
  `test_reopening_a_saved_job_needs_no_af3_output`).

---

## 5. CLI/GUI consistency findings (Phase 2)

* There is **one composition root**: `ui/services.build_services()` constructs
  `ProjectService`, `ConfigurationService`, `VariantService`,
  `ValidationService(filesystem=OsFilesystemPort())` and
  `GenerationService(..., validation=validation)`. The console
  (`app/cli.py` → `MenuApp`) and the GUI (`GuiState` → `MainWindow`) both receive
  that same bundle; neither builds a validator, a port or a rule of its own.
* Save, preview and generation are one code path
  (`GenerationService.plan_save` / `show_json` / `plan`), so the refusal text and
  the finding set are identical by construction. Readiness is
  `ValidationService.status()` in both.
* Verified on the audited MSA case (one job with an `unpaired` source pointing
  at a non-existent `.a3m`):
  * the console's own calls (`validation.status()` + `generation.plan_save`)
    reported `ready = False`, blocking `[('R-MSA-006', 'ERROR')]`,
    `failure_reason = validation_blocked`, and the message *“The MSA file of
    record 'A' is not usable: '<path>' is missing, empty, unreadable, or not a
    regular file.”*; since the GUI calls exactly the same two methods, that is
    its message too;
  * the GUI half is pinned as a test,
    `tests/gui/test_readiness.py::test_a_missing_msa_file_blocks_readiness_and_save`:
    `state.status()` is not ready with `R-MSA-006` blocking, the Overview verdict
    matches the service's blocking count, Save refuses, nothing is written, and
    the blocking header is shown.
* MSA choices (automatic / free / external single, and separate paired +
  unpaired sources) and the template pairing/multi-file flow are unchanged in
  both front ends; their tests pass (`tests/unit/app/test_gate_recovery.py`,
  `tests/gui/test_advanced_settings.py`, `tests/e2e/*`).
* **Template-chain bounds remain unverifiable**: there is still no mmCIF parser
  in the project, so no bounds or residue mappings were invented. Only file
  existence/readability and the service's existing pair checks are enforced.
  (Follow-up 2026-10-27: an attached template's file is now read as mmCIF — an
  established parser when installed, the bundled lexical scan otherwise — so a
  file that is not a structure is refused. Bounds and residue mappings are still
  not derived: `docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §2.)

---

## 6. Tests run and actual results

Environment: Windows, Python 3.11.15, pytest 8.2.2, PySide6 6.12.0 (the optional
`gui` extra, installed for this run).

| # | Command | Result |
|---|---|---|
| 1 | `python -m compileall -q configbuilder` | exit 0 (no output) |
| 2 | `python -m pytest --ignore=tests/gui -p no:cacheprovider` (final state, after `pyproject.toml` regained `testpaths`/`addopts`) | **1096 passed, 1 skipped, 1 warning in 169.17 s** (exit 0) |
| 3 | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -p no:cacheprovider --basetemp=.pytest-tmp -o addopts=""` (final state) | **290 passed in 62.03 s** (exit 0) |
| 4 | `python -m pytest tests/unit/app/test_gate_recovery.py -q` | 27 passed |
| 5 | `python -m pytest tests/gui/test_readiness.py -q --basetemp=.pytest-tmp` | 8 passed |
| 6 | `python -m pytest tests/gui/test_advanced_settings.py -q --basetemp=.pytest-tmp` | 72 passed |

Totals: **1386 passed, 1 skipped** (1096 + 290). The single skip is
`tests/unit/persistence/test_sequence_files.py::test_unreadable_file_is_a_clear_persistence_error`,
which is `skipif(os.name == "nt")` because Windows cannot express a read-denied
file through `chmod`.

Notes on the GUI run:

* Without `--basetemp` in the workspace, `tests/gui` hangs on this machine: the
  launch tests run `gui.py`, which starts the project venv
  (`.venv-gui/Scripts/python.exe`), and that interpreter cannot write into
  `%LOCALAPPDATA%\Temp` here (a `PermissionError` in `sitecustomize`), so the
  auto-close hook never installs and the child GUI never exits. With
  `--basetemp=.pytest-tmp` both launch tests finish in ~3 s and the suite is
  green. This is an environment limitation, not a code defect; the directory is
  now ignored.
* GUI modules skip themselves when the `gui` extra is missing, which is what CI
  does (it does not install PySide6). With PySide6 installed, a bare `pytest`
  now collects the GUI tests too (restored `testpaths`), so pass
  `--ignore=tests/gui` for a core-only run.

Targeted scenarios now covered (new `tests/unit/app/test_gate_recovery.py`, 27
tests): version default/preserve/single-finding; save without any AF3 run;
automatic/free MSA; valid, missing, empty and directory MSA paths; paired and
unpaired sources kept; `R-MSA-006` null-port warning; invalid SMILES blocked with
a real probe, valid SMILES accepted, probe exceptions reported not raised, null
probe downgraded, production wiring claims no SMILES guarantee; valid variant
passes; invalid base cannot bypass; variant generation without a prior run;
blocking leaves no partial output; blocking variant refuses generation before any
write; audited readiness/save disagreement fixed; advisory warnings do not block;
manifest records the summary; no hidden execution gate; save/reopen round trip.

Beside the new file, the recovery updated tests that encoded the removed
behaviour: `tests/unit/validation/test_catalogue.py`,
`tests/unit/validation/test_engine.py`, `tests/contract/test_rule_completeness.py`,
`tests/contract/test_catalogue_traceability.py` (MSA count 5 → 6, §19 spec row),
`tests/unit/persistence/test_versions_and_corruption.py` (duplicate version
finding), `tests/gui/test_advanced_settings.py` (external MSA fixtures now point
at real files, because a made-up path is now blocking by design), and
`AUTHORITATIVE_SPEC.md` §19 “MSA validation” gained the row the new rule cites.

Not run: none of the requested categories was skipped. `af3_analysis` and
`tools/af3_validation` were left alone (out of scope); their tests are not part
of this suite.

---

## 7. Files added, modified, restored, still untracked

### 7.1 Modified (tracked, uncommitted) — 21 files

```
.gitignore
pyproject.toml
configbuilder/app/generation_service.py
configbuilder/app/results.py
configbuilder/app/status.py
configbuilder/app/validation_service.py
configbuilder/model/__init__.py
configbuilder/model/configuration.py
configbuilder/ui/render/qt/models.py
configbuilder/ui/render/qt/pages/generate.py
configbuilder/ui/render/qt/pages/overview.py
configbuilder/ui/render/qt/pages/variants.py
configbuilder/ui/render/qt/state.py
configbuilder/ui/render/qt/windows/main_window.py
configbuilder/ui/services.py
configbuilder/validation/__init__.py
configbuilder/validation/catalogue.py
configbuilder/validation/ports.py
configbuilder/validation/rules/entity_rules.py
configbuilder/validation/rules/msa_rules.py
configbuilder/validation/rules/policy_rules.py
configbuilder/validation/rules/root_rules.py
```

### 7.2 Added during this task

* `tests/unit/app/test_gate_recovery.py` (new, 27 tests).
* `tests/gui/test_readiness.py::test_a_missing_msa_file_blocks_readiness_and_save`
  (new test in an existing file).
* `docs/GATE_RECOVERY_IMPLEMENTATION_REPORT.md` (this report).

### 7.3 Restored to `.gitignore` eligibility, **not yet staged or committed**

232 paths are untracked; 230 of them are the recovery set (the rest are the
thesis draft and a scratch `test.json`, both listed below). They are:

| Area | Files | Contents |
|---|---|---|
| `tests/` | 161 | the whole suite (`unit`, `e2e`, `contract`, `architecture`, `golden`, `variant`, `gui`) and `tests/fixtures/` |
| `docs/` | 53 | `CONTRACT_PIN.md`, audit/QA reports, implementation maps, screenshots |
| `fixtures/` | 11 | golden recipes, compatibility `.cbproj` files, builder fixtures |
| `.github/` | 1 | `workflows/ci.yml` |
| `tools/` | 1 | `tools/af3_validation/README.md` |
| root | 3 | `AUTHORITATIVE_SPEC.md`, `DOMAIN_MAPPING.md`, `RUNNING_THE_APPLICATION.md` |
| root (kept out) | 1 | `THESIS_EXPANDED_DRAFT.md` |

Deliberately **not** part of the recovery commit:

* `THESIS_EXPANDED_DRAFT.md` — an authoring draft, unrelated to the builder.
* `test.json` (repo root, 399 bytes) — a scratch job document left by a manual
  run; not a fixture.
* `af3_analysis/`, `generated_jobs/`, `/output/`, `/testdata/`, `.stage*`,
  `pytest-of-*/`, `.pytest-tmp/`, `__pycache__/`, caches — still ignored by
  design.

No `git add`, commit or push was performed: Phase 5 requires the report first,
and the working tree is therefore still uncommitted (see §8.3 for the exact
command proposed).

---

## 8. Remaining limitations and unresolved issues

### 8.1 SMILES parser — dependency decision required

No SMILES parser is available to the builder. `pyproject.toml` keeps
`dependencies = []` (plan §4: the core runs on the standard library), and none of
`rdkit`, `openbabel`/`pybel`, `indigo` or `openff-toolkit` is installed;
Biopython is present but is not a SMILES parser. No substitute parser was
invented and no large dependency was added silently.

Consequences, stated precisely:

* Production `build_services()` wires **no** chemistry probe, so `R-ENT-010`
  reports *“not checked”* as a **WARNING** and does not block. Production
  chemistry enforcement is therefore **not complete**.
* The blocking path is implemented and tested — with a probe injected through the
  port, the shape a deployment takes once a parser is chosen
  (`test_invalid_smiles_blocks_with_a_real_probe`,
  `test_valid_smiles_passes_a_real_probe`, `test_probe_error_is_reported_not_raised`).
* `test_production_wiring_claims_no_smiles_guarantee` pins the honest state, so
  the shipped bundle cannot silently claim SMILES validation.

**Decision needed:** whether to add a parser (e.g. `rdkit` behind a `smiles`
extra, wired in `build_services()` as a `ChemistryProbe`) and thereby make
invalid SMILES blocking in production. The parser's guarantee would still be
syntactic only: a parseable SMILES is not a promise that AF3 accepts the
resulting ligand.

### 8.2 Template chain bounds

Unchanged and still unverifiable: no mmCIF parser exists, so template chain
bounds and residue-index mappings are not validated beyond what the service
already checks (file readability, pair shape). Nothing was invented.

(Follow-up 2026-10-27: template files are now read as mmCIF and a file that is
not a structure is refused — `docs/AF3_VERIFICATION_GAP_CLOSURE_REPORT.md` §2.
Chain bounds and mappings remain as stated here.)

### 8.3 Git

Nothing was staged, committed or pushed. The approved recovery set is §7.1 +
§7.2 + the un-ignored trees in §7.3; the proposed commit (after your go-ahead):

```
git add .gitignore configbuilder tests fixtures docs .github \
        AUTHORITATIVE_SPEC.md DOMAIN_MAPPING.md RUNNING_THE_APPLICATION.md \
        tools/af3_validation/README.md
```

`THESIS_EXPANDED_DRAFT.md` and `test.json` stay out.

### 8.4 Smaller notes

* Variant drift/identity semantics are tested at rule level against hand-built
  wire documents (a committed spec cannot drift on its own), plus a service-level
  test proving a blocking variant report refuses the run before any write. There
  is no end-to-end fixture that *produces* drift through the UI, because the
  service API cannot express it without a bug — which is the point of the check.
* The GUI suite needs `--basetemp` inside the workspace on this machine (§6);
  CI is unaffected because it runs without Qt.
* `docs/screenshots/` (binary PNGs) is part of the restored `docs/` tree; they are
  review artifacts, not generated outputs, and total roughly 1 MB.
