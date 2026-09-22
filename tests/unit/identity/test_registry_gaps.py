"""Gap tests for identity/ API completeness (plan §8.2, §8.3; §12.1; §21 Phase 9).

These cover the registry operations the canonical model's later phases
need: group queries and atomic group release for variant edits resolved
through identity (never list position), and registry serialization so
persistence can guarantee reopening never reassigns identifiers.
"""

from __future__ import annotations

import json

import pytest

from configbuilder.identity import (
    EntityId,
    IdentityError,
    IdentityRegistry,
    Multiplicity,
)


def _registry_with_group() -> IdentityRegistry:
    registry = IdentityRegistry()
    registry.reserve_multiplicity(Multiplicity(["A", "B", "C"]), owner="chain")
    registry.allocate(owner="solo")
    return registry


class TestMultiplicityQueries:
    def test_multiplicity_of_returns_reserved_group(self):
        registry = _registry_with_group()
        assert registry.multiplicity_of(EntityId("A")) == Multiplicity(["A", "B", "C"])

    def test_multiplicity_of_single_reserve_is_itself(self):
        registry = IdentityRegistry()
        entity_id = registry.assign("D", owner="solo")
        assert registry.multiplicity_of(entity_id) == Multiplicity(["D"])

    def test_multiplicity_of_unknown_identifier_raises(self):
        registry = _registry_with_group()
        with pytest.raises(IdentityError):
            registry.multiplicity_of(EntityId("Z"))

    def test_membership_survives_rename(self):
        registry = _registry_with_group()
        registry.rename(EntityId("B"), "M")
        assert registry.multiplicity_of(EntityId("M")) == Multiplicity(["A", "M", "C"])
        assert registry.multiplicity_of(EntityId("A")) == Multiplicity(["A", "M", "C"])

    def test_membership_survives_clone(self):
        registry = _registry_with_group()
        assert registry.clone().multiplicity_of(EntityId("C")) == Multiplicity(["A", "B", "C"])


class TestReleaseMultiplicity:
    def test_releases_every_member_of_the_group(self):
        registry = _registry_with_group()
        registry.release_multiplicity(Multiplicity(["A", "B", "C"]))
        assert not registry.resolve(EntityId("A"))
        assert not registry.resolve(EntityId("C"))
        assert registry.resolve(EntityId("D"))  # the solo record remains

    def test_release_is_atomic_on_missing_member(self):
        """A partially-released group cannot happen by accident."""
        registry = _registry_with_group()
        registry.release(EntityId("B"))
        with pytest.raises(IdentityError):
            registry.release_multiplicity(Multiplicity(["A", "B", "C"]))
        # Atomic: A and C are untouched.
        assert registry.resolve(EntityId("A"))
        assert registry.resolve(EntityId("C"))

    def test_missing_ok_releases_only_present_members(self):
        registry = _registry_with_group()
        registry.release(EntityId("B"))
        registry.release_multiplicity(Multiplicity(["A", "B", "C"]), missing_ok=True)
        assert not registry.resolve(EntityId("A"))
        assert not registry.resolve(EntityId("C"))

    def test_released_group_members_are_not_reallocated(self):
        registry = _registry_with_group()
        registry.release_multiplicity(Multiplicity(["A", "B", "C"]))
        # A, B, C retired; D (the solo) assigned; next is E.
        assert registry.allocate().value == "E"

    def test_release_of_single_identifier_unchanged(self):
        registry = _registry_with_group()
        registry.release(EntityId("D"))
        assert registry.assigned_values() == frozenset({"A", "B", "C"})


class TestRegistrySerialization:
    """Plan Phase 9: registry persisted — reopening never reassigns."""

    def test_to_data_is_json_safe(self):
        data = _registry_with_group().to_data()
        assert json.loads(json.dumps(data)) == data

    def test_round_trip_preserves_order_and_owners(self):
        registry = _registry_with_group()
        restored = IdentityRegistry.from_data(registry.to_data())
        assert restored.order() == registry.order()
        assert [a.owner for a in restored.assignments()] == [
            a.owner for a in registry.assignments()
        ]

    def test_round_trip_keeps_allocation_position(self):
        """The next allocation continues after the highest ever-assigned
        value — never restarting from A (reopening never reassigns)."""
        registry = _registry_with_group()
        restored = IdentityRegistry.from_data(registry.to_data())
        assert restored.allocate().value == "E"
        assert restored.assigned_values() == frozenset({"A", "B", "C", "D", "E"})

    def test_released_identifiers_stay_retired_after_round_trip(self):
        registry = _registry_with_group()
        registry.release(EntityId("A"))
        restored = IdentityRegistry.from_data(registry.to_data())
        assert not restored.resolve(EntityId("A"))
        assert restored.allocate().value == "E"  # A is retired, not reused

    def test_restored_registry_is_independent(self):
        registry = _registry_with_group()
        restored = IdentityRegistry.from_data(registry.to_data())
        restored.allocate()
        assert registry.assigned_values() == frozenset({"A", "B", "C", "D"})

    def test_invalid_payload_is_refused_not_repaired(self):
        with pytest.raises(IdentityError):
            IdentityRegistry.from_data("not an object")  # type: ignore[arg-type]
        with pytest.raises(IdentityError):
            IdentityRegistry.from_data({"order": ["A", 1], "owners": {}})
        with pytest.raises(IdentityError):
            IdentityRegistry.from_data({"order": ["A"], "owners": []})
        with pytest.raises(IdentityError):
            IdentityRegistry.from_data({"order": ["A"], "owners": {"A": None}, "ever_assigned": ["B"]})
        with pytest.raises(IdentityError):
            IdentityRegistry.from_data({"order": ["A"], "owners": {"A": 3}})

    def test_legacy_payload_without_ever_assigned_falls_back_to_order(self):
        data = {"order": ["A", "B"], "owners": {"A": "x", "B": None}}
        restored = IdentityRegistry.from_data(data)
        assert restored.allocate().value == "C"

    def test_null_owner_survives_round_trip(self):
        registry = IdentityRegistry()
        registry.assign("A")
        registry.allocate(owner="named")
        restored = IdentityRegistry.from_data(registry.to_data())
        assert restored.owner_of(EntityId("A")) is None
        assert restored.owner_of(EntityId("B")) == "named"

    def test_from_data_refuses_duplicate_identifiers(self):
        with pytest.raises(Exception):
            IdentityRegistry.from_data(
                {"order": ["A", "A"], "owners": {"A": None}, "ever_assigned": ["A"]}
            )

    def test_clone_now_rides_the_serialization_path(self):
        registry = _registry_with_group()
        clone = registry.clone()
        assert clone.order() == registry.order()
        assert clone.assigned_values() == registry.assigned_values()
        clone.allocate()
        assert registry.assigned_values() == frozenset({"A", "B", "C", "D"})
