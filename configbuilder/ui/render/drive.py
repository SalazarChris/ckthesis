"""The shared step-workflow driver (IMPLEMENTATION_PLAN.md §16.2, §16.3).

``StepDrive`` holds the *entire* wizard workflow — the main loop, the
question-and-answer discipline, findings presentation, validation,
saving, the advanced screen, and the generate step — exactly once. The
plan's §16.7 exit criterion ("same transcript; no behavioural
difference") is met structurally: the plain and full-screen renderers
are thin adapters over this drive, differing **only** in the two
primitives ``write_line`` and ``ask``. Neither renderer can drift into
a second-class path, because there is no second workflow to drift from
(plan §16.7: "the same workflow with simpler drawing").

The drive talks to no terminal itself: it composes question text and
delegates to the primitives. ``write_line(text)`` emits one output
line; ``ask(prompt_text, field=None)`` asks one question and returns
one answer line (``field``, when given, is the ``FieldSpec`` for
input conveniences such as completion — presentation only).
EOF surfaces as ``EOFError`` from ``ask``; the session converts it
into the clean goodbye (plan §16.0).
"""

from __future__ import annotations

from configbuilder.ui.present import format_findings
from configbuilder.ui.present.strings import text as _text

__all__ = ["StepDrive"]


class StepDrive:
    """The one workflow, driven through two primitives."""

    def __init__(self, services, width=None, report_sink=None, glyph_set="unicode") -> None:
        self.services = services
        self.width = width if width is not None else 80
        self.glyph_set = glyph_set
        # Where the latest report goes so the session's view (and the
        # steps' entry conditions) see the validation state — the same
        # report the user saw (plan §16.2).
        self._report_sink = report_sink

    # -- the two primitives (the only thing renderers implement) ------------

    def write_line(self, text: str = "") -> None:
        """Emit one line of output."""
        raise NotImplementedError

    def ask(self, prompt_text: str, field=None) -> str:
        """Ask one question; return one answer line. Raises ``EOFError``
        on a closed stream (the session says goodbye, plan §16.0)."""
        raise NotImplementedError

    def remember_report(self, report) -> None:
        if self._report_sink is not None:
            self._report_sink(report)

    # -- framing (§16.3) ------------------------------------------------------

    def header(self, machine, view) -> None:
        """``Step 4 of 14 — title — project — unsaved`` (plan §16.3)."""
        parts = ["Step %d of %d" % (machine.position, machine.count), machine.current.title]
        if view.has_project:
            parts.append(view.project_name)
            if self.services.projects.is_dirty:
                parts.append(_text("plain.unsaved_marker"))
        self.write_line(_text("plain.header_separator") + _text("plain.header_join").join(parts))

    def hint_line(self) -> None:
        """The persistent one-line grammar hint; stated once, never
        varies by step (plan §16.3)."""
        self.write_line(_text("plain.hint"))

    # -- findings (§16.6) ------------------------------------------------------

    def show_findings(self, view) -> None:
        """The findings list: numbered cards, severity word + symbol,
        technical detail available on request (plan §16.6)."""
        if view.report is None:
            return
        cards = format_findings(view.report.findings, self.width)
        if not cards:
            self.write_line(_text("plain.no_findings"))
            return
        for card in cards:
            self.write_line("%d. %s — %s" % (card.number, card.severity_line, card.context))
            for line in card.lines:
                self.write_line(_text("plain.detail_indent") + line)
        self.write_line(_text("plain.jump_hint"))

    def show_technical_detail(self, cards, number_text: str) -> None:
        for card in cards:
            if card.number == number_text:
                for line in card.detail:
                    self.write_line(_text("plain.detail_indent") + line)
                return
        self.write_line(_text("plain.no_such_finding") % number_text)

    # -- prompting (§16.3) -------------------------------------------------------

    def ask_field(self, field, view):
        """One field prompt with its default inline (plan §16.3). The
        composed text is identical in every renderer."""
        label = field.prompt_label
        default = ""
        if field.default is not None and field.default != "":
            default = _text("plain.default_suffix") % field.default
        suffix = "" if field.required else _text("field.optional_suffix")
        return self.ask(_text("plain.prompt_join") % (label, default, suffix), field=field)

    def run_step_fields(self, step, view):
        """Collect answers for the step's visible fields."""
        answers = {}
        for field in step.fields(view):
            raw = self.ask_field(field, view)
            if raw == "" and field.default is not None:
                answers[field.key] = field.default
            else:
                answers[field.key] = raw
        return answers

    # -- the main loop ------------------------------------------------------------

    def run(self, machine, view_provider, journal=None):
        """Drive the wizard until the user quits or generates.

        ``view_provider()`` supplies the fresh ``WizardView`` each cycle
        (the caller rebuilds it after performing service calls);
        ``journal`` receives a record per completed step (plan §16.8).
        """
        while True:
            view = view_provider()
            step = machine.current
            self.header(machine, view)
            self.hint_line()

            if step.id.name == "validate":
                self.show_findings(view)
            if step.id.name == "generate":
                return self._finish(machine, view)

            answer = self._prompt_or_quit()

            if answer in ("q", "Q"):
                if self._confirm_discard():
                    if journal is not None:
                        journal.record(step.id.name, self.services.projects)
                    raise _renderer_exit(0)
                continue
            if answer in ("s", "S"):
                self._save()
                continue
            if answer in ("n", "N"):
                self._advance(machine, view, journal)
                continue
            if answer in ("p", "P"):
                machine.previous(view)
                continue
            if answer == "v":
                self._validate(view)
                continue
            if answer in ("a", "A"):
                self._advanced()
                continue
            if answer == "?":
                self._help(step, view)
                continue
            if answer.startswith(_text("plain.technical_prefix")):
                self.show_technical_detail(
                    format_findings(view.report.findings, self.width) if view.report else (),
                    answer[2:].strip(),
                )
                continue
            # Otherwise: accept the step's fields starting with this
            # answer for the first field, then keep the loop going —
            # _collect_and_apply advances the machine on a *fresh* view.
            self._collect_and_apply(machine, view_provider, journal, first_answer=answer)

    def _advance(self, machine, view, journal) -> None:
        step = machine.current
        if journal is not None:
            journal.record(step.id.name, self.services.projects)
        if machine.next(view) is None:
            self.write_line(_text("plain.no_further_step"))

    def _collect_and_apply(self, machine, view_provider, journal, first_answer=None) -> None:
        from configbuilder.ui.steps import apply_answer

        step = machine.current
        view = view_provider()
        fields = step.fields(view)
        answers = {}
        for index, field in enumerate(fields):
            raw = first_answer if (index == 0 and first_answer) else self.ask_field(field, view)
            if raw == "" and field.default is not None:
                answers[field.key] = field.default
            else:
                answers[field.key] = raw
        try:
            calls = apply_answer(step.id.name, answers, view)
        except Exception as error:  # a step refused the answers
            self.write_line(_text("plain.could_not_apply") % error)
            return
        ok = True
        for call in calls:
            ok = self._perform(call) and ok
        if ok:
            if journal is not None:
                journal.record(step.id.name, self.services.projects)
            # Advance on a fresh view: the answers just applied may have
            # opened the next step (a record added opens modifications).
            # A refused answer keeps the user on this step (§16.3:
            # the wizard repeats until the entry is valid).
            machine.next(view_provider())

    def _prompt_or_quit(self) -> str:
        """One main-loop prompt; EOF (Ctrl-D / closed pipe) is a clean
        goodbye — the session turns the EOFError into the farewell, so
        no traceback and no hang (plan §16.0)."""
        try:
            return self.ask(_text("plain.entry_prompt")).strip()
        except EOFError:
            raise _renderer_exit(0)

    def _perform(self, call) -> bool:
        """Perform one ``ServiceCall`` on the services; problems come
        back as messages, never exceptions (plan §15, §16)."""
        service = getattr(self.services, call.service, None)
        if service is None:
            self.write_line(_text("plain.unknown_service") % call.service)
            return False
        operation = getattr(service, call.operation, None)
        if operation is None or not callable(operation) or call.operation.startswith("_"):
            self.write_line(_text("plain.unknown_operation") % call.operation)
            return False
        try:
            result = operation(**call.args)
        except Exception as error:
            self.write_line(str(error))
            return False
        ok = bool(getattr(result, "ok", True))
        message = getattr(result, "message", "")
        if message:
            self.write_line(message)
        if not ok:
            reason = getattr(result, "failure_reason", "")
            self.write_line(_text("plain.not_applied") % (reason or "refused"))
        return ok

    def _validate(self, view) -> None:
        result = self.services.validation.validate_base()
        if result.ok:
            self.write_line(_text("plain.validate_clean"))
        self.remember_report(result.report)
        self.show_findings(_view_with_report(view, result.report))

    def _save(self) -> None:
        result = self.services.projects.save() if self.services.projects.path else None
        if result is None:
            path = self.ask(_text("plain.save_as_prompt")).strip()
            result = self.services.projects.save_as(path)
        if result.ok:
            # Report where the project went (§16.6's discipline, applied
            # to the project file too).
            self.write_line(_text("plain.saved_to") % self.services.projects.path)
        else:
            self.write_line(result.message)

    def _advanced(self) -> None:
        """The 'a advanced' action: the format-target pin (plan §16.4:
        the advanced settings screen offers the version selection and
        dialect). The evidence citation is operator-supplied — the runtime
        never reads any provenance document — and the wizard reports the
        validation result either way."""
        answer = self.ask(_text("plain.advanced_version_prompt")).strip()
        if not answer:
            return
        result = self.services.configuration.set_format_target(version=answer)
        self.write_line(
            _text("plain.saved")
            if result.ok
            else _text("plain.not_applied") % (result.message or "refused")
        )

    def _confirm_discard(self) -> bool:
        if not self.services.projects.is_dirty:
            return True
        answer = self.ask(_text("plain.quit_prompt")).strip().lower()
        if answer == "y":
            self._save()
        return True

    def _help(self, step, view) -> None:
        self.write_line(_text("plain.fields_header"))
        for field in step.fields(view):
            optional = "" if field.required else _text("field.optional_suffix")
            self.write_line("  %s%s" % (field.prompt_label, optional))
        self.write_line(_text("plain.actions_hint"))

    def _finish(self, machine, view) -> None:
        """The generate step: plan, show the reviewed layout, execute on
        confirmation, and report where the files went (plan §16.6)."""
        root = self.ask(_text("plain.output_prompt")).strip()
        plan = self.services.generation.plan(root)
        if not plan.ok:
            self.write_line(_text("plain.cannot_generate") % plan.message)
            for conflict in plan.conflicts:
                self.write_line(_text("plain.conflict") % conflict)
            return
        for entry in plan.entries:
            self.write_line(_text("plain.list_indent") % (entry.action, entry.path))
        if plan.warnings:
            for warning in plan.warnings:
                self.write_line(_text("plain.warning") % warning)
        confirm = self.ask(_text("plain.write_prompt")).strip().lower()
        if confirm != "y":
            self.write_line(_text("plain.nothing_written"))
            return
        result = self.services.generation.execute(plan)
        if result.ok:
            for path in result.written:
                self.write_line(_text("plain.wrote") % path)
            self.write_line(_text("plain.manifest_where") % plan.output_root)
        else:
            for error in result.errors:
                self.write_line(_text("plain.error") % error)


def _renderer_exit(status: int):
    """The exit exception, resolved lazily to keep the module import
    graph acyclic (plain defines it; both renderers share it)."""
    from configbuilder.ui.render.plain import RendererExit

    return RendererExit(status)


def _view_with_report(view, report):
    from configbuilder.ui.steps.view import WizardView

    return WizardView(
        has_project=view.has_project,
        project_name=view.project_name,
        records=view.records,
        has_external=view.has_external,
        needs_definition=view.needs_definition,
        seeds=view.seeds,
        report=report,
        variants=view.variants,
        conflicts=view.conflicts,
    )
