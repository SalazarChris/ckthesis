"""Fetch what the AF3-parser validator needs. Run once (re-running is cheap).

Downloads the official AlphaFold 3 source tarball and installs the parser's two
usable third-party dependencies into the same artifacts directory, so nothing is
added to this project's environment:

* ``etils[epath]`` -- AF3 reads ``*Path`` fields with it
* ``rdkit``        -- AF3 validates SMILES ligands with it
* ``zstandard``    -- AF3 imports it unconditionally for compressed inputs

The compiled ``alphafold3.cpp.*`` extensions are deliberately NOT built: AF3
only ships CMake targets for Linux/macOS, and the JSON-validation path does not
use them except for ``userCCD``. ``af3_validate.py`` stubs them to raise, so the
one field that needs them is reported ``UNVERIFIED`` rather than passed.

    python tools/af3_validation/setup_validator.py
"""
import os
import subprocess
import sys
import tarfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import af3_validate  # noqa: E402  (needs the path above when imported)

TARBALL = os.path.join(af3_validate.ARTIFACTS, "alphafold3-main.tar.gz")


def fetch_source():
    destination = os.path.join(af3_validate.ARTIFACTS, "alphafold3-main")
    if os.path.isdir(af3_validate.AF3_SRC):
        print("AF3 source already present: %s" % destination)
        return
    os.makedirs(af3_validate.ARTIFACTS, exist_ok=True)
    print("downloading %s" % af3_validate.AF3_TARBALL_URL)
    with urllib.request.urlopen(af3_validate.AF3_TARBALL_URL, timeout=180) as response:
        with open(TARBALL, "wb") as handle:
            handle.write(response.read())
    print("unpacking to %s" % af3_validate.ARTIFACTS)
    with tarfile.open(TARBALL) as archive:
        archive.extractall(af3_validate.ARTIFACTS)
    os.unlink(TARBALL)
    if not os.path.isdir(af3_validate.AF3_SRC):
        raise SystemExit("unexpected archive layout: %s is missing" % af3_validate.AF3_SRC)


def install_dependencies():
    marker = os.path.join(af3_validate.SITE, "etils")
    if os.path.isdir(marker):
        print("parser dependencies already installed: %s" % af3_validate.SITE)
        return
    print("installing parser dependencies into %s" % af3_validate.SITE)
    command = [
        sys.executable, "-m", "pip", "install", "--quiet",
        "--target", af3_validate.SITE,
        "etils[epath]", "rdkit", "zstandard",
    ]
    completed = subprocess.run(command)
    if completed.returncode != 0:
        raise SystemExit("dependency install failed (exit %d)" % completed.returncode)


def main():
    fetch_source()
    install_dependencies()
    parser = af3_validate.load_parser()
    print("ready: %s" % parser.__file__)
    print("dialect %s, versions %s" % (parser.JSON_DIALECT, parser.JSON_VERSIONS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
