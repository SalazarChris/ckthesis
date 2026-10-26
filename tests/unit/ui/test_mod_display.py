"""Residue-numbered modification display under entity listings.

Wherever the menu shows a record's modifications — the PTM view, the
selected-entity screen, and the save summary — it shows them as
residue-numbered rows using the same human 1-based numbering the position
prompt uses, so an operator sees the PTMs already on a record.
"""

from __future__ import annotations

from configbuilder.app.cli import MenuApp
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services


def _run(script, mod_positions=("1", "9")):
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


def test_ptm_view_shows_residue_numbered_mod_rows():
    transcript, status = _run(["5", "1", "0", "0", "0"])  # job -> PTM -> view -> back -> exit
    assert status == 0
    # The residue echo: position 1 of AGW is A.
    assert "SEP at residue 1 (A)" in transcript
    # Out-of-range positions still name the position, without a fake residue.
    assert "TPO at residue 9" in transcript


def test_save_summary_includes_mod_rows(tmp_path):
    transcript, status = _run(["6", str(tmp_path / "out.json"), "0", "0"])
    assert status == 0
    assert "SEP at residue 1 (A)" in transcript


def test_selected_entity_screen_includes_mod_rows():
    transcript, status = _run(["3", "1", "0", "0", "0"])  # edit entity -> record A -> back
    assert status == 0
    assert "A  protein  3 residues" in transcript
    assert "Entity: A  protein  3 residues" in transcript
    assert "SEP at residue 1 (A)" in transcript


def test_no_mod_block_for_unmodified_records():
    transcript, status = _run(["5", "1", "0", "0", "0"], mod_positions=())
    assert status == 0
    assert "No post-translational modifications are set" in transcript
    assert "SEP at residue" not in transcript


def test_mods_added_through_the_ui_appear_in_the_view():
    """End to end through the menus: add a protein, add a modification
    through the PTM screen, then see the row when the view is redrawn."""
    transcript, status = _run(
        [
            "2", "1", "AGW", "1", "n",   # add a protein (default MSA, no templates)
            "5", "2", "1", "SEP", "1",   # PTM -> add -> record A -> SEP @ 1
            "5", "1",                     # PTM -> view
            "0", "0", "0",
        ],
        mod_positions=(),
    )
    assert status == 0
    assert "Post-translational modification added." in transcript
    assert "SEP at residue 1 (A)" in transcript
