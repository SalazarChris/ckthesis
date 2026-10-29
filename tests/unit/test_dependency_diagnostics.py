"""Dependency diagnostics: metadata-driven, read-only, and actionable."""

from __future__ import annotations

import importlib.metadata as metadata
import re
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import check_dependencies as diagnostic


def _requirement_tools():
    return diagnostic._requirement_tools()[0]


def test_project_root_comes_from_the_script_location_not_the_working_directory():
    script = ROOT / "tools" / "check_dependencies.py"
    assert diagnostic.project_root(script) == ROOT
    assert diagnostic.project_root() == ROOT


def test_project_metadata_reads_declared_core_and_optional_groups():
    project = diagnostic.parse_project_metadata(ROOT)
    assert project["requires_python"] == ">=3.9"
    assert project["dependencies"] == ()
    assert project["optional_dependencies"]["gui"] == ("PySide6>=6.6",)
    assert project["optional_dependencies"]["templates"] == ("gemmi>=0.6",)


def test_a_required_distribution_must_exist_and_import(monkeypatch):
    requirement = "Fake-Required>=2"
    checker = diagnostic.check_dependency(
        requirement,
        ("fake_import",),
        get_version=lambda _name: "2.1",
        import_module=lambda name: object() if name == "fake_import" else None,
    )
    assert checker.status == "PASS"

    missing = diagnostic.check_dependency(
        requirement,
        ("fake_import",),
        get_version=lambda _name: (_ for _ in ()).throw(metadata.PackageNotFoundError()),
        import_module=lambda _name: None,
    )
    assert missing.status == "MISSING"
    assert missing.failed


def test_requirement_version_and_import_distribution_mismatch_are_detected():
    too_old = diagnostic.check_dependency(
        "Fake-Required>=2",
        ("fake_import",),
        get_version=lambda _name: "1.9",
        import_module=lambda _name: object(),
    )
    assert too_old.status == "INCOMPATIBLE"
    assert "does not satisfy >=2" in too_old.detail

    wrong_import = diagnostic.check_dependency(
        "Fake-Required>=2",
        ("fake_import",),
        get_version=lambda _name: "2.1",
        import_module=lambda name: (_ for _ in ()).throw(ImportError("module absent")),
    )
    assert wrong_import.status == "MISSING"
    assert "import failed" in wrong_import.detail


def test_an_absent_optional_parser_is_not_fatal_when_the_fallback_works():
    optional = diagnostic.check_dependency(
        "Gemmi>=0.6",
        ("gemmi",),
        get_version=lambda _name: (_ for _ in ()).throw(metadata.PackageNotFoundError()),
        import_module=lambda _name: None,
        required=False,
        fallback_available=True,
    )
    assert optional.status == "OPTIONAL"
    assert not optional.required
    assert not optional.failed


def test_optional_parser_version_and_import_failures_remain_nonfatal_with_fallback():
    old = diagnostic.check_dependency(
        "Gemmi>=0.6", ("gemmi",),
        get_version=lambda _name: "0.5",
        import_module=lambda _name: None,
        required=False,
        fallback_available=True,
    )
    broken_import = diagnostic.check_dependency(
        "Gemmi>=0.6", ("gemmi",),
        get_version=lambda _name: "0.8",
        import_module=lambda _name: (_ for _ in ()).throw(ImportError("broken")),
        required=False,
        fallback_available=True,
    )
    assert old.status == broken_import.status == "OPTIONAL"
    assert "fallback" in old.detail and "fallback" in broken_import.detail


def test_python_compatibility_uses_the_declared_pep440_requirement():
    assert diagnostic.check_python_version(">=3.9", (3, 11, 8)).status == "PASS"
    incompatible = diagnostic.check_python_version(">=3.9", (3, 8, 18))
    assert incompatible.status == "INCOMPATIBLE"
    assert incompatible.failed


def test_dependency_conflict_check_returns_nonzero_status(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "package-a 1.0 has requirement package-b<2, but package-b 2.2 is installed"

    monkeypatch.setattr(diagnostic.subprocess, "run", lambda *args, **kwargs: Result())
    result = diagnostic._pip_check()
    assert result.status == "INCOMPATIBLE"
    assert "package-b" in result.detail
    assert diagnostic.Report([result]).exit_code == 1


def test_a_broken_project_metadata_has_a_nonzero_cli_status(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text("not valid TOML = [", encoding="utf-8")
    status = diagnostic.main(["--root", str(tmp_path)])
    assert status != 0
    assert "INCOMPATIBLE" in capsys.readouterr().out


def test_checker_metadata_names_runtime_imports_and_keeps_dev_separate():
    project = diagnostic.parse_project_metadata(ROOT)
    names = [
        re.split(r"[\[<=>!~ ]", requirement)[0].lower()
        for requirement in project["optional_dependencies"]["gui"]
    ]
    assert names == ["pyside6"]
    assert "pytest>=7" in project["optional_dependencies"]["dev"]
    assert "pytest>=7" not in project["optional_dependencies"]["gui"]


def test_readme_describes_the_windows_scripts_and_remote_boundary():
    guide = (ROOT / "DEPENDENCY_SETUP.md").read_text(encoding="utf-8")
    assert "setup_windows.bat" in guide
    assert "check_dependencies.bat" in guide
    assert "inference" in guide.lower()
