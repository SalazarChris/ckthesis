"""to_wire unit tests (plan §10.1, §10.2)."""

from __future__ import annotations

import pytest

from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity
from configbuilder.model import (
    AlignmentBoth,
    AlignmentFree,
    AlignmentPairedOnly,
    AlignmentUnpairedOnly,
    ByCode,
    ByNotation,
    ComponentCode,
    ComponentRecord,
    Configuration,
    ConfigurationMetadata,
    Explicit,
    External,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    FormatTarget,
    IndexPair,
    Inline,
    LinkEndpoint,
    Linkage,
    ModificationRecord,
    PathSpec,
    Position,
    Present,
    Pinned,
    ReferenceRecord,
    ResidueRef,
    SeedSet,
    SequenceText,
    SingleFree,
    SingleProvided,
)
from configbuilder.transform import (
    ExternalResourceRequirement,
    TransformError,
    WireDocument,
    to_wire,
)


def _registry(*values):
    registry = IdentityRegistry()
    for value in values:
        registry.assign(value, owner="test")
    return registry


def _configuration(records=(), seeds=(1, 2, 3), name="job", version=3):
    return Configuration(
        metadata=ConfigurationMetadata(name),
        seeds=SeedSet(list(seeds)),
        records=tuple(records),
        identity=IdentityRegistry(),
    ).with_format_target(FormatTarget(version_selection=Pinned(version)))


def _protein(entity="A", **kwargs):
    return FamilyARecord(ids=Multiplicity([entity]), sequence=SequenceText("PEPTIDE", "protein"), **kwargs)


# -- root shape ---------------------------------------------------------------


def test_root_key_order_matches_contract():
    result = to_wire(_configuration(records=(_protein(),)))
    assert list(result.document.keys()) == [
        "name",
        "modelSeeds",
        "sequences",
        "dialect",
        "version",
    ]


def test_root_fields_present():
    result = to_wire(_configuration(records=(_protein(),)))
    assert result.document["name"] == "job"
    assert result.document["modelSeeds"] == [1, 2, 3]
    assert result.document["dialect"] == "alphafold3"
    assert result.document["version"] == 3


def test_bonded_omitted_when_no_linkages():
    result = to_wire(_configuration(records=(_protein(),)))
    assert "bondedAtomPairs" not in result.document


def test_bonded_atom_pairs_shape():
    protein = _protein("A")
    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByCode((ComponentCode("TPO"),)))
    linkage = Linkage(
        LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(2), atom="SG"),
        LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(1), atom="C1"),
    )
    configuration = _configuration(records=(protein, ligand)).with_linkages((linkage,))
    result = to_wire(configuration)
    assert result.document["bondedAtomPairs"] == [
        [["A", 2, "SG"], ["D", 1, "C1"]]
    ]


def test_user_ccd_xor_inline():
    configuration = _configuration(records=(_protein(),)).with_component_definition(
        Inline("data_x")
    )
    result = to_wire(configuration)
    assert result.document["userCCD"] == "data_x"
    assert "userCCDPath" not in result.document


def test_user_ccd_xor_path():
    configuration = _configuration(records=(_protein(),)).with_component_definition(
        External(PathSpec("ccd.cif"))
    )
    result = to_wire(configuration)
    assert result.document["userCCDPath"] == "ccd.cif"
    assert "userCCD" not in result.document
    assert result.external_resources == (ExternalResourceRequirement("userCCDPath", "ccd.cif"),)


# -- entity wrappers and id forms -----------------------------------------------


def test_each_entity_is_a_single_key_object():
    records = (
        _protein("A"),
        FamilyBRecord(ids=Multiplicity(["B"]), sequence=SequenceText("ACGU", "rna")),
        FamilyCRecord(ids=Multiplicity(["C"]), sequence=SequenceText("ACGT", "dna")),
        ComponentRecord(ids=Multiplicity(["D"]), representation=ByCode((ComponentCode("TPO"),))),
    )
    result = to_wire(_configuration(records=records))
    keys = [list(entity.keys())[0] for entity in result.document["sequences"]]
    assert keys == ["protein", "rna", "dna", "ligand"]


def test_multiplicity_single_value_form():
    result = to_wire(_configuration(records=(_protein("A"),)))
    assert result.document["sequences"][0]["protein"]["id"] == "A"


def test_multiplicity_list_form():
    protein = FamilyARecord(
        ids=Multiplicity(["A", "B"]),
        sequence=SequenceText("PEPTIDE", "protein"),
    )
    result = to_wire(_configuration(records=(protein,)))
    assert result.document["sequences"][0]["protein"]["id"] == ["A", "B"]

# -- presence: omitted vs empty (the heart of spec §6.2/6.3) ---------------------


def test_automatic_msa_omits_all_four_fields():
    result = to_wire(_configuration(records=(_protein("A"),)))
    protein = result.document["sequences"][0]["protein"]
    for field in ("unpairedMsa", "unpairedMsaPath", "pairedMsa", "pairedMsaPath"):
        assert field not in protein


def test_msa_free_emits_both_fields_empty():
    result = to_wire(_configuration(records=(_protein("A", alignment=AlignmentFree()),)))
    protein = result.document["sequences"][0]["protein"]
    assert protein["unpairedMsa"] == ""
    assert protein["pairedMsa"] == ""
    assert "unpairedMsaPath" not in protein
    assert "pairedMsaPath" not in protein


def test_unpaired_only_emits_populated_and_explicit_empty():
    """Spec §11 protein: both fields are represented, the empty side as ""."""
    result = to_wire(
        _configuration(
            records=(
                _protein("A", alignment=AlignmentUnpairedOnly(source=Inline(">q\nPEPTIDE"))),
            )
        )
    )
    protein = result.document["sequences"][0]["protein"]
    assert protein["unpairedMsa"] == ">q\nPEPTIDE"
    assert protein["pairedMsa"] == ""


def test_paired_only_emits_empty_then_populated():
    result = to_wire(
        _configuration(
            records=(
                _protein("A", alignment=AlignmentPairedOnly(source=Inline(">q\nPEPTIDE"))),
            )
        )
    )
    protein = result.document["sequences"][0]["protein"]
    assert protein["unpairedMsa"] == ""
    assert protein["pairedMsa"] == ">q\nPEPTIDE"


def test_unpaired_path_form():
    result = to_wire(
        _configuration(
            records=(
                _protein(
                    "A",
                    alignment=AlignmentUnpairedOnly(source=External(PathSpec("query.a3m"))),
                ),
            )
        )
    )
    protein = result.document["sequences"][0]["protein"]
    # Path side points at its file; the empty paired side is the inline ""
    # (spec §11: both fields represented as set values, possibly one empty
    # string; inline xor path within a side, spec §6.1).
    assert protein["unpairedMsaPath"] == "query.a3m"
    assert "unpairedMsa" not in protein
    assert protein["pairedMsa"] == ""
    assert "pairedMsaPath" not in protein
    assert result.external_resources == (
        ExternalResourceRequirement("unpairedMsaPath", "query.a3m"),
    )


def test_paired_path_form():
    result = to_wire(
        _configuration(
            records=(
                _protein(
                    "A",
                    alignment=AlignmentPairedOnly(source=External(PathSpec("paired.a3m"))),
                ),
            )
        )
    )
    protein = result.document["sequences"][0]["protein"]
    assert protein["pairedMsaPath"] == "paired.a3m"
    assert "pairedMsa" not in protein
    assert protein["unpairedMsa"] == ""
    assert "unpairedMsaPath" not in protein
    # The requirement kind names the wire field that references the file.
    assert result.external_resources == (
        ExternalResourceRequirement("pairedMsaPath", "paired.a3m"),
    )


def test_both_inline_emits_both_sides():
    result = to_wire(
        _configuration(
            records=(_protein("A", alignment=AlignmentBoth(source=Inline(">q\nPEPTIDE"))),)
        )
    )
    protein = result.document["sequences"][0]["protein"]
    assert protein["unpairedMsa"] == ">q\nPEPTIDE"
    assert protein["pairedMsa"] == ">q\nPEPTIDE"
    assert "unpairedMsaPath" not in protein
    assert "pairedMsaPath" not in protein


def test_rna_msa_states():
    automatic = FamilyBRecord(ids=Multiplicity(["B"]), sequence=SequenceText("ACGU", "rna"))
    free = FamilyBRecord(
        ids=Multiplicity(["B"]),
        sequence=SequenceText("ACGU", "rna"),
        alignment=SingleFree(),
    )
    provided = FamilyBRecord(
        ids=Multiplicity(["B"]),
        sequence=SequenceText("ACGU", "rna"),
        alignment=SingleProvided(source=Inline(">q\nACGU")),
    )
    automatic_doc = to_wire(_configuration(records=(automatic,))).document["sequences"][0]["rna"]
    free_doc = to_wire(_configuration(records=(free,))).document["sequences"][0]["rna"]
    provided_doc = to_wire(_configuration(records=(provided,))).document["sequences"][0]["rna"]
    assert "unpairedMsa" not in automatic_doc  # automatic search: omitted
    assert free_doc["unpairedMsa"] == ""  # MSA-free: explicit empty
    assert provided_doc["unpairedMsa"] == ">q\nACGU"  # custom: populated


def test_dna_record_never_emits_msa_fields():
    result = to_wire(
        _configuration(records=(FamilyCRecord(ids=Multiplicity(["C"]), sequence=SequenceText("ACGT", "dna")),))
    )
    dna = result.document["sequences"][0]["dna"]
    for field in ("unpairedMsa", "unpairedMsaPath", "pairedMsa", "pairedMsaPath"):
        assert field not in dna


# -- modifications ----------------------------------------------------------------


def test_modifications_omitted_when_empty():
    result = to_wire(_configuration(records=(_protein("A"),)))
    assert "modifications" not in result.document["sequences"][0]["protein"]


def test_modification_entry_uses_stored_1_based_position():
    protein = _protein(
        "A", modifications=(ModificationRecord(code=ComponentCode("TPO"), position=Position(7)),)
    )
    result = to_wire(_configuration(records=(protein,)))
    assert result.document["sequences"][0]["protein"]["modifications"] == [
        {"ptmType": "TPO", "ptmPosition": 7}
    ]


def test_rna_modification_entry_uses_modification_type_fields():
    """RNA/DNA modifications use modificationType + basePosition (MAP-304,
    MAP-354; spec §8), not the protein ptmType/ptmPosition names."""
    rna = FamilyBRecord(
        ids=Multiplicity(["B"]),
        sequence=SequenceText("ACGU", "rna"),
        modifications=(ModificationRecord(code=ComponentCode("2MG"), position=Position(12)),),
    )
    result = to_wire(_configuration(records=(rna,)))
    assert result.document["sequences"][0]["rna"]["modifications"] == [
        {"modificationType": "2MG", "basePosition": 12}
    ]


def test_dna_modification_entry_uses_modification_type_fields():
    dna = FamilyCRecord(
        ids=Multiplicity(["C"]),
        sequence=SequenceText("ACGT", "dna"),
        modifications=(ModificationRecord(code=ComponentCode("5MC"), position=Position(3)),),
    )
    result = to_wire(_configuration(records=(dna,)))
    assert result.document["sequences"][0]["dna"]["modifications"] == [
        {"modificationType": "5MC", "basePosition": 3}
    ]


# -- templates ----------------------------------------------------------------------


def test_templates_omitted_when_search_allowed():
    result = to_wire(_configuration(records=(_protein("A"),)))
    assert "templates" not in result.document["sequences"][0]["protein"]


def test_explicit_empty_templates_emit_empty_list():
    templates = Explicit(())
    result = to_wire(_configuration(records=(_protein("A", references=templates),)))
    assert result.document["sequences"][0]["protein"]["templates"] == []


def test_template_entry_splits_index_map_into_parallel_arrays():
    templates = Explicit(
        (
            ReferenceRecord(
                source=Inline("data_t"),
                index_map=(IndexPair(0, 0), IndexPair(1, 2), IndexPair(5, 9)),
            ),
        )
    )
    result = to_wire(_configuration(records=(_protein("A", references=templates),)))
    template = result.document["sequences"][0]["protein"]["templates"][0]
    assert template["mmcif"] == "data_t"
    assert template["queryIndices"] == [0, 1, 5]
    assert template["templateIndices"] == [0, 2, 9]


def test_template_path_form():
    templates = Explicit(
        (ReferenceRecord(source=External(PathSpec("template.cif")), index_map=()),)
    )
    result = to_wire(_configuration(records=(_protein("A", references=templates),)))
    template = result.document["sequences"][0]["protein"]["templates"][0]
    assert template["mmcifPath"] == "template.cif"
    assert result.external_resources == (
        ExternalResourceRequirement("mmcifPath", "template.cif"),
    )


# -- ligand representation ------------------------------------------------------------


def test_ligand_by_code():
    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByCode((ComponentCode("TPO"), ComponentCode("MLZ"))))
    result = to_wire(_configuration(records=(ligand,), seeds=(1,)))
    ligand_doc = result.document["sequences"][0]["ligand"]
    assert ligand_doc["ccdCodes"] == ["TPO", "MLZ"]
    assert "smiles" not in ligand_doc


def test_ligand_by_notation():
    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByNotation("C1=CC=CC=C1"))
    result = to_wire(_configuration(records=(ligand,), seeds=(1,)))
    ligand_doc = result.document["sequences"][0]["ligand"]
    assert ligand_doc["smiles"] == "C1=CC=CC=C1"
    assert "ccdCodes" not in ligand_doc


# -- description min-version behaviour -------------------------------------------------


def test_description_emitted_at_v4():
    protein = _protein("A")
    protein = FamilyARecord(
        ids=Multiplicity(["A"]),
        sequence=SequenceText("PEPTIDE", "protein"),
        description=Present("annotated chain"),
    )
    result = to_wire(_configuration(records=(protein,), version=4))
    assert result.document["sequences"][0]["protein"]["description"] == "annotated chain"


def test_unverified_blocks_with_explanatory_error():
    from configbuilder.model import Unverified

    configuration = Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1]),
        records=(_protein("A"),),
        identity=IdentityRegistry(),
    )
    assert isinstance(configuration.format_target.version_selection, Unverified)
    with pytest.raises(TransformError) as excinfo:
        to_wire(configuration)
    assert "no format version has been verified" in str(excinfo.value)


def test_pinned_selects_the_evidenced_version():
    result = to_wire(_configuration(version=3))
    assert result.version == 3
    assert result.document["version"] == 3


def test_auto_selects_minimum_evidenced_version():
    from configbuilder.model import Auto

    configuration = _configuration(records=(_protein("A"),))
    configuration = configuration.with_format_target(
        FormatTarget(version_selection=Auto((2, 3, 4)))
    )
    result = to_wire(configuration)
    assert result.version == 2
    assert result.document["version"] == 2


def test_feature_above_pin_raises_naming_the_feature():
    """A v4-only feature under a v3 pin is an error naming the feature —
    the version is never silently raised (plan §10.3)."""
    protein = FamilyARecord(
        ids=Multiplicity(["A"]),
        sequence=SequenceText("PEPTIDE", "protein"),
        description=Present("annotated"),
    )
    with pytest.raises(TransformError) as excinfo:
        to_wire(_configuration(records=(protein,), version=3))
    assert "description" in str(excinfo.value)


# -- determinism and purity ----------------------------------------------------------------


def test_transform_is_deterministic():
    protein = _protein(
        "A", modifications=(ModificationRecord(code=ComponentCode("TPO"), position=Position(2)),)
    )
    one = to_wire(_configuration(records=(protein,)))
    two = to_wire(_configuration(records=(protein,)))
    assert one.document == two.document
    assert list(one.document.keys()) == list(two.document.keys())
    assert one.external_resources == two.external_resources


def test_transform_is_total_on_validated_input():
    """Exercise every family and resource form; nothing raises."""
    records = (
        _protein("A", alignment=AlignmentBoth(source=Inline(">q\nPEPTIDE"))),
        FamilyBRecord(
            ids=Multiplicity(["B"]),
            sequence=SequenceText("ACGU", "rna"),
            alignment=SingleProvided(source=External(PathSpec("rna.a3m"))),
        ),
        FamilyCRecord(ids=Multiplicity(["C"]), sequence=SequenceText("ACGT", "dna")),
        ComponentRecord(ids=Multiplicity(["DD"]), representation=ByNotation("CCO")),
    )
    result = to_wire(_configuration(records=records, seeds=(1,)))
    assert len(result.document["sequences"]) == 4
    kinds = {req.kind for req in result.external_resources}
    assert kinds == {"unpairedMsaPath"}
