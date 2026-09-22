"""The capability probe (IMPLEMENTATION_PLAN.md §16.7, §16.9).

One decision at startup: which renderer and which glyph set. The probe
reads the environment once, applies the explicit overrides
(``--plain``/``--ascii``/``--no-color``), logs its result **and its
reason**, and changes nothing about what the wizard asks. Renderer
selection is the only decision it makes (plan §16.7).
"""

from __future__ import annotations

import os
import sys

from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.platform import (
    console_encoding,
    enable_windows_virtual_terminal,
    terminal_size,
)

__all__ = ["Capabilities", "RendererKind", "GlyphSet", "probe_capabilities"]


class RendererKind:
    """The renderer choices (plain and non-interactive are stdlib)."""

    PLAIN = "plain"
    FULL_SCREEN = "full_screen"
    NON_INTERACTIVE = "non_interactive"


class GlyphSet:
    """Unicode when confirmed, ASCII on doubt (plan §16.7)."""

    UNICODE = "unicode"
    ASCII = "ascii"


class Capabilities:
    """The probe's result: renderer, glyphs, colour, width, and the
    reasons — so \"it printed strange characters\" is diagnosable from
    the log (plan §16.7)."""

    __slots__ = ("renderer", "glyphs", "color", "width", "height", "reasons")

    def __init__(self, renderer, glyphs, color: bool, width: int, height: int, reasons=()) -> None:
        self.renderer = renderer
        self.glyphs = glyphs
        self.color = bool(color)
        self.width = int(width)
        self.height = int(height)
        self.reasons = tuple(reasons)

    def summary(self) -> str:
        """The one-line probe log: renderer, glyph set, colour, size,
        and why (wording from the wizard string registry)."""
        return _text("probe.summary") % (
            self.renderer,
            self.glyphs,
            "on" if self.color else "off",
            self.width,
            self.height,
            _text("journal.join").join(self.reasons) or _text("probe.default_reason"),
        )


def probe_capabilities(
    stdin=None,
    stdout=None,
    overrides=None,
    optional_package=None,
    vt_enabled=None,
    environ=None,
) -> Capabilities:
    """Read the environment once and decide.

    ``stdin``/``stdout`` default to the real streams (injected for
    tests); ``overrides`` carries the explicit flags; the optional
    package importability and the Windows VT outcome are parameters the
    caller resolves so the probe itself imports nothing optional and
    touches no real console (plan §16.7); ``environ`` defaults to the
    real environment.
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    environ = environ if environ is not None else os.environ
    overrides = dict(overrides or {})
    reasons = []

    # The overrides win immediately (plan §16.9: a user is never
    # dependent on the probe guessing correctly).
    if overrides.get("plain"):
        reasons.append(_text("probe.reason.plain_override"))
    if overrides.get("ascii"):
        reasons.append(_text("probe.reason.ascii_override"))

    # TTY: without one, the non-interactive guard applies — never prompt
    # into a pipe (plan §16.0, §16.7).
    is_tty = False
    try:
        is_tty = bool(stdin.isatty() and stdout.isatty())
    except Exception:
        is_tty = False
    if not is_tty:
        reasons.append(_text("probe.reason.no_tty"))
        return Capabilities(
            renderer=RendererKind.NON_INTERACTIVE,
            glyphs=GlyphSet.ASCII,
            color=False,
            width=80,
            height=24,
            reasons=reasons,
        )

    width, height = terminal_size()
    if width < 80:
        reasons.append(_text("probe.reason.narrow") % width)

    # Optional full-screen package: only when importable AND a capable
    # interactive TTY. The importability decision lives in exactly one
    # place (fullscreen.available) — the probe asks, never assumes.
    if optional_package is None:
        from configbuilder.ui.render.fullscreen import available as _fs_available

        full_screen_available = _fs_available()
    else:
        full_screen_available = bool(optional_package)

    # Colour: NO_COLOR and non-colour TERM are honoured (plan §16.0).
    color = True
    if environ.get("NO_COLOR"):
        color = False
        reasons.append(_text("probe.reason.no_color"))
    term = environ.get("TERM", "")
    if term in ("", "dumb") and not overrides.get("force_color"):
        color = False
        reasons.append(_text("probe.reason.term") % (term or "unset"))

    # Glyphs: ASCII on doubt (plan §16.7).
    glyphs = GlyphSet.UNICODE
    if overrides.get("ascii"):
        glyphs = GlyphSet.ASCII
    elif not _encoding_is_utf8(console_encoding(), stdout):
        glyphs = GlyphSet.ASCII
        reasons.append(_text("probe.reason.encoding"))

    # Windows legacy console: VT processing or plain (plan §16.7).
    renderer = None
    if overrides.get("plain"):
        renderer = RendererKind.PLAIN
    elif full_screen_available and 80 <= width and not overrides.get("no_fullscreen"):
        vt = vt_enabled if vt_enabled is not None else enable_windows_virtual_terminal()
        if not vt:
            renderer = RendererKind.PLAIN
            glyphs = GlyphSet.ASCII
            reasons.append(_text("probe.reason.vt"))
    if renderer is None:
        if width < 60:
            renderer = RendererKind.PLAIN
            reasons.append(_text("probe.reason.floor"))
        elif not full_screen_available:
            renderer = RendererKind.PLAIN
            reasons.append(_text("probe.reason.package_absent"))
        else:
            renderer = RendererKind.FULL_SCREEN

    return Capabilities(
        renderer=renderer,
        glyphs=glyphs,
        color=color,
        width=width,
        height=height,
        reasons=reasons,
    )


def _encoding_is_utf8(encoding_name: str, stdout) -> bool:
    if not encoding_name or encoding_name in ("utf-8", "utf8"):
        return True
    return False
