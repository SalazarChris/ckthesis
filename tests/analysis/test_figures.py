"""Figures (SOP §5), with the declared robustness rule for network edges."""

from __future__ import annotations

import pytest

pytest.importorskip("numpy", reason="af3_analysis requires numpy")
pytest.importorskip("pandas", reason="af3_analysis requires pandas")
pytest.importorskip("matplotlib", reason="the figure tests need matplotlib")

import pandas as pd

from af3_analysis import figures
from af3_analysis.config import FigureSettings, load_config
from af3_analysis.layout import prepare
from tests.analysis import _af3_fixture as fixture

SEQUENCE = "MAGSTVKLDEQSAAGSTVKLDEQP"
REGIONS = [
    {"region_id": "DOMAIN_1", "start": 1, "end": 11, "role": "domain"},
    {"region_id": "PTM_LOCAL", "start": 7, "end": 17, "role": "ptm_local"},
]

ANALYSIS = """
analysis:
  hbond:
    donor_acceptor_cutoff_A: 3.5
    network_min_seed_fraction: %s
    network_max_edges: %s
"""


def _config(tmp_path, min_fraction=0.5, max_edges=20):
    conditions = [
        {"condition_id": "WT", "name": "wt", "output_dir": tmp_path / "wt",
         "reference_id": "REF", "variant_type": "WT", "dna_present": "false"},
        {"condition_id": "PTM_01", "name": "ptm", "output_dir": tmp_path / "ptm",
         "reference_id": "REF", "variant_type": "PTM", "ptm_state": "phosphoserine",
         "ptm_positions_reference": 12, "dna_present": "false"},
    ]
    path = fixture.write_config(
        tmp_path, conditions, REGIONS, SEQUENCE,
        analysis_yaml=ANALYSIS % (min_fraction, max_edges))
    return load_config(path)


def _edge(condition, seed, sample, donor_atom, acceptor_atom, distance):
    return {
        "condition_id": condition, "seed": seed, "sample": sample,
        "scope": "PTM:S12|protein",
        "chain_donor": "A", "donor_model_res_id": 1, "donor_reference_position": 1,
        "donor_residue": "MET1", "donor_atom": donor_atom,
        "chain_acceptor": "A", "acceptor_model_res_id": 12,
        "acceptor_reference_position": 12, "acceptor_residue": "SEP12",
        "acceptor_atom": acceptor_atom, "distance_A": distance, "angle_deg": "",
        "edge_type": "heavy_atom_candidate",
        "confidence_or_recurrence": "present_in_predicted_model",
        "criterion": "D-A distance", "notes": "candidate",
    }


def _frame(rows):
    return pd.DataFrame(rows)


def _layout(tmp_path):
    return prepare(tmp_path / "analysis")


def test_network_figure_draws_the_edges_that_recur_across_seeds(tmp_path):
    # edge N->O1P in both seeds of PTM_01 (100%), edge N->O2P in only one (50%)
    rows = []
    for sample in (0, 1):
        rows.append(_edge("PTM_01", 1, sample, "N", "O1P", 2.04 + 0.01 * sample))
        rows.append(_edge("PTM_01", 2, sample, "N", "O1P", 2.05 + 0.01 * sample))
    rows.append(_edge("PTM_01", 1, 0, "N", "O2P", 2.55))
    frame = _frame(rows)

    config = _config(tmp_path, min_fraction=0.5)
    layout = _layout(tmp_path)
    result = figures.hbond_network_figures(config, frame, layout,
                                           FigureSettings(formats=["png"]))
    assert len(result.paths) == 1
    assert result.paths[0].name == "hbond_edge_recurrence.png"
    assert result.paths[0].parent.name == "interface_comparisons"
    assert result.paths[0].stat().st_size > 0
    # both edges reach the declared 50% rule, and the note reports the count
    assert any("2 edge(s)" in note for note in result.notes)

    # raising the declared rule above one edge's recurrence drops that edge
    stricter = _config(tmp_path / "strict", min_fraction=0.75)
    strict_layout = prepare(tmp_path / "strict" / "analysis")
    strict = figures.hbond_network_figures(stricter, frame, strict_layout,
                                           FigureSettings(formats=["png"]))
    assert len(strict.paths) == 1
    assert any("1 edge(s)" in note for note in strict.notes)


def test_network_figure_reports_when_no_edge_is_robust(tmp_path):
    # one seed of three, and only one seed per condition: 33% < the 50% rule
    frame = _frame([
        _edge("PTM_01", 1, 0, "N", "O1P", 2.0),
        _edge("PTM_01", 2, 0, "N", "O2P", 2.1),
        _edge("PTM_01", 3, 0, "N", "O3P", 2.2),
    ])
    config = _config(tmp_path, min_fraction=0.5)
    result = figures.hbond_network_figures(config, frame, _layout(tmp_path),
                                           FigureSettings(formats=["png"]))
    assert result.paths == []
    assert any("no hydrogen-bond candidate edge recurs" in note for note in result.notes)


def test_network_figure_is_skipped_without_rows(tmp_path):
    config = _config(tmp_path)
    result = figures.hbond_network_figures(config, pd.DataFrame(), _layout(tmp_path),
                                           FigureSettings(formats=["png"]))
    assert result.paths == []
    assert any("no hydrogen-bond candidate rows" in note for note in result.notes)


def test_network_figure_respects_the_declared_edge_cap(tmp_path):
    rows = []
    for index, atom in enumerate(("O1P", "O2P", "O3P")):
        for seed in (1, 2):
            rows.append(_edge("PTM_01", seed, 0, "N", atom, 2.0 + index))
    config = _config(tmp_path, max_edges=2)
    result = figures.hbond_network_figures(config, _frame(rows), _layout(tmp_path),
                                           FigureSettings(formats=["png"]))
    assert len(result.paths) == 1
    assert any("2 edge(s)" in note for note in result.notes)
