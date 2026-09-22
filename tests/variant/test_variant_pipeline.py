"""Variant pipeline test (plan §12, Phase 7 checklist).

Expansion produces complete variant configurations; the variant documents
are built by ``transform`` at the pipeline boundary (the plan §5.3 rule 2
join) and compared through the serializer: regions no edit touched must be
byte-identical to the base's document.
"""

from __future__ import annotations

from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import (
    Configuration,
    ConfigurationMetadata,
    FamilyARecord,
    FamilyBRecord,
    FormatTarget,
    Pinned,
    SeedSet,
    SequenceText,
)
from configbuilder.serialize import encode
from configbuilder.transform import to_wire
from configbuilder.variants import VariantSpec, expand
from configbuilder.variants.edits import SetName, SetSequence
from configbuilder.identity import EntityId


def _base():
    registry = IdentityRegistry()
    a = registry.allocate().value
    b = registry.allocate().value
    return Configuration(
        metadata=ConfigurationMetadata("variant demo"),
        seeds=SeedSet([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        records=(
            FamilyARecord(ids=Multiplicity([a]), sequence=SequenceText("PEPTIDE", "protein")),
            FamilyBRecord(ids=Multiplicity([b]), sequence=SequenceText("GGCC", "rna")),
        ),
        identity=registry,
    ).with_format_target(FormatTarget(version_selection=Pinned(3)))


def _mutant_spec():
    return VariantSpec(
        key="mut",
        label="mutant",
        edits=(SetSequence(EntityId("A"), SequenceText("MUTATEDPEPTIDE", "protein")),),
    )


def test_variant_document_builds_and_differs_only_in_the_edit():
    base = _base()
    variants = expand(base, (_mutant_spec(),))
    variant_doc = to_wire(variants[0].configuration).document
    base_doc = to_wire(base).document

    assert variant_doc["sequences"][0]["protein"]["sequence"] == "MUTATEDPEPTIDE"
    assert base_doc["sequences"][0]["protein"]["sequence"] == "PEPTIDE"
    # Untouched regions are identical.
    assert variant_doc["sequences"][1] == base_doc["sequences"][1]
    assert variant_doc["modelSeeds"] == base_doc["modelSeeds"]
    assert variant_doc["name"] == base_doc["name"]


def test_inherited_regions_are_byte_identical():
    base = _base()
    variants = expand(base, (_mutant_spec(),))
    base_doc = to_wire(base).document
    variant_doc = to_wire(variants[0].configuration).document

    assert encode({"sequences": [base_doc["sequences"][1]]}) == encode(
        {"sequences": [variant_doc["sequences"][1]]}
    )


def test_name_edit_reaches_the_wire_root():
    base = _base()
    variants = expand(base, (VariantSpec(key="renamed", label="r", edits=(SetName("renamed job"),)),))
    doc = to_wire(variants[0].configuration).document
    assert doc["name"] == "renamed job"


def test_full_variant_document_encodes_deterministically():
    first = encode(to_wire(expand(_base(), (_mutant_spec(),))[0].configuration).document)
    second = encode(to_wire(expand(_base(), (_mutant_spec(),))[0].configuration).document)
    assert first == second


def test_removed_record_drops_its_wire_entity():
    base = _base()
    from configbuilder.variants.edits import RemoveRecord

    variants = expand(base, (VariantSpec(key="trunc", label="t", edits=(RemoveRecord(EntityId("B")),)),))
    variant_doc = to_wire(variants[0].configuration).document
    assert [e["protein"]["id"] if "protein" in e else e["rna"]["id"] for e in variant_doc["sequences"]] == ["A"]
