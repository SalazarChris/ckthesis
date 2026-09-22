# Implementation Checklist — AF3 Input Builder (configbuilder)

Derived from `AUTHORITATIVE_SPEC.md` (external contract), `DOMAIN_MAPPING.md` (`MAP-###`
traceability), and `IMPLEMENTATION_PLAN.md` §21 (phases and exit criteria). Phases are
dependency-ordered: build exactly 0 → 12; nothing in a later phase is needed before its
predecessors' exit criteria are met.

---

## Phase 0 — Contract probe and scaffold
- [ ] Run the human contract probe (§22.4): submit a minimal valid input through the **real** execution path; record dialect + accepted version in `docs/CONTRACT_PIN.md` — until then `VersionPolicy` stays `Unverified` and generation is blocked *(human task; blocked on deployment access — `docs/CONTRACT_PIN.md` record structure is in place)*
- [ ] Retain the accepted probe input as the first `fixtures/golden/external/` fixture *(awaits the probe)*
- [x] Create `pyproject.toml` — `requires-python = ">=3.9"`, **zero runtime dependencies**
- [x] Create the ten packages: `model, identity, validation, transform, serialize, variants, output, persistence, app, ui` + `tests/` + `fixtures/{golden,invalid,projects}/`
- [x] `docs/CONTRACT_PIN.md` with the §22.4 record structure (observed format, evidence, date, outcome, unknowns)
- [x] CI: lint + pytest on **Python 3.9.18, both Linux and Windows** (`.github/workflows/ci.yml`); interpreter assertion + architecture tests enforce no 3.10-only constructs (`match`, `slots=True`, `X | Y`, `TypeAlias`, `assert_never`, `tomllib`)
- [x] `tests/architecture/` dependency-rule scanner passing on the empty tree

**Exit criteria:** suite green on 3.9.18 both platforms; pin records a verified format or an explicit "no probe yet". *(Local dev runs 3.11 with 3.9-compatible sources, CI-verified on 3.9; `CONTRACT_PIN.md` records "no probe yet" — `Unverified` blocks generation by design.)*

## Phase 1 — Rule catalogue as data
- [x] `validation/catalogue.py`: every rule as a row — `rule_id`, tier (`STRUCTURAL → RELATIONAL → CONTRACT → VARIANT → PREFLIGHT`), severity policy, `spec_ref` (AUTHORITATIVE_SPEC section), evidence status, `mapping_ids`; **no `check` implementations yet**
- [x] Transcribe every row of spec §19's validation matrix (root / entity / MSA / template / ligand-bond)
- [x] List spec §19's deliberately-not-promoted items (seed uniqueness/sorting, chain-ID algorithm, fixed 10 seeds, biological plausibility, output-analysis rules) as `INFO`-only
- [x] Tests: every `spec_ref` resolves to a real spec heading; `UNRESOLVED` ⇒ `INFO`-only; no uncited rule

**Exit criteria:** catalogue covers 100% of the spec matrix.

## Phase 2 — Identity
- [x] `identity/`: `EntityId` (uppercase-alphabetic enforced at construction), `Multiplicity` (ordered copy IDs), `IdAllocator`, `IdentityRegistry`
- [x] Deterministic monotonic allocation; skip taken IDs; explicit assignment of a taken ID ⇒ finding, never silent rename; progression continues past `Z` (spec §7.6)
- [x] `resolve(entity_id)` for linkages; `rename()` returns a rewrite map applied by `app` in one operation
- [x] Allocation is a pure function of assigned state — no clock, no randomness, no hash order
- [x] Tests: determinism, overflow past single-char range, collision refusal, rename rewrite completeness, clone independence, property test (uniqueness under arbitrary add/remove/rename sequences)

**Exit criteria:** no other module knows how an identifier is formed. *(Met: architecture tests confine `IdAllocator`/`EntityId` construction to `identity/`, and `identity/` imports no project module.)*

## Phase 3 — Canonical model
- [x] Value types: `Position` (1-based) and `IndexPair` (0-based) as **distinct nominal types**; `ResidueRef` (1-based); `Seed` (uint32); `SequenceText` (family alphabet); `ComponentCode` (rejects `CCD_` prefix); `ResourceRef = Inline | External(PathSpec)`
- [x] Presence algebra `Unset | ExplicitEmpty | Present` — `Optional`/`None` banned for contract fields; one `fold_*` per sum type, final `raise` on unknown case
- [x] Sum types: `AlignmentPairing` (Automatic/Free/UnpairedOnly/PairedOnly/Both — half-set uninstantiable), `SingleAlignment`, `ReferenceSet.SearchAllowed | Explicit(())` (empty tuple = explicitly template-free), `ComponentRepresentation.ByCode | ByNotation`
- [x] Four families, only contract-granted fields: `FamilyARecord` (protein: seq, modifications, alignment, references), `FamilyBRecord` (RNA: single alignment), `FamilyCRecord` (DNA: **no alignment/reference field at all**), `ComponentRecord` (representation)
- [x] `ModificationRecord` = code + position only (base identity stays in parent sequence — MAP-501..504 not collapsed)
- [x] `ReferenceRecord.index_map` as `(query, template)` **pairs**, not parallel arrays
- [x] `Linkage` at root (endpoints reference records by `EntityId`)
- [x] `Configuration` root: metadata, seeds (non-empty), records, linkages, `component_definition`, `IdentityRegistry`, `FormatTarget` (single-member `Dialect` enum; `VersionSelection = Unverified | Pinned | Auto`)
- [x] All frozen; `with_*` derivation helpers; defaults: `Unset`/`Automatic`/`SearchAllowed`/`Unverified`
- [x] Traceability registry: every type → mapping ID + UI label (plan §3 table)
- [x] Tests: invariants, half-set uninstantiable, DNA has no alignment field, equality/hash stability, registry completeness

**MAP-004 clarification (design record):** `Record` is a lightweight traceability anchor, not a
primary domain object. `Configuration` (MAP-001) remains the root aggregate; the protocol carries
only `ids` + `description` (plan §7.4), owns no workflow/validation/persistence/identifier role,
and nothing outside `model/` may import it — dispatch uses the concrete families. Machine-checked
by `tests/architecture/test_record_protocol.py`.

**Exit criteria:** full configuration constructible in code — no validation, no wire concepts, no IO.

## Phase 4 — Validation engine and rules
- [x] `report.py` (typed `FieldPath` locator, `Finding` with user_message vs diagnostic vs suggestion), `ports.py` (`FilesystemPort`, `ChemistryProbe`), `engine.py` (tier order; later tiers run despite earlier findings; skipped rules **reported**, never silently green)
- [x] Implement every catalogue rule; severity: CONFIRMED/DOCUMENTED ⇒ `ERROR` (non-downgradable); INFERRED/project ⇒ `WARNING` (adjustable); UNRESOLVED ⇒ `INFO`-only *(all 42 rules executable: `validation/rules/{root,entity,msa,template,bond,policy}_rules.py`; R-POL rules always emit their INFO finding)*
- [x] Convert identity exceptions to findings at the engine boundary: `identity.DuplicateIdError` ⇒ **R-ENT-002** (RELATIONAL, ERROR — explicit assignment of a taken ID is refused by the registry, plan §8.1, never silently renamed); other `IdentityError` cases (e.g. unresolved references) map to their own catalogue rules. The registry keeps its raise-based contract; raw identity exceptions never reach the UI *(implemented as `engine.convert_identity_error`, meta-tested in `tests/unit/validation/test_identity_conversion.py`)*
- [x] Generation gate: zero `ERROR`; `WARNING` needs explicit acknowledgement *(Report.blocking() = ERRORs; R-VER-001 blocks on Unverified — acknowledgement UI arrives with app/Phase 10)*
- [x] Preflight shallow only (path syntax, exists, readable, non-empty, execution-host resolvability) — no reimplementation of external parsing; disable-able by policy *(ValidationContext(run_preflight=False) reports skips; null FilesystemPort yields "not checked" findings)*
- [x] Chemistry probe optional: null probe ⇒ rule is `WARNING` "not checked"; real probe ⇒ `ERROR` *(R-ENT-010)*
- [x] Tests: one positive + one negative per rule; meta-tests for coverage and `spec_ref` resolution; fake filesystem; skip reporting *(positive/negative pairs in `test_rule_checks.py`; completeness meta-test in `tests/contract/test_rule_completeness.py` — every catalogue rule resolves to an executable check; valid-input run records zero skips)*

**Exit criteria:** every rule executes and is covered both ways; nothing enforces an unresolved item as an error.

## Phase 5 — Transformation
- [x] `transform/`: field-mapping tables per family + root, each row `(accessor, wire field, mapping id, emission rule, min version)`
  - `mappings.py` tables; compound rows (empty accessor) record the structural `sequences` container (MAP-103), modification entry sub-fields (MAP-204/205, 304/305, 354/355), the ion alias (MAP-405 → `ccdCodes`), and the MAP-406 constraint; a meta-test asserts every contract field id is covered
- [x] Emission: `Unset` ⇒ omit; `ExplicitEmpty` ⇒ contract's empty value; inline/path mutually exclusive per representation
  - protein MSA: both sides always represented (spec §11), empty side as inline `""`; a side emits exactly one of inline/path (spec §6.1); `AlignmentBoth` fills both sides from its shared source (observed usage pattern)
  - bug fixed en route: RNA/DNA modification entries now emit `modificationType`/`basePosition` (MAP-304/354), not protein's `ptmType`/`ptmPosition`
- [x] Conversions, here and nowhere else: `AlignmentPairing` → field pair; `ReferenceSet` → omitted-or-list; `index_map` pairs → two parallel 0-based arrays; `Multiplicity` → single value or list; representation → exactly one of `ccdCodes`/`smiles`
  - dispatch goes through the model folds (`fold_alignment`, `fold_single_alignment`, `fold_reference_set`, `fold_representation`, `fold_resource`) — no raw isinstance over sum types in transform
- [x] Version selection: `Unverified` blocks with an explanatory ERROR; `Pinned(n)` from the observed acceptance; `Auto` only over evidenced versions; feature above pin ⇒ ERROR naming the feature (never silently raise the version)
- [x] Emit `ExternalResourceRequirement[]`
  - requirement kind names the referencing wire field: `pairedMsaPath` for paired-only sources, both kinds for `AlignmentBoth`
- [x] Tests: row-level mappings; presence-preservation + index-preservation property tests (no arithmetic); version-selection cases; totality on validated input

**Exit criteria:** validated config → wire document; **no wire field-name literal outside `transform`** — machine-checked by `tests/architecture/test_wire_field_confinement.py` (wire names as dict keys/subscripts only inside `transform`; `FieldPath`'s finding-locator slot is explicitly not structure building, plan line 826).

## Phase 6 — Serialization
- [x] `serialize/encode.py`: UTF-8 no BOM, LF, one trailing newline, binary-mode writes, fixed indent/separators, key order exactly as produced by `transform`, no timestamps/host/env-derived content
  - `ensure_ascii=False` (non-ASCII stays UTF-8), `allow_nan=False`, `EncodeError` for unpaired surrogates/non-serializable values, `encode_to_file` binary-only with deliberately no encoding parameter
- [x] No conditionals on field names in the serializer
  - machine-checked: `tests/architecture/test_serializer_purity.py` (no wire-name literals in `serialize/`, no string-value comparisons; positive control in both operand orders incl. `in`-tuple form)
- [x] Tests: cross-process byte determinism, escaping (incl. non-ASCII), ordering stability
  - `tests/serialization/` per plan §18.1: six fresh interpreters with different `PYTHONHASHSEED` values produce byte-identical `encode(to_wire(c))`; control-char, quote/backslash, and non-ASCII escaping; insertion-order stability
  - golden: `fixtures/golden/project/{comprehensive_families_v4,minimal_protein_v3}` + `build_fixture.py` (recipe → model → wire → bytes); `tests/golden/` asserts byte identity, policy conformance, and provenance labels (plan §15)

**Exit criteria:** `encode(to_wire(c))` byte-stable ✓; first `golden/external/` fixture still awaits the Phase 0 probe — the first *project* golden fixtures now pass, and `external/` provenance requirements are enforced so probe evidence slots in unchanged.

## Phase 7 — Variants
- [x] Edit vocabulary (plan §12.1: SetName/SetDescription/SetSeeds/SetSequence/Add·RemoveModification/Set·SingleAlignment/SetReferences/SetComponentRepresentation/Add·RemoveRecord/Add·RemoveLinkage/SetComponentDefinition/SetFormatTarget), resolved via `record_key` through identity — never list position
- [x] `VariantSpec` (key, label, edits, declared_factors); `expand()` pure; `Lineage` with base fingerprint = content hash of base wire document
- [x] VARIANT-tier rules: drift check (variant wire doc vs base; anything not attributable to a declared edit ⇒ finding), identity stability, seed-set stability (project policy ⇒ `INFO` per the catalogue's spec §19 row; rules missing their comparison data report `WARNING` per plan §9.6)
- [x] Registry cloned per variant; released IDs not reused within an expansion run
- [x] Tests: isolation (edit one → siblings + base unchanged), inheritance byte-identity, expansion determinism, drift detection, lineage fingerprints

**Exit criteria:** editing one variant provably cannot change a sibling or the base; undeclared differences are reported.

## Phase 8 — Output generation
- [x] `slug()` pure, restricted charset legal on POSIX + Windows, underscores avoided in generated component-style names (spec §9.6); job `name` = directory/filename name (in-file and on-disk agree) — *the name agreement is completed by `app`/Phase 10, which passes the derived name into `to_wire`'s root `name` field*
- [x] `plan()` (pure) → `execute()` (writes only); collision detection case-insensitive, at plan time across the whole run
- [x] `OverwritePolicy` (default **Fail**), `PathPolicy` (default **CopyIntoAssets**; RelativeToOutput; AsGiven) — policy recorded in manifest
- [x] Atomic writes (temp + `os.replace`); all-or-nothing under Fail; directories created only as planned
- [x] Emitted paths: forward slashes, relative wherever policy permits; non-resolvable absolute path ⇒ authoring-time PREFLIGHT WARNING naming the fix — *collected as plan `warnings` data; their surfacing through validation reporting lands with `app` (§5.3 rule 4: output does not validate)*
- [x] Manifest: project name, base fingerprint, pinned version **+ CONTRACT_PIN record id**, path policy, per-variant key/label/factors/edits/filename/fingerprint, seed set, validation summary, builder version; time-varying data isolated in `run_info`
- [x] Tests: planning/collisions vs fake filesystem, each overwrite & path policy, atomicity under simulated failure, manifest determinism excl. `run_info`, naming-injectivity property

**Exit criteria:** variants → reviewed plan → self-describing directory tree.

## Phase 9 — Persistence
- [x] Project file ≠ generated input file; own `schema_version` axis; JSON payload *(payload keys deliberately avoid wire vocabulary — `job_name`, `pinned_version`, `target_dialect`, `modification_set`; the architecture test enforces the distinction, and the v0→v1 named upgrade step migrates the retired spellings)*
- [x] Lower version ⇒ named upgrade step; higher ⇒ refuse with clear message; load through the **same model constructors** (corrupt files can't inject invalid models); validation findings surfaced immediately on load *(`upgrade()` runs named steps in order; decode mirrors encode dispatch for every sum type; every constructor/`SequenceText`/`Multiplicity`/`resolve_strict` refusal becomes a `PersistenceError` naming the JSON location; `load` accepts an injected validator so findings ride `LoadResult` without a layering violation)*
- [x] Registry persisted — reopening never reassigns identifiers *(allocation state, owners, and groups serialized; retired IDs stay retired — `test_identifiers_survive_reopening` / `test_retired_identifiers_stay_retired_after_reopening`)*
- [x] Tests: round-trip fidelity (presence states + identifiers), corrupted-file handling, future-version refusal, `fixtures/projects/` compatibility *(40 tests: full `Configuration` round-trip incl. presence + every edit kind, AddRecord-with-modifications regression, 15+ refusal cases, fixtures with the legacy v0 file exercising the real upgrade path)*

**Exit criteria:** `load(save(p))` generates byte-identical output to `p`.

## Phase 10 — Application services
- [x] `ProjectService`, `ConfigurationService`, `ValidationService`, `VariantService`, `GenerationService` *(wired as a front end would: variants/validation/generation share the open-project owner; GenerationService takes its three collaborators explicitly)*
- [x] Generation sequence fixed in one place: validate base (stop on ERROR) → expand → validate variants incl. drift → transform → encode → plan; `execute` writes only what was reviewed *(the only place the 6-step order exists; §13.2 name agreement and §13.5 emitted-path rewrites go through `transform.with_*` helpers so wire vocabulary stays in transform; the manifest joins the plan as an ordinary planned file — same §13.3 action table via the shared `plan.decide_action` — and appears in the review surface with `variant_key=None`)*
- [x] Result objects, never raise for user-caused problems; no direct filesystem writes in `app` *(all filesystem access rides `output`/`persistence`; the Phase 4 boundary conversion confirmed e2e: a hand-built duplicate identifier surfaces as R-ENT-002 and blocks generation as data, not an exception)*
- [x] Tests: e2e service-level happy path + blocked path, no UI *(14 tests: full pipeline onto real temp dirs with manifest, byte-identical reruns, review-before-write, name/directory agreement, R-ENT-007-blocked path, empty expansion, not-open handling, spec CRUD/preview, save/open round trip, preflight policy toggle)*

**Exit criteria:** complete pipeline runs headlessly.

## Phase 11 — Terminal wizard

### 11a — Step machine + formatting (no terminal)
- [x] 14 steps with entry conditions, per-family field visibility, answers → service calls; jump-to-field from every `FieldPath` variant *(steps are pure values in `ui/steps/registry.py` over `WizardView`; answers become `ServiceCall` data the caller performs; `jump.py` maps every locator type the rules emit — an unmapped type raises, never a silent misjump)*
- [x] `present/`: registry-only labels, width-aware layout (80-col minimum, degraded below), sequence ruler with human numbering, finding formatting without internal names *(plus the wizard **string registry** `present/strings.py` for chrome wording — the meta-test's oracle; a real `Action.description` bug it exposed: actions displayed their domain-context label instead of their own wording)*
- [x] Tests: reachability, entry conditions, visibility, string-registry meta-test, "no terminal imports in `steps/`+`present/`" *(65 ui tests + `test_ui_purity.py`: no terminal library, no stream I/O, no environment consultation in steps/present; no transform/serialize/output/persistence imports anywhere in `ui`; every registry entry used, every fixed string registered)*

**Exit criteria:** whole workflow drivable programmatically; every finding resolves to a reachable prompt.

### 11b — Platform layer + plain renderer + input routes — **DONE** (686 tests)
- [x] `ui/render/platform.py` — the **only** module branching on `sys.platform` (`IS_WINDOWS` patchable; size/state-dir/editor candidates/VT/encoding); architecture test enforces the confinement
- [x] `PlainLineRenderer` stdlib-only and feature-complete (§16.3 headers, persistent hint, numbered findings with `t <n>` technical detail, honest repeat-until-valid on refusals, fresh-view advancement, `a advanced` = format-version pin, EOF ⇒ clean status-0 farewell); `NonInteractiveRenderer` (no TTY ⇒ never prompts, names missing inputs, exit 3 — hang guard, not batch mode)
- [x] Capability probe (`probe_capabilities`: TERM, NO_COLOR, TTY, width, optional package, Windows VT/encoding — all injectable), result logged with reasons at session start, overridable via `--plain`/`--ascii`/`--no-color`; `run_wizard` probes the *console's* streams, never the host's
- [x] Long-text routes: paste default, read-from-file, optional editor (offered only if one exists); **preserve-and-warn** on CRLF (`crlf_report`); echo received-content summary (size/shape, never content); `ScriptedConsole` is a chunk queue (menu script + `feed_multiline` paste); no silent repair ever
- [x] Session journal (`SessionJournal` atomic write, size cap, cleared on decline; `NullJournal` seam; state dir via `platform.state_directory`); resume offer shown and declinable; graceful save prompts (save-as path requested only when no path, saved-to echoed)
- [x] Tests: `tests/unit/ui/test_platform_and_probe.py` (probe matrix incl. legacy-VT degradation), `tests/unit/ui/test_render_routes.py` (route round-trips, CRLF preservation, per-line pair errors, journal atomicity/resume/clear), `tests/e2e/test_wizard_pipeline.py` (13 scripted full-workflow e2e through `build_services` onto real temp dirs: happy path to written files, factor-picker variant, byte-checked manifest, save/resume, blocked-and-stay, backward nav, EOF, guard status 3)

**Exit criteria MET:** full workflow on 3.9.18 with **no optional packages** (probe matrix pinned; plain renderer used without prompt_toolkit), Windows console (developed/host platform; `--plain` and VT-degradation paths tested), `TERM=dumb` (colour off, plain), and safely refused in batch (guard, exit 3, nothing started).

### 11c — Full-screen renderer — **DONE** (695 tests)
- [x] `prompt_toolkit`-based; identical questions/answers to plain **by construction**: the entire workflow loop was extracted into `ui/render/drive.py` (`StepDrive`) whose only variation points are the two primitives `write_line`/`ask`; `PlainLineRenderer` and `FullScreenRenderer` are thin adapters over the one shared drive. Path completion only on path fields (never suggests on non-path fields); input history; `available()` is the single importability decision the probe consults (lazy import — the guaranteed path never needs the package)
- [x] Degrade per probe: `optional_package=False` ⇒ plain; package vanishing between probe and renderer construction ⇒ session degrades to plain (never crashes); `TERM=dumb`/no-VT/narrow ⇒ plain, unchanged from 11b
- [x] Internal pager for the read-only inspector: technical finding detail pages via `prompt_toolkit.shortcuts.pager`, falling back to linear emission (content never cut) when no paging surface exists
- [x] Tests (`tests/unit/ui/test_fullscreen_renderer.py`): **transcript parity** (identical script through both renderers over fresh services ⇒ line-identical transcripts, except the probe line's renderer token, which §16.7 requires to name the selection), **output parity** (both runs' variant files + manifest byte-identical), probe selection matrix, post-probe degradation, registered missing-package wording (meta-test enforced), pager fallback, completion gating, `available()` vs reality

**Exit criteria MET:** same transcript as plain (pinned line-for-line, with only the probe log's renderer token differing); no behavioural difference (byte-identical output from both renderers).

## Phase 12 — Hardening and contract regression
- [ ] Optional external verification tier (Route A manual/dated observations → `golden/external/`; Route B local parser if ever available) — never a runtime dependency, never the only place a rule is checked
- [ ] Complete golden fixtures, all provenance-labelled (`external/` vs `project/`), meta-test asserts provenance declared
- [ ] Quick-start for the Windows-authoring → SFTP → Linux-execution transfer
- [ ] Full suite on 3.9.18 both platforms; cross-platform byte-identity + determinism re-runs

**Exit criteria:** every plan §24 "definition of done" item demonstrable; all architecture tests pass.

---

## Continuous cross-cutting invariants (architecture tests, keep green at all times)
- [ ] One dialect: `alphafold3` only — no Server-dialect converter exists anywhere
- [ ] Index bases never implicitly converted: modifications/bond residues 1-based, template indices 0-based (distinct types, property-tested no-arithmetic)
- [ ] Omitted ≠ null ≠ empty ≠ populated — in model, transformer, serializer, persistence
- [ ] No `CCD_` prefix on any modification code; ligand = exactly one of CCD/SMILES; `userCCD` xor `userCCDPath`; protein MSA pair both-or-neither
- [ ] Seeds: non-empty uint32; no invented uniqueness/sorting; fixed-10-seed set is an adjustable project policy only
- [ ] Wire field names only in `transform`; folds are the only `isinstance` sites; `Optional` banned on contract fields; only `identity` allocates IDs; only `output`/`persistence` (+validation's port) touch the filesystem; `ui` imports only `app` + traceability
- [ ] Every rule and mapping carries `spec_ref` + evidence status + `MAP-###` ids
