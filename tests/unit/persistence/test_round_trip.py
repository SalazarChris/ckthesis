"""Round-trip fidelity tests (IMPLEMENTATION_PLAN.md §14, Phase 9 checklist).

``load(save(p))`` must equal ``p`` — every presence state, every sum-type
case, every identifier — and re-saving the loaded project must produce
byte-identical files. The registry's retired identifiers must survive
reopening (reopening never reassigns).
"""

from __future__ import annotations

import json
import os

import pytest

from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity
from configbuilder.model import (
    AlignmentBoth,
    AlignmentFree,
    AlignmentPairedOnly,
    AlignmentUnpairedOnly,
    Auto,
    ByCode,
    ByNotation,
    ComponentCode,
    ComponentRecord,
    Configuration,
    ConfigurationMetadata,
    Explicit,
    ExplicitEmpty,
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
    Pinned,
    Position,
    Present,
    ReferenceRecord,
    ResidueRef,
    SearchAllowed,
    SeedSet,
    SequenceText,
    SingleProvided,
    Unset,
    Unverified,
)
from configbuilder.persistence import (
    Project,
    SCHEMA_VERSION,
    load,
    save,
)
from configbuilder.variants import (
    AddModification,
    AddRecord,
    RemoveRecord,
    SetComponentDefinition,
    SetDescription,
    SetFormatTarget,
    SetJobDescription,
    SetName,
    SetSeeds,
    SetSequence,
    VariantSpec,
)


def _registry():
    registry = IdentityRegistry()
    a = registry.allocate().value
    b = registry.allocate().value
    c = registry.allocate().value
    l_id = registry.allocate().value
    m_id = registry.allocate().value
    return registry, a, b, c, l_id, m_id


def _rich_configuration():
    """A configuration exercising every sum-type case and presence state."""
    registry, a, b, c, l_id, m_id = _registry()
    return Configuration(
        metadata=ConfigurationMetadata("Round Trip", "the job description"),
        seeds=SeedSet([11, 2, 3]),
        records=(
            FamilyARecord(
                ids=Multiplicity([a]),
                sequence=SequenceText("PEPTIDE", "protein"),
                description=Present("chain a"),
                modifications=(ModificationRecord(ComponentCode("P"), Position(5)),),
                alignment=AlignmentUnpairedOnly(External(PathSpec("../data/msa.a3m"))),
                references=Explicit(
                    (
                        ReferenceRecord(External(PathSpec("tpl.cif")), (IndexPair(0, 4), IndexPair(2, 9))),
                        ReferenceRecord(Inline("ATOM...."), ()),
                    )
                ),
            ),
            FamilyBRecord(
                ids=Multiplicity([b]),
                sequence=SequenceText("GGCC", "rna"),
                description=ExplicitEmpty(),
                alignment=SingleProvided(Inline(">query\nGGCC\n")),
            ),
            FamilyCRecord(
                ids=Multiplicity([c]),
                sequence=SequenceText("ATCG", "dna"),
                description=Unset(),
            ),
            ComponentRecord(ids=Multiplicity([l_id]), representation=ByCode((ComponentCode("ATP"), ComponentCode("MG")))),
            ComponentRecord(ids=Multiplicity([m_id]), representation=ByNotation("CC(=O)O"), description=Present("the ligand")),
        ),
        identity=registry,
        linkages=(
            Linkage(
                LinkEndpoint(EntityId(a), ResidueRef(3), "SG"),
                LinkEndpoint(EntityId(l_id), ResidueRef(1), "N1"),
            ),
        ),
        component_definition=Inline("data_lig_lig\n..."),
    ).with_format_target(
        # Pinned at v4: the rich configuration carries a Present chain
        # description, a v4 feature (§10.3 forbids generating it at v3).
        FormatTarget(version_selection=Pinned(4))
    )


def _tmp_path(tmp_path, name="project.cbproj"):
    return str(tmp_path / name)


# -- round trips ------------------------------------------------------------------


def test_load_save_round_trips_the_rich_project(tmp_path):
    project = Project(configuration=_rich_configuration())
    path = _tmp_path(tmp_path)
    save(project, path)
    result = load(path)
    assert result.project == project
    assert result.schema_version == SCHEMA_VERSION
    assert result.upgraded_from is None


def test_identifiers_survive_reopening(tmp_path):
    registry, a, _b, _c, _l, _m = _registry()
    project = Project(configuration=Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1]),
        records=(FamilyARecord(ids=Multiplicity([a]), sequence=SequenceText("P", "protein")),),
        identity=registry,
    ))
    path = _tmp_path(tmp_path)
    save(project, path)
    loaded = load(path).project
    # The full assigned order (A..E) survives; nothing is re-derived from
    # the records, which hold only A.
    assert [e.value for e in loaded.configuration.identity.order()] == ["A", "B", "C", "D", "E"]
    # The allocator continues past the persisted identifiers; it never
    # reassigns (plan §14).
    assert loaded.configuration.identity.allocate().value == "F"


def test_retired_identifiers_stay_retired_after_reopening(tmp_path):
    registry, a, b, _c, _l, _m = _registry()
    configuration = Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1]),
        records=(
            FamilyARecord(ids=Multiplicity([a]), sequence=SequenceText("P", "protein")),
            FamilyBRecord(ids=Multiplicity([b]), sequence=SequenceText("GG", "rna")),
        ),
        identity=registry,
    )
    path = _tmp_path(tmp_path)
    save(Project(configuration=configuration), path)
    loaded = load(path).project
    loaded.configuration.identity.release(EntityId(b))
    second_path = _tmp_path(tmp_path, "second.cbproj")
    save(loaded.with_configuration(loaded.configuration), second_path)
    reopened = load(second_path).project
    # B is released but stays retired: the next allocation skips past it
    # (and past every other persisted identifier) instead of reassigning.
    assert reopened.configuration.identity.allocate().value == "F"


def test_resaving_the_loaded_project_is_byte_identical(tmp_path):
    project = Project(
        configuration=_rich_configuration(),
        specs=(
            VariantSpec(
                key="mut",
                label="mutant",
                edits=(SetSequence(EntityId("A"), SequenceText("MUT", "protein")),),
            ),
        ),
    )
    first = _tmp_path(tmp_path, "first.cbproj")
    save(project, first)
    loaded = load(first).project
    second = _tmp_path(tmp_path, "second.cbproj")
    save(loaded, second)
    with open(first, "rb") as handle:
        assert handle.read() == open(second, "rb").read()


# -- every edit kind survives the project file ----------------------------------------


def test_every_edit_kind_round_trips(tmp_path):
    registry, a, b, _c, _l, _m = _registry()
    configuration = Configuration(
        metadata=ConfigurationMetadata("job", "base description"),
        seeds=SeedSet([1, 2]),
        records=(
            FamilyARecord(
                ids=Multiplicity([a]),
                sequence=SequenceText("PEPTIDE", "protein"),
                modifications=(ModificationRecord(ComponentCode("P"), Position(2)),),
                alignment=AlignmentFree(),
                references=SearchAllowed(),
            ),
            FamilyBRecord(ids=Multiplicity([b]), sequence=SequenceText("GGCC", "rna")),
            ComponentRecord(ids=Multiplicity(["L"]), representation=ByNotation("CCO")),
        ),
        identity=registry,
    )
    edits = (
        SetName("renamed"),
        SetJobDescription(Present("new job text")),
        SetDescription(EntityId(a), ExplicitEmpty()),
        SetSeeds([9, 8, 7]),
        SetSequence(EntityId(a), SequenceText("MUTATED", "protein")),
        AddModification(EntityId(a), ComponentCode("Q"), Position(4)),
        SetComponentDefinition(Inline("data_new")),
        SetFormatTarget(FormatTarget(version_selection=Auto((3, 4)))),
        RemoveRecord(EntityId(b)),
        AddRecord(
            FamilyCRecord(
                ids=Multiplicity(["D"]),
                sequence=SequenceText("AT", "dna"),
                # Modifications ride along in the AddRecord payload too
                # (regression: the encoder once dropped them silently).
                modifications=(ModificationRecord(ComponentCode("X"), Position(1)),),
            )
        ),
    )
    spec = VariantSpec(key="everything", label="kitchen sink", edits=edits)
    path = _tmp_path(tmp_path)
    save(Project(configuration=configuration, specs=(spec,)), path)
    loaded = load(path).project
    assert loaded.specs == (spec,)
    assert loaded.specs[0].edits == edits
