"""
Tests for QRData.from_json forward-compatibility and QRData edge cases.

Covers the unknown-field filtering added to from_json, ensuring
forward-compatible QR payloads don't break older verifiers.
"""

import json

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

    def test_verify_qr_data_tolerates_unknown_fields(self, qrlp_instance):
        """verify_qr_data must not crash on a QR that carries extra unknown fields.

        This is the wire-level counterpart of ``from_json`` forward
        compatibility. Previously ``verify_qr_data`` built ``QRData(**dict)``
        directly, so an unfamiliar field raised a TypeError that surfaced as
        ``valid_json=False`` — even for a legitimately-signed QR from a newer
        version. Now unknown fields are dropped for parsing, so verification
        runs and reports a definitive crypto outcome instead.
        """
        qr_data, _ = qrlp_instance.generate_single_qr(sign_data=True)
        payload = json.loads(qr_data.to_json())
        payload["future_field"] = "ignored-by-older-verifier"
        payload["another_new_field"] = {"nested": [1, 2, 3]}

        results = qrlp_instance.verify_qr_data(json.dumps(payload))

        # The payload still parses as valid JSON (no crash), and the crypto
        # layer produced a real decision rather than erroring out. The injected
        # field was not part of what was signed/HMAC'd, so both checks fail —
        # which is the correct tamper-detection outcome.
        assert results["valid_json"] is True
        assert results["signature_verified"] is False
        assert results["hmac_verified"] is False
