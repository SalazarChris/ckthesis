"""Batch variant generation from a sequence file — service level.

The contract under test: one file sequence → one independent variant
spec of the shape ``base + AddRecord(<that sequence>)``. The base is
never mutated; variants never accumulate one another; identifiers come
from the project's registry (never hand-assigned); the DNA duplex rides
through untouched as part of the base.
"""

from __future__ import annotations

import os

import pytest

from configbuilder.app.configuration_service import ConfigurationService
from configbuilder.app.project_service import ProjectService
from configbuilder.app.validation_service import ValidationService
from configbuilder.app.variant_service import VariantService
from configbuilder.variants import AddRecord


def _services():
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    variants = VariantService(projects)
    validation = ValidationService(projects)
    projects.new("Batch Job")
    configuration.set_format_target(version=3, evidence="PIN-001")
    configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")
    return projects, configuration, variants, validation


def _write(tmp_path, payload: str, name: str = "seqs.txt") -> str:
    path = os.path.join(str(tmp_path), name)
    with open(path, "w", newline="") as handle:
        handle.write(payload)
    return path


def _expanded_variants(variants, projects):
    outcome = variants.expand()
    assert outcome.ok, outcome.message
    return {variant.key: variant for variant in outcome.variants}


# -- the core shape ---------------------------------------------------------------


def test_one_sequence_produces_exactly_one_variant(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\n")
    outcome = variants.generate_from_file(path)
    assert outcome.ok, outcome.message
    specs = projects._specs()
    assert [spec.key for spec in specs] == ["batch_01"]
    assert [type(edit) for edit in specs[0].edits] == [AddRecord]
    assert _expanded_variants(variants, projects)["batch_01"] is not None


def test_multiple_sequences_produce_exactly_that_many_variants(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\nMSTNPKK\n")
    outcome = variants.generate_from_file(path)
    assert outcome.ok, outcome.message
    assert [spec.key for spec in projects._specs()] == [
        "batch_01",
        "batch_02",
        "batch_03",
    ]
    assert set(_expanded_variants(variants, projects)) == {
        "batch_01",
        "batch_02",
        "batch_03",
    }


def test_blank_lines_are_ignored(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\n\n   \nGKKIGYS\n\n")
    outcome = variants.generate_from_file(path)
    assert outcome.ok, outcome.message
    assert [spec.key for spec in projects._specs()] == ["batch_01", "batch_02"]


def test_each_variant_contains_exactly_its_own_sequence(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\nMSTNPKK\n")
    assert variants.generate_from_file(path).ok
    base_records = len(projects.project.configuration.records)
    for variant in _expanded_variants(variants, projects).values():
        records = variant.configuration.records
        # the base's records plus exactly one new protein record
        assert len(records) == base_records + 1
        added = records[-1]
        assert added.sequence.text in ("MSTNPKP", "GKKIGYS", "MSTNPKK")


def test_variants_never_accumulate_one_another(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\nMSTNPKK\n")
    assert variants.generate_from_file(path).ok
    expanded = _expanded_variants(variants, projects)

    def added_sequences(variant):
        base_count = len(projects.project.configuration.records)
        return tuple(record.sequence.text for record in variant.configuration.records[base_count:])

    assert added_sequences(expanded["batch_01"]) == ("MSTNPKP",)
    assert added_sequences(expanded["batch_02"]) == ("GKKIGYS",)
    assert added_sequences(expanded["batch_03"]) == ("MSTNPKK",)
    # B does not contain A's sequence; C contains neither.
    assert "MSTNPKP" not in added_sequences(expanded["batch_02"])
    assert "MSTNPKP" not in added_sequences(expanded["batch_03"])
    assert "GKKIGYS" not in added_sequences(expanded["batch_03"])


def test_base_configuration_is_unchanged_after_batch(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\nMSTNPKK\n")
    before = projects.project.configuration
    base_records = tuple(before.records)
    base_registry = [entity.value for entity in before.identity.order()]
    assert variants.generate_from_file(path).ok
    after = projects.project.configuration
    assert after is before
    assert after.records == base_records
    assert [entity.value for entity in after.identity.order()] == base_registry


def test_editing_one_variant_touches_neither_base_nor_siblings(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\n")
    assert variants.generate_from_file(path).ok
    expanded = _expanded_variants(variants, projects)
    first = expanded["batch_01"]
    second = expanded["batch_02"]
    base = projects.project.configuration
    # Mutate the expanded variant's records tuple; the base and the
    # sibling must be untouched (independence of materialised results).
    mutated = first.configuration.with_records(
        first.configuration.records + first.configuration.records[:1]
    )
    assert len(base.records) == 1
    assert len(second.configuration.records) == 2
    assert mutated is not first.configuration
    # and re-expanding gives a fresh, unmutated result again
    reexpanded = _expanded_variants(variants, projects)["batch_01"]
    assert len(reexpanded.configuration.records) == 2


def test_identifiers_are_registry_owned_and_unique_across_the_batch(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\nMSTNPKK\n")
    assert variants.generate_from_file(path).ok
    base_ids = [entity.value for entity in projects.project.configuration.identity.order()]
    expanded = _expanded_variants(variants, projects)
    seen_new = []
    for variant in expanded.values():
        records = variant.configuration.records
        new_records = records[len(base_ids):]
        assert len(new_records) == 1
        new_ids = [entity.value for entity in new_records[0].ids]
        # registry-owned: every id resolves in the variant's registry
        for value in new_ids:
            assert variant.configuration.identity.is_taken(value)
        # distinct from the base's ids and from every sibling's new ids
        for value in new_ids:
            assert value not in base_ids
            seen_new.append(value)
    assert len(seen_new) == len(set(seen_new))


def test_existing_dna_duplex_rides_through_untouched(tmp_path):
    projects, configuration, variants, _ = _services()
    configuration.add_record("dna", "ATGC")
    base = projects.project.configuration
    dna_before = [
        record.sequence.text
        for record in base.records
        if type(record).__name__ == "FamilyCRecord"
    ]
    assert dna_before == ["ATGC", "GCAT"]  # the duplex, as built by the base path
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\n")
    assert variants.generate_from_file(path).ok
    expanded = _expanded_variants(variants, projects)
    for variant in expanded.values():
        dna = [
            record.sequence.text
            for record in variant.configuration.records
            if type(record).__name__ == "FamilyCRecord"
        ]
        assert dna == ["ATGC", "GCAT"]  # both strands, ids and order intact
        ids = [entity.value for entity in variant.configuration.identity.order()]
        assert ids[:3] == ["A", "B", "C"]  # base ids survive expansion unchanged


def test_invalid_sequence_refuses_the_whole_batch_with_line_numbers(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\nacdx\nGKKIGYS\n")
    outcome = variants.generate_from_file(path)
    assert not outcome.ok
    assert "line 2" in outcome.message  # the invalid entry is named
    assert "acdx" in outcome.message.lower() or "outside its alphabet" in outcome.message
    assert projects._specs() == ()  # nothing was committed


def test_empty_and_blank_only_files_report_no_sequences(tmp_path):
    projects, configuration, variants, _ = _services()
    empty = _write(tmp_path, "", name="empty.txt")
    outcome = variants.generate_from_file(empty)
    assert not outcome.ok
    assert "no sequences" in outcome.message
    blank = _write(tmp_path, "\n \n\t\n", name="blank.txt")
    outcome = variants.generate_from_file(blank)
    assert not outcome.ok
    assert "no sequences" in outcome.message
    assert projects._specs() == ()


def test_duplicate_sequences_are_refused(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\nMSTNPKP\n")
    outcome = variants.generate_from_file(path)
    assert not outcome.ok
    assert "duplicate" in outcome.message.lower()
    assert projects._specs() == ()


def test_missing_file_gives_a_clear_error(tmp_path):
    projects, configuration, variants, _ = _services()
    outcome = variants.generate_from_file(os.path.join(str(tmp_path), "absent.txt"))
    assert not outcome.ok
    assert "cannot be read" in outcome.message


# -- the reuse contract ------------------------------------------------------------


def test_batch_specs_are_plain_variant_specs_editable_and_removable(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "MSTNPKP\n")
    assert variants.generate_from_file(path).ok
    # A generated variant is a plain spec: editable and removable through
    # the standard service routes — nothing batch-specific remains.
    outcome = variants.remove_spec("batch_01")
    assert outcome.ok
    assert projects._specs() == ()


def test_generated_variants_pass_variant_validation(tmp_path):
    projects, configuration, variants, validation = _services()
    path = _write(tmp_path, "MSTNPKP\nGKKIGYS\nMSTNPKK\n")
    assert variants.generate_from_file(path).ok
    result = validation.validate_all()
    assert not result.base_report.blocking()
    for key, report in result.variant_reports.items():
        assert not report.blocking(), (key, [f.user_message for f in report.blocking()])
