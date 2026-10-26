# Ligand Variant Generation — Audit

**Phase 1 deliverable. Audit only: no source file, test, menu, or interface was
modified to produce this report.**

Repository state: branch `main`, HEAD `6254ada` ("Consolidate AF3 validation
and generation safeguards"), working tree carrying the previously approved,
uncommitted work (23 paths — variant refocus, wording audit, fixture pack).

Baseline measured today (executed, not inferred):

| Suite | Command | Result |
|---|---|---|
| Full core | `python -m pytest -o addopts="" -q --ignore=tests/gui` | 1147 passed, 1 skipped (exit 0) |
| GUI (offscreen Qt) | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -p no:cacheprovider --basetemp=.pytest-tmp -o addopts="" -q` | 306 passed (exit 0) |
| Batch subsystem, re-run for this audit | `python -m pytest tests/unit/app/test_batch_variants.py tests/unit/persistence/test_sequence_files.py tests/gui/test_variants_batch.py -o addopts="" -q` | 70 passed, 1 skipped (exit 0) |

The one skip is the pre-existing Windows `chmod` readability test.

---

## A. Execution-path map

### Console (CLI)

```
main menu → job menu "7. Create variants based on this JSON"
  └─ MenuApp._variant_menu               configbuilder/ui/render/menus.py:1581
       ├─ "1" _vary_entities_menu        menus.py:1653   (targets workflow, previous task)
       ├─ "2" _set_variant_name          menus.py:1869   (manual flow)
       ├─ "3" _add_entity_menu           menus.py:771    (SHARED with job menu:611)
       ├─ "4" _edit_entity_menu          menus.py:1100   (SHARED with job menu:613)
       ├─ "5" _save_variant_and_reset    menus.py:1878   (manual flow)
       ├─ "6" _batch_generate_from_file  menus.py:1802   ← the file-based entry
       │     └─ VariantService.generate_from_file(path, family)   variant_service.py:1137
       │           ├─ read_smiles_file / read_sequence_file       persistence/sequences.py:109 / :56
       │           ├─ batch_specs_for_sequences                   app/batch_variants.py:101
       │           └─ add_spec (per spec, with rollback)           variant_service
       ├─ "7" _generate_variants_to_folder  menus.py:1748  ← the file-writing step
       │     └─ GenerationService.plan_selection(root, scope="variants", policies)   generation_service.py:299
       │           ├─ _variant_gate (validation)                   generation_service.py:159
       │           ├─ to_wire → plan_output (output/plan.py)
       │           └─ GenerationService.execute → output/execute.py:86
       └─ "8" _list_variants             menus.py:1829
```

**Input parsing** lives only in `configbuilder/persistence/sequences.py`
(filesystem access is confined to `persistence` and `output` by plan §5.3 rule 8):

- `read_sequence_file` (:56) — one sequence per line, blank lines skipped,
  **no comment syntax** (a `#` line fails sequence validation with its line
  number), UTF-8 or a named `PersistenceError`.
- `read_smiles_file` (:109) / `parse_smiles_text` (:79) — `#` comments skipped;
  `name SMILES` (first whitespace splits name from SMILES) or bare SMILES
  (auto-name `ligand_N`).

**Record construction** is only in `app/batch_variants.py`:
`BATCH_RECORD_BUILDERS = {protein, dna, ligand}`; the ligand builder wraps the
text in `ByNotation` → `ComponentRecord` (SMILES is *not* a sequence alphabet).
Each entry becomes one `VariantSpec(key="batch_NN", edits=(AddRecord(record),))`
— **the entry is added to the base, not substituted into an existing ligand**
(see §D, semantic question).

### Desktop (PySide6)

```
Variants page chooser (pages/variants.py:239 _build_chooser — 4 path buttons)
  └─ "Create variants from a file" → open_batch_path (variants.py:259)
       └─ _build_batch_tab (variants.py:480): family combo + path + Preview/Create
            ├─ preview_batch → state.inspect_batch_file   state.py:438 → variant_service.py:1049
            │     (read-only: builds prospective specs against a registry CLONE)
            └─ create_batch  → state.generate_from_file   state.py:442 → variant_service.py:1137
                 └─ Generate page → state.plan_selection (state.py:483) → state.execute (state.py:491)
                      = GenerationService.plan_selection / execute  (same pipeline as the console)
```

**Validation path (shared):** `GenerationService._variant_gate` (:159) runs the
authoritative `validate_all` — base report first, then every selected variant's
report (drift R-VAR-001, identity R-VAR-002 are blocking) — before anything is
planned; `execute` refuses a conflicted plan and returns `errors` rather than
raising (`output/execute.py:8-9`).

**Output layout (shared):** `<root>/<project_slug>/<project_slug>__<variant_key>.json`
plus `<root>/<project_slug>/manifest.json` (`output/naming.py:61-68`,
`generation_service.py:442/499/532`). Each variant's wire `name` is rewritten to
its directory stem (`with_wire_job_name`, `generation_service.py:439-443` —
established "job-name agreement", tested by
`test_job_name_agreement_completes_through_app`).

---

## B. Existing functionality matrix

Classification: **Verified** = code + passing test/reproducible path;
**Partial** = components exist, end-to-end not verified; **Missing**;
**Unverified**.

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | User can select and open the input file | **Verified** | Console `_pick_path` (typed path or numbered listing), driven by `tests/e2e/test_manual_test_data.py:512-516`; GUI read-only path field + browse, `tests/gui/test_variants_batch.py:926` |
| 2 | Supported formats parsed | **Verified** | `sequences.py` docstring + `tests/unit/persistence/test_sequence_files.py`; ligand = SMILES (`name SMILES` or bare, `#` comments) — `tests/e2e/test_manual_test_data.py:166` (`test_smiles_batch_reads_names_comments_and_bare_smiles`); RNA refused as a family — `test_inspect_batch_file_refuses_an_unsupported_family` |
| 3 | All entries read, not just the first | **Verified** | `test_multiple_sequences_produce_exactly_that_many_variants`, `test_blank_lines_are_ignored` (test_batch_variants.py:61,78); 3-entry e2e `test_batch_generation_full_pipeline_writes_independent_variant_files` (test_app_pipeline.py:368) |
| 4 | One independent configuration per molecule | **Verified** | `batch_specs_for_sequences` builds one `base + AddRecord` spec per entry; `test_variants_never_accumulate_one_another` (:99), `test_each_variant_contains_exactly_its_own_sequence` (:86) |
| 5 | Base configuration preserved | **Verified** | `test_base_configuration_is_unchanged_after_batch` (:118) and e2e assertion `projects.project.configuration is base`; `test_existing_dna_duplex_rides_through_untouched` (:174); GUI `test_one_variants_edits_never_leak_into_another_or_the_base` (:863) |
| 6 | Ligand representations (SMILES/CCD) per documented rules | **Partial** | SMILES verified: `_ligand_record` → `ByNotation` → wire `smiles` (`test_a_ligand_smiles_batch_builds_component_records` :264); **batch files cannot carry CCD codes** — no format exists for them (not claimed by docs); mutual exclusion enforced structurally: model sum type → `accessors.py:231-235` emits exactly one of `ccdCodes`/`smiles`, `from_wire.py:306` rejects both |
| 7 | Generated configurations are valid AF3 JSON | **Verified for protein/DNA; Unverified for ligand files on disk** | Full pipeline (transform → validate → encode → write) proven for protein batch (test_app_pipeline.py:368); ligand batch is proven only to the spec/JSON-in-memory level (`test_manual_test_data.py:175`); **no automated test writes ligand-batch files** — README scenario 2's "JSON chains carry `smiles`" is a manual claim (§D-5) |
| 8 | Entity/chain identifiers valid and unique | **Verified** | Ids allocated from a throwaway registry clone, re-reserved by `AddRecord`; `test_identifiers_are_registry_owned_and_unique_across_the_batch` (:152) |
| 9 | Seeds, version, job metadata preserved/changed per established rules | **Verified** | Base untouched ⇒ seeds/version/format ride through; wire `name` deliberately becomes `<project>__<key>` (job-name agreement, plan §13.1); manifest repeats `seed_set` (`generation_service.py:521`) |
| 10 | Output to selected folder without silent overwrite | **Verified** | Default overwrite policy is `Fail` (`output/policies.py:69-73`), passed explicitly by option 7 (`menus.py:1774-1780`); collision/casefold detection in `output/plan.py`; manifest subject to the same policy (`generation_service.py:532-540`); `execute` writes nothing on conflicts (`execute.py:94-98`) |
| 11 | Errors: malformed/empty/missing/write failures | **Verified** | `test_invalid_sequence_refuses_the_whole_batch_with_line_numbers` (:198), `test_empty_and_blank_only_files_report_no_sequences` (:208), `test_duplicate_sequences_are_refused` (:221), `test_missing_file_gives_a_clear_error` (:230); write errors returned as `OutputResult.errors`, covered by `tests/unit/output/test_execute*.py` |
| 12 | State isolation (no base mutation, no variant leakage) | **Verified** | Structural: specs expand from the same base at generation time; tests :99, :118, :131; manual-flow isolation `test_leaving_variant_management_restores_the_base` (test_menu_acceptance.py:483) |
| 13 | CLI, GUI, shared services use one implementation | **Verified for the primitives; Partial for the flow** | Both call `VariantService.generate_from_file` and `GenerationService.plan_selection`/`execute` (menus.py:1821/1759-1780, state.py:442/483/491). **Flow differs:** GUI previews with `inspect_batch_file` before committing; the console never calls it (menu.py has no reference) — §D-3 |
| 14 | Tests exercise the real generation path | **Partial** | Real path covered for protein (e2e pipeline) and GUI batch; gaps: console-ligand-batch e2e, ligand-files-on-disk e2e, menu option 8 (§D-5) |
| 15 | One-step "open file → files in folder" (the intended workflow) | **Missing** | No such path exists: `grep` for a combined helper in `configbuilder/app` returns nothing; console = option 6 then option 7; GUI = batch tab then Generate page |

### Semantic question: replace vs add (per instruction §3)

**Established behavior is ADD, not replace.** Each input entry becomes a *new*
entity record inside every variant (`base + AddRecord`); no code anywhere
substitutes a molecule into a designated ligand slot. Evidence:

- `app/batch_variants.py` module docstring and its explicit diagram
  (`Base ── + SEQ_A ──▶ Variant A`, "never A → A+B → A+B+C");
- `test_batch_generation_full_pipeline_writes_independent_variant_files`
  (base protein + DNA, each output = base + exactly one new record);
- README scenario 1: "each with the base protein **plus** one additional chain".

**Recommended minimal default: keep ADD semantics.** It is the only semantics
the code and docs define; introducing replacement would be inventing new
behavior. Note this means a ligand batch on a base job *adds N ligand entities*
(one per variant) rather than swapping an existing one — documented in §F tests.

---

## C. Menu cleanup map

Current menu (menus.py:1581-1648, labels at `strings.py:341-350`):

| # | Label | Handler | Verdict |
|---|---|---|---|
| 1 | Vary the entities in this job | `_vary_entities_menu` :1653 | **Decision D1 — see below.** Built as the primary multi-entity path in the previous approved task, GUI parity, 4 subprocess e2e tests (`tests/e2e/test_variant_cli_subprocess.py`). The sketch omits it; removing it would contradict that task and orphan its tests. |
| 2 | Set variant job name | `_set_variant_name` :1869 | **Remove from the menu** (manual in-memory flow only). Tests referencing it: test_menu_acceptance.py:467, test_edit_hardening.py:104/124. |
| 3 | Add entity | `_add_entity_menu` :771 | **Remove from this menu only — keep the function**: the job menu calls it at menus.py:611. Tests: test_menu_acceptance.py:500. |
| 4 | Edit entity | `_edit_entity_menu` :1100 | **Remove from this menu only — keep the function**: job menu at :613. Tests: test_menu_acceptance.py:487, test_edit_hardening.py:149. |
| 5 | Save variant and reset to base | `_save_variant_and_reset` :1878 (+ `_reset_variant` :1906) | **Remove from the menu** (manual flow; the base-snapshot machinery around it exists only for options 2-5). Tests: test_menu_acceptance.py:469/501/517/518, test_entity_lifecycle.py:347/350, test_edit_hardening.py:149. |
| 6 | Generate variants from file | `_batch_generate_from_file` :1802 | **Replace** by the streamlined single entry (its file/family selection folds into the new flow). Test: test_manual_test_data.py:502-522. |
| 7 | Generate the variants to a folder | `_generate_variants_to_folder` :1748 | **Integrate**: its body (destination → `plan_selection` with project policies → `execute` → written-file report) is exactly the write phase of the new flow; keep it callable as a function, drop it as a standalone menu step. Tests: test_manual_test_data scenario 0, `test_variant_cli_subprocess.py` (4 tests). |
| 8 | View all variants | `_list_variants` :1829 | **Remove** — replaced by the end-of-run report (files written + failures). No test drives it (grep for option `8` in variant flows: no matches). |

Notes:

- `_list_variants` has a dead inner branch ("Could add variant preview/edit
  options here in the future") and no test — safe to retire.
- The snapshot/restore machinery (`_variant_base`, `finally: _reset_variant`)
  exists to protect the base during options 2-5. With those gone, `_variant_menu`
  can drop it — but only after D1 is resolved, since `_vary_entities_menu`
  currently runs inside the same `try/finally`.
- Registry strings specific to removed steps: `menu.variant_name_prompt`,
  `menu.variant_saved`, `menu.variant_reset`, `menu.variant_list_*`,
  `menu.variant_batch_no_variants` (**already unused today** — 0 references
  outside the registry).

---

## D. Defect and risk list

### Demonstrated

1. **No one-step flow (the central gap).** Option 6 only creates in-memory
   specs; its success message (`menu.variant_batch_info`: "*%d variants are now
   available in the variant list*") never tells the user that option 7 writes
   files. The GUI likewise requires a second trip to the Generate page. The
   intended workflow (file → validated outputs in a folder) does not exist as a
   single action anywhere. *(Verified by code reading; no combined helper
   exists in `configbuilder/app`.)*
2. **Stale documentation number.** README says
   "`6` (View all variants) lists `batch 1 … batch 3`"
   (`manual_test_data/af3_builder/README.md:228`) — option 6 is "Generate
   variants from file"; viewing is option 8. Leftover from the menu renumbering
   in the variant-refocus task. A user following the walkthrough lands on the
   wrong prompt.
3. **Console has no preview; the GUI does.** `inspect_batch_file` (read-only
   count + per-line problems + key-collision check) is called only by the GUI
   (`state.py:440`); the console commits immediately and shows errors only after
   refusal. Same service, different amount of warning — an entry-point
   inconsistency in the exact workflow being streamlined.
4. **The SMILES `name` column is parsed and discarded.** `parse_smiles_text`
   documents `name SMILES` and returns `(line, name, smiles)`, but both service
   call sites drop it (`variant_service.py:1082` binds `_name`; `:1171` binds
   `name` and never uses it). The documented format promises something the
   feature silently ignores — users naming entries in their `.smiles` file get
   `batch 1…N` labels regardless.
5. **Test gaps** (all confirmed by grep/executed runs):
   - no console e2e drives option 6 with file type 3 (ligand) — ligand batch is
     tested only through direct service calls (`test_manual_test_data.py:175`,
     `test_batch_variants.py:276/298`);
   - **no test writes ligand-batch variants to disk** — requirement 7 above is
     Unverified for ligands on disk;
   - option 8 has no test;
   - the protein-batch console e2e asserts the success message but never
     generates files from those specs through the menu.
6. **Dead registry string:** `menu.variant_batch_no_variants` has zero
   references outside `strings.py`.

### Risks (not defects, but design hazards for the refactor)

7. **Re-running the same file in the same project refuses by design.** Variant
   keys are deterministic (`batch_01`…), so a second run hits
   `a variant keyed 'batch_01' already exists` (covered by
   `test_inspect_batch_file_reports_a_key_that_already_exists`). A one-step
   flow makes this a routine user path — decision D3 below.
8. **All-or-nothing batches.** One invalid line refuses the whole file, but
   reports *every* offending line with line numbers (`BatchError`). This matches
   "identify any entries that could not be processed" only in the
   reject-the-file sense; per-entry partial success is **not** implemented and
   is not claimed by the docs. Preserve this behavior unless explicitly changed.
9. **No chemistry validation.** SMILES are stored as text; malformed input is
   accepted with an advisory (`R-ENT-010`, warning). `batch/ligands_unchecked_syntax.smiles`
   exists to demonstrate the limit (README scenario 2 states it). Do not let the
   streamlined flow imply chemistry checking that does not exist.
10. **Overwrite safety depends on the project policy.** Default is `Fail`
    (safe), but a project configured to `Overwrite` will silently replace files
    — established behavior; the new flow must keep passing the project's
    policies explicitly, as option 7 does today.

### Decisions needed before implementation (Phase 2 gate)

- **D1 — fate of "Vary the entities in this job".** The sketch shows a
  one-option menu; this option is the primary multi-entity path from the
  previous approved task (GUI + console + 4 e2e tests). *Recommendation: keep
  it as a second entry (e.g. `2. Vary the entities in this job`) or confirm its
  retirement explicitly.* Removing it silently would undo approved work.
- **D2 — protein/DNA batch choices.** The instruction narrows the menu's purpose
  to ligands/small molecules, but the console flow currently offers three
  families and protein batch has documented walkthroughs + tests
  (README scenario 1, `test_manual_test_data.py:502`). *Recommendation: keep
  the family step (it is one question) rather than deleting a working, tested
  feature; if it must go, the affected tests/docs must be retired with it.*
- **D3 — re-run behavior.** Same file twice: refuse (current), auto-suffix keys,
  or clear specs after a successful write. *Recommendation: keep refusing
  (established, tested) and make the message say what to do.*
- **D4 — do specs created by the one-step flow stay in the variant list?**
  Current batch behavior keeps them (`variant_batch_info` says so), which is
  what makes D3 bite. *Recommendation: keep them (established) — the flow's
  report should list them alongside the written files.*

---

## E. Minimal implementation plan

### Required (to meet the success criterion)

1. **One shared orchestration method** in the app layer, e.g.
   `VariantService.generate_batch_to_folder(path, family, root) ->
   (ok, message, written_paths, failures)`, that composes the *existing*
   primitives in order: `inspect_batch_file` → `generate_from_file` →
   `generation.plan_selection(scope="variants", <project policies>)` →
   `generation.execute`. No new parsing, no new serialization, no duplicated
   CLI/GUI logic — the console handler becomes a thin prompt wrapper around it.
   (The GUI can adopt the same method later; its page already composes the same
   primitives today, so adoption is optional, not required.)
2. **Menu replacement** in `_variant_menu`: new option `1. Open ligand input
   file and generate variants` (labels per the sketch, registered in
   `strings.py`) + `0. Back`; remove options 2-8 from the menu. Keep
   `_add_entity_menu` / `_edit_entity_menu` functions (job menu depends on
   them). Resolve D1/D2 first.
3. **Flow prompts:** file selection (`_pick_path`, existing) → preview line
   (entry count, or the refusal with line numbers) → destination
   (`_ask_destination`, default `cwd/variants`, existing) → generation →
   report: written files, manifest path, and any failures (plan conflicts /
   execute errors), then return to the menu. Never claim success without
   `result.written`.
4. **Documentation fix**: README scenario 1 step 8 (`6` → `8`, D-2) and any
   walkthrough steps affected by the renumbering; note the new option in the
   menu map.
5. **Tests for the new flow** (see F) and updates to tests that scripted the
   removed option numbers (listed in §C).

### Optional (P1, not required for the criterion)

- Console preview parity: show the entry table before committing (GUI already
  does) — reuse `inspect_batch_file`.
- GUI: adopt `generate_batch_to_folder` for a one-click batch run.
- Consume the SMILES `name` as the variant **label** (keys stay `batch_NN`) —
  closes defect D4; needs no format change.
- Remove the dead `menu.variant_batch_no_variants` string.
- Drop the base-snapshot machinery from `_variant_menu` if D1 keeps the targets
  path (it does not use the snapshot).

### Explicitly out of scope

- No new file formats (e.g. SDF, CSV), no chemistry dependency, no changes to
  `output/` naming or policies, no changes to validation rules, no GUI layout
  surgery beyond what the console parity requires.

---

## F. Regression-test plan

New tests (all through real entry points; `tmp_path` for every output):

1. **Several valid ligand entries** — console subprocess e2e: option 1 →
   `manual_test_data/af3_builder/batch/ligands_valid.smiles` → destination →
   assert exit 0, the printed count, and **3 JSON files + manifest** exist.
2. **Output count / independence** — parse each file: exactly one has
   `smiles: "CCO"`, one `"CC(=O)O"`, one `"C1CCCCC1"`; every file still carries
   the base's entities (structural deep-equal of the base subset).
3. **Base preservation** — assert the input fixture file bytes are unchanged
   and the service's base configuration object/records are untouched after the
   flow (mirror of `test_base_configuration_is_unchanged_after_batch`).
4. **Molecule→variant mapping** — order: `batch_01` = first file line, etc.;
   wire `name` = `<project>__batch_01`; `modelSeeds`/`version` inherited from
   the base.
5. **Representations** — generated ligands emit `smiles` and **never** both
   `smiles` and `ccdCodes` in one entry (scan every output).
6. **Invalid input** — a SMILES file with one bad-alphabet entry (protein-style
   letters) and a `#`-comment file: refusal message names the line numbers,
   **zero files written**, exit path stays clean (no traceback).
7. **Empty input** — empty file and comments-only file → refusal, no files.
8. **Duplicates and collisions** — duplicate SMILES → refused with the values;
   second run against the same project → `a variant keyed … already exists`
   message, no partial output (D3 behavior, pinned by test).
9. **Output-directory errors** — destination is an existing file / an
   unwritable path / default `Fail` policy with pre-existing outputs → plan
   conflicts reported, nothing overwritten, no success message printed.
10. **Validation of every generated JSON** — after the run, `validate_all`
    reports no blocking findings for base + the created variants (the gate
    already runs before writing; assert the report, not just file existence).
11. **Preservation of everything else** — full core + GUI suites as the
    baseline above; any test that scripted removed menu options is renumbered
    (never weakened), and the job menu's shared add/edit entity flows keep
    their own coverage (test_menu_acceptance.py:286+).

Pre-change baseline for comparison: **core 1147 passed / 1 skipped, GUI 306
passed** (commands in the header table). Any failure after Phase 2 is triaged
as pre-existing vs regression against exactly those numbers.

---

*End of audit. No source, test, menu, configuration, or interface file was
modified in Phase 1. Awaiting review before Phase 2.*
