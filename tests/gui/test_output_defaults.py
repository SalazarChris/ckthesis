"""Where the window's save and batch dialogs open (audit P0-1 / P1).

Each test asks one question — does the offered folder come from the shared
output service rather than from the process's working directory, and is a
choice remembered only after it produced something? Nothing here opens a modal
or writes into the real user profile: the conftest pins the output root and the
preferences file inside the temporary tree.
"""

from __future__ import annotations

import os

from configbuilder.ui.present.strings import text as _text


def _saved_jobs(output_root):
    return str(output_root / "saved_jobs")


def _generated(output_root):
    return str(output_root / "generated_configurations")


# -- the Generate page -------------------------------------------------------


def test_the_generate_page_opens_with_the_saved_jobs_folder(window, output_root):
    assert window.output_page.destination.text() == _saved_jobs(output_root)


def test_the_generate_default_does_not_depend_on_the_working_directory(
    window, output_root, tmp_path, monkeypatch
):
    original = window.output_page.destination.text()
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert window.output_page.destination.text() == original
    assert not original.startswith(str(elsewhere))


def test_a_successful_generation_is_remembered_as_the_export_folder(filled, window, state, tmp_path):
    window.refresh()
    page = window.output_page
    destination = tmp_path / "exported"
    page.destination.setText(str(destination))

    assert page.preview_plan() is True
    assert page.generate() is True

    # A fresh state reads the same preferences file, so this is the remembered
    # value rather than an in-memory one.
    from configbuilder.ui.render.qt.state import GuiState

    fresh = GuiState(state.services)
    assert str(fresh.paths.save_directory()) == str(destination)


# -- the Entities batch action ----------------------------------------------


def test_the_batch_folder_picker_is_offered_the_generated_configurations_folder(
    reviewed, output_root, tmp_path
):
    window = reviewed
    page = window.entities_page
    input_file = tmp_path / "ligands.smiles"
    input_file.write_text("CCO\n", encoding="utf-8")
    starts = []
    previews = []

    page.batch_kind_chooser = lambda parent: "ligand-smiles"
    page.batch_file_chooser = lambda parent, kind="": str(input_file)
    page.batch_previewer = lambda parent, preview, root, kind="": previews.append(root) or False

    def record_start(parent, start=""):
        starts.append(start)
        return ""

    page.batch_folder_chooser = record_start

    page.generate_from_file()

    assert starts == [_generated(output_root)]
    # Cancelling at the folder question means nothing was previewed or written.
    assert previews == []


def test_a_successful_batch_is_remembered_as_the_batch_folder(reviewed, state, tmp_path):
    window = reviewed
    page = window.entities_page
    input_file = tmp_path / "ligands.smiles"
    input_file.write_text("CCO\n", encoding="utf-8")
    destination = tmp_path / "batch-out"

    page.batch_kind_chooser = lambda parent: "ligand-smiles"
    page.batch_file_chooser = lambda parent, kind="": str(input_file)
    page.batch_folder_chooser = lambda parent, start="": str(destination)
    page.batch_previewer = lambda parent, preview, root, kind="": True
    page.batch_reporter = lambda parent, output: None

    page.generate_from_file()

    from configbuilder.ui.render.qt.state import GuiState

    fresh = GuiState(state.services)
    assert str(fresh.paths.batch_directory()) == str(destination)


def test_the_batch_and_export_folders_stay_distinct(reviewed, output_root):
    window = reviewed
    paths = window.state.paths

    assert str(paths.batch_directory()) == _generated(output_root)
    assert str(paths.save_directory()) == _saved_jobs(output_root)


# -- Save JSON --------------------------------------------------------------


def test_the_save_dialog_opens_in_saved_jobs_with_the_job_name(reviewed, output_root):
    window = reviewed
    seen = []
    window.save_path_chooser = lambda parent, default: seen.append(default) or ("", False)

    assert window.save_json() is False

    expected = os.path.join(_saved_jobs(output_root), window.state.suggested_file_name())
    assert seen == [expected]
    assert os.path.dirname(seen[0]) == _saved_jobs(output_root)


def test_the_save_dialog_offers_the_current_file_once_one_exists(reviewed, tmp_path):
    window = reviewed
    destination = tmp_path / "chosen.json"
    seen = []
    window.save_path_chooser = lambda parent, default: seen.append(default) or (
        str(destination),
        True,
    )

    assert window.save_json() is True
    seen.clear()
    assert window.save_json() is True

    assert seen == [str(destination)]


def test_a_cancelled_save_remembers_nothing(reviewed, tmp_path):
    window = reviewed
    window.save_path_chooser = lambda parent, default: ("", False)

    assert window.save_json() is False

    from configbuilder.ui.render.qt.state import GuiState

    fresh = GuiState(window.state.services)
    assert str(fresh.paths.save_directory()) == str(window.state.paths.saved_jobs())


def test_a_successful_save_moves_the_next_default_to_its_folder(reviewed, tmp_path):
    window = reviewed
    chosen_folder = tmp_path / "my-exports"
    chosen_folder.mkdir()
    destination = chosen_folder / "job.json"
    window.save_path_chooser = lambda parent, default: (str(destination), True)

    assert window.save_json() is True

    from configbuilder.ui.render.qt.state import GuiState

    fresh = GuiState(window.state.services)
    assert str(fresh.paths.save_directory()) == str(chosen_folder)
    assert _text("menu.save_cancelled")
