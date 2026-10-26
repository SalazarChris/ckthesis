"""Executor tests (IMPLEMENTATION_PLAN.md §13.4): atomic writes, the
all-or-nothing rule, and every overwrite outcome, against a real
temporary filesystem.
"""

from __future__ import annotations

import os

import pytest

from configbuilder.output.naming import variant_directory_name
from configbuilder.output.policies import OverwritePolicy, PathPolicy
from configbuilder.output.plan import plan
from configbuilder.output.execute import execute


A3M = b">query\nPEPT\n"
DIFFERENT = b">query\nMUTA\n"


def _planned(tmp_path, payload=A3M, overwrite_policy=OverwritePolicy("Fail"), existing=None, key="wt", second_key=None, resources_by_variant=None, path_policy=None):
    keys = [key] + ([second_key] if second_key else [])
    if existing:
        for path, data in existing.items():
            full = tmp_path / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(data)
    payloads = {k: payload for k in keys}
    kwargs = {}
    if resources_by_variant is not None:
        kwargs["resources_by_variant"] = resources_by_variant
    if path_policy is not None:
        kwargs["path_policy"] = path_policy
    return plan(
        payloads,
        str(tmp_path),
        "P",
        overwrite_policy=overwrite_policy,
        **kwargs,
    )


def _planned_file(plan_result):
    return plan_result.entries[0].path


# -- happy path -----------------------------------------------------------------


def test_execute_writes_every_planned_file(tmp_path):
    planned = _planned(tmp_path, second_key="mut")
    result = execute(planned)
    assert all(outcome.written for outcome in result.outcomes)
    for entry in planned.entries:
        with open(entry.path, "rb") as handle:
            assert handle.read() == A3M
    assert result.errors == ()


def test_execute_writes_atomically_no_temp_files_left(tmp_path):
    planned = _planned(tmp_path)
    execute(planned)
    leftovers = [name for name in os.listdir(os.path.dirname(_planned_file(planned))) if ".tmp" in name]
    assert leftovers == []


def test_directories_are_created_only_as_planned(tmp_path):
    planned = _planned(tmp_path, second_key="mut")
    result = execute(planned)
    created = result.directories_created
    assert len(created) == 2
    for directory in created:
        assert os.path.isdir(directory)


def test_existing_directories_are_not_reported_as_created(tmp_path):
    planned = _planned(tmp_path)
    execute(planned)  # first run creates
    again = plan({"wt": A3M}, str(tmp_path), "P")
    result = execute(again)
    assert result.directories_created == ()
    assert all(outcome.written for outcome in result.outcomes)  # harmless rewrites


# -- all-or-nothing (§13.4) -------------------------------------------------------


def test_conflict_under_fail_writes_nothing(tmp_path):
    existing = {os.path.join("p", variant_directory_name("P", "wt"), variant_directory_name("P", "wt") + ".json"): DIFFERENT}
    planned = _planned(tmp_path, second_key="mut", existing=existing)
    result = execute(planned)
    assert result.outcomes == ()
    assert result.errors, "the result explains the refusal"
    assert not (tmp_path / "p" / variant_directory_name("P", "mut")).exists(), "the untouched variant wrote nothing"


def test_missing_resource_source_writes_nothing(tmp_path):
    source = tmp_path / "elsewhere" / "msa.a3m"  # deliberately never created
    planned = _planned(
        tmp_path,
        resources_by_variant={"wt": (_Req(str(source)),)},
    )
    result = execute(planned)
    assert result.outcomes == ()
    assert any("missing" in error for error in result.errors)


class _Req:
    def __init__(self, path, kind="unpairedMsaPath"):
        self.raw_path = path
        self.kind = kind


# -- overwrite outcomes at execute time ----------------------------------------------


def test_skip_leaves_the_existing_file_untouched(tmp_path):
    existing_path = os.path.join("p", variant_directory_name("P", "wt"), variant_directory_name("P", "wt") + ".json")
    planned = _planned(tmp_path, payload=DIFFERENT, overwrite_policy=OverwritePolicy("Skip"), existing={existing_path: A3M})
    result = execute(planned)
    assert result.outcomes[0].action == "skip"
    assert result.outcomes[0].written is False
    with open(_planned_file(planned), "rb") as handle:
        assert handle.read() == A3M  # untouched


def test_overwrite_replaces_the_bytes(tmp_path):
    existing_path = os.path.join("p", variant_directory_name("P", "wt"), variant_directory_name("P", "wt") + ".json")
    planned = _planned(tmp_path, payload=DIFFERENT, overwrite_policy=OverwritePolicy("Overwrite"), existing={existing_path: A3M})
    result = execute(planned)
    assert result.outcomes[0].action == "overwrite"
    with open(_planned_file(planned), "rb") as handle:
        assert handle.read() == DIFFERENT


def test_versioned_writes_the_suffixed_path_from_the_plan(tmp_path):
    existing_path = os.path.join("p", variant_directory_name("P", "wt"), variant_directory_name("P", "wt") + ".json")
    planned = _planned(tmp_path, payload=DIFFERENT, overwrite_policy=OverwritePolicy("Versioned"), existing={existing_path: A3M})
    entry = planned.entries[0]
    assert entry.path.endswith("-1.json")
    result = execute(planned)
    assert result.outcomes[0].written is True
    with open(entry.path, "rb") as handle:
        assert handle.read() == DIFFERENT
    with open(os.path.join(str(tmp_path), existing_path), "rb") as handle:
        assert handle.read() == A3M  # the original file survives


# -- resources ------------------------------------------------------------------------


def test_resources_are_copied_into_assets(tmp_path):
    source = tmp_path / "data" / "msa.a3m"
    source.parent.mkdir(parents=True)
    source.write_bytes(b">q\nAAAA\n")
    planned = _planned(tmp_path, resources_by_variant={"wt": (_Req(str(source)),)})
    result = execute(planned)
    assert len(result.copied_resources) == 1
    raw, destination = result.copied_resources[0]
    assert destination.endswith("msa.a3m")
    with open(destination, "rb") as handle:
        assert handle.read() == b">q\nAAAA\n"


def test_identical_existing_resource_is_not_recopied(tmp_path):
    source = tmp_path / "data" / "msa.a3m"
    source.parent.mkdir(parents=True)
    source.write_bytes(b">q\nAAAA\n")
    planned = _planned(tmp_path, resources_by_variant={"wt": (_Req(str(source)),)})
    execute(planned)
    # replan over the completed run: asset already in place with same bytes
    again = plan({"wt": A3M}, str(tmp_path), "P", resources_by_variant={"wt": (_Req(str(source)),)})
    execute(again)
    asset = again.resources[0]
    names = [name for name in os.listdir(os.path.dirname(asset.planned_path)) if name.startswith("msa")]
    assert names == ["msa.a3m"], "no duplicate suffixed copies appear"


# -- determinism of written bytes -------------------------------------------------------


def test_two_executions_produce_identical_bytes(tmp_path):
    first = execute(_planned(tmp_path))
    root = tmp_path / "p"
    digests = {}
    for directory in sorted(root.rglob("*")):
        if directory.is_file():
            digests[str(directory.relative_to(root))] = directory.read_bytes()
    second_tmp = tmp_path / "again"
    second_tmp.mkdir()
    planned2 = plan({"wt": A3M}, str(second_tmp), "P")
    execute(planned2)
    for relative, data in digests.items():
        assert (second_tmp / "p" / relative).read_bytes() == data
    assert first.errors == ()
