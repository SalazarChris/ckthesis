"""Seed-level statistics and the SOP §4 tables."""

from __future__ import annotations

import pytest

# The analysis stack is an optional extra (see pyproject.toml), and numpy and
# pandas are its hard requirements.  The guard sits before every other import in
# this module on purpose: on an interpreter without them the honest result is
# "not tested here", not an ImportError in the middle of the suite (CI installs
# the builder's dev extra only).
pytest.importorskip("numpy", reason="af3_analysis requires numpy")
pytest.importorskip("pandas", reason="af3_analysis requires pandas")

import math

import numpy as np
import pandas as pd

from af3_analysis.config import StatisticsSettings
from af3_analysis.stats import (
    benjamini_hochberg,
    bootstrap_interval,
    condition_estimate,
    direction_consistency,
    matched_comparison,
    seed_aggregate,
    sign_flip_pvalue,
    spread,
    summarise,
)
from af3_analysis.tables import observation

SETTINGS = StatisticsSettings(bootstrap_resamples=500, random_seed=7)


def _frame(rows):
    return pd.DataFrame(rows)


def _seed_frame(condition, values_by_seed):
    return _frame([
        {"condition_id": condition, "metric": "plddt_region_mean", "scope": "DOMAIN_1",
         "seed": seed, "n_samples": 3, "seed_value": value}
        for seed, value in values_by_seed.items()
    ])


def test_summarise_and_spread_rules():
    values = [1.0, 2.0, 3.0, 4.0]
    assert summarise(values, "median") == 2.5
    assert summarise(values, "mean") == 2.5
    assert spread(values, "range") == 3.0
    assert spread(values, "stdev") == pytest.approx(np.std(values, ddof=1))
    assert spread(values, "iqr") == pytest.approx(1.5)
    assert summarise([], "median") != summarise([], "median")  # NaN


def test_seed_aggregate_collapses_samples_within_a_seed():
    samples = _frame([
        {"condition_id": "WT", "metric": "plddt_region_mean", "scope": "DOMAIN_1",
         "seed": 1, "sample": 0, "numeric_value": 80.0},
        {"condition_id": "WT", "metric": "plddt_region_mean", "scope": "DOMAIN_1",
         "seed": 1, "sample": 1, "numeric_value": 90.0},
        {"condition_id": "WT", "metric": "plddt_region_mean", "scope": "DOMAIN_1",
         "seed": 2, "sample": 0, "numeric_value": 70.0},
    ])
    aggregated = seed_aggregate(samples, ["condition_id", "metric", "scope"],
                                "numeric_value", SETTINGS)
    assert len(aggregated) == 2
    seed_one = aggregated[aggregated["seed"] == 1].iloc[0]
    assert seed_one["n_samples"] == 2
    assert seed_one["seed_value"] == 85.0
    assert seed_one["summary_rule"] == "median"
    assert aggregated[aggregated["seed"] == 2].iloc[0]["n_samples"] == 1


def test_bootstrap_interval_is_deterministic_and_brackets_the_mean():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    first = bootstrap_interval(values, SETTINGS)
    second = bootstrap_interval(values, SETTINGS)
    assert first == second
    assert first[0] <= np.mean(values) <= first[1]


def test_sign_flip_pvalue_is_small_for_a_consistent_shift():
    consistent = [1.0, 1.1, 0.9, 1.2, 1.0]
    noisy = [1.0, -1.2, 0.8, -0.9, 0.3]
    assert sign_flip_pvalue(consistent, SETTINGS) < sign_flip_pvalue(noisy, SETTINGS)
    assert 0.0 < sign_flip_pvalue(consistent, SETTINGS) <= 1.0


def test_direction_consistency_and_benjamini_hochberg():
    assert direction_consistency([1.0, 2.0, 3.0, -0.1]) == 0.75
    assert direction_consistency([]) != direction_consistency([])  # NaN
    qvalues = benjamini_hochberg([0.01, 0.04, 0.03, 0.5])
    assert all(0.0 <= value <= 1.0 for value in qvalues)
    # monotone in rank: the smallest p gets the smallest q
    assert qvalues[0] == min(qvalues)
    assert benjamini_hochberg([float("nan")])[0] != benjamini_hochberg([float("nan")])[0]


def test_paired_comparison_uses_per_seed_differences():
    variant = _seed_frame("PTM", {1: 80.0, 2: 82.0, 3: 84.0})
    reference = _seed_frame("WT", {1: 70.0, 2: 72.0, 3: 74.0})
    result = matched_comparison(variant, reference, "plddt_region_mean", "DOMAIN_1",
                                SETTINGS)
    assert result.paired is True
    assert result.n_seeds_paired == 3
    assert result.delta == pytest.approx(10.0)
    assert result.ci_low <= 10.0 <= result.ci_high
    assert result.consistency == 1.0
    assert "matched per-seed" in result.notes


def test_a_metric_the_reference_cannot_produce_is_labeled_not_zeroed():
    variant = _seed_frame("PTM", {1: 3.0, 2: 3.2})
    empty = pd.DataFrame()
    result = matched_comparison(variant, empty, "ptm_local_rmsd_ca", "PTM", SETTINGS)
    assert result.status == "not_applicable"
    assert math.isnan(result.delta)
    assert math.isnan(result.q_value)
    assert math.isnan(result.p_value)
    assert "no value" in result.notes


def test_unpaired_comparison_is_labeled_when_seeds_do_not_match():
    variant = _seed_frame("PTM", {5: 80.0, 6: 82.0})
    reference = _seed_frame("WT", {1: 70.0, 2: 72.0})
    result = matched_comparison(variant, reference, "plddt_region_mean", "DOMAIN_1",
                                SETTINGS)
    assert result.paired is False
    assert result.n_seeds_paired == 0
    assert "unpaired" in result.notes


def test_condition_estimate_reports_counts_and_interval():
    seeds = _seed_frame("WT", {seed: 70.0 + seed for seed in range(1, 7)})
    estimate = condition_estimate(seeds, ["condition_id", "metric", "scope"], SETTINGS)
    row = estimate.iloc[0]
    assert row["n_seeds"] == 6
    assert row["estimate"] == pytest.approx(73.5)
    assert row["ci_low"] <= row["estimate"] <= row["ci_high"]
    assert row["confidence_level"] == 0.95


# --------------------------------------------------------------------------
# Observations and the §4.1 wide table
# --------------------------------------------------------------------------


def test_observation_rows_carry_evidence_and_tier():
    row = observation("WT", 1, 0, "plddt_region_mean", 80.0, unit="pLDDT",
                      scope="DOMAIN_1", region_id="DOMAIN_1")
    assert row["evidence"] == "confidence"
    assert row["tier"] == "Confidence"
    assert row["status"] == "ok"
    geometric = observation("WT", 1, 0, "rmsd_local_ca", 1.5, unit="angstrom")
    assert geometric["evidence"] == "structure"
    assert geometric["tier"] == "Structure"
    interface = observation("WT", 1, 0, "interface_contacts_heavy", 12)
    assert interface["tier"] == "Interface geometry"


def test_unavailable_metrics_are_not_written_as_zero():
    row = observation("WT", 1, 0, "iptm", "", metric_status="not_applicable",
                      notes="single-chain model")
    assert row["value"] == ""
    assert row["status"] == "not_applicable"


# --------------------------------------------------------------------------
# §4.2 deltas and the scope of the multiple-testing correction
# --------------------------------------------------------------------------

COMPARISON_YAML = """
analysis:
  statistics:
    bootstrap_resamples: 500
    random_seed: 7
"""


def _delta_config(tmp_path, metrics):
    from af3_analysis.config import load_config
    from tests.analysis import _af3_fixture as fixture

    sequence = "MAGSTVKLDEQSAAGSTVKLDEQP"
    conditions = [
        {"condition_id": "WT", "name": "wt", "output_dir": tmp_path / "wt",
         "reference_id": "REF", "variant_type": "WT", "dna_present": "false"},
        {"condition_id": "PTM_01", "name": "ptm", "output_dir": tmp_path / "ptm",
         "reference_id": "REF", "variant_type": "PTM", "ptm_state": "phosphoserine",
         "ptm_positions_reference": 12, "dna_present": "false"},
    ]
    regions = [
        {"region_id": "DOMAIN_1", "start": 1, "end": 11, "role": "domain"},
        {"region_id": "PTM_LOCAL", "start": 7, "end": 17, "role": "ptm_local"},
    ]
    path = fixture.write_config(
        tmp_path, conditions, regions, sequence,
        comparisons=[{"comparison_id": "C01", "variant": "PTM_01", "reference": "WT",
                      "factor_changed": "PTM", "region": "PTM_LOCAL",
                      "metrics": metrics}],
        analysis_yaml=COMPARISON_YAML,
    )
    return load_config(path)


def _observations(rows):
    return pd.DataFrame([
        observation(condition, seed, 0, metric, value, unit="x", scope=scope,
                    metric_status=status)
        for condition, metric, scope, seed, value, status in rows
    ])


def test_fdr_is_corrected_within_a_metric_family_and_the_family_is_recorded(tmp_path):
    from af3_analysis.tables import build_matched_deltas

    metrics = ["plddt_region_mean", "pae_median", "ptm_local_rmsd_ca"]
    config = _delta_config(tmp_path, metrics)
    rows = []
    for seed in (1, 2, 3, 4, 5, 6, 7, 8):
        for scope in ("DOMAIN_1", "PTM_LOCAL"):
            rows.append(("WT", "plddt_region_mean", scope, seed, 88.0, "ok"))
            # a small, seed-consistent improvement in the variant
            rows.append(("PTM_01", "plddt_region_mean", scope, seed,
                         88.0 - 0.5 * seed, "ok"))
        rows.append(("WT", "pae_median", "region:DOMAIN_1", seed, 6.0, "ok"))
        rows.append(("PTM_01", "pae_median", "region:DOMAIN_1", seed, 6.5, "ok"))
        # the reference condition has no PTM site, so it cannot produce this one
        rows.append(("PTM_01", "ptm_local_rmsd_ca", "PTM", seed, 3.0, "ok"))
    deltas = build_matched_deltas(_observations(rows), config)

    plddt = deltas[deltas["metric"] == "plddt_region_mean"]
    assert set(plddt["fdr_family"]) == {"C01|plddt_region_mean"}
    assert set(plddt["fdr_family_size"]) == {2}      # the two region scopes
    assert (plddt["paired"] == True).all()            # noqa: E712
    # With 8 seeds a perfectly consistent shift is the strongest evidence the
    # sign-flip test can express: two of the 2**8 sign patterns (all +, all -).
    # (the CSV writer rounds floats to six decimals, so this is a written-value check)
    assert np.allclose(plddt["p_value"].to_numpy(dtype=float), 2.0 / 256.0,
                       rtol=0.0, atol=1e-6)
    assert set(plddt["significance"]) == {"signal_after_fdr"}

    pae = deltas[deltas["metric"] == "pae_median"].iloc[0]
    assert pae["fdr_family_size"] == 1
    assert pae["q_value_fdr"] == pytest.approx(pae["p_value"])

    ptm = deltas[deltas["metric"] == "ptm_local_rmsd_ca"].iloc[0]
    assert ptm["status"] == "not_applicable"
    assert math.isnan(ptm["delta"])
    assert ptm["fdr_family_size"] == 0               # nothing to correct
    # empty, not 0: the row is written with a blank q-value (SOP §9 closing note)
    assert pd.isna(pd.to_numeric(ptm["q_value_fdr"], errors="coerce"))
    assert "no value" in ptm["notes"]

    for _, row in deltas.iterrows():
        if not math.isnan(row["p_value"]) and not math.isnan(row["q_value_fdr"]):
            assert row["q_value_fdr"] >= row["p_value"] - 1e-9
