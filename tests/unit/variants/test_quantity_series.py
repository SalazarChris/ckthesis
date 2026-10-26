"""Component quantity vs. concentration/quantity series (feature spec).

Two concepts kept separate throughout:

* **Quantity at add time** — ``add_record(copies=N)`` is base-job
  definition (already existing model machinery; here we pin that the
  app service round-trips it and the listing shows it).
* **Quantity series** — a *variant* operation: guided plan, preview as
  data, one independent ``base + SetComponentCount`` spec per level,
  committed through the standard route, base never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from configbuilder.app.project_service import ProjectService
from configbuilder.app.configuration_service import ConfigurationService
from configbuilder.app.variant_service import VariantService
from configbuilder.variants import SetComponentCount
from configbuilder.model import ComponentRecord


def _services(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    variants = VariantService(projects, configuration)
    projects.new("Series Probe")
    return projects, configuration, variants


def _base_with_components(configuration):
    """Protein A + H2O(B x1) + Na(C x3) + Cl(D x2)."""
    configuration.add_record(family="protein", sequence="MKTAY")
    configuration.add_record(family="ligand", representation="HOH", copies=1)
    configuration.add_record(family="ligand", representation="NA", copies=3)
    configuration.add_record(family="ligand", representation="CL", copies=2)


def _counts(configuration):
    """Primary-key → copy count for every ligand record."""
    return {
        record.ids.primary.value: len(record.ids.ids)
        for record in configuration.records
        if isinstance(record, ComponentRecord)
    }


def _count_sequence(configuration):
    """Copy counts in record order (id letters may shift with allocation)."""
    return tuple(
        len(record.ids.ids)
        for record in configuration.records
        if isinstance(record, ComponentRecord)
    )


def _expand_keys(variants):
    from configbuilder.app.results import ExpandOutput

    return variants.expand()


# -- quantity is part of the base job --------------------------------------------


def test_add_ion_with_quantity_one(tmp_path, monkeypatch):
    projects, configuration, _ = _services(tmp_path, monkeypatch)
    assert configuration.add_record(family="ligand", representation="NA").ok
    assert _counts(projects.project.configuration) == {"A": 1}


def test_add_ion_with_quantity_three(tmp_path, monkeypatch):
    projects, configuration, _ = _services(tmp_path, monkeypatch)
    assert configuration.add_record(family="ligand", representation="NA", copies=3).ok
    assert _counts(projects.project.configuration) == {"A": 3}


def test_add_ion_with_custom_quantity(tmp_path, monkeypatch):
    projects, configuration, _ = _services(tmp_path, monkeypatch)
    assert configuration.add_record(family="ligand", representation="NA", copies=7).ok
    assert _counts(projects.project.configuration) == {"A": 7}


def test_add_multiple_ions_with_different_quantities(tmp_path, monkeypatch):
    projects, configuration, _ = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    assert _count_sequence(projects.project.configuration) == (1, 3, 2)


def test_quantity_survives_persistence(tmp_path, monkeypatch):
    projects, configuration, _ = _services(tmp_path, monkeypatch)
    configuration.add_record(family="ligand", representation="NA", copies=3)
    from configbuilder.persistence import save, load

    path = str(tmp_path / "p.cbproj")
    save(projects.project, path)
    loaded = load(path).project
    assert _counts(loaded.configuration) == {"A": 3}


# -- the series plan (pure data; nothing created) --------------------------------


def test_plan_single_component_series(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    rows, failure = variants.quantity_series_plan(["C"], 1, 10, 4)
    assert failure is None
    assert [multiplier for multiplier, _ in rows] == [1, 10, 100, 1000]
    assert [counts["C"] for _, counts in rows] == [3, 30, 300, 3000]


def test_plan_multiple_component_series(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    component_keys = sorted(_counts(projects.project.configuration))
    rows, failure = variants.quantity_series_plan(component_keys, 1, 10, 3)
    assert failure is None
    # every selected component scales from *its own base quantity* (1,3,2)
    assert [rows[0][1][k] for k in component_keys] == [1, 3, 2]
    assert [rows[1][1][k] for k in component_keys] == [10, 30, 20]
    assert [rows[2][1][k] for k in component_keys] == [100, 300, 200]


def test_plan_factor_two(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    rows, _ = variants.quantity_series_plan(["C"], 1, 2, 3)
    assert [multiplier for multiplier, _ in rows] == [1, 2, 4]


def test_plan_rejects_bad_progression(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    for start, factor, levels in ((0, 10, 2), (1, 0, 2), (1, 10, 0)):
        _, failure = variants.quantity_series_plan(["C"], start, factor, levels)
        assert failure is not None
    _, failure = variants.quantity_series_plan([], 1, 10, 2)
    assert failure is not None
    _, failure = variants.quantity_series_plan(["A"], 1, 10, 2)  # a protein, not a ligand
    assert failure is not None


def test_plan_creates_nothing(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    variants.quantity_series_plan(["C"], 1, 10, 4)
    assert projects.project.specs == ()


# -- the committed series ---------------------------------------------------------


def test_create_series_makes_independent_variants_base_untouched(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    base_counts = _counts(projects.project.configuration)

    component_keys = sorted(_counts(projects.project.configuration))
    outcome = variants.create_quantity_series(component_keys, 1, 10, 3)
    assert outcome.ok, outcome.message
    keys = [spec.key for spec in projects.project.specs]
    assert keys == ["series_1x", "series_10x", "series_100x"]

    expanded = variants.expand()
    assert expanded.ok
    sequences = [
        _count_sequence(getattr(v, "configuration", v)) for v in expanded.variants
    ]
    assert sequences[0] == (1, 3, 2)
    assert sequences[1] == (10, 30, 20)
    assert sequences[2] == (100, 300, 200)

    # the base is exactly as it was
    assert _counts(projects.project.configuration) == base_counts


def test_series_variants_serialize_and_validate(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    na_key = _counts(projects.project.configuration)
    target = max(na_key, key=na_key.get)  # the x3 component
    variants.create_quantity_series([target], 1, 10, 3)

    # pin the version so generation passes the CONTRACT gate
    configuration.set_format_target(version=3)

    from configbuilder.app.generation_service import GenerationService
    from configbuilder.app.validation_service import ValidationService

    generation = GenerationService(projects, variants, validation=ValidationService(projects))
    out_root = tmp_path / "out"
    plan = generation.plan(str(out_root))
    assert plan.ok, getattr(plan, "message", "")
    result = generation.execute(plan)
    assert result.ok, getattr(result, "message", "")
    # every written variant JSON carries the scaled id list on the NA entity
    id_lists = []
    for path in sorted(out_root.rglob("*series*.json")):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for wrapper in payload.get("sequences", []):
            ligand = wrapper.get("ligand")
            if ligand is not None and ligand.get("ccdCodes") == ["NA"]:
                value = ligand.get("id")
                id_lists.append([str(v) for v in (value if isinstance(value, list) else [value])])
    assert id_lists, "the NA entities must appear in the written files"
    assert sorted(len(ids) for ids in id_lists) == [3, 30, 300]


def test_series_is_deterministic(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    keys = sorted(_counts(projects.project.configuration))
    variants.create_quantity_series(keys, 2, 5, 3)

    def snapshot():
        out = variants.expand()
        return [
            tuple(tuple(e.value for e in record.ids.ids) for record in getattr(v, "configuration", v).records)
            for v in out.variants
        ]

    first = snapshot()
    second = snapshot()
    assert first == second
    # multipliers follow start * factor**(level-1): 2, 10, 50
    assert [spec.key for spec in projects.project.specs] == ["series_2x", "series_10x", "series_50x"]


def test_series_refuses_duplicate_keys_without_partial_commit(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    variants.add_spec(key="series_10x", label="taken", edits=())
    before = [spec.key for spec in projects.project.specs]
    outcome = variants.create_quantity_series(sorted(_counts(projects.project.configuration)), 1, 10, 3)
    assert not outcome.ok
    assert [spec.key for spec in projects.project.specs] == before


def test_series_via_apply_variant_edit(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    assert variants.add_spec(key="na", label="Na", edits=()).ok
    counts = _counts(projects.project.configuration)
    na_key = max(counts, key=counts.get)  # the x3 component
    base_other = {k: v for k, v in counts.items() if k != na_key}
    outcome = variants.apply_variant_edit("na", "component_count", 6, record_key=na_key)
    assert outcome.ok, outcome.message
    expanded = variants.expand(only=("na",))
    vconf = getattr(expanded.variants[0], "configuration", expanded.variants[0])
    new_counts = _counts(vconf)
    assert new_counts[na_key] == 6
    assert {k: v for k, v in new_counts.items() if k != na_key} == base_other


# -- identity: unique, registry-owned ids -----------------------------------------


def test_series_ids_are_unique_and_registry_owned(tmp_path, monkeypatch):
    projects, configuration, variants = _services(tmp_path, monkeypatch)
    _base_with_components(configuration)
    variants.create_quantity_series(sorted(_counts(projects.project.configuration)), 1, 10, 3)
    expanded = variants.expand()
    for variant in expanded.variants:
        configuration_v = getattr(variant, "configuration", variant)
        letters = [
            entity.value
            for record in configuration_v.records
            for entity in record.ids.ids
        ]
        assert len(letters) == len(set(letters))
        # every id is claimed by the variant's own registry
        for letter in letters:
            assert configuration_v.identity.is_taken(letter)


# -- UI separation ----------------------------------------------------------------
#
# The reworked menu asks the quantity at add time and no longer exposes the
# series planner or the preview screen — those remain service operations,
# covered above. The UI pin that survives is the guided add-time quantity.


def test_ui_quantity_is_asked_on_add(tmp_path, monkeypatch):
    from configbuilder.app.cli import MenuApp
    from configbuilder.ui.services import build_services
    from configbuilder.ui.render.console import ScriptedConsole

    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole(
        ["1", "QtyUI"]
        # job 2 (add entity) → 4 (ligand) → 1 (CCD) → NA → qty 2, then the
        # entity picker shows the counted line, then leave → discard → exit
        + ["2", "4", "1", "NA", "2", "3", "0", "0", "2", "0"]
    )
    app = MenuApp(build_services(), console)
    status = app.run()
    out = console.transcript
    assert status == 0
    # the add flow asked the quantity question and never mentioned series
    assert "How many copies of this ligand do you want?" in out
    assert "concentration" not in out.lower()
    # the entity listing shows the counted ligand line
    assert "x2" in out
