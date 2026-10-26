"""Regression pins for the numbered-flow audit fixes (§9 wording rule).

Every P1 finding from the CLI audit: record selection, MSA modes, MSA
sources, and PTM operations are chosen from numbered menus; no prompt asks
the user to type a record letter, a mode letter, or a route letter.

The navigation is the reworked menu (see ``menu_flows``): job
1) Edit job configurations / 2) Add entity / 3) Edit entity /
5) PTM management.
"""

from __future__ import annotations

from pathlib import Path

from configbuilder.ui.present.strings import STRINGS
from configbuilder.ui.render import menus as menus_module
from tests.unit.ui.menu_flows import OPEN, PROTEIN, SEEDS, run


# -- the letter vocabulary is gone from the UI sources -----------------------


def test_no_letter_mode_or_typed_record_prompts_remain():
    """The retired prompts must not come back: record letters, MSA mode
    letters, source/route letters are all replaced by numbered menus."""
    banned = [
        "Which record (letter)",
        "Record id (e.g. A)",
        "MSA mode - p)",
        "MSA mode - a)",
        "Source - i)",
        "Templates - n)",
        "Variant keys to export",
        "Ligand (CCD code or SMILES)",
    ]
    for key, value in STRINGS.items():
        for phrase in banned:
            assert phrase not in value, "retired prompt returned: %r (%s)" % (value, key)


def test_menu_module_has_no_letter_mode_tables():
    """No single-letter mode translation tables survive in the menus."""
    source = Path(menus_module.__file__).read_text(encoding="utf-8")
    assert '"p": "paired"' not in source
    assert '"u": "unpaired"' not in source
    assert '"i", "inline"' not in source
    assert '"e", "external"' not in source


# -- the numbered flows land through the services ----------------------------


def _protein_job():
    """A job with one protein, back at the job menu."""
    return OPEN + SEEDS + PROTEIN


def test_edit_entity_uses_the_numbered_picker_and_blank_keeps_values():
    """Edit → pick by number → blank answers keep everything, then a real
    sequence change lands."""
    status, out = run(
        _protein_job()
        + ["3", "1", "1", "", "", "1", "n", "0", "0"]        # blanks + keep MSA → nothing applied
        + ["3", "1", "1", "GGUUAACCGGUUAACC", "", "1", "n", "0", "0"]  # a real sequence change
        + ["0", "2", "0"]                                  # leave → discard → exit
    )
    assert status == 0
    assert "EDIT ENTITY" in out
    assert "Which record" not in out
    assert "Not applied" not in out
    # Only the second edit — the real sequence change — was applied.
    assert out.split("EDIT ENTITY", 1)[1].count("Applied.") == 1


def test_ptm_add_picks_the_record_by_number():
    """PTM management → add a modification: the carrier is picked by number
    from the entity picker, then code + position."""
    status, out = run(
        _protein_job()
        + ["5", "2", "1", "SEP", "5", "0", "0"]  # PTM → add → record 1 → SEP @ 5
        + ["2", "0"]
    )
    assert status == 0
    assert "Post-translational modification added." in out
    assert "Not applied" not in out


def test_ptm_remove_offers_a_numbered_list():
    """With one modification present, remove offers it by number — no
    position typing."""
    status, out = run(
        _protein_job()
        + ["5", "2", "1", "SEP", "5", "0"]      # add one first
        + ["5", "4", "1", "1", "0", "0"]        # PTM → remove → record 1 → item 1
        + ["2", "0"]
    )
    assert status == 0
    assert "Post-translational modification removed." in out
    assert "Not applied" not in out


def test_ptm_edit_updates_in_place():
    status, out = run(
        _protein_job()
        + ["5", "2", "1", "SEP", "5", "0"]
        + ["5", "3", "1", "1", "TPO", "7", "0", "0"]
        + ["2", "0"]
    )
    assert status == 0
    assert "Post-translational modification updated." in out
    assert "TPO" in out


def test_ptm_remove_on_a_clean_record_says_so():
    """Nothing to remove: a clear message, never a prompt for an index."""
    status, out = run(
        _protein_job()
        + ["5", "4", "1", "0", "0", "2", "0"]  # remove on a record with none
    )
    assert status == 0
    assert "carries no post-translational modifications" in out


def test_msa_records_are_picked_by_number():
    """The alignment belongs to one record: editing it starts from the
    numbered record picker, before any mode menu appears, and the mode is
    chosen by number."""
    status, out = run(
        _protein_job()
        + ["3", "1", "1", "", "", "3", "n", "0", "0", "0", "2", "0"]
    )
    assert status == 0
    assert "A  protein" in out
    assert "MSA (multiple sequence alignment) configuration:" in out
    # the record edit and its alignment both landed
    assert out.split("EDIT ENTITY", 1)[1].count("Applied.") == 1


def test_no_wizard_front_end_remains():
    """The guided wizard is gone: no module for it."""
    import configbuilder.ui.render as render

    render_root = Path(render.__file__).parent
    assert not (render_root / "wizard.py").exists()
    assert not (render_root / "drive.py").exists()
    status, out = run(OPEN + ["0"])
    assert status == 0
    assert "wizard" not in out.lower()
