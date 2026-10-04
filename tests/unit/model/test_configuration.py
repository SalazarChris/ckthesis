"""Unit tests for the Configuration root (plan §7.5, §7.6; MAP-001..003)."""

from __future__ import annotations

import pytest

from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity
from configbuilder.model import (
    Auto,
    ByCode,
    ComponentCode,
    ComponentRecord,
    Configuration,
    ConfigurationError,
    ConfigurationMetadata,
    Dialect,
    External,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    FormatTarget,
    Inline,
    LinkEndpoint,
    Linkage,
    PathSpec,
    Pinned,
    ResidueRef,
    Seed,
    SeedSet,
    SequenceText,
    Unverified,
    fold_version_selection,
)

UINT32_MAX = 2 ** 32 - 1


def _protein_a(seq: str = "PEPTIDE") -> FamilyARecord:
    return FamilyARecord(ids=Multiplicity(["A"]), sequence=SequenceText(seq, "protein"))


def _metadata(name: str = "job") -> ConfigurationMetadata:
    return ConfigurationMetadata(name)


def _configuration(**overrides):
    kwargs = dict(
        metadata=_metadata(),
        seeds=SeedSet([Seed(1), Seed(2)]),
        records=(_protein_a(),),
        identity=IdentityRegistry(),
    )
    kwargs.update(overrides)
    return Configuration(**kwargs)


class TestConfigurationMetadata:
    def test_holds_name(self):
        assert _metadata("my job").name == "my job"

    def test_rejects_blank_name(self):
        with pytest.raises(ConfigurationError):
            ConfigurationMetadata("   ")

    def test_is_immutable(self):
        with pytest.raises(ConfigurationError):
            _metadata().name = "other"  # type: ignore[misc]


class TestSeedSet:
    def test_non_empty_uint32_seeds(self):
        seeds = SeedSet([0, UINT32_MAX])
        assert seeds.values == (0, UINT32_MAX)

    def test_order_is_preserved_as_given(self):
        """spec §14: neither uniqueness nor sorting is required; order carries
        no requirement but is preserved."""
        assert SeedSet([9, 1, 9]).values == (9, 1, 9)

    def test_rejects_empty(self):
        with pytest.raises(ConfigurationError):
            SeedSet([])

    def test_accepts_seed_values_and_seed_objects(self):
        assert SeedSet([Seed(5), 6]).values == (5, 6)

    def test_rejects_out_of_range(self):
        with pytest.raises(Exception):
            SeedSet([UINT32_MAX + 1])

    def test_is_immutable(self):
        with pytest.raises(ConfigurationError):
            SeedSet([1]).values = (2,)  # type: ignore[misc]


class TestDialect:
    def test_supports_exactly_one_dialect(self):
        assert Dialect("alphafold3") is Dialect("alphafold3")

    def test_rejects_any_other_dialect(self):
        with pytest.raises(ConfigurationError):
            Dialect("boltz")


class TestFormatTarget:
    def test_defaults_to_unverified(self):
        """Until the contract probe pins a version, generation stays blocked."""
        target = FormatTarget()
        assert isinstance(target.version_selection, Unverified)

    def test_pinned(self):
        target = FormatTarget(version_selection=Pinned(3))
        assert target.version_selection == Pinned(3)

    def test_auto_requires_evidence(self):
        with pytest.raises(ConfigurationError):
            Auto(())
        auto = Auto((1, 3))
        assert auto.evidenced == (1, 3)

    def test_pinned_rejects_non_positive(self):
        with pytest.raises(ConfigurationError):
            Pinned(0)

    def test_fold_covers_all_cases(self):
        assert (
            fold_version_selection(Unverified(), lambda: "blocked", lambda v: "pinned", lambda e: "auto")
            == "blocked"
        )
        assert (
            fold_version_selection(Pinned(2), lambda: "blocked", lambda v: v, lambda e: "auto") == 2
        )
        assert (
            fold_version_selection(Auto((1,)), lambda: "blocked", lambda v: "pinned", lambda e: e)
            == (1,)
        )

    def test_fold_raises_on_unknown(self):
        with pytest.raises(ConfigurationError):
            fold_version_selection("auto", lambda: 1, lambda v: 2, lambda e: 3)  # type: ignore[arg-type]


class TestConfiguration:
    def test_minimal_construction(self):
        configuration = _configuration()
        assert configuration.records == (_protein_a(),)
        assert configuration.linkages == ()
        assert configuration.component_definition is None

    def test_requires_typed_metadata_and_identity(self):
        with pytest.raises(ConfigurationError):
            Configuration(
                metadata=_metadata(),
                seeds=SeedSet([1]),
                records=(_protein_a(),),
                identity="registry",  # type: ignore[arg-type]
            )
        with pytest.raises(ConfigurationError):
            Configuration(
                metadata="meta",  # type: ignore[arg-type]
                seeds=SeedSet([1]),
                records=(_protein_a(),),
                identity=IdentityRegistry(),
            )

    def test_empty_records_is_constructible(self):
        """An entity-free root is a RELATIONAL validation finding (R-ROOT),
        not an unrepresentable state: the model stays constructible without
        validation (Phase 3 exit criterion)."""
        configuration = _configuration(records=())
        assert configuration.records == ()

    def test_rejects_foreign_records(self):
        with pytest.raises(ConfigurationError):
            _configuration(records=("protein",))  # type: ignore[arg-type]

    def test_holds_all_three_polymer_families_and_ligand(self):
        records = (
            _protein_a(),
            FamilyBRecord(ids=Multiplicity(["B"]), sequence=SequenceText("ACGU", "rna")),
            FamilyCRecord(ids=Multiplicity(["C"]), sequence=SequenceText("ACGT", "dna")),
            ComponentRecord(ids=Multiplicity(["D"]), representation=ByCode((ComponentCode("TPO"),))),
        )
        configuration = _configuration(records=records)
        assert len(configuration.records) == 4

    def test_holds_linkages(self):
        linkage = Linkage(
            LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG"),
            LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(2), atom="C1"),
        )
        configuration = _configuration(linkages=(linkage,))
        assert configuration.linkages == (linkage,)

    def test_rejects_foreign_linkages(self):
        with pytest.raises(ConfigurationError):
            _configuration(linkages=("a-b",))  # type: ignore[arg-type]

    def test_component_definition_accepts_inline_or_external(self):
        configuration = _configuration(component_definition=Inline("CCD text"))
        assert configuration.component_definition == Inline("CCD text")
        configuration = _configuration(component_definition=External(PathSpec("ccd.cif")))
        assert configuration.component_definition.path.raw == "ccd.cif"

    def test_component_definition_rejects_other_values(self):
        with pytest.raises(ConfigurationError):
            _configuration(component_definition="ccd.cif")  # type: ignore[arg-type]

    def test_format_target_defaults_to_unverified(self):
        assert isinstance(_configuration().format_target.version_selection, Unverified)

    def test_identity_registry_is_held_not_validated(self):
        """Plan §7.6: no validation flag travels with the data; the root only
        aggregates."""
        registry = IdentityRegistry()
        configuration = _configuration(identity=registry)
        assert configuration.identity is registry

    def test_is_immutable(self):
        with pytest.raises(ConfigurationError):
            _configuration().records = ()  # type: ignore[misc]


class TestWithDerivations:
    def test_with_seeds_produces_new_root(self):
        original = _configuration()
        derived = original.with_seeds(SeedSet([Seed(9)]))
        assert derived.seeds.values == (9,)
        assert original.seeds.values == (1, 2)
        assert derived is not original

    def test_with_records(self):
        original = _configuration()
        derived = original.with_records((_protein_a(), _protein_a()))
        assert len(derived.records) == 2
        assert len(original.records) == 1

    def test_with_linkages(self):
        original = _configuration()
        linkage = Linkage(
            LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG"),
            LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(2), atom="C1"),
        )
        derived = original.with_linkages((linkage,))
        assert derived.linkages == (linkage,)
        assert original.linkages == ()

    def test_with_metadata(self):
        original = _configuration()
        derived = original.with_metadata(_metadata("renamed"))
        assert derived.metadata.name == "renamed"
        assert original.metadata.name == "job"

    def test_with_component_definition(self):
        original = _configuration()
        derived = original.with_component_definition(Inline("ccd"))
        assert derived.component_definition == Inline("ccd")
        assert original.component_definition is None
        cleared = derived.with_component_definition(None)
        assert cleared.component_definition is None

    def test_with_format_target(self):
        original = _configuration()
        derived = original.with_format_target(FormatTarget(version_selection=Pinned(3)))
        assert derived.format_target.version_selection == Pinned(3)
        assert isinstance(original.format_target.version_selection, Unverified)

    def test_derivations_do_not_mutate_shared_registries(self):
        original = _configuration()
        derived = original.with_seeds(SeedSet([Seed(9)]))
        assert original.identity is derived.identity


def test_configuration_equality_by_value():
    one = _configuration()
    two = _configuration()
    assert one == two
    assert hash(one) == hash(two)
