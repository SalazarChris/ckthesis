"""Unit tests for the EntityId value type (plan §6.2, §7.2; spec §7.1)."""

from __future__ import annotations

import pytest

from configbuilder.identity import EntityId


def test_accepts_single_uppercase_letter():
    assert EntityId("A").value == "A"


def test_accepts_multi_character_identifiers():
    assert EntityId("AA").value == "AA"


@pytest.mark.parametrize("value", ["a", "A1", "A-", "", "AB1", "\u00e4", "A B"])
def test_rejects_non_uppercase_alphabetic(value):
    with pytest.raises(ValueError):
        EntityId(value)


def test_rejects_non_string():
    with pytest.raises(TypeError):
        EntityId(1)


def test_equality_and_hash_are_by_value():
    assert EntityId("A") == EntityId("A")
    assert hash(EntityId("A")) == hash(EntityId("A"))
    assert EntityId("A") != EntityId("B")
    assert len({EntityId("A"), EntityId("A"), EntityId("B")}) == 2


def test_str_returns_value():
    assert str(EntityId("Q")) == "Q"


def test_repr_round_trip_form():
    assert repr(EntityId("Q")) == "EntityId('Q')"
