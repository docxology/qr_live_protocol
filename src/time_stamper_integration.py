"""
OpenTimestamps integration with the QRLP verification pipeline.

This module connects the :class:`src.time_stamper.TimeStamper` to the QR data
verification flow. It is *additive*: the existing HMAC + signature + time +
blockchain checks run exactly as before, and the OTS timestamp proof is layered
on top as additional, independently-verifiable attestation that the QR payload
existed at the stamped time.
"""

import json
import logging
from pathlib import Path
from typing import Any

from .time_stamper import TimeStamper

_logger = logging.getLogger("qrlp.time_stamper_integration")

# Forward-declared type alias to avoid importing QRLiveProtocol at module load
# (which would create a circular import). The verifier is optional.
QRLiveProtocol = Any


class QRLPTimeStampVerifier:
    """Integrates OTS verification into QR data verification results.

    Parameters
    ----------
    time_stamper:
        The :class:`TimeStamper` used to verify ``.ots`` proofs.
    verifier:
        Optional :class:`src.core.QRLiveProtocol` instance. When provided, the
        existing HMAC / signature / time / blockchain checks are run first via
        ``verifier.verify_qr_data()`` and their result is merged with the OTS
        fields. When omitted, a minimal base result is used so this class can
        be exercised in isolation (useful for tests and for verifying a QR
        without a full QRLP setup).
    """

    def __init__(
        self,
        time_stamper: TimeStamper,
        verifier: QRLiveProtocol | None = None,
    ) -> None:
        self.time_stamper = time_stamper
        self.verifier = verifier

    def verify_qr_with_timestamp(
        self,
        qr_json: str,
        proof_path: Path,
        tolerance_seconds: int = 60,
    ) -> dict[str, Any]:
        """Full verification: existing checks + OTS timestamp proof.

        Runs the existing HMAC / signature / time / blockchain verification
        (when a :class:`QRLiveProtocol` verifier is configured) and then
        verifies the OTS proof against ``qr_json``. The returned dict contains
        all the existing verification fields plus:

        - ``ots_verified``: ``True`` if the OTS proof matches the QR data.
        - ``ots_proof_path``: string path of the proof file.
        - ``ots_timestamp``: ISO timestamp attested by the proof (from the
          ``.meta.json`` sidecar), or ``""`` if unavailable.
        - ``ots_blockchain``: ``"bitcoin"`` / ``"litecoin"`` / ``"pending"`` /
          ``"unknown"`` — the chain the proof is attested on.

        Parameters
        ----------
        qr_json:
            JSON string of the QR payload.
        proof_path:
            Path to the ``.ots`` proof file.
        tolerance_seconds:
            Acceptable time drift in seconds (recorded for callers; the OTS
            digest check itself is exact).
        """
        existing = self._existing_verification(qr_json)

        qr_bytes = qr_json.encode("utf-8")
        ots_ok = self.time_stamper.verify(qr_bytes, proof_path)

        proof_text = self.time_stamper.render_proof_text(proof_path)
        ots_ts = self._extract_timestamp(proof_text)
        ots_chain = self._extract_blockchain(proof_text)

        return {
            **existing,
            "ots_verified": ots_ok,
            "ots_proof_path": str(proof_path),
            "ots_timestamp": ots_ts,
            "ots_blockchain": ots_chain,
            "ots_tolerance_seconds": tolerance_seconds,
        }

    # ------------------------------------------------------------------ #
    # Static extraction helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_timestamp(ots_proof_text: str) -> str:
        """Parse the attested timestamp from a human-readable proof summary.

        Expects a line of the form ``Timestamp: <iso-8601>``. Returns ``""``
        when no timestamp line is present.
        """
        for line in ots_proof_text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("timestamp:"):
                value = stripped.split(":", 1)[1].strip()
                return value
        return ""

    @staticmethod
    def _extract_blockchain(ots_proof_text: str) -> str:
        """Parse which blockchain a proof is attested on.

        Expects a line of the form ``Blockchain: <name>``. Returns
        ``"unknown"`` when no blockchain line is present.
        """
        for line in ots_proof_text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("blockchain:"):
                value = stripped.split(":", 1)[1].strip()
                return value
        return "unknown"

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _existing_verification(self, qr_json: str) -> dict[str, Any]:
        """Run the existing QR verification, or return a minimal base dict."""
        if self.verifier is not None:
            try:
                return dict(self.verifier.verify_qr_data(qr_json))
            except Exception as exc:
                _logger.warning("Existing QR verification failed: %s", exc)
        # Minimal base result when no QRLiveProtocol is configured.
        return {
            "valid_json": _is_valid_json(qr_json),
            "identity_verified": False,
            "time_verified": False,
            "blockchain_verified": False,
            "signature_verified": False,
            "hmac_verified": False,
            "encrypted": False,
            "valid": False,
            "trust_mode": "none",
        }


def _is_valid_json(text: str) -> bool:
    """Return ``True`` if ``text`` parses as JSON."""
    try:
        json.loads(text)
        return True
    except (ValueError, TypeError):
        return False
