"""Unit tests for variant specification and expansion (plan §12.2–§12.4).

Expansion is a pure function: same base + same specs = same variants, in
the same order, with the same identifier assignments — no clock, no
randomness, no dict-order dependence.
"""

from __future__ import annotations

import pytest

from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity
from configbuilder.model import (
    Configuration,
    ConfigurationMetadata,
    FamilyARecord,
    FamilyBRecord,
    SeedSet,
    SequenceText,
)
from configbuilder.variants import (
    VariantSpec,
    VariantSpecError,
    apply_edit,
    declared_changes,
    expand,
)
from configbuilder.variants.edits import (
    AddModification,
    RemoveRecord,
    SetDescription,
    SetName,
    SetSequence,
)
from configbuilder.model import ComponentCode, Position, Present


def _base():
    registry = IdentityRegistry()
    a = registry.allocate().value
    b = registry.allocate().value
    return Configuration(
        metadata=ConfigurationMetadata("base job", "original description"),
        seeds=SeedSet([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        records=(
            FamilyARecord(ids=Multiplicity([a]), sequence=SequenceText("PEPTIDE", "protein")),
            FamilyBRecord(ids=Multiplicity([b]), sequence=SequenceText("GGCC", "rna")),
        ),
        identity=registry,
    )


def _specs():
    return (
        VariantSpec(key="wt", label="wild type", edits=()),
        VariantSpec(
            key="mut",
            label="mutant",
            edits=(
                SetSequence(EntityId("A"), SequenceText("MUTATED", "protein")),
                SetName("mutant job"),
            ),
        ),
        VariantSpec(key="trunc", label="truncated", edits=(RemoveRecord(EntityId("B")),)),
        VariantSpec(
            key="modsite",
            label="modified",
            edits=(AddModification(EntityId("A"), ComponentCode("P"), Position(5)),),
        ),
    )


# -- spec validation ------------------------------------------------------------


def test_spec_rejects_empty_key_and_label():
    with pytest.raises(VariantSpecError):
        VariantSpec(key="  ", label="x", edits=())
    with pytest.raises(VariantSpecError):
        VariantSpec(key="k", label="", edits=())


def test_spec_rejects_foreign_objects_as_edits():
    with pytest.raises(VariantSpecError, match="edit vocabulary"):
        VariantSpec(key="k", label="l", edits=("not an edit",))


def test_spec_is_immutable_and_value_equal():
    spec = VariantSpec(key="k", label="l", edits=(SetName("x"),))
    with pytest.raises(VariantSpecError):
        spec._key = "other"
    assert spec == VariantSpec(key="k", label="l", edits=(SetName("x"),))
    assert hash(spec) == hash(VariantSpec(key="k", label="l", edits=(SetName("x"),)))


# -- purity and determinism (plan §12.3) ---------------------------------------


def test_expand_is_deterministic_across_calls():
    first = expand(_base(), _specs())
    second = expand(_base(), _specs())
    assert [v.key for v in first] == [v.key for v in second]
    for one, two in zip(first, second):
        assert one.configuration == two.configuration


def test_expansion_never_mutates_the_base():
    base = _base()
    expand(base, _specs())
    assert [r.ids.primary.value for r in base.records] == ["A", "B"]
    assert base.metadata.name == "base job"
    assert base.records[0].sequence.text == "PEPTIDE"


def test_variant_order_and_labels_follow_spec_order():
    variants = expand(_base(), _specs())
    assert [(v.key, v.label) for v in variants] == [
        ("wt", "wild type"),
        ("mut", "mutant"),
        ("trunc", "truncated"),
        ("modsite", "modified"),
    ]


def test_empty_edits_produce_an_equal_configuration():
    base = _base()
    variants = expand(base, (VariantSpec(key="wt", label="wt", edits=()),),)
    assert variants[0].configuration == base


# -- declared changes (drift attribution data, plan §12.5) ----------------------


def test_declared_changes_are_derived_from_the_edits():
    specs = _specs()
    assert declared_changes(specs[0]) == ()
    mut = dict(declared_changes(specs[1]))
    assert set(mut) == {"sequence", "job_name"}
    assert mut["sequence"] == "A"
    trunc = dict(declared_changes(specs[2]))
    assert trunc == {"records": "B"}
    assert set(dict(declared_changes(specs[3]))) == {"modifications"}


def test_declared_changes_deduplicate_by_factor_and_key():
    spec = VariantSpec(
        key="two-site",
        label="two",
        edits=(
            AddModification(EntityId("A"), ComponentCode("P"), Position(2)),
            AddModification(EntityId("A"), ComponentCode("Q"), Position(7)),
        ),
    )
    assert declared_changes(spec) == (("modifications", "A"),)


def test_every_edit_class_has_a_declared_factor():
    from configbuilder.variants.spec import _FACTOR_BY_EDIT
    from configbuilder.variants.edits import EDIT_CLASSES

    missing = [cls.__name__ for cls in EDIT_CLASSES if cls not in _FACTOR_BY_EDIT]
    assert not missing, missing


# -- per-variant registries (isolation of identifiers, plan §12.4) ---------------


def test_each_variant_gets_its_own_registry():
    variants = expand(_base(), _specs())
    mut = next(v for v in variants if v.key == "mut")
    trunc = next(v for v in variants if v.key == "trunc")
    assert mut.configuration.identity is not trunc.configuration.identity
    assert trunc.configuration.identity.is_taken("B") is False
    assert next(v for v in variants if v.key == "wt").configuration.identity.is_taken("B") is True


def test_lineage_carries_provenance_for_the_manifest():
    variants = expand(_base(), _specs(), base_fingerprint="abc123")
    mut = next(v for v in variants if v.key == "mut")
    assert mut.lineage.base_fingerprint == "abc123"
    assert mut.lineage.applied_edits == (
        SetSequence(EntityId("A"), SequenceText("MUTATED", "protein")),
        SetName("mutant job"),
    )
    assert mut.lineage.declared_factors == ()


def test_duplicate_variant_keys_are_rejected():
    with pytest.raises(VariantSpecError, match="duplicate"):
        expand(
            _base(),
            (
                VariantSpec(key="same", label="a", edits=()),
                VariantSpec(key="same", label="b", edits=()),
            ),
        )


def test_edit_failure_names_the_variant():
    with pytest.raises(Exception, match="boom"):
        expand(
            _base(),
            (
                VariantSpec(
                    key="boom",
                    label="b",
                    edits=(SetSequence(EntityId("Z"), SequenceText("X", "protein")),),
                ),
            ),
        )


def test_description_edit_declares_chain_description_factor():
    spec = VariantSpec(
        key="d",
        label="d",
        edits=(SetDescription(EntityId("A"), Present("new")),),
    )
    assert dict(declared_changes(spec)) == {"chain_description": "A"}
