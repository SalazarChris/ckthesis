# Agent Execution Prompt: Build the 10-Condition Human Oct4 POU-Core AF3 Input Set

## Mission

Act as a careful structural-bioinformatics workflow engineer. Use the **existing Oct4/AF3 JSON builder in this repository** to create and validate the 10 AlphaFold 3 input JSONs specified below. This is an input-generation task, not a new analysis implementation and not an AF3 inference run.

The ten inputs are a focused first-stage dataset for comparing the human OCT4/POU5F1 core in the apo state and in a canonical double-stranded DNA context, with T235/S236 phosphorylation and S236 O-GlcNAcylation.

The dataset must follow the accompanying `AF3_Comparative_Structural_Analysis_SOP.md` if that file is present in the project. That SOP distinguishes model confidence, predicted geometry, and biological inference. This task creates inputs for downstream comparison; it must not claim that the inputs themselves establish biological effects.

## Non-negotiable working rules

1. **Inspect before changing.** First inspect the repository README, the JSON builder's current menu/workflow, its schema/serialization code, any documented builder tests, and at least one existing JSON that has successfully run on the target AF3 server, if available. Use the existing builder; do not redesign it or rebuild it from scratch.
2. **Create jobs through the builder.** Use its supported menu, job/variant workflow, save/export functions, and PTM/custom-component controls. Do not bypass it by hand-writing ten unrelated JSONs or inventing a parallel builder. If programmatic creation is a documented feature of this same builder, it may be used, but the saved outputs must still pass the builder's own validation path.
3. **Surgical fixes only.** If a necessary builder feature is broken or missing, reproduce the issue, identify the smallest fix, add/adjust a focused test, and rerun relevant tests. Do not refactor unrelated code. Record any code change in the final report.
4. **Do not silently invent chemistry.** Standard phosphorylation should use the builder's verified AF3 PTM mechanism. S236 O-GlcNAc must be represented as a chemically and structurally valid covalent modification. Do not represent it as a free, noncovalently associated NAG molecule, and do not call an unsupported/custom approximation “validated O-GlcNAc.” If the builder cannot represent the correct covalent linkage, report that blocker explicitly and do not falsely mark all ten conditions complete.
5. **Do not launch AF3 inference.** Create and locally validate input files only. Do not submit jobs to the university server, start expensive GPU jobs, or imply that an AF3 prediction has been run.
6. **Preserve existing user data.** Do not overwrite or delete existing JSONs, project files, or saved jobs. Use a new dedicated output folder.
7. **Keep conditions controlled.** Use the same protein construct, protein chain ID, seed list, AF3 input dialect/version, MSA/template policy, and all other settings wherever possible. Only the intended PTM and DNA entities/bonds should differ between conditions.
8. If a required detail is not directly supported by the builder or target server documentation, inspect the local documentation and existing working JSONs. Explain remaining uncertainty in the validation report instead of guessing.

---

## 1. Reference identity and exact protein construct

### Biological reference

Use the **canonical human OCT4/POU5F1 protein, UniProt Q01860**, 360 amino acids long. Do not use mouse Oct4, another human isoform, or a sequence copied from an unrelated structure without explicitly documenting the difference.

Reference source for verification: https://www.uniprot.org/uniprotkb/Q01860/entry

### Construct

Use the inclusive full-length reference interval **residues 130–290**. This produces a 161-amino-acid segmented POU-core construct.

Use the following exact sequence for chain A, and independently cross-check it against Q01860 positions 130–290 before saving:

```text
EQNPEESQDIKALQKELEQFAKLLKQKRITLGYTQADVGLTLGVLFGKVFSQTTICRFEALQLSFKNMCKLRPLLQKWVEEADNNENLQEICKAETLVQARKRKRTSIENRVRGNLENLFLQCPKPTLQQISHIAQQLGLEKDVVRVWFCNRRQKGKRSSS
```

Expected checks:

- Sequence length: **161 amino acids**.
- Full-length reference residue 130 maps to construct position 1.
- Conversion rule for positions in this construct: `construct_position = reference_position - 129`.
- Human reference **T235** is construct position **106**.
- Human reference **S236** is construct position **107**.
- Verify the construct has T at position 106 and S at position 107 before applying any modification.
- Keep the standard one-letter protein sequence unchanged for PTM conditions; express phosphorylation through the builder's PTM/modification field, not by changing the sequence to a nonstandard letter.

Use the same 161-aa sequence for all 10 jobs. The DNA-bound conditions add DNA chains but must not change the protein sequence or construct boundaries.

### Coordinate systems to record

Every report/manifest must distinguish:

- `reference_position`: position in full-length human Q01860 (e.g. T235).
- `construct_position`: 1-based position in the 130–290 construct (e.g. T235 -> 106).
- `model_residue_id`: residue identifier found later in the AF3 output mmCIF; this does not exist yet for input-only validation.

Do not confuse the PTM position in the submitted chain with full-length UniProt numbering. The native AF3 protein modification position is a **1-based position in the submitted sequence**.

---

## 2. DNA duplex specification

For every DNA-bound condition, add the same canonical 8-base-pair duplex as **two distinct DNA entities/chains**, each sequence written 5′ to 3′:

- DNA chain B: `ATGCAAAT`
- DNA chain C: `ATTTGCAT`

These two strings are reverse complements and together define one double-stranded 8-bp duplex. Do not submit only one strand. Do not duplicate the same strand sequence twice. Keep the chain IDs and strand sequences identical across all DNA-bound conditions.

This deliberately uses the same short 8-bp duplex in every DNA condition to isolate the protein/PTM comparison. Do not add flanking DNA bases in this batch. Record in the README that an 8-bp duplex may have end effects and could be expanded in a future, separate study; do not change the present design without authorization.

For apo conditions, omit both DNA chains entirely.

### Entity/chain ID plan

Use unique, stable IDs across all files:

- Protein construct: chain `A`.
- DNA strand 1 (only in DNA-bound conditions): chain `B`.
- DNA strand 2 (only in DNA-bound conditions): chain `C`.
- O-GlcNAc glycan component if represented as a covalently attached ligand: entity/chain `D`.

If the builder imposes a different stable ID policy, follow the builder's documented behavior but update the manifest and ensure every ID is unique. Never assign an ID to two separate entities in a JSON.

---

## 3. The ten required conditions

Create exactly these ten JSON jobs, with these IDs, filenames, and intended differences. Do not add acetylation, SUMO, mutations, deletions, Sox2, ions, or alternative DNA motifs to this batch.

| ID | Suggested filename | Protein state | DNA | PTM / special requirement | Main matched comparison |
|---|---|---|---|---|---|
| C01 | `C01_WT_apo.json` | Human Q01860 130–290 WT | None | No modification | Apo reference for C03/C05/C07/C09 |
| C02 | `C02_WT_canonical_DNA.json` | Same WT construct | B=`ATGCAAAT`; C=`ATTTGCAT` | No protein modification | DNA-bound reference for C04/C06/C08/C10 |
| C03 | `C03_pT235_apo.json` | Same sequence | None | Phosphorylate reference T235, construct position 106 | Compare to C01 |
| C04 | `C04_pT235_canonical_DNA.json` | Same sequence | Same B/C duplex | pT235 at construct position 106 | Compare to C02 |
| C05 | `C05_pS236_apo.json` | Same sequence | None | Phosphorylate reference S236, construct position 107 | Compare to C01 and C09 |
| C06 | `C06_pS236_canonical_DNA.json` | Same sequence | Same B/C duplex | pS236 at construct position 107 | Compare to C02 and C10 |
| C07 | `C07_pT235_pS236_apo.json` | Same sequence | None | Both pT235 at 106 and pS236 at 107 | Compare to C01/C03/C05 |
| C08 | `C08_pT235_pS236_canonical_DNA.json` | Same sequence | Same B/C duplex | Both modifications at 106 and 107 | Compare to C02/C04/C06 |
| C09 | `C09_OGlcNAc_S236_apo.json` | Same sequence | None | One O-GlcNAc attached to S236 (construct position 107) | Compare to C01 and C05 |
| C10 | `C10_OGlcNAc_S236_canonical_DNA.json` | Same sequence | Same B/C duplex | Same covalent O-GlcNAc-at-S236 chemistry as C09 | Compare to C02 and C06 |

The combined pT235+pS236 condition is an intentional modeled combination, not a claim about simultaneous occupancy in vivo. C05/C06 and C09/C10 model alternative states at S236; do not put phosphorylation and O-GlcNAc on the same S236 in any one input.

### 3.1 Standard phosphorylation representation

For native AF3 JSON, use the builder's confirmed representation of Chemical Component Dictionary (CCD) PTMs:

- Phosphothreonine at submitted protein position 106: CCD component `TPO` (where that exact code is the correct code for the builder's selected AF3 dialect).
- Phosphoserine at submitted protein position 107: CCD component `SEP` (where that exact code is the correct code for the builder's selected AF3 dialect).

The native AF3 input usually represents these in the protein's `modifications` list, conceptually as a modification type plus a 1-based submitted-chain position. Follow the builder's schema and its current working examples exactly; do not mix AlphaFold Server compatibility syntax with native AF3 syntax. If the builder serializes identifiers with a prefix such as `CCD_`, use the prefix only if confirmed as correct for the target dialect/server. Do not invent a new syntax.

Expected logical PTM lists:

- C01, C02, C09, C10: no standard phosphorylation PTMs.
- C03, C04: TPO at submitted position 106 only.
- C05, C06: SEP at submitted position 107 only.
- C07, C08: TPO at 106 and SEP at 107.

For C09/C10, the S236 glycosylation is represented by the covalent glycan specification below, not by also adding SEP at 107.

### 3.2 O-GlcNAc at S236: chemistry must be genuine

Conditions C09 and C10 must model a single **O-linked N-acetylglucosamine (O-GlcNAc)** group covalently attached through the serine side-chain oxygen at human S236 (chain A, construct position 107).

Preferred representation if supported by the builder and target AF3 version:

- Keep the protein's standard S residue at chain A, position 107.
- Add a single N-acetyl-D-glucosamine component using its verified standard CCD identifier (commonly `NAG` for the monosaccharide, if confirmed by the local CCD/schema).
- Define the explicit covalent linkage from chain A residue 107 atom `OG` to the glycan's anomeric carbon (commonly atom `C1`, but **verify exact CCD atom names and stereochemistry** against the actual component definition before using them). The linkage must represent the O-linked β-GlcNAc glycoside, not a noncovalent ligand near the residue.
- Use the builder's covalent-bond/custom-component feature to serialize the linkage. In native AF3 JSON, the relevant mechanism is typically `bondedAtomPairs`; follow the builder's supported format and validate it against the target deployment.
- In DNA-bound C10, include the same O-GlcNAc linkage plus DNA chains B and C. Do not alter the glycan linkage or composition between C09 and C10.

**Mandatory validation for C09/C10:**

1. Verify the CCD entry/atom list for the glycan component from the available local CCD or target AF3 installation/documentation.
2. Confirm the glycan is covalently attached to the S236 side-chain oxygen at construct position 107, not merely present as a free ligand entity.
3. Confirm the linkage atom names, glycosidic stereochemistry, entity/residue numbering, and JSON bond definition are correct for the actual CCD component.
4. Confirm the builder can save/reopen the JSON without discarding the ligand or bond.
5. If supported tools exist, run the builder's own preflight/schema validation. Do not run AF3 inference as part of this task.
6. Record the exact chemical representation and validation evidence in the manifest/validation report.

If this representation cannot be validated with the current builder and server schema, **do not silently approximate it**. Finish and validate C01–C08, save any C09/C10 drafts only in a clearly marked `needs_chemistry_validation` subfolder (not in the ready-to-run set), and write a specific blocker in `VALIDATION_REPORT.md` describing which builder feature or chemistry definition is missing. The report must clearly say that the ten-condition set is incomplete until this is resolved.

---

## 4. Names, AF3 schema version, seeds, and run settings

### Job names

Use unique names matching the IDs and descriptions, for example:

- `OCT4_POU_130_290_C01_WT_APO`
- `OCT4_POU_130_290_C02_WT_CANONICAL_DNA`
- etc.

Keep names stable and filesystem-safe. The JSON filenames should match the table in Section 3.

### JSON dialect and version

Before creating jobs, inspect the builder's current known-working output and the **actual AF3 schema/version accepted by the target university server**. The intended native AF3 dialect is `alphafold3`. Current native AF3 documentation distinguishes schema versions and the features available in each; version 3 supports `userCCDPath`, while version 4 adds textual entity descriptions.

Use one consistent version across all ten jobs. Prefer the version already used by working inputs on the target server if it supports every feature in this task. Do not upgrade or downgrade schema versions blindly. The builder may have a UI default that differs from the newest documented schema version; resolve that against actual deployment documentation and verified working inputs, and write the decision in `README.md`.

Official reference for the native input schema: https://github.com/google-deepmind/alphafold3/blob/main/docs/input.md

### Model seeds and sample count

- Use the project's already agreed seed list if present in repository notes/configuration.
- If no project seed list exists, use the deterministic default `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]`.
- The **exact same list and order** must be in all ten JSONs.
- Do not generate a different seed list for each condition.
- A `modelSeeds` list does not necessarily configure multiple diffusion samples per seed. If this project has an established sample count (for example, five samples per seed), record it as a server/inference configuration requirement separately. Do not add an undocumented JSON field to force sample count.
- Do not submit predictions during this task.

### MSA/template policy

Apply the same protein MSA/template policy for chain A across all ten conditions, using the existing builder defaults or the documented project settings. Do not invent absolute MSA/template file paths. If a selected builder option creates path fields, use the same paths and policy for all ten inputs and verify that all referenced files exist from the target server's perspective.

DNA conditions should differ only by the presence of the two DNA entities, plus the intended protein PTM/glycan state. Do not change the protein sequence or MSA/template policy merely because DNA is included.

---

## 5. Required builder workflow

Use the actual implemented builder interface. First identify how to create a new job, open/edit a saved JSON, manage protein and DNA entities, add PTMs, add a ligand/custom component, add covalent bonds, and save/export a JSON. Menu wording may differ; do not assume unimplemented menu options.

Recommended creation strategy:

1. Create and save C01 WT apo as the verified base.
2. Reopen the saved base or use the builder's documented variant-generation workflow to construct each remaining condition. Verify all edits after each save; do not rely on in-memory display alone.
3. For DNA-bound conditions, add both strands with the sequence and chain-ID mapping specified above.
4. For phosphorylation conditions, add PTMs only at construct positions 106 and/or 107 as specified.
5. For C09/C10, use the builder's supported bonded glycan workflow and validate the exact linkage. If adding a glycan introduces entity D, confirm that C10 also retains DNA entities B and C.
6. Save each condition as a separate JSON under the dedicated output folder. Never save a variant over C01 or another condition.
7. Close/reopen each saved file in the builder (or use the builder's supported load/validate function) to ensure the saved content survives serialization and round-tripping.

Do not call a condition finished until its saved JSON has been re-opened and validated, not merely assembled in the interactive editor.

---

## 6. Output folder and required artifacts

Use the repository's established location for generated AF3 inputs if one exists. If it does not, create:

```text
generated_jobs/oct4_pou_core_10_conditions/
├── inputs/
│   ├── C01_WT_apo.json
│   ├── C02_WT_canonical_DNA.json
│   ├── C03_pT235_apo.json
│   ├── C04_pT235_canonical_DNA.json
│   ├── C05_pS236_apo.json
│   ├── C06_pS236_canonical_DNA.json
│   ├── C07_pT235_pS236_apo.json
│   ├── C08_pT235_pS236_canonical_DNA.json
│   ├── C09_OGlcNAc_S236_apo.json
│   └── C10_OGlcNAc_S236_canonical_DNA.json
├── reference/
│   ├── human_Q01860_reference_130_290.fasta
│   └── condition_manifest.csv
├── README.md
└── VALIDATION_REPORT.md
```

Adapt to existing repository conventions if necessary, but preserve the separation of ready-to-run inputs, reference/provenance files, and validation report. If C09/C10 cannot pass chemistry validation, place those drafts in a clearly labeled `needs_chemistry_validation/` directory and state the overall set is incomplete.

### Manifest columns

Include at least:

`condition_id, filename, job_name, reference_accession, species, reference_start, reference_end, construct_length, protein_chain_id, protein_sequence_sha256, dna_present, dna_chain_B_sequence, dna_chain_C_sequence, ptm_reference_positions, ptm_construct_positions, ptm_components, glycan_component, glycan_bond_definition, model_seeds, num_seeds, sample_count_setting_note, dialect, version, msa_template_policy, validation_status, warnings`.

For apo conditions, leave DNA fields empty/not applicable. For non-glycosylated conditions, leave glycan fields empty/not applicable. Do not write one seed per row unless that is the established manifest format; it is sufficient to record the exact common list as JSON text plus the number of seeds.

### README.md

Explain in plain language:

- The scientific purpose and the ten matched conditions.
- Reference accession/species and construct boundaries.
- Full-length-to-construct mapping for T235/S236.
- DNA duplex sequences and chain IDs.
- PTM encodings and exact glycan-linkage representation.
- The common seeds and the external sample-count setting (or that sample count remains server-configured).
- How to open each job in the builder and where the JSONs were saved.
- Any known limitations, including the short 8-bp DNA duplex and the fact that predicted structures are not experimental evidence.

### VALIDATION_REPORT.md

Report, with explicit pass/fail status:

- Repository/builder features inspected and which workflow was used.
- AF3 dialect/version decision and its supporting local evidence.
- Per-file JSON parse result.
- Required field validation: job name, modelSeeds, sequences, unique entity IDs, protein sequence, and chain identities.
- Protein sequence length, sequence hash, and validation of reference-position mapping.
- Exact modifications per condition with both reference and construct positions.
- DNA duplex complementarity and confirmation that both chains occur only in C02/C04/C06/C08/C10.
- Glycan connectivity/chemistry validation for C09/C10, including atom names and evidence source; or a clearly stated blocker.
- Builder save/reopen (round-trip) results.
- Test commands run and results; whether any code was modified and why.
- A final overall status: `READY_FOR_AF3_INPUT_REVIEW`, `PARTIAL_BLOCKED_BY_GLYCAN_CHEMISTRY`, or `FAILED_VALIDATION`.

Do not describe the JSONs as fully validated if only JSON syntax parsing succeeded. Syntax, builder validation, AF3 schema compatibility, and chemical validity are separate gates.

---

## 7. Validation checklist (all applicable items must pass)

### All ten jobs

- [ ] Exactly ten expected condition IDs and filenames are present in the ready-to-run `inputs/` directory.
- [ ] Every JSON parses cleanly.
- [ ] Every job uses the same intended native AF3 dialect and schema version.
- [ ] Every job uses the same ten model seed values in the same order.
- [ ] Chain A sequence is exactly the 161-aa human Q01860 130–290 construct.
- [ ] Every entity ID is unique within a JSON.
- [ ] No unexpected entities, PTMs, sequence mutations, deletions, or DNA strands appear.
- [ ] Each file can be reopened using the builder without losing its contents.

### Per-condition logical validation

- [ ] C01: chain A only; no PTMs, DNA or glycan.
- [ ] C02: chain A + DNA B + DNA C; no PTMs/glycan.
- [ ] C03: chain A with TPO/T235 only (construct position 106); no DNA/glycan.
- [ ] C04: same T235 PTM as C03 plus both canonical DNA strands.
- [ ] C05: chain A with SEP/S236 only (construct position 107); no DNA/glycan.
- [ ] C06: same S236 PTM as C05 plus both canonical DNA strands.
- [ ] C07: TPO at 106 and SEP at 107; no DNA/glycan.
- [ ] C08: same two PTMs as C07 plus both canonical DNA strands.
- [ ] C09: single covalent O-GlcNAc at S236/position 107; no DNA and no SEP/TPO.
- [ ] C10: same covalent O-GlcNAc at S236 as C09 plus both canonical DNA strands; no SEP/TPO at S236.
- [ ] C02/C04/C06/C08/C10 use B=`ATGCAAAT` and C=`ATTTGCAT`.
- [ ] C01/C03/C05/C07/C09 contain no DNA entities.

### Cross-condition matched-design validation

- [ ] C01/C03/C05/C07/C09 have identical chain A sequence and same no-DNA context; only their intended PTM state differs.
- [ ] C02/C04/C06/C08/C10 have identical chain A sequence and identical DNA B/C composition; only their intended PTM/glycan state differs.
- [ ] C01 vs C02 differs only by DNA addition.
- [ ] C03 vs C04, C05 vs C06, C07 vs C08, and C09 vs C10 each differ only by DNA addition.
- [ ] Seeds and comparable preprocessing settings are identical across every condition.

---

## 8. Final response required from the agent

When done, report concisely but with evidence:

1. Exact path to the output folder and links/paths to `README.md` and `VALIDATION_REPORT.md`.
2. List the ten JSON filenames and mark each `PASS`, `BLOCKED`, or `FAIL`.
3. State the selected AF3 dialect/version and exact seed list.
4. Confirm the construct length and the mapping T235 -> position 106; S236 -> position 107.
5. For C09/C10, state the verified chemical component, linkage atom names, and covalent-bond representation. If not validated, explicitly say the ten-condition set is not yet complete.
6. State whether any builder code changed; if so, describe the minimal fix and tests.
7. State explicitly that AF3 inference jobs were **not** submitted or run.

Never claim that a PTM causes a particular structural or biological outcome based on these input files. Their purpose is to create a controlled, reproducible prediction dataset for subsequent analysis under the comparative SOP.
