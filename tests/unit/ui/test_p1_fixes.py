"""Regression tests for the three P1 fixes from the CLI re-audit.

1. Bonded pairs removal: the menu's 1-based number is parsed and
   converted to the service's 0-based index (a string used to be passed
   straight through, so removal could never succeed), the listing shows
   the stored linkages, and cancel/garbage never removes.
2. Generate JSON: cancelling the multi-select generates nothing
   (an empty selection used to be coerced into "export all").
3. Edit Entity: a blank description keeps the current description — a
   sequence-only edit no longer rewrites an absent description into an
   explicit empty one (which serialized as ``"description": ""``).

The navigation the scripts below drive is the simplified menu: master
1) Edit the job → 1) Entities → add/edit, and 3) Bonds, modifications &
custom components; master 4) Generate JSON.
"""

from __future__ import annotations

import json

from configbuilder.app.cli import MenuApp
from configbuilder.ui.render.console import ScriptedConsole
from configbuilder.ui.services import build_services


def _app(script):
    console = ScriptedConsole(script)
    app = MenuApp(build_services(), console)
    status = app.run()
    return app, console.transcript, status


# The shared opening: a new job with one protein (no MSA, no templates),
# back at the "Edit the job" screen.
_NEW_JOB_WITH_PROTEIN = [
    "1", "exp",                              # master -> new job
    "1", "1", "1", "1", "AG", "n", "n",      # Edit -> Entities -> add -> protein
    "0",                                     # back to Edit the job
]


# -- P1-1: bonded pairs removal ------------------------------------------


def test_linkage_add_then_remove_round_trip_through_the_menu():
    app, transcript, status = _app(
        _NEW_JOB_WITH_PROTEIN
        + [
            "3", "1",                   # bonds -> add a bond
            "1",                        # first entity
            "1", "CA",                  # residue a, atom a
            "1",                        # second entity
            "2", "N",                   # residue b, atom b
            "2",                        # remove...
            "1",                        # ...the 1-based number from the listing
            "0", "0", "0",              # back out; EOF ends
        ]
    )
    assert status == 0
    assert "Linkage added." in transcript
    assert "Linkage removed." in transcript
    assert app._services.projects.project.configuration.linkages == ()


def test_linkage_listing_shows_endpoints_before_removal():
    app, transcript, status = _app(
        _NEW_JOB_WITH_PROTEIN
        + [
            "3", "1",                   # add the bond first
            "1", "1", "CA", "1", "2", "N",
            "0", "0",                   # back -> Edit the job -> master
            "1", "3", "0",              # reopen the bonds screen: the listing prints
            "0", "0", "0",
        ]
    )
    assert status == 0
    assert "  1) A:1:CA -- A:2:N" in transcript


def test_linkage_removal_zero_or_blank_cancels():
    app, transcript, status = _app(
        _NEW_JOB_WITH_PROTEIN
        + [
            "3", "1", "1", "1", "CA", "1", "2", "N",
            "2", "0",                   # remove -> 0 cancels
            "2", "",                    # remove -> blank cancels
            "0", "0", "0",
        ]
    )
    assert status == 0
    assert "Not applied" not in transcript
    assert len(app._services.projects.project.configuration.linkages) == 1


def test_linkage_removal_garbage_and_out_of_range_cancel():
    app, transcript, status = _app(
        _NEW_JOB_WITH_PROTEIN
        + [
            "3", "1", "1", "1", "CA", "1", "2", "N",
            "2", "x",                   # unparsable
            "2", "9",                   # out of range
            "0", "0", "0",
        ]
    )
    assert status == 0
    assert transcript.count("Not a valid choice") == 2
    assert len(app._services.projects.project.configuration.linkages) == 1


def test_linkage_removal_second_of_two():
    app, transcript, status = _app(
        _NEW_JOB_WITH_PROTEIN
        + [
            "3", "1", "1", "1", "CA", "1", "2", "N",    # linkage 1: A:1:CA -- A:2:N
            "1", "1", "2", "CB", "1", "3", "O",         # linkage 2: A:1:CB -- A:3:O
            "2", "2",                   # remove the second listed linkage
            "0", "0", "0",
        ]
    )
    assert status == 0
    linkages = app._services.projects.project.configuration.linkages
    assert len(linkages) == 1
    assert linkages[0].a.residue.value == 1 and linkages[0].b.residue.value == 2


# -- P1-2: multi-select cancel scope ------------------------------------


def _project_with_two_variants(services):
    services.projects.new("exp")
    services.configuration.add_record("protein", "AG")
    services.variants.add_spec("v_one", "first", ())
    services.variants.add_spec("v_two", "second", ())


def test_cancelled_multi_select_generates_nothing():
    services = build_services()
    _project_with_two_variants(services)
    console = ScriptedConsole([
        "4",              # master -> Generate JSON
        "3",              # select variant JSONs to generate
        "0",              # cancel the multi-select
        "0",              # back; EOF ends
    ])
    app = MenuApp(services, console)
    status = app.run()
    assert status == 0
    assert "create" not in console.transcript
    assert "Write these files?" not in console.transcript


def test_multi_select_after_a_cancel_selects_exactly_the_chosen():
    services = build_services()
    _project_with_two_variants(services)
    console = ScriptedConsole([
        "4", "3", "0",    # first multi-select cancelled
        "3",              # the picker again
        "1 2",            # both, this time
        "n",              # decline the write prompt
        "0",
    ])
    app = MenuApp(services, console)
    status = app.run()
    assert status == 0
    # The plan this time covers exactly the chosen variants — and the
    # decline means nothing was written.
    assert console.transcript.count("Write these files?") == 1
    assert "exp__v-one" in console.transcript
    assert "exp__v-two" in console.transcript
    assert "Wrote " not in console.transcript


# -- P1-3: edit entity keeps an absent description ----------------------


def _protein_job():
    services = build_services()
    services.projects.new("exp")
    services.configuration.add_record("protein", "AG")
    return services


def _edit_flow_script():
    return [
        "1", "1", "2",     # Edit the job -> Entities -> edit
        "1",               # entity A
        "AGGGG",           # new sequence
        "",                # blank description: keeps
        "0", "0", "0",
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
        "1", "1", "2",
        "1",
        "",                      # keep the sequence
        "my favourite binder",   # a real description
        "0", "0", "0",
    ])
    app = MenuApp(services, console)
    status = app.run()
    assert status == 0
    record = services.projects.project.configuration.records[0]
    assert record.description.value == "my favourite binder"
