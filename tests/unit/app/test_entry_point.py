"""Entry-point tests (plan §5: one console entry point).

``app.cli`` is a composition root, not an application-domain module: these
tests pin that it composes the standard wiring into the free-navigation
builder (``ui.render.menus.MenuApp``) rather than owning any workflow
logic, that the packaging declaration and the implementation agree, and
that both invocation paths (console script, ``python -m configbuilder``)
start cleanly. The menu's own behaviour is exercised through the scripted
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


# -- the menu itself (scripted console over the real services) ---------------------


def _app(script):
    console = ScriptedConsole(script)
    return cli.MenuApp(build_services(), console), console


def test_start_screen_lists_new_load_and_exit():
    app, console = _app([])  # EOF immediately after the start screen
    assert app.run() == 0
    out = console.transcript
    assert MENU_TITLE in out
    assert "1) New experiment" in out
    assert "2) Load a saved project" in out
    assert "0)  Exit" in out


def test_option_1_opens_the_master_menu_over_a_new_experiment():
    app, console = _app(["1", "Oct4_POU", "0"])
    assert app.run() == 0
    out = console.transcript
    assert "Current job: Oct4_POU" in out
    assert "Job Builder" in out  # the master menu's first action


def _opened(script):
    """A run that starts at the master menu (a new experiment, name given)."""
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


def test_guided_wizard_stays_reachable_from_the_menu(monkeypatch):
    """Option 7 runs the existing wizard over the *same* services and
    console — no second workflow, no re-wiring."""
    seen = {}

    def fake_run_wizard(services, console=None, overrides=None, journal=None):
        seen["services"] = services
        seen["console"] = console
        return 0

    import configbuilder.ui.render.wizard as wizard_module

    monkeypatch.setattr(wizard_module, "run_wizard", fake_run_wizard)
    app, console = _opened(["8", "0"])
    assert app.run() == 0
    assert seen["services"] is app._services
    assert seen["console"] is console


def test_job_builder_submenu_navigation():
    """1 → builder menu → 0 back → master menu → 0 exit; the master menu
    redisplays after the submenu returns."""
    app, console = _opened(["1", "0", "0"])
    assert app.run() == 0
    out = console.transcript
    assert "Job Settings" in out
    assert "Proteins" in out
    assert "0)  Back" in out
    # Back at the master menu afterwards.
    assert out.count("Current job: experiment") == 2
