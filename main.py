#!/usr/bin/env python3
"""
QR Live Protocol (QRLP) - Main Entry Point

Modern, simplified launcher using uv for environment management.

This script launches the QRLP livestream demo with proper uv environment setup.

Usage:
    python main.py [--port 8080] [--no-browser]

The demo will:
1. Use the existing uv virtual environment
2. Launch a web server with live QR display
3. Update QR codes with live verification data
4. Open browser window automatically (unless disabled)
"""

import sys
import os
import subprocess
import platform
import webbrowser
import time
import argparse
from pathlib import Path


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="QR Live Protocol - Demo Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Launch demo with browser
  python main.py --no-browser       # Launch demo without browser
  python main.py --port 9000        # Use custom port

For development setup:
  uv venv                           # Create virtual environment
  source .venv/bin/activate        # Activate environment
  uv pip install -e .[dev]         # Install with dev dependencies
  qrlp live                        # Start live generation
        """
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help="Port for web server (default: 8080)"
    )

    parser.add_argument(
        '--no-browser',
        action='store_true',
        help="Don't automatically open browser"
    )

    args = parser.parse_args()

    print("🔲 QR Live Protocol (QRLP) - Modern Setup")
    print("=" * 50)

    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Not in a virtual environment.")
        print("For development setup, run:")
        print("  uv venv")
        print("  source .venv/bin/activate")
        print("  uv pip install -e .[dev]")
        print()

    # Check if QRLP is installed
    try:
        from src import QRLiveProtocol
        print("✅ QRLP package available")
    except ImportError as e:
        print(f"❌ QRLP package not available: {e}")
        print("Install with: uv pip install -e .")
        return 1

    # Launch the demo
    demo_file = Path(__file__).parent / "examples" / "livestream_demo.py"

    if not demo_file.exists():
        print(f"❌ Demo file not found: {demo_file}")
        return 1

    print(f"🚀 Launching QRLP demo on port {args.port}")
    print("📡 Server will be available at: http://localhost:" + str(args.port))

    if not args.no_browser:
        print("🌐 Browser will open automatically in 3 seconds...")

        def delayed_browser_open():
            time.sleep(3)
            webbrowser.open(f"http://localhost:{args.port}")

        import threading
        browser_thread = threading.Thread(target=delayed_browser_open)
        browser_thread.daemon = True
        browser_thread.start()

    print("▶️  Starting livestream demo (Ctrl+C to stop)...")
    print("📱 QR codes will update every second with live data!")
    print()

    # Set environment variables
    demo_env = os.environ.copy()
    demo_env['QRLP_PORT'] = str(args.port)
    demo_env['QRLP_AUTO_BROWSER'] = str(not args.no_browser).lower()

    try:
        # Run the demo
        result = subprocess.run(
            [sys.executable, str(demo_file)],
            cwd=Path(__file__).parent,
            env=demo_env
        )

        if result.returncode == 0:
            print("\n✅ Demo completed successfully!")
            return 0
        else:
            print(f"\n❌ Demo exited with code {result.returncode}")
            return result.returncode

    except KeyboardInterrupt:
        print("\n🛑 Demo stopped by user")
        return 0
    except Exception as e:
        print(f"\n💥 Demo error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 