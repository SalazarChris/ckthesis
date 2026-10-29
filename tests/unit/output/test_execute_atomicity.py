"""Atomicity under simulated failure (IMPLEMENTATION_PLAN.md §13.4).

A failed write leaves no partial file and no temporary file behind; the
destination holds either the complete old bytes or the complete new bytes.

The failure is *reported* (``OutputResult.errors``) rather than raised. That
is the delivered behavior, not an accident: playtesting the real CLI in a
redirected shell showed a user who typed an unusable output directory (a
path whose parent is a file, or ``nul``) getting a traceback and a dead
session. ``execute`` still catches nothing but ``OSError`` -- a defect in
this code must fail loudly -- and these tests keep every atomicity guarantee
while asserting the report.
"""

from __future__ import annotations

import importlib
import os

import pytest

from configbuilder.output.naming import variant_directory_name
from configbuilder.output.policies import OverwritePolicy
from configbuilder.output.plan import plan

# The package re-exports the ``execute`` function, so ``import ... as x``
# would bind the function, not the module; resolve the module explicitly.
execute_module = importlib.import_module("configbuilder.output.execute")
execute = execute_module.execute


A3M = b">query\nPEPT\n"
OTHER = b">query\nMUTA\n"


class _ExplodingAfterWrite:
    """A payload whose ``write`` explodes mid-stream (simulated disk full)."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.fingerprint = None

    def __len__(self) -> int:
        return len(self._payload)


def _plan_into(tmp_path, payload=A3M, existing=None):
    if existing:
        for relative, data in existing.items():
            full = tmp_path / relative
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(data)
    return plan({"wt": payload}, str(tmp_path), "P")


def test_failed_write_leaves_no_temporary_file(tmp_path, monkeypatch):
    planned = _plan_into(tmp_path)
    directory = os.path.dirname(planned.entries[0].path)
    os.makedirs(directory, exist_ok=True)
    temporary = os.path.join(directory, ".%s.tmp" % os.path.basename(planned.entries[0].path))

    real_replace = os.replace

    def exploding_replace(source, destination):
        if source == temporary:
            raise OSError("simulated crash during replace")
        return real_replace(source, destination)

    monkeypatch.setattr(execute_module.os, "replace", exploding_replace)
    result = execute(planned)  # reported, not raised: see the docstring above
    assert result.errors, "the failed write must be reported, not swallowed"
    assert result.outcomes == (), "the failed file is not reported as written"
    assert not os.path.exists(temporary), "the temporary file is cleaned up"
    assert not os.path.exists(planned.entries[0].path), "the destination is untouched"


def test_failed_overwrite_preserves_the_old_bytes(tmp_path, monkeypatch):
    existing_path = os.path.join("p", variant_directory_name("P", "wt"), variant_directory_name("P", "wt") + ".json")
    full = tmp_path / existing_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(A3M)
    # The Overwrite policy is what lets the plan reach the write at all
    # (default Fail would report a conflict and write nothing).
    planned = plan({"wt": OTHER}, str(tmp_path), "P", overwrite_policy=OverwritePolicy("Overwrite"))
    directory = os.path.dirname(planned.entries[0].path)
    os.makedirs(directory, exist_ok=True)
    temporary = os.path.join(directory, ".%s.tmp" % os.path.basename(planned.entries[0].path))

    real_replace = os.replace

    def exploding_replace(source, destination):
        if source == temporary:
            raise OSError("simulated crash during replace")
        return real_replace(source, destination)

    monkeypatch.setattr(execute_module.os, "replace", exploding_replace)
    result = execute(planned)  # reported, not raised: see the docstring above
    assert result.errors, "the failed overwrite must be reported, not swallowed"
    with open(planned.entries[0].path, "rb") as handle:
        assert handle.read() == A3M, "the old complete bytes survive a failed overwrite"


def test_successful_run_leaves_no_temporaries(tmp_path):
    planned = _plan_into(tmp_path)
    execute(planned)
    directory = os.path.dirname(planned.entries[0].path)
    assert [name for name in os.listdir(directory) if name.endswith(".tmp")] == []


# -- a filesystem refusal is reported, not raised -------------------------------


def test_uncreatable_directory_is_reported_not_raised(tmp_path):
    """A destination whose parent is an existing *file* cannot be created.

    Users reach this by naming their output directory after a file that
    already exists, or after a name the platform reserves (``nul`` on
    Windows). ``execute`` used to raise, so a beginner who had merely typed
    a name got a traceback and a dead session; now it is reported exactly
    like every other unusable destination, and the caller prints it.
    """
    out = tmp_path / "out"
    out.write_text("not a directory", encoding="utf-8")
    planned = plan({"wt": A3M}, str(out), "P")

    result = execute(planned)

    assert result.errors, "an unusable destination must be reported"
    assert result.outcomes == ()
    assert "could not create the directory" in result.errors[0]
    assert "the output directory" in result.errors[0] and "is a file" in result.errors[0]
    assert out.read_text(encoding="utf-8") == "not a directory", "the file is untouched"


@pytest.mark.skipif(os.name != "nt", reason="reserved device names are Windows-only")
def test_reserved_device_name_is_reported_not_raised(tmp_path):
    planned = plan({"wt": A3M}, os.path.join(str(tmp_path), "nul"), "P")

    result = execute(planned)

    assert result.errors, "Windows refuses write access to `nul`; say so, do not raise"
    assert result.outcomes == ()


def test_a_later_failure_removes_the_files_this_run_created(tmp_path, monkeypatch):
    """Base written, then the variant write fails: the batch leaves nothing.

    Nothing existed before the run, so every file it wrote is a ``create``
    and the rollback removes it again (with the directories it made). The
    error still names the file that failed and says what happened, rather
    than pretending the run never started.
    """
    planned = plan({"wt": A3M, "mut": OTHER}, str(tmp_path), "P")
    real = execute_module._atomic_write
    calls = {"count": 0}

    def fail_on_second(path, payload):
        calls["count"] += 1
        if calls["count"] > 1:
            raise OSError(28, "No space left on device")
        return real(path, payload)

    monkeypatch.setattr(execute_module, "_atomic_write", fail_on_second)
    result = execute(planned)

    assert result.errors
    assert "could not write" in result.errors[0]
    assert "created by this run were removed again" in result.errors[0]
    assert not [outcome for outcome in result.outcomes if outcome.written]
    assert not os.path.isfile(planned.entries[0].path), "no half-written batch"
    first_directory = os.path.dirname(os.path.dirname(planned.entries[0].path))
    assert not os.path.isdir(first_directory), "no empty scaffolding left behind"


def test_a_later_failure_leaves_a_pre_existing_file_as_rewritten(
    tmp_path, monkeypatch
):
    """A file that existed before the run is never deleted by the rollback.

    Its old bytes were replaced by design and cannot be restored, so deleting
    it would destroy the user's file instead of undoing the run. The message
    says that plainly, which is the honest limit of a per-file transaction.
    """
    # The file must exist *before* planning: the plan records what the
    # filesystem held when it was made, and that is what the rollback honours.
    first_path = os.path.join(str(tmp_path), "p", "p__wt", "p__wt.json")
    os.makedirs(os.path.dirname(first_path), exist_ok=True)
    with open(first_path, "wb") as handle:
        handle.write(b"older bytes\n")
    # Policy Overwrite, so the existing file is genuinely replaced rather than
    # refused as a conflict; that is the only case a rollback must think about.
    planned = plan(
        {"wt": A3M, "mut": OTHER},
        str(tmp_path),
        "P",
        overwrite_policy=OverwritePolicy("Overwrite"),
    )
    assert planned.entries[0].path == first_path
    assert planned.entries[0].action == "overwrite"

    real = execute_module._atomic_write
    calls = {"count": 0}

    def fail_on_second(path, payload):
        calls["count"] += 1
        if calls["count"] > 1:
            raise OSError(28, "No space left on device")
        return real(path, payload)

    monkeypatch.setattr(execute_module, "_atomic_write", fail_on_second)
    result = execute(planned)

    assert result.errors
    assert "could not write" in result.errors[0]
    assert "already existed were left as rewritten" in result.errors[0]
    assert os.path.isfile(first_path), "a pre-existing file is never deleted"
    assert not os.path.isfile(planned.entries[1].path)
