"""AF3 pipeline fixture generator (tests/fixtures/af3_pipeline).

Every fixture JSON here is produced by the **actual application pipeline** —
application services (ProjectService → ConfigurationService →
ValidationService → VariantService → GenerationService) — never by writing
a Python dictionary to disk. ``generate_all`` runs each test's builder,
which drives the real ``plan_base`` / ``plan`` + ``execute`` route, so the
committed files are exactly what the deployed tool writes.

Input files that are *not* generated JSON (the batch sequence list for
TEST 26) are marked ``INPUT`` in the manifest; everything else is
pipeline output.

Usage::

    python tests/fixtures/af3_pipeline/generate_fixtures.py            # build all
    python tests/fixtures/af3_pipeline/generate_fixtures.py --check    # verify determinism
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from configbuilder.app.configuration_service import ConfigurationService, ReferenceInput  # noqa: E402
from configbuilder.app.generation_service import GenerationService  # noqa: E402
from configbuilder.app.project_service import ProjectService  # noqa: E402
from configbuilder.app.validation_service import ValidationService  # noqa: E402
from configbuilder.app.variant_service import VariantService  # noqa: E402

FIXTURE_ROOT = Path(__file__).resolve().parent

# Deterministic synthetic test content (no thesis-specific sequences).
PROTEIN_A = "ACDEFGHIKL"
PROTEIN_B = "MNPQRSTVWY"
PROTEIN_C = "GKKIGYS"
RNA_D = "GGCACU"
DNA_C = "ATGCCGA"
SMILES = "C(C)O"  # ethanol; contains parens so it cannot be a CCD code (see README)
MSCIF_TEMPLATE = """data_template
#
# Inline structural template for the pipeline fixtures: a ten-residue protein
# chain with coordinates for its first three residues. Real mmCIF, because
# ``mmcif`` is mmCIF content (not a FASTA alignment), and the builder checks
# that before attaching it: a string that is not a structure is refused.
#
_entity_poly.entity_id 1
_entity_poly.type 'polypeptide(L)'
_entity_poly.pdbx_strand_id A
_entity_poly.pdbx_seq_one_letter_code ACDEFGHIKL
#
loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
1 1 ALA
1 2 CYS
1 3 ASP
1 4 GLU
1 5 PHE
1 6 GLY
1 7 HIS
1 8 ILE
1 9 LYS
1 10 LEU
#
loop_
_struct_asym.id
_struct_asym.entity_id
A 1
#
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
ATOM 1 C CA ALA A 1 0.000 0.000 0.000
ATOM 2 C CA CYS A 2 3.800 0.100 0.200
ATOM 3 C CA ASP A 3 7.400 -0.300 0.900
#
"""
USER_CCD = "data_LIG\n_chem_comp.id LIG\n_chem_comp.formula 'C1 H4'\n"
MSA_TEXT = ">Protein_A\n%s\n" % PROTEIN_A
RNA_MSA_TEXT = ">RNA_D\n%s\n" % RNA_D


class Pipeline:
    """One open project driven through the real application services."""

    def __init__(self, name: str) -> None:
        self.projects = ProjectService()
        self.validation = ValidationService(self.projects)
        self.configuration = ConfigurationService(self.projects)
        self.variants = VariantService(self.projects, self.configuration)
        self.generation = GenerationService(self.projects, self.variants, validation=self.validation)
        self.projects.new(name)
        self.configuration.set_format_target(version=4)

    def seeds(self, values) -> None:
        self.configuration.set_seeds(values)

    def generate_base(self, out_root: Path):
        plan = self.generation.plan_base(str(out_root))
        if not plan.ok:
            raise RuntimeError("plan_base failed: %s" % plan.message)
        result = self.generation.execute(plan)
        if not result.ok:
            raise RuntimeError("execute failed: %s" % (result.errors,))
        return result

    def generate_variants(self, out_root: Path, only=None):
        plan = self.generation.plan(str(out_root), only=only)
        if not plan.ok:
            raise RuntimeError("plan failed: %s" % plan.message)
        result = self.generation.execute(plan)
        if not result.ok:
            raise RuntimeError("execute failed: %s" % (result.errors,))
        return result

    def blocking(self):
        return self.validation.validate_base().report.blocking()


def _run(builder, out_root: Path):
    """Run one test builder into a clean directory; return (files, blocking)."""
    target = out_root
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    files = builder(target)
    return files


# -- TEST 01 — minimal protein ------------------------------------------------


def test01(root: Path):
    pipe = Pipeline("Test01 Protein Minimal")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.generate_base(root)
    return {}


# -- TEST 02 — protein with paired + unpaired MSA -----------------------------


def test02(root: Path):
    pipe = Pipeline("Test02 Protein MSA")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.set_alignment("A", "both", inline_text=MSA_TEXT)
    pipe.generate_base(root)
    return {}


# -- TEST 03 — protein with a template ----------------------------------------


def test03(root: Path):
    pipe = Pipeline("Test03 Protein Template")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.set_references(
        "A",
        references=[ReferenceInput(inline_text=MSCIF_TEMPLATE, pairs=[(1, 1), (2, 2)])],
    )
    pipe.generate_base(root)
    return {}


# -- TEST 04 — protein with MSA + template ------------------------------------


def test04(root: Path):
    pipe = Pipeline("Test04 Protein MSA Template")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.set_alignment("A", "both", inline_text=MSA_TEXT)
    pipe.configuration.set_references(
        "A",
        references=[ReferenceInput(inline_text=MSCIF_TEMPLATE, pairs=[(1, 1), (2, 2)])],
    )
    pipe.generate_base(root)
    return {}


# -- TEST 05 — minimal RNA -----------------------------------------------------


def test05(root: Path):
    pipe = Pipeline("Test05 RNA Minimal")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("rna", RNA_D)
    pipe.generate_base(root)
    return {}


# -- TEST 06 — RNA with MSA ----------------------------------------------------


def test06(root: Path):
    pipe = Pipeline("Test06 RNA MSA")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("rna", RNA_D)
    pipe.configuration.set_alignment("A", "provided", inline_text=RNA_MSA_TEXT)
    pipe.generate_base(root)
    return {}


# -- TEST 07 — DNA duplex ------------------------------------------------------


def test07(root: Path):
    pipe = Pipeline("Test07 DNA Duplex")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("dna", DNA_C)
    pipe.generate_base(root)
    return {}


# -- TEST 08 — protein + DNA duplex --------------------------------------------


def test08(root: Path):
    pipe = Pipeline("Test08 Protein DNA")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("dna", DNA_C)
    pipe.generate_base(root)
    return {}


# -- TEST 09 — two proteins ----------------------------------------------------


def test09(root: Path):
    pipe = Pipeline("Test09 Two Proteins")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("protein", PROTEIN_B)
    pipe.generate_base(root)
    return {}


# -- TEST 10 — protein + RNA ---------------------------------------------------


def test10(root: Path):
    pipe = Pipeline("Test10 Protein RNA")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("rna", RNA_D)
    pipe.generate_base(root)
    return {}


# -- TEST 11 — protein + CCD ligand --------------------------------------------


def test11(root: Path):
    pipe = Pipeline("Test11 Protein CCD Ligand")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("ligand", representation="ATP")
    pipe.generate_base(root)
    return {}


# -- TEST 12 — protein + SMILES ligand -----------------------------------------


def test12(root: Path):
    pipe = Pipeline("Test12 Protein SMILES Ligand")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    added = pipe.configuration.add_record("ligand", representation=SMILES)
    assert added.ok, added.message
    # Audit finding (README): the single-field classifier prefers CCD codes
    # for any space-free token, so the SMILES representation is set through
    # the application's explicit typed route, set_representation(notation=).
    key = pipe.projects.project.configuration.records[-1].ids.primary.value
    typed = pipe.configuration.set_representation(key, notation=SMILES)
    assert typed.ok, typed.message
    pipe.generate_base(root)
    return {}


# -- TEST 13 — protein + ion ---------------------------------------------------


def test13(root: Path):
    pipe = Pipeline("Test13 Protein Ion")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("ligand", representation="NA")
    pipe.generate_base(root)
    return {}


# -- TEST 14 — protein + HOH + Na + Cl ------------------------------------------


def test14(root: Path):
    pipe = Pipeline("Test14 Protein Water Ions")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("ligand", representation="HOH NA CL")
    pipe.generate_base(root)
    return {}


# -- TEST 15 — single PTM -------------------------------------------------------


def test15(root: Path):
    pipe = Pipeline("Test15 Single PTM")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_modification("A", "SEP", 3)
    pipe.generate_base(root)
    return {}


# -- TEST 16 — multiple PTMs -----------------------------------------------------


def test16(root: Path):
    pipe = Pipeline("Test16 Multiple PTMs")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_modification("A", "SEP", 3)
    pipe.configuration.add_modification("A", "TPO", 7)
    pipe.generate_base(root)
    return {}


# -- TEST 17 — protein + DNA + PTM -----------------------------------------------


def test17(root: Path):
    pipe = Pipeline("Test17 Protein DNA PTM")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_modification("A", "SEP", 3)
    pipe.configuration.add_record("dna", DNA_C)
    pipe.generate_base(root)
    return {}


# -- TEST 18 — protein + DNA + ligand ---------------------------------------------


def test18(root: Path):
    pipe = Pipeline("Test18 Protein DNA Ligand")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("dna", DNA_C)
    pipe.configuration.add_record("ligand", representation="ATP")
    pipe.generate_base(root)
    return {}


# -- TEST 19 — protein + RNA + ligand + ion ----------------------------------------


def test19(root: Path):
    pipe = Pipeline("Test19 Mixed Components")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("rna", RNA_D)
    pipe.configuration.add_record("ligand", representation="ATP")
    pipe.configuration.add_record("ligand", representation="MG")
    pipe.generate_base(root)
    return {}


# -- TEST 20 — comprehensive integration --------------------------------------------


def test20(root: Path):
    pipe = Pipeline("Test20 Comprehensive")
    pipe.seeds([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.set_alignment("A", "both", inline_text=MSA_TEXT)
    pipe.configuration.set_references(
        "A",
        references=[ReferenceInput(inline_text=MSCIF_TEMPLATE, pairs=[(1, 1), (2, 2)])],
    )
    pipe.configuration.add_modification("A", "SEP", 3)
    pipe.configuration.add_record("dna", DNA_C)
    pipe.configuration.add_record("ligand", representation="ATP")
    pipe.configuration.add_record("ligand", representation="NA")
    pipe.generate_base(root)
    return {}


# -- TEST 21 — two proteins + DNA (identity) ------------------------------------------


def test21(root: Path):
    pipe = Pipeline("Test21 Identity Check")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("protein", PROTEIN_B)
    pipe.configuration.add_record("dna", DNA_C)
    pipe.generate_base(root)
    return {}


# -- TEST 22 — custom chemistry (userCCD) ----------------------------------------------


def test22(root: Path):
    pipe = Pipeline("Test22 Custom Chemistry")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("ligand", representation="LIG")
    pipe.configuration.set_component_definition(inline_text=USER_CCD)
    pipe.generate_base(root)
    return {}


# -- TEST 23 — multiple ligands ---------------------------------------------------------


def test23(root: Path):
    pipe = Pipeline("Test23 Multiple Ligands")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("ligand", representation="ATP")
    pipe.configuration.add_record("ligand", representation="GTP")
    pipe.configuration.add_record("ligand", representation="MG")
    pipe.generate_base(root)
    return {}


# -- TEST 24 — single variant ------------------------------------------------------------


def test24(root: Path):
    pipe = Pipeline("Test24 Single Variant")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("dna", DNA_C)
    pipe.generate_base(root)
    assert pipe.variants.add_spec("sep3", "SEP at 3", ()).ok
    applied = pipe.variants.apply_variant_edit("sep3", "add_modification", ("SEP", 3), record_key="A")
    assert applied.ok, applied.message
    pipe.generate_variants(root)
    return {}


# -- TEST 25 — multiple independent variants ----------------------------------------------


def test25(root: Path):
    pipe = Pipeline("Test25 Independent Variants")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.configuration.add_record("dna", DNA_C)
    pipe.generate_base(root)
    # Three specs, each exactly ONE edit, all against the same base.
    assert pipe.variants.add_spec_from_factor("va_ptm", "job_name", "VA PTM", label="VA PTM").ok
    assert pipe.variants.apply_variant_edit("va_ptm", "add_modification", ("SEP", 3), record_key="A").ok
    assert pipe.variants.add_spec_from_factor("vb_seq", "sequence", PROTEIN_C, label="VB SEQ", record_key="A").ok
    assert pipe.variants.add_spec_from_factor("vc_seeds", "seeds", "9 9", label="VC SEEDS").ok
    pipe.generate_variants(root)
    return {}


# -- TEST 26 — batch variants from a sequence file ------------------------------------------


def test26(root: Path):
    pipe = Pipeline("Test26 Batch Variants")
    pipe.seeds([1, 2, 3])
    pipe.configuration.add_record("protein", PROTEIN_A)
    pipe.generate_base(root)
    sequence_file = root / "batch_sequences.txt"
    sequence_file.write_text(
        "%s\n%s\n%s\n" % ("MVTPEPTIDE", "MVSPEPTIDE", "MVYPEPTIDE"), encoding="utf-8"
    )
    outcome = pipe.variants.generate_from_file(str(sequence_file))
    assert outcome.ok, outcome.message
    pipe.generate_variants(root)
    return {"batch_sequences.txt"}


TESTS = [
    ("test01_protein_minimal", test01, "Smallest valid protein configuration"),
    ("test02_protein_msa", test02, "Protein with paired+unpaired MSA (both mode)"),
    ("test03_protein_template", test03, "Protein with an explicit structural template"),
    ("test04_protein_msa_template", test04, "Protein with MSA and template together"),
    ("test05_rna_minimal", test05, "Smallest valid RNA configuration"),
    ("test06_rna_msa", test06, "RNA with a provided (single) MSA"),
    ("test07_dna_duplex", test07, "One DNA input; pipeline builds the reverse-complement strand"),
    ("test08_protein_dna", test08, "Protein + DNA duplex complex"),
    ("test09_two_proteins", test09, "Two protein entities, unique deterministic IDs"),
    ("test10_protein_rna", test10, "Mixed protein/RNA configuration"),
    ("test11_protein_ccd_ligand", test11, "Ligand via CCD code (ATP)"),
    ("test12_protein_smiles_ligand", test12, "Ligand via SMILES notation (set_representation notation route)"),
    ("test13_protein_ion", test13, "Ion through the ligand representation (NA)"),
    ("test14_protein_water_ions", test14, "Water and ions (HOH NA CL as one multi-code ligand)"),
    ("test15_single_ptm", test15, "One modified residue (SEP at position 3)"),
    ("test16_multiple_ptms", test16, "Two independent modifications (SEP@3, TPO@7)"),
    ("test17_protein_dna_ptm", test17, "Protein + DNA + modification integration"),
    ("test18_protein_dna_ligand", test18, "Protein + DNA + ligand integration"),
    ("test19_protein_rna_ligand_ion", test19, "Multi-component mixed system"),
    ("test20_comprehensive", test20, "All supported features in one configuration"),
    ("test21_two_proteins_dna", test21, "Identity: two proteins + duplex, all IDs unique"),
    ("test22_custom_chemistry", test22, "Custom ligand chemistry via inline userCCD"),
    ("test23_multiple_ligands", test23, "Three ligand entities with unique IDs"),
    ("test24_single_variant", test24, "Base + one variant; base unchanged"),
    ("test25_independent_variants", test25, "Three independent one-edit variants from the same base"),
    ("test26_batch_variants", test26, "Batch variants from a sequence file (independent, deterministic)"),
]


def generate_all(out_root: Path = FIXTURE_ROOT):
    """Build every fixture; return {test_name: {relative_file: bytes}}."""
    results = {}
    for name, builder, _ in TESTS:
        target = out_root / name
        _run(builder, target)
        results[name] = {
            str(p.relative_to(out_root)).replace("\\", "/"): p.read_bytes()
            for p in sorted(target.rglob("*"))
            if p.is_file()
        }
    return results


def check(out_root: Path = FIXTURE_ROOT):
    """Determinism report: regenerate into a scratch root and compare bytes."""
    fresh_root = out_root.parent / "_af3_pipeline_regen"
    if fresh_root.exists():
        shutil.rmtree(fresh_root)
    try:
        fresh = generate_all(fresh_root)
        committed = {
            name: {
                rel: (out_root / rel).read_bytes()
                for rel in files
            }
            for name, files in generate_all.__wrapped__(out_root).items()
        } if False else None
        # compare directly against the committed tree
        differences = []
        for name, files in fresh.items():
            for rel, payload in sorted(files.items()):
                target = out_root / rel
                if not target.exists():
                    differences.append((rel, "missing from committed fixtures"))
                elif target.read_bytes() != payload:
                    differences.append((rel, "bytes differ"))
            for p in sorted((out_root / name).rglob("*")):
                if p.is_file() and str(p.relative_to(out_root)).replace("\\", "/") not in files:
                    differences.append((str(p.relative_to(out_root)).replace("\\", "/"), "extra committed file"))
        return differences
    finally:
        shutil.rmtree(fresh_root, ignore_errors=True)


def main(argv):
    if argv == ["--check"]:
        differences = check()
        if differences:
            for rel, why in differences:
                print("DIFF %s: %s" % (rel, why))
            return 1
        print("determinism check passed: all fixtures regenerate byte-identically")
        return 0
    results = generate_all()
    for name, files in results.items():
        for rel in sorted(files):
            print("wrote %s (%d bytes)" % (rel, len(files[rel])))
    write_readme(results)
    return 0


def write_readme(results):
    """Manifest: what each fixture tests and which files the pipeline wrote."""
    lines = [
        "# AF3 pipeline fixtures",
        "",
        "Every JSON file below was generated **through the application pipeline**",
        "(application services → canonical model → validation → variants → transform",
        "→ serializer → output). Nothing here is hand-written; `batch_sequences.txt`",
        "in test26 is pipeline *input*, marked INPUT.",
        "",
        "Regenerate with::",
        "",
        "    python fixtures/af3_pipeline/generate_fixtures.py",
        "",
        "Verify byte-determinism with::",
        "",
        "    python fixtures/af3_pipeline/generate_fixtures.py --check",
        "",
        "| Test | Purpose | Files written by the pipeline |",
        "| ---- | ------- | ----------------------------- |",
    ]
    for name, _, purpose in TESTS:
        files = sorted(results.get(name, {}))
        lines.append("| %s | %s | %s |" % (name, purpose, ", ".join("`%s`" % f for f in files) or "-"))
    lines.extend([
        "",
        "## Audit notes (implementation characteristics, documented not corrected)",
        "",
        "- TEST 12 (SMILES): the single-field ligand classifier",
        "  (`ConfigurationService._ligand_representation`) maps any space-free",
        "  token to `ccdCodes` first; `ComponentCode` is deliberately lenient",
        "  because codes are matched against the CCD at deployment time. The",
        "  SMILES representation therefore goes through the explicit typed",
        "  route `set_representation(key, notation=...)`, which emits `smiles`.",
        "- TEST 14 (water/ions): `HOH NA CL` is one ligand entity with a",
        "  multi-code `ccdCodes` list (the contract's multi-component ligand",
        "  representation), not three entities.",
        "- Templates (TEST 03/04/20): template content is carried inline in",
        "  the `mmcif` field with explicit `queryIndices`/`templateIndices`.",
        "- Variants (TEST 24-26): the committed `<base>.json` beside each run",
        "  is the base's own generation (expansion never mutates it); batch",
        "  names are `batch_NN` from input order; no sequence text enters a",
        "  file name.",
    ])
    lines.append("")
    (FIXTURE_ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
