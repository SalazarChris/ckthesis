# Gate Audit and Recovery Report

**Date:** 2026-10-24  
**Repository:** `main` at `347620f` (`origin/main` is the same commit)  
**Scope:** Audit only. No source, test, or configuration file was changed while producing this report.  
**Report location:** `docs/GATE_AUDIT_AND_RECOVERY_REPORT.md` (this directory is deliberately untracked by `.gitignore`; the report is a local audit artifact).

---

## 1. Executive Summary

The accidental removal is commit **`85a606a` — “Remove validation gates and keep the repository app-only”**. That commit removed far more than the personal post-execution checks:

- the validation service wiring;
- the generation, save, preview and variant validation gates;
- the GUI readiness card, validate actions, variant status column and findings surfaces;
- the console’s blocked-save findings output;
- the tracked test suite, fixtures, docs and CI configuration (they were moved to ignored local files).

The current working tree is an **uncommitted partial restoration** on top of `347620f`. It restores the core validation gate, the service wiring, the GUI readiness/variant/findings surfaces, and the console blocked-save/preview behavior. It does **not** restore the complete pre-removal gate behavior.

The central audit result is:

1. **No gate in the runtime checks whether a generated JSON has actually been run by AF3.** There is no code that looks for an AF3 output directory, result files, completion markers, logs, ranking scores, or prediction status. The builder does not import `af3_analysis` or `tools.af3_validation` on any builder path.
2. **The only deployment/execution-adjacent door is the version-selection gate**: `R-ROOT-002` and `R-VER-001` both block an `Unverified` format target. This is not a check for a successful prediction. It is a check that an explicit JSON version has been selected. New jobs start with `Pinned(3)`, and imported JSON always carries a version, so the normal workflow never encounters it. The old evidence-reference requirement was already removed in commit **`097c901`**; the current code allows a bare pin.
3. **The restoration is incomplete in three important ways:**
   - `GATE_TIERS` excludes `PREFLIGHT`, so an invalid SMILES with a real chemistry probe can pass save while readiness says it is blocked.
   - `GATE_TIERS` excludes `VARIANT`, and `GenerationService` never calls `validate_all`, so the drift and identity-stability checks do not block generation or variant preview.
   - `ValidationService.status()` still runs the full catalogue while the gate runs the smaller `GATE_TIERS`; the two can therefore disagree. A probe with a failing chemistry port produced **`status.ready == False`** and a successful `plan_save`.
4. **The version gate is duplicated.** `R-ROOT-002` and `R-VER-001` both fire on the same `Unverified` state. A probe produced two blocking findings for one condition.
5. **The local test suite is currently green**, but it is untracked and ignored. The restoration therefore has no tracked regression evidence and no CI protection.

**Recommendation:** do not remove validation merely because it says “verified against the deployment.” The specific unwanted requirement — that the operator must have observed AF3 accepting a format version and cite an evidence token — was already removed/neutralized by `097c901`. The remaining `Unverified` refusal is a version-selection policy, not proof of a successful AF3 run. A decision is needed on whether that residual state should remain.

---

## 2. Repository State and History Examined

### 2.1 Current working tree

`git status --short` at audit time:

```text
 M configbuilder/app/generation_service.py
 M configbuilder/app/results.py
 M configbuilder/app/validation_service.py
 M configbuilder/ui/render/qt/models.py
 M configbuilder/ui/render/qt/pages/generate.py
 M configbuilder/ui/render/qt/pages/overview.py
 M configbuilder/ui/render/qt/pages/variants.py
 M configbuilder/ui/render/qt/state.py
 M configbuilder/ui/render/qt/windows/main_window.py
 M configbuilder/ui/services.py
```

These are the restoration attempt. They are **not committed**. `git diff --stat` reports 10 files changed, 478 insertions and 85 deletions at audit time.

### 2.2 Relevant commits

| Commit | Meaning |
|---|---|
| `e8bd15a` | Last full pre-removal desktop builder and layout state, including validation wiring and gates. |
| `097c901` | “Make version pins evidence-free: exports need no provenance tokens.” This is the earlier, targeted removal of the evidence ritual. |
| `85a606a` | The accidental broad removal: validation gates, UI readiness/validate/status/findings, service wiring, tracked tests/docs/CI. |
| `28e0534` | Untracked fixtures and ignored local verification artifacts. |
| `84198f6` | Documented the local-only verification artifacts in `.gitignore`. |
| `347620f` | Current `HEAD`; MSA/template completion work. The restoration is uncommitted on top of this. |

Useful history commands used:

```bash
git show 85a606a^:configbuilder/app/generation_service.py
git show 85a606a -- configbuilder/app/generation_service.py
git show 85a606a -- configbuilder/ui/render/menus.py
git show 097c901 -- configbuilder/validation/rules/policy_rules.py
git show 097c901 -- configbuilder/app/project_service.py
```

The pre-removal generation service contained:

```python
base_validation = self._validation.validate_base()
if not base_validation.ok:
    return GenerationPlan(
        ok=False,
        failure_reason=FailureReason.VALIDATION_BLOCKED,
        ...
    )
...
variant_validation = self._validation.validate_all(only=only)
...
validation_report=combined,
```

The current service instead has:

```python
GATE_TIERS = (Tier.STRUCTURAL, Tier.RELATIONAL, Tier.CONTRACT)
...
validation_report=None,
```

This is the core difference between the original gate and the restoration.

### 2.3 Tests and docs are local-only

- `git ls-files tests` returns **0 files**. `tests/` is ignored by `.gitignore:63`.
- `git ls-files docs` returns **0 files**. `docs/` is ignored by `.gitignore:65`.
- This report is therefore a local file, not a tracked repository document.
- The tracked application is 105 files, of which 97 are under `configbuilder/`.
- The local suite exists and runs; it just is not part of a clone or CI.

This is a repository-state defect for recovery verification, not a functional gate defect.

---

## 3. Complete Gate Inventory

The table below covers every check that can reasonably be called a gate: a check that decides whether an operation is allowed to continue. It includes checks that exist but are not reached on a production path, and checks that are deliberately display-only.

| ID | Gate | Location | What it actually checks | Trigger | Blocking behavior | Classification |
|---|---|---|---|---|---|---|
| **V1** | Validation engine | `configbuilder/validation/engine.py:136` | Runs catalogue rules in tier order; records skipped rules | Every `validate(...)` call | Returns a `Report`; the caller decides | Keep |
| **V2** | Structural rules | `configbuilder/validation/catalogue.py`; `rules/*.py` | Shape and model invariants (see §4) | Any validation run with `STRUCTURAL` | ERROR findings block if tier is included | Keep |
| **V3** | Relational rules | Same | Cross-record and cross-field consistency (see §4) | Any validation run with `RELATIONAL` | ERROR findings block if tier is included | Keep |
| **V4** | Contract rules | Same | AF3 contract, version and feature compatibility | Any validation run with `CONTRACT` | ERROR findings block if tier is included | Keep |
| **V5** | Variant rules | `configbuilder/validation/rules/variant_rules.py` | Drift attribution and identity stability for expanded variants | Only `ValidationService.validate_all` | ERROR findings would block if checked | **Restore into generation** |
| **V6** | Preflight rules | `rules/entity_rules.py`, `rules/msa_rules.py` | SMILES probe; A3M shape and external MSA readability | Full validation; **not** current generation gate | ERROR with a real chemistry probe; WARNING with the null probe | **Restore into gate** |
| **V7** | Informational policy rules | `rules/policy_rules.py` | Seed uniqueness/order, chain allocation, seed policy, out-of-scope science | Any full validation | Never blocking (INFO by catalogue) | Keep |
| **G1** | Base generation gate | `configbuilder/app/generation_service.py:105-114` | Runs `GATE_TIERS` against the open base | `show_json(None)`, `plan`, `plan_base`, `plan_save` | Returns `VALIDATION_BLOCKED` and findings | **Repair** (PREFLIGHT missing) |
| **G2** | Variant generation gate | `generation_service.py:116-128`; callers at `:177`, `:340` | Runs `GATE_TIERS` against each expanded variant | Variant preview and `plan` | Returns `VALIDATION_BLOCKED` and findings | **Repair** (VARIANT checks missing) |
| **G3** | Readiness view | `configbuilder/app/validation_service.py:100-119`; `app/status.py:349` | Full base catalogue, then maps blocking findings to status rows | GUI Overview refresh; console blocked-save block | Display-only; `ready` is `not blocking` | **Repair** (uses a different rule set from G1) |
| **G4** | Full variant validation | `validation_service.py:120-199` | Base plus every expanded variant, with wire documents and declared changes | GUI Variants page; tests; no generation path | Returns reports; caller displays them | Keep, but **wire into generation** |
| **G5** | Console save gate | `configbuilder/ui/render/menus.py:1541-1568` | Calls `plan_save`; prints status block on `VALIDATION_BLOCKED` | Job menu → “Save and show summary” | Refuses the write | Keep |
| **G6** | GUI save gate | `configbuilder/ui/render/qt/windows/main_window.py:423-501` | Calls `plan_save`; reports blocking findings | “Save JSON…” | Refuses the write | Keep |
| **G7** | GUI generation gate | `ui/render/qt/pages/generate.py:841` | Calls `plan_selection` / `plan` then asks confirmation, then `execute` | “Generate files” | Refuses without a reviewed plan or confirmation | Keep |
| **G8** | JSON preview gate | `generation_service.py:147-191` | Runs base gate, or each variant gate, before `to_wire → encode` | Preview action | Returns `(None, reason)` | Keep |
| **G9** | Import/load gate | `app/project_service.py:125-203` | JSON parse, `from_wire` structural conversion, directory/missing-file handling | Open a JSON file; import preview/commit | Refuses corrupt or unsupported files; does not require AF3 results | Keep |
| **G10** | Format-version emitter gate | `transform/engine.py:95-113` | `Unverified` raises; `Pinned`/`Auto` select a version | Every `to_wire` | Raises `TransformError` → plan refuses | Keep (policy decision needed on `Unverified`) |
| **G11** | Version-feature gate | `transform/engine.py:153-165`; `R-VER-002` | A feature above the selected version is refused, never silently raised | `to_wire`; validation | Refuses emission; ERROR finding | Keep |
| **G12** | Output collision/overwrite gate | `output/plan.py:182-207` | Create/overwrite/skip/conflict/versioned decision | Planning | Conflict refuses plan; default policy is `Fail` | Keep |
| **G13** | Output resource gate | `output/plan.py:220-280`; `output/execute.py:86-169` | Missing copied resource refuses the whole write | Planning and execution | No write for missing sources; a later I/O failure reports files already written | Keep |
| **G14** | Input mutation guards | `app/configuration_service.py` throughout | Family, sequence alphabet, IDs, copies, PTM range/code, ligand representation, MSA source, bonds, seeds | Every service mutation | Returns a refusal object | Keep |
| **G15** | Template-reference input guard | `app/reference_validation.py:61-190`; `configuration_service.py:775` | CIF existence/readability/extension; non-empty pair list; pair syntax and query range | `set_references` | Refuses the reference set | Keep |
| **G16** | Empty-expansion gate | `generation_service.py:326-333` | A variant run with no variants refuses | `plan` | `EMPTY_EXPANSION` | Keep |
| **G17** | Confirmation gates | `ui/render/qt/dialogs/messages.py:45-133`; console equivalents | Discard, overwrite, entity/bond/PTM/variant deletion, generation, import preview | UI actions | Waits for user choice | Keep |
| **G18** | No-project gate | Services and pages | Operations need an open project | Every service/page | Returns `NOT_OPEN` / message | Keep |
| **G19** | Optional validation bypass | `generation_service.py:92-101`; `if self._validation is None` at `:106`, `:118` | A `GenerationService` built without a validator skips all gates | Construction | Silently ungated | **Investigate / repair** |
| **G20** | Duplicate version gate | `catalogue.py` `R-ROOT-002`, `R-VER-001`; `policy_rules.py` | Both block the same `Unverified` state | Any validation run | Two findings for one condition | **Repair (deduplicate)** |
| **G21** | Manifest validation summary | `generation_service.py:448` | Currently passes `None` | `plan` | Nothing recorded | **Restore** (traceability, not a gate) |
| **G22** | Unused findings renderer | `ui/render/menus.py:1769` `_print_cards` | Formats findings; no caller | Never | No effect | Obsolete |
| **G23** | Unreachable `Auto` branch | `policy_rules.py` `check_r_ver_002` | Checks an empty `Auto.evidenced` set | Cannot occur: `Auto.__init__` rejects empty | No effect | Obsolete branch |
| **G24** | External parser harness | `tools/af3_validation/` | Uses AF3’s parser (`Input.from_json`), not inference | Manual command | Exit code only | Keep separate; not a builder gate |
| **G25** | Downstream analysis QC | `af3_analysis/` | Validates AF3 output data and excludes bad samples | Separate `python -m af3_analysis` | Separate workflow | Keep separate; not a builder gate |
| **G26** | Generated-job parser scripts | `generated_jobs/*` | Run AF3 parser and record verdicts for local generated jobs | Manual scripts | Not in CLI path | Out of scope for builder gates |

### 3.1 Gates that exist but are never called on the production path

- `R-VAR-001` and `R-VAR-002` are only evaluated by `ValidationService.validate_all`. The generation service does not call it. The GUI Variants page does; the generation plan does not.
- `R-ENT-010` and the `R-MSA-*` preflight rules are only evaluated when `PREFLIGHT` is included. `GATE_TIERS` excludes it. `status()` still includes it.
- `_print_cards` (`menus.py:1769`) has no caller.
- `ProjectService._validate` and `ConfigurationService._validate` are optional constructor inputs; `build_services()` supplies neither. They are not production load/edit gates.
- `R-VER-002`’s empty-`Auto` branch cannot be reached through `Auto`, whose constructor refuses an empty evidenced tuple (`model/configuration.py:252-263`).
- `ValidationService.validate_all` is production code but not used by generation; it is used by the GUI Variants page and tests.

### 3.2 Gates that are bypassed or inconsistent

- **`GATE_TIERS` is a subset of the readiness catalogue.** `status()` validates all five tiers; `G1`/`G2` validate three. A preflight-only ERROR therefore gives `status.ready == False` while `plan_save` succeeds. Probe result below.
- **Variant validation is display-only.** The Variants page can label a variant “blocked,” but `GenerationService.plan` only runs the core tiers and would still write it.
- **Optional validator silently disables all gates.** This is not used by `build_services`, but the constructor makes it possible without an explicit test-only flag.
- **The catalogue text overstates two rules.** `R-ROOT-002` and `R-VER-001` summaries say “with its evidence reference,” but their checks only reject `Unverified`; they do not require `Pinned.evidence`. This is stale post-`097c901` wording.

---

## 4. Rule-by-Rule Catalogue Inventory

The catalogue contains 44 rules. The following list accounts for all of them.

### STRUCTURAL (14 rules, all ERROR in the catalogue)

`R-ROOT-003` (job name), `R-ROOT-004` (at least one seed), `R-ROOT-005` (uint32 seed range), `R-ROOT-006` (entity container non-empty); `R-ENT-001` (family), `R-ENT-003` (uppercase IDs), `R-ENT-004` (protein alphabet), `R-ENT-005` (RNA alphabet), `R-ENT-006` (DNA alphabet), `R-ENT-008` (no `CCD_` prefix); `R-TPL-003` (non-negative indices), `R-TPL-004` (parallel pair values); `R-BND-004` (1-based bond residue), `R-BND-005` (covalent-only model).

These are essential input-shape checks. Keep. They are included in `GATE_TIERS` through `STRUCTURAL`.

### RELATIONAL (13 rules; almost all ERROR, the `R-POL-003/005/006` rows are INFO)

`R-ROOT-007` (inline XOR external custom CCD); `R-ENT-002` (unique IDs including copies), `R-ENT-007` (modification position in range), `R-ENT-009` (ligand code XOR SMILES); `R-MSA-001` (protein MSA state); `R-TPL-001` (templates protein-only), `R-TPL-005` (max 20 templates); `R-BND-002` (SMILES-only ligand cannot be a bond endpoint), `R-BND-003` (bond endpoints resolve), `R-BND-006` (no polymer–polymer bonds); `R-POL-003` (chain allocation is policy, INFO), `R-POL-005` (biological validity out of scope, INFO), `R-POL-006` (scientific plausibility out of scope, INFO).

All are essential or deliberately non-blocking. Keep. Included in `GATE_TIERS` through `RELATIONAL`; the INFO rows never block.

### CONTRACT (7 rules, all ERROR)

`R-ROOT-001` (dialect exactly `alphafold3`); `R-ROOT-002` (explicit version / not `Unverified`); `R-MSA-002` (inline XOR path per MSA field); `R-TPL-002` (mmCIF XOR mmCIF path per template); `R-BND-001` (ions are ligands, no ion family); `R-VER-001` (explicit version / not `Unverified`); `R-VER-002` (feature/version consistency).

Keep all seven behaviors. `R-ROOT-002` and `R-VER-001` duplicate one condition and need repair. `R-VER-001`/`R-VER-002` are not checks for AF3 output; they check the selected JSON version and feature minimums.

### VARIANT (6 rules: `R-VAR-001/002` ERROR; `R-POL-001/002/004/007` INFO)

`R-VAR-001` (drift: every wire difference must be attributable to a declared edit); `R-VAR-002` (identity stability across expansion). `R-POL-001` (seed uniqueness policy), `R-POL-002` (seed ordering policy), `R-POL-004` (project’s ten-seed policy), `R-POL-007` (seed-set stability across variants) are informational.

The two `R-VAR` errors are essential to variant correctness and were part of the pre-removal generation gate. Current generation does not run them. **Restore them to the generation/preview path**, using the in-process `validate_all` context; this does not require an AF3 run.

### PREFLIGHT (4 rules: `R-ENT-010` ERROR/WARNING; `R-MSA-003/004/005` WARNING)

`R-ENT-010` (SMILES parses; ERROR when a chemistry probe is present, WARNING “not checked” with the null probe); `R-MSA-003` (A3M/A3M-file shallow check; advisory), `R-MSA-004` (first MSA sequence should match query; advisory), `R-MSA-005` (rectangular after removing lowercase insertions; advisory).

`R-ENT-010` is the important one. The current `ValidationService` is built with the null chemistry probe, so invalid SMILES currently produces only a warning even in `status()`. If a real chemistry probe is wired, `R-ENT-010` becomes a blocking ERROR. The gate currently excludes this entire tier, so even with a real probe the save/generate path would pass. **Restore `PREFLIGHT` to the gate.**

### Informational policy rows

The `R-POL-*` rules `001/002/003/004/005/006/007` are INFO by design. They must never become gates. Keep their non-blocking severity.

---

## 5. What Each Gate Really Does, and When It Runs

### 5.1 Base gate (`G1`)

`GenerationService._gate_base()` calls `ValidationService.validate_base(tiers=GATE_TIERS)`.

It runs from four places:

- `show_json(None)` — base preview (`generation_service.py:165`);
- `plan(...)` — variant generation, before expansion (`:317`);
- `plan_base(...)` — base generation (`:539`);
- `plan_save(...)` — explicit-path save (`:679`).

A failure returns a `GenerationPlan` with `failure_reason=VALIDATION_BLOCKED`, the blocking findings, and `refused_scope="base"`. Save and generate therefore refuse before any transform or write. Preview returns `(None, reason)`.

This is the correct shape of the restoration, but the rule set is incomplete: it excludes `PREFLIGHT` and `VARIANT`.

### 5.2 Variant gate (`G2`)

`GenerationService._gate_configuration(configuration, label)` calls `ValidationService.validate_configuration(...)` with the same three tiers. It runs for:

- each variant in `show_json(key)` (`:177`);
- each expanded variant in `plan(...)` (`:340`).

This catches core structural/relational/contract errors in a variant. It does **not** catch `R-VAR-001/002`, because those need the base/variant wire documents and declared changes. Those are available in-process from `validate_all`; no AF3 run is involved.

### 5.3 Readiness (`G3`)

`ValidationService.status()` calls `validate_base()` with **no tier restriction**, then `build_status`. The GUI Overview reads it; `status.ready` is `not blocking`. The console shows the same status block only after a blocked save.

This is a different catalogue from `G1`. In the default production wiring, the only difference that matters is `PREFLIGHT` (because `validate_base` cannot run `VARIANT` meaningfully without variant context, and those rules emit “not checked” warnings). With a real chemistry probe, the difference becomes visible:

> Probe: `ValidationService(projects, chemistry=BadSmiles())` reported `status.ready == False` with `R-ENT-010` ERROR; the same project's `plan_save` returned `ok=True` and `execute` wrote the JSON.

That is a direct readiness/gate contradiction. It is not an AF3-execution issue; it is a missing validation tier.

### 5.4 Full variant validation (`G4`)

`ValidationService.validate_all` runs the full catalogue on the base, then expands variants and runs the full catalogue on each with:

- `base_document` and `variant_documents` built by `to_wire`;
- `variant_declared_changes` from the specs;
- `variant_registries` and `variant_seeds`.

This is a pure in-memory operation. It does not run AF3 and does not need an output directory. It is used by the GUI Variants page and by tests. It is **not** called by `GenerationService`. The pre-removal `plan` did call it and blocked on variant reports. That behavior is missing.

### 5.5 Save gates (`G5`, `G6`)

Both console and GUI save routes call `plan_save`. That method calls the base gate, then transforms/encodes, resolves resources, and decides overwrite. A blocking finding returns before any write. This is essential and works.

The console’s `_write_json` prints the status block when `VALIDATION_BLOCKED`; the GUI’s `_report_save_refusal` prints a compact header and up to four findings with suggestions. The GUI’s behavior is an improvement over the console’s status block; both are user-facing only, not extra gates.

### 5.6 Preview (`G8`)

`show_json` now gates preview. This was a deliberate fix for BUG-003: an empty job previously previewed `"sequences": []`, which AF3 rejects. The current behavior is correct and covered by `tests/unit/ui/test_audit_regressions.py:135` and `:144`.

For a variant preview, it gates the expanded variant configuration with the core tiers. It does not run the variant drift/identity checks. That is the same `G2` gap.

### 5.7 Import/load (`G9`)

`ProjectService._prepare_import` reads JSON, catches `OSError`/`ValueError`, calls `from_wire`, and converts model errors into a refusal. `import_json_preview` and `import_json_commit` share that parser. A successful import installs an ordinary project.

There is no AF3 result check. An imported JSON with a version but no output directory opens normally. The console’s open path and the GUI’s preview/confirm path both use this route.

### 5.8 Transform version gates (`G10`, `G11`)

`_select_version` raises `TransformError` for `Unverified`; `_check_version_features` raises when the selected version is below a feature’s minimum. These are emitter correctness checks, not execution-success checks. They must stay unless the user deliberately removes the version concept.

### 5.9 Output safety (`G12`, `G13`)

`output.plan.decide_action` implements create/overwrite/skip/conflict/versioned. The default overwrite policy is `Fail`. `execute` refuses a plan with conflicts and refuses to write if a copied resource source is missing. A missing external MSA path produced this probe result:

```text
set_alignment: True
status ready: True
plan: True (with a warning that the resource does not exist)
execute: False
errors: ("resource source '...missing.a3m' is missing; nothing was written",)
json exists: False
```

This is a real protection, but it is delayed until execution. The user-facing status says “ready” because the missing MSA is only a preflight WARNING. This is an investigation item, not necessarily a missing gate; see §11.

### 5.10 Input guards (`G14`, `G15`)

`ConfigurationService` refuses bad families, sequences, copies, identifiers, PTM codes/positions, ligand representations, MSA source combinations, bond endpoints, seed values, and format targets. `reference_validation` checks that a template path exists, is a regular file, ends in `.cif`/`.mmcif`, is readable and non-empty, and that the pair list is non-empty, syntactically valid, and within the target sequence. These are essential and should remain.

### 5.11 Confirmations (`G17`)

The GUI asks before discard, overwrite, entity/bond/PTM/variant deletion, generation, and import. The console asks before overwrite and leaving with unsaved changes. These are workflow protections, not gates that block ordinary valid work. They should remain; the only question is whether any is redundant or too intrusive, and none currently appears to be.

---

## 6. Classification and Evidence

### 6.1 Essential builder validation — KEEP

Keep:

- all `STRUCTURAL`, `RELATIONAL` and `CONTRACT` ERROR rules;
- `R-ENT-010` when a chemistry probe is available;
- `R-MSA` advisory warnings;
- `R-VAR-001/002` (as enforcement, not merely display);
- input guards in `ConfigurationService`;
- template CIF/pair validation;
- import parse/`from_wire` validation;
- transform version and feature checks;
- output collision/overwrite/resource checks;
- confirmation and unsaved-change guards;
- no-project/empty-expansion refusals.

Evidence:

- `configbuilder/validation/catalogue.py` defines these as `CONFIRMED`/`DOCUMENTED` contract rules with ERROR severity;
- `tests/unit/validation/test_rule_checks.py` exercises the rules;
- `tests/e2e/test_app_pipeline.py:168` and `:307` verify blocking before writes;
- `tests/gui/test_readiness.py:65` verifies a blocked Save writes nothing;
- the behavioral probes above confirm valid saves and rejected invalid saves.

### 6.2 Workflow / confirmation gates — KEEP, with review

- overwrite confirmation (`messages.py:61`)
- discard confirmation (`:45`)
- entity/bond/PTM/variant deletion (`:73`, `:106`, `:111`, `:116`)
- generation confirmation (`:121`)
- import preview/confirm (`ui/render/qt/dialogs/import_preview.py`)

These are not accidental validation gates and do not require AF3 execution. They protect destructive or bulk actions. Keep. No evidence that any is redundant.

### 6.3 Personal AF3 execution-success gates — NONE VERIFIED TO REMOVE

**Finding: no runtime gate checks that a generated JSON was successfully run by AF3.**

Searched the runtime tree for:

- output/result directories, `ranking_scores`, `summary_confidences`, `*_model.cif`, `seed-*_sample-*`;
- completion markers, logs, execution status, prediction status;
- “has run”, “successfully run”, “executed”, “prediction”.

The only hits in `configbuilder/` are unrelated:

- `output/execute.py` — the builder’s own write execution;
- `transform` “execution” and “model seeds” — terminology, not status;
- `generation_service.py` “execute” — writes only;
- no AF3 result file or directory lookup.

The closest thing to an execution-adjacent gate is `R-ROOT-002`/`R-VER-001`:

- they check `configuration.format_target.version_selection` is not `Unverified`;
- they do **not** open a file, look for a result, or check a prediction;
- they do **not** require `Pinned.evidence` in the current code;
- a new job is `Pinned(3)`; an imported JSON carries its version; only explicitly unsetting the target triggers them.

The evidence-reference requirement that *was* a personal ritual is gone:

- `097c901` removed the `R-VER-002` error for a bare pin and removed the GUI evidence prompt;
- `tests/unit/validation/test_no_pin_document_dependency.py:203` asserts an unevidenced pin validates cleanly;
- `docs/CONTRACT_PIN.md` is documentation only and is never read by runtime.

Therefore **no code should be removed under category C on the current evidence**. The version gate is a policy/contract decision, not a verified AF3-execution gate.

### 6.4 Missing, damaged or incorrectly restored gates — RESTORE / REPAIR

| Finding | Evidence | Classification |
|---|---|---|
| `PREFLIGHT` omitted from `GATE_TIERS` | `validation_service.py:24`; `R-ENT-010` at `entity_rules.py:219`; probe shows status blocked/save succeeded | Restore |
| `VARIANT` omitted from generation | `GATE_TIERS`; `GenerationService.plan` has no `validate_all`; pre-removal `plan` did | Restore |
| Manifest validation report lost | `generation_service.py:448` `validation_report=None`; pre-removal passed `combined` | Restore |
| Readiness uses full catalogue, gate uses subset | `status()` at `validation_service.py:100`; `GATE_TIERS`; probe | Repair |
| `R-ROOT-002` and `R-VER-001` duplicate | both checks; probe produced two findings | Repair |
| Optional validator bypass | `GenerationService.__init__(validation=None)`; early returns | Investigate/repair |
| Stale rule summaries | `R-ROOT-002`/`R-VER-001` say “evidence reference”; actual only `Unverified` | Repair docs |
| Local tests untracked | `git ls-files tests` = 0; `.gitignore:63` | Repair repository/CI |
| Dead `_print_cards` | `menus.py:1769`, no caller | Obsolete |
| Unreachable `Auto` branch | `policy_rules.py`; `Auto.__init__` rejects empty | Obsolete |

### 6.5 Evidence for the restoration itself

The current uncommitted restoration correctly restores:

- `ValidationService` wiring in `ui/services.py:49-56`;
- base/variant gates in save/preview/generate;
- GUI Overview readiness (`pages/overview.py:140`, `:161`, `:210`);
- GUI Save refusal findings (`windows/main_window.py:462-501`);
- GUI Variants status/findings (`pages/variants.py:541`, `:631`, `:690`, `:1106`);
- GUI Generate findings and navigation (`pages/generate.py:761`, `:791`);
- console blocked-save status block (`menus.py:1541-1568`).

The local tests for these surfaces pass. That is evidence the restoration is mostly correctly adapted to the current architecture, not a blind reapply of the old code.

---

## 7. Missing or Broken Gates in Detail

### 7.1 Preflight is not in the generation gate

`GATE_TIERS` is:

```python
GATE_TIERS = (Tier.STRUCTURAL, Tier.RELATIONAL, Tier.CONTRACT)
```

`PREFLIGHT` contains `R-ENT-010` (SMILES) and the shallow MSA checks. The comment says preflight needs “a built JSON or an output environment,” but that is not accurate: `R-ENT-010` only needs a chemistry probe; the MSA rules only need inline text or a filesystem port. Neither needs a prior AF3 run or a generated output directory.

**Observed behavior:** with a `ChemistryProbe` that rejects `CCO`, `status()` reported `R-ENT-010` ERROR and `ready == False`, while `plan_save` succeeded and wrote the file. This is a genuine inconsistency and a missing essential validation tier.

**Caveat:** the production wiring uses `ValidationService(projects)` with the null chemistry probe, so today `R-ENT-010` is only a warning. Adding `PREFLIGHT` to `GATE_TIERS` alone will not block invalid SMILES unless a real probe is wired. That is a separate decision.

### 7.2 Variant checks are display-only

`ValidationService.validate_all` is the only place `R-VAR-001/002` receive the base document, variant documents, declared changes, registries and seeds. It runs on the GUI Variants page and in tests, but `GenerationService.plan` never calls it. Therefore:

- a variant can be marked “blocked” in the Variants page and still be generated;
- an unattributed drift or identity change would not stop `plan`/`plan_save`;
- the manifest records no validation summary (`validation_report=None`).

This is the clearest **missing gate** supported by pre-removal code. The old `plan` called `validate_all(only=only)` and refused when any variant report was blocking. No AF3 execution is involved; the comparison uses `to_wire` documents produced in memory.

### 7.3 Readiness and gate use different rule sets

`ValidationService.status()` calls `validate_base()` with all tiers. `configbuilder/app/status.py:157` claims `blocking` is “the same collection generation gates on.” That was true before `GATE_TIERS`; it is false now.

Consequences:

- a preflight-only ERROR can show “not ready” while Save succeeds;
- variant-tier “not checked” warnings can appear in the full base report but not in the gate;
- the Overview can be more pessimistic than the actual save/generate behavior.

This is a truthfulness/consistency defect, not an execution gate.

### 7.4 Version-rule duplication and stale wording

Both of these run in `CONTRACT`:

- `R-ROOT-002`: “JSON version is within the accepted values; the deployed-accepted value is supplied explicitly … with its evidence reference.”
- `R-VER-001`: “Generation is blocked until a format version has been verified against the deployment and the configuration carries that verification’s evidence reference.”

Actual checks:

```python
if isinstance(configuration.format_target.version_selection, Unverified):
    ...
```

Neither checks `Pinned.evidence`. Both fire for one `Unverified` state. The probe produced:

```text
('R-ROOT-002', 'No format version has been observed to be accepted by the deployment yet.')
('R-VER-001', 'Generation is blocked: no format version has been verified against the deployment.')
```

This is a duplicate gate with stale summaries. It should be repaired, not used as evidence that a successful AF3 run is required.

### 7.5 Optional validator bypass

`GenerationService.__init__` accepts `validation=None`; `_gate_base` and `_gate_configuration` return `None` when it is absent. `build_services()` always supplies it, so no production path bypasses today. But a script or future front end can construct an ungated service without saying so. This is low-risk but worth tightening after approval.

### 7.6 Local-only test evidence

The local suite is extensive and green (see §9), but `git ls-files tests` is empty and `.gitignore` excludes `tests/`, `docs/`, `fixtures/`, `tools/*.md`, `generated_jobs/`, and `af3_analysis/`. A fresh clone has no tests, no CI job and no report. The restoration can regress without any tracked check.

---

## 8. Intended Behavior Reconstructed

The builder should separate three concepts:

| Concept | Question | Current implementation | Should it block? |
|---|---|---|---|
| **Input validity** | Is this a correctly structured AF3 input? | Catalogue rules, model constructors, `from_wire`, transform version/feature checks | Yes, for genuine contract violations |
| **Builder readiness** | Does the configuration contain what the chosen operation needs? | `ValidationService.status`, base/variant gates | Yes, for missing required information |
| **Execution status** | Has AF3 actually run this input, and what did it return? | Not represented in `configbuilder` | **No** — the builder constructs inputs |

The builder currently satisfies the core separation:

- a valid job can be created and saved with no AF3 output;
- a saved JSON can be opened and edited with no AF3 output;
- a variant can be planned and written with no base AF3 run;
- invalid input is still rejected;
- missing copied resources are reported and no partial write occurs.

The only dependencies on “deployment” are version-selection policy, not prediction status:
`Unverified` is refused; a bare `Pinned` is accepted; no result file is consulted. That is consistent with “input validity” if the project chooses to require an explicit version, and inconsistent with the user’s intended removal only if the user also considers the explicit-version state itself personal.

**Conclusion:** the accidental removal was broader than the intended personal-gate removal. The restoration should keep the core validator and gates, but must not turn the version policy back into an evidence ritual.

---

## 9. Verification Performed

### 9.1 Test commands and actual results

Non-GUI suite:

```bash
python -m pytest -q tests/unit tests/e2e tests/contract tests/architecture tests/serialization tests/variant tests/golden
```

Result: **991 passed, 1 skipped** in 40.03 s, exit 0.

GUI suite (offscreen):

```bash
QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -q tests/gui
```

Result: **289 passed** in 101.15 s, exit 0.

Analysis suite:

```bash
python -m pytest -q tests/analysis
```

Result: **78 passed, 1 warning** in 108.02 s, exit 0. The warning is matplotlib’s `PyparsingDeprecationWarning`, unrelated to gates.

Targeted gate suites also passed:

```text
tests/unit/app/test_status.py
tests/unit/validation
tests/unit/ui/test_audit_regressions.py
tests/unit/ui/test_menu.py
tests/e2e/test_app_pipeline.py
 tests/gui/test_readiness.py
tests/gui/test_generate_output.py
tests/gui/test_import_flow.py
tests/gui/test_variants_batch.py
tests/gui/test_final_layout_refinement.py
```

### 9.2 Behavioral probes

All probes used temporary directories and left no project files behind.

**Valid save/open without AF3**

```text
preview: True None
plan_save: True None
execute: True
exists: True
reopen: True None
records: 1
```

No AF3 output directory, result file, or status flag was involved.

**Variant plan without a base AF3 run**

```text
add_spec: True
plan: True
execute: True
files: ['out/.../manifest.json', 'out/.../...__v1.json']
```

**Empty job blocked**

```text
status: False [('R-ROOT-006', 'The input defines no entities; ...')]
preview: True (refused with reason)
save: False validation_blocked
```

**Unverified version duplicates**

```text
status: False
blocking: [('R-ROOT-002', ...), ('R-VER-001', ...)]
```

**Preflight/gate contradiction**

```text
status ready: False
blocking: [('R-ENT-010', 'ERROR')]
save plan: True
execute: True (file written)
```

**Missing external MSA**

```text
set_alignment: True
status ready: True
plan: True (warning: resource does not exist)
execute: False (resource source is missing; nothing written)
json exists: False
```

**Actual console save**

The scripted `MenuApp` flow created a protein, saved to a temporary path, reopened it, and exited 0. The transcript contained `Saved to ...`; no blocking message. A console variant save also wrote successfully without any AF3 run.

### 9.3 What the tests cover

- `tests/unit/app/test_status.py` — defaults, missing required information, version feature conflict, blocked save status block.
- `tests/unit/validation/test_rule_checks.py` — individual catalogue rules, including `R-VER-001`.
- `tests/unit/validation/test_no_pin_document_dependency.py` — evidence-free pins and no runtime document reads.
- `tests/e2e/test_app_pipeline.py` — base/variant planning, blocking before write, save/reopen, variant CRUD.
- `tests/gui/test_readiness.py` — readiness is the service’s answer; blocked Save still refuses.
- `tests/gui/test_generate_output.py` — plan/review/execute, conflicts, blocked base/variants, findings navigation.
- `tests/gui/test_variants_batch.py` — variant status, base-blocked, `validate_all`.
- `tests/gui/test_import_flow.py` — import preview/commit and invalid/missing file refusals.

### 9.4 What the tests do not cover

- No test asserts that generation blocks on `R-VAR-001/002`; the tests only assert `validate_all` reports them.
- No test asserts readiness and `plan_save` agree when a preflight ERROR exists.
- No test asserts that `R-ROOT-002`/`R-VER-001` produce one finding rather than two.
- No test asserts that a bare pin remains accepted on the actual save path after a restoration change (the validation-level test exists).
- No test exercises a real chemistry probe on the generation path.
- No test is tracked in Git.

---

## 10. Proposed Minimal Changes, Ordered by Priority

**Do not implement any of these until the user approves this report.**

### P0 — Decide the version-policy question first

Decide whether the remaining `Unverified` refusal (`R-ROOT-002` + `R-VER-001`) is:

- a legitimate explicit-version requirement to keep, with one rule and corrected wording; or
- the last piece of the personal post-execution gate to remove.

Do not decide by name alone. The actual check is `version_selection is Unverified`; it does not read a result file. The evidence-reference ritual was already removed in `097c901`.

### P1 — Restore `PREFLIGHT` to `GATE_TIERS`

Change the gate tuple to include `Tier.PREFLIGHT`, or explicitly run preflight in the base gate. This restores the pre-removal behavior where a real chemistry probe could block a bad SMILES, and it lets the MSA advisories be reported consistently.

Do not add a new filesystem or chemistry dependency. With the default null ports, the rules remain warnings; with an injected probe, they block as designed.

### P2 — Restore variant validation in `GenerationService`

In `plan`, after expansion and before transforming, call `ValidationService.validate_all(only=only)` (or equivalent per-variant validation with the same context). Refuse if the base report or any selected variant report has `blocking()` findings. Include the findings in the `GenerationPlan`.

In variant `show_json`, use the same full variant validation for the selected key instead of only the core tiers.

This is not an AF3-execution gate: `validate_all` builds wire documents in memory with `to_wire`. It is the pre-removal behavior and it closes the display-only gap.

### P3 — Align readiness with the gate

Make `ValidationService.status()` validate with `GATE_TIERS` (plus `PREFLIGHT` after P1) rather than the full catalogue, or rename/document it as a broader review. The Overview is a base-readiness view; variant errors belong to the Variants page.

If the full catalogue is retained for `status`, the UI must not claim that its `blocking` collection is the same one generation uses. At minimum, fix the docstring and add a test that a preflight-only finding cannot make readiness disagree with `plan_save`.

### P4 — Pass the validation report to the manifest

Restore `validation_report=combined` in `plan` (the pre-removal behavior), using the reports from P2. This is traceability, not a gate: `manifest.validation_summary` should not be empty when validation ran.

### P5 — Deduplicate the version rules

Keep one blocking check for `Unverified` (recommend `R-VER-001`, because it is the rule the generation gate and tests name) and either remove `R-ROOT-002` or make it non-duplicating. Correct both summaries to say what the code actually checks: an explicit non-`Unverified` selection, not a required evidence reference.

This changes findings, not the gate condition.

### P6 — Tighten the optional validator

Prefer a required `validation` argument in production construction, or an explicit `allow_ungated=True` test seam. A silent `None` that disables every gate is a poor default even if `build_services` currently wires it correctly.

### P7 — Remove dead/stale code after the above

- remove `_print_cards` if no caller is intended;
- remove the unreachable empty-`Auto` branch or document why it remains;
- correct the `status()` docstring, `GATE_TIERS` comment, and manifest provenance docstring;
- do not remove `R-POL-*` INFO rules; their non-blocking status is intentional.

### P8 — Track verification or accept local-only testing

Either unignore a minimal tracked test suite and CI workflow, or explicitly accept that the restoration’s only regression evidence is local. At minimum, add the new regression tests from §11 to the local suite.

---

## 11. Tests Needed to Verify the Changes

### Required regression scenarios

1. **Valid base JSON saves and reopens without AF3.**
   - Build a job with one protein.
   - Assert `show_json` returns text, `plan_save` succeeds, `execute` writes, and `import_json_commit` reopens.
   - Assert no AF3 output directory or result file is consulted (a static source scan can enforce this).

2. **Valid variant JSON generates without a base AF3 run.**
   - Add a `SetSequence` spec.
   - Assert `plan` and `execute` write the variant and manifest.
   - Assert the base has no result artifact.

3. **Invalid base is still rejected.**
   - Empty job: `R-ROOT-006`, no file written.
   - Out-of-range PTM: `R-ENT-007`, no file written.
   - Duplicate ID: `R-ENT-002`, no file written.
   - Unverified version: the chosen version policy, no file written.

4. **Preflight can block.**
   - Inject a chemistry probe that rejects a SMILES ligand.
   - Assert `status.ready == False`, `plan_save` returns `VALIDATION_BLOCKED`, and no file exists.
   - This is the regression for the current contradiction.

5. **Variant drift/identity checks block generation.**
   - Construct a variant whose wire document differs from the declared edits, or use a test seam to inject an unattributed diff.
   - Assert `plan` returns `VALIDATION_BLOCKED` with `R-VAR-001`.
   - Assert a bad identity sequence blocks with `R-VAR-002`.

6. **Readiness and gate agree.**
   - For the same configuration, assert `status.ready` equals “plan_save succeeds” for base-only cases.
   - Include a preflight-only finding and a contract finding.

7. **One version finding, not two.**
   - Unset the format target.
   - Assert exactly one of `R-ROOT-002` / `R-VER-001` is reported after P5.

8. **Bare pin remains accepted.**
   - `Pinned(3)` with no evidence validates cleanly and saves.
   - `tests/unit/validation/test_no_pin_document_dependency.py:203` already covers the validation half; add the save-path half.

9. **Missing external MSA/CIF is reported clearly.**
   - Missing MSA file: current behavior is a plan warning and execution refusal; assert the user sees the error and no file is written.
   - Missing template CIF: `set_references` refuses at input time; assert it.

10. **Confirmations still work.**
    - Overwrite, discard, deletion, generation and import confirmations keep their existing tests.

11. **Optional validator cannot be forgotten in production.**
    - Assert `build_services().generation` has a validator, or make the constructor require it.

### Suggested test locations

- `tests/unit/app/test_generation_gates.py` (new: P1/P2/P3/P4)
- `tests/unit/validation/test_variant_rules.py` (existing; extend)
- `tests/gui/test_readiness.py` (extend the preflight case)
- `tests/gui/test_generate_output.py` (extend blocked variants)
- `tests/e2e/test_app_pipeline.py` (extend no-AF3 save/variant cases)
- `tests/unit/ui/test_audit_regressions.py` (keep preview/save regression)

No test should require a real AF3 installation or prediction output.

---

## 12. Uncertainties Requiring Your Decision

1. **Is `R-VER-001`/`R-ROOT-002` the personal gate you remember?**
   - The current check is only “version selection is not `Unverified`.”
   - It does not look for an AF3 result, output directory, completion marker or successful prediction.
   - A new job defaults to `Pinned(3)`, so it is normally dormant.
   - The evidence-reference requirement was already removed in `097c901`.
   - **Decision needed:** keep one explicit-version rule, or remove the `Unverified` block entirely. Removing it would also require revisiting `transform._select_version`, which currently refuses to emit without a version.

2. **Should a missing external MSA file block at save time, or only at execution?**
   - Current behavior: `status` says ready, the plan warns, `execute` refuses and writes nothing.
   - The preflight MSA rule is advisory (WARNING), so even a full validation with a real filesystem would not block.
   - **Decision needed:** is “reported at the copy step” sufficient, or should external MSA existence become a blocking input check?

3. **Should a real chemistry probe be wired into production validation?**
   - Without one, invalid SMILES is only a warning.
   - With one, `R-ENT-010` becomes an ERROR and can block.
   - **Decision needed:** is SMILES parsing a required builder guarantee or an optional advisory?

4. **Should generation enforce `R-VAR-001/002`?**
   - Pre-removal behavior did; current behavior does not.
   - The checks are in-process and do not need AF3.
   - **Recommendation:** yes, restore. Confirm that variant drift/identity stability is intended as a hard gate.

5. **Should readiness use the gate subset or the full catalogue?**
   - The current docstring says they are the same; they are not.
   - **Recommendation:** readiness should use the gate subset; variants get their own page-level full validation.

6. **Should the local test suite be tracked?**
   - It is 991 + 289 + 78 passing tests, but a fresh clone has none.
   - **Decision needed:** unignore a minimal suite and CI, or accept local-only verification.

7. **Are `tools/af3_validation`, `af3_analysis` and `generated_jobs` in scope?**
   - They are separate analysis/validation tooling, not builder gates.
   - `tools/af3_validation` uses AF3’s parser, not inference; `af3_analysis` analyzes prediction output; `generated_jobs` scripts invoke the parser.
   - **Recommendation:** leave them out of the builder gate changes. If you want them removed because they are personal post-execution tooling, that is a separate cleanup decision.

---

## 13. Bottom Line

- The accidental removal was commit `85a606a`; it removed the **entire validation/readiness layer**, not just personal execution checks.
- The uncommitted restoration correctly brings back the core gate and most UI surfaces, but it is **incomplete**: preflight and variant validation are not enforced, the readiness view disagrees with the gate, the manifest loses its validation summary, and the version rule is duplicated.
- **No runtime check requires an AF3 prediction or output result.** The only deployment-adjacent rule is the explicit-version gate, and its evidence ritual was already removed in `097c901`.
- **No removal is justified on the current evidence.** Restoring preflight and variant enforcement is the next correct step; the version-policy question needs your decision first.
- **No implementation changes have been made.** This report is the stopping point for approval.

---

### Appendix A — Files inspected

Runtime:

`configbuilder/app/{generation_service,validation_service,status,results,project_service,configuration_service,reference_validation}.py`,
`configbuilder/validation/{engine,catalogue,report,ports}.py`,
`configbuilder/validation/rules/{root,entity,msa,template,bond,policy,variant}_rules.py`,
`configbuilder/transform/{engine,from_wire,accessors,mappings}.py`,
`configbuilder/output/{plan,execute,manifest,policies}.py`,
`configbuilder/model/{configuration,records,values,references}.py`,
`configbuilder/ui/services.py`,
`configbuilder/ui/render/menus.py`,
`configbuilder/ui/render/console.py`,
`configbuilder/ui/render/qt/{state,models}.py`,
`configbuilder/ui/render/qt/windows/main_window.py`,
`configbuilder/ui/render/qt/pages/{overview,generate,variants}.py`,
`configbuilder/ui/render/qt/dialogs/{messages,import_preview}.py`.

Tests and docs:

`tests/unit`, `tests/e2e`, `tests/gui`, `tests/contract`, `tests/architecture`, `tests/serialization`, `tests/variant`, `tests/golden`, `tests/analysis`,
`docs/JSON_BUILDER_AUDIT_AND_FINALIZATION.md`,
`docs/CONTRACT_PIN.md`,
`tools/af3_validation/`,
`generated_jobs/`.

### Appendix B — Git evidence commands

```bash
git status --short
git log --oneline --decorate -25
git show 85a606a --stat
git show 85a606a -- configbuilder/app/generation_service.py
git show 85a606a -- configbuilder/ui/render/menus.py
git show 85a606a^:configbuilder/app/generation_service.py
git show 097c901 -- configbuilder/validation/rules/policy_rules.py
git show 097c901 -- configbuilder/app/project_service.py
git log --all --oneline -S "execution status" -- .
git log --all --oneline -S "has been run" -- .
git log --all --oneline -S "successfully run" -- .
```
