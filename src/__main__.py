"""
Main entry point for QRLP when run as a module.

Allows running QRLP with: python -m qrlp
"""

from .cli import cli

if __name__ == '__main__':
    cli()
