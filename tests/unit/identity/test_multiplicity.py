"""Unit tests for Multiplicity (plan §6.2, §8.2; spec §7.1)."""

from __future__ import annotations

import pytest

from configbuilder.identity import EntityId, Multiplicity


def test_single_identifier_form():
    multiplicity = Multiplicity(["A"])
    assert multiplicity.count == 1
    assert multiplicity.primary == EntityId("A")


def test_copy_form_preserves_order():
    multiplicity = Multiplicity(["B", "A"])
    assert [e.value for e in multiplicity.ids] == ["B", "A"]
    assert multiplicity.primary == EntityId("B")


def test_accepts_entity_id_instances():
    assert Multiplicity([EntityId("A"), EntityId("C")]).count == 2


def test_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicate"):
        Multiplicity(["A", "A"])


def test_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        Multiplicity([])


def test_rejects_invalid_identifier():
    with pytest.raises(ValueError):
        Multiplicity(["A", "a1"])


def test_contains():
    multiplicity = Multiplicity(["A", "B"])
    assert multiplicity.contains(EntityId("A"))
    assert not multiplicity.contains(EntityId("C"))


def test_equality_and_hash_by_ordered_ids():
    assert Multiplicity(["A", "B"]) == Multiplicity(["A", "B"])
    assert Multiplicity(["A", "B"]) != Multiplicity(["B", "A"])
    assert hash(Multiplicity(["A", "B"])) == hash(Multiplicity(["A", "B"]))


def test_len_and_iter():
    multiplicity = Multiplicity(["A", "B", "C"])
    assert len(multiplicity) == 3
    assert [e.value for e in multiplicity] == ["A", "B", "C"]
