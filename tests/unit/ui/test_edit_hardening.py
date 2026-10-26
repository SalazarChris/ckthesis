"""Menu-level pins for the 2026-10-08 entity-editing hardening pass.

Each test drives the real ``MenuApp`` over a ``ScriptedConsole`` — the
interface a human uses — because the defects in that pass were reachable only
through a menu path. The manual variant editor that used to live behind the console's
job menu is gone (the ligand file workflow replaced it), so the pins that
guarded its service calls now drive those calls directly — the same
``VariantService`` methods the file workflow uses:

- BUG-021  a wrong-alphabet sequence change must be refused, never raised
- BUG-024  removing the *second* of two modifications at one position removed
           the first (the picker's payload was the position, not the row)
- the modification row a picker shows must be the row the edit removes, even
  when the base already carries a modification ahead of it (BUG-025's shape)
- a ligand change writes SMILES and leaves the base's CCD code alone
- cancellation must leave the configuration identical
"""

from __future__ import annotations

from configbuilder.model import ByCode, ByNotation
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"
RNA = "ACGUACGU"

NEW_JOB = ["1", "job"]
ADD_PROTEIN = ["2", "1", PROTEIN, "1", ""]
ADD_RNA = ["2", "3", RNA, "1"]
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


def test_the_row_removed_inside_a_variant_is_the_row_it_showed():
    """BUG-025's shape, pinned where the batch flow runs it.

    With the base's SEP@3 ahead of the spec's own TPO@5, the row the picker
    shows second is the row ``RemoveModification`` must take: the edit indexes
    the *expanded* record's list, not this spec's own additions.
    """
    services = build_services()
    projects, variants = services.projects, services.variants
    projects.new("job")
    services.configuration.add_record("protein", PROTEIN)
    services.configuration.add_modification("A", "SEP", 3)
    assert variants.add_spec_with_edit(
        "v1", "v1", "add_modification", ("TPO", 5), record_key="A"
    ).ok

    rows = variants.modification_choices("v1")
    assert [row[2] for row in rows] == ["A @ 3 (SEP)", "A @ 5 (TPO)"]
    index = next(row[0] for row in rows if row[2].endswith("(TPO)"))
    assert variants.apply_variant_edit(
        "v1", "remove_modification", index, record_key="A"
    ).ok

    expanded = variants.preview("v1")
    assert expanded.ok
    kept = [
        (modification.code.value, modification.position.value)
        for modification in expanded.variants[0].configuration.records[0].modifications
    ]
    assert kept == [("SEP", 3)]
    # the base never moved
    assert _mods(services) == [("SEP", 3)]


# -- BUG-021: a wrong-alphabet sequence change -------------------------------


def test_a_wrong_alphabet_at_the_variant_sequence_change_is_refused_not_raised():
    services = build_services()
    services.projects.new("job")
    services.configuration.add_record("rna", RNA)

    outcome = services.variants.add_spec_with_edit(
        "v1", "v1", "sequence", "ACDEFG", record_key="A"
    )

    assert not outcome.ok
    assert "alphabet" in outcome.message
    # nothing was recorded and the base still reads as the user entered it
    assert services.projects.project.configuration.records[0].sequence.text == RNA


# -- a ligand change writes the representation it was given ------------------


def test_a_ligand_variant_change_writes_smiles_and_leaves_the_base_ccd():
    services = build_services()
    services.projects.new("job")
    services.configuration.add_record("ligand", representation="ATP")

    outcome = services.variants.add_spec_with_edit(
        "v1", "v1", "component_representation", "CCO", record_key="A"
    )
    assert outcome.ok, outcome.message

    expanded = services.variants.preview("v1")
    assert expanded.ok
    changed = expanded.variants[0].configuration.records[0].representation
    assert isinstance(changed, ByNotation) and changed.text == "CCO"
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
