"""JSON import tests (feature spec §7, §22): AF3 JSON → canonical
configuration → the normal pipeline.

The importer must rebuild the model through the validated constructors,
preserve the file's own DNA strands without duplexing them, route new
identifiers through the existing registry so nothing collides, and refuse
unsupported entity types explicitly (never silently).
"""

from __future__ import annotations

import json
import os

import pytest

from configbuilder.app.project_service import ProjectService
from configbuilder.model import ExplicitEmpty, Unset
from configbuilder.transform import WireImportError, from_wire, to_wire


def _doc(**overrides):
    doc = {
        "name": "Imported_Job",
        "modelSeeds": [1, 2, 3],
        "sequences": [
            {"protein": {"id": "A", "sequence": "ACDEFGHIKLMNP"}},
            {"dna": {"id": "B", "sequence": "ATGC"}},
            {"dna": {"id": "C", "sequence": "GCAT"}},
            {"ligand": {"id": "D", "ccdCodes": ["ATP"]}},
        ],
        "dialect": "alphafold3",
        "version": 4,
    }
    doc.update(overrides)
    return doc


def _write(tmp_path, doc, name="job.json"):
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


# -- basic import ---------------------------------------------------------------


def test_minimal_protein_json_imports_into_the_canonical_model():
    configuration, notes = from_wire(
        _doc(sequences=[{"protein": {"id": "A", "sequence": "ACDE"}}])
    )
    assert notes == ()
    assert configuration.metadata.name == "Imported_Job"
    assert [record.ids.primary.value for record in configuration.records] == ["A"]


def test_every_supported_family_imports(tmp_path):
    doc = _doc()
    doc["sequences"] = doc["sequences"] + [
        {"rna": {"id": "E", "sequence": "AUGCAUGC"}},
    ]
    path = _write(tmp_path, doc)
    service = ProjectService()
    result = service.import_json_commit(path)
    assert result.ok, result.message
    families = sorted(type(record).__name__ for record in service.project.configuration.records)
    assert families == ["ComponentRecord", "FamilyARecord", "FamilyBRecord", "FamilyCRecord", "FamilyCRecord"]


def test_modifications_and_msa_and_templates_import():
    configuration, notes = from_wire(
        _doc(
            sequences=[
                {
                    "protein": {
                        "id": "A",
                        "sequence": "ACDEFGHIKLMNP",
                        "modifications": [{"ptmType": "SEP", "ptmPosition": 5}],
                        "unpairedMsaPath": "msa.a3m",
                        "templates": [
                            {"mmcifPath": "tpl.cif", "queryIndices": [0, 1], "templateIndices": [0, 0]}
                        ],
                    }
                }
            ]
        )
    )
    assert notes == ()
    record = configuration.records[0]
    assert [(mod.code.value, mod.position.value) for mod in record.modifications] == [("SEP", 5)]
    assert record.alignment is not None
    assert record.references.items[0].index_map[0].query == 0


def test_ion_as_ccd_codes_imports_like_a_ligand():
    configuration, notes = from_wire(_doc(sequences=[{"ligand": {"id": "MG", "ccdCodes": ["MG"]}}]))
    assert notes == ()
    assert configuration.records[0].representation.codes[0].value == "MG"


def test_smiles_ligand_imports():
    configuration, notes = from_wire(
        _doc(sequences=[{"ligand": {"id": "L", "smiles": "COCO"}}])
    )
    assert notes == ()
    assert configuration.records[0].representation.text == "COCO"


def test_version_and_seeds_are_preserved():
    configuration, notes = from_wire(_doc())
    assert notes == ()
    selection = configuration.format_target.version_selection
    assert selection.version == 4
    assert [seed.value for seed in configuration.seeds.seeds] == [1, 2, 3]


# -- DNA duplex (§8): the file's strands are authoritative -----------------------


def test_dna_import_does_not_duplicate_strands():
    """A file that already carries both strands imports exactly two."""
    configuration, _notes = from_wire(_doc())
    dna_records = [record for record in configuration.records if type(record).__name__ == "FamilyCRecord"]
    assert len(dna_records) == 2
    assert [record.sequence.text for record in dna_records] == ["ATGC", "GCAT"]


def test_single_dna_strand_stays_single_on_import():
    """Import never complements: one strand in, one strand out (the duplex
    construction belongs to record creation, not to import)."""
    configuration, _notes = from_wire(
        _doc(sequences=[{"dna": {"id": "B", "sequence": "ATGC"}}])
    )
    assert len(configuration.records) == 1
    assert configuration.records[0].sequence.text == "ATGC"


# -- identity (§9) ----------------------------------------------------------------


def test_imported_ids_are_preserved_and_new_ones_do_not_collide():
    configuration, _notes = from_wire(_doc())
    assert [record.ids.primary.value for record in configuration.records] == ["A", "B", "C", "D"]
    assert configuration.identity.allocate(owner="record").value == "E"


def test_duplicate_ids_in_the_file_are_refused():
    with pytest.raises(WireImportError) as error:
        from_wire(
            _doc(sequences=[
                {"protein": {"id": "A", "sequence": "ACDE"}},
                {"protein": {"id": "A", "sequence": "ACDF"}},
            ])
        )
    assert "already assigned" in str(error.value)


def test_bond_to_an_undefined_entity_is_refused():
    with pytest.raises(WireImportError) as error:
        from_wire({**_doc(), "bondedAtomPairs": [[["Z", 1, "SG"], ["A", 3, "SG"]]]})
    assert "does not define" in str(error.value)


def test_valid_bond_imports():
    configuration, notes = from_wire({**_doc(), "bondedAtomPairs": [[["A", 3, "SG"], ["D", 1, "OXT"]]]})
    assert notes == ()
    assert len(configuration.linkages) == 1


# -- round trip (§16) ---------------------------------------------------------------


def test_round_trip_import_then_export_is_semantically_equal():
    configuration, _notes = from_wire(_doc())
    document = to_wire(configuration).document
    assert document["name"] == "Imported_Job"
    assert document["modelSeeds"] == [1, 2, 3]
    assert document["version"] == 4
    assert len(document["sequences"]) == 4
    assert [list(entity)[0] for entity in document["sequences"]] == [
        "protein", "dna", "dna", "ligand",
    ]
    ids = [entity[fam]["id"] for entity, fam in zip(document["sequences"], ["protein", "dna", "dna", "ligand"])]
    assert ids == ["A", "B", "C", "D"]


def test_full_feature_round_trip_is_byte_stable_through_the_model():
    doc = _doc(
        sequences=[{
            "protein": {
                "id": "A",
                "sequence": "ACDEFGHIKLMNP",
                "modifications": [{"ptmType": "SEP", "ptmPosition": 5}],
                "unpairedMsa": ">query\nACDE\n",
                "pairedMsa": "",
                "templates": [{"mmcifPath": "tpl.cif"}],
                "description": "kinase domain",
            }
        }]
    )
    first, _notes = from_wire(doc)
    second, _again = from_wire(to_wire(first).document)
    assert to_wire(first).document == to_wire(second).document


# -- unsupported content (§19): explicit, never silent ------------------------------


def test_unsupported_entity_type_is_refused_with_a_clear_reason():
    with pytest.raises(WireImportError) as error:
        from_wire(_doc(sequences=[{"nanobody": {"id": "X", "sequence": "ACDE"}}]))
    message = str(error.value)
    assert "nanobody" in message
    assert "not supported" in message


def test_unknown_root_field_becomes_an_explicit_note():
    configuration, notes = from_wire({**_doc(), "affinityPrediction": True})
    assert configuration.metadata.name == "Imported_Job"
    assert len(notes) == 1
    assert "affinityPrediction" in notes[0].field


def test_unknown_family_field_becomes_an_explicit_note():
    _, notes = from_wire(
        _doc(sequences=[{"protein": {"id": "A", "sequence": "ACDE", "ionCoord": {"x": 1}}}])
    )
    assert any("ionCoord" in note.field for note in notes)


def test_dialect_mismatch_warns_but_imports():
    configuration, notes = from_wire({**_doc(), "dialect": "boltz"})
    assert configuration.metadata.name == "Imported_Job"
    assert any("dialect" in note.field for note in notes)


# -- app service: preview/commit and error handling (§20) ----------------------------


def test_preview_does_not_touch_the_current_project(tmp_path):
    path = _write(tmp_path, _doc())
    service = ProjectService()
    service.new("My Job")
    preview = service.import_json_preview(path)
    assert preview.ok
    assert preview.summary["job_name"] == "Imported_Job"
    assert service.project.configuration.metadata.name == "My Job"


def test_commit_makes_the_import_a_normal_editable_project(tmp_path):
    path = _write(tmp_path, _doc())
    service = ProjectService()
    result = service.import_json_commit(path)
    assert result.ok
    assert service.is_open
    assert service.project.specs == ()  # variants start empty: the import is a base job
    # and the normal mutation service can edit it through the registry:
    from configbuilder.app.configuration_service import ConfigurationService

    configuration = ConfigurationService(service)
    outcome = configuration.add_record("protein", "GKKIGYS")
    assert outcome.ok, outcome.message


def test_import_then_add_entity_receives_a_non_colliding_id(tmp_path):
    path = _write(tmp_path, _doc())
    service = ProjectService()
    assert service.import_json_commit(path).ok
    from configbuilder.app.configuration_service import ConfigurationService

    configuration = ConfigurationService(service)
    assert configuration.add_record("protein", "GKKIGYS").ok
    ids = [record.ids.primary.value for record in service.project.configuration.records]
    assert len(ids) == len(set(ids)) == 5
    assert "E" in ids


def test_broken_json_is_a_clear_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    service = ProjectService()
    result = service.import_json_preview(str(path))
    assert not result.ok
    assert "not valid JSON" in result.message


def test_wrong_top_level_structure_is_rejected(tmp_path):
    path = _write(tmp_path, {"hello": "world"})
    service = ProjectService()
    result = service.import_json_preview(str(path))
    assert not result.ok
    assert "name" in result.message


def test_missing_required_data_names_the_problem(tmp_path):
    doc = _doc()
    del doc["modelSeeds"]
    path = _write(tmp_path, doc)
    service = ProjectService()
    result = service.import_json_preview(str(path))
    assert not result.ok
    assert "modelSeeds" in result.message


def test_nonexistent_file_is_a_normal_error(tmp_path):
    service = ProjectService()
    result = service.import_json_preview(str(tmp_path / "absent.json"))
    assert not result.ok
    assert result.failure_reason == "io_error"


def test_original_file_is_never_modified_by_import_or_generation(tmp_path):
    path = _write(tmp_path, _doc())
    before = open(path, "rb").read()
    service = ProjectService()
    assert service.import_json_commit(path).ok
    assert open(path, "rb").read() == before


# -- description on every family (§4; AF3 examples carry it on all of them) -------------


def _described_document():
    return _doc(sequences=[
        {"protein": {"id": "A", "sequence": "ACDEFGHIKLMNP", "description": "protein note"}},
        {"rna": {"id": "B", "sequence": "ACGUACGU", "description": "rna note"}},
        {"dna": {"id": "C", "sequence": "ATGC", "description": "dna note"}},
        {"ligand": {"id": "D", "ccdCodes": ["ATP"], "description": "ligand note"}},
    ])


def test_description_is_imported_for_every_family():
    """§4 grants ``description`` to protein, RNA, DNA *and* ligand entries.

    The importer's own field list already advertised it for all four, but the
    DNA branch never passed it on and the ligand branch was built before the
    description was read -- so a re-emitted file silently lost the annotation.
    Every official AF3 example that annotates a DNA strand or a ligand hits it.
    """
    configuration, _notes = from_wire(_described_document())
    descriptions = {
        record.ids.primary.value: record.description.value
        for record in configuration.records
    }
    assert descriptions == {
        "A": "protein note",
        "B": "rna note",
        "C": "dna note",
        "D": "ligand note",
    }


def test_description_survives_a_round_trip_for_dna_and_ligand():
    configuration, _notes = from_wire(_described_document())
    document = to_wire(configuration).document
    seen = {}
    for sequence in document["sequences"]:
        for family, body in sequence.items():
            seen.setdefault(family, []).append(body.get("description"))
    # The importer keeps the file's own DNA strands as written: a described
    # strand stays one strand. (The builder creates a *new* DNA entity as a
    # duplex, which is a different path -- see test_to_wire.)
    assert seen["dna"] == ["dna note"]
    assert seen["ligand"] == ["ligand note"]
    assert seen["protein"] == ["protein note"]
    assert seen["rna"] == ["rna note"]


def test_absent_description_stays_absent_for_dna_and_ligand():
    """Unset must not become ExplicitEmpty: the two are different states."""
    configuration, _notes = from_wire(_doc())
    for record in configuration.records:
        assert isinstance(record.description, Unset)


def test_empty_description_stays_explicitly_empty_for_dna_and_ligand():
    """A present-but-empty description is not the same state as an absent one."""
    document = _doc(sequences=[
        {"dna": {"id": "C", "sequence": "ATGC", "description": ""}},
        {"ligand": {"id": "D", "ccdCodes": ["ATP"], "description": ""}},
    ])
    configuration, _notes = from_wire(document)
    for record in configuration.records:
        assert isinstance(record.description, ExplicitEmpty)
