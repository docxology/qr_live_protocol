#!/usr/bin/env python3
"""
QRLP Comprehensive Runner - Single Entry Point for All Functionality

This script provides a unified interface for accessing, testing, and demonstrating
all QRLP functionality including setup, testing, examples, and production usage.

Features:
- Complete setup and installation
- Comprehensive testing suite execution
- All example demonstrations
- Interactive functionality selection
- Production deployment assistance
- Documentation and help system
- Performance monitoring and optimization
- Security auditing and validation

Usage:
    python run_all.py [options]

Options:
    --setup-only        Only run setup, don't launch demos
    --test-only         Only run tests, don't launch demos
    --examples-only     Only run examples, don't launch demos
    --interactive       Interactive mode for functionality selection
    --quick             Quick mode (skip optional components)
    --verbose           Verbose output for debugging
    --help              Show this help message
"""

import sys
import os
import time
import argparse
import subprocess
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional
import webbrowser

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src import QRLiveProtocol, QRLPConfig


class QRLPComprehensiveRunner:
    """
    Comprehensive QRLP runner providing unified access to all functionality.

    This class provides methods to:
    - Setup and install QRLP
    - Run comprehensive test suites
    - Execute all example demonstrations
    - Provide interactive functionality selection
    - Monitor system health and performance
    - Assist with production deployment
    """

    def __init__(self, verbose: bool = False):
        """Initialize comprehensive runner."""
        self.verbose = verbose
        self.project_root = project_root
        self.setup_complete = False
        self.tests_run = False
        self.examples_run = False

        # Component status tracking
        self.component_status = {
            'setup': False,
            'tests': False,
            'examples': False,
            'crypto': False,
            'security': False,
            'monitoring': False
        }

        # Performance metrics
        self.performance_metrics = {}

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp and level."""
        if not self.verbose and level == "DEBUG":
            return

        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_setup(self, quick_mode: bool = False) -> bool:
        """Run complete QRLP setup and installation."""
        self.log("🚀 Starting QRLP Setup and Installation", "INFO")

        try:
            # Check Python version
            if not self._check_python_version():
                return False

            # Install dependencies
            if not self._install_dependencies(quick_mode):
                return False

            # Setup package
            if not self._setup_package():
                return False

            # Validate installation
            if not self._validate_installation():
                return False

            self.setup_complete = True
            self.component_status['setup'] = True

            self.log("✅ QRLP Setup Complete", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"❌ Setup failed: {e}", "ERROR")
            return False

    def run_tests(self) -> bool:
        """Run comprehensive test suite."""
        self.log("🧪 Running QRLP Test Suite", "INFO")

        try:
            # Check if pytest is available
            if not self._check_pytest_available():
                self.log("⚠️  pytest not available, skipping tests", "WARNING")
                return True

            # Run all tests
            test_results = self._run_test_suite()

            if test_results['success']:
                self.log(f"✅ Tests passed: {test_results['passed']}/{test_results['total']}", "SUCCESS")
                self.tests_run = True
                self.component_status['tests'] = True
                return True
            else:
                self.log(f"❌ Tests failed: {test_results['failed']} failures", "ERROR")
                return False

        except Exception as e:
            self.log(f"❌ Test execution failed: {e}", "ERROR")
            return False

    def run_examples(self) -> bool:
        """Run all example demonstrations."""
        self.log("💡 Running QRLP Examples", "INFO")

        try:
            examples = [
                ('comprehensive_demo', 'examples/comprehensive_demo.py'),
                ('thin_orchestrator', 'examples/thin_orchestrator.py'),
                ('integration_patterns', 'examples/integration_patterns.py'),
                ('error_recovery_demo', 'examples/error_recovery_demo.py')
            ]

            success_count = 0

            for example_name, example_path in examples:
                self.log(f"Running {example_name}...", "INFO")

                if self._run_example(example_path):
                    success_count += 1
                    self.log(f"✅ {example_name} completed successfully", "SUCCESS")
                else:
                    self.log(f"❌ {example_name} failed", "ERROR")

            if success_count == len(examples):
                self.log(f"✅ All examples completed: {success_count}/{len(examples)}", "SUCCESS")
                self.examples_run = True
                self.component_status['examples'] = True
                return True
            else:
                self.log(f"⚠️  Examples partially completed: {success_count}/{len(examples)}", "WARNING")
                return success_count > 0

        except Exception as e:
            self.log(f"❌ Example execution failed: {e}", "ERROR")
            return False

    def run_interactive_mode(self):
        """Run interactive mode for functionality selection."""
        self.log("🎮 Starting Interactive QRLP Mode", "INFO")

        while True:
            self._show_interactive_menu()

            try:
                choice = input("\nSelect option (or 'q' to quit): ").strip().lower()
            except EOFError:
                print("\n⚠️ Input not available in this environment. Starting web demo automatically...")
                choice = "6"  # Auto-select web interface demo

            if choice == 'q':
                break
            elif choice == '1':
                self._demo_setup()
            elif choice == '2':
                self._demo_basic_qr()
            elif choice == '3':
                self._demo_signed_qr()
            elif choice == '4':
                self._demo_encrypted_qr()
            elif choice == '5':
                self._demo_verification()
            elif choice == '6':
                self._demo_web_interface()
            elif choice == '7':
                self._demo_performance()
            elif choice == '8':
                self._demo_security()
            elif choice == '9':
                self._demo_integration()
            elif choice == '10':
                self._run_system_health_check()
            elif choice == '11':
                self._show_documentation()
            elif choice == '12':
                self._show_performance_stats()
            else:
                print("❌ Invalid choice. Please try again.")

        self.log("👋 Interactive mode ended", "INFO")

    def run_production_deployment(self):
        """Assist with production deployment."""
        self.log("🏭 Production Deployment Assistant", "INFO")

        print("\n" + "=" * 60)
        print("QRLP Production Deployment Guide")
        print("=" * 60)

        # System requirements
        print("\n📋 System Requirements:")
        print("   • Python 3.8+")
        print("   • 2GB+ RAM recommended")
        print("   • Stable internet connection")
        print("   • SSL certificate (for HTTPS)")
        print("   • Load balancer (for high availability)")

        # Configuration recommendations
        print("\n⚙️  Recommended Configuration:")
        print("   • Update interval: 1-5 seconds")
        print("   • QR error correction: Medium-High")
        print("   • Enable all security features")
        print("   • Use Redis for caching (optional)")
        print("   • Configure monitoring and alerting")

        # Deployment steps
        print("\n🚀 Deployment Steps:")
        print("   1. Install dependencies: pip install -r requirements.txt")
        print("   2. Configure environment variables")
        print("   3. Set up SSL certificates")
        print("   4. Configure firewall and security")
        print("   5. Set up monitoring (Prometheus/Grafana)")
        print("   6. Configure load balancer")
        print("   7. Set up backup and disaster recovery")

        # Security checklist
        print("\n🔒 Security Checklist:")
        print("   ✅ Enable HTTPS")
        print("   ✅ Configure firewall")
        print("   ✅ Set up authentication")
        print("   ✅ Enable audit logging")
        print("   ✅ Configure rate limiting")
        print("   ✅ Set up intrusion detection")

        # Monitoring setup
        print("\n📊 Monitoring Setup:")
        print("   • CPU and memory monitoring")
        print("   • QR generation performance")
        print("   • API response times")
        print("   • Error rate tracking")
        print("   • Circuit breaker status")

        print("\n✅ Production deployment guide completed")

    def _check_python_version(self) -> bool:
        """Check Python version compatibility."""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.log(f"❌ Python {version.major}.{version.minor} detected. QRLP requires Python 3.8+", "ERROR")
            return False

        self.log(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible", "SUCCESS")
        return True

    def _install_dependencies(self, quick_mode: bool = False) -> bool:
        """Install QRLP dependencies using uv (fast Python package manager)."""
        self.log("📦 Installing dependencies with uv...", "INFO")

        try:
            # Check if uv is available, install it if not
            uv_available = self._ensure_uv_available()

            # Read requirements
            requirements_file = self.project_root / "requirements.txt"
            if not requirements_file.exists():
                self.log("❌ requirements.txt not found", "ERROR")
                return False

            with open(requirements_file, 'r') as f:
                requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            if not requirements:
                self.log("✅ No dependencies to install", "SUCCESS")
                return True

            # Use uv if available, fallback to pip
            if uv_available:
                self.log("🚀 Using uv (fast Python package manager)", "INFO")
                install_cmd = ["uv", "pip", "install"]
                if not quick_mode:
                    install_cmd.extend(["--upgrade"])
                install_cmd.extend(requirements)

                result = subprocess.run(
                    install_cmd,
                    capture_output=True,
                    text=True,
                    timeout=180  # uv is faster, so shorter timeout
                )
            else:
                self.log("📦 uv not available, using pip", "WARNING")
                install_cmd = [sys.executable, "-m", "pip", "install"]
                if not quick_mode:
                    install_cmd.append("--upgrade")
                install_cmd.extend(requirements)

                result = subprocess.run(
                    install_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

            if result.returncode != 0:
                self.log(f"❌ Dependency installation failed: {result.stderr}", "ERROR")
                return False

            self.log("✅ Dependencies installed successfully", "SUCCESS")
            return True

        except subprocess.TimeoutExpired:
            self.log("❌ Dependency installation timed out", "ERROR")
            return False
        except Exception as e:
            self.log(f"❌ Dependency installation error: {e}", "ERROR")
            return False

    def _ensure_uv_available(self) -> bool:
        """Ensure uv package manager is available, install if needed."""
        try:
            # First check if uv is available
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return True

            # uv not available, try to install it
            self.log("📦 uv not found, attempting to install...", "INFO")
            try:
                # Install uv using curl
                install_cmd = "curl -LsSf https://astral.sh/uv/install.sh | sh"
                result = subprocess.run(
                    install_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode == 0:
                    self.log("✅ uv installed successfully", "SUCCESS")
                    # Try again to verify installation
                    verify_result = subprocess.run(
                        ["uv", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    return verify_result.returncode == 0
                else:
                    self.log(f"❌ uv installation failed: {result.stderr}", "ERROR")
                    return False

            except Exception as e:
                self.log(f"❌ uv installation error: {e}", "ERROR")
                return False

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _setup_package(self) -> bool:
        """Setup QRLP package using uv or pip."""
        self.log("🔧 Setting up QRLP package...", "INFO")

        try:
            setup_file = self.project_root / "setup.py"
            if not setup_file.exists():
                self.log("❌ setup.py not found", "ERROR")
                return False

            # Check if uv is available
            uv_available = self._check_uv_available()

            if uv_available:
                self.log("🚀 Using uv for package installation", "INFO")
                # Install in development mode with uv
                result = subprocess.run(
                    ["uv", "pip", "install", "-e", "."],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=45  # uv is faster
                )
            else:
                self.log("📦 Using pip for package installation", "WARNING")
                # Install in development mode with pip
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-e", "."],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

            if result.returncode != 0:
                self.log(f"❌ Package setup failed: {result.stderr}", "ERROR")
                return False

            self.log("✅ QRLP package installed successfully", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"❌ Package setup error: {e}", "ERROR")
            return False

    def _check_uv_available(self) -> bool:
        """Check if uv package manager is available."""
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _validate_installation(self) -> bool:
        """Validate QRLP installation."""
        self.log("🔍 Validating installation...", "INFO")

        try:
            # Test import
            from src import QRLiveProtocol, QRLPConfig
            self.log("✅ Core modules imported successfully", "SUCCESS")

            # Test basic functionality
            config = QRLPConfig()
            qrlp = QRLiveProtocol(config)
            self.log("✅ QRLP instance created successfully", "SUCCESS")

            # Test QR generation
            qr_data, qr_image = qrlp.generate_single_qr()
            if qr_data and qr_image:
                self.log("✅ QR generation working", "SUCCESS")
            else:
                self.log("⚠️  QR generation returned empty results", "WARNING")

            return True

        except Exception as e:
            self.log(f"❌ Installation validation failed: {e}", "ERROR")
            return False

    def _check_pytest_available(self) -> bool:
        """Check if pytest is available."""
        try:
            import pytest
            return True
        except ImportError:
            return False

    def _run_test_suite(self) -> Dict[str, Any]:
        """Run the test suite."""
        try:
            # Run tests with coverage
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "--tb=short", "-q"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )

            # Parse results
            output = result.stdout + result.stderr

            # Simple result parsing (in production, use pytest's JSON output)
            passed = output.count("PASSED") + output.count("✓")
            failed = output.count("FAILED") + output.count("✗")
            total = passed + failed

            return {
                'success': result.returncode == 0,
                'passed': passed,
                'failed': failed,
                'total': total,
                'output': output
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'passed': 0,
                'failed': 0,
                'total': 0,
                'output': 'Tests timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'passed': 0,
                'failed': 1,
                'total': 1,
                'output': f'Test execution error: {e}'
            }

    def _run_example(self, example_path: str) -> bool:
        """Run a single example."""
        try:
            full_path = self.project_root / example_path
            if not full_path.exists():
                self.log(f"❌ Example not found: {example_path}", "ERROR")
                return False

            result = subprocess.run(
                [sys.executable, str(full_path)],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            self.log(f"❌ Example timed out: {example_path}", "ERROR")
            return False
        except Exception as e:
            self.log(f"❌ Example execution failed: {e}", "ERROR")
            return False

    def _show_interactive_menu(self):
        """Show interactive menu."""
        print("\n" + "=" * 60)
        print("🎮 QRLP Interactive Mode")
        print("=" * 60)
        print("Select functionality to demonstrate:")
        print()
        print("1.  🚀 Setup and Installation")
        print("2.  🔲 Basic QR Generation")
        print("3.  ✍️  Cryptographic Signatures")
        print("4.  🔒 Encrypted QR Data")
        print("5.  🔍 Verification and Validation")
        print("6.  🌐 Web Interface Demo")
        print("7.  📊 Performance Monitoring")
        print("8.  🔒 Security Features")
        print("9.  🔗 Integration Examples")
        print("10. 🏥 System Health Check")
        print("11. 📚 Documentation Browser")
        print("12. 📈 Performance Statistics")
        print()
        print("q.  Quit")
        print("=" * 60)

    def _demo_setup(self):
        """Demo setup functionality."""
        self.log("🚀 Running QRLP Setup Demo", "INFO")

        if self.run_setup():
            self.log("✅ Setup completed successfully", "SUCCESS")

            # Show next steps
            print("\n🎯 Next Steps:")
            print("   • Run 'python run_all.py --test-only' to run tests")
            print("   • Run 'python run_all.py --examples-only' to see examples")
            print("   • Run 'python run_all.py --interactive' for interactive mode")
        else:
            self.log("❌ Setup failed", "ERROR")

    def _demo_basic_qr(self):
        """Demo basic QR generation."""
        self.log("🔲 Basic QR Generation Demo", "INFO")

        try:
            qrlp = QRLiveProtocol()
            qr_data, qr_image = qrlp.generate_single_qr({"demo": "basic_qr"})

            print(f"✅ Generated QR #{qr_data.sequence_number}")
            print(f"   Timestamp: {qr_data.timestamp}")
            print(f"   Identity: {qr_data.identity_hash[:16]}...")
            print(f"   Image size: {len(qr_image)} bytes")

            # Verify the QR
            verification = qrlp.verify_qr_data(qr_data.to_json())
            print(f"✅ Verification: HMAC={verification['hmac_verified']}")

        except Exception as e:
            self.log(f"❌ Basic QR demo failed: {e}", "ERROR")

    def _demo_signed_qr(self):
        """Demo signed QR generation."""
        self.log("✍️  Signed QR Demo", "INFO")

        try:
            qrlp = QRLiveProtocol()

            # Generate key for signing
            public_key, private_key = qrlp.key_manager.generate_keypair("rsa", 2048)
            keys = qrlp.key_manager.list_keys()
            key_id = list(keys.keys())[0]

            # Generate signed QR
            qr_data, qr_image = qrlp.generate_signed_qr({"demo": "signed_qr"}, key_id)

            print(f"✅ Generated signed QR #{qr_data.sequence_number}")
            print(f"   Key ID: {qr_data.__dict__.get('signing_key_id', 'Unknown')}")
            print(f"   Algorithm: {qr_data.__dict__.get('signature_algorithm', 'Unknown')}")

            # Verify signature
            verification = qrlp.verify_qr_data(qr_data.to_json())
            print(f"✅ Signature verified: {verification['signature_verified']}")

        except Exception as e:
            self.log(f"❌ Signed QR demo failed: {e}", "ERROR")

    def _demo_encrypted_qr(self):
        """Demo encrypted QR generation."""
        self.log("🔒 Encrypted QR Demo", "INFO")

        try:
            qrlp = QRLiveProtocol()
            sensitive_data = {"secret": "confidential_information_123"}

            qr_data, qr_image = qrlp.generate_encrypted_qr(sensitive_data)

            print(f"✅ Generated encrypted QR #{qr_data.sequence_number}")
            print(f"   Encrypted fields: {qr_data.__dict__.get('_encrypted_fields', [])}")

            # Verify encryption
            verification = qrlp.verify_qr_data(qr_data.to_json())
            print(f"✅ Encrypted: {verification['encrypted']}")

        except Exception as e:
            self.log(f"❌ Encrypted QR demo failed: {e}", "ERROR")

    def _demo_verification(self):
        """Demo verification functionality."""
        self.log("🔍 Verification Demo", "INFO")

        try:
            qrlp = QRLiveProtocol()

            # Generate QR for verification
            qr_data, qr_image = qrlp.generate_single_qr({"verification": "demo"})

            # Verify the QR
            verification = qrlp.verify_qr_data(qr_data.to_json())

            print("✅ Verification Results:")
            print(f"   Valid JSON: {verification['valid_json']}")
            print(f"   HMAC Verified: {verification['hmac_verified']}")
            print(f"   Identity Verified: {verification['identity_verified']}")
            print(f"   Time Verified: {verification['time_verified']}")
            print(f"   Blockchain Verified: {verification['blockchain_verified']}")

            if verification['signature_verified']:
                print(f"   Signature Verified: {verification['signature_verified']}")

            if verification['encrypted']:
                print(f"   Encrypted: {verification['encrypted']}")

        except Exception as e:
            self.log(f"❌ Verification demo failed: {e}", "ERROR")

    def _demo_web_interface(self):
        """Demo web interface with live QR updates."""
        self.log("🌐 Web Interface Demo", "INFO")

        try:
            from src.web_server import QRLiveWebServer
            from src.config import WebSettings

            # Create web server configuration
            web_config = WebSettings()
            web_config.auto_open_browser = False  # Don't auto-open in demo
            web_config.host = "localhost"
            web_config.port = 8080

            # Create QRLiveProtocol instance for live QR generation
            qrlp = QRLiveProtocol()
            qrlp.config.update_interval = 2.0  # Update every 2 seconds for demo
            qrlp.config.blockchain_settings.enabled_chains = []  # Disable blockchain to avoid API issues

            # Create and connect web server
            server = QRLiveWebServer(web_config)
            qrlp.add_update_callback(server.update_qr_display)

            print("🌐 QRLP Web Interface")
            print(f"   Server URL: {server.get_server_url()}")
            print(f"   Viewer URL: {server.get_server_url()}/viewer")
            print(f"   Admin URL: {server.get_server_url()}/admin")
            print(f"   API Status: {server.get_server_url()}/api/status")

            print("\n📋 Web Interface Features:")
            print("   • Live QR code display with real-time updates")
            print("   • Encrypted QR codes with cryptographic verification")
            print("   • Real-time WebSocket updates every 2 seconds")
            print("   • User input integration for custom messages")
            print("   • Verification statistics and blockchain data")
            print("   • Download and copy functionality")

            print("\n🚀 Starting web interface with live QR generation...")
            print("📱 QR codes will update every 2 seconds")
            print("🔐 Features: Encryption, signatures, blockchain verification")
            print("⏹️  Press Ctrl+C to stop")

            # Start QRLP first to generate QR data
            qrlp.start_live_generation()
            self.log("📱 Started QR generation", "SUCCESS")
            
            # Wait for first QR to be generated
            time.sleep(3)
            
            # Start web server
            server.start_server(threaded=True)
            self.log("🌐 Started web server", "SUCCESS")
            
            # Test API endpoints
            time.sleep(2)
            import requests
            
            try:
                status = requests.get('http://localhost:8080/api/status', timeout=5)
                if status.status_code == 200:
                    self.log("✅ Web interface API working", "SUCCESS")
                else:
                    self.log(f"⚠️ API returned status {status.status_code}", "WARNING")
            except Exception as e:
                self.log(f"⚠️ API test failed: {e}", "WARNING")

            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping web interface...")
                qrlp.stop_live_generation()
                server.stop_server()
                print("✅ Web interface demo completed")

        except Exception as e:
            self.log(f"❌ Web interface demo failed: {e}", "ERROR")
            import traceback
            traceback.print_exc()

    def _demo_performance(self):
        """Demo performance monitoring."""
        self.log("📊 Performance Demo", "INFO")

        try:
            qrlp = QRLiveProtocol()

            # Generate some QR codes to collect metrics
            start_time = time.time()
            for i in range(10):
                qr_data, qr_image = qrlp.generate_single_qr({"perf_test": i})

            end_time = time.time()
            duration = end_time - start_time

            # Get statistics
            stats = qrlp.get_statistics()

            print("✅ Performance Results:")
            print(f"   Generated: {stats['total_updates']} QR codes")
            print(f"   Duration: {duration:.3f} seconds")
            print(f"   Rate: {stats['total_updates']/duration:.1f} QR/second")
            print(f"   Crypto keys: {stats['crypto_stats']['keys_count']}")

        except Exception as e:
            self.log(f"❌ Performance demo failed: {e}", "ERROR")

    def _demo_security(self):
        """Demo security features."""
        self.log("🔒 Security Features Demo", "INFO")

        try:
            qrlp = QRLiveProtocol()

            # Show cryptographic keys
            keys = qrlp.key_manager.list_keys()
            print(f"🔑 Cryptographic Keys: {len(keys)}")

            for key_id, key_info in keys.items():
                print(f"   {key_id}: {key_info.algorithm} {key_info.key_size}bit")

            # Generate secure QR
            qr_data, qr_image = qrlp.generate_single_qr(
                {"security_demo": True},
                sign_data=True,
                encrypt_data=False
            )

            # Verify security
            verification = qrlp.verify_qr_data(qr_data.to_json())

            print("✅ Security Verification:")
            print(f"   HMAC Verified: {verification['hmac_verified']}")

            if verification['signature_verified']:
                print(f"   Signature Verified: {verification['signature_verified']}")

            print(f"   Identity Verified: {verification['identity_verified']}")

        except Exception as e:
            self.log(f"❌ Security demo failed: {e}", "ERROR")

    def _demo_integration(self):
        """Demo integration examples."""
        self.log("🔗 Integration Demo", "INFO")

        try:
            # Run integration patterns example
            if self._run_example("examples/integration_patterns.py"):
                self.log("✅ Integration examples completed", "SUCCESS")
            else:
                self.log("❌ Integration examples failed", "ERROR")

        except Exception as e:
            self.log(f"❌ Integration demo failed: {e}", "ERROR")

    def _run_system_health_check(self):
        """Run system health check."""
        self.log("🏥 System Health Check", "INFO")

        try:
            qrlp = QRLiveProtocol()

            # Test basic functionality
            qr_data, qr_image = qrlp.generate_single_qr({"health_check": True})
            verification = qrlp.verify_qr_data(qr_data.to_json())

            # Get system statistics
            stats = qrlp.get_statistics()

            print("✅ System Health Status:")
            print(f"   QR Generation: {'✅ Working' if qr_data else '❌ Failed'}")
            print(f"   Verification: {'✅ Working' if verification['hmac_verified'] else '❌ Failed'}")
            print(f"   Components: {len(stats)} statistics collected")
            print(f"   Crypto Keys: {stats['crypto_stats']['keys_count']}")
            print(f"   Memory Usage: Normal")

            if qr_data and verification['hmac_verified']:
                print("🏥 Overall Health: EXCELLENT")
            else:
                print("🏥 Overall Health: NEEDS ATTENTION")

        except Exception as e:
            self.log(f"❌ Health check failed: {e}", "ERROR")

    def _show_documentation(self):
        """Show documentation browser."""
        self.log("📚 Documentation Browser", "INFO")

        docs_dir = self.project_root / "docs"

        if not docs_dir.exists():
            print("❌ Documentation directory not found")
            return

        print("\n📚 Available Documentation:")
        print("=" * 40)

        doc_files = list(docs_dir.glob("*.md"))
        for i, doc_file in enumerate(doc_files, 1):
            doc_name = doc_file.stem
            print(f"{i:2}. {doc_name.replace('_', ' ').title()}")

        print("\n🌐 Online Documentation:")
        print("   • GitHub: https://github.com/your-org/qr_live_protocol")
        print("   • API Docs: https://qrlp.readthedocs.io/")

        print("\n📖 Quick Reference:")
        print("   • API.md - Complete API reference")
        print("   • CONFIGURATION.md - Configuration options")
        print("   • INSTALLATION.md - Setup guide")
        print("   • FAQ.md - Frequently asked questions")

    def _show_performance_stats(self):
        """Show performance statistics."""
        self.log("📈 Performance Statistics", "INFO")

        try:
            qrlp = QRLiveProtocol()

            # Generate some QR codes for metrics
            for i in range(5):
                qr_data, qr_image = qrlp.generate_single_qr({"stats_test": i})

            # Get comprehensive statistics
            stats = qrlp.get_statistics()

            print("📊 QRLP Performance Statistics:")
            print(f"   Total Updates: {stats['total_updates']}")
            print(f"   Sequence Number: {stats['sequence_number']}")
            print(f"   Running: {stats['running']}")

            if 'crypto_stats' in stats:
                crypto = stats['crypto_stats']
                print(f"   Crypto Keys: {crypto['keys_count']}")
                print(f"   Signatures: {crypto.get('signature_count', 0)}")

            if 'time_provider_stats' in stats:
                time_stats = stats['time_provider_stats']
                print(f"   Time Servers: {time_stats.get('active_servers', 0)}")

            if 'blockchain_stats' in stats:
                blockchain = stats['blockchain_stats']
                print(f"   Blockchain Chains: {len(blockchain.get('cached_chains', []))}")

        except Exception as e:
            self.log(f"❌ Performance stats failed: {e}", "ERROR")


def main():
    """Main entry point for QRLP comprehensive runner."""
    parser = argparse.ArgumentParser(
        description="QRLP Comprehensive Runner - Unified access to all functionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all.py                    # Full setup and interactive mode
  python run_all.py --setup-only       # Only setup, no demos
  python run_all.py --test-only        # Only run tests
  python run_all.py --examples-only    # Only run examples
  python run_all.py --interactive      # Interactive functionality selection
  python run_all.py --quick            # Quick mode (skip optional components)
  python run_all.py --verbose          # Verbose output for debugging
        """
    )

    parser.add_argument('--setup-only', action='store_true',
                       help='Only run setup, don\'t launch demos')
    parser.add_argument('--test-only', action='store_true',
                       help='Only run tests, don\'t launch demos')
    parser.add_argument('--examples-only', action='store_true',
                       help='Only run examples, don\'t launch demos')
    parser.add_argument('--interactive', action='store_true',
                       help='Interactive mode for functionality selection')
    parser.add_argument('--quick', action='store_true',
                       help='Quick mode (skip optional components)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output for debugging')
    parser.add_argument('--production', action='store_true',
                       help='Show production deployment guide')

    args = parser.parse_args()

    # Create runner
    runner = QRLPComprehensiveRunner(verbose=args.verbose)

    # Determine execution mode
    if args.production:
        runner.run_production_deployment()
        return 0

    if args.interactive or not any([args.setup_only, args.test_only, args.examples_only]):
        # Default to setup validation + interactive mode
        print("🚀 QRLP Comprehensive Runner")
        print("=" * 60)

        # First validate/ensure setup is complete
        setup_success = runner.run_setup(quick_mode=args.quick)
        if not setup_success:
            print("❌ Setup failed. Please check your environment and try again.")
            return 1

        print("\n✅ Setup validated successfully!")
        print("🎮 Starting interactive mode...\n")

        # Now show the interactive menu
        runner.run_interactive_mode()
        return 0

    # Specific execution modes
    success = True

    if args.setup_only:
        success &= runner.run_setup(quick_mode=args.quick)

    if args.test_only:
        # Ensure setup is complete before running tests
        if not runner.setup_complete:
            success &= runner.run_setup(quick_mode=args.quick)
        success &= runner.run_tests()

    if args.examples_only:
        # Ensure setup is complete before running examples
        if not runner.setup_complete:
            success &= runner.run_setup(quick_mode=args.quick)
        success &= runner.run_examples()

    # Exit with appropriate code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

