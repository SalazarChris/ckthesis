"""The service bundle (plan §5.3 rule 6: ``ui`` imports ``app``).

The render layer receives the five services as one read-only bundle;
nothing in ``ui`` constructs pipeline stages itself. The *wiring* is
here so a front end (or a test) builds exactly one object and passes it
around.
"""

from __future__ import annotations

from configbuilder.app import (
    ConfigurationService,
    GenerationService,
    ProjectService,
    ValidationService,
    VariantService,
)

__all__ = ["Services", "build_services"]


class Services:
    """The five application services, wired as a front end wires them."""

    __slots__ = ("projects", "configuration", "variants", "validation", "generation")

    def __init__(self, projects, configuration, variants, validation, generation) -> None:
        self.projects = projects
        self.configuration = configuration
        self.variants = variants
        self.validation = validation
        self.generation = generation

    def __iter__(self):
        # Iteration is by service *name* so renderers can validate
        # ServiceCall.service names without reflection surprises.
        return iter(
            (
                ("projects", self.projects),
                ("configuration", self.configuration),
                ("variants", self.variants),
                ("validation", self.validation),
                ("generation", self.generation),
            )
        )


def build_services():
    """The standard wiring (the same shape the e2e tests use)."""
    projects = ProjectService()
    configuration = ConfigurationService(projects)
    variants = VariantService(projects, configuration)
    validation = ValidationService(projects)
    generation = GenerationService(projects, validation, variants)
    return Services(projects, configuration, variants, validation, generation)
