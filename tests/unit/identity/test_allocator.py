"""Unit tests for IdAllocator (plan §6.2 tests; §8.1)."""

from __future__ import annotations

import pytest

from configbuilder.identity import IdAllocator, IdentityError

# The progression's shape is an implementation detail (plan §8.1): no test
# outside identity asserts specific identifier values, but the allocator's
# own tests may pin the documented behaviour: monotonic, skips taken,
# continues past the single-character range.


def test_first_value_is_the_first_progression_element():
    allocator = IdAllocator()
    assert allocator.next(frozenset()) == "A"


def test_skips_assigned_values():
    allocator = IdAllocator()
    assert allocator.next(frozenset({"A", "B"})) == "C"


def test_progresses_past_single_character_range():
    """Spec §7.6: no 26-identifier ceiling."""
    allocator = IdAllocator()
    full_single = frozenset(chr(ord("A") + i) for i in range(26))
    beyond = allocator.next(full_single)
    assert len(beyond) == 2


def test_is_a_pure_function_of_the_assigned_set():
    allocator = IdAllocator()
    assigned = frozenset({"A", "C"})
    assert allocator.next(assigned) == allocator.next(assigned)


def test_arbitrary_taken_sets_yield_unused_candidate():
    allocator = IdAllocator()
    taken = frozenset({"A", "B", "AA", "AB"})
    value = allocator.next(taken)
    assert value not in taken


def test_exhaustion_raises_rather_than_ambiguous_reuse():
    allocator = IdAllocator()
    everything = frozenset(
        [chr(ord("A") + i) for i in range(26)]
        + [a + b for a in (chr(ord("A") + i) for i in range(26)) for b in (chr(ord("A") + j) for j in range(26))]
    )
    with pytest.raises(IdentityError):
        allocator.next(everything)
