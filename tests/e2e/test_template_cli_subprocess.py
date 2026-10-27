"""Structural templates through the real console, as a user runs it.

The interface is menu-driven, so these tests start the real process the user
starts — ``python af3builder.py`` — from a working directory of their own and
answer its prompts through its own standard input. Nothing imports the
services: a break in the menu, the prompt order, the reference rules or the
writer shows up here.

The committed fixtures in ``manual_test_data/af3_builder/templates`` are
attached for real, the job is saved as AF3 JSON, and the file on disk is read
back. The assertions are on that JSON: the template belongs to the protein
entity, the two index arrays are the expected pairs, they are the same length,
the template file travelled beside the JSON, and reopening the saved job and
saving it again does not change the mapping.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "af3builder.py"
TEMPLATES = ROOT / "manual_test_data" / "af3_builder" / "templates"
RESOLVED = TEMPLATES / "template_fully_resolved.cif"
UNRESOLVED = TEMPLATES / "template_unresolved_residues.cif"
EMPTY = TEMPLATES / "template_empty.cif"
MALFORMED = TEMPLATES / "template_malformed.cif"
NO_RECORDS = TEMPLATES / "template_no_records.cif"

pytestmark = pytest.mark.skipif(
    not LAUNCHER.exists() or not RESOLVED.exists() or not UNRESOLVED.exists(),
    reason="the launcher or the committed template fixtures are missing",
)


def _run(tmp_path, answers):
    """Start the console exactly as a user does and answer its prompts."""
    script = "\n".join(str(answer) for answer in answers) + "\n"
    return subprocess.run(
        [sys.executable, str(LAUNCHER)],
        input=script,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )


def _attach_answers(name, sequence, template, pairs, destination, another="n"):
    """New job → protein → MSA default → templates → list → pairs → save."""
    return [
        "1",            # main menu: new job
        name,
        "2",            # job menu: add entity
        "1",            # protein
        sequence,
        "1",            # keep the MSA setting (automatic)
        "y",            # use structural templates
        "3",            # provide mmCIF files and residue index pairs
        str(template),  # the picker takes a path
        pairs,
        another,        # add another template?
        "6",            # job menu: save and show summary
        str(destination),
        "0",            # leave the job (it was just saved)
        "0",            # exit
    ]


def _templates(path):
    with open(str(path), encoding="utf-8") as handle:
        document = json.load(handle)
    return document["sequences"][0]["protein"]["templates"]


# -- fixture A ---------------------------------------------------------------


def test_the_console_writes_a_fully_resolved_template_mapping(tmp_path):
    target = tmp_path / "resolved.json"

    completed = _run(
        tmp_path,
        _attach_answers("tpl-a", "ACDEFG", RESOLVED, "0:0,1:1,2:2,3:3,4:4,5:5", target),
    )

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "Not applied" not in completed.stdout
    assert "Saved to" in completed.stdout

    templates = _templates(target)
    assert len(templates) == 1
    assert templates[0]["queryIndices"] == [0, 1, 2, 3, 4, 5]
    assert templates[0]["templateIndices"] == [0, 1, 2, 3, 4, 5]
    assert len(templates[0]["queryIndices"]) == len(templates[0]["templateIndices"])
    assert templates[0]["mmcifPath"].replace("\\", "/") == (
        "assets/template-fully-resolved.cif"
    )
    copied = tmp_path / "assets" / "template-fully-resolved.cif"
    assert copied.is_file()
    assert copied.read_bytes() == RESOLVED.read_bytes()


# -- fixture B: unresolved residues ------------------------------------------


def test_the_console_writes_the_unresolved_residue_mapping(tmp_path):
    """queryIndices 0-3 with templateIndices 3-6: the full polymer's positions."""
    target = tmp_path / "partial.json"

    completed = _run(
        tmp_path,
        _attach_answers(
            "tpl-b", "DEFG", UNRESOLVED, "0:3,1:4,2:5,3:6", target
        ),
    )

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "Not applied" not in completed.stdout

    template = _templates(target)[0]
    assert template["queryIndices"] == [0, 1, 2, 3]
    assert template["templateIndices"] == [3, 4, 5, 6]
    assert template["templateIndices"] != [0, 1, 2, 3]
    assert len(template["queryIndices"]) == len(template["templateIndices"])


def test_reopening_and_resaving_keeps_the_mapping(tmp_path):
    """Save → open the saved file → save again: byte-for-byte same mapping.

    This is the round trip that used to be refused: the saved job pointed at
    ``assets/<template>.cif`` and the reopened job looked for that path under
    the process's working directory ("resource source ... is missing").
    """
    first = tmp_path / "first.json"
    assert (
        _run(
            tmp_path,
            _attach_answers(
                "tpl-b", "DEFG", UNRESOLVED, "0:3,1:4,2:5,3:6", first
            ),
        ).returncode
        == 0
    )
    second = tmp_path / "second.json"

    completed = _run(
        tmp_path,
        [
            "2",              # main menu: open a JSON file
            str(first),
            "6",              # job menu: save and show summary
            str(second),
            "0",
            "0",
        ],
    )

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Not applied" not in completed.stdout, completed.stdout[-800:]
    assert _templates(second) == _templates(first)
    assert _templates(second)[0]["templateIndices"] == [3, 4, 5, 6]


# -- the invalid fixture -----------------------------------------------------


def test_the_console_refuses_an_empty_template_and_keeps_the_job(tmp_path):
    target = tmp_path / "refused.json"

    # The file prompt re-asks after a rejection, so the second answer is the
    # cancel token rather than a pair list.
    completed = _run(
        tmp_path,
        _attach_answers("tpl-c", "ACDEFG", EMPTY, "0", target, another="n"),
    )

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "cannot be used: the file is empty" in completed.stdout
    assert "Template collection cancelled" in completed.stdout
    assert "Saved to" in completed.stdout
    # The job saved normally and carries no template: nothing was half-attached.
    assert target.is_file()
    with open(str(target), encoding="utf-8") as handle:
        protein = json.load(handle)["sequences"][0]["protein"]
    assert protein == {"id": "A", "sequence": "ACDEFG"}


@pytest.mark.parametrize(
    "template, fragment",
    (
        (MALFORMED, "the loop starting at line 9 declares 3 tags"),
        (NO_RECORDS, "no _atom_site, _entity_poly, _struct_asym or _entity records"),
    ),
)
def test_the_console_refuses_a_template_that_is_not_a_structure(
    tmp_path, template, fragment
):
    """The same refusal the window makes: an unusable mmCIF is not attached."""
    target = tmp_path / "not-a-structure.json"

    completed = _run(
        tmp_path,
        _attach_answers("tpl-d", "ACDEFG", template, "0", target, another="n"),
    )

    assert completed.returncode == 0, completed.stderr[-800:]
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    assert "cannot be used" in completed.stdout
    assert fragment in completed.stdout
    assert "Template collection cancelled" in completed.stdout
    assert target.is_file()
    with open(str(target), encoding="utf-8") as handle:
        protein = json.load(handle)["sequences"][0]["protein"]
    assert protein == {"id": "A", "sequence": "ACDEFG"}
