"""The ligand file workflow through the real console, as a user runs it.

The interface is menu-driven: a user opens a job, chooses the ligand file and
a folder, and the configurations are written. There is no command-line flag
that means "generate these", so these tests start the real process the user
starts — ``python af3builder.py``, from a working directory of their own — and
answer its prompts through its own standard input. Nothing imports the
services or calls an internal function: a break in the menu, the wiring, the
services or the writer shows up here.

The base they open is the committed multi-ligand / small-protein example, and
the ligand list is the committed ``batch/ligands_valid.smiles``. The
assertions are on the JSON that came out: one independent configuration per
entry, the entry's name in the file name, every base entity still there, and
the file they opened byte-for-byte unchanged.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "af3builder.py"
PACK = ROOT / "manual_test_data" / "af3_builder"
FIXTURE = PACK / "inputs" / "multi_ligand_small_protein_test.txt"
LIGANDS = PACK / "batch" / "ligands_valid.smiles"

pytestmark = pytest.mark.skipif(
    not LAUNCHER.exists() or not FIXTURE.exists() or not LIGANDS.exists(),
    reason="the launcher or the committed example is missing",
)


def _run(tmp_path, answers):
    """Start the console exactly as a user does and answer its prompts."""
    script = "\n".join(str(answer) for answer in answers) + "\n"
    return subprocess.run(
        [sys.executable, str(LAUNCHER)],
        input=script,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )


def _documents(root):
    """Every written configuration, by file name (the manifest excluded)."""
    documents = {}
    for path in sorted(Path(root).rglob("*.json")):
        if path.name == "manifest.json":
            continue
        documents[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return documents


def _open_example(tmp_path, output):
    """The answers that open the example and run the ligand file in it."""
    return [
        "2",                # main menu: open a JSON file
        str(FIXTURE),       # the picker takes a path
        "7",                # job menu: generate ligand configurations
        "1",                # the one action
        str(LIGANDS),       # the ligand list
        str(output),        # the output folder
        "0",                # back to the job menu
        "0",                # leave the job (nothing was changed)
        "0",                # exit
    ]


def test_the_console_writes_one_configuration_per_ligand_entry(tmp_path):
    """Scenario A/G: a file in, one independent configuration per entry out."""
    output = tmp_path / "out"
    before = FIXTURE.read_bytes()

    completed = _run(tmp_path, _open_example(tmp_path, output))

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "2 entries read" not in completed.stdout
    assert "3 entries read" in completed.stdout
    assert "Wrote" in completed.stdout

    documents = _documents(output)
    assert sorted(documents) == [
        "multi-ligand-small-protein__acetic-acid.json",
        "multi-ligand-small-protein__ethanol.json",
        "multi-ligand-small-protein__ligand-1.json",
    ]
    by_smiles = {}
    for document in documents.values():
        ligand = [
            entry["ligand"]
            for entry in document["sequences"]
            if "ligand" in entry
        ][-1]
        by_smiles[ligand["smiles"]] = document
    assert sorted(by_smiles) == ["C1CCCCC1", "CC(=O)O", "CCO"]

    # Every base entity survives untouched in every file: the ligand is added,
    # nothing is replaced. The four base definitions carry ids A-D (the ATP
    # ligand is one definition with two copies).
    base_ids = {"A", "B", "C", "D"}
    for document in documents.values():
        identifiers = set()
        for entry in document["sequences"]:
            body = next(iter(entry.values()))
            ids = body["id"]
            identifiers.update([ids] if isinstance(ids, str) else ids)
        assert base_ids.issubset(identifiers)

    # The opened file is the source of truth and is never written to.
    assert FIXTURE.read_bytes() == before
    assert (output / "multi-ligand-small-protein" / "manifest.json").exists()


def test_the_console_refuses_a_duplicate_entry_and_writes_nothing(tmp_path):
    """A repeated molecule refuses the whole file, before any write."""
    listing = tmp_path / "duplicates.smiles"
    listing.write_text("one CCO\ntwo CCO\n", encoding="utf-8")
    output = tmp_path / "out"

    completed = _run(
        tmp_path,
        [
            "2",
            str(FIXTURE),
            "7",
            "1",
            str(listing),
            "0",   # back from the ligand menu: the refusal returned there
            "0",
            "0",
        ],
    )

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Nothing was written" in completed.stdout
    assert "duplicate ligand entries" in completed.stdout
    assert not output.exists() or not list(output.rglob("*.json"))


def test_the_console_refuses_an_empty_file(tmp_path):
    empty = tmp_path / "empty.smiles"
    empty.write_text("# only comments\n\n", encoding="utf-8")

    completed = _run(
        tmp_path,
        ["2", str(FIXTURE), "7", "1", str(empty), "0", "0", "0"],
    )

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Nothing was written" in completed.stdout
    assert "no entries" in completed.stdout


def test_the_console_never_replaces_existing_output(tmp_path):
    """Scenario G: a pre-existing file with other content refuses the run.

    The project folder is derived from the job name, so a second run over the
    same base would land on the same paths. The planner reports the conflict
    and writes nothing — and the pre-existing bytes are untouched.
    """
    project_dir = tmp_path / "out" / "multi-ligand-small-protein"
    existing = project_dir / "multi-ligand-small-protein__ethanol"
    existing.mkdir(parents=True)
    target = existing / "multi-ligand-small-protein__ethanol.json"
    target.write_text('{"kept": true}\n', encoding="utf-8")

    completed = _run(tmp_path, _open_example(tmp_path, tmp_path / "out"))

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Nothing was written" in completed.stdout
    assert "already exists with different content" in completed.stdout
    assert target.read_text(encoding="utf-8") == '{"kept": true}\n'
    # no partial batch: the sibling entries were not written either
    assert not (
        project_dir / "multi-ligand-small-protein__acetic-acid"
    ).exists()
    assert not (project_dir / "manifest.json").exists()


def test_the_console_does_not_claim_chemistry_it_does_not_check(tmp_path):
    """The documented limitation, pinned: SMILES text is stored, not parsed.

    ``batch/ligands_unchecked_syntax.smiles`` holds deliberately malformed
    SMILES. The builder wires no chemistry parser, so they are accepted (an
    advisory warning, never a blocking finding) — this test says so on the
    record instead of letting the flow imply a check that does not exist.
    """
    malformed = PACK / "batch" / "ligands_unchecked_syntax.smiles"
    output = tmp_path / "out"

    completed = _run(
        tmp_path,
        [
            "2",
            str(FIXTURE),
            "7",
            "1",
            str(malformed),
            str(output),
            "0",
            "0",
            "0",
        ],
    )

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Wrote" in completed.stdout
    documents = _documents(output)
    assert len(documents) == 2
    # The added ligand is the last entry; the base's own ligands (CCD codes)
    # are still there ahead of it.
    added = []
    for document in documents.values():
        ligands = [entry["ligand"] for entry in document["sequences"] if "ligand" in entry]
        added.append(ligands[-1]["smiles"])
    assert sorted(added) == ["C1CC", "this is not a smiles"]
