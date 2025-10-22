"""
Unit tests for Key Manager cryptographic functionality.

Tests key generation, storage, encryption, and management operations.
"""

import pytest
import os
import json
from pathlib import Path

from src.crypto import KeyManager, KeyPair, KeyInfo
from src.crypto.exceptions import KeyError


class TestKeyManager:
    """Test suite for KeyManager class."""

    def test_key_manager_initialization(self, temp_key_dir):
        """Test key manager initializes correctly."""
        km = KeyManager(str(temp_key_dir))

        assert km.key_dir == temp_key_dir
        assert km.keys_file.exists()
        assert km._master_key is not None
        assert len(km._master_key) == 32  # AES-256 key

    def test_generate_rsa_keypair(self, key_manager):
        """Test RSA key pair generation."""
        public_key, private_key = key_manager.generate_keypair(
            algorithm="rsa",
            key_size=2048,
            purpose="test_rsa"
        )

        assert len(public_key) > 0
        assert len(private_key) > 0
        assert b"-----BEGIN PUBLIC KEY-----" in public_key
        assert b"-----BEGIN PRIVATE KEY-----" in private_key

        # Check metadata
        keys_info = key_manager.list_keys()
        assert len(keys_info) == 1

        key_id = list(keys_info.keys())[0]
        key_info = keys_info[key_id]

        assert key_info.algorithm == "rsa"
        assert key_info.key_size == 2048
        assert key_info.purpose == "test_rsa"
        assert key_info.usage_count == 0

    def test_generate_ecdsa_keypair(self, key_manager):
        """Test ECDSA key pair generation."""
        public_key, private_key = key_manager.generate_keypair(
            algorithm="ecdsa",
            key_size=256,
            purpose="test_ecdsa"
        )

        assert len(public_key) > 0
        assert len(private_key) > 0
        assert b"-----BEGIN PUBLIC KEY-----" in public_key
        assert b"-----BEGIN PRIVATE KEY-----" in private_key

        # Check metadata
        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]
        key_info = keys_info[key_id]

        assert key_info.algorithm == "ecdsa"
        assert key_info.key_size == 256
        assert key_info.purpose == "test_ecdsa"

    def test_invalid_algorithm_raises_error(self, key_manager):
        """Test that invalid algorithm raises appropriate error."""
        with pytest.raises(ValueError, match="Algorithm must be"):
            key_manager.generate_keypair(algorithm="invalid")

    def test_invalid_ecdsa_key_size_raises_error(self, key_manager):
        """Test that invalid ECDSA key size raises error."""
        with pytest.raises(ValueError, match="ECDSA key size must be"):
            key_manager.generate_keypair(algorithm="ecdsa", key_size=128)

    def test_get_keypair(self, key_manager):
        """Test retrieving key pairs."""
        # Generate a key first
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Retrieve the key pair
        retrieved_keypair = key_manager.get_keypair(key_id)

        assert retrieved_keypair is not None
        assert retrieved_keypair.key_id == key_id
        assert retrieved_keypair.algorithm == "rsa"
        assert retrieved_keypair.public_key == public_key

    def test_get_nonexistent_keypair(self, key_manager):
        """Test retrieving non-existent key pair returns None."""
        result = key_manager.get_keypair("nonexistent_key_id")
        assert result is None

    def test_list_keys(self, key_manager):
        """Test listing keys functionality."""
        # Initially empty
        keys = key_manager.list_keys()
        assert len(keys) == 0

        # Generate a key
        key_manager.generate_keypair("rsa", 2048)

        # Should have one key
        keys = key_manager.list_keys()
        assert len(keys) == 1

        key_id = list(keys.keys())[0]
        key_info = keys[key_id]

        assert isinstance(key_info, KeyInfo)
        assert key_info.algorithm == "rsa"
        assert key_info.key_size == 2048

    def test_delete_key(self, key_manager):
        """Test key deletion functionality."""
        # Generate a key
        key_manager.generate_keypair("rsa", 2048)
        keys_before = key_manager.list_keys()
        assert len(keys_before) == 1

        key_id = list(keys_before.keys())[0]

        # Delete the key
        result = key_manager.delete_key(key_id)
        assert result is True

        # Should be empty now
        keys_after = key_manager.list_keys()
        assert len(keys_after) == 0

    def test_delete_nonexistent_key(self, key_manager):
        """Test deleting non-existent key returns False."""
        result = key_manager.delete_key("nonexistent_key_id")
        assert result is False

    def test_export_public_key_pem(self, key_manager):
        """Test exporting public key in PEM format."""
        # Generate a key
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)
        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Export public key
        exported = key_manager.export_public_key(key_id, "pem")

        assert exported == public_key
        assert b"-----BEGIN PUBLIC KEY-----" in exported

    def test_export_public_key_der(self, key_manager):
        """Test exporting public key in DER format."""
        # Generate a key
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)
        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Export public key in DER format
        exported = key_manager.export_public_key(key_id, "der")

        assert exported is not None
        assert len(exported) > 0
        # DER format is binary, should not contain PEM headers
        assert b"-----BEGIN" not in exported

    def test_export_public_key_json(self, key_manager):
        """Test exporting public key in JSON format."""
        # Generate a key
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)
        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Export public key in JSON format
        exported = key_manager.export_public_key(key_id, "json")

        assert exported is not None
        exported_str = exported.decode('utf-8')

        # Should be valid JSON
        data = json.loads(exported_str)
        assert data["key_id"] == key_id
        assert data["algorithm"] == "rsa"
        assert "public_key" in data

    def test_export_nonexistent_key(self, key_manager):
        """Test exporting non-existent key returns None."""
        result = key_manager.export_public_key("nonexistent_key_id")
        assert result is None

    def test_backup_keys(self, key_manager, temp_key_dir):
        """Test key backup functionality."""
        # Generate a key
        key_manager.generate_keypair("rsa", 2048)

        # Create backup directory
        backup_dir = temp_key_dir / "backup"
        backup_dir.mkdir()

        # Perform backup
        result = key_manager.backup_keys(str(backup_dir))

        assert result is True

        # Check backup file exists
        backup_file = backup_dir / "keys_backup.json"
        assert backup_file.exists()

        # Check backup content
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)

        assert "backup_created" in backup_data
        assert "keys" in backup_data
        assert len(backup_data["keys"]) == 1

    def test_key_metadata_persistence(self, temp_key_dir):
        """Test that key metadata persists across instances."""
        # Create first key manager instance
        km1 = KeyManager(str(temp_key_dir))
        km1.generate_keypair("rsa", 2048, "persistence_test")

        keys_info_1 = km1.list_keys()
        assert len(keys_info_1) == 1

        key_id = list(keys_info_1.keys())[0]
        original_info = keys_info_1[key_id]

        # Create second key manager instance
        km2 = KeyManager(str(temp_key_dir))
        keys_info_2 = km2.list_keys()

        # Should have the same key
        assert len(keys_info_2) == 1
        assert key_id in keys_info_2

        restored_info = keys_info_2[key_id]

        # Metadata should be preserved
        assert restored_info.algorithm == original_info.algorithm
        assert restored_info.key_size == original_info.key_size
        assert restored_info.purpose == original_info.purpose

    def test_key_usage_tracking(self, key_manager):
        """Test that key usage is tracked correctly."""
        # Generate a key
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]
        key_info = keys_info[key_id]

        # Initial usage count should be 0
        assert key_info.usage_count == 0
        assert key_info.last_used is None

        # Get the key pair (this increments usage)
        keypair = key_manager.get_keypair(key_id)

        # Usage should be tracked
        key_info = key_manager.list_keys()[key_id]
        assert key_info.usage_count == 1
        assert key_info.last_used is not None

    def test_multiple_key_generation(self, key_manager):
        """Test generating multiple keys."""
        # Generate multiple keys
        key1_id = None
        key2_id = None

        # Generate first key
        public1, private1 = key_manager.generate_keypair("rsa", 2048, "key1")
        keys_info = key_manager.list_keys()
        assert len(keys_info) == 1
        key1_id = list(keys_info.keys())[0]

        # Generate second key
        public2, private2 = key_manager.generate_keypair("ecdsa", 256, "key2")
        keys_info = key_manager.list_keys()
        assert len(keys_info) == 2
        key2_id = [k for k in keys_info.keys() if k != key1_id][0]

        # Verify both keys exist and have correct properties
        key1_info = keys_info[key1_id]
        key2_info = keys_info[key2_id]

        assert key1_info.algorithm == "rsa"
        assert key1_info.key_size == 2048
        assert key1_info.purpose == "key1"

        assert key2_info.algorithm == "ecdsa"
        assert key2_info.key_size == 256
        assert key2_info.purpose == "key2"

        # Verify key retrieval
        keypair1 = key_manager.get_keypair(key1_id)
        keypair2 = key_manager.get_keypair(key2_id)

        assert keypair1 is not None
        assert keypair2 is not None
        assert keypair1.algorithm == "rsa"
        assert keypair2.algorithm == "ecdsa"

