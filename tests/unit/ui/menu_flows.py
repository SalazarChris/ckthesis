"""Shared keystroke scripts for the simplified menu.

The menu navigation is written down once here, so a menu change is one
edit instead of one per test file:

    master    1 Edit the job   2 Review configuration   3 Variants
              4 Generate JSON  5 Open saved work        6 Import AF3 JSON
    edit      1 Entities       2 Job settings           3 Bonds, modifications
                                                         & custom components
    entities  1 Add  2 Edit  3 Delete

Every constant is a **self-contained unit that starts and ends at the
master menu**, so units concatenate: ``OPEN + SEEDS + PROTEIN + [...]``.
The two "_OPEN" constants deliberately stop inside a submenu, for the
tests that work there.
"""

from __future__ import annotations

from configbuilder.app.cli import MenuApp
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services

PROTEIN_SEQUENCE = "ACDEFGHIKLMNPQRSTVWY"

# -- openings -----------------------------------------------------------------

OPEN = ["1", "Oct4_POU"]          # start screen: 1 New job, then a name
OPEN_BLANK_NAME = ["1", ""]       # blank: the service mints config-NNN

# -- whole units, each ending back at the master menu -------------------------

# Edit the job → Job settings → seeds → version → back → back
SEEDS = ["1", "2", "3", "1 2 3 4", "2", "3", "0", "0"]

# Edit the job → Entities → Add → Protein → sequence → MSA? templates? → back → back
PROTEIN = ["1", "1", "1", "1", PROTEIN_SEQUENCE, "", "", "0", "0"]

# The same, with a shorter sequence (the MSA tests) — still ends at master.
SHORT_PROTEIN = ["1", "1", "1", "1", "ACDEFGHIKLMNP", "", "", "0", "0"]

# Edit the job → Entities → Add → DNA → 5'-to-3' strand (a duplex: two records)
DNA = ["1", "1", "1", "2", "ATGC"]

# Edit the job → Entities → Add → RNA → sequence → MSA? (no templates) → back → back
RNA = ["1", "1", "1", "3", "ACGU", "", "0", "0"]

# master 3 (Variants) → 3 (from a sequence file)
BATCH_FLOW = ["3", "3"]

# -- openings that stop inside a submenu --------------------------------------

# Edit the job → Entities → Add → Protein → sequence → MSA? templates? — the
# add flow ends at the *Entities* screen, which is where the MSA work starts.
PROTEIN_THEN_ENTITIES = ["1", "1", "1", "1", "ACDEFGHIKLMNP", "", ""]

# From the Entities screen: Edit an entity, then record 1, then two blank
# answers (keep the sequence and the description) — which lands on the
# record's own MSA question, the only place an alignment is asked for.
MSA_EDIT = ["2", "1", "", ""]


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
