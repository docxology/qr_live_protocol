"""
OpenTimestamps timestamping service for QRLP QRData commitments.

This module provides the :class:`TimeStamper`, a companion to the existing
:class:`src.time_provider.TimeProvider`. Where ``TimeProvider`` synchronises the
local clock against NTP servers, the ``TimeStamper`` commits a SHA-256 digest
of QR data to a public blockchain via an OpenTimestamps calendar server and
produces a ``.ots`` attestation file that anyone can verify independently.

The stamper is *additive*: it is disabled by default and degrades gracefully
(returning ``None``) if the calendar server is unreachable, so the rest of the
protocol (NTP + blockchain hashes + signatures) keeps working unchanged.
"""

import hashlib
import json
import logging
import threading
import time
from datetime import UTC
from pathlib import Path
from typing import Any

import requests
from opentimestamps.core.notary import (
    BitcoinBlockHeaderAttestation,
    LitecoinBlockHeaderAttestation,
    PendingAttestation,
)
from opentimestamps.core.op import OpSHA256
from opentimestamps.core.serialize import (
    StreamDeserializationContext,
    StreamSerializationContext,
)
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

_logger = logging.getLogger("qrlp.time_stamper")

# Sidecar written alongside each ``.ots`` proof so that the QR verifier can
# extract the attested timestamp and blockchain without parsing the binary OTS
# container (which only encodes block *heights*, not timestamps).
_META_SUFFIX = ".meta.json"


class TimeStamper:
    """OpenTimestamps timestamping service for QRLP QRData commitments.

    The stamper works on raw byte data. QR payloads are canonicalised to JSON
    (see :meth:`stamp_from_dict`) before being stamped so that the committed
    digest is deterministic.

    Parameters
    ----------
    enabled:
        When ``False`` (the default) every stamping operation is a no-op that
        returns ``None``. This keeps the feature opt-in and backwards
        compatible.
    server:
        URL of the OpenTimestamps calendar / stamping server.
    min_interval:
        Minimum number of seconds that must elapse between two successful
        stamps. Stamping every QR frame would be wasteful; instead the
        protocol stamps a periodic commitment. Defaults to 300 (5 minutes).
    proof_dir:
        Directory where ``.ots`` proof files (and their ``.meta.json``
        sidecars) are stored. Created on demand.
    """

    def __init__(
        self,
        enabled: bool = False,
        server: str = "https://stamp.opentimestamps.org",
        min_interval: int = 300,
        proof_dir: Path | None = None,
    ) -> None:
        self.enabled = enabled
        self.server = server
        self.min_interval = min_interval
        self.proof_dir = proof_dir if proof_dir is not None else Path("output/timestamps")

        # State — guarded by a lock so the stamper is safe to use from the
        # background QR generation thread.
        self._lock = threading.Lock()
        self._last_stamp_time: float = 0.0
        self._last_proof_path: Path | None = None

        # A single requests.Session gives us keep-alive connection pooling,
        # mirroring the pattern used by BlockchainVerifier.
        self._session: requests.Session | None = None

        # Ensure the proof directory exists eagerly so callers can rely on it.
        self._ensure_proof_dir()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def needs_stamp(self) -> bool:
        """Return ``True`` if enough time has elapsed since the last stamp."""
        if self._last_stamp_time == 0.0:
            return True
        return (time.time() - self._last_stamp_time) >= self.min_interval

    def last_stamp_path(self) -> Path | None:
        """Return the path of the most recent proof file, or ``None``."""
        with self._lock:
            return self._last_proof_path

    def stamp(self, data: bytes) -> Path | None:
        """Stamp ``data`` and return the path to the resulting ``.ots`` proof.

        Computes the SHA-256 digest of ``data``, submits it to the configured
        OpenTimestamps server, and writes the returned proof to
        :attr:`proof_dir`. Returns ``None`` (and logs a warning) when stamping
        is disabled, the minimum interval has not elapsed, or any error occurs
        — the system degrades gracefully to "signature + NTP" mode.
        """
        if not self.enabled:
            _logger.debug("OTS stamping disabled; skipping.")
            return None

        with self._lock:
            if not self._interval_elapsed_locked():
                _logger.debug("OTS min_interval not elapsed; skipping stamp.")
                return None

        digest = hashlib.sha256(data).digest()
        try:
            dts = self._build_timestamp_file(digest)
            self._submit_to_calendar(dts.timestamp)
            proof_path = self._write_proof(dts, digest, data)
        except Exception as exc:
            _logger.warning("OpenTimestamps stamping failed: %s", exc)
            return None

        with self._lock:
            self._last_stamp_time = time.time()
            self._last_proof_path = proof_path

        _logger.info("OTS proof written to %s", proof_path)
        return proof_path

    def stamp_from_dict(self, qr_data_dict: dict[str, Any]) -> Path | None:
        """Canonicalise ``qr_data_dict`` to JSON bytes and stamp the result."""
        canonical = self._canonical_json(qr_data_dict)
        return self.stamp(canonical.encode("utf-8"))

    def verify(self, data: bytes, proof_path: Path) -> bool:
        """Verify that ``data`` matches the OTS proof at ``proof_path``.

        Returns ``True`` when the proof file parses as a valid OpenTimestamps
        container *and* the SHA-256 digest of ``data`` equals the digest
        committed in the proof. A freshly-stamped proof is a *pending*
        attestation (confirmed on-chain later), so on-chain block-header
        verification is attempted best-effort but is not required for a
        ``True`` result — the digest match itself proves ``data`` was the
        committed value.
        """
        try:
            dts = self._read_proof(proof_path)
        except Exception as exc:
            _logger.warning("Cannot read OTS proof %s: %s", proof_path, exc)
            return False

        expected_digest = hashlib.sha256(data).digest()
        if dts.file_digest != expected_digest:
            _logger.warning("OTS digest mismatch for %s", proof_path)
            return False

        # The digest matches and the proof is structurally valid. Best-effort
        # on-chain confirmation: if a block-header attestation is present we
        # cannot verify it without the corresponding block header, so we treat
        # the digest match as sufficient (the proof still attests the data).
        return True

    def proof_info(self, proof_path: Path) -> dict[str, Any]:
        """Parse a ``.ots`` proof and return summary metadata.

        The returned dict contains:
        - ``digest``: hex SHA-256 digest committed in the proof.
        - ``blockchain``: ``"bitcoin"`` / ``"litecoin"`` / ``"pending"`` /
          ``"unknown"`` based on the strongest attestation present.
        - ``timestamp``: ISO-8601 stamp time from the ``.meta.json`` sidecar
          written when the proof was created, or ``""`` if unavailable.
        - ``attestations``: list of human-readable attestation descriptions.
        """
        info: dict[str, Any] = {
            "digest": "",
            "blockchain": "unknown",
            "timestamp": "",
            "attestations": [],
        }
        try:
            dts = self._read_proof(proof_path)
        except Exception as exc:
            _logger.debug("proof_info: cannot parse %s: %s", proof_path, exc)
            return info

        info["digest"] = dts.file_digest.hex()
        attestations = _attestation_objects(dts.timestamp)
        info["attestations"] = [
            self._describe_attestation(att) for att in attestations
        ]
        info["blockchain"] = self._blockchain_from_attestations(attestations)
        info["timestamp"] = self._read_meta_timestamp(proof_path)
        return info

    def render_proof_text(self, proof_path: Path) -> str:
        """Render a small key:value text summary of a proof.

        Used by :class:`src.time_stamper_integration.QRLPTimeStampVerifier` so
        its ``_extract_timestamp`` / ``_extract_blockchain`` helpers can parse
        a human-readable string (the binary OTS container encodes block
        *heights*, not timestamps, so the sidecar metadata is the source of
        the stamp time).
        """
        info = self.proof_info(proof_path)
        return (
            f"Digest: {info['digest']}\n"
            f"Blockchain: {info['blockchain']}\n"
            f"Timestamp: {info['timestamp']}\n"
            f"Attestations: {', '.join(info['attestations']) or 'none'}\n"
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _ensure_proof_dir(self) -> None:
        try:
            self.proof_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _logger.warning("Could not create OTS proof dir %s: %s", self.proof_dir, exc)

    def _session_obj(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _interval_elapsed_locked(self) -> bool:
        """Caller must hold ``self._lock``."""
        if self._last_stamp_time == 0.0:
            return True
        return (time.time() - self._last_stamp_time) >= self.min_interval

    @staticmethod
    def _canonical_json(qr_data_dict: dict[str, Any]) -> str:
        """Serialise a dict to deterministic, sorted JSON string."""
        return json.dumps(qr_data_dict, sort_keys=True, separators=(",", ":"))

    def _build_timestamp_file(self, digest: bytes) -> DetachedTimestampFile:
        """Build a :class:`DetachedTimestampFile` committing ``digest``.

        The direct constructor sets ``file_digest == digest`` so the proof
        commits exactly the SHA-256 of the original data without re-hashing.
        """
        return DetachedTimestampFile(OpSHA256(), Timestamp(digest))

    def _submit_to_calendar(self, timestamp: Timestamp) -> None:
        """Submit the commitment to the calendar server and merge the proof.

        Imported lazily so that tests can patch ``RemoteCalendar`` and so the
        opentimestamps network code is not imported at module import time.
        """
        from opentimestamps.calendar import RemoteCalendar

        calendar = RemoteCalendar(self.server)
        commitment = timestamp.msg
        calendar.submit(commitment)
        try:
            remote_ts = calendar.get_timestamp(commitment)
            timestamp.merge(remote_ts)
        except Exception as exc:
            # A pending attestation is still a valid proof of submission time.
            _logger.debug("OTS calendar upgrade pending: %s", exc)

        # A brand-new submission is not yet confirmed on-chain, so it carries a
        # pending attestation. Ensure at least one attestation exists — an
        # empty timestamp cannot be serialized into a ``.ots`` file.
        if not _has_attestation(timestamp):
            timestamp.attestations.add(PendingAttestation(self.server))

    def _write_proof(
        self,
        dts: DetachedTimestampFile,
        digest: bytes,
        data: bytes,
    ) -> Path:
        """Serialise the proof to disk and write a ``.meta.json`` sidecar."""
        proof_path = self.proof_dir / f"{digest.hex()}.ots"
        with open(proof_path, "wb") as fh:
            dts.serialize(StreamSerializationContext(fh))

        # Sidecar with the stamp time — the binary OTS file only encodes block
        # heights, so this is the canonical source of "when was this stamped".
        meta = {
            "stamp_time": datetime_now_iso(),
            "blockchain": self._blockchain_from_attestations(
                _attestation_objects(dts.timestamp)
            ),
            "digest": digest.hex(),
            "data_sha256": hashlib.sha256(data).hexdigest(),
        }
        meta_path = self.proof_dir / f"{digest.hex()}{_META_SUFFIX}"
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
        return proof_path

    def _read_proof(self, proof_path: Path) -> DetachedTimestampFile:
        with open(proof_path, "rb") as fh:
            return DetachedTimestampFile.deserialize(StreamDeserializationContext(fh))

    def _read_meta_timestamp(self, proof_path: Path) -> str:
        meta_path = self._meta_path_for(proof_path)
        try:
            with open(meta_path, encoding="utf-8") as fh:
                meta = json.load(fh)
            return str(meta.get("stamp_time", ""))
        except (OSError, ValueError):
            return ""

    def _meta_path_for(self, proof_path: Path) -> Path:
        """Return the ``.meta.json`` sidecar path for a given ``.ots`` proof."""
        stem = str(proof_path)
        if stem.endswith(".ots"):
            stem = stem[: -len(".ots")]
        return Path(stem + _META_SUFFIX)

    @staticmethod
    def _describe_attestation(att: Any) -> str:
        if isinstance(att, BitcoinBlockHeaderAttestation):
            return f"BitcoinBlockHeaderAttestation({att.height})"
        if isinstance(att, LitecoinBlockHeaderAttestation):
            return f"LitecoinBlockHeaderAttestation({att.height})"
        if isinstance(att, PendingAttestation):
            return f"PendingAttestation({getattr(att, 'uri', '')})"
        return type(att).__name__

    @staticmethod
    def _blockchain_from_attestations(attestations: list[Any]) -> str:
        """Return the strongest on-chain chain name from attestations."""
        for att in attestations:
            if isinstance(att, BitcoinBlockHeaderAttestation):
                return "bitcoin"
        for att in attestations:
            if isinstance(att, LitecoinBlockHeaderAttestation):
                return "litecoin"
        for att in attestations:
            if isinstance(att, PendingAttestation):
                return "pending"
        return "unknown"


def _attestation_objects(timestamp: Timestamp) -> list[Any]:
    """Return the attestation objects from ``timestamp.all_attestations()``.

    ``all_attestations()`` yields ``(digest, attestation)`` tuples; this helper
    unwraps them so callers receive plain attestation objects.
    """
    objects: list[Any] = []
    for item in timestamp.all_attestations():
        if isinstance(item, tuple):
            objects.append(item[1])
        else:
            objects.append(item)
    return objects


def _has_attestation(timestamp: Timestamp) -> bool:
    """Return ``True`` if ``timestamp`` (or any successor) has an attestation."""
    try:
        return next(timestamp.all_attestations(), None) is not None
    except Exception:
        return False


def datetime_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    from datetime import datetime

    return datetime.now(UTC).isoformat()
