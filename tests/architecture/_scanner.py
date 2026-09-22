"""Static-analysis helpers for the architecture tests.

IMPLEMENTATION_PLAN.md §5.3 / §18.7: the dependency rules are asserted by
scanning imports, so violations fail CI rather than accumulating. The scanner
parses source with :mod:`ast`; it never imports the scanned code.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "configbuilder"


@dataclass(frozen=True)
class SourceModule:
    """One parsed module of the ``configbuilder`` package."""

    module: str  # full dotted name, e.g. "configbuilder.ui.render.plain"
    family: str  # plan §5.1 family, e.g. "ui.render"
    path: Path
    tree: ast.Module


def dotted_name(path: Path) -> str:
    """``configbuilder/ui/render/plain.py`` -> ``configbuilder.ui.render.plain``."""
    rel = path.relative_to(PACKAGE_ROOT.parent)
    return ".".join(rel.with_suffix("").parts)


def family_of(module: str) -> str:
    """Map a dotted module name onto its plan §5.1 family."""
    parts = module.split(".")
    if len(parts) < 2:
        return "root"
    if parts[1] == "ui" and len(parts) > 2:
        # ui/steps, ui/render, ui/present are families in their own right;
        # deeper modules belong to their subpackage family.
        return ".".join(parts[:3])
    return parts[1]


def iter_source_modules():
    """Yield every ``configbuilder`` module, parsed, in stable path order."""
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        module = dotted_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        yield SourceModule(module=module, family=family_of(module), path=path, tree=tree)


def imported_targets(source: SourceModule):
    """All dotted import targets named by a module, with relative imports resolved.

    Absolute targets outside ``configbuilder`` are returned verbatim so callers
    can apply their own allow/deny lists.
    """
    targets = []
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    targets.append(node.module)
            else:
                parts = source.module.split(".")
                package = parts[:-1]
                up = node.level - 1
                if up:
                    if up > len(package):
                        package = []
                    else:
                        package = package[: len(package) - up]
                base = ".".join(package)
                if node.module:
                    targets.append(f"{base}.{node.module}" if base else node.module)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    targets.append(f"{base}.{alias.name}" if base else alias.name)
    return targets


def within_project(target: str) -> bool:
    """True when an import target resolves inside the ``configbuilder`` package."""
    return target == "configbuilder" or target.startswith("configbuilder.")


def family_of_target(target: str) -> str:
    """Family of an import target (``configbuilder`` prefix assumed)."""
    stripped = target[len("configbuilder") :] if target == "configbuilder" else target[len("configbuilder.") :]
    if not stripped:
        return "root"
    return family_of("configbuilder." + stripped)
