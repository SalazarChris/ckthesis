"""Unit tests for the presence algebra (plan §7.3; spec §6.2, §6.3)."""

from __future__ import annotations

import pytest

from configbuilder.model import (
    ExplicitEmpty,
    PresenceError,
    Present,
    Unset,
    fold_presence,
)


def test_unset_and_explicit_empty_are_distinct_singletons():
    assert Unset() is Unset()
    assert ExplicitEmpty() is ExplicitEmpty()
    assert Unset() != ExplicitEmpty()


def test_present_carries_value():
    assert Present("x").value == "x"
    assert Present("") == Present("")  # empty string content is fine; it is content


def test_present_cannot_nest_presence():
    for nested in (Unset(), ExplicitEmpty(), Present(1)):
        with pytest.raises(PresenceError):
            Present(nested)


def test_present_is_immutable():
    present = Present("x")
    with pytest.raises(PresenceError):
        present.value = "y"


def test_fold_covers_all_three_cases():
    value = fold_presence(
        Unset(),
        on_unset=lambda: "unset",
        on_empty=lambda: "empty",
        on_present=lambda v: "present:%s" % v,
    )
    assert value == "unset"
    assert (
        fold_presence(
            ExplicitEmpty(), lambda: "unset", lambda: "empty", lambda v: "p"
        )
        == "empty"
    )
    assert (
        fold_presence(Present(7), lambda: "unset", lambda: "empty", lambda v: v * 2)
        == 14
    )


def test_fold_raises_on_unknown_value():
    with pytest.raises(PresenceError):
        fold_presence(None, lambda: 1, lambda: 2, lambda v: 3)
    with pytest.raises(PresenceError):
        fold_presence("", lambda: 1, lambda: 2, lambda v: 3)


def test_states_are_never_interchangeable():
    """The heart of spec §6.3: four different states, never collapsed."""
    assert Unset() != ExplicitEmpty()
    assert Unset() != Present(None)
    assert ExplicitEmpty() != Present("")
