"""
Setup script for QR Live Protocol (QRLP).

Provides installation and packaging configuration for QRLP.
When run without arguments, performs a complete setup installation.
"""

import sys
import os

# Check if no arguments provided - run default setup via pip
if len(sys.argv) == 1:
    print("=" * 70)
    print("QRLP Setup - Installing dependencies and package")
    print("=" * 70)
    print()
    os.execvp(sys.executable, [
        sys.executable, "-m", "pip", "install", 
        "--break-system-packages", "."
    ])
    # execvp replaces the process, so we never reach here

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
if readme_path.exists():
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "QR Live Protocol - Generate live, verifiable QR codes for streaming"

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path, "r", encoding="utf-8") as f:
        requirements = [
            line.strip() for line in f 
            if line.strip() and not line.startswith("#")
        ]
else:
    requirements = [
        "qrcode[pil]>=7.4.2",
        "Pillow>=10.0.0", 
        "Flask>=3.0.0",
        "Flask-CORS>=4.0.0",
        "Flask-SocketIO>=5.3.6",
        "click>=8.1.7",
        "ntplib>=0.4.0",
        "requests>=2.31.0",
        "python-dateutil>=2.8.2"
    ]

setup(
    name="qr-live-protocol",
    version="1.0.0",
    author="QRLP Development Team", 
    author_email="contact@qrlp.org",
    description="Generate live, verifiable QR codes for streaming and official video releases",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/qr_live_protocol",
    
    # Package configuration
    packages=find_packages(),
    package_dir={"": "."},
    python_requires=">=3.8",
    
    # Dependencies
    install_requires=requirements,
    
    # Optional dependencies
    extras_require={
        "full": [
            "PyYAML>=6.0.1",
            "pyzbar>=0.1.9", 
            "opencv-python>=4.8.0",
            "cryptography>=41.0.0"
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0", 
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0"
        ]
    },
    
    # Entry points for CLI
    entry_points={
        "console_scripts": [
            "qrlp=src.cli:cli",
            "qr-live-protocol=src.cli:cli"
        ]
    },
    
    # Package data
    include_package_data=True,
    package_data={
        "src": [
            "templates/*.html",
            "static/*", 
            "static/**/*"
        ]
    },
    
    # Metadata
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video",
        "Topic :: Security :: Cryptography",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9", 
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent"
    ],
    
    keywords=[
        "qr-code", "livestream", "verification", "blockchain", 
        "timestamp", "cryptography", "video", "authentication"
    ],
    
    project_urls={
        "Bug Reports": "https://github.com/your-org/qr_live_protocol/issues",
        "Source": "https://github.com/your-org/qr_live_protocol",
        "Documentation": "https://qrlp.readthedocs.io/",
    }
) 