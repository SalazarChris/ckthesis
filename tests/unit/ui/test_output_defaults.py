"""Where the console's save and batch prompts point (audit P0-1).

The console used to offer ``<cwd>/generated_configurations`` and a bare
``<job>.json``; both now come from the shared output service. These tests pin
the offered sentence, the folder a blank answer actually writes into, and that
a configured-but-unusable output root is said out loud instead of ignored.
"""

from __future__ import annotations

import json

from configbuilder.app.paths import ENV_OUTPUT_ROOT, OutputPaths, Preferences
from configbuilder.ui.render import menus as menus_module
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services
from tests.unit.ui.menu_flows import OPEN, PROTEIN

#: The job OPEN names.
JOB_NAME = "Oct4_POU"
JOB_FILE = JOB_NAME + ".json"

#: Job menu 7 → "Load an input file…" → kind 4 (ligand SMILES) → the file,
#: then a blank answer at the output-folder prompt.
GENERATE = ["7", "1", "4"]


def _menu(script, paths):
    console = ScriptedConsole(script)
    app = menus_module.MenuApp(build_services(), console, paths=paths)
    return app.run(), console.transcript


def _isolated(tmp_path):
    """An output tree and preferences file entirely inside ``tmp_path``."""
    return OutputPaths(
        preferences=Preferences(tmp_path / "appdata" / "preferences.json"),
        env={},
        home=tmp_path / "home",
        local_appdata=tmp_path / "local",
    )


# -- save -------------------------------------------------------------------


def test_the_save_prompt_offers_a_path_inside_saved_jobs(tmp_path):
    paths = _isolated(tmp_path)
    expected = str(paths.saved_jobs() / JOB_FILE)

    _status, out = _menu(OPEN + PROTEIN + ["6", "0", "0"], paths=paths)

    assert "blank = %s" % expected in out


def test_accepting_the_save_default_writes_into_saved_jobs(tmp_path):
    paths = _isolated(tmp_path)

    _status, out = _menu(OPEN + PROTEIN + ["6", "", "0", "0"], paths=paths)

    written = paths.saved_jobs() / JOB_FILE
    assert written.is_file()
    # The file keeps the job's own name; the document carries the slug.
    assert json.loads(written.read_text(encoding="utf-8"))["name"] == "oct4-pou"
    assert str(written) in out


def test_the_save_default_is_not_the_working_directory(tmp_path, monkeypatch):
    paths = _isolated(tmp_path)
    working = tmp_path / "cwd"
    working.mkdir()
    monkeypatch.chdir(working)

    _status, _out = _menu(OPEN + PROTEIN + ["6", "", "0", "0"], paths=paths)

    assert list(working.iterdir()) == []
    assert (paths.saved_jobs() / JOB_FILE).is_file()


def test_a_cancelled_save_remembers_nothing(tmp_path):
    paths = _isolated(tmp_path)

    _menu(OPEN + PROTEIN + ["6", "0", "0"], paths=paths)

    assert paths._preferences.get("last_save_directory") is None


# -- generation -------------------------------------------------------------


def _ligand_file(tmp_path):
    ligands = tmp_path / "ligands.smiles"
    ligands.write_text("CCO\n", encoding="utf-8")
    return ligands


def test_the_batch_prompt_offers_the_generated_configurations_folder(tmp_path):
    paths = _isolated(tmp_path)
    ligands = _ligand_file(tmp_path)
    expected = str(paths.generated_configurations())

    _status, out = _menu(
        OPEN + PROTEIN + GENERATE + [str(ligands), "", "0", "0"], paths=paths
    )

    assert "[%s]" % expected in out


def test_accepting_the_batch_default_writes_under_the_output_root(tmp_path):
    paths = _isolated(tmp_path)
    ligands = _ligand_file(tmp_path)

    _status, out = _menu(
        OPEN + PROTEIN + GENERATE + [str(ligands), "", "0", "0"], paths=paths
    )

    written = sorted(p.name for p in paths.generated_configurations().rglob("*.json"))
    assert written, out
    assert any(name.endswith("manifest.json") for name in written)
    # ...and the folder is remembered for the next batch.
    assert paths._preferences.get("last_batch_directory") == str(
        paths.generated_configurations()
    )


def test_the_batch_default_is_not_the_working_directory(tmp_path, monkeypatch):
    paths = _isolated(tmp_path)
    ligands = _ligand_file(tmp_path)
    working = tmp_path / "cwd"
    working.mkdir()
    monkeypatch.chdir(working)

    _menu(OPEN + PROTEIN + GENERATE + [str(ligands), "", "0", "0"], paths=paths)

    assert list(working.iterdir()) == []


# -- the configured root ----------------------------------------------------


def test_an_unusable_configured_root_is_reported_and_a_default_is_used(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not a folder", encoding="utf-8")
    paths = OutputPaths(
        preferences=Preferences(tmp_path / "appdata" / "preferences.json"),
        env={ENV_OUTPUT_ROOT: str(blocker / "out")},
        home=tmp_path / "home",
        local_appdata=tmp_path / "local",
    )

    _status, out = _menu(OPEN + PROTEIN + ["6", "0", "0"], paths=paths)

    assert ENV_OUTPUT_ROOT in out
    assert str(tmp_path / "home" / "Documents" / "AF3Builder") in out


def test_the_output_root_is_named_once_per_session(tmp_path):
    paths = _isolated(tmp_path)
    ligands = _ligand_file(tmp_path)
    note = "Output folder: %s" % paths.root()

    _status, out = _menu(
        OPEN + PROTEIN + GENERATE + [str(ligands), "", "6", "0", "0"], paths=paths
    )

    assert out.count(note) == 1
