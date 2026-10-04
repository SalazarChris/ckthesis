# AUTHORITATIVE_SPEC

## 1. Scope

This specification defines the external contract that a builder must target when generating **standalone/open-source AlphaFold 3 (`alphafold3` JSON dialect) input**.

It covers:

- accepted top-level JSON structure;
- supported molecular entity types;
- entity fields, representations, and constraints;
- polymer modifications/PTMs;
- ligands, ions, SMILES, CCD, and user-provided CCD;
- MSA and template representations and external-file paths;
- covalent bonds;
- identifiers and indexing conventions;
- model seeds and reproducibility;
- input/output naming and relationships relevant to downstream traceability;
- versioning and the distinction between the standalone AF3 JSON format and AlphaFold Server JSON;
- validation rules that are directly evidenced by the official AF3 documentation/source;
- builder requirements derived from those external rules.

It does **not** define the implementation architecture of the user's builder. Internal classes, enums, data models, registries, menus, UI choices, and validation modules are recommendations only unless explicitly marked as external AF3 contract.

### Evidence-status vocabulary

- **CONFIRMED** — directly supported by current official AF3 source code or official AF3 documentation.
- **DOCUMENTED** — explicitly stated in official documentation but not additionally cross-checked in source in this research pass.
- **INFERRED** — logically derived from confirmed/documented behavior; useful for builder design but not an AF3 rule by itself.
- **AMBIGUOUS** — official sources contain conflicting/stale wording or the exact boundary is unclear.
- **UNRESOLVED** — not established from authoritative sources reviewed; the builder must not invent a rule.

---

## 2. Source Hierarchy

### Primary sources used

| Source ID | Authority | Use |
|---|---|---|
| S1 | Official `google-deepmind/alphafold3` `docs/input.md` | Human-facing standalone AF3 input contract, representations, examples, compatibility, paths, bonds, templates, MSA, CCD. |
| S2 | Official `google-deepmind/alphafold3` `src/alphafold3/common/folding_input.py` | Executable input datamodel and validation behavior. |
| S3 | Official `google-deepmind/alphafold3` `docs/output.md` | Output files, seed/sample naming, confidence/ranking outputs. |
| S4 | Official `google-deepmind/alphafold3` `run_alphafold_test.py` | Official example smoke coverage and expected output layout. |
| S5 | Official `google-deepmind/alphafold` `server/README.md` | AlphaFold Server JSON contract where it intentionally differs from standalone AF3. |
| S6 | Official `google-deepmind/alphafold` `server/example.json` | Concrete Server JSON example. |
| S7 | Official `google-deepmind/alphafold3` releases | AF3 software release/version context. |

### Authority rule

When S1 and S2 conflict, prefer **S2 executable behavior**, then record the discrepancy. A stale documentation sentence must not override the parser.

When standalone AF3 and AlphaFold Server differ, they are **different external contracts** and must not be collapsed into one schema.

---

## 3. External System Version

The latest official release listed by the AF3 repository at the time of this research is **AlphaFold v3.0.4**. The release page also identifies v3.0.4 as the latest release and notes that the 3.0.x line shares compatible model parameters. S7.

The **input JSON schema version** is a different concept from the software release version. The standalone `alphafold3` dialect currently recognizes JSON versions `1, 2, 3, 4`; version 4 adds the textual `description` field for protein, RNA, DNA, and ligand entities. S1, S2.

### Target recommendation

For a current builder targeting the current standalone AF3 contract:

- software target: pin a concrete AF3 release/commit rather than an unpinned branch;
- JSON dialect: `alphafold3`;
- JSON version: `4` when using current AF3 features;
- do not treat JSON `version` as synonymous with the AF3 software release.

**Status:** CONFIRMED.

### Important documentation discrepancy

In the rendered `input.md`, one descriptive bullet at the top-level field list still says the `version` field “must be set to 1 or 2”, while the immediately following version section explicitly documents versions 1–4, and the source code defines `JSON_VERSIONS = (1, 2, 3, 4)`. This is an official documentation inconsistency. The builder should follow the executable source plus the explicit version-history section: version 4 is valid.

**Status:** AMBIGUOUS in wording; **CONFIRMED** for accepted source-code versions.

---

## 4. Top-Level AF3 Contract

The standalone AF3 JSON is a single JSON object with the following conceptual fields:

```json
{
  "name": "Job name",
  "modelSeeds": [1, 2],
  "sequences": [
    {"protein": {...}},
    {"rna": {...}},
    {"dna": {...}},
    {"ligand": {...}}
  ],
  "bondedAtomPairs": [],
  "userCCD": "...",
  "userCCDPath": "...",
  "dialect": "alphafold3",
  "version": 4
}
```

| Field | Type | Required | Core rule | Status |
|---|---|---:|---|---|
| `name` | string | yes | Must be non-empty and yield a valid sanitized name. | CONFIRMED |
| `modelSeeds` | list[int] | yes | At least one seed; current source validates unsigned 32-bit range. | CONFIRMED |
| `sequences` | list | yes | Contains protein/RNA/DNA/ligand entities. | CONFIRMED |
| `bondedAtomPairs` | list | no | Covalent atom-pair declarations. | CONFIRMED |
| `userCCD` | string | no | Inline user CCD; mutually exclusive with `userCCDPath`. | CONFIRMED |
| `userCCDPath` | path string | no | Path to CCD mmCIF; mutually exclusive with `userCCD`. | CONFIRMED |
| `dialect` | string | yes | Must be `alphafold3`. | CONFIRMED |
| `version` | int | yes | Current accepted standalone values: 1–4. | CONFIRMED |

The official parser explicitly rejects unexpected keys within entity dictionaries. This means a builder should serialize only fields supported for the selected AF3 JSON version/entity representation.

**Status:** CONFIRMED.

---

## 5. Data Families / Entity Types

The standalone AF3 `sequences` array supports four entity families:

1. **Protein**
2. **RNA**
3. **DNA**
4. **Ligand**

There is no separate standalone AF3 input entity type for an ion. **Ions are represented as ligands**, typically using a CCD code such as `MG`, `NA`, or `CL`. S1, S2.

### 5.1 Protein

Conceptually:

```json
{
  "protein": {
    "id": "A",
    "sequence": "...",
    "modifications": [
      {"ptmType": "...", "ptmPosition": 10}
    ],
    "description": "...",
    "unpairedMsa": "...",
    "pairedMsa": "...",
    "unpairedMsaPath": "...",
    "pairedMsaPath": "...",
    "templates": []
  }
}
```

Core fields:

- `id`
- `sequence`
- optional `modifications`
- optional `description` (JSON version 4)
- optional MSA fields
- optional templates

Protein sequence input uses one-letter standard amino-acid codes. The modification representation is a **separate location-bearing field**; it does not modify the textual sequence itself. Internally, AF3 converts the modified position into a CCD-coded sequence for processing.

**Status:** CONFIRMED.

### 5.2 RNA

Core fields:

- `id`
- `sequence`
- optional `modifications`
- optional `description`
- optional `unpairedMsa` or `unpairedMsaPath`

RNA sequence uses `A`, `C`, `G`, `U`. RNA modifications use `modificationType` + 1-based `basePosition`.

**Status:** CONFIRMED.

### 5.3 DNA

Core fields:

- `id`
- `sequence`
- optional `modifications`
- optional `description`

DNA sequence uses `A`, `C`, `G`, `T`. DNA modifications use `modificationType` + 1-based `basePosition`.

There is no DNA `unpairedMsa`, `pairedMsa`, `templates`, or DNA-specific path field documented in the standalone AF3 input contract.

**Status:** CONFIRMED.

### 5.4 Ligand

Core fields:

- `id`
- exactly one ligand representation: `ccdCodes` or `smiles`
- optional `description`

A ligand can contain one CCD component or multiple CCD components. Multiple components can be connected with `bondedAtomPairs`.

**Status:** CONFIRMED.

---

## 6. Representations

AF3 frequently provides more than one representation for the same abstract concept. The builder must preserve the distinction between **conceptual object** and **wire representation**.

### 6.1 Inline vs external file

| Concept | Inline | External path | Mutual exclusion |
|---|---|---|---|
| Protein unpaired MSA | `unpairedMsa` | `unpairedMsaPath` | yes |
| Protein paired MSA | `pairedMsa` | `pairedMsaPath` | yes |
| Template structure | `mmcif` | `mmcifPath` | yes, per template |
| User CCD | `userCCD` | `userCCDPath` | yes, root level |

Paths can be absolute or relative to the input JSON path. AF3 source also supports compressed external files for these path-based inputs (`gzip`, `xz`, `zstd`). S1, S2.

**Status:** CONFIRMED.

### 6.2 Absence vs empty value

AF3 distinguishes an **unset/`null`** MSA or template field from an explicitly empty field.

For protein MSA:

- both MSA fields unset/`null` → AF3 can build MSAs automatically;
- `unpairedMsa` non-empty + `pairedMsa` empty → use supplied unpaired MSA and no paired MSA;
- `pairedMsa` non-empty + `unpairedMsa` empty → paired-only expert case;
- both empty → fully MSA-free;
- both non-empty → fully user-supplied MSA.

For protein templates:

- omitted/`null` → template search is allowed;
- `[]` → explicit template-free operation;
- non-empty list → explicit templates.

RNA `unpairedMsa` similarly distinguishes automatic search (`null`/unset), MSA-free (`""`), and custom MSA (non-empty A3M).

**Status:** CONFIRMED.

### 6.3 Builder implication

Do not collapse `None`, empty string, empty list, and omitted field into one internal state. They represent different AF3 semantics.

**Status:** INFERRED from confirmed external behavior and is a REQUIRED builder-design implication.

---

## 7. Identifiers and Indexing

### 7.1 Entity IDs

Every entity in the standalone `sequences` list must have a unique identifier. The documented external form allows a string or a list of strings for homomeric copies. Each ID is an uppercase alphabetic identifier and is also used in the output mmCIF.

Examples:

```json
"id": "A"
```

or:

```json
"id": ["A", "B", "C"]
```

The multi-ID form means multiple copies of the same entity.

The executable internal model validates uppercase alphabetic IDs and rejects duplicate IDs after normalization of the parsed chain objects.

**Status:** CONFIRMED.

### 7.2 Residue/modification positions

Polymer modification positions are **1-based**.

Example:

```json
{"ptmType": "TPO", "ptmPosition": 101}
```

means the 101st residue of that polymer chain is represented by the supplied CCD modification code.

**Status:** CONFIRMED.

### 7.3 Template indices

Template `queryIndices` and `templateIndices` are **0-based**. The two arrays must be parallel mappings of equal length. Template indices must account for residues represented in the mmCIF residue table even when atom coordinates are unresolved.

**Status:** CONFIRMED.

### 7.4 Bond residue IDs

Within `bondedAtomPairs`, residue IDs are **1-based**. A single-residue ligand uses residue ID `1`.

**Status:** CONFIRMED.

### 7.5 Atom names

Bond endpoints use the entity/chain ID, residue ID, and an atom name. Atom naming is derived from the relevant CCD component. SMILES-only ligands cannot participate in explicit AF3 covalent bonds because SMILES does not provide the required named-atom addressing scheme.

**Status:** CONFIRMED.

### 7.6 No fixed 26-ID limit

The official Server converter documents a “reverse spreadsheet style” assignment extending beyond `Z`. Therefore a builder should not impose a 26-chain ceiling merely because the default visible IDs start at `A`.

**Status:** CONFIRMED for the Server converter; exact preferred standalone generation policy is a builder decision.

---

## 8. Modifications / Special Objects

### 8.1 Protein modifications

Protein modifications are expressed as:

```json
{"ptmType": "CCD_CODE_OR_CUSTOM_CODE", "ptmPosition": <1-based integer>}
```

The current AF3 source treats the modification code as a CCD component code and replaces the corresponding residue in its internal CCD-coded sequence representation.

The modification code should **not** be prefixed with `CCD_` in standalone AF3 input; the source explicitly rejects a protein PTM code beginning with `CCD_`. The same no-`CCD_` prefix rule is applied to RNA and DNA modification codes in the current source.

**Status:** CONFIRMED.

### 8.2 Biological residue vs modification identity

A builder must keep these concepts distinct:

- base/canonical polymer sequence residue;
- modification/CCD identity;
- polymer position at which the modified component replaces the canonical residue;
- optional custom CCD definition that supplies the chemistry.

Example conceptual record:

```text
base residue = T
position = 101
modification code = TPO
```

AF3 wire representation then uses:

```json
"sequence": "...T...",
"modifications": [{"ptmType": "TPO", "ptmPosition": 101}]
```

The sequence remains the canonical one-letter sequence while the modification field carries the chemical replacement.

**Status:** CONFIRMED externally; the internal separation is a recommended builder representation.

### 8.3 Custom polymer modifications

A user-provided CCD can define a non-canonical amino acid or nucleotide used through a polymer modification field. The `ptmType`/`modificationType` must match the custom CCD component ID. The custom CCD entry must represent an appropriate polymer-linked component, not a free non-polymer ligand, and its backbone/bond graph must be appropriate for the position.

**Status:** CONFIRMED.

### 8.4 Protein example relevant to phosphorylation

The official Server documentation lists `CCD_SEP` and `CCD_TPO` among allowed server PTM codes; in standalone AF3 these codes are represented without the `CCD_` prefix in the `ptmType` value (e.g. `SEP`, `TPO`) because the standalone parser rejects the `CCD_` prefix.

This is a concrete example of why Server JSON and standalone AF3 JSON must not be mixed.

**Status:** CONFIRMED.

---

## 9. Components / Ligands / Ions

### 9.1 Standard CCD ligand

Use:

```json
{"ligand": {"id": "L", "ccdCodes": ["ATP"]}}
```

CCD codes can also be combined in one ligand entity. If multiple components are meant to behave as one connected molecular assembly, explicit covalent bonds can be provided.

**Status:** CONFIRMED.

### 9.2 SMILES ligand

Use:

```json
{"ligand": {"id": "L", "smiles": "..."}}
```

A ligand may use **CCD codes or SMILES but not both**. The AF3 source also parses the SMILES through RDKit during input construction and rejects invalid SMILES.

SMILES must be valid JSON-escaped text.

**Status:** CONFIRMED.

### 9.3 User-provided CCD ligand

A custom ligand can be supplied by a user CCD plus a custom component code listed in `ccdCodes`.

This is the representation to prefer when:

- the molecule needs explicit atom names for covalent bonding;
- the user needs custom bond orders/atom names/ideal coordinates;
- RDKit conformer generation fails and ideal/reference coordinates are needed.

**Status:** CONFIRMED.

### 9.4 Ions

Standalone AF3 has no separate ion entity. An ion is a ligand. For example:

```json
{"ligand": {"id": "L", "ccdCodes": ["NA"]}}
```

or analogous valid CCD codes for other ions.

The Server format has a distinct ion entity representation, but its converter maps ions into AF3 ligands.

**Status:** CONFIRMED.

### 9.5 `userCCD` vs `userCCDPath`

Only one root representation may be used:

- inline `userCCD`, or
- external `userCCDPath`.

They are mutually exclusive.

**Status:** CONFIRMED.

### 9.6 Custom CCD naming

A custom CCD component code must not collide with existing CCD names. Official docs give examples such as `LIG-1` and warn against underscores because they can cause mmCIF issues.

**Status:** DOCUMENTED.

---

## 10. External Files and Paths

Supported external file references include:

| Input | Field | File format | Relative-path behavior | Compression |
|---|---|---|---|---|
| Protein unpaired MSA | `unpairedMsaPath` | A3M | relative to JSON or absolute | gzip/xz/zstd supported |
| Protein paired MSA | `pairedMsaPath` | A3M | relative to JSON or absolute | gzip/xz/zstd supported |
| RNA unpaired MSA | `unpairedMsaPath` | A3M | relative to JSON or absolute | gzip/xz/zstd supported |
| Protein template | `mmcifPath` | mmCIF | relative to JSON or absolute | gzip/xz/zstd supported |
| User CCD | `userCCDPath` | CCD mmCIF | relative to JSON or absolute | gzip/xz/zstd supported |

The parser resolves relative paths against the directory containing the input JSON.

### Important implementation boundary

The **serialized JSON contract** contains a path string; whether a builder should verify the path exists before saving is a builder validation policy. AF3 itself will later try to read the referenced resource.

**Status:** Path semantics CONFIRMED; builder preflight existence check INFERRED/RECOMMENDED.

---

## 11. MSA Contract

### Protein

Both `unpairedMsa` and `pairedMsa` are conceptually paired fields. If custom MSA is supplied, both fields must be represented as set values (possibly one empty string). The official docs explicitly warn against setting only one.

Custom A3M requirements include:

1. FASTA/A3M syntax;
2. first sequence exactly equals the query sequence;
3. after removing lowercase insertions, all sequences have the same length as the query.

**Status:** CONFIRMED.

### RNA

Only `unpairedMsa`/`unpairedMsaPath` is supported. Automatic, MSA-free, and custom-MSA states are distinguished by unset/null, empty string, and non-empty A3M respectively.

**Status:** CONFIRMED.

### DNA

No MSA fields are part of the standalone DNA entity schema.

**Status:** CONFIRMED.

### Pairing

For multimers, AF3 uses MSA pairing information when constructing concatenated MSAs. The official documentation recommends manual pairing through `unpairedMsa` plus an empty `pairedMsa` in expert cases and describes a `--resolve_msa_overlaps=false` execution setting for preserving carefully constructed pairing.

The builder should therefore not silently rewrite or “fix” user-supplied MSA content.

**Status:** AF3 behavior DOCUMENTED; builder preservation rule INFERRED/RECOMMENDED.

---

## 12. Structural Templates

Templates are supported **only on protein chains**.

Per-template representation:

```json
{
  "mmcif": "...",
  "queryIndices": [0, 1, 2],
  "templateIndices": [0, 2, 5]
}
```

or:

```json
{
  "mmcifPath": "template.cif",
  "queryIndices": [0, 1, 2],
  "templateIndices": [0, 2, 5]
}
```

Rules:

- `mmcif` and `mmcifPath` are mutually exclusive per template;
- mmCIF contains one protein chain;
- query and template index arrays are 0-based;
- they define a position-by-position mapping and therefore must have equal lengths;
- unresolved template residues still count for template indexing;
- current source documents up to 20 templates on a protein chain.

`templates: []` explicitly means no templates, while omission/`null` permits template search.

**Status:** CONFIRMED.

---

## 13. Covalent Bonds

`bondedAtomPairs` is an optional top-level list.

Each bond is:

```json
[
  ["CHAIN_ID", 145, "ATOM_NAME"],
  ["OTHER_CHAIN_ID", 1, "ATOM_NAME"]
]
```

The semantics are:

- entity ID corresponds to the entity's `id`;
- residue ID is 1-based;
- atom name is the CCD atom name;
- bonds are **always covalent**;
- other bond types are not supported;
- bonds may connect entities or components within a ligand entity;
- covalent bonds between or within polymer entities are not currently supported through this field;
- a SMILES-only ligand cannot be an endpoint because it lacks uniquely named atoms.

**Status:** CONFIRMED.

### Builder implication

Bond construction should be a separate domain operation because it references already-resolved entity IDs, residue positions, and atom names. It should not be encoded as a generic “relationship” that permits unsupported bond types.

**Status:** INFERRED/RECOMMENDED.

---

## 14. Reproducibility / Model Seeds

`modelSeeds` is the per-input list of random seeds used for model execution. The official docs state that if `n` seeds are supplied, AF3 produces predictions corresponding to those seeds.

Current source validation requires:

- non-empty list;
- each seed is an integer within unsigned 32-bit range `0..2^32-1`.

The source-level contract does **not** establish a requirement that seeds be unique, sorted, or generated in any particular order.

Therefore:

- non-empty: CONFIRMED;
- 32-bit unsigned range: CONFIRMED;
- exactly one prediction per seed: CONFIRMED at documentation level;
- uniqueness requirement: **UNRESOLVED / not established**;
- sorting requirement: **UNRESOLVED / not established**.

### Builder requirement for the thesis workflow

The project requirement that all variants use the **same fixed set of 10 seeds** is a comparison/reproducibility requirement imposed by the project, not an AF3 schema requirement.

**Status:** PROJECT-INFERRED, not an external AF3 rule.

### Server difference

AlphaFold Server permits an empty `modelSeeds` list to request automatic random seed assignment. Standalone `alphafold3` requires at least one specified seed; the converter can translate an empty Server list into a randomly selected standalone seed.

**Status:** CONFIRMED.

---

## 15. Variant-Relevant Fields

The following fields affect the molecular input and therefore are legitimate variant dimensions for a builder:

- protein/RNA/DNA sequences;
- polymer modifications;
- entity IDs and copy counts (structural identity, not necessarily scientific treatment);
- ligand CCD codes;
- ligand SMILES;
- user CCD content/path;
- bonded atom pairs;
- MSA representation and content/path;
- template list/content/path and residue mappings;
- random seeds;
- job name and descriptions (metadata/naming rather than molecular chemistry).

### Stable-factor principle

For a controlled model-comparison experiment, the builder should make it possible to hold all non-target fields constant across variants while changing only the intended experimental factor.

This is a **builder/experimental-design recommendation**, not an AF3 schema rule.

---

## 16. External Output Contract

Standalone AF3 output is organized around seed/sample results.

For an example with one seed and five samples, official output includes directories named like:

```text
seed-1234_sample-0/
seed-1234_sample-1/
...
seed-1234_sample-4/
```

Each sample directory contains:

- predicted model mmCIF;
- confidence JSON;
- summary confidence JSON.

At the job root, AF3 also writes:

- top-ranking prediction mmCIF (`<job_name>_model.cif`);
- top-ranking confidence JSON;
- top-ranking summary confidence JSON;
- data JSON with MSA/template data added by the data pipeline;
- ranking scores CSV;
- terms of use file.

Optional seed-level distograms/embeddings may also be present when corresponding execution flags are enabled.

**Status:** CONFIRMED.

### Output identifiers relevant to analysis

Seed and sample identifiers are visible in output paths, and official tests use the `seed-<seed>_sample-<index>` relationship. The latest release notes also mention chain IDs being added to summary confidence JSON for easier use.

**Status:** CONFIRMED for naming; exact complete output metadata schema is outside this builder input specification and should be parsed separately when analysis is implemented.

### Confidence caution

Official output documentation describes pLDDT, PAE, pTM, and ipTM as confidence measures. These are **predicted/confidence metrics**, not direct ground-truth accuracy or structural-change measurements.

**Status:** CONFIRMED as a conceptual boundary; scientific interpretation belongs to the analysis pipeline, not the input builder.

---

## 17. AF3 Server vs Open-Source AF3

These are distinct JSON dialects.

### Standalone AF3

- root is a single job object;
- `dialect = "alphafold3"`;
- entity type key names are `protein`, `rna`, `dna`, `ligand`;
- every entity needs an ID;
- ions are ligands;
- multiple inputs require multiple JSON files;
- supports the more expressive custom ligand/user-CCD/bond workflow.

### AlphaFold Server

- root is a list of job dictionaries;
- `dialect = "alphafoldserver"`;
- entity types are named differently, including separate ion handling;
- entity IDs are not user-specified in the same way;
- an empty `modelSeeds` is allowed for automatic random assignment;
- Server has a separate feature set, including its own treatment of glycans.

The official standalone parser contains a converter from Server format to standalone AF3 format.

**Status:** CONFIRMED.

### Builder consequence

The project must choose one target dialect at the serialization boundary. A builder that “mostly follows Server JSON” but emits `alphafold3` is a correctness risk.

**Status:** INFERRED/RECOMMENDED.

---

## 18. Versioning

There are two independent version axes:

1. **AF3 software release**, e.g. v3.0.4.
2. **Standalone AF3 JSON format version**, currently 1–4.

JSON version history documented by AF3:

| JSON version | Added capability |
|---:|---|
| 1 | Initial AF3 input format |
| 2 | External MSA/template path fields (`unpairedMsaPath`, `pairedMsaPath`, `mmcifPath`) |
| 3 | `userCCDPath` |
| 4 | textual `description` for protein/RNA/DNA/ligand |

**Status:** CONFIRMED.

### Version-selection rule

A builder should select the minimum JSON version that supports all chosen features **or** consistently target the current version 4. The project should not silently emit a higher/lower version unrelated to the features in use.

This is a builder policy derived from the documented version history.

**Status:** INFERRED/RECOMMENDED.

---

## 19. Validation Matrix

### Root-level validation

| Rule | Evidence | Status |
|---|---|---|
| JSON dialect is `alphafold3` | S1/S2 | CONFIRMED |
| JSON version supported values are 1–4 in current source | S2 | CONFIRMED |
| name is non-empty and sanitizable | S2 | CONFIRMED |
| at least one model seed | S1/S2 | CONFIRMED |
| seed range 0..2^32-1 | S2 | CONFIRMED |
| sequences is the entity container | S1/S2 | CONFIRMED |
| `userCCD` and `userCCDPath` mutually exclusive | S1/S2 | CONFIRMED |

### Entity validation

| Rule | Evidence | Status |
|---|---|---|
| entity families = protein/RNA/DNA/ligand | S1/S2 | CONFIRMED |
| entity IDs unique | S1/S2 | CONFIRMED |
| entity IDs uppercase alphabetic | S2 | CONFIRMED |
| protein sequence alphabetic | S2 | CONFIRMED |
| RNA sequence alphabetic / documented alphabet A,C,G,U | S1/S2 | CONFIRMED |
| DNA sequence alphabetic / documented alphabet A,C,G,T | S1/S2 | CONFIRMED |
| modification positions within sequence range | S2 | CONFIRMED |
| polymer modification codes must not start `CCD_` | S2 | CONFIRMED |
| ligand has exactly one of CCD codes or SMILES | S2 | CONFIRMED |
| invalid SMILES rejected | S2 | CONFIRMED |

### MSA validation

| Rule | Evidence | Status |
|---|---|---|
| protein unpaired/paired are both set or both unset | S1/S2 | CONFIRMED |
| inline/path pair is mutually exclusive per MSA | S1/S2 | CONFIRMED |
| custom A3M required for custom MSA | S1 | DOCUMENTED |
| query must be first MSA sequence | S1 | DOCUMENTED |
| custom MSA must form rectangular alignment after insertions removed | S1 | DOCUMENTED |

### Template validation

| Rule | Evidence | Status |
|---|---|---|
| templates are protein-only | S1 | CONFIRMED |
| `mmcif` and `mmcifPath` mutually exclusive | S1 | CONFIRMED |
| query/template indices are 0-based | S1 | CONFIRMED |
| query/template arrays are a parallel mapping | S1/S2 | CONFIRMED |
| up to 20 templates per protein chain | S2 docstring | CONFIRMED |

### Ligand / bond validation

| Rule | Evidence | Status |
|---|---|---|
| ions are ligands in standalone format | S1/S2 | CONFIRMED |
| SMILES ligand cannot be explicitly bonded | S1/S2 | CONFIRMED |
| bonded endpoints use chain/residue/atom triples | S1/S2 | CONFIRMED |
| bond residue IDs are 1-based | S1/S2 | CONFIRMED |
| all explicit bonds are covalent | S1 | CONFIRMED |
| polymer-polymer covalent bonds through this field unsupported | S1 | DOCUMENTED |

### Rules deliberately NOT promoted to confirmed AF3 requirements

- seed list uniqueness;
- seed sorting;
- project-specific chain-ID allocation algorithm;
- project-specific requirement to use exactly 10 seeds;
- biological validity of a requested PTM/site;
- scientific plausibility of any modification;
- requirement to create a `config.json`;
- requirement to avoid `config.json`;
- output analysis rules;
- structural-distance/RMSD interpretation rules.

These must remain project policies or analysis-layer concerns.

---

## 20. Derived Builder Requirements

The builder should expose abstractions corresponding to the actual AF3 domain rather than generic “data family” placeholders.

### Core capabilities

1. Create one canonical job configuration.
2. Add protein, RNA, DNA, and ligand entities.
3. Support single IDs and copy IDs.
4. Support polymer modifications with explicit position + chemical code.
5. Support ligand representation selection: CCD or SMILES.
6. Represent ions as ligand/CCD entities.
7. Support inline or file-backed MSA where AF3 allows it.
8. Support inline or file-backed templates where AF3 allows it.
9. Support inline or file-backed user CCD.
10. Support explicit covalent bonds using resolved chain/residue/atom identifiers.
11. Support fixed seed sets and preserve them across variants.
12. Validate before serialization.
13. Generate exactly the chosen AF3 dialect/version.
14. Preserve the distinction between omitted/null/empty values.
15. Produce deterministic JSON serialization for the same canonical configuration.
16. Make variant generation clone a canonical configuration rather than mutate shared base state.
17. Make naming, identifiers, and variant lineage inspectable.

### Canonical internal model recommendation

Use a domain model roughly equivalent to:

```text
AF3Input
  ├── metadata/name/version/dialect
  ├── model_seeds
  ├── entities[]
  │    ├── ProteinChain
  │    ├── RnaChain
  │    ├── DnaChain
  │    └── Ligand
  ├── bonded_atom_pairs[]
  └── user_ccd_source
```

This is a recommended abstraction, not a claim that these exact classes currently exist in the project.

### Variant requirement

The canonical model should be capable of expressing:

```text
Base configuration
        ↓ clone
Variant A  — target factor changed
Variant B  — target factor changed
Variant C  — target factor changed
```

without accidentally changing IDs, seeds, MSA paths, templates, or unrelated entities.

**Status:** INFERRED/RECOMMENDED.

---

## 21. Explicit Non-Goals

The AF3 input builder should not become the authority for:

- biological correctness of PTM annotations;
- literature validation of modification sites;
- structural interpretation of AF3 predictions;
- confidence-score interpretation;
- RMSD or distance-matrix analysis;
- statistical testing;
- visualization;
- AF3 execution scheduling;
- supercomputer job-management policy, unless separately added as an integration layer;
- scientific conclusions.

The builder's external responsibility ends at generating a valid, reproducible AF3 input representation.

---

## 22. Open Questions

These questions remain intentionally open because the authoritative sources reviewed do not establish a project-specific answer.

1. **Exact deployed AF3 release on the user's university supercomputer.** The builder specification should be pinned to the actual server deployment before final implementation.
2. **Exact accepted JSON-version policy of the deployed build.** Current official source accepts 1–4, but a local deployment may be pinned to an earlier release.
3. **Seed uniqueness.** AF3 requires non-empty valid seeds but the current source reviewed does not establish uniqueness as a schema requirement.
4. **Preferred ID allocator.** AF3 requires valid unique IDs; the algorithm used by the builder is a project choice.
5. **Which optional fields should the UI expose by default.** This is UX, not AF3 contract.
6. **How much preflight validation should be performed locally for MSA/CIF/CCD content.** AF3 defines input semantics; the builder can choose stronger early checks.

---

## 23. Source References

**S1 — Official AF3 input documentation**  
`google-deepmind/alphafold3`, `docs/input.md`  
https://github.com/google-deepmind/alphafold3/blob/main/docs/input.md

Key evidence: top-level contract; entity types; versions; IDs; modifications; MSA; templates; ligands; ions; bonds; user CCD; path semantics; Server compatibility.

**S2 — Official AF3 input source**  
`google-deepmind/alphafold3`, `src/alphafold3/common/folding_input.py`  
https://github.com/google-deepmind/alphafold3/blob/main/src/alphafold3/common/folding_input.py

Key evidence: `JSON_VERSIONS = (1,2,3,4)`; object types; field parsing; input validation; seed range; ID validation; ligand representation rules; polymer modification handling; file resolution; templates; bond addressing.

**S3 — Official AF3 output documentation**  
`google-deepmind/alphafold3`, `docs/output.md`  
https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md

Key evidence: output directory/file naming; seed/sample relationships; confidence and ranking outputs.

**S4 — Official AF3 execution tests**  
`google-deepmind/alphafold3`, `run_alphafold_test.py`  
https://github.com/google-deepmind/alphafold3/blob/main/run_alphafold_test.py

Key evidence: official example inputs exercised by tests and expected output layout.

**S5 — Official AlphaFold Server JSON documentation**  
`google-deepmind/alphafold`, `server/README.md`  
https://github.com/google-deepmind/alphafold/blob/main/server/README.md

Key evidence: Server dialect, top-level list, seed behavior, separate Server entity types, Server PTM naming, ID generation/conversion behavior.

**S6 — Official AlphaFold Server example**  
`google-deepmind/alphafold`, `server/example.json`  
https://github.com/google-deepmind/alphafold/blob/main/server/example.json

**S7 — Official AlphaFold 3 releases**  
https://github.com/google-deepmind/alphafold3/releases

Key evidence: latest listed v3.0.4 release and release history.

---

## 24. Research Conclusion

The external domain is now sufficiently concrete for implementation planning without inventing generic categories.

The most important architectural boundary is:

```text
Project domain model
        ↓
validated canonical AF3 configuration
        ↓
AF3 dialect/version serializer
        ↓
standalone `alphafold3` JSON
        ↓
AlphaFold 3
        ↓
seed/sample-linked output files
```

The strongest correctness risks are not the existence of protein/RNA/DNA/ligand objects; they are representation mismatches: Server-vs-standalone dialect confusion, 1-based vs 0-based indices, omitted-vs-empty semantics, CCD-vs-SMILES choice, user-CCD handling, and accidental seed/variant drift.
