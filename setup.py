"""Compatibility entry point; package metadata lives in pyproject.toml."""

from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parent


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        with (ROOT / "pyproject.toml").open("rb") as stream:
            print(tomllib.load(stream)["project"]["version"])
        return 0
    if args in ([], ["install"]):
        return subprocess.call([sys.executable, "-m", "pip", "install", str(ROOT)])
    print("Use 'python -m pip install .' to install or 'uv build' to build distributions.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
