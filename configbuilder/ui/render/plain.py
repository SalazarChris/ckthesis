"""The plain-line renderer (IMPLEMENTATION_PLAN.md §16.7).

The baseline and the guaranteed path: sequential question-and-answer
with no cursor addressing and no escape sequences beyond newlines,
written against the standard library only. It is feature-complete by
requirement, not by courtesy — and it is feature-complete *by
construction*: the entire workflow lives in ``drive.StepDrive`` and
this class supplies only the two primitives (``write_line`` and
``ask``), so the full-screen renderer cannot drift into a second-class
path (plan §16.7: "the same workflow with simpler drawing").
"""

from __future__ import annotations

from configbuilder.ui.render.drive import StepDrive
from configbuilder.ui.render.platform import terminal_size

__all__ = ["PlainLineRenderer", "RendererExit"]


class RendererExit(Exception):
    """Raised (not printed) when the user quits or the session cannot
    continue; carries the exit status convention of §16.7."""

    def __init__(self, status: int, message: str = "") -> None:
        super().__init__(message or ("exit %d" % status))
        self.status = int(status)


class PlainLineRenderer(StepDrive):
    """Drives the wizard through a ``Console``. Linear output only."""

    def __init__(self, console, services, glyph_set: str = "unicode", width: int = None, report_sink=None) -> None:
        super().__init__(services, width=width, report_sink=report_sink, glyph_set=glyph_set)
        self.console = console
        if width is None:
            self.width = terminal_size()[0]

    def write_line(self, text: str = "") -> None:
        self.console.write_line(text)

    def ask(self, prompt_text: str, field=None) -> str:
        return self.console.prompt(prompt_text)
