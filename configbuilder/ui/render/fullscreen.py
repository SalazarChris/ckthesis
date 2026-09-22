"""The full-screen renderer (IMPLEMENTATION_PLAN.md §16.7, Phase 11c).

An enhancement that appears only when its optional dependency
(``prompt_toolkit``) happens to be importable. It is an adapter, not a
second workflow: the entire question-and-answer discipline lives in
``drive.StepDrive``, so this renderer asks **exactly the same
questions** and performs exactly the same service calls as the plain
renderer — the plan's exit criterion ("same transcript; no
behavioural difference") holds by construction, not by discipline.

What the extra dependency buys (convenience only, §16.7): a persistent
header, typed input with history, **path completion** on the fields
that ask for a path, and an **internal pager** for the read-only
inspector (technical finding detail and long listings scroll instead
of spilling). Nothing here changes what is asked, in what order, or
what is done with the answers.

The import is lazy and ``available()`` is the single decision point —
the module imports cleanly without the package, and the capability
probe selects this renderer only when ``available()`` is true, the
streams are a capable interactive TTY, and no override says otherwise
(probe rules live in ``capabilities.py``, not here).
"""

from __future__ import annotations

__all__ = ["FullScreenRenderer", "available", "import_error"]

_IMPORT_ERROR = None


def import_error():
    """Why ``prompt_toolkit`` is unusable, or ``None`` — resolved once
    per process (the package is optional; the probe asks, never assumes)."""
    global _IMPORT_ERROR
    if _IMPORT_ERROR is None:
        try:
            import prompt_toolkit  # noqa: F401

        except Exception as error:  # any import failure: absent or broken
            _IMPORT_ERROR = error
    return _IMPORT_ERROR


def available() -> bool:
    return import_error() is None


# The fields whose answers are filesystem paths — the only ones that
# get completion (§16.7 lists path completion; completion on non-path
# fields would suggest rather than ask, which the wizard never does).
_PATH_FIELD_KEYS = frozenset({"path", "external_path", "a_path", "file_path"})


class _DriveConsole:
    """prompt_toolkit's input/output adapter, spoken to by the drive.

    ``ask`` runs a ``PromptSession`` prompt (history, editing) and adds
    path completion **only** when the drive says the field is a path.
    Output goes through the session's output so escape sequences and
    line drawing agree with whatever console the package detected.
    """

    def __init__(self, title: str = "configbuilder") -> None:
        self.title = title
        self._session = None
        self._completer = None
        # The completer is an inert object — building it needs no
        # terminal, unlike the session (which opens input state), so
        # only the session stays lazy.
        try:
            from prompt_toolkit.completion import PathCompleter

            self._completer = PathCompleter(only_directories=False, expanduser=True)
        except Exception:
            self._completer = None  # no package: completion is simply off

    def _ensure_session(self):
        if self._session is None:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import InMemoryHistory

            self._session = PromptSession(history=InMemoryHistory())
        return self._session

    def _completer_for(self, field):
        if field is not None and getattr(field, "key", None) in _PATH_FIELD_KEYS:
            return self._completer
        return None

    def ask(self, prompt_text: str, field=None) -> str:
        session = self._ensure_session()
        return session.prompt(prompt_text, completer=self._completer_for(field))

    def read_multiline(self, instructions: str, terminator: str = "") -> bytes:
        """The paste route's primitive (§16.5), rendered full screen:
        a multiline prompt; the blank-line terminator still finishes."""
        from prompt_toolkit import prompt as pt_prompt

        lines = []
        print(instructions)
        while True:
            try:
                line = pt_prompt()
            except EOFError:
                break
            if line.rstrip("\r\n") == terminator:
                break
            lines.append(line)
        return "".join(line + "\n" for line in lines).encode("utf-8")

    # -- the Console surface (write side) -------------------------------

    def write_line(self, text: str = "") -> None:
        print(text)

    def prompt(self, text: str) -> str:
        return self.ask(text)


class FullScreenRenderer:
    """The StepDrive adapter: two primitives over prompt_toolkit.

    The class is deliberately **not** a subclass of ``StepDrive`` at
    the type level — it *has* a drive and forwards, so the renderer's
    own code is exactly what the package adds: the pager and nothing
    else. All workflow questions come from the drive.
    """

    def __init__(self, console, services, glyph_set: str = "unicode", width: int = None, report_sink=None) -> None:
        from configbuilder.ui.render.drive import StepDrive

        if not available():
            from configbuilder.ui.present.strings import text as _text

            raise RuntimeError(_text("guard.fullscreen_missing"))
        self.console = console if console is not None else _DriveConsole()
        self.drive = _ForwardingDrive(self, services, width=width, report_sink=report_sink, glyph_set=glyph_set)

    # -- the two primitives ------------------------------------------------

    def write_line(self, text: str = "") -> None:
        self.console.write_line(text)

    def ask(self, prompt_text: str, field=None) -> str:
        return self.console.ask(prompt_text, field=field)

    # -- the full-screen extra: the internal pager (§16.7) -------------------

    def page(self, title: str, lines) -> None:
        """The read-only inspector: technical finding detail and long
        listings through an internal pager (never a shell-out; §16.7).
        Falls back to plain emission when the terminal cannot page."""
        try:
            from prompt_toolkit.shortcuts import pager

            body = "\n".join(lines)
            pager(body, title=self._page_title(title))
            return
        except Exception:
            # No usable paging surface: emit linearly — content is
            # never cut (the plain renderer's guarantee holds).
            self.write_line(self._page_title(title))
            for line in lines:
                self.write_line(line)

    def _page_title(self, title: str) -> str:
        if self.drive.glyph_set == "ascii":
            return "%s - %s" % (self.console.title, title)
        return "%s — %s" % (self.console.title, title)

    # -- the drive delegations the session calls ------------------------------

    def run(self, machine, view_provider, journal=None):
        return self.drive.run(machine, view_provider, journal=journal)

    def remember_report(self, report) -> None:
        self.drive.remember_report(report)


class _ForwardingDrive:
    """The drive whose ``write_line``/``ask`` render full screen.

    It subclasses ``StepDrive`` so the *workflow* is the one shared
    implementation, and overrides technical-detail presentation to use
    the pager — the one place §16.7's "internal pager for the
    read-only inspector" attaches, without changing any question.
    """

    def __init__(self, renderer, services, width=None, report_sink=None, glyph_set="unicode") -> None:
        from configbuilder.ui.render.drive import StepDrive

        self._renderer = renderer
        self._drive = StepDrive(
            services, width=width, report_sink=report_sink, glyph_set=glyph_set
        )
        self._drive.write_line = renderer.write_line
        self._drive.ask = renderer.ask

    def __getattr__(self, name):
        return getattr(self._drive, name)

    def show_technical_detail(self, cards, number_text: str) -> None:
        """Same content as plain, paged (§16.7: internal pager for the
        read-only inspector). Unknown numbers still say so — identical
        answers, better presentation."""
        from configbuilder.ui.present.strings import text as _text

        for card in cards:
            if card.number == number_text:
                lines = [card.severity_line, card.context, ""]
                lines.extend(card.detail)
                self._renderer.page(_text("plain.technical_title") % card.number, lines)
                return
        self._renderer.write_line(_text("plain.no_such_finding") % number_text)
