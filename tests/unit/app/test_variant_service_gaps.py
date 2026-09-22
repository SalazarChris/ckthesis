"""Tests for the variant-service additions behind the free-navigation UI.

``expand(only=...)`` is the subset route shared by validation and export;
``append_factor`` grows an existing spec through the picker's own factor →
edit conversion (``ui`` never constructs variant vocabulary).
"""

from __future__ import annotations

from configbuilder.app.project_service import Project
from configbuilder.app.project_service import ProjectService
from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import SeedSet, SequenceText
from configbuilder.model.configuration import Configuration, ConfigurationMetadata
from configbuilder.model.records import FamilyARecord
from configbuilder.ui.services import build_services
from configbuilder.variants.spec import VariantSpec


def _services_with_spec():
    """Services over a real project holding one variant spec."""
    services = build_services()
    registry = IdentityRegistry()
    record = FamilyARecord(
        Multiplicity(["A"]), SequenceText("ACDEFG", "protein")
    )
    configuration = Configuration(
        metadata=ConfigurationMetadata("experiment"),
        seeds=SeedSet([1, 2, 3]),
        records=(record,),
        identity=registry,
    )
    spec = VariantSpec("T101P", "T101P", ())
    project = Project(configuration=configuration, specs=(spec,), settings=None)
    services.projects._project = project
    return services


# -- expand(only=...) ---------------------------------------------------------------


def test_expand_without_only_expands_every_spec():
    services = _services_with_spec()
    outcome = services.variants.expand()
    assert outcome.ok
    assert [variant.key for variant in outcome.variants] == ["T101P"]


def test_expand_only_selects_the_named_subset_in_order():
    services = _services_with_spec()
    services.variants.add_spec("WT", "WT", ())
    services.variants.add_spec("S102P", "S102P", ())
    outcome = services.variants.expand(only=["S102P", "WT"])
    assert outcome.ok
    assert [variant.key for variant in outcome.variants] == ["S102P", "WT"]


def test_expand_only_with_unknown_key_refuses():
    services = _services_with_spec()
    outcome = services.variants.expand(only=["NOPE"])
    assert not outcome.ok
    assert "NOPE" in outcome.message


def test_expand_only_empty_selection_expands_nothing():
    """An empty ``only`` means \"nothing selected\", never \"everything\"."""
    services = _services_with_spec()
    outcome = services.variants.expand(only=())
    assert outcome.ok
    assert outcome.variants == ()


# -- append_factor --------------------------------------------------------------------


def test_append_factor_grows_the_existing_spec():
    services = _services_with_spec()
    outcome = services.variants.append_factor("T101P", "job_name", "T101P_run")
    assert outcome.ok
    specs = services.projects.project.specs
    assert len(specs) == 1  # grown, not duplicated
    kinds = [type(edit).__name__ for edit in specs[0].edits]
    assert kinds == ["SetName"]


def test_append_factor_twice_keeps_both_edits():
    services = _services_with_spec()
    assert services.variants.append_factor("T101P", "job_name", "A").ok
    assert services.variants.append_factor("T101P", "job_description", "d").ok
    kinds = [type(edit).__name__ for edit in services.projects.project.specs[0].edits]
    assert kinds == ["SetName", "SetJobDescription"]


def test_append_factor_unknown_variant_refuses():
    services = _services_with_spec()
    outcome = services.variants.append_factor("NOPE", "job_name", "x")
    assert not outcome.ok


def test_append_factor_unknown_factor_refuses():
    services = _services_with_spec()
    outcome = services.variants.append_factor("T101P", "colour", "red")
    assert not outcome.ok
    assert "colour" in outcome.message


def test_append_factor_sequence_targets_a_named_record():
    services = _services_with_spec()
    outcome = services.variants.append_factor(
        "T101P", "sequence", "ACDEWP", record_key="A"
    )
    assert outcome.ok
    assert outcome.ok
    edits = services.projects.project.specs[0].edits
    assert len(edits) == 1
