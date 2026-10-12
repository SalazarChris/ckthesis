"""Service-layer pins for the 2026-10-08 entity-editing hardening pass.

One test per defect of ``JSON_BUILDER_AUDIT_AND_FINALIZATION.md`` section H,
each driving the real service the menu drives. Every defect here is the same
shape: an operation the model cannot perform for the chosen record escaped as
a Python exception (``AttributeError`` / ``SequenceTextError``) instead of the
result object every service operation promises.

- BUG-020  ``update_record`` blew up on a sequence change aimed at a ligand
- BUG-021  a wrong-alphabet variant sequence killed the session
- BUG-022  ``validate_all`` let an unexpandable variant escape as a traceback
- BUG-023  ``RemoveModification`` on a record with no modification list
- BUG-025  the variant remove-modification picker indexed the wrong list
"""

from __future__ import annotations

from configbuilder.identity import EntityId
from configbuilder.model import ComponentCode, Position
from configbuilder.ui.services import build_services
from configbuilder.variants import AddModification
from configbuilder.variants.edits import EditError, RemoveModification, apply_edit

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"
RNA = "ACGUACGU"


def _services():
    return build_services()


# -- BUG-020: a sequence change aimed at a ligand ----------------------------


def test_a_sequence_change_on_a_ligand_is_refused_not_raised():
    """``ComponentRecord`` has no ``with_sequence``; requesting one used to
    escape as ``AttributeError`` out of ``update_record``."""
    services = _services()
    services.projects.new("probe")
    assert services.configuration.add_record("ligand", representation="ATP").ok

    outcome = services.configuration.update_record("A", sequence="ACDEFG")

    assert outcome.ok is False
    assert "ligand" in outcome.message and "no sequence" in outcome.message
    # nothing changed: same representation, same identity
    record = services.projects.project.configuration.records[0]
    assert record.representation.codes[0].value == "ATP"
    assert record.ids.primary.value == "A"


def test_a_description_change_on_a_ligand_still_works():
    """The guard is about the *sequence* field only; a ligand's description is
    a legal edit (spec §4) and must keep working."""
    services = _services()
    services.projects.new("probe")
    services.configuration.add_record("ligand", representation="ATP")

    outcome = services.configuration.update_record("A", description="cofactor")

    assert outcome.ok, outcome.message
    record = services.projects.project.configuration.records[0]
    assert record.description.value == "cofactor"


def test_a_sequence_change_on_a_multi_copy_ligand_is_refused_too():
    services = _services()
    services.projects.new("probe")
    services.configuration.add_record("ligand", representation="ATP", copies=3)

    outcome = services.configuration.update_record("B", sequence="ACDEFG")  # a copy key

    assert outcome.ok is False
    assert "ligand" in outcome.message


# -- BUG-021: a wrong-alphabet sequence at the variant prompt ----------------


def test_a_variant_sequence_in_the_wrong_alphabet_is_refused_not_raised():
    """``SequenceTextError`` derives from ``ModelError``, *not* ``ValueError``:
    the picker's factor conversion caught only ``ValueError``, so an ordinary
    wrong-alphabet answer escaped all the way out of the menu."""
    services = _services()
    services.projects.new("probe")
    services.configuration.add_record("rna", RNA)
    services.variants.add_spec("V1", "V1", ())

    outcome = services.variants.apply_variant_edit(
        "V1", "sequence", "ACDEFG", record_key="A"  # protein letters on an RNA chain
    )

    assert outcome.ok is False
    assert "alphabet" in outcome.message
    assert services.projects.project.specs[0].edits == ()  # nothing was recorded


def test_append_factor_refuses_a_wrong_alphabet_too():
    """The same refusal through the direct route (a CLI or a front end)."""
    services = _services()
    services.projects.new("probe")
    services.configuration.add_record("dna", "ATGC")
    services.variants.add_spec("V1", "V1", ())

    outcome = services.variants.append_factor("V1", "sequence", "ZZZZ", record_key="A")

    assert outcome.ok is False
    assert services.projects.project.specs[0].edits == ()


def test_a_variant_sequence_aimed_at_a_ligand_says_so():
    """The record exists, it is simply not a polymer — the refusal must say
    that instead of "no record is identified by"."""
    services = _services()
    services.projects.new("probe")
    services.configuration.add_record("ligand", representation="ATP")
    services.variants.add_spec("V1", "V1", ())

    outcome = services.variants.apply_variant_edit(
        "V1", "sequence", PROTEIN, record_key="A"
    )

    assert outcome.ok is False
    assert "ligand" in outcome.message


# -- the modification-carrier guard (the prevention behind BUG-022/023) ------


def test_a_modification_edit_aimed_at_a_ligand_is_refused_when_composed():
    services = _services()
    services.projects.new("probe")
    services.configuration.add_record("ligand", representation="ATP")
    services.variants.add_spec("V1", "V1", ())

    added = services.variants.apply_variant_edit(
        "V1", "add_modification", ("SEP", 1), record_key="A"
    )
    removed = services.variants.apply_variant_edit(
        "V1", "remove_modification", 0, record_key="A"
    )

    assert added.ok is False and "ligand" in added.message
    assert removed.ok is False and "ligand" in removed.message
    assert services.projects.project.specs[0].edits == ()


# -- BUG-023: RemoveModification on a record with no modification list -------


def test_remove_modification_on_a_non_polymer_is_an_editerror():
    """Expansion must report a refusal, not raise ``AttributeError``."""
    services = _services()
    services.projects.new("probe")
    services.configuration.add_record("ligand", representation="ATP")
    base = services.projects.project.configuration

    try:
        apply_edit(RemoveModification(EntityId("A"), 0), base)
    except EditError as error:
        assert "not a polymer" in str(error)
    else:  # pragma: no cover - the failure path the test exists for
        raise AssertionError("RemoveModification on a ligand did not refuse")


# -- BUG-022: an unexpandable committed variant ---------------------------


def _legacy_spec_services():
    """A project holding a spec that can no longer expand.

    This is what a project file written by an older build (or hand-edited)
    looks like: the edit targets a ligand, which the *current* pickers refuse
    to compose, but the stored spec still has to be survivable.
    """
    services = _services()
    services.projects.new("legacy")
    services.configuration.add_record("ligand", representation="ATP")
    services.configuration.add_record("protein", PROTEIN)
    outcome = services.variants.add_spec(
        "V1", "V1", (AddModification(EntityId("A"), ComponentCode("SEP"), Position(1)),)
    )
    assert outcome.ok, outcome.message
    return services


def test_validate_all_reports_an_unexpandable_variant_instead_of_raising():
    services = _legacy_spec_services()

    outcome = services.validation.validate_all()

    assert outcome.failure_reason == "expansion_failed"
    assert "not a polymer" in outcome.message
    assert outcome.base_report is not None  # the base half is still reported
    assert outcome.variant_reports == {}


def test_preview_and_generation_refuse_the_unexpandable_variant_cleanly():
    services = _legacy_spec_services()

    preview = services.variants.preview("V1")
    assert preview.ok is False and "not a polymer" in preview.message

    plan = services.generation.plan("output")
    assert plan.ok is False
    assert "not a polymer" in plan.message
    # the base is still readable: the refusal is about the variant only
    assert services.generation.show_json(None)[0] is not None


# -- BUG-025: the variant remove-modification picker's index space -----------


def test_modification_summary_indices_address_the_expanded_record():
    """The picker must offer the indices ``RemoveModification`` applies.

    The base already carries a modification, so the spec's own edit index (0)
    and the expanded index of the row the user sees differ. The summary must
    report the expanded one; applying it must remove exactly the offered row
    and leave the base's modification alone (BUG-025).
    """
    services = _services()
    services.projects.new("probe")
    services.configuration.add_record("protein", PROTEIN)
    services.configuration.add_modification("A", "SEP", 3)  # the base's own PTM
    services.variants.add_spec("V1", "V1", ())
    assert services.variants.apply_variant_edit(
        "V1", "add_modification", ("TPO", 5), record_key="A"
    ).ok

    rows = services.variants.modification_summary("V1")
    labels = {label: index for index, label in rows}
    assert labels == {"A @ 3 (SEP)": 0, "A @ 5 (TPO)": 1}

    tpo_index = labels["A @ 5 (TPO)"]
    assert services.variants.apply_variant_edit(
        "V1", "remove_modification", tpo_index, record_key="A"
    ).ok

    expanded = services.variants.preview("V1")
    assert expanded.ok, expanded.message
    remaining = [
        (modification.code.value, modification.position.value)
        for modification in expanded.variants[0].configuration.records[0].modifications
    ]
    assert remaining == [("SEP", 3)]  # the picked row went, the base's stayed
    base_remaining = [
        (modification.code.value, modification.position.value)
        for modification in services.projects.project.configuration.records[0].modifications
    ]
    assert base_remaining == [("SEP", 3)]  # and the base never moved


def test_modification_summary_is_empty_when_the_variant_cannot_expand():
    services = _legacy_spec_services()
    assert services.variants.modification_summary("V1") == []
