"""The batch fixtures through the real console, entry by entry.

``manual_test_data/af3_builder/batch`` holds one base job that
carries everything a batch entry cannot say — a custom CCD definition, a
CCD-coded ligand with two copies, an ion and a SMILES ligand — plus the entry
files themselves. These tests start ``python af3builder.py`` and answer its
prompts, then read the JSON that came out.

The console asks **what the file holds** before it opens it (kind 1–5), because
a ``.txt`` identifies nothing: the same four lines are protein records when the
protein kind is chosen and refused when the SMILES kind is. Every run here
therefore names its kind, and the kind it names is the one the written
documents must show.

What they pin:

- the base survives verbatim (ids, ``userCCD`` text, seeds, version) and exactly
  one entity is added per configuration;
- each kind writes its own representation: ``protein``/``dna``/``rna`` with a
  ``sequence``, ``smiles`` for notation, ``ccdCodes`` for codes;
- the identities of the added entities are distinct across the file;
- an entry's name is used for the file name, and two entries sharing a name take
  a deterministic ``-2`` suffix;
- a CCD code typed into a *SMILES* file is refused, not stored as SMILES text —
  a SMILES file has no CCD syntax, so the run stops before a folder is chosen;
- a sequence file in SMILES mode is refused *with advice*, never reinterpreted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "af3builder.py"
PACK = ROOT / "manual_test_data" / "af3_builder" / "batch"
BASE = PACK / "base_job_custom_ccd.json"
NAMED = PACK / "ligands_named.smiles"
DUPLICATE_NAMES = PACK / "ligands_duplicate_names.smiles"
CCD_LOOKALIKE = PACK / "ligands_ccd_lookalike.smiles"
NOTATION_EDGES = PACK / "ligands_notation_edges.smiles"
PROTEINS_MINIMAL = PACK / "proteins_minimal.txt"
CCD_CODES = PACK / "ligands_ccd_codes.txt"

#: The console's kind numbers, as the menu lists them. Spelled out here rather
#: than imported so a menu reordering fails this file loudly instead of
#: silently driving the wrong reader.
PROTEIN, DNA, RNA, SMILES, CCD = "1", "2", "3", "4", "5"

pytestmark = pytest.mark.skipif(
    not LAUNCHER.exists() or not BASE.exists() or not NAMED.exists(),
    reason="the launcher or the committed batch fixtures are missing",
)


def _run(tmp_path, ligands, output, kind=SMILES):
    answers = [
        "2",            # open
        str(BASE),
        "7",            # configuration generation from a file
        "1",            # load an input file and generate configurations
        kind,           # what does the file contain?
        str(ligands),
        str(output),
        "0",
        "0",
        "0",
    ]
    return subprocess.run(
        [sys.executable, str(LAUNCHER)],
        input="\n".join(answers) + "\n",
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )


def _documents(root):
    found = {}
    for path in sorted(Path(root).rglob("*.json")):
        if path.name == "manifest.json":
            continue
        found[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return found


def _added(document):
    """The entry this run added: the last one in the document."""
    return document["sequences"][-1]


def _identifiers(entry):
    body = next(iter(entry.values()))
    ids = body["id"]
    return ids if isinstance(ids, list) else [ids]


def test_the_console_keeps_every_base_field_and_adds_one_ligand_per_entry(tmp_path):
    output = tmp_path / "out"

    completed = _run(tmp_path, NAMED, output)

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr
    assert "3 entries read from" in completed.stdout
    # The summary counts roles, not plan rows: three configurations plus one
    # manifest, never "wrote 4 files" with the manifest described as one of
    # the configurations.
    assert (
        "Generated 3 AF3 configurations. Wrote 1 manifest. Total output files: 4."
        in completed.stdout
    )

    documents = _documents(output)
    assert sorted(documents) == [
        "batch-base-with-ccd__acetic-acid.json",
        "batch-base-with-ccd__ethanol.json",
        "batch-base-with-ccd__ligand-1.json",
    ]

    base_text = BASE.read_text(encoding="utf-8")
    custom_ccd = json.loads(base_text)["userCCD"]
    added_ids = set()
    molecules = {}
    for document in documents.values():
        assert document["modelSeeds"] == [7], "the base's seeds ride through"
        assert document["version"] == 3
        assert document["dialect"] == "alphafold3"
        assert document["userCCD"] == custom_ccd, "the custom CCD is preserved"
        # Four base definitions, five identifiers; one ligand added on top.
        assert len(document["sequences"]) == 5
        identifiers = []
        for entry in document["sequences"]:
            identifiers.extend(_identifiers(entry))
        assert identifiers[:5] == ["A", "B", "E", "C", "D"]
        assert len(set(identifiers)) == 6, "every identifier is unique"
        added = _added(document)["ligand"]
        assert set(added) == {"id", "smiles"}, "never ccdCodes and smiles together"
        added_ids.add(added["id"])
        molecules[added["smiles"]] = document.get("name")

    assert added_ids == {"F", "G", "H"}
    assert set(molecules) == {"CCO", "CC(=O)O", "c1ccccc1"}


def test_duplicate_names_get_a_deterministic_suffix(tmp_path):
    output = tmp_path / "out"

    completed = _run(tmp_path, DUPLICATE_NAMES, output)

    assert completed.returncode == 0, completed.stderr[-800:]
    documents = _documents(output)
    assert sorted(documents) == [
        "batch-base-with-ccd__kinase-inhibitor-2.json",
        "batch-base-with-ccd__kinase-inhibitor.json",
    ]
    by_name = {
        name: _added(document)["ligand"]["smiles"]
        for name, document in documents.items()
    }
    assert by_name["batch-base-with-ccd__kinase-inhibitor.json"] == "CCO"
    assert by_name["batch-base-with-ccd__kinase-inhibitor-2.json"] == "c1ccccc1"


def test_the_protein_kind_writes_four_protein_configurations(tmp_path):
    """The reported case end to end: ``MVT``/``MVS``/``MVY``/``TEST``.

    Four lines in, four documents out, each the base plus **one** protein
    entity carrying that line. Nothing is written as a ligand: no ``smiles``
    and no ``ccdCodes`` appears in the added entry.
    """
    output = tmp_path / "out"

    completed = _run(tmp_path, PROTEINS_MINIMAL, output, kind=PROTEIN)

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "4 entries read from" in completed.stdout
    assert (
        "Generated 4 AF3 configurations. Wrote 1 manifest. Total output files: 5."
        in completed.stdout
    )

    documents = _documents(output)
    assert sorted(documents) == [
        "batch-base-with-ccd__batch-01.json",
        "batch-base-with-ccd__batch-02.json",
        "batch-base-with-ccd__batch-03.json",
        "batch-base-with-ccd__batch-04.json",
    ]
    sequences = {}
    identifiers = set()
    for document in documents.values():
        assert document["modelSeeds"] == [7]
        assert document["version"] == 3
        assert document["dialect"] == "alphafold3"
        assert "userCCD" in document, "the base's custom CCD is preserved"
        added = _added(document)
        assert list(added) == ["protein"], added
        assert set(added["protein"]) == {"id", "sequence"}
        sequences[added["protein"]["id"]] = added["protein"]["sequence"]
        identifiers.add(added["protein"]["id"])
        # The base's own four definitions are still ahead of the added one.
        assert len(document["sequences"]) == 5
    assert sorted(sequences.values()) == ["MVS", "MVT", "MVY", "TEST"]
    assert len(identifiers) == 4, "one identifier per entry"


@pytest.mark.parametrize(
    "kind, fixture, family, expected",
    (
        (DNA, "dna_sequences.txt", "dna", ["ATGCATGC", "GGCCTTAA"]),
        (
            RNA,
            "rna_sequences.txt",
            "rna",
            ["ACGUACGUACGU", "GGGCCCAAAUUU"],
        ),
    ),
)
def test_the_dna_and_rna_kinds_write_their_own_entity(kind, fixture, family, expected, tmp_path):
    output = tmp_path / "out"

    completed = _run(tmp_path, PACK / fixture, output, kind=kind)

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    documents = _documents(output)
    assert len(documents) == len(expected), sorted(documents)
    written = []
    for document in documents.values():
        if family == "dna":
            strands = document["sequences"][-2:]
            assert [list(entry) for entry in strands] == [["dna"], ["dna"]]
            assert all(set(entry["dna"]) == {"id", "sequence"} for entry in strands)
            assert strands[1]["dna"]["sequence"] == strands[0]["dna"]["sequence"][::-1].translate(
                str.maketrans("ATGC", "TACG")
            )
            written.append(strands[0]["dna"]["sequence"])
        else:
            added = _added(document)
            assert list(added) == [family], added
            assert set(added[family]) == {"id", "sequence"}
            written.append(added[family]["sequence"])
    assert sorted(written) == sorted(expected)


def test_the_ccd_kind_writes_component_codes(tmp_path):
    """Codes are identifiers: ``ccdCodes``, one ligand per line, never SMILES."""
    output = tmp_path / "out"

    completed = _run(tmp_path, CCD_CODES, output, kind=CCD)

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "3 entries read from" in completed.stdout
    documents = _documents(output)
    assert sorted(documents) == [
        "batch-base-with-ccd__atp.json",
        "batch-base-with-ccd__nag-nag-bma-man-man.json",
        "batch-base-with-ccd__zn.json",
    ]
    codes = {
        name: _added(document)["ligand"]["ccdCodes"]
        for name, document in documents.items()
    }
    assert codes["batch-base-with-ccd__atp.json"] == ["ATP"]
    assert codes["batch-base-with-ccd__zn.json"] == ["ZN"]
    assert codes["batch-base-with-ccd__nag-nag-bma-man-man.json"] == [
        "NAG",
        "NAG",
        "BMA",
        "MAN",
        "MAN",
    ]
    for document in documents.values():
        assert "smiles" not in _added(document)["ligand"]


def test_invalid_and_empty_sequence_batches_are_refused_before_output(tmp_path):
    for fixture, kind in (("invalid_sequence.txt", PROTEIN), ("empty.txt", PROTEIN)):
        output = tmp_path / fixture.replace(".txt", "-out")
        completed = _run(tmp_path, PACK / fixture, output, kind=kind)
        assert completed.returncode == 0, completed.stderr[-800:]
        assert "invalid" in completed.stdout.lower() or "no sequences" in completed.stdout.lower()
        assert "Wrote" not in completed.stdout
        assert not output.exists() or not _documents(output)


@pytest.mark.parametrize(
    "sequence_file",
    (
        "proteins_valid.txt",
        "proteins_wrapped_fasta.txt",
        "proteins_minimal.txt",
        "dna_sequences.txt",
        "rna_sequences.txt",
        "invalid_sequence.txt",
        "empty.txt",
    ),
)


def test_a_sequence_file_in_smiles_mode_is_refused_with_advice(tmp_path, sequence_file):
    """No silent reinterpretation: refused, and told which kind would read it.

    The same files are protein/DNA/RNA batches under their own kinds (above).
    Choosing SMILES for them is the user's mistake, and the console answers it
    with the offending lines plus the kind that would take them — before the
    folder question, and without writing or creating anything.
    """
    output = tmp_path / "out"

    completed = _run(tmp_path, PACK / sequence_file, output, kind=SMILES)

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "Wrote" not in completed.stdout
    assert "not SMILES notation" in completed.stdout or "no entries" in completed.stdout
    assert not output.exists() or not _documents(output)
    if sequence_file in ("proteins_valid.txt", "proteins_minimal.txt"):
        # The advice names the sequence kind and the CCD alternative, because a
        # short capitalised string is both.
        assert "may be protein sequences rather than SMILES" in completed.stdout
        assert "protein sequence input type" in completed.stdout


def test_the_kind_menu_offers_exactly_the_supported_input_types(tmp_path):
    """Five kinds, named, and nothing that reads as variant management.

    The menu is the contract with the user: what it lists is what the services
    can build. It must not offer a family no reader supports, and it must not
    resurrect the retired variant workflow.
    """
    completed = subprocess.run(
        [sys.executable, str(LAUNCHER)],
        input="\n".join(["2", str(BASE), "7", "1", "0", "0", "0", "0"]) + "\n",
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )

    screen = completed.stdout.split("What does the file contain?")[-1]
    menu = screen.split("Select:")[0]
    assert "Protein sequences" in menu
    assert "DNA sequences" in menu
    assert "RNA sequences" in menu
    assert "Ligands by SMILES" in menu
    assert "Ligands by CCD code" in menu
    for number in range(1, 6):
        assert "\n%d. " % number in menu, (number, menu)
    assert "\n6. " not in menu, "five kinds, no sixth entry"
    assert "variant" not in menu.lower()


def test_notation_the_check_must_keep_is_generated_entry_by_entry(tmp_path):
    """The positive control: bracketed atoms, charges, ``%nn`` rings, isotopes.

    A grammar check that refused any of these would block a real job, so the
    pack keeps them and the console is driven through the whole file.
    """
    output = tmp_path / "out"

    completed = _run(tmp_path, NOTATION_EDGES, output)

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "6 entries read" in completed.stdout.replace("\r", "")
    documents = _documents(output)
    assert sorted(documents) == [
        "batch-base-with-ccd__alanine.json",
        "batch-base-with-ccd__aspirin.json",
        "batch-base-with-ccd__deuterated-methane.json",
        "batch-base-with-ccd__isotopic-methane.json",
        "batch-base-with-ccd__macrocycle.json",
        "batch-base-with-ccd__saline.json",
    ]
    added = {name: _added(document)["ligand"] for name, document in documents.items()}
    assert added["batch-base-with-ccd__aspirin.json"]["smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert added["batch-base-with-ccd__saline.json"]["smiles"] == "[Na+].[Cl-]"
    assert added["batch-base-with-ccd__macrocycle.json"]["smiles"] == "C%10CCCCCC%10"
    assert added["batch-base-with-ccd__alanine.json"]["smiles"] == "C[C@H](N)C(=O)O"
    assert (
        added["batch-base-with-ccd__deuterated-methane.json"]["smiles"]
        == "[2H]C([2H])([2H])[2H]"
    )
    assert added["batch-base-with-ccd__isotopic-methane.json"]["smiles"] == "[13CH4]"
    # The base is untouched in every one of them.
    for document in documents.values():
        assert document["modelSeeds"] == [7]
        assert document["version"] == 3
        assert "userCCD" in document


def test_a_ccd_code_in_a_smiles_file_is_refused_and_nothing_is_written(tmp_path):
    """A SMILES file has no CCD syntax: a code in one is not a molecule.

    This used to be written as ``{"smiles": "ATP"}``. The console now refuses
    the file before choosing a folder, naming each offending line, and no
    output folder is created — the refusal is the whole result. The CCD kind is
    how such a file is meant to be read (and it is tested above).
    """
    output = tmp_path / "out"

    completed = _run(tmp_path, CCD_LOOKALIKE, output, kind=SMILES)

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "not SMILES notation" in completed.stdout
    assert "'ATP'" in completed.stdout and "'ZN'" in completed.stdout
    assert "Wrote" not in completed.stdout
    assert not output.exists() or not _documents(output)
