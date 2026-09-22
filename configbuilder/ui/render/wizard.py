"""The wizard session (IMPLEMENTATION_PLAN.md §16): the front end's
entry point that ties the pure step machine, the chosen renderer, the
journal, and the live services together.

The renderer is selected by the capability probe (§16.7) and
overridable; the view is rebuilt from the services after every applied
step, so navigation always reasons over current state (plan §16.1:
revisiting invalidates the cached report rather than keeping a stale
green state).
"""

from __future__ import annotations

from configbuilder.ui.render.capabilities import RendererKind
from configbuilder.ui.render.journal import NullJournal, SessionJournal
from configbuilder.ui.render.noninteractive import NonInteractiveRenderer
from configbuilder.ui.render.plain import PlainLineRenderer, RendererExit
from configbuilder.ui.steps import WizardMachine, WizardView

__all__ = ["WizardSession", "run_wizard"]


class WizardSession:
    """One wizard run: services + renderer + machine + journal."""

    def __init__(self, services, console, capabilities, journal=None) -> None:
        self.services = services
        self.console = console
        self.capabilities = capabilities
        self.journal = journal if journal is not None else NullJournal()
        self.machine = WizardMachine()
        self._cached_report = None  # invalidated by rebuilding the view

    # -- the view ---------------------------------------------------------------

    def view(self) -> WizardView:
        """The read-only projection of the live project (plan §16.2),
        rebuilt every cycle."""
        projects = self.services.projects
        project = projects.project
        if project is None:
            return WizardView()
        configuration = project.configuration
        records = []
        has_external = False
        needs_definition = False
        for record in configuration.records:
            family = _family_of(record)
            primary = record.ids.primary.value
            sequence = getattr(record, "sequence", None)
            records.append(
                _Row(
                    family,
                    primary,
                    sequence.text if sequence is not None else "",
                )
            )
            if _has_external_source(record):
                has_external = True
        # A ligand whose codes need a definition and none exists yet
        # promotes the definition prompt into the main flow (§16.4).
        if configuration.component_definition is None and any(
            _uses_codes(record) for record in configuration.records
        ):
            needs_definition = True
        variants = []
        try:
            expansion = self.services.variants.expand()
            if expansion.ok:
                variants = [variant.key for variant in expansion.variants]
        except Exception:
            variants = []
        # Conflicts come from the last plan when one exists (the generate
        # step reports them); otherwise the view is conflict-free.
        conflicts = ()
        return WizardView(
            has_project=True,
            project_name=configuration.metadata.name,
            records=tuple(records),
            has_external=has_external,
            needs_definition=needs_definition,
            seeds=tuple(configuration.seeds.values),
            report=self._cached_report,
            variants=tuple(variants),
            conflicts=conflicts,
        )

    def remember_report(self, report) -> None:
        """Cache the latest report between explicit validations."""
        self._cached_report = report

    # -- the run loop ---------------------------------------------------------------

    def run(self) -> int:
        """Drive the session; returns the process exit status."""
        renderer = self._renderer()
        # The probe's result and reason are logged (plan §16.7) —
        # always, whatever the renderer, so "it printed strange
        # characters" is diagnosable from the transcript alone.
        self.console.write_line(self.capabilities.summary())
        # The resume offer (plan §16.8): one line, one question.
        offer = self.journal.resume_offer(self.services.projects)
        if offer and isinstance(renderer, PlainLineRenderer):
            self.console.write_line(offer)
            from configbuilder.ui.present.strings import text as _text

            answer = self.console.prompt(_text("journal.offer_prompt")).strip().lower()
            if answer == "y":
                entry = self.journal.read()
                if entry and entry.get("step"):
                    self.machine.goto_name(entry["step"], self.view())
            self.journal.clear()
        try:
            renderer.run(self.machine, self.view, journal=self.journal)
        except RendererExit as exit_signal:
            return exit_signal.status
        except EOFError:
            # A closed stream anywhere (a prompt, a confirm) is a clean
            # goodbye, never a traceback (plan §16.0). The session owns
            # the goodbye so every EOF path says it exactly once.
            from configbuilder.ui.present.strings import text as _text

            self.console.write_line(_text("plain.farewell"))
            return 0
        return 0

    def _renderer(self):
        kind = self.capabilities.renderer
        if kind == RendererKind.NON_INTERACTIVE:
            return NonInteractiveRenderer(self.console)
        if kind == RendererKind.FULL_SCREEN:
            # The probe selected full screen (capable TTY + importable
            # package + no override, §16.7); if the package vanished
            # since the probe, degrade to plain — never crash.
            from configbuilder.ui.render import fullscreen

            if fullscreen.available():
                return fullscreen.FullScreenRenderer(
                    self.console,
                    self.services,
                    glyph_set=self.capabilities.glyphs,
                    width=self.capabilities.width,
                    report_sink=self.remember_report,
                )
        return PlainLineRenderer(
            self.console,
            self.services,
            glyph_set=self.capabilities.glyphs,
            width=self.capabilities.width,
            report_sink=self.remember_report,
        )


class _Row:
    """The view's record row (family, primary identifier, sequence)."""

    __slots__ = ("family", "entity", "sequence")

    def __init__(self, family, entity, sequence) -> None:
        self.family = family
        self.entity = entity
        self.sequence = sequence


def _family_of(record) -> str:
    """The record's family from its traceability-registered type name —
    the same vocabulary the registry and the steps share."""
    from configbuilder.model.traceability import mapping_ids_for

    type_name = type(record).__name__
    try:
        mapping_ids_for(type_name)
    except Exception:
        return "record"
    return _FAMILY_BY_TYPE.get(type_name, "record")


_FAMILY_BY_TYPE = {
    "FamilyARecord": "protein",
    "FamilyBRecord": "rna",
    "FamilyCRecord": "dna",
    "ComponentRecord": "ligand",
}


def _uses_codes(record) -> bool:
    """True when a component record's representation is component codes
    (which may need a custom chemistry definition)."""
    representation = getattr(record, "representation", None)
    return representation is not None and type(representation).__name__ == "ByCode"


def _has_external_source(record) -> bool:
    """True when the record references an external file (alignment or
    structural reference) — by type name, per the registry vocabulary."""
    alignment = getattr(record, "alignment", None)
    if alignment is not None and _carries_external(alignment):
        return True
    references = getattr(record, "references", None)
    if references is not None and type(references).__name__ == "Explicit":
        for reference in getattr(references, "records", ()):
            if _carries_external(reference):
                return True
    return False


def _carries_external(container) -> bool:
    for attribute in ("source", "unpaired", "paired"):
        value = getattr(container, attribute, None)
        if value is not None and type(value).__name__ == "External":
            return True
    return False


def run_wizard(services, console=None, overrides=None, journal=None) -> int:
    """Probe, wire, run: the one-call front end.

    ``overrides`` carries ``plain``/``ascii``/``no_color`` (plan §16.9).
    The probe consults the **console's** streams — so a scripted or
    redirected console gets the guard, exactly as a real terminal gets
    the plain or full-screen renderer.
    """
    from configbuilder.ui.render.capabilities import probe_capabilities
    from configbuilder.ui.render.console import Console

    console = console if console is not None else Console()
    capabilities = probe_capabilities(
        stdin=console.stdin,
        stdout=console.stdout,
        overrides=overrides,
        # A scripted console has no real terminal to VT-process; the
        # probe must not poke the host's console on its behalf.
        vt_enabled=False if hasattr(console, "_chunks") else None,
    )
    if journal is None:
        journal = SessionJournal()
    session = WizardSession(services, console, capabilities, journal)
    return session.run()
