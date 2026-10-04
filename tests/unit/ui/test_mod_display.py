"""Residue-numbered modification display under entity listings.

Every place the menu lists entities — the Entities screen, the Review
screen, and the generation confirm screen — shows each record's
modifications as residue-numbered rows, the same human 1-based
numbering the position prompt uses, so an operator sees the PTMs
already on a record while editing it.
"""

from __future__ import annotations

from configbuilder.app.cli import MenuApp
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services


def _run(script, mod_positions=("1", "9"), pin=False):
    """A base job (protein AGW) with modifications at the given 1-based
    positions — SEP at residue 1 and, by default, TPO at 9, deliberately
    out of range, which the service accepts."""
    services = build_services()
    services.projects.new("exp")
    services.configuration.add_record("protein", "AGW")
    key = services.projects.project.configuration.records[0].ids.primary.value
    for position in mod_positions:
        services.configuration.add_modification(key, "SEP" if position == "1" else "TPO", position)
    console = ScriptedConsole(script)
    app = MenuApp(services, console)
    status = app.run()
    return console.transcript, status


def test_entities_screen_shows_residue_numbered_mod_rows():
    transcript, status = _run(["1", "1", "0", "0"])  # Edit -> Entities -> back out
    assert status == 0
    assert "  A  protein  3 residues" in transcript
    # The residue echo: position 1 of AGW is A.
    assert "SEP at residue 1 (A)" in transcript
    # Out-of-range positions still name the position, without a fake residue.
    assert "TPO at residue 9" in transcript


def test_review_screen_includes_mod_rows():
    transcript, status = _run(["2", "0", "0"])  # master -> Review -> back -> exit
    assert status == 0
    assert "SEP at residue 1 (A)" in transcript


def test_base_generate_preview_includes_mod_rows():
    transcript, status = _run(["4", "1", "2", "0", "0"], mod_positions=("1",))
    assert status == 0
    assert "SEP at residue 1 (A)" in transcript


def test_no_mod_block_for_unmodified_records():
    transcript, status = _run(["1", "1", "0", "0"], mod_positions=())
    assert status == 0
    assert "  A  protein  3 residues" in transcript
    assert "modifications:" not in transcript


def test_edit_flow_sees_the_mod_rows_before_the_prompts():
    """The operator choosing 2) Edit sees the PTMs in the listing that
    precedes the editor's questions."""
    transcript, status = _run(["1", "1", "2", "1", "", "", "0", "0"])
    assert status == 0
    assert "SEP at residue 1 (A)" in transcript


def test_mods_added_through_the_ui_appear_in_the_listing():
    """End to end through the menus: add a protein, add a modification
    through the bonds/modifications screen, then see the row in the
    Entities listing."""
    transcript, status = _run(
        [
            "1", "1", "1", "1", "AGW", "n", "n",  # Edit -> Entities -> add -> protein
            "0",                                 # back to Edit the job
            "3", "3", "1", "SEP", "1",            # Bonds -> add a modification
            "0",                                 # back to Edit the job
            "1", "0",                            # Entities: the listing, then back
            "0",
        ],
        mod_positions=(),
    )
    assert status == 0
    assert "Modification added." in transcript
    assert "SEP at residue 1 (A)" in transcript
