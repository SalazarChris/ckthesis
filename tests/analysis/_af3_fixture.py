"""Synthetic AF3 output directories for the analysis tests.

The tests must not need real predictions, so this module writes the *shape* of an
AF3 output tree: per-sample folders with a model mmCIF, a full confidence JSON
and a summary confidence JSON, plus the root-level ranking scores, processed
input and (optionally) a top-ranked copy beside the sample folders.

The geometry is crude but not trivial: a two-domain backbone whose second domain
can be rotated and translated, so RMSD, per-residue displacement and inter-domain
orientation metrics have something real to measure.  Every value is deterministic
(seeded ``numpy.random.default_rng`` and a CRC-based PAE seed), so a test can
assert exact reproducibility rather than compare against golden numbers.
"""

from __future__ import annotations

import json
import math
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from af3_analysis.chemistry import AA1_TO_3
from af3_analysis.io import ModelStructure

PROTEIN_ATOMS = ("N", "CA", "C", "O")
PHOSPHO_ATOMS = {
    "SEP": ("P", "O1P", "O2P", "O3P", "CB", "OG"),
    "TPO": ("P", "O1P", "O2P", "O3P", "CB", "OG1"),
}
DNA_ATOMS = ("P", "OP1", "OP2", "O5'", "C5'", "C4'", "O4'", "C3'", "O3'", "C2'",
             "C1'", "N1")
DNA_COMPONENT = {"A": "DA", "C": "DC", "G": "DG", "T": "DT", "U": "DU"}

AtomRow = Tuple[str, str, float, float, float, float]  # name, element, x, y, z, b


def element_of(atom_name: str) -> str:
    name = atom_name.strip().upper()
    if name in ("CA", "CB", "CG", "CD", "CE", "CZ"):
        return "C"
    return name[0]


def rotation_matrix(axis: Sequence[float], degrees: float) -> np.ndarray:
    vector = np.asarray(axis, dtype=float)
    vector = vector / np.linalg.norm(vector)
    angle = math.radians(degrees)
    cross = np.array([[0.0, -vector[2], vector[1]],
                      [vector[2], 0.0, -vector[0]],
                      [-vector[1], vector[0], 0.0]])
    return np.eye(3) + math.sin(angle) * cross + (1 - math.cos(angle)) * (cross @ cross)


def _backbone(index: int, plddt: float) -> List[AtomRow]:
    x = index * 3.8
    return [
        ("N", "N", x - 1.2, 0.4, 0.0, plddt - 2.0),
        ("CA", "C", x, 0.0, 0.0, plddt),
        ("C", "C", x + 1.1, -0.3, 0.0, plddt - 1.0),
        ("O", "O", x + 1.1, -1.5, 0.0, plddt - 3.0),
    ]


class ConditionGeometry:
    """Deterministic geometry for one condition."""

    def __init__(
        self,
        sequence: str,
        ptm_positions: Sequence[int] = (),
        ptm_component: str = "SEP",
        seed: int = 0,
        second_domain_rotation_deg: float = 0.0,
        second_domain_offset: float = 0.0,
        jitter: float = 0.02,
        plddt_base: float = 85.0,
        plddt_ptm_drop: float = 0.0,
        plddt_domain2_drop: float = 0.0,
        domain_split: int = 0,
    ):
        self.sequence = sequence
        self.ptm_positions = tuple(ptm_positions)
        self.ptm_component = ptm_component
        self.seed = seed
        self.domain_split = domain_split or max(1, len(sequence) // 2)
        self.second_domain_rotation_deg = second_domain_rotation_deg
        self.second_domain_offset = second_domain_offset
        self.jitter = jitter
        self.plddt_base = plddt_base
        self.plddt_ptm_drop = plddt_ptm_drop
        self.plddt_domain2_drop = plddt_domain2_drop
        self.rng = np.random.default_rng(seed)

    # -- geometry ----------------------------------------------------------

    def protein_residues(self) -> Tuple[Dict[int, List[AtomRow]], Dict[int, str]]:
        atoms_by_residue: Dict[int, List[AtomRow]] = {}
        components: Dict[int, str] = {}
        rotation = rotation_matrix((0.0, 1.0, 0.0), self.second_domain_rotation_deg)
        shift = np.array([self.second_domain_offset, 0.0, 0.0])
        for index, letter in enumerate(self.sequence, start=1):
            plddt = self.plddt_base + float(self.rng.normal(0.0, 1.0))
            if index > self.domain_split:
                plddt -= self.plddt_domain2_drop
            atoms = _backbone(index, plddt)
            component = AA1_TO_3.get(letter, "GLY")
            if index in self.ptm_positions:
                component = self.ptm_component
                plddt -= self.plddt_ptm_drop
                for position, atom_name in enumerate(PHOSPHO_ATOMS[component]):
                    atoms.append((
                        atom_name, element_of(atom_name),
                        1.0 + 1.3 * position, 2.0 + 0.3 * position, 0.5,
                        plddt - 4.0,
                    ))
            if index > self.domain_split:
                transformed = []
                for (name, element, x, y, z, bfactor) in atoms:
                    point = rotation @ np.array([x, y, z]) + shift
                    transformed.append((name, element, float(point[0]),
                                        float(point[1]), float(point[2]), bfactor))
                atoms = transformed
            atoms_by_residue[index] = atoms
            components[index] = component
        return atoms_by_residue, components

    def dna_residues(
        self, sequence: str, offset: Sequence[float]
    ) -> Tuple[Dict[int, List[AtomRow]], Dict[int, str]]:
        atoms_by_residue: Dict[int, List[AtomRow]] = {}
        components: Dict[int, str] = {}
        shift = np.asarray(offset, dtype=float)
        for index, letter in enumerate(sequence, start=1):
            origin = np.array([index * 6.0, 12.0, 0.0]) + shift
            atoms: List[AtomRow] = []
            for position, atom_name in enumerate(DNA_ATOMS):
                atoms.append((
                    atom_name, element_of(atom_name),
                    float(origin[0] + 0.4 * position),
                    float(origin[1] + 0.2 * position),
                    float(origin[2] + 0.1 * position),
                    80.0 + float(self.rng.normal(0.0, 1.0)),
                ))
            # the base atom points back towards the protein so an interface exists
            atoms[-1] = ("N1", "N", float(origin[0] - 2.0), 4.0,
                         float(origin[2]), 82.0)
            atoms_by_residue[index] = atoms
            components[index] = DNA_COMPONENT.get(letter, "DA")
        return atoms_by_residue, components


def _jitter(atoms: List[AtomRow], rng: np.random.Generator, jitter: float) -> List[AtomRow]:
    if jitter <= 0:
        return list(atoms)
    noise = rng.normal(0.0, jitter, size=3)
    return [
        (name, element, float(x + noise[0]), float(y + noise[1]),
         float(z + noise[2]), bfactor)
        for (name, element, x, y, z, bfactor) in atoms
    ]


def write_condition(
    root: Path,
    name: str,
    geometry: ConditionGeometry,
    seeds: Sequence[int] = (1, 2),
    samples: int = 2,
    dna_strands: Sequence[str] = (),
    dna_chain_ids: Sequence[str] = ("B", "C"),
    ranking_base: float = 0.7,
    write_top_ranked: bool = True,
) -> Path:
    """Write a complete synthetic AF3 output directory for one condition."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    protein_chain = "A"
    protein_atoms, protein_components = geometry.protein_residues()
    dna_offsets = ([0.0, 0.0, 0.0], [0.0, 7.0, 0.0])

    ranking_rows = ["seed,sample,ranking_score"]
    best: Optional[Tuple[float, int, int]] = None
    for seed in seeds:
        for sample in range(samples):
            score = ranking_base + 0.01 * seed + 0.001 * sample
            ranking_rows.append("%d,%d,%.10f" % (seed, sample, score))
            if best is None or score > best[0]:
                best = (score, seed, sample)
            _write_sample(
                geometry, root / ("seed-%d_sample-%d" % (seed, sample)), name,
                seed, sample,
                {protein_chain: (protein_atoms, protein_components)},
                dna_strands, dna_chain_ids, dna_offsets, protein_chain,
            )
    (root / ("%s_ranking_scores.csv" % name)).write_text(
        "\n".join(ranking_rows) + "\n", encoding="utf-8", newline="\n")
    _write_processed_input(geometry, root / ("%s_data.json" % name), name, seeds,
                           protein_chain, dna_strands, dna_chain_ids)
    if write_top_ranked and best is not None:
        _write_sample(
            geometry, root, name, best[1], best[2],
            {protein_chain: (protein_atoms, protein_components)},
            dna_strands, dna_chain_ids, dna_offsets, protein_chain,
        )
    return root


def _write_sample(
    geometry: ConditionGeometry,
    directory: Path,
    name: str,
    seed: int,
    sample: int,
    protein: Dict[str, Tuple[Dict[int, List[AtomRow]], Dict[int, str]]],
    dna_strands: Sequence[str],
    dna_chain_ids: Sequence[str],
    dna_offsets: Sequence[Sequence[float]],
    protein_chain: str,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(zlib.crc32(("%s-%d-%d" % (name, seed, sample)).encode()))
    chains: Dict[str, Tuple[Dict[int, List[AtomRow]], Dict[int, str]]] = {}
    for chain_id, (residues, components) in protein.items():
        chains[chain_id] = (
            {res_id: _jitter(atoms, rng, geometry.jitter)
             for res_id, atoms in residues.items()},
            components,
        )
    for index, strand in enumerate(dna_strands):
        chain_id = dna_chain_ids[index % len(dna_chain_ids)]
        chains[chain_id] = geometry.dna_residues(strand, dna_offsets[index % len(dna_offsets)])

    prefix = "%s_seed-%d_sample-%d" % (name, seed, sample) if directory.name != name else name
    _write_cif(directory / ("%s_model.cif" % prefix), name, chains)
    _write_confidence(directory / ("%s_confidences.json" % prefix), chains, name,
                      seed, sample)
    _write_summary(directory / ("%s_summary_confidences.json" % prefix), chains,
                   protein_chain, geometry, seed, sample)


def _write_cif(
    path: Path,
    name: str,
    chains: Dict[str, Tuple[Dict[int, List[AtomRow]], Dict[int, str]]],
) -> None:
    lines = [
        "# Synthetic AF3-style model written by tests/analysis/_af3_fixture.py",
        "data_%s" % name,
        "#",
        "loop_",
        "_atom_site.group_PDB",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        "_atom_site.label_alt_id",
        "_atom_site.label_comp_id",
        "_atom_site.label_asym_id",
        "_atom_site.label_entity_id",
        "_atom_site.label_seq_id",
        "_atom_site.pdbx_PDB_ins_code",
        "_atom_site.Cartn_x",
        "_atom_site.Cartn_y",
        "_atom_site.Cartn_z",
        "_atom_site.occupancy",
        "_atom_site.B_iso_or_equiv",
        "_atom_site.auth_seq_id",
        "_atom_site.auth_asym_id",
        "_atom_site.pdbx_PDB_model_num",
    ]
    serial = 0
    for chain_id, (residues, components) in chains.items():
        for res_id in sorted(residues):
            for (atom_name, element, x, y, z, bfactor) in residues[res_id]:
                serial += 1
                lines.append(
                    "ATOM %-6d %-2s %-4s . %-3s %s 1 %-4d ? %8.3f %8.3f %8.3f "
                    "1.00 %6.2f %d %s 1"
                    % (serial, element, atom_name, components.get(res_id, "GLY"),
                       chain_id, res_id, x, y, z, bfactor, res_id, chain_id)
                )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _tokens(
    chains: Dict[str, Tuple[Dict[int, List[AtomRow]], Dict[int, str]]]
) -> Tuple[List[str], List[int]]:
    chain_ids: List[str] = []
    res_ids: List[int] = []
    for chain_id, (residues, _components) in chains.items():
        for res_id in sorted(residues):
            chain_ids.append(chain_id)
            res_ids.append(res_id)
            names = {atom[0] for atom in residues[res_id]}
            if "O1P" in names:
                # AF3 tokenises a modified residue as several atom-level tokens
                # that all carry the same residue id.
                chain_ids.append(chain_id)
                res_ids.append(res_id)
    return chain_ids, res_ids


def _write_confidence(
    path: Path,
    chains: Dict[str, Tuple[Dict[int, List[AtomRow]], Dict[int, str]]],
    name: str,
    seed: int,
    sample: int,
) -> None:
    token_chain_ids, token_res_ids = _tokens(chains)
    n_tokens = len(token_chain_ids)
    rng = np.random.default_rng(zlib.crc32(("%s-%d-%d-pae" % (name, seed, sample)).encode()))
    pae = 3.0 + 6.0 * rng.random((n_tokens, n_tokens))
    pae = (pae + pae.T) / 2.0
    contact = rng.random((n_tokens, n_tokens)) * 0.2
    contact = (contact + contact.T) / 2.0
    atom_plddts: List[float] = []
    atom_chain_ids: List[str] = []
    for chain_id, (residues, _components) in chains.items():
        for res_id in sorted(residues):
            for atom in residues[res_id]:
                atom_plddts.append(round(float(atom[5]), 2))
                atom_chain_ids.append(chain_id)
    document = {
        "pae": [[round(float(value), 3) for value in row] for row in pae],
        "contact_probs": [[round(float(value), 3) for value in row] for row in contact],
        "atom_plddts": atom_plddts,
        "atom_chain_ids": atom_chain_ids,
        "token_chain_ids": token_chain_ids,
        "token_res_ids": token_res_ids,
    }
    path.write_text(json.dumps(document), encoding="utf-8", newline="\n")


def _write_summary(
    path: Path,
    chains: Dict[str, Tuple[Dict[int, List[AtomRow]], Dict[int, str]]],
    protein_chain: str,
    geometry: ConditionGeometry,
    seed: int,
    sample: int,
) -> None:
    order = list(chains.keys())
    n_chains = len(order)
    pair_iptm = []
    pair_pae = []
    for i in range(n_chains):
        row_iptm = []
        row_pae = []
        for j in range(n_chains):
            if i == j:
                row_iptm.append(0.85)
                row_pae.append(0.75)
            else:
                row_iptm.append(0.72 if protein_chain in (order[i], order[j]) else 0.05)
                row_pae.append(1.05)
        pair_iptm.append(row_iptm)
        pair_pae.append(row_pae)
    score = 0.6 + 0.02 * seed + 0.001 * sample
    document = {
        "chain_ids": order,
        "chain_iptm": [0.8 if chain == protein_chain else 0.4 for chain in order],
        "chain_pair_iptm": pair_iptm,
        "chain_pair_pae_min": pair_pae,
        "chain_ptm": [0.8 if chain == protein_chain else 0.05 for chain in order],
        "fraction_disordered": 0.0,
        "has_clash": 0.0,
        "iptm": 0.72 if n_chains > 1 else None,
        "ptm": round(score, 3),
        "ranking_score": round(score, 3),
    }
    path.write_text(json.dumps(document, indent=1), encoding="utf-8", newline="\n")


def _write_processed_input(
    geometry: ConditionGeometry,
    path: Path,
    name: str,
    seeds: Sequence[int],
    protein_chain: str,
    dna_strands: Sequence[str],
    dna_chain_ids: Sequence[str],
) -> None:
    modifications = [
        {"ptmType": geometry.ptm_component, "ptmPosition": position}
        for position in geometry.ptm_positions
    ]
    sequences: List[Dict[str, object]] = [
        {"protein": {"id": protein_chain, "sequence": geometry.sequence,
                     "modifications": modifications, "unpairedMsa": ">query\n",
                     "pairedMsa": ">query\n", "templates": []}}
    ]
    for index, strand in enumerate(dna_strands):
        sequences.append({"dna": {"id": dna_chain_ids[index % len(dna_chain_ids)],
                                  "sequence": strand, "modifications": []}})
    document = {
        "name": name,
        "modelSeeds": list(seeds),
        "sequences": sequences,
        "dialect": "alphafold3",
        "version": 3,
        "bondedAtomPairs": None,
        "userCCD": None,
    }
    path.write_text(json.dumps(document), encoding="utf-8", newline="\n")


def write_config(
    directory: Path,
    conditions: Sequence[Dict[str, object]],
    regions: Sequence[Dict[str, object]],
    sequence: str,
    reference_id: str = "REF",
    comparisons: Sequence[Dict[str, object]] = (),
    analysis_yaml: str = "",
) -> Path:
    """Write a config tree (conditions/regions/analysis_config) and return its path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    condition_keys = (
        "condition_id", "name", "output_dir", "reference_id", "variant_type",
        "ptm_state", "ptm_positions_reference", "dna_present", "construct_start",
        "construct_end", "seeds", "samples_per_seed", "input_json", "data_json",
        "ranking_scores", "notes",
    )
    rows = [",".join(condition_keys)]
    for condition in conditions:
        rows.append(",".join(str(condition.get(key, "")) for key in condition_keys))
    (directory / "conditions.csv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8", newline="\n")

    region_rows = ["region_id,reference_id,start,end,role,rationale,use_plddt,"
                   "use_rmsd,use_pae_contacts"]
    for region in regions:
        region_rows.append("%s,%s,%s,%s,%s,%s,%s,%s,%s" % (
            region["region_id"], region.get("reference_id", reference_id),
            region["start"], region["end"], region.get("role", "domain"),
            region.get("rationale", ""), region.get("use_plddt", "true"),
            region.get("use_rmsd", "true"), region.get("use_pae_contacts", "true"),
        ))
    (directory / "regions.csv").write_text(
        "\n".join(region_rows) + "\n", encoding="utf-8", newline="\n")

    lines = [
        "project: synthetic analysis test",
        "output_root: ./analysis",
        "reference_sequences:",
        "  - reference_id: %s" % reference_id,
        "    name: synthetic reference",
        "    sequence: >-",
        "      %s" % sequence,
        "conditions: conditions.csv",
        "regions: regions.csv",
    ]
    if comparisons:
        lines.append("comparisons:")
        for comparison in comparisons:
            lines.append("  - comparison_id: %s" % comparison["comparison_id"])
            lines.append("    variant: %s" % comparison["variant"])
            lines.append("    reference: %s" % comparison["reference"])
            lines.append("    factor_changed: %s"
                         % comparison.get("factor_changed", "PTM"))
            lines.append("    region: %s" % comparison.get("region", "PTM_LOCAL"))
            lines.append("    metrics: [%s]"
                         % ", ".join(comparison.get("metrics", [])))
            lines.append("    comparison_type: %s"
                         % comparison.get("comparison_type", "primary"))
    if analysis_yaml:
        lines.append(analysis_yaml.rstrip())
    (directory / "analysis_config.yaml").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return directory / "analysis_config.yaml"


def read_model(path: Path) -> ModelStructure:
    from af3_analysis.io import read_structure

    return read_structure(path)
