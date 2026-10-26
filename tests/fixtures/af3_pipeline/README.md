# AF3 pipeline fixtures

Every JSON file below was generated **through the application pipeline**
(application services → canonical model → validation → variants → transform
→ serializer → output). Nothing here is hand-written; `batch_sequences.txt`
in test26 is pipeline *input*, marked INPUT.

Regenerate with::

    python fixtures/af3_pipeline/generate_fixtures.py

Verify byte-determinism with::

    python fixtures/af3_pipeline/generate_fixtures.py --check

| Test | Purpose | Files written by the pipeline |
| ---- | ------- | ----------------------------- |
| test01_protein_minimal | Smallest valid protein configuration | `test01_protein_minimal/test01-protein-minimal/test01-protein-minimal.json` |
| test02_protein_msa | Protein with paired+unpaired MSA (both mode) | `test02_protein_msa/test02-protein-msa/test02-protein-msa.json` |
| test03_protein_template | Protein with an explicit structural template | `test03_protein_template/test03-protein-template/test03-protein-template.json` |
| test04_protein_msa_template | Protein with MSA and template together | `test04_protein_msa_template/test04-protein-msa-template/test04-protein-msa-template.json` |
| test05_rna_minimal | Smallest valid RNA configuration | `test05_rna_minimal/test05-rna-minimal/test05-rna-minimal.json` |
| test06_rna_msa | RNA with a provided (single) MSA | `test06_rna_msa/test06-rna-msa/test06-rna-msa.json` |
| test07_dna_duplex | One DNA input; pipeline builds the reverse-complement strand | `test07_dna_duplex/test07-dna-duplex/test07-dna-duplex.json` |
| test08_protein_dna | Protein + DNA duplex complex | `test08_protein_dna/test08-protein-dna/test08-protein-dna.json` |
| test09_two_proteins | Two protein entities, unique deterministic IDs | `test09_two_proteins/test09-two-proteins/test09-two-proteins.json` |
| test10_protein_rna | Mixed protein/RNA configuration | `test10_protein_rna/test10-protein-rna/test10-protein-rna.json` |
| test11_protein_ccd_ligand | Ligand via CCD code (ATP) | `test11_protein_ccd_ligand/test11-protein-ccd-ligand/test11-protein-ccd-ligand.json` |
| test12_protein_smiles_ligand | Ligand via SMILES notation (set_representation notation route) | `test12_protein_smiles_ligand/test12-protein-smiles-ligand/test12-protein-smiles-ligand.json` |
| test13_protein_ion | Ion through the ligand representation (NA) | `test13_protein_ion/test13-protein-ion/test13-protein-ion.json` |
| test14_protein_water_ions | Water and ions (HOH NA CL as one multi-code ligand) | `test14_protein_water_ions/test14-protein-water-ions/test14-protein-water-ions.json` |
| test15_single_ptm | One modified residue (SEP at position 3) | `test15_single_ptm/test15-single-ptm/test15-single-ptm.json` |
| test16_multiple_ptms | Two independent modifications (SEP@3, TPO@7) | `test16_multiple_ptms/test16-multiple-ptms/test16-multiple-ptms.json` |
| test17_protein_dna_ptm | Protein + DNA + modification integration | `test17_protein_dna_ptm/test17-protein-dna-ptm/test17-protein-dna-ptm.json` |
| test18_protein_dna_ligand | Protein + DNA + ligand integration | `test18_protein_dna_ligand/test18-protein-dna-ligand/test18-protein-dna-ligand.json` |
| test19_protein_rna_ligand_ion | Multi-component mixed system | `test19_protein_rna_ligand_ion/test19-mixed-components/test19-mixed-components.json` |
| test20_comprehensive | All supported features in one configuration | `test20_comprehensive/test20-comprehensive/test20-comprehensive.json` |
| test21_two_proteins_dna | Identity: two proteins + duplex, all IDs unique | `test21_two_proteins_dna/test21-identity-check/test21-identity-check.json` |
| test22_custom_chemistry | Custom ligand chemistry via inline userCCD | `test22_custom_chemistry/test22-custom-chemistry/test22-custom-chemistry.json` |
| test23_multiple_ligands | Three ligand entities with unique IDs | `test23_multiple_ligands/test23-multiple-ligands/test23-multiple-ligands.json` |
| test24_single_variant | Base + one variant; base unchanged | `test24_single_variant/test24-single-variant/manifest.json`, `test24_single_variant/test24-single-variant/test24-single-variant.json`, `test24_single_variant/test24-single-variant/test24-single-variant__sep3/test24-single-variant__sep3.json` |
| test25_independent_variants | Three independent one-edit variants from the same base | `test25_independent_variants/test25-independent-variants/manifest.json`, `test25_independent_variants/test25-independent-variants/test25-independent-variants.json`, `test25_independent_variants/test25-independent-variants/test25-independent-variants__va-ptm/test25-independent-variants__va-ptm.json`, `test25_independent_variants/test25-independent-variants/test25-independent-variants__vb-seq/test25-independent-variants__vb-seq.json`, `test25_independent_variants/test25-independent-variants/test25-independent-variants__vc-seeds/test25-independent-variants__vc-seeds.json` |
| test26_batch_variants | Batch variants from a sequence file (independent, deterministic) | `test26_batch_variants/batch_sequences.txt`, `test26_batch_variants/test26-batch-variants/manifest.json`, `test26_batch_variants/test26-batch-variants/test26-batch-variants.json`, `test26_batch_variants/test26-batch-variants/test26-batch-variants__batch-01/test26-batch-variants__batch-01.json`, `test26_batch_variants/test26-batch-variants/test26-batch-variants__batch-02/test26-batch-variants__batch-02.json`, `test26_batch_variants/test26-batch-variants/test26-batch-variants__batch-03/test26-batch-variants__batch-03.json` |

## Audit notes (implementation characteristics, documented not corrected)

- TEST 12 (SMILES): the single-field ligand classifier
  (`ConfigurationService._ligand_representation`) maps any space-free
  token to `ccdCodes` first; `ComponentCode` is deliberately lenient
  because codes are matched against the CCD at deployment time. The
  SMILES representation therefore goes through the explicit typed
  route `set_representation(key, notation=...)`, which emits `smiles`.
- TEST 14 (water/ions): `HOH NA CL` is one ligand entity with a
  multi-code `ccdCodes` list (the contract's multi-component ligand
  representation), not three entities.
- Templates (TEST 03/04/20): template content is carried inline in
  the `mmcif` field with explicit `queryIndices`/`templateIndices`.
- Variants (TEST 24-26): the committed `<base>.json` beside each run
  is the base's own generation (expansion never mutates it); batch
  names are `batch_NN` from input order; no sequence text enters a
  file name.
