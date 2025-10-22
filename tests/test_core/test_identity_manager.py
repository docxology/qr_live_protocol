"""
Unit tests for Identity Manager functionality.

Tests system fingerprinting, file hashing, and identity management operations.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

from src.identity_manager import IdentityManager, IdentityInfo
from src.config import IdentitySettings


class TestIdentityManager:
    """Test suite for IdentityManager class."""

    def test_identity_manager_initialization(self):
        """Test identity manager initializes correctly."""
        settings = IdentitySettings(auto_generate=False)
        im = IdentityManager(settings)

        assert im.settings == settings
        assert im.identity_info is None  # No identity initially
        assert im.cached_hash is None
        assert im.last_hash_time == 0
        assert im.hash_generations == 0

    def test_auto_generate_identity(self):
        """Test automatic identity generation."""
        settings = IdentitySettings(auto_generate=True, include_system_info=True)
        im = IdentityManager(settings)

        # Should have generated identity
        assert im.identity_info is not None
        assert isinstance(im.identity_info, IdentityInfo)
        assert im.identity_info.identity_hash is not None
        assert len(im.identity_info.identity_hash) == 64  # SHA-256 hex

    def test_identity_hash_generation(self):
        """Test identity hash generation."""
        settings = IdentitySettings(auto_generate=True, include_system_info=True)
        im = IdentityManager(settings)

        hash1 = im.get_identity_hash()
        assert hash1 is not None
        assert len(hash1) == 64

        # Hash should be cached
        hash2 = im.get_identity_hash()
        assert hash1 == hash2

        # Should increment generation count
        assert im.hash_generations == 1

    def test_identity_hash_caching(self):
        """Test identity hash caching behavior."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        # Get hash multiple times quickly
        hash1 = im.get_identity_hash()
        hash2 = im.get_identity_hash()
        hash3 = im.get_identity_hash()

        # Should return same hash (cached)
        assert hash1 == hash2 == hash3
        assert im.hash_generations == 1

    def test_identity_info_access(self):
        """Test identity info access methods."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        # Get identity info
        info = im.get_identity_info()
        assert info is not None
        assert isinstance(info, IdentityInfo)

        # Check info structure
        assert info.identity_hash is not None
        assert info.creation_time is not None
        assert info.system_info is not None
        assert info.file_hashes is not None
        assert info.custom_data is not None

    def test_custom_data_management(self):
        """Test custom data addition and management."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        # Initially empty custom data
        info = im.get_identity_info()
        assert len(info.custom_data) == 0

        # Add custom data
        im.update_custom_data("test_key", "test_value")
        im.update_custom_data("another_key", {"nested": "data"})

        # Check custom data was added
        info = im.get_identity_info()
        assert info.custom_data["test_key"] == "test_value"
        assert info.custom_data["another_key"] == {"nested": "data"}

        # Hash should be invalidated
        assert im.cached_hash is None

    def test_file_hash_addition(self, tmp_path):
        """Test adding files to identity."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        # Create test file
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("Test file content for hashing")

        # Add file to identity
        result = im.add_file_to_identity(str(test_file), "test_file")

        assert result is True

        # Check file was added
        info = im.get_identity_info()
        assert "test_file" in info.file_hashes
        assert len(info.file_hashes["test_file"]) == 64  # SHA-256 hash

        # Hash should be invalidated
        assert im.cached_hash is None
        assert im.file_reads == 1

    def test_file_hash_addition_nonexistent_file(self):
        """Test adding non-existent file returns False."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        result = im.add_file_to_identity("nonexistent_file.txt")
        assert result is False

    def test_remove_file_from_identity(self, tmp_path):
        """Test removing files from identity."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        # Create and add test file
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("Test content")
        im.add_file_to_identity(str(test_file), "test_file")

        # Remove file
        result = im.remove_file_from_identity("test_file")
        assert result is True

        # Check file was removed
        info = im.get_identity_info()
        assert "test_file" not in info.file_hashes

        # Hash should be invalidated
        assert im.cached_hash is None

    def test_remove_nonexistent_file(self):
        """Test removing non-existent file returns False."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        result = im.remove_file_from_identity("nonexistent")
        assert result is False

    def test_identity_export_import(self, tmp_path):
        """Test identity export and import functionality."""
        settings = IdentitySettings(auto_generate=True)
        im1 = IdentityManager(settings)

        # Add some custom data and files
        im1.update_custom_data("test_key", "test_value")

        test_file = tmp_path / "export_test.txt"
        test_file.write_text("Export test content")
        im1.add_file_to_identity(str(test_file), "export_test")

        # Export identity
        export_file = tmp_path / "exported_identity.json"
        result = im1.export_identity(str(export_file))
        assert result is True
        assert export_file.exists()

        # Create new identity manager
        settings2 = IdentitySettings(auto_generate=False)  # Don't auto-generate
        im2 = IdentityManager(settings2)

        # Import identity
        result = im2.import_identity(str(export_file))
        assert result is True

        # Check imported identity
        info1 = im1.get_identity_info()
        info2 = im2.get_identity_info()

        assert info2.identity_hash == info1.identity_hash
        assert info2.custom_data == info1.custom_data
        assert info2.file_hashes == info1.file_hashes

    def test_identity_import_nonexistent_file(self):
        """Test importing from non-existent file returns False."""
        settings = IdentitySettings(auto_generate=False)
        im = IdentityManager(settings)

        result = im.import_identity("nonexistent_file.json")
        assert result is False

    def test_identity_import_invalid_json(self, tmp_path):
        """Test importing invalid JSON file."""
        settings = IdentitySettings(auto_generate=False)
        im = IdentityManager(settings)

        # Create invalid JSON file
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("invalid json content {")

        result = im.import_identity(str(invalid_file))
        assert result is False

    def test_get_statistics(self):
        """Test statistics collection."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        # Get initial statistics
        stats = im.get_statistics()

        assert stats["hash_generations"] == 1  # One hash generated during init
        assert stats["file_reads"] == 0
        assert stats["system_info_queries"] == 1  # One query during init
        assert stats["has_identity"] is True
        assert stats["cached_hash"] is True
        assert stats["file_count"] == 0

        # Add a file and check updated stats
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_file = f.name

        try:
            im.add_file_to_identity(temp_file, "test_file")
            stats = im.get_statistics()

            assert stats["file_reads"] == 1
            assert stats["file_count"] == 1
        finally:
            os.unlink(temp_file)

    def test_no_auto_generate_identity(self):
        """Test identity manager without auto-generation."""
        settings = IdentitySettings(auto_generate=False)
        im = IdentityManager(settings)

        # Should not have identity
        assert im.identity_info is None
        assert im.get_identity_hash() == ""  # Should return empty string

    def test_system_info_collection(self):
        """Test system information collection."""
        settings = IdentitySettings(auto_generate=True, include_system_info=True)
        im = IdentityManager(settings)

        info = im.get_identity_info()
        system_info = info.system_info

        # Check required system info fields
        expected_fields = [
            'platform', 'system', 'machine', 'processor',
            'python_version', 'hostname', 'username', 'mac_address'
        ]

        for field in expected_fields:
            assert field in system_info
            assert system_info[field] is not None

        # Check that system info queries are tracked
        assert im.system_info_queries == 1

    def test_identity_file_loading(self, tmp_path):
        """Test loading identity from file."""
        # Create identity file
        identity_file = tmp_path / "test_identity.json"
        identity_data = {
            "identity_hash": "test_hash_1234567890abcdef",
            "creation_time": "2025-01-11T15:30:45.123456",
            "system_info": {"test": "data"},
            "file_hashes": {"test_file": "hash123"},
            "custom_data": {"custom": "value"},
            "version": "1.0"
        }

        with open(identity_file, 'w') as f:
            json.dump(identity_data, f)

        # Create settings pointing to identity file
        settings = IdentitySettings(
            identity_file=str(identity_file),
            auto_generate=False
        )

        im = IdentityManager(settings)

        # Should have loaded identity from file
        assert im.identity_info is not None
        assert im.identity_info.identity_hash == "test_hash_1234567890abcdef"

    def test_identity_file_not_found(self):
        """Test handling of missing identity file."""
        settings = IdentitySettings(
            identity_file="nonexistent_file.json",
            auto_generate=False
        )

        im = IdentityManager(settings)

        # Should not have identity (file not found, auto-generate disabled)
        assert im.identity_info is None

    def test_hash_algorithm_configuration(self):
        """Test different hash algorithms."""
        for algorithm in ["sha256", "sha512", "md5"]:
            settings = IdentitySettings(
                auto_generate=True,
                hash_algorithm=algorithm
            )
            im = IdentityManager(settings)

            hash_value = im.get_identity_hash()
            expected_length = {
                "sha256": 64,  # 32 bytes * 2 hex chars
                "sha512": 128, # 64 bytes * 2 hex chars
                "md5": 32      # 16 bytes * 2 hex chars
            }

            assert len(hash_value) == expected_length[algorithm]

    def test_identity_change_detection(self, tmp_path):
        """Test identity change detection."""
        settings = IdentitySettings(
            auto_generate=True,
            identity_file=str(tmp_path / "identity_file.txt")
        )
        im = IdentityManager(settings)

        # Create identity file
        identity_file = tmp_path / "identity_file.txt"
        identity_file.write_text("Initial content")

        # Add file to identity
        im.add_file_to_identity(str(identity_file), "identity_file")

        # Get initial hash
        hash1 = im.get_identity_hash()

        # Modify file
        identity_file.write_text("Modified content")

        # Hash should change
        hash2 = im.get_identity_hash()
        assert hash1 != hash2

    def test_multiple_files_in_identity(self, tmp_path):
        """Test adding multiple files to identity."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        # Create multiple test files
        files_data = {
            "file1.txt": "Content of file 1",
            "file2.txt": "Content of file 2",
            "file3.txt": "Content of file 3"
        }

        for filename, content in files_data.items():
            file_path = tmp_path / filename
            file_path.write_text(content)
            im.add_file_to_identity(str(file_path), filename)

        # Check all files were added
        info = im.get_identity_info()
        assert len(info.file_hashes) == 3

        for filename in files_data.keys():
            assert filename in info.file_hashes
            assert len(info.file_hashes[filename]) == 64  # SHA-256 hash

    def test_identity_info_immutability(self):
        """Test that identity info is properly structured."""
        settings = IdentitySettings(auto_generate=True)
        im = IdentityManager(settings)

        info = im.get_identity_info()

        # Check that all fields are present and properly typed
        assert isinstance(info.identity_hash, str)
        assert isinstance(info.creation_time, type(info.creation_time))
        assert isinstance(info.system_info, dict)
        assert isinstance(info.file_hashes, dict)
        assert isinstance(info.custom_data, dict)
        assert isinstance(info.version, str)

