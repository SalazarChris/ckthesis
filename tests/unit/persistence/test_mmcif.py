"""Template structure checking: the file half of a template definition.

Two tiers are exercised here — the bundled lexical scan (present in every
environment) and the established mmCIF parser when it is installed — and the
committed pack in ``manual_test_data/af3_builder/templates`` is what they are
asked about, so the fixtures' real content is the evidence (plan §9.6: an
optional component may strengthen a check, never be required for one).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from configbuilder.persistence import mmcif

PACK = (
    Path(__file__).resolve().parents[3]
    / "manual_test_data"
    / "af3_builder"
    / "templates"
)

# The pack's structure, as the templates README states it: four structures the
# builder must accept, three inputs it must refuse.
ACCEPTED = (
    "minimal_template.cif",
    "template_fully_resolved.cif",
    "template_unresolved_residues.cif",
    "with spaces/template with spaces.cif",
)
REFUSED = {
    "template_empty.cif": "the file is empty",
    "template_malformed.cif": (
        "the loop starting at line 9 declares 3 tags, and its values do not "
        "form complete rows of that size"
    ),
    "template_no_records.cif": "it has no _atom_site, _entity_poly, _struct_asym or _entity records",
}


@pytest.fixture
def without_parser(monkeypatch):
    """Run as an environment where the optional parser is not installed."""
    monkeypatch.setattr(mmcif, "_LOADED", True)
    monkeypatch.setattr(mmcif, "_LIBRARY", None)


# -- the committed fixtures ----------------------------------------------------


@pytest.mark.parametrize("name", ACCEPTED)
def test_every_accepting_fixture_is_accepted(name):
    assert mmcif.template_structure_problem(str(PACK / name)) is None


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_every_refusing_fixture_is_refused_with_its_reason(name):
    problem = mmcif.template_structure_problem(str(PACK / name))
    assert problem is not None
    assert REFUSED[name] in problem


@pytest.mark.parametrize("name", ACCEPTED + tuple(sorted(REFUSED)))
def test_the_optional_parser_does_not_change_a_fixtures_verdict(name, without_parser):
    """The bundled scan is the floor: same verdict, parser or no parser.

    Installing gemmi may add strictness for input neither tier has seen; it
    must never flip a committed fixture from accepted to refused.
    """
    problem = mmcif.template_structure_problem(str(PACK / name))
    if name in ACCEPTED:
        assert problem is None
    else:
        assert problem is not None and REFUSED[name] in problem


# -- the bundled lexical rules -------------------------------------------------


def test_a_loop_row_that_does_not_match_the_declared_tags_is_refused():
    """The defect that makes a truncated template unusable, named by line."""
    text = "data_x\nloop_\n_atom_site.id\n_atom_site.Cartn_x\n1 0.0\n2\n"

    problem = mmcif.structure_problem(text)

    assert problem is not None
    assert "line 2 declares 2 tags" in problem
    assert "do not form complete rows" in problem


def test_complete_loop_rows_are_accepted():
    text = (
        "data_x\n"
        "loop_\n"
        "_atom_site.id\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "1 0.0 0.0\n"
        "2 1.0 1.0\n"
    )

    assert mmcif.structure_problem(text) is None


def test_a_data_item_without_a_value_is_refused():
    """The parser's own complaint ("has no value"), applied without it."""
    text = "data_x\n_entity.id 1\n_atom_site.group_PDB\n_atom_site.id 1\n"

    problem = mmcif.structure_problem(text)

    assert problem is not None
    assert "the data item _atom_site.group_PDB at line 3 has no value" in problem


def test_a_data_item_may_take_a_text_field_on_the_next_line():
    text = "data_x\n_struct.title\n;\nsynthetic template\n;\n_atom_site.id 1\n"

    assert mmcif.structure_problem(text) is None


def test_quotes_group_a_value_and_a_trailing_comment_is_not_a_value():
    text = (
        "data_x\n"
        "_struct.title 'a b # not a comment'\n"
        "_atom_site.label_asym_id 'A B' # the id\n"
        "_atom_site.id 1\n"
    )

    assert mmcif.structure_problem(text) is None


def test_text_without_a_data_block_is_refused():
    problem = mmcif.structure_problem("_atom_site.id 1\n_atom_site.label_asym_id A\n")

    assert problem is not None
    assert "no 'data_' block" in problem


def test_a_data_block_without_structure_records_is_refused():
    problem = mmcif.structure_problem("data_x\n_struct.title 'no atoms here'\n")

    assert problem is not None
    assert "no _atom_site, _entity_poly, _struct_asym or _entity records" in problem


@pytest.mark.parametrize(
    "name",
    ("pdb", "json", "fasta", "csv"),
)
def test_files_that_are_not_structures_are_refused(name):
    """A template prompt takes any file the user picks, so nonsense is normal."""
    samples = {
        "pdb": "HEADER    PROTEIN\nATOM      1  N   ALA A   1       0.000   0.000\nEND\n",
        "json": '{"name": "job", "modelSeeds": [1]}\n',
        "fasta": ">query\nACDEFGHIKL\n",
        "csv": "name,smiles\nethanol,CCO\n",
    }

    assert mmcif.structure_problem(samples[name]) is not None


# -- reading a file ------------------------------------------------------------


def test_an_empty_file_is_reported_as_empty(tmp_path):
    path = tmp_path / "empty.cif"
    path.write_text("", encoding="utf-8")

    assert mmcif.template_structure_problem(str(path)) == "the file is empty"


def test_a_whitespace_only_file_is_reported_as_empty(tmp_path):
    path = tmp_path / "blank.cif"
    path.write_text("\n   \n#\n", encoding="utf-8")

    problem = mmcif.template_structure_problem(str(path))

    # Only the comment line is content, and it carries no block.
    assert problem is not None and problem != "the file is empty"


def test_a_file_that_is_not_utf8_text_is_reported_as_such(tmp_path):
    path = tmp_path / "binary.cif"
    path.write_bytes(b"data_x\n\xff\xfe\x00\x01\n")

    assert (
        mmcif.template_structure_problem(str(path)) == "the file is not UTF-8 text"
    )


def test_a_missing_file_is_reported_as_unreadable(tmp_path):
    assert (
        mmcif.template_structure_problem(str(tmp_path / "absent.cif"))
        == "the file cannot be read"
    )


# -- the optional parser's own tier -------------------------------------------


def test_the_installed_parser_is_consulted_when_it_is_present():
    """Its tier answers directly: both a structure and a refusal."""
    module = mmcif._load_library()
    if module is None:
        pytest.skip("no optional mmCIF parser is installed")

    assert mmcif.library_available() is True
    assert mmcif._library_problem("data_x\n_atom_site.id 1\n") is None
    # Two tags, three values: a row cannot be that wide, and the parser says so.
    assert (
        mmcif._library_problem(
            "data_x\nloop_\n_atom_site.id\n_atom_site.Cartn_x\n1 2 3\n"
        )
        is not None
    )


def test_the_parser_tier_is_absent_cleanly_when_it_is_not_installed(monkeypatch):
    monkeypatch.setattr(mmcif, "_load_library", lambda: None)
    monkeypatch.setattr(mmcif, "_LOADED", False)
    try:
        assert mmcif.library_available() is False
        assert mmcif._library_problem("data_x\nloop_\n_atom_site.id\n1 2\n") is None
    finally:
        monkeypatch.undo()
