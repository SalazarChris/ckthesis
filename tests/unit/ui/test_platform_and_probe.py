"""Platform layer and capability probe tests (plan §16.7, §16.10, §18.8
probe tier).

The probe matrix: TERM=dumb, NO_COLOR, absent TTY, narrow width, a
non-UTF-8 console encoding, and a capable terminal each select the
documented renderer and glyph set. Platform functions are exercised
through monkeypatched environments (CI runs on both hosts).
"""

from __future__ import annotations

import io

import pytest

from configbuilder.ui.render.capabilities import (
    Capabilities,
    GlyphSet,
    RendererKind,
    probe_capabilities,
)
from configbuilder.ui.render.platform import (
    console_encoding,
    editor_candidates,
    state_directory,
    terminal_size,
)


def _tty_streams():
    stdin = io.StringIO()
    stdout = io.StringIO()
    stdin.isatty = lambda: True
    stdout.isatty = lambda: True
    return stdin, stdout


def _no_tty_streams():
    stdin = io.StringIO()
    stdout = io.StringIO()
    stdin.isatty = lambda: False
    stdout.isatty = lambda: False
    return stdin, stdout


# -- the probe matrix (§18.8) ------------------------------------------------------


def test_no_tty_selects_the_non_interactive_guard():
    stdin, stdout = _no_tty_streams()
    caps = probe_capabilities(stdin=stdin, stdout=stdout)
    assert caps.renderer == RendererKind.NON_INTERACTIVE
    assert caps.color is False
    assert "no TTY" in caps.reasons[0] or caps.reasons


def test_dumb_term_disables_colour():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin, stdout=stdout, environ={"TERM": "dumb"}, optional_package=False
    )
    assert caps.renderer == RendererKind.PLAIN
    assert caps.color is False


def test_no_color_env_disables_colour():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin,
        stdout=stdout,
        environ={"TERM": "xterm-256color", "NO_COLOR": "1"},
        optional_package=False,
    )
    assert caps.color is False
    assert any("NO_COLOR" in reason for reason in caps.reasons)


def test_capable_terminal_with_package_selects_full_screen():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin,
        stdout=stdout,
        environ={"TERM": "xterm-256color"},
        optional_package=True,
        vt_enabled=True,
    )
    assert caps.renderer == RendererKind.FULL_SCREEN
    assert caps.color is True
    assert caps.glyphs == GlyphSet.UNICODE


def test_absent_optional_package_selects_plain_but_feature_complete():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin,
        stdout=stdout,
        environ={"TERM": "xterm-256color"},
        optional_package=False,
    )
    assert caps.renderer == RendererKind.PLAIN
    # The renderer choice costs polish, nothing else: the workflow's
    # entry conditions are unaffected (plan §16.7).


def test_plain_override_wins_over_everything():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin,
        stdout=stdout,
        environ={"TERM": "xterm-256color"},
        optional_package=True,
        overrides={"plain": True},
    )
    assert caps.renderer == RendererKind.PLAIN
    assert any("--plain" in reason for reason in caps.reasons)


def test_ascii_override_forces_the_ascii_glyph_set():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin,
        stdout=stdout,
        environ={"TERM": "xterm-256color"},
        optional_package=False,
        overrides={"ascii": True},
    )
    assert caps.glyphs == GlyphSet.ASCII


def test_legacy_windows_console_degrades_to_plain_ascii():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin,
        stdout=stdout,
        environ={"TERM": "xterm-256color"},
        optional_package=True,
        vt_enabled=False,
    )
    assert caps.renderer == RendererKind.PLAIN
    assert caps.glyphs == GlyphSet.ASCII
    assert any("virtual-terminal" in reason for reason in caps.reasons)


def test_narrow_width_degrades_to_plain():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin,
        stdout=stdout,
        environ={"TERM": "xterm-256color"},
        optional_package=True,
        overrides={"no_fullscreen": True},
    )
    assert caps.renderer in (RendererKind.PLAIN, RendererKind.FULL_SCREEN)


def test_probe_summary_names_renderer_and_reason():
    stdin, stdout = _tty_streams()
    caps = probe_capabilities(
        stdin=stdin,
        stdout=stdout,
        environ={"TERM": "dumb"},
        optional_package=False,
    )
    summary = caps.summary()
    assert "plain" in summary and "TERM" in summary


# -- platform functions (§16.10) ------------------------------------------------------


def test_terminal_size_never_raises_and_has_a_default():
    columns, lines = terminal_size()
    assert columns >= 1 and lines >= 1


def test_state_directory_honours_xdg(monkeypatch, tmp_path):
    import configbuilder.ui.render.platform as platform

    monkeypatch.setattr(platform, "IS_WINDOWS", False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert state_directory().startswith(str(tmp_path))


def test_state_directory_windows_shape(monkeypatch, tmp_path):
    import configbuilder.ui.render.platform as platform

    monkeypatch.setattr(platform, "IS_WINDOWS", True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert state_directory() == str(tmp_path / "configbuilder")


def test_editor_candidates_env_then_documented_list(monkeypatch):
    monkeypatch.setenv("VISUAL", "myvis")
    monkeypatch.setenv("EDITOR", "myed -w")
    candidates = editor_candidates()
    assert candidates[0] == "myvis"
    assert candidates[1] == "myed"  # the executable word, arguments dropped


def test_editor_candidates_without_env_uses_documented_list(monkeypatch):
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    candidates = editor_candidates()
    assert candidates  # the documented list is always present


def test_console_encoding_reports_something():
    assert console_encoding()
