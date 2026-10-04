"""Work preservation: the job in hand survives navigation, refusals, and crashes.

The menu makes three promises about the current job — it is kept as you
edit, it comes back through ``Open saved work``, and nothing (bad input, a
blocked validation, a refused generation, closing the application) throws
it away. These tests pin the service behaviour those promises rest on.
"""

from __future__ import annotations

import json
import os

from configbuilder.app.cli import MenuApp
from configbuilder.app.configuration_service import ConfigurationService
import configbuilder.app.project_service as project_service
from configbuilder.app.project_service import (
    INTERNAL_PROJECTS_DIR,
    PROJECT_EXTENSION,
    ProjectService,
)
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services

PROTEIN_SEQUENCE = "ACDEFGHIKLMNPQRSTVWY"

AF3_JSON = {
    "name": "imported-job",
    "modelSeeds": [7],
    "sequences": [{"protein": {"id": "A", "sequence": PROTEIN_SEQUENCE}}],
    "dialect": "alphafold3",
    "version": 3,
}


def _store(tmp_path):
    return tmp_path / INTERNAL_PROJECTS_DIR


def _copy_names(tmp_path):
    return sorted(path.name for path in _store(tmp_path).glob("*" + PROJECT_EXTENSION))


def _write(tmp_path, document, name="input.json"):
    path = tmp_path / name
    path.write_text(
        document if isinstance(document, str) else json.dumps(document),
        encoding="utf-8",
    )
    return path


# -- the working copy ----------------------------------------------------------


def test_every_committed_change_lands_in_the_working_copy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    projects.new("Oct4_POU")
    assert configuration.add_record("protein", PROTEIN_SEQUENCE).ok

    assert len(_copy_names(tmp_path)) == 1

    # A fresh process finds the job exactly as it was left.
    reopened = ProjectService()
    outcome = reopened.load_saved_work()
    assert outcome.ok, outcome.message
    assert reopened.project.configuration.metadata.name == "Oct4_POU"
    records = reopened.project.configuration.records
    assert [record.ids.primary.value for record in records] == ["A"]


def test_open_saved_work_reports_the_copy_you_are_already_editing(tmp_path, monkeypatch):
    """The old no-op: re-opening the copy you are already editing looked like
    nothing happened. It now refuses with the reason instead."""
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    projects.new("Only job")  # committed as it starts, so it *is* the newest copy

    outcome = projects.load_saved_work()
    assert not outcome.ok
    assert "already the most recent working copy" in outcome.message

    # A fresh process really does restore it — and then it is current again.
    fresh = ProjectService()
    assert fresh.load_saved_work().ok
    assert not fresh.load_saved_work().ok


def test_open_saved_work_without_any_saved_work_starts_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outcome = ProjectService().load_saved_work()
    assert not outcome.ok
    assert "no saved work" in outcome.message


def test_the_working_copy_store_is_bounded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(project_service, "WORKING_COPIES_KEPT", 3)
    store = _store(tmp_path)
    store.mkdir(parents=True, exist_ok=True)
    for index in range(5):
        path = store / ("%d%s" % (index, PROJECT_EXTENSION))
        path.write_text("{}", encoding="utf-8")
        stamp = 1_700_000_000 + index
        os.utime(path, (stamp, stamp))

    ProjectService().new("Bounded")

    # The three newest of the old copies are kept and the two oldest are gone;
    # nothing outside this application's own store is ever a candidate.
    kept = _copy_names(tmp_path)
    assert "0%s" % PROJECT_EXTENSION not in kept
    assert "1%s" % PROJECT_EXTENSION not in kept
    assert {"2%s" % PROJECT_EXTENSION, "3%s" % PROJECT_EXTENSION,
            "4%s" % PROJECT_EXTENSION} <= set(kept)
    assert len(kept) == 4  # the three kept copies plus the job just started


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
    """Playtest finding, both halves of the import path.

    Pointing the picker at a folder is an ordinary mistake — the file
    listing shows directories too. Windows reports reading one as
    ``Permission denied``, which sent the user looking for a permissions
    problem they did not have; the refusal now names the real mistake and
    the open job is untouched.
    """
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


def test_an_imported_job_is_persisted_immediately(tmp_path, monkeypatch):
    """An import used to wait for the next edit before reaching the working
    copy — so a crash right after importing lost it."""
    monkeypatch.chdir(tmp_path)
    projects = ProjectService()
    path = _write(tmp_path, AF3_JSON, "af3.json")
    assert projects.import_json_commit(str(path)).ok

    fresh = ProjectService()
    outcome = fresh.load_saved_work()
    assert outcome.ok, outcome.message
    configuration = fresh.project.configuration
    assert configuration.metadata.name == "imported-job"
    assert list(configuration.seeds.values) == [7]



def test_the_confirmed_import_installs_what_was_previewed(tmp_path, monkeypatch):
    """The confirm installs the document the preview screen described.

    Regression: preview and commit were two independent reads of the file,
    so a file edited between the screen and the user's answer installed
    content that had never been shown. The parse result now travels from
    the preview as the pending import.
    """
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
    assert preview.summary["job_name"] == configuration.metadata.name
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

# -- navigation ------------------------------------------------------------------


def test_wandering_the_menus_and_exiting_keeps_the_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    console = ScriptedConsole(
        ["1", "Wander"]                                     # new job, named
        + ["1", "1", "1", "1", PROTEIN_SEQUENCE, "", ""]    # edit → entities → add → protein
        + ["0", "0"]                                        # back to the master menu
        + ["2", "1", "0"]                                   # review → validate → back
        + ["3", "0"]                                        # variants (none yet) → back
        + ["4", "0"]                                        # generate screen, leave without writing
        + ["0"]                                             # exit
    )
    app = MenuApp(build_services(), console)
    assert app.run() == 0
    assert not (tmp_path / "output").exists()  # nothing was generated

    console2 = ScriptedConsole(["2", "0"])  # start screen: Open saved work → exit
    app2 = MenuApp(build_services(), console2)
    assert app2.run() == 0
    project = app2._services.projects.project
    assert project is not None
    assert project.configuration.metadata.name == "Wander"
    assert len(project.configuration.records) == 1
