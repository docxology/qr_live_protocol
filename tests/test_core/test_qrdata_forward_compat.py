"""
Tests for QRData.from_json forward-compatibility and QRData edge cases.

Covers the unknown-field filtering added to from_json, ensuring
forward-compatible QR payloads don't break older verifiers.
"""

import json
import pytest
from src.core import QRData


class TestQRDataForwardCompat:
    """Test QRData handles unknown fields gracefully."""

    def test_from_json_ignores_unknown_fields(self):
        """from_json should silently ignore fields not in the dataclass."""
        data = {
            "timestamp": "2025-01-11T15:30:45.123456+00:00",
            "identity_hash": "abc123",
            "blockchain_hashes": {},
            "time_server_verification": {},
            "sequence_number": 1,
            "future_field": "should be ignored",
            "another_unknown": 42,
        }
        qr_data = QRData.from_json(json.dumps(data))
        assert qr_data.timestamp == "2025-01-11T15:30:45.123456+00:00"
        assert qr_data.identity_hash == "abc123"
        assert qr_data.sequence_number == 1

    def test_from_json_round_trip(self):
        """to_json -> from_json round trip preserves known fields."""
        qr = QRData(
            timestamp="2025-01-11T15:30:45Z",
            identity_hash="deadbeef",
            blockchain_hashes={"bitcoin": "abc"},
            time_server_verification={},
            sequence_number=42,
        )
        json_str = qr.to_json()
        restored = QRData.from_json(json_str)
        assert restored.timestamp == qr.timestamp
        assert restored.identity_hash == qr.identity_hash
        assert restored.sequence_number == qr.sequence_number
        assert restored.blockchain_hashes == qr.blockchain_hashes

    def test_to_json_filters_none_values(self):
        """to_json should filter out None values for compact serialization."""
        qr = QRData(
            timestamp="2025-01-11T15:30:45Z",
            identity_hash="abc",
            blockchain_hashes={},
            time_server_verification={},
            sequence_number=1,
        )
        data = json.loads(qr.to_json())
        assert "user_data" not in data
        assert "issuer_id" not in data
        assert "digital_signature" not in data
