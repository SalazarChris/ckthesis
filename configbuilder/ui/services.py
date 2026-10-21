"""The service bundle (plan §5.3 rule 6: ``ui`` imports ``app``).

The render layer receives the application services as one read-only
bundle; nothing in ``ui`` constructs pipeline stages itself. The *wiring*
is here so a front end (or a test) builds exactly one object and passes it
around. Validation is deliberately not wired: save, generate and variant
creation are not gated.
"""

from __future__ import annotations

from configbuilder.app import (
    ConfigurationService,
    GenerationService,
    ProjectService,
    VariantService,
)

__all__ = ["Services", "build_services"]


class Services:
    """The application services, wired as a front end wires them."""

    __slots__ = ("projects", "configuration", "variants", "generation")

    def __init__(self, projects, configuration, variants, generation) -> None:
        self.projects = projects
        self.configuration = configuration
        self.variants = variants
        self.generation = generation

    def __iter__(self):
        # Iteration is by service *name* so renderers can validate
        # ServiceCall.service names without reflection surprises.
        return iter(
            (
                ("projects", self.projects),
                ("configuration", self.configuration),
                ("variants", self.variants),
                ("generation", self.generation),
            )
        )


def build_services():
    """The standard wiring (the same shape the e2e tests use)."""
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    variants = VariantService(projects, configuration)
    generation = GenerationService(projects, variants)
    return Services(projects, configuration, variants, generation)
