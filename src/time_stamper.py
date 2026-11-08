"""
OpenTimestamps timestamping service for QRLP QRData commitments.

This module provides the :class:`TimeStamper`, a companion to the existing
:class:`src.time_provider.TimeProvider`. Where ``TimeProvider`` synchronises the
local clock, the ``TimeStamper`` submits a SHA-256 digest of QR data to an
OpenTimestamps calendar and saves the returned ``.ots`` receipt. A pending
receipt needs a later upgrade and independent chain verification.

The stamper is *additive*: it is disabled by default and degrades gracefully
(returning ``None``) if the calendar server is unreachable, so the rest of the
protocol (NTP + blockchain hashes + signatures) keeps working unchanged.
"""

import hashlib
import json
import logging
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from opentimestamps.core.notary import (
    BitcoinBlockHeaderAttestation,
    LitecoinBlockHeaderAttestation,
    PendingAttestation,
)
from opentimestamps.core.op import OpSHA256
from opentimestamps.core.serialize import (
    BytesDeserializationContext,
    BytesSerializationContext,
)
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

_logger = logging.getLogger("qrlp.time_stamper")

# This sidecar records local receipt metadata outside the OTS commitment.
_META_SUFFIX = ".meta.json"
_MAX_PROOF_BYTES = 1024 * 1024
_MAX_METADATA_BYTES = 8192


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
        sidecars) are stored.
    timeout:
        Calendar request timeout in seconds.
    """

    def __init__(
        self,
        enabled: bool = False,
        server: str = "https://a.pool.opentimestamps.org",
        min_interval: int = 300,
        proof_dir: Path | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.enabled = enabled
        self.server = server
        self.min_interval = min_interval
        self.timeout = timeout
        self.proof_dir = proof_dir if proof_dir is not None else Path("output/timestamps")

        # State — guarded by a lock so the stamper is safe to use from the
        # background QR generation thread.
        self._lock = threading.Lock()
        self._last_stamp_time: float = 0.0
        self._last_proof_path: Path | None = None
        self._stamp_in_progress = False

        if enabled:
            self._ensure_proof_dir()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def needs_stamp(self) -> bool:
        """Return whether a new stamp can be attempted now."""
        with self._lock:
            return self.enabled and not self._stamp_in_progress and self._interval_elapsed_locked()

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
            if self._stamp_in_progress or not self._interval_elapsed_locked():
                return None
            self._stamp_in_progress = True

        proof_path = None
        try:
            digest = hashlib.sha256(data).digest()
            dts = self._build_timestamp_file(digest)
            self._submit_to_calendar(dts.timestamp)
            proof_path = self._write_proof(dts, digest)
        except Exception as exc:
            _logger.warning("OpenTimestamps stamping failed: %s", exc)
            return None
        finally:
            with self._lock:
                if proof_path is not None:
                    self._last_stamp_time = time.monotonic()
                    self._last_proof_path = proof_path
                self._stamp_in_progress = False

        _logger.info("OTS proof written to %s", proof_path)
        return proof_path

    def stamp_from_dict(self, qr_data_dict: dict[str, Any]) -> Path | None:
        """Canonicalise ``qr_data_dict`` to JSON bytes and stamp the result."""
        canonical = self._canonical_json(qr_data_dict)
        return self.stamp(canonical.encode("utf-8"))

    def verify(self, data: bytes, proof_path: Path) -> bool:
        """Check the SHA-256 digest and the presence of an attestation.

        This is a structural check. Calendar and block-header claims require
        independent OpenTimestamps verification against a trusted chain.
        """
        matches, _ = self.check_proof(data, proof_path)
        return matches

    def check_proof(self, data: bytes, proof_path: Path) -> tuple[bool, dict[str, Any]]:
        """Return the structural digest result and metadata from one proof read."""
        digest = hashlib.sha256(data).digest()
        dts = self._read_proof_if_valid(proof_path)
        if dts is None or dts.file_digest != digest:
            return False, self._proof_summary(None, proof_path)
        return _has_attestation(dts.timestamp), self._proof_summary(dts, proof_path)

    def proof_info(self, proof_path: Path) -> dict[str, Any]:
        """Return digest, reported chain, local receipt time and attestations."""
        return self._proof_summary(self._read_proof_if_valid(proof_path), proof_path)

    def _read_proof_if_valid(self, proof_path: Path) -> DetachedTimestampFile | None:
        try:
            dts = self._read_proof(proof_path)
            if not isinstance(dts.file_hash_op, OpSHA256):
                raise ValueError("QRLP receipts must commit to SHA-256")
            return dts
        except Exception as exc:
            _logger.debug("Cannot read OTS proof %s: %s", proof_path, exc)
            return None

    def _proof_summary(self, dts: DetachedTimestampFile | None, proof_path: Path) -> dict[str, Any]:
        if dts is None:
            return {"digest": "", "blockchain": "unknown", "timestamp": "", "attestations": []}

        digest = dts.file_digest.hex()
        attestations = _attestation_objects(dts.timestamp)
        return {
            "digest": digest,
            "blockchain": self._blockchain_from_attestations(attestations),
            "timestamp": self._read_meta_timestamp(proof_path, digest),
            "attestations": [self._describe_attestation(att) for att in attestations],
        }

    def render_proof_text(self, proof_path: Path) -> str:
        """Render a small key:value text summary of a proof.

        Timestamp is the local receipt time saved in the sidecar.
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

    def _interval_elapsed_locked(self) -> bool:
        return self._last_proof_path is None or time.monotonic() - self._last_stamp_time >= self.min_interval

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
        """Merge the attestation returned by the calendar's submit operation."""
        from opentimestamps.calendar import RemoteCalendar

        calendar = RemoteCalendar(self.server.rstrip("/") + "/")
        returned = calendar.submit(timestamp.msg, timeout=self.timeout)
        timestamp.merge(returned)
        if not _has_attestation(timestamp):
            raise ValueError("OpenTimestamps calendar response has no attestation")

    def _write_proof(self, dts: DetachedTimestampFile, digest: bytes) -> Path:
        proof_path = self.proof_dir / f"{digest.hex()}.ots"
        self._ensure_proof_dir()
        context = BytesSerializationContext()
        dts.serialize(context)
        _atomic_write(proof_path, context.getbytes())

        # The locally measured receipt time is optional metadata. A sidecar
        # write failure must not discard the successfully stored proof.
        meta = {
            "stamp_time": datetime_now_iso(),
            "blockchain": self._blockchain_from_attestations(_attestation_objects(dts.timestamp)),
            "digest": digest.hex(),
            "data_sha256": digest.hex(),
        }
        try:
            _atomic_write(self._meta_path_for(proof_path), json.dumps(meta).encode("utf-8"))
        except OSError as exc:
            _logger.warning("Could not write OTS receipt metadata: %s", exc)
        return proof_path

    def _read_proof(self, proof_path: Path) -> DetachedTimestampFile:
        with proof_path.open("rb") as stream:
            proof = stream.read(_MAX_PROOF_BYTES + 1)
        if len(proof) > _MAX_PROOF_BYTES:
            raise ValueError("OpenTimestamps proof exceeds size limit")
        return DetachedTimestampFile.deserialize(BytesDeserializationContext(proof))

    def _read_meta_timestamp(self, proof_path: Path, digest: str | None = None) -> str:
        try:
            with self._meta_path_for(proof_path).open("rb") as stream:
                data = stream.read(_MAX_METADATA_BYTES + 1)
            if len(data) <= _MAX_METADATA_BYTES:
                meta = json.loads(data)
                if isinstance(meta, dict) and (digest is None or meta.get("digest") == digest):
                    timestamp = meta.get("stamp_time")
                    if isinstance(timestamp, str):
                        return timestamp
        except (OSError, ValueError):
            pass
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


def _atomic_write(path: Path, data: bytes) -> None:
    """Publish complete bytes using a private temporary in the same directory."""
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


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
    return datetime.now(UTC).isoformat()
