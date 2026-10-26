"""Independent paired/unpaired MSA sources across the model and persistence."""

from __future__ import annotations

from configbuilder.model import AlignmentBoth, External, Inline, PathSpec
from configbuilder.persistence.decode_model import decode_configuration
from configbuilder.persistence.encode_model import encode_configuration
from configbuilder.transform import to_wire
from configbuilder.ui.services import build_services


def _project():
    services = build_services()
    services.projects.new("msa-sources")
    services.configuration.add_record("protein", "ACDEFGHIKL")
    return services


def test_both_keeps_two_inline_sources_distinct():
    services = _project()
    outcome = services.configuration.set_alignment(
        "A",
        "both",
        inline_text=">unpaired\nACDEFGHIKL\n",
        paired_inline_text=">paired\nACDEFGHIKL\n",
    )
    assert outcome.ok, outcome.message
    alignment = services.projects.project.configuration.records[0].alignment
    assert isinstance(alignment, AlignmentBoth)
    assert alignment.unpaired_source == Inline(">unpaired\nACDEFGHIKL\n")
    assert alignment.paired_source == Inline(">paired\nACDEFGHIKL\n")


def test_both_keeps_two_external_paths_and_serializes_each_field():
    services = _project()
    outcome = services.configuration.set_alignment(
        "A",
        "both",
        external_path="unpaired.a3m",
        paired_external_path="paired.a3m",
    )
    assert outcome.ok, outcome.message
    result = to_wire(services.projects.project.configuration)
    protein = result.document["sequences"][0]["protein"]
    assert protein["unpairedMsaPath"] == "unpaired.a3m"
    assert protein["pairedMsaPath"] == "paired.a3m"
    kinds = {(requirement.kind, requirement.raw_path) for requirement in result.external_resources}
    assert kinds == {
        ("unpairedMsaPath", "unpaired.a3m"),
        ("pairedMsaPath", "paired.a3m"),
    }


def test_one_source_both_keeps_the_historical_same_file_behaviour():
    services = _project()
    outcome = services.configuration.set_alignment(
        "A", "both", external_path="shared.a3m"
    )
    assert outcome.ok, outcome.message
    protein = to_wire(services.projects.project.configuration).document["sequences"][0][
        "protein"
    ]
    assert protein["unpairedMsaPath"] == "shared.a3m"
    assert protein["pairedMsaPath"] == "shared.a3m"


def test_persistence_round_trip_preserves_distinct_sources():
    services = _project()
    services.configuration.set_alignment(
        "A",
        "both",
        inline_text=">unpaired\nACDEFGHIKL\n",
        paired_inline_text=">paired\nACDEFGHIKL\n",
    )
    original = services.projects.project.configuration
    decoded = decode_configuration(encode_configuration(original))
    alignment = decoded.records[0].alignment
    assert isinstance(alignment, AlignmentBoth)
    assert alignment.source == Inline(">unpaired\nACDEFGHIKL\n")
    assert alignment.paired_source == Inline(">paired\nACDEFGHIKL\n")


def test_persistence_still_reads_the_old_single_source_form():
    services = _project()
    services.configuration.set_alignment("A", "both", external_path="shared.a3m")
    data = encode_configuration(services.projects.project.configuration)
    record = data["records"][0]["alignment"]
    assert record["form"] == "both"
    assert "paired_source" not in record

    decoded = decode_configuration(data)
    alignment = decoded.records[0].alignment
    assert alignment.source == External(PathSpec("shared.a3m"))
    assert alignment.paired_source == External(PathSpec("shared.a3m"))
