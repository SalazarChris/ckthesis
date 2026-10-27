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


# -- ligand batches: SMILES is a representation, never a sequence -------------------


def test_a_ligand_smiles_batch_builds_component_records(tmp_path):
    """A ligand file becomes ligand records with a ByNotation representation.

    Regression: the builder wrapped SMILES in ``SequenceText(..., "ligand")``,
    an unknown sequence family, so every ligand batch refused before creating
    anything. The entry's documented ``name SMILES`` name is kept: it is the
    spec's key (and so the output file's name), and a bare SMILES still gets
    a positional name.
    """
    from configbuilder.model import ByNotation, ComponentRecord

    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "first CCO\nCCC\n", name="ligands.smiles")

    outcome = variants.generate_from_file(path, family="ligand")

    assert outcome.ok, outcome.message
    assert [spec.key for spec in projects._specs()] == ["first", "ligand-1"]
    expanded = _expanded_variants(variants, projects)
    for key, smiles in (("first", "CCO"), ("ligand-1", "CCC")):
        added = expanded[key].configuration.records[-1]
        assert isinstance(added, ComponentRecord)
        assert isinstance(added.representation, ByNotation)
        assert added.representation.text == smiles
    # The base still has only its own protein.
    assert len(projects.project.configuration.records) == 1


def test_inspect_batch_file_previews_the_family_reader(tmp_path):
    projects, configuration, variants, _ = _services()
    protein = _write(tmp_path, "MSTNPKP\nGKKIGYS\n")
    preview = variants.inspect_batch_file(protein, family="protein")
    assert preview.ok
    assert preview.entries == ("MSTNPKP", "GKKIGYS")

    smiles = _write(tmp_path, "first CCO\nCCC\n", name="ligands.smiles")
    preview = variants.inspect_batch_file(smiles, family="ligand")
    assert preview.ok
    # The name is shown with the molecule it names: the entry is identified by
    # what the user wrote, not by its position in the file.
    assert preview.entries == ("first  CCO", "ligand_1  CCC")
    assert preview.planned == 2
    assert projects._specs() == ()


def test_inspect_batch_file_refuses_an_unsupported_family(tmp_path):
    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "ACGU\n")
    preview = variants.inspect_batch_file(path, family="rna")
    assert not preview.ok
    assert "not supported" in preview.message
    assert projects._specs() == ()


def test_inspect_batch_file_reports_the_planned_count_and_the_lines(tmp_path):
    """Stage 8: the preview checks the batch the way the commit will.

    A usable file reports how many variants the commit would create; an
    unusable one is refused with the offending line *before* anything is
    created, and the base keeps its identifiers and its records because the
    check runs against a discarded registry clone.
    """
    projects, configuration, variants, _ = _services()
    good = _write(tmp_path, "MSTNPKP\nGKKIGYS\n")

    preview = variants.inspect_batch_file(good, family="protein")

    assert preview.ok, preview.message
    assert preview.planned == 2

    bad = _write(tmp_path, "MSTNPKP\nACD EFG\n", name="bad.txt")
    before = projects.project.configuration
    preview = variants.inspect_batch_file(bad, family="protein")

    assert not preview.ok
    assert "line 2" in preview.message
    assert preview.entries == ("MSTNPKP", "ACD EFG"), "what was read is shown"
    assert projects._specs() == ()
    assert projects.project.configuration is before, "no record was reserved"


def test_inspect_batch_file_reports_a_key_that_already_exists(tmp_path):
    """A collision the commit would refuse is visible before the commit."""
    projects, configuration, variants, _ = _services()
    assert variants.add_spec_with_edit("batch_01", "Taken", "job_name", "x").ok
    path = _write(tmp_path, "MSTNPKP\n")

    preview = variants.inspect_batch_file(path, family="protein")

    assert not preview.ok
    assert "batch_01" in preview.message
    assert [spec.key for spec in projects._specs()] == ["batch_01"]


# -- create a spec and its first change atomically ----------------------------------


def test_add_spec_with_edit_commits_the_spec_and_its_change_together():
    projects, configuration, variants, _ = _services()
    outcome = variants.add_spec_with_edit(
        "long_loop", "Long loop", "sequence", "GGGGS", record_key="A"
    )
    assert outcome.ok, outcome.message
    spec = projects._specs()[0]
    assert spec.label == "Long loop"
    assert [type(edit).__name__ for edit in spec.edits] == ["SetSequence"]
    assert "GGGGS" not in projects.project.configuration.records[0].sequence.text


def test_add_spec_with_edit_refuses_without_leaving_a_spec():
    projects, configuration, variants, _ = _services()
    before = projects.project.configuration
    outcome = variants.add_spec_with_edit(
        "bad", "Bad", "sequence", "ACDE\nFGH", record_key="A"
    )
    assert not outcome.ok
    assert projects._specs() == ()
    assert projects.project.configuration is before


def test_add_spec_with_edit_keeps_keys_unique():
    projects, configuration, variants, _ = _services()
    assert variants.add_spec_with_edit(
        "v1", "V1", "job_name", "one"
    ).ok
    before = projects.project.configuration
    outcome = variants.add_spec_with_edit(
        "v1", "Again", "job_name", "two"
    )
    assert not outcome.ok
    assert [spec.key for spec in projects._specs()] == ["v1"]
    assert projects.project.configuration is before


# -- names: slugs, duplicates, and what a ligand file cannot say --------------------


def test_duplicate_entry_names_take_a_deterministic_suffix(tmp_path):
    """Two entries may name the same thing; both survive, in file order."""
    from configbuilder.persistence import read_smiles_file
    from configbuilder.app.batch_variants import ligand_specs_for_entries

    projects, configuration, variants, _ = _services()
    path = _write(
        tmp_path,
        "kinase-inhibitor CCO\nkinase-inhibitor c1ccccc1\n",
        name="names.smiles",
    )

    entries = read_smiles_file(path)
    specs = ligand_specs_for_entries(
        entries, projects.project.configuration.identity.clone()
    )

    assert [spec.key for spec in specs] == ["kinase-inhibitor", "kinase-inhibitor-2"]
    assert [spec.label for spec in specs] == ["kinase-inhibitor", "kinase-inhibitor"]


def test_a_name_that_cannot_be_slugged_falls_back_to_its_position(tmp_path):
    from configbuilder.persistence import read_smiles_file
    from configbuilder.app.batch_variants import ligand_specs_for_entries

    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "/ CCO\n", name="odd.smiles")

    specs = ligand_specs_for_entries(
        read_smiles_file(path), projects.project.configuration.identity.clone()
    )

    assert specs[0].key == "ligand-01"


def test_a_ccd_code_in_a_ligand_file_is_refused_rather_than_stored(tmp_path):
    """A ligand file has no CCD syntax, so a code in one is not a molecule.

    Until the notation check existed the text was stored and serialised as
    ``{"smiles": "ATP"}`` — a document AF3 refuses. It is now refused here,
    once, naming the line and the reason, and nothing is generated.
    """
    from configbuilder.app.batch_variants import BatchError, ligand_specs_for_entries
    from configbuilder.persistence import read_smiles_file

    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "atp ATP\nzinc ZN\n", name="ccd.smiles")

    outcome = variants.generate_from_file(path, family="ligand")

    assert not outcome.ok
    assert "2 of 2 ligand entries are invalid" in outcome.message
    assert repr("ATP") in outcome.message
    assert "line 1" in outcome.message and "line 2" in outcome.message
    assert "not SMILES notation" in outcome.message
    # Nothing was committed, and the base job still has only what it started
    # with: the refusal is all-or-nothing, exactly like a duplicate entry.
    assert variants.specs() == []
    assert [record.ids.primary.value for record in projects.project.configuration.records] == [
        "A"
    ]
    with pytest.raises(BatchError) as caught:
        ligand_specs_for_entries(
            read_smiles_file(path), projects.project.configuration.identity.clone()
        )
    assert "the atom 'A' in 'ATP' is not one SMILES writes without brackets" in str(
        caught.value
    )


def test_a_notation_that_is_smiles_is_still_stored_as_by_notation(tmp_path):
    """The positive half: grammar-valid notation is stored, not judged for
    chemistry — this check never claims a molecule."""
    from configbuilder.model import ByCode, ByNotation

    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "aspirin CC(=O)Oc1ccccc1C(=O)O\nzinc [Zn+2]\n", name="ok.smiles")

    assert variants.generate_from_file(path, family="ligand").ok

    expanded = _expanded_variants(variants, projects)
    for key, token in (("aspirin", "CC(=O)Oc1ccccc1C(=O)O"), ("zinc", "[Zn+2]")):
        added = expanded[key].configuration.records[-1]
        assert isinstance(added.representation, ByNotation)
        assert not isinstance(added.representation, ByCode)
        assert added.representation.text == token


def test_the_whole_file_is_refused_when_one_entry_repeats(tmp_path):
    from configbuilder.app.batch_variants import BatchError, ligand_specs_for_entries
    from configbuilder.persistence import read_smiles_file

    projects, configuration, variants, _ = _services()
    path = _write(tmp_path, "first CCO\nsecond CCO\n", name="dupes.smiles")

    with pytest.raises(BatchError) as caught:
        ligand_specs_for_entries(
            read_smiles_file(path), projects.project.configuration.identity.clone()
        )

    message = str(caught.value)
    assert "duplicate ligand entries" in message
    assert "CCO" in message
    assert "..." in message, "an ASCII ellipsis survives every console encoding"
    assert projects._specs() == ()
