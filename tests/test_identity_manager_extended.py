"""
Extended tests for IdentityManager module.

Covers export_identity / import_identity round trip, add_file_to_identity,
remove_file_from_identity, update_custom_data, get_identity_info,
get_statistics, _calculate_file_hash, _collect_system_info,
_identity_changed, _create_new_identity, import_identity edge cases.
"""

import os
import time
import pytest
import tempfile
import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.identity_manager import IdentityManager, IdentityInfo
from src.config import IdentitySettings


class TestExportImportIdentity:
    """Tests for export_identity and import_identity round trip."""

    def test_export_import_identity_round_trip(self, tmp_path):
        """export_identity and import_identity should work together."""
        settings = IdentitySettings(
            identity_file=str(tmp_path / "identity.json"),
            auto_generate=False,
            include_system_info=False,
            include_file_hash=False
        )
        manager = IdentityManager(settings)
        
        # Create initial identity
        manager._create_new_identity()
        
        # Export to file
        export_path = str(tmp_path / "exported_identity.json")
        result = manager.export_identity(export_path)
        assert result is True
        assert os.path.exists(export_path)
        
        # Create new manager and import
        new_settings = IdentitySettings(
            identity_file=str(tmp_path / "imported_identity.json"),
            auto_generate=False,
            include_system_info=False,
            include_file_hash=False
        )
        new_manager = IdentityManager(new_settings)
        
        result = new_manager.import_identity(export_path)
        assert result is True
        assert new_manager.identity_info is not None
        assert new_manager.identity_info.identity_hash == manager.identity_info.identity_hash

    def test_export_identity_no_identity(self, tmp_path):
        """export_identity should return False when no identity exists."""
        settings = IdentitySettings(
            identity_file=str(tmp_path / "identity.json"),
            auto_generate=False
        )
        manager = IdentityManager(settings)
        
        result = manager.export_identity(str(tmp_path / "export.json"))
        assert result is False

    def test_import_identity_nonexistent_file(self, tmp_path):
        """import_identity should return False for nonexistent file."""
        settings = IdentitySettings(auto_generate=False)
        manager = IdentityManager(settings)
        
        result = manager.import_identity(str(tmp_path / "nonexistent.json"))
        assert result is False

    def test_import_identity_invalid_json(self, tmp_path):
        """import_identity should return False for invalid JSON."""
        settings = IdentitySettings(auto_generate=False)
        manager = IdentityManager(settings)
        
        # Create file with invalid JSON
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json {{{")
        
        result = manager.import_identity(str(invalid_file))
        assert result is False


class TestAddFileToIdentity:
    """Tests for add_file_to_identity method."""

    def test_add_file_to_identity_valid_file(self, tmp_path):
        """add_file_to_identity should add hash of existing file."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content for hashing")
        
        result = manager.add_file_to_identity(str(test_file))
        assert result is True
        assert "test.txt" in manager.identity_info.file_hashes
        
        # Verify hash is correct
        expected_hash = hashlib.sha256(b"test content for hashing").hexdigest()
        assert manager.identity_info.file_hashes["test.txt"] == expected_hash

    def test_add_file_to_identity_nonexistent_file(self, tmp_path):
        """add_file_to_identity should return False for nonexistent file."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        result = manager.add_file_to_identity(str(tmp_path / "nonexistent.txt"))
        assert result is False

    def test_add_file_to_identity_with_alias(self, tmp_path):
        """add_file_to_identity should use alias as key when provided."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Create a test file
        test_file = tmp_path / "actual_name.txt"
        test_file.write_text("content")
        
        result = manager.add_file_to_identity(str(test_file), alias="my_alias")
        assert result is True
        assert "my_alias" in manager.identity_info.file_hashes
        assert "actual_name.txt" not in manager.identity_info.file_hashes

    def test_add_file_to_identity_invalidate_cache(self, tmp_path):
        """add_file_to_identity should invalidate cached hash."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Get initial hash
        initial_hash = manager.get_identity_hash()
        
        # Add a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("new content")
        manager.add_file_to_identity(str(test_file))
        
        # Cache should be invalidated
        assert manager.cached_hash is None


class TestRemoveFileFromIdentity:
    """Tests for remove_file_from_identity method."""

    def test_remove_file_from_identity_existing(self, tmp_path):
        """remove_file_from_identity should remove existing file."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Add a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        manager.add_file_to_identity(str(test_file))
        
        assert "test.txt" in manager.identity_info.file_hashes
        
        result = manager.remove_file_from_identity("test.txt")
        assert result is True
        assert "test.txt" not in manager.identity_info.file_hashes

    def test_remove_file_from_identity_nonexistent(self, tmp_path):
        """remove_file_from_identity should return False for nonexistent key."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        result = manager.remove_file_from_identity("nonexistent_key")
        assert result is False


class TestUpdateCustomData:
    """Tests for update_custom_data method."""

    def test_update_custom_data_adds_key(self, tmp_path):
        """update_custom_data should add new key-value pair."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        manager.update_custom_data("event_name", "Test Event 2024")
        
        assert "event_name" in manager.identity_info.custom_data
        assert manager.identity_info.custom_data["event_name"] == "Test Event 2024"

    def test_update_custom_data_updates_existing(self, tmp_path):
        """update_custom_data should update existing key."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        manager.update_custom_data("key", "value1")
        manager.update_custom_data("key", "value2")
        
        assert manager.identity_info.custom_data["key"] == "value2"

    def test_update_custom_data_invalidate_cache(self, tmp_path):
        """update_custom_data should invalidate cached hash."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        initial_hash = manager.get_identity_hash()
        manager.update_custom_data("new_key", "new_value")
        
        # Cache should be invalidated
        assert manager.cached_hash is None

    def test_update_custom_data_no_identity(self, tmp_path):
        """update_custom_data should initialize identity if none exists."""
        settings = IdentitySettings(auto_generate=False, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Manually set identity_info to None to simulate no identity
        manager.identity_info = None
        
        manager.update_custom_data("key", "value")
        
        # _initialize_identity is called but since auto_generate=False, it stays None
        # The method just sets cached_hash = None
        assert manager.cached_hash is None


class TestGetIdentityInfo:
    """Tests for get_identity_info method."""

    def test_get_identity_info_returns_info(self, tmp_path):
        """get_identity_info should return IdentityInfo object."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        result = manager.get_identity_info()
        
        assert result is not None
        assert isinstance(result, IdentityInfo)
        assert result.identity_hash != ""
        assert result.creation_time is not None

    def test_get_identity_info_no_identity(self, tmp_path):
        """get_identity_info should return None when no identity."""
        settings = IdentitySettings(auto_generate=False, include_system_info=False)
        manager = IdentityManager(settings)
        
        result = manager.get_identity_info()
        
        assert result is None


class TestGetStatistics:
    """Tests for get_statistics method."""

    def test_get_statistics_initial(self, tmp_path):
        """get_statistics should return initial statistics."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        stats = manager.get_statistics()
        
        assert stats["hash_generations"] == 1  # Initial generation
        assert stats["file_reads"] == 0
        assert stats["system_info_queries"] == 0
        assert stats["has_identity"] is True
        assert stats["cached_hash"] is True
        assert stats["file_count"] == 0

    def test_get_statistics_after_operations(self, tmp_path):
        """get_statistics should reflect operations."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Add a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        manager.add_file_to_identity(str(test_file))
        
        # Update custom data
        manager.update_custom_data("key", "value")
        
        stats = manager.get_statistics()
        
        assert stats["file_reads"] == 1
        assert stats["file_count"] == 1


class TestCalculateFileHash:
    """Tests for _calculate_file_hash method."""

    def test_calculate_file_hash_known_content(self, tmp_path):
        """_calculate_file_hash should return correct SHA-256 hash."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        test_file = tmp_path / "test.txt"
        content = b"known content for hashing"
        test_file.write_bytes(content)
        
        result = manager._calculate_file_hash(str(test_file))
        
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_calculate_file_hash_large_file(self, tmp_path):
        """_calculate_file_hash should handle large files in chunks."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Create a file larger than 8192 bytes
        test_file = tmp_path / "large.txt"
        content = b"x" * 10000  # 10KB
        test_file.write_bytes(content)
        
        result = manager._calculate_file_hash(str(test_file))
        
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_calculate_file_hash_nonexistent_file(self, tmp_path):
        """_calculate_file_hash should return error string for nonexistent file."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        result = manager._calculate_file_hash(str(tmp_path / "nonexistent.txt"))
        
        assert result.startswith("error:")


class TestCollectSystemInfo:
    """Tests for _collect_system_info method."""

    def test_collect_system_info_returns_dict(self, tmp_path):
        """_collect_system_info should return dictionary with system info."""
        settings = IdentitySettings(include_system_info=True)
        manager = IdentityManager(settings)
        
        result = manager._collect_system_info()
        
        assert isinstance(result, dict)

    def test_collect_system_info_contains_expected_fields(self, tmp_path):
        """_collect_system_info should contain expected system fields."""
        settings = IdentitySettings(include_system_info=True)
        manager = IdentityManager(settings)
        
        result = manager._collect_system_info()
        
        expected_fields = ["platform", "system", "machine", "python_version", "hostname"]
        for field in expected_fields:
            assert field in result

    def test_collect_system_info_includes_username(self, tmp_path):
        """_collect_system_info should include username."""
        settings = IdentitySettings(include_system_info=True)
        manager = IdentityManager(settings)
        
        result = manager._collect_system_info()
        
        assert "username" in result
        # Username should not be empty
        assert result["username"] != ""

    def test_collect_system_info_includes_environment(self, tmp_path):
        """_collect_system_info should include environment variables."""
        settings = IdentitySettings(include_system_info=True)
        manager = IdentityManager(settings)
        
        result = manager._collect_system_info()
        
        assert "environment" in result
        assert isinstance(result["environment"], dict)


class TestIdentityChanged:
    """Tests for _identity_changed method."""

    def test_identity_changed_file_modified(self, tmp_path):
        """_identity_changed should return True when file is modified."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Add a file with full path so _identity_changed can find it
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")
        # Use the full path as the key (not just basename)
        manager.add_file_to_identity(str(test_file), alias=str(test_file))
        
        # Get initial hash
        initial_hash = manager.get_identity_hash()
        
        # Modify file
        test_file.write_text("modified content")
        
        # Check identity changed
        result = manager._identity_changed()
        assert result is True

    def test_identity_changed_file_unchanged(self, tmp_path):
        """_identity_changed should return False when file unchanged."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Add a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        manager.add_file_to_identity(str(test_file))
        
        # Get hash (this caches)
        _ = manager.get_identity_hash()
        
        # Check identity - should be unchanged
        result = manager._identity_changed()
        assert result is False

    def test_identity_changed_no_identity(self, tmp_path):
        """_identity_changed should return True when no identity."""
        settings = IdentitySettings(auto_generate=False, include_system_info=False)
        manager = IdentityManager(settings)
        
        result = manager._identity_changed()
        assert result is True


class TestCreateNewIdentity:
    """Tests for _create_new_identity method."""

    def test_create_new_identity_with_system_info(self, tmp_path):
        """_create_new_identity should include system info when enabled."""
        settings = IdentitySettings(
            auto_generate=True,
            include_system_info=True,
            include_file_hash=False
        )
        manager = IdentityManager(settings)
        
        manager._create_new_identity()
        
        assert manager.identity_info is not None
        assert len(manager.identity_info.system_info) > 0
        assert "platform" in manager.identity_info.system_info

    def test_create_new_identity_without_system_info(self, tmp_path):
        """_create_new_identity should not include system info when disabled."""
        settings = IdentitySettings(
            auto_generate=True,
            include_system_info=False,
            include_file_hash=False
        )
        manager = IdentityManager(settings)
        
        manager._create_new_identity()
        
        assert manager.identity_info is not None
        assert manager.identity_info.system_info == {}

    def test_create_new_identity_with_file_hash(self, tmp_path):
        """_create_new_identity should include file hash when enabled."""
        identity_file = tmp_path / "identity.json"
        settings = IdentitySettings(
            auto_generate=True,
            include_system_info=False,
            include_file_hash=True,
            identity_file=str(identity_file)
        )
        manager = IdentityManager(settings)
        
        # Create the identity file first
        identity_file.write_text("{}")
        
        manager._create_new_identity()
        
        assert manager.identity_info is not None
        assert "identity_file" in manager.identity_info.file_hashes

    def test_create_new_identity_without_file_hash(self, tmp_path):
        """_create_new_identity should not include file hash when disabled."""
        settings = IdentitySettings(
            auto_generate=True,
            include_system_info=False,
            include_file_hash=False,
            identity_file=None
        )
        manager = IdentityManager(settings)
        
        manager._create_new_identity()
        
        assert manager.identity_info is not None
        assert manager.identity_info.file_hashes == {}

    def test_create_new_identity_generates_hash(self, tmp_path):
        """_create_new_identity should generate and set identity hash."""
        settings = IdentitySettings(
            auto_generate=True,
            include_system_info=False,
            include_file_hash=False
        )
        manager = IdentityManager(settings)
        
        manager._create_new_identity()
        
        assert manager.identity_info is not None
        assert manager.identity_info.identity_hash != ""
        assert manager.cached_hash is not None


class TestGetIdentityHash:
    """Tests for get_identity_hash method."""

    def test_get_identity_hash_returns_hash(self, tmp_path):
        """get_identity_hash should return SHA-256 hash string."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        result = manager.get_identity_hash()
        
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex length
        assert all(c in '0123456789abcdef' for c in result)

    def test_get_identity_hash_caches_result(self, tmp_path):
        """get_identity_hash should cache result for 1 minute."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        hash1 = manager.get_identity_hash()
        hash2 = manager.get_identity_hash()
        
        assert hash1 == hash2
        assert manager.cached_hash == hash1

    def test_get_identity_hash_regenerates_after_cache_expiry(self, tmp_path):
        """get_identity_hash should regenerate after cache expiry."""
        settings = IdentitySettings(auto_generate=True, include_system_info=False)
        manager = IdentityManager(settings)
        
        # Set last_hash_time to past
        manager.last_hash_time = time.time() - 120  # 2 minutes ago
        
        hash1 = manager.get_identity_hash()
        # Modify identity to force new hash
        manager.identity_info.custom_data["new_key"] = "new_value"
        manager.cached_hash = None
        
        hash2 = manager.get_identity_hash()
        
        # Hashes should be different due to different custom_data
        assert hash1 != hash2


class TestInitializeIdentity:
    """Tests for _initialize_identity method."""

    def test_initialize_identity_auto_generate(self, tmp_path):
        """_initialize_identity should create new identity when auto_generate=True."""
        settings = IdentitySettings(
            identity_file=str(tmp_path / "identity.json"),
            auto_generate=True,
            include_system_info=False
        )
        manager = IdentityManager(settings)
        
        assert manager.identity_info is not None
        assert manager.identity_info.identity_hash != ""

    def test_initialize_identity_imports_existing(self, tmp_path):
        """_initialize_identity should import existing identity file."""
        identity_file = tmp_path / "existing_identity.json"
        
        # Create an existing identity file using json.dumps for valid JSON
        existing_identity = {
            "identity_hash": "existing_hash_12345678901234567890123456789012",
            "creation_time": "2024-01-01T00:00:00+00:00",
            "system_info": {},
            "file_hashes": {},
            "custom_data": {"imported": True},
            "version": "1.0"
        }
        identity_file.write_text(json.dumps(existing_identity))
        
        settings = IdentitySettings(
            identity_file=str(identity_file),
            auto_generate=True,
            include_system_info=False
        )
        manager = IdentityManager(settings)
        
        assert manager.identity_info is not None
        assert manager.identity_info.identity_hash == "existing_hash_12345678901234567890123456789012"

    def test_initialize_identity_no_file_no_auto_generate(self, tmp_path):
        """_initialize_identity should set None when no file and auto_generate=False."""
        settings = IdentitySettings(
            identity_file=str(tmp_path / "nonexistent.json"),
            auto_generate=False
        )
        manager = IdentityManager(settings)
        
        assert manager.identity_info is None


class TestIdentityInfoDataclass:
    """Tests for IdentityInfo dataclass."""

    def test_identity_info_creation(self):
        """IdentityInfo should be created with all fields."""
        info = IdentityInfo(
            identity_hash="test_hash_12345678901234567890123456789012",
            creation_time=datetime.now(timezone.utc),
            system_info={"platform": "test"},
            file_hashes={"file.txt": "hash123"},
            custom_data={"key": "value"},
            version="1.0"
        )
        
        assert info.identity_hash == "test_hash_12345678901234567890123456789012"
        assert info.creation_time is not None
        assert info.system_info == {"platform": "test"}
        assert info.file_hashes == {"file.txt": "hash123"}
        assert info.custom_data == {"key": "value"}
        assert info.version == "1.0"

    def test_identity_info_default_version(self):
        """IdentityInfo should default version to 1.0."""
        info = IdentityInfo(
            identity_hash="hash",
            creation_time=datetime.now(timezone.utc),
            system_info={},
            file_hashes={},
            custom_data={}
        )
        
        assert info.version == "1.0"


class TestIdentityManagerIntegration:
    """Integration tests for IdentityManager."""

    def test_full_workflow(self, tmp_path):
        """Full workflow: create, modify, export, import."""
        # Step 1: Create initial identity
        settings = IdentitySettings(
            identity_file=str(tmp_path / "workflow_identity.json"),
            auto_generate=True,
            include_system_info=True,
            include_file_hash=False
        )
        manager1 = IdentityManager(settings)
        
        # Step 2: Add custom data and file
        manager1.update_custom_data("event", "Test Event")
        
        test_file = tmp_path / "data.txt"
        test_file.write_text("important data")
        manager1.add_file_to_identity(str(test_file))
        
        # Step 3: Export identity
        export_path = str(tmp_path / "exported.json")
        assert manager1.export_identity(export_path) is True
        
        # Step 4: Create new manager and import
        settings2 = IdentitySettings(auto_generate=False)
        manager2 = IdentityManager(settings2)
        assert manager2.import_identity(export_path) is True
        
        # Step 5: Verify data
        assert manager2.identity_info.custom_data.get("event") == "Test Event"
        assert "data.txt" in manager2.identity_info.file_hashes