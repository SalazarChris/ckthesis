"""The console's codec boundary (playtest 2026-10-04).

A terminal's encoding is not the application's business. Two real failures
were reproduced against the running program before these tests existed:

* ``Console.write_line`` raised ``UnicodeEncodeError`` when a registered
  string held a glyph the output code page lacks — ``\u2192`` on cp1252,
  which is what a Windows redirect to a file or pipe uses. Creating a variant
  that renamed the job printed one such row and ended the session with a
  traceback.
* ``Console.prompt`` let ``UnicodeDecodeError`` escape when the input codec
  could not decode a byte (a garbled or binary paste on a UTF-8 stream).

Both are reproduced here at the real stream boundary with real
``io.TextIOWrapper`` streams, not mocks, so the fix is pinned where it lives.
"""

from __future__ import annotations

import io
import sys

import pytest

from configbuilder.ui.render.console import Console, ScriptedConsole


def _text_stream(encoding, errors="strict"):
    """A real text stream over bytes, with an explicitly strict codec."""
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, errors=errors)


def test_default_output_survives_a_glyph_the_code_page_lacks(monkeypatch):
    """The exact failure: '→' written to a cp1252 stdout."""
    stdout = _text_stream("cp1252")
    stdin = _text_stream("utf-8")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stdin", stdin)

    console = Console()
    console.write_line("job name \u2192 renamed")   # must not raise

    stdout.flush()
    raw = stdout.buffer.getvalue()
    assert b"job name ? renamed" in raw, raw
    assert "\u2192".encode("cp1252", "replace") not in raw or b"?" in raw


def test_default_input_survives_bytes_the_codec_cannot_decode(monkeypatch):
    """The other half: invalid bytes on a strict UTF-8 stdin."""
    stdin = _text_stream("utf-8")
    stdin.buffer.write(b"\xff\xfe broken\n")
    stdin.buffer.seek(0)
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", _text_stream("utf-8"))

    console = Console()
    line = console.prompt("Select: ")               # must not raise

    assert "broken" in line


def test_a_caller_supplied_stream_is_not_reconfigured():
    """Only the default streams are adjusted: a stream handed in stays the
    caller's own, so the scripted console and stream captures are untouched."""
    stdout = _text_stream("cp1252")
    stdin = _text_stream("utf-8")

    console = Console(stdin=stdin, stdout=stdout)

    assert console.stdout is stdout
    assert console.stdin is stdin
    assert stdout.errors == "strict"
    assert stdin.errors == "strict"

    with pytest.raises(UnicodeEncodeError):
        console.write_line("job name \u2192 renamed")


def test_scripted_console_is_unaffected():
    console = ScriptedConsole(["0"])
    console.write_line("job name \u2192 renamed")
    console.write_line("plain")
    assert "job name \u2192 renamed" in console.transcript


def test_registered_ui_text_stays_within_a_legacy_code_page():
    """Our own strings must not depend on a modern code page: the playtest
    crash came from registered text, not from user input."""
    from configbuilder.ui.present.strings import STRINGS

    offenders = {}
    for key, value in sorted(STRINGS.items()):
        try:
            value.encode("cp1252")
        except UnicodeEncodeError as error:
            offenders.setdefault(value[error.start], []).append(key)
    assert not offenders, (
        "these registered strings cannot be printed on a cp1252 console: %r"
        % {char: keys for char, keys in offenders.items()}
    )
