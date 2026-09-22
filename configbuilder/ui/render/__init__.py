"""Terminal rendering (plan §5.1, §5.3 rule 9, §16.7).

The only ``ui`` family that may read or write a stream, consult the
environment, or branch on the host platform (and platform branching is
confined to ``platform.py``). Three renderers drive the one pure step
machine: the stdlib-only plain-line renderer (the guaranteed path),
the non-interactive hang guard, and the optional prompt_toolkit
full-screen renderer (import lazily; the package stays optional).
"""

from configbuilder.ui.render.capabilities import (
    Capabilities,
    GlyphSet,
    RendererKind,
    probe_capabilities,
)
from configbuilder.ui.render.console import Console, ScriptedConsole, make_console
from configbuilder.ui.render.journal import NullJournal, SessionJournal
from configbuilder.ui.render.noninteractive import EXIT_MISSING_INPUTS, NonInteractiveRenderer
from configbuilder.ui.render.plain import PlainLineRenderer, RendererExit
from configbuilder.ui.render.platform import (
    IS_WINDOWS,
    console_encoding,
    editor_candidates,
    state_directory,
    terminal_size,
)
from configbuilder.ui.render.wizard import WizardSession, run_wizard

__all__ = [
    "EXIT_MISSING_INPUTS",
    "Capabilities",
    "Console",
    "FullScreenRenderer",
    "GlyphSet",
    "IS_WINDOWS",
    "NonInteractiveRenderer",
    "NullJournal",
    "PlainLineRenderer",
    "RendererExit",
    "RendererKind",
    "ScriptedConsole",
    "SessionJournal",
    "WizardSession",
    "console_encoding",
    "editor_candidates",
    "make_console",
    "probe_capabilities",
    "run_wizard",
    "state_directory",
    "terminal_size",
]


def __getattr__(name):
    # The full-screen renderer is imported lazily so the guaranteed
    # path never needs the optional package to import this namespace.
    if name == "FullScreenRenderer":
        from configbuilder.ui.render.fullscreen import FullScreenRenderer

        return FullScreenRenderer
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
