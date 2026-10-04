"""AF3 pipeline fixture suite tests (tests/fixtures/af3_pipeline).

Every fixture JSON is produced by the real application pipeline (services,
validation, variants, transform, serializer, output) via the generator in
``tests/fixtures/af3_pipeline/generate_fixtures.py``. These tests rebuild
the fixtures in temporary roots and verify the structural properties the
manual review depends on: required fields, forbidden fields, unique and
deterministic identifiers, the DNA duplex complement, variant isolation,
batch independence, and byte determinism across runs.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.fixtures.af3_pipeline.generate_fixtures import (  # noqa: E402
    TESTS,
    generate_all,
)

COMMITTED_ROOT = REPO_ROOT / "tests" / "fixtures" / "af3_pipeline"


def _docs(root: Path):
    out = {}
    for path in sorted(root.rglob("*.json")):
        out[str(path.relative_to(root)).replace("\\", "/")] = json.loads(
            path.read_text(encoding="utf-8")
        )
    return out


def _entities(doc):
    return [list(entry.values())[0] for entry in doc["sequences"]]


def _ids(doc):
    return [entity["id"] for entity in _entities(doc)]


def _base_doc(root: Path, name: str):
    """The run's base JSON: `<name>/<slug>/<slug>.json` (the slug comes
    from the project name, so it is found structurally — the file whose
    stem equals its parent directory and carries no variant suffix)."""
    for json_file in sorted((root / name).rglob("*.json")):
        parent = json_file.parent.name
        if json_file.stem == parent and "__" not in parent:
            return json.loads(json_file.read_text(encoding="utf-8"))
    raise AssertionError("no base json found for %s" % name)


def _reverse_complement(seq: str) -> str:
    table = str.maketrans("ACGT", "TGCA")
    return seq.translate(table)[::-1]


# -- suite shape ---------------------------------------------------------------


def test_generator_covers_all_26_tests():
    assert len(TESTS) == 26
    names = [name for name, _, _ in TESTS]
    assert names[0] == "test01_protein_minimal"
    assert names[-1] == "test26_batch_variants"


# -- base structure ------------------------------------------------------------


def test_base_fixtures_have_required_structure(tmp_path):
    generate_all(tmp_path / "run")
    for name in (
        "test01_protein_minimal",
        "test05_rna_minimal",
        "test07_dna_duplex",
        "test09_two_proteins",
        "test20_comprehensive",
    ):
        base = _base_doc(tmp_path / "run", name)
        assert base["dialect"] == "alphafold3", name
        assert base["version"] == 4, name
        assert base["modelSeeds"], name
        ids = _ids(base)
        assert len(ids) == len(set(ids)), "duplicate entity ids in %s" % name


def test_minimal_protein_omits_optional_fields(tmp_path):
    generate_all(tmp_path / "run")
    protein = _entities(_base_doc(tmp_path / "run", "test01_protein_minimal"))[0]
    assert protein["id"] == "A"
    assert protein["sequence"] == "ACDEFGHIKL"
    for forbidden in ("unpairedMsa", "pairedMsa", "templates", "modifications"):
        assert forbidden not in protein, forbidden


# -- MSA / templates ------------------------------------------------------------


def test_protein_msa_emits_both_fields(tmp_path):
    generate_all(tmp_path / "run")
    protein = _entities(_base_doc(tmp_path / "run", "test02_protein_msa"))[0]
    assert "unpairedMsa" in protein and "pairedMsa" in protein
    assert "templates" not in protein


def test_template_fixture_has_no_msa_fields(tmp_path):
    generate_all(tmp_path / "run")
    protein = _entities(_base_doc(tmp_path / "run", "test03_protein_template"))[0]
    template = protein["templates"][0]
    assert template["mmcif"].startswith(">template")
    assert template["queryIndices"] == [1, 2]
    assert template["templateIndices"] == [1, 2]
    for forbidden in ("unpairedMsa", "pairedMsa"):
        assert forbidden not in protein, forbidden


def test_msa_and_template_coexist(tmp_path):
    generate_all(tmp_path / "run")
    protein = _entities(_base_doc(tmp_path / "run", "test04_protein_msa_template"))[0]
    assert "unpairedMsa" in protein and "pairedMsa" in protein
    assert protein["templates"]


def test_rna_msa_uses_single_provided_field(tmp_path):
    generate_all(tmp_path / "run")
    rna_min = _entities(_base_doc(tmp_path / "run", "test05_rna_minimal"))[0]
    assert set(rna_min) == {"id", "sequence"}
    rna_msa = _entities(_base_doc(tmp_path / "run", "test06_rna_msa"))[0]
    assert "unpairedMsa" in rna_msa
    assert "pairedMsa" not in rna_msa, "RNA has no paired MSA in this contract"


# -- identity / DNA duplex --------------------------------------------------------


def test_dna_duplex_builds_reverse_complement(tmp_path):
    generate_all(tmp_path / "run")
    entities = _entities(_base_doc(tmp_path / "run", "test07_dna_duplex"))
    given, partner = entities[0], entities[1]
    assert partner["sequence"] == _reverse_complement(given["sequence"])
    assert given["id"] != partner["id"]


def test_dna_combined_with_protein_keeps_ids_distinct(tmp_path):
    generate_all(tmp_path / "run")
    base = _base_doc(tmp_path / "run", "test08_protein_dna")
    assert _ids(base) == ["A", "B", "C"]
    sequences = [e["sequence"] for e in _entities(base)]
    assert sequences[1] == "ATGCCGA"
    assert sequences[2] == _reverse_complement("ATGCCGA")


def test_identity_tests_have_unique_ordered_ids(tmp_path):
    generate_all(tmp_path / "run")
    assert _ids(_base_doc(tmp_path / "run", "test09_two_proteins")) == ["A", "B"]
    # two proteins + both duplex strands: four distinct registry-allocated ids
    assert _ids(_base_doc(tmp_path / "run", "test21_two_proteins_dna")) == ["A", "B", "C", "D"]


# -- chemistry ---------------------------------------------------------------------


def test_ccd_ligand_has_no_smiles(tmp_path):
    generate_all(tmp_path / "run")
    ligand = _entities(_base_doc(tmp_path / "run", "test11_protein_ccd_ligand"))[1]
    assert ligand["ccdCodes"] == ["ATP"]
    assert "smiles" not in ligand


def test_smiles_ligand_has_no_ccd_codes(tmp_path):
    generate_all(tmp_path / "run")
    ligand = _entities(_base_doc(tmp_path / "run", "test12_protein_smiles_ligand"))[1]
    assert ligand["smiles"] == "C(C)O"
    assert "ccdCodes" not in ligand


def test_water_and_ions_are_one_multicode_ligand(tmp_path):
    generate_all(tmp_path / "run")
    ligand = _entities(_base_doc(tmp_path / "run", "test14_protein_water_ions"))[1]
    assert ligand["ccdCodes"] == ["HOH", "NA", "CL"]


def test_custom_chemistry_emits_user_ccd(tmp_path):
    generate_all(tmp_path / "run")
    base = _base_doc(tmp_path / "run", "test22_custom_chemistry")
    assert base["userCCD"].startswith("data_LIG")


# -- PTMs ----------------------------------------------------------------------------


def test_ptm_representation_and_ordering(tmp_path):
    generate_all(tmp_path / "run")
    single = _entities(_base_doc(tmp_path / "run", "test15_single_ptm"))[0]
    assert single["modifications"] == [{"ptmType": "SEP", "ptmPosition": 3}]
    multi = _entities(_base_doc(tmp_path / "run", "test16_multiple_ptms"))[0]
    assert multi["modifications"] == [
        {"ptmType": "SEP", "ptmPosition": 3},
        {"ptmType": "TPO", "ptmPosition": 7},
    ]


def test_comprehensive_case_covers_every_feature(tmp_path):
    generate_all(tmp_path / "run")
    base = _base_doc(tmp_path / "run", "test20_comprehensive")
    protein = _entities(base)[0]
    assert protein["modifications"] and protein["templates"]
    assert "unpairedMsa" in protein and "pairedMsa" in protein
    assert _ids(base) == ["A", "B", "C", "D", "E"]
    dna_entities = [e for e in _entities(base) if e["id"] in ("B", "C")]
    assert dna_entities[1]["sequence"] == _reverse_complement(dna_entities[0]["sequence"])


# -- variants ---------------------------------------------------------------------------


def test_single_variant_does_not_mutate_the_base(tmp_path):
    root = tmp_path / "run"
    generate_all(root)
    run_dir = root / "test24_single_variant" / "test24-single-variant"
    base = json.loads((run_dir / "test24-single-variant.json").read_text(encoding="utf-8"))
    variant = json.loads(
        (run_dir / "test24-single-variant__sep3" / "test24-single-variant__sep3.json")
        .read_text(encoding="utf-8")
    )
    assert "modifications" not in _entities(base)[0]
    assert _entities(variant)[0]["modifications"] == [{"ptmType": "SEP", "ptmPosition": 3}]
    assert _ids(variant) == _ids(base)
    assert variant["modelSeeds"] == base["modelSeeds"]


def test_multiple_variants_are_independent(tmp_path):
    root = tmp_path / "run"
    generate_all(root)
    run_dir = root / "test25_independent_variants" / "test25-independent-variants"
    base = json.loads((run_dir / "test25-independent-variants.json").read_text(encoding="utf-8"))
    base_entities = _entities(base)

    def variant_doc(key):
        return json.loads(
            (run_dir / ("test25-independent-variants__%s" % key) / ("test25-independent-variants__%s.json" % key))
            .read_text(encoding="utf-8")
        )

    va, vb, vc = variant_doc("va-ptm"), variant_doc("vb-seq"), variant_doc("vc-seeds")
    # va: exactly the modification differs
    assert _entities(va)[0]["modifications"] == [{"ptmType": "SEP", "ptmPosition": 3}]
    assert "modifications" not in base_entities[0]
    assert [_entities(va)[i].get("sequence") for i in range(3)] == [
        e.get("sequence") for e in base_entities
    ]
    # vb: exactly the protein sequence differs
    assert _entities(vb)[0]["sequence"] == "GKKIGYS"
    assert base_entities[0]["sequence"] == "ACDEFGHIKL"
    # vc: exactly the seeds differ
    assert vc["modelSeeds"] == [9, 9]
    assert base["modelSeeds"] == [1, 2, 3]
    # every variant keeps the base's entity identity set
    for doc in (va, vb, vc):
        assert _ids(doc) == _ids(base)


def test_batch_variants_are_independent_and_deterministic(tmp_path):
    root = tmp_path / "run"
    generate_all(root)
    run_dir = root / "test26_batch_variants" / "test26-batch-variants"
    base = json.loads((run_dir / "test26-batch-variants.json").read_text(encoding="utf-8"))
    inputs = [
        line
        for line in (root / "test26_batch_variants" / "batch_sequences.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert inputs == ["MVTPEPTIDE", "MVSPEPTIDE", "MVYPEPTIDE"]
    for index, expected in enumerate(inputs, start=1):
        key = "batch-%02d" % index
        doc = json.loads(
            (run_dir / ("test26-batch-variants__%s" % key) / ("test26-batch-variants__%s.json" % key))
            .read_text(encoding="utf-8")
        )
        # the batch allocates ids sequentially from one registry clone:
        # batch-01 -> B, batch-02 -> C, batch-03 -> D (deterministic)
        assert _ids(doc) == ["A", chr(65 + index)], (key, _ids(doc))
        assert _entities(doc)[1]["sequence"] == expected
        assert _entities(doc)[0]["sequence"] == _entities(base)[0]["sequence"]


# -- determinism ----------------------------------------------------------------------------


def test_generation_is_byte_deterministic(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    generate_all(first)
    generate_all(second)
    assert set(_docs(first)) == set(_docs(second))
    for rel in _docs(first):
        assert (first / rel).read_bytes() == (second / rel).read_bytes(), rel


def test_committed_fixtures_match_a_fresh_run():
    if not (COMMITTED_ROOT / "README.md").exists():
        pytest.skip("committed fixture tree not present; run generate_fixtures.py first")
    fresh_root = COMMITTED_ROOT.parent / "_af3_pipeline_fresh"
    if fresh_root.exists():
        shutil.rmtree(fresh_root)
    try:
        generate_all(fresh_root)
        fresh = _docs(fresh_root)
        assert fresh, "generator produced nothing"
        for rel in fresh:
            committed = COMMITTED_ROOT / rel
            assert committed.exists(), "committed tree missing %s" % rel
            assert committed.read_bytes() == (fresh_root / rel).read_bytes(), rel
    finally:
        shutil.rmtree(fresh_root, ignore_errors=True)
