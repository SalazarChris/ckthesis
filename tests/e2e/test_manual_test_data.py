"""The committed manual test pack, exercised through the real services.

`manual_test_data/af3_builder/` exists so a person can drive batch generation,
external MSA and template inputs through the console and the desktop window by
hand. These tests make the same claims the README makes, by loading *those
files* (repository-relative) and running the same service calls the two front
ends run, so the pack cannot rot into documentation that no longer matches the
code.

Two properties are pinned here beyond "the feature works":

* the pack is **read-only** — every generated file goes to ``tmp_path``, and
  the fixture tree is compared before and after;
* **RNA is not protein** — its MSA is one field, one path, never a paired
  side; the explicitly selected RNA batch kind builds `FamilyBRecord` entities.

The tests do not run AF3 inference. The serialized input corpus is separately
checked against AF3's own parser by ``tools/af3_validation/run_all.py``; custom
CCD documents remain unverified in that harness because the compiled CIF parser
is stubbed. See ``docs/AF3_MANUAL_TEST_DATA_AND_RNA_MSA_REPORT.md`` for the
builder/runtime verification boundary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from configbuilder.app import FailureReason
from configbuilder.app.configuration_service import ReferenceInput
from configbuilder.persistence import (
    PersistenceError,
    parse_sequence_text,
    parse_smiles_text,
    read_sequence_file,
    read_smiles_file,
)
from configbuilder.model import FamilyBRecord, SingleProvided
from configbuilder.output.policies import PathPolicy
from configbuilder.transform import to_wire
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

#: The pack, located from this file rather than from the working directory, so
#: the suite works whatever directory pytest is started in.
PACK = Path(__file__).resolve().parents[2] / "manual_test_data" / "af3_builder"

PROTEIN_SEQUENCES = ("MKTAYIAKQRQISFVKSHFSRQ", "ACDEFGHIKLMNPQRSTVWY", "GGGGGGGGGG")
DNA_SEQUENCES = ("ATGCATGC", "GGCCTTAA")
QUERY_PROTEIN = "ACDEFGHIKLMNPQRSTVWY"
QUERY_RNA = "ACGUACGU"


def _pack(*parts) -> str:
    return os.path.join(str(PACK), *parts)


def _services(name="pack"):
    services = build_services()
    services.projects.new(name)
    return services


def _rna_document(services):
    document = to_wire(services.projects._require_project().configuration).document
    return document["sequences"][0]["rna"]


def _tree(root: Path):
    """Every file path and size under ``root`` — the read-only comparison."""
    return sorted(
        (str(path.relative_to(root)), path.stat().st_size)
        for path in root.rglob("*")
        if path.is_file()
    )


def _save(script, destination):
    console = ScriptedConsole(script + ["6", str(destination), "0", "0"])
    assert MenuApp(build_services(), console).run() == 0
    assert destination.exists(), console.transcript[-1500:]
    return json.loads(destination.read_text(encoding="utf-8")), console.transcript


# ---------------------------------------------------------------------------
# A. Batch inputs
# ---------------------------------------------------------------------------


def test_the_protein_batch_file_is_one_sequence_per_line():
    entries = read_sequence_file(_pack("batch", "proteins_valid.txt"))
    assert [text for _line, text in entries] == list(PROTEIN_SEQUENCES)


def test_protein_batch_previews_then_commits_every_entry():
    services = _services("batch-protein")
    preview = services.variants.inspect_batch_file(
        _pack("batch", "proteins_valid.txt"), family="protein"
    )
    assert preview.ok, preview.message
    assert tuple(preview.entries) == PROTEIN_SEQUENCES
    assert preview.planned == len(PROTEIN_SEQUENCES)

    outcome = services.variants.generate_from_file(
        _pack("batch", "proteins_valid.txt"), family="protein"
    )
    assert outcome.ok, outcome.message
    assert [spec.key for spec in services.variants.specs()] == [
        "batch_01",
        "batch_02",
        "batch_03",
    ]
    # The base job itself is untouched: batch entries become independent specs.
    base = services.projects._require_project().configuration
    assert base.records == ()


def test_wrapped_fasta_is_not_a_batch_format_and_is_refused_whole():
    """The reader is one-sequence-per-line: it has no header/wrapping support.

    The fixture is refused because of its ``>`` header line, and the refusal
    is all-or-nothing — nothing is created. (A headerless *wrapped* file would
    instead be read as several sequences: the README warns about that.)
    """
    services = _services("batch-fasta")
    preview = services.variants.inspect_batch_file(
        _pack("batch", "proteins_wrapped_fasta.txt"), family="protein"
    )
    assert not preview.ok
    assert "line 1" in preview.message

    outcome = services.variants.generate_from_file(
        _pack("batch", "proteins_wrapped_fasta.txt"), family="protein"
    )
    assert not outcome.ok
    assert services.variants.specs() == []


def test_rna_batch_is_one_family_record_per_entry():
    """RNA is a batch family: the records are ``FamilyBRecord``, not protein.

    The ``rna`` representation, its ``ACGU`` alphabet and the ``rna``
    serialisation all already existed for single entities, so the batch needs
    no second implementation — this pins that the shared builder produces the
    right family and refuses the wrong alphabet.
    """
    services = _services("batch-rna")
    preview = services.variants.inspect_batch_file(
        _pack("batch", "rna_sequences.txt"), family="rna"
    )
    assert preview.ok, preview.message
    assert preview.planned == 2
    assert preview.entries == ("ACGUACGUACGU", "GGGCCCAAAUUU")

    outcome = services.variants.generate_from_file(
        _pack("batch", "rna_sequences.txt"), family="rna"
    )
    assert outcome.ok, outcome.message
    assert [spec.key for spec in services.variants.specs()] == ["batch_01", "batch_02"]
    expanded = services.variants.expand()
    assert expanded.ok, expanded.message
    for variant in expanded.variants:
        added = variant.configuration.records[-1]
        assert isinstance(added, FamilyBRecord), added
        assert added.sequence.family == "rna"

    # The alphabets are the model's: ``T`` is DNA, never RNA.
    wrong = services.variants.inspect_batch_file(
        _pack("batch", "dna_sequences.txt"), family="rna"
    )
    assert not wrong.ok
    assert "outside its alphabet" in wrong.message


def test_dna_batch_commits_one_variant_per_entry():
    services = _services("batch-dna")
    outcome = services.variants.generate_from_file(
        _pack("batch", "dna_sequences.txt"), family="dna"
    )
    assert outcome.ok, outcome.message
    assert [spec.key for spec in services.variants.specs()] == ["batch_01", "batch_02"]


def test_smiles_batch_reads_names_comments_and_bare_smiles():
    entries = read_smiles_file(_pack("batch", "ligands_valid.smiles"))
    assert [(name, smiles) for _line, name, smiles in entries] == [
        ("ethanol", "CCO"),
        ("acetic-acid", "CC(=O)O"),
        ("ligand_1", "C1CCCCC1"),
    ]
    services = _services("batch-ligand")
    assert services.variants.generate_from_file(
        _pack("batch", "ligands_valid.smiles"), family="ligand"
    ).ok
    assert len(services.variants.specs()) == 3


def test_the_malformed_smiles_fixture_is_refused_with_its_own_reasons():
    """Grammar is checked; chemistry is not, and the pack says which.

    The fixture holds a broken ring closure and a sentence. Both are refused
    by the reader with the offending line and the reason, before anything is
    written — builder acceptance here would mean "stored as text", which is
    exactly what the notation check stopped doing. What is still not claimed:
    that a grammatical notation describes a molecule.
    """
    services = _services("batch-smiles-unchecked")
    malformed = _pack("batch", "ligands_unchecked_syntax.smiles")

    preview = services.variants.inspect_batch_file(malformed, family="ligand")
    assert not preview.ok
    assert "not SMILES notation" in preview.message
    assert "ring-closure number 1 is opened but never closed" in preview.message
    assert services.variants.specs() == []
    assert not services.variants.generate_from_file(malformed, family="ligand").ok

    # The same notation as a *base* entity, where the rule looks: a blocking
    # finding that names the defect, so a save cannot write it either.
    checked = _services("batch-smiles-warning")
    checked.configuration.add_record(
        "ligand", representation="C1CC", representation_kind="smiles"
    )
    findings = [
        f for f in checked.validation.validate_base().report.findings
        if f.rule_id == "R-ENT-010"
    ]
    assert findings
    assert {finding.severity.value for finding in findings} == {"ERROR"}
    assert "ring-closure number 1 is opened but never closed" in findings[0].user_message


def test_a_grammatical_notation_is_never_judged_for_chemistry():
    """The other half of the claim: the fixture below is notation the pack
    documents as absent from the builder's promises, and it is written."""
    services = _services("batch-smiles-grammar-only")
    services.configuration.add_record(
        "ligand", representation="C(C)(C)(C)(C)C", representation_kind="smiles"
    )

    findings = [
        f for f in services.validation.validate_base().report.findings
        if f.rule_id == "R-ENT-010"
    ]

    assert findings == []


def test_empty_and_invalid_batch_files_are_refused_with_their_lines(tmp_path):
    services = _services("batch-invalid")
    empty = services.variants.inspect_batch_file(
        _pack("batch", "empty.txt"), family="protein"
    )
    assert not empty.ok
    assert "no sequences" in empty.message

    invalid = services.variants.inspect_batch_file(
        _pack("batch", "invalid_sequence.txt"), family="protein"
    )
    assert not invalid.ok
    # Lines 2 and 3 are unusable; line 1 is fine and is not blamed.
    assert "line 2" in invalid.message
    assert "line 3" in invalid.message
    assert "line 1" not in invalid.message
    assert services.variants.specs() == []

    with pytest.raises(PersistenceError):
        read_sequence_file(str(tmp_path / "absent.txt"))


def test_the_sequence_parser_keeps_line_numbers_and_skips_blank_lines():
    numbered = parse_sequence_text("ACDE\n\n  FGHI  \n")
    assert numbered == ((1, "ACDE"), (3, "FGHI"))
    assert parse_smiles_text("# comment\n\nCCO\n") == ((3, "ligand_1", "CCO"),)


# ---------------------------------------------------------------------------
# B/C. Protein and RNA MSA
# ---------------------------------------------------------------------------


def test_protein_unpaired_and_paired_files_reach_their_own_fields():
    services = _services("protein-msa")
    services.configuration.add_record("protein", QUERY_PROTEIN)
    assert services.configuration.set_alignment(
        "A", "unpaired", external_path=_pack("msa", "protein", "unpaired-query.a3m")
    ).ok
    protein = to_wire(
        services.projects._require_project().configuration
    ).document["sequences"][0]["protein"]
    assert protein["unpairedMsaPath"].endswith("unpaired-query.a3m")
    assert protein["pairedMsa"] == ""
    assert "pairedMsaPath" not in protein

    assert services.configuration.set_alignment(
        "A",
        "both",
        external_path=_pack("msa", "protein", "unpaired-query.a3m"),
        paired_external_path=_pack("msa", "protein", "paired-query.a3m"),
    ).ok
    protein = to_wire(
        services.projects._require_project().configuration
    ).document["sequences"][0]["protein"]
    assert protein["unpairedMsaPath"].endswith("unpaired-query.a3m")
    assert protein["pairedMsaPath"].endswith("paired-query.a3m")


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("automatic", {}),
        ("free", {"unpairedMsa": ""}),
    ],
)
def test_rna_msa_modes_without_a_source_emit_the_contract_values(mode, expected):
    services = _services("rna-" + mode)
    services.configuration.add_record("rna", QUERY_RNA)
    assert services.configuration.set_alignment("A", mode).ok
    rna = _rna_document(services)
    assert {key: rna[key] for key in rna if "Msa" in key} == expected


def test_rna_provided_file_is_one_path_and_never_a_paired_side():
    services = _services("rna-file")
    services.configuration.add_record("rna", QUERY_RNA)
    path = _pack("msa", "with spaces", "rna query.a3m")
    assert services.configuration.set_alignment(
        "A", "provided", external_path=path
    ).ok
    rna = _rna_document(services)
    assert rna["unpairedMsaPath"] == path
    # The protein-only keys are absent: RNA has a single MSA field.
    for field in ("pairedMsa", "pairedMsaPath"):
        assert field not in rna
    assert "unpairedMsa" not in rna


def test_rna_provided_inline_text_is_the_same_field_as_a_file():
    services = _services("rna-inline")
    services.configuration.add_record("rna", QUERY_RNA)
    text = Path(_pack("msa", "rna", "query-rna.a3m")).read_text(encoding="utf-8")
    assert services.configuration.set_alignment(
        "A", "provided", inline_text=text
    ).ok
    rna = _rna_document(services)
    assert rna["unpairedMsa"] == text
    assert "unpairedMsaPath" not in rna


def test_an_imported_rna_paired_msa_is_dropped_with_a_note():
    """RNA has no paired side: the importer keeps the single field and says so."""
    from configbuilder.transform import from_wire

    configuration, notes = from_wire(
        {
            "name": "imported-rna",
            "modelSeeds": [1],
            "dialect": "alphafold3",
            "version": 3,
            "sequences": [
                {
                    "rna": {
                        "id": "A",
                        "sequence": QUERY_RNA,
                        "unpairedMsa": ">q\nACGUACGU\n",
                        "pairedMsa": "",
                    }
                }
            ],
        }
    )
    assert [note.field for note in notes] == ["sequences[0].rna.pairedMsa"]
    assert isinstance(configuration.records[0].alignment, SingleProvided)


def test_an_external_msa_path_at_version_one_is_refused_by_name(tmp_path):
    services = _services("rna-v1")
    services.configuration.add_record("rna", QUERY_RNA)
    services.configuration.set_alignment(
        "A", "provided", external_path=_pack("msa", "rna", "query-rna.a3m")
    )
    assert services.configuration.set_format_target(version=1).ok

    destination = tmp_path / "never.json"
    plan = services.generation.plan_save(str(destination))
    assert not plan.ok
    assert plan.failure_reason is FailureReason.VALIDATION_BLOCKED
    assert "version 2" in plan.message
    assert not destination.exists()


def test_automatic_is_the_default_and_omits_both_rna_msa_fields():
    services = _services("rna-default")
    services.configuration.add_record("rna", QUERY_RNA)
    rna = _rna_document(services)
    assert "unpairedMsa" not in rna and "unpairedMsaPath" not in rna


# ---------------------------------------------------------------------------
# D/E. Templates, paths and output policy
# ---------------------------------------------------------------------------


def test_a_missing_rna_msa_file_blocks_save(tmp_path):
    services = _services("rna-missing")
    services.configuration.add_record("rna", QUERY_RNA)
    missing = _pack("msa", "rna", "absent.a3m")
    assert services.configuration.set_alignment(
        "A", "provided", external_path=missing
    ).ok

    plan = services.generation.plan_save(str(tmp_path / "job.json"))
    assert not plan.ok
    assert plan.failure_reason is FailureReason.VALIDATION_BLOCKED
    assert [finding.rule_id for finding in plan.findings] == ["R-MSA-006"]
    assert not (tmp_path / "job.json").exists()


def test_rna_msa_is_copied_into_assets_by_default_and_slugged(tmp_path):
    services = _services("rna-copy")
    services.configuration.add_record("rna", QUERY_RNA)
    services.configuration.set_alignment(
        "A", "provided", external_path=_pack("msa", "with spaces", "rna query.a3m")
    )
    plan = services.generation.plan_base(str(tmp_path / "out"))
    assert plan.ok, plan.message
    assert [(r.wire_field, r.emitted_path) for r in plan.reviewed.resources] == [
        ("unpairedMsaPath", "assets/rna-query.a3m")
    ]
    assert plan.reviewed.resources[0].raw_path.endswith("rna query.a3m")

    assert services.generation.execute(plan).ok
    written = json.loads(
        (tmp_path / "out" / "rna-copy" / "rna-copy.json").read_text(encoding="utf-8")
    )
    assert written["sequences"][0]["rna"]["unpairedMsaPath"] == "assets/rna-query.a3m"
    assert (tmp_path / "out" / "rna-copy" / "assets" / "rna-query.a3m").is_file()


def test_rna_msa_path_is_emitted_forward_slashed_when_kept_as_given(tmp_path):
    services = _services("rna-as-given")
    services.configuration.add_record("rna", QUERY_RNA)
    services.configuration.set_alignment(
        "A", "provided", external_path=_pack("msa", "with spaces", "rna query.a3m")
    )
    destination = tmp_path / "as-given.json"
    plan = services.generation.plan_save(
        str(destination), path_policy=PathPolicy("AsGiven")
    )
    assert plan.ok, plan.message
    assert services.generation.execute(plan).ok
    rna = json.loads(destination.read_text(encoding="utf-8"))["sequences"][0]["rna"]
    assert rna["unpairedMsaPath"] == _pack(
        "msa", "with spaces", "rna query.a3m"
    ).replace(os.sep, "/")


def test_a_template_file_is_emitted_and_copied_with_assets(tmp_path):
    services = _services("template")
    services.configuration.add_record("protein", QUERY_PROTEIN)
    cif = _pack("templates", "with spaces", "template with spaces.cif")
    assert services.configuration.set_references(
        "A", references=(ReferenceInput(external_path=cif, pairs=((0, 0), (1, 1))),)
    ).ok

    destination = tmp_path / "job.json"
    plan = services.generation.plan_save(str(destination))
    assert plan.ok, plan.message
    assert services.generation.execute(plan).ok
    protein = json.loads(destination.read_text(encoding="utf-8"))["sequences"][0][
        "protein"
    ]
    assert protein["templates"] == [
        {
            "mmcifPath": "assets/template-with-spaces.cif",
            "queryIndices": [0, 1],
            "templateIndices": [0, 1],
        }
    ]
    copied = tmp_path / "assets" / "template-with-spaces.cif"
    assert copied.is_file()
    assert copied.read_bytes() == Path(cif).read_bytes()


def test_a_missing_template_file_is_refused_when_it_is_configured():
    services = _services("template-missing")
    services.configuration.add_record("protein", QUERY_PROTEIN)
    outcome = services.configuration.set_references(
        "A",
        references=(
            ReferenceInput(external_path=_pack("templates", "absent.cif"), pairs=((0, 0),)),
        ),
    )
    assert not outcome.ok
    assert "does not exist" in outcome.message


def test_templates_are_protein_only():
    """The model gives RNA no ``references`` field; the service refuses it."""
    services = _services("template-rna")
    services.configuration.add_record("rna", QUERY_RNA)
    outcome = services.configuration.set_references(
        "A",
        references=(
            ReferenceInput(
                external_path=_pack("templates", "minimal_template.cif"),
                pairs=((0, 0),),
            ),
        ),
    )
    assert not outcome.ok


# ---------------------------------------------------------------------------
# The console, on the pack, with a path that contains spaces
# ---------------------------------------------------------------------------


def test_console_rna_msa_file_flow_round_trips_a_path_with_spaces(tmp_path):
    destination = tmp_path / "spaces.json"
    script = [
        "1",
        "manual-rna",
        "2",
        "3",
        QUERY_RNA,
        "2",
        _pack("msa", "with spaces", "rna query.a3m"),
    ]
    document, transcript = _save(script, destination)
    rna = document["sequences"][0]["rna"]
    # The default policy copies the file beside the saved JSON and emits the
    # slugged asset path — the space in the source name never reaches the wire.
    assert rna["unpairedMsaPath"] == "assets/rna-query.a3m"
    assert (destination.parent / "assets" / "rna-query.a3m").is_file()
    assert "pairedMsa" not in rna
    assert "RNA MSA file: " in transcript
    assert "Paired MSA file" not in transcript


def test_console_ligand_file_writes_one_configuration_per_entry(tmp_path):
    """The console's ligand route, driven with the pack's ligand file."""
    output = str(tmp_path / "configurations")
    console = ScriptedConsole(
        [
            "1",
            "manual-ligands",
            "2",
            "1",
            QUERY_PROTEIN,
            "1",
            "n",
            "7",  # configuration generation from a file
            "1",  # open the file and generate
            "4",  # what it holds: SMILES ligands
            _pack("batch", "ligands_valid.smiles"),
            output,
            "0",
            "0",
            "0",
        ]
    )
    assert MenuApp(build_services(), console).run() == 0, console.transcript[-2000:]
    transcript = console.transcript
    assert "Traceback" not in transcript
    # The three entries of the pack's file, shown before anything is written.
    assert "3 entries read" in transcript
    for name in ("ethanol", "acetic-acid"):
        assert "%s  " % name in transcript
    assert "Wrote" in transcript
    # One independent configuration per entry, named after the entry, plus the
    # manifest. The bare SMILES line is auto-named by the reader.
    written = sorted(
        path.name
        for path in (tmp_path / "configurations" / "manual-ligands").rglob("*.json")
    )
    assert written == [
        "manifest.json",
        "manual-ligands__acetic-acid.json",
        "manual-ligands__ethanol.json",
        "manual-ligands__ligand-1.json",
    ]
    # The prompt names the two formats the reader accepts; it never suggests a
    # wrapped FASTA file, which this reader would read as several entries.
    assert ".smiles or .txt" in transcript
    assert "FASTA" not in transcript


# ---------------------------------------------------------------------------
# The pack is input only
# ---------------------------------------------------------------------------


def test_running_the_pack_writes_nothing_inside_it(tmp_path):
    before = _tree(PACK)
    services = _services("pack-readonly")
    services.configuration.add_record("protein", QUERY_PROTEIN)
    services.configuration.set_alignment(
        "A",
        "both",
        external_path=_pack("msa", "protein", "unpaired-query.a3m"),
        paired_external_path=_pack("msa", "protein", "paired-query.a3m"),
    )
    services.configuration.set_references(
        "A",
        references=(
            ReferenceInput(
                external_path=_pack("templates", "minimal_template.cif"), pairs=((0, 0),)
            ),
        ),
    )
    services.variants.generate_from_file(
        _pack("batch", "proteins_valid.txt"), family="protein"
    )
    plan = services.generation.plan(str(tmp_path / "out"))
    assert plan.ok, plan.message
    assert services.generation.execute(plan).ok
    assert _tree(PACK) == before
    assert not (PACK / "assets").exists()
