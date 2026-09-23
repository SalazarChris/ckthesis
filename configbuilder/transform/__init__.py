"""Transform package: canonical model -> wire document (plan §6.4, §10).

The only module family permitted to name wire fields (single-authority
rule, plan §10.1).
"""

from configbuilder.transform.engine import (
    ExternalResourceRequirement,
    TransformError,
    TransformResult,
    WireDocument,
    to_wire,
    with_emitted_resource_paths,
    with_wire_job_name,
)
from configbuilder.transform.mappings import (
    DNA_FIELDS,
    FAMILY_TABLES,
    LIGAND_FIELDS,
    PROTEIN_FIELDS,
    RNA_FIELDS,
    ROOT_FIELDS,
)
from configbuilder.transform.presence import OMITTED, EmissionRule, Omitted

from configbuilder.transform.from_wire import ImportNote, WireImportError, from_wire

__all__ = [
    "ExternalResourceRequirement",
    "TransformError",
    "TransformResult",
    "WireDocument",
    "from_wire",
    "to_wire",
    "with_emitted_resource_paths",
    "with_wire_job_name",
    "DNA_FIELDS",
    "ImportNote",
    "WireImportError",
    "FAMILY_TABLES",
    "LIGAND_FIELDS",
    "PROTEIN_FIELDS",
    "RNA_FIELDS",
    "ROOT_FIELDS",
    "OMITTED",
    "EmissionRule",
    "Omitted",
]
