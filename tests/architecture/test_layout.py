"""Architecture tests: package layout per IMPLEMENTATION_PLAN.md §5.1.

Ten modules, fixed. A new top-level package requires a justification entry
in the plan (§23: "new modules require an entry here").
"""

from __future__ import annotations

from tests.architecture import _scanner

EXPECTED_FAMILIES = {
    "model",
    "identity",
    "validation",
    "transform",
    "serialize",
    "variants",
    "output",
    "persistence",
    "app",
    "ui",
}

EXPECTED_UI_SUBPACKAGES = {"steps", "render", "present"}


def _subdirs(path):
    return {
        p.name
        for p in path.iterdir()
        if p.is_dir() and p.name != "__pycache__"
    }


def test_exactly_ten_top_level_packages():
    top = _subdirs(_scanner.PACKAGE_ROOT)
    assert top == EXPECTED_FAMILIES, top


def test_ui_has_the_three_declared_subpackages():
    ui = _scanner.PACKAGE_ROOT / "ui"
    subpackages = _subdirs(ui)
    assert subpackages == EXPECTED_UI_SUBPACKAGES, subpackages
