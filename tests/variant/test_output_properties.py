"""Property tests for output naming and manifest determinism (plan §13.2,
§13.7, §18.6).

The naming-injectivity property: two distinct variant keys never silently
plan the same directory — the planner reports a conflict instead. The
manifest property: everything except ``run_info`` is a pure function of
the inputs, so two builds over the same data are byte-identical. Seeded
random cases run everywhere; hypothesis widens the space when installed
(the suite's standing convention).
"""

from __future__ import annotations

import json
import random
import string

import pytest

from configbuilder.output.manifest import build_manifest
from configbuilder.output.naming import MAX_SLUG_LENGTH, slug, variant_directory_name
from configbuilder.output.plan import plan
from configbuilder.output.policies import OverwritePolicy, PathPolicy
from configbuilder.serialize import encode

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAVE_HYPOTHESIS = True
except ImportError:  # pragma: no cover - exercised only without hypothesis
    HAVE_HYPOTHESIS = False

NASTY_ALPHABET = string.ascii_letters + string.digits + " _-/\\:.!?#$%&'()*+,;=@[]^`{|}~\""


# -- the naming-injectivity property ---------------------------------------------


def _assert_injective(keys):
    """Distinct keys either plan distinct directories or are reported as
    conflicts — never silently merged."""
    result = plan({key: b"{}" for key in keys}, "out", "P", filesystem=type("F", (), {"exists": lambda self, p: False, "read": lambda self, p: b""})())
    planned_directories = [entry.path for entry in result.entries]
    if len(set(planned_directories)) < len(planned_directories):
        # duplicates planned: they must have been reported
        assert result.conflicts, "duplicate planned paths without a conflict report"
    distinct_keys = len(set(keys))
    if distinct_keys < len(keys) and not result.conflicts:
        # identical keys would legitimately plan identical paths only if
        # the caller asked for them; distinct keys must conflict.
        lowered = {key.lower() for key in keys}
        if len(lowered) == len(set(keys)):
            pytest.fail("distinct keys planned the same path with no conflict")


def _random_key(rng):
    length = rng.randint(1, 24)
    text = "".join(rng.choice(NASTY_ALPHABET) for _ in range(length))
    return text


def test_naming_injectivity_seeded_random():
    rng = random.Random(20260921)
    for _trial in range(120):
        keys = [_random_key(rng) for _ in range(rng.randint(2, 5))]
        _assert_injective(keys)


def test_case_differing_pairs_always_conflict():
    rng = random.Random(42)
    for _trial in range(60):
        key = _random_key(rng)
        variant = key + rng.choice(["a", "A", "x", "X"])
        if variant_directory_name("P", key).lower() == variant_directory_name("P", variant).lower():
            result = plan({key: b"{}", variant: b"{}"}, "out", "P")
            assert result.conflicts, (key, variant)


def test_slug_is_idempotent_on_its_own_output():
    rng = random.Random(7)
    for _trial in range(100):
        text = _random_key(rng)
        try:
            once = slug(text)
        except Exception:
            continue  # empty-after-cleaning inputs are the documented refusal
        assert slug(once) == once, (text, once)


def test_slug_output_is_always_in_the_safe_alphabet():
    rng = random.Random(11)
    for _trial in range(200):
        try:
            result = slug(_random_key(rng))
        except Exception:
            continue
        assert result == result.lower()
        assert all(character in string.ascii_lowercase + string.digits + "-" for character in result)
        assert len(result) <= MAX_SLUG_LENGTH


@pytest.mark.skipif(not HAVE_HYPOTHESIS, reason="hypothesis not installed")
@given(st.text(max_size=64))
@settings(max_examples=100, deadline=None)
def test_hypothesis_slug_stays_in_alphabet(text):
    try:
        result = slug(text)
    except Exception:
        return  # the documented empty-after-cleaning refusal
    assert all(character in string.ascii_lowercase + string.digits + "-" for character in result)


# -- manifest determinism ---------------------------------------------------------


class _Variant:
    def __init__(self, key, fingerprint):
        self.key = key
        self.label = "label of " + key
        self.declared_factors = ("sequence",)
        self.applied_edits = ({"kind": "SetSequence", "record_key": "A", "text": "M"},)
        self.file_name = key + ".json"
        self.fingerprint = fingerprint


def _manifest_inputs(seed):
    rng = random.Random(seed)
    keys = ["wt", "mut", "trunc"]
    variants = tuple(_Variant(key, "%064x" % rng.getrandbits(256)) for key in keys)
    return {
        "project_name": "Property Project",
        "base_fingerprint": "%064x" % rng.getrandbits(256),
        "format_version": 3,
        "variants": variants,
        "seed_set": [rng.randint(0, 2**31) for _ in range(10)],
        "path_policy": PathPolicy("CopyIntoAssets"),
        "overwrite_policy": OverwritePolicy("Fail"),
    }


def test_manifest_bytes_are_identical_across_builds():
    first = build_manifest(**_manifest_inputs(5))
    second = build_manifest(**_manifest_inputs(5))
    assert encode(first.data) == encode(second.data)


def test_manifest_bytes_differ_when_inputs_differ():
    first = encode(build_manifest(**_manifest_inputs(1)).data)
    second = encode(build_manifest(**_manifest_inputs(2)).data)
    assert first != second


def test_manifest_payload_is_valid_json():
    manifest = build_manifest(**_manifest_inputs(9))
    restored = json.loads(encode(manifest.data).decode("utf-8"))
    assert restored["project_name"] == "Property Project"
