"""Golden fixture tests (CHECKLIST Phase 6, plan §13, §15).

A golden fixture is the exact byte sequence ``encode(to_wire(c))``
produces for a configuration described by its recipe. The comparison runs
the *current* pipeline and requires byte identity with the committed
``golden.json`` — so any change to transformation or serialization output
surfaces as a reviewed diff, never a silent drift.

Provenance is part of the fixture (plan §15): ``golden/project/`` holds
configurations authored in this repository (recipe.json is the record);
``golden/external/`` is reserved for inputs the deployment actually
accepted, each carrying its own ``provenance.json`` (Phase 0 probe —
still pending, so the directory is legitimately empty today).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fixtures.golden.build_fixture import build, fixture_dirs  # noqa: E402

GOLDEN_ROOT = REPO_ROOT / "fixtures" / "golden"


def _project_fixtures():
    return sorted(p for p in (GOLDEN_ROOT / "project").glob("*/") if p.is_dir())


def test_every_project_fixture_matches_its_recipe():
    """Byte identity between the committed golden file and a fresh
    pipeline run over the recipe."""
    assert _project_fixtures(), "no project golden fixtures found"
    for directory in _project_fixtures():
        golden = directory / "golden.json"
        assert golden.exists(), "%s has a recipe but no golden.json; run build_fixture.py" % directory.name
        fresh = build(directory)
        committed = golden.read_bytes()
        assert fresh == committed, (
            "%s: golden bytes differ from a fresh encode(to_wire()) run; "
            "review the diff and regenerate deliberately with "
            "build_fixture.py if the change is intended" % directory.name
        )


def test_project_fixtures_have_recipe_and_golden():
    for directory in _project_fixtures():
        assert (directory / "recipe.json").exists(), directory.name
        assert (directory / "golden.json").exists(), directory.name


def test_golden_files_follow_the_encoding_policy():
    for golden in GOLDEN_ROOT.glob("project/*/golden.json"):
        data = golden.read_bytes()
        assert not data.startswith(b"\xef\xbb\xbf"), golden.name
        assert data.endswith(b"\n") and not data.endswith(b"\n\n"), golden.name
        assert b"\r" not in data, golden.name


def test_every_golden_declares_provenance():
    """Plan §15: golden fixtures are provenance-labelled. ``project/`` is
    the label for recipe-backed fixtures; ``external/`` entries must carry
    their own ``provenance.json`` (deployment evidence)."""
    for directory in GOLDEN_ROOT.glob("*"):
        if not directory.is_dir() or directory.name == "__pycache__":
            continue
        if directory.name == "project":
            for fixture in _project_fixtures():
                assert (fixture / "recipe.json").exists(), (
                    "%s: project fixture without a recipe (no provenance)" % fixture.name
                )
        elif directory.name == "external":
            for fixture in directory.glob("*/"):
                assert (fixture / "provenance.json").exists(), (
                    "%s: external fixture without provenance.json" % fixture.name
                )
        else:
            raise AssertionError(
                "unexpected directory under fixtures/golden/: %s" % directory.name
            )


def test_fixture_directory_layout_is_not_accidental():
    """Guard the Phase 0 scaffold contract: exactly project/ + external/."""
    names = {p.name for p in GOLDEN_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert names == {"project", "external"}
