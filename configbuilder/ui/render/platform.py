"""The platform layer (IMPLEMENTATION_PLAN.md §16.10).

Everything that differs between POSIX and Windows lives here, so the
rest of the wizard is written once. This is the **only** module allowed
to branch on the host platform (an architecture test asserts it), and
it changes nothing about generated output: line endings, encoding, and
ordering in generated files stay fixed by ``serialize`` (plan §16.10).

Rule 9 boundary note: this module lives in ``ui/render`` — the one
family that may consult the host — and it exposes plain values to its
callers, so platform branching stays confined here while the callers
stay pure-ish: they consume values, they do not branch on the host.
"""

from __future__ import annotations

import os
import sys

__all__ = [
    "IS_WINDOWS",
    "terminal_size",
    "state_directory",
    "editor_candidates",
    "enable_windows_virtual_terminal",
    "console_encoding",
]


IS_WINDOWS = sys.platform == "win32"

# The documented per-platform candidate lists (plan §16.10).
_POSIX_EDITORS = ("vi", "vim", "nano", "emacs")
_WINDOWS_EDITORS = ("notepad.exe",)


def terminal_size():
    """The console's ``(columns, lines)``, or a documented default when
    it cannot be measured (pipes, embedded consoles). Never raises."""
    try:
        import shutil

        size = shutil.get_terminal_size(fallback=(80, 24))
        return int(size.columns), int(size.lines)
    except Exception:  # any console failure degrades to the default
        return 80, 24


def state_directory() -> str:
    """The state directory per §16.10: ``$XDG_STATE_HOME`` or
    ``~/.local/state/configbuilder`` on POSIX,
    ``%LOCALAPPDATA%\\configbuilder`` on Windows."""
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "configbuilder")
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser(
        os.path.join("~", ".local", "state")
    )
    return os.path.join(base, "configbuilder")


def editor_candidates():
    """``$VISUAL``, then ``$EDITOR``, then the documented per-platform
    candidate list. Returns command names/paths, unvalidated — the
    caller probes executability (§16.5: no editor is a dependency)."""
    visual = os.environ.get("VISUAL")
    editor = os.environ.get("EDITOR")
    candidates = []
    if visual:
        candidates.append(visual)
    if editor:
        # Editor env vars may carry arguments ("code -w"); take the
        # executable word for probing.
        candidates.append(editor.split()[0])
    if IS_WINDOWS:
        candidates.extend(_WINDOWS_EDITORS)
    else:
        candidates.extend(_POSIX_EDITORS)
    return candidates


def enable_windows_virtual_terminal():
    """Try to enable virtual-terminal processing on Windows; returns
    True when enabled or not needed. Failure selects the plain renderer
    with the ASCII glyph set (plan §16.7) — never an escape-sequence
    crash on a legacy console."""
    if not IS_WINDOWS:
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
        return True
    except Exception:
        return False


def console_encoding() -> str:
    """The console's output encoding name; on Windows a non-UTF-8
    console selects the ASCII glyph set (plan §16.10)."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return (encoding or "utf-8").lower()
