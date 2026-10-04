"""Version and corruption handling (IMPLEMENTATION_PLAN.md §14).

Lower stored versions run named upgrade steps; higher versions are
refused with a message naming both versions; corrupted or hand-mangled
files are refusals that name the location — never invalid models.
"""

from __future__ import annotations

import json

import pytest

from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import (
    Configuration,
    ConfigurationMetadata,
    FamilyARecord,
    SeedSet,
    SequenceText,
)
from configbuilder.persistence import (
    FutureVersionError,
    PersistenceError,
    Project,
    SCHEMA_VERSION,
    load,
    save,
    upgrade,
)


def _minimal_project(name="job"):
    registry = IdentityRegistry()
    a = registry.allocate().value
    return Project(
        configuration=Configuration(
            metadata=ConfigurationMetadata(name),
            seeds=SeedSet([1]),
            records=(FamilyARecord(ids=Multiplicity([a]), sequence=SequenceText("PEPT", "protein")),),
            identity=registry,
        )
    )


def _write(tmp_path, data, name="p.cbproj"):
    path = str(tmp_path / name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(data if isinstance(data, str) else json.dumps(data))
    return path


def _tmp_path(tmp_path, name="p.cbproj"):
    return str(tmp_path / name)


def _saved_data(tmp_path):
    import os

    path = _write(tmp_path, "{}", "tmp.cbproj")
    os.remove(path)
    save(_minimal_project(), path)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle), path


# -- future versions are refused, never guessed ------------------------------------


def test_higher_schema_version_is_refused_by_name(tmp_path):
    data, _ = _saved_data(tmp_path)
    data["schema_version"] = SCHEMA_VERSION + 1
    path = _write(tmp_path, data)
    with pytest.raises(FutureVersionError) as excinfo:
        load(path)
    message = str(excinfo.value)
    assert str(SCHEMA_VERSION) in message and str(SCHEMA_VERSION + 1) in message
    assert "upgrade the builder" in message


def test_non_integer_schema_version_is_refused(tmp_path):
    data, _ = _saved_data(tmp_path)
    data["schema_version"] = "1"
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="schema_version"):
        load(path)


def test_missing_schema_version_is_refused(tmp_path):
    data, _ = _saved_data(tmp_path)
    del data["schema_version"]
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="schema_version"):
        load(path)


# -- named upgrade steps ------------------------------------------------------------


def test_upgrade_registry_runs_named_steps_in_order():
    def step(data):
        return data

    from configbuilder.persistence import schema

    assert schema.UPGRADES, "the upgrade table documents the migration path"


def test_upgrade_applies_the_stored_step():
    data = {"schema_version": 0, "project": {"marker": True}}
    upgraded = upgrade(data, 0)
    assert upgraded["schema_version"] == SCHEMA_VERSION
    assert upgraded["project"]["marker"] is True  # content preserved


def test_upgrade_gap_is_a_refusal_not_a_guess():
    from configbuilder.persistence import schema

    data = {"schema_version": 0}
    saved = schema.UPGRADES
    try:
        schema.UPGRADES = {}  # simulate a missing step
        with pytest.raises(PersistenceError, match="no upgrade step"):
            upgrade(data, 0)
    finally:
        schema.UPGRADES = saved


def test_load_runs_the_upgrade_path(tmp_path, monkeypatch):
    data, path = _saved_data(tmp_path)
    data["schema_version"] = 0
    # v0's shape has no groups key: the loader must land on the current
    # schema through the named step, and the registry then gets its default
    # groups from the persisted order.
    from configbuilder.identity.registry import IdentityRegistry as _R

    original = _R.from_data.__doc__
    written = _write(tmp_path, data, "v0.cbproj")
    result = load(written)
    assert result.upgraded_from == 0
    assert result.schema_version == SCHEMA_VERSION
    assert result.project == _minimal_project()


# -- corrupted files are refusals naming the location --------------------------------


def test_truncated_json_is_refused(tmp_path):
    import os

    path = str(tmp_path / "p.cbproj")
    save(_minimal_project(), path)
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    _write(tmp_path, content[: len(content) // 2])
    with pytest.raises(PersistenceError, match="not valid JSON"):
        load(str(tmp_path / "p.cbproj"))


def test_non_object_json_is_refused(tmp_path):
    path = _write(tmp_path, "[1, 2, 3]")
    with pytest.raises(PersistenceError, match="JSON object"):
        load(path)


def test_missing_project_object_is_refused(tmp_path):
    data, _ = _saved_data(tmp_path)
    del data["project"]
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="project"):
        load(path)


def test_unknown_record_family_is_refused(tmp_path):
    data, _ = _saved_data(tmp_path)
    data["project"]["configuration"]["records"][0]["family"] = "FamilyZRecord"
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="unknown record family"):
        load(path)


def test_unknown_presence_state_is_refused(tmp_path):
    data, _ = _saved_data(tmp_path)
    data["project"]["configuration"]["records"][0]["presence"]["state"] = "maybe"
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="presence state"):
        load(path)


def test_unknown_edit_kind_is_refused(tmp_path):
    data, _ = _saved_data(tmp_path)
    data["project"]["variant_specs"] = [
        {
            "key": "k",
            "label": "l",
            "edits": [{"kind": "DeleteEverything"}],
            "declared_factors": [],
        }
    ]
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="unknown edit kind"):
        load(path)


def test_invalid_model_values_are_refused(tmp_path):
    data, _ = _saved_data(tmp_path)
    # a protein record with an empty sequence: the SequenceText constructor
    # must refuse it on load, exactly as it would in the UI. The refusal
    # names the record's location in the file.
    data["project"]["configuration"]["records"][0]["sequence_text"]["text"] = ""
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="configuration.records"):
        load(path)


def test_load_of_hand_mangled_record_refuses_through_the_constructor(tmp_path):
    data, _ = _saved_data(tmp_path)
    # ids must be a list of identifier strings; hand-edited junk is caught
    # by the Multiplicity constructor during decode.
    data["project"]["configuration"]["records"][0]["ids"] = "not-a-list"
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="configuration.records"):
        load(path)


def test_unresolvable_linkage_endpoint_is_refused(tmp_path):
    data, _ = _saved_data(tmp_path)
    # Z was never assigned in the persisted registry; decode refuses the
    # dangling endpoint because identity is the sole resolution authority.
    data["project"]["configuration"]["linkages"] = [
        {
            "a": {"entity": "A", "residue": 1, "atom": "CA"},
            "b": {"entity": "Z", "residue": 2, "atom": "CB"},
        }
    ]
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="linkages"):
        load(path)


def test_missing_required_key_is_refused_with_location(tmp_path):
    data, _ = _saved_data(tmp_path)
    del data["project"]["configuration"]["seeds"]
    path = _write(tmp_path, data)
    with pytest.raises(PersistenceError, match="seeds"):
        load(path)


def test_unreadable_file_is_refused(tmp_path):
    with pytest.raises(PersistenceError, match="cannot be read"):
        load(str(tmp_path / "does-not-exist.cbproj"))


# -- loaded projects validate immediately (plan §14) ----------------------------------


def test_load_surfaces_validation_findings_immediately(tmp_path):
    """Plan §14: a loaded project is validated immediately and its findings
    are presented now. A modification beyond the sequence end is the clean
    case: constructible by the model (position-within-sequence is a
    RELATIONAL rule, not a model invariant) and an ERROR by R-ENT-007."""
    from configbuilder.model import ComponentCode, ModificationRecord, Position
    from configbuilder.validation import validate

    registry = IdentityRegistry()
    a = registry.allocate().value
    configuration = Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1]),
        records=(
            FamilyARecord(
                ids=Multiplicity([a]),
                sequence=SequenceText("PEPT", "protein"),
                modifications=(ModificationRecord(ComponentCode("P"), Position(5000)),),
            ),
        ),
        identity=registry,
    )
    path = _tmp_path(tmp_path)
    save(Project(configuration=configuration), path)
    result = load(path, validate=validate)
    assert result.report is not None
    errors = [finding for finding in result.report.findings if finding.severity.name == "ERROR"]
    assert any("R-ENT-007" in finding.rule_id for finding in errors), errors


def test_clean_project_loads_with_the_expected_blockers(tmp_path):
    """A structurally clean project still carries the documented Unverified
    blockers (R-ROOT-002, R-VER-001) — the load-time report must show them,
    and nothing else."""
    from configbuilder.validation import validate

    path = _tmp_path(tmp_path)
    save(_minimal_project(), path)
    result = load(path, validate=validate)
    assert result.report is not None
    errors = sorted(f.rule_id for f in result.report.findings if f.severity.name == "ERROR")
    assert errors == ["R-ROOT-002", "R-VER-001"]
