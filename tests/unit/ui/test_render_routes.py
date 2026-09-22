"""Long-text route tests (plan §16.5): content preservation, CRLF
preserve-and-warn, the echo that never echoes content, per-line pair
errors, and the editor route's optional existence.
"""

from __future__ import annotations

import json
import os

import pytest

from configbuilder.ui.render.console import Console, ScriptedConsole
from configbuilder.ui.render.journal import NullJournal, SessionJournal
from configbuilder.ui.render.longtext import (
    ReceivedContent,
    collect_long_text,
    crlf_report,
    parse_index_pairs,
    strip_comment_lines,
    summarize,
)
from configbuilder.ui.render.longtext_io import (
    editor_header,
    find_editor,
    read_from_file,
)


# -- line endings: preserve and warn, never repair (§22 Q16) -----------------------


def test_lf_content_warns_nothing():
    assert crlf_report(b">query\nMKTAY") == ""


def test_crlf_content_gets_the_preserve_notice():
    report = crlf_report(b">query\r\nMKTAY\r\n")
    assert report  # the notice exists
    assert "preserved" in report.lower() or "carriage" in report.lower()


def test_mixed_endings_get_their_own_notice():
    assert crlf_report(b"a\r\nb\nc") != ""
    assert crlf_report(b"a\r\nb\nc") != crlf_report(b"a\r\nb\r\nc")


def test_crlf_bytes_are_preserved_exactly():
    # The paste route must hand back exactly what arrived: the notice
    # warns, nothing rewrites (plan §16.5).
    console = ScriptedConsole(["1"])  # choose the paste route
    console.feed_multiline("MKT\r\nAYIA\r\n\r\n")  # paste + blank terminator
    content, route, _notice = collect_long_text(console, "Sequence", routes=("paste",))
    assert route == "paste"
    assert content == "MKT\r\nAYIA\r\n".encode("utf-8")


def test_multiline_terminates_on_blank_line():
    console = ScriptedConsole(["1"])
    console.feed_multiline("MKTAY\n\nTRAILING-NOT-PART-OF-PASTE\n")
    content, _route, _notice = collect_long_text(console, "Sequence", routes=("paste",))
    assert content == b"MKTAY\n"


def test_eof_terminates_a_paste_instead_of_hanging():
    console = ScriptedConsole(["1", "MKTAY"])  # menu, one line, then EOF
    content, _route, _notice = collect_long_text(console, "Sequence", routes=("paste",))
    assert content == b"MKTAY\n"


# -- the echo summarizes, never repeats (§16.5) -------------------------------------


def test_summarize_reports_size_and_shape_not_content():
    received = ReceivedContent(b"MKTA", "paste")
    summary = summarize(received)
    assert "4" in summary  # byte count
    assert "MKTA" not in summary  # content never echoed


def test_summarize_notes_crlf_condition():
    summary = summarize(ReceivedContent(b"MK\r\nTA\r\n", "file"))
    assert "CRLF" in summary or "carriage" in summary.lower()


# -- the editor-route header convention (§16.5) -------------------------------------


def test_strip_comment_lines_removes_header_lines():
    text = "# header\n\n# example\nMKTAY\n#trailing\n"
    assert strip_comment_lines(text) == "\nMKTAY\n"


def test_editor_header_documents_the_convention():
    header = editor_header("Sequence", "MKTAYIAI")
    assert header.startswith("# Sequence")
    assert "#" in header and "8<" in header  # the scissors line


# -- the file route (§16.5) ----------------------------------------------------------


def test_file_route_reads_bytes_exactly(tmp_path):
    path = tmp_path / "seq.txt"
    path.write_bytes(b"MKT\r\nAYIA\r\n")
    console = ScriptedConsole(["2", str(path)])
    content, route, _notice = collect_long_text(
        console, "Sequence", routes=("file",)
    )
    assert content == b"MKT\r\nAYIA\r\n"
    assert route == "file"


def test_file_route_reports_unusable_paths(tmp_path):
    console = ScriptedConsole(["2", str(tmp_path / "missing.txt")])
    content, route, notice = collect_long_text(console, "Sequence", routes=("file",))
    assert content is None and route is None
    assert notice  # the reason is stated


def test_read_from_file_expands_user_directory(tmp_path, monkeypatch):
    # ntpath.expanduser consults USERPROFILE (posixpath: HOME).
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    home_file = tmp_path / "home_seq.txt"
    home_file.write_bytes(b"MKTA")
    content, _notice = read_from_file(ScriptedConsole([]), "~/home_seq.txt")
    assert content == b"MKTA"


# -- the editor route exists only when an editor exists (§16.5) ----------------------


def test_editor_route_not_offered_without_an_editor():
    console = ScriptedConsole(["1", "MKTAY", ""])
    content, route, _notice = collect_long_text(
        console, "Sequence", routes=("paste", "file", "editor"), editors_available=False
    )
    assert route == "paste"
    assert "editor" not in console.transcript.lower() or "3)" not in console.transcript


def test_find_editor_returns_none_without_candidates():
    assert find_editor(candidates=[]) is None


def test_find_editor_accepts_an_absolute_path(tmp_path):
    fake_editor = tmp_path / "fancy-editor"
    fake_editor.write_text("")
    assert find_editor(candidates=[str(fake_editor)]) == str(fake_editor)


def test_find_editor_skips_missing_candidates():
    assert find_editor(candidates=["definitely-not-a-real-editor-xyz"]) is None


# -- pair parsing: per-line errors, never a guess (§16.4) ----------------------------


def test_parse_index_pairs_accepts_the_documented_shapes():
    pairs, errors = parse_index_pairs("0 5\n1, 7\n# comment\n\n2 9")
    assert pairs == ((0, 5), (1, 7), (2, 9))
    assert errors == ()


def test_parse_index_pairs_reports_each_bad_line():
    pairs, errors = parse_index_pairs("0 5\noops\n3\n")
    assert pairs == ((0, 5),)
    assert [number for number, _message in errors] == [2, 3]


def test_parse_index_pairs_negative_indices_are_accepted_tokens():
    # 0-based validation of sign happens downstream (R-ENT-007
    # territory); the parser only recognizes integer tokens.
    pairs, errors = parse_index_pairs("-1 5")
    assert errors == () and pairs == ((-1, 5),)


# -- console primitives (§18.8 scripted harness) -------------------------------------


def test_console_eof_raises_instead_of_looping():
    console = Console(*_open_sink_streams())
    with pytest.raises(EOFError):
        console.prompt("value: ")


def _open_sink_streams():
    import io

    source = io.StringIO("")  # immediately EOF
    sink = io.StringIO()
    return source, sink


def test_scripted_console_captures_the_transcript():
    console = ScriptedConsole(["answer"])
    console.write_line("Question?")
    console.prompt("> ")
    assert "Question?" in console.transcript


def test_console_prompt_strips_the_trailing_newline_only():
    console = ScriptedConsole(["  spaced  \r"])
    value = console.prompt("> ")
    assert value == "  spaced  \r"  # interior whitespace is the user's


# -- the journal: advice, never authority (§16.8) -------------------------------------


def test_journal_records_and_reads_one_step(tmp_path):
    journal = SessionJournal(directory=str(tmp_path))

    class FakeProjects:
        path = "C:/proj/example.cbproj" if os.name == "nt" else "/tmp/example.cbproj"
        is_dirty = True
        is_open = True

    journal.record("components", FakeProjects())
    entry = journal.read()
    assert entry["step"] == "components"
    assert entry["unsaved"] is True
    assert entry["project_open"] is True


def test_journal_write_is_atomic_no_tmp_left_behind(tmp_path):
    journal = SessionJournal(directory=str(tmp_path))

    class FakeProjects:
        path = ""
        is_dirty = False
        is_open = False

    journal.record("review", FakeProjects())
    assert os.path.exists(journal.path)
    assert not os.path.exists(journal.path + ".tmp")
    data = json.load(open(journal.path, encoding="utf-8"))
    assert data["step"] == "review"


def test_journal_absent_or_corrupt_reads_as_none(tmp_path):
    journal = SessionJournal(directory=str(tmp_path))
    assert journal.read() is None
    journal.path and open(journal.path, "w", encoding="utf-8").write("{not json")
    assert journal.read() is None


def test_resume_offer_declines_silently_when_project_gone(tmp_path):
    journal = SessionJournal(directory=str(tmp_path))

    class FakeProjects:
        path = str(tmp_path / "vanished.cbproj")
        is_dirty = True
        is_open = True

    journal.record("variants", FakeProjects())
    assert journal.resume_offer(FakeProjects()) == ""


def test_resume_offer_mentions_step_and_unsaved_state(tmp_path):
    journal = SessionJournal(directory=str(tmp_path))

    class FakeProjects:
        path = ""
        is_dirty = True
        is_open = True

    journal.record("review", FakeProjects())
    offer = journal.resume_offer(FakeProjects())
    assert "review" in offer


def test_declining_clears_the_journal(tmp_path):
    journal = SessionJournal(directory=str(tmp_path))

    class FakeProjects:
        path = ""
        is_dirty = False
        is_open = False

    journal.record("review", FakeProjects())
    journal.clear()
    assert journal.read() is None


def test_null_journal_is_the_no_op_seam():
    journal = NullJournal()
    journal.record("review", None)  # must not raise
    assert journal.read() is None
    journal.clear()
