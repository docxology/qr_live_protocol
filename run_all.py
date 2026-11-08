#!/usr/bin/env python3
"""Compatibility runner for setup, tests, demos, and the live CLI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXAMPLES = (
    "comprehensive_demo.py",
    "thin_orchestrator.py",
    "integration_patterns.py",
    "error_recovery_demo.py",
)


class QRLPComprehensiveRunner:
    """Dispatch to the same project commands used directly by developers."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _run(self, argv: list[str], *, timeout: int | None = None) -> bool:
        if self.verbose:
            print("+", *argv, flush=True)
        try:
            return subprocess.run(argv, cwd=ROOT, timeout=timeout).returncode == 0
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"{Path(argv[0]).name}: {exc}", file=sys.stderr)
            return False

    def run_setup(self, quick_mode: bool = False) -> bool:
        uv = shutil.which("uv")
        if uv is None:
            print("Install uv first; see docs/INSTALLATION.md.", file=sys.stderr)
            return False
        # Both modes include pytest-asyncio, which the test suite requires.
        extras = ["--extra", "dev"] if quick_mode else ["--extra", "dev", "--extra", "full"]
        return self._run([uv, "sync", "--locked", *extras], timeout=300)

    def run_tests(self) -> bool:
        return self._run([sys.executable, "-m", "pytest", "tests"], timeout=300)

    def run_examples(self) -> bool:
        results = [
            self._run([sys.executable, str(ROOT / "examples" / example)], timeout=120)
            for example in EXAMPLES
        ]
        return all(results)

    def run_production_deployment(self) -> None:
        print((ROOT / "docs" / "STREAMING.md").read_text(encoding="utf-8"))

    def run_interactive_mode(self, *, quick_mode: bool = False) -> bool:
        actions = {
            "1": ("Set up project", lambda: self.run_setup(quick_mode)),
            "2": ("Run tests", self.run_tests),
            "3": ("Run examples", self.run_examples),
            "4": ("Start live display", lambda: self._run([sys.executable, "-m", "src", "live"])),
            "5": ("Open improvement dashboard", lambda: self._run([sys.executable, "-m", "src", "dashboard"])),
            "6": ("Run optical simulation", lambda: self._run([sys.executable, "-m", "src", "simulate-live"])),
        }
        success = True
        while True:
            print("\nQR Live Protocol")
            for option, (label, _) in actions.items():
                print(f"{option}. {label}")
            try:
                choice = input("Choose an action (q to quit): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return success
            if choice == "q":
                return success
            if choice in actions:
                try:
                    success = actions[choice][1]() and success
                except KeyboardInterrupt:
                    print()
            else:
                print("Unknown action.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-only", action="store_true", help="Sync the locked uv environment")
    parser.add_argument("--test-only", action="store_true", help="Run tests with the current interpreter")
    parser.add_argument("--examples-only", action="store_true", help="Run the finite examples")
    parser.add_argument("--interactive", action="store_true", help="Open the action menu")
    parser.add_argument("--quick", action="store_true", help="Omit optional full extras during setup")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show dispatched commands")
    parser.add_argument("--production", action="store_true", help="Print the streaming guide")
    args = parser.parse_args()
    runner = QRLPComprehensiveRunner(verbose=args.verbose)
    if args.production:
        runner.run_production_deployment()
        return 0
    if args.interactive or not any((args.setup_only, args.test_only, args.examples_only)):
        if not sys.stdin.isatty():
            parser.print_help()
            return 0
        return int(not runner.run_interactive_mode(quick_mode=args.quick))
    if args.setup_only and not runner.run_setup(args.quick):
        return 1
    if args.test_only and not runner.run_tests():
        return 1
    return int(args.examples_only and not runner.run_examples())


if __name__ == "__main__":
    raise SystemExit(main())
