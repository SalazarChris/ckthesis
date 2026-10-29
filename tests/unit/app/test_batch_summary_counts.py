"""The batch run's output counts, and the one sentence built from them.

The practical audit found the console and the desktop describing the same
run differently: the console counted every plan row, so the manifest was
reported as one more file alongside the configurations, and the desktop
could not mention copied assets at all because the batch outcome did not
carry them. ``app.results.batch_counts`` counts roles instead of rows and
``ui.present.strings.batch_summary`` turns those counts into the sentence
both front ends print, so the two cannot drift apart again.
"""

from __future__ import annotations

import os

import pytest

from configbuilder.app import (
    BatchCounts,
    ConfigurationService,
    GenerationService,
    ProjectService,
    ValidationService,
    VariantService,
    batch_counts,
)
from configbuilder.app.results import LigandBatchOutput
from configbuilder.ui.present.strings import batch_summary


def _services():
    projects = ProjectService()
    variants = VariantService(projects)
    validation = ValidationService(projects)
    generation = GenerationService(projects, variants, validation=validation)
    configuration = ConfigurationService(projects)
    projects.new("Count Job")
    configuration.set_format_target(version=3, evidence="PIN-001")
    configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")
    return projects, configuration, generation


def _write(tmp_path, payload: str, name: str = "seqs.txt") -> str:
    path = os.path.join(str(tmp_path), name)
    with open(path, "w", newline="") as handle:
        handle.write(payload)
    return path


def _batch(generation, path, root):
    defaults = generation.output_defaults()
    return generation.generate_input_batch(
        path,
        str(root),
        "protein-sequence",
        overwrite_policy=defaults["overwrite"],
        path_policy=defaults["path"],
    )


# -- the counts --------------------------------------------------------------------


def test_four_records_count_as_four_configurations_and_one_manifest(tmp_path):
    _projects, _configuration, generation = _services()
    path = _write(tmp_path, "MVT\r\nMVS\r\nMVY\r\nTEST\r\n")

    outcome = _batch(generation, path, tmp_path / "out")
    assert outcome.ok, outcome.errors

    counts = batch_counts(outcome)
    assert counts.records == 4
    assert counts.configurations == 4
    assert counts.manifests == 1
    assert counts.assets == 0
    # The manifest is an output file, never a fifth configuration.
    assert counts.total == 5
    assert counts.configurations == len(outcome.written) - 1
    assert batch_summary(counts) == (
        "Generated 4 AF3 configurations. Wrote 1 manifest. "
        "Total output files: 5."
    )


def test_copied_assets_are_counted_and_named(tmp_path):
    _projects, configuration, generation = _services()
    ccd = tmp_path / "my_ccd.cif"
    ccd.write_text(
        "data_MYCCD\nloop_\n_atom_site.id\n_atom_site.type_symbol\n1 C\n",
        encoding="utf-8",
    )
    assert configuration.set_component_definition(external_path=str(ccd)).ok
    path = _write(tmp_path, "MVT\nMVS\n")

    outcome = _batch(generation, path, tmp_path / "out")
    assert outcome.ok, outcome.errors

    counts = batch_counts(outcome)
    assert (counts.configurations, counts.manifests) == (2, 1)
    assert counts.assets == 2, "one copy per generated configuration"
    assert counts.total == 5
    assert batch_summary(counts) == (
        "Generated 2 AF3 configurations. Wrote 1 manifest. "
        "Copied 2 asset files. Total output files: 5."
    )


def test_a_refused_batch_counts_nothing(tmp_path):
    _projects, _configuration, generation = _services()
    path = _write(tmp_path, "MVT\n!!!\n")

    outcome = _batch(generation, path, tmp_path / "out")
    assert not outcome.ok
    assert outcome.written == ()

    counts = batch_counts(outcome)
    assert (counts.records, counts.configurations, counts.manifests, counts.assets) == (
        0,
        0,
        0,
        0,
    )
    assert counts.total == 0


def test_a_batch_with_no_plan_counts_nothing():
    """The outcome type is also what a front end shows before a run."""
    assert batch_counts(LigandBatchOutput()).total == 0


# -- the sentence ------------------------------------------------------------------


@pytest.mark.parametrize(
    "counts, expected",
    [
        (
            BatchCounts(records=1, configurations=1, manifests=1),
            "Generated 1 AF3 configuration. Wrote 1 manifest. Total output files: 2.",
        ),
        (
            BatchCounts(records=2, configurations=2, manifests=2),
            "Generated 2 AF3 configurations. Wrote 2 manifest files. "
            "Total output files: 4.",
        ),
        (
            BatchCounts(records=1, configurations=1),
            "Generated 1 AF3 configuration. Total output files: 1.",
        ),
        (
            BatchCounts(records=1, configurations=1, manifests=1, assets=1),
            "Generated 1 AF3 configuration. Wrote 1 manifest. "
            "Copied 1 asset file. Total output files: 3.",
        ),
    ],
)
def test_the_sentence_agrees_in_number_and_names_each_role(counts, expected):
    assert batch_summary(counts) == expected


def test_the_total_is_the_sum_of_the_roles_it_names():
    counts = BatchCounts(records=3, configurations=3, manifests=1, assets=3)
    assert counts.total == counts.configurations + counts.manifests + counts.assets
