"""The step machine (plan §16.2): steps are values, navigation is pure.

A step is a named state with an explicit entry condition, the fields
this state asks for, and the actions it offers. ``apply`` turns an
answer into the service calls the *caller* performs — the machine
itself invokes nothing, touches no terminal, and reads nothing from
the environment (plan §5.3 rule 9). This is what makes the navigation
model unit-testable without a terminal and lets the same steps drive
three different renderers.
"""

from __future__ import annotations

from configbuilder.ui.present.labels import action_description, label
from configbuilder.ui.steps.view import WizardView

__all__ = [
    "StepId",
    "FieldSpec",
    "Action",
    "ServiceCall",
    "Step",
    "WizardMachine",
]


class StepId:
    """The fourteen steps in plan §16.1 order. A value class, not an
    enum, so steps can be data without import-order coupling."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, StepId) and self.name == other.name

    def __hash__(self) -> int:
        return hash(("StepId", self.name))

    def __repr__(self) -> str:
        return "StepId(%r)" % self.name


STEP_ORDER = (
    "start",
    "job_details",
    "molecules",
    "modifications",
    "components",
    "custom_chemistry",
    "links",
    "alignments",
    "files_paths",
    "reproducibility",
    "validate",
    "variants",
    "review",
    "generate",
)

STEP_IDS = tuple(StepId(name) for name in STEP_ORDER)


class FieldSpec:
    """One prompt a step shows: a stable key, the type whose registry
    label names it, whether it is required, and an optional default."""

    __slots__ = ("key", "type_name", "required", "default", "help_key")

    def __init__(self, key: str, type_name: str, required: bool = False, default=None, help_key: str = "") -> None:
        self.key = key
        self.type_name = type_name
        self.required = bool(required)
        self.default = default
        self.help_key = help_key

    @property
    def prompt_label(self) -> str:
        """The prompt's wording, from the registry (plan §3.1)."""
        return label(self.type_name)

    def __repr__(self) -> str:
        return "FieldSpec(%r, %r, required=%r)" % (self.key, self.type_name, self.required)


class Action:
    """Something the user may do from a step: a key (``n``, ``e``,
    ``d``, ``v``, ``a``, ``s``, ``q``) with registry-vocabulary wording."""

    __slots__ = ("key", "type_name", "description_key")

    def __init__(self, key: str, type_name: str, description_key: str = "") -> None:
        self.key = key
        self.type_name = type_name
        self.description_key = description_key

    @property
    def description(self) -> str:
        """The action's wording, from the wizard string registry."""
        return action_description(self.description_key)

    def __repr__(self) -> str:
        return "Action(%r, %r)" % (self.key, self.type_name)


class ServiceCall:
    """One call the *caller* should perform on the app services, as
    plain data: service name, operation, arguments. The machine never
    invokes anything itself (plan §16.2)."""

    __slots__ = ("service", "operation", "args")

    def __init__(self, service: str, operation: str, **args) -> None:
        self.service = service
        self.operation = operation
        self.args = dict(args)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ServiceCall)
            and self.service == other.service
            and self.operation == other.operation
            and self.args == other.args
        )

    def __repr__(self) -> str:
        return "ServiceCall(%r, %r, **%r)" % (self.service, self.operation, self.args)


class Step:
    """One named state: entry condition, visible fields, actions."""

    __slots__ = ("id", "title_type", "entry_condition", "fields_fn", "actions_fn")

    def __init__(self, id: StepId, title_type: str, entry_condition, fields_fn, actions_fn) -> None:
        self.id = id
        self.title_type = title_type  # a traceability-registered type name
        self.entry_condition = entry_condition
        self.fields_fn = fields_fn
        self.actions_fn = actions_fn

    @property
    def title(self) -> str:
        """The step's wording, from the registry (plan §16.2:
        ``title_key`` resolved through the traceability registry)."""
        return label(self.title_type)

    def fields(self, view: WizardView) -> tuple:
        """Only the fields this state should ask for (per-family
        visibility is a function of the view, plan §16.2)."""
        return tuple(self.fields_fn(view))

    def actions(self, view: WizardView) -> tuple:
        return tuple(self.actions_fn(view))

    def __repr__(self) -> str:
        return "Step(%r)" % self.id.name


class WizardMachine:
    """The navigation model over the fourteen steps: current position,
    entry-condition gating, forward/backward movement, and jump
    resolution. Pure — no terminal, no services, no environment."""

    def __init__(self, steps=None) -> None:
        self._steps = tuple(steps) if steps is not None else _default_steps()
        self._current_index = 0
        self._completed = set()  # type: set

    # -- position ------------------------------------------------------------

    @property
    def current(self) -> Step:
        return self._steps[self._current_index]

    @property
    def position(self) -> int:
        """1-based position for the ``Step 4 of 14`` header."""
        return self._current_index + 1

    @property
    def count(self) -> int:
        return len(self._steps)

    @property
    def completed(self) -> tuple:
        """Ids of steps whose entry conditions have held this session."""
        return tuple(step.id for step in self._steps if step.id.name in self._completed)

    # -- movement ------------------------------------------------------------

    def can_enter(self, step_id: StepId, view: WizardView) -> bool:
        """A step is enterable when its entry condition holds on the
        view (plan §16.1: explicit entry conditions)."""
        step = self._by_id(step_id)
        return step is not None and bool(step.entry_condition(view))

    def next(self, view: WizardView):
        """Move forward to the next step whose entry condition holds;
        ``None`` when none does (the caller stays put)."""
        for index in range(self._current_index + 1, len(self._steps)):
            if self._steps[index].entry_condition(view):
                self._current_index = index
                self._completed.add(self._steps[index].id.name)
                return self._steps[index]
        return None

    def previous(self, view: WizardView):
        """Move backward — never blocked (plan §16.1: the wizard never
        blocks backward navigation)."""
        if self._current_index == 0:
            return None
        self._current_index -= 1
        self._completed.add(self._steps[self._current_index].id.name)
        return self.current

    def goto(self, step_id: StepId, view: WizardView) -> bool:
        """Jump to a step if its entry condition holds; revisiting a
        step re-evaluates it on the fresh view so a stale green state
        is never kept (plan §16.1)."""
        step = self._by_id(step_id)
        if step is None or not step.entry_condition(view):
            return False
        self._current_index = self._steps.index(step)
        self._completed.add(step.id.name)
        return True

    def goto_name(self, name: str, view: WizardView) -> bool:
        """``goto`` by step name (the journal records names, plan §16.8)."""
        return self.goto(StepId(name), view)

    def steps_reachable(self, view: WizardView) -> tuple:
        """Which steps are enterable right now (test seam for the
        reachability tier)."""
        return tuple(step.id for step in self._steps if step.entry_condition(view))

    # -- private -----------------------------------------------------------------

    def _by_id(self, step_id: StepId):
        for step in self._steps:
            if step.id == step_id:
                return step
        return None


def _default_steps():
    """The fourteen steps from ``registry.py`` (imported here so the
    step table itself stays data-only and hot-swappable in tests)."""
    from configbuilder.ui.steps.registry import build_steps

    return build_steps()
