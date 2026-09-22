"""The non-interactive renderer (IMPLEMENTATION_PLAN.md §16.7).

``stdin`` is not a TTY: the renderer **never prompts**. It reports
precisely which inputs would have been required and exits with a
distinct status code. This is a guard against hanging — **not** a batch
authoring front end; it does not author configurations from a
parameter file, and none is defined in this plan (§22, Q14).
"""

from __future__ import annotations

from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.plain import RendererExit

__all__ = ["NonInteractiveRenderer", "EXIT_MISSING_INPUTS"]


# The distinct status the guard exits with (plan §16.7).
EXIT_MISSING_INPUTS = 3


class NonInteractiveRenderer:
    """Names what the workflow would have asked, then exits."""

    def __init__(self, console) -> None:
        self.console = console

    def run(self, machine, view_provider, journal=None) -> None:
        view = view_provider()
        self.console.write_line(_text("guard.header"))
        missing = self._missing(machine, view)
        if missing:
            self.console.write_line(_text("guard.missing_header"))
            for line in missing:
                self.console.write_line(_text("guard.list_item") % line)
        else:
            self.console.write_line(_text("guard.missing_none") % machine.current.id.name)
        self.console.write_line(_text("guard.footer"))
        raise RendererExit(EXIT_MISSING_INPUTS)

    def _missing(self, machine, view):
        """The prompts the current state would raise, named by their
        registry labels through the pure step machine."""
        lines = []
        step = machine.current
        for field in step.fields(view):
            lines.append(
                "%s: %s%s" % (
                    step.title,
                    field.prompt_label,
                    "" if field.required else _text("field.optional_suffix"),
                )
            )
        if not lines:
            lines.append("%s: confirm to continue" % step.title)
        return lines
