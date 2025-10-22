"""
QRLP Test Suite

Comprehensive testing framework for QR Live Protocol including unit tests,
integration tests, performance tests, and security tests.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src to path for testing
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Test markers for different test types
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for component interaction"
    )
    config.addinivalue_line(
        "markers", "performance: Performance and load testing"
    )
    config.addinivalue_line(
        "markers", "security: Security and penetration testing"
    )
    config.addinivalue_line(
        "markers", "crypto: Cryptographic functionality tests"
    )

# Test environment setup
os.environ.setdefault('QRLP_TESTING', 'true')
os.environ.setdefault('QRLP_LOG_LEVEL', 'WARNING')

