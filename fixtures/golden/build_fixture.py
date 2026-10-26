"""Golden fixture builder (CHECKLIST Phase 6).

``fixtures/golden/project/<name>/recipe.json`` describes a configuration in
a neutral, human-readable form (provenance label ``project``: authored in
this repository, not observed from the deployment). ``build`` constructs
the canonical model from a recipe and returns
``encode(to_wire(configuration))`` — the exact bytes of a generated file.

A recipe describes *model content only*; it never names wire fields, so
the fixture bytes remain meaningful even if the mapping tables change
(and a change then shows up as a golden diff to be reviewed, not silently
absorbed).

Usage::

    python fixtures/golden/build_fixture.py <recipe-dir> [<recipe-dir> ...]
    python fixtures/golden/build_fixture.py --all
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity  # noqa: E402
from configbuilder.model import (  # noqa: E402
    AlignmentAutomatic,
    AlignmentBoth,
    AlignmentFree,
    AlignmentPairedOnly,
    AlignmentUnpairedOnly,
    ByCode,
    ByNotation,
    ComponentCode,
    ComponentRecord,
    Configuration,
    ConfigurationMetadata,
    Explicit,
    ExplicitEmpty,
    External,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    FormatTarget,
    IndexPair,
    Inline,
    LinkEndpoint,
    Linkage,
    ModificationRecord,
    PathSpec,
    Pinned,
    Position,
    Present,
    ReferenceRecord,
    ResidueRef,
    SearchAllowed,
    SeedSet,
    SequenceText,
    SingleProvided,
    Unset,
)
from configbuilder.serialize import encode  # noqa: E402
from configbuilder.transform import to_wire  # noqa: E402

GOLDEN_ROOT = Path(__file__).resolve().parent


# -- recipe decoders (model content only — no wire field names) -------------------


def _resource(spec):
    if "inline" in spec:
        return Inline(spec["inline"])
    return External(PathSpec(spec["path"]))


def _description(spec):
    state = spec["state"]
    if state == "unset":
        return Unset()
    if state == "empty":
        return ExplicitEmpty()
    return Present(spec["text"])


_ALIGNMENT_KINDS = {
    "automatic": AlignmentAutomatic,
    "free": AlignmentFree,
    "unpaired_only": AlignmentUnpairedOnly,
    "paired_only": AlignmentPairedOnly,
    "both": AlignmentBoth,
}


def _alignment(spec):
    try:
        cls = _ALIGNMENT_KINDS[spec["kind"]]
    except KeyError:
        raise ValueError("unknown alignment kind %r" % (spec["kind"],)) from None
    if spec["kind"] in ("automatic", "free"):
        return cls()
    return cls(source=_resource(spec["source"]))


def _references(spec):
    if spec is None or spec.get("kind") != "explicit":
        return SearchAllowed()
    items = tuple(
        ReferenceRecord(
            source=_resource(item["source"]),
            index_map=tuple(IndexPair(q, t) for q, t in item.get("index_map", ())),
        )
        for item in spec["items"]
    )
    return Explicit(items)


def _representation(spec):
    if "by_code" in spec:
        return ByCode(tuple(ComponentCode(code) for code in spec["by_code"]))
    return ByNotation(spec["by_notation"])


_FAMILY_CLASSES = {
    "protein": FamilyARecord,
    "rna": FamilyBRecord,
    "dna": FamilyCRecord,
    "ligand": ComponentRecord,
}


def _record(spec):
    try:
        cls = _FAMILY_CLASSES[spec["family"]]
    except KeyError:
        raise ValueError("unknown family %r" % (spec["family"],)) from None

    family = spec["family"]
    kwargs = {}
    if "description" in spec:
        kwargs["description"] = _description(spec["description"])
    if "sequence" in spec:
        kwargs["sequence"] = SequenceText(spec["sequence"], family)
    if family == "protein":
        if "alignment" in spec:
            kwargs["alignment"] = _alignment(spec["alignment"])
        if "references" in spec:
            kwargs["references"] = _references(spec["references"])
        if "modifications" in spec:
            kwargs["modifications"] = tuple(
                ModificationRecord(code=ComponentCode(m["code"]), position=Position(m["position"]))
                for m in spec["modifications"]
            )
    if family == "rna" and "alignment" in spec:
        kwargs["alignment"] = SingleProvided(source=_resource(spec["alignment"]["source"]))
    if family == "ligand":
        kwargs["representation"] = _representation(spec["representation"])
    return cls(ids=Multiplicity(spec["ids"]), **kwargs)


def build(recipe_dir):
    """Build a fixture directory's golden bytes from its recipe."""
    recipe = json.loads((recipe_dir / "recipe.json").read_text(encoding="utf-8"))
    records = tuple(_record(spec) for spec in recipe["records"])
    linkages = tuple(
        Linkage(
            LinkEndpoint(EntityId(pair["a"][0]), ResidueRef(pair["a"][1]), pair["a"][2]),
            LinkEndpoint(EntityId(pair["b"][0]), ResidueRef(pair["b"][1]), pair["b"][2]),
        )
        for pair in recipe.get("linkages", ())
    )
    definition = recipe.get("component_definition")
    component_definition = None
    if definition is not None:
        component_definition = (
            Inline(definition["inline"])
            if "inline" in definition
            else External(PathSpec(definition["path"]))
        )
    configuration = Configuration(
        metadata=ConfigurationMetadata(recipe["metadata"]["name"]),
        seeds=SeedSet(list(recipe["seeds"])),
        records=records,
        linkages=linkages,
        component_definition=component_definition,
        identity=IdentityRegistry(),
    ).with_format_target(FormatTarget(version_selection=Pinned(recipe["version"])))
    return encode(to_wire(configuration).document)


def fixture_dirs():
    """Every ``fixtures/golden/project/<name>/`` directory with a recipe."""
    return sorted(p for p in GOLDEN_ROOT.glob("project/*/") if (p / "recipe.json").exists())


def main(argv):
    targets = fixture_dirs() if argv == ["--all"] else [Path(arg) for arg in argv]
    for directory in targets:
        if not (directory / "recipe.json").exists():
            directory = GOLDEN_ROOT / "project" / directory.name
        data = build(directory)
        golden = directory / "golden.json"
        golden.write_bytes(data)
        print("wrote %s (%d bytes)" % (golden, len(data)))


if __name__ == "__main__":
    main(sys.argv[1:])
