"""
Tests for the QRLPTimeStampVerifier integration layer.

These tests exercise the bridge between the OpenTimestamps :class:`TimeStamper`
and the QR verification pipeline. Network calls are mocked via the same
``RemoteCalendar`` patches used in ``test_time_stamper.py``.
"""

import json
from unittest.mock import patch

import pytest
from src.time_stamper import TimeStamper
from src.time_stamper_integration import QRLPTimeStampVerifier


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _confirmed_calendar():
    """Patch RemoteCalendar to return a confirmed bitcoin attestation."""
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
    from opentimestamps.core.timestamp import Timestamp

    @staticmethod
    def _submit(commitment, timeout=None):
        return None

    @staticmethod
    def _get_timestamp(commitment, timeout=None):
        ts = Timestamp(commitment)
        ts.attestations.add(BitcoinBlockHeaderAttestation(800000))
        return ts

    return patch(
        "opentimestamps.calendar.RemoteCalendar.submit", _submit
    ), patch(
        "opentimestamps.calendar.RemoteCalendar.get_timestamp", _get_timestamp
    )


@pytest.fixture
def stamper(tmp_path):
    """An enabled TimeStamper writing to a temp dir."""
    return TimeStamper(
        enabled=True,
        server="https://example.test",
        min_interval=0,
        proof_dir=tmp_path / "timestamps",
    )


@pytest.fixture
def verifier(stamper):
    """A QRLPTimeStampVerifier with no QRLiveProtocol (minimal base result)."""
    return QRLPTimeStampVerifier(stamper)


@pytest.fixture
def stamped_qr(verifier, stamper):
    """Stamp a QR JSON payload and return (qr_json, proof_path)."""
    qr_json = json.dumps(
        {
            "timestamp": "2025-01-11T15:30:45Z",
            "identity_hash": "abc123def456",
            "sequence_number": 1,
        },
        separators=(",", ":"),
    )
    with _confirmed_calendar()[0], _confirmed_calendar()[1]:
        proof_path = stamper.stamp(qr_json.encode("utf-8"))
    assert proof_path is not None
    return qr_json, proof_path


# --------------------------------------------------------------------------- #
# Full verification flow
# --------------------------------------------------------------------------- #
class TestVerifyQRWithTimestamp:
    def test_full_verification_with_ots(self, verifier, stamped_qr):
        """Stamp a QR, verify with OTS returns ots_verified=True."""
        qr_json, proof_path = stamped_qr
        result = verifier.verify_qr_with_timestamp(qr_json, proof_path)
        assert result["ots_verified"] is True

    def test_ots_field_added_to_result(self, verifier, stamped_qr):
        """The verification dict contains all the new OTS fields."""
        qr_json, proof_path = stamped_qr
        result = verifier.verify_qr_with_timestamp(qr_json, proof_path)
        for field in ("ots_verified", "ots_proof_path", "ots_timestamp",
                      "ots_blockchain"):
            assert field in result, f"missing OTS field: {field}"
        assert result["ots_proof_path"] == str(proof_path)
        assert result["ots_tolerance_seconds"] == 60

    def test_ots_verification_fails_on_tampered_data(self, verifier, stamped_qr):
        """Verifying a modified QR payload against the proof fails."""
        _, proof_path = stamped_qr
        tampered = json.dumps({"timestamp": "1999-01-01T00:00:00Z", "tampered": True})
        result = verifier.verify_qr_with_timestamp(tampered, proof_path)
        assert result["ots_verified"] is False

    def test_timestamp_extraction(self, verifier, stamped_qr):
        """The parsed timestamp matches what is in the proof sidecar."""
        qr_json, proof_path = stamped_qr
        result = verifier.verify_qr_with_timestamp(qr_json, proof_path)
        assert result["ots_timestamp"] != ""
        # ISO-8601 timestamp should contain a date separator.
        assert "-" in result["ots_timestamp"]

    def test_blockchain_extraction(self, verifier, stamped_qr):
        """The parsed blockchain name is correct (bitcoin for confirmed)."""
        qr_json, proof_path = stamped_qr
        result = verifier.verify_qr_with_timestamp(qr_json, proof_path)
        assert result["ots_blockchain"] == "bitcoin"

    def test_missing_proof_returns_ots_verified_false(self, verifier, tmp_path):
        """A missing proof file yields ots_verified=False."""
        qr_json = json.dumps({"a": 1})
        result = verifier.verify_qr_with_timestamp(
            qr_json, tmp_path / "nonexistent.ots"
        )
        assert result["ots_verified"] is False
        assert result["ots_blockchain"] == "unknown"
        assert result["ots_timestamp"] == ""


# --------------------------------------------------------------------------- #
# Static extraction helpers
# --------------------------------------------------------------------------- #
class TestExtractionHelpers:
    def test_extract_timestamp_found(self):
        text = "Digest: abc\nBlockchain: bitcoin\nTimestamp: 2025-01-11T15:30:45Z\n"
        assert QRLPTimeStampVerifier._extract_timestamp(text) == "2025-01-11T15:30:45Z"

    def test_extract_timestamp_missing(self):
        text = "Digest: abc\nBlockchain: bitcoin\n"
        assert QRLPTimeStampVerifier._extract_timestamp(text) == ""

    def test_extract_blockchain_found(self):
        text = "Blockchain: litecoin\nTimestamp: x\n"
        assert QRLPTimeStampVerifier._extract_blockchain(text) == "litecoin"

    def test_extract_blockchain_missing(self):
        text = "Digest: abc\n"
        assert QRLPTimeStampVerifier._extract_blockchain(text) == "unknown"

    def test_extract_case_insensitive(self):
        text = "blockchain: pending\ntimestamp: 2025-01-01\n"
        assert QRLPTimeStampVerifier._extract_blockchain(text) == "pending"
        assert QRLPTimeStampVerifier._extract_timestamp(text) == "2025-01-01"


# --------------------------------------------------------------------------- #
# Existing-verifier integration & error paths
# --------------------------------------------------------------------------- #
class TestExistingVerifierIntegration:
    def test_with_qrlp_verifier(self, stamper, stamped_qr):
        """When a QRLiveProtocol verifier is provided, its result is merged."""
        qr_json, proof_path = stamped_qr

        class FakeQRLP:
            def verify_qr_data(self, qr_json_str):
                return {
                    "valid_json": True,
                    "identity_verified": True,
                    "signature_verified": False,
                    "valid": True,
                }

        v = QRLPTimeStampVerifier(stamper, verifier=FakeQRLP())  # type: ignore[arg-type]
        result = v.verify_qr_with_timestamp(qr_json, proof_path)
        assert result["identity_verified"] is True
        assert result["valid"] is True
        assert result["ots_verified"] is True

    def test_qrlp_verifier_error_degrades(self, stamper, stamped_qr):
        """If the existing verifier raises, the base result is used."""
        qr_json, proof_path = stamped_qr

        class BrokenQRLP:
            def verify_qr_data(self, qr_json_str):
                raise RuntimeError("boom")

        v = QRLPTimeStampVerifier(stamper, verifier=BrokenQRLP())  # type: ignore[arg-type]
        result = v.verify_qr_with_timestamp(qr_json, proof_path)
        # Falls back to the minimal base result, but OTS still verified.
        assert result["valid_json"] is True
        assert result["ots_verified"] is True

    def test_tolerance_recorded(self, verifier, stamped_qr):
        """The tolerance_seconds argument is echoed in the result."""
        qr_json, proof_path = stamped_qr
        result = verifier.verify_qr_with_timestamp(
            qr_json, proof_path, tolerance_seconds=120
        )
        assert result["ots_tolerance_seconds"] == 120

    def test_invalid_json_base_result(self, verifier, stamped_qr):
        """Invalid QR JSON yields valid_json=False in the base result."""
        _, proof_path = stamped_qr
        result = verifier.verify_qr_with_timestamp("not valid json{", proof_path)
        assert result["valid_json"] is False
