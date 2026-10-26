"""pLDDT, PAE, contacts and summary metrics (SOP §2)."""

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

from af3_analysis import confidence
from af3_analysis.config import load_config
from af3_analysis.inventory import discover_condition
from af3_analysis.io import read_confidence, read_structure, read_summary
from af3_analysis.mapping import build_condition_mapping
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
"""


def _load(tmp_path, name="ptm", ptm=True, dna=()):
    geometry = fixture.ConditionGeometry(
        SEQUENCE, ptm_positions=(12,) if ptm else (), seed=5)
    root = fixture.write_condition(tmp_path / name, name, geometry, seeds=(1,),
                                   samples=1, dna_strands=dna,
                                   dna_chain_ids=("B", "C"))
    conditions = [{
        "condition_id": "PTM" if ptm else "WT", "name": name, "output_dir": root,
        "reference_id": "REF", "variant_type": "PTM" if ptm else "WT",
        "ptm_state": "phosphoserine" if ptm else "none",
        "ptm_positions_reference": 12 if ptm else "", "dna_present": "true" if dna else "false",
        "construct_start": 1, "construct_end": len(SEQUENCE), "seeds": 1,
        "samples_per_seed": 1,
    }]
    config = load_config(fixture.write_config(tmp_path, conditions, REGIONS, SEQUENCE,
                                              analysis_yaml=ANALYSIS))
    condition = config.conditions[0]
    inventory = discover_condition(condition)
    files = inventory.samples[0]
    structure = read_structure(files.model_cif)
    mappings = build_condition_mapping(condition, structure, config.reference("REF"))
    return (config, condition, files, structure, mappings,
            read_confidence(files.confidences_json), read_summary(files.summary_json))


def test_plddt_is_read_per_atom_and_summarised_per_residue(tmp_path):
    config, condition, files, structure, mappings, conf_data, summary = _load(tmp_path)
    result = confidence.analyse_confidence(condition, 1, 0, structure, conf_data,
                                           summary, mappings, config)
    assert result.atom_rows
    assert len(result.atom_rows) == structure.atom_count()
    # the CIF B-factor is the reported source; the JSON vector is cross-checked
    assert {row["plddt_source"] for row in result.atom_rows} == {"cif_bfactor"}
    assert all(row["plddt_json"] != "" for row in result.atom_rows)

    residue_rows = {row["model_res_id"]: row for row in result.residue_rows}
    assert residue_rows[1]["plddt_ca"] == pytest.approx(
        structure.residue("A", 1).atom("CA").bfactor)
    assert residue_rows[1]["plddt_backbone_median"] != ""
    assert residue_rows[1]["plddt_bin"] in ("very_high", "confident", "low", "very_low")
    # the modified residue is flagged and keeps its component
    assert residue_rows[12]["is_modified"] is True
    assert residue_rows[12]["modification_component"] == "SEP"
    # a residue no region covers reports no region membership
    assert residue_rows[1]["regions"] == "DOMAIN_1"


def test_region_summaries_use_ca_plddt_for_protein(tmp_path):
    config, condition, files, structure, mappings, conf_data, summary = _load(tmp_path)
    result = confidence.analyse_confidence(condition, 1, 0, structure, conf_data,
                                           summary, mappings, config)
    by_region = {row["region_id"]: row for row in result.region_rows}
    for region_id in ("DOMAIN_1", "LINKER", "DOMAIN_2", "PTM_LOCAL"):
        assert region_id in by_region
    assert by_region["DOMAIN_1"]["n_residues"] == 11
    assert by_region["DOMAIN_1"]["aggregation"] == "ca_plddt"
    assert by_region["DOMAIN_1"]["status"] == "ok"
    assert by_region["LINKER"]["reference_id"] == "REF"


def test_region_with_no_mapped_residue_is_failed_validation_not_zero(tmp_path):
    config, condition, files, structure, mappings, conf_data, summary = _load(tmp_path)
    config = _with_extra_region(config, "OUTSIDE", start=90, end=95)
    result = confidence.analyse_confidence(condition, 1, 0, structure, conf_data,
                                           summary, mappings, config)
    empty = [row for row in result.region_rows if row["region_id"] == "OUTSIDE"]
    assert empty and empty[0]["status"] == "failed_validation"
    assert empty[0]["plddt_ca_mean"] == ""
    assert "no modelled residue" in empty[0]["notes"]


def _with_extra_region(config, region_id, start, end):
    from dataclasses import replace

    from af3_analysis.config import Region

    extra = Region(region_id=region_id, reference_id="REF", start=start, end=end)
    return replace(config, regions=tuple(config.regions) + (extra,))


def test_pae_blocks_report_both_directions(tmp_path):
    config, condition, files, structure, mappings, conf_data, summary = _load(tmp_path)
    result = confidence.analyse_confidence(condition, 1, 0, structure, conf_data,
                                           summary, mappings, config)
    blocks = {row["block_id"]: row for row in result.pae_rows}
    assert "region:DOMAIN_1|DOMAIN_2" in blocks
    block = blocks["region:DOMAIN_1|DOMAIN_2"]
    assert block["status"] == "ok"
    assert block["n_tokens_i"] == 11
    assert block["n_tokens_j"] == 10
    assert block["symmetrised"] is False
    assert block["median_i_to_j"] != "" and block["median_j_to_i"] != ""
    # the directional medians differ because the matrix is not symmetric
    assert block["median_i_to_j"] != block["median_j_to_i"]
    assert "chain:A|A" in blocks


def test_within_region_pair_values_match_the_matrix(tmp_path):
    config, condition, files, structure, mappings, conf_data, summary = _load(tmp_path)
    result = confidence.analyse_confidence(condition, 1, 0, structure, conf_data,
                                           summary, mappings, config)
    block = next(row for row in result.pae_rows
                 if row["block_id"] == "region:DOMAIN_1|DOMAIN_2")
    tokens_i = confidence.region_tokens(conf_data, mappings["A"], config.region("DOMAIN_1"))
    tokens_j = confidence.region_tokens(conf_data, mappings["A"], config.region("DOMAIN_2"))
    expected = np.median(conf_data.pae[np.ix_(tokens_i, tokens_j)])
    assert block["pae_median"] == pytest.approx(expected)


def test_single_chain_iptm_is_not_applicable(tmp_path):
    config, condition, files, structure, mappings, conf_data, summary = _load(tmp_path)
    result = confidence.analyse_confidence(condition, 1, 0, structure, conf_data,
                                           summary, mappings, config)
    iptm = next(row for row in result.metric_rows if row["metric"] == "iptm")
    assert iptm["status"] == "not_applicable"
    assert iptm["value"] == ""
    rank = next(row for row in result.metric_rows if row["metric"] == "ranking_score")
    assert rank["status"] == "ok"
    # the ranking composite is annotated as a ranking score, not an effect size
    assert "not a biological-effect score" in rank["notes"]


def test_dna_condition_reports_chain_pair_metrics(tmp_path):
    config, condition, files, structure, mappings, conf_data, summary = _load(
        tmp_path, name="ptm_dna", dna=("ATGC", "GCAT"))
    assert set(mappings) == {"A", "B", "C"}
    result = confidence.analyse_confidence(condition, 1, 0, structure, conf_data,
                                           summary, mappings, config)
    pairs = {(row["metric"], row["scope"]) for row in result.metric_rows}
    assert ("chain_pair_iptm", "A|B") in pairs
    assert ("chain_pair_iptm", "A|C") in pairs
    assert ("chain_pair_pae_min", "A|B") in pairs
    # the diagonal duplicates chain_ptm and is therefore not repeated
    assert ("chain_pair_iptm", "A|A") not in pairs
    iptm = next(row for row in result.metric_rows if row["metric"] == "iptm")
    assert iptm["status"] == "ok"
    contacts = {(row["metric"], row["scope"]) for row in result.interface_rows}
    assert ("contact_prob_mean", "chain:A|B") in contacts
    assert ("contact_prob_mean", "chain:B|C") in contacts


def test_contact_probability_notes_the_af3_criterion(tmp_path):
    config, condition, files, structure, mappings, conf_data, summary = _load(tmp_path)
    result = confidence.analyse_confidence(condition, 1, 0, structure, conf_data,
                                           summary, mappings, config)
    row = next(r for r in result.interface_rows if r["metric"] == "contact_prob_mean")
    assert "8 A" in row["notes"]


def test_missing_contact_probs_is_not_applicable():
    class FakeConfidence:
        pae = np.zeros((2, 2))
        contact_probs = None
        atom_plddts = np.zeros(0)
        token_chain_ids = ("A", "A")
        token_res_ids = (1, 2)
        atom_chain_ids = ()
        keys = ()

        @property
        def n_tokens(self):
            return 2

    rows = confidence._contact_rows(
        _condition(), 1, 0, FakeConfidence(), {}, (), ("A",),
    )
    assert rows[0]["status"] == "not_applicable"
    assert rows[0]["value"] == ""


def _condition():
    from af3_analysis.config import Condition

    return Condition(condition_id="X", name="x", output_dir=Path("."),
                     reference_id="REF")


def test_plddt_bins_are_heuristic_labels():
    assert confidence.plddt_bin(95) == "very_high"
    assert confidence.plddt_bin(75) == "confident"
    assert confidence.plddt_bin(55) == "low"
    assert confidence.plddt_bin(10) == "very_low"
    assert confidence.plddt_bin(None) == ""
