"""Persistence (IMPLEMENTATION_PLAN.md §14, §6.8): project file save/load
with its own schema version axis.

Depends on ``model``, ``identity``, and ``variants`` (edit types) only
(plan §5.3 rule 8); validation is injected into ``load`` by ``app`` so
findings surface at load time without a layering violation.
"""

from configbuilder.persistence.schema import (
    SCHEMA_VERSION,
    FutureVersionError,
    LoadResult,
    OutputSettings,
    PersistenceError,
    Project,
    upgrade,
)
from configbuilder.persistence.sequences import read_sequence_file
from configbuilder.persistence.store import load, save

__all__ = [
    "SCHEMA_VERSION",
    "FutureVersionError",
    "LoadResult",
    "OutputSettings",
    "PersistenceError",
    "Project",
    "load",
    "read_sequence_file",
    "save",
    "upgrade",
]
