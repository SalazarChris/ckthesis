"""Menu-level pins for the 2026-10-08 entity-editing hardening pass.

Each test drives the real ``MenuApp`` over a ``ScriptedConsole`` — the
interface a human uses — because the defects in that pass were reachable only
through a menu path. The menu rework moved the variant flow from a stored
spec catalogue to save-as copies, so these pins use the new routes:

- BUG-021  a wrong-alphabet sequence answer killed the session (base and
           variant editor alike)
- BUG-024  removing the *second* of two modifications at one position removed
           the first (the picker's payload was the position, not the row)
- the modification picker's row must be the row removed inside a variant too
  (the shape BUG-025 caught in the old variant catalogue)
- a ligand edit asks for the ligand's representation, never for a sequence
- cancellation must leave the configuration identical
"""

from __future__ import annotations

import json

from configbuilder.model import ByCode, ByNotation
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"
RNA = "ACGUACGU"

NEW_JOB = ["1", "job"]
ADD_PROTEIN = ["2", "1", PROTEIN, "", ""]
ADD_RNA = ["2", "3", RNA, ""]
ADD_MOD = lambda code, position: ["5", "2", "1", code, str(position), "0"]
REMOVE_MOD = lambda row: ["5", "4", "1", str(row), "0"]
LEAVE_DIRTY = ["0", "2", "0"]
LEAVE_CLEAN = ["0", "0"]


def run(script, services=None, prepare=None):
    services = services or build_services()
    if prepare is not None:
        prepare(services)
    console = ScriptedConsole(script)
    app = MenuApp(services, console)
    status = app.run()
    return status, console.transcript, services


def _mods(services, index=0):
    return [
        (modification.code.value, modification.position.value)
        for modification in services.projects.project.configuration.records[index].modifications
    ]


def _load(path):
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


# -- BUG-024: two modifications at one position ------------------------------


def test_removing_the_second_of_two_modifications_at_one_position_removes_it():
    """The rows are the record's own list; the picked *row* must be removed.

    Both rows show ``@ 5`` and the old picker carried the position as its
    payload, so choosing row 2 removed row 1 — the wrong modification, with
    nothing on screen saying so.
    """
    status, out, services = run(
        NEW_JOB + ADD_PROTEIN
        + ADD_MOD("SEP", 5) + ADD_MOD("TPO", 5)
        + REMOVE_MOD(2)                              # the TPO row
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "Post-translational modification removed." in out
    assert "Not applied" not in out
    assert _mods(services) == [("SEP", 5)]


def test_removing_the_first_of_two_modifications_at_one_position_removes_it():
    """The other direction of the same defect: row 1 is the SEP row."""
    status, out, services = run(
        NEW_JOB + ADD_PROTEIN
        + ADD_MOD("SEP", 5) + ADD_MOD("TPO", 5)
        + REMOVE_MOD(1)
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "Post-translational modification removed." in out
    assert _mods(services) == [("TPO", 5)]


def test_the_row_removed_inside_a_variant_is_the_row_it_showed(tmp_path):
    """BUG-025's shape in the save-as variant flow: with the base's SEP@3
    ahead of the variant's own TPO@5, removing row 2 must remove TPO — the
    base's modification and the saved file must both keep SEP@3."""
    destination = tmp_path / "variant.json"
    status, out, services = run(
        NEW_JOB + ADD_PROTEIN
        + ADD_MOD("SEP", 3)                                  # the base's own PTM
        + ["7", "1", "V1"]                                   # variant editor
        + ["3", "1", "3", "1", "TPO", "5", "0", "0", "0"]    # add TPO@5
        + ["3", "1", "3", "3", "2", "0", "0", "0"]           # remove row 2 → TPO
        + ["4", str(destination), "0"]                       # save & reset, leave
        + LEAVE_DIRTY
    )
    assert status == 0
    assert "Traceback" not in out
    assert _mods(services) == [("SEP", 3)]                   # the base never moved
    document = _load(destination)
    modifications = document["sequences"][0]["protein"].get("modifications", [])
    assert [(entry["ptmType"], entry["ptmPosition"]) for entry in modifications] == [("SEP", 3)]


# -- BUG-021: a wrong-alphabet answer at the variant sequence prompt ---------


def test_a_wrong_alphabet_at_the_variant_sequence_prompt_is_refused_not_raised():
    status, out, services = run(
        NEW_JOB + ADD_RNA
        + ["7", "1", "V1"]                               # variant editor
        + ["3", "1", "1", "ACDEFG", "", ""]            # edit the RNA: protein letters
        + ["0", "0", "0"]                                # action → picker → leave
        + LEAVE_CLEAN
    )
    assert status == 0
    assert "Traceback" not in out
    assert "Not applied" in out
    assert "alphabet" in out
    # nothing was recorded and the base still reads as the user entered it
    assert services.projects.project.configuration.records[0].sequence.text == RNA


# -- the ligand editor asks for what a ligand has -----------------------------


def _replacement_prepare(services):
    services.projects.new("job")
    services.configuration.add_record("ligand", representation="ATP")
    services.configuration.add_record("protein", PROTEIN)


def test_a_ligand_edit_asks_for_its_representation_not_a_sequence(tmp_path):
    destination = tmp_path / "ligand-variant.json"
    status, out, services = run(
        ["7", "3", "1", "1", "2", "CCO", "0", "0", "4", str(destination), "0"]
        + LEAVE_CLEAN,
        prepare=_replacement_prepare,
    )
    assert status == 0
    assert "Is this ligand given as a CCD code or a SMILES string?" in out
    assert "New sequence" not in out
    # the variant file carries the SMILES; the base keeps its CCD code
    document = _load(destination)
    ligands = [entry["ligand"] for entry in document["sequences"] if "ligand" in entry]
    assert ligands and ligands[0].get("smiles") == "CCO"
    base = services.projects.project.configuration.records[0].representation
    assert isinstance(base, ByCode)


# -- cancellation leaves the configuration untouched -------------------------


def test_cancelling_every_operation_leaves_the_configuration_identical():
    """One script's worth of cancellations — a blank sequence, a blank ligand
    value, a cancelled quantity, a cancelled delete, a cancelled modification
    and a cancelled position — must leave the canonical configuration equal to
    what it was, not merely close to it."""
    services = build_services()
    services.projects.new("job")
    services.configuration.add_record("protein", PROTEIN)
    before = services.projects.project.configuration

    script = (
        ["2", "1", ""]                                  # add protein: blank sequence
        + ["2", "4", "1", ""]                           # add ligand: blank value
        + ["2", "4", "1", "ATP", "0"]                   # add ligand: cancel at quantity
        + ["3", "1", "2", "2", "0", "0"]                 # delete: cancel, back to job
        + ["3", "1", "1", "", "", "", "", "0", "0"]     # edit: keep everything
        + ["5", "2", "1", "", "0"]                      # modification: blank code
        + ["5", "2", "1", "SEP", "0", "0"]              # modification: no position
        + LEAVE_DIRTY
    )
    status, out, services = run(script, services=services)

    assert status == 0
    assert "Traceback" not in out
    # the cancellations that say so, really said so, and no operation was
    # ever reported as applied — the script cannot pass by having silently
    # done nothing at all
    assert out.count("Cancelled") >= 5
    assert "Applied." not in out
    assert "Not applied" not in out
    after = services.projects.project.configuration
    assert after == before
    assert len(after.records) == 1
    assert after.linkages == ()


def test_cancelled_entity_adds_do_not_reserve_identifiers():
    """A cancellation must not leave a half-added record or a leaked
    identifier: the next real add gets the *first* free letter."""
    services = build_services()
    services.projects.new("job")

    status, out, services = run(
        ["2", "1", ""] + ADD_PROTEIN + LEAVE_CLEAN, services=services
    )

    assert status == 0
    assert [record.ids.primary.value for record in services.projects.project.configuration.records] == ["A"]
    assert sorted(services.projects.project.configuration.identity.assigned_values()) == ["A"]
