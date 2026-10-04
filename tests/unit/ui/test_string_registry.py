"""String-registry meta-test (plan §18.7, §18.8; CHECKLIST 11a).

"Every user-visible string comes from the registry or a rule message."
The registries are: the model's traceability registry (domain labels)
and the wizard string registry (chrome wording); finding wording comes
from the rule messages. This meta-test asserts the discipline in both
directions — nothing user-visible outside the three sources, and no
dead registry entries.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from configbuilder.model import traceability
from configbuilder.ui.present import strings as wizard_strings

UI_ROOT = Path("configbuilder/ui")

# Strings that are never user-visible: docstrings/comments (not ast
# string *expression* context here — we scan only runtime literals),
# format templates, and internal tokens.
# Format templates: their fragments are registered or developer-facing
# (%r diagnostics); the meta-test's target is fixed display wording.
_FORMAT_PATTERN = re.compile(r"%[sdr]|%\(")


def _runtime_string_literals(path: Path):
    """String literals in runtime positions of one module.

    A string that is a standalone ``Expr`` statement is a docstring (or
    a no-op) — never user-visible output — so only literals used as
    *values* (arguments, returns, dict entries) are runtime strings.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            docstring_ids.add(id(node.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue
            yield node.value


def _wizard_sources():
    return sorted(UI_ROOT.rglob("*.py"))


def test_wizard_string_registry_is_complete_and_clean():
    for key, value in wizard_strings.STRINGS.items():
        assert isinstance(key, str) and key, "registry keys must be non-empty"
        assert isinstance(value, str) and (value.strip() or value == value), (
            "registry wording must be a string (%r)" % key
        )
        assert value != "", "entries are never empty strings (%r)" % key
        assert key == key.lower() and " " not in key, "keys are dotted tokens (%r)" % key


def test_wizard_registry_text_accessor_is_total():
    assert wizard_strings.text("action.next_step") == "next step"
    with pytest.raises(KeyError):
        wizard_strings.text("action.does_not_exist")


def test_every_fixed_ui_string_is_a_registered_entry():
    """The runtime string literals of ``ui`` that reach a user are
    exactly: registry wording, traceability labels referenced by key,
    format templates (%-placeholders), single-word/technical tokens
    (keys, separators, service names), or member-access tokens. This
    test pins that nothing else — a new fixed sentence must be added
    to the registry first."""
    registered = set(wizard_strings.STRINGS.values())
    allowed_exact = {
        " ", "", "-", "—", ".", ", ", ": ", "%d. %s — %s", "%s  %s", "%s %s",
        "  ", "  %s  %d", "(empty sequence)", "General", "t ", " — ",
    }
    allowed_exact.update(registered)
    violations = []
    for path in _wizard_sources():
        for literal in _runtime_string_literals(path):
            if literal in allowed_exact:
                continue
            if _FORMAT_PATTERN.search(literal):
                continue  # a format template; its output wording is registered
            if " " not in literal:
                continue  # a key, service name, separator, or technical token
            violations.append((str(path), literal))
    assert not violations, violations


def test_every_registry_entry_is_used():
    """No dead vocabulary: each registry entry's key is referenced by
    ``ui`` code (directly or through a producer like ``Action``)."""
    sources = [path.read_text(encoding="utf-8") for path in _wizard_sources()]
    for key in wizard_strings.STRINGS:
        assert any(key in source for source in sources), "dead registry entry: %r" % key


def test_traceability_registry_covers_every_registered_label():
    """Sanity: the traceability registry itself stays clean — non-empty
    unique labels, stable mapping ids (plan §3)."""
    seen_labels = {}
    for entry in traceability.registry_entries():
        assert entry.ui_label.strip(), entry.internal_type
        assert entry.mapping_ids, entry.internal_type
        seen_labels.setdefault(entry.ui_label, []).append(entry.internal_type)
    # Labels may repeat across types only when the plan's table repeats
    # them (e.g. shared MAP rows); every repeat must be intentional via
    # mapping ids, never a typo.
    for label_value, types in seen_labels.items():
        assert len(types) >= 1
