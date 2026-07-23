"""
Tests for v1.4.0 features: QRSerializer, keys rotate, batch verify,
expiry callback, WebSocket validation, fuzz tests.
"""

import json
import time
import pytest
import random
import string
from click.testing import CliRunner
from datetime import datetime, timezone, timedelta

from src.cli import cli
from src.config import QRLPConfig
from src.core import QRLiveProtocol, QRData
from src.serializer import QRSerializer


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def config_file(tmp_path):
    config = {
        "update_interval": 0.1,
        "blockchain_settings": {"enabled_chains": []},
        "time_settings": {"time_servers": []},
    }
    path = tmp_path / "test_config.json"
    path.write_text(json.dumps(config))
    return str(path)


class TestQRSerializer:
    """Test QRSerializer centralized serialization."""

    def test_serialize_basic(self):
        result = QRSerializer.serialize({"key": "value"})
        assert result == '{"key":"value"}'

    def test_serialize_filter_none(self):
        result = QRSerializer.serialize({"a": 1, "b": None})
        assert "a" in result
        assert "b" not in result

    def test_serialize_no_filter_none(self):
        result = QRSerializer.serialize({"a": 1, "b": None}, filter_none=False)
        assert "b" in result

    def test_serialize_sort_keys(self):
        result = QRSerializer.serialize({"b": 1, "a": 2}, sort_keys=True)
        assert result.index("a") < result.index("b")

    def test_serialize_for_signature(self):
        result = QRSerializer.serialize_for_signature({"b": 1, "a": 2, "c": None})
        assert result.index("a") < result.index("b")
        assert "c" not in result

    def test_deserialize(self):
        result = QRSerializer.deserialize('{"key":"value"}')
        assert result == {"key": "value"}

    def test_serialize_to_dict_from_object(self):
        class FakeObj:
            def __init__(self):
                self.a = 1
                self.b = None
        result = QRSerializer.serialize_to_dict(FakeObj())
        assert result == {"a": 1}

    def test_serialize_to_dict_from_dict(self):
        result = QRSerializer.serialize_to_dict({"a": 1, "b": None})
        assert result == {"a": 1}

    def test_exported_from_src(self):
        from src import QRSerializer as SrcQS
        assert SrcQS is QRSerializer

    def test_consistency_with_qrdata_to_json(self):
        """QRSerializer should produce same output as QRData.to_json for same data."""
        qr = QRData(
            timestamp="2025-01-01T00:00:00Z",
            identity_hash="abc",
            blockchain_hashes={},
            time_server_verification={},
            sequence_number=1,
        )
        qr_json = qr.to_json()
        serializer_json = QRSerializer.serialize(qr.to_dict())
        assert qr_json == serializer_json


class TestCLIKeysRotate:
    """Test qrlp keys rotate command."""

    def test_keys_rotate(self, runner, config_file, tmp_path):
        # First generate a key
        result = runner.invoke(cli, ['--config', config_file, 'keys', 'generate'])
        assert result.exit_code == 0
        key_id = result.output.split("Generated key: ")[1].strip()

        # Rotate it
        pub_key = str(tmp_path / "new_pub.pem")
        result = runner.invoke(cli, [
            '--config', config_file,
            'keys', 'rotate', key_id,
            '--public-key-output', pub_key,
        ])
        assert result.exit_code == 0
        assert "New key generated" in result.output
        assert "Old key deleted" in result.output
        assert f"{key_id}" in result.output

    def test_keys_rotate_nonexistent(self, runner, config_file):
        result = runner.invoke(cli, [
            '--config', config_file,
            'keys', 'rotate', 'nonexistent-key-id',
        ])
        assert result.exit_code != 0
        assert "Key not found" in result.output


class TestBatchVerify:
    """Test qrlp verify --batch."""

    def test_batch_verify(self, runner, config_file, tmp_path):
        # Generate several QR codes
        qrlp_config = QRLPConfig.from_file(config_file)
        qrlp = QRLiveProtocol(qrlp_config)

        payloads = []
        for i in range(3):
            qr_data, _ = qrlp.generate_single_qr(sign_data=True, user_data={"id": i})
            payloads.append(qr_data.to_json())

        batch_file = tmp_path / "batch.json"
        batch_file.write_text(json.dumps(payloads))

        result = runner.invoke(cli, [
            '--config', config_file,
            'verify', '--file', str(batch_file), '--batch',
        ])
        assert result.exit_code == 0
        assert "Batch:" in result.output
        assert "3/3 valid" in result.output

    def test_batch_verify_empty(self, runner, config_file, tmp_path):
        batch_file = tmp_path / "empty_batch.json"
        batch_file.write_text("[]")

        result = runner.invoke(cli, [
            '--config', config_file,
            'verify', '--file', str(batch_file), '--batch',
        ])
        assert result.exit_code == 0
        assert "0/0 valid" in result.output

    def test_batch_verify_not_array(self, runner, config_file, tmp_path):
        batch_file = tmp_path / "not_array.json"
        batch_file.write_text('{"not": "an array"}')

        result = runner.invoke(cli, [
            '--config', config_file,
            'verify', '--file', str(batch_file), '--batch',
        ])
        assert result.exit_code != 0
        assert "JSON array" in result.output


class TestExpiryCallback:
    """Test QR expiry notification callback."""

    def test_set_expiry_callback(self, tmp_path):
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        qrlp = QRLiveProtocol(config)

        called_with = []
        def callback(qr_data):
            called_with.append(qr_data)

        qrlp.set_expiry_callback(callback)
        assert qrlp._expiry_callback is callback

    def test_expiry_callback_triggered(self, tmp_path):
        """Expiry callback fires when a QR's expires_at is in the past."""
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(tmp_path / "keys")
        config.update_interval = 0.05
        config.security_settings.qr_ttl_seconds = 1
        qrlp = QRLiveProtocol(config)

        called_with = []
        def callback(qr_data):
            called_with.append(qr_data)

        qrlp.set_expiry_callback(callback)
        # Generate a QR with short TTL
        qrlp.generate_single_qr()
        # Manually set expiry in the past
        if qrlp._current_qr_data:
            qrlp._current_qr_data.expires_at = (
                datetime.now(timezone.utc) - timedelta(seconds=10)
            ).isoformat()

        # Start the loop briefly
        qrlp.start_live_generation()
        time.sleep(0.3)
        qrlp.stop_live_generation()

        assert len(called_with) >= 1


class TestQRDataFromDict:
    """Test QRData.from_dict classmethod."""

    def test_from_dict_basic(self):
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc",
            "blockchain_hashes": {},
            "time_server_verification": {},
            "sequence_number": 1,
        }
        qr = QRData.from_dict(data)
        assert qr.timestamp == "2025-01-01T00:00:00Z"
        assert qr.sequence_number == 1

    def test_from_dict_filters_unknown(self):
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc",
            "blockchain_hashes": {},
            "time_server_verification": {},
            "sequence_number": 1,
            "future_field": "ignored",
        }
        qr = QRData.from_dict(data)
        assert qr.timestamp == "2025-01-01T00:00:00Z"

    def test_from_dict_round_trip(self):
        qr = QRData(
            timestamp="2025-01-01T00:00:00Z",
            identity_hash="abc",
            blockchain_hashes={"bitcoin": "hash"},
            time_server_verification={},
            sequence_number=42,
        )
        d = qr.to_dict()
        restored = QRData.from_dict(d)
        assert restored.timestamp == qr.timestamp
        assert restored.sequence_number == 42
        assert restored.blockchain_hashes == {"bitcoin": "hash"}


class TestQRDataFuzz:
    """Fuzz tests for QRData.from_json with random JSON payloads."""

    def test_fuzz_random_json_strings(self):
        """from_json should never crash on random JSON strings."""
        random.seed(42)
        for _ in range(100):
            # Generate random JSON
            payload = self._generate_random_json()
            json_str = json.dumps(payload)
            try:
                QRData.from_json(json_str)
            except (TypeError, ValueError):
                pass  # Expected for invalid field types
            # Should never crash with an unhandled exception

    def test_fuzz_random_strings(self):
        """from_json should handle random string payloads gracefully."""
        random.seed(123)
        for _ in range(50):
            chars = string.printable + string.whitespace
            random_str = ''.join(random.choice(chars) for _ in range(random.randint(0, 100)))
            try:
                QRData.from_json(random_str)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass  # Expected for non-JSON input

    def _generate_random_json(self):
        """Generate a random JSON-compatible object."""
        result = {}
        for _ in range(random.randint(0, 5)):
            key = ''.join(random.choice(string.ascii_lowercase) for _ in range(random.randint(1, 10)))
            val = random.choice([
                random.randint(0, 1000),
                random.random(),
                ''.join(random.choice(string.ascii_letters) for _ in range(10)),
                None,
                True,
                False,
                [random.randint(0, 100) for _ in range(3)],
                {"nested": random.randint(0, 100)},
            ])
            result[key] = val
        return result
