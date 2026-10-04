# PROJECT AUDIT — configbuilder

Audit of the working tree as it stands, based on the **actual source** (not the
documents). Every claim below was checked against code that was executed, read,
or fuzz-tested on this machine (Windows, CPython 3.11.15) on 2026-09-30.

> **Graphify status:** the Graphify MCP server is reachable, but it holds **no
> graph for this project** — `list_projects` returned `[]` and `resolve_project`
> found nothing for `configbuilder` or `THESISSP`. The architecture picture
> below therefore comes from the source itself (import scans, AST inventory,
> execution traces), which is the same evidence Graphify would have indexed.
> Findings were verified by running the code, not inferred from filenames.

---

## 1. What the project is

`configbuilder` is a terminal builder that produces validated, reproducible
**AlphaFold 3 input JSON** files. It is a pure-Python package with **zero
runtime dependencies** (`dependencies = []`), one console entry point, and a
canonical internal model that is deliberately *distinct* from the wire format so
that identity, presence, and validation can be reasoned about before anything is
serialized.

Scale: 17 926 lines of production code across 18 packages/modules, 838 passing
tests (12 821 lines) plus 1 environment-dependent skip.

---

## 2. Entry points (verified by running them)

| Mechanism | Status |
|---|---|
| `configbuilder` (console script → `configbuilder.app.cli:main`) | **Works.** Start screen, `0`/`q`/`exit` and EOF all leave with status 0. |
| `python -m configbuilder` (`configbuilder/__main__.py`) | **Works** — a 4-line delegation to the same `main()`, so `app.cli` cannot execute twice. |
| Library: `MenuApp(build_services(), Console()).run()` | Works; the e2e suite uses exactly this shape with `ScriptedConsole`. |
| `run_wizard` / `python -m configbuilder.ui.render.wizard` | **Gone** (the second front end was removed in the previous revision); `HANDOFF.md` still documents it — see §9. |

`main()` returns 0 for every *deliberate* end (exit choice, quit word, Ctrl+C,
EOF) and reports per-operation outcomes itself. No second status system.

---

## 3. Real execution flow

```
configbuilder (console script)
  └─ app/cli.py::main
       └─ ui/services.py::build_services        one wiring: 5 services
            ├─ ProjectService        (current project, .cbproj autosave)
            ├─ ConfigurationService  (all base mutations)
            ├─ VariantService        (specs, edits, expansion, batch/series)
            ├─ ValidationService     (base + per-variant reports, status view)
            └─ GenerationService     (validate → transform → encode → plan → execute)
       └─ ui/render/menus.py::MenuApp.run       the master loop
            ├─ menu screens (edit / review / variants / generate / open / import)
            └─ services.*                       every mutation, one call at a time

data path for one committed change:
  menu → service → model.with_* rebuild (immutable) → _commit_project()
       → persistence.store._atomic_write_bytes   (.configbuilder/*.cbproj autosave)
  request for JSON:
  generation.plan_base/plan → validation.validate (tiers) → transform.to_wire
       → serialize.encode (deterministic bytes) → output.plan → output.execute
       → .tmp + fsync + os.replace, plus manifest.json
```

One source of truth for state: the `Project` held by `ProjectService`
(`_project`, `_path`, `_dirty`). Variants are *specs* applied to the base at
expansion time — no second copy of the configuration exists. The status view
(`app/status.py`) is derived from the validation catalogue's own blocking
findings, so a front end cannot show "ready" while generation refuses.

---

## 4. User workflow (as it actually is)

```
start screen       1 New job (blank name → automatic config-NNN)
                   2 Open saved work (restores the newest autosaved working copy)
                   3 Import an AF3 JSON file
master menu        1 Edit the job     → entities / job settings / bonds+mods+CCD
                   2 Review configuration → status, entities, variants, validate, JSON
                   3 Variants          → create / manage / from file / quantity series
                   4 Generate JSON     → the job, all variants, or selected variants
                   5 Open saved work   6 Import
                   0 Exit
```

Work preservation is a property of the service layer, not of user discipline:
every committed change autosaves the working copy, `new()` and an import commit
immediately, and the store is bounded (50 newest copies). Nothing in the
navigation path can discard the configuration; a refused generation says so
explicitly.

---

## 5. Broken / risky findings

### 5.1 DNA duplex desync — **BROKEN** (correctness)

`ConfigurationService.add_record("dna", X)` commits **two** records — `X` and its
reverse complement — as separate `FamilyCRecord`s with their own identifiers.
Nothing records the pairing afterwards, and `complement()` is recomputed from the
sequence, so:

* `update_record(key, sequence=...)` on one strand **does not update the partner**;
* `remove_record(key)` on one strand **leaves the partner orphaned**;
* **no validation rule detects either state** (there is no duplex rule).

Reproduction (executed; transcript in `build/audit3/duplex.txt`):

```
add dna  ATGC  → records A=ATGC, B=GCAT          (consistent duplex)
update A = AAAA → records A=AAAA, B=GCAT         (silently inconsistent)
validate base   → INFO/WARNING only, no ERROR
generate JSON   → succeeds:
   {"dna": {"id": "A", "sequence": "AAAA"}}, {"dna": {"id": "B", "sequence": "GCAT"}}
```

Impact: the builder's own duplex invariant is broken and the emitted file
contains a strand pair that cannot be a duplex. The user is told nothing. This is
the most serious defect found: silent wrong output, P1.

### 5.2 CI does not verify the application — **RISKY** (P2)

* **The test suite is not in the repository.** `.gitignore` ignores `tests/`,
  `fixtures/`, `testdata/`, `docs/` and the four planning documents (commit
  `34a3887` "Ship source only"), so CI cannot run tests — and 838 tests + all
  golden fixtures exist only on this machine, unversioned and unprotected.
* The **lint** job runs bare `ruff check configbuilder`: default rules produce
  **62 findings**, all pre-existing, so that job is red on every push.
* The Windows smoke step runs `configbuilder < /dev/null`. The runner's default
  shell on Windows is PowerShell, where `<` is not input redirection. (Not
  reproducible here — no pwsh/runner — so this is flagged, not asserted.)

### 5.3 Packaging metadata references a deleted component — **CONFUSING** (P2)

`pyproject.toml` still advertises `fullscreen = ["prompt_toolkit>=3.0"]` and
promises "Absence selects PlainLineRenderer". Neither the full-screen renderer
nor the plain renderer exists any more; the single renderer is
`ui/render/console.py::Console`. The extra installs an unused 3rd-party package.

### 5.4 A dead line in the validation façade — **FIX** (P5)

`ValidationService.validate_base` contains
`report = self._projects._require_project() and None` immediately before the real
`report = validate(...)`. It computes nothing; it was left in place during an
earlier revision to keep a diff small.

### 5.5 A latent `NameError` on the import refusal path — **FIXED** (P1)

`ProjectService.import_json_preview/commit` caught `(ModelError, ValueError,
TypeError)` without importing `ModelError`, so that clause would have raised
`NameError` instead of returning a clean refusal. Fixed in the previous revision;
verified by fuzzing 600 structurally random documents through `from_wire` and 18
malformed payloads through the public import entry: **0 raw exceptions**.

---

## 6. Dead code

Verified unused by an AST inventory of every module-level and class-level
definition, cross-checked against both production and test source:

| Item | Evidence |
|---|---|
| `configbuilder/ui/steps/` — `machine.py`, `registry.py`, `jump.py`, `view.py` (~960 lines) | The wizard front end was removed; nothing outside the package's own test imports it. `ui/__init__.py` still re-exports the machine. |
| `ProjectService.save`, `save_as`, `suggested_project_path`, `_with_settings` | Reachable only from `tests/e2e/test_app_pipeline.py` — i.e. kept alive by their own test. Legacy of the pre-JSON-first workflow. |
| `VariantService.duplicate_with_edits`, `record_sequence_choices`, `component_counts` | Zero references anywhere, including tests. |
| `ValidationService.set_policy` | Only its own e2e test. |
| `transform/presence.py::empty_value_for` | Zero references. |
| `output/plan.py::_NoFilesystem` | Zero references. |
| `validation/report.py::Report.infos` | Zero references. |
| `MenuApp._confirm`, `_set_protein_alignment`, `_set_rna_alignment`, `_set_references` | Zero references (leftovers of the menu restructure). |
| `tests/terminal/` | Empty package (only `__init__.py`). |

Rule dispatch (`getattr(module, "check_r_root_001")`) makes every `check_r_*`
look "unreferenced" to a static scan; those are **live** and guarded by
`tests/contract/test_rule_completeness.py`.

---

## 7. Duplication and complexity

* **`ui/render/menus.py`: 2 178 lines, ~80 methods in one class.** It owns
  navigation, prompts, entity rendering, status formatting, variant flows and
  the generation screens. It is the project's complexity hotspot.
* **Status row keys are known in three places** inside that module
  (`_STATUS_LABEL_ROWS`, `_OPTIONAL_KEYS`, the `_status_detail` branch chain).
  Small, contained, but it means a new row needs three edits.
* **Rules are dispatched by string convention** rather than a table. It keeps
  the catalogue pure data, but a typo degrades to "skipped". Guarded by the
  contract tests, so this is acceptable.
* No duplicated *validation*: catalogue severities, `Finding`s and
  `Report.blocking()` are the only requirement opinion; `app/status.py` maps them
  onto display rows and does not re-decide. No duplicated serialization: one
  encoder, one planner, one executor.

---

## 8. Verified-good (explicitly kept)

* Zero runtime dependencies; the whole application is stdlib.
* Immutable model with `with_*` rebuilds; identity allocated only by
  `IdentityRegistry`.
* Validation as data (catalogue) with tier ordering, explicit `mark_skipped`,
  `ERROR`/`WARNING`/`INFO` semantics, and blocking = ERROR only.
* Deterministic encoder (LF-only, no platform bytes); golden fixtures with
  manifests prove it.
* **Atomic writes everywhere it matters**: `output/execute.py` and
  `persistence/store.py` both write `.tmp`, `flush`, `fsync`, `os.replace`.
  Interrupted writes cannot truncate an existing file.
* Import path robust against arbitrary documents (fuzz: 600 docs, 0 raw
  exceptions).
* Menu robust against arbitrary keystrokes: 400 randomised scripted sessions
  (random digits, words, blanks, junk, 40 steps each) produced **0 crashes** and
  0 tracebacks.
* Two working entry points; `main()` with a single exit-status contract.
* Python 3.9 grammar clean across all 89 modules (`ast.parse(...,
  feature_version=(3, 9))`: 0 failures), matching `requires-python = ">=3.9"` and
  the CI baseline.

---

## 9. Documentation drift — CONFUSING (P4)

`HANDOFF.md`, `CHECKLIST.md`, `IMPLEMENTATION_PLAN.md` §5.1/§16 and the CI
comment describe the **14-step wizard with three renderers** as the architecture.
Concretely wrong instructions a new developer would follow:

* "There is no Git repository here (git rev-parse fails)" — there is one.
* "running `configbuilder` fails with `ModuleNotFoundError: No module named
  'configbuilder.app.cli'" — it works.
* Smoke test steps that type `new`, `a`, `v`, `s` at "Step 1 of 14" — that UI
  does not exist.
* A test count of 695 (now 838) and a `695 passed` expectation.

`docs/` is gitignored, so these documents ship nowhere; they are still the
project's own handover material and are now actively misleading.

---

## 10. Test coverage assessment

**Covered well:** the full generation pipeline (e2e), validation catalogue
completeness/traceability, wire-field confinement, architecture/dependency rules,
serialization determinism (incl. cross-process), golden fixture trees with
manifests, variant expansion/isolation, persistence round-trip and schema
upgrade, the menu's public workflows, identity authority, model invariants, and
property tests (hypothesis).

**Not covered (found by this audit):**

1. DNA duplex semantics under edit and delete — the defect in §5.1.
2. The interaction between the status view and generation refusals for a
   partially complete job (only the "no entities" case is tested).
3. Windows-specific behaviour: the platform/console-probe layer was removed with
   the second front end, so `Console` on a real Windows console is exercised only
   by the CI smoke step.
4. No test would catch a `.gitignore` that hides the suite from CI (§5.2).

---

## 11. Classification of every major finding

| # | Finding | Class |
|---|---|---|
| 1 | DNA duplex desync (edit/delete, undetected) | **FIX** (P1) |
| 2 | Latent `NameError` on import refusal | **FIXED** (P1) |
| 3 | Dead no-op line in `validate_base` | **FIX** (P5) |
| 4 | CI cannot run tests; suite unversioned | **REWORK** (P2) — needs the owner's decision |
| 5 | Lint job red; Windows smoke step shell-dependent | **FIX** (P2) |
| 6 | `pyproject.toml` dead `fullscreen` extra | **REMOVE** (P2) |
| 7 | `ui/steps/` orphaned wizard engine + its test | **REMOVE** (P3) |
| 8 | Dead service methods (save/save_as/set_policy/…) | **REMOVE** (P3) |
| 9 | Empty `tests/terminal/` package | **REMOVE** (P5) |
| 10 | `menus.py` 2 178-line class | **SIMPLIFY** (P3) — split by screen family |
| 11 | Status row keys in three places | **SIMPLIFY** (P3) |
| 12 | Stale HANDOFF/CHECKLIST/PLAN + docstrings | **REWORK** (P4) |
| 13 | String-convention rule dispatch | **LEAVE** (guarded) |
| 14 | Layered arch (model/identity/validation/transform/serialize/output/persistence/app/ui) | **KEEP** — each layer has one responsibility and the dependency rules are enforced by tests |

---

## 12. Revision plan (priority order)

**Stage 1 — Correctness (P1)**
1. Keep the DNA duplex consistent: editing one strand updates its partner;
   deleting one strand deletes the duplex as the user understands it. Tests for
   both, plus a regression test asserting the emitted JSON is complementary.
2. Remove the dead line in `validate_base`.

**Stage 2 — Packaging and CI reliability (P2)**
3. Drop the dead `fullscreen` extra; correct the surrounding comments.
4. Make the lint job green on the shipped source (curated rule set + fix the
   remaining real findings in shipped files).
5. Make the smoke step shell-independent.
6. Fix the real lint findings in shipped files (unused imports, an ambiguous
   name, a duplicate import).

**Stage 3 — Remove dead code (P3/P5)**
7. Delete the orphaned `ui/steps/` package, its dedicated test, and the
   re-exports/architecture-test references to it.
8. Delete the dead service methods and their test-only usage, replacing that e2e
   coverage with the real paths (`load_saved_work`, open/close).
9. Delete the other single-use dead helpers listed in §6.
10. Delete the empty `tests/terminal/` package.

**Stage 4 — Documentation truth (P4)**
11. Correct the module docstrings that still describe the removed second front
    end.
12. Add a short, dated *reality check* to `HANDOFF.md` and `CHECKLIST.md` so the
    handover material stops contradicting the code, and record in this document
    which parts of `IMPLEMENTATION_PLAN.md` §5.1/§16 are superseded.

**Stages run with the suite after each step; no stage is allowed to leave the
tree red without an explanation in the final report.**

---

## 13. Revision log — what was actually changed (2026-09-30)

**Stage 1 — Correctness (done).**

* **DNA duplex desync fixed.** `model/records.py` gains `duplex_partner(configuration,
  record)`: the partner of a DNA strand is the adjacent DNA record that is exactly its
  reverse complement — the same construction `_build_records` uses, so the pairing is
  read back from the state that created it rather than guessed. `ConfigurationService.
  update_record` now rewrites the partner's sequence with the new reverse complement
  (and says so: *"both strands of the DNA duplex were updated"*); `remove_record`
  removes the pair and releases both identifiers (*"the DNA duplex and its partner
  strand were removed"*). The same rule is applied on the variant path
  (`variants/edits.py`: `SetSequence`, `RemoveRecord`), so a variant cannot produce a
  broken duplex either. A lone strand — an imported single DNA chain — has no partner
  and is edited/removed alone. Nine tests were added to `tests/unit/app/
  test_dna_duplex.py`, including a regression test that asserts the **written JSON** is
  complementary (the original defect produced a mismatched pair in the file).
* **Dead no-op removed** from `ValidationService.validate_base`.

**Stage 2 — Packaging and CI (done).**

* `pyproject.toml`: the dead `fullscreen` extra (`prompt_toolkit`, for a renderer that
  no longer exists) is gone; the dependency-free rule is unchanged.
* `.github/workflows/ci.yml`: the Windows-fragile `configbuilder < /dev/null` step is
  replaced by stdin-detached invocations of **both** entry points (identical on bash and
  PowerShell); a `compileall` gate and a **pipeline smoke test** (services → planned →
  executed → written JSON asserted) were added, so CI now verifies real behaviour rather
  than only that the package imports; the lint job uses the correctness rule set
  (`--select E4,E7,E9,F`), which now passes.
* Shipped-source lint findings fixed at the root: 57 unused/duplicated imports removed,
  the ambiguous name `l` renamed in `configuration_service.remove_linkage`, a dead local
  in `variant_rules._attribute` deleted, and a wrong annotation (`source: ResourceRef`,
  a name that never existed) corrected in `model/references.py`. `ruff check --select
  E4,E7,E9,F configbuilder` is clean.

**Stage 3 — Dead code removed (done, except `ui/steps/`).**

Deleted, each verified unused before removal: `ProjectService.save`, `save_as`,
`suggested_project_path`, `set_output_policies`, `_settings`, `_with_settings`;
`VariantService.duplicate_with_edits`, `record_sequence_choices`, `component_counts`;
`ValidationService.set_policy`; `transform/presence.empty_value_for`;
`output/plan._NoFilesystem`; `validation/report.Report.infos`; `MenuApp._confirm`,
`_set_protein_alignment`, `_set_rna_alignment`, `_set_references`; the `SaveOutput`
result type and `FailureReason.SAVE_WITHOUT_PATH`; and the empty `tests/terminal/`
package. The three e2e tests that were the last users of the removed API were rewritten
onto the real paths (`projects.path` + `open`, `load_saved_work`, and a
`ValidationService(..., run_preflight=False)` wiring) rather than deleted.

**`ui/steps/` removed (owner-approved).** The orphaned wizard engine — `machine.py`,
`registry.py`, `jump.py`, `view.py`, `__init__.py`, 969 lines — is gone, together with
its 543-line test. The module is recoverable from Git history (`git checkout HEAD --
configbuilder/ui/steps`); its test file was untracked, so a copy was kept first at
`build/audit3/removed/test_step_machine.py.bak`. `ui/__init__.py` no longer re-exports
the machine, and the three architecture tests that named it (`test_layout.py`'s
expected subpackages, `test_ui_purity.py`'s present-only scope, `_scanner.py` /
`test_dependency_rules.py` wording) were updated rather than weakened: `ui` is now
`render → present`, exactly as the running application uses it.

**Stage 4 — Documentation truth (done).**

* Module docstrings that still described the removed wizard/front ends were corrected
  (`app/results.py`, `app/configuration_service.py`, `app/variant_service.py`,
  `validation/report.py`, `validation/rules/entity_rules.py`, `ui/present/*`,
  `ui/render/console.py`, `ui/__init__.py`).
* `HANDOFF.md` and `CHECKLIST.md` carry a dated **REALITY CHECK** banner naming every
  wrong claim (missing `cli.py`, "no Git repository", 695 tests, "CI runs pytest",
  wizard smoke test, the version-pin rule) and pointing here. `IMPLEMENTATION_PLAN.md`
  §5.1/§16 (the ten-module map including a wizard) and §15 (the service table listing
  `save`/`save_as`/`set_policy`) are superseded by §5–§7 of this document.

**Verification after every stage.**

```
tests:                838 passed / 1 skipped  →  847 (+9 duplex)  →  809 passed / 1 skipped
                      (the final drop is the removed step-machine suite, 38 tests)
lint (E4,E7,E9,F):    62 findings             →  0
entry points:         both exit 0 with stdin detached
pipeline smoke:       services → plan → execute → JSON asserted (also run in CI)
menu fuzz:            400 randomised sessions, 0 crashes
import fuzz:          600 (+200 after the change) random documents, 0 raw exceptions
3.9 grammar:          0 failures across 77 modules; compileall clean
imports/__all__:      0 unresolved names across 77 modules
```

---

## 14. Owner decisions recorded

* **The repository stays source-only.** `tests/`, `fixtures/`, `testdata/`, `docs/` and the
  planning documents remain gitignored (the owner's explicit choice, 2026-09-30). The
  consequence stands and is not worked around: the 809-test suite cannot run in CI, the
  golden fixtures are not versioned, and a fresh clone has no way to verify behaviour
  beyond the CI smoke test. Mitigation applied instead of reversal: CI now runs a real
  pipeline smoke test (services → plan → execute → assert the written JSON) alongside the
  install/compile/entry-point checks, so a broken build fails CI even without the suite.
* **`ui/steps/` deleted** (see §13), test backed up under `build/audit3/removed/`.

---

## 15. MSA and structural templates moved onto their record (2026-09-30)

**Why.** The Entities screen carried a fourth entry, "MSA / Templates", that opened a
record picker and then a sub-menu of the two settings. Both settings belong to exactly one
record — the record whose alignment or templates they are — so the entry let the operator
start a setting without a record, duplicated questions the add flow already asked, and
(in the variant layer) offered targets that cannot carry them at all. The request was
simple: an alignment or a template set is asked for *while the record that owns it is
added or edited*, and for no other family.

**What changed.**

* **Entities screen is three actions again** (`menu.entity_menu_actions`): add, edit,
delete. Typing the retired `4` there is reported as an invalid choice, not answered.
* **`_msa_flow` deleted** together with the strings only it used (`menu.msa_title`,
`menu.msa_target`, `menu.msa_note`, `menu.msa_actions`, `menu.templates_protein_only`).
The dead `_alignment_for` helper went with it.
* **`_edit_entity` now owns the record's questions**: sequence and description first
(blank keeps the current value), then — by family — protein: MSA then templates; RNA:
MSA only; DNA: neither (the service moves the partner strand, which it reports); ligand:
nothing to edit here, and `menu.entity_no_fields` says so instead of asking questions the
record cannot answer.
* **Add flow asks templates for protein only.** `_add_entity` chained `_chain_templates`
for RNA too, and `set_references` refuses every non-protein chain (`R-TPL-001`, "Templates
are supported only on protein chains") — the operator was asked a question whose only
possible answer was a refusal.
* **`_chain_msa` / `_chain_templates` take the record key** when the edit flow names one;
without it they use the record just created (add flow). Declining now says
`menu.msa_skip` ("edit the entity to set it later") in the add flow and the new
`menu.msa_skip_edit` / `menu.templates_skip_edit` ("…is unchanged") in the edit flow,
where the advice to edit would be nonsense.
* **`_select_entity` gained a family-restricted call with an honest empty note.** When the
protein picker is empty, `menu.no_protein_target` says alignments and templates live on a
protein chain — not the generic "add an entity first", which was false in a DNA-only job.
* **Variant change kinds "MSA (alignment)" and "Structural templates" now offer protein
records only.** The variant vocabulary builds `SetAlignment` for the alignment kind, so a
DNA record could be selected, stored, displayed as "MSA of A", and then expand to **zero
variants** with no warning. `SetSingleAlignment` (the RNA case) exists in the edit
vocabulary and in encode/decode but is never constructed by `VariantService`, so variant
MSA edits stay protein-only until that path is finished; the base builder's RNA MSA is
unaffected.
* **Duplicate `_msa_source_payload` removed.** The class held two identical copies (the
second silently shadowed the first); there is now one, shared by the base flow and the
variant alignment flow as its docstring always claimed.

**Intentional behaviour changes.** The Entities screen has no fourth entry; editing a
record asks its own MSA/template questions; adding an RNA no longer asks for templates;
variant MSA/templates changes cannot target DNA/RNA/ligand.

**Verification.**

```
tests:                812 passed / 1 skipped (the UI suite grew 79 → 81)
lint (E4,E7,E9,F):    all checks passed
entry points:         python -m configbuilder and configbuilder both exit 0, stdin detached
compileall:           clean;  3.9 grammar: 0 failures across 72 modules
menu fuzz:            400 randomised sessions over every family, 0 crashes
scripted tour:        no "MSA / Templates" entry; protein add/edit asks MSA + templates;
                      RNA asks MSA and never templates; DNA and ligand ask neither
```

---

## 16. Aligning with the real AlphaFold 3 input contract (2026-09-30)

**Why.** Check the real AlphaFold 3 documentation and source against what this builder
emits: (a) whether RNA `unpairedMsa` is a real field, (b) whether any documented
parameter is missing or emitted in a shape the reference parser rejects.

**Checked against** `docs/input.md` and `src/alphafold3/common/folding_input.py` in
`google-deepmind/alphafold3` (`JSON_VERSIONS = (1, 2, 3, 4)`, `JSON_VERSION = 4`).

**Findings and changes.**

* **RNA `unpairedMsa` is real** — "Protein and RNA chains allow setting a custom MSA":
unset/null = search, `""` = MSA-free, non-empty A3M = provided. The base builder already
emits exactly that shape (`automatic` → omitted, `free` → `""`, `provided` → inline or
path); RNA has no paired MSA and no templates, DNA has neither — the tool matches.
* **Templates must always carry both index arrays.** `Template.from_dict` reads
`json_dict['queryIndices']`/`['templateIndices']` directly, so an entry without them is a
`KeyError`; the builder omitted both when the mapping was empty. Fixed in
`transform/accessors.py`: both arrays are always emitted (the empty pair for an empty
mapping), pinned by the transform and property tests.
* **Input version 4 is current, and the default pin is now 4** (`app/status.py`). The
reference implementation emits `version: 4`; v4 covers the chain `description` fields the
builder can set. Previously a fresh job pinned 3 while the golden fixtures pinned 4, so a
`description` was refused at generation time (the `R-VER-002` semantics are preserved: a
feature above the pin still errors naming the feature).
* **The feature→version map was incomplete.** `unpairedMsaPath`, `pairedMsaPath` and
`mmcifPath` arrived in v2, `userCCDPath` in v3; all four were recorded as v1 and none was
reported as a used feature. `transform/mappings.py` now owns the numbers
(`PATH_FEATURE_MIN_VERSIONS`) and the engine reports the ones a document actually uses — a
v1 pin with an external MSA names `unpairedMsaPath` instead of silently emitting a v2
feature.
* **Variant MSA changes now reach RNA too.** `VariantService` dispatches by the target's
family: protein → `SetAlignment` (the paired/unpaired cases), RNA → `SetSingleAlignment`
(automatic/free/provided), any other family refused naming the chain type. The UI picker
offers protein *or* RNA with the family's own mode menu; templates stay protein-only with
their own note (`menu.no_protein_target`, new `menu.no_alignment_target`).
* **Crash fixed while wiring the RNA path:** `describe_edit` read `.path` off the value
`fold_resource` hands its handler (the `PathSpec` itself), so describing *any* variant
with an external MSA source or an external user-CCD definition raised `AttributeError`
when the variant list rendered. Both handlers fixed; pinned by tests in
`tests/unit/variants/test_edits.py`.

**Reported, not implemented (documented gaps).**

* **Homomeric polymer copies.** The contract's `id: list[str]` (e.g. `["A","B","C"]`)
is emitted correctly from `Multiplicity`, but only ligands can be created with copies > 1
in the UI; protein/RNA/DNA copies are model-level only.
* **Ligand `description`.** Emitted (v4) and imported, but the ligand edit path says a
ligand has no editable fields, so a ligand description cannot be typed in the UI.
* The upstream `version` prose is self-inconsistent ("must be set to 1 or 2", then "1, 2,
or 3", while the example and `JSON_VERSION` use 4); the code lists 1–4 and is the
authority used here.

**Verification.** 823 passed / 1 skipped; ruff E4/E7/E9/F clean; compileall clean; both
entry points exit 0 with stdin detached; the golden fixture suite (already pinned to 4)
unchanged in shape; scripted tours: a variant MSA change on an RNA record stores
`SetSingleAlignment` and expands to an RNA `unpairedMsa`, a DNA-only job refuses both
settings by name, an RNA-only job refuses templates.
