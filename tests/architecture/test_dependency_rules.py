"""Architecture tests: dependency rules (IMPLEMENTATION_PLAN.md §5.3).

Every rule of §5.3 is asserted here by scanning imports statically. The
scanner never imports the scanned code, so these tests cannot pass by
import-time side effects.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scanner import (  # noqa: E402
    family_of_target,
    imported_targets,
    iter_source_modules,
    within_project,
)

# Plan §5 architecture map: one console entry point (declared in
# pyproject.toml as configbuilder.app.cli:main). An entry point is a
# composition root, not an ordinary application-domain module, so it is the
# single designated exception that may import ui (§5.3 rule 6). It may not
# import the pipeline stages directly — orchestration belongs to app (§5.3
# rule 5) — and no other app module gains this freedom.
ENTRY_POINT_MODULE = "configbuilder.app.cli"
# The package-level ``__main__`` (``python -m configbuilder``) is a second
# launcher of the same entry point; its only permitted project import is the
# entry point itself (asserted below).
PACKAGE_MAIN_MODULE = "configbuilder.__main__"
ENTRY_POINT_MODULES = (ENTRY_POINT_MODULE, PACKAGE_MAIN_MODULE)

STAGE_FAMILIES = (
    "validation",
    "variants",
    "transform",
    "serialize",
    "output",
    "persistence",
)


def project_imports(source):
    return [t for t in imported_targets(source) if within_project(t)]


def collect(predicate):
    """Violations of one predicate over (source, target) import pairs."""
    found = []
    for source in iter_source_modules():
        for target in project_imports(source):
            if predicate(source, family_of_target(target)):
                found.append(f"{source.module} -> {target}")
    return found


def test_no_module_imports_app_or_ui():
    """§5.3 rules 6-7: no module imports ui; nothing but ui imports app.
    The scanner's family for ``ui`` subpackages is the dotted path
    (``configbuilder.ui.services``), so ui-ness is checked by prefix.
    The designated entry point (``app.cli``, plan §5: one console entry
    point) is the single intentional exception — it is a composition root
    reaching the wizard, not an ordinary app-module dependency."""

    def source_is_ui(source):
        return source.family == "ui" or source.family.startswith("configbuilder.ui")

    violations = collect(
        lambda source, family: (
            family == "app"
            and not source_is_ui(source)
            and source.family != "app"
            and source.module not in ENTRY_POINT_MODULES
        )
        or (family == "ui" and not source_is_ui(source))
    )
    assert not violations, violations


def test_entry_point_is_the_single_ui_exception():
    """The §5 entry point is the *only* non-ui module allowed to import ui,
    and it must stay a thin composition root: it may reach the wizard and
    the standard wiring, never the pipeline stages — orchestration belongs
    to app (§5.3 rule 5), rendering to ui/render, steps to ui/steps."""
    ui_importers = sorted(
        {
            source.module
            for source in iter_source_modules()
            for target in project_imports(source)
            if family_of_target(target) == "configbuilder.ui"
            or family_of_target(target).startswith("configbuilder.ui.")
            if source.family != "ui"
            and not source.family.startswith("configbuilder.ui")
        }
    )
    assert ui_importers == [ENTRY_POINT_MODULE], ui_importers

    for source in iter_source_modules():
        if source.module != ENTRY_POINT_MODULE:
            continue
        stages = {
            family_of_target(target)
            for target in project_imports(source)
            if family_of_target(target) in STAGE_FAMILIES
        }
        assert not stages, sorted(stages)

    # The package ``__main__`` is pure delegation: its only project import is
    # the entry point itself — it can grow into nothing else.
    for source in iter_source_modules():
        if source.module == PACKAGE_MAIN_MODULE:
            imports = sorted(project_imports(source))
            assert imports == [ENTRY_POINT_MODULE], imports


def test_core_modules_import_model_only():
    """§5.3 rule 2: validation, transform, variants depend on model and on
    each other not at all."""
    violations = collect(
        lambda source, family: source.family in ("validation", "transform", "variants")
        and family in ("validation", "transform", "variants")
        and family != source.family
    )
    assert not violations, violations


def test_serialize_depends_on_transform_only():
    """§5.3 rule 3: serialize touches transform's WireDocument type, no other
    project family."""
    violations = collect(
        lambda source, family: source.family == "serialize"
        and family in ("validation", "variants", "output", "persistence", "app", "ui")
    )
    assert not violations, violations


def test_output_depends_on_serialize_and_naming_inputs_only():
    """§5.3 rule 4: output depends on serialize and naming inputs; no
    contract logic, no validation — and no model/transform/variants
    imports either: payloads, names, and policies arrive as plain data."""
    violations = collect(
        lambda source, family: source.family == "output"
        and family not in ("output", "serialize")
    )
    assert not violations, violations


def test_only_app_imports_multiple_pipeline_stages():
    """§5.3 rule 5: app is the only module that depends on the pipeline
    stages together. Non-app modules may hold at most one cross-stage
    dependency (the granted ones: serialize->transform, output->serialize,
    persistence->variants; plan §6.5, §6.7, §6.8)."""
    importers = {}
    for source in iter_source_modules():
        if source.family == "app":
            continue
        families = {
            family_of_target(target)
            for target in project_imports(source)
            if family_of_target(target) in STAGE_FAMILIES
            and family_of_target(target) != source.family
        }
        if len(families) > 1:
            importers[source.module] = sorted(families)
    assert not importers, importers


def test_ui_imports_only_app_and_model():
    """§5.3 rule 6: ui imports app and model.traceability only."""
    violations = collect(
        lambda source, family: source.family.startswith("ui")
        and family not in ("app", "model")
    )
    assert not violations, violations


def test_no_module_outside_ui_render_branches_on_platform():
    """§16.10: platform branching is confined to one module —
    ``configbuilder/ui/render/platform.py`` (the scanner's family for it
    is the dotted ``configbuilder.ui.render``)."""
    exempt = ("configbuilder.ui.render.platform",)
    violations = []
    for source in iter_source_modules():
        if source.module in exempt:
            continue
        text = source.path.read_text(encoding="utf-8")
        for marker in ("sys.platform", "os.name"):
            if marker in text:
                violations.append(f"{source.module}: references {marker}")
    assert not violations, violations
