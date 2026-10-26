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
from configbuilder.transform import to_wire
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


# -- variant MSA changes: the target family's own case -------------------------------


def _services_with_protein_and_rna():
    """A real project holding one protein (A) and one RNA (B), and a spec."""
    services = build_services()
    services.projects.new("rna variant")
    services.configuration.add_record("protein", "ACDEFG")
    services.configuration.add_record("rna", "ACGU")
    services.variants.add_spec("WT", "WT", ())
    return services


def test_alignment_change_on_an_rna_record_builds_the_single_case():
    services = _services_with_protein_and_rna()
    outcome = services.variants.apply_variant_edit(
        "WT", "alignment", ("provided", ("inline", ">q\nACGU")), record_key="B"
    )
    assert outcome.ok, outcome.message
    edit = services.projects.project.specs[0].edits[0]
    assert type(edit).__name__ == "SetSingleAlignment"
    assert edit._record_key.value == "B"


def test_alignment_change_on_a_protein_record_builds_the_paired_case():
    services = _services_with_protein_and_rna()
    outcome = services.variants.apply_variant_edit(
        "WT", "alignment", ("free", None), record_key="A"
    )
    assert outcome.ok, outcome.message
    assert type(services.projects.project.specs[0].edits[0]).__name__ == "SetAlignment"


def test_alignment_change_on_a_dna_record_refuses():
    services = build_services()
    services.projects.new("dna variant")
    services.configuration.add_record("dna", "ATGC")
    services.variants.add_spec("WT", "WT", ())
    outcome = services.variants.apply_variant_edit(
        "WT", "alignment", ("automatic", None), record_key="A"
    )
    assert not outcome.ok
    assert "protein or an RNA chain" in outcome.message


def test_rna_alignment_change_expands_into_the_unpaired_msa_field():
    services = _services_with_protein_and_rna()
    services.variants.apply_variant_edit(
        "WT", "alignment", ("provided", ("inline", ">q\nACGU")), record_key="B"
    )
    outcome = services.variants.expand(only=["WT"])
    assert outcome.ok
    document = to_wire(outcome.variants[0].configuration).document
    rna = [entity["rna"] for entity in document["sequences"] if "rna" in entity][0]
    assert rna["unpairedMsa"] == ">q\nACGU"
    assert "pairedMsa" not in rna
