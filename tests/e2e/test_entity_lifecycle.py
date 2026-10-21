"""End-to-end entity lifecycle over the reworked menu.

The recipes a builder must not lose: create → view → edit → modify → cancel →
save → reopen → edit again → remove for every family, an imported AF3 document
edited like a built one, variants that are save-as copies never touching the
base, and long repeated operation chains that used to be where state bugs hid.

These drive the shipped menu over a ``ScriptedConsole`` in a temporary working
directory, then assert on the *state* and on the JSON actually written to disk
— the same two artifacts a user checks. A job is reopened by opening its JSON:
the rework removed the internal working-copy/recovery store.
"""

from __future__ import annotations

import json
import os

from configbuilder.app.cli import MenuApp
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"
OTHER_PROTEIN = "MKTAYIAKQR"
RNA = "ACGUACGU"

# Whole menu units. Each starts and ends at the job menu; add/edit units carry
# their family's own trailing answers (MSA? templates?).
NEW = lambda name: ["1", name]
ADD_PROTEIN = lambda sequence: ["2", "1", sequence, "", ""]
ADD_RNA = lambda sequence: ["2", "3", sequence, ""]
ADD_DNA = lambda sequence: ["2", "2", sequence, "1"]  # yes to the complement
ADD_LONE_DNA = lambda sequence: ["2", "2", sequence, "2"]  # single strand
ADD_LIGAND = lambda value, copies="1": ["2", "4", "1", value, copies]
DELETE_ENTITY = lambda number: ["3", str(number), "2", "1", "0"]
EDIT_PROTEIN = lambda number, sequence, description="": [
    "3", str(number), "1", sequence, description, "", "", "0", "0",
]
# RNA carries an alignment but no templates; DNA carries neither.
EDIT_RNA = lambda number, sequence, description="": [
    "3", str(number), "1", sequence, description, "", "0", "0",
]
EDIT_DNA = lambda number, sequence, description="": [
    "3", str(number), "1", sequence, description, "0", "0",
]
EDIT_LIGAND = lambda number, kind, value: [
    "3", str(number), "1", kind, value, "0", "0",
]
# The record's own modifications submenu: job 3 → record → 3 → operation.
ADD_MOD = lambda number, code, position: [
    "3", str(number), "3", "1", code, str(position), "0", "0", "0",
]
REMOVE_MOD = lambda number, row: ["3", str(number), "3", "3", str(row), "0", "0", "0"]
REMOVE_MOD_NONE = lambda number: ["3", str(number), "3", "3", "0", "0", "0"]
CANCEL_DELETE = ["3", "1", "2", "2", "0", "0"]
SAVE = lambda destination: ["6", str(destination)]
REOPEN = lambda path: ["2", str(path)]
LEAVE_DIRTY = ["0", "2", "0"]
LEAVE_CLEAN = ["0", "0"]
EXIT = ["0"]


def run(script, services=None):
    services = services or build_services()
    console = ScriptedConsole(script)
    app = MenuApp(services, console)
    status = app.run()
    return status, console.transcript, services


def load(path):
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_invariants(services, transcript):
    """The pass's own invariants, checked against the live configuration."""
    assert "Traceback" not in transcript
    configuration = services.projects.project.configuration
    registry = set(configuration.identity.assigned_values())
    seen = []
    for record in configuration.records:
        for entity in record.ids.ids:
            assert entity.value not in seen, "duplicate identifier %r" % entity.value
            seen.append(entity.value)
    assert registry == set(seen), "registry and records disagree"
    for linkage in configuration.linkages:
        for endpoint in (linkage.a, linkage.b):
            assert configuration.identity.resolve(endpoint.entity)
    return configuration


def identifiers(document):
    """Every entity id in a wire document, flattened."""
    ids = []
    for entity in document["sequences"]:
        payload = next(iter(entity.values()))
        identifier = payload["id"]
        ids.extend(identifier if isinstance(identifier, list) else [identifier])
    return ids


# -- add / remove / re-add / edit / save -------------------------------------


def test_add_remove_readd_edit_then_save_writes_the_model_it_shows(tmp_path, monkeypatch):
    """Task recipe: add A, add B, add C, remove B, add D, edit A, edit C, save.

    The identifiers stay unique and unreused, the edits land on the records
    the user picked, and the file's ids are exactly the model's.
    """
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "lifecycle.json"
    status, out, services = run(
        NEW("Lifecycle")
        + ADD_PROTEIN(PROTEIN)            # A
        + ADD_PROTEIN(OTHER_PROTEIN)      # B
        + ADD_PROTEIN("GGGGSGGGGS")       # C
        + DELETE_ENTITY(2)                # remove B
        + ADD_PROTEIN("ACDEFGHIK")        # D
        + EDIT_PROTEIN(1, "AAAAAGGGGG")   # edit A
        + EDIT_PROTEIN(3, "")             # edit C (kept as it was)
        + SAVE(destination)
        + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0

    keys = [record.ids.primary.value for record in configuration.records]
    assert keys == ["A", "C", "D"]        # B retired, never reused
    assert [record.sequence.text for record in configuration.records] == [
        "AAAAAGGGGG",
        "GGGGSGGGGS",
        "ACDEFGHIK",
    ]

    document = load(destination)
    assert identifiers(document) == keys


def test_every_family_survives_a_full_lifecycle(tmp_path, monkeypatch):
    """Protein, RNA, DNA and ligand each added, edited where editable, saved,
    reopened and removed — the per-family lifecycle."""
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "families.json"
    second = tmp_path / "families-edited.json"
    third = tmp_path / "families-final.json"
    status, out, services = run(
        NEW("Families")
        + ADD_PROTEIN(PROTEIN)
        + ADD_RNA(RNA)
        + ADD_DNA("ATGC")                 # a duplex: two records
        + ADD_LIGAND("ATP")
        + SAVE(first)
        + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert [type(record).__name__ for record in configuration.records] == [
        "FamilyARecord",
        "FamilyBRecord",
        "FamilyCRecord",
        "FamilyCRecord",
        "ComponentRecord",
    ]
    assert [record.sequence.text for record in configuration.records[2:4]] == ["ATGC", "GCAT"]

    # Reopen the saved job and edit the protein again.
    status, out, services = run(
        REOPEN(first) + EDIT_PROTEIN(1, OTHER_PROTEIN) + SAVE(second) + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert configuration.records[0].sequence.text == OTHER_PROTEIN

    # Reopen, remove the duplex: both strands go, nothing else moves.
    status, out, services = run(
        REOPEN(second) + DELETE_ENTITY(3) + SAVE(third) + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert [record.ids.primary.value for record in configuration.records] == ["A", "B", "E"]


# -- a single supplied DNA strand -------------------------------------------


def test_dna_can_be_added_as_one_supplied_strand():
    """The "single-stranded" answer adds exactly the strand the user typed.

    Regression: the console used to add the duplex and then remove its
    partner, which removed both strands and left an empty job while still
    reporting that an entity had been added.
    """
    status, out, services = run(
        NEW("Lone DNA") + ADD_LONE_DNA("ATGC") + LEAVE_DIRTY
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert [type(record).__name__ for record in configuration.records] == [
        "FamilyCRecord"
    ]
    assert configuration.records[0].sequence.text == "ATGC"
    assert "Only the supplied strand will be used." in out


# -- modifications -----------------------------------------------------------


def test_modification_lifecycle_add_remove_readd_and_reload(tmp_path, monkeypatch):
    """Task recipe: add a modification, remove it, add another, edit the
    entity, save, reload — the modifications stay on the right record."""
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "mods.json"
    status, out, services = run(
        NEW("Mods")
        + ADD_PROTEIN(PROTEIN)
        + ADD_MOD(1, "SEP", 5)
        + REMOVE_MOD(1, 1)
        + ADD_MOD(1, "TPO", 7)
        + EDIT_PROTEIN(1, "ACDEFGHIKLMNPQR")   # a shorter sequence, kept PTM in range
        + SAVE(first)
        + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert [
        (modification.code.value, modification.position.value)
        for modification in configuration.records[0].modifications
    ] == [("TPO", 7)]

    status, out, services = run(REOPEN(first) + LEAVE_CLEAN)
    configuration = assert_invariants(services, out)
    assert status == 0
    assert [
        (modification.code.value, modification.position.value)
        for modification in configuration.records[0].modifications
    ] == [("TPO", 7)]


def test_two_modifications_at_one_position_are_removed_row_by_row():
    """A shared position is legal in the model and in an imported file; the
    picker's rows must address their own modification (BUG-024)."""
    status, out, services = run(
        NEW("Same position")
        + ADD_PROTEIN(PROTEIN)
        + ADD_MOD(1, "SEP", 5)
        + ADD_MOD(1, "TPO", 5)
        + REMOVE_MOD(1, 2)
        + LEAVE_DIRTY
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert [
        (modification.code.value, modification.position.value)
        for modification in configuration.records[0].modifications
    ] == [("SEP", 5)]


# -- import → edit → remove → add → save → reload ----------------------------


RICH_IMPORT = {
    "name": "rich-import",
    "modelSeeds": [7, 8],
    "sequences": [
        {
            "protein": {
                "id": ["A", "B"],          # the multi-copy form: one record, two ids
                "sequence": PROTEIN,
                "modifications": [{"ptmType": "SEP", "ptmPosition": 4}],
                "unpairedMsa": ">A\n" + PROTEIN + "\n",
                "pairedMsa": "",
                "templates": [
                    {"mmcifPath": "t.cif", "queryIndices": [0, 1], "templateIndices": [0, 2]}
                ],
                "description": "kinase",
            }
        },
        {"rna": {"id": "C", "sequence": RNA}},
        {"ligand": {"id": "G", "ccdCodes": ["ATP"]}},
        {"ligand": {"id": "H", "ccdCodes": ["MG"]}},          # a bonded pair of CCD ligands
        {"ligand": {"id": "I", "smiles": "CCO"}},            # a SMILES ligand, unbonded
    ],
    "bondedAtomPairs": [[["G", 1, "C1"], ["H", 1, "MG"]]],
    "userCCD": "data_probe\n",
    "dialect": "alphafold3",
    "version": 4,
}


def test_an_imported_document_is_editable_like_a_built_one(tmp_path, monkeypatch):
    """Task recipe: import → view → edit → remove → add → save → reload.

    The imported file has identifiers, multiplicities and optional fields a
    built job would not produce; everything downstream must still hold.
    """
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "rich.json"
    source.write_text(json.dumps(RICH_IMPORT), encoding="utf-8")
    saved = tmp_path / "rich-edited.json"

    status, out, services = run(
        REOPEN(source)
        + EDIT_RNA(2, "ACGUGGCC")       # edit the RNA (record 2 = C)
        + ADD_PROTEIN("ACDEFGHIK")
        + DELETE_ENTITY(1)              # remove the multi-id protein A/B
        + SAVE(saved)
        + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert configuration.metadata.name == "rich-import"
    keys = [record.ids.primary.value for record in configuration.records]
    assert "A" not in keys and "B" not in keys
    # the multi-id record's letters stay retired; the new protein takes the
    # first free letter of the progression (A/B/C are reserved)
    assert keys == ["C", "G", "H", "I", "D"]
    assert configuration.records[0].sequence.text == "ACGUGGCC"

    document = load(saved)
    assert identifiers(document) == keys
    assert document["name"] == "rich-import"

    # The saved file reopens with the same content and identity set.
    status, out, services = run(REOPEN(saved) + LEAVE_CLEAN)
    configuration = assert_invariants(services, out)
    assert [record.ids.primary.value for record in configuration.records] == keys


# -- variants are save-as copies that never touch the base -------------------


def test_variants_keep_their_own_declarations_after_the_base_changes(tmp_path, monkeypatch):
    """Create the base, save a variant, edit the base, save another variant,
    save the base: each file carries exactly its own declaration, and the
    base is exactly the user's edits."""
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "v1.json"
    second = tmp_path / "v2.json"
    base_file = tmp_path / "base.json"
    status, out, services = run(
        NEW("Base")
        + ADD_PROTEIN(PROTEIN)
        + ["7",                                        # V1: a sequence change
           "3", "1", "1", "ACDEFGHIKL", "", "", "", "0", "0",
           "4", str(first),
           "0"]                                        # leave variants
        + EDIT_PROTEIN(1, OTHER_PROTEIN)               # the base changes after V1
        + ["7", "1", "V2", "4", str(second), "0"]      # V2: job name only
        + SAVE(base_file)
        + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert configuration.records[0].sequence.text == OTHER_PROTEIN
    assert services.projects.project.specs == ()

    assert load(first)["sequences"][0]["protein"]["sequence"] == "ACDEFGHIKL"
    second_document = load(second)
    assert second_document["name"] == "v2"
    assert second_document["sequences"][0]["protein"]["sequence"] == OTHER_PROTEIN
    assert load(base_file)["sequences"][0]["protein"]["sequence"] == OTHER_PROTEIN


# -- repeated operations -----------------------------------------------------


def test_a_long_repeated_chain_of_operations_leaves_consistent_state(tmp_path, monkeypatch):
    """Task §16's chain: add add edit edit remove add edit remove save reload
    edit add remove save — the invariants must hold at the end, and both the
    model and the written JSON must agree."""
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "chained.json"
    second = tmp_path / "chained-again.json"
    status, out, services = run(
        NEW("Chained")
        + ADD_PROTEIN(PROTEIN)                  # A
        + ADD_RNA(RNA)                          # B
        + EDIT_PROTEIN(1, "ACDEFGHIK")          # edit A
        + ADD_DNA("GATTACA")                    # C, D (duplex)
        + DELETE_ENTITY(2)                      # remove B
        + ADD_LIGAND("NAG NAG BMA")             # E
        + EDIT_PROTEIN(1, "ACDEFGHIKLMNP")
        + REMOVE_MOD_NONE(1)                    # nothing to remove: refused cleanly
        + ADD_MOD(1, "SEP", 4)
        + REMOVE_MOD(1, 1)
        + SAVE(first)
        + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    keys = [record.ids.primary.value for record in configuration.records]
    assert keys == ["A", "C", "D", "E"]
    assert identifiers(load(first)) == keys

    # Reload, then keep going: edit, add, remove, save again. The second save
    # goes to its own file, so no overwrite dialog stands in the way.
    status, out, services = run(
        REOPEN(first)
        + EDIT_PROTEIN(1, "ACDEFGHIKLMNPQ")
        + ADD_PROTEIN("ACDEFGHIKLMNPQR")
        + DELETE_ENTITY(2)                      # remove the duplex
        + SAVE(second)
        + LEAVE_CLEAN
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    keys = [record.ids.primary.value for record in configuration.records]
    assert keys == ["A", "E", "B"]
    # Reopening a JSON restores only its live ids, not the old session's
    # retirement ledger, so the next free letter ('B') is reusable here.
    document = load(second)
    assert identifiers(document) == keys
    assert [
        entity["protein"]["sequence"] for entity in document["sequences"] if "protein" in entity
    ] == ["ACDEFGHIKLMNPQ", "ACDEFGHIKLMNPQR"]


def test_cancel_interleaved_with_real_operations_changes_nothing():
    """Task §16's second chain: add cancel add cancel edit cancel remove
    cancel edit save. Every cancellation is a no-op; the real operations
    land."""
    status, out, services = run(
        NEW("Cancels")
        + ["2", "1", ""]                    # cancel: blank sequence
        + ADD_PROTEIN(PROTEIN)              # A
        + ["2", "4", "1", ""]            # cancel: blank ligand value
        + EDIT_PROTEIN(1, "", "")           # cancel: keep sequence and description
        + CANCEL_DELETE                     # cancel: the delete confirm
        + ["3", "1", "3", "1", "SEP", "0", "0", "0", "0"]  # cancel: no position
        + EDIT_PROTEIN(1, OTHER_PROTEIN)    # a real edit
        + LEAVE_DIRTY
    )
    configuration = assert_invariants(services, out)
    assert status == 0
    assert len(configuration.records) == 1
    assert configuration.records[0].sequence.text == OTHER_PROTEIN
    assert configuration.linkages == ()
