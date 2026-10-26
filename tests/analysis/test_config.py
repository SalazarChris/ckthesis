"""Configuration loading and validation (SOP §0, §3.1, §4.3)."""

from __future__ import annotations

import pytest

# The analysis stack is an optional extra (see pyproject.toml), and numpy and
# pandas are its hard requirements.  The guard sits before every other import in
# this module on purpose: on an interpreter without them the honest result is
# "not tested here", not an ImportError in the middle of the suite (CI installs
# the builder's dev extra only).
pytest.importorskip("numpy", reason="af3_analysis requires numpy")
pytest.importorskip("pandas", reason="af3_analysis requires pandas")

import json
from pathlib import Path


from af3_analysis.config import (
    ConfigError,
    load_config,
    read_residue_mapping,
)
from af3_analysis.templates import write_templates
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
  contact_cutoff_A: 4.5
  statistics:
    bootstrap_resamples: 200
"""


def _conditions(tmp_path: Path):
    return [
        {"condition_id": "WT", "name": "wild type", "output_dir": tmp_path / "wt",
         "reference_id": "REF", "variant_type": "WT", "ptm_state": "none",
         "dna_present": "false", "construct_start": 1, "construct_end": len(SEQUENCE),
         "seeds": "1 2", "samples_per_seed": 2},
        {"condition_id": "PTM_01", "name": "phospho", "output_dir": tmp_path / "ptm",
         "reference_id": "REF", "variant_type": "PTM", "ptm_state": "phosphoserine",
         "ptm_positions_reference": 12, "dna_present": "false",
         "construct_start": 1, "construct_end": len(SEQUENCE),
         "seeds": "1 2", "samples_per_seed": 2},
    ]


def test_loads_a_complete_configuration(tmp_path):
    path = fixture.write_config(
        tmp_path, _conditions(tmp_path), REGIONS, SEQUENCE,
        comparisons=[{"comparison_id": "C01", "variant": "PTM_01", "reference": "WT",
                      "metrics": ["plddt_region_mean", "rmsd_local_ca"]}],
        analysis_yaml=ANALYSIS,
    )
    config = load_config(path)
    assert [c.condition_id for c in config.conditions] == ["WT", "PTM_01"]
    assert config.conditions[1].modified_positions_reference == (12,)
    assert config.region("PTM_LOCAL").positions()[0] == 7
    assert [s.name for s in config.settings.fit_selections] == ["CORE", "ANCHOR"]
    assert config.comparisons[0].comparison_id == "C01"
    assert config.output_root == (path.parent / "analysis").resolve()
    assert config.problems == ()


def test_archive_document_records_the_decisions(tmp_path):
    path = fixture.write_config(tmp_path, _conditions(tmp_path), REGIONS, SEQUENCE,
                                analysis_yaml=ANALYSIS)
    config = load_config(path)
    document = config.archive_document()
    assert document["project"] == "synthetic analysis test"
    assert document["conditions"][0]["condition_id"] == "WT"
    assert document["references"][0]["sequence"] == SEQUENCE
    assert document["settings"]["contact_cutoff_A"] == 4.5
    written = config.archive(tmp_path / "frozen.yaml")
    assert written.exists() and "conditions" in written.read_text(encoding="utf-8")


def test_region_outside_the_reference_is_refused(tmp_path):
    bad = list(REGIONS) + [{"region_id": "TOO_FAR", "start": 1, "end": 999}]
    path = fixture.write_config(tmp_path, _conditions(tmp_path), bad, SEQUENCE)
    with pytest.raises(ConfigError) as excinfo:
        load_config(path)
    assert "TOO_FAR" in str(excinfo.value)


def test_unknown_reference_is_refused(tmp_path):
    conditions = _conditions(tmp_path)
    conditions[0]["reference_id"] = "NOT_DECLARED"
    path = fixture.write_config(tmp_path, conditions, REGIONS, SEQUENCE)
    with pytest.raises(ConfigError) as excinfo:
        load_config(path)
    assert "NOT_DECLARED" in str(excinfo.value)


def test_unknown_comparison_metric_is_refused(tmp_path):
    path = fixture.write_config(
        tmp_path, _conditions(tmp_path), REGIONS, SEQUENCE,
        comparisons=[{"comparison_id": "C01", "variant": "PTM_01", "reference": "WT",
                      "metrics": ["not_a_metric"]}],
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(path)
    assert "not_a_metric" in str(excinfo.value)


def test_fit_selection_naming_an_unknown_region_is_refused(tmp_path):
    path = fixture.write_config(tmp_path, _conditions(tmp_path), REGIONS, SEQUENCE,
                                analysis_yaml="analysis:\n  fit_selections:\n"
                                              "    - name: CORE\n      regions: [NOPE]\n")
    with pytest.raises(ConfigError) as excinfo:
        load_config(path)
    assert "NOPE" in str(excinfo.value)


def test_missing_fit_selections_is_a_recorded_problem_not_a_crash(tmp_path):
    path = fixture.write_config(tmp_path, _conditions(tmp_path), REGIONS, SEQUENCE)
    config = load_config(path)
    assert any("fit_selections" in problem for problem in config.problems)


def test_json_configuration_is_accepted(tmp_path):
    yaml_path = fixture.write_config(tmp_path, _conditions(tmp_path), REGIONS, SEQUENCE,
                                      analysis_yaml=ANALYSIS)
    document = {
        "project": "json config",
        "output_root": "./analysis",
        "reference_sequences": [{"reference_id": "REF", "name": "ref",
                                 "sequence": SEQUENCE}],
        "conditions": "conditions.csv",
        "regions": "regions.csv",
        "analysis": {"fit_selections": [{"name": "CORE",
                                         "regions": ["DOMAIN_1", "DOMAIN_2"]}]},
    }
    json_path = yaml_path.with_name("analysis_config.json")
    json_path.write_text(json.dumps(document), encoding="utf-8")
    config = load_config(json_path)
    assert config.project == "json config"
    assert config.settings.fit_selections[0].regions == ("DOMAIN_1", "DOMAIN_2")


def test_templates_load_without_editing(tmp_path):
    written = write_templates(tmp_path)
    assert {path.name for path in written} == {
        "analysis_config.yaml", "conditions.csv", "regions.csv", "residue_mapping.csv"}
    config = load_config(tmp_path / "analysis_config.yaml")
    # The template carries four example conditions and four declared regions.
    assert len(config.conditions) == 4
    assert {region.region_id for region in config.regions} == {
        "DOMAIN_1", "LINKER", "DOMAIN_2", "PTM_LOCAL"}
    assert config.comparisons[0].comparison_id == "C01"


def test_explicit_residue_mapping_file_is_optional_and_parsed(tmp_path):
    path = fixture.write_config(tmp_path, _conditions(tmp_path), REGIONS, SEQUENCE)
    config = load_config(path)
    assert read_residue_mapping(config.residue_mapping_path) == {}
    mapping_file = tmp_path / "residue_mapping.csv"
    mapping_file.write_text(
        "condition_id,chain_id,model_res_id,insertion_code,residue_name,"
        "reference_position,is_modified,modification_component,alignment_status,notes\n"
        "DEL_01,A,45,,GLY,45,false,,explicit,kept for context\n",
        encoding="utf-8",
    )
    grouped = read_residue_mapping(mapping_file)
    assert ("DEL_01", "A") in grouped
    assert grouped[("DEL_01", "A")]["45"]["reference_position"] == "45"
