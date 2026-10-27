"""Gate-recovery regressions (docs/GATE_RECOVERY_IMPLEMENTATION_REPORT.md).

Commit ``85a606a`` removed more than the personal AF3 execution-success
gates: it dropped a validation tier from the generation gate, duplicated the
version finding, stopped the manifest recording its validation, and let an
invalid variant generate anyway. Each module below pins one approved
recovery decision, written at the service boundary both front ends share so
the CLI and the GUI cannot disagree.

The through-line every test guards: **nothing here consults AF3.** Validation
asks only the configuration and the shallow ports (filesystem, chemistry). A
valid job is created, saved, reopened and generated without a prediction, a
result directory or a completion marker ever existing.
"""

import json
import os

from configbuilder.app import GenerationService, ValidationService
from configbuilder.app.results import (
    ConfigurationOutput,
    FailureReason,
    VariantValidationOutput,
)
from configbuilder.identity import IdentityRegistry, Multiplicity
from configbuilder.model import (
    DEFAULT_INPUT_VERSION,
    SUPPORTED_INPUT_VERSIONS,
    ByNotation,
    ComponentRecord,
    Configuration,
    ConfigurationMetadata,
    Dialect,
    FamilyARecord,
    FormatTarget,
    Pinned,
    SeedSet,
    SequenceText,
    Unverified,
)
from configbuilder.ui.services import Services, build_services
from configbuilder.validation import NullChemistryProbe, OsFilesystemPort, Report, Tier, validate
from configbuilder.validation.catalogue import RULES, Severity, get_rule
from configbuilder.validation.engine import ValidationContext
from configbuilder.validation.report import FieldPath, Finding
from configbuilder.validation.rules.msa_rules import check_r_msa_006


# -- helpers ---------------------------------------------------------------


def _blocking_ids(outcome):
    return [f.rule_id for f in outcome.report.blocking()]


def _record_key(services, index=0):
    return services.projects._require_project().configuration.records[index].ids.primary.value


def _job(services, name="gate-recovery", sequence="PEPTIDE"):
    """A fresh project with one protein chain and the default pinned version."""
    services.projects.new(name)
    assert services.configuration.add_record("protein", sequence).ok
    return services


def _unverified_target():
    return FormatTarget(version_selection=Unverified(), dialect=Dialect("alphafold3"))


def _services_with_chemistry(probe):
    """The standard wiring with a chemistry probe injected through its port —
    the shape a deployment takes when a real parser is available."""
    base = build_services()
    validation = ValidationService(base.projects, filesystem=OsFilesystemPort(), chemistry=probe)
    generation = GenerationService(base.projects, base.variants, validation=validation)
    return Services(base.projects, base.configuration, base.variants, generation, validation)


def _configuration_with(record, target=None):
    registry = IdentityRegistry()
    entity_id = registry.allocate(owner="test")
    if target is None:
        target = FormatTarget(
            version_selection=Pinned(DEFAULT_INPUT_VERSION), dialect=Dialect("alphafold3")
        )
    return Configuration(
        metadata=ConfigurationMetadata("job"),
        seeds=SeedSet([1]),
        records=(record,),
        identity=registry,
        format_target=target,
    )


def _rejecting_probe():
    """A real parser's shape when it says no: the port a rejecting checker
    presents, not a mock of production behaviour."""

    class _Probe:
        def parses_smiles(self, notation):
            return False

    return _Probe()


def _accepting_probe():
    class _Probe:
        def parses_smiles(self, notation):
            return True

    return _Probe()


def _raising_probe():
    """A parser that raises on malformed input — a real parser's normal way
    of refusing. It must surface as a finding, never escape as a crash."""

    class _Probe:
        def parses_smiles(self, notation):
            raise ValueError("unrecognised token at 0")

    return _Probe()


def _smiles_job(services, name="chem", smiles="C(C)O"):
    """A protein plus a SMILES ligand, built through the service.

    ``representation_kind="smiles"`` is the submenu's explicit choice: without
    it the text is read as CCD component codes instead of a notation.
    """
    services.projects.new(name)
    assert services.configuration.add_record("protein", "PEPTIDE").ok
    added = services.configuration.add_record(
        "ligand", representation=smiles, representation_kind="smiles"
    )
    assert added.ok, added.message
    return services


def _no_variant_drift_warnings(report):
    """The two variant rules warn (not block) when no documents were joined."""
    return [
        f
        for f in report
        if f.rule_id in ("R-VAR-001", "R-VAR-002") and f.severity.value != "WARNING"
    ]


# -- 1. Version ------------------------------------------------------------


def test_new_job_pins_the_default_version_3():
    """A new job defaults to version 3 and is never Unverified, so it is
    immediately saveable with no AF3 run."""
    services = build_services()
    services.projects.new("version-default")
    target = services.projects._require_project().configuration.format_target
    assert DEFAULT_INPUT_VERSION == 3
    assert isinstance(target.version_selection, Pinned)
    assert target.version_selection.version == 3


def test_version_pin_survives_editing_and_saving(tmp_path):
    """The pin is what a save persists, so reopening the file restores the
    same supported version — the version is preserved, not re-derived."""
    services = build_services()
    _job(services)
    assert services.configuration.set_format_target(version=2).ok
    destination = str(tmp_path / "pinned.json")
    plan = services.generation.plan_save(destination)
    assert plan.ok, plan.message
    assert services.generation.execute(plan).ok
    with open(destination, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    assert document.get("version") == 2, sorted(document)


def test_supported_explicit_version_is_preserved():
    services = build_services()
    _job(services)
    for version in SUPPORTED_INPUT_VERSIONS:
        outcome = services.configuration.set_format_target(version=version)
        assert outcome.ok, outcome.message
        target = services.projects._require_project().configuration.format_target
        assert target.version_selection.version == version
        validated = services.validation.validate_base()
        assert validated.ok, _blocking_ids(validated)


def test_unverified_version_produces_exactly_one_finding():
    """The duplicate finding is gone: R-VER-001 owns the missing explicit
    selection, and R-ROOT-002 stays silent when nothing is selected."""
    registry = IdentityRegistry()
    entity_id = registry.allocate(owner="test")
    record = FamilyARecord(
        ids=Multiplicity([entity_id.value]), sequence=SequenceText("PEPTIDE", "protein")
    )
    report = validate(_configuration_with(record, target=_unverified_target()))
    version_ids = [
        f.rule_id for f in report.blocking() if f.rule_id in ("R-VER-001", "R-ROOT-002")
    ]
    assert version_ids == ["R-VER-001"]


def test_valid_json_saves_without_any_af3_run(tmp_path):
    """Opening, editing and saving a valid JSON needs no prediction result, no
    result directory and no completion marker."""
    services = build_services()
    _job(services)
    destination = str(tmp_path / "job.json")
    plan = services.generation.plan_save(destination)
    assert plan.ok, plan.message
    result = services.generation.execute(plan)
    assert result.ok, result.message
    assert os.path.isfile(destination)


# -- 2. External MSA -------------------------------------------------------


def test_automatic_msa_configuration_stays_valid(tmp_path):
    """Automatic search configures no file and must never be reported: the
    MSA rule must not make a file mandatory."""
    services = build_services()
    _job(services)
    assert services.configuration.set_alignment(_record_key(services), "automatic").ok
    outcome = services.validation.validate_base()
    assert outcome.ok, _blocking_ids(outcome)


def test_valid_external_msa_file_passes(tmp_path):
    msa = tmp_path / "hits.a3m"
    msa.write_text(">query\nPEPTIDE\n>hit\nPEPTIDER\n", encoding="utf-8")
    services = build_services()
    _job(services)
    assert services.configuration.set_alignment(
        _record_key(services), "unpaired", external_path=str(msa)
    ).ok
    outcome = services.validation.validate_base()
    assert outcome.ok, _blocking_ids(outcome)


def test_missing_external_msa_file_blocks_save(tmp_path):
    """An explicitly configured MSA path that does not exist blocks the save
    through the shared gate — the operation boundary, not a display-only
    warning."""
    services = build_services()
    _job(services)
    assert services.configuration.set_alignment(
        _record_key(services), "unpaired", external_path=str(tmp_path / "gone.a3m")
    ).ok
    outcome = services.validation.validate_base()
    assert not outcome.ok
    assert "R-MSA-006" in _blocking_ids(outcome)
    refused = services.generation.plan_save(str(tmp_path / "job.json"))
    assert not refused.ok
    assert refused.failure_reason is FailureReason.VALIDATION_BLOCKED


def test_empty_external_msa_file_is_not_usable(tmp_path):
    """An empty file is not a usable MSA: the shallow contract is exists +
    regular file + readable + non-empty."""
    msa = tmp_path / "empty.a3m"
    msa.write_text("", encoding="utf-8")
    services = build_services()
    _job(services)
    services.configuration.set_alignment(_record_key(services), "unpaired", external_path=str(msa))
    outcome = services.validation.validate_base()
    assert not outcome.ok
    assert "R-MSA-006" in _blocking_ids(outcome)


def test_directory_path_is_not_a_usable_msa(tmp_path):
    services = build_services()
    _job(services)
    services.configuration.set_alignment(_record_key(services), "unpaired", external_path=str(tmp_path))
    outcome = services.validation.validate_base()
    assert not outcome.ok
    assert "R-MSA-006" in _blocking_ids(outcome)


def test_paired_and_unpaired_sources_stay_supported(tmp_path):
    """Separate paired and unpaired files remain a legal configuration: the
    file check validates each file, never demands a second source."""
    unpaired = tmp_path / "unpaired.a3m"
    unpaired.write_text(">query\nPEPTIDE\n", encoding="utf-8")
    paired = tmp_path / "paired.a3m"
    paired.write_text(">query\nPEPTIDE\n", encoding="utf-8")
    services = build_services()
    _job(services)
    outcome = services.configuration.set_alignment(
        _record_key(services),
        "both",
        external_path=str(unpaired),
        paired_external_path=str(paired),
    )
    assert outcome.ok, outcome.message
    validated = services.validation.validate_base()
    assert validated.ok, _blocking_ids(validated)


def test_r_msa_006_null_port_reports_not_checked_not_error():
    """With no filesystem port the rule must not invent a false error: it
    downgrades to a WARNING 'not checked' (plan 9.6)."""
    services = build_services()
    _job(services)
    services.configuration.set_alignment(
        _record_key(services), "unpaired", external_path="/nonexistent/x.a3m"
    )
    configuration = services.projects._require_project().configuration
    report = Report()
    check_r_msa_006(
        configuration, report, get_rule("R-MSA-006"), ValidationContext(filesystem=None)
    )
    assert report.blocking() == ()
    assert [f.rule_id for f in report.findings] == ["R-MSA-006"]
    assert report.findings[0].severity.value == "WARNING"


# -- 3. Chemistry ----------------------------------------------------------


def test_invalid_smiles_blocks_with_a_real_probe(tmp_path):
    """With a real probe wired, an unparseable SMILES is a blocking finding —
    not a warning that save ignores (the gate includes PREFLIGHT)."""
    services = _services_with_chemistry(_rejecting_probe())
    _smiles_job(services, smiles="not-smiles")
    outcome = services.validation.validate_base()
    assert not outcome.ok
    assert "R-ENT-010" in _blocking_ids(outcome)
    refused = services.generation.plan_save(str(tmp_path / "job.json"))
    assert not refused.ok
    assert refused.failure_reason is FailureReason.VALIDATION_BLOCKED


def test_valid_smiles_passes_a_real_probe():
    services = _services_with_chemistry(_accepting_probe())
    _smiles_job(services, smiles="C(C)O")
    outcome = services.validation.validate_base()
    assert outcome.ok, _blocking_ids(outcome)


def test_probe_error_is_reported_not_raised():
    """A parser that raises produces a blocking finding naming the failure and
    never escapes into the CLI or GUI."""
    services = _services_with_chemistry(_raising_probe())
    _smiles_job(services, smiles="not-smiles")
    outcome = services.validation.validate_base()
    assert not outcome.ok
    findings = [f for f in outcome.report.blocking() if f.rule_id == "R-ENT-010"]
    assert findings
    assert "could not be checked" in findings[0].user_message


def test_no_probe_at_all_downgrades_to_warning(tmp_path):
    """A caller that wires *nothing* is told so, and the advisory never blocks
    a save (plan §9.6). ``build_services`` wires the bundled grammar probe; a
    caller with no checker is the ``NullChemistryProbe`` case pinned here."""
    services = _services_with_chemistry(NullChemistryProbe())
    _smiles_job(services, smiles="not-smiles")
    report = services.validation.validate_base().report
    ent = [f for f in report.findings if f.rule_id == "R-ENT-010"]
    assert ent, [f.rule_id for f in report]
    assert ent[0].severity.value == "WARNING"
    assert "not checked" in ent[0].user_message
    plan = services.generation.plan_save(str(tmp_path / "job.json"))
    assert plan.ok, plan.message


def test_production_wiring_claims_grammar_only(tmp_path):
    """What the shipped bundle checks, and what it still does not.

    ``build_services`` wires the bundled grammar probe, so notation that is
    not SMILES is a blocking finding with the reason quoted, while a
    notation this check cannot judge is left alone: chemistry is still the
    external parser's business (plan §9.6), and no dependency was taken on one.
    """
    from configbuilder.ui.services import build_services

    services = build_services()
    _smiles_job(services, smiles="not-smiles")
    report = services.validation.validate_base().report
    ent = [f for f in report.findings if f.rule_id == "R-ENT-010"]
    assert ent and ent[0].severity.value == "ERROR"
    assert "not one SMILES writes without brackets" in ent[0].user_message
    refused = services.generation.plan_save(str(tmp_path / "job.json"))
    assert not refused.ok

    # Grammatical but chemically impossible: still written, because valence is
    # not a grammar question and this check does not pretend otherwise.
    lenient = build_services()
    _smiles_job(lenient, smiles="C(C)(C)(C)(C)C")
    assert [
        f
        for f in lenient.validation.validate_base().report.findings
        if f.rule_id == "R-ENT-010"
    ] == []


# -- 4. Variant generation -------------------------------------------------


def _variant_job(services, name="variant-gate"):
    """A protein job with one declared sequence-change variant."""
    _job(services, name=name)
    added = services.variants.add_spec_with_edit(
        "v1", "sub-1", "sequence", "APETIDE", record_key=_record_key(services)
    )
    assert added.ok, added.message
    return services


def test_valid_variant_passes_the_gate():
    """A valid variant is not refused by validation: drift and identity checks
    pass, so generation is free to write."""
    services = _variant_job(build_services())
    detail = services.validation.validate_all()
    assert detail.failure_reason is None, detail.message
    assert all(not report.blocking() for report in detail.variant_reports.values()), {
        key: [f.rule_id for f in report.blocking()]
        for key, report in detail.variant_reports.items()
    }


def test_invalid_base_cannot_bypass_the_gate(tmp_path):
    """An invalid base cannot generate by hiding inside a variant run."""
    services = build_services()
    _job(services)
    added = services.variants.add_spec_with_edit(
        "v1", "sub-1", "sequence", "APETIDE", record_key=_record_key(services)
    )
    assert added.ok, added.message
    assert services.configuration.unset_format_target().ok

    plan = services.generation.plan(str(tmp_path / "out"))
    assert not plan.ok
    assert plan.failure_reason is FailureReason.VALIDATION_BLOCKED


def test_variant_generation_needs_no_prior_af3_run(tmp_path):
    """Variant enforcement must not require the base job to have run: this
    project has never been predicted and a valid variant clears the gate."""
    services = _variant_job(build_services(), name="no-run")
    plan = services.generation.plan(str(tmp_path / "out"))
    assert plan.failure_reason is not FailureReason.VALIDATION_BLOCKED, plan.message


def test_blocking_variant_leaves_no_partial_output(tmp_path):
    """When validation blocks, the refusal happens before any write: the
    output directory must not exist afterwards."""
    services = build_services()
    _job(services, name="no-partial")
    assert services.variants.add_spec_with_edit(
        "v1", "sub-1", "sequence", "APETIDE", record_key=_record_key(services)
    ).ok
    assert services.configuration.unset_format_target().ok

    out = tmp_path / "out"
    plan = services.generation.plan(str(out))
    assert not plan.ok
    assert not out.exists()


class _BlockedVariantValidator:
    """A validator whose *variant* half is blocked.

    The R-VAR findings themselves are produced by real rule code and tested in
    ``tests/unit/validation/test_variant_rules.py`` against hand-built wire
    documents — the only way to reach an out-of-region difference, because a
    committed spec cannot drift on its own. This stub pins the other half of
    the contract: ``GenerationService`` treats such a report as a refusal of
    the run, never as a message meant only for the Variants page.
    """

    def __init__(self, detail):
        self._detail = detail

    def validate_base(self, tiers=None):
        return ConfigurationOutput(ok=True, report=Report())

    def validate_all(self, only=None):
        return self._detail


def test_a_blocking_variant_refuses_generation_before_any_write(tmp_path):
    """Drift found by the variant tier stops the run instead of being shown
    and ignored; nothing is transformed and no output directory appears."""
    services = _variant_job(build_services(), name="variant-scope")
    report = Report()
    report.add(
        Finding(
            rule_id="R-VAR-001",
            severity=Severity.ERROR,
            user_message="Variant 'v1' changed fields that no declared edit explains.",
            diagnostic="unattributed wire differences: sequences/0/protein/sequence",
            paths=(FieldPath("Configuration", "v1", ""),),
        )
    )
    detail = VariantValidationOutput(
        base_report=Report(), variant_reports={"v1": report}
    )
    generation = GenerationService(
        services.projects,
        services.variants,
        validation=_BlockedVariantValidator(detail),
    )
    out = tmp_path / "out"
    plan = generation.plan(str(out))
    assert not plan.ok
    assert plan.failure_reason is FailureReason.VALIDATION_BLOCKED
    assert plan.refused_scope == "variant"
    assert "v1" in plan.message
    assert [finding.rule_id for finding in plan.findings] == ["R-VAR-001"]
    assert not out.exists()


# -- 5. Readiness and manifests -------------------------------------------


def test_blocking_chemistry_finding_agrees_between_status_and_save(tmp_path):
    """The audited scenario, fixed: status.ready False implies save is refused,
    for a real blocking chemistry finding."""
    services = _services_with_chemistry(_rejecting_probe())
    services.projects.new("readiness-agrees")
    assert services.configuration.add_record("protein", "PEPTIDE").ok
    assert services.configuration.add_record(
        "ligand", representation="C1CC", representation_kind="smiles"
    ).ok

    status = services.validation.status()
    plan = services.generation.plan_save(str(tmp_path / "job.json"))
    assert status is not None and not status.ready, "expected a blocking chemistry finding"
    assert not plan.ok, "status said not ready but save succeeded"
    assert plan.failure_reason is FailureReason.VALIDATION_BLOCKED


def test_advisory_warnings_do_not_block_a_valid_save(tmp_path):
    """A report carrying only advisory findings still saves: INFO and WARNING
    are not turned into blockers."""
    services = build_services()
    _job(services)
    report = services.validation.validate_base().report
    assert list(report.blocking()) == []
    assert _no_variant_drift_warnings(report) == []
    assert len(report) > 0, "expected the usual advisory findings on a valid job"
    plan = services.generation.plan_save(str(tmp_path / "job.json"))
    assert plan.ok, plan.message


def test_generated_manifest_records_the_validation_summary(tmp_path):
    """The manifest carries the base-plus-variant report the gate produced for
    exactly the configurations written."""
    services = _variant_job(build_services(), name="manifest-report")
    plan = services.generation.plan(str(tmp_path / "out"))
    assert plan.ok, plan.message
    manifest_paths = [e.path for e in plan.entries if e.path.endswith("manifest.json")]
    assert manifest_paths, [e.path for e in plan.entries]

    result = services.generation.execute(plan)
    assert result.ok, result.message
    with open(manifest_paths[0], "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    summary = manifest["validation_summary"]
    assert summary, sorted(manifest)
    # The summary describes the configurations actually written: it counts the
    # findings of the report the gate produced, and skips nothing silently.
    assert "finding_counts" in summary, summary
    assert "skipped_rules" in summary, summary


# -- 6. Gate-removal regressions ------------------------------------------


def test_no_hidden_execution_status_gate():
    """No rule consults a prediction, a result directory or a completion
    marker: every rule is decidable from the configuration and the shallow
    ports alone."""
    import inspect

    from configbuilder.validation import rules as rules_pkg

    family_by_prefix = {
        "R-ROOT": "root_rules",
        "R-ENT": "entity_rules",
        "R-MSA": "msa_rules",
        "R-TPL": "template_rules",
        "R-BND": "bond_rules",
        "R-VER": "policy_rules",
        "R-POL": "policy_rules",
        "R-VAR": "variant_rules",
    }
    for rule in RULES:
        module = getattr(rules_pkg, family_by_prefix[rule.rule_id.rsplit("-", 1)[0]])
        check = getattr(module, "check_" + rule.rule_id.lower().replace("-", "_"), None)
        if check is None:
            continue
        source = inspect.getsource(check).lower()
        for marker in ("result_dir", "prediction", "completed", "ranking_score", "af3_run"):
            assert marker not in source, (rule.rule_id, marker)


def test_reopening_a_saved_job_needs_no_af3_output(tmp_path):
    """Round-trip: save a job, reopen the project it came from, and validate
    again — with no prediction anywhere on disk."""
    services = build_services()
    _job(services, name="round-trip")
    document_path = str(tmp_path / "round-trip.json")
    plan = services.generation.plan_save(document_path)
    assert plan.ok, plan.message
    assert services.generation.execute(plan).ok

    reopened = build_services()
    preview = reopened.projects.import_json_preview(document_path)
    assert preview.ok, preview.message
    loaded = reopened.projects.import_json_commit(document_path)
    assert loaded.ok, loaded.message
    outcome = reopened.validation.validate_base()
    assert outcome.ok, _blocking_ids(outcome)
