"""Unit tests for IdentityRegistry (plan §6.2 tests; §8)."""

from __future__ import annotations

import pytest

from configbuilder.identity import (
    DuplicateIdError,
    EntityId,
    IdentityError,
    IdentityRegistry,
    Multiplicity,
)


def test_allocate_returns_deterministic_sequence():
    """Plan §8.1: the same sequence of allocation requests against the same
    starting state always yields the same identifiers."""
    first = IdentityRegistry().allocate().value
    fresh = IdentityRegistry()
    assert [fresh.allocate().value, fresh.allocate().value][0] == first


def test_allocate_skips_user_assigned_identifiers():
    registry = IdentityRegistry()
    registry.assign("A", owner="kept")
    assert registry.allocate().value != "A"


def test_assign_taken_identifier_is_refused_not_renamed():
    registry = IdentityRegistry()
    registry.assign("B")
    with pytest.raises(DuplicateIdError):
        registry.assign("B")


def test_allocate_never_collides_with_copy_multiplicity():
    """Plan §8.2: every identifier of a multiplicity is reserved."""
    registry = IdentityRegistry()
    registry.reserve_multiplicity(Multiplicity(["A", "B", "C"]), owner="chain")
    allocated = registry.allocate()
    assert not any(allocated == EntityId(v) for v in ("A", "B", "C"))


def test_uniqueness_holds_across_records_and_copies():
    registry = IdentityRegistry()
    values = [registry.allocate().value for _ in range(30)]
    assert len(values) == len(set(values))


def test_resolve():
    registry = IdentityRegistry()
    entity_id = registry.assign("D")
    assert registry.resolve(entity_id)
    assert not registry.resolve(EntityId("E"))
    assert registry.resolve_strict(entity_id) == entity_id


def test_resolve_strict_raises_on_unknown():
    registry = IdentityRegistry()
    with pytest.raises(IdentityError):
        registry.resolve_strict(EntityId("Z"))


def test_rename_returns_rewrite_map():
    registry = IdentityRegistry()
    old = registry.assign("F", owner="rec")
    rename_map = registry.rename(old, "G")
    assert rename_map.rewrite(EntityId("F")) == EntityId("G")
    assert rename_map.rewrite(EntityId("H")) == EntityId("H")
    assert registry.resolve(EntityId("G"))
    assert not registry.resolve(EntityId("F"))
    assert registry.owner_of(EntityId("G")) == "rec"


def test_rename_to_same_value_is_a_noop_map():
    registry = IdentityRegistry()
    entity_id = registry.assign("F")
    assert len(registry.rename(entity_id, "F")) == 0


def test_rename_to_taken_identifier_refused():
    registry = IdentityRegistry()
    first = registry.assign("F")
    registry.assign("G")
    with pytest.raises(DuplicateIdError):
        registry.rename(first, "G")


def test_rename_of_unassigned_refused():
    registry = IdentityRegistry()
    with pytest.raises(IdentityError):
        registry.rename(EntityId("F"), "G")


def test_release_frees_the_reservation():
    registry = IdentityRegistry()
    entity_id = registry.assign("F")
    registry.release(entity_id)
    assert not registry.resolve(entity_id)
    with pytest.raises(IdentityError):
        registry.release(entity_id)


def test_released_identifier_is_not_reused_within_the_run():
    """Plan §8.3: released identifiers are not reused in the same expansion run."""
    registry = IdentityRegistry()
    first = registry.assign("A")
    registry.release(first)
    assert registry.allocate().value != "A"


def test_clone_preserves_identifiers_and_is_independent():
    """Plan §8.3 / §12.4: copies preserved; allocation in a clone must not
    affect the base or siblings."""
    base = IdentityRegistry()
    base.assign("A")
    base.assign("C")
    clone = base.clone()
    assert clone.order() == base.order()
    clone.allocate()
    clone.assign("M")
    assert base.assigned_values() == frozenset({"A", "C"})
    assert base.order() == (EntityId("A"), EntityId("C"))


def test_snapshot_is_immutable_view():
    registry = IdentityRegistry()
    registry.assign("A")
    snapshot = registry.snapshot()
    registry.assign("B")
    assert snapshot.values() == frozenset({"A"})
    assert registry.snapshot().values() == frozenset({"A", "B"})


def test_order_and_assignments_are_consistent():
    registry = IdentityRegistry()
    a = registry.assign("A", owner="one")
    b = registry.allocate(owner="two")
    assert registry.order() == (a, b)
    assignments = registry.assignments()
    assert [assignment.owner for assignment in assignments] == ["one", "two"]


def test_construction_from_records_preserves_order():
    records = [
        (Multiplicity(["B", "C"]), "first"),
        (Multiplicity(["A"]), "second"),
    ]
    registry = IdentityRegistry(records=records)
    assert registry.order() == (EntityId("B"), EntityId("C"), EntityId("A"))
    assert registry.owner_of(EntityId("C")) == "first"


def test_duplicate_in_construction_records_refused():
    records = [(Multiplicity(["A"]), "one"), (Multiplicity(["A"]), "two")]
    with pytest.raises(DuplicateIdError):
        IdentityRegistry(records=records)
