"""Regression tests for package metadata and distributable assets."""

import re
import tomllib
from pathlib import Path

from src import __version__

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_REPOSITORY_URL = "https://github.com/docxology/" "qr_live_protocol"


def read_pyproject() -> dict:
    """Read package metadata from pyproject.toml."""
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_version_is_consistent_across_package_metadata() -> None:
    """The release version should be synchronized."""
    pyproject = read_pyproject()
    setup_py = (ROOT / "setup.py").read_text(encoding="utf-8")
    setup_version = re.search(r'version="([^"]+)"', setup_py)

    assert setup_version is not None
    assert pyproject["project"]["version"] == "1.2.0"
    assert __version__ == "1.2.0"
    assert setup_version.group(1) == "1.2.0"


def test_metadata_repository_and_license_are_current() -> None:
    """Metadata should not publish stale URLs or MIT classifiers."""
    pyproject = read_pyproject()
    setup_py = (ROOT / "setup.py").read_text(encoding="utf-8")
    project = pyproject["project"]
    classifiers = project["classifiers"]
    placeholder_url = "https://github.com/" + "your" + "-org/qr_live_protocol"

    assert project["urls"]["Source"] == PUBLIC_REPOSITORY_URL
    assert placeholder_url not in setup_py
    assert project["license"]["text"] == "CC-BY-NC-SA-4.0"
    assert all("MIT" not in classifier for classifier in classifiers)


def test_wheel_configuration_includes_top_level_templates() -> None:
    """Installed wheels need the top-level Flask templates."""
    pyproject = read_pyproject()
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    force_include = wheel["force-include"]

    assert force_include["templates"] == "templates"
    assert (ROOT / "templates" / "improve.html").exists()
    assert (ROOT / "templates" / "index.html").exists()
