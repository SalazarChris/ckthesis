"""Import resolves a document's *relative* resource paths against its folder.

An AF3 file's relative paths mean "relative to this file". Saving a job with the
default *copy into the output folder* policy writes ``assets/<template>.cif``
beside the JSON and points at it relatively; without rebasing on import, a
reopened job looked for that path under the process's working directory and the
re-write was refused ("resource source 'assets/…' is missing").

``from_wire`` itself stays a pure document→model mapping (its own tests pin that
relative paths come through verbatim); the rebase happens once, in
``ProjectService``, before the model is built. These tests cover both halves.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from configbuilder.transform import from_wire, rebase_resource_paths


def _document(paths):
    protein = {"id": "A", "sequence": "ACDEFG"}
    protein.update(paths)
    return {
        "name": "rebased",
        "modelSeeds": [1],
        "sequences": [{"protein": protein}],
        "dialect": "alphafold3",
        "version": 3,
    }


def test_relative_template_and_msa_paths_become_absolute():
    document = _document(
        {
            "unpairedMsaPath": "assets/unpaired.a3m",
            "templates": [{"mmcifPath": "assets/tpl.cif",
                           "queryIndices": [0], "templateIndices": [0]}],
        }
    )
    document["userCCDPath"] = "assets/custom.cif"

    rebased = rebase_resource_paths(document, "/base/folder")

    def expected(name):
        return "/base/folder/assets/%s" % name

    protein = rebased["sequences"][0]["protein"]
    assert protein["unpairedMsaPath"] == expected("unpaired.a3m")
    assert protein["templates"][0]["mmcifPath"] == expected("tpl.cif")
    assert rebased["userCCDPath"] == expected("custom.cif")
    # The mapping is untouched.
    assert protein["templates"][0]["queryIndices"] == [0]


def test_absolute_paths_and_inline_text_are_left_alone():
    absolute = os.path.abspath(os.path.join("already", "here", "tpl.cif"))
    document = _document(
        {
            # Inline text lives in the *non*-path field; it is never a path.
            "unpairedMsa": ">query\nACDEFG\n",
            "templates": [{"mmcifPath": absolute,
                           "queryIndices": [0], "templateIndices": [0]}],
        }
    )

    rebased = rebase_resource_paths(document, "/base")

    protein = rebased["sequences"][0]["protein"]
    assert protein["templates"][0]["mmcifPath"] == absolute
    assert protein["unpairedMsa"] == ">query\nACDEFG\n"
    assert "unpairedMsaPath" not in protein


def test_a_non_document_is_returned_unchanged():
    assert rebase_resource_paths(None, "/base") is None
    assert rebase_resource_paths({"name": "x"}, None) == {"name": "x"}


def test_from_wire_keeps_relative_paths_verbatim():
    """The rebase is the caller's decision, not the parser's."""
    configuration, _notes = from_wire(
        _document({"templates": [{"mmcifPath": "tpl.cif",
                                  "queryIndices": [0], "templateIndices": [0]}]})
    )
    reference = configuration.records[0].references.items[0]
    assert reference.source.path.raw == "tpl.cif"


def test_importing_a_saved_job_rebases_the_asset_path(tmp_path):
    """The regression: reopen the saved JSON, then save it again."""
    assets = tmp_path / "assets"
    assets.mkdir()
    template = assets / "tpl.cif"
    template.write_text("data_x\n#\n", encoding="utf-8")
    saved = tmp_path / "job.json"
    saved.write_text(
        json.dumps(
            {
                "name": "reopened",
                "modelSeeds": [1],
                "sequences": [
                    {
                        "protein": {
                            "id": "A",
                            "sequence": "ACDEFG",
                            "templates": [
                                {
                                    "mmcifPath": "assets/tpl.cif",
                                    "queryIndices": [0, 1, 2, 3],
                                    "templateIndices": [3, 4, 5, 6],
                                }
                            ],
                        }
                    }
                ],
                "dialect": "alphafold3",
                "version": 3,
            }
        ),
        encoding="utf-8",
    )

    from configbuilder.ui.services import build_services

    bundle = build_services()
    assert bundle.projects.import_json_commit(str(saved)).ok

    reference = bundle.projects.project.configuration.records[0].references.items[0]
    assert Path(reference.source.path.raw) == template, "resolved to the asset"
    assert [(pair.query, pair.template) for pair in reference.index_map] == [
        (0, 3),
        (1, 4),
        (2, 5),
        (3, 6),
    ]

    # And the re-save now finds the file: copy it into a second folder.
    second = tmp_path / "second"
    plan = bundle.generation.plan_save(str(second / "job.json"), overwrite=False)
    assert plan.ok, plan.message
    result = bundle.generation.execute(plan)
    assert result.ok, result.errors
    with open(str(second / "job.json"), encoding="utf-8") as handle:
        rewritten = json.load(handle)
    assert rewritten["sequences"][0]["protein"]["templates"][0]["templateIndices"] == [
        3,
        4,
        5,
        6,
    ]
