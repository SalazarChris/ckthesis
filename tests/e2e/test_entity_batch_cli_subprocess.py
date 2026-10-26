"""The batch fixtures through the real console, entry by entry.

``manual_test_data/af3_builder/batch`` holds one base job that
carries everything a batch entry cannot say — a custom CCD definition, a
CCD-coded ligand with two copies, an ion and a SMILES ligand — plus the entry
files themselves. These tests start ``python af3builder.py`` and answer its
prompts, then read the JSON that came out.

What they pin:

- the base survives verbatim (ids, ``userCCD`` text, seeds, version) and exactly
  one ligand is added per configuration;
- the identities of the added ligands are distinct across the file;
- an entry's name is used for the file name, and two entries sharing a name take
  a deterministic ``-2`` suffix;
- a CCD code typed into a ligand file is stored as SMILES text — the documented
  limitation, stated on the record instead of implied away.
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

pytestmark = pytest.mark.skipif(
    not LAUNCHER.exists() or not BASE.exists() or not NAMED.exists(),
    reason="the launcher or the committed batch fixtures are missing",
)


def _run(tmp_path, ligands, output):
    answers = [
        "2",            # open
        str(BASE),
        "7",            # generate ligand configurations
        "1",
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


def _added_ligand(document):
    return document["sequences"][-1]["ligand"]


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
    assert "Wrote 4 file(s) under" in completed.stdout

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
        added = _added_ligand(document)
        assert set(added) == {"id", "smiles"}, "never ccdCodes and smiles together"
        added_ids.add(added["id"])
        molecules[added["smiles"]] = document["name"] if "name" in document else None

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
        name: _added_ligand(document)["smiles"]
        for name, document in documents.items()
    }
    assert by_name["batch-base-with-ccd__kinase-inhibitor.json"] == "CCO"
    assert by_name["batch-base-with-ccd__kinase-inhibitor-2.json"] == "c1ccccc1"


def test_a_ccd_code_in_a_file_is_stored_as_smiles_text(tmp_path):
    """The honest limit: a ligand file has no CCD syntax."""
    output = tmp_path / "out"

    completed = _run(tmp_path, CCD_LOOKALIKE, output)

    assert completed.returncode == 0, completed.stderr[-800:]
    documents = _documents(output)
    assert sorted(documents) == [
        "batch-base-with-ccd__atp.json",
        "batch-base-with-ccd__zinc.json",
    ]
    added = {name: _added_ligand(document) for name, document in documents.items()}
    assert added["batch-base-with-ccd__atp.json"]["smiles"] == "ATP"
    assert added["batch-base-with-ccd__zinc.json"]["smiles"] == "ZN"
    for entry in added.values():
        assert "ccdCodes" not in entry
