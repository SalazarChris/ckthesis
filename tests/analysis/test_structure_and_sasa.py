"""Superposition, contacts, geometry and solvent accessibility (SOP §3.2, §3.7)."""

from __future__ import annotations

import pytest

# The analysis stack is an optional extra (see pyproject.toml), and numpy and
# pandas are its hard requirements.  The guard sits before every other import in
# this module on purpose: on an interpreter without them the honest result is
# "not tested here", not an ImportError in the middle of the suite (CI installs
# the builder's dev extra only).
pytest.importorskip("numpy", reason="af3_analysis requires numpy")
pytest.importorskip("pandas", reason="af3_analysis requires pandas")

import pathlib
from pathlib import Path

import numpy as np

from af3_analysis import sasa, structure
from af3_analysis.io import Atom, ModelStructure, Residue, read_structure
from af3_analysis.structure import heavy_atom_contacts, kabsch, principal_axis, rmsd
from tests.analysis._af3_fixture import ConditionGeometry, rotation_matrix, write_condition

SEQUENCE = "MAGSTVKLDEQSAAGSTVKLDEQP"


def _bio_atoms(coordinates):
    from Bio.PDB.Atom import Atom as BioAtom

    return [
        BioAtom("CA", np.asarray(coord, dtype=float), 1.0, 1.0, " ", " CA ",
                index + 1, "C")
        for index, coord in enumerate(coordinates)
    ]


def test_kabsch_agrees_with_biopython_superimposer():
    pytest.importorskip("Bio.PDB", reason="Biopython is the superposition reference")
    from Bio.PDB import Superimposer

    rng = np.random.default_rng(11)
    fixed = rng.normal(size=(25, 3)) * 5.0
    rotation = rotation_matrix((0.3, 1.0, 0.2), 37.0)
    mobile = fixed @ rotation.T + np.array([4.0, -2.0, 7.0])

    mine = kabsch(fixed, mobile)
    superimposer = Superimposer()
    superimposer.set_atoms(_bio_atoms(fixed), _bio_atoms(mobile))

    assert mine.rmsd == pytest.approx(superimposer.rms, abs=1e-6)
    assert mine.n_pairs == 25
    assert np.allclose(mine.apply(mobile), fixed, atol=1e-6)
    assert mine.rotation_angle_deg() == pytest.approx(37.0, abs=1e-6)


def test_kabsch_needs_three_pairs():
    with pytest.raises(ValueError):
        kabsch(np.zeros((2, 3)), np.zeros((2, 3)))


def test_rmsd_without_fitting():
    fixed = np.zeros((3, 3))
    mobile = np.array([[3.0, 0.0, 0.0], [3.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
    assert rmsd(fixed, mobile) == pytest.approx(3.0)


def _structure(residues) -> ModelStructure:
    """Build an in-memory ModelStructure from ``{chain: {res_id: [(name, el, x, y, z)]}}``."""
    built = []
    for chain_id, entries in residues.items():
        for res_id, atoms in entries.items():
            residue = Residue(chain_id=chain_id, res_id=res_id, icode="",
                              comp_id="GLY", entity="protein")
            for name, element, x, y, z in atoms:
                residue.atoms.append(Atom(
                    chain_id=chain_id, res_id=res_id, icode="", comp_id="GLY",
                    atom_name=name, element=element, x=x, y=y, z=z, bfactor=90.0,
                    hetero=False,
                ))
            built.append(residue)
    return ModelStructure(path=pathlib.Path("memory.cif"), residues=tuple(built))


def test_heavy_atom_contacts_counts_pairs_within_the_cutoff():
    residues = {index + 1: [("CA", "C", float(index * 2.0), 0.0, 0.0)]
                for index in range(6)}
    built = _structure({"A": residues})
    assert heavy_atom_contacts(built, "A", [1, 2], "A", [2, 3], 3.0) == 2
    assert heavy_atom_contacts(built, "A", [1], "A", [6], 3.0) == 0
    assert heavy_atom_contacts(built, "A", [], "A", [1], 3.0) == 0


def test_heavy_atom_contacts_ignores_hydrogens():
    residues = {1: [("CA", "C", 0.0, 0.0, 0.0), ("H", "H", 0.5, 0.0, 0.0)],
                2: [("CA", "C", 1.0, 0.0, 0.0)]}
    built = _structure({"A": residues})
    assert heavy_atom_contacts(built, "A", [1], "A", [2], 2.0) == 1


def test_principal_axis_is_sign_deterministic():
    rng = np.random.default_rng(3)
    cloud = rng.normal(size=(20, 3)) @ np.diag([8.0, 1.0, 1.0])
    assert np.allclose(principal_axis(cloud), principal_axis(cloud))
    assert abs(principal_axis(cloud)[0]) > abs(principal_axis(cloud)[1])


def test_spatial_neighbourhood_reports_the_closest_atom_per_residue():
    residues = {
        "A": {
            1: [("OG", "O", 0.0, 0.0, 0.0)],
            2: [("NZ", "N", 2.5, 0.0, 0.0)],
            3: [("NZ", "N", 20.0, 0.0, 0.0)],
        }
    }
    built = _structure(residues)
    found = structure.spatial_neighbourhood(
        built, built.residue("A", 1).atoms, 8.0, excluded_residues=[("A", 1)])
    assert [entry[1] for entry in found] == [2]
    assert found[0][4] == pytest.approx(2.5)


# --------------------------------------------------------------------------
# SASA (SOP §3.7)
# --------------------------------------------------------------------------


def test_single_atom_sasa_is_the_expanded_sphere():
    area = sasa.shrake_rupley(np.zeros((1, 3)), np.array([1.70]), 1.4, 960)
    assert area[0] == pytest.approx(4.0 * np.pi * (1.70 + 1.4) ** 2, rel=1e-9)


def test_overlapping_atoms_bury_surface():
    radii = np.array([1.70, 1.70])
    single = 4.0 * np.pi * (1.70 + 1.4) ** 2
    overlapping = sasa.shrake_rupley(
        np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]), radii, 1.4, 960)
    assert overlapping[0] < single and overlapping[1] < single
    apart = sasa.shrake_rupley(
        np.array([[0.0, 0.0, 0.0], [50.0, 0.0, 0.0]]), radii, 1.4, 960)
    assert apart[0] == pytest.approx(single, rel=1e-9)


def test_an_isolated_atom_in_a_larger_model_keeps_its_full_sphere():
    coordinates = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 40.0]])
    areas = sasa.shrake_rupley(coordinates, np.array([1.70, 1.70]), 1.4, 960)
    single = 4.0 * np.pi * (1.70 + 1.4) ** 2
    assert areas[1] == pytest.approx(single, rel=1e-9)


def test_fibonacci_sphere_is_a_unit_sphere():
    points = sasa.fibonacci_sphere(200)
    assert np.allclose(np.linalg.norm(points, axis=1), 1.0)


def test_internal_sasa_agrees_with_biopython_on_a_real_structure(tmp_path):
    pytest.importorskip("Bio.PDB")
    from Bio.PDB import MMCIFParser
    from Bio.PDB.SASA import ShrakeRupley as BioShrakeRupley

    geometry = ConditionGeometry(SEQUENCE, seed=2, jitter=0.0)
    root = write_condition(tmp_path / "wt", "wt", geometry, seeds=(1,), samples=1,
                           write_top_ranked=False)
    path = root / "seed-1_sample-0" / "wt_seed-1_sample-0_model.cif"
    model = read_structure(path)
    atoms = list(model.atoms())
    mine = sasa.shrake_rupley(
        np.vstack([atom.coord for atom in atoms]),
        np.array([sasa.atom_radius(atom.element) for atom in atoms]),
        1.4, 960,
    ).sum()

    bio_structure = MMCIFParser(QUIET=True).get_structure("wt", path)
    reference = BioShrakeRupley(probe_radius=1.4, n_points=960)
    reference.compute(bio_structure, level="A")
    expected = sum(atom.sasa for atom in bio_structure.get_atoms())
    assert mine == pytest.approx(expected, rel=0.01)


def test_surface_calculator_records_which_implementation_ran(tmp_path):
    from af3_analysis.config import SasaSettings

    geometry = ConditionGeometry("MAGSTVKLDEQP", seed=2, jitter=0.0)
    root = write_condition(tmp_path / "wt", "wt", geometry, seeds=(1,), samples=1,
                           write_top_ranked=False)
    model = read_structure(root / "seed-1_sample-0" / "wt_seed-1_sample-0_model.cif")

    auto = sasa.SurfaceCalculator(SasaSettings(method="auto"))
    result = auto.calculate(model)
    assert result.status == "ok"
    assert result.method in ("freesasa", "shrake_rupley_internal")

    forced = sasa.SurfaceCalculator(SasaSettings(method="freesasa"))
    forced_result = forced.calculate(model)
    if auto.method == "shrake_rupley_internal":
        assert "freesasa was requested" in forced_result.note

    assert sasa.SurfaceCalculator(SasaSettings(enabled=False)).calculate(model).status \
        == "not_run"


def test_atom_radius_falls_back_for_unknown_elements():
    assert sasa.atom_radius("C") == pytest.approx(1.70)
    assert sasa.atom_radius("XX") == pytest.approx(sasa.DEFAULT_RADIUS)
