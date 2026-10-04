"""Unit tests for the serializer's fixed encoding policy (plan §11)."""

from __future__ import annotations

import json

import pytest

from configbuilder.serialize import EncodeError, encode, encode_to_file
from configbuilder.transform.engine import WireDocument


def _document(**overrides):
    doc = WireDocument()
    doc["name"] = "job"
    doc["modelSeeds"] = [1, 2]
    doc["version"] = 3
    doc.update(overrides)
    return doc


# -- encoding policy -----------------------------------------------------------------


def test_output_is_utf8_without_bom():
    data = encode(_document())
    assert not data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8")  # decodable as UTF-8


def test_exactly_one_trailing_newline():
    data = encode(_document())
    assert data.endswith(b"\n")
    assert not data.endswith(b"\n\n")


def test_lf_line_endings_only():
    data = encode(_document(unpairedMsa=">q\nA\nB"))
    assert b"\r" not in data


def test_fixed_indentation_and_separators():
    text = encode(_document()).decode("utf-8")
    assert text.startswith('{\n  "name": "job",')
    assert '": ' in text  # key-value separator is ": "


def test_key_order_is_insertion_order_never_sorted():
    doc = _document()
    doc["aaa"] = 1
    doc["zzz"] = 2
    text = encode(doc).decode("utf-8")
    assert text.index('"version"') < text.index('"aaa"') < text.index('"zzz"')


def test_encode_to_file_writes_exact_bytes(tmp_path):
    target = tmp_path / "out.json"
    encode_to_file(_document(), target)
    raw = target.read_bytes()
    assert raw == encode(_document())
    assert b"\r" not in raw


# -- escaping policy ------------------------------------------------------------------


def test_control_characters_are_escaped_not_raw():
    data = encode(_document(description="a\tb\nc\x01d"))
    assert b"\t" not in data and b"\x01" not in data
    assert b"\\t" in data and b"\\n" in data and b"\\u0001" in data


def test_non_ascii_is_preserved_as_utf8():
    text = "café — αβγ ← 日本語"
    data = encode(_document(description=text))
    assert text in data.decode("utf-8")
    assert "\\u" not in data.decode("utf-8")


def test_quotes_and_backslashes_escaped():
    data = encode(_document(description='say "hi" \\ ok'))
    assert b'\\"' in data and b"\\\\" in data


def test_unpaired_surrogate_is_diagnosed():
    with pytest.raises(EncodeError) as excinfo:
        encode(_document(description="bad \ud800 tail"))
    assert "surrogate" in str(excinfo.value)


# -- what must never appear -----------------------------------------------------------


def test_nan_and_infinity_rejected():
    doc = _document()
    doc["oops"] = float("nan")
    with pytest.raises(EncodeError):
        encode(doc)


def test_non_document_rejected():
    with pytest.raises(EncodeError):
        encode(["not", "a", "document"])


def test_no_timestamp_or_host_content():
    data = encode(_document()).decode("utf-8")
    for banned in ("timestamp", "generated", "hostname", "platform", "now()", "uuid"):
        assert banned not in data.lower()


# -- encode_to_file --------------------------------------------------------------------


def test_encode_to_file_writes_exact_bytes(tmp_path):
    target = tmp_path / "job.json"
    encode_to_file(_document(), target)
    assert target.read_bytes() == encode(_document())
    assert not (tmp_path / "job.json.bak").exists()


def test_decode_round_trip_preserves_order_and_values():
    doc = _document(sequences=[{"protein": {"id": "A", "sequence": "PEPTIDE"}}])
    restored = json.loads(encode(doc).decode("utf-8"))
    assert list(restored.keys()) == list(doc.keys())
    assert restored == doc
