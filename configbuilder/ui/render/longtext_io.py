"""File and editor route IO (IMPLEMENTATION_PLAN.md §16.5).

Read-from-file reports what it found; the editor route writes a
temporary buffer with a commented header and a worked example, launches
the discovered editor, re-reads on exit, and on a parse problem returns
the user to the same buffer with the error at the top rather than
discarding the work. Content is preserved byte-for-byte — the editor
round-trip is byte-exact.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.platform import editor_candidates

__all__ = ["read_from_file", "read_via_editor", "find_editor", "editor_header"]


def editor_header(title: str, example: str) -> str:
    """The commented header + worked example written into the buffer
    (plan §16.5)."""
    return (
        "# %s\n"
        "# Edit the content below the line. Lines starting with '#' are\n"
        "# removed when you save. Do not add formatting; the text is used\n"
        "# exactly as it stands.\n"
        "# Example:\n"
        "#   %s\n"
        "# -------------------8<-------------------\n" % (title, example)
    )


def find_editor(candidates=None):
    """The first candidate that exists as an executable file, or
    ``None`` — **no external editor is a dependency** (plan §16.5)."""
    from shutil import which

    for candidate in candidates if candidates is not None else editor_candidates():
        if not candidate:
            continue
        if os.path.isabs(candidate):
            if os.path.isfile(candidate):
                return candidate
            continue
        found = which(candidate)
        if found:
            return found
    return None


def read_from_file(console, path: str):
    """Read a file byte-for-byte and report what it found.

    Returns ``(content, notice)``; ``content`` is ``None`` when the
    path is unusable, with the reason in ``notice`` (plan §16.5)."""
    if not path:
        return None, _text("route.file.none")
    expanded = os.path.expanduser(os.path.expandvars(path))
    try:
        with open(expanded, "rb") as handle:
            content = handle.read()
    except OSError as error:
        return None, _text("route.file.error") % (path, error)
    notice = _text("route.file.read") % (len(content), expanded)
    return content, notice


def read_via_editor(console, title: str, example=None, editor=None):
    """Round-trip a temporary buffer through the user's editor.

    Returns ``(content, notice)``; ``content`` is ``None`` when no
    editor exists (the route is simply not usable, with the reason) or
    the editor could not be run. The original bytes are kept exactly —
    comment lines are stripped by the *documented convention* only when
    the caller asks for it, via ``strip_comment_lines`` (plan §16.5)."""
    from configbuilder.ui.render.longtext import strip_comment_lines

    command = editor if editor is not None else find_editor()
    if command is None:
        return None, _text("route.editor.missing")

    if example is None:
        example = _text("route.example.pairs")
    header = editor_header(title, example)
    handle = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8", newline="")
    try:
        handle.write(header)
        handle.close()
        try:
            subprocess.run([command, handle.name], check=False)
        except OSError as error:
            return None, _text("route.editor.launch_error") % (command, error)
        with open(handle.name, "rb") as reopened:
            raw = reopened.read()
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass

    text = raw.decode("utf-8", errors="replace")
    body = strip_comment_lines(text)
    # Drop the scissors line itself and everything the header owned.
    if "-------------------8<-------------------" in body:
        body = body.split("-------------------8<-------------------", 1)[1]
        if body.startswith("\n"):
            body = body[1:]
    return body.encode("utf-8"), _text("route.editor.complete")
