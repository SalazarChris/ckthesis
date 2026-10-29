"""The two root-level launchers: ``af3builder.py`` and ``gui.py``.

The launchers are packaging convenience, not application logic, so these
tests pin exactly two things and no more:

- ``af3builder.py`` is a one-call delegation to the existing console entry
  point (``configbuilder.app.cli.main``), with no side effect on import.
- ``gui.py`` builds the *right* child command -- ``.venv-gui``'s own
  interpreter running ``configbuilder.ui.render.qt`` from the repository
  root -- and forwards the user's arguments verbatim.

None of this needs PySide6, a display, or a real GUI: the child process is
injected, so the tests observe the argv, the working directory and the exit
status without anything ever opening a window. The one real subprocess test
that *does* touch the GUI environment runs ``gui.py --help``, which exits at
argument parsing and therefore opens no window either; it is skipped when
``.venv-gui`` has not been created.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # the launchers live in the repository root
    sys.path.insert(0, str(ROOT))

import af3builder  # noqa: E402  (after the sys.path adjustment above)
import gui  # noqa: E402

MENU_TITLE = "JSON CONFIGURATION BUILDER"
SPACED_PATH = r"C:\path\to\job with spaces.json"


# -- shared helpers ------------------------------------------------------------


def _imported_roots(path: Path):
    """The root module name of every ``import`` / ``from ... import`` in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _run_process(argv, cwd, stdin_text=""):
    """Run a real child process against the checked-out tree.

    ``PYTHONPATH`` is set explicitly (as the entry-point tests do) so the
    child imports this working tree rather than any installed copy.
    """
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=environment,
        input=stdin_text,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


class _Completed:
    """The least a subprocess result needs to be for ``gui.main``."""

    def __init__(self, returncode):
        self.returncode = returncode


@pytest.fixture
def fake_root(tmp_path):
    """A hermetic stand-in for the checkout, with a stub ``.venv-gui``.

    The launcher discovers its root from ``Path(__file__)``; the tests point
    that discovery at a temporary directory holding an empty file where the
    GUI interpreter would be, so they neither depend on ``.venv-gui`` having
    been created on this machine nor ever execute anything.
    """
    interpreter = tmp_path / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_text("", encoding="utf-8")
    return tmp_path


# -- af3builder.py -------------------------------------------------------------


def test_importing_the_cli_launcher_does_not_start_the_builder():
    """``import af3builder`` must not run the interactive menu."""
    result = _run_process(
        [sys.executable, "-c", "import af3builder"], ROOT
    )
    assert result.returncode == 0, result.stderr
    assert MENU_TITLE not in result.stdout
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("status", [0, 4])
def test_cli_launcher_delegates_once_and_propagates_the_exit_result(
    monkeypatch, status
):
    """One call to ``configbuilder.app.cli.main``; its int passes straight through."""
    calls = []

    def fake_main():
        calls.append("main")
        return status

    monkeypatch.setattr(af3builder.cli, "main", fake_main)
    assert af3builder.main() == status
    assert calls == ["main"]


def test_cli_launcher_is_a_thin_delegation():
    """Statically: stdlib/``__future__`` plus the one entry-point module."""
    assert _imported_roots(ROOT / "af3builder.py") == {
        "__future__",
        "configbuilder",
    }


def test_cli_launcher_starts_the_menu_and_exits_cleanly():
    """The real ``python af3builder.py`` reaches the menu and ends on EOF."""
    result = _run_process([sys.executable, str(ROOT / "af3builder.py")], ROOT)
    assert result.returncode == 0, (result.returncode, result.stderr[-600:])
    assert MENU_TITLE in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


# -- gui.py: the command it builds ---------------------------------------------


def test_gui_launcher_falls_back_to_a_legacy_gui_environment(tmp_path):
    """Existing GUI-only environments remain usable after setup standardizes .venv."""
    legacy = tmp_path / ".venv-gui" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    legacy.parent.mkdir(parents=True)
    legacy.write_text("", encoding="utf-8")
    assert gui.gui_python(tmp_path) == legacy


def test_gui_command_runs_the_existing_module_in_the_isolated_environment():
    root = gui.repository_root()
    interpreter = gui.gui_python(root)
    scripts = "Scripts" if os.name == "nt" else "bin"
    name = "python.exe" if os.name == "nt" else "python"
    preferred = root / ".venv" / scripts / name
    # setup_windows.bat standardises .venv; a checkout that has not run it yet
    # must keep using the legacy GUI-only environment instead of failing.
    expected = preferred if preferred.is_file() else root / ".venv-gui" / scripts / name
    assert interpreter == expected
    assert gui.build_command(["job.json"], interpreter) == [
        str(interpreter),
        "-m",
        "configbuilder.ui.render.qt",
        "job.json",
    ]


def test_gui_arguments_are_forwarded_unchanged_as_separate_elements():
    """A path with spaces stays one argument, and options are not reordered."""
    command = gui.build_command([SPACED_PATH, "--demo"], python="python.exe")
    assert command == [
        "python.exe",
        "-m",
        "configbuilder.ui.render.qt",
        SPACED_PATH,
        "--demo",
    ]
    assert command[-2] == SPACED_PATH  # still a single element
    assert " " not in command[0]  # no shell string was assembled


@pytest.mark.parametrize("arguments", [[], ["--demo"], ["--help"], [SPACED_PATH]])
def test_gui_forwards_this_process_arguments_by_default(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["gui.py", *arguments])
    seen = {}

    def runner(command, **kwargs):
        seen["command"] = command
        return _Completed(0)

    assert gui.main(runner=runner) == 0
    assert seen["command"] == gui.build_command(arguments)
    assert [str(a) for a in arguments] == seen["command"][3:]


# -- gui.py: launching the child -----------------------------------------------


def test_gui_runs_the_child_from_the_repository_root_without_a_shell(
    monkeypatch, fake_root
):
    monkeypatch.setattr(gui, "repository_root", lambda: fake_root)
    seen = {}

    def runner(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return _Completed(0)

    assert gui.main(["--demo"], runner=runner) == 0
    assert seen["command"] == [
        str(gui.gui_python(fake_root)),
        "-m",
        "configbuilder.ui.render.qt",
        "--demo",
    ]
    # Only cwd is passed: no shell, no string command, no captured output.
    assert seen["kwargs"] == {"cwd": str(fake_root)}


@pytest.mark.parametrize("status", [0, 1, 7])
def test_gui_propagates_the_child_exit_code(monkeypatch, fake_root, status):
    monkeypatch.setattr(gui, "repository_root", lambda: fake_root)
    assert gui.main([], runner=lambda *a, **k: _Completed(status)) == status


def test_gui_reports_a_failed_child_with_the_install_command(
    monkeypatch, fake_root, capsys
):
    """A dependency failure is surfaced, never hidden."""
    monkeypatch.setattr(gui, "repository_root", lambda: fake_root)
    assert gui.main([], runner=lambda *a, **k: _Completed(1)) == 1
    err = capsys.readouterr().err
    assert "exited with status 1" in err
    assert 'pip install -e ".[gui,templates]"' in err


# -- gui.py: no environment, no launch -----------------------------------------


def test_missing_environment_is_actionable_and_launches_nothing(
    monkeypatch, tmp_path, capsys
):
    """No ``.venv-gui``: print copyable commands, exit non-zero, start nothing."""
    monkeypatch.setattr(gui, "repository_root", lambda: tmp_path)

    def exploding_runner(*args, **kwargs):
        raise AssertionError("gui.py must not launch anything without .venv-gui")

    status = gui.main(["--demo"], runner=exploding_runner)

    assert status != 0
    captured = capsys.readouterr()
    message = captured.err + captured.out
    assert str(gui.gui_python(tmp_path)) in message
    assert "venv .venv" in message
    assert 'pip install -e ".[gui,templates]"' in message
    assert not (tmp_path / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")).exists()


def test_the_gui_launcher_imports_no_desktop_or_project_dependency():
    """It runs on the plain core interpreter: stdlib only, at module import."""
    assert _imported_roots(ROOT / "gui.py") == {
        "__future__",
        "os",
        "subprocess",
        "sys",
        "pathlib",
    }


# -- the real wrapper, end to end (no window) ----------------------------------


@pytest.mark.skipif(
    not gui.gui_python().exists(),
    reason="the isolated GUI environment (.venv-gui) has not been created",
)
def test_gui_launcher_help_round_trips_through_the_real_environment():
    """``python gui.py --help`` reaches the real GUI module and exits at parsing.

    ``--help`` is handled by ``argparse`` before any ``QApplication`` exists,
    so this exercises the launcher, the interpreter switch and the module
    path with no window and no display.
    """
    result = _run_process([sys.executable, str(ROOT / "gui.py"), "--help"], ROOT)
    assert result.returncode == 0, (result.returncode, result.stderr[-600:])
    assert "--demo" in result.stdout
    assert "Traceback" not in result.stderr
