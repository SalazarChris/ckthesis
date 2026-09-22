"""The wizard's read-only view (plan §16.2: ``view`` is a read-only
projection of the project plus the latest ``ValidationReport``).

Steps receive a ``WizardView``; they never touch a service. Building
the view is ``ui``'s job (it is the only family allowed to import
``app``, plan §5.3 rule 6) — the machine and the steps stay pure.
"""

from __future__ import annotations

__all__ = ["WizardView"]


class WizardView:
    """What a step may know: the open project's shape and the latest
    report. Nothing here mutates; nothing here reaches a service.

    Attributes are the plain data steps branch on:

    - ``has_project`` / ``project_name`` — step 1/2 gating;
    - ``records`` — ``(family, entity_id, sequence, label)`` rows;
    - ``polymers`` / ``components`` — the filtered rows;
    - ``addressable`` — rows that can take a link endpoint;
    - ``has_external`` — any external resource referenced;
    - ``needs_definition`` — a component code without a definition;
    - ``seeds`` — the seed list;
    - ``errors`` / ``warnings`` — counts from the latest report;
    - ``variants`` — expanded variant keys (empty when none);
    - ``conflicts`` — unresolved plan conflicts (empty when planned);
    - ``report`` — the raw latest ``Report`` (or ``None``).
    """

    __slots__ = (
        "has_project",
        "project_name",
        "records",
        "has_external",
        "needs_definition",
        "seeds",
        "report",
        "variants",
        "conflicts",
    )

    def __init__(
        self,
        has_project: bool = False,
        project_name: str = "",
        records=(),
        has_external: bool = False,
        needs_definition: bool = False,
        seeds=(),
        report=None,
        variants=(),
        conflicts=(),
    ) -> None:
        self.has_project = bool(has_project)
        self.project_name = project_name or ""
        self.records = tuple(records)
        self.has_external = bool(has_external)
        self.needs_definition = bool(needs_definition)
        self.seeds = tuple(seeds)
        self.report = report
        self.variants = tuple(variants)
        self.conflicts = tuple(conflicts)

    # -- derived rows -----------------------------------------------------

    @property
    def polymers(self):
        """Records whose family is a polymer (protein/rna/dna)."""
        return tuple(r for r in self.records if r.family in ("protein", "rna", "dna"))

    @property
    def components(self):
        """Records whose family is a ligand/ion component."""
        return tuple(r for r in self.records if r.family == "ligand")

    @property
    def addressable(self):
        """Records that can take a link endpoint (all families can)."""
        return self.records

    # -- report helpers ---------------------------------------------------

    @property
    def errors(self) -> int:
        return _count(self.report, "ERROR")

    @property
    def warnings(self) -> int:
        return _count(self.report, "WARNING")


def _count(report, severity_name: str) -> int:
    if report is None:
        return 0
    total = 0
    for finding in getattr(report, "findings", ()):
        name = finding.severity.name if hasattr(finding.severity, "name") else str(finding.severity)
        if name == severity_name:
            total += 1
    return total
