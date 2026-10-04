"""Validate JSON with AlphaFold 3's OWN input parser.

The parser used here is the real ``alphafold3.common.folding_input.Input.from_json``
from the official repository, not a reimplementation. Two things cannot be built
on an ordinary machine, so they are stubbed **to raise if used**:

* ``alphafold3.cpp.*`` -- compiled C++ extensions. AF3 builds them through
  CMake for Linux/macOS targets only. They back CIF/mmCIF parsing and fast MSA
  conversion. The JSON-validation path never calls them, except for one field:
  ``userCCD`` / ``userCCDPath``, which is parsed with
  ``cif_dict.parse_multi_data_cif``.

Everything else is real: ``etils`` (epath) and ``rdkit`` are installed from PyPI
by ``setup_validator.py``, so SMILES ligands and every path read are genuine.

A stub raises ``StubUsed`` and the file is reported ``UNVERIFIED`` -- never
``PASS`` -- so a check that was stubbed out can never look green.

Run ``run_all.py`` for the full report, or this module directly:

    python af3_validate.py FILE_OR_DIR [FILE_OR_DIR ...]
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# Where setup_validator.py keeps the AF3 checkout and the third-party wheels.
# It lives outside the repository (the OS temp dir) so a checkout of this
# project stays clean; override with AF3_VALIDATOR_HOME to reuse one download.
ARTIFACTS = os.environ.get(
    "AF3_VALIDATOR_HOME", os.path.join(tempfile.gettempdir(), "af3-validator")
)
AF3_SRC = os.path.join(ARTIFACTS, "alphafold3-main", "src")
SITE = os.path.join(ARTIFACTS, "site")
AF3_TARBALL_URL = (
    "https://codeload.github.com/google-deepmind/alphafold3/tar.gz/refs/heads/main"
)

STUBBED_CPP = (
    "cif_dict",
    "mmcif_atom_site",
    "mmcif_struct_conn",
    "string_array",
    "membership",
    "aggregation",
    "mmcif_utils",
    "mmcif_layout",
    "fasta_iterator",
    "msa_conversion",
)


class StubUsed(RuntimeError):
    """A stubbed compiled extension was actually called."""


class _Stub:
    """Attribute tree that raises the moment it is called."""

    def __init__(self, dotted):
        self._dotted = dotted

    def __call__(self, *args, **kwargs):
        raise StubUsed(self._dotted)

    def __getattr__(self, item):
        return _Stub("%s.%s" % (self._dotted, item))

    def __getitem__(self, item):
        raise StubUsed(self._dotted)

    def __iter__(self):
        raise StubUsed(self._dotted)


class _StubModule(types.ModuleType):
    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return _Stub("%s.%s" % (self.__name__, item))


def install_stubs():
    package = types.ModuleType("alphafold3.cpp")
    package.__path__ = []
    sys.modules["alphafold3.cpp"] = package
    for name in STUBBED_CPP:
        module = _StubModule("alphafold3.cpp." + name)
        sys.modules["alphafold3.cpp." + name] = module
        setattr(package, name, module)

    try:
        import alphafold3.structure  # noqa: F401
    except Exception:
        # The real package wants the compiled string_array at import time. Keep
        # a name-only shim, but load the *real* mmcif module: folding_input uses
        # its int_id_to_str_id to name chains when an entry carries id lists.
        shim = types.ModuleType("alphafold3.structure")
        shim.__path__ = [os.path.join(AF3_SRC, "alphafold3", "structure")]
        sys.modules["alphafold3.structure"] = shim
        from alphafold3.structure import mmcif as real_mmcif
        shim.mmcif = real_mmcif
        for attribute in (
            "Structure", "SequenceFormat", "from_mmcif", "from_sequences_and_bonds",
        ):
            setattr(shim, attribute, _Stub("alphafold3.structure." + attribute))


def load_parser():
    """Import AF3's real JSON-validating entry point."""
    if not os.path.isdir(AF3_SRC):
        raise SystemExit(
            "AlphaFold 3 source not found at %s\n"
            "Run: python %s" % (AF3_SRC, os.path.join(HERE, "setup_validator.py"))
        )
    for path in (SITE, AF3_SRC, REPO):
        if path not in sys.path:
            sys.path.insert(0, path)
    install_stubs()
    from alphafold3.common import folding_input
    return folding_input


class Verdict:
    """One file's outcome. ``ok`` is None when the result is not a pass/fail."""

    __slots__ = ("verdict", "detail")

    def __init__(self, verdict, detail):
        self.verdict = verdict
        self.detail = detail

    @property
    def accepted(self):
        return self.verdict == "ACCEPTED"

    @property
    def rejected(self):
        return self.verdict == "REJECTED"


def check(folding_input, path):
    """Validate one file: ACCEPTED, REJECTED (AF3's own message) or UNVERIFIED."""
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    try:
        parsed = folding_input.Input.from_json(text, json_path=path)
    except StubUsed as error:
        return Verdict("UNVERIFIED", "stubbed compiled extension needed: %s" % error)
    except Exception as error:                     # AF3's refusal, verbatim
        return Verdict("REJECTED", "%s: %s" % (type(error).__name__, error))
    chains = ",".join("%s(%d)" % (chain.id, len(chain)) for chain in parsed.chains)
    return Verdict(
        "ACCEPTED",
        "name=%r chains=%s seeds=%s bonds=%d ccd=%s" % (
            parsed.name,
            chains or "none",
            list(parsed.rng_seeds),
            len(parsed.bonded_atom_pairs or ()),
            "yes" if parsed.user_ccd else "no",
        ),
    )


def gather(argument):
    if os.path.isdir(argument):
        found = []
        for base, _dirs, names in os.walk(argument):
            for name in sorted(names):
                if name.endswith(".json") and name != "manifest.json":
                    found.append(os.path.join(base, name))
        return sorted(found)
    return [argument]


def main(argv):
    folding_input = load_parser()
    print("parser : %s" % folding_input.__file__)
    print("dialect: %s   versions: %s"
          % (folding_input.JSON_DIALECT, folding_input.JSON_VERSIONS))
    targets = []
    for argument in argv:
        targets.extend(gather(argument))
    if not targets:
        print("usage: python af3_validate.py FILE_OR_DIR [...]")
        return 2
    counts = {}
    for path in targets:
        result = check(folding_input, path)
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
        print("%-10s %s" % (result.verdict, path))
        print("           %s" % result.detail)
    print("---")
    print("summary: " + ", ".join("%s=%d" % item for item in sorted(counts.items())))
    return 1 if counts.get("REJECTED") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
