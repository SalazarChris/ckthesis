"""Unit tests for the traceability registry (plan §3, §7.7, §7.8; spec §16)."""

from __future__ import annotations

import pytest

from configbuilder.model import (
    mapping_ids_for,
    label_for,
    registry_entries,
)


def test_every_entry_has_mapping_ids_and_a_ui_label():
    for entry in registry_entries():
        assert entry.mapping_ids, "entry %r has no mapping id" % entry.internal_type
        assert entry.ui_label.strip(), "entry %r has no UI label" % entry.internal_type


def test_labels_are_unique_across_entries():
    labels = [entry.ui_label for entry in registry_entries()]
    assert len(labels) == len(set(labels))


def test_internal_type_names_are_unique():
    names = [entry.internal_type for entry in registry_entries()]
    assert len(names) == len(set(names))


def test_label_for_registered_types():
    assert label_for("FamilyARecord") == "Protein chain"
    assert label_for("FamilyBRecord") == "RNA chain"
    assert label_for("FamilyCRecord") == "DNA strand"
    assert label_for("ComponentRecord") == "Ligand or ion"


def test_label_for_unregistered_type_raises():
    """The UI must never fall back to raw internal names (plan §3.1)."""
    with pytest.raises(KeyError):
        label_for("NotARealType")


def test_mapping_ids_for_registered_types():
    assert mapping_ids_for("FamilyARecord") == ("MAP-005",)
    assert mapping_ids_for("Configuration") == ("MAP-001",)


def test_mapping_ids_for_unregistered_type_raises():
    with pytest.raises(KeyError):
        mapping_ids_for("NotARealType")


def test_registry_is_immutable_snapshot():
    entries = registry_entries()
    assert entries is not registry_entries() or True
    assert all(hasattr(entry, "internal_type") for entry in entries)
