# AF3 JSON Builder — Independent Final Release Review

Date: 2026-10-21
Mode: read-only review. No application code, tests, configuration, dependencies,
fixtures, screenshots or generated outputs were changed. The only file created
by this review is this report.

## 1. Verdict

**Ready with caveats.**

The builder's normal workflows are backed by a green core suite, a green GUI
suite, a green CLI end-to-end suite, passing architecture/launcher/string
checks, and a filesystem-backed generation review. The single-stranded DNA
defect described in `docs/GUI_AUTOMATED_QA_REPORT.md` is genuinely fixed for
the ordinary case.

Two caveats prevent an unqualified "verified" verdict:

1. **Confirmed DNA pairing edge case.** Two independently entered lone DNA
   strands that are reverse complements of each other, or a new lone strand
   added next to an existing duplex whose partner it complements, are treated
   as one duplex. Editing or deleting one then changes or removes the other.
   This is a consequence of the model's adjacency-plus-complement partner
   heuristic (`configbuilder/model/records.py:duplex_partner`), not of the new
   `duplex=False` service path itself. It needs a product decision about
   provenance/relationships before it can be fixed correctly.
2. **CLI test-parity gap.** The CLI runtime behaviour matches the GUI for the
   DNA cases I exercised, but the permanent CLI suite has no end-to-end test
   for lone-strand edit/delete/import, and the CLI's "no complement logic"
   test is an empty `pass` placeholder. The GUI equivalent makes real
   assertions. See §5 and §7.

No normal-workflow test failed. The caveats are narrow but real; they are not
hidden by the green suite.

## 2. Environment and revision

| Item | Value |
| --- | --- |
| Branch | `main` |
| HEAD | `e8bd15ac562b8722d6f3abb0f2b489d5e8120f7c` (`Land the desktop builder and the final layout refinement`) |
| Core interpreter | `C:\Users\Chris\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`, CPython 3.11.15 |
| Core PySide6 | **not installed** (`ModuleNotFoundError`), so the core package remains usable without the GUI extra |
| GUI interpreter | `.venv-gui\Scripts\python.exe`, CPython 3.11.15, PySide6 6.12.0 |
| Core pytest | 8.2.2 |
| GUI pytest | 9.1.1 |
| Ruff | 0.16.9, default rules (repository has no Ruff configuration) |
| OS | Windows-10-10.0.26200-SP0, Git Bash |
| Qt platform | `offscreen` for automated GUI tests; no fresh real-display session in this review |

Commands were run from the repository root. The documented core/GUI split in
`RUNNING_THE_APPLICATION.md` matches the two interpreters above.

## 3. Starting working tree and protections

Before this review, `git status --short` reported:

```text
 D JSON_BUILDER_AUDIT_AND_FINALIZATION.md
 M RUNNING_THE_APPLICATION.md
 M configbuilder/app/configuration_service.py
 M configbuilder/ui/present/strings.py
 M configbuilder/ui/render/menus.py
 M configbuilder/ui/render/qt/pages/overview.py
 M configbuilder/ui/render/qt/pages/settings.py
 M configbuilder/ui/render/qt/windows/main_window.py
 M tests/e2e/test_entity_lifecycle.py
 M tests/e2e/test_menu_acceptance.py
 M tests/unit/app/test_dna_duplex.py
 M tests/unit/ui/menu_flows.py
?? .stage8_shots/
?? .stage9_core_final.txt
?? .stage9_gui_final.txt
?? .stage9_shots/
?? af3_analysis/
?? docs/AF3_Comparative_Structural_Analysis_SOP.md
?? docs/AF3_GUI_AUTOMATED_END_TO_END_QA_PROMPT.md
?? docs/AF3_GUI_FINAL_RELEASE_REVIEW_PROMPT.md
?? docs/AF3_Oct4_10_Condition_JSON_Builder_Agent_Prompt.md
?? docs/GUI_AUTOMATED_QA_REPORT.md
?? docs/IMPLEMENTATION_MAP.md
?? docs/IMPLEMENTATION_MAP_FULL.md
?? docs/JSON_BUILDER_AUDIT_AND_FINALIZATION.md
?? docs/THESIS_IMPLEMENTATION_CHAPTER.md
?? docs/screenshots/variants_probe.png
?? generated_jobs/
?? pytest-of-Chris/
?? tests/analysis/
?? tests/gui/test_accessibility_and_launch.py
```

The root audit-file deletion and every untracked item above were pre-existing.
`docs/AF3_GUI_FINAL_RELEASE_REVIEW_PROMPT.md` is the supplied review prompt,
not a file created by this review. No reset, clean, stash, restore, checkout,
rebase, amend or commit was performed, and no existing file was deleted,
renamed, moved, reformatted or overwritten.

`git diff --check` exited 0. Git emitted only CRLF/LF normalization warnings for
files already in the working tree; those are not diff errors.

Review artifacts were kept outside the tracked tree. A direct generation probe
initially resolved the GUI venv's `tempfile.gettempdir()` to the checkout
because the shell inherited POSIX `TEMP=/tmp`; the probe directories were
removed immediately, and a final `git status` shows no `af3_review_*` entries.
Pytest used its managed `pytest-of-Chris` tree, which was already untracked
before the review.

## 4. Exact commands and results

All commands below were run in this review; exit codes are the actual process
status.

| Command | Result | Exit |
| --- | --- | --- |
| `python -m pytest -o addopts="" -q` | **1048 passed, 17 skipped, 1 warning** in 119.91 s | 0 |
| `python -m pytest -o addopts="" -q tests/architecture` | **40 passed** in 8.87 s | 0 |
| `python -m pytest -o addopts="" -q tests/unit/test_launchers.py` | **19 passed** in 2.74 s | 0 |
| `python -m pytest -o addopts="" -q tests/unit/ui/test_string_registry.py` | **5 passed** in 0.69 s | 0 |
| `python -m pytest -o addopts="" -q tests/e2e` | **64 passed** in 1.53 s | 0 |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | **286 passed** in 70.62 s | 0 |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui/test_accessibility_and_launch.py -k launcher -v` | **3 passed, 8 deselected** in 7.24 s | 0 |
| `QT_QPA_PLATFORM=offscreen ./.venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui/test_generate_output.py` | **24 passed** in 4.44 s | 0 |
| `python -m compileall -q configbuilder tests/gui tests/e2e` | no output | 0 |
| `python gui.py --help` | usage printed | 0 |
| `python af3builder.py` with EOF on stdin | banner printed, exited cleanly; 0.41 s | 0 |
| `python af3builder.py` with `0\n0\n` | banner printed, exited cleanly; 0.45 s | 0 |
| `python -m ruff check configbuilder tests` | **1187 findings** under Ruff defaults | 1 |
| `python -m ruff check .` | **2437 findings** across the whole checkout | 1 |

The focused generation run was repeated with pytest's managed temporary tree
after a first attempt with an explicit `--basetemp` produced 19 setup errors,
all `PermissionError: [WinError 5] ... pytest-output` while creating the
temporary directory. Those were environment setup errors, not assertion
failures; the retry above ran all 24 tests and passed. This is a Windows
temporary-directory limitation of the review harness, not a product defect.

The full core run includes the untracked `tests/analysis` tree that is already
in the checkout; the result is the current checkout's actual result, not a
filtered subset.

### Baseline comparison

The earlier QA report's historical baseline was 1032 passed / 13 failed / 16
skipped, with the 13 failures in the two legacy CLI e2e modules. Reproducing
that baseline would require reverting the current working tree, which this
read-only review did not do. The current checkout has no failing e2e tests:
the same two modules now contribute to the 64-pass e2e result. The prior
report's claim that the 13 scripts were repaired is therefore consistent with
the current tree; the exact historical failure sequence was not re-run.

One documentation discrepancy was found: `docs/GUI_AUTOMATED_QA_REPORT.md`
describes `tests/gui/test_generate_output.py` as **26 tests**. The file defines
24 tests, and the focused run collected 24. This is a report-count error, not a
test failure or missing test file.

## 5. DNA single-strand fix and CLI parity audit

### 5.1 Service contract

`ConfigurationService.add_record` now has `duplex: bool = True`. The default
path is unchanged: one supplied DNA sequence still produces two records, the
given strand and its reverse complement, with two registry-allocated IDs. The
existing tests `test_one_input_yields_two_strands`,
`test_second_strand_is_the_reverse_complement`,
`test_strands_receive_distinct_registry_allocated_ids` and
`test_ids_stay_correct_alongside_other_entities` remain in place and pass.

`duplex=False` allocates exactly one ID and returns one `FamilyCRecord` built
from the supplied sequence. The new unit test asserts `("B", "ATGC")`, that
`B` is taken, and that `C` was not allocated. A second test edits the lone
strand and removes it without a partner; the registry releases `B`. These
assertions are real state assertions, not source-text checks.

The GUI's Add DNA action still calls `GuiState.add_record("dna", ...)` without
`duplex`, so it uses the default duplex. `tests/gui/test_entity_management.py`
checks both strands, the partner labels, partner propagation on edit, deletion
cancellation and pair deletion.

The CLI's `_add_dna_with_complement_choice` now makes one service call,
`add_record("dna", sequence, duplex=add_complement)`. The old add-duplex-then-
remove-partner loop is gone. Deletion is still by registry key through
`remove_record(record_key)`, never by list position. IDs are allocated by the
registry in the service.

### 5.2 CLI behaviour exercised manually

Because the permanent CLI e2e suite does not cover every lone-strand path, I
drove the real `MenuApp` over `ScriptedConsole` in a temporary directory. All
scenarios exited 0 with no traceback:

| Scenario | Result |
| --- | --- |
| Add protein, add lone DNA, edit it to `GGGG`, save | records `A` protein and `B` DNA `GGGG`; saved JSON parses |
| Reopen that saved lone DNA, delete it, save | only `A` remains; no partner invented |
| Protein `A` + duplex `B/C`, delete `C` | both `B` and `C` removed; `A` remains |
| Duplex `A/B`, edit `A` to `GGGG` | `A=GGGG`, `B=CCCC` (service propagation) |
| Add lone DNA, cancel its deletion | both records unchanged |
| Two lone strands with the same sequence `ATGC`, delete the first | only `A` remains; the second lone strand is untouched |

These confirm the ordinary CLI/GUI parity for the DNA paths, including the
single-strand deletion path that previously failed.

### 5.3 Confirmed edge-case defect

The partner heuristic in `configbuilder/model/records.py` defines a duplex as
an adjacent DNA record whose sequence is the reverse complement. It has no
record of whether a strand was created as part of a duplex or entered/imported
as a lone strand. That produces a real ambiguity:

```text
Add lone ATGC   -> A=ATGC
Add lone GCAT   -> B=GCAT       (B is A's reverse complement and adjacent)
Edit A to GGGG  -> A=GGGG, B=CCCC
Delete A        -> both A and B are removed
Delete B        -> both B and A are removed
```

A second form is worse for an existing duplex:

```text
Add duplex ATGC -> A=ATGC, B=GCAT
Add lone ATGC   -> C=ATGC       (C's complement GCAT is adjacent B)
Edit C to GGGG  -> B becomes CCCC, breaking the A/B duplex
Delete C        -> C and B are removed, leaving A orphaned
```

The service and both front ends share this behaviour. It is a confirmed
semantic defect for the stated goal that a lone strand can be edited and
removed without a partner. It is not fixed here because the read-only review
must not change the model, service or tests, and because a correct fix requires
a product decision about provenance (for example, an explicit duplex
relationship, a record-level origin marker, or refusing an ambiguous add). A
heuristic-only patch would risk changing the JSON contract or mispairing other
imported documents.

This edge case is not covered by the current unit, GUI or CLI tests. The
existing lone-strand tests use a single strand; the existing duplex tests use a
pair; none adds two complementary lone strands or a lone strand next to an
existing duplex.

## 6. CLI e2e repairs

The two legacy modules now pass **64 tests** in total. The previous failure
list had 13 IDs. Twelve of those node IDs now pass unchanged. The thirteenth,
`test_open_json_can_be_cancelled_at_the_confirm`, was renamed to
`test_open_json_can_be_cancelled_at_the_picker` because the CLI intentionally
opens a chosen JSON directly and no longer shows a second confirmation. The
replacement still drives the real picker, cancels with `0`, and asserts that no
project was opened and no job was replaced. Its original cancellation purpose
is preserved; the test was not deleted, skipped, xfailed or loosened.

The other repairs update stale scripted input and expected wording:

- blank job name expectation moved to the service's `Untitled job 1`;
- seeds now answer the specific/generate method question;
- DNA add now answers the complement yes/no question;
- PTM wording and the return from PTM management match the current menu;
- direct-open imports no longer need a confirmation keystroke;
- refusal cases now leave the job clean, matching the service's no-mutation
  behaviour.

The meaningful assertions remain: record types, identifiers, registry/record
agreement, saved JSON IDs, saved sequences, round-trip content, DNA duplex
counts, and cancellation state. `test_every_family_survives_a_full_lifecycle`
still saves, reopens and removes the duplex; the long-chain test still checks
state and written JSON after repeated operations.

### CLI test-quality gaps

1. `tests/unit/ui/test_menu.py::test_cli_module_contains_no_complement_logic`
   is an empty `pass` with a docstring saying the old test no longer applies.
   The GUI equivalent,
   `tests/gui/test_entity_management.py::test_the_gui_module_computes_no_complement_of_its_own`,
   actually reads the module and asserts the complement helpers are absent.
   The CLI placeholder provides no regression protection.
2. There is no permanent CLI e2e test for editing or deleting a lone strand
   after a normal add, nor for importing a lone strand and then editing or
   deleting it. The manual scenarios above pass, but they will not catch a
   future regression.
3. The e2e helper comments and scripts are now current, but the absence of a
   test for the adjacent-complement edge case in §5.3 means the suite cannot
   distinguish "lone strand" from "duplex partner" structurally.

These are test gaps, not additional runtime failures observed in the normal
paths.

## 7. GUI test quality

The GUI suite is not merely screenshot- or string-based. Representative checks
use real widgets, real Qt signals and service state:

- `tests/gui/test_accessibility_and_launch.py` starts the supported launcher
  in a real subprocess under a site hook, checks `--demo`, a path containing
  spaces, DPI scale factors 1.25 and 1.5, minimum/normal window sizes, visible
  focus traversal, the retired preview's absence, accessible names, visible
  button labels, and Escape-as-cancel.
- `tests/gui/test_entity_management.py` drives the Add/Edit dialogs, checks
  both DNA strands and partner propagation, deletion cancellation/confirmation,
  imported lone strands, ligand representations/copies, refusals and state
  preservation.
- `tests/gui/test_advanced_settings.py` covers PTMs, one-based positions,
  MSA/alignment modes and sources, templates, custom CCDs, covalent bonds,
  version interactions, refusals and cancellation.
- `tests/gui/test_variants_batch.py` covers guided variant creation, rename,
  duplicate, removal, quantity series, sequence/SMILES batches, preview-vs-
  commit equality, all-or-nothing failures and base preservation.
- `tests/gui/test_generate_output.py` covers base/selected/all scopes, policy
  pickers, plan preview with no writes, cancellation, stale plans, conflict
  policies, unwritable destinations, output bytes, manifest and assets.
- `tests/gui/test_job_lifecycle.py` and `test_import_flow.py` cover save
  refusal, overwrite confirmation, save/reopen identity and order, deterministic
  plan payload bytes, preview cancellation, invalid/missing files and
  read-only import.

Weaknesses and scope limits:

- The autouse `tests/gui/conftest.py` fixture stubs destructive confirmations
  to safe defaults. Dedicated tests override the stubs when they assert
  cancellation, but a future test that forgets to override would silently
  proceed. This is a test-design risk, not a current failure.
- `test_a_json_path_with_spaces_reaches_the_window_as_one_argument` proves
  argument forwarding and that the real window starts; its hook rejects the
  import preview, so it does not prove the file was committed.
- `test_every_destination_fits_at_the_minimum_and_normal_sizes` checks page
  bounds and the Overview horizontal scrollbar, not every child widget's
  clipping.
- The tab-order test samples 14 focus moves; it is not an exhaustive focus
  audit.
- The GUI's "no complement logic" test is a source-text assertion. It is
  stronger than the CLI placeholder but still not a runtime proof.
- No fresh screenshot or human visual inspection was performed in this
  review. The earlier QA report's real Windows screenshots are historical
  evidence, not revalidated here.

## 8. Output verification

The focused GUI generation suite passed all 24 tests. Its assertions include:

- every planned variant JSON and the manifest are parsed with `json.loads`;
- the base file is parsed separately;
- the manifest's `variants` keys are exactly `["v1", "v2"]`;
- `overwrite_policy` and `path_policy` match the picker;
- copied assets exist at the paths named in the plan and are referenced from
  the emitted JSON;
- preview writes nothing, cancellation writes nothing, and conflict policies
  preserve existing bytes;
- a file created after preview causes generation to stop before writing;
- an unwritable destination is reported, not raised.

A direct filesystem probe built a job with two variants and an external MSA,
planned with `Fail`/`CopyIntoAssets`, and executed it. It wrote three planned
entries, parsed the manifest and variant JSONs, confirmed the manifest keys
`v1`/`v2`, and confirmed the copied asset. A separate base-scope plan wrote the
base JSON. The combined probe parsed four JSON documents in total. The probe's
temporary root was the checkout only because the GUI venv resolved its temp
directory there; it was removed immediately and no output remains.

The review did not invoke AlphaFold 3, a cluster, a network service or real
thesis data.

## 9. Launch and packaging

- `python gui.py --help` exited 0 and printed the launcher usage.
- The three launcher tests passed: `--demo` starts and closes cleanly; a path
  with spaces arrives as one argv element; both 1.25 and 1.5 scale-factor
  launches start and close cleanly.
- `python af3builder.py` with EOF exited 0 in 0.41 s, printing the menu and an
  interrupted-input notice. A clean `0\n0\n` run exited 0 in 0.45 s.
- No GUI event loop was left running; the launcher tests use bounded
  subprocesses and the EOF smoke uses a timeout.
- No PyInstaller executable was built, inspected or claimed. Packaging remains
  documented, not verified as a binary.

## 10. Defects and weak tests

### Confirmed

| Item | Classification | Evidence |
| --- | --- | --- |
| Adjacent complementary lone DNA strands are treated as a duplex; editing/deleting one affects the other, and a lone strand can steal an existing duplex's partner | **Confirmed defect, edge case** | Manual `MenuApp` scenarios in §5.3: `A=ATGC`, `B=GCAT`; edit A -> B=CCCC; delete A -> both gone; duplex + lone -> partner corruption/orphan |
| `test_cli_module_contains_no_complement_logic` is an empty `pass` | **Confirmed test weakness** | `tests/unit/ui/test_menu.py:90-96`; GUI has a real source assertion at `tests/gui/test_entity_management.py:208` |
| QA report says the generation test file has 26 tests | **Confirmed documentation error** | File defines 24 tests; run collected 24 |

### Likely / coverage gaps

| Item | Classification | Evidence |
| --- | --- | --- |
| No permanent CLI e2e for lone-strand edit/delete/import | **Coverage gap** | Manual parity scenarios pass; no test function covers them |
| Autouse GUI confirmation stubs could mask a missing cancellation assertion | **Test-design risk** | `tests/gui/conftest.py` stubs discard/overwrite/delete confirmations; dedicated tests override them |
| Path-with-spaces launch test does not prove import commit | **Scope limitation** | Hook rejects the import preview; test asserts argv/window only |
| Real display, screen reader, high contrast and true 150% DPI behavior | **Unverified / human-only** | Offscreen widget checks and prior screenshots cannot prove these |

No other defects were reproduced in the normal GUI, CLI, service, persistence,
validation or generation workflows.

## 11. Prioritized remaining actions

1. **Decide the DNA relationship semantics.** If lone strands must remain
   independent, add explicit provenance/relationship data (or reject an
   ambiguous add) instead of inferring a duplex solely from adjacency plus
   complement. Add unit, GUI and CLI regression tests for:
   - two independently added complementary lone strands;
   - a lone strand added next to an existing duplex;
   - editing and deleting each in both orders.
   This is a design/application change, deliberately not made in this review.
2. **Replace the empty CLI test** with the same kind of static assertion the
   GUI uses, and add permanent CLI e2e for lone-strand edit/delete/import.
3. **Correct the QA report's 24-vs-26 test count.**
4. **Run the human checks before thesis use:** real 150% DPI, screen-reader
   announcements, high-contrast/visual review, and OS-level permission dialogs.
5. Keep the working tree's pre-existing thesis/analysis files untouched. No
   broad refactor or restyle is warranted by this review.

## 12. Final working-tree status

At the start of the review the status was the list in §3. This review created
only:

```text
?? docs/AF3_GUI_FINAL_RELEASE_REVIEW_REPORT.md
```

The final `git status --short` is the §3 list plus that report. No reset,
clean, stash, restore, checkout, rebase, amend, commit, deletion, rename or
source/test edit was performed. The root audit-file deletion remains the
pre-existing unstaged deletion. `pytest-of-Chris/` remains the pre-existing
pytest-managed temporary tree; no review-specific output directory remains in
the checkout.
