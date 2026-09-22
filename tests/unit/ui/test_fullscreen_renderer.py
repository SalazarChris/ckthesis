"""Full-screen renderer tests (IMPLEMENTATION_PLAN.md §16.7, Phase 11c).

The exit criterion is "same transcript; no behavioural difference".
These tests pin it from three sides:

1. **Transcript parity** — the identical script through
   ``PlainLineRenderer`` and ``FullScreenRenderer`` (over fresh,
   identically-wired services) produces line-identical output;
2. **Output parity** — the files the two runs write are byte-identical
   (the encode/serialize guarantees are renderer-independent);
3. **Probe parity** — the probe selects full screen exactly when the
   capability table says it must, and the session degrades to plain
   when the package disappears after the probe.

The full-screen renderer is tested without a real terminal: the
underlying input object is a scripted double standing in for
prompt_toolkit's prompt surface (a pty would make these tests
host-dependent, and §18.8's harnesses are the plain-line snapshots —
the *structure* of parity is what these tests own).
"""

from __future__ import annotations

import os
import unittest.mock

import pytest


from configbuilder.ui.render.capabilities import (
    Capabilities,
    GlyphSet,
    RendererKind,
    probe_capabilities,
)
from configbuilder.ui.render.fullscreen import FullScreenRenderer, available
from configbuilder.ui.render.journal import NullJournal
from configbuilder.ui.render.plain import PlainLineRenderer
from configbuilder.ui.render.wizard import WizardSession
from configbuilder.ui.services import build_services

from tests.e2e.test_wizard_pipeline import (
    _add_protein,
    _capabilities,
    _new_named_project,
    _pin_evidenced,
)


def _plain_session(script, tmp_path):
    from configbuilder.ui.render.console import ScriptedConsole

    console = ScriptedConsole(script)
    session = WizardSession(
        build_services(), console, _capabilities(), journal=NullJournal()
    )
    return session, console


def _full_session(script, tmp_path):
    console = _StubbedFullScreen(script)
    session = WizardSession(
        build_services(),
        console,
        _capabilities(renderer=RendererKind.FULL_SCREEN),
        journal=NullJournal(),
    )
    return session, console


class _StubbedFullScreen:
    """A full-screen renderer over a scripted input surface.

    ``prompt_toolkit``'s real prompt loop is replaced by a scripted
    feed — the *drive* (the thing 11c must prove identical) is the
    real one; only the keystroke source is synthetic. If the optional
    package is absent in an environment, the class still constructs:
    the renderer itself never needs it to *ask questions*.
    """

    def __init__(self, script) -> None:
        self._lines = list(script)
        self._pos = 0
        self._chunks = []  # raw output, exactly like Console's stream
        self.title = "configbuilder"
        self.completions_requested = []
        self._renderer = FullScreenRenderer.__new__(FullScreenRenderer)
        from configbuilder.ui.render.drive import StepDrive

        self._drive = StepDrive(build_services(), report_sink=None)
        self._drive.write_line = self.write_line
        self._drive.ask = self.ask
        self._renderer.drive = self._drive
        self._renderer.console = self

    # -- the FullScreenRenderer surface the session calls -----------------

    @property
    def drive(self):
        return self._drive

    def run(self, machine, view_provider, journal=None):
        return self._drive.run(machine, view_provider, journal=journal)

    def remember_report(self, report) -> None:
        self._drive.remember_report(report)

    # -- the two primitives ----------------------------------------------

    def write_line(self, text: str = "") -> None:
        self._chunks.append(text + "\n")

    def ask(self, prompt_text, field=None) -> str:
        if field is not None:
            self.completions_requested.append(getattr(field, "key", None))
        # The prompt text is emitted *without* a trailing newline —
        # exactly what Console.prompt writes — so the transcript joins
        # identically to the plain renderer's.
        self._chunks.append(prompt_text)
        line = self._lines[self._pos] if self._pos < len(self._lines) else ""
        self._pos += 1
        return line

    @property
    def transcript(self) -> str:
        return "".join(self._chunks)


# -- 1. transcript parity ---------------------------------------------------------------


def _full_run_script(tmp_path, out_name="out"):
    """One script that exercises every §16.3-16.6 interaction: new,
    name, add a protein, advanced version pin, validate, walk the
    steps, add a variant through the factor picker, generate.
    ``out_name`` separates the two parity runs' output roots so the
    second plans 'create', not 'overwrite' (a harness concern, not a
    renderer difference)."""
    script = []
    _new_named_project(script)
    _add_protein(script)
    script.extend(["a", "3", "PIN-001"])  # advanced: pin version 3 with evidence
    script.append("v")  # validate (findings display)
    script.extend(["n"] * 8)  # molecules -> ... -> variants
    script.extend(["nob", "sequence", "A", "AUUA", "no B chain"])
    script.append("n")  # review -> generate
    script.append(str(tmp_path / out_name))  # output root
    script.append("y")  # confirm the reviewed plan
    return script


def test_transcript_is_identical_between_renderers(tmp_path):
    with _pin_evidenced():
        script = _full_run_script(tmp_path, "out_plain")

        _s1, c1 = _plain_session(list(script), tmp_path)
        status1 = _run(_s1)
        t1 = c1.transcript

        _s2, c2 = _full_session(_full_run_script(tmp_path, "out_full"), tmp_path)
        status2 = _run(_s2)
        t2 = c2.transcript

        assert status1 == status2 == 0
        # Line-identical transcripts (§16.7 exit criterion) — except
        # the probe summary's renderer token, which §16.7 *requires* to
        # differ: the probe logs which renderer it selected and why.
        # Pin both: the one differing line differs exactly there, and
        # every other line is identical. The two runs' output roots
        # (out_plain / out_full) are normalized too — they are the
        # harness's separation of on-disk effects, not a renderer
        # difference.
        t1 = t1.replace("out_plain", "out_ROOT")
        t2 = t2.replace("out_full", "out_ROOT")
        lines1, lines2 = t1.splitlines(), t2.splitlines()
        assert len(lines1) == len(lines2)
        for index, (a, b) in enumerate(zip(lines1, lines2)):
            if index == 0 and a.startswith("probe:") and b.startswith("probe:"):
                assert a.replace("renderer=plain", "renderer=X") == b.replace(
                    "renderer=full_screen", "renderer=X"
                )
            else:
                assert a == b, (index, a, b)


def _run(session):
    return session.run()


# -- 2. output parity -----------------------------------------------------------------


def test_written_output_is_byte_identical_between_renderers(tmp_path):
    with _pin_evidenced():
        _s1, _c1 = _plain_session(_full_run_script(tmp_path, "out_plain"), tmp_path)
        _run(_s1)
        _s2, _c2 = _full_session(_full_run_script(tmp_path, "out_full"), tmp_path)
        _run(_s2)

        def _read_all(root):
            out = {}
            for base, _dirs, files in os.walk(root):
                for name in files:
                    path = os.path.join(base, name)
                    out[os.path.relpath(path, root)] = open(path, "rb").read()
            return out

        first = _read_all(tmp_path / "out_plain")
        second = _read_all(tmp_path / "out_full")
        assert first, "nothing was written"
        assert sorted(first) == sorted(second)
        # The encode/serialize guarantees are renderer-independent:
        # every file byte-identical, including the manifest.
        for name in first:
            assert first[name] == second[name], name


# -- 3. probe parity -----------------------------------------------------------------


def test_probe_selects_full_screen_only_for_capable_tty_with_package():
    class FakeStream:
        def isatty(self):
            return True

    caps = probe_capabilities(
        stdin=FakeStream(),
        stdout=FakeStream(),
        environ={"TERM": "xterm-256color"},
        optional_package=True,
        vt_enabled=True,
    )
    if available():
        assert caps.renderer == RendererKind.FULL_SCREEN
    else:  # CI without the extra: the guarantee is plain, never a crash
        assert caps.renderer == RendererKind.PLAIN


def test_probe_degrades_to_plain_without_the_package():
    class FakeStream:
        def isatty(self):
            return True

    caps = probe_capabilities(
        stdin=FakeStream(),
        stdout=FakeStream(),
        environ={"TERM": "xterm-256color"},
        optional_package=False,  # the package is not importable
        vt_enabled=True,
    )
    assert caps.renderer == RendererKind.PLAIN
    assert any("package" in reason.lower() for reason in caps.reasons)


def test_session_degrades_to_plain_when_package_vanishes_after_probe():
    """The probe said full screen; the import then fails. The session
    must degrade to plain — never crash (§16.7's one-decision rule)."""
    with unittest.mock.patch(
        "configbuilder.ui.render.fullscreen.available", return_value=False
    ):
        from configbuilder.ui.render.console import ScriptedConsole

        console = ScriptedConsole(["q", ""])
        session = WizardSession(
            build_services(),
            console,
            _capabilities(renderer=RendererKind.FULL_SCREEN),
            journal=NullJournal(),
        )
        with _pin_evidenced():
            status = session.run()
        assert status == 0
        # It ran — through the plain renderer (transcript happened).
        assert "Step 1 of 14" in console.transcript


def test_fullscreen_missing_package_error_is_registered_wording():
    from configbuilder.ui.present.strings import text as _text

    with unittest.mock.patch(
        "configbuilder.ui.render.fullscreen.available", return_value=False
    ):
        with pytest.raises(RuntimeError) as excinfo:
            FullScreenRenderer(None, build_services())
        assert _text("guard.fullscreen_missing") in str(excinfo.value)


# -- convenience-only extras ------------------------------------------------------------


def test_pager_falls_back_to_linear_output_without_a_surface():
    """The internal pager (§16.7) must never shell out and never cut
    content: without a usable paging surface it emits linearly."""
    console = _StubbedFullScreen([])
    renderer = console._renderer
    renderer.page("Technical detail", ["line one", "line two"])
    assert "line one" in console.transcript
    assert "line two" in console.transcript


def test_path_completion_is_offered_only_on_path_fields():
    """The _DriveConsole completes only on path fields — completion on
    non-path fields would *suggest* rather than ask (§16.7)."""
    from configbuilder.ui.render.fullscreen import _PATH_FIELD_KEYS, _DriveConsole

    assert "path" in _PATH_FIELD_KEYS
    assert "external_path" in _PATH_FIELD_KEYS
    assert "family" not in _PATH_FIELD_KEYS
    console = _DriveConsole()

    class FakeField:
        def __init__(self, key):
            self.key = key

    assert console._completer_for(FakeField("path")) is not None
    assert console._completer_for(FakeField("external_path")) is not None
    assert console._completer_for(FakeField("family")) is None
    assert console._completer_for(None) is None


def test_available_matches_the_optional_package():
    # The one decision point agrees with reality in this environment.
    try:
        import prompt_toolkit  # noqa: F401

        installed = True
    except Exception:
        installed = False
    assert available() is installed
