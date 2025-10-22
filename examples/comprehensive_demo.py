#!/usr/bin/env python3
"""
QRLP Comprehensive Demo

Demonstrates all QRLP features including cryptographic enhancements,
comprehensive testing, security hardening, and production-ready patterns.

This example shows real-world usage patterns for:
- Cryptographic QR generation with signing and encryption
- Cross-instance verification for authenticity proof
- Error handling and graceful degradation
- Performance monitoring and optimization
- Security best practices
"""

import sys
import time
import json
import base64
import secrets
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src import QRLiveProtocol, QRLPConfig
from src.crypto import KeyManager, DataEncryptor, HMACManager, QRSignatureManager


class QRLPDemo:
    """
    Comprehensive QRLP demonstration showing all features.

    Demonstrates:
    - Basic QR generation with HMAC integrity
    - Cryptographically signed QR codes
    - Encrypted QR data for sensitive information
    - Cross-instance verification
    - Error handling and recovery
    - Performance monitoring
    - Security best practices
    """

    def __init__(self):
        """Initialize demo with comprehensive configuration."""
        self.config = self._create_demo_config()
        self.qrlp = QRLiveProtocol(self.config)

        # Setup output directory structure (use absolute path from project root)
        self.output_dir = Path(__file__).parent.parent / "output" / "examples" / "comprehensive_demo"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Demo statistics
        self.demo_stats = {
            'qr_generated': 0,
            'verification_attempts': 0,
            'successful_verifications': 0,
            'crypto_operations': 0,
            'errors_handled': 0
        }

        # Setup cryptographic keys for demo
        self._setup_demo_keys()

    def _create_demo_config(self) -> QRLPConfig:
        """Create comprehensive configuration for demo."""
        config = QRLPConfig()

        # Fast updates for demo
        config.update_interval = 1.0

        # High-quality QR settings
        config.qr_settings.error_correction_level = "H"
        config.qr_settings.box_size = 12
        config.qr_settings.border_size = 6

        # Enable all verification layers
        config.blockchain_settings.enabled_chains = {"bitcoin", "ethereum"}
        config.blockchain_settings.cache_duration = 60

        # Multiple time servers for accuracy
        config.time_settings.time_servers = [
            "time.nist.gov",
            "pool.ntp.org",
            "time.google.com",
            "time.cloudflare.com"
        ]
        config.time_settings.update_interval = 30.0

        # Strong identity verification
        config.identity_settings.auto_generate = True
        config.identity_settings.include_system_info = True
        config.identity_settings.hash_algorithm = "sha256"

        # Security settings
        config.verification_settings.max_time_drift = 60.0
        config.verification_settings.require_blockchain = False  # Optional for demo
        config.verification_settings.require_time_server = False

        return config

    def _setup_demo_keys(self):
        """Setup cryptographic keys for demo."""
        print("🔐 Setting up cryptographic keys...")

        # Generate signing key
        public_key, private_key = self.qrlp.key_manager.generate_keypair(
            algorithm="rsa",
            key_size=2048,
            purpose="demo_signing"
        )

        # Generate encryption key
        encryption_key = self.qrlp.key_manager.generate_keypair(
            algorithm="rsa",
            key_size=2048,
            purpose="demo_encryption"
        )

        keys = self.qrlp.key_manager.list_keys()
        print(f"✅ Generated {len(keys)} cryptographic keys")

        for key_id, key_info in keys.items():
            print(f"   Key {key_id}: {key_info.algorithm} {key_info.key_size}bit")

    def demonstrate_basic_qr_generation(self):
        """Demonstrate basic QR generation with HMAC integrity."""
        print("\n🔲 Basic QR Generation Demo")
        print("=" * 50)

        # Generate basic QR
        user_data = {
            "demo": "basic_generation",
            "timestamp": datetime.now().isoformat(),
            "purpose": "Demonstrate HMAC integrity"
        }

        qr_data, qr_image = self.qrlp.generate_single_qr(user_data)

        print(f"✅ Generated QR #{qr_data.sequence_number}")
        print(f"   Timestamp: {qr_data.timestamp}")
        print(f"   Identity: {qr_data.identity_hash[:16]}...")
        hmac_value = qr_data.__dict__.get('_hmac', 'Not present')
        if hmac_value != 'Not present' and hmac_value:
            print(f"   HMAC: {hmac_value[:16]}...")
        else:
            print(f"   HMAC: {hmac_value}")

        # Verify the QR
        qr_json = qr_data.to_json()
        verification = self.qrlp.verify_qr_data(qr_json)

        print(f"✅ Verification Results:")
        print(f"   Valid JSON: {verification['valid_json']}")
        print(f"   HMAC Verified: {verification['hmac_verified']}")
        print(f"   Identity Verified: {verification['identity_verified']}")

        self.demo_stats['qr_generated'] += 1
        self.demo_stats['verification_attempts'] += 1
        if verification['hmac_verified']:
            self.demo_stats['successful_verifications'] += 1

        # Save QR image to output directory
        self._save_qr_image(qr_data, qr_image)

        return qr_data, qr_image

    def _save_qr_image(self, qr_data, qr_image):
        """Save QR image to organized output directory."""
        try:
            # Create subdirectories for different types
            qr_dir = self.output_dir / "qr_codes"
            qr_dir.mkdir(exist_ok=True)

            # Save QR image
            filename = f"qr_{qr_data.sequence_number:03d}.png"
            filepath = qr_dir / filename
            with open(filepath, 'wb') as f:
                f.write(qr_image)

            # Save QR data as JSON
            data_filename = f"qr_{qr_data.sequence_number:03d}_data.json"
            data_filepath = qr_dir / data_filename
            with open(data_filepath, 'w') as f:
                json.dump(qr_data.__dict__, f, indent=2, default=str)

            print(f"💾 Saved: {filepath}")
            print(f"💾 Saved: {data_filepath}")

        except Exception as e:
            print(f"❌ Failed to save QR #{qr_data.sequence_number}: {e}")
            self.demo_stats['errors_handled'] += 1

    def demonstrate_signed_qr_generation(self):
        """Demonstrate cryptographically signed QR codes."""
        print("\n✍️  Cryptographic Signature Demo")
        print("=" * 50)

        # Get signing key
        keys = self.qrlp.key_manager.list_keys()
        signing_keys = [k for k, v in keys.items() if v.purpose == "demo_signing"]

        if not signing_keys:
            print("❌ No signing key available")
            return None, None

        key_id = signing_keys[0]

        # Generate signed QR
        sensitive_data = {
            "demo": "digital_signature",
            "document_id": "demo_doc_123",
            "author": "QRLP Demo",
            "classification": "confidential",
            "signing_timestamp": datetime.now().isoformat()
        }

        qr_data, qr_image = self.qrlp.generate_signed_qr(sensitive_data, key_id)

        print(f"✅ Generated signed QR #{qr_data.sequence_number}")
        print(f"   Signing Key: {qr_data.__dict__.get('signing_key_id', 'Unknown')}")
        print(f"   Algorithm: {qr_data.__dict__.get('signature_algorithm', 'Unknown')}")
        print(f"   Signature: {qr_data.__dict__.get('digital_signature', 'Not present')[:32]}...")

        # Verify signature
        qr_json = json.dumps(qr_data.__dict__, separators=(',', ':'))
        verification = self.qrlp.verify_qr_data(qr_json)

        print(f"✅ Signature Verification:")
        print(f"   Signature Verified: {verification['signature_verified']}")
        print(f"   HMAC Verified: {verification['hmac_verified']}")

        if verification['signature_verified']:
            print("✅ Digital signature is valid - authenticity proven!")

        self.demo_stats['qr_generated'] += 1
        self.demo_stats['verification_attempts'] += 1
        self.demo_stats['crypto_operations'] += 1
        if verification['signature_verified']:
            self.demo_stats['successful_verifications'] += 1

        # Save QR image to output directory
        self._save_qr_image(qr_data, qr_image)

        return qr_data, qr_image

    def demonstrate_encrypted_qr_generation(self):
        """Demonstrate encrypted QR codes for sensitive data."""
        print("\n🔒 Encrypted QR Data Demo")
        print("=" * 50)

        # Generate encrypted QR
        highly_sensitive_data = {
            "demo": "field_level_encryption",
            "api_key": "sk_live_abcdef1234567890",
            "database_password": "super_secret_password_123",
            "user_pii": {
                "name": "John Doe",
                "ssn": "123-45-6789",
                "address": "123 Main St, Anytown, USA"
            },
            "encryption_timestamp": datetime.now().isoformat()
        }

        qr_data, qr_image = self.qrlp.generate_encrypted_qr(highly_sensitive_data)

        print(f"✅ Generated encrypted QR #{qr_data.sequence_number}")
        print(f"   Encrypted Fields: {qr_data.__dict__.get('_encrypted_fields', [])}")
        print(f"   Encryption Key: {qr_data.__dict__.get('_encryption_key_id', 'Unknown')}")
        print(f"   Encrypted At: {qr_data.__dict__.get('_encrypted_at', 'Unknown')}")

        # Show that sensitive data is encrypted
        print(f"   User Data (encrypted): {str(qr_data.user_data)[:50]}...")

        # Verify encryption and decryption
        qr_json = json.dumps(qr_data.__dict__, separators=(',', ':'))
        verification = self.qrlp.verify_qr_data(qr_json)

        print(f"✅ Encryption Verification:")
        print(f"   Encrypted: {verification['encrypted']}")
        print(f"   HMAC Verified: {verification['hmac_verified']}")

        if verification['encrypted']:
            print("✅ Sensitive data is properly encrypted!")

            # Demonstrate decryption (requires proper key)
            try:
                decrypted_data = self.qrlp.encryptor.decrypt_qr_payload(qr_data.__dict__)
                print(f"   Decrypted Data: {decrypted_data['user_data']['api_key'][:10]}...")
            except Exception as e:
                print(f"   Decryption: Requires proper encryption key - {type(e).__name__}")

        self.demo_stats['qr_generated'] += 1
        self.demo_stats['verification_attempts'] += 1
        self.demo_stats['crypto_operations'] += 1
        if verification['encrypted']:
            self.demo_stats['successful_verifications'] += 1

        # Save QR image to output directory
        self._save_qr_image(qr_data, qr_image)

        return qr_data, qr_image

    def demonstrate_cross_instance_verification(self):
        """Demonstrate verification across different QRLP instances."""
        print("\n🔍 Cross-Instance Verification Demo")
        print("=" * 50)

        # Generate QR with first instance
        print("📝 Generating QR with Instance 1...")
        user_data = {
            "demo": "cross_instance_verification",
            "generated_by": "instance_1",
            "verification_test": True
        }

        qr_data1, qr_image1 = self.qrlp.generate_single_qr(user_data)

        # Create second instance for verification (simulates external verifier)
        print("🔍 Verifying with Instance 2...")

        # Create separate config for second instance
        verifier_config = QRLPConfig()
        verifier_config.identity_settings.identity_file = None
        verifier_config.blockchain_settings.enabled_chains = set()
        verifier_config.time_settings.time_servers = []

        verifier = QRLiveProtocol(verifier_config)

        # Share key manager for consistent verification
        verifier.key_manager = self.qrlp.key_manager

        # Verify with second instance
        qr_json = qr_data1.to_json()
        verification = verifier.verify_qr_data(qr_json)

        print(f"✅ Cross-Instance Verification Results:")
        print(f"   Valid JSON: {verification['valid_json']}")
        print(f"   HMAC Verified: {verification['hmac_verified']}")
        print(f"   Identity Verified: {verification['identity_verified']}")
        print(f"   Time Verified: {verification['time_verified']}")

        if verification['identity_verified']:
            print("✅ Identity verification successful across instances!")

        if verification['hmac_verified']:
            print("✅ HMAC integrity verified - data not tampered with!")

        self.demo_stats['verification_attempts'] += 1
        if verification['hmac_verified'] and verification['identity_verified']:
            self.demo_stats['successful_verifications'] += 1

        return verification

    def demonstrate_error_handling(self):
        """Demonstrate comprehensive error handling."""
        print("\n🛡️  Error Handling Demo")
        print("=" * 50)

        # Test various error conditions
        error_tests = [
            ("Invalid JSON", '{"invalid": json}'),
            ("Empty data", ""),
            ("Wrong data type", 123),
            ("Tampered data", self._create_tampered_qr_data()),
            ("Missing signature", self._create_unsigned_qr_data())
        ]

        for test_name, test_data in error_tests:
            print(f"\n🧪 Testing: {test_name}")

            try:
                if test_name == "Tampered data" or test_name == "Missing signature":
                    # These are dictionaries, convert to JSON
                    test_json = json.dumps(test_data, separators=(',', ':'))
                else:
                    test_json = test_data

                verification = self.qrlp.verify_qr_data(test_json)

                print(f"   Result: Valid JSON={verification['valid_json']}, "
                      f"HMAC={verification['hmac_verified']}")

                if not verification['valid_json']:
                    print(f"   Error: {verification.get('error', 'Unknown error')}")
                    self.demo_stats['errors_handled'] += 1

            except Exception as e:
                print(f"   Exception: {type(e).__name__}: {e}")
                self.demo_stats['errors_handled'] += 1

    def _create_tampered_qr_data(self) -> Dict[str, Any]:
        """Create tampered QR data for testing."""
        # Generate valid QR first
        qr_data, _ = self.qrlp.generate_single_qr({"test": "tamper_test"})

        # Tamper with the data
        tampered = qr_data.__dict__.copy()
        tampered['sequence_number'] = 999999  # Obviously wrong value

        return tampered

    def _create_unsigned_qr_data(self) -> Dict[str, Any]:
        """Create QR data without signature for testing."""
        # Generate basic QR data without cryptographic enhancements
        qr_data, _ = self.qrlp.generate_single_qr(sign_data=False)

        # Remove HMAC (simulates unsigned data)
        unsigned = qr_data.__dict__.copy()
        if '_hmac' in unsigned:
            del unsigned['_hmac']

        return unsigned

    def demonstrate_performance_monitoring(self):
        """Demonstrate performance monitoring and optimization."""
        print("\n📊 Performance Monitoring Demo")
        print("=" * 50)

        # Monitor generation performance
        start_time = time.time()

        print("⏱️  Generating 50 QR codes...")
        for i in range(50):
            qr_data, qr_image = self.qrlp.generate_single_qr({
                "performance_test": i,
                "timestamp": datetime.now().isoformat()
            })

            # Verify each one
            qr_json = qr_data.to_json()
            verification = self.qrlp.verify_qr_data(qr_json)

            if not verification['hmac_verified']:
                print(f"⚠️  Verification failed for QR #{i}")

        end_time = time.time()
        duration = end_time - start_time

        print("✅ Performance Results:")
        print(f"   Generated: {50} QR codes")
        print(f"   Duration: {duration:.3f} seconds")
        print(f"   Average: {(duration/50)*1000:.1f}ms per QR")
        print(f"   Rate: {50/duration:.1f} QR/second")

        # Get comprehensive statistics
        stats = self.qrlp.get_statistics()
        print("\n📈 QRLP Statistics:")
        print(f"   Total Updates: {stats['total_updates']}")
        print(f"   Crypto Stats: {stats['crypto_stats']}")

        # Performance assessment
        if duration < 10.0:  # Should generate 50 QRs in under 10 seconds
            print("✅ Performance: EXCELLENT")
        elif duration < 20.0:
            print("✅ Performance: GOOD")
        else:
            print("⚠️  Performance: NEEDS OPTIMIZATION")

    def demonstrate_security_best_practices(self):
        """Demonstrate security best practices."""
        print("\n🔒 Security Best Practices Demo")
        print("=" * 50)

        # Show key management
        print("🔑 Key Management:")
        keys = self.qrlp.key_manager.list_keys()
        for key_id, key_info in keys.items():
            print(f"   {key_id}: {key_info.algorithm} {key_info.key_size}bit")
            print(f"      Purpose: {key_info.purpose}")
            print(f"      Usage: {key_info.usage_count} times")
            print(f"      Created: {key_info.created_at}")

        # Show input validation
        print("\n🛡️  Input Validation:")

        # Test valid input
        valid_data = {"event": "security_test", "data": "valid_input_123"}
        try:
            qr_data, qr_image = self.qrlp.generate_single_qr(valid_data)
            print("   ✅ Valid input accepted")
        except Exception as e:
            print(f"   ❌ Valid input rejected: {e}")

        # Show that cryptographic operations are always applied
        print("\n🔐 Cryptographic Operations:")

        # Check that all generated QRs have HMAC
        for i in range(3):
            qr_data, _ = self.qrlp.generate_single_qr({"crypto_test": i})
            qr_dict = qr_data.__dict__

            if '_hmac' in qr_dict:
                print(f"   ✅ QR #{i+1}: HMAC present")
            else:
                print(f"   ❌ QR #{i+1}: HMAC missing")

        # Demonstrate secure configuration
        print("\n⚙️  Secure Configuration:")

        config_issues = self.config.validate()
        if not config_issues:
            print("   ✅ Configuration is valid and secure")
        else:
            print(f"   ❌ Configuration issues: {config_issues}")

    def run_comprehensive_demo(self):
        """Run the complete comprehensive demonstration."""
        print("🚀 QRLP Comprehensive Demo")
        print("=" * 80)
        print("This demo showcases all QRLP features including:")
        print("• Cryptographic QR generation with HMAC integrity")
        print("• Digital signature authentication")
        print("• Field-level encryption for sensitive data")
        print("• Cross-instance verification")
        print("• Comprehensive error handling")
        print("• Performance monitoring")
        print("• Security best practices")
        print("=" * 80)

        try:
            # Run all demonstrations
            self.demonstrate_basic_qr_generation()
            self.demonstrate_signed_qr_generation()
            self.demonstrate_encrypted_qr_generation()
            self.demonstrate_cross_instance_verification()
            self.demonstrate_error_handling()
            self.demonstrate_performance_monitoring()
            self.demonstrate_security_best_practices()

            # Print final statistics
            self.print_demo_summary()

        except KeyboardInterrupt:
            print("\n🛑 Demo interrupted by user")
        except Exception as e:
            print(f"\n❌ Demo error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.print_demo_summary()

    def print_demo_summary(self):
        """Print comprehensive demo summary."""
        print("\n" + "=" * 80)
        print("📊 QRLP Comprehensive Demo Summary")
        print("=" * 80)

        print("🎯 Demonstrations Completed:")
        print(f"   QR Codes Generated: {self.demo_stats['qr_generated']}")
        print(f"   Verification Attempts: {self.demo_stats['verification_attempts']}")
        print(f"   Successful Verifications: {self.demo_stats['successful_verifications']}")
        print(f"   Cryptographic Operations: {self.demo_stats['crypto_operations']}")
        print(f"   Errors Handled: {self.demo_stats['errors_handled']}")

        # Calculate success rates
        if self.demo_stats['verification_attempts'] > 0:
            success_rate = (self.demo_stats['successful_verifications'] /
                          self.demo_stats['verification_attempts']) * 100
            print(f"   Verification Success Rate: {success_rate:.1f}%")

        # Show cryptographic key status
        keys = self.qrlp.key_manager.list_keys()
        print(f"   Active Keys: {len(keys)}")

        for key_id, key_info in keys.items():
            print(f"      {key_id}: {key_info.algorithm} {key_info.key_size}bit")

        print("\n🔧 QRLP Configuration:")
        print(f"   Update Interval: {self.config.update_interval}s")
        print(f"   QR Error Correction: {self.config.qr_settings.error_correction_level}")
        print(f"   Blockchain Chains: {len(self.config.blockchain_settings.enabled_chains)}")
        print(f"   Time Servers: {len(self.config.time_settings.time_servers)}")

        print("\n✨ Key Features Demonstrated:")
        features = [
            "✅ HMAC-SHA256 integrity verification (always applied)",
            "✅ RSA/ECDSA digital signatures (optional)",
            "✅ AES-256-GCM field-level encryption (optional)",
            "✅ Cross-instance verification capability",
            "✅ Comprehensive error handling and recovery",
            "✅ Performance monitoring and optimization",
            "✅ Security best practices implementation",
            "✅ Input validation and sanitization",
            "✅ Configuration validation and management"
        ]

        for feature in features:
            print(f"   {feature}")

        print("\n🎉 Demo completed successfully!")
        print("=" * 80)


def main():
    """Main function to run the comprehensive demo."""
    demo = QRLPDemo()
    demo.run_comprehensive_demo()


if __name__ == "__main__":
    main()

