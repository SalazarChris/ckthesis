"""End-to-end pipeline behaviour (SOP §1-§9)."""

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

import pandas as pd

from af3_analysis.config import load_config
from af3_analysis.pipeline import Pipeline, RunOptions
from tests.analysis import _af3_fixture as fixture

SEQUENCE = "MAGSTVKLDEQSAAGSTVKLDEQP"
PTM_POSITION = 12
DNA_STRANDS = ("ATGCAT", "ATGCAT")

REGIONS = [
    {"region_id": "DOMAIN_1", "start": 1, "end": 11, "role": "domain"},
    {"region_id": "LINKER", "start": 12, "end": 13, "role": "linker"},
    {"region_id": "DOMAIN_2", "start": 14, "end": 23, "role": "domain"},
    {"region_id": "PTM_LOCAL", "start": 7, "end": 17, "role": "ptm_local"},
]

ANALYSIS = """
analysis:
  structural_reference:
    condition: ""
  fit_selections:
    - name: CORE
      regions: [DOMAIN_1, DOMAIN_2]
    - name: ANCHOR
      regions: [DOMAIN_1]
  contact_cutoff_A: 4.5
  ptm_neighborhood:
    sequence_window: 5
    spatial_radius_A: 8.0
  statistics:
    bootstrap_resamples: 200
  figures:
    enabled: true
    formats: [png]
"""


def _build(tmp_path: Path, corrupt_sample: bool = False) -> Path:
    wt = fixture.ConditionGeometry(SEQUENCE, seed=1, plddt_base=88.0)
    ptm = fixture.ConditionGeometry(SEQUENCE, ptm_positions=(PTM_POSITION,), seed=2,
                                    plddt_base=88.0, plddt_ptm_drop=8.0,
                                    plddt_domain2_drop=5.0,
                                    second_domain_rotation_deg=15.0,
                                    second_domain_offset=1.5, jitter=0.05)
    roots = {
        "WT": fixture.write_condition(tmp_path / "wt", "wt", wt, seeds=(1, 2), samples=2),
        "PTM_01": fixture.write_condition(tmp_path / "ptm", "ptm", ptm, seeds=(1, 2),
                                          samples=2),
        "WT_DNA": fixture.write_condition(tmp_path / "wt_dna", "wt_dna", wt, seeds=(1, 2),
                                          samples=2, dna_strands=DNA_STRANDS),
        "PTM_01_DNA": fixture.write_condition(tmp_path / "ptm_dna", "ptm_dna", ptm,
                                              seeds=(1, 2), samples=2,
                                              dna_strands=DNA_STRANDS),
    }
    if corrupt_sample:
        broken = roots["PTM_01"] / "seed-1_sample-0" / "ptm_seed-1_sample-0_confidences.json"
        broken.write_text("{not json", encoding="utf-8")

    conditions = []
    for condition_id, root in roots.items():
        has_dna = "DNA" in condition_id
        has_ptm = condition_id.startswith("PTM")
        conditions.append({
            "condition_id": condition_id,
            "name": condition_id,
            "output_dir": root,
            "reference_id": "REF",
            "variant_type": "PTM" if has_ptm else ("complex" if has_dna else "WT"),
            "ptm_state": "phosphoserine" if has_ptm else "none",
            "ptm_positions_reference": PTM_POSITION if has_ptm else "",
            "dna_present": "true" if has_dna else "false",
            "construct_start": 1,
            "construct_end": len(SEQUENCE),
            "seeds": "1 2",
            "samples_per_seed": 2,
        })
    comparisons = [
        {"comparison_id": "C01", "variant": "PTM_01", "reference": "WT",
         "factor_changed": "PTM", "region": "PTM_LOCAL",
         "metrics": ["plddt_region_mean", "rmsd_local_ca", "pae_median",
                     "ptm_local_rmsd_ca"]},
        {"comparison_id": "C02", "variant": "PTM_01_DNA", "reference": "WT_DNA",
         "factor_changed": "PTM (DNA held constant)", "region": "DNA_INTERFACE",
         "metrics": ["chain_pair_iptm", "interface_contacts_heavy", "plddt_region_mean"]},
    ]
    return fixture.write_config(tmp_path, conditions, REGIONS, SEQUENCE,
                                comparisons=comparisons, analysis_yaml=ANALYSIS)


def _matplotlib_available() -> bool:
    try:
        import matplotlib  # noqa: F401
    except Exception:
        return False
    return True


def _run(config_path: Path, **options):
    config = load_config(config_path)
    run = Pipeline(config, RunOptions(**options)).run()
    return run


def test_pipeline_writes_the_documented_layout(tmp_path):
    config_path = _build(tmp_path)
    run = _run(config_path, per_atom_plddt=True)
    layout = run.layout
    for path in (
        layout.config / "analysis_config.yaml",
        layout.config / "conditions.csv",
        layout.config / "regions.csv",
        layout.config / "residue_mapping.csv",
        layout.data / "manifest.csv",
        layout.data / "plddt_per_atom.csv",
        layout.data / "plddt_per_residue.csv",
        layout.data / "plddt_region_summary.csv",
        layout.data / "pae_block_metrics.csv",
        layout.data / "interface_metrics.csv",
        layout.data / "structural_metrics.csv",
        layout.data / "hydrogen_bonds.csv",
        layout.data / "sasa_metrics.csv",
        layout.data / "electrostatics_metrics.csv",
        layout.data / "qc_report.csv",
        layout.tables / "sample_level_metrics.csv",
        layout.tables / "seed_aggregated_metrics.csv",
        layout.tables / "matched_wt_deltas.csv",
        layout.tables / "condition_summary.csv",
        layout.logs / "processing.log",
        layout.logs / "exclusions.csv",
        layout.logs / "software_versions.txt",
        layout.reports / "workflow_summary.md",
        layout.reports / "limitations.md",
    ):
        assert path.exists(), path
    for directory in ("plddt_profiles", "pae_heatmaps", "rmsd_matrices",
                      "displacement_maps", "interface_comparisons",
                      "representative_overlays"):
        assert (layout.figures / directory).is_dir()
    if _matplotlib_available():
        assert run.facts.figures
    else:
        # matplotlib is optional: without it the run must say so rather than
        # silently produce a tree with an empty figures/ directory
        assert not run.facts.figures
        assert any("matplotlib is not installed" in note for note in run.facts.notes)


def test_manifest_accounts_for_every_sample_and_excludes_the_top_ranked_copy(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    manifest = run.facts.manifest
    included = manifest[manifest["include_status"] == "included"]
    excluded = manifest[manifest["include_status"] != "included"]
    assert len(included) == 16  # 4 conditions x 2 seeds x 2 samples
    assert len(excluded) == 4   # one top-ranked alias per condition
    assert all("top-ranked" in reason for reason in excluded["exclusion_reason"])
    assert set(included["condition_id"]) == {"WT", "PTM_01", "WT_DNA", "PTM_01_DNA"}
    wild_type = included[included["condition_id"] == "WT"]
    assert set(wild_type["construct_start"]) == {1}
    assert set(wild_type["construct_end"]) == {len(SEQUENCE)}
    assert (pd.to_numeric(manifest["ranking_score"], errors="coerce") > 0).all()


def test_validation_gates_pass_and_no_sample_is_excluded(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    qc = run.facts.qc
    assert (qc["status"] == "fail").sum() == 0
    assert (qc["status"] == "pass").sum() > 0
    assert run.blocking_failures == 0
    # the gates that protect the SOP §1.2/§2.1 joins actually ran
    for check in ("token_dimensions", "atom_plddt_length", "bfactor_matches_plddt",
                  "ptm_component_present", "residue_mapping", "construct_bounds"):
        assert check in set(qc["check_id"])


def test_sample_table_marks_not_applicable_metrics_and_keeps_real_zeroes(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    table = pd.read_csv(run.layout.tables / "sample_level_metrics.csv")
    protein_only = table[table["condition_id"] == "WT"]
    with_dna = table[table["condition_id"] == "WT_DNA"]

    # ipTM and protein-DNA contacts do not apply without DNA: empty, never 0
    assert protein_only["iptm"].isna().all()
    assert protein_only["interface_contacts_heavy"].isna().all()
    assert "iptm[complex]=not_applicable" in protein_only.iloc[0]["na_metrics"]
    assert pd.to_numeric(with_dna["iptm"], errors="coerce").notna().all()
    assert pd.to_numeric(with_dna["interface_contacts_heavy"],
                         errors="coerce").notna().all()

    # a searched scope with no candidate edge is a measured zero, not a blank
    assert "hbond_candidate_count" in table.columns
    assert pd.to_numeric(with_dna["hbond_candidate_count"], errors="coerce").notna().all()

    # the §4.1 fixed columns all exist, with region columns added from the config
    for column in ("rank", "ptm", "fraction_disordered", "has_clash",
                   "mean_plddt_protein", "rmsd_global_core_ca", "rmsd_ca_DOMAIN_1",
                   "rmsd_after_anchor_DOMAIN_2", "plddt_PTM_LOCAL",
                   "pae_median_region_DOMAIN_1|DOMAIN_2"):
        assert column in table.columns


def test_structural_metrics_use_the_declared_fit_selections(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    metrics = pd.read_csv(run.layout.data / "structural_metrics.csv")
    selections = set(metrics["fit_selection"])
    assert {"CORE", "ANCHOR"} <= selections
    assert {"region:DOMAIN_1", "region:DOMAIN_2", "region:PTM_LOCAL"} <= selections
    core = metrics[(metrics["metric"] == "rmsd_global_core_ca")
                   & (metrics["fit_selection"] == "CORE")].iloc[0]
    # CORE is DOMAIN_1 (1-11) plus DOMAIN_2 (14-23): the fit never silently
    # widens to the whole construct, so the pair count is the declared regions'.
    declared_core = (11 - 1 + 1) + (23 - 14 + 1)
    assert core["n_pairs"] == declared_core
    assert core["unit"] == "angstrom"
    assert core["atom_selection"] == "CA"
    # the anchor fit measures the other domain without refitting it
    after_anchor = metrics[metrics["metric"] == "rmsd_region_after_anchor_fit"]
    assert set(after_anchor["region_id"]) == {"DOMAIN_2", "PTM_LOCAL", "LINKER"}
    measured = after_anchor[after_anchor["status"] == "ok"]
    assert "without refitting" in measured.iloc[0]["notes"]
    # LINKER is only two residues here, so its RMSD is undefined: recorded with a
    # reason instead of being dropped (SOP §1.3, §3.2).
    linker = after_anchor[(after_anchor["region_id"] == "LINKER")
                          & (after_anchor["status"] != "ok")]
    assert not linker.empty
    assert "not defined" in linker.iloc[0]["notes"]
    # the wild type is its own reference, so the top-ranked sample must land on
    # exactly zero while the other samples keep their own displacement
    protein_only = metrics[metrics["condition_id"] == "WT"]
    reference_row = protein_only[(protein_only["metric"] == "rmsd_global_core_ca")
                                 & (protein_only["fit_selection"] == "CORE")
                                 & (protein_only["n_pairs"] == declared_core)]
    assert reference_row["value"].min() == pytest.approx(0.0, abs=1e-9)
    assert set(reference_row["reference_condition"]) == {"WT"}


def test_deltas_are_matched_at_the_seed_level_with_an_interval(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    deltas = pd.read_csv(run.layout.tables / "matched_wt_deltas.csv")
    assert {"C01", "C02"} <= set(deltas["comparison_id"])
    plddt = deltas[(deltas["comparison_id"] == "C01")
                   & (deltas["metric"] == "plddt_region_mean")
                   & (deltas["scope"] == "PTM_LOCAL")].iloc[0]
    assert plddt["paired"] is True or plddt["paired"] == True  # noqa: E712
    assert plddt["n_seeds_paired"] == 2
    assert float(plddt["delta"]) < 0  # the PTM condition is modelled less confidently
    assert float(plddt["ci_low"]) <= float(plddt["delta"]) <= float(plddt["ci_high"])
    assert plddt["interpretation_tier"] == "Confidence"
    interface = deltas[deltas["comparison_id"] == "C02"]
    assert "Interface confidence" in set(interface["interpretation_tier"])
    assert set(interface["matched_reference_condition"]) == {"WT_DNA"}


def test_condition_summary_counts_coverage(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    summary = pd.read_csv(run.layout.tables / "condition_summary.csv")
    assert set(summary["condition_id"]) == {"WT", "PTM_01", "WT_DNA", "PTM_01_DNA"}
    assert (summary["n_samples_included"] == 4).all()
    assert (summary["n_seeds"] == 2).all()
    assert (summary["n_samples_excluded"] == 1).all()  # the top-ranked alias


def test_a_second_run_reuses_the_cache_and_reproduces_the_tables(tmp_path):
    config_path = _build(tmp_path)
    first = _run(config_path, per_atom_plddt=False, figures=False)
    assert first.facts.cache_misses > 0 and first.facts.cache_hits == 0
    first_table = (first.layout.tables / "sample_level_metrics.csv").read_bytes()

    second = _run(config_path, per_atom_plddt=False, figures=False)
    assert second.facts.cache_hits == first.facts.cache_misses
    assert second.facts.cache_misses == 0
    assert (second.layout.tables / "sample_level_metrics.csv").read_bytes() == first_table


def test_corrupt_sample_is_excluded_with_a_reason(tmp_path):
    run = _run(_build(tmp_path, corrupt_sample=True), per_atom_plddt=False,
               figures=False)
    manifest = run.facts.manifest
    broken = manifest[(manifest["condition_id"] == "PTM_01")
                      & (manifest["seed"] == 1) & (manifest["sample"] == 0)]
    assert len(broken) == 1
    assert broken.iloc[0]["include_status"] == "excluded"
    assert "confidence" in broken.iloc[0]["exclusion_reason"]
    exclusions = pd.read_csv(run.layout.logs / "exclusions.csv")
    assert len(exclusions) >= 1
    assert any("confidence JSON" in str(reason) for reason in exclusions["reason"])
    # the other samples of the same condition are still analysed
    assert len(manifest[(manifest["condition_id"] == "PTM_01")
                        & (manifest["include_status"] == "included")]) == 3


def test_validate_only_records_gates_without_metrics(tmp_path):
    run = _run(_build(tmp_path), validate_only=True)
    assert not run.facts.qc.empty
    # a gate-only run writes the documented tables empty, with their headers
    table = pd.read_csv(run.layout.tables / "sample_level_metrics.csv")
    assert table.empty and "condition_id" in table.columns
    observations = pd.read_csv(run.layout.data / "metrics_long.csv")
    assert observations.empty and "metric" in observations.columns
    # and produces no analysis artefacts: no figures, no overlay scripts
    assert run.facts.figures == []
    assert run.facts.overlay_scripts == []
    assert not list((run.layout.figures / "representative_overlays").glob("*.pml"))


def test_reports_state_the_evidence_boundaries(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    summary = (run.layout.reports / "workflow_summary.md").read_text(encoding="utf-8")
    limitations = (run.layout.reports / "limitations.md").read_text(encoding="utf-8")
    assert "predictions, not experiments" in summary
    assert "SOP §8 checklist" in summary
    assert "| item | result | evidence |" in summary
    assert "heavy-atom donor/acceptor candidates" in limitations
    assert "not a biological claim" in limitations or "biological claim" in limitations
    assert "electrostatics" in limitations
    versions = (run.layout.logs / "software_versions.txt").read_text(encoding="utf-8")
    assert "python" in versions and "freesasa" in versions


def test_summary_escapes_pipes_so_the_markdown_tables_hold_their_columns(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    summary = (run.layout.reports / "workflow_summary.md").read_text(encoding="utf-8")
    # Comparison rows carry scopes such as chain:A|A and region:DOMAIN_1|DOMAIN_2;
    # an unescaped pipe would be read as a column break by any Markdown renderer.
    section = summary.split("## Predefined comparisons (SOP §4.2)", 1)[1]
    section = section.split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| C0")]
    assert rows
    for line in rows:
        assert line.count("|") - line.count("\\|") == 12  # 11 columns
    assert "\\|" in section


def test_overlay_scripts_use_mapped_residue_numbers(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    scripts = sorted((run.layout.figures / "representative_overlays").glob("*.pml"))
    assert scripts, "no overlay scripts were written"
    text = scripts[0].read_text(encoding="utf-8")
    assert "align" in text
    assert "resi 1-11" in text  # ANCHOR = DOMAIN_1, expressed in model numbering
    assert "spectrum b" in text
    assert "ptm_site" in text


def test_summary_carries_the_sop_7_reading_guide_with_its_evidence_pointers(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    summary = (run.layout.reports / "workflow_summary.md").read_text(encoding="utf-8")
    assert "## Reading guide (SOP §7)" in summary
    for heading in ("Confidence and local structure", "Domain arrangement and geometry",
                    "DNA binding", "PTM chemistry and local interactions",
                    "Cofactor recruitment and functional hypotheses"):
        assert "### %s" % heading in summary
    # the guide states the paired design and points at the artefacts, without
    # claiming to answer the questions itself
    assert "C01: PTM_01 vs WT (PTM)" in summary
    assert "it does not answer any of them" in summary
    assert "`tables/matched_wt_deltas.csv`" in summary
    assert "`data/interface_residues.csv`" in summary


def test_structural_reference_follows_the_declared_comparison(tmp_path):
    run = _run(_build(tmp_path), per_atom_plddt=False, figures=False)
    summary = (run.layout.reports / "workflow_summary.md").read_text(encoding="utf-8")
    # C01 compares PTM_01 with WT and C02 compares PTM_01_DNA with WT_DNA, so the
    # PTM effect is read with the DNA state held constant (SOP §0).
    assert "structural reference is WT (matched reference declared by comparison C01" \
        in summary
    assert "structural reference is WT_DNA (matched reference declared by comparison C02" \
        in summary
    assert "wild-type baseline" in summary
    deltas = pd.read_csv(run.layout.tables / "matched_wt_deltas.csv")
    assert set(deltas[deltas["comparison_id"] == "C02"]["matched_reference_condition"]) \
        == {"WT_DNA"}
