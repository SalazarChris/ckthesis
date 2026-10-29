"""Manifest tests (IMPLEMENTATION_PLAN.md §13.6, §13.7).

Everything except ``run_info`` is a deterministic function of the inputs:
same project, same plan — byte-identical manifest data. ``run_info`` is
the single home of time-varying values and is asserted to stay separate.
"""

from __future__ import annotations

import json

import pytest

from configbuilder.output.manifest import (
    MANIFEST_SCHEMA_VERSION,
    ManifestData,
    build_manifest,
    run_info,
)
from configbuilder.output.policies import OverwritePolicy, PathPolicy
from configbuilder.serialize import encode


class _VariantRecord:
    """The per-variant manifest record app assembles (plan §13.6 fields)."""

    def __init__(self, key, label, declared_factors, applied_edits, file_name, fingerprint):
        self.key = key
        self.label = label
        self.declared_factors = declared_factors
        self.applied_edits = applied_edits
        self.file_name = file_name
        self.fingerprint = fingerprint


def _variants():
    return (
        _VariantRecord("wt", "wild type", [], [], "p__wt.json", "aa" * 32),
        _VariantRecord(
            "mut",
            "mutant",
            ["sequence"],
            [{"kind": "SetSequence", "key": "A"}],
            "p__mut.json",
            "bb" * 32,
        ),
    )


def test_manifest_data_is_deterministic_across_calls():
    first = build_manifest(
        project_name="My Project",
        base_fingerprint="cf" * 32,
        format_version=3,
        variants=_variants(),
        seed_set=[1, 2, 3],
        path_policy=PathPolicy("CopyIntoAssets"),
        overwrite_policy=OverwritePolicy("Fail"),
    )
    second = build_manifest(
        project_name="My Project",
        base_fingerprint="cf" * 32,
        format_version=3,
        variants=_variants(),
        seed_set=[1, 2, 3],
        path_policy=PathPolicy("CopyIntoAssets"),
        overwrite_policy=OverwritePolicy("Fail"),
    )
    assert encode(first.data) == encode(second.data)


def test_manifest_carries_every_documented_field():
    manifest = build_manifest(
        project_name="My Project",
        base_fingerprint="cf" * 32,
        format_version=3,
        variants=_variants(),
        seed_set=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        path_policy=PathPolicy("CopyIntoAssets"),
        overwrite_policy=OverwritePolicy("Fail"),
    )
    data = manifest.data
    assert data["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert data["project_name"] == "My Project"
    assert data["base_fingerprint"] == "cf" * 32
    assert data["format_version"] == 3
    assert "contract_pin_record" in data  # None while the probe is unrun
    assert data["path_policy"] == "CopyIntoAssets"
    assert data["overwrite_policy"] == "Fail"
    assert data["seed_set"] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert "builder_version" in data
    variant = data["variants"][1]
    assert variant["key"] == "mut"
    assert variant["label"] == "mutant"
    assert variant["declared_factors"] == ["sequence"]
    assert variant["applied_edits"] == [{"kind": "SetSequence", "key": "A"}]
    assert variant["file_name"] == "p__mut.json"
    assert variant["fingerprint"] == "bb" * 32


def test_manifest_json_round_trips_stably():
    manifest = build_manifest(
        project_name="P",
        base_fingerprint="ab" * 32,
        format_version=3,
        variants=_variants(),
        seed_set=[1],
        path_policy=PathPolicy("CopyIntoAssets"),
        overwrite_policy=OverwritePolicy("Fail"),
    )
    restored = json.loads(encode(manifest.data).decode("utf-8"))
    assert encode(restored) == encode(manifest.data)


def test_the_manifest_schema_is_exactly_the_documented_fields():
    """The module says which fields are written; the file must match.

    ``manifest.py``'s docstring lists them, and ``run_info`` is documented as
    not written. The audit found the prose claiming a per-run block that the
    file never contained — a manifest that disagreed with its own description.
    """
    manifest = build_manifest(
        project_name="P",
        base_fingerprint="ab" * 32,
        format_version=3,
        variants=_variants(),
        seed_set=[1],
        path_policy=PathPolicy("CopyIntoAssets"),
        overwrite_policy=OverwritePolicy("Fail"),
    )
    written = json.loads(encode(manifest.data).decode("utf-8"))

    assert sorted(written) == [
        "base_fingerprint",
        "builder_version",
        "contract_pin_record",
        "format_version",
        "overwrite_policy",
        "path_policy",
        "project_name",
        "schema_version",
        "seed_set",
        "validation_summary",
        "variants",
    ]
    # run_info is available to callers and deliberately absent from the file.
    assert set(manifest.run_info) == {"timestamp", "host", "user", "platform", "pid"}
    assert "run_info" not in written
    assert "timestamp" not in written
    assert "host" not in written


def test_run_info_is_isolated_and_time_varying():
    info = run_info()
    assert set(info) == {"timestamp", "host", "user", "platform", "pid"}
    manifest = build_manifest(
        project_name="P",
        base_fingerprint="ab" * 32,
        format_version=3,
        variants=(),
        seed_set=[1],
        path_policy=PathPolicy("CopyIntoAssets"),
        overwrite_policy=OverwritePolicy("Fail"),
    )
    assert manifest.run_info == info or set(manifest.run_info) == set(info)
    # run_info never leaks into the deterministic part
    assert "timestamp" not in json.dumps(manifest.data)
    assert "pid" not in json.dumps(manifest.data)


def test_validation_summary_counts_are_stable():
    class _Finding:
        def __init__(self, severity):
            self.severity = type("S", (), {"name": severity})()

    class _Rule:
        def __init__(self, rule_id):
            self.rule_id = rule_id

    class _Report:
        findings = [_Finding("INFO"), _Finding("INFO"), _Finding("WARNING")]
        skipped = (_Rule("R-MSA-003"),)

    manifest = build_manifest(
        project_name="P",
        base_fingerprint="ab" * 32,
        format_version=3,
        variants=(),
        seed_set=[1],
        validation_report=_Report(),
        path_policy=PathPolicy("CopyIntoAssets"),
        overwrite_policy=OverwritePolicy("Fail"),
    )
    assert manifest.data["validation_summary"]["finding_counts"] == {"INFO": 2, "WARNING": 1}
    assert manifest.data["validation_summary"]["skipped_rules"] == ["R-MSA-003"]
