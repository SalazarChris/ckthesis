"""Pages of the Qt front end (Stages 1-6).

Each page is a plain ``QWidget`` that reads the application services through
:class:`configbuilder.ui.render.qt.state.GuiState` and re-projects itself when
the state says the open job changed. Only the entities and advanced pages
change a job, and each does so exclusively through the application services
(``ConfigurationService``). Job-wide settings have **one** destination since
Stage 8: the ``JobSettingsPanel`` Overview hosts. The ligand file action on
the Entities page and the generate page write files only through
``GenerationService`` — planning, validation and execution are its own.
"""

from __future__ import annotations

from configbuilder.ui.render.qt.pages.advanced import AdvancedPage
from configbuilder.ui.render.qt.pages.entities import EntitiesPage
from configbuilder.ui.render.qt.pages.generate import GeneratePage
from configbuilder.ui.render.qt.pages.overview import OverviewPage
from configbuilder.ui.render.qt.pages.preview import PreviewPage
from configbuilder.ui.render.qt.pages.settings import JobSettingsPanel

__all__ = [
    "AdvancedPage",
    "EntitiesPage",
    "GeneratePage",
    "JobSettingsPanel",
    "OverviewPage",
    "PreviewPage",
]
