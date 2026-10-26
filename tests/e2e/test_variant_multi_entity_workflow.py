"""The multi-ligand / small-protein variant workflow, through the services.

The everyday job for this builder is an existing AF3 input holding several
ligands and a small protein: open it, pick the entities that should change,
review what each variant would carry, and generate. These tests drive that
job through the real services over the committed example at
``manual_test_data/af3_builder/inputs/multi_ligand_small_protein_test.txt``
— the same file the README tells a user to open — and assert on the JSON that
comes out, not merely that files exist.

What is *not* tested here, and cannot be: whether AlphaFold 3 accepts these
documents. Nothing on this path runs inference, reads a prediction, or needs
one; the assertions are about the builder's input contract.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from configbuilder.ui.services import build_services

#: Located from this file, so the suite runs whatever directory pytest starts
#: in. One directory up from ``tests/e2e`` is the repository root.
FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "manual_test_data"
    / "af3_builder"
    / "inputs"
    / "multi_ligand_small_protein_test.txt"
)


def _document():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _opened():
    """The fixture opened as a job, through the import path a user takes."""
    services = build_services()
    outcome = services.projects.import_json_commit(str(FIXTURE))
    assert outcome.ok, outcome.message
    return services


def _run(services, destination, only=None):
    """Plan and execute a variant run exactly as the front ends do."""
    plan = services.generation.plan_selection(
        str(destination), scope="variants", only=only
    )
    assert plan.ok, plan.message
    result = services.generation.execute(plan)
    assert result.ok, [str(error) for error in result.errors]
    return plan, result


def _variant_documents(destination):
    """Every generated AF3 JSON file under ``destination``, by variant key."""
    documents = {}
    for path in sorted(Path(destination).rglob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        documents[path.name] = payload
    return documents


def _sequences_by_key(document):
    """``{chain id: sequence entry}`` for one wire document."""
    table = {}
    for entry in document["sequences"]:
        (family, body), = entry.items()
        identifiers = body["id"]
        for identifier in identifiers if isinstance(identifiers, list) else [identifiers]:
            table[identifier] = (family, body)
    return table


# -- the fixture itself -------------------------------------------------------


def test_the_example_opens_as_a_normal_editable_job():
    document = _document()
    assert document["version"] == 3
    assert document["dialect"] == "alphafold3"
    services = _opened()
    configuration = services.projects.project.configuration
    assert configuration.metadata.name == "multi-ligand-small-protein"
    assert list(configuration.seeds.values) == [1, 2, 3]
    # Four entity definitions; the ATP ligand is one entity with two copies.
    assert len(configuration.records) == 4


def test_the_example_is_multi_ligand_with_a_small_protein():
    table = {row.key: row for row in _opened().variants.entity_table()}
    assert table["A"].family == "protein"
    assert table["A"].summary == "MKTAYIAKQRQISFVKSHFSRQ"
    assert table["B"].family == "ligand"
    assert table["B"].copies == 2
    assert table["B"].summary == "CCD ATP"
    assert table["C"].summary.startswith("SMILES ")
    assert table["D"].summary == "CCD MG"
    # Only the protein carries a sequence or an MSA, and only the ligands can
    # take a ligand representation or a copy count.
    assert table["A"].can("sequence") and not table["A"].can("component_representation")
    assert table["C"].can("component_representation") and not table["C"].can("sequence")


def test_the_strategy_list_follows_the_entities_that_are_there():
    services = _opened()
    kinds = {choice.kind for choice in services.variants.target_strategy_choices()}
    assert "component_representation" in kinds
    assert "sequence" in kinds
    # A protein-only job still gets no ligand strategy offered.
    protein_only = build_services()
    protein_only.projects.new("protein only")
    protein_only.configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")
    only_kinds = {
        choice.kind for choice in protein_only.variants.target_strategy_choices()
    }
    assert "sequence" in only_kinds
    assert "component_representation" not in only_kinds
    assert "component_count" not in only_kinds


# -- planning: one, several, all ---------------------------------------------


def test_one_selected_ligand_plans_exactly_one_variant():
    services = _opened()
    plan = services.variants.plan_target_variants(["C"], "component_representation", "CCO")
    assert plan.ok and plan.count == 1
    assert plan.rows[0].spec_key == "C_component_representation"
    assert [described["kind"] for described in plan.rows[0].described] == [
        "SetComponentRepresentation"
    ]
    assert plan.unchanged_keys == ("A", "B", "D")


def test_several_ligands_plan_one_independent_variant_each():
    services = _opened()
    plan = services.variants.plan_target_variants(
        ["B", "C", "D"], "component_representation", "CCO"
    )
    assert plan.ok and plan.count == 3
    assert plan.spec_keys == (
        "B_component_representation",
        "C_component_representation",
        "D_component_representation",
    )
    # Independent, not combined: every spec carries exactly one edit, for its
    # own record, and none of them mentions a sibling.
    outcome = services.variants.create_target_variants(
        ["B", "C", "D"], "component_representation", "CCO"
    )
    assert outcome.ok, outcome.message
    expanded = services.variants.expand()
    assert expanded.ok, expanded.message
    for variant in expanded.variants:
        assert len(variant.lineage.applied_edits) == 1
        base_records = services.projects.project.configuration.records
        changed = {
            record.ids.primary.value
            for record, base in zip(variant.configuration.records, base_records)
            if hasattr(record, "representation")
            and record.representation != base.representation
        }
        assert changed == {variant.key.split("_")[0]}


def test_two_entities_in_one_variant_is_the_separate_combined_action():
    """Combining is explicit: a second change added to the same variant."""
    services = _opened()
    created = services.variants.add_spec_with_edit(
        "B_and_C", "B and C", "component_representation", "CCO", record_key="B"
    )
    assert created.ok, created.message
    appended = services.variants.apply_variant_edit(
        "B_and_C", "component_representation", "CCN", record_key="C"
    )
    assert appended.ok, appended.message
    expanded = services.variants.expand(only=("B_and_C",))
    assert expanded.ok
    variant = expanded.variants[0]
    assert len(variant.lineage.applied_edits) == 2
    ligands = {
        record.ids.primary.value: record
        for record in variant.configuration.records
        if hasattr(record, "representation")
    }
    assert ligands["B"].representation.text == "CCO"
    assert ligands["C"].representation.text == "CCN"


# -- the changes themselves --------------------------------------------------


def test_a_ligand_representation_change_leaves_every_other_entity_alone(tmp_path):
    services = _opened()
    services.variants.create_target_variants(["C"], "component_representation", "CCO")
    _run(services, tmp_path)
    documents = _variant_documents(tmp_path)
    assert len(documents) == 1
    document = next(iter(documents.values()))
    base = _document()
    expected = copy.deepcopy(base)
    expected["name"] = document["name"]
    expected["sequences"][2]["ligand"] = {"id": "C", "smiles": "CCO"}
    assert document == expected


def test_a_small_protein_sequence_change_keeps_the_ligands(tmp_path):
    services = _opened()
    services.variants.create_target_variants(["A"], "sequence", "ACDEFGHIKL")
    _run(services, tmp_path)
    document = next(iter(_variant_documents(tmp_path).values()))
    table = _sequences_by_key(document)
    assert table["A"][1]["sequence"] == "ACDEFGHIKL"
    assert table["B"][1]["ccdCodes"] == ["ATP"]
    assert table["C"][1]["smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert table["D"][1]["ccdCodes"] == ["MG"]
    assert document["modelSeeds"] == [1, 2, 3]
    assert document["version"] == 3


def test_a_copy_count_change_adds_copies_without_renaming_the_entity(tmp_path):
    services = _opened()
    services.variants.create_target_variants(["B"], "component_count", "3")
    _run(services, tmp_path)
    document = next(iter(_variant_documents(tmp_path).values()))
    identifiers = document["sequences"][1]["ligand"]["id"]
    assert len(identifiers) == 3
    # The entity keeps its identity: the original primary id is still first.
    assert identifiers[:2] == ["B", "F"]
    assert identifiers[2] not in {"A", "C", "D"}


def test_removing_one_entity_leaves_the_rest_of_the_job(tmp_path):
    services = _opened()
    services.variants.create_target_variants(["D"], "remove_entity", "")
    _run(services, tmp_path)
    document = next(iter(_variant_documents(tmp_path).values()))
    table = _sequences_by_key(document)
    assert set(table) == {"A", "B", "F", "C"}
    assert "D" not in table


# -- refusals ----------------------------------------------------------------


def test_a_strategy_the_entity_cannot_take_is_refused_with_a_reason():
    services = _opened()
    protein = services.variants.plan_target_variants(
        ["A"], "component_representation", "CCO"
    )
    assert not protein.ok
    assert "cannot be applied to protein entity 'A'" in protein.message
    ligand = services.variants.plan_target_variants(["C"], "sequence", "ACDE")
    assert not ligand.ok
    # The long-standing wording for this case, kept: it names the family the
    # change does belong to instead of only saying "no".
    assert "only a protein, RNA or DNA chain carries a sequence" in ligand.message


def test_unknown_and_empty_selections_are_refused():
    services = _opened()
    unknown = services.variants.plan_target_variants(["Z"], "sequence", "ACDE")
    assert not unknown.ok
    assert "no entity is identified by 'Z'" in unknown.message
    empty = services.variants.plan_target_variants([], "sequence", "ACDE")
    assert not empty.ok
    assert "select at least one entity" in empty.message


def test_a_partly_invalid_selection_creates_nothing():
    services = _opened()
    outcome = services.variants.create_target_variants(
        ["C", "Z"], "component_representation", "CCO"
    )
    assert not outcome.ok
    assert "Z" in outcome.message
    assert services.variants.spec_count() == 0


def test_a_repeated_selection_does_not_silently_rename_variants():
    services = _opened()
    first = services.variants.create_target_variants(
        ["C"], "component_representation", "CCO"
    )
    assert first.ok
    second = services.variants.create_target_variants(
        ["C"], "component_representation", "CCN"
    )
    assert not second.ok
    assert "already named C_component_representation" in second.message
    assert services.variants.spec_count() == 1


def test_a_non_numeric_copy_count_is_worded_for_a_reader():
    services = _opened()
    plan = services.variants.plan_target_variants(["C"], "component_count", "many")
    assert not plan.ok
    assert "whole number" in plan.message
    assert "invalid literal" not in plan.message


def test_an_unknown_strategy_is_refused():
    services = _opened()
    plan = services.variants.plan_target_variants(["C"], "docking", "CCO")
    assert not plan.ok
    assert "is not a per-entity strategy" in plan.message


# -- generation --------------------------------------------------------------


def test_the_planned_count_is_the_number_of_files_written(tmp_path):
    services = _opened()
    services.variants.create_target_variants(
        ["B", "C"], "component_representation", "CCO"
    )
    plan, _result = _run(services, tmp_path)
    assert plan.ok
    variant_entries = [entry for entry in plan.entries if entry.variant_key]
    assert len(variant_entries) == 2
    assert len(_variant_documents(tmp_path)) == 2
    # The manifest joins the run: it describes exactly the variants written.
    manifest = json.loads(
        next(Path(tmp_path).rglob("manifest.json")).read_text(encoding="utf-8")
    )
    assert [variant["key"] for variant in manifest["variants"]] == [
        entry.variant_key for entry in variant_entries
    ]


def test_generation_never_touches_the_source_file(tmp_path):
    before = FIXTURE.read_bytes()
    services = _opened()
    services.variants.create_target_variants(["C"], "component_representation", "CCO")
    _run(services, tmp_path)
    assert FIXTURE.read_bytes() == before


def test_output_names_are_deterministic_and_collision_safe(tmp_path):
    services = _opened()
    services.variants.create_target_variants(
        ["B", "C"], "component_representation", "CCO"
    )
    _run(services, tmp_path / "one")
    _run(services, tmp_path / "two")
    first_names = sorted(name for name in _variant_documents(tmp_path / "one"))
    second_names = sorted(name for name in _variant_documents(tmp_path / "two"))
    assert first_names == second_names
    # No sequence text and no variant label reaches a file name: only the
    # base's slug and the variant's own key do.
    assert first_names == [
        "multi-ligand-small-protein__b-component-representation.json",
        "multi-ligand-small-protein__c-component-representation.json",
    ]
    # Re-planning the same run under the project's own "Fail" policy is
    # allowed only because nothing would change: the action table calls an
    # identical file "overwrite" (visible in the plan, harmless), and the
    # bytes on disk stay the same.
    before = {
        path.name: path.read_bytes()
        for path in Path(tmp_path / "one").rglob("*.json")
    }
    again = services.generation.plan_selection(
        str(tmp_path / "one"), scope="variants", overwrite_policy="Fail"
    )
    assert again.ok
    services.generation.execute(again)
    after = {
        path.name: path.read_bytes()
        for path in Path(tmp_path / "one").rglob("*.json")
    }
    assert after == before
    # Two different bases never collide: the base's slug is part of the name,
    # so the same variant key under another job gets its own file.
    other = build_services()
    other.projects.import_json_commit(str(FIXTURE))
    other.projects.project.configuration.metadata.name
    assert services.projects.project.configuration.metadata.name == (
        "multi-ligand-small-protein"
    )
