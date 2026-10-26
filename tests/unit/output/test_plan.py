"""Planner tests (IMPLEMENTATION_PLAN.md §13.2, §13.3, §13.5).

Planning is pure apart from the injected read-only ``FileView``: the same
inputs and the same filesystem state always yield the same plan. All
policies and collision rules are exercised here against a fake filesystem
in memory.
"""

from __future__ import annotations

import os

import pytest

from configbuilder.output.naming import variant_directory_name, variant_file_name
from configbuilder.output.policies import OverwritePolicy, PathPolicy
from configbuilder.output.plan import FileView, OutputPlan, PlanEntry, fingerprint, plan


class FakeFilesystem(FileView):
    """In-memory filesystem for planning: a dict of path -> bytes."""

    def __init__(self, files=None) -> None:
        self.files = dict(files or {})

    def exists(self, path) -> bool:
        return path in self.files

    def read(self, path) -> bytes:
        return self.files[path]


A3M = b">query\nPEPT\n"
DIFFERENT = b">query\nMUTA\n"


def _payloads(*keys):
    return {key: A3M for key in keys}


def _requirements(path="msa.a3m", kind="unpairedMsaPath"):
    class _Req:
        pass

    requirement = _Req()
    requirement.kind = kind
    requirement.raw_path = path
    return (requirement,)


# -- basic planning ---------------------------------------------------------------


def test_plan_is_deterministic():
    first = plan(_payloads("wt", "mut"), "out", "Project", filesystem=FakeFilesystem())
    second = plan(_payloads("wt", "mut"), "out", "Project", filesystem=FakeFilesystem())
    assert [e.path for e in first.entries] == [e.path for e in second.entries]
    assert [e.action for e in first.entries] == [e.action for e in second.entries]
    assert first.conflicts == second.conflicts == ()


def test_every_variant_gets_directory_and_same_named_file():
    result = plan(_payloads("wt"), "out", "Project", filesystem=FakeFilesystem())
    directory = variant_directory_name("Project", "wt")
    assert result.entries[0].path == os.path.join("out", "project", directory, directory + ".json")
    assert result.entries[0].action == "create"
    assert result.entries[0].payload_fingerprint == fingerprint(A3M)


def test_plan_carries_the_policies():
    result = plan(_payloads("wt"), "out", "P", filesystem=FakeFilesystem())
    assert result.overwrite_policy == OverwritePolicy("Fail")
    assert result.path_policy == PathPolicy("CopyIntoAssets")


# -- collision detection (§13.2) ---------------------------------------------------


def test_case_differing_variant_keys_conflict():
    result = plan(_payloads("Var", "var"), "out", "P", filesystem=FakeFilesystem())
    assert result.conflicts, "case-differing keys must be treated as a collision everywhere"


def test_distinct_variant_keys_do_not_conflict():
    result = plan(_payloads("wt", "mut"), "out", "P", filesystem=FakeFilesystem())
    assert result.conflicts == ()


def test_truncation_colliding_slugs_are_detected():
    # The two keys differ only beyond the slug's length cap, so both
    # truncate to the same directory name (plan §13.2: resolved as a
    # conflict, never silently merged).
    long_a = "alpha-" + "b" * 100
    long_b = "alpha-" + "b" * 100 + "suffix"
    result = plan(_payloads(long_a, long_b), "out", "P", filesystem=FakeFilesystem())
    assert result.conflicts, "two keys truncating to the same slug must be a planned conflict"


# -- overwrite policies (§13.3) -----------------------------------------------------


def _existing_plan(payload, overwrite_policy, existing=A3M):
    directory = variant_directory_name("P", "wt")
    file_path = os.path.join("out", "p", directory, directory + ".json")
    filesystem = FakeFilesystem({file_path: existing})
    return plan(
        {"wt": payload},
        "out",
        "P",
        overwrite_policy=overwrite_policy,
        filesystem=filesystem,
    )


def test_fail_policy_reports_conflict_on_different_bytes():
    result = _existing_plan(DIFFERENT, OverwritePolicy("Fail"))
    assert result.entries[0].action == "conflict"
    assert result.conflicts


def test_fail_policy_creates_when_bytes_match():
    result = _existing_plan(A3M, OverwritePolicy("Fail"))
    assert result.entries[0].action == "overwrite"  # identical bytes: harmless


def test_skip_policy_plans_a_skip():
    result = _existing_plan(DIFFERENT, OverwritePolicy("Skip"))
    assert result.entries[0].action == "skip"
    assert result.conflicts == ()


def test_overwrite_policy_plans_an_overwrite():
    result = _existing_plan(DIFFERENT, OverwritePolicy("Overwrite"))
    assert result.entries[0].action == "overwrite"
    assert result.conflicts == ()


def test_versioned_policy_resolves_the_real_suffixed_path():
    result = _existing_plan(DIFFERENT, OverwritePolicy("Versioned"))
    entry = result.entries[0]
    assert entry.action == "create"
    assert entry.path.endswith("-1.json")
    assert os.path.dirname(entry.path) == os.path.dirname(
        os.path.join("out", "p", variant_directory_name("P", "wt"), "x")
    )


def test_versioned_reuses_an_identical_existing_suffixed_file():
    directory = variant_directory_name("P", "wt")
    stem = directory
    first_suffixed = os.path.join("out", "p", directory, "%s-1.json" % stem)
    original = plan(
        {"wt": A3M}, "out", "P", overwrite_policy=OverwritePolicy("Fail"), filesystem=FakeFilesystem()
    )
    original_path = original.entries[0].path
    filesystem = FakeFilesystem({original_path: DIFFERENT, first_suffixed: A3M})
    again = plan(
        {"wt": A3M},
        "out",
        "P",
        overwrite_policy=OverwritePolicy("Versioned"),
        filesystem=filesystem,
    )
    assert again.entries[0].path == first_suffixed
    assert again.entries[0].action == "create"


# -- path policies (§13.5) -----------------------------------------------------------


def test_copy_into_assets_is_the_default_and_plans_a_copy():
    directory = variant_directory_name("P", "wt")
    result = plan(
        _payloads("wt"),
        "out",
        "P",
        resources_by_variant={"wt": _requirements("msa.a3m")},
        filesystem=FakeFilesystem({"msa.a3m": b">q\nAAAA\n"}),
    )
    resource = result.resources[0]
    assert resource.copied is True
    assert resource.planned_path.endswith(os.path.join("assets", "msa.a3m"))
    assert resource.emitted_path == "assets/msa.a3m"
    assert "\\" not in resource.emitted_path
    assert resource.planned_path.endswith("msa.a3m"), "the asset keeps its extension"


def test_relative_to_output_emits_the_path_as_given():
    result = plan(
        _payloads("wt"),
        "out",
        "P",
        path_policy=PathPolicy("RelativeToOutput"),
        resources_by_variant={"wt": _requirements("../data/msa.a3m")},
        filesystem=FakeFilesystem(),
    )
    resource = result.resources[0]
    assert resource.copied is False
    assert resource.planned_path is None
    assert resource.emitted_path == "../data/msa.a3m"


def test_as_given_emits_unchanged_but_warns_on_absolute_paths():
    result = plan(
        _payloads("wt"),
        "out",
        "P",
        path_policy=PathPolicy("AsGiven"),
        resources_by_variant={"wt": _requirements("C:\\data\\msa.a3m")},
        filesystem=FakeFilesystem(),
    )
    assert result.resources[0].emitted_path == "C:/data/msa.a3m"
    assert result.warnings, "absolute paths must warn: they do not travel (§13.5)"


def test_missing_source_warns_under_copy_into_assets():
    result = plan(
        _payloads("wt"),
        "out",
        "P",
        resources_by_variant={"wt": _requirements("gone.a3m")},
        filesystem=FakeFilesystem(),
    )
    assert any("does not exist" in warning for warning in result.warnings)


def test_emitted_paths_always_use_forward_slashes():
    result = plan(
        _payloads("wt"),
        "out",
        "P",
        resources_by_variant={"wt": _requirements("C:\\data\\msa.a3m")},
        filesystem=FakeFilesystem(),
    )
    for resource in result.resources:
        assert "\\" not in resource.emitted_path


# -- plan object shape -----------------------------------------------------------------


def test_plan_records_everything_execute_needs():
    result = plan(_payloads("wt", "mut"), "out", "My Project", filesystem=FakeFilesystem())
    assert isinstance(result, OutputPlan)
    assert all(isinstance(entry, PlanEntry) for entry in result.entries)
    assert result.project_slug == "my-project"
    assert result.output_root == "out"
