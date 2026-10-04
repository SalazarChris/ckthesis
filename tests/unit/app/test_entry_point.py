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
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import configbuilder.app.cli as cli
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MENU_TITLE = "ConfigBuilder"
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
    builder runs over it, and its status is returned. Nothing here
    builds a project, validates, or serializes."""
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


def _run_process(argv, cwd, stdin_text=""):
    return subprocess.run(
        argv,
        cwd=str(cwd),
        input=stdin_text,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def test_module_invocation_shows_the_start_screen_and_exits_cleanly():
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
    """The declared command reaches the implemented application. Resolution
    failure would exit 1 with a ModuleNotFoundError traceback."""
    result = _run_process(["configbuilder"], cwd=Path.cwd())
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert MENU_TITLE in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


# -- the same surface with a real pipe, and an output path that cannot be used ------


def test_unusable_output_directory_is_reported_and_the_session_survives(tmp_path):
    """Playtest finding, pinned at the real surface.

    Driven through ``python -m configbuilder`` with piped stdin, a user who
    names their output directory after an existing *file* used to get
    ``OSError`` out of the executor: a traceback and a dead session, after
    nothing but a typed name. The refusal is now reported in the menu's own
    voice, the session carries on, and the file they named is untouched.
    """
    (tmp_path / "out").write_text("not a directory", encoding="utf-8")
    script = "\n".join([
        "1", "job",                     # start -> New job, name it
        "1", "1", "1", "1", PROTEIN,    # Edit -> Entities -> Add -> Protein -> sequence
        "", "",                         # accept the default id and (no) description
        "0", "0",                       # back to the master menu
        "4", "4", "out",                # Generate -> change the output directory
        "1", "1",                       # write this job's JSON -> confirm
        "0", "0",                       # back out
    ]) + "\n"
    result = _run_process(
        [sys.executable, "-m", "configbuilder"], tmp_path, script
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
    assert "could not create the directory" in result.stdout
    assert (tmp_path / "out").read_text(encoding="utf-8") == "not a directory"
    assert list(tmp_path.glob("out/*")) == [], "nothing may be written"


# -- the menu itself (scripted console over the real services) ---------------------


def _app(script):
    console = ScriptedConsole(script)
    return cli.MenuApp(build_services(), console), console


def test_start_screen_lists_new_load_and_exit():
    app, console = _app([])  # EOF immediately after the start screen
    assert app.run() == 0
    out = console.transcript
    assert MENU_TITLE in out
    assert "1) New job" in out
    assert "2) Open saved work" in out
    assert "0)  Exit" in out


def test_option_1_opens_the_master_menu_over_a_new_job():
    app, console = _app(["1", "Oct4_POU", "0"])
    assert app.run() == 0
    out = console.transcript
    assert "Current job: Oct4_POU" in out
    assert "1) Edit the job" in out  # the master menu


def _opened(script):
    """A run that starts at the master menu (a new job, name given)."""
    return _app(["1", "experiment"] + script)


@pytest.mark.parametrize("word", ["0", "q", "quit", "exit"])
def test_exit_words_end_the_menu(word):
    app, _console = _opened([word])
    assert app.run() == 0


def test_blank_choice_redisplays_the_menu():
    app, console = _opened(["", "0"])
    assert app.run() == 0
    # The master menu was displayed twice: once per loop pass.
    assert console.transcript.count("Current job: experiment") == 2


def test_unknown_choice_reports_and_keeps_asking():
    app, console = _opened(["12", "nope", "0"])
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


def test_edit_the_job_submenu_navigation():
    """1 → Edit the job → 0 back → master menu → 0 exit; the master menu
    redisplays after the submenu returns."""
    app, console = _opened(["1", "0", "0"])
    assert app.run() == 0
    out = console.transcript
    assert "Edit the job" in out
    assert "Entities" in out
    assert "Job settings" in out
    assert "Bonds, modifications & custom components" in out
    assert "0)  Back" in out
    # Back at the master menu afterwards.
    assert out.count("Current job: experiment") == 2

# -- the real console's codec, end to end (playtest 2026-10-04) --------------


def test_a_legacy_output_code_page_does_not_end_the_session(tmp_path):
    """The crashing flow, reproduced as a process.

    Creating a variant that renames the job prints the change row
    ``job name -> X``. On a cp1252 output stream (what a Windows redirect to a
    file or a pipe uses) that row used to raise ``UnicodeEncodeError`` out of
    ``Console.write_line`` and end the session with a traceback -- after the
    variant had already been created, so the user's work appeared to vanish
    behind a Python error.

    ``PYTHONIOENCODING`` is set explicitly so this reproduces on every
    platform, not only where the ANSI code page is the default.
    """
    import os

    script = "\n".join([
        "1", "job",                  # new job
        "1", "1", "1", "1",          # edit -> entities -> add -> protein
        "ACDE", "n", "n",            # sequence, no MSA, no templates
        "0", "0",                    # back to the master menu
        "3",                         # variants
        "1", "1", "v1",              # create a variant named v1
        "6", "renamed",              # change kind 6 is the job name
        "0", "0", "0",               # back out and exit
    ]) + "\n"

    environment = dict(os.environ, PYTHONIOENCODING="cp1252")
    result = subprocess.run(
        [sys.executable, "-m", "configbuilder"],
        cwd=str(tmp_path),
        env=environment,
        input=script,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert result.returncode == 0, (result.returncode, result.stderr[-600:])
    assert "Traceback" not in result.stderr, result.stderr[-600:]
    assert "UnicodeEncodeError" not in result.stderr
    assert "Created variant" in result.stdout
    assert "job name" in result.stdout, result.stdout[-600:]


def test_a_garbled_input_byte_does_not_end_the_session(tmp_path):
    """The other half of the same boundary: a byte the input codec cannot
    decode used to raise ``UnicodeDecodeError`` out of ``Console.prompt``."""
    import os

    environment = dict(os.environ, PYTHONIOENCODING="utf-8")
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
