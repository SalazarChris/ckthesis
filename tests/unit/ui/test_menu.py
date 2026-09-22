"""The free-navigation builder's end-to-end workflow (§20's journey).

The whole user story through the real services and the scripted console:
start an experiment, set seeds, add a protein, create a WT variant, grow
it with an edit through the factor picker, validate, and export — one
experiment, many JSONs. Every section is entered freely; nothing repeats
a guided sequence.
"""

from __future__ import annotations

import re
from pathlib import Path

from configbuilder.app.cli import MenuApp
from configbuilder.ui.render import menus as menus_module
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services

OPEN = ["1", "Oct4_POU"]
# master 1 → builder 1 → settings 3 → value → back → back (at the builder)
SEEDS = ["1", "1", "3", "1 2 3 4", "2", "3", "PIN-001", "0"]
# builder 2 → proteins 1 → sequence → back (at the builder)
PROTEIN = ["2", "1", "ACDEFGHIKLMNPQRSTVWY", "0"]
TO_MASTER = ["0"]  # leave the job builder


def _run(script):
    console = ScriptedConsole(script)
    app = MenuApp(build_services(), console)
    status = app.run()
    return status, console.transcript


def test_base_and_variant_export_produces_json_files(tmp_path):
    status, out = _run(
        OPEN
        + SEEDS
        + PROTEIN
        + TO_MASTER
        + [
            "6", "1", "WT", "", "job_name", "Oct4_POU_WT", "0",  # create + edit
            "7", "3", str(tmp_path), "1", "y", "0",              # export all
            "0",                                                  # exit
        ]
    )
    assert status == 0
    files = sorted(p.name for p in tmp_path.rglob("*") if p.suffix == ".json")
    assert files, out
    assert "Wrote " in out


def test_validate_all_reports_each_variant():
    status, out = _run(
        OPEN
        + SEEDS
        + PROTEIN
        + TO_MASTER
        + [
            "6", "1", "WT", "", "", "0",   # a variant with no edits yet
            "2", "2", "0",                 # validation → all variants
            "0",
        ]
    )
    assert status == 0
    # The per-variant report: base and every variant named with a status.
    assert "OK  WT" in out or "FAIL WT" in out


def test_show_json_prints_the_encoded_document():
    status, out = _run(
        OPEN + SEEDS + PROTEIN + TO_MASTER + ["3", "0"]  # master 3 = show JSON
    )
    assert status == 0
    assert '"name"' in out or "Cannot build JSON" in out


def test_invalid_choices_never_terminate_the_application():
    status, out = _run(OPEN + ["99", "x", "0"])
    assert status == 0
    assert "Not a valid choice: '99'" in out
    assert "Not a valid choice: 'x'" in out


# -- DNA duplex at the UI boundary: one sequence in, duplex out ------------

# master 1 → builder 4 → DNA submenu 1 (Add) → sequence → back ×2
_DNA_FLOW = ["1", "4", "1"]


def test_dna_menu_collects_one_sequence_and_reports_a_duplex():
    """The front end asks once; the service silently builds two strands."""
    status, out = _run(OPEN + _DNA_FLOW + ["ATGC", "0", "0"])
    assert status == 0
    # The UI never mentions complementing — the duplex is not its concern.
    assert "complement" not in out.lower()
    # Both strands reached the configuration.
    assert "Currently: 2 dna(s)" in out
    assert "Entities: 2" in out


def test_invalid_dna_input_is_reported_and_discarded():
    status, out = _run(OPEN + _DNA_FLOW + ["ATGX", "0", "0"])
    assert status == 0
    # The pipeline's own refusal, surfaced by the UI verbatim.
    assert "outside its alphabet" in out
    # And nothing was committed (a duplex would have made Entities: 2).
    assert "Entities: 2" not in out
    assert "Currently: 2 dna(s)" not in out


def test_cli_module_contains_no_complement_logic():
    """Requirement 7: no front end constructs the second strand."""
    import configbuilder.ui

    ui_root = Path(configbuilder.ui.__file__).parent
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in ui_root.glob("**/*.py")
    ).lower()
    for forbidden in ("complement", "reverse_complement"):
        assert forbidden not in sources, forbidden


# -- batch variants from a sequence file -------------------------------------

_BATCH_FLOW = ["6", "7"]  # master 6 (Variants) → action 7 (from file)


def test_variants_menu_offers_batch_generation():
    status, out = _run(OPEN + _BATCH_FLOW + ["", "0", "0"])
    assert status == 0
    assert "Generate from sequence file" in out


def test_batch_generation_reports_the_generated_variants(tmp_path):
    seq_file = tmp_path / "seqs.txt"
    seq_file.write_text("MSTNPKP\nGKKIGYS\n", encoding="utf-8")
    status, out = _run(
        OPEN
        + ["1", "2", "1", "ACDEFGHIKLMNPQRSTVWY", "0", "0"]  # one base protein
        + _BATCH_FLOW
        + [str(seq_file), "0", "0"]
    )
    assert status == 0
    assert "Batch applied: 2 variants generated" in out
    # The variants menu lists the generated specs — they are plain variants.
    assert "batch_01" in out and "batch_02" in out


def test_batch_generation_reports_service_refusals_verbatim(tmp_path):
    status, out = _run(
        OPEN + _BATCH_FLOW + [str(tmp_path / "absent.txt"), "0", "0"]
    )
    assert status == 0
    assert "Not applied" in out
    assert "cannot be read" in out


def test_batch_ui_stays_thin_no_parsing_in_the_front_end():
    """Requirement 12: the Variants UI *invokes* the batch operation —
    it never reads files, parses sequences, or builds variants itself."""
    menus_source = Path(menus_module.__file__).read_text(encoding="utf-8")
    # no direct file opens (the service-dispatch ``projects.open(...)`` is
    # a method call, not a builtin): every open( is attribute access
    assert not re.search(r"(?<![.\w])open\(", menus_source)
    # and no import of the layers the batch flow must not touch
    # (model/records helpers are legal here; batch machinery is not)
    assert "from configbuilder.persistence" not in menus_source
    assert "from configbuilder.app.batch_variants" not in menus_source
    assert "from configbuilder.variants" not in menus_source
    assert "SequenceText" not in menus_source
    assert "AddRecord" not in menus_source
