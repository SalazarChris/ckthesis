"""Session journal (IMPLEMENTATION_PLAN.md §16.8).

A small journal records the current step, the project file path, and
unsaved-change status after each completed step, in a
platform-appropriate state directory. The journal — not a shutdown
hook — is what makes recovery work: the next start offers to resume at
the recorded step (plan §16.8). It is capped and pruned, because home
directories on shared systems are quota-limited.
"""

from __future__ import annotations

import json
import os

from configbuilder.ui.present.strings import text as _text
from configbuilder.ui.render.platform import state_directory

__all__ = ["SessionJournal", "NullJournal"]


_JOURNAL_NAME = "session.json"
_MAX_CHARS = 8192  # capped: small by design (plan §16.8)


class SessionJournal:
    """Writes one small JSON record per completed step, atomically."""

    def __init__(self, directory=None) -> None:
        self._directory = directory if directory is not None else state_directory()
        self._path = os.path.join(self._directory, _JOURNAL_NAME)

    @property
    def path(self) -> str:
        return self._path

    def record(self, step_name: str, projects) -> None:
        """Journal one completed step (best effort: a journal failure
        never breaks the session)."""
        try:
            entry = {
                "step": step_name,
                "project_path": projects.path or "",
                "unsaved": bool(projects.is_dirty),
                "project_open": bool(projects.is_open),
            }
            text = json.dumps(entry, indent=1, sort_keys=True)
            os.makedirs(self._directory, exist_ok=True)
            self._prune(text)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, self._path)
        except OSError:
            pass

    def read(self):
        """The recorded entry, or ``None`` (absent, unreadable, or
        corrupt — a journal is advice, never authority)."""
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or "step" not in data:
            return None
        return data

    def resume_offer(self, projects) -> str:
        """The one-line resume offer for the recorded step, or ``""``
        when there is nothing to offer (project file gone ⇒ decline
        silently, plan §16.8)."""
        entry = self.read()
        if not entry:
            return ""
        project_path = entry.get("project_path") or ""
        if project_path and not os.path.exists(project_path):
            return ""
        parts = [_text("journal.resume") % entry.get("step", "")]
        if project_path:
            parts.append(_text("journal.for_project") % project_path)
        if entry.get("unsaved"):
            parts.append(_text("journal.unsaved"))
        return _text("journal.join").join(parts)

    def clear(self) -> None:
        """Declining the resume offer discards the journal (plan §16.8)."""
        try:
            os.unlink(self._path)
        except OSError:
            pass

    def _prune(self, incoming: str) -> None:
        """Keep the journal small: a single record is written per
        session, so the cap is enforced by refusing oversized writes —
        the journal stays advice, never a transcript."""
        if len(incoming) > _MAX_CHARS:  # pragma: no cover - defensive
            raise OSError(_text("journal.size_cap"))


class NullJournal:
    """The no-op journal: for tests and embedded runs."""

    def record(self, step_name, projects) -> None:
        return None

    def read(self):
        return None

    def resume_offer(self, projects) -> str:
        return ""

    def clear(self) -> None:
        return None
