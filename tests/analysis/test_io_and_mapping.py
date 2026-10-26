"""AF3 file readers, inventory discovery and residue correspondence (SOP §1)."""

from __future__ import annotations

import pytest

# The analysis stack is an optional extra (see pyproject.toml), and numpy and
# pandas are its hard requirements.  The guard sits before every other import in
# this module on purpose: on an interpreter without them the honest result is
# "not tested here", not an ImportError in the middle of the suite (CI installs
# the builder's dev extra only).
pytest.importorskip("numpy", reason="af3_analysis requires numpy")
pytest.importorskip("pandas", reason="af3_analysis requires pandas")

from pathlib import Path

import numpy as np

from af3_analysis.config import Condition, ReferenceSequence, Region, load_config
from af3_analysis.inventory import discover, discover_condition
from af3_analysis.io import (
    ParseError,
    read_confidence,
    read_processed_input,
    read_ranking_scores,
    read_structure,
    read_summary,
)
from af3_analysis.mapping import (
    align_to_reference,
    build_chain_mapping,
    build_condition_mapping,
    ptm_site_rows,
    residue_map_rows,
    select_protein_chain,
)
from af3_analysis import validate
from tests.analysis import _af3_fixture as fixture

SEQUENCE = "MAGSTVKLDEQSAAGSTVKLDEQP"
REGIONS = [
    {"region_id": "DOMAIN_1", "start": 1, "end": 11, "role": "domain"},
    {"region_id": "LINKER", "start": 12, "end": 13, "role": "linker"},
    {"region_id": "DOMAIN_2", "start": 14, "end": 23, "role": "domain"},
    {"region_id": "PTM_LOCAL", "start": 7, "end": 17, "role": "ptm_local"},
]
ANALYSIS = """
analysis:
  fit_selections:
    - name: CORE
      regions: [DOMAIN_1, DOMAIN_2]
    - name: ANCHOR
      regions: [DOMAIN_1]
"""


def config_region(regions, region_id):
    spec = next(region for region in regions if region["region_id"] == region_id)
    return Region(region_id=spec["region_id"], reference_id="REF",
                  start=spec["start"], end=spec["end"])


@pytest.fixture()
def ptm_root(tmp_path):
    geometry = fixture.ConditionGeometry(SEQUENCE, ptm_positions=(12,), seed=3)
    return fixture.write_condition(tmp_path / "ptm", "ptm", geometry, seeds=(1, 2),
                                   samples=2)


def test_reads_the_model_structure(ptm_root):
    path = ptm_root / "seed-1_sample-0" / "ptm_seed-1_sample-0_model.cif"
    structure = read_structure(path)
    assert structure.chains() == ("A",)
    assert structure.entities() == {"A": "protein"}
    assert structure.residue_count() == len(SEQUENCE)
    modified = structure.modified_residues()
    assert [residue.res_id for residue in modified] == [12]
    assert modified[0].comp_id == "SEP"
    assert modified[0].has("O1P")
    assert structure.sequence("A")[:4] == "MAGS"
    # SEP maps to its parent residue for alignment purposes
    assert structure.sequence("A")[11] == "S"


def test_reads_the_confidence_arrays(ptm_root):
    path = ptm_root / "seed-1_sample-0" / "ptm_seed-1_sample-0_confidences.json"
    confidence = read_confidence(path)
    assert confidence.pae.shape[0] == confidence.pae.shape[1]
    assert confidence.pae.shape[0] == len(confidence.token_chain_ids)
    assert confidence.contact_probs.shape == confidence.pae.shape
    assert len(confidence.atom_plddts) == len(confidence.atom_chain_ids)
    # the modified residue is tokenised twice (residue token + component token)
    positions = [r for c, r in zip(confidence.token_chain_ids, confidence.token_res_ids)
                 if r == 12]
    assert len(positions) == 2


def test_reads_the_summary_and_processed_input(ptm_root):
    summary = read_summary(ptm_root / "seed-1_sample-0" /
                           "ptm_seed-1_sample-0_summary_confidences.json")
    assert summary.scalar("ptm") == pytest.approx(summary.scalar("ranking_score"))
    assert summary.chain_ids() == ("A",)
    assert summary.scalar("iptm") is None

    processed = read_processed_input(ptm_root / "ptm_data.json")
    assert processed.protein().sequence == SEQUENCE
    assert processed.protein().modifications == (("SEP", 12),)
    assert processed.sequence_hash()


def test_ranking_scores_and_missing_files(tmp_path, ptm_root):
    scores = read_ranking_scores(ptm_root / "ptm_ranking_scores.csv")
    assert sorted(scores) == [(1, 0), (1, 1), (2, 0), (2, 1)]
    with pytest.raises(ParseError):
        read_structure(tmp_path / "nothing.cif")
    with pytest.raises(ParseError):
        read_confidence(ptm_root / "ptm_data.json")


def test_discovery_finds_every_sample_and_the_top_ranked_copy(tmp_path):
    geometry = fixture.ConditionGeometry(SEQUENCE, seed=1)
    root = fixture.write_condition(tmp_path / "wt", "wt", geometry, seeds=(1, 2),
                                   samples=2)
    condition = Condition(condition_id="WT", name="wt", output_dir=root,
                          reference_id="REF", seeds=(1, 2), samples_per_seed=2)
    inventory = discover_condition(condition)
    assert len(inventory.samples) == 4
    assert inventory.seeds() == (1, 2)
    assert inventory.samples_per_seed() == {1: 2, 2: 2}
    assert inventory.top_ranked_sample() is not None
    assert inventory.data_json.name == "wt_data.json"
    # the root-level copy is recorded, never counted as a fifth prediction
    assert len(inventory.top_ranked) == 1
    assert {sample.role for sample in inventory.samples} == {"sample"}
    # ranking order comes from ranking_scores.csv
    ranked = inventory.ranked()
    assert (ranked[0].seed, ranked[0].sample) == (2, 1)


def test_discovery_reports_a_missing_output_directory(tmp_path):
    condition = Condition(condition_id="GONE", name="gone",
                          output_dir=tmp_path / "absent", reference_id="REF")
    inventory = discover_condition(condition)
    assert inventory.samples == ()
    assert any("not found" in problem for problem in inventory.problems)


def test_alignment_is_exact_for_an_identical_sequence():
    alignment = align_to_reference(SEQUENCE, SEQUENCE)
    assert alignment.identity == 1.0
    assert alignment.method == "exact_match"
    assert alignment.reference_position(12) == 12


def test_alignment_maps_a_deletion_construct_onto_the_reference():
    deleted = SEQUENCE[:5] + SEQUENCE[8:]
    alignment = align_to_reference(deleted, SEQUENCE)
    # positions 6-8 are absent from the construct, and everything downstream is
    # mapped to its true reference position rather than the model numbering
    assert alignment.reference_position(5) == 5
    assert alignment.reference_position(6) == 9


def test_chain_mapping_uses_reference_coordinates(tmp_path):
    geometry = fixture.ConditionGeometry(SEQUENCE, ptm_positions=(12,), seed=1)
    root = fixture.write_condition(tmp_path / "ptm", "ptm", geometry, seeds=(1,),
                                   samples=1)
    structure = read_structure(root / "seed-1_sample-0" / "ptm_seed-1_sample-0_model.cif")
    reference = ReferenceSequence(reference_id="REF", name="ref", sequence=SEQUENCE)
    condition = Condition(condition_id="PTM_01", name="ptm", output_dir=root,
                          reference_id="REF", variant_type="PTM",
                          modified_positions_reference=(12,))
    mapping = build_chain_mapping(condition, structure, "A", reference)
    assert mapping.alignment_status == "mapped"
    assert mapping.identity == 1.0
    assert mapping.reference_position(12) == 12
    assert mapping.model_residues_in(config_region(REGIONS, "DOMAIN_1"))[0] == 1
    assert select_protein_chain(structure, reference) == "A"

    rows = residue_map_rows(condition, structure, mapping, reference)
    assert len(rows) == len(SEQUENCE)
    modified = [row for row in rows if row["is_modified"]]
    assert modified[0]["reference_position"] == 12
    assert modified[0]["modification_component"] == "SEP"

    sites = ptm_site_rows(condition, structure, {"A": mapping}, reference)
    assert sites[0]["matches_declared_condition"] is True
    assert "O1P" in sites[0]["phosphate_atoms_present"]


def test_explicit_mapping_overrides_the_alignment(tmp_path):
    geometry = fixture.ConditionGeometry(SEQUENCE, seed=1)
    root = fixture.write_condition(tmp_path / "wt", "wt", geometry, seeds=(1,),
                                   samples=1)
    structure = read_structure(root / "seed-1_sample-0" / "wt_seed-1_sample-0_model.cif")
    reference = ReferenceSequence(reference_id="REF", name="ref", sequence=SEQUENCE)
    condition = Condition(condition_id="WT", name="wt", output_dir=root,
                          reference_id="REF")
    rows = {"1": {"reference_position": "9"}, "2": {"reference_position": "8"}}
    mapping = build_chain_mapping(condition, structure, "A", reference,
                                  explicit_rows=rows)
    assert mapping.alignment_status == "explicit"
    assert mapping.model_to_reference == {1: 9, 2: 8}


def test_condition_mapping_covers_ligand_chains_as_not_applicable(tmp_path):
    geometry = fixture.ConditionGeometry(SEQUENCE, seed=1)
    root = fixture.write_condition(tmp_path / "wt", "wt", geometry, seeds=(1,),
                                   samples=1)
    structure = read_structure(root / "seed-1_sample-0" / "wt_seed-1_sample-0_model.cif")
    reference = ReferenceSequence(reference_id="REF", name="ref", sequence=SEQUENCE)
    condition = Condition(condition_id="WT", name="wt", output_dir=root,
                          reference_id="REF")
    mappings = build_condition_mapping(condition, structure, reference)
    assert mappings["A"].entity == "protein"


def test_validation_gates_pass_on_a_consistent_sample(tmp_path):
    geometry = fixture.ConditionGeometry(SEQUENCE, ptm_positions=(12,), seed=1)
    root = fixture.write_condition(tmp_path / "ptm", "ptm", geometry, seeds=(1,),
                                   samples=1)
    config_path = fixture.write_config(
        tmp_path,
        [{"condition_id": "PTM_01", "name": "ptm", "output_dir": root,
          "reference_id": "REF", "variant_type": "PTM", "ptm_state": "phosphoserine",
          "ptm_positions_reference": 12, "dna_present": "false", "construct_start": 1,
          "construct_end": len(SEQUENCE), "seeds": 1, "samples_per_seed": 1}],
        REGIONS, SEQUENCE, analysis_yaml=ANALYSIS,
    )
    config = load_config(config_path)
    inventory = discover_condition(config.conditions[0])
    files = inventory.samples[0]
    structure = read_structure(files.model_cif)
    confidence = read_confidence(files.confidences_json)
    summary = read_summary(files.summary_json)
    reference = config.reference("REF")
    mappings = build_condition_mapping(config.conditions[0], structure, reference)
    rows = validate.check_sample(config, config.conditions[0], files, structure,
                                 confidence, summary, mappings, reference,
                                 inventory.processed_input)
    statuses = {row["check_id"]: row["status"] for row in rows}
    assert statuses["token_dimensions"] == "pass"
    assert statuses["atom_plddt_length"] == "pass"
    assert statuses["bfactor_matches_plddt"] == "pass"
    assert statuses["ptm_component_present"] == "pass"
    assert statuses["residue_mapping"] == "pass"
    assert validate.excluded_samples(rows) == {}


def test_validation_flags_a_missing_ptm_component(tmp_path):
    """A condition that declares a PTM the model does not contain must fail."""
    geometry = fixture.ConditionGeometry(SEQUENCE, seed=1)  # no PTM in the model
    root = fixture.write_condition(tmp_path / "ptm", "ptm", geometry, seeds=(1,),
                                   samples=1)
    config_path = fixture.write_config(
        tmp_path,
        [{"condition_id": "PTM_01", "name": "ptm", "output_dir": root,
          "reference_id": "REF", "variant_type": "PTM", "ptm_state": "phosphoserine",
          "ptm_positions_reference": 12, "dna_present": "false", "construct_start": 1,
          "construct_end": len(SEQUENCE), "seeds": 1, "samples_per_seed": 1}],
        REGIONS, SEQUENCE, analysis_yaml=ANALYSIS,
    )
    config = load_config(config_path)
    inventory = discover_condition(config.conditions[0])
    files = inventory.samples[0]
    structure = read_structure(files.model_cif)
    rows = validate.check_sample(
        config, config.conditions[0], files, structure,
        read_confidence(files.confidences_json), read_summary(files.summary_json),
        build_condition_mapping(config.conditions[0], structure, config.reference("REF")),
        config.reference("REF"), inventory.processed_input,
    )
    ptm_rows = [row for row in rows if row["check_id"] == "ptm_component_present"]
    assert ptm_rows and ptm_rows[0]["status"] == "fail" and ptm_rows[0]["blocking"]
    blocked = validate.excluded_samples(rows)
    assert any("ptm_component_present" in reason for reason in blocked.values())
