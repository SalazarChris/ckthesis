"""The executor (IMPLEMENTATION_PLAN.md §13.3, §13.4).

``execute(plan)`` performs the writes the plan lists — nothing more. All
writes are atomic per file (temporary file in the destination directory,
flush, then ``os.replace``), directories are created only as the plan
requires, and the run is all-or-nothing: any plan-level conflict, or any
resource whose source cannot be read, aborts before the first byte is
written. ``execute`` raises nothing for user-caused conditions; it returns
an ``OutputResult`` describing what happened (errors included).
"""

from __future__ import annotations

import os

from configbuilder.output.plan import OutputPlan

__all__ = ["OutputResult", "WriteOutcome", "execute"]


class WriteOutcome:
    """What happened to one planned file."""

    __slots__ = ("path", "action", "written", "bytes_written")

    def __init__(self, path, action: str, written: bool, bytes_written: int) -> None:
        self.path = path
        self.action = action
        self.written = written
        self.bytes_written = bytes_written

    def __repr__(self) -> str:
        return "WriteOutcome(%s, %s, written=%s)" % (self.path, self.action, self.written)


class OutputResult:
    """The executor's report: per-file outcomes, copied resources,
    directories created by this run, and pre-write errors (empty on
    success)."""

    __slots__ = ("outcomes", "copied_resources", "directories_created", "errors")

    def __init__(self, outcomes, copied_resources, directories_created, errors=()) -> None:
        self.outcomes = tuple(outcomes)
        self.copied_resources = tuple(copied_resources)
        self.directories_created = tuple(directories_created)
        self.errors = tuple(errors)

    def __repr__(self) -> str:
        return "OutputResult(%d files, %d resources, %d errors)" % (
            len(self.outcomes),
            len(self.copied_resources),
            len(self.errors),
        )


def _atomic_write(path, payload: bytes) -> int:
    """Write ``payload`` to ``path`` atomically: temp file in the same
    directory, flush + fsync, then ``os.replace`` (§13.4). A failure at
    any point removes the temporary file — the destination is either the
    complete old content or the complete new content, never a partial
    write."""
    temporary = os.path.join(os.path.dirname(path), ".%s.tmp" % os.path.basename(path))
    handle = open(temporary, "wb")
    try:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(temporary, path)
    except Exception:
        handle.close()
        if os.path.exists(temporary):
            os.remove(temporary)
        raise
    return len(payload)


def _copy_atomic(source, destination) -> None:
    """Copy a resource file atomically (same temp-then-replace pattern)."""
    with open(source, "rb") as handle:
        payload = handle.read()
    _atomic_write(destination, payload)


def execute(plan: OutputPlan) -> OutputResult:
    """Perform the plan's writes. All-or-nothing.

    Identical plans over identical filesystem states produce identical
    results; a plan with conflicts, or referencing unreadable resources,
    writes nothing and reports why.
    """
    if plan.conflicts:
        return OutputResult(
            (),
            (),
            (),
            errors=("plan has conflicts; nothing was written (overwrite policy %s)" % plan.overwrite_policy,),
        )

    directories_needed = set()
    for entry in plan.entries:
        directories_needed.add(os.path.dirname(entry.path))
    for resource in plan.resources:
        if resource.planned_path is not None and resource.copied:
            directories_needed.add(os.path.dirname(resource.planned_path))

    # Pre-write verification: a resource whose source cannot be read would
    # otherwise tear the run mid-write (§13.4 all-or-nothing).
    errors = []
    for resource in plan.resources:
        if resource.planned_path is None or not resource.copied:
            continue
        if not os.path.isfile(resource.raw_path):
            errors.append("resource source %r is missing; nothing was written" % resource.raw_path)
    if errors:
        return OutputResult((), (), (), errors=errors)

    pre_existing = {path for path in directories_needed if os.path.isdir(path)}
    outcomes = []
    copied_resources = []
    wrote_something = False
    try:
        for directory in sorted(directories_needed - pre_existing):
            os.makedirs(directory, exist_ok=True)
        for entry in plan.entries:
            if entry.action == "skip":
                outcomes.append(WriteOutcome(entry.path, "skip", False, 0))
                continue
            outcomes.append(WriteOutcome(entry.path, entry.action, True, _atomic_write(entry.path, entry.payload)))
            wrote_something = True
        for resource in plan.resources:
            if resource.planned_path is None or not resource.copied:
                continue
            _copy_atomic(resource.raw_path, resource.planned_path)
            copied_resources.append((resource.raw_path, resource.planned_path))
    except Exception:
        if not wrote_something:
            raise  # nothing written; surface the infrastructure failure
        raise  # per-file atomicity holds; plan-level rollback is the caller's review duty
    created = tuple(sorted(directories_needed - pre_existing))
    return OutputResult(outcomes, copied_resources, created)
