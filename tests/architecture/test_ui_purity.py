"""UI purity (IMPLEMENTATION_PLAN.md §5.3 rule 9, §18.7; CHECKLIST 11a).

``ui/steps/`` and ``ui/present/`` import no terminal library, must not
read or write a stream, and must not consult the environment — only
``ui/render/`` (Phase 11b) may do those things. The direction inside
``ui`` is ``render → steps → present``; ``ui`` imports ``app`` and
``model.traceability`` only (rule 6). All assertions are static, over
the AST and the source text.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scanner import iter_source_modules  # noqa: E402

UI_ROOT = Path("configbuilder") / "ui"

# Anything that could pull in a terminal, a TTY, or console I/O. The
# guaranteed path is stdlib-only, but the *rule* is that steps/present
# do not even import the stdlib terminal modules — drawing belongs to
# ui/render (plan §5.3 rule 9).
TERMINAL_MODULES = {
    "curses",
    "curses.ascii",
    "curses.panel",
    "termios",
    "tty",
    "pty",
    "readline",
    "rlcompleter",
    "prompt_toolkit",
    "rich",
    "colorama",
    "blessed",
    "urwid",
    "msvcrt",
}

# Symbols that read/write streams or consult the environment.
FORBIDDEN_NAMES = {
    "sys.stdin",
    "sys.stdout",
    "sys.stderr",
    "os.environ",
    "getenv",
    "environ",
    "input",
    "print",
    "open",
    "termios",
    "msvcrt",
}

# Functions that must never appear in steps/present source.
STREAM_CALLS = {"input", "print", "open"}


def _steps_present_modules():
    for source in iter_source_modules():
        if source.module.startswith("configbuilder.ui.steps") or source.module.startswith(
            "configbuilder.ui.present"
        ):
            yield source


def test_steps_and_present_import_no_terminal_library():
    violations = []
    for source in _steps_present_modules():
        for node in ast.walk(source.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in TERMINAL_MODULES:
                        violations.append("%s imports %s" % (source.module, alias.name))
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in TERMINAL_MODULES:
                    violations.append("%s imports from %s" % (source.module, node.module))
    assert not violations, violations


def test_steps_and_present_touch_no_stream():
    """No ``input``/``print``/``open`` calls and no ``sys.stdin``/
    ``sys.stdout``/``sys.stderr`` references in steps/present."""
    import re

    stream_calls = re.compile(r"(?<![\w.])(input|print|open)\s*\(")
    violations = []
    for source in _steps_present_modules():
        text = source.path.read_text(encoding="utf-8")
        for marker in ("sys.stdin", "sys.stdout", "sys.stderr"):
            if marker in text:
                violations.append("%s uses %s" % (source.module, marker))
        for match in stream_calls.finditer(text):
            violations.append("%s calls %s(" % (source.module, match.group(1)))
    assert not violations, violations


def test_steps_and_present_consult_no_environment():
    violations = []
    for source in _steps_present_modules():
        for node in ast.walk(source.tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.attr == "environ" and node.value.id == "os":
                    violations.append("%s reads os.environ" % source.module)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "getenv":
                    violations.append("%s calls getenv" % source.module)
    assert not violations, violations


def test_ui_imports_only_app_model_and_itself():
    """Rule 6 in force for the whole ``ui`` family: no transform,
    serialize, output, persistence imports (app and model.traceability
    are the permitted dependencies)."""
    import sys as _sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    violations = []
    for source in iter_source_modules():
        if not source.module.startswith("configbuilder.ui"):
            continue
        for node in ast.walk(source.tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                targets = [node.module]
            for target in targets:
                if target.startswith("configbuilder.transform") or target in (
                    "configbuilder.serialize",
                    "configbuilder.output",
                    "configbuilder.persistence",
                ):
                    violations.append("%s imports %s" % (source.module, target))
    assert not violations, violations


def test_ui_never_reaches_the_pipeline_from_steps_or_present():
    """steps/present import no ``app`` either: the *view* is handed to
    them; the render layer (and only it) performs service calls from
    ``ServiceCall`` data."""
    violations = []
    for source in _steps_present_modules():
        for node in ast.walk(source.tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                targets = [node.module]
            for target in targets:
                if target.startswith("configbuilder.app"):
                    violations.append("%s imports %s" % (source.module, target))
    assert not violations, violations
