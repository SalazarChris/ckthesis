"""Shared keystroke scripts for the reworked menu.

The navigation is written down once here, so a menu change is one edit
instead of one per test file:

    main    1 New job        2 Open a JSON file      0 Exit
    job     1 Edit config    2 Add entity   3 Edit entity
            4 Custom CCD     5 PTM          6 Save and show summary
            7 Variants       0 Return to main menu
    config  1 Job name       2 Model seeds  3 JSON version   0 Back
    add     1 Protein        2 DNA          3 RNA            4 Ligand
    edit    1 Edit           2 Delete       0 Back

Every constant is a **self-contained unit that starts and ends at the job
menu**, so units concatenate: ``OPEN + SEEDS + PROTEIN + [...]``. The
``_THEN_*`` constants deliberately stop inside a submenu.
"""

from __future__ import annotations

from configbuilder.app.cli import MenuApp
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services

PROTEIN_SEQUENCE = "ACDEFGHIKLMNPQRSTVWY"

# -- openings -----------------------------------------------------------------

OPEN = ["1", "Oct4_POU"]          # main: 1 New job, then a name
OPEN_BLANK_NAME = ["1", ""]       # blank: the service names it "Untitled job N"
OPEN_FILE = ["2"]                 # main: 2 Open a JSON file (then the picker)

# -- whole units, each ending back at the job menu ----------------------------

# Job → Edit job configurations → seeds → specific values → back
SEEDS = ["1", "2", "1", "1 2 3 4", "0"]

# Job → Add entity → Protein → sequence → MSA? templates? → back at the job menu
PROTEIN = ["2", "1", PROTEIN_SEQUENCE, "", ""]

SHORT_PROTEIN = ["2", "1", "ACDEFGHIKLMNP", "", ""]

# Job → Add entity → DNA → sequence → yes to complement → back at job menu
DNA = ["2", "2", "ATGC", "1"]

# Job → Add entity → RNA → sequence → MSA? → job menu
RNA = ["2", "3", "ACGU", ""]

# -- openings that stop inside a submenu --------------------------------------

# Job → Add entity → Protein → sequence → MSA? templates? — stops back at the
# job menu (the add flow owns the MSA/template questions now).
PROTEIN_THEN_EDIT = ["2", "1", PROTEIN_SEQUENCE, "", ""]

# From the job menu: 3 Edit entity → pick record 1 → 1 Edit → two blank answers
# (keep the sequence and the description) — which lands on the record's own MSA
# question, the only place an alignment is asked for.
EDIT_ENTITY_FIELDS = ["3", "1", "1", "", ""]


def protein_job(sequence: str = PROTEIN_SEQUENCE):
    """A job with one protein already recorded, services in hand."""
    services = build_services()
    services.projects.new("exp")
    services.configuration.add_record("protein", sequence)
    return services


def run(script, services=None):
    """Drive the menu over ``script`` and return ``(status, transcript)``."""
    console = ScriptedConsole(script)
    app = MenuApp(services if services is not None else build_services(), console)
    return app.run(), console.transcript
