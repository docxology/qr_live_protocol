"""
Extended tests for trust.py TrustStore and TrustedPublicKey.

Covers file I/O, edge cases, and all public methods.
"""

import json
import pytest
import tempfile
from pathlib import Path

from src.trust import TrustStore, TrustedPublicKey


class TestTrustedPublicKey:
    """Test TrustedPublicKey dataclass."""

    def test_default_algorithm(self):
        """TrustedPublicKey defaults to rsa."""
        key = TrustedPublicKey(
            issuer_id="issuer1",
            key_id="key1",
            public_key_pem=b"-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
        )
        assert key.algorithm == "rsa"

    def test_custom_algorithm(self):
        """TrustedPublicKey accepts custom algorithm."""
        key = TrustedPublicKey(
            issuer_id="issuer1",
            key_id="key1",
            public_key_pem=b"fake-key",
            algorithm="ecdsa",
        )
        assert key.algorithm == "ecdsa"

    def test_frozen(self):
        """TrustedPublicKey is frozen and immutable."""
        key = TrustedPublicKey(
            issuer_id="issuer1",
            key_id="key1",
            public_key_pem=b"fake",
        )
        with pytest.raises(Exception):
            key.issuer_id = "changed"


class TestTrustStoreAdd:
    """Test TrustStore add operations."""

    def test_add_public_key_bytes(self):
        """add_public_key accepts bytes."""
        store = TrustStore()
        result = store.add_public_key("issuer1", "key1", b"fake-pem-bytes")
        assert result.issuer_id == "issuer1"
        assert result.key_id == "key1"
        assert result.public_key_pem == b"fake-pem-bytes"

    def test_add_public_key_str(self):
        """add_public_key accepts str and converts to bytes."""
        store = TrustStore()
        result = store.add_public_key("issuer1", "key1", "fake-pem-str")
        assert result.public_key_pem == b"fake-pem-str"

    def test_add_public_key_normalizes_algorithm(self):
        """add_public_key lowercases algorithm."""
        store = TrustStore()
        result = store.add_public_key("i", "k", b"pem", algorithm="RSA")
        assert result.algorithm == "rsa"

    def test_add_public_key_overwrites(self):
        """Adding same issuer/key-id overwrites previous."""
        store = TrustStore()
        store.add_public_key("issuer1", "key1", b"old-pem")
        store.add_public_key("issuer1", "key1", b"new-pem")
        key = store.get_public_key("issuer1", "key1")
        assert key.public_key_pem == b"new-pem"

    def test_add_multiple_keys(self):
        """Multiple issuer/key-id pairs coexist."""
        store = TrustStore()
        store.add_public_key("issuer1", "key1", b"pem1")
        store.add_public_key("issuer1", "key2", b"pem2")
        store.add_public_key("issuer2", "key1", b"pem3")
        assert len(store) == 3

    def test_add_public_key_file(self, tmp_path):
        """add_public_key_file reads PEM from file."""
        pem_file = tmp_path / "pub.pem"
        pem_file.write_bytes(b"-----BEGIN PUBLIC KEY-----\nfile-content\n-----END PUBLIC KEY-----")
        store = TrustStore()
        result = store.add_public_key_file("issuer1", "key1", pem_file)
        assert result.public_key_pem == b"-----BEGIN PUBLIC KEY-----\nfile-content\n-----END PUBLIC KEY-----"

    def test_add_public_key_file_with_str_path(self, tmp_path):
        """add_public_key_file accepts string path."""
        pem_file = tmp_path / "pub.pem"
        pem_file.write_bytes(b"pem-content")
        store = TrustStore()
        store.add_public_key_file("issuer1", "key1", str(pem_file))
        assert len(store) == 1


class TestTrustStoreQuery:
    """Test TrustStore query operations."""

    def test_get_public_key_existing(self):
        """get_public_key returns TrustedPublicKey."""
        store = TrustStore()
        store.add_public_key("issuer1", "key1", b"pem")
        key = store.get_public_key("issuer1", "key1")
        assert key is not None
        assert key.issuer_id == "issuer1"

    def test_get_public_key_missing(self):
        """get_public_key returns None for missing."""
        store = TrustStore()
        assert store.get_public_key("issuer1", "key1") is None

    def test_get_public_key_none_args(self):
        """get_public_key returns None when issuer_id or key_id is None."""
        store = TrustStore()
        store.add_public_key("issuer1", "key1", b"pem")
        assert store.get_public_key(None, "key1") is None
        assert store.get_public_key("issuer1", None) is None
        assert store.get_public_key(None, None) is None

    def test_is_trusted_true(self):
        """is_trusted returns True for trusted key."""
        store = TrustStore()
        store.add_public_key("issuer1", "key1", b"pem")
        assert store.is_trusted("issuer1", "key1") is True

    def test_is_trusted_false(self):
        """is_trusted returns False for untrusted key."""
        store = TrustStore()
        assert store.is_trusted("issuer1", "key1") is False

    def test_list_public_keys_sorted(self):
        """list_public_keys returns sorted list."""
        store = TrustStore()
        store.add_public_key("issuer_b", "key_z", b"pem")
        store.add_public_key("issuer_a", "key_a", b"pem")
        store.add_public_key("issuer_a", "key_b", b"pem")
        keys = store.list_public_keys()
        assert len(keys) == 3
        # Sorted by lookup_key "issuer:key_id"
        assert keys[0].issuer_id == "issuer_a"
        assert keys[0].key_id == "key_a"
        assert keys[1].issuer_id == "issuer_a"
        assert keys[1].key_id == "key_b"
        assert keys[2].issuer_id == "issuer_b"

    def test_len(self):
        """__len__ returns number of trusted keys."""
        store = TrustStore()
        assert len(store) == 0
        store.add_public_key("i1", "k1", b"pem")
        assert len(store) == 1
        store.add_public_key("i2", "k2", b"pem")
        assert len(store) == 2


class TestTrustStoreSerialization:
    """Test TrustStore serialization."""

    def test_to_dict_empty(self):
        """to_dict on empty store returns empty list."""
        store = TrustStore()
        data = store.to_dict()
        assert data == {"trusted_keys": []}

    def test_to_dict_with_keys(self):
        """to_dict serializes trusted keys."""
        store = TrustStore()
        store.add_public_key("issuer1", "key1", b"pem-data", "ecdsa")
        data = store.to_dict()
        assert len(data["trusted_keys"]) == 1
        entry = data["trusted_keys"][0]
        assert entry["issuer_id"] == "issuer1"
        assert entry["key_id"] == "key1"
        assert entry["algorithm"] == "ecdsa"
        assert entry["public_key_pem"] == "pem-data"

    def test_from_dict_empty(self):
        """from_dict on empty data creates empty store."""
        store = TrustStore.from_dict({"trusted_keys": []})
        assert len(store) == 0

    def test_from_dict_with_keys(self):
        """from_dict creates store from dict."""
        data = {
            "trusted_keys": [
                {
                    "issuer_id": "issuer1",
                    "key_id": "key1",
                    "algorithm": "rsa",
                    "public_key_pem": "pem-content",
                }
            ]
        }
        store = TrustStore.from_dict(data)
        assert len(store) == 1
        key = store.get_public_key("issuer1", "key1")
        assert key.public_key_pem == b"pem-content"

    def test_from_dict_missing_algorithm_defaults_rsa(self):
        """from_dict defaults algorithm to rsa when missing."""
        data = {
            "trusted_keys": [
                {
                    "issuer_id": "issuer1",
                    "key_id": "key1",
                    "public_key_pem": "pem-content",
                }
            ]
        }
        store = TrustStore.from_dict(data)
        key = store.get_public_key("issuer1", "key1")
        assert key.algorithm == "rsa"

    def test_round_trip_file(self, tmp_path):
        """to_file -> from_file round trip preserves data."""
        store = TrustStore()
        store.add_public_key("issuer1", "key1", b"pem1", "rsa")
        store.add_public_key("issuer2", "key2", b"pem2", "ecdsa")

        trust_file = tmp_path / "trust.json"
        store.to_file(trust_file)

        # Verify file is valid JSON
        data = json.loads(trust_file.read_text())
        assert len(data["trusted_keys"]) == 2

        # Load back
        loaded = TrustStore.from_file(trust_file)
        assert len(loaded) == 2
        assert loaded.get_public_key("issuer1", "key1").public_key_pem == b"pem1"
        assert loaded.get_public_key("issuer2", "key2").algorithm == "ecdsa"

    def test_from_file_nonexistent(self):
        """from_file raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            TrustStore.from_file("/nonexistent/path/trust.json")

    def test_from_file_invalid_json(self, tmp_path):
        """from_file raises error for invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")
        with pytest.raises(json.JSONDecodeError):
            TrustStore.from_file(bad_file)

    def test_from_file_non_object_json(self, tmp_path):
        """from_file raises ValueError for non-object JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("[1, 2, 3]")
        with pytest.raises(ValueError, match="must be a JSON object"):
            TrustStore.from_file(bad_file)
