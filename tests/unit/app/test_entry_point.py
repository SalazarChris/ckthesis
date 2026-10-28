"""Entry-point tests (plan §5: one console entry point).

``app.cli`` is a composition root, not an application-domain module: these
tests pin that it composes the standard wiring into the menu
(``ui.render.menus.MenuApp``) rather than owning any workflow logic, that
the packaging declaration and the implementation agree, and that both
invocation paths (console script, ``python -m configbuilder``) start
cleanly. The menu's own behaviour is exercised through the scripted
console — the §18.8 harness, no terminal needed.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import configbuilder.app.cli as cli
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MENU_TITLE = "JSON CONFIGURATION BUILDER"
PROTEIN = "ACDEFGHIKLMNPQRSTVWY"


def test_main_exists_and_is_callable():
    assert callable(cli.main)
    assert cli.__all__ == ["main"]


def test_pyproject_declares_this_module():
    """The declared entry point and the implemented one are the same module."""
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'configbuilder = "configbuilder.app.cli:main"' in text


def test_main_composes_services_into_the_builder(monkeypatch):
    """``main`` is delegation only: the standard wiring goes in, the
    builder runs over it, and its status is returned."""
    services = object()
    seen = {}

    class FakeBuilder:
        def __init__(self, services_arg, console_arg):
            seen["services"] = services_arg
            seen["console"] = console_arg

        def run(self):
            return 4

    monkeypatch.setattr(cli, "build_services", lambda: services)
    monkeypatch.setattr(cli, "MenuApp", FakeBuilder)
    assert cli.main() == 4
    assert seen["services"] is services
    assert seen["console"] is not None


def test_cli_is_a_thin_boundary():
    """Statically: cli.py imports exactly the console, the builder, and
    the service wiring — no pipeline stage, no step or rendering internals
    of its own."""
    tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    project = sorted(t for t in imported if t.startswith("configbuilder"))
    assert project == [
        "configbuilder.ui.render.console",
        "configbuilder.ui.render.menus",
        "configbuilder.ui.services",
    ], project


# The subprocess must exercise the checked-out tree, not whatever copy of
# the package happens to be installed in the environment: an installed
# distribution shadows the working tree once the child process runs from
# another cwd, so the repository root goes on PYTHONPATH explicitly.
_REPO_ENV = {"PYTHONPATH": str(PROJECT_ROOT)}


def _run_process(argv, cwd, stdin_text="", env=None):
    environment = dict(os.environ, **(env or {}))
    environment["PYTHONPATH"] = os.pathsep.join(
        [value for value in (str(PROJECT_ROOT), environment.get("PYTHONPATH")) if value]
    )
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=environment,
        input=stdin_text,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def test_module_invocation_shows_the_main_menu_and_exits_cleanly():
    """``python -m configbuilder`` reaches the application; piped stdin
    (immediate EOF) ends it cleanly with status 0 — never a traceback,
    never a hang."""
    result = _run_process([sys.executable, "-m", "configbuilder"], PROJECT_ROOT)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert MENU_TITLE in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


@pytest.mark.skipif(
    shutil.which("configbuilder") is None,
    reason="console script not installed (pip install -e .)",
)
def test_console_script_resolves_to_the_entry_point():
    result = _run_process(["configbuilder"], cwd=Path.cwd())
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert MENU_TITLE in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


# -- the same surface with a real pipe, and a save path that cannot be used -------


def test_unusable_save_path_is_reported_and_the_session_survives(tmp_path):
    """Playtest finding, pinned at the real surface.

    A save path whose parent is an existing *file* used to reach the
    executor's ``OSError``: a traceback and a dead session, after nothing
    but a typed path. The refusal is now reported in the menu's own voice,
    the session carries on, and the file the user named is untouched.
    """
    (tmp_path / "out").write_text("not a directory", encoding="utf-8")
    script = "\n".join([
        "1", "job",                      # main -> New job, name it
        "2", "1", PROTEIN, "1", "",       # Add entity -> Protein -> sequence
        "6", "out/child.json",           # Save and show summary -> the bad path
        "0", "0",                        # leave the job (unsaved -> discard) -> exit
    ]) + "\n"
    result = _run_process(
        [sys.executable, "-m", "configbuilder"], tmp_path, script
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
    assert "could not create the directory" in result.stdout
    assert (tmp_path / "out").read_text(encoding="utf-8") == "not a directory"


# -- the menu itself (scripted console over the real services) ---------------------


def _app(script):
    console = ScriptedConsole(script)
    return cli.MenuApp(build_services(), console), console


def test_main_menu_lists_new_open_and_exit():
    app, console = _app([])  # EOF immediately after the main menu
    assert app.run() == 0
    out = console.transcript
    assert MENU_TITLE in out
    assert "1. New job" in out
    assert "2. Open a JSON file" in out
    assert "0. Exit" in out


def test_new_job_opens_the_job_menu():
    app, console = _app(["1", "Oct4_POU", "0", "0"])
    assert app.run() == 0
    out = console.transcript
    assert "Name          : Oct4_POU" in out
    assert "1. Edit job configurations" in out
    assert "7. Generate configurations from a file (sequences or ligands)" in out


def _opened(script):
    """A run that starts at the job menu (a new job, name given)."""
    return _app(["1", "experiment"] + script)


@pytest.mark.parametrize("word", ["0", "q", "quit", "exit"])
def test_exit_words_end_the_menu(word):
    app, _console = _opened([word, word])
    assert app.run() == 0


def test_blank_choice_redisplays_the_job_menu():
    app, console = _opened(["", "0", "0"])
    assert app.run() == 0
    # The job menu was displayed twice: once per loop pass.
    assert console.transcript.count("Name          : experiment") == 2


def test_unknown_choice_reports_and_keeps_asking():
    app, console = _opened(["12", "nope", "0", "0"])
    assert app.run() == 0
    out = console.transcript
    assert "Not a valid choice: '12'" in out
    assert "Not a valid choice: 'nope'" in out


def test_eof_ends_the_menu_cleanly():
    app, console = _opened([])
    assert app.run() == 0
    assert "Interrupted" in console.transcript


def test_ctrl_c_ends_the_menu_cleanly():
    class InterruptingConsole:
        def __init__(self):
            self.lines = []

        def write_line(self, text=""):
            self.lines.append(text)

        def prompt(self, prompt_text):
            raise KeyboardInterrupt

        def read_multiline(self, instructions, terminator=""):
            raise KeyboardInterrupt

    app = cli.MenuApp(build_services(), InterruptingConsole())
    assert app.run() == 0
    assert "Interrupted" in "\n".join(app._console.lines)


def test_edit_job_configuration_submenu_navigation():
    """1 → Edit job configurations → 0 back → job menu again → 0 → main → 0."""
    app, console = _opened(["1", "0", "0", "0"])
    assert app.run() == 0
    out = console.transcript
    assert "EDIT JOB CONFIGURATIONS" in out
    assert "1. Job name" in out
    assert "2. Model seeds" in out
    assert "3. JSON version" in out
    assert "0. Back" in out
    # Back at the job menu afterwards, then the main menu.
    assert out.count("Name          : experiment") == 2
    assert out.count("1. New job") >= 2


# -- the real console's codec, end to end (playtest 2026-10-04) --------------


def test_a_legacy_output_code_page_does_not_end_the_session(tmp_path):
    """A ligand run on a cp1252 output stream (what a Windows redirect to a
    file or a pipe uses) must not raise ``UnicodeEncodeError`` out of
    ``Console.write_line`` and end the session with a traceback.

    The file names a molecule with a character cp1252 lacks, so the preview
    prints glyphs the stream cannot encode — the exact shape that used to kill
    a session, now on the workflow that replaced the old variant save.
    """
    ligands = tmp_path / "ligands.smiles"
    ligands.write_text("omega-\u03a9 CCO\n", encoding="utf-8")
    output = tmp_path / "out"
    script = "\n".join([
        "1", "job",                      # new job
        "2", "1", "ACDE", "", "",        # add protein
        "7", "1", "4", str(ligands), str(output),  # file → SMILES kind → folder
        "0", "0", "2", "0",             # back, leave (discard), exit
    ]) + "\n"

    result = _run_process(
        [sys.executable, "-m", "configbuilder"],
        tmp_path,
        script,
        env={"PYTHONIOENCODING": "cp1252"},
    )

    assert result.returncode == 0, (result.returncode, result.stderr[-600:])
    assert "Traceback" not in result.stderr, result.stderr[-600:]
    assert "UnicodeEncodeError" not in result.stderr
    assert "Wrote" in result.stdout
    assert list(output.rglob("*.json")), "the run must have written its files"


def test_a_garbled_input_byte_does_not_end_the_session(tmp_path):
    """A byte the input codec cannot decode must not raise
    ``UnicodeDecodeError`` out of ``Console.prompt``."""
    environment = dict(os.environ, PYTHONIOENCODING="utf-8")
    environment["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "configbuilder"],
        cwd=str(tmp_path),
        env=environment,
        input=b"\xff\xfe\x81 not text\n0\n",
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, (result.returncode, result.stderr[-600:])
    assert b"Traceback" not in result.stderr, result.stderr[-600:]
    assert b"UnicodeDecodeError" not in result.stderr
