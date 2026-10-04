"""Cross-process byte determinism (plan §11, Phase 6 checklist).

The whole point of the fixed encoding policy is that ``encode(to_wire(c))``
is byte-stable across processes and invocations — that is what makes
golden tests possible and what lets a regenerated file be compared against
an old one. These tests spawn fresh interpreters with *different*
``PYTHONHASHSEED`` values, so string-hash randomisation differs per
process; any hash-order dependence anywhere in the pipeline (dict
iteration, set membership feeding emission order) breaks these tests.

The pipeline run inside each child process: build the model objects →
``to_wire`` → ``encode``. That covers the full chain, not just the
serializer.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

PIPELINE_SCRIPT = textwrap.dedent(
    """
    from configbuilder.identity import EntityId, IdentityRegistry, Multiplicity
    from configbuilder.model import (
        AlignmentUnpairedOnly, ByNotation, ComponentCode, ComponentRecord,
        Configuration, ConfigurationMetadata, Explicit, External, FamilyARecord,
        FamilyBRecord, FormatTarget, IndexPair, Inline, LinkEndpoint, Linkage,
        ModificationRecord, Pinned, PathSpec, Position, ReferenceRecord,
        ResidueRef, SeedSet, SequenceText,
    )
    from configbuilder.transform import to_wire
    from configbuilder.serialize import encode

    records = (
        FamilyARecord(
            ids=Multiplicity(["A"]),
            sequence=SequenceText("PEPTIDE", "protein"),
            alignment=AlignmentUnpairedOnly(source=Inline(">query\\nPEPTIDE")),
            references=Explicit(
                (
                    ReferenceRecord(
                        source=External(PathSpec("templates/1ubq.cif")),
                        index_map=(IndexPair(0, 0), IndexPair(2, 4)),
                    ),
                )
            ),
            modifications=(
                ModificationRecord(code=ComponentCode("TPO"), position=Position(7)),
            ),
        ),
        FamilyBRecord(ids=Multiplicity(["B", "C"]), sequence=SequenceText("ACGU", "rna")),
        ComponentRecord(ids=Multiplicity(["E"]), representation=ByNotation("CCO")),
    )
    configuration = Configuration(
        metadata=ConfigurationMetadata("demo_job"),
        seeds=SeedSet([11, 22]),
        records=records,
        linkages=(
            Linkage(
                LinkEndpoint(EntityId("A"), ResidueRef(3), "OG1"),
                LinkEndpoint(EntityId("E"), ResidueRef(1), "N1"),
            ),
        ),
        identity=IdentityRegistry(),
    ).with_format_target(FormatTarget(version_selection=Pinned(4)))
    import sys
    sys.stdout.buffer.write(encode(to_wire(configuration).document))
    """
)


def _run_pipeline(hash_seed):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(hash_seed)
    result = subprocess.run(
        [sys.executable, "-c", PIPELINE_SCRIPT],
        capture_output=True,
        env=env,
        cwd=os.getcwd(),
    )
    if result.returncode != 0:
        raise AssertionError(
            "pipeline failed under PYTHONHASHSEED=%d:\n%s"
            % (hash_seed, result.stderr.decode("utf-8", "replace"))
        )
    return result.stdout


def test_byte_identical_across_fresh_processes():
    outputs = {
        _run_pipeline(seed)
        for seed in (0, 1, 12, 1234, 98765, 4294967295)
    }
    assert len(outputs) == 1, "output depends on the process hash seed"


def test_output_is_stable_and_well_formed():
    data = _run_pipeline(7)
    assert data.endswith(b"\n")
    assert b"\r" not in data
    assert b'"unpairedMsa"' in data  # spot-check the document really built
