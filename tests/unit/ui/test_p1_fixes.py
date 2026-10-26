"""Regression tests for the edit-entity description behaviour.

An edit that leaves the description blank must keep the current (absent)
description — a sequence-only edit must not rewrite an absent description
into an explicit empty one, which would serialize as ``"description": ""``.
The edit flow's navigation is the reworked menu: job 3) Edit entity.
"""

from __future__ import annotations

import json

from configbuilder.app.cli import MenuApp
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services


def _protein_job():
    services = build_services()
    services.projects.new("exp")
    services.configuration.add_record("protein", "AG")
    return services


def _edit_flow_script():
    return [
        "3", "1", "1",     # job -> Edit entity -> record A -> 1 Edit
        "AGGGG",           # new sequence
        "",                # blank description: keeps
        "n", "n",          # no MSA, no templates (protein edit questions)
        "0",               # back to the entity list
        "0",               # back to the job menu
        "2", "0",          # leave without saving (dirty), then exit
    ]


def test_sequence_only_edit_leaves_description_unset():
    services = _protein_job()
    console = ScriptedConsole(_edit_flow_script())
    app = MenuApp(services, console)
    status = app.run()
    assert status == 0
    from configbuilder.model import Unset

    record = services.projects.project.configuration.records[0]
    assert isinstance(record.description, Unset)


def test_sequence_only_edit_omits_description_in_wire_json():
    services = _protein_job()
    console = ScriptedConsole(_edit_flow_script())
    app = MenuApp(services, console)
    status = app.run()
    assert status == 0
    text_json, error = services.generation.show_json(None)
    assert error is None
    document = json.loads(text_json)
    assert "description" not in document["sequences"][0]["protein"]


def test_typed_description_still_applies():
    services = _protein_job()
    console = ScriptedConsole([
        "3", "1", "1",
        "",                      # keep the sequence
        "my favourite binder",   # a real description
        "n", "n",
        "0", "2", "0",
    ])
    app = MenuApp(services, console)
    status = app.run()
    assert status == 0
    record = services.projects.project.configuration.records[0]
    assert record.description.value == "my favourite binder"


# -- cancel semantics: editing must not partially modify ----------------------


def test_cancelling_the_entity_action_menu_changes_nothing():
    services = _protein_job()
    before = services.projects.project.configuration
    console = ScriptedConsole(["3", "0", "0", "2", "0"])  # edit entity -> back; leave; exit
    app = MenuApp(services, console)
    assert app.run() == 0
    assert services.projects.project.configuration == before


def test_a_blank_sequence_edit_keeps_the_current_sequence():
    services = _protein_job()
    console = ScriptedConsole(["3", "1", "1", "", "", "1", "n", "0", "2", "0"])
    app = MenuApp(services, console)
    assert app.run() == 0
    record = services.projects.project.configuration.records[0]
    assert record.sequence.text == "AG"
