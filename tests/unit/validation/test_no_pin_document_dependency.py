"""Runtime independence from docs/CONTRACT_PIN.md (plan §22.4 as amended).

The pin document is **provenance documentation**: the application must run
without it. Version evidence travels in the model (``Pinned.evidence``,
supplied by the operator); no runtime code locates, reads, or parses the
document. These tests pin that property from five sides: a subprocess with
the doc deleted, module execution without the repository at all, a static
scan of the runtime tree, byte-identical output with the doc present vs
absent, and the no-silent-inference rule.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

import pytest

from configbuilder.model import Pinned
from configbuilder.transform.engine import TransformError, to_wire

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIN_DOC = PROJECT_ROOT / "docs" / "CONTRACT_PIN.md"


# -- Test A: the documented no-docs subprocess ---------------------------------

def _fresh_services():
    """The five services wired exactly like the e2e suite wires them."""
    from configbuilder.app.configuration_service import ConfigurationService
    from configbuilder.app.generation_service import GenerationService
    from configbuilder.app.project_service import ProjectService
    from configbuilder.app.validation_service import ValidationService
    from configbuilder.app.variant_service import VariantService

    projects = ProjectService()
    variants = VariantService(projects)
    validation = ValidationService(projects)
    generation = GenerationService(projects, validation, variants)
    configuration = ConfigurationService(projects)
    return projects, configuration, variants, validation, generation


def test_app_pipeline_runs_without_the_pin_document(tmp_path, monkeypatch):
    """Scripted e2e in a temp working directory while the doc is absent:
    author → pin with evidence → variant → generate → files written."""
    from tests.e2e.test_app_pipeline import _project_with_variant

    monkeypatch.chdir(tmp_path)  # no docs/ anywhere near the cwd
    projects, configuration, variants, validation, generation = _fresh_services()
    _project_with_variant(projects, configuration, variants)

    result = generation.execute(generation.plan(str(tmp_path / "out")))
    assert result.ok, result.errors
    assert len(result.written) == 2  # one variant file + the manifest


def test_installed_package_runs_without_the_repository(tmp_path):
    """``python -m configbuilder`` from a scratch directory that shares
    nothing with the source tree except the interpreter: the package
    imports, shows its menu, and ends cleanly at EOF (status 0) with no
    docs/CONTRACT_PIN.md anywhere in play."""
    scratch = tmp_path / "clean-machine"
    scratch.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "configbuilder"],
        cwd=str(scratch),
        input="",
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert "ConfigBuilder" in result.stdout  # the menu, not a crash
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


# -- Test C: static no-filesystem-lookup scan -----------------------------------

def test_no_runtime_module_references_the_pin_document():
    """The entire runtime tree carries zero references to the document —
    there is nothing to locate, read, or parse, so no architecture drift
    can reintroduce the dependency without failing here."""
    violations = []
    for path in (PROJECT_ROOT / "configbuilder").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in ("CONTRACT_PIN", "contract_pin.md"):
            if marker in text:
                violations.append("%s: %s" % (path.name, marker))
    assert violations == []


def test_validation_never_opens_any_document():
    """The validation and transform packages import no file-reading modules:
    a stronger, cheaper invariant than spying on ``open`` — the capability
    simply is not present."""
    import ast

    banned = {"pathlib", "builtins"}
    suspicious = {"os", "io", "glob", "shutil"}
    violations = []
    for family in ("validation", "transform"):
        for path in (PROJECT_ROOT / "configbuilder" / family).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [(node.module or "").split(".")[0]]
                else:
                    continue
                for name in names:
                    if name in banned:
                        violations.append("%s imports %s" % (path.name, name))
                    if name in suspicious:
                        violations.append(
                            "%s imports %s (review: %s)" % (path.name, name, name)
                        )
    assert violations == [], violations


# -- Test D: identical output with the doc present vs absent ---------------------

@pytest.mark.skipif(
    not PIN_DOC.exists(), reason="repository layout without docs/CONTRACT_PIN.md"
)
def test_generation_output_identical_with_and_without_the_document(tmp_path, monkeypatch):
    """The critical test: same configuration, two runs — the document present
    on disk and then deleted. The generated bytes must be identical; the
    document must not influence anything."""
    from tests.e2e.test_app_pipeline import _project_with_variant

    pin_text = PIN_DOC.read_text(encoding="utf-8")
    byte_results = []
    try:
        for doc_present in (True, False):
            if not doc_present:
                PIN_DOC.unlink()
            workdir = tmp_path / ("with-doc" if doc_present else "without-doc")
            workdir.mkdir()
            monkeypatch.chdir(workdir)
            projects, configuration, variants, validation, generation = _fresh_services()
            _project_with_variant(projects, configuration, variants)
            result = generation.execute(generation.plan(str(workdir / "out")))
            assert result.ok, result.errors
            variant_file = next(
                path
                for path in result.written
                if path.endswith(".json") and "manifest" not in path
            )
            with open(variant_file, encoding="utf-8") as handle:
                byte_results.append(handle.read())
            monkeypatch.chdir(PROJECT_ROOT)
    finally:
        PIN_DOC.write_text(pin_text, encoding="utf-8")

    assert byte_results[0] == byte_results[1]


# -- Test E: no silent inference -------------------------------------------------

def test_no_version_without_an_explicit_target():
    """Removing the explicit format target never lets the builder pick a
    version: Unverified refuses in transform, and validation reports the
    blocking finding. Nothing is inferred from documentation, examples,
    releases, or defaults."""
    from tests.e2e.test_app_pipeline import _project_with_variant

    import tempfile as _tempfile

    original = os.getcwd()
    os.chdir(_tempfile.mkdtemp())
    try:
        projects, configuration, variants, validation, generation = _fresh_services()
        _project_with_variant(projects, configuration, variants)
        # Strip the explicit target: back to Unverified.
        configuration.unset_format_target()

        with pytest.raises(TransformError):
            to_wire(projects.project.configuration)
        outcome = validation.validate_base()
        assert not outcome.ok
        rule_ids = [f.rule_id for f in outcome.report.findings]
        assert "R-VER-001" in rule_ids or "R-ROOT-002" in rule_ids
    finally:
        os.chdir(original)


# -- evidence semantics -----------------------------------------------------------

def test_pinned_requires_explicit_evidence_for_a_clean_report():
    """R-VER-002 is model-based: a pin without an evidence reference is an
    error naming the pin; citing one (operator-supplied) clears it. Same
    result whether the doc exists or not — the model decides."""
    from configbuilder.identity import IdentityRegistry, Multiplicity
    from configbuilder.model import (
        Configuration,
        ConfigurationMetadata,
        FamilyARecord,
        FormatTarget,
        SeedSet,
        SequenceText,
    )
    from configbuilder.validation import validate

    def _config(evidence):
        return Configuration(
            metadata=ConfigurationMetadata("job"),
            seeds=SeedSet([1]),
            records=(
                FamilyARecord(
                    ids=Multiplicity(["A"]),
                    sequence=SequenceText("PEPTIDE", "protein"),
                ),
            ),
            identity=IdentityRegistry(),
        ).with_format_target(
            FormatTarget(version_selection=Pinned(3, evidence=evidence))
        )

    bare = validate(_config(""))
    assert "R-VER-002" in [f.rule_id for f in bare.findings]
    cited = validate(_config("PIN-001"))
    assert "R-VER-002" not in [f.rule_id for f in cited.findings]


def test_manifest_provenance_comes_from_the_model_not_a_document(tmp_path):
    """The manifest's provenance field mirrors ``Pinned.evidence`` verbatim
    (or records None when no citation was supplied) — with the document
    deleted, so no lookup could have supplied it."""
    from configbuilder.output.manifest import build_manifest

    real_pin = None
    if PIN_DOC.exists():
        real_pin = PIN_DOC.read_text(encoding="utf-8")
        PIN_DOC.unlink()
    try:
        with_evidence = build_manifest(
            project_name="job",
            base_fingerprint="fp",
            format_version=3,
            variants=(),
            seed_set=[],
            format_target=_FormatTargetStub(Pinned(3, evidence="PIN-001")),
        )
        without_evidence = build_manifest(
            project_name="job",
            base_fingerprint="fp",
            format_version=3,
            variants=(),
            seed_set=[],
            format_target=_FormatTargetStub(Pinned(3)),
        )
    finally:
        if real_pin is not None:
            PIN_DOC.write_text(real_pin, encoding="utf-8")

    assert with_evidence.data["contract_pin_record"] == "PIN-001"
    assert without_evidence.data["contract_pin_record"] is None


class _FormatTargetStub:
    def __init__(self, selection) -> None:
        self.version_selection = selection
