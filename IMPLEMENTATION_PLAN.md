# IMPLEMENTATION_PLAN

Greenfield architecture and implementation strategy for a guided configuration builder that
produces validated external input files.

**Inputs that govern this plan**

| Document | Role | How this plan uses it |
|---|---|---|
| `AUTHORITATIVE_SPEC.md` | External data contract | Source of every rule, field, cardinality, and validation requirement. Not reinterpreted here. |
| `DOMAIN_MAPPING.md` | Translation / debug layer | Source of `MAP-###` identifiers used for traceability and for UI-facing wording. |
| This document | Software blueprint | Modules, ownership, dependency direction, sequencing, tests. |

**Scope of this document.** It answers only: *how should a clean system be built so that it
reliably executes the contract?* It contains no external-domain research, no reinterpretation of
the contract, no audit of any prior implementation, and no migration steps. Where the contract is
silent, this plan records an explicit project decision rather than inventing external behaviour, and
where a fact belongs to the target deployment it records a verification item instead of guessing
(Section 22).

---

## 1. Objective

Build an application that a non-programmer can use to produce valid, reproducible external input
files, through one explicit pipeline:

```text
User Configuration        (UI intent)
      ↓
Canonical Internal Model  (normalized, immutable)
      ↓
Validation                (structural → relational → contract)
      ↓
Variant Generation        (base + declared edits → isolated variants)
      ↓
Transformation            (canonical → wire document)
      ↓
Serialization             (wire document → deterministic bytes)
      ↓
File Generation           (planned, deterministic writes + manifest)
      ↓
Verified Input Format     (a format observed to be accepted by the deployment)
```

The target at the bottom of that pipeline is an **observable external contract**, not an external
implementation. The deployed system is a black box: the builder is designed against the written
specification plus one dated observation of which input format that deployment accepts, and it never
requires access to the system's source, installation metadata, or release identity (Section 10.4).

Two stage orderings matter and are deliberate:

- **Validation precedes variant generation** for the base configuration, and runs **again per
  variant** after edits are applied. A variant is a first-class configuration, not a diff that
  escapes validation.
- **Transformation precedes serialization** and is a separate module. Transformation carries the
  contract mapping; serialization carries only encoding and determinism.

---

## 2. Authority and traceability rules

These rules exist to stop contract drift and domain leakage. They are testable (Section 18.7).

1. **Single authority.** Every responsibility in the Authority Map (Section 20) has exactly one
   owning module. No second implementation, not even a convenience helper.
2. **Contract citation.** Every validation rule and every wire-field mapping carries a citation to
   a section of `AUTHORITATIVE_SPEC.md` plus its evidence status
   (`CONFIRMED` / `DOCUMENTED` / `INFERRED` / `AMBIGUOUS` / `UNRESOLVED`).
3. **Evidence status drives severity.** `CONFIRMED` / `DOCUMENTED` contract rules may block
   generation. `INFERRED` and project-policy rules default to advisory and must be individually
   switchable. `UNRESOLVED` items must **never** be enforced as errors.
4. **Domain terminology is confined to two places:** the UI label registry (Section 3) and the
   rule/mapping metadata tables. Module names, class names, control flow, validation code,
   serializer internals, variant logic, and filesystem logic use neutral names.
5. **`MAP-###` identifiers are the cross-reference mechanism.** Every canonical model type and
   every wire field mapping declares its mapping IDs. The mapping table itself is **not** copied
   into the codebase or into this plan; it stays in `DOMAIN_MAPPING.md`.
6. **Semantic distinctions survive to the wire.** Omitted, null, empty, and populated are four
   different states and are never collapsed (spec §6.2, §6.3, MAP-601..606). Index bases are never
   converted implicitly (spec §7, MAP-701..705).

### 2.1 Reconciling neutral naming with spec §20

`AUTHORITATIVE_SPEC.md` §20 warns against generic "data family" placeholders. Its actual concern is
the collapsing of distinct families into one loose container that loses field-level distinctions.
This plan satisfies that concern structurally: each family is a **separate type with only the
fields the contract allows for it** (Section 7.4). Neutrality is applied to *labels*, and
traceability is restored by the mandatory registry in Section 3 plus `MAP-###` annotations on every
type. No family shares a field that the contract does not grant it.

### 2.2 Two kinds of evidence, kept apart

The plan relies on two independent evidence sources, and conflating them would be a correctness
problem, so they are labelled differently everywhere:

| | Specification evidence | Deployment evidence |
|---|---|---|
| Source | `AUTHORITATIVE_SPEC.md`, with its own status vocabulary | Observed behaviour of the actual deployed external system |
| Answers | what fields exist, what values are legal, what relationships must hold | one question only: which input format that deployment accepts |
| Recorded in | `validation/catalogue.py`, as `spec_ref` + `evidence` per rule | `docs/CONTRACT_PIN.md`, as a dated observation (Section 22.4) |
| Obtained by | reading the specification | submitting a minimal valid input through the normal execution path and observing acceptance |
| If unavailable | the rule is not written; the item stays unresolved and never becomes an error | generation is blocked until an observation exists (Section 10.3) |

The external system is a black box (Section 10.4): its internal implementation and release identity are
**not** evidence sources for this architecture, and nothing in the design may depend on reading them.

---

## 3. Naming and traceability registry

This table is the single translation point between neutral internal names, mapping IDs, and
human-facing UI wording. It is implemented as data in `configbuilder/model/traceability.py` and is
the only source the UI consults for labels.

| Internal type (neutral) | Family tag | Mapping ID | UI label (human-facing) |
|---|---|---|---|
| `Configuration` | — | MAP-001 | Job |
| `ConfigurationMetadata` | — | MAP-002 | Job details |
| `SeedSet` | — | MAP-003 | Reproducibility seeds |
| `Record` (protocol) | — | MAP-004 | Molecule |
| `FamilyARecord` | DataFamilyA | MAP-005 | Protein chain |
| `FamilyBRecord` | DataFamilyB | MAP-006 | RNA chain |
| `FamilyCRecord` | DataFamilyC | MAP-007 | DNA strand |
| `ComponentRecord` | ComponentFamilyA | MAP-008 | Ligand or ion |
| `ModificationRecord` | ModificationFamilyA | MAP-009 | Chemical modification |
| `AlignmentSource` | — | MAP-010 | Sequence alignment source |
| `ReferenceRecord` | — | MAP-011 | Structural reference |
| `ComponentDefinitionSource` | — | MAP-012 | Custom chemistry definition |
| `Linkage` | — | MAP-013 | Covalent link |
| `Variant` | — | MAP-014 | Variant |
| `VariantManifest` | — | MAP-015 | Variant report |
| `OutputReference` | — | MAP-016 | Result location |

Field-level mappings (MAP-101..108, MAP-201..211, MAP-301..308, MAP-351..356, MAP-401..406,
MAP-501..506, MAP-601..606, MAP-701..705, MAP-801..807, MAP-901..908, MAP-1001..1006) are declared
in the transformation field tables (Section 10.2), each row carrying its mapping ID. They are
referenced, not duplicated.

### 3.1 UI label rule

The UI must resolve every label, option name, help text, and error phrase through this registry or
through a rule's `user_message`. Raw internal names, wire field names, JSON fragments, internal
identifiers, and index bases must never appear in the default UI surface. One read-only advanced
inspector (Section 16.11) is the single exception.

---

## 4. Technology decisions

Decisions not derivable from the contract; recorded here with rationale so a coding agent does not
have to re-litigate them.

| Decision | Choice | Rationale |
|---|---|---|
| Language | **Python 3.9.18** | This is the established project baseline. Every language feature, standard-library API, and dependency version named in this plan must work on 3.9.18. Section 4.1 lists the consequences that actually constrain the design. |
| Model representation | Frozen dataclasses plus sum types expressed as small sealed class families, each with one central fold function (Section 4.1) | Immutability is the mechanism that guarantees variant isolation (Section 12.4). Structural pattern matching is unavailable on 3.9, so dispatch is explicit and centralized rather than scattered. |
| Encoding | stdlib `json` with pinned separators and key order | Determinism must not depend on a third-party serializer. |
| Core dependencies | **None beyond the standard library** | The core builder — model, identity, validation, transform, serialize, variants, output, persistence, app, and the plain-line wizard — runs on a bare Python 3.9.18 installation. This is what keeps the application usable on a machine where installing packages is awkward. |
| Optional dependencies | `prompt_toolkit` (full-screen renderer), a chemistry-notation parser (stronger notation validation), the external system's own parser (extra contract test tier) | Each is strictly additive. Absence changes convenience or validation strength, never capability. Each is wired through a port with a documented fallback (Sections 9.6, 16.7, 18.5). |
| UI | Terminal wizard. The stdlib-only plain-line renderer is the guaranteed path; a full-screen renderer is enabled when `prompt_toolkit` is present | There is no display and no browser. The workflow must complete on a plain terminal with no third-party packages installed. Section 16 specifies the design. |
| Host platforms | **Windows for authoring, Linux for execution**, with both supported for running the builder | Section 4.2 states the workflow. Platform differences are confined to one module (Section 16.10) and generated output is byte-identical on both (Section 11). CI runs the suite on both. |
| Tests | `pytest` + `hypothesis`, pinned to versions supporting Python 3.9 | Table-driven contract tests plus property-based tests for determinism and isolation. Development-only; not required to run the application. |
| Long text entry | Paste and read-from-file as primary routes; an external-editor handoff as an optional convenience | Users paste into the terminal and move files by SFTP; both are reliable in practice. The editor route is offered only when an editor is actually available (Section 16.5). |
| Packaging | `pyproject.toml`, single distribution `configbuilder`, one console entry point. Distribution format deferred | A normal Python environment on 3.9.18 is the assumption. Packaging is addressed after the core system is stable and must not shape the architecture. |

No network calls are made by the application. The builder reads and writes local files only. It
requires no display server, no root privileges, no compiled extensions, and no third-party package to
complete its workflow.

### 4.1 Python 3.9.18 consequences

These are the constraints that actually affect the design, and the decision taken for each.

| 3.10+ feature not available | Decision for this plan |
|---|---|
| `match` / structural pattern matching | Each sum type gets exactly one `fold_*` function in `model/` containing the only `isinstance` chain for that type. Every consumer calls the fold rather than testing types itself. A test asserts each fold handles every declared case and raises on an unknown one, which replaces the exhaustiveness checking a `match` statement would have given. |
| `@dataclass(slots=True)` | Plain `@dataclass(frozen=True)`. `__slots__` is declared by hand only if profiling shows a need. Immutability, not slots, is what the architecture depends on. |
| `X \| Y` union syntax | `typing.Union` and `typing.Optional` in annotations. The ban on `Optional` for contract-bearing model fields (Section 7.3) is unchanged and unrelated. |
| `typing.TypeAlias`, `assert_never` | Plain module-level aliases; the fold's final `raise` plus its coverage test serve the same purpose as `assert_never`. |
| `tomllib` | Not needed. Project files are JSON (Section 14); packaging metadata is read by the build tool, not by the application. |
| Exception groups | Not needed. Validation collects findings in a report rather than raising. |

Available on 3.9 and used freely: built-in generic annotations (`tuple[X, ...]`, `dict[str, int]`),
`functools.cache`, `str.removeprefix`/`removesuffix`, dictionary merge operators, `graphlib`,
`pathlib`, `os.replace`, `dataclasses`, `typing.Protocol`, `typing.Literal`.

A CI job runs the full suite on Python 3.9.18 specifically, and the packaging metadata declares
`requires-python = ">=3.9"`, so a 3.10-only construct fails the build rather than reaching a user.

### 4.2 Authoring and execution are different machines

The expected workflow crosses a machine boundary:

```text
Windows authoring machine
        ↓  run the builder, validate, create variants, generate
Generated files + manifest
        ↓  transfer (SFTP)
University Linux system
        ↓
External execution
```

This is the normal case, not an edge case. It drives four decisions stated in full elsewhere and
listed here so they are not treated as incidental:

1. Generated files are byte-identical regardless of the platform they were produced on (Section 11).
2. Emitted resource paths favour portable, output-relative forms; the default path policy produces a
   self-contained, transferable output directory (Section 13.5).
3. A path that cannot resolve on the execution host is reported to the user at authoring time
   (Section 13.5).
4. The builder is an authoring application. It does not need to run on the execution system, and the
   architecture does not depend on holding an interactive session open there (Section 16.0).

---

## 5. System overview

### 5.1 Module map

```text
configbuilder/
  model/          canonical internal model, value types, presence algebra, traceability registry
  identity/       identifier allocation, uniqueness, reference resolution
  validation/     rule catalogue, engine, findings, report
  transform/      canonical model → wire document (contract mapping, version selection)
  serialize/      wire document → deterministic bytes (single encoding authority)
  variants/       edit vocabulary, variant specs, generator, lineage
  output/         naming, output plan, atomic writer, manifest
  persistence/    project file save/load, schema versioning, load-time validation
  app/            application services (use cases) consumed by any front end
  ui/             terminal wizard: pure step machine + interchangeable renderers
    steps/        step definitions, entry conditions, field visibility (no IO)
    render/       renderers: full-screen, plain-line, non-interactive
    present/      label resolution, finding formatting, width-aware layout
tests/
  unit/ contract/ golden/ negative/ variant/ serialization/ e2e/ architecture/
fixtures/
  golden/ invalid/ projects/
```

Ten modules. Additional modules require a justification entry in this document.

### 5.2 Stage ownership

| Pipeline stage | Owning module | Produces |
|---|---|---|
| User intent capture | `ui` | service calls only |
| Use-case orchestration | `app` | result objects |
| Canonical representation | `model` | `Configuration` |
| Identifier/reference integrity | `identity` | `IdentityRegistry` |
| Validation | `validation` | `ValidationReport` |
| Variant expansion | `variants` | `Variant[]` |
| Contract mapping | `transform` | `WireDocument` |
| Encoding | `serialize` | `bytes` |
| Planning + writing | `output` | `OutputPlan`, files, manifest |
| Project save/load | `persistence` | project file |

### 5.3 Dependency rules

```text
ui
 ↓
app
 ↓
variants ─┐
validation ├→ model → identity
transform ─┘
 ↓
serialize
 ↓
output
 ↓
filesystem
```

Enforced rules:

1. `model` and `identity` import nothing from other project modules (`identity` is imported **by**
   `model` for identifier value types only).
2. `validation`, `transform`, `variants` depend on `model` and on each other **not at all**.
3. `serialize` depends on `transform`'s `WireDocument` type only. It contains no contract logic.
4. `output` depends on `serialize` and on naming inputs. It contains no contract logic and no
   validation.
5. `app` is the only module allowed to depend on `validation` + `variants` + `transform` +
   `serialize` + `output` + `persistence` together.
6. `ui` imports `app` and `model.traceability` only. It must not import `transform`, `serialize`,
   `output`, or `persistence`.
7. No module imports `ui`. No module imports `app` except `ui`.
8. Filesystem access is confined to `output`, `persistence`, and the path-reading adapters in
   `validation` (preflight existence checks, Section 9.5). No other module touches the filesystem.
9. Inside `ui`, the direction is `render → steps → present`. `ui/steps/` and `ui/present/` must not
   import any terminal library, must not read or write a stream, and must not consult the
   environment. Only `ui/render/` may do those things. This is what keeps the entire workflow
   testable without a terminal, and it is asserted in `tests/architecture/`.

Deviation from the default layering: `validation` performs optional filesystem reads. Justification:
the contract permits external file references (spec §10) and a preflight existence check is a
recognised builder policy; isolating it in one advisory rule group with an injectable filesystem
port keeps the rest of validation pure and testable.

`tests/architecture/` asserts rules 1–9 by scanning imports, so violations fail CI rather than
accumulating.
---

## 6. Module specifications

Each entry states purpose, responsibilities, explicit non-responsibilities, inputs, outputs,
dependencies, public interface, and tests.

### 6.1 `model`

- **Purpose.** The one canonical internal representation of user intent.
- **Responsibilities.** Entity and value types; presence algebra; structural invariants that can be
  made unrepresentable; the traceability registry; deterministic equality and hashing; cloning
  semantics (free, via immutability).
- **Non-responsibilities.** Validation messages, wire field names, JSON, file IO, identifier
  allocation policy, UI labels beyond the registry data.
- **Inputs.** Primitive values from `app`.
- **Outputs.** `Configuration` and its parts.
- **Dependencies.** `identity` (value types only).
- **Public interface.** Constructors and `with_*` derivation helpers for every type;
  `traceability.registry`.
- **Tests.** `unit/model/` — invariant construction, presence algebra, equality/hash stability,
  registry completeness (every type has a mapping ID and a UI label).

### 6.2 `identity`

- **Purpose.** The sole authority for identifiers and reference integrity.
- **Responsibilities.** Allocation, uniqueness, collision detection, format compliance, reference
  resolution, reference rewriting on rename, deterministic ordering, registry cloning.
- **Non-responsibilities.** Deciding *whether* an identifier is contractually required (that is a
  validation rule), serialization form, UI display.
- **Inputs.** Allocation requests, rename requests, reference lookups.
- **Outputs.** `EntityId` values, `IdentityRegistry` snapshots, resolution results.
- **Dependencies.** None.
- **Public interface.** `EntityId`, `IdentityRegistry`, `IdAllocator`.
- **Tests.** `unit/identity/` — allocation sequence determinism, overflow past the single-character
  range, collision rejection, reference rewrite completeness, clone independence.

### 6.3 `validation`

- **Purpose.** The sole authority for deciding whether a configuration may be generated.
- **Responsibilities.** Rule catalogue with contract citations; four rule tiers; engine execution
  order; `Finding` construction with field locators; user message vs diagnostic separation;
  severity policy resolution.
- **Non-responsibilities.** Mutating or repairing the model; producing wire output; deciding UI
  presentation; enforcing anything the contract leaves unresolved.
- **Inputs.** `Configuration` or `Variant`, a `ValidationPolicy`, an optional filesystem port, an
  optional chemistry probe.
- **Outputs.** `ValidationReport`.
- **Dependencies.** `model`.
- **Public interface.** `validate(configuration, policy, ports) -> ValidationReport`; `RULES`.
- **Tests.** `contract/`, `negative/`, plus `unit/validation/` for engine mechanics.

### 6.4 `transform`

- **Purpose.** The sole authority for mapping canonical concepts onto contract fields.
- **Responsibilities.** Field name mapping; presence-state → field presence/absence; index-base
  handling; representation selection (inline vs external, and mutually exclusive alternatives);
  format-version selection; ordering of collections; emitting the list of external resources the
  output depends on.
- **Non-responsibilities.** Encoding, byte layout, file IO, validation, identifier allocation.
- **Inputs.** A validated `Configuration`.
- **Outputs.** `WireDocument` (an ordered, JSON-ready structure) and `ExternalResourceRequirement[]`.
- **Dependencies.** `model`.
- **Public interface.** `to_wire(configuration, version_policy) -> TransformResult`.
- **Tests.** `unit/transform/` field-mapping tables; `contract/` version-selection rules.

### 6.5 `serialize`

- **Purpose.** The sole encoding authority.
- **Responsibilities.** `WireDocument` → deterministic UTF-8 bytes; separator/indent policy; escape
  policy; trailing newline; stable key order as given by `transform`.
- **Non-responsibilities.** Any decision about *what* is in the document.
- **Inputs.** `WireDocument`.
- **Outputs.** `bytes`.
- **Dependencies.** `transform` (type only).
- **Public interface.** `encode(wire_document) -> bytes`.
- **Tests.** `serialization/` — byte determinism across repeated runs and process restarts, escape
  handling, ordering stability.

### 6.6 `variants`

- **Purpose.** Express and expand a family of related configurations from one base.
- **Responsibilities.** The typed edit vocabulary; `VariantSpec` composition; deterministic
  expansion; lineage records; slug generation input; isolation guarantees.
- **Non-responsibilities.** Validating results (delegated to `validation` by `app`), naming files,
  serializing.
- **Inputs.** Base `Configuration`, `VariantSpec[]`.
- **Outputs.** `Variant[]` with lineage.
- **Dependencies.** `model`.
- **Public interface.** `Edit` types, `VariantSpec`, `expand(base, specs) -> tuple[Variant, ...]`.
- **Tests.** `variant/` — isolation, determinism, lineage correctness, edit replay.

### 6.7 `output`

- **Purpose.** Deterministic, predictable artefact layout on disk.
- **Responsibilities.** Slug and filename derivation; collision detection; `OutputPlan`
  construction; overwrite policy application; atomic writes; external-resource path normalization;
  manifest construction.
- **Non-responsibilities.** Contract rules, validation, transformation, encoding.
- **Inputs.** `Variant[]`, encoded bytes, `OutputSettings`.
- **Outputs.** `OutputPlan`, written files, manifest.
- **Dependencies.** `serialize`.
- **Public interface.** `plan(...) -> OutputPlan`; `execute(plan) -> OutputResult`.
- **Tests.** `unit/output/` planning and collision logic against a fake filesystem; `e2e/` for real
  writes into a temporary directory.

### 6.8 `persistence`

- **Purpose.** Save and reopen the user's project.
- **Responsibilities.** Project file schema and its own `schema_version`; save; load with
  validation; forward-compatibility refusal; clear separation from generated output.
- **Non-responsibilities.** Producing external input files; validating the external contract.
- **Inputs.** `Project` (base configuration + variant specs + settings).
- **Outputs.** Project file; loaded `Project`.
- **Dependencies.** `model`, `variants` (edit types), `identity`.
- **Public interface.** `save(project, path)`, `load(path) -> LoadResult`.
- **Tests.** `unit/persistence/` round-trip fidelity, unknown-version refusal, corrupted-file
  handling; `fixtures/projects/` compatibility fixtures.

### 6.9 `app`

- **Purpose.** Use-case orchestration; the only API any front end needs.
- **Responsibilities.** Compose the pipeline in the correct order; return result objects; never
  raise for user-caused problems; own the transactional boundary of a generation run.
- **Non-responsibilities.** Contract rules, encoding, presentation behaviour, direct filesystem
  writes.
- **Inputs.** Service commands from `ui`.
- **Outputs.** Result objects carrying findings, plans, and summaries.
- **Dependencies.** All non-`ui` modules.
- **Public interface.** `ConfigurationService`, `ValidationService`, `VariantService`,
  `GenerationService`, `ProjectService`.
- **Tests.** `e2e/` service-level workflows without any UI.

### 6.10 `ui`

- **Purpose.** Guide a non-programmer through valid states from a terminal, including over SSH on a
  shared system.
- **Responsibilities.** The step machine (which step is reachable, which fields are visible, what a
  step asks for); label resolution through the registry; width-aware formatting of prompts, tables,
  and findings; renderer selection based on terminal capability; long-text entry handoff; session
  resume.
- **Non-responsibilities.** Constructing wire documents, encoding, writing generated files, embedding
  contract rules, allocating identifiers, computing indices, deciding validation severity.
- **Inputs.** Keyboard input; terminal capability probe; environment variables (`TERM`, `NO_COLOR`,
  `COLUMNS`, `LINES`, `VISUAL`, `EDITOR`).
- **Outputs.** Service calls; rendered text to the output stream.
- **Dependencies.** `app`, `model.traceability`.
- **Internal structure.** Three parts with a hard boundary between them:
  - `steps/` — a pure state machine over a read-only view of the project plus the latest report.
    Given a state and an answer, it returns the next state and the service calls to make. No IO, no
    terminal, no `prompt_toolkit` import.
  - `render/` — renderers that draw a step and collect one answer. Interchangeable by construction:
    `FullScreenRenderer`, `PlainLineRenderer`, `NonInteractiveRenderer` (Section 16.7).
  - `present/` — pure formatting: label lookup, finding text, table layout for a given width,
    sequence rendering with position rulers.
- **Tests.** The step machine and `present/` are pure and unit-tested directly. Renderers are tested
  through a scripted-input harness and a pseudo-terminal (Section 18.8). Escape-sequence output is
  snapshot-tested only for the plain-line renderer, where it is stable.

---

## 7. Canonical internal model

### 7.1 Why a canonical model distinct from the wire structure

The external contract encodes several concepts in forms that are lossy or error-prone as an
in-memory representation:

- One concept is spread across mutually exclusive field pairs (inline vs external path) — spec §6.1.
- Meaning depends on the difference between omitted, null, empty, and populated — spec §6.2.
- Two different index bases coexist in the same document — spec §7.2–§7.4.
- Parallel arrays encode a single pairwise mapping — spec §7.3, §12.
- A collection field carries an identity-plus-multiplicity meaning — spec §7.1.

A direct in-memory copy of the wire structure would therefore make invalid states easy to construct
and hard to detect. The canonical model instead makes invalid states unrepresentable where possible
and defers the wire shape to `transform`.

### 7.2 Value types

```text
EntityId            immutable identifier value; format enforced at construction   [MAP-901]
Multiplicity        one or more EntityId, ordered, deduplicated                   [MAP-901/902]
Position            1-based polymer position; a distinct type from IndexPair      [MAP-903]
ResidueRef          1-based reference used by linkages                            [MAP-904]
IndexPair           one (query_index, reference_index) pair, both 0-based         [MAP-905/906]
Seed                integer constrained to the contract's numeric range           [MAP-907]
SequenceText        polymer sequence text, family-constrained alphabet            [MAP-202/302/352]
ComponentCode       component code value; rejects the prefix the contract forbids [MAP-204/304/354]
ResourceRef         Inline(text) | External(PathSpec)                             [MAP-1001..1006]
PathSpec            raw user path + normalization metadata                        [MAP-1001..1005]
```

`Position` and `IndexPair` are distinct nominal types specifically so that a 1-based value can never
be passed where a 0-based value is expected. This is the architectural mitigation for the mixed
index-base risk called out in `DOMAIN_MAPPING.md` §10.

### 7.3 Presence algebra

The contract distinguishes four states for several optional fields (spec §6.2, §6.3,
MAP-601..606). One shared algebra expresses them:

```text
Presence[T] =
    Unset                  field is omitted from the wire document entirely
  | ExplicitEmpty          field is present with the contract's empty value
  | Present(value: T)      field is present with content
```

Rules:

- `Unset` and `ExplicitEmpty` are never interchangeable, in the model, in the transformer, in the
  serializer, or in persistence.
- `None` is never used to mean either of them. `Optional[...]` is banned for contract-bearing
  optional fields; a lint test in `tests/architecture/` enforces this on model dataclasses.

Where two optional fields form a contractual pair or an exclusive choice, the algebra is replaced by
a purpose-built sum type so the invariant is structural rather than validated after the fact:

```text
AlignmentPairing =                    # DataFamilyA, MAP-601..606
    Automatic                         # neither field emitted
  | Free                              # both emitted empty
  | UnpairedOnly(source)              # one populated, the other emitted empty
  | PairedOnly(source)                # inverse; contract marks this an expert case
  | Both(unpaired, paired)

SingleAlignment =                     # DataFamilyB, MAP-601/604/606
    Automatic | Free | Provided(source)

ReferenceSet =                        # MAP-705
    SearchAllowed                     # field omitted
  | Explicit(items: tuple[ReferenceRecord, ...])   # empty tuple = explicitly none

ComponentRepresentation =             # MAP-406
    ByCode(codes: tuple[ComponentCode, ...])
  | ByNotation(text: str)

ComponentDefinitionSource = ResourceRef            # MAP-012, exclusive by construction
```

`AlignmentPairing` is the architectural answer to the contract's "both set or both unset" rule
(spec §11): the illegal half-set combination cannot be instantiated. `ReferenceSet.Explicit(())`
is the architectural answer to "empty list means explicitly none" (spec §6.2).

Each case is a frozen dataclass deriving from a common base that exists only to mark the family.
Because structural pattern matching is unavailable on the Python baseline (Section 4.1), every sum
type ships **one** fold function beside it:

```text
fold_presence(value, on_unset, on_empty, on_present)
fold_alignment(value, on_automatic, on_free, on_unpaired_only, on_paired_only, on_both)
fold_single_alignment(value, on_automatic, on_free, on_provided)
fold_reference_set(value, on_search_allowed, on_explicit)
fold_representation(value, on_code, on_notation)
fold_resource(value, on_inline, on_external)
```

Rules that make this equivalent in safety to a checked `match`:

- The fold is the only place an `isinstance` test on that family may appear. `validation`,
  `transform`, `variants`, and `persistence` call the fold and supply a handler per case, so adding a
  case breaks every call site loudly instead of falling through a silent default.
- Each fold ends with a `raise` on an unrecognised case.
- A test per fold asserts it accepts every declared case and raises on an unknown one, and an
  architecture test asserts no `isinstance` check against these families exists outside `model/`.

This matters most for the presence algebra: a fallthrough branch there would be exactly the
omitted-versus-empty collapse the contract forbids (spec §6.3).

### 7.4 Record families

Families are separate types carrying only the fields the contract grants them. No shared base class
adds capability; a minimal `Record` protocol supplies identity and descriptive metadata only.

```text
Record (protocol)                                            [MAP-004]
    ids: Multiplicity
    description: Presence[str]                               [MAP-206/306/356/404]

FamilyARecord(Record)                                        [MAP-005]
    sequence: SequenceText
    modifications: tuple[ModificationRecord, ...]            [MAP-203]
    alignment: AlignmentPairing                               [MAP-207..210]
    references: ReferenceSet                                  [MAP-211]

FamilyBRecord(Record)                                        [MAP-006]
    sequence: SequenceText
    modifications: tuple[ModificationRecord, ...]             [MAP-303]
    alignment: SingleAlignment                                [MAP-307/308]

FamilyCRecord(Record)                                        [MAP-007]
    sequence: SequenceText
    modifications: tuple[ModificationRecord, ...]             [MAP-353]
    # deliberately has no alignment and no reference fields   [DOMAIN_MAPPING §6 note]

ComponentRecord(Record)                                       [MAP-008]
    representation: ComponentRepresentation                   [MAP-402/403/405/406]

ModificationRecord                                            [MAP-009]
    code: ComponentCode                                       [MAP-502]
    position: Position                                        [MAP-503]
    # base identity is read from the parent sequence, never stored here [MAP-501]

ReferenceRecord                                               [MAP-011]
    source: ResourceRef                                       [MAP-701/702]
    index_map: tuple[IndexPair, ...]                           [MAP-703/704]

Linkage                                                       [MAP-013]
    a: LinkEndpoint
    b: LinkEndpoint
LinkEndpoint
    entity: EntityId                                          [MAP-801/804]
    residue: ResidueRef                                       [MAP-802/805]
    atom: str                                                 [MAP-803/806]
```

Three deliberate modelling choices:

1. `FamilyCRecord` has no alignment field at all. The contract grants none, so the type cannot carry
   one, which structurally prevents the field-reuse bug named in `DOMAIN_MAPPING.md` §6.
2. `ModificationRecord` stores code and position only. Base identity stays in the parent sequence,
   keeping the four concepts the mapping document warns about (§8) separate by construction.
3. `ReferenceRecord.index_map` stores pairs, not two parallel arrays. Equal length is therefore
   guaranteed by the data structure, and `transform` splits the pairs at the wire boundary.

### 7.5 Root aggregate

```text
Configuration                                                 [MAP-001]
    metadata: ConfigurationMetadata                           [MAP-002]
    seeds: SeedSet                                            [MAP-003]
    records: tuple[Record, ...]                               [MAP-103]
    linkages: tuple[Linkage, ...]                             [MAP-104]
    component_definition: Presence[ComponentDefinitionSource]  [MAP-105/106]
    identity: IdentityRegistry
    format_target: FormatTarget                                [MAP-107/108]

ConfigurationMetadata
    name: str                                                  [MAP-101]

FormatTarget
    dialect: Dialect                     # single supported value; see §7.7
    version: VersionSelection            # Unverified | Pinned(int) | Auto(evidenced_set); see §10.3
```

Ownership and relationships (mirroring MAP-1201..1212):

| Relationship | Cardinality | Owner |
|---|---|---|
| `Configuration` → records | 1 → many | Configuration owns records by value |
| `Configuration` → seeds | 1 → many, non-empty | Configuration |
| `Configuration` → component definition | 1 → 0..1 | Configuration |
| record → modifications | 1 → 0..many | the record |
| `FamilyARecord` → references | 1 → 0..many | the record |
| `Configuration` → linkages | 1 → 0..many | Configuration; endpoints *reference* records by `EntityId` |
| `Variant` → base | many → 1 | `variants` module |

Linkages are the only cross-record reference and are stored at the root rather than on a record,
because an endpoint pair may span two records and must have exactly one owner.

### 7.6 Mutability, defaults, lifecycle

- Every model type is frozen. Editing produces a new object through `with_*` helpers.
- Defaults are minimal and never invent contract behaviour: optional contract fields default to
  `Unset` (omitted), alignment defaults to `Automatic`, references default to `SearchAllowed`, and
  version selection defaults to `Unverified` — which blocks generation until a format has been observed
  to be accepted by the deployment and recorded (Section 10.3). The builder never guesses a format
  version.
- A `Configuration` has no internal validation flag. Validation state is a separate artefact
  (`ValidationReport`) held by `app`, so a stale "valid" bit can never travel with the data.
- Lifecycle: `draft` (under edit in `app`) → `report` attached → `variant expansion` → `generated`.
  Only `app` tracks the phase; the model stays a plain value.

### 7.7 Format target

`Dialect` is an enumeration with one member, the dialect the contract requires (spec §4, §17). It is
an enumeration rather than a literal so that the second, incompatible external dialect described in
spec §17 can never be produced by accident, and so that a rule can assert the value explicitly.
The builder targets exactly one dialect at the serialization boundary; no converter is implemented.
---

## 8. Identifier and reference authority

One module, `identity`, answers every identifier question. No other module generates, formats, or
mutates an identifier.

| Question | Answer |
|---|---|
| Who creates identifiers? | `IdAllocator`, only through `IdentityRegistry.allocate()`. |
| Who owns them? | The `IdentityRegistry` held by the `Configuration`. |
| Who validates them? | `EntityId` validates format at construction; the registry validates uniqueness; a contract rule in `validation` asserts both independently so a bypass is still caught. |
| Who resolves references? | `IdentityRegistry.resolve(entity_id)`; linkage endpoints and any future reference resolve only through it. |
| Who updates references? | `IdentityRegistry.rename(old, new)` returns a rewrite map; `app` applies it to the configuration in one operation. A rename never happens outside this path. |
| How are collisions handled? | Allocation skips taken identifiers; explicit user assignment of a taken identifier is refused with a finding, never silently renamed. |
| How is determinism maintained? | Allocation is a pure function of the ordered set of already-assigned identifiers. No randomness, no clock, no hash-order dependence. |

### 8.1 Allocation policy

**Decision: deterministic monotonic allocation.** `IdAllocator` hands out the next unused identifier
in a fixed monotonic progression that satisfies the contract's format constraint (spec §7.1) and
continues past the single-character range, because the contract explicitly does not impose a
26-identifier ceiling (spec §7.6).

Guarantees, which are the part that matters architecturally:

- **Unique** within a configuration, including across copy multiplicity.
- **Deterministic**: the same sequence of allocation requests against the same starting state always
  yields the same identifiers. No randomness, no clock, no hash-order dependence.
- **Collision-free**: taken identifiers are skipped; an explicit user assignment of a taken identifier
  is refused with a finding rather than silently renamed.
- **Stable across variant creation**: cloning preserves identifiers (Section 8.3).
- **Isolated**: the progression itself is an implementation detail of `IdAllocator`. No other module
  may depend on its shape, and no test outside `unit/identity/` asserts a specific identifier value.

The specification does not mandate a particular progression, so none is elevated to a contract rule
here. Should it ever do so, the change is confined to this one class.

### 8.1.1 Ordering carries no meaning

Identifier order is **not** semantically meaningful and nothing may treat it as such. Determinism
exists for reproducibility and for comparing variants, not to encode priority, sequence, or any
relationship between records. Specifically:

- No rule, transformer, or output-naming decision may infer anything from the relative order of two
  identifiers.
- No downstream ordering dependency is introduced. The specification does not establish one, and
  Section 19 keeps the builder's commitments to what the manifest records.
- Record order within the configuration is preserved for the user's benefit and serialized as given,
  but that is collection order, not identifier semantics.

### 8.2 Multiplicity

Copy multiplicity is expressed as an ordered `Multiplicity` of allocated identifiers on a single
record (MAP-902), not as duplicated records. The registry reserves every identifier in the
multiplicity, so uniqueness holds across copies as well as across records.

### 8.3 Behaviour under copy and variant expansion

- Copying a configuration clones the registry wholesale. Identifiers are **preserved**, not
  reallocated, so a variant is comparable to its base.
- An edit that adds a record allocates from the variant's own cloned registry.
- An edit that removes a record releases its identifiers in that variant only; released identifiers
  are not reused within the same expansion run, so ordering differences cannot silently reshuffle
  identifiers between variants.
- Any edit that would change an existing identifier is flagged by the variant manifest as
  identity-affecting, because the contract makes identifiers visible in downstream artefacts
  (spec §7.1, §16).

---

## 9. Validation architecture

### 9.1 Shape

```text
validation/
  catalogue.py    the rule table: id, tier, severity policy, spec citation, mapping ids, messages
  rules/          rule implementations grouped by tier
  engine.py       ordered execution, short-circuit policy, report assembly
  report.py       Finding, FieldPath, ValidationReport, severity
  ports.py        FilesystemPort, ChemistryProbe protocols
```

Every rule is a small object with a stable identifier:

```text
Rule
    rule_id: str                 e.g. "R-ROOT-004"
    tier: Tier                   STRUCTURAL | RELATIONAL | CONTRACT | VARIANT | PREFLIGHT
    default_severity: Severity   ERROR | WARNING | INFO
    spec_ref: str                section of AUTHORITATIVE_SPEC.md
    evidence: Evidence           CONFIRMED | DOCUMENTED | INFERRED | AMBIGUOUS | UNRESOLVED
    mapping_ids: tuple[str, ...]
    check(subject, ports) -> Iterable[Finding]
```

### 9.2 Tiers and execution order

| Tier | Question | Examples (citations in the catalogue) |
|---|---|---|
| STRUCTURAL | Is this object well formed on its own? | required root fields present; non-empty name; seed range; sequence alphabet per family; modification position within sequence range; component code prefix constraint; exactly one component representation |
| RELATIONAL | Are references and cross-object rules consistent? | identifier uniqueness across records and copies; linkage endpoints resolve; linkage endpoint is addressable under the chosen representation; modification codes that require a custom definition have one |
| CONTRACT | Does the document satisfy the external contract as a whole? | dialect value; format version supports every feature used; mutually exclusive representation pairs; paired-alignment both-or-neither; reference count ceiling; reference index-map consistency; only permitted fields emitted for the selected version |
| VARIANT | Does the expanded variant still satisfy everything, and does it keep the intended factors stable? | every base rule re-run; unintended-drift check on fields the variant did not declare as edited; identity stability; seed-set stability |
| PREFLIGHT | Shallow, local, low-false-positive checks the contract permits but does not require | referenced path is syntactically valid; the resource exists and is readable; it is not empty; it will resolve on the execution host; an explicitly documented file requirement is met; component notation parses, when a probe is available |

Order: STRUCTURAL → RELATIONAL → CONTRACT → (VARIANT) → PREFLIGHT. A tier runs even if an earlier
tier produced findings, unless a finding makes the subject unreadable for a later tier; in that case
the later rule reports `skipped` rather than a false pass. The report records skips explicitly so a
green result can never hide an unevaluated rule.

**Preflight is deliberately shallow.** The builder checks what can be established cheaply and locally:
does the path make sense, is the resource there, can it be read, is it non-empty, will the emitted
path work where the file will be consumed. It does **not** attempt to re-implement the external
system's parsing or semantic processing of resource contents — no alignment-geometry reconstruction, no
structural-file interpretation, no chemistry re-derivation. Two reasons, both architectural: a partial
reimplementation would be a second authority for rules the external system owns, and a deep local
checker on user-supplied scientific data produces false positives, which train users to ignore
findings. Anything deeper belongs to the optional verification tier (Section 18.5), never to a default
rule. Preflight defaults to `WARNING` and the whole tier can be switched off by policy while a user is
still assembling resources.

### 9.3 Severity policy

`ValidationPolicy` resolves each rule's effective severity. Constraints, enforced by a test over the
catalogue:

- `CONFIRMED` / `DOCUMENTED` contract rules: `ERROR`, not downgradable.
- `INFERRED` and project-policy rules: default `WARNING`, user-adjustable up to `ERROR`.
- `UNRESOLVED` subjects: may only produce `INFO`. The catalogue explicitly lists the items spec §19
  declines to promote (seed uniqueness, seed ordering, identifier-allocation algorithm, fixed seed
  count, biological plausibility, downstream-analysis rules) as `INFO`-only, so no future change can
  silently turn a non-rule into a gate.

Generation is permitted when no `ERROR` finding is open. `WARNING` requires explicit user
acknowledgement in the review step. `INFO` is informational.

### 9.4 Findings and locators

```text
FieldPath        typed locator: root | record(index) | record.field | modification(index).field |
                 reference(index).field | linkage(index).endpoint.field
Finding
    rule_id, severity, path: FieldPath
    user_message: str        registry-resolved wording, no internal names, no wire field names
    diagnostic: str          rule id, spec ref, evidence status, mapping ids, observed value
    suggestion: str | None   the concrete next action the user can take
```

`FieldPath` is typed rather than a string so the wizard can navigate directly to the prompt that owns
the offending field (Section 16.6) without parsing text.

### 9.5 Filesystem port

Preflight rules receive a `FilesystemPort`. Tests inject a fake. This keeps the rest of validation
pure, keeps the deviation in Section 5.3 contained, and lets the preflight tier be disabled entirely
by policy when a user is composing a configuration whose referenced resources do not exist yet.

### 9.6 Chemistry probe port — optional by decision

A chemistry-notation parsing library is **not a dependency of this application**. The core builder
completes its entire workflow without one.

The contract states that certain component notations are rejected by the external system's own
parsing (spec §9.2), so the check is worth performing when it is cheaply available. It is wired as a
port so that availability changes validation strength and nothing else:

- `ChemistryProbe` is a protocol with one operation: parse a notation and report validity. The default
  binding is a null probe that reports "not checked".
- With a real probe present, the corresponding rule is `ERROR`, because it then mirrors a `CONFIRMED`
  contract rule with local evidence behind it.
- With no probe, the rule is `WARNING` and its message says the check could not be performed locally.
  It never silently passes, never claims a guarantee it has not made, and never blocks generation.
- No other rule, and no other module, may acquire a chemistry dependency. There is exactly one port
  and one rule behind it, so the optional dependency cannot become a hidden requirement.

The same principle applies to every optional dependency in this plan: it may strengthen a check, and
its absence may never remove a capability.

### 9.7 Testing validation

Each catalogue row gets at least one passing and one failing case (`contract/` and `negative/`), and
a test asserts full coverage of the catalogue so a new rule cannot be added without tests. A second
test asserts every rule's `spec_ref` resolves to a real section heading in `AUTHORITATIVE_SPEC.md`,
which turns contract drift into a test failure.

---

## 10. Transformation layer

### 10.1 Contract

```text
to_wire(configuration, version_policy) -> TransformResult
TransformResult
    document: WireDocument                      ordered mapping, JSON-ready primitives only
    version: int                                the selected format version
    external_resources: tuple[ExternalResourceRequirement, ...]
```

Properties, asserted by tests:

- **Pure.** No filesystem, no clock, no randomness, no global state.
- **Total on validated input.** If a configuration passes `ERROR`-level validation, transformation
  does not raise. Any condition that would make it raise must exist as a validation rule first.
- **Deterministic.** Same input, same document, including key and element order.
- **Single authority.** No other module builds a wire structure. A test asserts no module other than
  `transform` contains a wire field-name literal.

### 10.2 Field mapping tables

`transform` contains one table per record family plus one for the root. Each row is
`(canonical accessor, wire field name, mapping id, emission rule, minimum version)`. Emission rules
derive from the presence algebra:

| Canonical state | Emission |
|---|---|
| `Unset` | field omitted |
| `ExplicitEmpty` | field emitted with the contract's empty value for that field's type |
| `Present(inline)` | inline field emitted, path field omitted |
| `Present(external)` | path field emitted, inline field omitted |

Structural conversions performed here and nowhere else:

- `AlignmentPairing` → the corresponding pair of inline/path fields with the correct
  omitted/empty/populated combination (MAP-601..606).
- `ReferenceSet` → field omitted, or a list (possibly empty), per spec §6.2.
- `ReferenceRecord.index_map` → two parallel 0-based arrays (MAP-703/704).
- `Position` → 1-based value (MAP-903); `ResidueRef` → 1-based value (MAP-904). A test asserts no
  arithmetic adjustment is applied in either direction.
- `Multiplicity` → single value or list form per spec §7.1.
- `ComponentRepresentation` → exactly one of the mutually exclusive fields (MAP-406).

### 10.3 Version selection — pinned to empirically verified evidence

The external system is a **black box** (Section 10.4). Its accepted input format is therefore
established by observation, not by reading its implementation, and `VersionPolicy` is built around
evidence rather than inference:

```text
Unverified              no format has been verified against the deployment yet   → blocks
Pinned(n)               emit version n, where n is an evidenced version
Auto(evidenced_set)     minimum version covering the features used, within the evidenced set
```

- **`Unverified` is the default** for a fresh installation. A CONTRACT rule reports an `ERROR`:
  generation is blocked until a format has been verified and recorded in `docs/CONTRACT_PIN.md`
  (Section 21, Phase 0). The message states how to obtain the evidence — submit a minimal valid input
  through the normal execution path — rather than asking the user for a fact they cannot look up.
- **`Pinned(n)` is the normal operating state.** `n` is the version value observed in the input that the
  deployment actually accepted. This is the initial target for the implementation.
- **`Auto(evidenced_set)`** exists for the case where more than one version has been separately
  evidenced. With a single evidenced version it is equivalent to `Pinned`. It may only ever choose from
  versions with direct evidence behind them; it never extrapolates a range.
- If a feature the user has configured requires a version above the evidenced one, that is a CONTRACT
  `ERROR` naming the feature and stating that a new verification run is needed. The builder does not
  quietly raise the version to make the configuration fit.
- The selected version, and the identifier of the `CONTRACT_PIN.md` record that justifies it, are
  reported in the transform result, shown in the review step, and recorded in the manifest. Every
  generated file can therefore be traced to the evidence that its format was accepted.

**No version is ever inferred.** Not from an example in the specification, not from the newest version
this plan happens to mention, not from a previous implementation, and not from the deployment's software
release — the specification is explicit that the software release and the format version are
independent axes (spec §3, §18), so neither can be derived from the other.

### 10.4 The external system is a black box

The builder is designed against the **observable external contract**, not against the external system's
implementation:

```text
Observable External Contract
        ↓
Canonical Internal Model
        ↓
Validation
        ↓
Transformation
        ↓
Serialization
        ↓
Verified Input Format
```

Consequences that hold throughout this plan:

- The architecture requires **no access** to the deployment's source tree, installation metadata, or
  internal release identity. None of those are inputs to any design decision here.
- The builder does not reproduce, emulate, or partially reimplement the external system. Its
  responsibility ends at producing an input file in a format that has been observed to be accepted
  (spec §21 non-goals).
- The authoritative written contract (`AUTHORITATIVE_SPEC.md`) supplies the field-level rules; the
  deployment supplies one fact only, namely which format it accepts. Those are different kinds of
  evidence and Section 2.2 keeps them labelled apart.
- What cannot be observed is recorded as unknown rather than assumed. An unobtainable internal release
  identity is a documentation gap, not a design gap.

---

## 11. Serialization

One function, one encoding policy:

```text
encode(document: WireDocument) -> bytes
```

- UTF-8, no byte-order mark, exactly one trailing newline.
- `LF` line endings always, on every host platform. Files are opened in binary mode so no platform
  translation can occur. A generated file built on Windows is byte-identical to one built on Linux,
  which is what keeps golden tests valid on both and keeps a file usable on the execution host
  regardless of where it was authored.
- Fixed indentation and separators; key order exactly as produced by `transform` (never re-sorted,
  because ordering is a transformation decision).
- Escaping policy fixed and asserted by tests, including text that contains characters requiring
  escapes and non-ASCII text.
- No timestamps, no host information, no environment-derived values anywhere in the output. This is
  what makes byte-level golden tests possible.

The serializer contains no conditionals on field names. If a change requires one, the change belongs
in `transform`.

---

## 12. Variant system

### 12.1 Representation

A variant is **base + an ordered, typed, serializable list of edits**, not a hand-copied
configuration:

```text
Edit = SetName | SetDescription | SetSeeds
     | SetSequence(record_key, text)
     | AddModification(record_key, code, position) | RemoveModification(record_key, index)
     | SetAlignment(record_key, AlignmentPairing) | SetSingleAlignment(record_key, SingleAlignment)
     | SetReferences(record_key, ReferenceSet)
     | SetComponentRepresentation(record_key, ComponentRepresentation)
     | AddRecord(spec) | RemoveRecord(record_key)
     | AddLinkage(spec) | RemoveLinkage(index)
     | SetComponentDefinition(Presence[...])
     | SetFormatTarget(...)

VariantSpec
    key: str                       stable, user-visible short key
    label: str                     human-facing name
    edits: tuple[Edit, ...]
    declared_factors: tuple[str, ...]   what this variant is intended to change
```

`record_key` is a stable record handle (the record's primary `EntityId`), resolved through
`identity`, so an edit never depends on list position.

Why edits as data rather than a mutated copy: they are reviewable before application, they persist
into the project file and the manifest, they make "what differs between these variants" answerable
without diffing two documents, and they make the drift check in Section 12.5 possible.

The variant dimensions that are meaningful are exactly those spec §15 lists. The edit vocabulary
covers them and nothing else.

### 12.2 Expansion

```text
expand(base: Configuration, specs: tuple[VariantSpec, ...]) -> tuple[Variant, ...]
Variant
    key, label
    configuration: Configuration        fully materialised, independently valid
    lineage: Lineage                     base fingerprint, applied edits, declared factors
```

- Edits apply in declared order; each application returns a new `Configuration`.
- Expansion is a pure function: same base and specs, same variants, same order.
- `base fingerprint` is a content hash of the base's wire document, so a manifest can prove which
  base a variant came from.
- The base itself is always also available for generation as an unmodified member of the set, if the
  user asks for it; it is never implicitly included.

### 12.3 Inheritance semantics

Everything not named by an edit is inherited unchanged. Explicitly: identifiers, seeds, alignment
sources, reference lists, external paths, component definitions, and unrelated records are
inherited byte-identically after transformation. This is the mechanism behind the stable-factor
principle of spec §15, and Section 12.5 tests it rather than trusting it.

### 12.4 Isolation

Isolation is structural, not defensive:

- Every model type is frozen, so sharing sub-objects between base and variants is safe by
  construction. No deep copy is required and none is performed.
- Edits return new objects; there is no in-place mutation path to misuse.
- `IdentityRegistry` is the one mutable-feeling object, and it is cloned per variant at expansion
  time. A test asserts that allocating in one variant does not affect any sibling or the base.

### 12.5 Drift detection

A VARIANT-tier rule compares each variant's wire document against the base's, field by field, and
reports any difference that is not attributable to a declared edit. This converts "a variant
accidentally changed something" from a silent scientific error into a visible finding. Because the
comparison runs on wire documents, it also catches differences introduced by transformation rather
than by the model.

Seeds get a dedicated check: the seed sequence must be identical across the whole set unless a
variant declares a seed edit. The contract does not require this (spec §14); it is a project policy,
so it is a `WARNING` that can be raised to `ERROR`, never a hidden rule.

### 12.6 Naming

Variant naming is derived, deterministic, and owned by `output` (Section 13.2), not by the variant
module, so that naming can change without touching variant semantics.
---

## 13. File generation

### 13.1 Layout

```text
<output_root>/
  <project_slug>/
    manifest.json                       project-side report (MAP-015), not external input
    <project_slug>__<variant_key>/
      <project_slug>__<variant_key>.json        the generated external input file
      assets/                                   optional copies of referenced external resources
```

One directory per variant, with the input file named after the directory. A user can therefore map a
result directory back to a variant by name alone, without opening any file.

### 13.2 Naming rules

- `slug(text)` is a single pure function: lower-cased, restricted to an explicitly allowed character
  set, collapsed separators, length-capped, with a deterministic numeric suffix if truncation would
  cause a collision. Underscores are avoided in generated component-style names because the contract
  documents them as problematic (spec §9.6).
- The generated job name field carries the same derived name that the directory and filename use, so
  the value inside the file and the path outside it agree. This is what makes downstream artefacts
  traceable (spec §16).
- Collisions are detected during planning across the whole run, not discovered mid-write.
- Collision detection is **case-insensitive**, and generated names are restricted to a character set
  that is legal on both POSIX and Windows filesystems. Two variant keys differing only in case would
  collide on a Windows filesystem and not on a Linux one; treating them as a collision everywhere
  means the same project produces the same layout on both, and a project authored on one platform can
  be regenerated on the other without surprise.

### 13.3 Plan then execute

```text
plan(variants, settings) -> OutputPlan            pure; no filesystem writes
execute(plan) -> OutputResult                     performs writes
```

`OutputPlan` lists every intended path, its byte payload's fingerprint, and the action
(`create` / `overwrite` / `skip` / `conflict`). The review step (Section 16.6) shows the plan before
anything is written. Nothing is ever written without a plan.

`OverwritePolicy`: `Fail` (default), `Skip`, `Overwrite`, `Versioned` (append a deterministic
numeric suffix). The default refuses to destroy existing files.

### 13.4 Write semantics

- Writes are atomic per file: write to a temporary file in the destination directory, then rename.
- A run is all-or-nothing at the plan level: if any conflict exists under `Fail`, nothing is written.
- Directories are created only as the plan requires.

### 13.5 External resource paths

The contract allows external resource references to be absolute or relative to the generated input
file's directory (spec §10). `PathPolicy` decides, per resource:

- `AsGiven` — emit the user's path unchanged (normalized separators only).
- `RelativeToOutput` — emit a path relative to the generated file's directory.
- `CopyIntoAssets` — copy the resource into `assets/` and emit the relative path to the copy.

**`CopyIntoAssets` is the default.** The established workflow authors on one machine and executes on
another (Section 4.2), so the output set must survive a transfer. `CopyIntoAssets` is the only policy
that produces a directory which can be copied anywhere and still resolve, because every referenced
resource travels with the file that references it. `RelativeToOutput` is correct when the resources
already live beside the output on the execution system. `AsGiven` exists for a user who knows exactly
what they are doing and is the only policy that can emit a path meaningful on just one machine.

The chosen policy is recorded in the manifest, because it changes the meaning of the emitted path
strings.

Three rules follow from the cross-machine workflow:

- **Emitted paths always use forward slashes**, on every host platform. The contract resolves relative
  paths against the generated file's directory; forward slashes are the form that works on the
  execution host, and they keep output byte-identical regardless of where it was built.
- **Emitted paths are relative wherever the policy permits**, so that nothing in the generated file
  depends on the authoring machine's directory layout.
- **A path that cannot resolve on the execution host is reported at authoring time.** A drive-letter or
  UNC absolute path is the clear case: valid where it was typed, meaningless on the Linux execution
  system. This is a PREFLIGHT `WARNING` — the contract does not forbid any particular path form
  (spec §10), so it cannot be an error — and it names `CopyIntoAssets` or `RelativeToOutput` as the
  fix. Catching this while the user is still at the keyboard is the whole point; the alternative is a
  failure hours later on a machine where they cannot see the configuration.

### 13.6 Manifest

Project-side, never consumed by the external system. Contains: project name; base fingerprint;
selected format version **and the identifier of the `CONTRACT_PIN.md` record that evidences it**; path
policy; per variant the key, label, declared factors, applied edits, generated filename and payload
fingerprint; the seed set; the validation summary; and the builder version. Recording the pin reference
is what lets anyone holding a generated file establish which observation justified its format, and
notice when that observation has gone stale. Time-varying data (timestamps, host, user) lives in a single separate `run_info` object that
is excluded from determinism assertions, so the rest of the manifest stays byte-reproducible.

### 13.7 Determinism definition

Given the same project file and the same output root, two runs produce byte-identical generated input
files and byte-identical manifests apart from `run_info`. This is a tested property
(Section 18.6), not an aspiration.

---

## 14. Configuration persistence

Persistence is **required**: the workflow includes reopening and editing configurations, and the
variant model is worthless if a user cannot come back to a base configuration later.

The project file is deliberately **not** the generated external input file. The generated file cannot
represent variant specs, declared factors, presence states chosen for future use, path policy, or
project-side labels. Round-tripping through it would lose user intent.

```text
project file (own extension, JSON payload)
    schema_version: int                     independent of the external format version
    project: { metadata, base configuration, variant specs, output settings }
```

- **Lifecycle.** `new` → `save` → `load` → `edit` → `save`. Saving is explicit; the UI warns on
  unsaved changes.
- **Versioning.** `schema_version` is the project file's own axis and is never conflated with the
  external format version (spec §18's two-axis warning applies here too).
- **Compatibility.** Loading a lower `schema_version` runs a named upgrade step. Loading a higher one
  is refused with a clear message; guessing is not attempted.
- **Load-time validation.** A loaded project is reconstructed through the same model constructors as
  a UI-built one, so a hand-edited or corrupted file cannot inject an invalid model. Validation then
  runs and its findings are presented immediately.
- **Identity.** The registry is persisted so identifiers survive reopening; reopening a project never
  reassigns identifiers.

---

## 15. Application services

`app` exposes the only API a front end needs. Every operation returns a result object; user-caused
problems are findings, not exceptions.

| Service | Operations |
|---|---|
| `ProjectService` | `new`, `open(path)`, `save`, `save_as`, `is_dirty` |
| `ConfigurationService` | `set_name`, `set_seeds`, `add_record(family, ...)`, `update_record`, `remove_record`, `add_modification`, `set_alignment`, `set_references`, `set_component_definition`, `add_linkage`, `remove_linkage`, `set_format_target` |
| `ValidationService` | `validate_base`, `validate_all`, `set_policy` |
| `VariantService` | `add_spec`, `update_spec`, `remove_spec`, `duplicate_spec`, `preview(spec)`, `expand` |
| `GenerationService` | `plan(output_settings)`, `execute(plan)` |

Generation sequence inside `GenerationService.plan`, in this exact order:

1. Validate the base. Stop on `ERROR`.
2. Expand variants.
3. Validate each variant, including the drift check.
4. Transform each variant.
5. Encode each wire document.
6. Build the output plan, including collision detection and the manifest payload.

`execute` performs writes only. It does not re-derive content, so what the user reviewed is exactly
what is written.

---

## 16. Terminal wizard workflow

### 16.0 Operating assumptions

The builder is an **authoring application**. It normally runs on the user's own machine, and its
output is transferred to the execution system (Section 4.2). Three settings are supported:

1. **Local Windows** — Windows Terminal, PowerShell, or `conhost`. This is the primary authoring
   environment.
2. **Local Linux** — an ordinary Linux terminal, equally supported for authoring.
3. **Remote Linux over SSH** — supported, and useful when the referenced resource files already live
   on that system. It is **not** the design centre: the architecture does not assume or require a
   long-running interactive session on a shared login node, and nothing in the workflow depends on one.
   Users who prefer to author remotely can, but the plan does not optimise for it.

The design assumes all of the following and degrades rather than failing:

| Assumption | Consequence for the design |
|---|---|
| No display and no browser; mouse may exist but is never required | Keyboard-only navigation. Nothing requires pointing, dragging, or hovering. Every action has a typed or keyed equivalent. |
| Terminal capability varies | Renderer is selected by capability probe (Section 16.7), from full-screen down to a plain line-based dialogue that needs only `stdin`/`stdout`. |
| Both POSIX and Windows hosts | No POSIX-only assumption is load-bearing. Signals, terminal size notification, state directories, path syntax, and editor discovery all go through a thin platform layer (Section 16.10). |
| Width and height vary and can change mid-session | All layout is computed for the measured width, with a documented minimum of 80 columns and a usable degraded layout below it. Resize is picked up from `SIGWINCH` on POSIX and by polling the console size on Windows; neither path may crash. |
| Latency and low bandwidth over SSH | Redraws are incremental and bounded; no animation, no spinner-driven redraw loops, no full-screen repaint per keystroke. |
| Colour may be absent or unwanted | Colour is never the only carrier of meaning. Severity is always also a word and a symbol. `NO_COLOR` and a non-colour `TERM` are honoured. |
| Unicode may not render | Box-drawing and symbols come from a glyph set chosen by capability; an ASCII-only set is always available. This matters most on legacy Windows consoles running a non-UTF-8 code page. |
| A session can end unexpectedly | Work is recoverable: every completed step is journalled (Section 16.8). This is ordinary resilience against a closed window or a lost connection, not an accommodation for long remote sessions. |
| Copy-paste is reliable and is how users move text in | Paste is a first-class input route (Section 16.5), with bracketed paste used where available so a multi-line paste is never interpreted as a series of commands. |
| Resource files are moved between machines by SFTP | Read-from-file is the other first-class route, with completion against the local filesystem, wherever the builder happens to be running (Section 16.5). |
| Optional packages may be absent | The stdlib-only plain-line renderer is the guaranteed path and completes the entire workflow. The full-screen renderer is enabled only when its optional dependency is importable (Section 16.7). |
| The process may have no TTY (batch job, pipe, `nohup`) | A non-interactive renderer refuses to prompt and instead reports what input it needed (Section 16.7). |
| Home directory is shared and quota-limited | State and logs live under a platform-appropriate state directory, are small, and are capped (Section 16.8). |
| Screen readers are used by some terminal users | Output is linear and readable in order; the plain-line renderer exists partly for this reason (Section 16.9). |

### 16.1 Steps

The wizard covers the full user workflow. Each step is a named state with an explicit entry
condition, so navigation logic is testable independently of any rendering.

| Step | Purpose | Entry condition |
|---|---|---|
| 1 Start | New or open a project | always |
| 2 Job details | Name, optional description | project open |
| 3 Molecules | Add and configure records; family chosen from a labelled list | name set |
| 4 Modifications | Per-record modification entries with a position picker | at least one polymer record |
| 5 Components | Ligand/ion configuration and representation choice | a component record exists |
| 6 Custom chemistry | Inline or file-based definition, if needed | a code needs a definition, or user opts in |
| 7 Links | Covalent links between addressable endpoints | at least two addressable endpoints exist |
| 8 Alignments and references | Per-record alignment mode and structural references | a record supports them |
| 9 Files and paths | External resource paths and path policy | any external resource is referenced |
| 10 Reproducibility | Seed set | always |
| 11 Validate | Full report, grouped and navigable | reachable from any completed step |
| 12 Variants | Build variant specs from a guided factor picker | base validates without errors |
| 13 Review | Per-variant summary, differences, and the write plan | variants expanded |
| 14 Generate | Execute the plan and report where the files went | plan has no unresolved conflicts |

Steps are revisitable. The wizard never blocks backward navigation, and revisiting invalidates the
cached report rather than keeping a stale green state.

### 16.2 Step machine

A step is a value, not a screen:

```text
Step
    id: StepId
    title_key: str                    resolved through the traceability registry
    entry_condition(view) -> bool
    fields(view) -> tuple[FieldSpec, ...]      only the fields this state should ask for
    actions(view) -> tuple[Action, ...]        what the user may do from here
    apply(answer) -> tuple[ServiceCall, ...]   what to ask `app` to do
```

`view` is a read-only projection of the project plus the latest `ValidationReport`. The machine is
pure: no terminal, no filesystem, no service invocation of its own. This is what makes the whole
navigation model unit-testable without a terminal at all, and what lets the same steps drive three
different renderers.

### 16.3 Interaction model

One consistent, keyboard-only grammar across every step. It is stated once in a persistent hint line
and never varies by step:

| Input | Meaning |
|---|---|
| `Enter` on empty input | accept the shown default and continue |
| a number | choose that numbered option from a list |
| a name or prefix | choose by name where options are named; ambiguous prefixes re-prompt with the candidates |
| `n` / `p` | next / previous step |
| `e` | edit an existing item in a list |
| `d` | delete an item, always with a confirmation naming what will be deleted |
| `v` | validate now |
| `a` | show this step's advanced settings (Section 16.4) |
| `?` | help for the current field, in plain language |
| `s` | save the project |
| `q` | quit, with an unsaved-changes prompt |
| `Ctrl-C` | cancel the current prompt and return to the step menu; twice in a row exits after a save prompt |

Rules that keep this usable over a slow link:

- Every prompt shows its default inline, so the common path is `Enter` repeatedly.
- Every list is numbered and paginated for the measured height; long lists are searchable by typing.
- No prompt requires more than one line of input except the long-text route (Section 16.5).
- The step header always shows position in the sequence (`Step 4 of 14`), the project name, and
  whether unsaved changes exist, so a user returning to a stale session knows where they are.

### 16.4 Hiding complexity

The wizard never asks the user to do any of the following, all of which are owned by lower layers:
assign identifiers, count positions manually, keep two index arrays aligned, choose between a field
and its path twin, write any markup or notation by hand for something the builder can construct,
remember which family supports which optional field, duplicate a configuration to make a variant, or
construct an output directory.

Concretely, in terminal terms:

- **Family choice** is a numbered list of registry labels. The user types a number.
- **Modification position** is chosen against a rendered sequence with a position ruler, shown in
  width-sized blocks with human numbering at both ends of each line:

  ```text
  Chain 1 (Protein chain) — 128 positions

  Position to modify [1-128]: 101
    → position 101 is T
  Modification to apply: TPO
  ```

  The user types the position number directly, which is how positions are referenced in the domain
  anyway. The wizard echoes the residue currently at that position as confirmation, which is what
  catches an off-by-one or a wrong-chain mistake before it reaches the file. The value becomes a
  `Position` with no arithmetic shown or requested.

  Typing `?` at the position prompt prints the sequence with a position ruler, for a user who wants to
  look before choosing. It is an aid on request, not a step everyone pays for:

  ```text
       1  MKWVTFISLL LLFSSAYSRG VFRRDTHKSE IAHRFKDLGE   40
      41  EHFKGLVLIA FSQYLQQCPF DEHVKLVNEL TEFAKTCVAD   80
      81  ESHAGCEKSL HTLFGDELCK VASLRETYGD MADCCEKQEP  120
     121  ERNECFLS                                     128
  ```

  Out-of-range and non-numeric entries re-prompt with the valid range. The same
  type-the-number-and-see-it-echoed pattern is used everywhere a position is requested, including
  link endpoints, so the user learns one habit.
- **Structural reference mapping** is entered as pairs, one per line, through any of the routes in
  Section 16.5 — paste is usually the quickest — with a worked example shown above the prompt. The
  wizard parses the pairs into `IndexPair` values and reports any malformed line by line number. Two
  parallel arrays are never shown, and the user never maintains alignment between two lists.
- **Alignment mode** is a numbered single-choice list of plain-language options corresponding one to
  one with the sum-type cases. Because the illegal combination is not in the list, the "both or
  neither" rule needs no explanation.
- **Fields a family does not support are absent** from that family's prompts, not shown-and-refused.

**Progressive disclosure.** Each step asks for what is required and commonly used first, and keeps
optional or advanced settings one keystroke away rather than in the main flow:

- Required fields are prompted directly. Optional fields with a sensible default are applied silently
  and reported in the step's summary line, so the user can see them without being asked about them.
- Advanced settings — expert alignment modes, explicit path policy, format-version pinning, overwrite
  policy, severity policy — are reached with `a` from the step they belong to, and the step's summary
  states that they exist and what they currently are.
- Disclosure is driven by relevance, not by a fixed difficulty tier: an advanced field becomes a normal
  prompt once something in the configuration makes it necessary. Declaring a component that needs a
  custom definition, for example, promotes the definition prompt into the main flow.
- **Nothing is permanently hidden.** Every capability the contract supports is reachable through the
  wizard. A field that this plan classifies as advanced is still a field the user can find, set, and
  see in the review step. Progressive disclosure controls when a question is asked, never whether the
  capability exists.
- **Variants** come from a factor picker: choose what to vary from a numbered list, supply a label
  and a value per variant, and the builder writes the edits. The user never copies a configuration.
- **Paths** are prompted with tab completion against the filesystem, shown expanded after entry
  (`~` and environment variables resolved), and immediately reported as readable or not.

### 16.5 Long text entry

Sequences, alignment content, and inline chemistry definitions are large. Two routes carry almost all
real use — pasting into the terminal, and reading a file that was uploaded by SFTP — and both are
first-class. An editor route exists for composing or fixing content in place.

```text
Sequence for chain 1:
  1) Paste it here
  2) Read from a file on this machine
  3) Open an editor
Choose [1]:
```

- **Paste** is the default. Bracketed paste is enabled wherever the terminal supports it, so a
  multi-line paste arrives as one value and is never interpreted as a series of commands. The prompt
  states how to finish (a blank line, or the platform's end-of-input key) and then reports what it
  received — length, and whether the shape is plausible for the field — before accepting. Where
  bracketed paste is unavailable, the wizard still accepts multi-line input, terminated explicitly,
  rather than silently restricting the route.
- **Read from a file** prompts for a path with completion against the local filesystem, reads it, and
  reports what it found. This is the natural partner to an SFTP upload: the user puts the file on the
  server with WinSCP, then points the wizard at it. For fields the contract allows to be referenced by
  path, this route also offers to keep the content as an external reference instead of inlining it,
  and explains the difference in one sentence, since that choice changes what the generated file
  depends on at run time.
- **Open an editor** is a convenience, never a requirement. It writes a temporary buffer with a
  commented header explaining the expected content and a worked example, launches `$VISUAL` or
  `$EDITOR` (or a documented per-platform candidate when neither is set), then re-reads and parses the
  buffer on exit. Comment lines are stripped. A parse problem returns the user to the same buffer with
  the error at the top rather than discarding the work.

  **No external editor is a dependency.** If none can be found, this option is simply not offered, and
  the wizard says why if the user asks. The application remains fully usable through paste and
  read-from-file, both of which are built in. Nothing in the workflow is reachable only through an
  editor, and no step may ever require one.

Rules that apply to all three routes:

- **No silent repair.** Nothing is truncated, reflowed, re-cased, or whitespace-normalized. This is
  the terminal-side expression of the specification's warning against rewriting supplied alignment
  content.
- **Line endings are reported, not fixed.** Content pasted from a Windows client or read from a file
  transferred in text mode may carry `CRLF`. The wizard detects this and says so, and the handling
  policy is a single documented decision applied in one place rather than an incidental side effect of
  whichever route was used. **The decision is preserve and warn** (Section 22, Q16): the original
  content is kept byte-for-byte, the condition is reported, and validation decides whether it is
  actually invalid. The builder does not modify user content for convenience.
- **What was received is echoed back** as a short summary before acceptance, so a paste that was
  clipped by the client is caught at entry rather than at generation.

### 16.6 Findings, review, and generation in a terminal

- **Findings list.** Grouped by severity, then by the record a `FieldPath` points to, each with a
  stable reference number the user can type to jump straight to that field's prompt. Severity is
  shown as a word and a symbol (`ERROR  [x]`, `WARNING [!]`, `INFO [i]`), so meaning survives without
  colour.
- **Jump-to-field.** Because `FieldPath` is typed, the step machine can compute which step and which
  prompt corresponds to a finding. Typing a finding's number navigates there directly — the terminal
  equivalent of clicking an error.
- **Technical details** are behind a per-finding `t` key rather than printed inline, so the default
  view stays readable at 80 columns.
- **Review step** prints, per variant: the label, the declared factors, the differences from the base
  in registry vocabulary, and the planned output path with the action (`create` / `overwrite` /
  `skip` / `conflict`). Warnings requiring acknowledgement are listed with an explicit
  `Acknowledge warnings? [y/N]` prompt; the default is no.
- **Generate step** prints one line per written file and a final summary with the output root, then
  the exact command-free instruction for where to find the manifest. Long runs print progress as
  completed-count lines rather than a redrawn progress bar, so the output remains readable in a log
  or through a slow connection.
- **Non-interactive echo.** Everything the generate step prints is also appended to a run log in the
  output directory, so a user who ran the wizard inside a batch job can read what happened.

### 16.7 Renderers and capability degradation

One step machine, three renderers, selected by a capability probe at startup and overridable by a
flag. **`PlainLineRenderer` is the baseline and is written against the standard library only**; it is
what guarantees the workflow is completable on any supported machine. The full-screen renderer is an
enhancement that appears when its optional dependency happens to be installed.

| Renderer | Dependency | Used when | Behaviour |
|---|---|---|---|
| `PlainLineRenderer` | none | the default whenever the full-screen renderer is unavailable or not selected: optional package absent, limited `TERM` (including `dumb`), a legacy Windows console without virtual-terminal support, no colour, narrow width, screen-reader use, or user preference | Sequential question-and-answer with no cursor addressing and no escape sequences beyond newlines. Every step is reachable and nothing is cut; this renderer is feature-complete by requirement, not by courtesy. |
| `FullScreenRenderer` | `prompt_toolkit`, optional | a capable interactive TTY **and** the package is importable | Persistent header and hint line, in-place list navigation, inline help, path completion. Convenience only: it asks exactly the same questions and produces exactly the same configurations. |
| `NonInteractiveRenderer` | none | `stdin` is not a TTY | Never prompts. Reports precisely which inputs would have been required and exits with a distinct status code. This is a guard against hanging, **not** a batch authoring front end — it does not author configurations from a parameter file, and none is defined in this plan (Section 22, Q14). |

The capability probe reads, on both platforms, whether the optional renderer package is importable,
whether the streams are a TTY, the measured size, `NO_COLOR`, and any explicit override flag. On POSIX
it also reads `TERM`. On Windows it additionally attempts to enable virtual-terminal processing and
checks the console's output encoding; if either is unavailable it selects `PlainLineRenderer` with the
ASCII glyph set rather than emitting escape sequences the console will print literally. The probe's
result and the reason for it are logged, so a user reporting "it printed strange characters" can be
diagnosed from the log. Choosing a renderer and a glyph set is the only decision the probe makes; it
never changes what the wizard asks.

Because the step machine is pure, `PlainLineRenderer` is not a reduced feature set — it is the same
workflow with simpler drawing. Two things keep it that way rather than letting it rot into a
second-class path: the wizard-level end-to-end test runs through it, and the snapshot transcripts are
taken from it (Section 18.8). A missing optional package therefore costs polish and nothing else.

### 16.8 Session state and resume

- The project file (Section 14) remains the only representation of user intent. Nothing about the
  wizard's position in the workflow is stored inside it.
- A small session journal records the current step, the project file path, and unsaved-change status
  in a platform-appropriate state directory: `$XDG_STATE_HOME` or `~/.local/state/configbuilder` on
  POSIX, `%LOCALAPPDATA%\configbuilder` on Windows. It is capped in size and pruned, because home
  directories on shared systems are quota-limited.
- On startup, if a journal exists for a project file that is still present, the wizard offers to
  resume at that step. Declining discards the journal.
- Prompting for a save happens on `q` and on `Ctrl-C` twice. On POSIX it is also attempted on
  `SIGHUP`/`SIGTERM`. Windows offers no equivalent for an abruptly closed console window, so the
  journal is written after each completed step rather than relying on a shutdown hook; the next start
  reports that unsaved changes existed rather than pretending the project was clean. The journal, not
  the signal handler, is what makes recovery work — which is why this costs one small write per step
  and requires no assumption about how the session ends.

### 16.9 Accessibility and plain-output guarantees

- No information is conveyed by colour alone, ever.
- The plain-line renderer produces linear, top-to-bottom output with no cursor addressing, which is
  what screen readers and terminal multiplexer logs handle reliably.
- Minimum supported width is 80 columns; between 60 and 80 the layout degrades to single-column
  without losing content; below 60 the wizard says so and continues in plain-line mode rather than
  producing scrambled tables.
- A `--plain` flag forces the plain-line renderer, `--ascii` forces the ASCII glyph set, and
  `--no-color` is honoured in addition to `NO_COLOR`, so a user is never dependent on the probe
  guessing correctly.

### 16.10 Platform layer

Everything that differs between POSIX and Windows lives in one small module, `ui/render/platform.py`,
so the rest of the wizard is written once. It is the only place allowed to branch on the host
platform.

| Concern | POSIX | Windows |
|---|---|---|
| Terminal size changes | `SIGWINCH` handler | size polled between prompts |
| Graceful-shutdown save prompt | `SIGHUP`, `SIGTERM` | not available; journal-after-each-step covers it |
| Interrupt | `SIGINT` via `Ctrl-C` | `Ctrl-C`, same semantics |
| State and log directory | `$XDG_STATE_HOME`, else `~/.local/state` | `%LOCALAPPDATA%` |
| Escape-sequence support | assumed, verified by `TERM` | virtual-terminal processing enabled at startup, else plain renderer |
| Output encoding | UTF-8 assumed, ASCII glyphs on doubt | console encoding checked; ASCII glyphs unless UTF-8 is confirmed |
| Editor discovery | `$VISUAL`, `$EDITOR`, then a documented list | `$VISUAL`, `$EDITOR`, then a documented Windows list |
| Path display and completion | as entered, `~` expanded | as entered, drive-letter and UNC paths accepted |
| Atomic replace | rename over target | `os.replace`, same guarantee |

Two rules keep this from spreading:

- No other module imports `sys.platform` or `os.name`. An architecture test asserts this.
- Generated output never depends on the host platform. Line endings, encoding, and ordering in
  generated files are fixed by `serialize` (Section 11) and are identical on both platforms, so golden
  tests are valid everywhere and a file built on Windows is byte-identical to one built on Linux.

### 16.11 Advanced inspector

A read-only view can page through the generated document and the write plan for a selected variant,
for users who want to check the output before or after generation. It is read-only, reached only from
the review step, and has no editing affordance, so it cannot become a second authoring route. It uses
an internal pager rather than shelling out, so it behaves identically regardless of what pager the
system has configured.

---

## 17. Error handling

Two distinct channels, never mixed.

| | User-facing | Technical diagnostic |
|---|---|---|
| Answers | what is wrong, where, why it is invalid, what to do next | rule id, spec citation, evidence status, mapping ids, observed value, stack context |
| Vocabulary | registry labels only | internal names permitted |
| Surface | at the prompt where the problem belongs, plus the grouped findings list | the per-finding `t` key and the log file |

Failure classes:

- **User-caused** (invalid or incomplete configuration): always a `Finding`. Never an exception.
- **Environmental** (path unreadable, destination not writable, project file corrupted, quota
  exceeded, read-only filesystem): a result object with a plain-language cause and a remedy, plus a
  log entry. On shared systems these are common, so each one names the path involved and what to
  check.
- **Internal invariant violation** (a bug): fail loudly with the diagnostic, invite the user to
  report it, never write partial output. Because `execute` only writes a reviewed plan and writes
  atomically, a crash cannot leave a half-written input file.
- **Terminal-environment problems** (no TTY, unsupported `TERM`, width below the usable minimum, no
  editor available for the long-text route): never fatal. Each one degrades to a documented fallback
  and says which fallback it chose and why.

Exit statuses are distinct and documented, so the wizard can be used inside a batch script: success,
validation-blocked, missing-input under the non-interactive renderer, environmental failure, and
internal error each have their own code.

A rotating log file in the platform state directory (Section 16.10) holds diagnostics. It contains no file contents and
no user sequence data beyond identifiers and names, so it can be attached to a bug report safely.

---

## 18. Testing strategy

### 18.1 Layout

```text
tests/
  unit/           model, identity, validation engine, transform tables, output planning, persistence
  contract/       one or more cases per catalogue rule, each citing its spec section
  golden/         byte-exact expected outputs
  negative/       invalid configurations must be rejected, with the expected rule id
  variant/        inheritance, isolation, determinism, drift detection, lineage
  serialization/  encoding determinism and escaping
  terminal/       step machine, formatting, renderers under a pseudo-terminal
  e2e/            full service-level and full wizard-driven workflows into a temporary directory
  architecture/   dependency rules, single-authority checks, naming rules
```

### 18.2 Unit tests

Cover construction invariants, the presence algebra, identifier allocation, field-mapping rows,
naming and slug derivation, plan construction against a fake filesystem, and persistence
round-trips.

### 18.3 Contract tests

Table-driven, one row per rule in the catalogue. Each case carries the rule id and spec section, so a
failure names the contract clause it violates. Two meta-tests guard the suite: every catalogue rule
has at least one positive and one negative case, and every `spec_ref` resolves to a real heading in
`AUTHORITATIVE_SPEC.md`.

### 18.4 Golden tests

Byte-exact comparison of generated files against fixtures in `fixtures/golden/`. Fixtures are
labelled by provenance:

- `external/` — inputs with evidence behind them. Two kinds, each labelled: derived from examples the
  specification's own sources provide, or **observed to be accepted by the actual deployment** (the
  Phase 0 probe input and any later accepted output, Section 22.4). The second kind carries the date and
  the `CONTRACT_PIN.md` record that justifies it.
- `project/` — builder-defined expectations for cases with no authoritative example and no acceptance
  observation. These assert determinism and stability only, and are explicitly not evidence about the
  external contract.

Tests must not encode any expectation absent from the specification. A meta-test asserts every
golden fixture declares its provenance.

### 18.5 External verification — two routes, both optional

**Decision: optional, never required** (Section 22, Q3). The core suite — every tier in Section 18.1 —
is complete and meaningful with no access to the external system at all, and it is what CI runs. Neither
route below is a runtime dependency or a precondition for development.

**Route A — deployment acceptance (the black-box route).** A generated file is submitted through the real
execution path and observed to be accepted, exactly as in the Phase 0 probe (Section 22.4). This is the
strongest evidence available about the deployment, and the only route available when the system's
implementation cannot be inspected. It is **not** an automated test: it is a manual, dated observation
recorded in `docs/CONTRACT_PIN.md`, worth repeating when the pin is re-established or when the builder
gains a feature the original probe never exercised. Accepted outputs feed back into the suite as
`golden/external/` fixtures, which *are* automated from then on.

**Route B — local parser.** If a checkout of the external system's own input parser is ever available
locally, an opt-in tier feeds every golden output through it. On a black-box deployment this is expected
to be unavailable, and nothing depends on it.

Neither route may become the only place a contract rule is checked: anything either would catch must also
be expressed as a catalogue rule with its own test, so the suite's meaning never depends on access the
project may not have.

### 18.6 Property-based tests

| Property | Statement |
|---|---|
| Determinism | `encode(to_wire(c))` is identical across repeated calls and across processes |
| Transform totality | any configuration passing `ERROR` validation transforms without raising |
| Presence preservation | for every field, the canonical presence state and the emitted presence state correspond exactly; no state maps onto another |
| Index-base preservation | no position or index value is altered between model and wire |
| Identifier uniqueness | after any sequence of add/remove/rename operations, all identifiers remain unique and all references resolve |
| Variant isolation | for any base and any specs, editing any variant leaves every sibling's and the base's wire document unchanged |
| Inheritance | any field not named by a variant's edits is byte-identical to the base's |
| Expansion determinism | `expand` is a pure function of base and specs, including ordering |
| Naming injectivity | distinct variant keys produce distinct filenames, or a planned conflict is reported |
| Persistence round-trip | `load(save(p))` yields a project whose wire documents are byte-identical to `p`'s |

### 18.7 Architecture tests

Assert the dependency rules of Section 5.3; assert wire field-name literals appear only in
`transform`; assert `Optional` is not used for contract-bearing model fields; assert the traceability
registry covers every model type; assert no module other than `identity` allocates identifiers; assert
`ui` contains no reference to `transform`, `serialize`, `output`, or `persistence`; assert
`ui/steps/` and `ui/present/` import no terminal library, so the step machine cannot acquire a
rendering dependency; assert no module outside `ui/render/platform.py` branches on `sys.platform` or
`os.name`, so platform differences cannot leak into the pipeline.

### 18.8 Terminal interface tests

The terminal front end is testable because the step machine is pure and the renderers are isolated.

| Tier | Method | Asserts |
|---|---|---|
| Step machine | direct calls, no terminal | reachability of every step, entry conditions, field visibility per family, which service calls an answer produces, jump-to-field resolution from every `FieldPath` variant |
| Formatting | pure functions over a fixed width | sequence rendering with correct human numbering at 80/100/60/40 columns, table degradation, finding text containing no internal names and no wire field names |
| Plain-line renderer | scripted `stdin`, captured `stdout`, snapshot comparison | exact transcript of a full workflow; no escape sequences present in the output at all. Runs on both platforms and the snapshot is identical on both |
| Full-screen renderer | pseudo-terminal harness with scripted keystrokes on POSIX; the library's own test input pipe on Windows | the workflow completes; resize mid-session re-lays out without error; `Ctrl-C` returns to the step menu rather than exiting |
| Capability probe | synthetic environments | `TERM=dumb`, `NO_COLOR`, absent TTY, 40-column width, a legacy Windows console without virtual-terminal support, a non-UTF-8 console encoding, and a capable terminal each select the documented renderer and glyph set |
| Non-interactive renderer | no TTY, incomplete input | never blocks on a prompt; names the missing inputs; returns the documented exit status |
| Long-text routes | scripted paste, fixture files, and a fake editor | multi-line paste arrives as one value; the received-content summary is correct; editor round-trip preserves content byte-for-byte; comment headers are stripped; a parse error returns the buffer with the error rather than discarding it; file-read reports what it found |
| Line-ending handling | `CRLF` and `LF` fixtures through every route | the detection warning fires exactly when it should, and the documented policy is applied identically by all three routes |
| Position entry | scripted answers | the echoed residue matches the requested position for every family; out-of-range and non-numeric input re-prompts with the range; `?` prints a correctly numbered ruler; no arithmetic is applied to the entered value |
| Platform layer | both hosts in CI | resize, interrupt, state-directory location, editor discovery, and atomic replace behave per Section 16.10 on each platform |
| Signals and resume | POSIX harness sending `SIGWINCH`, `SIGHUP`, `SIGTERM`; Windows harness killing the process | no crash; journal present; next start offers resume at the recorded step in both cases |
| Content preservation | property test | any content entered through any long-text route reaches the model unmodified — no truncation, reflow, whitespace normalization, or case change |

Three rules for this tier. Snapshots are only taken of the plain-line renderer, because full-screen
escape output is not a stable contract. No terminal test asserts anything about the external contract,
which belongs to `contract/`. And the suite runs on Linux and Windows in CI, with the golden and
serialization tiers asserting byte-identical generated files on both — a platform-dependent output
difference is a test failure, not a known quirk.

### 18.9 End-to-end tests

Two layers, both into a temporary directory.

- **Service-level.** Drive `app` services only: build a configuration covering every family, every
  modification form, every alignment state, every reference state, both component representations, a
  custom chemistry definition, links, and a fixed seed set; validate; create several variants; review;
  generate; assert the directory layout, the manifest content, and the byte content of each generated
  file. Also assert the negative path: an invalid configuration blocks generation and writes nothing.
- **Wizard-level.** Drive the same scenario through the plain-line renderer with a scripted keystroke
  transcript, and assert the generated files are byte-identical to those produced by the
  service-level test. This is the check that the terminal front end adds no behaviour of its own and
  bypasses no stage.

---

## 19. Downstream boundary

The execution system and the downstream analysis systems are out of scope. Only the boundary is
documented.

```text
Generated Output  →  External Execution  →  External Results  →  Downstream Consumer
```

The execution system is a **black box** (Section 10.4). The builder writes files and stops. It does not
submit them, does not invoke the execution system, does not poll for results, and does not read the
system's implementation or installation metadata. Everything it knows about that system is one dated
observation of which input format it accepts (Section 22.4). Placing files in a submission location and
running them is a human step, deliberately outside this architecture.

Boundary commitments this builder makes, and nothing more:

1. **Interface.** Its output is a set of files in the layout of Section 13.1, one input file per
   variant, plus a project-side manifest.
2. **Format.** Each input file targets exactly one dialect and one format version, both recorded in
   the manifest along with the observation that evidences the format.
3. **Traceability.** The manifest links each generated file to its variant key, declared factors, and
   payload fingerprint. Result locations produced by the external system are identified by the seed
   and sample naming the specification documents (spec §16, MAP-016, MAP-907/908); the builder
   records the seed set so a consumer can reconstruct that correspondence.
4. **Non-commitments.** The builder does not parse results, does not interpret confidence or quality
   measures, does not perform statistics, comparison, visualization, or any scientific judgement, and
   does not schedule or manage execution. Spec §16's caution about the nature of the external
   system's quality measures is respected by not touching them at all.

Any future result-consuming tool reads the manifest; it must not re-derive naming or re-parse the
generated input files to recover project intent.
---

## 20. Authority map

Exactly one owner per responsibility. This table is the anti-drift contract for the codebase.

| Responsibility | Authoritative module | Consumed by | Must not be duplicated in |
|---|---|---|---|
| Canonical model and invariants | `model` | all layers | `app`, `ui`, `transform`, `persistence` |
| Presence / representation states | `model` (presence algebra, sum types) | `validation`, `transform`, `variants`, `persistence` | anywhere reintroducing `None`/`""`/`[]` as meaning |
| Identifier allocation, uniqueness, reference resolution and rewrite | `identity` | `model`, `validation`, `variants`, `app` | `ui`, `transform`, `output`, `persistence` |
| Traceability registry and UI labels | `model.traceability` | `ui`, `validation` messages | hard-coded strings in `ui` |
| Validation rules and severity policy | `validation` | `app` | `ui`, `transform`, `serialize`, `output`, `model` methods |
| Contract citations and evidence status | `validation.catalogue` | tests, diagnostics | scattered comments |
| Canonical → wire mapping, field names, index bases, version selection | `transform` | `serialize`, `app` | `ui`, `output`, `persistence`, `variants` |
| Encoding and byte determinism | `serialize` | `output`, `app` | `transform`, `output`, `persistence` |
| Variant edit vocabulary, expansion, lineage, isolation | `variants` | `app`, `persistence` | `ui`, `output` |
| Drift and stability checks | `validation` (VARIANT tier) | `app` | `variants`, `ui` |
| Output naming, slugs, plan, collisions, overwrite policy, path policy | `output` | `app` | `ui`, `variants`, `transform` |
| Filesystem writes | `output` | `app` | everywhere else |
| Manifest construction | `output` | `app` | `variants`, `ui` |
| Project persistence and schema versioning | `persistence` | `app` | `output`, `ui` |
| Use-case orchestration and stage ordering | `app` | `ui` | `ui`, `output` |
| Step sequence, entry conditions, field visibility | `ui/steps` | `ui/render` | `ui/render`, `app` |
| Presentation, formatting, label resolution | `ui/present` | `ui/render` | `ui/steps`, `ui/render` |
| Terminal drawing, input collection, capability probe | `ui/render` | — | `ui/steps`, `ui/present`, any non-`ui` module |

---

## 21. Implementation phases

Each phase is independently verifiable and leaves the repository in a working, tested state. The
order follows the dependency graph: nothing is built before what it depends on, and the contract is
pinned before any code encodes it.

### Phase 0 — Contract probe and scaffold

- **Objective.** Establish empirically which input format the deployment accepts, and make the
  repository testable on day one.
- **Do first.** Run the contract probe of Section 22.4: submit a minimal valid input through the real
  execution path, observe acceptance, and record the result in `docs/CONTRACT_PIN.md`. Retain the probe
  input as the first `golden/external/` fixture.
- **Create.** `pyproject.toml` declaring `requires-python = ">=3.9"` and no runtime dependencies; the
  ten empty packages; `tests/` tree; `docs/CONTRACT_PIN.md` with the record structure of Section 22.4;
  CI running lint plus tests on Python 3.9.18 on both Linux and Windows; `tests/architecture/` with the
  dependency-rule scanner.
- **Depends on.** Access to the deployment's normal submission path. **Not** on access to its source
  tree, installation metadata, or release identity — those are recorded as unknown and block nothing
  (Section 22.1, Q1).
- **Tests.** Architecture scanner runs and passes on an empty tree; a CI check asserts the interpreter
  is 3.9.x and that no 3.10-only construct is present.
- **Exit criteria.** `pytest` is green on 3.9.18 on both platforms, and `CONTRACT_PIN.md` records either
  a verified format with its evidence, or an explicit statement that no probe has yet succeeded — in
  which case `VersionPolicy` stays `Unverified` and generation remains blocked (Section 10.3) while every
  other phase proceeds normally. The unknown release identity is recorded as unknown and is not a
  blocker.

### Phase 1 — Rule catalogue as data

- **Objective.** Transcribe the specification's validation matrix into a machine-readable catalogue
  before writing any checking code, so coverage is measurable from the start.
- **Create.** `validation/catalogue.py` with every rule's id, tier, severity policy, spec citation,
  evidence status, and mapping ids — `check` implementations still absent.
- **Tests.** Every `spec_ref` resolves to a real heading in `AUTHORITATIVE_SPEC.md`; every rule whose
  evidence is `UNRESOLVED` has `INFO`-only severity; no rule is missing a citation.
- **Exit criteria.** The catalogue enumerates every row of the specification's validation matrix, and
  the deliberately non-promoted items appear as `INFO`-only entries.

### Phase 2 — Identity

- **Objective.** One authority for identifiers, before anything can be tempted to grow its own.
- **Create.** `identity/` — `EntityId`, `Multiplicity`, `IdAllocator`, `IdentityRegistry`.
- **Tests.** Allocation determinism, progression past the single-character range, collision refusal,
  rename rewrite maps, clone independence, property test for uniqueness under arbitrary operation
  sequences.
- **Exit criteria.** No other module needs to know how an identifier is formed.

### Phase 3 — Canonical model

- **Objective.** A representation in which the contract's dangerous states are unrepresentable.
- **Create.** `model/` — value types, presence algebra, the alignment/reference/representation sum
  types, the four record families, `Linkage`, `Configuration`, `FormatTarget`, the traceability
  registry.
- **Tests.** Construction invariants; the half-set alignment combination is uninstantiable; the
  no-alignment family has no such field; equality and hashing are stable; registry completeness.
- **Exit criteria.** A full configuration can be constructed in code with no validation, no wire
  concepts, and no IO.

### Phase 4 — Validation engine and rules

- **Objective.** The single gate before generation.
- **Create.** `validation/report.py`, `ports.py`, `engine.py`, `rules/` implementing every catalogue
  entry.
- **Tests.** `contract/` and `negative/` with the two meta-tests from Section 18.3; fake filesystem
  and absent-probe paths; skip reporting.
- **Exit criteria.** Every catalogue rule executes and is covered both ways; nothing enforces an
  unresolved item as an error.

### Phase 5 — Transformation

- **Objective.** The contract mapping, in one place, pure.
- **Create.** `transform/` — `WireDocument`, the field-mapping tables per family and root, presence
  emission, index splitting, multiplicity form, version selection.
- **Tests.** Row-level mapping tests; presence-preservation and index-preservation property tests;
  version-selection cases including a pinned version below a used feature; totality on validated
  input.
- **Exit criteria.** A validated configuration becomes a wire document; no wire field name exists
  outside this module.

### Phase 6 — Serialization

- **Objective.** Deterministic bytes.
- **Create.** `serialize/encode.py`.
- **Tests.** Cross-process byte determinism, escaping, ordering stability, trailing newline, no
  environment-derived content.
- **Exit criteria.** `encode(to_wire(c))` is byte-stable; the first `golden/external/` fixtures pass.

### Phase 7 — Variants

- **Objective.** Many related configurations from one base, safely.
- **Create.** `variants/` — edit vocabulary, `VariantSpec`, `expand`, `Lineage`; plus the VARIANT-tier
  rules (drift, identity stability, seed stability) added to `validation`.
- **Tests.** `variant/` — isolation, inheritance, expansion determinism, drift detection catches an
  undeclared change, lineage fingerprints.
- **Exit criteria.** Editing one variant provably cannot change a sibling or the base, and an
  undeclared difference is reported.

### Phase 8 — Output generation

- **Objective.** Predictable artefacts on disk.
- **Create.** `output/` — `slug`, naming, `OutputPlan`, `OverwritePolicy`, `PathPolicy`, atomic
  writer, manifest builder.
- **Tests.** Planning and collision logic against a fake filesystem; each overwrite policy; each path
  policy; atomicity under a simulated failure; manifest determinism excluding `run_info`; naming
  injectivity property test.
- **Exit criteria.** A set of variants becomes a reviewed plan and then a directory tree whose names
  a user can interpret without opening a file.

### Phase 9 — Persistence

- **Objective.** Reopen and continue work.
- **Create.** `persistence/` — project schema, save, load, upgrade step registry, refusal of unknown
  future versions.
- **Tests.** Round-trip fidelity including presence states and identifiers; corrupted-file handling;
  future-version refusal; fixture-based compatibility.
- **Exit criteria.** `load(save(p))` produces byte-identical generated output to `p`.

### Phase 10 — Application services

- **Objective.** One API for any front end, with the pipeline order fixed in one place.
- **Create.** `app/` — the five services and their result objects.
- **Tests.** `e2e/` service-level workflows, both the happy path and the blocked-by-errors path.
- **Exit criteria.** The complete pipeline runs headlessly with no UI present.

### Phase 11 — Terminal wizard

Split into three sub-phases so that the step machine is proven before any terminal code exists, and
the plain renderer is proven before the full-screen one.

**11a — Step machine and formatting (no terminal).**

- **Create.** `ui/steps/` — the fourteen steps, entry conditions, field visibility, answer handling,
  jump-to-field resolution from a `FieldPath`. `ui/present/` — label resolution, width-aware layout,
  sequence rendering with position rulers, finding formatting.
- **Tests.** Step-machine and formatting tiers of Section 18.8; a test that every user-visible string
  resolves through the registry or a rule message; a test that `ui/steps/` and `ui/present/` import no
  terminal library.
- **Exit criteria.** The entire workflow can be driven programmatically with no terminal present, and
  every finding resolves to a reachable prompt.

**11b — Platform layer, plain-line renderer, and input routes.**

- **Create.** `ui/render/platform.py` (Section 16.10), `ui/render/plain.py`,
  `ui/render/noninteractive.py`, the capability probe, all three long-text routes with the paste route
  as the default, line-ending detection, the session journal, signal handling, exit statuses.
- **Tests.** Plain-line snapshot transcripts on both platforms, capability-probe matrix including the
  legacy-Windows-console and non-UTF-8 cases, non-interactive behaviour, paste and file and editor
  round-trips, line-ending handling, position-entry behaviour, the content-preservation property test,
  platform-layer tests on both hosts, signal and resume tests, and the wizard-level end-to-end test of
  Section 18.9.
- **Exit criteria.** The full workflow is completable on Python 3.9.18 with **no optional package
  installed**, on a Windows console, on a plain `TERM=dumb` Linux terminal, and safely refused inside a
  batch job — producing byte-identical output to the service-level path in every interactive case. This
  is the phase that proves the application is complete without any third-party dependency.

**11c — Full-screen renderer.**

- **Create.** `ui/render/fullscreen.py` — persistent header and hint line, numbered list navigation,
  inline help, path completion, bracketed paste, resize handling, internal pager for the inspector.
- **Tests.** Full-screen tier of Section 18.8, on both platforms.
- **Exit criteria.** The full-screen renderer completes the same transcript as the plain renderer with
  no behavioural difference, and degrades to plain when the probe says so.

Across all three: no JSON, no identifiers, and no index arithmetic are exposed at any point.

### Phase 12 — Hardening and contract regression

- **Objective.** Prove the whole thing, then keep it proven.
- **Create.** The optional external-verification tier; the complete golden fixture set with
  provenance labels; a user-facing quick-start covering the Windows-authoring to Linux-execution
  transfer.
- **Tests.** Full suite on Python 3.9.18 on both platforms, plus the optional tier where the
  environment allows; cross-platform byte-identity re-check; determinism re-run.
- **Exit criteria.** Every item in Section 24 is demonstrable, and every architecture test passes.
- **Explicitly out of scope here.** Distribution packaging beyond the console entry point, and any
  batch front end. Both are deferred by decision (Section 22, Q14 and Q15) and neither may influence
  the core architecture.

---

## 22. Decisions and remaining verification items

Every question is resolved. The external system is treated as a black box (Section 10.4): its internal
release identity is unobtainable and is not required, and the one fact the builder genuinely needs — 
which input format the deployment accepts — is established by observation in Phase 0.

### 22.1 Status table

| # | Status | Resolution |
|---|---|---|
| Q1 | RESOLVED — not required | The deployment's internal software release is unavailable and is treated as unknown deployment metadata. It is **not** a prerequisite for implementation and **not** a blocker. The builder targets the observable external contract, not the internal release identity. Never inferred from the input format version. If the deployment happens to report a version through its normal user-facing interface or job output, that is recorded as supplementary evidence only (Section 22.4). |
| Q2 | RESOLVED — verified empirically | The target input format is established by submitting a minimal valid input through the real execution path and observing that it is accepted. The version value carried by that verified input becomes the builder's pinned target. No further versions are assumed without their own direct evidence (Sections 10.3, 22.4). |
| Q3 | RESOLVED | The external system's own parser is optional. The core test suite is complete without it; if present it adds a verification tier (Section 18.5). Never a runtime dependency. |
| Q4 | RESOLVED | A chemistry-notation parser is optional. Absent, the application is fully functional and the one rule behind the port is advisory (Section 9.6). |
| Q5 | RESOLVED | Deterministic monotonic identifier allocation through one `IdAllocator`; the progression itself is an isolated implementation detail (Section 8.1). |
| Q6 | RESOLVED | Identifier ordering carries no semantic meaning. Determinism serves reproducibility only, and no downstream ordering dependency is introduced (Section 8.1.1). |
| Q7 | RESOLVED | Progressive disclosure: required and common information first, advanced settings one keystroke away, nothing permanently hidden (Section 16.4). |
| Q8 | RESOLVED | Conservative, shallow preflight: path validity, existence, readability, non-emptiness, documented file requirements, execution-host resolvability. No reimplementation of external semantics (Section 9.2). |
| Q9 | RESOLVED | Cross-machine portability is a normal requirement. `CopyIntoAssets` is the default path policy and emitted paths are relative and forward-slashed (Sections 4.2, 13.5). |
| Q10 | RESOLVED | **Python 3.9.18** is the baseline. Core dependencies: none beyond the standard library. `prompt_toolkit` is optional and enhances one renderer only (Sections 4, 4.1, 16.7). |
| Q11 | RESOLVED | Authoring and execution normally occur on different machines. Treated as the expected workflow throughout, not an edge case (Section 4.2). |
| Q12 | RESOLVED | The builder is an authoring application and is not designed around interactive sessions on a shared login node. Remote use is supported but not assumed (Section 16.0). |
| Q13 | RESOLVED | An external editor is optional. Paste and read-from-file are built in; if no editor exists the route is simply not offered (Section 16.5). |
| Q14 | RESOLVED | No batch front end in the initial implementation. The service layer stays front-end agnostic so one could be added later without a second pipeline (Section 22.3). |
| Q15 | RESOLVED | Packaging is deferred. Assume a normal Python 3.9.18 environment; distribution format is decided after the core is stable and must not shape the architecture. |
| Q16 | RESOLVED | Preserve supplied content and warn. `CRLF` is detected and reported, never silently normalized; validation decides whether it is actually invalid (Section 16.5). |
| Q17 | RESOLVED | Windows authoring, Linux execution, as the expected workflow. Portability is first-class (Sections 4.2, 13.5). |

### 22.2 Known project decisions

```text
External system        = black box; observable contract only
Deployed release       = unknown, not required
Target input format    = empirically verified, then pinned
Python baseline        = 3.9.18
Core dependencies      = standard library only
Authoring platform     = Windows (Linux equally supported)
Execution platform     = Linux
Portability            = required, first-class
Primary UI             = terminal wizard, plain-line renderer guaranteed
External parser        = optional (extra test tier)
Chemistry parser       = optional (strengthens one rule)
External editor        = optional (convenience route)
Batch front end        = not in initial implementation
Identifier allocation  = deterministic, monotonic, no ordering semantics
Preflight depth        = shallow and conservative
User content           = preserved, never rewritten
Packaging              = deferred
```

### 22.3 What "no batch front end" does and does not mean

Not building one now is a scope decision, not an architectural one. The application layer already has
no knowledge of its caller (Section 15), so a future non-interactive front end would reuse the same
canonical model, identity authority, validation, transformation, variant generation, serialization, and
file generation. Two constraints protect that:

- No second pipeline may be created. Any future front end calls `app` services, exactly as the wizard
  does.
- `NonInteractiveRenderer` is not that front end. It exists to refuse safely when no terminal is
  attached (Section 16.7), and it does not author configurations from a parameter file.

### 22.4 Phase 0 contract probe

One observation establishes the contract target. It is a **human task**, performed once up front and
repeated only on the triggers listed below — never a feature of the application: the builder does not
submit or execute anything (spec §21 non-goals, Section 19).

**Procedure**

1. Hand-write a minimal input in the intended format — valid, and no larger than it needs to be to be
   valid. Minimal matters: a large input that fails leaves you guessing which part was rejected.
2. Place it in the deployment's normal submission/input location.
3. Execute it through the **same path real jobs use**. A special-case invocation would evidence a
   different thing than the one being tested.
4. Observe the result. Passing the deployment's input validation and submission stage is the evidence
   sought. Full downstream completion is welcome confirmation but is not what is being established.
5. Record the outcome in `docs/CONTRACT_PIN.md`.

**What the observation does and does not prove.** It proves that this deployment accepts input in the
format that was submitted. It does not prove that any other version is accepted, does not reveal the
internal release, and does not validate any field rule beyond those the probe input happened to
exercise — field-level rules come from the specification, not from this observation (Section 2.2).

**`docs/CONTRACT_PIN.md` record structure**

| Field | Content |
|---|---|
| Observed input format | The dialect and the version value carried by the accepted input. This becomes the pinned target. |
| Evidence source | What was submitted and through which execution path, with the probe input retained as a fixture. |
| Date tested | The date the observation was made. |
| Execution outcome | Whether acceptance was confirmed by successful execution through the real path, and how far the run proceeded. |
| Unknown deployment metadata | Explicitly listed: internal software release identity; installation metadata; any other accepted format versions. Recorded as **unknown**, never as a guess. |
| Supplementary evidence | Any version string the deployment volunteers through its normal user-facing interface or job output. Informational; it does not become a pin and nothing depends on it. |

The retained probe input becomes a golden fixture with `external` provenance (Section 18.4), since it is
the one input known to have been accepted by the real system.

**Re-probing.** The pin is a dated observation of a system that can be upgraded without notice. The
record is re-established when the deployment is known or suspected to have changed, when an input the
builder generated is rejected, or when a feature is needed that the pinned version does not cover. A
stale pin is visible because every generated file's manifest names the pin record behind it.

**Supporting environment checks**, neither of which blocks the architecture:

- Confirm Python 3.9.18 is available where the builder will run, and record the interpreter path used.
- Record which optional components are present — a chemistry parser, an editor, and any local copy of the
  external system's own input parser. On a black-box deployment the last of these is expected to be
  absent; the core test suite is complete without it (Section 18.5).

### 22.5 Items the specification resolves as non-rules

Deliberately not open questions, because the specification already declines to promote them: identifier
uniqueness or ordering expectations beyond what the contract states, and the project's fixed seed-count
policy. Both are adjustable project policies (Sections 9.3, 12.5), never contract gates.

---

## 23. Risks and mitigations

| Risk | How it would show up | Architectural mitigation |
|---|---|---|
| Contract drift: code diverges from the specification over time | A rule silently stops matching the contract | Every rule carries a spec citation; a test asserts citations resolve; the catalogue is data, reviewed as a unit |
| Representation collapse: omitted/empty/populated merged | The external system behaves differently than the user expected, silently | Presence algebra plus purpose-built sum types; `Optional` banned on contract-bearing fields by an architecture test; a presence-preservation property test |
| Index-base confusion | Off-by-one errors that produce valid-looking but wrong files | Distinct nominal types for the two bases; pairs instead of parallel arrays; an index-preservation property test asserting no arithmetic occurs |
| Duplicate authority: a second place builds wire output | Two code paths diverge; one is fixed and the other is not | Authority map; architecture test that wire field names appear only in `transform`; `ui` forbidden from importing `transform`/`serialize`/`output` |
| Variant mutation bleed | One variant's edit silently alters a sibling or the base | Frozen model types throughout; per-variant registry clones; isolation property test over arbitrary edit sequences |
| Silent variant drift | An unintended factor differs between variants, invalidating a comparison | VARIANT-tier drift rule comparing wire documents against the base, reporting anything not declared as an edit |
| Nondeterministic output | Golden tests flake; two runs disagree; results are not reproducible | No clock/host/random data in generated files; fixed encoding policy; ordering owned by `transform`; cross-process determinism test; time-varying manifest data isolated in `run_info` |
| UI/business-logic coupling | Rules get implemented in a prompt handler and bypassed elsewhere | `ui` may import only `app` and the registry; services return results; architecture test enforces the import rule |
| Validation duplication | The same rule enforced in two places with two behaviours | One catalogue, one engine; model raises only on invariants that are structurally impossible to violate, not on contract rules |
| Over-abstraction | A generic framework nobody can follow | Ten modules, fixed; families are concrete separate types; every abstraction in this plan states the specific bug it prevents; new modules require an entry here |
| Domain leakage into internals | Scientific vocabulary spreads through control flow, then becomes wrong | Terminology confined to the registry and rule metadata; mapping IDs used for traceability; the mapping table stays in `DOMAIN_MAPPING.md` |
| Cryptic UI as a side effect of neutral internals | Users cannot understand their own configuration | Registry-resolved labels are mandatory; a test asserts every user-visible string comes from the registry or a rule message |
| Terminal capability assumptions | Garbled tables, invisible prompts, or unreadable output on a cluster terminal | Capability probe with three renderers; no colour-only meaning; ASCII glyph set always available; documented minimum width with a degraded layout; probe result logged; `--plain` and `--no-color` overrides |
| Plain renderer becomes second-class | HPC users get a worse or incomplete workflow than the developer's local terminal | One pure step machine drives all renderers; the wizard-level end-to-end test runs through the plain renderer and asserts byte-identical output; the plain transcript is the snapshotted one |
| Hanging in a batch job | A job waits forever on a prompt nobody can answer, burning allocation | `NonInteractiveRenderer` is selected when `stdin` is not a TTY and never prompts; it reports missing inputs and exits with a distinct status; tested |
| Lost work when a session drops | Hours of configuration vanish with the SSH connection | Session journal after every completed step; resume offer on restart; explicit record that unsaved changes existed; the project file remains the only intent representation |
| Long content mangled on the way in | A pasted sequence is clipped by the client, or partly interpreted as commands, silently corrupting a configuration | Bracketed paste where supported and explicit multi-line termination where not; a received-content summary echoed before acceptance so clipping is caught at entry; a content-preservation property test asserts byte-for-byte arrival through every route |
| Line-ending divergence between platforms | A value gains `CRLF` because it was pasted from Windows, changing content in a way nobody notices | Detection with an explicit warning; one documented policy applied in one place for all three input routes; preserve-and-warn as the default because it cannot alter content; Q16 open until settled |
| Platform-dependent generated output | A file built on Windows differs from one built on Linux, breaking reproducibility and golden tests | `serialize` fixes `LF`, UTF-8, no BOM, and binary-mode writes; emitted paths always use forward slashes; CI runs golden and serialization tiers on both platforms and treats any difference as a failure |
| Case-only filename collisions | Two variants coexist on Linux and silently overwrite each other on Windows | Collision detection is case-insensitive everywhere, and generated names use a character set legal on both filesystems |
| Non-portable paths in generated files | A configuration authored on Windows emits a drive-letter path that is meaningless on the execution host | Advisory finding naming the offending path and the two policies that fix it; `CopyIntoAssets` recommended as the default |
| Platform branching spreading through the code | Small `if windows` checks accumulate until behaviour silently differs | One platform module (Section 16.10); an architecture test forbids `sys.platform` and `os.name` anywhere else |
| Step machine acquiring a rendering dependency | Navigation logic becomes untestable without a terminal, then untested | Architecture test forbids terminal-library imports in `ui/steps/` and `ui/present/` |
| Environment-specific failures on shared systems | Quota, read-only filesystem, or missing editor surface as crashes | Each is an explicit failure class (Section 17) with a named path and a remedy; terminal-environment problems degrade rather than terminate; the state directory is platform-appropriate, small, and pruned |
| Unclear persistence semantics | Users confuse their project file with generated output, or lose intent | Separate format, separate extension, separate version axis, explicit save, load-time validation through the same constructors |
| Enforcing an unestablished rule | The builder rejects configurations the external system would accept | Evidence status is stored per rule; `UNRESOLVED` items are `INFO`-only, enforced by a catalogue test |
| Wrong dialect emitted | Files rejected by the external system despite passing local checks | `Dialect` is a single-member enumeration; a CONTRACT rule asserts it; no converter to the other dialect exists in the codebase |
| Partial or destructive writes | A crash leaves a half-written input file, or an existing file is destroyed | Plan-then-execute; atomic write-and-rename; `Fail` is the default overwrite policy; all-or-nothing conflict handling |
| Scope creep into downstream analysis | The builder starts interpreting results | Section 19 states the boundary; no module reads results; no dependency on any analysis library |
| Guessing an unverified format version | Files are emitted that the deployment rejects, or worse, silently misreads | `VersionPolicy` starts at `Unverified` and blocks generation with an explanatory finding; the pinned version must come from an observed acceptance recorded in `CONTRACT_PIN.md` (Sections 10.3, 22.4) |
| Blocking the project on unobtainable deployment metadata | Implementation stalls waiting for a release identity nobody can read | The internal release is recorded as unknown and is not an input to any design decision (Sections 10.4, 22.1 Q1); only the observed input format gates generation, and every other phase proceeds regardless |
| A stale contract pin after a silent deployment upgrade | Generated files start being rejected, and nobody knows which observation they were based on | The pin is a dated observation with a named re-probe trigger; every generated file's manifest records the pin identifier behind it, so staleness is visible at the artefact rather than inferred |
| Reconstructing the black box | The builder drifts toward emulating the external system, becoming a second authority for rules it cannot see | Section 10.4 states the boundary; field rules come only from the specification catalogue; preflight is shallow by decision (Section 9.2); no module submits, invokes, or reads the execution system (Section 19) |
| An optional dependency becoming required in practice | A user without `prompt_toolkit`, a chemistry parser, or an editor finds the application unusable | Each optional component sits behind one port with a documented fallback; the plain-line renderer is stdlib-only and carries the wizard-level end-to-end test; the editor route is hidden when absent; a CI job runs the whole suite with no optional package installed |
| A 3.10-only construct slipping in | The application fails to import on the target interpreter | Baseline stated once (Section 4.1); `requires-python = ">=3.9"`; CI runs the suite on 3.9.18 specifically; the fold pattern removes the main temptation to reach for `match` |
| Preflight depth creeping upward | Validation slowly reimplements external semantics, producing false positives that train users to ignore findings | Preflight is defined as shallow and local (Section 9.2); anything deeper belongs to the optional verification tier; preflight defaults to `WARNING` and is switchable |
| Silent content modification | A convenience normalization changes user data, invalidating a scientific input | Preserve-and-warn is the standing decision (Sections 16.5, 22 Q16); a content-preservation property test asserts byte-for-byte arrival through every route |

---

## 24. Definition of done

### User-facing

A non-programmer can, from a terminal over SSH, without writing any file by hand:

1. launch the application with one command — on a remote Linux system over SSH, on a local Linux
   terminal, or on a Windows terminal — with no display and no root access;
2. create a configuration and name it;
3. add and configure records of every supported family;
4. add and configure components, including the ion case, through labelled choices;
5. add modifications and special cases by picking a position and a chemistry, including custom
   chemistry definitions;
6. declare external files and choose how paths are written;
7. set the reproducibility seed set;
8. validate and receive findings that state what is wrong, where, why, and what to do;
9. create several variants through a factor picker, without duplicating anything by hand;
10. review each variant, its declared differences, and exactly what will be written;
11. generate the external input files;
12. find the outputs in a predictable, self-describing directory layout with a manifest;
13. reopen the project later and continue editing;
14. survive a dropped connection without losing more than the step in progress;
15. supply long content by pasting it, or by pointing the wizard at a file they uploaded, and see
    confirmation of what was received;
16. transfer the output directory to the Linux execution system and have every referenced resource
    still resolve;
17. do all of the above on a limited terminal (`TERM=dumb`, no colour, 80 columns), on a Windows
    console, and with no optional package installed, with the same workflow and byte-identical
    resulting files.

### Technical

- one canonical internal model, with the contract's dangerous states unrepresentable;
- one identifier authority;
- one validation authority, with every rule traceable to a specification section and an evidence
  status;
- one transformation layer;
- one variant-generation mechanism, with isolation guaranteed structurally;
- one serialization authority;
- deterministic, byte-reproducible output;
- explicit contract tests, negative tests, variant tests, serialization tests, and end-to-end tests,
  with meta-tests guarding coverage;
- dependency rules and single-authority rules enforced by automated architecture tests;
- a complete workflow on Python 3.9.18 with no third-party package installed, every optional component
  behind a port with a documented fallback;
- generation blocked rather than guessed until a format has been observed to be accepted by the
  deployment, with every generated file traceable to that observation;
- a pure step machine that drives every renderer, with terminal libraries confined to `ui/render`;
- three renderers covering a capable terminal, a limited terminal, and no TTY at all, with the
  wizard-driven path producing byte-identical output to the service-driven path;
- no process that can block on a prompt when no terminal is attached;
- generated files byte-identical across host platforms, with platform differences confined to one
  module and asserted by an architecture test;
- no wire construction in the UI, no contract logic in the serializer or filesystem layer;
- domain terminology confined to the traceability registry and rule metadata, with `MAP-###`
  cross-references to `DOMAIN_MAPPING.md`;
- every unresolved specification item recorded in Section 22 rather than implemented as a guess.

### Not done by this system

Result parsing, quality-measure interpretation, statistics, visualization, scientific judgement,
execution scheduling, and any conversion to the second external dialect. These are outside the
boundary in Section 19 and no module may acquire them without amending this plan.