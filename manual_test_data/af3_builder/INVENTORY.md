# Inventory

Every file in this manual test pack, with its size and SHA-256. The pack is
input only: no workflow writes here, and `tests/e2e/test_manual_test_data.py`
asserts the tree is unchanged after a full run.

| File | Bytes | SHA-256 |
|---|---:|---|
| `batch/base_job_custom_ccd.json` | 1082 | `a8c28b4be89bddd4f0641576f2311ea368d1b449c14b795bcc11e9395b254172` |
| `batch/dna_sequences.txt` | 18 | `0e53b0c8927702bd066c5bc211c1b2e150e5518a3639f7e94a7d97b897e8516f` |
| `batch/empty.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `batch/invalid_sequence.txt` | 24 | `d9a25f012c525420020da0845a1286aea67035a21250843dc32f7afbbc66133f` |
| `batch/ligands_ccd_codes.txt` | 410 | `cc527244daea97367a4e01a03a7b0e922b4e956aecf003bdfe5522c622087732` |
| `batch/ligands_ccd_lookalike.smiles` | 157 | `2dbb8248dbdf9701a5c372317c77fdf17068f630dcaef87f9a9dfbf4550b9063` |
| `batch/ligands_duplicate_entries.smiles` | 86 | `03ad798e9d49e31358633f01c068f3380bf78e27aea6d1a7b0b62d3483b58857` |
| `batch/ligands_duplicate_names.smiles` | 119 | `452e8101387c6101f4270d8b6836a8b4943e1b0055590f817d159cee125efba1` |
| `batch/ligands_empty.smiles` | 73 | `1306db6a2d66cbad88d46a10b9c09d752805a68ab0fe6b344082a26dc7fa0cac` |
| `batch/ligands_named.smiles` | 166 | `d6c79dc6e33c29ec86a1df023b288cd50c7e88486082c7072fecec187d45daaa` |
| `batch/ligands_notation_edges.smiles` | 584 | `0a0b398a29076d1e0346a2779a76861347322f08058d1dfbc3088d2f11f4f70f` |
| `batch/ligands_unchecked_syntax.smiles` | 198 | `486f5327cb83abea84c17379d481f70bce9aac0da69849cc0d35c61926b0de79` |
| `batch/ligands_valid.smiles` | 171 | `3bfa132f606b982c6d7f6e971b5539591e0489f01e6b16f974f409cae140ea47` |
| `batch/proteins_minimal.txt` | 17 | `553a95a15312667d56d3ef663dff45f8e5775aa40e2479750103f2aabb4bd5fa` |
| `batch/proteins_valid.txt` | 55 | `dbef49619c3561b030f5ac81005912f6eb23652b14fadff930ad9769d7d31d4b` |
| `batch/proteins_wrapped_fasta.txt` | 88 | `c9b68c46c5982e007b45e0e20d18e2887c6ebf6c267ba8abdb7e0276c6352e70` |
| `batch/README.md` | 19791 | `e9749458bca652e4fb3dce963e6d2443fc5e7ff9657c631535d725792581475e` |
| `batch/rna_sequences.txt` | 26 | `04b8a59fdec9c83a6b19c98f963e4b6a6e51dc882fd3c3a1680c3b9ffad33f1a` |
| `inputs/multi_ligand_small_protein_test.txt` | 602 | `d35b09e3218ae3ee4584378d62ed6dd70435763312d7d2227907f122776f9132` |
| `msa/protein/paired-query.a3m` | 57 | `5083e390bad4cbafc1b95c239e86c43a8da06cbeb0ee28671cb15a4aeba67498` |
| `msa/protein/unpaired-query.a3m` | 60 | `9d6d705cb186ab91c11e05506bfd54601a8faec3fff4f3d71e020fd714306d83` |
| `msa/rna/query-rna.a3m` | 32 | `8ba7564af33a5d103975ff1658e580b7019e1a044f3c4d4752cb8cb88ae32ec3` |
| `msa/with spaces/rna query.a3m` | 32 | `8ba7564af33a5d103975ff1658e580b7019e1a044f3c4d4752cb8cb88ae32ec3` |
| `README.md` | 25379 | `e7d341095fa91e96f0983a1cad9df3a65917b84e6386b858563282e61c6ee462` |
| `templates/minimal_template.cif` | 566 | `0ff680248aa438d89897439735fb8e3f760414a9858c9c4e8e038f6194fe1ca6` |
| `templates/README.md` | 8955 | `4a084e566ae91f28031c65a635433ce667b40fa1dc0eb8666bb8bf7e3aab475d` |
| `templates/template_empty.cif` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `templates/template_fully_resolved.cif` | 1283 | `25dc33c9405d3973236c38027eb536814362966beb2ddd64a274e4457f33cf05` |
| `templates/template_malformed.cif` | 469 | `0582d265ed596964f431f0056cf28467d618a3a76113ec28b2d48673a624bd2c` |
| `templates/template_no_records.cif` | 404 | `07c5441ada254cc9ae604048de299910d8f4f6bd0311a899728370447b2c9d6b` |
| `templates/template_unresolved_residues.cif` | 1635 | `eea8b8850e34974cf66dcb8807aaf32a8911e461035c8dde86956141261d42f0` |
| `templates/with spaces/template with spaces.cif` | 566 | `0ff680248aa438d89897439735fb8e3f760414a9858c9c4e8e038f6194fe1ca6` |
