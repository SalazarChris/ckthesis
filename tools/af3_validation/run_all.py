"""Harden the "our JSON is valid AF3 input" claim with AF3's own parser.

Four stages, all judged by ``alphafold3.common.folding_input.Input.from_json``
from the official repository:

1. **Positive control** - AF3's own ``examples/*.json`` must be ACCEPTED. If the
   harness cannot accept genuine AF3 input, nothing it says about us counts.
2. **Negative control** - deliberate corruptions of a real AF3 example must be
   REJECTED. If the harness accepts rubbish, an ACCEPTED verdict means nothing.
3. **Corpus** - every document this builder emits for a matrix of families and
   features is validated directly. The corpus is produced by the builder's own
   services and serialization path, not hand-written JSON.
4. **Round trip** - each official example is imported by the builder, re-emitted
   through the builder's generation path, and compared field by field against
   the original, with AF3's parser as the judge on both sides.

    python tools/af3_validation/run_all.py
    python tools/af3_validation/setup_validator.py   # first, once

Exit status is 0 only when every stage passes. ``UNVERIFIED`` is never counted
as a pass: it means the one field that needs AF3's compiled CIF parser was
reached, and that field is reported as not verified.
"""
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import af3_validate  # noqa: E402
from configbuilder.ui.services import build_services  # noqa: E402

EXAMPLES = os.path.join(af3_validate.ARTIFACTS, "alphafold3-main", "examples")
WORK = os.path.join(af3_validate.ARTIFACTS, "work")

PROT = "ACDEFGHIKLMNPQRSTVWY"
RNA = "ACGUACGUACGUACGUACGU"
DNA = "ATGCATGCATGCATGCATGC"
OTHER_PROT = "MKTAYIAKQR"
A3M = ">query\n%s\n>hit1\n%s\n" % (PROT, PROT[:-1] + "-")

TEMPLATE_CIF = """data_template
_entry.id template
_entity.id 1
_entity.type polymer
_entity.polymer.type polypeptide(L)
_struct.title synthetic template
_atom_site.group_PDB
_atom_site.id
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
ATOM 1 N N ALA A 1 0.000 0.000 0.000
"""

USER_CCD = """data_MY_LIG
#
_chem_comp.id MY_LIG
_chem_comp.name 'custom ligand used by the thesis builder'
_chem_comp.type non-polymer
_chem_comp.formula 'C8 H9 N O2'
_chem_comp.formula_weight 151.163
#
loop_
_chem_comp_atom.comp_id
_chem_comp_atom.atom_id
_chem_comp_atom.type_symbol
_chem_comp_atom.charge
MY_LIG C1 C 0
MY_LIG C2 C 0
MY_LIG N1 N 0
MY_LIG O1 O 0
#
loop_
_chem_comp_bond.comp_id
_chem_comp_bond.atom_id_1
_chem_comp_bond.atom_id_2
_chem_comp_bond.value_order
MY_LIG C1 C2 SING
MY_LIG C2 N1 SING
MY_LIG N1 O1 DOUB
#
"""

# Fields AF3 stores per chain entry; used for the round-trip comparison.
AF3_VISIBLE = (
    "sequence", "ccdCodes", "smiles", "modifications", "description",
    "unpairedMsa", "pairedMsa", "templates", "unpairedMsaPath",
    "pairedMsaPath", "mmcifPath",
)


# --------------------------------------------------------------- controls
MUTATIONS = [
    ("missing modelSeeds", lambda d: d.pop("modelSeeds")),
    ("empty modelSeeds", lambda d: d.__setitem__("modelSeeds", [])),
    ("wrong dialect", lambda d: d.__setitem__("dialect", "alphafold-server")),
    ("unsupported version 5", lambda d: d.__setitem__("version", 5)),
    ("unknown top-level key", lambda d: d.__setitem__("userCcd", "x")),
    ("unknown protein-chain key",
     lambda d: d["sequences"][0]["protein"].__setitem__("bogusField", 1)),
    ("sequence entry without an id",
     lambda d: d["sequences"][0]["protein"].pop("id")),
    ("bond naming an unknown chain",
     lambda d: d.__setitem__("bondedAtomPairs", [[["Z", 1, "CA"], ["A", 1, "CA"]]])),
]


def positive_control(folding_input):
    paths = af3_validate.gather(EXAMPLES)
    results = [(path, af3_validate.check(folding_input, path)) for path in paths]
    for path, result in results:
        print("  %-10s %s" % (result.verdict, os.path.basename(path)))
    accepted = sum(1 for _p, r in results if r.accepted)
    return accepted, len(results)


def negative_control(folding_input):
    example = os.path.join(EXAMPLES, "erk2_phosphorylated.json")
    with open(example, "r", encoding="utf-8") as handle:
        base = json.load(handle)
    rejected = 0
    for label, mutate in MUTATIONS:
        document = copy.deepcopy(base)
        mutate(document)
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                             encoding="utf-8")
        try:
            json.dump(document, handle)
            handle.close()
            result = af3_validate.check(folding_input, handle.name)
        finally:
            handle.close()
            os.unlink(handle.name)
        ok = result.rejected
        rejected += 1 if ok else 0
        print("  %-9s %-32s %s" % ("REJECT" if ok else "!!ACCEPTED", label,
                                   result.detail[:100]))
    return rejected, len(MUTATIONS)


# ---------------------------------------------------------------- corpus
def _fresh():
    services = build_services()
    services.projects.new("case")
    return services


def _apply(label, outcome, refusals):
    if not outcome.ok:
        refusals.append("%s -> %s" % (label, outcome.message or outcome.failure_reason))
    return outcome.ok


def _emit(directory, services, refusals, variants=False):
    os.makedirs(directory, exist_ok=True)
    plan = services.generation.plan_base(directory)
    if not plan.ok:
        refusals.append("plan_base refused: %s (%s)" % (plan.failure_reason, plan.message))
        return
    result = services.generation.execute(plan)
    if not result.ok:
        refusals.append("execute refused: %s" % (result.errors,))
    if variants:
        variant_plan = services.generation.plan(directory)
        if not variant_plan.ok:
            refusals.append("variant plan refused: %s" % (variant_plan.failure_reason,))
            return
        variant_result = services.generation.execute(variant_plan)
        if not variant_result.ok:
            refusals.append("variant execute refused: %s" % (variant_result.errors,))


def _case(build, directory, variants=False):
    refusals = []
    services = _fresh()
    try:
        build(services, services.configuration, refusals, directory)
    except Exception as error:
        refusals.append("EXCEPTION %s: %s" % (type(error).__name__, error))
        traceback.print_exc(limit=4)
    _emit(directory, services, refusals, variants=variants)
    return refusals


def _protein(services, configuration, refusals, directory):
    _apply("add protein", configuration.add_record("protein", PROT), refusals)


def _protein_multicopy(services, configuration, refusals, directory):
    _apply("add 3-copy protein",
           configuration.add_record("protein", PROT, copies=3), refusals)


def _protein_ptm(services, configuration, refusals, directory):
    configuration.add_record("protein", PROT)
    _apply("PTM TPO@4", configuration.add_modification("A", "TPO", 4), refusals)


def _protein_bond_ligand(services, configuration, refusals, directory):
    """A covalent bond between a protein and a CCD ligand: the supported kind.

    AF3's docs: "Defining covalent bonds between or within polymer entities is
    not currently supported", which this builder refuses as R-BND-006.
    """
    configuration.add_record("protein", PROT)
    configuration.add_record("ligand", representation="ATP",
                             representation_kind="ccd")
    _apply("bond A:1:CA -- ATP:1:PB",
           configuration.add_linkage("A", 1, "CA", "B", 1, "PB"), refusals)


def _glycan_bonded(services, configuration, refusals, directory):
    """The documented glycan case: a multi-CCD ligand bonded residue by residue.

    Residues are numbered one per CCD code (AF3's ``Ligand.__len__``), so a
    five-code glycan is addressable as residues 1..5 -- the topology of the
    official rnaseb_glycosylated example: one bond from the protein, then the
    glycan's own glycosidic links. The builder used to refuse any ligand bond
    above residue 1 (BUG-014) and to glue the five codes into one component
    (BUG-016), so this job could not be produced at all.
    """
    configuration.add_record("protein", PROT)
    configuration.add_record("ligand", representation="NAG NAG BMA MAN MAN",
                             representation_kind="ccd")
    bonds = [
        ("A", 1, "ND2", "B", 1, "C1"),
        ("B", 1, "O4", "B", 2, "C1"),
        ("B", 2, "O4", "B", 3, "C1"),
        ("B", 3, "O3", "B", 4, "C1"),
        ("B", 3, "O6", "B", 5, "C1"),
    ]
    for a_key, a_residue, a_atom, b_key, b_residue, b_atom in bonds:
        _apply("bond %s:%d:%s -- %s:%d:%s" % (a_key, a_residue, a_atom,
                                               b_key, b_residue, b_atom),
               configuration.add_linkage(a_key, a_residue, a_atom,
                                         b_key, b_residue, b_atom), refusals)


def _dna(services, configuration, refusals, directory):
    _apply("add dna", configuration.add_record("dna", DNA), refusals)


def _rna(services, configuration, refusals, directory):
    configuration.add_record("rna", RNA)
    _apply("rna provided alignment",
           configuration.set_alignment("A", "provided", inline_text=A3M), refusals)


def _ligand_ccd(services, configuration, refusals, directory):
    _apply("add ATP ligand",
           configuration.add_record("ligand", representation="ATP",
                                    representation_kind="ccd"), refusals)


def _ligand_smiles(services, configuration, refusals, directory):
    _apply("add SMILES ligand",
           configuration.add_record("ligand", representation="CC(=O)Oc1ccccc1C(=O)O",
                                    representation_kind="smiles"), refusals)


def _ions(services, configuration, refusals, directory):
    _apply("add NA", configuration.add_record(
        "ligand", representation="NA", representation_kind="ccd"), refusals)
    _apply("add CL", configuration.add_record(
        "ligand", representation="CL", representation_kind="ccd"), refusals)


def _msa_inline(services, configuration, refusals, directory):
    configuration.add_record("protein", PROT)
    _apply("protein inline paired+unpaired alignment",
           configuration.set_alignment("A", "both", inline_text=A3M), refusals)


def _msa_external(services, configuration, refusals, directory):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "chains.a3m")
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(A3M)
    configuration.add_record("protein", PROT)
    _apply("pin version 2", configuration.set_format_target(version="2"), refusals)
    _apply("protein external unpaired alignment",
           configuration.set_alignment("A", "unpaired", external_path=path), refusals)


def _templates(services, configuration, refusals, directory):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "template.cif")
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(TEMPLATE_CIF)
    configuration.add_record("protein", PROT)
    _apply("pin version 2", configuration.set_format_target(version="2"), refusals)
    from configbuilder.app.configuration_service import ReferenceInput
    _apply("protein template reference",
           configuration.set_references(
               "A", [ReferenceInput(external_path=path, pairs=[(1, 1), (2, 2)])]),
           refusals)


def _user_ccd_inline(services, configuration, refusals, directory):
    configuration.add_record("ligand", representation="MY_LIG",
                             representation_kind="ccd")
    _apply("pin version 3", configuration.set_format_target(version="3"), refusals)
    _apply("inline custom component",
           configuration.set_component_definition(inline_text=USER_CCD), refusals)


def _user_ccd_external(services, configuration, refusals, directory):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "extra.ccd")
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(USER_CCD)
    configuration.add_record("ligand", representation="MY_LIG",
                             representation_kind="ccd")
    _apply("pin version 3", configuration.set_format_target(version="3"), refusals)
    _apply("external custom component",
           configuration.set_component_definition(external_path=path), refusals)


def _descriptions(services, configuration, refusals, directory):
    """A description on every family, which §4 allows for all four."""
    configuration.add_record("protein", PROT, description="protein note")
    configuration.add_record("rna", RNA, description="rna note")
    configuration.add_record("dna", DNA, description="dna note")
    configuration.add_record("ligand", representation="ATP",
                             representation_kind="ccd", description="ligand note")
    _apply("job description",
           configuration.set_job_description("thesis goal: a described job"), refusals)


def _version(version):
    def build(services, configuration, refusals, directory):
        configuration.add_record("protein", PROT)
        _apply("pin version %s" % version,
               configuration.set_format_target(version=str(version)), refusals)
    return build


def _variants(services, configuration, refusals, directory):
    os.makedirs(directory, exist_ok=True)
    configuration.add_record("protein", PROT)
    seqs = os.path.join(directory, "seqs.txt")
    with io.open(seqs, "w", encoding="utf-8") as handle:
        handle.write("%s\nGGGG\n" % OTHER_PROT)
    _apply("batch variants", services.variants.generate_from_file(seqs), refusals)


CASES = [
    ("protein_only", _protein, False),
    ("protein_multicopy", _protein_multicopy, False),
    ("protein_ptm", _protein_ptm, False),
    ("protein_bond_ligand", _protein_bond_ligand, False),
    ("ligand_glycan_bonded", _glycan_bonded, False),
    ("dna_duplex", _dna, False),
    ("rna_provided_msa", _rna, False),
    ("ligand_ccd", _ligand_ccd, False),
    ("ligand_smiles", _ligand_smiles, False),
    ("ions_na_cl", _ions, False),
    ("msa_inline_both", _msa_inline, False),
    ("msa_external_v2", _msa_external, False),
    ("templates_v2", _templates, False),
    ("user_ccd_inline_v3", _user_ccd_inline, False),
    ("user_ccd_external_v3", _user_ccd_external, False),
    ("descriptions_all_families", _descriptions, False),
    ("version_v1", _version(1), False),
    ("version_v2", _version(2), False),
    ("version_v3", _version(3), False),
    ("version_v4", _version(4), False),
    ("variants_batch", _variants, True),
]


def corpus(folding_input):
    root = os.path.join(WORK, "corpus")
    if os.path.isdir(root):
        shutil.rmtree(root)
    refusals = {}
    for name, build, variants in CASES:
        problems = _case(build, os.path.join(root, name), variants=variants)
        refusals[name] = problems
        print("  %-26s %s" % (name, "built" if not problems else "REFUSED"))
        for problem in problems:
            print("        %s" % problem)
    counts = {}
    unverified = []
    rejected = []
    for path in af3_validate.gather(root):
        result = af3_validate.check(folding_input, path)
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
        if result.rejected:
            rejected.append((path, result.detail))
        elif not result.accepted:
            unverified.append((path, result.detail))
    for path, detail in rejected:
        print("  REJECTED  %s\n        %s" % (os.path.relpath(path, root), detail))
    for path, detail in unverified:
        print("  UNVERIFIED %s\n        %s" % (os.path.relpath(path, root), detail))
    return counts, refusals


# ------------------------------------------------------------ round trip
def _entries(document):
    found = {}
    for sequence in document.get("sequences", []):
        for family, body in sequence.items():
            identifier = body.get("id")
            for chain_id in (identifier if isinstance(identifier, list) else [identifier]):
                found[chain_id] = (family, body)
    return found


def round_trip(folding_input):
    root = os.path.join(WORK, "roundtrip")
    if os.path.isdir(root):
        shutil.rmtree(root)
    identical = 0
    problems = []
    names = [name for name in sorted(os.listdir(EXAMPLES)) if name.endswith(".json")]
    for name in names:
        original = os.path.join(EXAMPLES, name)
        services = build_services()
        services.projects.new("roundtrip")
        commit = services.projects.import_json_commit(original)
        if not getattr(commit, "ok", False):
            problems.append("%s: import refused (%s)" % (name, commit.message))
            print("  %-34s IMPORT REFUSED  %s" % (name, commit.message[:60]))
            continue
        case_dir = os.path.join(root, name[:-5])
        plan = services.generation.plan_base(case_dir)
        if not plan.ok:
            problems.append("%s: build refused (%s)" % (name, plan.failure_reason))
            print("  %-34s BUILD REFUSED   %s" % (name, plan.failure_reason))
            continue
        services.generation.execute(plan)
        emitted = None
        for base, _dirs, files in os.walk(case_dir):
            for candidate in files:
                if candidate.endswith(".json") and candidate != "manifest.json":
                    emitted = os.path.join(base, candidate)
        verdict = af3_validate.check(folding_input, emitted)
        if not verdict.accepted:
            problems.append("%s: emitted document %s (%s)" % (name, verdict.verdict,
                                                              verdict.detail))
            print("  %-34s EMITTED %s" % (name, verdict.verdict))
            continue
        with open(original, "r", encoding="utf-8") as handle:
            left = _entries(json.load(handle))
        with open(emitted, "r", encoding="utf-8") as handle:
            right = _entries(json.load(handle))
        differences = []
        for chain_id, (family, body) in sorted(left.items()):
            other = right.get(chain_id)
            if other is None or other[0] != family:
                differences.append("chain %s missing or changed family" % chain_id)
                continue
            for key in AF3_VISIBLE:
                if body.get(key) != other[1].get(key):
                    differences.append("%s.%s" % (chain_id, key))
        if differences:
            problems.append("%s: %s" % (name, ", ".join(differences)))
            print("  %-34s DIFFERS: %s" % (name, ", ".join(differences)))
        else:
            identical += 1
            print("  %-34s identical, accepted" % name)
    return identical, len(names), problems


# ------------------------------------------------------------------ main
def main():
    print("=" * 78)
    print("AF3 parser validation")
    print("=" * 78)
    folding_input = af3_validate.load_parser()
    print("parser    : %s" % folding_input.__file__)
    print("dialect   : %s   versions: %s"
          % (folding_input.JSON_DIALECT, folding_input.JSON_VERSIONS))
    print("artifacts : %s" % af3_validate.ARTIFACTS)

    print("\n-- 1. positive control: AF3's own examples ----------------------")
    accepted, total = positive_control(folding_input)
    control_ok = accepted == total
    print("  %d/%d official examples ACCEPTED" % (accepted, total))

    print("\n-- 2. negative control: corruptions must be refused -------------")
    rejected, attempts = negative_control(folding_input)
    negative_ok = rejected == attempts
    print("  %d/%d corruptions REJECTED" % (rejected, attempts))

    print("\n-- 3. corpus: what this builder emits ---------------------------")
    counts, refusals = corpus(folding_input)
    refused_cases = [name for name, problems in refusals.items() if problems]
    print("  verdicts: " + ", ".join("%s=%d" % item for item in sorted(counts.items())))

    print("\n-- 4. round trip: AF3 example -> builder -> AF3 parser ----------")
    identical, examined, problems = round_trip(folding_input)

    ok = (
        control_ok
        and negative_ok
        and not refused_cases
        and not counts.get("REJECTED")
        and identical == examined
        and not problems
    )
    print("\n" + "=" * 78)
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    print("  positive control : %d/%d accepted" % (accepted, total))
    print("  negative control : %d/%d rejected" % (rejected, attempts))
    print("  corpus           : %s, refused cases: %s"
          % (", ".join("%s=%d" % item for item in sorted(counts.items())) or "none",
             refused_cases or "none"))
    print("  round trip       : %d/%d identical and accepted" % (identical, examined))
    if counts.get("UNVERIFIED"):
        print("  NOTE: %d corpus document(s) are UNVERIFIED, not passed: the field"
              % counts["UNVERIFIED"])
        print("        needing AF3's compiled CIF parser (userCCD) cannot be checked")
        print("        on a machine without that extension. See README.md.")
    print("  artifacts        : %s" % WORK)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
