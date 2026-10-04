# DOMAIN_MAPPING

This document is a **debugging and cross-reference layer**, not the authoritative AF3 contract.

It maps project-facing abstract concepts to the actual AlphaFold 3 domain representation so that an implementation can be understood by crosschecking names and representations instead of reverse-engineering intent from variable names.

A mapping entry does **not** claim that the corresponding internal class already exists. Names prefixed with `Recommended*` are proposed abstractions for implementation planning.

---

## 1. Mapping Rules

1. Every important abstract concept gets a stable `MAP-###` identifier.
2. The stable ID survives later class/module renames.
3. The external AF3 term is written exactly enough to permit a reverse lookup.
4. The domain meaning explains what the object means biologically/structurally/software-contract-wise.
5. Source/status points back to `AUTHORITATIVE_SPEC.md` and the official AF3 source/documentation.
6. If a concept is project-specific rather than AF3-defined, this is explicit.
7. Unknowns remain `UNRESOLVED`; they are not filled with generic placeholders.

---

## 2. Class / Dataclass Mapping

| ID | Recommended abstract class | Abstract role | AF3 external concept | Domain meaning | Status |
|---|---|---|---|---|---|
| MAP-001 | `RecommendedAF3Input` | Root canonical model | top-level AF3 input object | One standalone AF3 job definition | INFERRED |
| MAP-002 | `RecommendedAF3Metadata` | Root metadata | `name`, `dialect`, `version` | Naming and wire-format identity | INFERRED |
| MAP-003 | `RecommendedModelSeedSet` | Reproducibility | `modelSeeds` | Random seeds used for model execution | CONFIRMED externally / abstraction INFERRED |
| MAP-004 | `RecommendedEntity` | Polymorphic molecular object | `sequences[]` member | One AF3 molecular entity | INFERRED |
| MAP-005 | `RecommendedProteinChain` | Protein entity | `protein` | Amino-acid polymer chain | CONFIRMED |
| MAP-006 | `RecommendedRNAChain` | RNA entity | `rna` | RNA polymer chain | CONFIRMED |
| MAP-007 | `RecommendedDNAChain` | DNA entity | `dna` | Single-strand DNA polymer chain | CONFIRMED |
| MAP-008 | `RecommendedLigand` | Small molecule/ion entity | `ligand` | Non-polymer ligand; ions use this representation too | CONFIRMED |
| MAP-009 | `RecommendedPolymerModification` | Chemical replacement at position | protein `modifications[].ptmType`, RNA/DNA `modifications[].modificationType` | Modified polymer residue/base | CONFIRMED |
| MAP-010 | `RecommendedMSASource` | MSA representation | `unpairedMsa`, `pairedMsa`, `*Path` | Custom sequence-alignment input source | CONFIRMED |
| MAP-011 | `RecommendedTemplate` | Structural template | protein `templates[]` | Protein structural reference + alignment | CONFIRMED |
| MAP-012 | `RecommendedCCDSource` | Custom chemistry source | `userCCD` / `userCCDPath` | User-defined CCD component dictionary | CONFIRMED |
| MAP-013 | `RecommendedBond` | Covalent relationship | `bondedAtomPairs` | Explicit covalent bond between named atoms | CONFIRMED |
| MAP-014 | `RecommendedVariant` | Project experiment unit | no single AF3 object | Clone of a canonical AF3 configuration with controlled differences | PROJECT-SPECIFIC |
| MAP-015 | `RecommendedVariantManifest` | Lineage/comparison metadata | no AF3 wire equivalent | Records which project factors differ between variants | PROJECT-SPECIFIC |
| MAP-016 | `RecommendedOutputReference` | Output provenance | seed/sample directory + output filenames | Link from input seed to generated AF3 artifacts | CONFIRMED externally / abstraction INFERRED |

---

## 3. Root Field Mapping

| ID | Abstract field | AF3 field | Type | Meaning | Status |
|---|---|---|---|---|---|
| MAP-101 | `job_name` | `name` | string | Human-readable job name used in output naming | CONFIRMED |
| MAP-102 | `seeds` | `modelSeeds` | list[int] | Model execution seeds | CONFIRMED |
| MAP-103 | `entities` | `sequences` | list[entity] | Molecular entities to fold | CONFIRMED |
| MAP-104 | `bonds` | `bondedAtomPairs` | list[pair] | Explicit covalent bonds | CONFIRMED |
| MAP-105 | `user_ccd_inline` | `userCCD` | string | Inline custom CCD mmCIF | CONFIRMED |
| MAP-106 | `user_ccd_path` | `userCCDPath` | path string | External custom CCD mmCIF | CONFIRMED |
| MAP-107 | `dialect` | `dialect` | string | Identifies standalone AF3 input dialect | CONFIRMED |
| MAP-108 | `json_version` | `version` | int | Standalone AF3 JSON format version | CONFIRMED |

---

## 4. Protein Mapping

| ID | Abstract field | AF3 field | Type | Meaning | Status |
|---|---|---|---|---|---|
| MAP-201 | `entity_id` | `protein.id` | string/list[string] | Unique chain/copy identifier(s) | CONFIRMED |
| MAP-202 | `sequence` | `protein.sequence` | string | Canonical one-letter protein sequence | CONFIRMED |
| MAP-203 | `modifications` | `protein.modifications` | list | Polymer chemical replacements | CONFIRMED |
| MAP-204 | `modification.code` | `modifications[].ptmType` | string | CCD/custom component code | CONFIRMED |
| MAP-205 | `modification.position` | `modifications[].ptmPosition` | int | 1-based residue position | CONFIRMED |
| MAP-206 | `description` | `protein.description` | string | Human-readable chain comment | CONFIRMED in JSON v4 |
| MAP-207 | `unpaired_msa` | `protein.unpairedMsa` | A3M string | Inline unpaired MSA | CONFIRMED |
| MAP-208 | `unpaired_msa_path` | `protein.unpairedMsaPath` | path | External unpaired MSA | CONFIRMED |
| MAP-209 | `paired_msa` | `protein.pairedMsa` | A3M string | Inline paired MSA | CONFIRMED |
| MAP-210 | `paired_msa_path` | `protein.pairedMsaPath` | path | External paired MSA | CONFIRMED |
| MAP-211 | `templates` | `protein.templates` | list | Structural templates | CONFIRMED |

### Protein debugging note

`sequence` and `modifications` are **not interchangeable**. For example, a phosphorylated threonine is not represented by replacing the `T` character with an arbitrary textual token in `sequence`. The canonical sequence remains the one-letter polymer sequence and the PTM is encoded in `modifications`.

---

## 5. RNA Mapping

| ID | Abstract field | AF3 field | Type | Meaning | Status |
|---|---|---|---|---|---|
| MAP-301 | `entity_id` | `rna.id` | string/list[string] | RNA chain/copy identifier(s) | CONFIRMED |
| MAP-302 | `sequence` | `rna.sequence` | string | A/C/G/U RNA sequence | CONFIRMED |
| MAP-303 | `modifications` | `rna.modifications` | list | Modified bases | CONFIRMED |
| MAP-304 | `modification.code` | `modifications[].modificationType` | string | CCD/custom component code | CONFIRMED |
| MAP-305 | `modification.position` | `modifications[].basePosition` | int | 1-based base position | CONFIRMED |
| MAP-306 | `description` | `rna.description` | string | Human-readable RNA comment | CONFIRMED in JSON v4 |
| MAP-307 | `unpaired_msa` | `rna.unpairedMsa` | A3M string | Inline RNA MSA | CONFIRMED |
| MAP-308 | `unpaired_msa_path` | `rna.unpairedMsaPath` | path | External RNA MSA | CONFIRMED |

---

## 6. DNA Mapping

| ID | Abstract field | AF3 field | Type | Meaning | Status |
|---|---|---|---|---|---|
| MAP-351 | `entity_id` | `dna.id` | string/list[string] | DNA chain/copy identifier(s) | CONFIRMED |
| MAP-352 | `sequence` | `dna.sequence` | string | A/C/G/T DNA sequence | CONFIRMED |
| MAP-353 | `modifications` | `dna.modifications` | list | Modified bases | CONFIRMED |
| MAP-354 | `modification.code` | `modifications[].modificationType` | string | CCD/custom component code | CONFIRMED |
| MAP-355 | `modification.position` | `modifications[].basePosition` | int | 1-based base position | CONFIRMED |
| MAP-356 | `description` | `dna.description` | string | Human-readable DNA comment | CONFIRMED in JSON v4 |

### DNA debugging note

There is no standalone AF3 DNA MSA representation in the reviewed contract. A variable such as `msa_path` must therefore not be blindly reused from protein/RNA abstractions for DNA.

---

## 7. Ligand and Ion Mapping

| ID | Abstract field | AF3 field | Type | Meaning | Status |
|---|---|---|---|---|---|
| MAP-401 | `entity_id` | `ligand.id` | string/list[string] | Ligand/copy identifier(s) | CONFIRMED |
| MAP-402 | `ccd_codes` | `ligand.ccdCodes` | list[string] | Standard/custom CCD components | CONFIRMED |
| MAP-403 | `smiles` | `ligand.smiles` | string | SMILES ligand representation | CONFIRMED |
| MAP-404 | `description` | `ligand.description` | string | Human-readable ligand comment | CONFIRMED in JSON v4 |
| MAP-405 | `ion` | `ligand.ccdCodes` | list[string] | Ion represented as ligand/CCD | CONFIRMED |
| MAP-406 | `ligand_representation` | CCD vs SMILES | sum type | Exactly one ligand representation | CONFIRMED |

### Ion debugging example

Concept:

```text
ion = sodium
```

AF3 standalone wire representation:

```json
{"ligand":{"id":"X","ccdCodes":["NA"]}}
```

There must not be a standalone `ion` key in the `alphafold3` entity list merely because the Server dialect has a separate ion concept.

---

## 8. Modification Mapping

| ID | Abstract concept | AF3 representation | Meaning | Status |
|---|---|---|---|---|
| MAP-501 | `base_residue` | sequence character at position | Canonical polymer identity before modification | CONFIRMED conceptually |
| MAP-502 | `modification_code` | `ptmType` / `modificationType` | Chemical CCD/custom component replacing that position | CONFIRMED |
| MAP-503 | `position` | `ptmPosition` / `basePosition` | 1-based polymer position | CONFIRMED |
| MAP-504 | `custom_component_definition` | `userCCD`/`userCCDPath` | Definition of a non-standard component | CONFIRMED |
| MAP-505 | `server_ptm_code` | Server `CCD_*` code | Server-specific naming form | CONFIRMED |
| MAP-506 | `standalone_ptm_code` | AF3 `ptmType` without `CCD_` prefix | Standalone naming form | CONFIRMED |

### Important anti-bug distinction

The following are four different things and should not be collapsed into one variable:

```text
residue_identity
modification_identity
modification_position
custom_component_definition
```

A single “modified_residue” variable is likely to conflate chemistry with location and base identity.

---

## 9. MSA Representation Mapping

| ID | Abstract state | AF3 representation | Meaning | Status |
|---|---|---|---|---|
| MAP-601 | `AutoMSA` | protein MSA fields unset/null | AF3 data pipeline searches automatically | CONFIRMED |
| MAP-602 | `CustomUnpairedOnly` | non-empty `unpairedMsa`, empty `pairedMsa` | User controls unpaired MSA, no paired MSA | CONFIRMED |
| MAP-603 | `CustomPairedOnly` | empty `unpairedMsa`, non-empty `pairedMsa` | User controls paired MSA only | CONFIRMED, not recommended by docs |
| MAP-604 | `MSAFree` | both protein fields empty | No MSA search/input beyond query | CONFIRMED |
| MAP-605 | `CustomBoth` | both non-empty | User provides both MSA forms | CONFIRMED |
| MAP-606 | `FileBackedUnpaired` | `unpairedMsaPath` + appropriate paired state | MSA content stored externally | CONFIRMED |

Do not represent all six states with a simple boolean `use_msa` variable.

---

## 10. Template Representation Mapping

| ID | Abstract field | AF3 field | Meaning | Index base | Status |
|---|---|---|---|---:|---|
| MAP-701 | `template_source_inline` | `mmcif` | Inline structure template | — | CONFIRMED |
| MAP-702 | `template_source_path` | `mmcifPath` | External template file | — | CONFIRMED |
| MAP-703 | `query_indices` | `queryIndices` | Query positions participating in mapping | 0 | CONFIRMED |
| MAP-704 | `template_indices` | `templateIndices` | Template positions participating in mapping | 0 | CONFIRMED |
| MAP-705 | `template_collection` | `templates` | Protein-chain template list | — | CONFIRMED |

Debug rule:

```text
polymer modification position -> 1-based
bond residue ID              -> 1-based
template query index         -> 0-based
template residue index      -> 0-based
```

This mixed indexing is a high-risk source of off-by-one errors.

---

## 11. Bond Mapping

| ID | Abstract field | AF3 field | Type | Meaning | Status |
|---|---|---|---|---|---|
| MAP-801 | `bond.source.entity_id` | first triple item | string | Source entity ID | CONFIRMED |
| MAP-802 | `bond.source.residue_id` | second triple item | int | 1-based source residue | CONFIRMED |
| MAP-803 | `bond.source.atom_name` | third triple item | string | Source atom name | CONFIRMED |
| MAP-804 | `bond.target.entity_id` | first triple item | string | Target entity ID | CONFIRMED |
| MAP-805 | `bond.target.residue_id` | second triple item | int | 1-based target residue | CONFIRMED |
| MAP-806 | `bond.target.atom_name` | third triple item | string | Target atom name | CONFIRMED |
| MAP-807 | `bond` | `bondedAtomPairs[]` | pair | Explicit covalent bond | CONFIRMED |

Bond type should be modeled as an internal fixed concept `COVALENT`, or omitted internally if the implementation prefers a dedicated bond type, because AF3 currently supports no alternate bond types through this field.

---

## 12. Identifier Mapping

| ID | Abstract concept | AF3 identifier | Format / scope | Status |
|---|---|---|---|---|
| MAP-901 | `entity_id` | entity `id` | uppercase alphabetic; unique across input entities | CONFIRMED |
| MAP-902 | `copy_ids` | entity `id` list form | multiple uppercase IDs for copies | CONFIRMED |
| MAP-903 | `residue_position` | `ptmPosition` / `basePosition` | 1-based within chain | CONFIRMED |
| MAP-904 | `bond_residue_id` | bond triple residue member | 1-based | CONFIRMED |
| MAP-905 | `template_query_index` | `queryIndices[]` | 0-based | CONFIRMED |
| MAP-906 | `template_index` | `templateIndices[]` | 0-based | CONFIRMED |
| MAP-907 | `seed` | `modelSeeds[]` | uint32 range | CONFIRMED |
| MAP-908 | `sample_index` | output `sample-N` | output naming, zero-based example | CONFIRMED |

---

## 13. File Mapping

| ID | Abstract resource | AF3 field | File type | Path rule | Status |
|---|---|---|---|---|---|
| MAP-1001 | `ProteinUnpairedMSAFile` | `unpairedMsaPath` | A3M | relative to input JSON or absolute | CONFIRMED |
| MAP-1002 | `ProteinPairedMSAFile` | `pairedMsaPath` | A3M | relative to input JSON or absolute | CONFIRMED |
| MAP-1003 | `RNAUnpairedMSAFile` | `unpairedMsaPath` | A3M | relative to input JSON or absolute | CONFIRMED |
| MAP-1004 | `TemplateMMCIFFile` | `mmcifPath` | mmCIF | relative to input JSON or absolute | CONFIRMED |
| MAP-1005 | `UserCCDFile` | `userCCDPath` | CCD mmCIF | relative to input JSON or absolute | CONFIRMED |
| MAP-1006 | `InlineCCD` | `userCCD` | CCD mmCIF as string | JSON-escaped | CONFIRMED |

---

## 14. Serialization Mapping

| ID | Abstract stage | External representation | Boundary | Status |
|---|---|---|---|---|
| MAP-1101 | `CanonicalModel` | internal domain objects | pre-serialization | PROJECT-SPECIFIC |
| MAP-1102 | `ValidatedModel` | internal validated objects | validation boundary | PROJECT-SPECIFIC |
| MAP-1103 | `VariantModel` | internal cloned/edited object | experiment boundary | PROJECT-SPECIFIC |
| MAP-1104 | `SerializedRepresentation` | Python mapping / JSON-ready dict | serialization boundary | PROJECT-SPECIFIC |
| MAP-1105 | `AF3InputJSON` | `alphafold3` JSON object | external AF3 input | CONFIRMED |
| MAP-1106 | `AF3Execution` | AF3 runtime | external execution system | CONFIRMED |
| MAP-1107 | `AF3Output` | mmCIF/JSON/CSV/files | downstream boundary | CONFIRMED |

---

## 15. Pipeline Mapping

The requested conceptual pipeline is:

```text
UserConfiguration
      ↓
CanonicalModel
      ↓
ValidatedModel
      ↓
VariantModel
      ↓
SerializedRepresentation
      ↓
AF3InputJSON
      ↓
AlphaFold 3
      ↓
AF3Output
```

### Mapping details

| Stage | Meaning | AF3 equivalent | Boundary |
|---|---|---|---|
| `UserConfiguration` | Human intent captured by UI/API | none | project → domain |
| `CanonicalModel` | Normalized AF3-domain model | conceptually AF3 input object | domain |
| `ValidatedModel` | Canonical model passing project + AF3 contract checks | `Input`-compatible semantics | domain → serializer |
| `VariantModel` | Controlled experimental variant | no direct AF3 concept | experiment layer |
| `SerializedRepresentation` | JSON-ready structure | exact wire fields | serializer |
| `AF3InputJSON` | Concrete file | `dialect=alphafold3` | external input |
| `AlphaFold 3` | execution | AF3 runtime | execution |
| `AF3Output` | generated artifacts | output file tree | execution → analysis |

---

## 16. Reverse Lookup: AF3 → Abstract Concept

| AF3 term | Look up | Abstract meaning |
|---|---|---|
| `alphafold3` | MAP-107 | standalone AF3 JSON dialect |
| `version` | MAP-108 | JSON format version |
| `modelSeeds` | MAP-102 / MAP-003 | execution seed set |
| `sequences` | MAP-103 | molecular entity collection |
| `protein` | MAP-005 | protein chain |
| `rna` | MAP-006 | RNA chain |
| `dna` | MAP-007 | DNA chain |
| `ligand` | MAP-008 | ligand / ion-as-ligand |
| `modifications` | MAP-203 / MAP-303 / MAP-353 | polymer chemical modifications |
| `ptmType` | MAP-204 | protein modification component code |
| `ptmPosition` | MAP-205 | protein 1-based modification location |
| `modificationType` | MAP-304 / MAP-354 | nucleic-acid modification component code |
| `basePosition` | MAP-305 / MAP-355 | nucleic-acid 1-based modification location |
| `ccdCodes` | MAP-402 | CCD/custom component representation |
| `smiles` | MAP-403 | SMILES ligand representation |
| `userCCD` | MAP-105 / MAP-012 | inline custom CCD |
| `userCCDPath` | MAP-106 / MAP-012 | external custom CCD |
| `unpairedMsa` | MAP-207 / MAP-307 | inline unpaired MSA |
| `unpairedMsaPath` | MAP-208 / MAP-308 | external unpaired MSA |
| `pairedMsa` | MAP-209 | inline paired MSA |
| `pairedMsaPath` | MAP-210 | external paired MSA |
| `templates` | MAP-211 / MAP-705 | protein template collection |
| `mmcif` | MAP-701 | inline structural template |
| `mmcifPath` | MAP-702 | external structural template |
| `queryIndices` | MAP-703 | 0-based query template mapping indices |
| `templateIndices` | MAP-704 | 0-based template mapping indices |
| `bondedAtomPairs` | MAP-807 | explicit covalent bonds |
| `description` | MAP-206 / MAP-306 / MAP-356 / MAP-404 | textual metadata |

---

## 17. Reverse Lookup: Abstract Concept → AF3

### “Protein”

```text
RecommendedProteinChain
  -> sequences[]
  -> {"protein": {...}}
  -> protein.id
  -> protein.sequence
  -> protein.modifications
  -> protein.unpairedMsa / unpairedMsaPath
  -> protein.pairedMsa / pairedMsaPath
  -> protein.templates
  -> protein.description
```

### “Ion”

```text
RecommendedIon concept
  -> no standalone AF3 entity key
  -> RecommendedLigand
  -> ligand.ccdCodes = [ION_CCD_CODE]
```

### “Phosphorylation”

```text
RecommendedPolymerModification
  -> protein.modifications[]
  -> ptmType = AF3 CCD component code, e.g. TPO or SEP when appropriate
  -> ptmPosition = 1-based residue position
```

### “Custom small molecule”

```text
RecommendedLigand
  -> either ligand.smiles
  OR
  -> ligand.ccdCodes + root userCCD/userCCDPath
```

### “Covalent attachment”

```text
RecommendedBond
  -> bondedAtomPairs[]
  -> endpoint = [entity_id, residue_id_1_based, atom_name]
```

---

## 18. Representation-State Matrix

| Abstract concept | State A | State B | State C | State D | Do not collapse into |
|---|---|---|---|---|---|
| Protein MSA | auto (`null`/unset) | unpaired-only | paired-only | fully MSA-free | `use_msa: bool` |
| Protein template | search allowed | template-free `[]` | explicit templates | — | `use_template: bool` |
| Ligand | CCD | SMILES | custom CCD via CCD codes | — | generic `ligand_data: str` |
| User CCD | inline | file path | absent | — | generic `ccd_path_or_text` without state |
| MSA storage | inline | file path | absent | — | generic `file_or_text` |
| Modification | canonical residue | modified component | custom modified component | — | single “modified residue” string |

---

## 19. Relationship Mapping

| ID | Relationship | Cardinality | Constraint | Status |
|---|---|---|---|---|
| MAP-1201 | AF3Input → entities | 1 → many | `sequences` contains entity objects | CONFIRMED |
| MAP-1202 | AF3Input → model seeds | 1 → many | at least one | CONFIRMED |
| MAP-1203 | AF3Input → user CCD source | 1 → 0/1 | `userCCD` xor `userCCDPath` | CONFIRMED |
| MAP-1204 | Protein → modifications | 1 → 0/many | each position within sequence | CONFIRMED |
| MAP-1205 | RNA → modifications | 1 → 0/many | each position within sequence | CONFIRMED |
| MAP-1206 | DNA → modifications | 1 → 0/many | each position within sequence | CONFIRMED |
| MAP-1207 | Protein → templates | 1 → 0/many | protein-only; current source docs up to 20 | CONFIRMED |
| MAP-1208 | Ligand → CCD components | 1 → 1/many | CCD representation when selected | CONFIRMED |
| MAP-1209 | Ligand → SMILES | 1 → 0/1 | mutually exclusive with CCD representation | CONFIRMED |
| MAP-1210 | AF3Input → bondedAtomPairs | 1 → 0/many | endpoints reference named atoms | CONFIRMED |
| MAP-1211 | Bond → endpoint | 1 → 2 | each endpoint = entity + residue + atom | CONFIRMED |
| MAP-1212 | Variant → canonical model | many → 1 | cloned base plus controlled differences | PROJECT-SPECIFIC |

---

## 20. Validation / Debug Crosswalk

Use this table as a fast debugging checklist.

| Symptom / variable | Crosscheck |
|---|---|
| wrong molecular entity type | MAP-005..008 |
| ion not accepted | MAP-405: represent ion as ligand + CCD |
| PTM code rejected | MAP-204/304/354; check no `CCD_` prefix in standalone AF3 |
| PTM appears on wrong residue | MAP-205/305/355; positions are 1-based |
| template alignment off by one | MAP-703/704; indices are 0-based |
| MSA behaves unexpectedly | MAP-601..606; distinguish null/omitted/empty/non-empty |
| ligand has both CCD and SMILES | MAP-406; exactly one representation |
| SMILES bond failure | MAP-403 + MAP-807; use user CCD for explicit atom names |
| custom CCD not found | MAP-105/106/402; code must match CCD component ID |
| `userCCD` + `userCCDPath` conflict | MAP-105/106; mutually exclusive |
| duplicate chain/entity ID | MAP-901/902 |
| seed changed between variants | MAP-003 / MAP-102; compare exact ordered seed list at variant boundary |
| Server JSON accepted but standalone AF3 fails | check dialect and entity representation first; MAP-107 + MAP-008/MAP-405 |
| output files cannot be matched to input | MAP-003, MAP-1106, MAP-1107 and seed/sample naming |

---

## 21. Stable Project IDs for Future Implementation

The following IDs are intentionally stable even if implementation class names change:

```text
MAP-001  Root AF3 input
MAP-005  Protein chain
MAP-006  RNA chain
MAP-007  DNA chain
MAP-008  Ligand / ion-as-ligand
MAP-009  Polymer modification
MAP-010  MSA source
MAP-011  Structural template
MAP-012  User CCD source
MAP-013  Covalent bond
MAP-014  Project variant
MAP-015  Variant manifest
MAP-016  Output reference
MAP-101..108  Root fields
MAP-201..211  Protein fields
MAP-301..308  RNA fields
MAP-351..356  DNA fields
MAP-401..406  Ligand fields
MAP-501..506  Modification concepts
MAP-601..606  MSA states
MAP-701..705  Template fields
MAP-801..807  Bond fields
MAP-901..908  Identifier concepts
MAP-1001..1006  File concepts
MAP-1101..1107  Serialization/output stages
MAP-1201..1212  Relationships
```

These identifiers should be used in implementation documentation, tests, debugging messages, and migration notes whenever practical.

---

## 22. Source References

Primary references are defined in `AUTHORITATIVE_SPEC.md`:

- S1: official AF3 `docs/input.md`
- S2: official AF3 `src/alphafold3/common/folding_input.py`
- S3: official AF3 `docs/output.md`
- S4: official AF3 `run_alphafold_test.py`
- S5: official AlphaFold Server `server/README.md`
- S6: official AlphaFold Server `server/example.json`
- S7: official AF3 releases

---

## 23. Final Domain Summary

The external AF3 domain can be reduced to a small number of real concepts:

```text
AF3Input
├── metadata
│   ├── name
│   ├── dialect
│   └── version
├── modelSeeds
├── entities
│   ├── ProteinChain
│   ├── RNAChain
│   ├── DNAChain
│   └── Ligand (includes ion representation)
├── polymer modifications
├── MSA sources
├── structural templates
├── user CCD source
└── covalent bonds
```

The highest-value debugging principle is to retain **semantic distinctions** all the way to serialization:

```text
protein != ligand != ion-as-separate-type
sequence != modification
modification_code != modification_position
CCD != SMILES
inline != path
unset/null != empty
1-based polymer position != 0-based template index
standalone AF3 JSON != AlphaFold Server JSON
AF3 software version != JSON format version
project seed policy != AF3 schema requirement
```

That is the cross-reference layer that should be used before changing implementation variables, classes, or serializers.
