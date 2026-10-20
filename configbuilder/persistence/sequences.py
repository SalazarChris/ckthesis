"""Sequence-list and SMILES file reading — batch-variant input adapters.

Filesystem access is confined to ``output`` and ``persistence`` (plan
§5.3 rule 8), so the batch-variant feature reads its input files here
and ``app`` stays IO-free.

Supported formats:

**Sequence files (.txt):**
  One biological sequence per line (protein, DNA, RNA):
  - blank (or whitespace-only) lines are ignored;
  - surrounding whitespace on a line is stripped;
  - Windows and Unix line endings both work (text mode + ``splitlines``);
  - comments are deliberately **not** part of the format: a ``#`` line is
    simply a line that will fail sequence validation, reported with its
    line number like any other invalid entry.

**SMILES files (.smiles or .txt):**
  One ligand per line, with optional name:
  - Format 1 (name + SMILES): ``<name> <SMILES>`` (name and SMILES separated by whitespace)
  - Format 2 (SMILES only): ``<SMILES>`` (no name, auto-generated)
  - blank lines are ignored;
  - lines starting with ``#`` are treated as comments and ignored;
  - surrounding whitespace is stripped.

Reading never interprets a sequence or SMILES — validation belongs to the
model, applied by the caller (``VariantService``). This module only turns
file bytes into numbered, cleaned entries.
"""

from __future__ import annotations

import os
from typing import Tuple

from configbuilder.persistence.store import PersistenceError

__all__ = ["parse_sequence_text", "parse_smiles_text", "read_sequence_file", "read_smiles_file"]


def parse_sequence_text(payload: str) -> Tuple[Tuple[int, str], ...]:
    """The usable lines of file text as ``(line_number, text)`` pairs.

    Line numbers are 1-based file lines, preserved so the caller can
    report an invalid entry at its exact position. Blank lines never
    reach the result.
    """
    numbered = []
    for number, line in enumerate(payload.splitlines(), start=1):
        text = line.strip()
        if text:
            numbered.append((number, text))
    return tuple(numbered)


def read_sequence_file(path: str) -> Tuple[Tuple[int, str], ...]:
    """Read a sequence-list file, or raise ``PersistenceError``.

    The failure vocabulary matches project files: a missing, unreadable,
    or non-UTF-8 file is a ``PersistenceError`` naming the cause — never
    a raw ``OSError`` leaking into the application layer.
    """
    if os.path.isdir(path):
        # A folder is an ordinary slip at the file picker — its listing
        # shows directories too. Windows reports reading one as
        # ``Permission denied``, which points the user at a permissions
        # problem they do not have.
        raise PersistenceError("that path is a directory, not a sequence file")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = handle.read()
    except OSError as error:
        raise PersistenceError("sequence file cannot be read: %s" % error) from error
    except UnicodeDecodeError as error:
        raise PersistenceError("sequence file is not UTF-8 text: %s" % error) from error
    return parse_sequence_text(payload)


def parse_smiles_text(payload: str) -> Tuple[Tuple[int, str, str], ...]:
    """The usable lines of a SMILES file as ``(line_number, name, smiles)`` tuples.

    Line numbers are 1-based file lines, preserved so the caller can
    report an invalid entry at its exact position.
    
    Format:
    - ``<name> <SMILES>`` → (line, name, smiles)
    - ``<SMILES>`` → (line, "ligand_N", smiles) where N is the 1-based index
    - blank lines and ``#`` comment lines are skipped
    """
    numbered = []
    ligand_index = 0
    for number, line in enumerate(payload.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = text.split(None, 1)  # Split on whitespace, max 1 split
        if len(parts) == 2:
            name, smiles = parts
            numbered.append((number, name, smiles))
        elif len(parts) == 1:
            ligand_index += 1
            numbered.append((number, "ligand_%d" % ligand_index, parts[0]))
        else:
            # Shouldn't happen, but handle gracefully
            numbered.append((number, "ligand_%d" % (ligand_index + 1), text))
    return tuple(numbered)


def read_smiles_file(path: str) -> Tuple[Tuple[int, str, str], ...]:
    """Read a SMILES file, or raise ``PersistenceError``.

    Returns ``(line_number, name, smiles)`` tuples.
    """
    if os.path.isdir(path):
        raise PersistenceError("that path is a directory, not a SMILES file")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = handle.read()
    except OSError as error:
        raise PersistenceError("SMILES file cannot be read: %s" % error) from error
    except UnicodeDecodeError as error:
        raise PersistenceError("SMILES file is not UTF-8 text: %s" % error) from error
    return parse_smiles_text(payload)
