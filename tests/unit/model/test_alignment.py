"""Unit tests for alignment sum types (plan §7.3; spec §11, MAP-601..606)."""

from __future__ import annotations

import pytest

from configbuilder.model import (
    AlignmentAutomatic,
    AlignmentBoth,
    AlignmentError,
    AlignmentFree,
    AlignmentPairedOnly,
    AlignmentUnpairedOnly,
    External,
    Inline,
    PathSpec,
    SingleAutomatic,
    SingleFree,
    SingleProvided,
    fold_alignment,
    fold_single_alignment,
)


class TestAlignmentPairingCases:
    def test_automatic_is_a_distinct_case(self):
        assert isinstance(AlignmentAutomatic(), AlignmentAutomatic)

    def test_free_is_a_distinct_case(self):
        assert AlignmentFree() == AlignmentFree()

    def test_one_sided_cases_hold_exactly_one_source(self):
        unpaired = AlignmentUnpairedOnly(source=Inline("unpaired"))
        paired = AlignmentPairedOnly(source=External(PathSpec("paired.a3m")))
        both = AlignmentBoth(source=Inline("shared"))
        assert unpaired.source.text == "unpaired"
        assert paired.source.path.raw == "paired.a3m"
        assert both.source.text == "shared"

    def test_one_sided_cases_reject_non_resource_source(self):
        for case in (AlignmentUnpairedOnly, AlignmentPairedOnly, AlignmentBoth):
            with pytest.raises(AlignmentError):
                case(source="sequence")  # type: ignore[arg-type]

    def test_case_identity_is_part_of_equality(self):
        """Same source in different cases is never equal (MAP-601..606 are
        distinct, mutually exclusive states)."""
        assert AlignmentUnpairedOnly(Inline("s")) != AlignmentBoth(Inline("s"))
        assert AlignmentUnpairedOnly(Inline("s")) != AlignmentPairedOnly(Inline("s"))

    def test_cases_are_immutable(self):
        with pytest.raises(AlignmentError):
            AlignmentBoth(source=Inline("x")).source = Inline("y")  # type: ignore[misc]


class TestFoldAlignment:
    def test_dispatches_every_case(self):
        source = Inline("s")
        out = fold_alignment(
            AlignmentAutomatic(),
            on_automatic=lambda: "auto",
            on_free=lambda: "free",
            on_unpaired_only=lambda s: ("unpaired", s),
            on_paired_only=lambda s: ("paired", s),
            on_both=lambda s: ("both", s),
        )
        assert out == "auto"
        assert (
            fold_alignment(
                AlignmentFree(), lambda: "auto", lambda: "free", lambda s: 0, lambda s: 0, lambda s: 0
            )
            == "free"
        )
        assert (
            fold_alignment(
                AlignmentUnpairedOnly(source),
                lambda: "auto",
                lambda: "free",
                lambda s: ("unpaired", s),
                lambda s: 0,
                lambda s: 0,
            )
            == ("unpaired", source)
        )
        assert (
            fold_alignment(
                AlignmentPairedOnly(source),
                lambda: "auto",
                lambda: "free",
                lambda s: 0,
                lambda s: ("paired", s),
                lambda s: 0,
            )
            == ("paired", source)
        )
        assert (
            fold_alignment(
                AlignmentBoth(source),
                lambda: "auto",
                lambda: "free",
                lambda s: 0,
                lambda s: 0,
                lambda s: ("both", s),
            )
            == ("both", source)
        )

    def test_raises_on_unknown_value(self):
        with pytest.raises(AlignmentError):
            fold_alignment("auto", lambda: 1, lambda: 2, lambda s: 3, lambda s: 4, lambda s: 5)  # type: ignore[arg-type]


class TestSingleAlignment:
    """The RNA form (MAP-601/604/606)."""

    def test_cases(self):
        assert SingleAutomatic() == SingleAutomatic()
        assert SingleFree() == SingleFree()
        provided = SingleProvided(source=External(PathSpec("r.sto")))
        assert provided.source.path.raw == "r.sto"

    def test_provided_rejects_non_resource(self):
        with pytest.raises(AlignmentError):
            SingleProvided(source=42)  # type: ignore[arg-type]

    def test_fold_dispatches_every_case(self):
        source = Inline("q")
        assert (
            fold_single_alignment(
                SingleAutomatic(), lambda: "auto", lambda: "free", lambda s: ("provided", s)
            )
            == "auto"
        )
        assert (
            fold_single_alignment(
                SingleFree(), lambda: "auto", lambda: "free", lambda s: ("provided", s)
            )
            == "free"
        )
        assert (
            fold_single_alignment(
                SingleProvided(source), lambda: "auto", lambda: "free", lambda s: ("provided", s)
            )
            == ("provided", source)
        )

    def test_fold_raises_on_unknown_value(self):
        with pytest.raises(AlignmentError):
            fold_single_alignment(None, lambda: 1, lambda: 2, lambda s: 3)  # type: ignore[arg-type]


def test_alignment_cases_are_hashable():
    assert hash(AlignmentAutomatic()) == hash(AlignmentAutomatic())
    assert hash(AlignmentBoth(Inline("s"))) == hash(AlignmentBoth(Inline("s")))
