#!/usr/bin/env python3
"""Compatibility launcher for the live QR display."""

from src.cli import cli


def main() -> None:
    """Forward the existing launcher arguments to the live CLI."""
    import sys

    cli.main(args=["live", *sys.argv[1:]], prog_name="python main.py")


if __name__ == "__main__":
    main()
