"""End-to-end terminal-wizard tests (plan §16, Phase 11b checklist).

The whole front end is driven over a ``ScriptedConsole`` — the §18.8
plain-line snapshot harness: scripted stdin in, captured transcript
out, no terminal involved. The service seam is the real ``Services``
wiring (build_services), so these tests are the wiring proof the
checklist asks for: what a user types at the terminal reaches the
Phase 10 application services unchanged.

Scripting notes the tests pin down deliberately:

- the entry answer *is* the first field's answer (``_collect_and_apply``
  consumes it as ``first_answer``), so at ``molecules`` the user types
  the family directly, not ``n`` first;
- a refused answer keeps the user on the step (§16.3), so the script
  must re-supply the fields;
- EOF anywhere is a clean status-0 goodbye, never a traceback (§16.0).
"""

from __future__ import annotations

import os

import pytest


from configbuilder.ui.render.capabilities import (
    Capabilities,
    GlyphSet,
    RendererKind,
    probe_capabilities,
)
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.render.journal import SessionJournal
from configbuilder.ui.render.wizard import WizardSession, run_wizard
from configbuilder.ui.services import build_services


def _pin_evidenced():
    """Historical name; now a no-op context retained for call-site shape.
    There is no runtime pin-file seam left to patch — evidence travels in
    the model (Pinned.evidence), and the wizard scripts below supply it
    explicitly, which is the property this suite exercises."""
    import contextlib

    return contextlib.nullcontext()


def _capabilities(renderer=RendererKind.PLAIN, glyphs=GlyphSet.UNICODE):
    return Capabilities(
        renderer=renderer,
        glyphs=glyphs,
        color=False,
        width=80,
        height=24,
        reasons=("test",),
    )


def _drive(script, journal=None):
    console = ScriptedConsole(script)
    session = WizardSession(
        build_services(), console, _capabilities(), journal=journal
    )
    with _pin_evidenced():
        status = session.run()
    return status, console.transcript


def _new_named_project(script):
    """Start → Job: new project, named (the job_description default is
    accepted with the empty line)."""
    script.extend(["new", "E2E Wizard Job", ""])


def _add_protein(script):
    """Molecules, answered in place: family, sequence, representation
    (ignored for polymers), copies default, description default."""
    script.extend(["protein", "ACDEFGHIKLMNPQRSTVWY", "", "", ""])


def _validate_clean(script):
    """Pin the format version through the advanced action (the §16.4
    advanced screen) and validate; the clean report lands in the
    session's view and the variants gate opens. The pin's evidence is
    an explicit pin with its evidence citation — the same model-supplied
    evidence the transform tests use."""
    script.extend(["a", "3", "PIN-001"])  # advanced: pin version 3 with evidence
    script.append("v")


def test_wizard_drives_the_full_happy_path_to_written_files(tmp_path):
    script = []
    _new_named_project(script)
    _add_protein(script)
    _validate_clean(script)  # from molecules: pin, validate, then walk on
    script.extend(["n"] * 8)  # molecules -> ... -> variants (step 12)
    # The factor picker (§16.4): key, factor, record, value, label. At
    # least one spec is required — the base is never implicitly
    # generated (§12.2).
    script.extend(["nob", "sequence", "A", "AUUA", "no B chain"])
    script.append("n")  # review -> generate
    script.append(str(tmp_path / "out"))  # the output root
    script.append("y")  # confirm the reviewed plan

    status, transcript = _drive(script)
    assert status == 0, transcript
    # The §16.3 header discipline and the probe summary are present.
    assert "Step 1 of 14" in transcript
    assert "probe" in transcript.lower()
    # The output landed where the plan said, and the transcript reports
    # every written path (§16.6).
    variant_file = (
        tmp_path
        / "out"
        / "e2e-wizard-job"
        / "e2e-wizard-job__nob"
        / "e2e-wizard-job__nob.json"
    )
    assert variant_file.exists(), sorted(str(p) for p in tmp_path.rglob("*.json"))
    assert (tmp_path / "out" / "e2e-wizard-job" / "manifest.json").exists()
    assert "manifest.json" in transcript


def test_wizard_persists_and_reports_the_saved_project(tmp_path):
    script = []
    _new_named_project(script)
    _add_protein(script)
    project_path = str(tmp_path / "wizard.cbproj")
    script.extend(["s", project_path])  # save from molecules, no path yet

    status, transcript = _drive(script)
    assert status == 0, transcript
    assert os.path.exists(project_path)
    assert "wizard.cbproj" in transcript


def test_wizard_resume_offer_is_shown_and_declinable(tmp_path):
    services = build_services()
    journal = SessionJournal(directory=str(tmp_path / "state"))
    journal.record("molecules", services.projects)

    script = []
    _new_named_project(script)
    _add_protein(script)
    script.append("q")  # quit at molecules; nothing dirty after the save
    script.append("")  # the discard prompt (project is dirty)

    status, transcript = _drive(script, journal=journal)
    assert status == 0
    # The offer named the recorded step; the user proceeded normally.
    assert "molecules" in transcript
    assert journal.read() is None  # cleared after the offer


def test_wizard_validate_command_shows_numbered_findings(tmp_path):
    script = []
    _new_named_project(script)
    _add_protein(script)
    script.extend(["v", "q", ""])  # validate, then quit through discard

    status, transcript = _drive(script)
    assert status == 0
    # The numbered cards (§16.6): severity word + symbol, technical
    # detail available via the 't <number>' command.
    assert "1. ERROR" in transcript or "1. WARNING" in transcript
    assert "t <" in transcript.lower() or "technical" in transcript.lower() or "t 1" in transcript.lower()
    # The unverified-version errors are shown, as the §10.3 design
    # demands — generation stays blocked until a human probe records
    # evidence (plan §2.2).
    assert "unverified" in transcript.lower() or "blocked" in transcript.lower()


def test_wizard_blocked_input_reports_and_stays(tmp_path):
    script = []
    _new_named_project(script)
    # A bad family first: refused, stay on the step, re-asked.
    script.extend(["lipid", "", "", "", ""])
    script.append("q")
    script.append("")  # the discard prompt

    status, transcript = _drive(script)
    assert status == 0
    assert "lipid" in transcript  # echoed
    assert "unknown family" in transcript.lower()
    # After the refusal the family prompt appears again (§16.3) —
    # the registry label "Molecule" names the field.
    assert transcript.count("Molecule") >= 2


def test_wizard_factor_picker_adds_a_variant(tmp_path):
    script = []
    _new_named_project(script)
    _add_protein(script)
    _validate_clean(script)
    script.extend(["n"] * 8)  # molecules -> ... -> variants
    # The factor picker: key, factor, record (asked; sole polymer), value, label.
    script.extend(["nob", "sequence", "A", "AUUA", "no B chain"])
    script.extend(["n", str(tmp_path / "out"), "y"])  # review, generate, confirm

    status, transcript = _drive(script)
    assert status == 0, transcript
    # The variant file exists with the picker's key in its name
    # (naming agreement, §13.2), plus the manifest.
    written = sorted(str(p) for p in (tmp_path / "out").rglob("*.json"))
    assert any("nob" in p for p in written), written
    assert any("manifest" in p for p in written)


def test_wizard_backwards_navigation_never_blocked(tmp_path):
    script = []
    _new_named_project(script)
    _add_protein(script)
    script.extend(["p", "p", "p", "q", ""])  # back to job_details, quit

    status, transcript = _drive(script)
    assert status == 0
    # The header shows the step counter at earlier steps.
    assert "Step 2 of 14" in transcript


def test_wizard_quit_confirms_and_saves_unsaved_work(tmp_path):
    script = []
    _new_named_project(script)
    _add_protein(script)
    project_path = str(tmp_path / "keep.cbproj")
    script.extend(["q", "y", project_path])  # quit → save before quitting

    status, transcript = _drive(script)
    assert status == 0
    assert os.path.exists(project_path)


def test_wizard_help_lists_the_step_fields(tmp_path):
    script = []
    _new_named_project(script)
    script.extend(["?", "q", ""])

    status, transcript = _drive(script)
    assert status == 0
    # The help lists the visible fields by registry label.
    assert "Molecule" in transcript
    assert "Sequence" in transcript
    assert "Actions:" in transcript


def test_run_wizard_uses_the_probe_summary_and_plain_renderer(tmp_path):
    # A scripted console is not a TTY, so run_wizard's probe — reading
    # the console's own streams, not the host's — selects the guard.
    # That is the documented §16.7 decision chain, end to end.
    console = ScriptedConsole(["q", ""])
    with _pin_evidenced():
        status = run_wizard(build_services(), console=console, overrides={"plain": True})
    assert status == 3
    transcript = console.transcript
    # The probe logged its one-line summary with its reasons (§16.7):
    # both the override and the missing TTY are named.
    assert "renderer=non_interactive" in transcript
    assert "--plain" in transcript
    assert "TTY" in transcript or "no TTY" in transcript.lower()
    # The guard named what it would have asked, and nothing was started.
    assert "cannot ask" in transcript.lower()


def test_non_interactive_guard_exits_with_status_3(tmp_path):
    console = ScriptedConsole([])  # no input at all
    session = WizardSession(
        build_services(), console, _capabilities(renderer=RendererKind.NON_INTERACTIVE)
    )
    with _pin_evidenced():
        status = session.run()
    assert status == 3
    # The guard names what it would have asked, never prompts.
    assert "cannot ask" in console.transcript.lower()


def test_capabilities_matrix_end_to_end_decisions():
    # The documented matrix, exercised through the real probe: the
    # renderer choice changes presentation, never the workflow (§16.7).
    class FakeStream:
        def isatty(self):
            return False

    caps = probe_capabilities(stdin=FakeStream(), stdout=FakeStream())
    assert caps.renderer == RendererKind.NON_INTERACTIVE

    tty_in, tty_out = FakeStream(), FakeStream()
    tty_in.isatty = lambda: True
    tty_out.isatty = lambda: True
    caps = probe_capabilities(
        stdin=tty_in, stdout=tty_out, environ={"TERM": "dumb"}, optional_package=False
    )
    assert caps.renderer == RendererKind.PLAIN
    assert caps.color is False


def test_wizard_survives_eof_mid_step(tmp_path):
    # The script runs out at a prompt: the wizard says goodbye cleanly
    # instead of crashing or hanging (§16.0).
    script = []
    _new_named_project(script)
    script.append("protein")  # EOF hits during the sequence prompt

    status, transcript = _drive(script)
    assert status == 0
    assert "session ended" in transcript.lower()
