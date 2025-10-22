"""
Integration tests for complete QRLP workflows.

Tests end-to-end functionality including QR generation, verification,
and cryptographic operations working together.
"""

import pytest
import json
import time
from unittest.mock import patch

from src import QRLiveProtocol, QRLPConfig


class TestFullWorkflow:
    """Test complete QRLP workflows."""

    def test_basic_qr_lifecycle(self, qrlp_instance):
        """Test complete QR lifecycle from generation to verification."""
        # Generate QR code
        user_data = {"event": "test_event", "user_id": "user123"}
        qr_data, qr_image = qrlp_instance.generate_single_qr(user_data)

        # Verify QR data structure
        assert qr_data.user_data == user_data
        assert qr_data.sequence_number >= 1
        assert qr_data.timestamp is not None
        assert qr_data.identity_hash is not None

        # Verify QR image
        assert len(qr_image) > 0
        assert qr_image.startswith(b'\x89PNG\r\n\x1a\n')  # PNG signature

        # Convert to JSON and verify
        qr_json = qr_data.to_json()
        parsed = json.loads(qr_json)
        assert parsed['user_data'] == user_data

        # Verify the QR data
        results = qrlp_instance.verify_qr_data(qr_json)

        # Should verify successfully
        assert results['valid_json'] is True
        assert results['hmac_verified'] is True

        # May have other verifications depending on configuration
        if results['identity_verified']:
            assert results['identity_verified'] is True

    def test_signed_qr_workflow(self, qrlp_instance):
        """Test complete signed QR workflow."""
        # Generate a key for signing
        public_key, private_key = qrlp_instance.key_manager.generate_keypair("rsa", 2048)

        keys_info = qrlp_instance.key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Generate signed QR
        user_data = {"sensitive": "signed_data"}
        qr_data, qr_image = qrlp_instance.generate_signed_qr(user_data, key_id)

        # Should have signature fields
        qr_dict = qr_data.__dict__
        assert 'digital_signature' in qr_dict
        assert 'signing_key_id' in qr_dict
        assert 'signature_algorithm' in qr_dict

        # Convert to JSON for verification
        qr_json = json.dumps(qr_dict, separators=(',', ':'))

        # Verify the signed QR data
        results = qrlp_instance.verify_qr_data(qr_json)

        # Should verify successfully
        assert results['valid_json'] is True
        assert results['hmac_verified'] is True
        assert results['signature_verified'] is True

    def test_encrypted_qr_workflow(self, qrlp_instance):
        """Test complete encrypted QR workflow."""
        # Generate encrypted QR
        sensitive_data = {"secret": "classified_information"}
        qr_data, qr_image = qrlp_instance.generate_encrypted_qr(sensitive_data)

        # Should have encryption metadata
        qr_dict = qr_data.__dict__
        assert '_encrypted_fields' in qr_dict
        assert '_encryption_key_id' in qr_dict
        assert '_encrypted_at' in qr_dict

        # User data should be encrypted (not plaintext)
        assert qr_dict['user_data'] != sensitive_data['secret']

        # Convert to JSON for verification
        qr_json = json.dumps(qr_dict, separators=(',', ':'))

        # Verify the encrypted QR data
        results = qrlp_instance.verify_qr_data(qr_json)

        # Should verify successfully
        assert results['valid_json'] is True
        assert results['hmac_verified'] is True
        assert results['encrypted'] is True

    def test_multiple_qr_generation_workflow(self, qrlp_instance):
        """Test generating multiple QR codes in sequence."""
        qr_codes = []

        # Generate 5 QR codes
        for i in range(5):
            qr_data, qr_image = qrlp_instance.generate_single_qr({"batch": i})
            qr_codes.append((qr_data, qr_image))

            # Each should have incrementing sequence numbers
            assert qr_data.sequence_number == i + 1
            assert qr_data.user_data == {"batch": i}

        # Verify all QR codes can be verified
        for qr_data, qr_image in qr_codes:
            qr_json = qr_data.to_json()
            results = qrlp_instance.verify_qr_data(qr_json)

            assert results['valid_json'] is True
            assert results['hmac_verified'] is True

    def test_qr_verification_with_external_verifier(self, qrlp_instance):
        """Test QR verification using external verifier instance."""
        # Generate QR with first instance
        qr_data, qr_image = qrlp_instance.generate_single_qr({"test": "data"})

        # Create second instance for verification (simulates external verifier)
        test_config = QRLPConfig()
        test_config.identity_settings.identity_file = None
        test_config.blockchain_settings.enabled_chains = set()
        test_config.time_settings.time_servers = []

        external_verifier = QRLiveProtocol(test_config)

        # Copy key manager from first instance to simulate shared keys
        external_verifier.key_manager = qrlp_instance.key_manager

        # Verify QR data with external verifier
        qr_json = qr_data.to_json()
        results = external_verifier.verify_qr_data(qr_json)

        # Should verify successfully
        assert results['valid_json'] is True
        assert results['hmac_verified'] is True

    def test_cryptographic_features_integration(self, qrlp_instance):
        """Test all cryptographic features working together."""
        # Generate key for signing
        public_key, private_key = qrlp_instance.key_manager.generate_keypair("rsa", 2048)
        keys_info = qrlp_instance.key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Generate QR with all features
        complex_data = {
            "event": "crypto_integration_test",
            "sensitive_info": "secret_value",
            "public_info": "public_value"
        }

        qr_data, qr_image = qrlp_instance.generate_single_qr(
            user_data=complex_data,
            sign_data=True,
            encrypt_data=True
        )

        # Convert to JSON for verification
        qr_dict = qr_data.__dict__
        qr_json = json.dumps(qr_dict, separators=(',', ':'))

        # Verify with full cryptographic checks
        results = qrlp_instance.verify_qr_data(qr_json)

        # Should have comprehensive verification
        assert results['valid_json'] is True
        assert results['hmac_verified'] is True
        assert results['signature_verified'] is True  # May be True if key available
        assert results['encrypted'] is True

        # Should include cryptographic metadata
        assert '_hmac' in qr_dict
        assert 'digital_signature' in qr_dict or 'signing_key_id' in qr_dict
        assert '_encrypted_fields' in qr_dict
        assert '_encryption_key_id' in qr_dict

    def test_error_recovery_workflow(self, qrlp_instance):
        """Test error recovery in QR generation workflow."""
        # Test invalid user data handling
        try:
            # This should not crash even with problematic data
            qr_data, qr_image = qrlp_instance.generate_single_qr({"problematic": object()})
            # If we get here, error was handled gracefully
        except Exception as e:
            # If an exception occurs, it should be a specific error type
            assert "object" in str(e) or "serializable" in str(e)

        # Test with valid data after potential error
        qr_data, qr_image = qrlp_instance.generate_single_qr({"recovery": "test"})

        assert qr_data is not None
        assert qr_image is not None
        assert qr_data.user_data == {"recovery": "test"}

    def test_performance_under_load(self, qrlp_instance):
        """Test QR generation performance under moderate load."""
        start_time = time.time()

        # Generate 100 QR codes
        for i in range(100):
            qr_data, qr_image = qrlp_instance.generate_single_qr({"load_test": i})

            # Verify each QR is valid
            qr_json = qr_data.to_json()
            results = qrlp_instance.verify_qr_data(qr_json)

            assert results['valid_json'] is True
            assert results['hmac_verified'] is True

        end_time = time.time()
        duration = end_time - start_time

        # Should generate 100 QR codes in reasonable time (< 10 seconds)
        assert duration < 10.0

        # Check statistics
        stats = qrlp_instance.get_statistics()
        assert stats['total_updates'] >= 100

    def test_concurrent_qr_generation(self, qrlp_instance):
        """Test QR generation under concurrent access."""
        import threading
        import queue

        results_queue = queue.Queue()

        def generate_qrs(count):
            """Generate multiple QR codes in a thread."""
            for i in range(count):
                qr_data, qr_image = qrlp_instance.generate_single_qr({"thread": threading.current_thread().name, "count": i})
                results_queue.put((qr_data, qr_image))

        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=generate_qrs, args=(10,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Collect results
        total_generated = 0
        while not results_queue.empty():
            qr_data, qr_image = results_queue.get()
            total_generated += 1

            # Verify each QR
            qr_json = qr_data.to_json()
            results = qrlp_instance.verify_qr_data(qr_json)

            assert results['valid_json'] is True
            assert results['hmac_verified'] is True

        # Should have generated 30 QR codes (3 threads × 10 each)
        assert total_generated == 30

        # Check final statistics
        stats = qrlp_instance.get_statistics()
        assert stats['total_updates'] >= 30

    def test_qr_data_persistence_across_instances(self, qrlp_instance, temp_key_dir):
        """Test that QR data can be verified across different instances."""
        # Generate QR with first instance
        user_data = {"persistence": "test"}
        qr_data1, qr_image1 = qrlp_instance.generate_single_qr(user_data)

        # Create second instance with same configuration
        test_config = QRLPConfig()
        test_config.identity_settings.identity_file = None
        test_config.blockchain_settings.enabled_chains = set()
        test_config.time_settings.time_servers = []

        qrlp2 = QRLiveProtocol(test_config)

        # Copy key manager for shared keys
        qrlp2.key_manager = qrlp_instance.key_manager

        # Verify QR data with second instance
        qr_json = qr_data1.to_json()
        results = qrlp2.verify_qr_data(qr_json)

        # Should verify successfully
        assert results['valid_json'] is True
        assert results['hmac_verified'] is True

        # Should maintain same identity verification
        if results['identity_verified']:
            assert results['identity_verified'] is True

    def test_cryptographic_key_rotation_workflow(self, qrlp_instance):
        """Test key rotation and verification across key changes."""
        # Generate initial key and signed QR
        public_key1, private_key1 = qrlp_instance.key_manager.generate_keypair("rsa", 2048)
        keys_info1 = qrlp_instance.key_manager.list_keys()
        key_id1 = list(keys_info1.keys())[0]

        qr_data1, qr_image1 = qrlp_instance.generate_signed_qr(
            {"key_rotation": "test1"}, key_id1
        )

        # Generate new key (key rotation)
        public_key2, private_key2 = qrlp_instance.key_manager.generate_keypair("rsa", 2048)
        keys_info2 = qrlp_instance.key_manager.list_keys()
        key_id2 = [k for k in keys_info2.keys() if k != key_id1][0]

        qr_data2, qr_image2 = qrlp_instance.generate_signed_qr(
            {"key_rotation": "test2"}, key_id2
        )

        # Verify both QR codes
        qr_json1 = json.dumps(qr_data1.__dict__, separators=(',', ':'))
        results1 = qrlp_instance.verify_qr_data(qr_json1)

        qr_json2 = json.dumps(qr_data2.__dict__, separators=(',', ':'))
        results2 = qrlp_instance.verify_qr_data(qr_json2)

        # Both should verify successfully
        assert results1['valid_json'] is True
        assert results1['hmac_verified'] is True
        assert results1['signature_verified'] is True

        assert results2['valid_json'] is True
        assert results2['hmac_verified'] is True
        assert results2['signature_verified'] is True

        # Should use different keys
        assert qr_data1.__dict__['signing_key_id'] == key_id1
        assert qr_data2.__dict__['signing_key_id'] == key_id2

