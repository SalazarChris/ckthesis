"""Work preservation: the job in hand survives refusals and bad input.

The builder keeps the current job in memory and writes only AF3 JSON on
request. These tests pin the service behaviour the promises rest on: a bad
import is refused with a reason and leaves the current job untouched, and a
confirmed open installs exactly what the preview described.
"""

from __future__ import annotations

import json

from configbuilder.app.project_service import ProjectService

PROTEIN_SEQUENCE = "ACDEFGHIKLMNPQRSTVWY"

AF3_JSON = {
    "name": "imported-job",
    "modelSeeds": [7],
    "sequences": [{"protein": {"id": "A", "sequence": PROTEIN_SEQUENCE}}],
    "dialect": "alphafold3",
    "version": 3,
}


def _write(tmp_path, document, name="input.json"):
    path = tmp_path / name
    path.write_text(
        document if isinstance(document, str) else json.dumps(document),
        encoding="utf-8",
    )
    return path


# -- refusals never cost the job ----------------------------------------------


def test_a_bad_import_is_refused_and_the_current_job_is_kept(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    projects.new("Kept")

    not_json = _write(tmp_path, "{ this is not json", "bad.json")
    assert not projects.import_json_preview(str(not_json)).ok
    assert not projects.import_json_commit(str(not_json)).ok

    # valid JSON, but not a legal AF3 document: still a clean refusal with a
    # reason, never a traceback and never a half-installed job
    not_af3 = _write(
        tmp_path,
        {"name": "x", "modelSeeds": [1], "sequences": [{"protein": {"id": "A"}}]},
        "not-af3.json",
    )
    preview = projects.import_json_preview(str(not_af3))
    assert not preview.ok and preview.message
    commit = projects.import_json_commit(str(not_af3))
    assert not commit.ok and commit.message

    assert projects.project.configuration.metadata.name == "Kept"
    assert projects.project.configuration.records == ()


def test_importing_a_directory_says_so_instead_of_permission_denied(tmp_path, monkeypatch):
    """Pointing the picker at a folder is an ordinary mistake — the file
    listing shows directories too. The refusal names the real mistake and
    the open job is untouched."""
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    projects.new("Kept")

    preview = projects.import_json_preview(str(tmp_path))
    assert not preview.ok
    assert "is a directory" in preview.message
    commit = projects.import_json_commit(str(tmp_path))
    assert not commit.ok
    assert "is a directory" in commit.message

    assert projects.project.configuration.metadata.name == "Kept"


def test_the_confirmed_import_installs_what_was_previewed(tmp_path, monkeypatch):
    """The confirm installs the document the preview screen described:
    preview and commit must not be two independent reads of the file."""
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    path = _write(tmp_path, AF3_JSON, "af3.json")
    preview = projects.import_json_preview(str(path))
    assert preview.ok
    assert preview.summary["job_name"] == "imported-job"

    # the file changes while the confirm screen is on display
    _write(tmp_path, dict(AF3_JSON, name="changed-behind-you"), "af3.json")

    result = projects.import_json_commit(str(path))
    assert result.ok
    configuration = projects.project.configuration
    assert configuration.metadata.name == "imported-job", (
        "what landed must be what the preview summarised"
    )
    assert list(configuration.seeds.values) == [7]


def test_a_commit_with_no_preview_reads_the_file_then(tmp_path, monkeypatch):
    """The direct-commit path is unchanged: no preview, so the file is read."""
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    _write(tmp_path, dict(AF3_JSON, name="first"), "af3.json")
    _write(tmp_path, dict(AF3_JSON, name="second"), "af3.json")

    assert projects.import_json_commit(str(tmp_path / "af3.json")).ok
    assert projects.project.configuration.metadata.name == "second"


def test_a_second_commit_reads_the_file_again(tmp_path, monkeypatch):
    """The pending import is one-shot: a later commit is a fresh read."""
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    path = _write(tmp_path, dict(AF3_JSON, name="previewed"), "af3.json")
    assert projects.import_json_preview(str(path)).ok
    assert projects.import_json_commit(str(path)).ok
    assert projects.project.configuration.metadata.name == "previewed"

    _write(tmp_path, dict(AF3_JSON, name="written-after"), "af3.json")
    assert projects.import_json_commit(str(path)).ok
    assert projects.project.configuration.metadata.name == "written-after"


def test_a_failed_preview_clears_the_pending_import(tmp_path, monkeypatch):
    """A refused preview must not leave an earlier parse waiting to be installed."""
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    good = _write(tmp_path, dict(AF3_JSON, name="previewed"), "good.json")
    assert projects.import_json_preview(str(good)).ok

    broken = _write(tmp_path, "{not json", "broken.json")
    assert not projects.import_json_preview(str(broken)).ok

    _write(tmp_path, dict(AF3_JSON, name="now-on-disk"), "good.json")
    assert projects.import_json_commit(str(good)).ok
    assert projects.project.configuration.metadata.name == "now-on-disk"


def test_a_commit_for_another_path_ignores_the_pending_preview(tmp_path, monkeypatch):
    """A preview of one file must never be installed for another path."""
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    first = _write(tmp_path, dict(AF3_JSON, name="previewed"), "first.json")
    second = _write(tmp_path, dict(AF3_JSON, name="other-file"), "second.json")
    assert projects.import_json_preview(str(first)).ok

    assert projects.import_json_commit(str(second)).ok
    assert projects.project.configuration.metadata.name == "other-file"
