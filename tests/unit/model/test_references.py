"""Unit tests for structural references (plan §7.3, §7.4; spec §12, MAP-705)."""

from __future__ import annotations

import pytest

from configbuilder.model import (
    Explicit,
    External,
    IndexPair,
    Inline,
    PathSpec,
    ReferenceError,
    ReferenceRecord,
    SearchAllowed,
    fold_reference_set,
)


class TestReferenceRecord:
    def test_source_round_trip(self):
        record = ReferenceRecord(source=External(PathSpec("template.cif")), index_map=())
        assert record.source.path.raw == "template.cif"

    def test_inline_source(self):
        record = ReferenceRecord(source=Inline("mmCIF text"), index_map=())
        assert record.source.text == "mmCIF text"

    def test_index_map_stores_pairs_not_parallel_arrays(self):
        record = ReferenceRecord(
            source=Inline("t"),
            index_map=(IndexPair(0, 0), IndexPair(1, 2), IndexPair(2, 5)),
        )
        assert [(p.query, p.template) for p in record.index_map] == [(0, 0), (1, 2), (2, 5)]

    def test_rejects_non_resource_source(self):
        with pytest.raises(ReferenceError):
            ReferenceRecord(source="template.cif", index_map=())  # type: ignore[arg-type]

    def test_rejects_non_pair_entries(self):
        with pytest.raises(ReferenceError):
            ReferenceRecord(source=Inline("t"), index_map=((0, 0),))  # type: ignore[arg-type]

    def test_is_immutable(self):
        record = ReferenceRecord(source=Inline("t"), index_map=())
        with pytest.raises(ReferenceError):
            record.source = External(PathSpec("other"))  # type: ignore[misc]

    def test_equality_and_hash(self):
        one = ReferenceRecord(source=Inline("t"), index_map=(IndexPair(0, 1),))
        two = ReferenceRecord(source=Inline("t"), index_map=(IndexPair(0, 1),))
        assert one == two
        assert hash(one) == hash(two)


class TestReferenceSet:
    def test_search_allowed_is_the_omitted_state(self):
        """MAP-705: omitted field means template search allowed."""
        assert SearchAllowed() is SearchAllowed()

    def test_explicit_empty_means_template_free(self):
        """Explicitly empty is distinct from omitted (spec §6.2)."""
        explicit = Explicit(())
        assert explicit.items == ()
        assert explicit != SearchAllowed()

    def test_explicit_holds_records_in_order(self):
        records = (
            ReferenceRecord(source=Inline("a"), index_map=()),
            ReferenceRecord(source=Inline("b"), index_map=()),
        )
        assert Explicit(records).items == records

    def test_explicit_rejects_foreign_items(self):
        with pytest.raises(ReferenceError):
            Explicit(("not-a-record",))  # type: ignore[arg-type]

    def test_cases_are_immutable(self):
        with pytest.raises(ReferenceError):
            Explicit(()).items = ()  # type: ignore[misc]


class TestFoldReferenceSet:
    def test_dispatches_both_cases(self):
        assert (
            fold_reference_set(SearchAllowed(), lambda: "search", lambda items: "explicit")
            == "search"
        )
        record = ReferenceRecord(source=Inline("t"), index_map=())
        assert (
            fold_reference_set(
                Explicit((record,)), lambda: "search", lambda items: ("explicit", items)
            )
            == ("explicit", (record,))
        )

    def test_raises_on_unknown_value(self):
        with pytest.raises(ReferenceError):
            fold_reference_set(None, lambda: 1, lambda items: 2)  # type: ignore[arg-type]

    def test_omitted_vs_empty_distinction_survives_the_fold(self):
        out = fold_reference_set(
            Explicit(()), lambda: "omitted", lambda items: "present-empty"
        )
        assert out == "present-empty"
