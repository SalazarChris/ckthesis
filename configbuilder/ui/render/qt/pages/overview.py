"""The Overview page: job settings and entities at a glance.

The job's name, model seeds and JSON version are **editable here**, and this is
the only place they are edited: the separate Job Settings destination was
removed, so the page embeds the single :class:`JobSettingsPanel` and it reads
and writes through ``ConfigurationService``.

What remains on the page is deliberately small:

1. **Job details** — the job-wide settings with their Apply semantics and
   default/changed markers;
2. **Entities** — the record count, the per-family breakdown and one
   :class:`Entities` action that opens the Entities workspace.

The readiness card and its *Validate job* action are gone: save and generate
are not gated. The counts are read directly from ``configuration.records``.

No JSON preview action is on this page either: the document is written through
**Save JSON** in the FILE footer, which is the one visible save route.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from configbuilder.model import (
    ComponentRecord,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
)
from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.qt.pages.settings import JobSettingsPanel
from configbuilder.ui.render.qt.style import (
    breadcrumb_label,
    caption_label,
    field_label,
    hint_label,
    page_title_label,
)

__all__ = ["OverviewPage"]


class OverviewPage(QWidget):
    """Job settings and an entity summary."""

    #: The summary action the window answers by changing destination.
    entities_requested = Signal()

    def __init__(self, state, notify=None, problems=None, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self.job_settings = JobSettingsPanel(
            state, notify=notify, problems=problems, parent=self
        )
        self._build()

    # -- construction ------------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(breadcrumb_label(_text("gui.breadcrumb_overview")))
        layout.addWidget(page_title_label(_text("gui.overview_title")))
        layout.addWidget(hint_label(_text("gui.overview_intro")))
        layout.addSpacing(2)
        layout.addWidget(self.job_settings)
        self._no_job_note = hint_label(_text("gui.overview_no_job"))
        self._no_job_note.setVisible(False)
        layout.addWidget(self._no_job_note)
        self._summary_card = self._build_entity_summary()
        layout.addWidget(self._summary_card)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _build_entity_summary(self):
        """A compact card: how many entities, which families, and where to go."""
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        layout.addWidget(field_label(_text("gui.stat_entities")))
        self._entities_value = QLabel(_text("menu.status_absent"))
        self._entities_value.setProperty("role", "statValue")
        self._entities_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._entities_value)
        self._entities_detail = caption_label(wrap=True)
        layout.addWidget(self._entities_detail)
        self._dialect_label = caption_label()
        self._dialect_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._dialect_label)
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 0)
        row.setSpacing(10)
        self.entities_button = QPushButton(_text("gui.overview_go_entities"))
        self.entities_button.setProperty("role", "quiet")
        self.entities_button.clicked.connect(self.entities_requested.emit)
        row.addWidget(self.entities_button)
        # Wrap: the hint's full sentence is wider than the content area at the
        # window's 940 px minimum, and an unwrapped label forced the whole
        # Overview into a horizontal scrollbar there.
        row.addWidget(
            caption_label(_text("gui.entity_summary_hint"), wrap=True), 1
        )
        layout.addLayout(row)
        return card

    # -- refresh -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the model. Never writes anything."""
        configuration = self._state.configuration
        project = self._state.project
        if configuration is None or project is None:
            self._clear()
            return
        self.job_settings.refresh()
        self.job_settings.setVisible(True)
        self._no_job_note.setVisible(False)
        self._summary_card.setVisible(True)

        total = len(configuration.records)
        self._entities_value.setText(str(total))
        self._entities_detail.setText(
            _family_summary(_components_counts(configuration))
            if total
            else _text("gui.stat_entities_none")
        )
        self._dialect_label.setText(
            _text("gui.dialect_caption") % configuration.format_target.dialect.value
        )

    def _clear(self) -> None:
        """No job: keep the page neutral and leave New/Open to the footer."""
        self.job_settings.refresh()
        self.job_settings.setVisible(False)
        self._entities_value.setText("0")
        self._entities_detail.setText("")
        self._dialect_label.setText("")
        self._summary_card.setVisible(False)
        self._no_job_note.setVisible(True)

    # -- reading the page back (used by the window's tests) ----------------

    def entities_value_text(self) -> str:
        """The entity count the summary card shows."""
        return self._entities_value.text()

    def summary_text(self, label_key: str) -> str:
        """The summary value displayed for one label key (``""`` if none)."""
        if label_key == "menu.status_components":
            return self._entities_detail.text()
        if label_key == "gui.dialect_label":
            return self._dialect_label.text()
        return ""


#: Per-family wording for the entity summary, in the mockup's order.
_FAMILY_WORDS = (
    ("protein", "gui.family_protein", "gui.family_proteins"),
    ("rna", "gui.family_rna", "gui.family_rna"),
    ("dna", "gui.family_dna", "gui.family_dna_plural"),
    ("ligand", "gui.family_ligand", "gui.family_ligands"),
)


def _family_summary(counts) -> str:
    """Only the families present, in plain words.

    The numbers are the status service's own ``components`` value; this only
    chooses wording and skips empty families, so a three-ligand job reads
    "3 ligands" rather than listing zeros for protein, RNA and DNA. DNA is
    counted as chain records, so a duplex the builder added is two strands.
    """
    counts = counts if isinstance(counts, dict) else {}
    parts = []
    for key, singular, plural in _FAMILY_WORDS:
        amount = counts.get(key, 0) or 0
        if amount == 1:
            parts.append("%d %s" % (amount, _text(singular)))
        elif amount > 1:
            parts.append("%d %s" % (amount, _text(plural)))
    return " · ".join(parts)


def _components_counts(configuration):
    """The per-family record counts, read from the model's own records."""
    counts = {"protein": 0, "rna": 0, "dna": 0, "ligand": 0}
    for record in configuration.records:
        if isinstance(record, FamilyARecord):
            counts["protein"] += 1
        elif isinstance(record, FamilyBRecord):
            counts["rna"] += 1
        elif isinstance(record, FamilyCRecord):
            counts["dna"] += 1
        elif isinstance(record, ComponentRecord):
            counts["ligand"] += 1
    return counts
