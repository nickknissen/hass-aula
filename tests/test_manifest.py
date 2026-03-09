"""Tests to verify manifest.json requirements are valid and installable."""

from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

import pytest
from packaging.requirements import Requirement

MANIFEST_PATH = (
    Path(__file__).parent.parent / "custom_components" / "hass_aula" / "manifest.json"
)
REQUIREMENTS_PATH = Path(__file__).parent.parent / "requirements.txt"


@pytest.fixture
def manifest() -> dict:
    """Load manifest.json."""
    return json.loads(MANIFEST_PATH.read_text())


def test_manifest_requirements_are_installed(manifest: dict) -> None:
    """
    Verify every manifest requirement is installed and version-compatible.

    This catches the case where manifest.json pins a version that doesn't
    exist on PyPI or isn't installable (e.g. aula==1.0.1 not found).
    """
    for req_str in manifest["requirements"]:
        req = Requirement(req_str)
        installed_version = version(req.name)
        assert req.specifier.contains(installed_version), (
            f"Installed {req.name}=={installed_version} does not satisfy "
            f"manifest requirement {req_str}"
        )


def test_manifest_requirements_in_requirements_txt(manifest: dict) -> None:
    """
    Verify every manifest requirement also appears in requirements.txt.

    Ensures the dev/test environment installs the same versions that HA
    will try to install at runtime.
    """
    req_txt_lines = REQUIREMENTS_PATH.read_text().splitlines()
    req_txt_packages = {}
    for raw_line in req_txt_lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        req = Requirement(line)
        req_txt_packages[req.name.lower()] = str(req.specifier)

    for req_str in manifest["requirements"]:
        req = Requirement(req_str)
        name = req.name.lower()
        assert name in req_txt_packages, (
            f"Manifest requirement {req_str} not found in requirements.txt"
        )
        assert str(req.specifier) == req_txt_packages[name], (
            f"Version mismatch for {name}: manifest has {req.specifier}, "
            f"requirements.txt has {req_txt_packages[name]}"
        )
