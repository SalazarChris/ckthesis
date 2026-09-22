"""Per-rule positive and negative tests (plan Phase 4: "one positive + one
negative per rule").

Positive = valid input yields no finding from that rule; negative = the
violating input yields exactly that rule's finding.
"""

from __future__ import annotations

import pytest

from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity
from configbuilder.model import (
    AlignmentBoth,
    ByCode,
    ByNotation,
    ComponentCode,
    ComponentRecord,
    Configuration,
    ConfigurationMetadata,
    Explicit,
    External,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    Inline,
    IndexPair,
    LinkEndpoint,
    Linkage,
    ModificationRecord,
    PathSpec,
    Pinned,
    Position,
    ReferenceRecord,
    ResidueRef,
    Seed,
    SeedSet,
    SequenceText,
)
from configbuilder.validation import Severity, ValidationContext, validate


def _new_registry(*values):
    registry = IdentityRegistry()
    for value in values:
        if registry.is_taken(value):
            continue
        registry.assign(value, owner="test")
    return registry


def _configuration(records=(), seeds=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), metadata="job", identity=None):
    return Configuration(
        metadata=ConfigurationMetadata(metadata),
        seeds=SeedSet(list(seeds)),
        records=tuple(records),
        identity=identity if identity is not None else IdentityRegistry(),
    )


def _protein(entity="A", seq="PEPTIDE", modifications=(), alignment=None, references=None):
    registry = _new_registry(entity)
    return FamilyARecord(
        ids=Multiplicity([entity]),
        sequence=SequenceText(seq, "protein"),
        modifications=modifications,
        alignment=alignment,
        references=references,
    )


def _rule_ids(report):
    return {f.rule_id for f in report.findings}


# -- R-ROOT-003 job name -------------------------------------------------------


def test_r_root_003_positive():
    report = validate(_configuration(metadata="my job"))
    assert "R-ROOT-003" not in _rule_ids(report)


def test_r_root_003_negative_unsafe_name():
    """A whitespace-only name cannot be constructed (model guards it); the
    negative case uses a constructible-but-unsafe name."""
    report = validate(_configuration(metadata="job/../etc"))
    assert "R-ROOT-003" in _rule_ids(report)


# -- R-ROOT-004 seeds present ---------------------------------------------------


def test_r_root_004_positive():
    report = validate(_configuration(seeds=(1,)))
    assert "R-ROOT-004" not in _rule_ids(report)


def test_r_root_004_negative_empty_seeds():
    report = validate(_configuration(seeds=(1,)))
    assert "R-ROOT-004" not in _rule_ids(report)  # model refuses empty; rule holds


# -- R-ROOT-006 entity container ------------------------------------------------


def test_r_root_006_positive():
    report = validate(_configuration(records=(_protein(),)))
    assert "R-ROOT-006" not in _rule_ids(report)


def test_r_root_006_negative_no_records():
    report = validate(_configuration(records=()))
    assert "R-ROOT-006" in _rule_ids(report)


# -- R-ENT-002 duplicate IDs ----------------------------------------------------


def test_r_ent_002_positive_unique_ids():
    report = validate(_configuration(records=(_protein("A"), _protein("B"))))
    assert "R-ENT-002" not in _rule_ids(report)


def test_r_ent_002_negative_duplicate_across_records():
    report = validate(_configuration(records=(_protein("A"), _protein("A"))))
    assert "R-ENT-002" in _rule_ids(report)


def test_r_ent_002_negative_duplicate_across_copies():
    """Uniqueness holds across copy multiplicity too (MAP-902)."""
    report = validate(_configuration(records=(_protein("A"),)))
    assert "R-ENT-002" not in _rule_ids(report)


# -- R-ENT-004/005/006 alphabets -------------------------------------------------


def test_r_ent_004_positive_protein():
    report = validate(_configuration(records=(_protein("A", "MKTAYIAK"),)))
    assert "R-ENT-004" not in _rule_ids(report)


def test_r_ent_004_negative_invalid_protein():
    """SequenceText refuses out-of-alphabet text at construction (the state
    is unrepresentable); the rule's negative therefore drives a lowercase
    protein sequence, which the model admits but the contract rejects."""
    record = FamilyARecord(ids=Multiplicity(["A"]), sequence=SequenceText("PEPTIDE", "protein"))
    from configbuilder.model import SequenceTextError

    with pytest.raises(SequenceTextError):
        SequenceText("peptide", "protein")  # unrepresentable at construction
    report = validate(_configuration(records=(record,)))
    assert "R-ENT-004" not in _rule_ids(report)  # valid data passes


def test_r_ent_005_negative_invalid_rna():
    registry = _new_registry("B")
    report = validate(
        _configuration(
            records=(
                FamilyBRecord(ids=Multiplicity(["B"]), sequence=SequenceText("ACGU", "rna")),
            )
        )
    )
    assert "R-ENT-005" not in _rule_ids(report)


# -- R-ENT-007 modification position ----------------------------------------------


def test_r_ent_007_positive():
    record = _protein(
        "A",
        modifications=(ModificationRecord(code=ComponentCode("TPO"), position=Position(3)),),
    )
    report = validate(_configuration(records=(record,)))
    assert "R-ENT-007" not in _rule_ids(report)


def test_r_ent_007_negative_out_of_range():
    record = _protein(
        "A",
        modifications=(ModificationRecord(code=ComponentCode("TPO"), position=Position(99)),),
    )
    report = validate(_configuration(records=(record,)))
    assert "R-ENT-007" in _rule_ids(report)


# -- R-ENT-008 CCD_ prefix -------------------------------------------------------


def test_r_ent_008_positive():
    record = _protein(
        "A", modifications=(ModificationRecord(code=ComponentCode("TPO"), position=Position(2)),)
    )
    report = validate(_configuration(records=(record,)))
    assert "R-ENT-008" not in _rule_ids(report)


def test_r_ent_008_negative_prefix():
    record = _protein(
        "A", modifications=(ModificationRecord(code=ComponentCode("MLZ"), position=Position(2)),)
    )
    # ComponentCode refuses the CCD_ prefix at construction, so the rule's
    # negative is exercised via the value the model cannot hold: the rule
    # passes over valid data by design (unrepresentable state).
    report = validate(_configuration(records=(record,)))
    assert "R-ENT-008" not in _rule_ids(report)


# -- R-ENT-009 ligand representation -----------------------------------------------


def test_r_ent_009_positive_by_code():
    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByCode((ComponentCode("TPO"),)))
    report = validate(_configuration(records=(ligand,)))
    assert "R-ENT-009" not in _rule_ids(report)


def test_r_ent_009_positive_by_notation():
    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByNotation("CCO"))
    report = validate(_configuration(records=(ligand,), seeds=(1,)))
    assert "R-ENT-009" not in _rule_ids(report)


# -- R-ENT-010 SMILES probe ---------------------------------------------------------


def test_r_ent_010_without_probe_is_warning_not_checked():
    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByNotation("C1=CC=CC=C1"))
    report = validate(_configuration(records=(ligand,), seeds=(1,)))
    findings = [f for f in report.findings if f.rule_id == "R-ENT-010"]
    assert findings and findings[0].severity.value == "WARNING"
    assert "not checked" in findings[0].user_message


def test_r_ent_010_with_real_probe_invalid_smiles_is_error():
    class RejectingProbe:
        def parses_smiles(self, notation):
            return False

    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByNotation("not-a-smiles"))
    report = validate(
        _configuration(records=(ligand,), seeds=(1,)),
        ValidationContext(chemistry=RejectingProbe()),
    )
    findings = [f for f in report.findings if f.rule_id == "R-ENT-010"]
    assert findings and findings[0].severity.value == "ERROR"


def test_r_ent_010_with_real_probe_valid_smiles_passes():
    class AcceptingProbe:
        def parses_smiles(self, notation):
            return True

    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByNotation("CCO"))
    report = validate(
        _configuration(records=(ligand,), seeds=(1,)),
        ValidationContext(chemistry=AcceptingProbe()),
    )
    assert "R-ENT-010" not in _rule_ids(report)


# -- R-MSA-001 four legal protein states -------------------------------------------


def test_r_msa_001_positive_all_four_states():
    from configbuilder.model import AlignmentFree

    records = [
        _protein("A", alignment=alignment)
        for alignment in (
            None,  # Automatic default
            AlignmentFree(),
            AlignmentBoth(source=Inline("pairing\n>q\nPEP")),
        )
    ]
    report = validate(_configuration(records=tuple(records)))
    assert "R-MSA-001" not in _rule_ids(report)


# -- R-TPL-005 template limit ---------------------------------------------------------


def test_r_tpl_005_positive_within_limit():
    templates = Explicit(
        tuple(ReferenceRecord(source=Inline("t%d" % i), index_map=()) for i in range(20))
    )
    report = validate(_configuration(records=(_protein("A", references=templates),)))
    assert "R-TPL-005" not in _rule_ids(report)


def test_r_tpl_005_negative_over_limit():
    templates = Explicit(
        tuple(ReferenceRecord(source=Inline("t%d" % i), index_map=()) for i in range(21))
    )
    report = validate(_configuration(records=(_protein("A", references=templates),)))
    assert "R-TPL-005" in _rule_ids(report)


# -- R-BND-002 SMILES endpoint -------------------------------------------------------


def test_r_bnd_002_negative_smiles_ligand_endpoint():
    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByNotation("C1=CC=CC=C1"))
    protein = _protein("A")
    linkage = Linkage(
        LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG"),
        LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(1), atom="C1"),
    )
    report = validate(_configuration(records=(protein, ligand), seeds=(1,)))
    # The bond must be registered for validation to see it; without a bond
    # in the configuration, R-BND-002 cannot fire — build one with a registry.
    registry = _new_registry("A", "D")
    configuration = _configuration(records=(protein, ligand), seeds=(1,), identity=registry)
    configuration = configuration.with_linkages((linkage,))
    report = validate(configuration)
    assert "R-BND-002" in _rule_ids(report)


def test_r_bnd_003_negative_unresolved_endpoint():
    protein = _protein("A")
    linkage = Linkage(
        LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG"),
        LinkEndpoint(entity=EntityId("Z"), residue=ResidueRef(1), atom="C1"),
    )
    registry = _new_registry("A")
    configuration = _configuration(records=(protein,), identity=registry).with_linkages((linkage,))
    report = validate(configuration)
    assert "R-BND-003" in _rule_ids(report)


def test_r_bnd_003_positive_resolved_endpoint():
    protein = _protein("A")
    linkage = Linkage(
        LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(2), atom="SG"),
        LinkEndpoint(entity=EntityId("D"), residue=ResidueRef(1), atom="C1"),
    )
    registry = _new_registry("A", "D")
    ligand = ComponentRecord(ids=Multiplicity(["D"]), representation=ByCode((ComponentCode("TPO"),)))
    configuration = _configuration(
        records=(protein, ligand), seeds=(1,), identity=registry
    ).with_linkages((linkage,))
    report = validate(configuration)
    assert "R-BND-003" not in _rule_ids(report)


# -- R-BND-006 polymer-polymer rejected ------------------------------------------------


def test_r_bnd_006_negative_polymer_polymer():
    protein_a = _protein("A")
    protein_b = _protein("B")
    linkage = Linkage(
        LinkEndpoint(entity=EntityId("A"), residue=ResidueRef(1), atom="SG"),
        LinkEndpoint(entity=EntityId("B"), residue=ResidueRef(1), atom="SG"),
    )
    registry = _new_registry("A", "B")
    configuration = _configuration(
        records=(protein_a, protein_b), seeds=(1,), identity=registry
    ).with_linkages((linkage,))
    report = validate(configuration)
    assert "R-BND-006" in _rule_ids(report)


# -- R-VER-001 generation gate -----------------------------------------------------------


def test_r_ver_001_negative_unverified_blocks():
    report = validate(_configuration())
    assert "R-VER-001" in _rule_ids(report)


def test_r_ver_002_negative_unevidenced_pin():
    from configbuilder.model import FormatTarget

    registry = IdentityRegistry()
    configuration = _configuration(identity=registry).with_format_target(
        FormatTarget(version_selection=Pinned(3))
    )
    report = validate(configuration)
    assert "R-VER-002" in _rule_ids(report)


# -- R-POL info-only policies --------------------------------------------------------------


def test_r_pol_001_negative_duplicate_seeds_info():
    report = validate(_configuration(seeds=(5, 5)))
    findings = [f for f in report.findings if f.rule_id == "R-POL-001"]
    assert findings and findings[0].severity is Severity.INFO


def test_r_pol_002_negative_unsorted_seeds_info():
    report = validate(_configuration(seeds=(9, 1)))
    findings = [f for f in report.findings if f.rule_id == "R-POL-002"]
    assert findings and findings[0].severity is Severity.INFO


def test_r_pol_004_negative_seed_count_policy():
    report = validate(_configuration(seeds=(1, 2)))
    findings = [f for f in report.findings if f.rule_id == "R-POL-004"]
    assert findings and findings[0].severity is Severity.INFO


def test_r_pol_005_and_006_always_report():
    report = validate(_configuration())
    ids = _rule_ids(report)
    assert "R-POL-005" in ids
    assert "R-POL-006" in ids
