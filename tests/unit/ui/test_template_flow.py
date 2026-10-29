"""The console's explicit template flow, through the real services and save."""

from __future__ import annotations

import json

from configbuilder.app.reference_validation import file_issue
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.menus import MenuApp
from configbuilder.ui.services import build_services

SEQUENCE = "ACDEFGHIKL"


def _save(script, destination):
    console = ScriptedConsole(script + ["6", str(destination), "0", "0"])
    status = MenuApp(build_services(), console).run()
    assert status == 0
    assert "Traceback" not in console.transcript
    assert destination.exists(), console.transcript[-2000:]
    return json.loads(destination.read_text(encoding="utf-8")), console.transcript


def _protein_script(*template_answers):
    return [
        "1",
        "template-job",
        "2",
        "1",
        SEQUENCE,
        "1",  # keep the default MSA behavior
        "y",  # use structural templates
        "3",  # provide an explicit list
        *template_answers,
    ]


#: A real single-chain protein template of ten residues. ``_entity_poly`` is
#: what AF3's ``templateIndices`` address, so a stub with only an
#: ``_atom_site`` row would (correctly) be refused as having no polymer chain.
def _cif(path, name="template"):
    path.write_text(
        "data_%s\n"
        "#\n"
        "_entity_poly.entity_id 1\n"
        "_entity_poly.type 'polypeptide(L)'\n"
        "_entity_poly.pdbx_strand_id A\n"
        "_entity_poly.pdbx_seq_one_letter_code ACDEFGHIKL\n"
        "#\n" % name,
        encoding="utf-8",
    )
    return path


def test_two_templates_keep_their_own_paths_and_index_maps(tmp_path):
    first = _cif(tmp_path / "first.cif", "first")
    second = _cif(tmp_path / "second.mmcif", "second")

    document, transcript = _save(
        _protein_script(
            str(first),
            " 0:5, 1:6, 2:7 ",
            "y",
            str(second),
            "0:0,1:1",
            "n",
        ),
        tmp_path / "two-templates.json",
    )

    assert "query:template residue index pairs" in transcript
    protein = document["sequences"][0]["protein"]
    templates = protein["templates"]
    assert len(templates) == 2
    assert templates[0]["mmcifPath"].endswith("first.cif")
    assert templates[0]["queryIndices"] == [0, 1, 2]
    assert templates[0]["templateIndices"] == [5, 6, 7]
    assert templates[1]["mmcifPath"].endswith("second.mmcif")
    assert templates[1]["queryIndices"] == [0, 1]
    assert templates[1]["templateIndices"] == [0, 1]
    assert templates[0]["mmcifPath"] != templates[1]["mmcifPath"]


def test_bad_files_and_bad_pairs_are_refused_and_reasked(tmp_path):
    missing = tmp_path / "missing.cif"
    wrong_extension = tmp_path / "not-a-cif.txt"
    wrong_extension.write_text("data_x\n", encoding="utf-8")
    empty = tmp_path / "empty.cif"
    empty.write_text("", encoding="utf-8")
    valid = _cif(tmp_path / "valid.cif")

    document, transcript = _save(
        _protein_script(
            str(missing),
            str(wrong_extension),
            str(empty),
            str(valid),
            "0-5",
            "0:-1",
            "10:0",
            "",
            "0:5,1:6",
            "n",
        ),
        tmp_path / "retried.json",
    )

    assert "the file does not exist" in transcript
    assert "the file must end in .cif or .mmcif" in transcript
    assert "the file is empty" in transcript
    assert "'0-5' is not query:template" in transcript
    assert "'-1' is not query:template" in transcript
    assert "query index 10 is outside the target sequence (length 10; valid 0-9)" in transcript
    assert "At least one query:template pair is required" in transcript
    protein = document["sequences"][0]["protein"]
    templates = protein["templates"]
    assert len(templates) == 1
    assert templates[0]["mmcifPath"].endswith("valid.cif")
    assert templates[0]["queryIndices"] == [0, 1]
    assert templates[0]["templateIndices"] == [5, 6]


def test_template_file_rules_reject_directories_and_unreadable_files(
    tmp_path, monkeypatch
):
    directory = tmp_path / "folder.cif"
    directory.mkdir()
    assert "the path is not a regular file" in file_issue(str(directory)).message

    valid = _cif(tmp_path / "valid.cif")

    def deny(*args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr("builtins.open", deny)
    assert "the file cannot be read" in file_issue(str(valid)).message


def test_cancelling_after_a_valid_template_commits_nothing(tmp_path):
    first = _cif(tmp_path / "first.cif")

    document, transcript = _save(
        _protein_script(str(first), "0:5", "y", "0"),
        tmp_path / "cancelled.json",
    )

    assert "Template collection cancelled - the template setting is unchanged." in transcript
    protein = document["sequences"][0]["protein"]
    assert "templates" not in protein


def test_the_no_template_path_still_skips_collection(tmp_path):
    document, transcript = _save(
        [
            "1",
            "no-template-job",
            "2",
            "1",
            SEQUENCE,
            "1",  # keep the default MSA behavior
            "n",  # no structural templates
        ],
        tmp_path / "no-template.json",
    )

    assert "Template 1 mmCIF file" not in transcript
    protein = document["sequences"][0]["protein"]
    assert "templates" not in protein
