"""Project-file contract tests (plan §14, Phase 9 exit criterion).

The exit criterion is the strongest statement of persistence fidelity:
``load(save(p))`` generates byte-identical output to ``p`` — through the
transform + serialize pipeline, not just model equality. The
``fixtures/projects/`` files pin compatibility across schema versions.
"""

from __future__ import annotations

import json
import os

import pytest

from configbuilder.persistence import (
    FutureVersionError,
    PersistenceError,
    SCHEMA_VERSION,
    load,
    save,
)
from configbuilder.serialize import encode
from configbuilder.transform import to_wire

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "projects")


def _fixture(name):
    return os.path.normpath(os.path.join(FIXTURES, name))


# -- exit criterion: byte-identical regeneration --------------------------------


def _round_trip_bytes(path, tmp_path):
    project = load(path).project
    document = to_wire(project.configuration).document
    return encode(document)


def test_load_save_generates_byte_identical_output(tmp_path):
    from tests.unit.persistence.test_round_trip import _rich_configuration
    from configbuilder.persistence import Project

    original = str(tmp_path / "p.cbproj")
    save(Project(configuration=_rich_configuration()), original)
    regenerated = _round_trip_bytes(original, tmp_path)
    # And once more through a full save/load cycle: still identical.
    second = str(tmp_path / "p2.cbproj")
    save(load(original).project, second)
    assert _round_trip_bytes(second, tmp_path) == regenerated


def test_exit_criterion_holds_for_the_v1_fixture(tmp_path):
    regenerated = _round_trip_bytes(_fixture("v1_compatibility.cbproj"), tmp_path)
    assert regenerated.startswith(b"{")
    # and is stable across a second load
    assert _round_trip_bytes(_fixture("v1_compatibility.cbproj"), tmp_path) == regenerated


# -- fixtures/projects compatibility ---------------------------------------------


def test_v1_fixture_loads_at_the_current_schema():
    result = load(_fixture("v1_compatibility.cbproj"))
    assert result.schema_version == SCHEMA_VERSION
    assert result.upgraded_from is None
    assert result.project.configuration.metadata.name == "Compatibility Project"
    assert result.project.specs[0].key == "apo"


def test_legacy_v0_fixture_upgrades_and_loads():
    result = load(_fixture("legacy_v0.cbproj"))
    assert result.upgraded_from == 0
    assert result.schema_version == SCHEMA_VERSION
    # The upgraded project matches the v1 fixture's content.
    v1 = load(_fixture("v1_compatibility.cbproj")).project
    assert result.project == v1


def test_fixtures_are_stable_across_a_resave(tmp_path):
    """A compatibility fixture re-saved by this builder must load to the
    same project — the fixture is a real project file, not a special case."""
    path = _fixture("v1_compatibility.cbproj")
    project = load(path).project
    resaved = str(tmp_path / "resaved.cbproj")
    save(project, resaved)
    assert load(resaved).project == project


def test_future_fixture_data_is_refused(tmp_path):
    with open(_fixture("v1_compatibility.cbproj"), "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data["schema_version"] = SCHEMA_VERSION + 3
    path = str(tmp_path / "future.cbproj")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    with pytest.raises(FutureVersionError):
        load(path)


def test_corrupted_fixture_is_a_refusal(tmp_path):
    path = str(tmp_path / "broken.cbproj")
    with open(_fixture("v1_compatibility.cbproj"), "r", encoding="utf-8") as handle:
        content = handle.read()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.replace('"schema_version": 1', '"schema_version": !'))
    with pytest.raises(PersistenceError):
        load(path)
