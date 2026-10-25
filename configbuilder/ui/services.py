"""The service bundle (plan §5.3 rule 6: ``ui`` imports ``app``).

The render layer receives the application services as one read-only
bundle; nothing in ``ui`` constructs pipeline stages itself. The *wiring*
is here so a front end (or a test) builds exactly one object and passes it
around. Validation is wired for the status view and for save, preview and
generation, with the real filesystem port — so an external MSA path that
cannot be read is refused by the console and the GUI alike, and neither
front end needs its own copy of the rule.
"""

from __future__ import annotations

from configbuilder.app import (
    ConfigurationService,
    GenerationService,
    ProjectService,
    ValidationService,
    VariantService,
)
from configbuilder.validation import OsFilesystemPort

__all__ = ["Services", "build_services"]


class Services:
    """The application services, wired as a front end wires them."""

    __slots__ = ("projects", "configuration", "variants", "generation", "validation")

    def __init__(self, projects, configuration, variants, generation, validation) -> None:
        self.projects = projects
        self.configuration = configuration
        self.variants = variants
        self.generation = generation
        self.validation = validation

    def __iter__(self):
        # Iteration is by service *name* so renderers can validate
        # ServiceCall.service names without reflection surprises.
        return iter(
            (
                ("projects", self.projects),
                ("configuration", self.configuration),
                ("variants", self.variants),
                ("generation", self.generation),
                ("validation", self.validation),
            )
        )


def build_services():
    """The standard wiring (the same shape the e2e tests use)."""
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    variants = VariantService(projects, configuration)
    # The real shallow filesystem port: existence/readability of configured
    # external files is a production preflight check, not a test-only one. No
    # chemistry probe is wired — see docs/GATE_RECOVERY_IMPLEMENTATION_REPORT.md
    # for the parser decision this leaves open.
    validation = ValidationService(projects, filesystem=OsFilesystemPort())
    generation = GenerationService(projects, variants, validation=validation)
    return Services(projects, configuration, variants, generation, validation)
