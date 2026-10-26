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


def test_duplex_false_commits_only_the_supplied_strand():
    """The console's "single-stranded" answer is one record, not a pair that
    is then deleted (which removed both strands)."""
    projects, configuration = _service_with_protein()
    outcome = configuration.add_record("dna", "ATGC", duplex=False)

    assert outcome.ok, outcome.message
    dna = [
        record
        for record in projects.project.configuration.records
        if isinstance(record, FamilyCRecord)
    ]
    assert [(record.ids.primary.value, record.sequence.text) for record in dna] == [
        ("B", "ATGC")
    ]
    assert projects.project.configuration.identity.is_taken("B")
    assert not projects.project.configuration.identity.is_taken("C")


def test_a_single_strand_edit_and_remove_need_no_partner():
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC", duplex=False)

    assert configuration.update_record("B", sequence="GGGG").ok
    assert _strands(projects) == [("B", "GGGG")]

    assert configuration.remove_record("B").ok
    assert _strands(projects) == []
    assert not projects.project.configuration.identity.is_taken("B")


# -- keeping the duplex consistent through edits and deletes ----------------------
#
# The builder creates the duplex, so it owns the invariant: whatever the user
# does to one strand, the pair must stay a pair. Before this was enforced, a
# sequence edit silently produced a "duplex" of two unrelated strands and the
# generated JSON contained it — the defect this block exists to prevent.


def _keys(projects):
    return [
        record.ids.primary.value for record in projects.project.configuration.records
    ]


def _strands(projects):
    return [
        (record.ids.primary.value, record.sequence.text)
        for record in projects.project.configuration.records
        if isinstance(record, FamilyCRecord)
    ]


def test_editing_one_strand_updates_its_partner():
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    given, partner = _keys(projects)[1:]

    outcome = configuration.update_record(given, sequence="AAAA")

    assert outcome.ok, outcome.message
    assert _strands(projects) == [(given, "AAAA"), (partner, "TTTT")]
    assert "both strands" in outcome.message


def test_editing_the_partner_strand_updates_the_other_side():
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    given, partner = _keys(projects)[1:]

    assert configuration.update_record(partner, sequence="CCCC").ok

    assert _strands(projects) == [(given, "GGGG"), (partner, "CCCC")]


def test_descriptions_do_not_disturb_the_pair():
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    given, partner = _keys(projects)[1:]

    assert configuration.update_record(given, description="keep me").ok

    assert _strands(projects) == [(given, "ATGC"), (partner, "GCAT")]


def test_removing_one_strand_removes_the_duplex_and_releases_both_ids():
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    given, partner = _keys(projects)[1:]

    outcome = configuration.remove_record(given)

    assert outcome.ok, outcome.message
    assert "duplex" in outcome.message
    assert _strands(projects) == []
    registry = projects.project.configuration.identity
    assert not registry.is_taken(given)
    assert not registry.is_taken(partner)


def test_independently_added_duplexes_never_cross_pair():
    """Adding ATGC and later GCAT makes two duplexes, not a four-strand tangle:
    each strand pairs only with the strand allocated beside it."""
    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    configuration.add_record("dna", "GCAT")
    first, first_partner, second, second_partner = _keys(projects)[1:]
    assert _strands(projects) == [
        (first, "ATGC"),
        (first_partner, "GCAT"),
        (second, "GCAT"),
        (second_partner, "ATGC"),
    ]

    assert configuration.update_record(first, sequence="TTTT").ok

    assert _strands(projects) == [
        (first, "TTTT"),
        (first_partner, "AAAA"),
        (second, "GCAT"),          # untouched
        (second_partner, "ATGC"),  # untouched
    ]


def test_a_lone_strand_is_edited_on_its_own(tmp_path, monkeypatch):
    """An imported single DNA chain has no partner; editing it must not fail
    and must not look for one."""
    import json

    monkeypatch.chdir(tmp_path)
    document = {
        "name": "lone-dna",
        "modelSeeds": [1],
        "sequences": [{"dna": {"id": "A", "sequence": "ATGC"}}],
        "dialect": "alphafold3",
        "version": 3,
    }
    source = tmp_path / "lone.json"
    source.write_text(json.dumps(document), encoding="utf-8")

    projects = ProjectService()
    assert projects.import_json_commit(str(source)).ok
    configuration = ConfigurationService(projects)

    outcome = configuration.update_record("A", sequence="GGGG")

    assert outcome.ok, outcome.message
    assert _strands(projects) == [("A", "GGGG")]


def test_generated_json_never_contains_a_broken_duplex(tmp_path):
    """The regression that motivated the fix: after editing a strand, the
    written file held two non-complementary DNA entities."""
    import json
    import pathlib as _pathlib

    from configbuilder.app.generation_service import GenerationService
    from configbuilder.app.validation_service import ValidationService
    from configbuilder.app.variant_service import VariantService

    projects = ProjectService()
    configuration = ConfigurationService(projects)
    variants = VariantService(projects, configuration)
    projects.new("Duplex Output")
    configuration.add_record("dna", "ATGC")
    given, partner = _keys(projects)[0:2]
    assert configuration.update_record(given, sequence="AAAA").ok

    generation = GenerationService(projects, variants, validation=ValidationService(projects))
    plan = generation.plan_base(str(tmp_path / "out"))
    assert plan.ok, getattr(plan, "message", "")
    assert generation.execute(plan).ok

    written = sorted(_pathlib.Path(tmp_path / "out").rglob("*.json"))
    assert written
    document = json.loads(written[0].read_text(encoding="utf-8"))
    strands = {
        entity["dna"]["id"]: entity["dna"]["sequence"]
        for entity in document["sequences"]
        if "dna" in entity
    }
    assert strands == {given: "AAAA", partner: "TTTT"}


# -- the same rule on the variant path -------------------------------------------


def test_variant_sequence_edit_keeps_the_duplex_and_leaves_the_base_alone():
    from configbuilder.identity import EntityId
    from configbuilder.model import SequenceText
    from configbuilder.variants.edits import SetSequence, apply_edit

    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    base = projects.project.configuration
    given, partner = _keys(projects)[1:]

    edited = apply_edit(SetSequence(EntityId(given), SequenceText("GGGG", "dna")), base)

    assert [
        (r.ids.primary.value, r.sequence.text) for r in edited.records
        if isinstance(r, FamilyCRecord)
    ] == [(given, "GGGG"), (partner, "CCCC")]
    assert [
        (r.ids.primary.value, r.sequence.text) for r in base.records
        if isinstance(r, FamilyCRecord)
    ] == [(given, "ATGC"), (partner, "GCAT")]  # the base is untouched


def test_variant_remove_record_removes_the_duplex_pair():
    from configbuilder.identity import EntityId
    from configbuilder.variants.edits import RemoveRecord, apply_edit

    projects, configuration = _service_with_protein()
    configuration.add_record("dna", "ATGC")
    base = projects.project.configuration
    given, partner = _keys(projects)[1:]

    removed = apply_edit(RemoveRecord(EntityId(given)), base)

    remaining = [r.ids.primary.value for r in removed.records]
    assert given not in remaining and partner not in remaining
    assert given in [r.ids.primary.value for r in base.records]  # base untouched
