"""The default policy and the configuration-status view (task §13–§18).

Two claims are pinned here. First, a new job arrives complete enough to
export without any boilerplate ritual: it has a name, model seeds, and a
format-version pin, and every one of those is reported as *automatic* rather
than as user input. Second, the status view is the single place that says
what is still required — it points at the entities and nothing else, treats
absent optional fields as absent (never as errors), and follows conditional
requirements (a version pin only matters while the version is unverified; a
feature's row appears only once the feature is used).

The display half is covered too: the master menu shows the status block, and
a blocked generation names the missing information instead of stating a bare
verdict.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from configbuilder.app.cli import MenuApp
from configbuilder.app.validation_service import ValidationService
from configbuilder.app.status import (
    DEFAULT_SEED_VALUES,
    DEFAULT_VERSION,
    FieldState,
    is_automatic_name,
)
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services

OPTIONAL_KEYS = ("modifications", "msa", "templates")


def _services():
    """The shipped bundle plus a local validation service.

    ``build_services()`` wires validation into generation and exposes it on
    the bundle; these tests keep a local handle so they can exercise the
    status and validation calls directly.
    """
    services = build_services()
    return SimpleNamespace(
        projects=services.projects,
        configuration=services.configuration,
        variants=services.variants,
        generation=services.generation,
        validation=ValidationService(services.projects),
    )


def _job_with_protein(sequence: str = "ACDEFGHIKLMNPQRSTVWY"):
    services = _services()
    services.projects.new()
    services.configuration.add_record("protein", sequence)
    return services


def _states(status):
    return {field.key: field.state for field in status.fields}


def _record_key(services, index: int = 0) -> str:
    record = services.projects.project.configuration.records[index]
    return record.ids.primary.value


# -- Test 1: an empty new configuration ---------------------------------------


def test_empty_new_configuration_defaults_what_it_can_and_asks_for_entities():
    services = _services()
    services.projects.new()
    status = services.validation.status()

    assert _states(status)["name"] == FieldState.DEFAULTED
    assert _states(status)["seeds"] == FieldState.DEFAULTED
    assert _states(status)["version"] == FieldState.DEFAULTED
    assert status.field("seeds").value == DEFAULT_SEED_VALUES
    assert is_automatic_name(status.field("name").value)
    # The one genuinely required input is named, with the rule's own wording.
    assert _states(status)["components"] == FieldState.MISSING
    assert status.field("components").message
    assert not status.ready
    assert [field.key for field in status.attention()] == ["components"]


def test_successive_new_jobs_get_distinct_automatic_names():
    services = _services()
    services.projects.new()
    first = services.projects.project.configuration.metadata.name
    services.projects.new("")
    second = services.projects.project.configuration.metadata.name

    assert is_automatic_name(first) and is_automatic_name(second)
    assert first != second


def test_a_supplied_name_is_kept():
    services = _services()
    services.projects.new("Chosen Name")
    status = services.validation.status()

    assert status.field("name").value == "Chosen Name"
    assert status.field("name").state == FieldState.PROVIDED


# -- Test 2 / Test 3: provided protein and DNA --------------------------------


def test_provided_protein_leaves_defaults_and_completes_the_entity_row():
    services = _job_with_protein()
    status = services.validation.status()

    assert _states(status)["components"] == FieldState.PROVIDED
    assert status.field("components").value["protein"] == 1
    assert _states(status)["name"] == FieldState.DEFAULTED
    assert _states(status)["seeds"] == FieldState.DEFAULTED
    assert status.ready


def test_provided_dna_is_stored_as_a_duplex_and_completes_the_entity_row():
    services = _services()
    services.projects.new()
    services.configuration.add_record("dna", "ACGTACGT")

    status = services.validation.status()

    assert status.field("components").value["dna"] == 2
    assert _states(status)["components"] == FieldState.PROVIDED
    assert status.ready


# -- Test 4: a complete configuration generates JSON --------------------------


def test_complete_configuration_generates_json(tmp_path):
    services = _job_with_protein()
    assert services.validation.status().ready

    plan = services.generation.plan_base(str(tmp_path))
    assert plan.ok, plan.message
    result = services.generation.execute(plan)

    assert result.ok, result.errors
    assert result.written
    document = json.loads(open(result.written[0], encoding="utf-8").read())
    assert document["sequences"][0]["protein"]["sequence"] == "ACDEFGHIKLMNPQRSTVWY"


# -- Test 5: missing required information -------------------------------------


def test_missing_required_information_blocks_and_is_named(tmp_path):
    services = _services()
    services.projects.new()

    plan = services.generation.plan_base(str(tmp_path))
    assert not plan.ok
    assert any(
        getattr(finding, "rule_id", "") == "R-ROOT-006" for finding in plan.findings
    )

    status = services.validation.status()
    assert not status.ready
    missing = status.attention()
    assert [field.key for field in missing] == ["components"]
    assert "entities" in missing[0].message


# -- Test 6: a user override replaces the default and reaches the JSON --------


def test_user_overrides_replace_defaults_and_survive_into_json(tmp_path):
    services = _job_with_protein()
    assert services.configuration.set_name("my-job").ok
    assert services.configuration.set_seeds([2, 3]).ok

    status = services.validation.status()
    assert status.field("name").state == FieldState.PROVIDED
    assert status.field("name").value == "my-job"
    assert status.field("seeds").state == FieldState.PROVIDED
    assert status.field("seeds").value == (2, 3)
    # The version pin is a separate default, untouched by the other edits.
    assert status.field("version").state == FieldState.DEFAULTED

    plan = services.generation.plan_base(str(tmp_path))
    assert plan.ok, plan.message
    result = services.generation.execute(plan)
    document = json.loads(open(result.written[0], encoding="utf-8").read())

    assert document["name"] == "my-job"
    assert document["modelSeeds"] == [2, 3]


# -- Test 7: an absent optional field is not an error -------------------------


def test_absent_optional_fields_are_not_errors():
    services = _job_with_protein()
    status = services.validation.status()

    for key in OPTIONAL_KEYS:
        assert not status.field(key).needs_attention, key
    assert status.ready
    # Nothing about an unused optional feature blocks the job either.
    report = services.validation.validate_base().report
    assert report.blocking() == ()


# -- Test 8: conditional requirements -----------------------------------------


def test_optional_feature_row_appears_only_once_the_feature_is_used():
    services = _job_with_protein()
    assert services.validation.status().field("modifications").state == FieldState.NONE

    assert services.configuration.add_modification(_record_key(services), "SEP", 1).ok
    status = services.validation.status()

    assert status.field("modifications").state == FieldState.PROVIDED
    assert status.ready  # using a feature does not itself become a requirement


def test_version_requirement_follows_the_selected_state():
    services = _job_with_protein()
    assert services.validation.status().field("version").state == FieldState.DEFAULTED

    assert services.configuration.set_format_target(version=None).ok
    unverified = services.validation.status()
    assert unverified.field("version").state == FieldState.MISSING
    assert not unverified.ready

    assert services.configuration.set_format_target(version=DEFAULT_VERSION).ok
    assert services.validation.status().ready


def test_a_version_too_low_for_a_used_field_is_not_ready_and_names_the_version():
    """A per-entity description is written from version 4 only, so a job
    pinned to 3 must not read as ready — and the finding, the readiness
    verdict and the JSON preview must all tell the same story.

    This is the Stage 3 inconsistency, now impossible: readiness reads the
    same mapping-layer facts the generation gate refuses on.
    """
    services = _job_with_protein()
    key = _record_key(services)
    assert services.validation.status().ready

    assert services.configuration.update_record(key, description="tagged").ok
    conflicting = services.validation.status()

    assert not conflicting.ready
    assert conflicting.field("version").state == FieldState.INVALID
    assert "version 4" in conflicting.field("version").message

    # Generation now refuses at the readiness gate — the same verdict the
    # status view shows — instead of reaching the transform's feature check.
    # One refusal, one reason, and the field that explains it is the
    # INVALID version row asserted above.
    text, reason = services.generation.show_json()
    assert text is None
    assert "not ready" in reason

    # Raising the pin explicitly — the user's own action — clears it.
    assert services.configuration.set_format_target(version=4).ok
    resolved = services.validation.status()
    assert resolved.ready
    assert resolved.field("version").state == FieldState.PROVIDED
    assert services.generation.show_json()[0] is not None


# -- the display: one status view, shown wherever the user looks --------------


def test_a_blocked_save_shows_the_status_block():
    """The status view is shown wherever the user looks — here, when a save
    is refused because the job has no entities yet."""
    services = _services()
    console = ScriptedConsole(["1", "", "6", "blocked.json", "0", "0"])
    MenuApp(services, console).run()

    out = console.transcript
    assert "Configuration status" in out
    assert "STATUS: INCOMPLETE" in out
    assert "MISSING" in out
    assert "Untitled job 1" in out


def test_a_refused_save_names_the_missing_information():
    """A save with a blocking finding is refused, names the missing field,
    and leaves the job editable."""
    services = _services()
    console = ScriptedConsole(["1", "job", "6", "blocked.json", "0", "0"])
    MenuApp(services, console).run()

    out = console.transcript
    assert "This job cannot be saved yet:" in out
    assert "Configuration status" in out
    assert "Entities" in out
    # the blocked field is named by the catalogue's own row
    assert "no entities" in out.lower() or "at least one" in out.lower()
    # the job is still there, editable
    assert services.projects.project is not None
