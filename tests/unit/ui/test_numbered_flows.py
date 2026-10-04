"""Regression pins for the numbered-flow audit fixes (§9 wording rule).

Every P1 finding from the CLI audit: record selection, MSA modes, MSA
sources, and template routes are chosen from numbered menus; no prompt
anywhere asks the user to type a record letter, a mode letter, a route
letter, or a comma-separated variant-key list. The strings are pinned
directly against the UI sources (the wording registry holds them), and
the scripted flows prove the numbered paths land through the services.

The navigation is the simplified menu (see ``menu_flows``): master
1) Edit the job → 1) Entities / 3) Bonds, modifications & custom
components, and master 4) Generate JSON for the write path.
"""

from __future__ import annotations

from pathlib import Path

from configbuilder.ui.render import menus as menus_module
from configbuilder.ui.present.strings import STRINGS
from tests.unit.ui.menu_flows import OPEN, PROTEIN, SEEDS, run


# -- the letter vocabulary is gone from the UI sources -----------------------


def test_no_letter_mode_or_typed_record_prompts_remain():
    """The retired prompts must not come back: record letters, MSA mode
    letters, source/route letters, and the comma-separated variant-key
    prompt are all replaced by numbered menus."""
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
    assert '"n", "")' not in source  # the templates route's search default


# -- the numbered flows land through the services ----------------------------


def _protein_job():
    """A job with one protein, back at the master menu."""
    return OPEN + SEEDS + PROTEIN


def test_edit_entity_uses_the_numbered_picker_and_blank_keeps_values():
    """Edit → pick by number → blank answers keep everything (no accidental
    description clears), then a real sequence change lands."""
    status, out = run(
        _protein_job()
        + ["1", "1", "2", "1", "", "", "n", "n", "0", "0",            # blank blank → nothing applied
           "1", "1", "2", "1", "GGUUAACCGGUUAACC", "", "n", "n",        # a real sequence change, no MSA/templates
           "0", "0", "0"]
    )
    assert status == 0
    # The edit flow asked through the entity picker, not a letter prompt.
    assert "Edit Entity" in out
    assert "Which record" not in out
    assert "Not applied" not in out
    # Only the second edit — the real sequence change — was applied.
    assert out.split("Edit Entity", 1)[1].count("Applied.") == 1


def test_add_modification_picks_the_record_by_number():
    """Bonds, modifications & custom components → add a modification: the
    carrier is picked by number from the entity picker, then code + position."""
    status, out = run(
        _protein_job()
        + ["1", "3", "3", "1", "SEP", "5", "0", "0", "0"]  # add a modification on record 1
    )
    assert status == 0
    assert "Modification added." in out
    assert "Not applied" not in out


def test_remove_modification_offers_a_numbered_list():
    """With one modification present, remove offers it by number —
    no position typing, and the empty case is a clean message."""
    status, out = run(
        _protein_job()
        + ["1", "3", "3", "1", "SEP", "5", "0", "0",      # add one first
           "1", "3", "4", "1", "1", "0", "0", "0", "0"]   # remove: record 1, item 1
    )
    assert status == 0
    assert "Modification removed." in out
    assert "Not applied" not in out


def test_remove_modification_on_a_clean_record_says_so():
    """Nothing to remove: a clear message, never a prompt for an index."""
    status, out = run(
        _protein_job()
        + ["1", "3", "4", "1", "0", "0", "0"]  # remove on a record with none
    )
    assert status == 0
    assert "carries no modifications" in out


def test_bonded_pair_picks_both_records_by_number():
    """Add a bond: both endpoints come from the numbered entity picker
    (the same record twice is legitimate)."""
    status, out = run(
        _protein_job()
        + ["1", "3", "1", "1", "12", "SG", "1", "37", "SG", "0", "0", "0"]
    )
    assert status == 0
    assert "Linkage added." in out
    assert "Currently: 1 linkage(s)" in out
    assert "Not applied" not in out


def test_msa_records_are_picked_by_number():
    """The alignment belongs to one record: editing it starts from the
    numbered record picker, before any mode menu appears, and the mode is
    chosen by number."""
    status, out = run(
        _protein_job()
        + ["1", "1", "2", "1", "", "", "y", "1", "n", "0", "0", "0"]  # edit record 1 → MSA automatic, no templates
    )
    assert status == 0
    assert "A  protein" in out
    assert "MSA mode:" in out
    assert out.split("Edit Entity", 1)[1].count("Applied.") == 1
    assert "Not applied" not in out


# -- the generate screen: numbered selection, no key lists --------------------


def _two_variants():
    return (
        ["3", "1", "1", "WT", "1", "1", "", "0", "0"]     # Variants → create WT
        + ["3", "1", "1", "ALT", "1", "1", "", "0", "0"]  # Variants → create ALT
    )


def test_generate_select_variants_is_a_numbered_multi_select(tmp_path):
    """Generate → select variants: numbers (and repeats) pick variants; no
    comma-separated key list is ever requested."""
    status, out = run(
        _protein_job()
        + _two_variants()
        + ["4", "4", str(tmp_path), "3", "1 2", "y", "0", "0"]  # Generate → set dir → select 1 2 → write
    )
    assert status == 0
    assert "Select variants to export" in out
    assert "Variant keys to export" not in out
    assert "Wrote " in out


def test_generate_select_repeats_are_ignored(tmp_path):
    """Typing a number twice selects that variant once."""
    status, out = run(
        _protein_job()
        + _two_variants()
        + ["4", "4", str(tmp_path), "3", "1 1 2", "y", "0", "0"]
    )
    assert status == 0
    assert "Wrote " in out


def test_generate_select_cancel_writes_nothing(tmp_path):
    """Backing out of the multi-select (0) leaves the disk untouched."""
    status, out = run(
        _protein_job()
        + ["3", "1", "1", "WT", "1", "1", "", "0", "0"]   # one variant
        + ["4", "3", "0", "0", "0"]                       # Generate → select → 0 → back out
    )
    assert status == 0
    assert "Wrote " not in out


def test_master_menu_names_each_goal_once():
    """The seven master actions are the whole application; nothing is named
    twice and no development-only entry survives.

    ``5`` is the explicit save action (write the job's AF3 JSON) and ``6``
    recovers the working copy. The save action has to exist: without it the
    only route to a file was the Generate screen, and the menu's "working
    copy is kept automatically" line read as "your file is already saved".
    """
    status, out = run(_protein_job() + ["0"])
    assert status == 0
    assert "1) Edit the job" in out
    assert "2) Review configuration" in out
    assert "3) Variants" in out
    assert "4) Generate JSON" in out
    assert "5) Save the job (write its AF3 JSON)" in out
    assert "6) Recover the last working copy" in out
    assert "7) Import an AF3 JSON file" in out
    assert "Guided wizard" not in out
    assert "Job Builder" not in out


def test_generate_screen_numbering_is_stable_without_variants(tmp_path):
    """The same digit reaches the same action whether or not variants exist.

    With no variants the screen used to renumber "change the output
    directory" onto ``2``; the variant rows now stay on screen and say what
    they need instead.
    """
    status, out = run(
        _protein_job()
        + ["4", "2", "4", str(tmp_path), "1", "1", "0", "0"]
    )
    assert status == 0
    assert "no variants to write yet" in out
    assert "4) Change the output directory" in out
    assert "Wrote " in out


def test_generate_screen_without_variants_offers_the_job_itself():
    """With no variants the Generate screen still offers the job's own
    JSON, and an invalid choice just says so."""
    status, out = run(OPEN + ["4", "9", "2", "0", "0"])
    assert status == 0
    assert "Generate this job's JSON" in out
    assert "Not a valid choice: '9'" in out
    assert "variants to generate" not in out


def test_no_wizard_front_end_remains():
    """The guided wizard is gone: no menu entry, and no module for it."""
    import configbuilder.ui.render as render

    render_root = Path(render.__file__).parent
    assert not (render_root / "wizard.py").exists()
    assert not (render_root / "drive.py").exists()
    status, out = run(OPEN + ["0"])
    assert status == 0
    assert "wizard" not in out.lower()
