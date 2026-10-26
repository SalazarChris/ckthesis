# Task: Create AF3 Builder Manual Test Data and Verify RNA MSA Handling

## Role

You are working in the existing AF3 JSON Builder repository. This is a focused test-data and behaviour-verification task for the working CLI and PySide6 GUI. The goal is to give the developer small, reusable dummy files for manually testing batch generation, external MSA inputs, and template files through **both** interfaces, while carefully verifying how RNA MSA is represented and applied.

The application already has working services, JSON serialization, CLI workflows, GUI pages, tests, and a file-output planner. Reuse them. Do not rebuild the application or invent a separate implementation for the test pack.

## Safety and scope constraints

1. Start by inspecting the current repository, the current Git status, and the latest implementation reports. Report the actual HEAD and baseline; do not assume older reports describe the current tree.
2. Preserve all existing tracked modifications and untracked files. Do not run `git reset`, `git clean`, `git checkout`, `git restore`, `git stash`, rebase, amend, or broad formatting/cleanup commands. Do not commit anything.
3. Do not run AlphaFold 3 inference, submit cluster jobs, use network resources, or require a university server. This task tests the builder's parsing, configuration, UI, validation, serialization, and output handling only.
4. Never put credentials, private user files, or large biological datasets in the test pack. Use small, clearly synthetic examples, or reuse an existing repository fixture only if its purpose and provenance are clear.
5. Do not claim a file is accepted by the AF3 runtime merely because the builder accepts its path or serializes it into JSON. Distinguish **builder behaviour**, **input-contract/schema support**, and **runtime acceptance**, and explicitly state which were and were not tested.
6. Do not guess about RNA MSA. Follow the real code path and the authoritative schema/documentation available in the repository. If the repo does not establish a rule, record the uncertainty and seek a primary AF3 source only if internet access is permitted in this environment. Cite the exact source/version/date in the report; do not silently infer behaviour from protein MSA.
7. Keep changes focused on test data, tests, and documentation. If the audit finds a likely RNA-specific defect, first demonstrate it with a failing test and report the evidence. Make only a minimal fix if the intended behaviour is clearly established by the project contract or a primary AF3 source. If semantics remain ambiguous, do not change biological/input semantics; leave a clear finding and recommended decision.

## Phase 1 — Audit existing behaviour before creating files

Inspect the actual current implementations and relevant tests, including (adapt paths if the repository has changed):

- `AUTHORITATIVE_SPEC.md`, `DOMAIN_MAPPING.md`, and the applicable AF3 JSON schema/documentation included in the repository.
- `configbuilder/model/` alignment/MSA representations and record models for protein, RNA, and DNA.
- `configbuilder/app/configuration_service.py` methods for setting alignment/MSA and templates.
- `configbuilder/transform/` mappings and serialization path that turns each MSA mode into AF3 JSON fields.
- MSA-related validation rules and finding messages.
- `configbuilder/persistence/sequences.py` and related parsers for sequence/SMILES batch files.
- `configbuilder/app/variant_service.py` methods for batch-file inspection and generation.
- `configbuilder/app/generation_service.py` and output/resource-copy logic for external MSA and template paths.
- CLI menus and GUI `AdvancedPage`/entity-selection workflows, plus existing tests for alignment, templates, batch generation, output planning, and JSON serialization.

Create a concise behaviour matrix with columns:

- entity family;
- supported MSA/alignment modes in the current code;
- service method and model representation used;
- exact JSON keys emitted for each mode (for example, do not assume `unpairedMsa` or `pairedMsa` are applicable to RNA—verify each key);
- whether the input is inline text, an external path, or no input;
- validation behaviour for missing/unreadable files;
- whether generation copies the external resource into an assets directory or references its original path under each supported policy;
- what can be tested without running AF3;
- what remains uncertain about the AF3 runtime.

### RNA MSA audit — required, explicit conclusions

Do not treat RNA as protein with a different sequence alphabet. Trace the RNA path end to end:

1. What RNA MSA modes does the application actually offer in the CLI and GUI?
2. What options are enabled or disabled in the UI for each mode? Does choosing a mode reveal the appropriate text/file control?
3. What exact model value is stored by the service for Automatic, Free/None (if present), and user-provided RNA MSA?
4. Which exact AF3 JSON field(s) does the serializer emit for RNA in each mode? Confirm this from transformation/mapping code and tests, not from the UI label.
5. Does RNA use the same file format and semantics as protein MSA, or a distinct contract? Cite repository/primary documentation evidence. If unknown, say so.
6. Does a user-provided RNA MSA need a particular format, such as A3M or another format? Verify before choosing fixture content and extension. Do not claim format validation if the application only stores a string/path.
7. Is the external RNA MSA path handled correctly through save/output generation, including spaces in the path and assets-copy policy?
8. Are absent, empty, malformed, and nonexistent RNA MSA inputs treated consistently with the project contract? Test only cases that can be justified.
9. Check whether the current GUI and CLI offer equivalent capabilities. Report any mismatch (for example, a mode available in one interface but not the other).
10. Do not run inference. The final report must clearly separate conclusions proven by code/tests from claims that would require an AF3 server run.

## Phase 2 — Create a small, user-facing manual test pack

Create a clearly named root-level directory such as `manual_test_data/af3_builder/` (inspect existing conventions first and avoid overwriting existing files). Include a `README.md` in that directory explaining the purpose of every file, which CLI and GUI workflow uses it, the expected result, and what it does **not** prove.

Keep files tiny and deterministic. Prefer relative links in the README and include a generated inventory/manifest with file names, purposes, and SHA-256 checksums if convenient.

Include appropriate fixtures from these categories, following the formats the existing parser and contract actually support:

### A. Batch generation inputs

- A valid protein FASTA/sequence file with several distinct entries, including at least one multi-line/wrapped entry **only if** the existing parser is supposed to support wrapping. Otherwise use the exact supported syntax and add a separate invalid example for unsupported wrapping.
- A small RNA sequence file only if RNA is an officially supported batch family; if not, document that fact and include an intentional negative test rather than implying support.
- A small DNA sequence batch file if supported by the batch service.
- A multi-line SMILES batch file with several simple, clearly labelled examples, using the exact delimiter/comment/record convention accepted by the parser.
- Invalid examples for an empty file, a malformed sequence record, and malformed SMILES only where these can be tested meaningfully. Keep invalid examples separate and label them clearly.

Batch test fixtures should cover multiple entries, not just a single sequence. Use harmless synthetic sequences (for example, short standard amino-acid sequences and short nucleotide sequences) and simple illustrative SMILES. They are builder test inputs, not evidence of biological usefulness.

### B. Protein MSA fixtures

Create very small fixtures for each user-provided protein MSA mode the current app supports. Use the format and field semantics established by the project contract. If both inline and file-based MSA are supported, provide examples for both. If paired and unpaired MSA have distinct inputs, provide the minimum examples required for manual testing each distinct path. Clearly label synthetic content and do not imply it is a biologically meaningful alignment.

### C. RNA MSA fixtures — highest priority

Create fixture(s) that let the user test each confirmed user-configurable RNA MSA mode in both CLI and GUI. Use the correct, verified file format only. Provide a README section that explains:

- which UI choice to select;
- what file/text to select/paste;
- what should be visible in the builder's model/status;
- what key(s)/value(s) should appear in the saved JSON;
- whether an external file should be copied into assets or referenced, according to the selected output policy;
- whether the behaviour is only builder-verified or also supported by authoritative AF3 documentation.

If the current interface permits “provided RNA MSA” but the intended external format or JSON field cannot be established, do **not** fabricate an alignment. Make a clearly labelled investigation fixture only if it is still safe/useful for testing path handling, and prominently label it “format not runtime-verified”. Report the ambiguity separately.

### D. Template fixtures

Provide a minimal, small mmCIF template fixture for the template-selection/path workflow, plus a README that identifies its limitations. Prefer an existing repository fixture with a known purpose if suitable. Otherwise create a syntactically structured synthetic mmCIF only if the expected fields and chain/sequence references can be determined from the applicable contract.

Do not claim the synthetic mmCIF is a valid biological template or will be accepted by AF3 unless that has actually been verified against an authoritative validator/runtime. If all that can be verified locally is file path selection, serialization, and copying, state that explicitly. Include one missing-template-path scenario in tests without creating a real broken file in the normal valid-fixture folder.

### E. Path-handling fixture

Place at least one copy of an MSA and/or template fixture under a directory name containing spaces, or create a second copy for this purpose, so both interfaces can be tested for correct path handling. Document the intended relative/absolute path usage. Avoid hard-coding the developer's machine-specific absolute path into JSON fixtures.

## Phase 3 — Automated tests using the manual test pack

Add focused tests that load the committed fixtures by repository-relative path and exercise the real service/CLI/GUI flows as far as practical, while keeping existing test architecture intact.

Tests should cover, when supported:

- parser output for multi-entry protein/RNA/DNA batch files and SMILES lists;
- batch preview followed by commit, with correct count/order and all-or-nothing behaviour;
- cancelling batch generation without changing the base configuration;
- each supported protein MSA mode and each supported RNA MSA mode at the model/service boundary;
- exact serialized JSON field names and values for RNA vs protein MSA;
- validation of missing external MSA/template paths, where a relevant rule exists;
- correct asset copying or path emission under each available output policy;
- filenames/paths containing spaces;
- template path serialization and resource handling;
- GUI controls correspond to the modes genuinely supported by the service;
- CLI and GUI parity for supported options, with documented exceptions where the CLI or GUI is intentionally different;
- no AF3 inference, network calls, or writes into the working directory during tests.

Use `tmp_path`/temporary output directories for generated files. Do not make tests dependent on the user's actual home directory or on manually installed external applications. Where GUI tests require PySide6, follow the repo's existing optional-GUI test conventions.

If a defect is found, add a regression test demonstrating the defect before the fix. Do not loosen an existing test just to make the suite green.

## Phase 4 — Prepare the manual CLI and GUI walkthrough

The `manual_test_data/af3_builder/README.md` must give the user clear steps for both interfaces, using actual commands and fixture paths determined from the current repository. Avoid invented menu numbers: inspect the current menus and write instructions using their real wording/order.

For every scenario, include:

- **Goal**;
- **Files to select**;
- **CLI steps** (actual prompt sequence, not guessed menu numbering);
- **GUI steps** (page, controls, buttons);
- **Expected builder result**;
- **How to check the saved JSON** without running AF3;
- **Cleanup** (only the temporary output folder created for the scenario).

At minimum provide walkthroughs for:

1. Batch creation of multiple protein variants from FASTA/sequence input.
2. Batch creation from SMILES input, if supported.
3. Protein MSA using each available user-provided mode.
4. RNA MSA using each supported user-provided mode — explicitly compare it with protein behaviour.
5. Protein template selection with mmCIF path.
6. External MSA/template asset handling when generating to a new output directory.
7. Invalid/missing MSA and template paths.

Avoid telling the user to manually inspect raw JSON unless it is the only practical way to verify an output. If you do use JSON inspection, explain exactly which field/path should be present.

## Phase 5 — Verification and report

Run and record:

- relevant existing and new parser/service tests;
- relevant CLI end-to-end tests;
- the GUI test suite in the GUI environment;
- architecture tests;
- the full test suite using the core interpreter;
- compilation/lint checks for changed files using repository conventions (do not run automatic repository-wide formatting).

Compare the test result to a measured baseline from immediately before your changes. List exact failed node IDs if anything fails, and label them as pre-existing, newly introduced, or indeterminate with evidence.

Create `docs/AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md`, containing:

1. repository revision and working-tree protection statement;
2. inventory of every created/modified file;
3. the test-data directory tree and each fixture's purpose;
4. the RNA MSA behaviour matrix with exact JSON fields and source evidence;
5. differences between GUI and CLI, if any;
6. exact test commands and results;
7. any defect found and its minimal fix, with regression test;
8. what is known only about builder behaviour versus what remains unverified at AF3 runtime;
9. a concise manual run checklist for both interfaces;
10. limitations and decisions needing human input.

Also update the repository's existing `RUNNING_THE_APPLICATION.md` only with a short link to the new manual fixture README, unless there is a clear reason not to touch it. Do not rewrite general user documentation unnecessarily.

## Acceptance criteria

This task is complete only when:

- The user has a dedicated directory of small, clearly labelled dummy input files for batch generation, MSA and templates.
- Each fixture has an explanation and expected use in the README.
- RNA MSA has been traced from UI choice → service/model state → validation → JSON serialization → output/resource handling, with exact keys and source/test evidence.
- Tests distinguish supported builder behaviour from assumptions about the remote AF3 runtime.
- Both CLI and GUI have practical, accurate manual instructions.
- Existing user work is preserved, the baseline is measured, and all test results are reported honestly.
- A final report is written to `docs/AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md`.

Start with the audit, then proceed through the phases. Do not stop after merely listing what you intend to do; deliver the fixture pack, tests, documentation, and evidence-based report within this scope.
