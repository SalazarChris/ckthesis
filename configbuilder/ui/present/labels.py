"""Labels (plan §5.3 rule 6, §16.1, §18.8 formatting tier).

Every user-visible label resolves through the model's traceability
registry — the single translation point between neutral internal names
and human-facing wording (plan §3). Nothing here hard-codes a label; a
string that is neither registry wording nor rule message wording is a
defect the meta-test catches.

This module imports ``model.traceability`` only: ``ui`` may import
``app`` and ``model.traceability`` (plan §5.3 rule 6), and ``present``
is the family whose whole job is label resolution.
"""

from __future__ import annotations

from configbuilder.model.traceability import label_for, mapping_ids_for
from configbuilder.ui.present.strings import text as _text

__all__ = [
    "label",
    "labels",
    "mapping_ids",
    "with_record_label",
    "finding_context_label",
    "finding_reference_label",
    "severity_label",
    "action_description",
    "general_finding_context",
    "alignment_text",
    "change_text",
    "SEVERITY_SYMBOLS",
]


def alignment_text(alignment) -> str:
    """One alignment case as a short phrase (the change and editor rows).

    ``alignment`` is the ``describe_edit`` dictionary, never a model object:
    ``app`` serialises the case and this layer only words it, so a new case
    shows up as its ``form`` rather than being lost in translation.
    """
    form = alignment.get("form", "")
    if form == "Automatic":
        return _text("menu.msa_mode_auto")
    if form == "Free":
        return _text("menu.msa_mode_free")
    if form == "Provided":
        return _text("menu.msa_mode_provided")
    source = alignment.get("source", {})
    if source.get("form") == "inline":
        value = _text("gui.alignment_source_inline")
    else:
        value = _text("gui.alignment_source_file")
    return "%s (%s)" % (form, value)


def change_text(kind: str, described) -> str:
    """One variant edit as a sentence a user reads (plan §12.1 review).

    The single renderer for ``describe_edit`` dictionaries: the desktop page
    and the console both call it, so the same edit is never worded two ways
    depending on the entry point (plan §5.3 rule 6 — wording is a ``ui``
    concern, and this is that layer's one place for it). The ``kind`` is the
    edit's class name, which is exactly what ``describe_edit`` returns.
    """
    record = described.get("record_key", "") or _text("gui.variants_no_changes")
    if kind == "SetSequence":
        return _text("gui.variant_change_sequence") % (
            record,
            described.get("text", ""),
        )
    if kind == "SetName":
        return _text("gui.variant_change_job_name") % described.get("job_name", "")
    if kind in ("SetJobDescription", "SetDescription"):
        presence = described.get("presence", {})
        if presence.get("form") == "Present":
            value = presence.get("value", "")
        elif presence.get("form") == "ExplicitEmpty":
            value = _text("gui.variant_value_empty")
        else:
            value = _text("gui.variant_value_unset")
        key = (
            "gui.variant_change_description"
            if kind == "SetDescription"
            else "gui.variant_change_job_description"
        )
        if kind == "SetDescription":
            return _text(key) % (record, value)
        return _text(key) % value
    if kind == "SetSeeds":
        return _text("gui.variant_change_seeds") % ", ".join(
            str(value) for value in described.get("seeds", ())
        )
    if kind == "AddModification":
        return _text("gui.variant_change_add_mod") % (
            described.get("code", ""),
            described.get("position", 0),
            record,
        )
    if kind == "RemoveModification":
        return _text("gui.variant_change_remove_mod") % (
            described.get("index", 0),
            record,
        )
    if kind in ("SetAlignment", "SetSingleAlignment"):
        return _text("gui.variant_change_alignment") % (
            record,
            alignment_text(described.get("alignment", {})),
        )
    if kind == "SetReferences":
        references = described.get("references", {})
        if references.get("form", "") == "SearchAllowed":
            value = _text("gui.variant_route_search")
        else:
            value = _text("gui.variant_reference_count") % len(
                references.get("items", ())
            )
        return _text("gui.variant_change_references") % (record, value)
    if kind == "SetComponentCount":
        return _text("gui.variant_change_count") % (
            record,
            described.get("count", 0),
        )
    if kind == "SetComponentRepresentation":
        representation = described.get("representation", {})
        if representation.get("form") == "ByCode":
            value = ", ".join(representation.get("codes", ()))
        else:
            value = representation.get("text", "")
        return _text("gui.variant_change_representation") % (record, value)
    if kind == "AddRecord":
        family = {
            "FamilyARecord": _text("menu.family_protein"),
            "FamilyBRecord": _text("menu.family_rna"),
            "FamilyCRecord": _text("menu.family_dna"),
            "ComponentRecord": _text("menu.family_ligand"),
        }.get(described.get("family", ""), described.get("family", ""))
        return _text("gui.variant_change_add_record") % (
            family,
            ", ".join(described.get("ids", ())),
        )
    if kind == "RemoveRecord":
        return _text("gui.variant_change_remove_record") % described.get(
            "record_key", ""
        )
    if kind in ("AddLinkage", "RemoveLinkage"):
        return _text("gui.variant_change_bond")
    if kind == "SetComponentDefinition":
        return _text("gui.variant_change_definition")
    if kind == "SetFormatTarget":
        return _text("gui.variant_change_version")
    return _text("gui.variant_change_unknown")


def label(type_name: str) -> str:
    """The registry label for an internal type name.

    Unregistered names raise — the UI never falls back to a raw
    internal name (plan §3.1); ``FieldPath`` already refuses to carry
    one, so this only fires for a programming error here.
    """
    return label_for(type_name)


def labels(type_names) -> tuple:
    """Labels for a sequence of type names, in order."""
    return tuple(label_for(name) for name in type_names)


def mapping_ids(type_name: str) -> tuple:
    """The mapping IDs a type's label traces to (for the inspector and
    diagnostics where traceability is shown alongside the wording)."""
    return mapping_ids_for(type_name)


def with_record_label(type_name: str, record_key) -> str:
    """The context label for a finding pointed at a specific record.

    The registry vocabulary plus the chain identifier the registry
    itself allocated — no internal class names (plan §16.6)."""
    base = label_for(type_name)
    if record_key is None:
        return base
    return "%s %s" % (base, record_key)


def finding_context_label(field_path) -> str:
    """The context line for a ``FieldPath`` locator, entirely in
    registry vocabulary: ``"Protein chain A"`` or ``"Job details"``."""
    return with_record_label(field_path.type_name, field_path.record_key)


# Severity is always a word AND a symbol (plan §16.6: meaning survives
# without colour). Both are printed on every finding card.
SEVERITY_SYMBOLS = {"ERROR": "[x]", "WARNING": "[!]", "INFO": "[i]"}

# The plan's exact card tokens: "ERROR  [x]", "WARNING [!]", "INFO [i]".
_SEVERITY_FORMATS = {"ERROR": "%s  %s"}


def severity_label(severity) -> str:
    """``"ERROR  [x]"``-style severity rendering: word, then symbol."""
    name = severity.name if hasattr(severity, "name") else str(severity)
    symbol = SEVERITY_SYMBOLS.get(name, "[?]")
    fmt = _SEVERITY_FORMATS.get(name, "%s %s")
    return fmt % (name, symbol)


def finding_reference_label(number: int, severity, field_path) -> str:
    """The reference line of a jump-to-field finding card:
    ``"3. ERROR [x] — Protein chain A"`` (plan §16.6). The number is the
    token the user types; the wording is registry vocabulary only."""
    return _text("jump.reference") % (
        number,
        severity_label(severity),
        finding_context_label(field_path),
    )


def action_description(description_key: str) -> str:
    """An action's wording, from the string registry (the traceability
    registry is for domain *types*, not chrome)."""
    return _text(description_key)


def general_finding_context() -> str:
    """The group header for findings without a locator."""
    return _text("finding.context.general")
