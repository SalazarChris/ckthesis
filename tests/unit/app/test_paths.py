"""The output-root resolver and its preference store (audit P0-1).

Every case here is about *where a default comes from*, so the tests never
depend on the machine running them: the home directory, ``LOCALAPPDATA`` and
``APPDATA`` are all injected, and nothing reads the real user profile.
"""

from __future__ import annotations

import json
import os

import pytest

from configbuilder.app.paths import (
    ENV_OUTPUT_ROOT,
    GENERATED_DIRECTORY_NAME,
    PREFERENCE_LAST_BATCH_DIRECTORY,
    PREFERENCE_LAST_SAVE_DIRECTORY,
    PREFERENCE_OUTPUT_ROOT,
    SAVED_JOBS_DIRECTORY_NAME,
    OutputPaths,
    Preferences,
    preferences_path,
)


def _paths(tmp_path, env=None, home=None):
    """An ``OutputPaths`` rooted entirely inside ``tmp_path``."""
    home = tmp_path / "home" if home is None else home
    environment = {"APPDATA": str(tmp_path / "appdata"), "LOCALAPPDATA": str(tmp_path / "local")}
    environment.update(env or {})
    return OutputPaths(
        preferences=Preferences(tmp_path / "appdata" / "AF3Builder" / "preferences.json"),
        env=environment,
        home=home,
        local_appdata=tmp_path / "local",
    )


# -- resolution order -------------------------------------------------------


def test_documents_is_the_default_root(tmp_path):
    paths = _paths(tmp_path)

    resolved = paths.resolve_root()

    assert resolved.path == tmp_path / "home" / "Documents" / "AF3Builder"
    assert resolved.source == "documents"
    assert resolved.diagnostics == ()
    assert resolved.path.is_dir()


def test_environment_variable_wins_and_is_created(tmp_path):
    target = tmp_path / "elsewhere" / "with space"
    paths = _paths(tmp_path, env={ENV_OUTPUT_ROOT: str(target)})

    resolved = paths.resolve_root()

    assert resolved.path == target
    assert resolved.source == ENV_OUTPUT_ROOT
    assert resolved.diagnostics == ()
    assert target.is_dir()


def test_invalid_environment_variable_is_reported_not_ignored(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where a folder should be", encoding="utf-8")
    paths = _paths(tmp_path, env={ENV_OUTPUT_ROOT: str(blocker)})

    resolved = paths.resolve_root()

    assert resolved.path == tmp_path / "home" / "Documents" / "AF3Builder"
    assert resolved.source == "documents"
    assert len(resolved.diagnostics) == 1
    assert ENV_OUTPUT_ROOT in resolved.diagnostics[0]


def test_remembered_root_is_used_when_it_still_exists(tmp_path):
    remembered = tmp_path / "chosen"
    remembered.mkdir()
    preferences = Preferences(tmp_path / "appdata" / "AF3Builder" / "preferences.json")
    assert preferences.update(**{PREFERENCE_OUTPUT_ROOT: str(remembered)})
    paths = OutputPaths(
        preferences=preferences,
        env={"APPDATA": str(tmp_path / "appdata")},
        home=tmp_path / "home",
        local_appdata=tmp_path / "local",
    )

    resolved = paths.resolve_root()

    assert resolved.path == remembered
    assert resolved.source == "preferences"


def test_unusable_remembered_root_falls_through(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a folder", encoding="utf-8")
    preferences = Preferences(tmp_path / "appdata" / "AF3Builder" / "preferences.json")
    assert preferences.update(**{PREFERENCE_OUTPUT_ROOT: str(blocker / "gone")})
    paths = OutputPaths(
        preferences=preferences,
        env={"APPDATA": str(tmp_path / "appdata")},
        home=tmp_path / "home",
        local_appdata=tmp_path / "local",
    )

    resolved = paths.resolve_root()

    assert resolved.path == tmp_path / "home" / "Documents" / "AF3Builder"


def test_local_appdata_is_the_last_resort_when_documents_cannot_be_used(tmp_path):
    # A *file* named Documents makes the preferred location impossible.
    home = tmp_path / "home"
    home.mkdir()
    (home / "Documents").write_text("not a directory", encoding="utf-8")
    paths = _paths(tmp_path, home=home)

    resolved = paths.resolve_root()

    assert resolved.path == tmp_path / "local" / "AF3Builder"
    assert resolved.source == "localappdata"
    assert any("Documents" in note for note in resolved.diagnostics)


def test_resolution_does_not_depend_on_the_working_directory(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    first = paths.resolve_root().path

    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    second = paths.resolve_root().path

    monkeypatch.chdir(tmp_path)
    third = paths.resolve_root().path

    assert first == second == third
    assert not str(first).startswith(str(elsewhere))


def test_paths_with_spaces_and_non_ascii_survive_resolution(tmp_path):
    home = tmp_path / "Chris Smith" / "hôme"
    paths = _paths(tmp_path, home=home)

    resolved = paths.resolve_root()

    assert resolved.path == home / "Documents" / "AF3Builder"
    assert resolved.path.is_dir()


# -- the two operation folders ---------------------------------------------


def test_saved_jobs_and_generated_configurations_are_separate(tmp_path):
    paths = _paths(tmp_path)

    assert paths.saved_jobs() != paths.generated_configurations()
    assert paths.saved_jobs().name == SAVED_JOBS_DIRECTORY_NAME
    assert paths.generated_configurations().name == GENERATED_DIRECTORY_NAME
    assert paths.saved_jobs().parent == paths.generated_configurations().parent


def test_default_save_path_is_a_file_inside_saved_jobs(tmp_path):
    paths = _paths(tmp_path)

    destination = paths.default_save_path("my-job.json")

    assert destination.endswith(".json")
    assert os.path.dirname(destination) == str(paths.saved_jobs())
    assert not os.path.isabs("my-job.json")


def test_default_batch_root_is_generated_configurations(tmp_path):
    paths = _paths(tmp_path)

    assert paths.default_batch_root() == str(paths.generated_configurations())


# -- remembering ------------------------------------------------------------


def test_remembering_a_save_folder_overrides_the_default(tmp_path):
    paths = _paths(tmp_path)
    chosen = tmp_path / "jobs"
    chosen.mkdir()

    assert paths.remember_save_directory(chosen)
    assert paths.save_directory() == chosen


def test_remembering_a_batch_folder_overrides_the_default(tmp_path):
    paths = _paths(tmp_path)
    chosen = tmp_path / "batches"
    chosen.mkdir()

    assert paths.remember_batch_directory(chosen)
    assert paths.batch_directory() == chosen


def test_the_two_remembered_folders_are_independent(tmp_path):
    paths = _paths(tmp_path)
    jobs = tmp_path / "jobs"
    batches = tmp_path / "batches"
    jobs.mkdir()
    batches.mkdir()

    paths.remember_save_directory(jobs)
    paths.remember_batch_directory(batches)

    assert paths.save_directory() == jobs
    assert paths.batch_directory() == batches


def test_a_deleted_remembered_folder_falls_back_to_the_default(tmp_path):
    paths = _paths(tmp_path)
    chosen = tmp_path / "jobs"
    chosen.mkdir()
    paths.remember_save_directory(chosen)

    chosen.rmdir()

    assert paths.save_directory() == paths.saved_jobs()


def test_remembering_nothing_changes_nothing(tmp_path):
    paths = _paths(tmp_path)

    assert paths.remember_save_directory("") is False
    assert paths.save_directory() == paths.saved_jobs()


def test_remembering_keeps_the_other_stored_values(tmp_path):
    paths = _paths(tmp_path)
    chosen = tmp_path / "jobs"
    chosen.mkdir()
    assert paths.remember_save_directory(chosen)

    preferences = Preferences(tmp_path / "appdata" / "AF3Builder" / "preferences.json")
    assert preferences.update(**{PREFERENCE_OUTPUT_ROOT: str(tmp_path / "root")})

    assert paths.remember_batch_directory(chosen)
    stored = preferences.read()
    assert stored[PREFERENCE_LAST_SAVE_DIRECTORY] == str(chosen)
    assert stored[PREFERENCE_LAST_BATCH_DIRECTORY] == str(chosen)
    assert stored[PREFERENCE_OUTPUT_ROOT] == str(tmp_path / "root")


# -- preferences robustness -------------------------------------------------


def test_missing_preferences_file_reads_as_empty(tmp_path):
    preferences = Preferences(tmp_path / "nowhere" / "preferences.json")

    assert preferences.read() == {}
    assert preferences.get(PREFERENCE_OUTPUT_ROOT) is None


def test_malformed_preferences_file_reads_as_empty(tmp_path):
    target = tmp_path / "preferences.json"
    target.write_text("{not json at all", encoding="utf-8")

    assert Preferences(target).read() == {}


def test_preferences_file_with_a_non_object_reads_as_empty(tmp_path):
    target = tmp_path / "preferences.json"
    target.write_text(json.dumps(["a", "list"]), encoding="utf-8")

    assert Preferences(target).read() == {}


def test_non_string_preference_values_are_ignored(tmp_path):
    target = tmp_path / "preferences.json"
    target.write_text(json.dumps({PREFERENCE_LAST_SAVE_DIRECTORY: 7}), encoding="utf-8")

    assert Preferences(target).get(PREFERENCE_LAST_SAVE_DIRECTORY) is None


def test_preferences_path_is_outside_the_application_folder(tmp_path):
    path = preferences_path(env={"APPDATA": str(tmp_path / "roaming")}, home=tmp_path / "home")

    assert path == tmp_path / "roaming" / "AF3Builder" / "preferences.json"


def test_preferences_fall_back_to_dot_config_without_appdata(tmp_path):
    path = preferences_path(env={}, home=tmp_path / "home")

    assert path == tmp_path / "home" / ".config" / "AF3Builder" / "preferences.json"


def test_an_unwritable_preferences_location_does_not_raise(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not a folder", encoding="utf-8")
    preferences = Preferences(blocker / "preferences.json")

    assert preferences.update(**{PREFERENCE_LAST_SAVE_DIRECTORY: str(tmp_path)}) is False
    assert preferences.read() == {}


def test_preferences_write_is_atomic_and_leaves_no_temporary_files(tmp_path):
    target = tmp_path / "preferences.json"
    preferences = Preferences(target)

    assert preferences.update(**{PREFERENCE_LAST_SAVE_DIRECTORY: str(tmp_path)})

    assert [entry.name for entry in tmp_path.iterdir()] == ["preferences.json"]
    assert json.loads(target.read_text(encoding="utf-8")) == {
        PREFERENCE_LAST_SAVE_DIRECTORY: str(tmp_path)
    }


def test_resolving_twice_is_stable(tmp_path):
    paths = _paths(tmp_path)

    assert paths.resolve_root().path == paths.resolve_root().path


@pytest.mark.parametrize("variable", [ENV_OUTPUT_ROOT])
def test_blank_environment_variable_is_ignored(tmp_path, variable):
    paths = _paths(tmp_path, env={variable: "   "})

    resolved = paths.resolve_root()

    assert resolved.source == "documents"
    assert resolved.diagnostics == ()
