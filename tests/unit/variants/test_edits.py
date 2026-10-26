"""Unit tests for the typed edit vocabulary (plan §12.1, spec §15).

Edits are immutable data; applying one never mutates the base — the
variant gets cloned registries and cloned records. These tests pin the
isolation guarantee (§12.4) and the resolve-through-identity rule (§12.2).
"""

from __future__ import annotations

import pytest

from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity
from configbuilder.model import (
    AlignmentUnpairedOnly,
    ByCode,
    ComponentCode,
    ComponentRecord,
    Configuration,
    ConfigurationMetadata,
    Explicit,
    ExplicitEmpty,
    External,
    FamilyARecord,
    FamilyBRecord,
    FormatTarget,
    IndexPair,
    Inline,
    ModificationRecord,
    PathSpec,
    Pinned,
    Position,
    Present,
    ReferenceRecord,
    SeedSet,
    SequenceText,
    SingleProvided,
    Unset,
    Unverified,
)
from configbuilder.variants import (
    EDIT_CLASSES,
    AddModification,
    AddRecord,
    EditError,
    RemoveModification,
    RemoveRecord,
    SetAlignment,
    SetComponentDefinition,
    SetComponentRepresentation,
    SetDescription,
    SetFormatTarget,
    SetJobDescription,
    SetName,
    SetReferences,
    SetSeeds,
    SetSequence,
    SetSingleAlignment,
    apply_edit,
    describe_edit,
)


def _base():
    registry = IdentityRegistry()
    a = registry.allocate().value
    b = registry.allocate().value
    return Configuration(
        metadata=ConfigurationMetadata("base job", "original description"),
        seeds=SeedSet([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        records=(
            FamilyARecord(ids=Multiplicity([a]), sequence=SequenceText("PEPTIDE", "protein")),
            FamilyBRecord(ids=Multiplicity([b]), sequence=SequenceText("GGCC", "rna")),
        ),
        identity=registry,
    )


# -- resolution through identity (plan §12.2) ---------------------------------


def test_edits_carry_entity_id_keys_not_positions():
    edit = SetSequence(EntityId("A"), SequenceText("MUTATED", "protein"))
    assert edit._record_key == EntityId("A")
    assert "A" in repr(edit)


def test_edit_vocabulary_is_closed_and_frozen():
    # Spec §15 lists job name and descriptions among variant-relevant
    # fields, so the vocabulary is the plan §12.1 grammar (16 edits) plus
    # SetJobDescription and the quantity-series SetComponentCount — 18.
    assert len(EDIT_CLASSES) == 18
    for cls in EDIT_CLASSES:
        assert cls.__slots__, cls  # every edit declares its fields as slots


def test_apply_edit_argument_order_is_edit_first():
    base = _base()
    variant = apply_edit(SetName("renamed"), base)
    assert variant.metadata.name == "renamed"
    assert base.metadata.name == "base job"


# -- isolation: the base is never mutated (plan §12.4) ------------------------


def test_set_sequence_never_mutates_the_base():
    base = _base()
    variant = apply_edit(SetSequence(EntityId("A"), SequenceText("MUTATED", "protein")), base)
    assert variant.records[0].sequence.text == "MUTATED"
    assert base.records[0].sequence.text == "PEPTIDE"
    assert variant.records[0] is not base.records[0]


def test_job_description_edit_keeps_base_intact():
    base = _base()
    variant = apply_edit(SetJobDescription(Unset()), base)
    assert variant.metadata.description == Unset()
    # A bare string constructor argument is normalised to Present, so the
    # state algebra holds everywhere (persistence round-trips depend on it).
    assert base.metadata.description == Present("original description")


def test_record_description_edit_targets_one_record():
    base = _base()
    variant = apply_edit(SetDescription(EntityId("A"), Present("chain A only")), base)
    assert variant.records[0].description == Present("chain A only")
    assert variant.records[1].description == base.records[1].description
    assert base.records[0].description != Present("chain A only")


def test_record_description_can_go_explicit_empty_and_unset():
    base = _base()
    variant = apply_edit(SetDescription(EntityId("A"), ExplicitEmpty()), base)
    assert variant.records[0].description == ExplicitEmpty()
    variant = apply_edit(SetDescription(EntityId("A"), Unset()), base)
    assert variant.records[0].description == Unset()


def test_add_record_allocates_only_in_the_variant():
    base = _base()
    # The edit's record carries an identifier that is free in the base; the
    # registry reserves it for the variant (never the other way around).
    fresh = FamilyARecord(ids=Multiplicity(["C"]), sequence=SequenceText("KINASE", "protein"))
    variant = apply_edit(AddRecord(fresh), base)
    assert len(base.records) == 2
    assert len(variant.records) == 3
    assert variant.records[2].ids.primary.value == "C"
    assert base.identity.is_taken("C") is False
    assert variant.identity.is_taken("C") is True


def test_add_record_refuses_an_already_assigned_identifier():
    base = _base()
    clashing = FamilyARecord(ids=Multiplicity(["A"]), sequence=SequenceText("X", "protein"))
    with pytest.raises(EditError, match="already assigned"):
        apply_edit(AddRecord(clashing), base)


def test_remove_record_releases_only_in_the_variant():
    base = _base()
    variant = apply_edit(RemoveRecord(EntityId("B")), base)
    assert [r.ids.primary.value for r in variant.records] == ["A"]
    assert base.records[1].ids.primary.value == "B"
    assert base.identity.is_taken("B") is True


def test_seeds_edit_replaces_the_whole_list():
    base = _base()
    variant = apply_edit(SetSeeds([9, 9, 9]), base)
    assert list(variant.seeds.values) == [9, 9, 9]
    assert list(base.seeds.values) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_component_definition_edit_supports_inline_external_and_removal():
    base = _base()
    variant = apply_edit(SetComponentDefinition(Inline("LIG")), base)
    assert variant.component_definition == Inline("LIG")
    assert base.component_definition is None
    variant = apply_edit(SetComponentDefinition(External(PathSpec("ccd.cif"))), variant)
    assert variant.component_definition == External(PathSpec("ccd.cif"))
    variant = apply_edit(SetComponentDefinition(None), variant)
    assert variant.component_definition is None


def test_format_target_edit():
    base = _base()
    variant = apply_edit(SetFormatTarget(FormatTarget(version_selection=Pinned(4))), base)
    assert variant.format_target.version_selection == Pinned(4)
    assert base.format_target.version_selection == Unverified()


# -- modifications ------------------------------------------------------------


def test_add_and_remove_modification():
    base = _base()
    variant = apply_edit(AddModification(EntityId("A"), ComponentCode("P"), Position(5)), base)
    assert variant.records[0].modifications == (ModificationRecord(ComponentCode("P"), Position(5)),)
    assert base.records[0].modifications == ()
    variant = apply_edit(RemoveModification(EntityId("A"), 0), variant)
    assert variant.records[0].modifications == ()


def test_remove_modification_out_of_range_is_an_error():
    base = _base()
    with pytest.raises(EditError, match="out of range"):
        apply_edit(RemoveModification(EntityId("A"), 0), base)


# -- errors --------------------------------------------------------------------


def test_unknown_record_key_raises_an_edit_error():
    with pytest.raises(EditError, match="Z"):
        apply_edit(SetSequence(EntityId("Z"), SequenceText("X", "protein")), _base())


def test_remove_unknown_record_raises():
    with pytest.raises(EditError):
        apply_edit(RemoveRecord(EntityId("Z")), _base())


def test_edits_are_immutable():
    edit = SetName("x")
    with pytest.raises(EditError):
        edit._name = "y"


def test_set_component_representation_rejects_a_polymer_record():
    base = _base()
    with pytest.raises(EditError, match="ligand"):
        apply_edit(SetComponentRepresentation(EntityId("A"), ByCode((ComponentCode("ATP"),))), base)


# -- reconstruction preserves family fields ------------------------------------


def test_modifications_edit_preserves_other_record_fields():
    registry = IdentityRegistry()
    a = registry.allocate().value
    record = FamilyARecord(
        ids=Multiplicity([a]),
        sequence=SequenceText("PEPTIDE", "protein"),
        description=Present("kept"),
        modifications=(ModificationRecord(ComponentCode("P"), Position(5)),),
    )
    configuration = Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1]),
        records=(record,),
        identity=registry,
    )
    variant = apply_edit(RemoveModification(EntityId(a), 0), configuration)
    edited = variant.records[0]
    assert edited.description == record.description
    assert edited.ids == record.ids
    assert edited.modifications == ()


# -- describe_edit: external resources -------------------------------------------------


def test_describe_edit_reports_an_external_alignment_path():
    """``fold_resource`` hands the handler the PathSpec itself; the variant
    list renders this data, and an external MSA used to crash it with an
    AttributeError (the handler read ``.path`` off the PathSpec)."""
    described = describe_edit(
        SetSingleAlignment(
            EntityId("B"), SingleProvided(External(PathSpec("rna.a3m")))
        )
    )
    assert described["alignment"] == {
        "form": "Provided",
        "source": {"form": "external", "path": "rna.a3m"},
    }

    described = describe_edit(
        SetAlignment(
            EntityId("A"), AlignmentUnpairedOnly(External(PathSpec("msa.a3m")))
        )
    )
    assert described["alignment"] == {
        "form": "UnpairedOnly",
        "source": {"form": "external", "path": "msa.a3m"},
    }


def test_describe_edit_reports_an_external_component_definition():
    described = describe_edit(SetComponentDefinition(External(PathSpec("extra.ccd"))))
    assert described["definition"] == {"form": "external", "path": "extra.ccd"}


def test_describe_edit_reports_inline_alignment_text():
    """``fold_resource`` hands the handler the inline text itself; an inline
    MSA used to crash the variant list with an AttributeError (the handler
    read ``.text`` off the string)."""
    described = describe_edit(
        SetAlignment(EntityId("A"), AlignmentUnpairedOnly(Inline(">p1\nACDE\n>p2\nFGHI")))
    )
    assert described["alignment"] == {
        "form": "UnpairedOnly",
        "source": {"form": "inline", "text": ">p1\nACDE\n>p2\nFGHI"},
    }

    described = describe_edit(
        SetSingleAlignment(EntityId("B"), SingleProvided(Inline(">r1\nACGU")))
    )
    assert described["alignment"] == {
        "form": "Provided",
        "source": {"form": "inline", "text": ">r1\nACGU"},
    }


def test_describe_edit_reports_an_inline_template_source():
    """A template's source is inline xor path, like every other resource:
    the describe path used to read fields ``ReferenceRecord`` no longer
    carries (code/chain/aligned) instead of the source and its index map."""
    described = describe_edit(
        SetReferences(
            EntityId("A"),
            Explicit(
                (
                    ReferenceRecord(
                        Inline("data_template"), (IndexPair(0, 3), IndexPair(1, 4))
                    ),
                )
            ),
        )
    )
    assert described["references"] == {
        "form": "Explicit",
        "items": [
            {
                "source": {"form": "inline", "text": "data_template"},
                "index_map": [[0, 3], [1, 4]],
            }
        ],
    }


def test_describe_edit_reports_an_inline_component_definition():
    described = describe_edit(SetComponentDefinition(Inline("data_LIG\n")))
    assert described["definition"] == {"form": "inline", "text": "data_LIG\n"}


# -- the attached describe helpers (Python 3.9 regression) ----------------------


def test_describe_edit_helpers_are_plain_callables_not_staticmethods():
    """``describe_edit``'s attached helpers must not be ``staticmethod``
    wrappers.

    They are assigned onto a *function* (``describe_edit`` is not a class), so
    there is no descriptor to neutralise; wrapping them made every call site
    raise ``TypeError: 'staticmethod' object is not callable`` on Python 3.9,
    where the ``staticmethod`` object is not itself callable (that arrived in
    3.10). ``requires-python`` is ``>=3.9`` and CI gates on 3.9, so this broke
    variant alignment, template, description and representation round-tripping
    on the declared floor.

    The assertion is written against the module attribute rather than by simply
    calling the helper, because a plain call *passes* on 3.10+ even when the
    wrapper is present -- it would prove nothing on the interpreter that runs
    the suite here.
    """
    import configbuilder.variants.edits as edits_module

    for name in (
        "_presence",
        "_alignment",
        "_single",
        "_references",
        "_representation",
        "_resource",
        "_endpoint",
    ):
        attached = getattr(describe_edit, name)
        assert not isinstance(attached, staticmethod), (
            "%s is wrapped in staticmethod; it is not callable on Python 3.9" % name
        )
        assert callable(attached), "%s must be callable" % name
        # and it must be the module-level implementation, not a copy
        assert attached is getattr(edits_module, name), name


def test_describe_edit_helpers_are_actually_callable_today():
    """Call each attached helper, so a future refactor that reintroduces a
    non-callable wrapper fails here on any interpreter."""
    described = describe_edit(SetAlignment(EntityId("A"), AlignmentUnpairedOnly(Inline(">p1\nACDE"))))
    assert described["alignment"]["form"] == "UnpairedOnly"

    presence = describe_edit(SetDescription(EntityId("A"), Present("hello")))
    assert presence["presence"]["form"] == "Present"
