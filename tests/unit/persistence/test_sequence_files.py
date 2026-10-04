"""Sequence-list file reading — the batch-variant input adapter.

The format is deliberately minimal: one sequence per line, blank lines
ignored, both line-ending conventions, whitespace stripped. Comment
syntax is deliberately absent — a ``#`` line is just a line that fails
sequence validation later, reported with its line number (batch-variant
feature contract).
"""

from __future__ import annotations

import os

import pytest

from configbuilder.persistence import PersistenceError, read_sequence_file
from configbuilder.persistence.sequences import parse_sequence_text


def test_one_sequence_per_line():
    assert parse_sequence_text("MSTNPKP\nGKKIGYS\n") == ((1, "MSTNPKP"), (2, "GKKIGYS"))


def test_blank_lines_are_ignored_and_line_numbers_preserved():
    payload = "MSTNPKP\n\n   \nGKKIGYS\n\n"
    assert parse_sequence_text(payload) == ((1, "MSTNPKP"), (4, "GKKIGYS"))


def test_surrounding_whitespace_is_stripped():
    assert parse_sequence_text("  MSTNPKP  \n\tGKKIGYS\n") == ((1, "MSTNPKP"), (2, "GKKIGYS"))


def test_windows_line_endings(tmp_path):
    path = tmp_path / "seqs.txt"
    path.write_bytes(b"MSTNPKP\r\nGKKIGYS\r\n")
    assert read_sequence_file(str(path)) == ((1, "MSTNPKP"), (2, "GKKIGYS"))


def test_unix_line_endings(tmp_path):
    path = tmp_path / "seqs.txt"
    path.write_bytes(b"MSTNPKP\nGKKIGYS\n")
    assert read_sequence_file(str(path)) == ((1, "MSTNPKP"), (2, "GKKIGYS"))


def test_missing_file_is_a_clear_persistence_error(tmp_path):
    with pytest.raises(PersistenceError, match="cannot be read"):
        read_sequence_file(str(tmp_path / "absent.txt"))


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows cannot express a read-denied file through chmod",
)
def test_unreadable_file_is_a_clear_persistence_error(tmp_path):
    path = tmp_path / "seqs.txt"
    path.write_bytes(b"MSTNPKP")
    os.chmod(path, 0o000)
    try:
        with pytest.raises(PersistenceError, match="cannot be read"):
            read_sequence_file(str(path))
    finally:
        os.chmod(path, 0o644)


def test_binary_garbage_is_reported_as_unreadable(tmp_path):
    path = tmp_path / "seqs.txt"
    path.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(PersistenceError):
        read_sequence_file(str(path))


def test_a_directory_is_reported_as_a_directory_not_a_permission_problem(tmp_path):
    """Playtest finding: pointing the picker at a folder is ordinary (its
    listing shows directories). Windows reports *reading* one as
    ``Permission denied``, so the user went hunting for a permissions
    problem they did not have. The message now names the real mistake.
    """
    with pytest.raises(PersistenceError, match="is a directory, not a sequence file"):
        read_sequence_file(str(tmp_path))


def test_a_missing_file_still_names_the_missing_path(tmp_path):
    """The directory branch must not swallow the ordinary missing-file case."""
    missing = tmp_path / "not-here.txt"
    with pytest.raises(PersistenceError, match="cannot be read"):
        read_sequence_file(str(missing))
