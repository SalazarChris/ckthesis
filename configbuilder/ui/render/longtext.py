"""Long-text entry routes (IMPLEMENTATION_PLAN.md §16.5).

Sequences, alignment content, and inline chemistry definitions are
large; paste, read-from-file, and an optional editor carry them. The
rules that bind all three routes:

- **No silent repair** — nothing is truncated, reflowed, re-cased, or
  whitespace-normalized; content reaches the model byte-for-byte.
- **Line endings are reported, not fixed** — CRLF is detected and
  reported, the policy is *preserve and warn* (plan §22 Q16), and
  validation decides whether it is invalid.
- **What was received is echoed back** as a summary before acceptance,
  so a clipped paste is caught at entry (plan §16.5).

The routes talk to streams through the ``Console`` passed in; every
decision function here is pure and separately testable.
"""

from __future__ import annotations

import os

from configbuilder.ui.present.strings import text as _text

__all__ = [
    "ReceivedContent",
    "summarize",
    "crlf_report",
    "strip_comment_lines",
    "parse_index_pairs",
    "collect_long_text",
    "parse_pairs_text",
]


class ReceivedContent:
    """What a route received, before acceptance (plan §16.5)."""

    __slots__ = ("content", "route", "line_endings", "lines")

    def __init__(self, content: bytes, route: str) -> None:
        self.content = content
        self.route = route
        self.line_endings = _line_ending_kind(content)
        self.lines = content.count(b"\n") + (0 if content.endswith(b"\n") or not content else 1)

    @property
    def byte_count(self) -> int:
        return len(self.content)

    @property
    def crlf(self) -> bool:
        return self.line_endings == "crlf"


def _line_ending_kind(content: bytes) -> str:
    has_crlf = b"\r\n" in content
    lone_lf = b"\n" in content.replace(b"\r\n", b"")
    if has_crlf and lone_lf:
        return "mixed"
    if has_crlf:
        return "crlf"
    return "lf"


def summarize(received: ReceivedContent) -> str:
    """The received-content echo: length, shape, line-ending condition
    — never the content itself (plan §16.5)."""
    shape = "plausible" if received.byte_count else "empty"
    plural = "" if received.lines == 1 else _text("summary.plural")
    line = _text("summary.received") % (
        received.byte_count,
        received.lines,
        _text("summary.lines_suffix") % plural,
        shape,
    )
    if received.line_endings == "crlf":
        line += _text("summary.crlf")
    elif received.line_endings == "mixed":
        line += _text("summary.mixed")
    return line


def crlf_report(content: bytes) -> str:
    """The preserve-and-warn notice for CRLF content, or ``""`` when
    the content carries none (plan §16.5, §22 Q16)."""
    kind = _line_ending_kind(content)
    if kind == "crlf":
        return _text("crlf.crlf")
    if kind == "mixed":
        return _text("crlf.mixed")
    return ""


def strip_comment_lines(text: str) -> str:
    """Remove editor-header comment lines (``#``-prefixed and blank
    leader lines). This is the *editor route's documented header
    convention*, not silent repair: the header is written by the wizard
    itself (plan §16.5)."""
    kept = []
    for line in text.split("\n"):
        if line.strip().startswith("#"):
            continue
        kept.append(line)
    return "\n".join(kept)


def parse_index_pairs(text: str):
    """Parse pasted reference mappings into ``(query, template)`` pairs.

    One pair per line, comma- or whitespace-separated, 0-based. Returns
    ``(pairs, errors)`` where ``errors`` are ``(line_number, message)``
    — reported per line, never guessed (plan §16.4)."""
    pairs = []
    errors = []
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace(",", " ").split()
        if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
            errors.append((number, _text("route.pairs.error")))
            continue
        pairs.append((int(parts[0]), int(parts[1])))
    return tuple(pairs), tuple(errors)


def parse_pairs_text(text: str):
    """Alias kept for the worked-example flow name in §16.4."""
    return parse_index_pairs(text)


def collect_long_text(console, title: str, routes=("paste", "file", "editor"), editors_available=None):
    """The §16.5 route menu, driven through ``console``.

    Returns ``(content_bytes, route_name, notice)`` or ``(None, None,
    notice)`` when the user declines. ``editors_available`` gates the
    editor option: when none exists the option is *not offered* and the
    wizard says why if asked (plan §16.5: no editor is a dependency)."""
    from configbuilder.ui.render.longtext_io import read_from_file, read_via_editor

    offered = []
    if "paste" in routes:
        offered.append(("1", "paste", _text("route.menu.paste")))
    if "file" in routes:
        offered.append(("2", "file", _text("route.menu.file")))
    if editors_available is None:
        editors_available = bool(os.environ.get("VISUAL") or os.environ.get("EDITOR"))
    if editors_available and "editor" in routes:
        offered.append(("3", "editor", _text("route.menu.editor")))
    if not offered:  # degenerate call: nothing can be collected
        return None, None, _text("route.none_available")

    console.write_line(title)
    for number, _route, label in offered:
        console.write_line("  %s) %s" % (number, label))
    default = offered[0][0]
    choice = console.prompt(_text("route.choose") % default).strip() or default
    selected = dict((number, route) for number, route, _label in offered).get(choice, "paste")

    if selected == "paste":
        content = console.read_multiline(_text("route.paste.instructions"))
        received = ReceivedContent(content, "paste")
    elif selected == "file":
        path = console.prompt(_text("route.file.prompt")).strip()
        content, notice = read_from_file(console, path)
        if content is None:
            return None, None, notice
        received = ReceivedContent(content, "file")
    else:
        content, notice = read_via_editor(console, title)
        if content is None:
            return None, None, notice
        received = ReceivedContent(content, "editor")

    notice = crlf_report(received.content)
    console.write_line(summarize(received))
    return received.content, received.route, notice
