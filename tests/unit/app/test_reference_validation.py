"""The application service owns template file and index-pair validation."""

from __future__ import annotations

from configbuilder.app.configuration_service import ReferenceInput
from configbuilder.model import Explicit, SearchAllowed
from configbuilder.transform import to_wire
from configbuilder.ui.services import build_services


def _project():
    services = build_services()
    services.projects.new("reference-validation")
    services.configuration.add_record("protein", "ACDEFGHIKL")
    return services


#: A real single-chain protein template: ten residues declared by
#: ``_entity_poly``, which is the sequence ``templateIndices`` address. A stub
#: with only an ``_atom_site`` row is not a template (no polymer chain, no
#: residue list), and the mapping checks say so.
TEMPLATE_CIF = (
    "data_template\n"
    "#\n"
    "_entity_poly.entity_id 1\n"
    "_entity_poly.type 'polypeptide(L)'\n"
    "_entity_poly.pdbx_strand_id A\n"
    "_entity_poly.pdbx_seq_one_letter_code ACDEFGHIKL\n"
    "#\n"
)


def _cif(tmp_path, name="template.cif"):
    path = tmp_path / name
    path.write_text(TEMPLATE_CIF, encoding="utf-8")
    return path


def _references(services):
    return services.projects.project.configuration.records[0].references


def test_the_service_rejects_a_missing_template_file_directly(tmp_path):
    services = _project()
    missing = tmp_path / "missing.cif"

    outcome = services.configuration.set_references(
        "A",
        references=(
            ReferenceInput(external_path=str(missing), pairs=((0, 0),)),
        ),
    )

    assert not outcome.ok
    assert "The template file %r cannot be used" % str(missing) in outcome.message
    assert "the file does not exist" in outcome.message
    assert isinstance(_references(services), SearchAllowed)


def test_the_service_rejects_bad_extensions_and_empty_files(tmp_path):
    services = _project()
    wrong = tmp_path / "template.txt"
    wrong.write_text("data_template\n", encoding="utf-8")
    empty = tmp_path / "empty.cif"
    empty.write_text("", encoding="utf-8")

    for path, reason in (
        (wrong, "the file must end in .cif or .mmcif"),
        (empty, "the file is empty"),
        (tmp_path, "the path is not a regular file"),
    ):
        outcome = services.configuration.set_references(
            "A",
            references=(
                ReferenceInput(external_path=str(path), pairs=((0, 0),)),
            ),
        )
        assert not outcome.ok, path
        assert reason in outcome.message, outcome.message
        assert isinstance(_references(services), SearchAllowed)


def test_the_service_refuses_a_template_that_is_not_a_structure(tmp_path):
    """A refused file leaves the record exactly as it was: nothing half-attached.

    The text below is a loop whose values cannot form rows of the declared
    width — the shape of a truncated template. Existence, extension and
    emptiness are not enough for a template: AF3 has to be able to read it.
    """
    services = _project()
    broken = tmp_path / "truncated.cif"
    broken.write_text(
        "data_template\nloop_\n_atom_site.group_PDB\n_atom_site.id\n"
        "_atom_site.Cartn_x\nATOM 1 0.000\nATOM\n",
        encoding="utf-8",
    )

    outcome = services.configuration.set_references(
        "A",
        references=(ReferenceInput(external_path=str(broken), pairs=((0, 0),)),),
    )

    assert not outcome.ok
    assert "the file is not a usable mmCIF structure" in outcome.message
    assert isinstance(_references(services), SearchAllowed)


def test_the_service_refuses_an_mmCIF_file_with_no_structure_in_it(tmp_path):
    services = _project()
    empty_structure = tmp_path / "title-only.cif"
    empty_structure.write_text(
        "data_template\n_struct.title 'no atoms here'\n", encoding="utf-8"
    )

    outcome = services.configuration.set_references(
        "A",
        references=(
            ReferenceInput(external_path=str(empty_structure), pairs=((0, 0),)),
        ),
    )

    assert not outcome.ok
    assert "no _atom_site, _entity_poly, _struct_asym or _entity records" in (
        outcome.message
    )
    assert isinstance(_references(services), SearchAllowed)


def test_the_service_rejects_empty_and_malformed_pairs(tmp_path):
    services = _project()
    path = _cif(tmp_path)

    for pairs, reason in (
        ((), "At least one query:template pair is required"),
        ((("notanumber", "1"),), "is not query:template"),
        (((-1, 0),), "is not query:template"),
        (((10, 0),), "query index 10 is outside the target sequence"),
    ):
        outcome = services.configuration.set_references(
            "A",
            references=(ReferenceInput(external_path=str(path), pairs=pairs),),
        )
        assert not outcome.ok, pairs
        assert reason in outcome.message, outcome.message
        assert isinstance(_references(services), SearchAllowed)


def test_the_service_accepts_and_serializes_two_valid_templates(tmp_path):
    services = _project()
    first = _cif(tmp_path, "first.cif")
    second = _cif(tmp_path, "second.mmcif")

    outcome = services.configuration.set_references(
        "A",
        references=(
            ReferenceInput(external_path=str(first), pairs=((0, 5), (1, 6))),
            ReferenceInput(external_path=str(second), pairs=((0, 0),)),
        ),
    )

    assert outcome.ok, outcome.message
    assert isinstance(_references(services), Explicit)
    document = to_wire(services.projects.project.configuration).document
    templates = document["sequences"][0]["protein"]["templates"]
    assert templates == [
        {
            "mmcifPath": str(first),
            "queryIndices": [0, 1],
            "templateIndices": [5, 6],
        },
        {
            "mmcifPath": str(second),
            "queryIndices": [0],
            "templateIndices": [0],
        },
    ]
