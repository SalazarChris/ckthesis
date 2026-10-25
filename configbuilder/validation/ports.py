"""Ports: the narrow world outside the builder (IMPLEMENTATION_PLAN.md §9.5).

Validation may ask about the filesystem and about chemistry only through
these protocols. A rule never opens a file itself, and the deep semantics
of external formats belong to the external system — the probes here are
shallow by design (plan §9.2: "no reimplementation of external parsing").
"""

from __future__ import annotations

import os
from typing import Protocol

__all__ = [
    "ChemistryProbe",
    "FilesystemPort",
    "NullChemistryProbe",
    "NullFilesystemPort",
    "OsFilesystemPort",
]


class FilesystemPort(Protocol):
    """Shallow file existence/readability questions (plan §9.5)."""

    def is_readable_file(self, raw_path: str) -> bool:
        """True when the path resolves to a readable, non-empty file."""
        ...


class ChemistryProbe(Protocol):
    """Shallow chemical-syntax checks (plan §9.5, §9.6)."""

    def parses_smiles(self, notation: str) -> bool:
        """True when the notation parses as a SMILES string."""
        ...


class OsFilesystemPort:
    """The real shallow probe: exists, is a regular file, readable, non-empty.

    This is the production answer to ``is_readable_file`` — the whole of what
    the builder asks the local filesystem (plan §9.5). A directory, a device,
    an unreadable file or an empty file all answer ``False``; no content is
    read or interpreted here, and no directory is created.
    """

    def is_readable_file(self, raw_path: str) -> bool:  # noqa: D102 - see protocol
        if not isinstance(raw_path, str) or not raw_path:
            return False
        try:
            if not os.path.isfile(raw_path):
                return False
            if os.path.getsize(raw_path) <= 0:
                return False
            return os.access(raw_path, os.R_OK)
        except OSError:
            return False


class NullFilesystemPort:
    """The probe that answers nothing: every path is reported unreadable.

    Used when validation runs without a real filesystem — with this port,
    PREFLIGHT path rules must downgrade to "not checked" findings rather
    than report false errors (plan §9.6).
    """

    def is_readable_file(self, raw_path: str) -> bool:  # noqa: D102 - see protocol
        return False


class NullChemistryProbe:
    """The probe that answers nothing: no notation parses.

    With this probe the SMILES rule reports a WARNING "not checked"
    instead of an ERROR (plan §9.6).
    """

    def parses_smiles(self, notation: str) -> bool:  # noqa: D102 - see protocol
        return False
