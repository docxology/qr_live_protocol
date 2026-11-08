"""Regression tests for release metadata and CLI exposure."""

from pathlib import Path

import tomllib
from click.testing import CliRunner

from src import __version__
from src.cli import cli

ROOT = Path(__file__).resolve().parents[1]


def test_cli_reports_package_version() -> None:
    """The installed CLI and distribution report the same release version."""
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert project["version"] == __version__ == result.output.strip().rsplit(" ", 1)[-1]
