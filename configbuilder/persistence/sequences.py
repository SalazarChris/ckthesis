"""Sequence-list file reading — the batch-variant input adapter.

Filesystem access is confined to ``output`` and ``persistence`` (plan
§5.3 rule 8), so the batch-variant feature reads its ``.txt`` input
here and ``app`` stays IO-free. The format is deliberately minimal —
**one biological sequence per line** (batch-variant feature contract):

* blank (or whitespace-only) lines are ignored;
* surrounding whitespace on a line is stripped;
* Windows and Unix line endings both work (text mode + ``splitlines``);
* comments are deliberately **not** part of the format: a ``#`` line is
  simply a line that will fail sequence validation, reported with its
  line number like any other invalid entry.

Reading never interprets a sequence — alphabets belong to the model's
``SequenceText``, applied by the caller (``VariantService``). This
module only turns file bytes into numbered, cleaned lines.
"""

from __future__ import annotations

from typing import Tuple

from configbuilder.persistence.store import PersistenceError

__all__ = ["parse_sequence_text", "read_sequence_file"]


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
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = handle.read()
    except OSError as error:
        raise PersistenceError("sequence file cannot be read: %s" % error) from error
    except UnicodeDecodeError as error:
        raise PersistenceError("sequence file is not UTF-8 text: %s" % error) from error
    return parse_sequence_text(payload)
