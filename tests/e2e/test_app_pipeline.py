"""End-to-end application-service tests (IMPLEMENTATION_PLAN.md §15,
Phase 10 checklist).

The whole pipeline runs headlessly through the five services: project
lifecycle, configuration editing, variant specs, validation, and the
fixed generation sequence onto a real temporary filesystem.

Generation requires an explicit format target (plan §10.3): the tests pin
one through the model with its evidence reference supplied — the runtime
never reads docs/CONTRACT_PIN.md, which these suites prove by running
everything without the patch seam the old file-based lookup required.
"""

from __future__ import annotations

import json
import os

import pytest


from configbuilder.app import (
    ConfigurationService,
    FailureReason,
    GenerationService,
    ProjectService,
    ValidationService,
    VariantService,
)
from configbuilder.identity import EntityId
from configbuilder.model import SequenceText
from configbuilder.variants import SetSequence


def _pin_evidenced():
    """Historical name; now a no-op context retained for call-site shape.
    There is no runtime pin-file seam left to patch — evidence travels in
    the model (Pinned.evidence), which is exactly the property this suite
    exercises."""
    import contextlib

    return contextlib.nullcontext()


def _services():
    """The five services wired the way a front end wires them."""
    projects = ProjectService()
    variants = VariantService(projects)
    validation = ValidationService(projects)
    generation = GenerationService(projects, validation, variants)
    configuration = ConfigurationService(projects)
    return projects, configuration, variants, validation, generation


def _project_with_variant(projects, configuration, variants):
    """A valid three-record project with one spec, built through services."""
    projects.new("E2E Job")
    configuration.set_format_target(version=3, evidence="PIN-001")
    configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")
    configuration.add_record("rna", "GGCC")
    configuration.add_record("ligand", representation="ATP")
    keys = [entity.value for entity in projects.project.configuration.identity.order()]
    variants.add_spec(
        "nob",
        "no B chain",
        (SetSequence(EntityId(keys[1]), SequenceText("AUUA", "rna")),),
    )


# -- the happy path -----------------------------------------------------------------


def test_full_generation_pipeline_writes_layout_and_manifest(tmp_path):
    with _pin_evidenced():
        projects, configuration, variants, validation, generation = _services()
        _project_with_variant(projects, configuration, variants)

        plan = generation.plan(str(tmp_path / "out"))
        assert plan.ok, plan.message
        assert plan.conflicts == ()
        # One variant file plus the manifest, under the project slug.
        names = sorted(os.path.basename(entry.path) for entry in plan.entries)
        assert names == ["e2e-job__nob.json", "manifest.json"]
        variant_entry = next(
            entry for entry in plan.entries if entry.path.endswith("e2e-job__nob.json")
        )
        assert variant_entry.action == "create"
        assert variant_entry.variant_key == "nob"

        result = generation.execute(plan)
        assert result.ok, result.errors
        assert len(result.written) == 2

        output_root = tmp_path / "out"
        variant_file = output_root / "e2e-job" / "e2e-job__nob" / "e2e-job__nob.json"
        manifest_file = output_root / "e2e-job" / "manifest.json"
        assert variant_file.exists() and manifest_file.exists()

        document = json.loads(variant_file.read_text(encoding="utf-8"))
        # Plan §13.2: the job name agrees with the derived directory name.
        assert document["name"] == "e2e-job__nob"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest["project_name"] == "E2E Job"
        assert [v["key"] for v in manifest["variants"]] == ["nob"]


def test_generation_is_reproducible_byte_for_byte(tmp_path):
    with _pin_evidenced():
        projects, configuration, variants, _validation, generation = _services()
        _project_with_variant(projects, configuration, variants)

        first_root = str(tmp_path / "first")
        second_root = str(tmp_path / "second")
        first = generation.plan(first_root)
        assert first.ok, first.message
        assert generation.execute(first).ok
        second = generation.plan(second_root)
        assert second.ok, second.message
        assert generation.execute(second).ok

        def _read_all(root):
            out = {}
            for base, _dirs, files in os.walk(root):
                for name in files:
                    path = os.path.join(base, name)
                    out[os.path.relpath(path, root)] = open(path, "rb").read()
            return out

        # Same inputs, fresh output root: byte-identical files, layout included.
        assert _read_all(first_root) == _read_all(second_root)


def test_plan_is_review_only_until_execute(tmp_path):
    with _pin_evidenced():
        projects, configuration, variants, _validation, generation = _services()
        _project_with_variant(projects, configuration, variants)

        plan = generation.plan(str(tmp_path / "out"))
        assert plan.ok
        # Nothing is on disk before execute (plan §13.3: nothing is written
        # without a reviewed plan being executed).
        assert not (tmp_path / "out").exists()


def test_job_name_agreement_completes_through_app(tmp_path):
    """The Phase 8 checklist note: the job-name/directory agreement completes
    when app passes the derived name into the wire document."""
    with _pin_evidenced():
        projects, configuration, variants, _validation, generation = _services()
        _project_with_variant(projects, configuration, variants)

        plan = generation.plan(str(tmp_path / "out"))
        assert plan.ok
        result = generation.execute(plan)
        assert result.ok
        written_file = next(
            path for path in result.written if path.endswith(".json") and "manifest" not in path
        )
        document = json.loads(open(written_file, encoding="utf-8").read())
        directory = os.path.basename(os.path.dirname(written_file))
        assert document["name"] == directory
        assert os.path.basename(written_file) == directory + ".json"


# -- the blocked path -----------------------------------------------------------------


def test_blocking_finding_stops_generation_before_any_write(tmp_path):
    with _pin_evidenced():
        projects, configuration, variants, _validation, generation = _services()
        _project_with_variant(projects, configuration, variants)
        # A relational ERROR the constructors cannot see (R-ENT-007's domain):
        # a modification pointing beyond the end of the sequence.
        configuration.add_modification("A", "P", 99)

        plan = generation.plan(str(tmp_path / "out"))
        assert not plan.ok
        assert plan.failure_reason == FailureReason.VALIDATION_BLOCKED
        assert not (tmp_path / "out").exists()  # nothing written


def test_execute_never_writes_after_a_failed_plan(tmp_path):
    with _pin_evidenced():
        projects, configuration, variants, _validation, generation = _services()
        _project_with_variant(projects, configuration, variants)
        configuration.add_modification("A", "P", 99)

        failed = generation.plan(str(tmp_path / "out"))
        assert not failed.ok
        result = generation.execute(failed)
        assert not result.ok
        assert result.written == ()
        assert not (tmp_path / "out").exists()


def test_generation_without_project_reports_not_open(tmp_path):
    with _pin_evidenced():
        projects, _configuration, _variants, validation, generation = _services()
        assert not validation.validate_base().ok
        plan = generation.plan(str(tmp_path / "out"))
        assert not plan.ok
        assert plan.failure_reason == FailureReason.NOT_OPEN


def test_empty_expansion_blocks_generation(tmp_path):
    with _pin_evidenced():
        projects, configuration, variants, _validation, generation = _services()
        projects.new("E2E Job")
        configuration.set_format_target(version=3, evidence="PIN-001")
        configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")

        plan = generation.plan(str(tmp_path / "out"))
        assert not plan.ok
        assert plan.failure_reason == FailureReason.EMPTY_EXPANSION


def test_duplicate_identifier_across_records_becomes_r_ent_002(tmp_path):
    """The Phase 4 boundary conversion, seen from the app layer: hand-built
    records claiming one identifier surface as an R-ENT-002 finding, and a
    finding — never an exception — blocks generation."""
    from configbuilder.identity import IdentityRegistry, Multiplicity
    from configbuilder.model import (
        Configuration,
        ConfigurationMetadata,
        FamilyARecord,
        FamilyBRecord,
        FormatTarget,
        Pinned,
        SeedSet,
    )

    registry = IdentityRegistry()
    configuration = Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1]),
        records=(
            FamilyARecord(ids=Multiplicity(["A"]), sequence=SequenceText("PEPT", "protein")),
            FamilyBRecord(ids=Multiplicity(["A"]), sequence=SequenceText("GGCC", "rna")),
        ),
        identity=registry,
    ).with_format_target(FormatTarget(version_selection=Pinned(3, evidence="PIN-001")))
    from configbuilder.persistence import Project as _Project

    projects = ProjectService()
    projects._replace_project(_Project(configuration=configuration))
    variants = VariantService(projects)
    validation = ValidationService(projects)
    generation = GenerationService(projects, validation, variants)

    with _pin_evidenced():
        report = validation.validate_base()
        assert not report.ok
        assert any(f.rule_id == "R-ENT-002" for f in report.report.findings)
        plan = generation.plan(str(tmp_path / "out"))
        assert not plan.ok
        assert plan.failure_reason == FailureReason.VALIDATION_BLOCKED


# -- service-level units through the same wiring -----------------------------------------


def test_project_service_save_open_round_trip(tmp_path):
    with _pin_evidenced():
        projects, configuration, variants, validation, generation = _services()
        _project_with_variant(projects, configuration, variants)

        path = str(tmp_path / "project.cbproj")
        saved = projects.save_as(path)
        assert saved.ok
        assert not projects.is_dirty

        fresh = ProjectService()
        loaded = fresh.open(path)
        assert loaded.ok, loaded.message
        assert loaded.project is not None
        names = [r.ids.primary.value for r in loaded.project.configuration.records]
        assert len(names) == 3


def test_save_without_path_is_reported_not_raised():
    with _pin_evidenced():
        projects, _configuration, _variants, _validation, _generation = _services()
        projects.new("E2E Job")
        result = projects.save()
        assert not result.ok
        assert result.failure_reason == FailureReason.SAVE_WITHOUT_PATH


def test_variant_service_crud_and_preview(tmp_path):
    with _pin_evidenced():
        projects, configuration, variants, _validation, _generation = _services()
        _project_with_variant(projects, configuration, variants)

        assert variants.duplicate_spec("nob", "nob2", "another").ok
        keys = [spec.key for spec in projects.project.specs]
        assert keys == ["nob", "nob2"]

        preview = variants.preview("nob")
        assert preview.ok
        assert [v.key for v in preview.variants] == ["nob"]

        assert variants.update_spec("nob", label="renamed").ok
        assert variants.remove_spec("nob2").ok
        assert [spec.key for spec in projects.project.specs] == ["nob"]

        missing = variants.remove_spec("ghost")
        assert not missing.ok
        assert missing.failure_reason == FailureReason.UNKNOWN_RECORD


def test_configuration_service_reports_unknown_record():
    with _pin_evidenced():
        projects, configuration, _variants, _validation, _generation = _services()
        projects.new("E2E Job")
        result = configuration.update_record("Z", sequence="PEPT")
        assert not result.ok
        assert result.failure_reason == FailureReason.UNKNOWN_RECORD


def test_validation_service_set_policy_disables_preflight():
    with _pin_evidenced():
        projects, configuration, variants, validation, _generation = _services()
        _project_with_variant(projects, configuration, variants)
        validation.set_policy(run_preflight=False)
        output = validation.validate_base()
        assert output.ok
        assert all(
            finding.rule_id.split("-")[1] != "PRE" for finding in output.report.findings
        )


# -- batch variant generation from a sequence file (batch-variant feature) ----


def test_batch_generation_full_pipeline_writes_independent_variant_files(tmp_path):
    """Base + TXT → N variants → validation → AF3 JSON files.

    The integration proof of the batch feature: three sequences in, three
    independent variants out, every one validated by the normal pipeline
    and serialized by the normal (only) serializer — with the base and
    the DNA duplex untouched.
    """
    import os

    from configbuilder.persistence import read_sequence_file

    with _pin_evidenced():
        projects, configuration, variants, validation, generation = _services()
        projects.new("Batch E2E")
        configuration.set_format_target(version=3, evidence="PIN-001")
        configuration.add_record("protein", "ACDEFGHIKLMNPQRSTVWY")
        configuration.add_record("dna", "ATGC")
        base = projects.project.configuration
        base_record_count = len(base.records)

        seq_file = tmp_path / "seqs.txt"
        seq_file.write_text("MSTNPKP\r\n\r\nGKKIGYS\r\nMSTNPKK\r\n", encoding="utf-8")
        entries = read_sequence_file(str(seq_file))
        assert [text for _, text in entries] == ["MSTNPKP", "GKKIGYS", "MSTNPKK"]

        outcome = variants.generate_from_file(str(seq_file))
        assert outcome.ok, outcome.message
        assert [spec.key for spec in projects.project.specs] == [
            "batch_01",
            "batch_02",
            "batch_03",
        ]

        # the base is unchanged: same object, same records, no batch ids
        assert projects.project.configuration is base
        assert len(base.records) == base_record_count

        # every variant validates through the normal pipeline (drift and
        # identity-stability included)
        validated = validation.validate_all()
        assert not validated.base_report.blocking()
        assert set(validated.variant_reports) == {"batch_01", "batch_02", "batch_03"}
        for key, report in validated.variant_reports.items():
            assert not report.blocking(), (key, [f.user_message for f in report.blocking()])

        # expansion: base records + the duplex + exactly one new protein
        expanded = variants.expand()
        assert expanded.ok
        for variant in expanded.variants:
            records = variant.configuration.records
            assert len(records) == base_record_count + 1
            added = records[-1]
            assert type(added).__name__ == "FamilyARecord"
            assert added.sequence.text in ("MSTNPKP", "GKKIGYS", "MSTNPKK")
            new_id = added.ids.primary.value
            assert new_id not in [
                entity.value for entity in base.identity.order()
            ]

        # serialization: the normal generation sequence writes all three
        plan = generation.plan(str(tmp_path / "out"))
        assert plan.ok, plan.message
        assert plan.conflicts == ()
        names = sorted(os.path.basename(entry.path) for entry in plan.entries)
        # the naming authority slugs keys: ``batch_01`` becomes ``batch-01``
        assert names == [
            "batch-e2e__batch-01.json",
            "batch-e2e__batch-02.json",
            "batch-e2e__batch-03.json",
            "manifest.json",
        ]
        result = generation.execute(plan)
        assert result.ok, result.errors
        written = sorted(os.path.basename(path) for path in result.written)
        assert written == names
        payloads = {}
        for name in names:
            if name != "manifest.json":
                payloads[name] = (
                    tmp_path / "out" / "batch-e2e" / name[: -len(".json")] / name
                ).read_text(encoding="utf-8")
                assert '"name"' in payloads[name]
        # each file carries exactly its own batch sequence, and all three
        # of the file's sequences reached the wire exactly once overall
        seen = [text for payload in payloads.values() for text in ("MSTNPKP", "GKKIGYS", "MSTNPKK") if text in payload]
        assert sorted(seen) == ["GKKIGYS", "MSTNPKK", "MSTNPKP"]
