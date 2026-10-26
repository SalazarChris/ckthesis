"""Naming tests (IMPLEMENTATION_PLAN.md §13.2, spec §9.6).

The slug is a single pure function: same input, same output — no clock,
no randomness, no locale. These tests pin the character allowlist, the
determinism, and the invariants the collision machinery relies on.
"""

from __future__ import annotations

import pytest

from configbuilder.output.naming import (
    MAX_SLUG_LENGTH,
    NameError,
    casefold_conflicts,
    slug,
    variant_directory_name,
    variant_file_name,
)


# -- character policy -----------------------------------------------------------


def test_lowercases_and_uses_dash_separator():
    assert slug("My Project: ADK!") == "my-project-adk"


def test_avoids_underscores_in_component_style_names():
    # spec §9.6 documents underscores as problematic; the separator is '-'.
    assert slug("snake_case_name") == "snake-case-name"
    assert "_" not in slug("every _ kind _ of input")


def test_collapses_and_strips_separators():
    assert slug("  a   ---  b  ") == "a-b"
    assert slug("--head--tail--") == "head-tail"


def test_keeps_ascii_letters_digits_and_dashes_only():
    assert slug("Alpha-12_beta/ω") == "alpha-12-beta"


@pytest.mark.parametrize("bad", ["", "   ", "///", "___", "###"])
def test_rejects_input_that_cleans_to_nothing(bad):
    with pytest.raises(NameError):
        slug(bad)


def test_length_cap_is_deterministic():
    long = "a" * 200
    first = slug(long)
    assert first == slug(long)
    assert len(first) <= MAX_SLUG_LENGTH


def test_length_cap_keeps_the_head_and_drops_a_trailing_separator():
    text = "alpha-" + "b" * 100
    result = slug(text)
    assert len(result) <= MAX_SLUG_LENGTH
    assert result == ("alpha-" + "b" * (MAX_SLUG_LENGTH - len("alpha-")))
    # Truncation-induced collisions are the *planner's* business (deterministic
    # numeric suffix, plan §13.2) — the slug itself stays deterministic. Two
    # different texts really can truncate to the same slug:
    assert slug("alpha-" + "b" * 100) == slug("alpha-" + "b" * 200)
    assert len("alpha-" + "b" * (MAX_SLUG_LENGTH - len("alpha-"))) == MAX_SLUG_LENGTH


# -- derived names --------------------------------------------------------------


def test_variant_directory_and_file_names_agree():
    directory = variant_directory_name("Thesis Project", "Wild Type")
    assert directory == "thesis-project__wild-type"
    assert variant_file_name("Thesis Project", "Wild Type") == directory + ".json"


def test_directory_name_has_exactly_one_double_underscore():
    # The __ separates project from variant; component parts use '-'.
    name = variant_directory_name("Some Long Project Name", "Variant KEY With CASE")
    parts = name.split("__")
    assert len(parts) == 2
    assert parts[0] == slug("Some Long Project Name")
    assert parts[1] == slug("Variant KEY With CASE")


# -- case folding (plan §13.2) ----------------------------------------------------


def test_casefold_conflicts_detects_case_differing_names():
    folded = casefold_conflicts(("Var", "var", "other"))
    assert folded == {"var": ("Var", "var")}


def test_casefold_conflicts_ignores_distinct_names():
    assert casefold_conflicts(("a", "b", "c")) == {}


# -- purity ------------------------------------------------------------------------


def test_slug_is_pure_across_calls():
    samples = ["Peptide Study", "MSA/Complex (v2)", "ligand ATP binding"]
    for sample in samples:
        assert slug(sample) == slug(sample)
