# AlphaFold 3 Comparative Structural Analysis SOP

**Purpose:** A reproducible downstream workflow for comparing AF3 predictions across wild-type (WT), sequence variants, deletions, and post-translational modification (PTM) states. The immediate application is segmented Oct4/POU5F1, including POU-domain geometry, linker behavior, and DNA-associated predictions. The workflow is generalizable to other proteins.

**Core rule:** Keep three types of evidence distinct:

1. **Model confidence:** how confident AF3 is in a prediction (pLDDT, PAE, pTM/ipTM, clash flags).
2. **Predicted structural differences:** geometric/chemical differences between modeled coordinates (RMSD, residue displacement, contacts, hydrogen bonds, solvent accessibility, surface electrostatics).
3. **Biological inference:** hypotheses about binding, recruitment, folding, or function that require independent support.

A confidence change is not itself a structural change; a structural change is not proof of a functional change. AF3 models are predictions, not experiments or molecular-dynamics trajectories.

---

## 0. Define the comparison before processing

For every condition, record:

- Stable `condition_id` and human-readable name.
- Protein sequence and the exact reference sequence against which positions are numbered.
- Variant type: WT, substitution, deletion, PTM, combination, or complex composition change.
- Modified/deleted positions in **reference-sequence coordinates**.
- Protein construct boundaries and any omitted domains/linkers.
- DNA/RNA/ligand presence, sequence/identity, chain IDs, stoichiometry, and strand representation.
- PTM chemistry and input representation (CCD component/residue name/custom CCD, atom/bond definition, charge/protonation assumptions if relevant).
- AF3 input JSON, AF3 version/server release, run date, seed list, sample count, MSA/template configuration, and output paths.

Use matched AF3 settings across conditions wherever possible: the same seed design, sample count, input pipeline settings, templates/MSA policy, chain definitions, and output-processing version. Differences in inputs or preprocessing must be recorded as potential confounders.

### Recommended condition table

| condition_id | sequence/construct | change vs WT | PTM state | DNA state | seed set | samples/seed | input JSON |
|---|---|---|---|---|---|---:|---|
| WT | Reference construct | None | None | Absent | same planned set | e.g. 5 | `inputs/WT.json` |
| WT_DNA | Reference construct | DNA added | None | Present | same planned set | e.g. 5 | `inputs/WT_DNA.json` |
| VAR_01 | Reference construct | Mutation/deletion | None | As specified | same planned set | e.g. 5 | `inputs/VAR_01.json` |
| PTM_01 | Reference construct | None | Specified PTM | As specified | same planned set | e.g. 5 | `inputs/PTM_01.json` |

Do not combine comparisons that change several factors unless the combination is the explicit experimental condition. To estimate a PTM effect, compare matched conditions differing only in that PTM (including the same DNA state); to estimate a DNA effect, compare matched protein/PTM states with and without DNA.

---

## 1. AF3 output inventory and extraction

### 1.1 Files to preserve

A standard AF3 output directory includes sample-specific folders named `seed-<seed>_sample-<sample>` containing a model mmCIF, a full confidence JSON, and a summary confidence JSON. The job root also includes a top-ranked model and corresponding confidence files, a processed input JSON (`*_data.json`), and `ranking_scores.csv`. Distograms and embeddings are optional and may be very large.

| File | Extract/use | Priority |
|---|---|---|
| `*_model.cif` | Coordinates, chain/residue/atom identifiers, residue names/PTMs; AF3 pLDDT is recorded in the B-factor field | Required |
| `*_confidences.json` | Full `pae`, `atom_plddts`, `contact_probs`, `token_chain_ids`, `token_res_ids`, `atom_chain_ids` arrays | Required |
| `*_summary_confidences.json` | Overall and chain-level summary scores and pairwise metrics | Required |
| `ranking_scores.csv` (name can be job-prefixed in some outputs) | Score/rank every sample; preserve original ranking | Required |
| `*_data.json` | Exact processed job/input provenance, often with MSA/template data added by the data pipeline | Strongly recommended |
| `TERMS_OF_USE.md` | Preserve with archive | Archive |
| `*_distogram.npz` | Pair-distance-bin distributions if `--save_distogram=true` was used | Optional |
| `*_embeddings.npz` | Single/pair model embeddings if `--save_embeddings=true` was used | Optional; not usually needed for standard comparisons |

**Do not retain only the root-level top-ranked structure.** Analyze the individual seed/sample outputs to quantify prediction variability. The root model is a convenient representative for visualization, not a substitute for the ensemble.

### 1.2 Output manifest (one row per predicted sample)

Recommended columns:

`condition_id, seed, sample, input_json, processed_data_json, model_cif, confidences_json, summary_json, ranking_score, ptm, iptm, fraction_disordered, has_clash, chain_ids, sequence_hash, construct_start, construct_end, modified_positions_ref, dna_present, af3_version, run_date, include_status, exclusion_reason`.

Also maintain a chain/residue map table:

`condition_id, chain_id, entity_type, model_res_id, insertion_code, residue_name, reference_position, reference_residue, sequence_position, is_modified, modification_component, alignment_status`.

For segmented constructs, maintain **two coordinate systems**:

- Model coordinates: chain, mmCIF residue number, insertion code, residue/atom identities.
- Reference coordinates: position in the selected full-length or domain reference sequence.

Map them explicitly by sequence alignment. Never assume CIF residue numbering, sequence numbering, AF3 token indexing, and full-length reference positions are interchangeable. This is especially important for deletions, inserted residues, chain breaks, PTM components, and custom CCD inputs.

### 1.3 Data validation gates

Before calculating metrics, automatically check:

- Every manifest path exists and parses.
- `pae` is square and has the same token dimension as `token_chain_ids` and `token_res_ids`.
- `atom_plddts` length agrees with the atom count and atom ordering of the corresponding model; cross-check the CIF B-factor values.
- All chain IDs match the intended input entities.
- The observed protein sequence matches the submitted construct after accounting for explicitly modeled PTMs/non-standard residues.
- Expected DNA strands/chains are present when DNA is part of the condition.
- Expected PTM component/atoms are present at the correct reference-mapped residue; flag any PTM absent from the coordinate file.
- There are no duplicate manifest rows, missing sample folders, unexpected sample counts, or inconsistent seed lists.
- Record rather than silently discard a structure with a warning, clash, missing component, or parse failure. Exclusions need explicit reasons.

AF3's CIF is the primary structural file format; AF3 documentation says its standard output is mmCIF rather than PDB. Avoid converting to PDB unless a downstream tool requires it, because conversion can lose component or atom metadata.

---

## 2. Confidence and model-consistency analyses

### 2.1 Per-atom and per-residue pLDDT

AF3 pLDDT is a **per-atom** confidence estimate on a 0–100 scale. It is present as `atom_plddts` in the full confidence JSON and in the mmCIF B-factor field. A residue-level pLDDT is therefore a derived summary, not the only raw AF3 value.

Recommended extraction:

1. Read the mmCIF and collect per-atom confidence from the B-factor field.
2. Cross-check the atom count/order against `atom_plddts` and `atom_chain_ids` in the associated confidence JSON.
3. For protein residue summaries, use the Cα pLDDT as the main single representative value when present; optionally retain the median of backbone atom pLDDTs (`N`, `CA`, `C`, `O`) as a secondary summary.
4. Preserve atom-level values separately. Do not average protein, DNA, and ligand atoms together into a single “protein pLDDT”.
5. Aggregate to reference-coordinate windows only after the model-to-reference residue mapping is validated.

Useful outputs:

- `plddt_per_residue.csv`: one row per model residue/sample, including model ID, reference position, residue, domain/region, and pLDDT summary.
- `plddt_region_summary.csv`: per-sample and per-condition summaries for predefined regions.
- Plots: per-residue profile, region-level distributions, and paired ΔpLDDT (variant − matched WT) over reference positions.

Common interpretive bins are pLDDT >90 (very high confidence), 70–90 (generally confident), 50–70 (low confidence), and <50 (very low confidence). Treat these as heuristic bins, not physical-state definitions. Low pLDDT can be consistent with disorder or uncertainty, but a static AF3 model does not directly measure flexibility or prove an order/disorder transition. A well-folded domain can be modeled with high local confidence while its position relative to another domain remains uncertain.

### 2.2 PAE: relative-position confidence

The full confidence JSON key `pae` is a `[num_tokens, num_tokens]` matrix. Entry `(i, j)` estimates the positional error for token `j` when aligned using token `i`'s frame. High PAE means lower confidence in that relative positioning; low PAE means more confidence. The matrix need not be treated as symmetric because the directional interpretation is defined by the reference token.

Procedure:

1. Load the full `pae` matrix and map each token with `token_chain_ids` and `token_res_ids`.
2. Save a PAE heatmap with chain/domain boundaries annotated.
3. For each biologically relevant region pair, extract the corresponding rectangular PAE block. Report median and 90th percentile PAE; optionally report both directional blocks/means instead of silently symmetrizing.
4. For multi-chain protein–DNA complexes, summarize protein–DNA and chain-pair PAE separately from within-protein PAE.
5. Compare each variant's block summaries with the matched WT block under the same complex composition.

For segmented Oct4, define regions before looking at results—for example, POU-specific domain, linker, POU homeodomain, DNA-contacting residues, and variant/PTM neighborhood. Use the actual sequence boundaries for your construct, not guessed residue numbers.

**Interpretation boundary:** PAE evaluates confidence in relative placement, not the actual observed domain orientation. Use PAE to assess how strongly AF3 supports that placement; use coordinate alignment/geometry to measure whether the predicted orientation differs.

### 2.3 Summary confidence metrics

Extract keys when available in the summary JSON:

- `ptm`: global predicted TM-like confidence metric.
- `iptm`: interface-related confidence across the modeled complex; most useful for multi-chain complexes.
- `chain_ptm`: per-chain fold confidence.
- `chain_iptm`: chain interface confidence relative to other chains.
- `chain_pair_iptm`: chain-pair-specific interface confidence (diagonal values are chain pTM; off-diagonal values are chain-pair ipTM according to AF3 output documentation).
- `chain_pair_pae_min`: chain-pair minimum PAE summary.
- `fraction_disordered`: AF3's reported estimate of disordered fraction based on accessible surface area methodology.
- `has_clash`: AF3 clash flag.
- `ranking_score`: ranking composite.
- `chain_ids`: chain ordering for chain-level arrays.

Do not interpret `ranking_score` as a biological-effect score or as a direct accuracy measurement; it is for ranking model samples. Do not interpret global ipTM as meaningful for an isolated single-chain protein. For protein–DNA comparisons, use chain-pair metrics for the protein/DNA chains when available, alongside the PAE block and geometric interface analysis. For very short constructs, TM-type scores may be less informative.

`fraction_disordered` is not interchangeable with the per-residue pLDDT profile and is not an experimental disorder measurement. Treat a change in it as one model-derived summary that needs corroboration.

### 2.4 Contact probabilities

`contact_probs` is a `[num_tokens, num_tokens]` matrix that estimates contact probability between representative atoms (AF3 documents the contact criterion as 8 Å). Use it to assess predicted contacts between region pairs or between protein and DNA, but retain the method's definition and do not confuse contact probability with a contact observed across independently sampled molecular dynamics frames.

Suggested outputs:

- Domain–domain contact probability summaries.
- Protein–DNA contact probability summaries by chain pair or residue region.
- Contact-probability differences from the matched WT condition.
- Heatmaps annotated with chain and domain boundaries.

### 2.5 Reproducibility across seeds and samples

AF3 often produces several samples for each seed. Samples from the same seed must not automatically be treated as independent biological or statistical replicates.

Recommended hierarchy:

1. Keep every sample's raw metrics.
2. Within each seed and condition, summarize the sample distribution (e.g. median and spread, while retaining each sample).
3. Use the seed as the principal replicate for condition-level uncertainty summaries when seeds were run independently.
4. If identical seed values were used across conditions under a matched protocol, calculate per-seed paired differences (variant − WT); otherwise use an unpaired seed-level comparison.
5. Report the number of seeds, samples per seed, excluded predictions, and interval method. For many exploratory comparisons, control the false-discovery rate or clearly label findings as exploratory.

For a design such as 10 seeds × 5 samples per condition, report n=10 seed-level units (with five nested predictions per seed), not n=50 independent replicates. For eight conditions, 10×5 gives 400 prediction files before exclusions; every exclusion must be documented.

---

## 3. Comparative structural framework

### 3.1 Sequence and residue correspondence comes first

Before alignment, make a residue correspondence table from a sequence alignment between each construct and the reference. For deletions or changed construct boundaries, calculate metrics only over residue pairs that have a valid correspondence. Map biological positions to model residue IDs explicitly.

For mutation comparisons, retain the mutated position and nearby residues in the mapping even though the amino acid identity differs. For a deletion comparison, never compare downstream residues solely because they share the same numeric CIF residue ID.

### 3.2 Alignment strategy and RMSD

Calculate several distinct measurements; they answer different questions:

1. **Global common-core Cα RMSD:** align corresponding Cα atoms across a predefined shared structured core. Use this to summarize whole-construct shape agreement, while recognizing that inter-domain motion can inflate global RMSD.
2. **Domain-specific RMSD:** align the POU-specific domain (or other domain of interest) independently, and separately align the POU homeodomain. This tests local domain fold conservation.
3. **Local-window RMSD:** calculate over predefined windows around the PTM, mutation, deletion junction, loop/linker, or DNA-contact surface, provided enough homologous residues remain.
4. **Per-residue displacement:** after fitting on a specified anchor selection, calculate the Cα displacement for each mapped residue. State which region was used for fitting.
5. **Inter-domain orientation change:** fit one domain (e.g. POU-specific domain), then measure displacement/RMSD of the other domain, domain-centroid separation, inter-domain angle, and/or inter-domain contacts without refitting the second domain.

**Critical interpretation detail:** If each domain is independently aligned, global changes in the relative placement of those domains are removed from each domain-level RMSD. Therefore, domain-specific RMSD assesses local fold differences; an anchor-domain fit followed by measuring the second domain is needed to assess relative orientation differences.

RMSD must be computed over matched atom pairs after a defined alignment. Report units (Å), atom selection, residue range/mapping, number of paired residues/atoms, and whether outlier rejection was used. Do not compare RMSD numbers calculated with different atom selections or fit selections as if they were equivalent.

### 3.3 Protein–DNA interface comparison

When DNA is included, record and compare:

- Chain-pair ipTM and protein–DNA PAE block summaries.
- Protein–DNA contact probabilities from `contact_probs`.
- Protein–DNA heavy-atom contacts under a declared distance cutoff (e.g. 4.0–5.0 Å); use the same cutoff and atom filtering across conditions.
- Contacts from known DNA-recognition residues, separately from backbone/phosphate contacts.
- Number and identity of protein residues contacting DNA bases versus DNA backbone, where atom naming/chemistry supports that distinction.
- Hydrogen-bond candidates with distances and angles when hydrogens are available and chemically meaningful.
- Shape/position of the DNA relative to a domain after fitting the protein domain, rather than aligning complexes to each other in a way that erases interface changes.

When comparing protein-only with protein–DNA models, do not directly interpret whole-complex global RMSD because the entities differ. Compare the homologous protein portion and report the DNA interface separately.

### 3.4 PTM-centered local geometry

For each PTM site, define an analysis neighborhood before comparing results—for example, the modified residue plus residues within ±5 or ±10 reference-sequence positions, and/or a spatial neighborhood (e.g. all protein atoms within 8 Å of the PTM group). Report both sequence-window and spatial-neighborhood definitions so results are interpretable if a loop moves.

Measure:

- Local backbone RMSD and per-residue Cα displacement.
- pLDDT/PAE changes in the PTM neighborhood.
- PTM-group orientation and distances to nearby charged/polar residues.
- New/lost close contacts and hydrogen-bond candidates.
- Changes in solvent-accessible surface area (SASA), local pocket geometry, and electrostatic potential only where parameterization is valid.
- Whether changes are repeated across seeds, or are driven by a small subset of samples.

For phosphorylation, consider plausible new electrostatic interactions and charge repulsion but do not infer them from the presence of a phosphate alone. Verify that the modeled PTM has the expected atoms, bonds, and chemistry in the mmCIF.

### 3.5 Hydrogen bonds and contact networks

Use the same atom definitions and distance/angle criteria across conditions. A geometric candidate is not automatically a stable bond. Hydrogen placement, donor/acceptor typing, PTM chemistry, and side-chain protonation affect results.

Report specific edges in a network table:

`condition_id, seed, sample, donor_residue, donor_atom, acceptor_residue, acceptor_atom, distance_A, angle_deg, edge_type, confidence_or_recurrence, notes`.

For AF3 single structures, “present in the predicted model” is appropriate. Do not call a bond “persistent” unless it was assessed over an ensemble or molecular dynamics trajectory with a defined persistence calculation. For hydrogen-bond tools that require explicit hydrogens, add hydrogens using a documented, chemically appropriate method and keep that preparation consistent.

### 3.6 Electrostatic surface and charge

Suitable open-source tools include PDB2PQR + APBS for Poisson–Boltzmann electrostatics and PyMOL/ChimeraX for visualization. However, PTMs require particular care:

- Do not assume a default protein force field or PDB2PQR setup has correct parameters for every non-standard PTM residue.
- Verify phosphate charge, atom types, protonation state, radii, and force-field/CCD support explicitly.
- If no validated PTM parameter set is available, report the electrostatics calculation as unavailable/qualitative rather than generating incomparable maps.
- Apply identical protonation, ionic strength, dielectric, grid, radii, and preparation settings across compared structures.
- Compare surface potential near the PTM site and DNA-binding surface, not just a whole-protein visual impression.

A phosphate group's negative charge may create new salt-bridge possibilities, repel acidic patches, or alter local electrostatic potential; the actual effect depends on local geometry, protonation, solvent, and the selected parameterization.

### 3.7 SASA and pocket volume

Use FreeSASA to calculate residue/atom solvent-accessible surface area with identical settings across models. Compare total protein SASA, residue SASA around the PTM site, and buried surface area at protein–DNA or protein–protein interfaces where appropriate.

For pocket/cavity volumes, tools such as fpocket may be useful, but pocket detection can be unreliable on short segmented domains, low-confidence loops, or structures whose pocket is not a well-defined ligand-binding site. Define the region and parameters in advance and use the same method for every condition. Treat changes as geometric descriptors, not evidence of ligand binding or co-factor recruitment.

---

## 4. Comparison matrix templates

### 4.1 Sample-level metrics table

One row per AF3 prediction:

| condition_id | seed | sample | rank | pTM | ipTM | fraction_disordered | has_clash | mean_pLDDT_protein | mean_pLDDT_POU_S | mean_pLDDT_linker | mean_pLDDT_POU_HD | median_PAE_POU_S_to_HD | median_PAE_protein_to_DNA | DNA_contacts | global_RMSD_A | POU_S_RMSD_A | POU_HD_RMSD_A | PTM_local_RMSD_A | notes |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|

Metrics that do not apply to a condition (e.g. ipTM for a single chain or protein–DNA PAE when no DNA is present) should be `NA`, not zero.

### 4.2 Matched WT-versus-variant table

| comparison_id | variant | matched_WT_condition | factor_changed | region/interaction | metric | WT estimate | variant estimate | delta (variant − WT) | uncertainty/seed interval | direction consistent across seeds? | interpretation tier |
|---|---|---|---|---|---|---:|---:|---:|---|---|---|
| C01 | PTM_01 | WT | PTM | PTM neighborhood | mean/median pLDDT | | | | | | Confidence |
| C02 | PTM_01 | WT | PTM | POU-S fold | Cα RMSD (Å) | | | | | | Structure |
| C03 | PTM_01_DNA | WT_DNA | PTM with DNA held constant | protein–DNA interface | chain-pair ipTM | | | | | | Interface confidence |
| C04 | PTM_01_DNA | WT_DNA | PTM with DNA held constant | DNA-contact residues | contact probability/number | | | | | | Interface geometry |

### 4.3 Region definition table

| region_id | reference positions | definition rationale | use in pLDDT | use in RMSD | use in PAE/contact analysis |
|---|---|---|---|---|---|
| POU_S | explicitly map for construct | POU-specific domain | Yes | Yes | Domain blocks/contacts |
| LINKER | explicitly map for construct | Connecting region | Yes | Optional; often flexible | Domain-block PAE/contacts |
| POU_HD | explicitly map for construct | POU homeodomain | Yes | Yes | Domain blocks/contacts |
| PTM_LOCAL | PTM ± defined sequence window and spatial neighborhood | Local chemistry/geometry | Yes | Yes | Contacts/H-bonds/PAE |
| DNA_INTERFACE | mapped DNA-contacting residues and DNA chain | Interaction surface | Yes | Local interface geometry | Protein–DNA metrics |

Use the actual reference mapping for the modeled Oct4 construct; this table defines the categories, not universal residue-number boundaries.

---

## 5. Statistical and uncertainty plan

For each metric, preserve sample-level data but perform primary condition-level inference at the independent-seed level:

1. Summarize samples within each seed and condition (e.g. median and range/IQR; use the same rule for all conditions).
2. If the same seeds were run under the same setup for WT and variant, calculate matched per-seed differences.
3. Report mean or median effect size, uncertainty interval, sample count, seed count, and excluded-model count.
4. Show raw seed-level points; do not show only a bar of the mean.
5. Predefine primary comparisons (e.g. each PTM versus matched WT, with DNA state held constant). Label post-hoc comparisons as exploratory and use multiple-testing correction for large metric families.
6. Avoid turning arbitrary thresholds into pass/fail biological conclusions. Use effect magnitude, repeatability, confidence context, and independent evidence together.

Useful plots:

- pLDDT profiles: reference position on x-axis, pLDDT on y-axis, condition as line/color, domain boundaries and modified positions annotated.
- PAE heatmaps: token/region boundaries labeled; separate plots or panels per matched condition.
- Seed-level condition distributions for region pLDDT, PAE blocks, RMSDs, contacts, and interface scores.
- Pairwise condition matrices for structural similarity, calculated with the same residue mapping and fit strategy.
- Residue-displacement plots after anchor-domain superposition.
- Contact/H-bond network diagrams only for robust, interpretable edges.
- Representative structural overlays colored by displacement, with low-confidence regions visible in a separate confidence view.

---

## 6. Open-source tools and command patterns

### Core recommended stack

| Tool | Role | Recommended use |
|---|---|---|
| Python + NumPy + pandas + SciPy + Matplotlib | Data processing, statistics, plots | Required workflow backbone |
| Biopython (`Bio.PDB`) | mmCIF parsing, sequence handling, coordinate superposition | Core structural calculations |
| PyMOL (open-source build where available) | Structural overlays, colors, publication images | Interactive inspection/figure generation |
| UCSF ChimeraX | Structure alignment, sequence-structure views, interface inspection | Alternative GUI workflow; check local license/edition terms for usage |
| MDAnalysis or MDTraj | Atom selections, contacts, hydrogen-bond geometry, ensemble trajectory analysis | Optional deeper analysis |
| FreeSASA | Total/residue/atom SASA | Optional but useful |
| PDB2PQR + APBS | Electrostatic potential | Only with verified PTM parameters/protonation |
| fpocket | Predicted pocket/cavity detection | Optional, only when biologically appropriate |
| Reduce or another validated hydrogen-placement tool | Add/check hydrogens before geometry-based H-bond analysis | Optional, with documented preparation |

Example environment commands (adapt for the university cluster and available modules):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy pandas scipy matplotlib biopython
python -m pip install MDAnalysis mdtraj
```

Install PyMOL, FreeSASA, APBS, PDB2PQR, and fpocket using a supported package manager or the university's software modules. Package availability varies by operating system; record versions in the analysis manifest. Do not install heavy visualization or modeling tools on a compute node unless allowed by local policy.

### 6.1 Quick PyMOL overlay (same chain/residue mapping required)

Save as `compare.pml` and run with `pymol -cq compare.pml` (or open in the PyMOL GUI). Replace example residue ranges with validated selections for the modeled construct.

```pymol
load WT_model.cif, wt
load PTM_model.cif, ptm
hide everything
show cartoon, wt or ptm
color gray70, wt
color cyan, ptm

# Example only: fit variant to WT using the shared, well-structured domain core.
# The two selections must identify corresponding residues/atoms.
# If numbering differs because of truncations/deletions, generate mapped selections first.
align ptm and chain A and name CA and resi 10-60, wt and chain A and name CA and resi 10-60

# After the fit, report displacement on a different region WITHOUT refitting it.
# Inspect visually and color variant pLDDT from the B-factor field if desired.
spectrum b, blue_white_red, ptm, 50, 90
select ptm_site, ptm and chain A and resi 101
show sticks, ptm_site
color yellow, ptm_site
set cartoon_transparency, 0.15
orient wt or ptm
```

PyMOL's `align` performs sequence alignment followed by structural superposition with optional outlier rejection. For similar proteins, it is convenient; for variants with altered sequences or nontrivial deletions, a validated explicit residue correspondence or a domain-focused alignment may be more appropriate. Always report the fitting selection and the final RMSD; a displayed overlay alone is not quantitative evidence.

For the structural-shift figure, fit on a reference domain (for example, POU-specific domain), then visualize/measure the second domain and linker without fitting them independently. Use separate views for per-atom pLDDT (confidence) and geometric displacement (difference).

### 6.2 Biopython superposition skeleton (explicit residue mapping)

The following example assumes the reference and mobile models have already been parsed and a correct reference-position-to-model-residue mapping has been constructed. It illustrates the fit and per-residue displacement; it is not a substitute for validating that mapping.

```python
import numpy as np
from Bio.PDB import MMCIFParser, Superimposer

parser = MMCIFParser(QUIET=True)
ref = parser.get_structure("WT", "WT_model.cif")
mobile = parser.get_structure("PTM", "PTM_model.cif")
ref_chain = ref[0]["A"]
mobile_chain = mobile[0]["A"]
# Simple residue-number dictionaries for this illustrative example; include modified polymer residues with a C-alpha.
# Production code should use a compound key (hetero flag, residue number, insertion code, residue name).
ref_residues = {r.id[1]: r for r in ref_chain if "CA" in r and r.resname not in {"HOH", "WAT"}}
mobile_residues = {r.id[1]: r for r in mobile_chain if "CA" in r and r.resname not in {"HOH", "WAT"}}

# Keys are positions in the shared reference coordinate system.
# Values are the actual mmCIF residue numbers for each structure.
# Replace with a mapping produced from a validated sequence alignment.
ref_to_wt_model = {i: i for i in range(10, 61)}
ref_to_variant_model = {i: i for i in range(10, 61)}
shared_reference_positions = sorted(set(ref_to_wt_model) & set(ref_to_variant_model))

fixed_atoms = []
moving_atoms = []
valid_positions = []
for ref_pos in shared_reference_positions:
    wt_id = ref_to_wt_model[ref_pos]
    var_id = ref_to_variant_model[ref_pos]
    if wt_id in ref_residues and var_id in mobile_residues:
        if "CA" in ref_residues[wt_id] and "CA" in mobile_residues[var_id]:
            fixed_atoms.append(ref_residues[wt_id]["CA"])
            moving_atoms.append(mobile_residues[var_id]["CA"])
            valid_positions.append(ref_pos)

if len(fixed_atoms) < 3:
    raise ValueError("Fewer than 3 valid corresponding C-alpha pairs; check residue mapping.")

superimposer = Superimposer()
superimposer.set_atoms(fixed_atoms, moving_atoms)
fit_rmsd_A = float(superimposer.rms)
superimposer.apply(list(mobile.get_atoms()))

per_residue_displacement_A = {}
for ref_pos in valid_positions:
    wt_id = ref_to_wt_model[ref_pos]
    var_id = ref_to_variant_model[ref_pos]
    per_residue_displacement_A[ref_pos] = float(np.linalg.norm(
        ref_residues[wt_id]["CA"].coord - mobile_residues[var_id]["CA"].coord
    ))

print(f"Fit RMSD: {fit_rmsd_A:.3f} Å over {len(valid_positions)} C-alpha pairs")
for pos, delta in per_residue_displacement_A.items():
    print(pos, f"{delta:.3f} Å")
```

Important: The example uses integer residue IDs for simplicity. mmCIFs can include insertion codes, hetero-residue IDs, modified residues, and numbering that does not match reference sequence coordinates. A production implementation should use a compound residue key (chain, residue number, insertion code, residue name) and a separate reference-position mapping. Do not use the illustrative `10:61` mapping without checking the real model.

### 6.3 Reading AF3 confidence JSON

```python
import json
import numpy as np

path = "WT_seed-1234_sample-0_confidences.json"
with open(path, encoding="utf-8") as handle:
    confidence = json.load(handle)

pae = np.asarray(confidence["pae"], dtype=float)
contact_probs = np.asarray(confidence["contact_probs"], dtype=float)
token_chain_ids = confidence["token_chain_ids"]
token_res_ids = confidence["token_res_ids"]
atom_plddts = np.asarray(confidence["atom_plddts"], dtype=float)
atom_chain_ids = confidence["atom_chain_ids"]

assert pae.ndim == 2 and pae.shape[0] == pae.shape[1]
assert pae.shape[0] == len(token_chain_ids) == len(token_res_ids)
assert contact_probs.shape == pae.shape
print("PAE shape:", pae.shape)
print("Atoms with pLDDT:", len(atom_plddts))
print("Available keys:", sorted(confidence.keys()))
```

This loads the fields documented by AF3; mapping token indices to residues must use the JSON token arrays and the coordinate-file mapping. Do not index the PAE matrix with raw sequence position numbers. For residue-level pLDDT, use mmCIF atom records/B factors and validate atom counts/order against `atom_plddts`.

### 6.4 Electrostatics workflow (only with PTM-aware parameters)

Conceptually:

1. Validate protonation and PTM component chemistry.
2. Prepare the same protein/complex selection for each condition.
3. Generate PQR using a parameterization that explicitly supports every included residue, including PTMs.
4. Run APBS with matched dielectric, ionic strength, grid, and boundary settings.
5. Compare potential on a consistent surface/grid and inspect the PTM and DNA-binding regions.

A command such as `pdb2pqr --ff=AMBER input.pdb output.pqr` is only an example for supported standard residues. Do **not** assume it correctly parameterizes phosphoserine/phosphothreonine, glycosylated residues, custom CCD components, or other non-standard chemistry. Resolve missing parameters before using the map for biological inference.

---

## 7. Interpretation checklist for Oct4 / POU models

### Confidence and local structure

- Is the effect localized near the modified residue or spread across a domain/linker?
- Does per-residue pLDDT change consistently across independent seeds, or only in isolated samples?
- Does the change involve a structured core, an exposed loop, or a low-confidence linker?
- Does PAE support the relative placement of affected regions, or are the domains independently plausible but mutually uncertain?
- Is the apparent “disordering” only a pLDDT decrease, a change in AF3 `fraction_disordered`, or both? What independent support exists?

### Domain arrangement and geometry

- Does the POU-specific domain retain its local fold after core alignment?
- Does the POU homeodomain retain its local fold after independent alignment?
- After fitting one domain, does the other domain shift relative to it?
- Are changes in global RMSD driven by real domain reorientation, local deformation, residue mapping, or an altered construct length?
- Are the same changes seen in most seeds, and are they larger than ordinary WT model-to-model variation?

### DNA binding

- Were protein and DNA inputs matched exactly between the comparison pair?
- Are the protein–DNA interface metrics (chain-pair ipTM, PAE, contact probabilities, geometric contacts) concordant?
- Are changes concentrated at known or hypothesized base-recognition residues, DNA-backbone contacts, or the inter-domain DNA-binding arrangement?
- Does the protein shift after a domain-based fit in a way that changes DNA pose or contacts?
- Is any conclusion based only on global ipTM or visual inspection? If so, add interface-specific metrics.

### PTM chemistry and local interactions

- Is the PTM actually represented in the final model with the expected component and atoms?
- Is the modified site solvent-exposed or buried in the predicted model?
- Does the PTM introduce plausible salt bridges, repulsion, hydrogen bonds, or steric constraints?
- Are the chemistry and charge assignments valid for the analysis tool used?
- Does the conclusion persist across predicted samples and after considering the local pLDDT/PAE?

### Cofactor recruitment and functional hypotheses

- Does the predicted structure expose, occlude, or reshape a plausible interaction surface?
- Is there a modeled cofactor/partner, or is recruitment inferred from a single protein-only structure? Treat the latter as a hypothesis, not a prediction of binding affinity.
- Are there known experimental data, validated interaction structures, mutagenesis data, or literature observations to support the proposed mechanism?
- Could a result be explained by AF3 input representation, PTM tokenization, missing binding partners, construct truncation, or MSA/template differences instead of a biological effect?
- What independent experiment would distinguish the leading hypotheses (e.g. DNA-binding assay, interaction assay, PTM validation, NMR/HDX-MS, or structural experiment)?

---

## 8. Minimum quality-control and reporting checklist

A comparison is ready for interpretation only when:

- [ ] The exact input JSON and condition metadata are archived.
- [ ] Sequence and PTM identity were checked against the model mmCIF.
- [ ] Reference positions are explicitly mapped for mutations, deletions, and truncations.
- [ ] All samples/seeds are accounted for; exclusions have documented reasons.
- [ ] JSON array dimensions and atom/token mappings pass validation.
- [ ] pLDDT summaries specify how atoms were aggregated into residues/regions.
- [ ] PAE summaries specify which tokens/regions were used and whether directionality was preserved.
- [ ] RMSD reports specify alignment selection, atom type, residue mapping, fit size, and units.
- [ ] Protein-only and protein–DNA comparisons use appropriate matched subsets.
- [ ] PTM geometry/electrostatic calculations use verified chemistry/parameters or are marked unavailable.
- [ ] Seed/sample hierarchy is respected in statistical summaries.
- [ ] Plots show variability and are not based only on the top-ranked model.
- [ ] Confidence, geometry, and biological inference are reported separately.
- [ ] All claims are phrased as model-supported hypotheses unless independently validated.

## 9. Recommended output directory layout

```text
analysis/
  config/
    conditions.csv
    regions.csv
    residue_mapping.csv
    analysis_config.yaml
  data/
    manifest.csv
    plddt_per_atom.csv
    plddt_per_residue.csv
    pae_block_metrics.csv
    interface_metrics.csv
    structural_metrics.csv
    hydrogen_bonds.csv
    sasa_metrics.csv
    electrostatics_metrics.csv
    qc_report.csv
  tables/
    sample_level_metrics.csv
    seed_aggregated_metrics.csv
    matched_wt_deltas.csv
    condition_summary.csv
  figures/
    plddt_profiles/
    pae_heatmaps/
    rmsd_matrices/
    displacement_maps/
    interface_comparisons/
    representative_overlays/
  logs/
    processing.log
    exclusions.csv
    software_versions.txt
  reports/
    workflow_summary.md
    limitations.md
```

Some analyses are conditional: for example, protein–DNA metrics require DNA-containing predictions, while APBS outputs require valid PTM-aware parameterization. The pipeline should label these outputs `not_applicable`, `not_run`, or `failed_validation` rather than silently filling them with zeroes.

---

## 10. References and official documentation

1. AlphaFold 3 official output documentation (output files, confidence JSON fields, pLDDT, PAE, pTM/ipTM, chain-pair metrics, optional arrays): https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md
2. AlphaFold 3 official input documentation (including user-provided CCD inputs): https://github.com/google-deepmind/alphafold3/blob/main/docs/input.md
3. EMBL-EBI AlphaFold training: how to assess AF3 prediction quality: https://www.ebi.ac.uk/training/online/courses/alphafold/alphafold-3-and-alphafold-server/how-to-assess-the-quality-of-alphafold-3-predictions/
4. Biopython structural superposition documentation: https://biopython.org/wiki/The_Biopython_Structural_Bioinformatics_FAQ
5. PyMOL command reference: https://pymol.org/pymol-command-ref.html
6. ChimeraX Matchmaker documentation: https://www.rbvi.ucsf.edu/chimerax/docs/user/tools/matchmaker.html
7. MDAnalysis alignment documentation: https://docs.mdanalysis.org/stable/documentation_pages/analysis/align.html
8. MDTraj hydrogen-bond analysis documentation: https://mdtraj.readthedocs.io/en/stable/notebook-examples/hbonds.html
9. FreeSASA: https://freesasa.github.io/
10. PDB2PQR and APBS documentation: https://pdb2pqr.readthedocs.io/en/latest/ and https://apbs.readthedocs.io/
