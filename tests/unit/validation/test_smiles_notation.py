"""SMILES notation grammar: what is claimed, and what is deliberately not.

The claim under test is narrow and stated in ``validation/smiles.py``: notation
that cannot be SMILES is refused (a component code, a protein sequence, a
sentence, an unbalanced ring), and everything the check cannot rule out is
accepted — no valence, no aromaticity, no element vocabulary. The positive
battery is therefore as important as the negative one: a false refusal would
block a user from writing a job.
"""

from __future__ import annotations

import pytest

from configbuilder.validation import BundledChemistryProbe, NullChemistryProbe
from configbuilder.validation.smiles import notation_problem, parses

# Notation a SMILES parser accepts. The check must never refuse any of it.
VALID = (
    "CCO",
    "CC(=O)O",
    "CC(=O)Oc1ccccc1C(=O)O",  # aspirin, AF3's own documentation example shape
    "OC(=O)CCCC[C@@H]1SC[C@@H]2NC(=O)N[C@H]12",  # biotin, from AF3's examples
    "C1CCCCC1",
    "c1ccccc1",
    "c1ccncc1",
    "c1ccc2ccccc2c1",
    "C1=CC=CC=C1",
    "C[C@H](N)C(=O)O",
    "N[C@H](C)",
    "N#N",
    "O=C=O",
    "C#C",
    "C/C=C/C",
    "C=C/C=C\\C",
    "[Na+].[Cl-]",
    "[Zn+2]",
    "[Cu+2]",
    "[Mg+2]",
    "[Fe]",
    "[Se]",
    "[SiH4]",
    "[13CH4]",
    "[2H]",
    "[C]",
    "[NH4+]",
    "[nH]1cccc1",
    "[O-]S(=O)(=O)[O-]",
    "[C@@H]1CCCC1",
    "[H]C([H])([H])[H]",
    "B(O)O",
    "O=S(=O)(O)O",
    "P(=O)(O)(O)O",
    "FC(F)(F)F",
    "ClC(Cl)Cl",
    "BrCCBr",
    "IC",
    "*",
    "C%10CCCCCC%10",
    "CC%11CCCCC%11",
    "C1CC2CCC1C2",
    "c1ccccc1-c1ccccc1",
    "CCCCCCCCCCCCCCCC(=O)O",
    # Grammar-valid and chemistry-invalid: accepted, deliberately (see the
    # rule's scope; valence is the external parser's business).
    "C(C)(C)(C)(C)C",
)

# Text that is not SMILES notation, with the reason the check gives.
INVALID = {
    "": "it is empty",
    "   ": "it is empty",
    " ATP": "it has leading or trailing whitespace",
    "ATP ": "it has leading or trailing whitespace",
    "C C": "it contains ' ', which is not a SMILES character",
    "this is not a smiles": "it contains ' ', which is not a SMILES character",
    "C,C": "it contains ',', which is not a SMILES character",
    "C~C": "it contains '~', which is not a SMILES character",
    "ATP": "the atom 'A' in 'ATP' is not one SMILES writes without brackets",
    "ZN": "the atom 'Z' in 'ZN' is not one SMILES writes without brackets",
    "ethanol": "is not one SMILES writes without brackets",
    "MKTAYIAK": "is not one SMILES writes without brackets",
    "MVTPEPTIDE": "is not one SMILES writes without brackets",
    "C1CC": "ring-closure number 1 is opened but never closed",
    "c1ccccc": "ring-closure number 1 is opened but never closed",
    "C1=CC=CC=C": "ring-closure number 1 is opened but never closed",
    "cc1": "ring-closure number 1 is opened but never closed",
    "1CC1": "it starts with a ring-closure number, which needs an atom first",
    "C%1": "'%' must be followed by exactly two digits",
    "C%ab": "'%' must be followed by exactly two digits",
    # Three digits: one two-digit closure, then a stray one of its own.
    "C%123": "ring-closure number 12 is opened but never closed",
    "C(=O": "a parenthesis is never closed",
    "C1CC)C1": "a parenthesis is closed without being opened",
    "[Zn+2": "a bracket is never closed",
    "Zn]": "a bracket is closed without being opened",
    "[]": "a bracket contains no atom",
    "=C": "it starts with a bond symbol, which needs an atom first",
    "CC=": "it ends with a bond symbol, with no atom for it to bond to",
}


@pytest.mark.parametrize("notation", VALID)
def test_valid_notation_is_never_refused(notation):
    assert notation_problem(notation) is None, notation_problem(notation)
    assert parses(notation)


@pytest.mark.parametrize("notation", sorted(INVALID))
def test_invalid_notation_is_refused_with_its_reason(notation):
    problem = notation_problem(notation)

    assert problem is not None
    assert INVALID[notation] in problem


def test_a_non_string_is_refused_rather_than_raising():
    assert notation_problem(None) is not None


# -- the probe the application wires -------------------------------------------


def test_the_bundled_probe_answers_the_grammar_question():
    probe = BundledChemistryProbe()

    assert probe.parses_smiles("CC(=O)O")
    assert not probe.parses_smiles("ATP")
    assert "not one SMILES writes without brackets" in probe.smiles_problem("ATP")
    assert probe.smiles_problem("CC(=O)O") is None


def test_the_null_probe_still_says_it_checked_nothing():
    """§9.6: a caller with no checker must not look like a passing check."""
    assert NullChemistryProbe().parses_smiles("CC(=O)O") is False


def test_the_application_wires_the_bundled_probe():
    from configbuilder.ui.services import build_services

    assert isinstance(build_services().validation._chemistry, BundledChemistryProbe)
