"""Property tests: uniqueness under arbitrary operation sequences.

CHECKLIST Phase 2: "property test (uniqueness under arbitrary add/remove/
rename sequences)" — plan §6.2 tests, §8 guarantees. hypothesis is optional
(plan §4: development-only); a seeded random fallback keeps the guarantee
verified when it is absent.
"""

from __future__ import annotations

import random
import string as string_module

import pytest

from configbuilder.identity import (
    DuplicateIdError,
    EntityId,
    IdentityRegistry,
)

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAVE_HYPOTHESIS = True
except ImportError:  # pragma: no cover - exercised only without hypothesis
    HAVE_HYPOTHESIS = False


def _random_ops(rng, count):
    ops = []
    for _ in range(count):
        kind = rng.choice(["allocate", "assign", "rename", "release"])
        if kind == "assign":
            value = "".join(rng.choice(string_module.ascii_uppercase) for _ in range(rng.randint(1, 2)))
            ops.append(("assign", value))
        elif kind == "rename":
            ops.append(("rename", rng.random()))
        else:
            ops.append((kind, rng.random()))
    return ops


def _apply_ops(registry, ops, rng):
    """Apply an operation script, tolerating expected refusals."""
    for op in ops:
        try:
            if op[0] == "allocate":
                registry.allocate()
            elif op[0] == "assign":
                registry.assign(op[1])
            elif op[0] == "rename":
                assigned = registry.order()
                if not assigned:
                    continue
                old = assigned[int(op[1] * len(assigned)) % len(assigned)]
                target = "".join(
                    rng.choice(string_module.ascii_uppercase) for _ in range(2)
                )
                try:
                    registry.rename(old, target)
                except DuplicateIdError:
                    pass
            elif op[0] == "release":
                assigned = registry.order()
                if assigned:
                    registry.release(assigned[int(op[1] * len(assigned)) % len(assigned)])
        except DuplicateIdError:
            pass


def _assert_unique_and_valid(registry):
    order = registry.order()
    values = [entity.value for entity in order]
    assert len(values) == len(set(values)), "duplicate identifiers in registry"
    for value in values:
        assert value.isalpha() and value.isupper(), value


def test_seeded_random_operation_sequences_keep_uniqueness():
    for seed in range(25):
        rng = random.Random(seed)
        registry = IdentityRegistry()
        _apply_ops(registry, _random_ops(rng, 60), rng)
        _assert_unique_and_valid(registry)


if HAVE_HYPOTHESIS:

    @settings(max_examples=50, deadline=None)
    @given(st.integers(min_value=0, max_value=10_000))
    def test_hypothesis_seeded_sequences_keep_uniqueness(seed):
        rng = random.Random(seed)
        registry = IdentityRegistry()
        _apply_ops(registry, _random_ops(rng, 60), rng)
        _assert_unique_and_valid(registry)


def test_clone_isolation_under_arbitrary_allocation():
    """Plan §12.4: allocating in one variant must not affect any sibling or
    the base — checked over many random starting states.

    Two clones independently allocating from the same base state may choose
    the same next identifier: that is determinism (plan §8.1), not a leak.
    Isolation means no clone's *state* changes because another clone acted.
    """
    for seed in range(25):
        rng = random.Random(seed)
        base = IdentityRegistry()
        _apply_ops(base, _random_ops(rng, 20), rng)
        baseline_order = base.order()
        baseline_values = base.assigned_values()

        sibling_a = base.clone()
        sibling_b = base.clone()
        before_b = (sibling_b.order(), sibling_b.assigned_values())

        # Act on sibling A only.
        for _ in range(3):
            sibling_a.allocate()
        assigned = sibling_a.order()
        if assigned:
            sibling_a.release(assigned[-1])
            sibling_a.rename(assigned[0], "ZZ")

        # Base untouched...
        assert base.order() == baseline_order
        assert base.assigned_values() == baseline_values
        # ...and sibling B byte-for-byte unchanged by A's activity.
        assert (sibling_b.order(), sibling_b.assigned_values()) == before_b
        # Determinism restated at the clone boundary: a fresh clone of the
        # same base makes exactly the choices A made (plan §8.1).
        expected = []
        probe = base.clone()
        for _ in range(3):
            expected.append(probe.allocate().value)
        sibling_d = base.clone()
        assert [sibling_d.allocate().value for _ in range(3)] == expected
