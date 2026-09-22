"""Service-layer duplex tests (DNA duplex feature).

``ConfigurationService.add_record("dna", ...)`` must turn **one**
user-supplied 5'-to-3' strand into **two** records — the given strand and
its reverse complement — with registry-allocated, distinct identifiers,
without any front end knowing what a complement is.
"""

from __future__ import annotations

from configbuilder.app.configuration_service import ConfigurationService
from configbuilder.app.project_service import ProjectService
from configbuilder.identity import EntityId
from configbuilder.model import (
    ComponentRecord,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
)


def _service_with_protein():
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    projects.new("Duplex Probe")
    configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")
    return projects, configuration


def test_one_input_yields_two_strands():
    projects, configuration = _service_with_protein()
    outcome = configuration.add_record("dna", "ATGC")
    assert outcome.ok, outcome.message
    dna = [
        record
        for record in projects.project.configuration.records
        if isinstance(record, FamilyCRecord)
    ]
    assert [record.sequence.text for record in dna] == ["ATGC", "GCAT"]


def test_second_strand_is_the_reverse_complement():
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "GATTACA")
    dna = [
        record
        for record in projects.project.configuration.records
        if isinstance(record, FamilyCRecord)
    ]
    given, partner = dna
    assert partner.sequence.text == "TGTAATC"
    assert given.sequence.text == "GATTACA"  # user text preserved verbatim


def test_strands_receive_distinct_registry_allocated_ids():
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    dna = [
        record
        for record in projects.project.configuration.records
        if isinstance(record, FamilyCRecord)
    ]
    ids = [record.ids.primary.value for record in dna]
    assert ids[0] != ids[1]
    registry = projects.project.configuration.identity
    for value in ids:
        assert registry.multiplicity_of(EntityId(value))  # registry knows both


def test_ids_stay_correct_alongside_other_entities():
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    configuration.add_record("rna", "GGCC")
    configuration.add_record("ligand", representation="ATP")
    records = projects.project.configuration.records
    families = [type(record) for record in records]
    # protein, then the two DNA strands, then the RNA, then the ligand
    assert families == [
        FamilyARecord,
        FamilyCRecord,
        FamilyCRecord,
        FamilyBRecord,
        ComponentRecord,
    ]
    registry = projects.project.configuration.identity
    seen = []
    for record in records:
        primary = record.ids.primary.value
        seen.append(primary)
        assert registry.multiplicity_of(EntityId(primary))  # every id resolves
    assert len(set(seen)) == len(seen)  # no collisions


def test_invalid_input_follows_existing_validation_behavior():
    projects, configuration = _service_with_protein()
    before = projects.project.configuration.records
    outcome = configuration.add_record("dna", "ATGX")
    assert not outcome.ok
    assert outcome.message  # names the alphabet violation
    assert projects.project.configuration.records == before  # nothing committed


def test_dna_rejects_copies_because_duplex_is_automatic():
    projects, configuration = _service_with_protein()
    outcome = configuration.add_record("dna", "ATGC", copies=2)
    assert not outcome.ok
    assert "duplex" in outcome.message
