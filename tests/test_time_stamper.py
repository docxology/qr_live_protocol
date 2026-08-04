"""
Tests for the OpenTimestamps TimeStamper.

All network-dependent paths are mocked: ``RemoteCalendar.submit`` and
``RemoteCalendar.get_timestamp`` are patched so no real HTTP calls are made.
The tests exercise stamping, verification, interval enforcement, canonical
serialisation, and graceful degradation.
"""

import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from src.time_stamper import TimeStamper


# --------------------------------------------------------------------------- #
# Helpers / fixtures
# --------------------------------------------------------------------------- #
def _make_calendar_stub(attestation_factory):
    """Return stubs for RemoteCalendar.submit / get_timestamp.

    ``attestation_factory(commitment)`` returns a ``Timestamp`` whose
    attestations reflect the desired proof state (pending or confirmed).
    """

    @staticmethod
    def _submit(commitment, timeout=None):
        return None

    @staticmethod
    def _get_timestamp(commitment, timeout=None):
        return attestation_factory(commitment)

    return _submit, _get_timestamp


def _confirmed_timestamp(commitment):
    """A timestamp with a Bitcoin block-header attestation (on-chain)."""
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
    from opentimestamps.core.timestamp import Timestamp

    ts = Timestamp(commitment)
    ts.attestations.add(BitcoinBlockHeaderAttestation(800000))
    return ts


def _pending_timestamp(commitment):
    """A timestamp with a PendingAttestation (submitted, not yet confirmed)."""
    from opentimestamps.core.notary import PendingAttestation
    from opentimestamps.core.timestamp import Timestamp

    ts = Timestamp(commitment)
    ts.attestations.add(PendingAttestation("https://example.test"))
    return ts


def _empty_timestamp(commitment):
    """A timestamp with no attestations — exercises the pending fallback."""
    from opentimestamps.core.timestamp import Timestamp

    return Timestamp(commitment)


@pytest.fixture
def proof_dir(tmp_path):
    """A temporary directory for OTS proof files."""
    return tmp_path / "timestamps"


@pytest.fixture
def stamper(proof_dir):
    """An enabled TimeStamper with min_interval=0 (always stamps)."""
    return TimeStamper(
        enabled=True,
        server="https://example.test",
        min_interval=0,
        proof_dir=proof_dir,
    )


@pytest.fixture
def patched_calendar():
    """Patch RemoteCalendar to use a confirmed (bitcoin) attestation."""
    submit, get_ts = _make_calendar_stub(_confirmed_timestamp)
    with patch(
        "opentimestamps.calendar.RemoteCalendar.submit", submit
    ), patch(
        "opentimestamps.calendar.RemoteCalendar.get_timestamp", get_ts
    ):
        yield


# --------------------------------------------------------------------------- #
# Stamping
# --------------------------------------------------------------------------- #
class TestStamping:
    def test_stamp_returns_path(self, stamper, patched_calendar):
        """Stamping valid bytes returns a Path to a .ots proof file."""
        path = stamper.stamp(b"hello world")
        assert path is not None
        assert isinstance(path, Path)
        assert path.exists()
        assert path.suffix == ".ots"

    def test_stamp_with_disabled_returns_none(self, proof_dir):
        """A disabled stamper returns None without stamping."""
        s = TimeStamper(enabled=False, proof_dir=proof_dir)
        assert s.stamp(b"data") is None

    def test_stamp_with_server_error_returns_none(self, stamper):
        """A network/server failure degrades gracefully to None."""
        with patch(
            "opentimestamps.calendar.RemoteCalendar.submit",
            side_effect=ConnectionError("network down"),
        ):
            assert stamper.stamp(b"data") is None

    def test_stamp_from_dict(self, stamper, patched_calendar):
        """A QR-like dict round-trips through canonical JSON to a stamp."""
        qr_dict = {
            "timestamp": "2025-01-11T15:30:45Z",
            "identity_hash": "abc123",
            "sequence_number": 1,
            "blockchain_hashes": {"bitcoin": "deadbeef"},
        }
        path = stamper.stamp_from_dict(qr_dict)
        assert path is not None
        assert path.exists()

    def test_proof_dir_created(self, tmp_path):
        """The proof directory is created if it does not exist."""
        target = tmp_path / "nested" / "deep" / "timestamps"
        assert not target.exists()
        TimeStamper(enabled=True, proof_dir=target)
        assert target.exists()
        assert target.is_dir()

    def test_stored_proof_path_persistence(self, stamper, patched_calendar):
        """last_stamp_path() returns the most recent proof path."""
        assert stamper.last_stamp_path() is None
        path = stamper.stamp(b"persist-me")
        assert stamper.last_stamp_path() == path


# --------------------------------------------------------------------------- #
# Interval enforcement
# --------------------------------------------------------------------------- #
class TestIntervalEnforcement:
    def test_stamp_interval_enforced(self, proof_dir):
        """Two stamps in quick succession: the second returns None."""
        s = TimeStamper(
            enabled=True, server="https://example.test",
            min_interval=300, proof_dir=proof_dir,
        )
        submit, get_ts = _make_calendar_stub(_confirmed_timestamp)
        with patch("opentimestamps.calendar.RemoteCalendar.submit", submit), \
                patch("opentimestamps.calendar.RemoteCalendar.get_timestamp", get_ts):
            first = s.stamp(b"first")
            second = s.stamp(b"second")
        assert first is not None
        assert second is None  # too soon

    def test_stamps_at_least_interval_apart(self, proof_dir):
        """Two stamps >= min_interval apart both succeed."""
        s = TimeStamper(
            enabled=True, server="https://example.test",
            min_interval=1, proof_dir=proof_dir,
        )
        submit, get_ts = _make_calendar_stub(_confirmed_timestamp)
        with patch("opentimestamps.calendar.RemoteCalendar.submit", submit), \
                patch("opentimestamps.calendar.RemoteCalendar.get_timestamp", get_ts):
            first = s.stamp(b"first")
            # Force the last-stamp time into the past so the interval elapsed.
            s._last_stamp_time = time.time() - 2
            second = s.stamp(b"second")
        assert first is not None
        assert second is not None

    def test_needs_stamp_initial_true(self, stamper):
        """needs_stamp() is True before any stamp."""
        assert stamper.needs_stamp() is True


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
class TestVerification:
    def test_verify_matches(self, stamper, patched_calendar):
        """Stamp then verify the same data returns True."""
        path = stamper.stamp(b"verify-me")
        assert stamper.verify(b"verify-me", path) is True

    def test_verify_modified_data_fails(self, stamper, patched_calendar):
        """Stamp data A, verify with modified data returns False."""
        path = stamper.stamp(b"original data")
        assert stamper.verify(b"tampered data", path) is False

    def test_verify_invalid_proof_fails(self, stamper, proof_dir):
        """A bogus .ots file returns False."""
        bogus = proof_dir / "bogus.ots"
        bogus.write_bytes(b"not a real ots file at all")
        assert stamper.verify(b"anything", bogus) is False

    def test_nonexistent_proof_fails(self, stamper, proof_dir):
        """Verifying against a missing file returns False."""
        assert stamper.verify(b"data", proof_dir / "missing.ots") is False

    def test_verify_pending_proof(self, proof_dir):
        """A pending (not-yet-on-chain) proof still verifies the digest."""
        s = TimeStamper(enabled=True, server="https://example.test",
                        min_interval=0, proof_dir=proof_dir)
        submit, get_ts = _make_calendar_stub(_pending_timestamp)
        with patch("opentimestamps.calendar.RemoteCalendar.submit", submit), \
                patch("opentimestamps.calendar.RemoteCalendar.get_timestamp", get_ts):
            path = s.stamp(b"pending-data")
        assert s.verify(b"pending-data", path) is True

    def test_verify_empty_calendar_fallback(self, proof_dir):
        """When get_timestamp returns empty, a pending attestation is added."""
        s = TimeStamper(enabled=True, server="https://example.test",
                        min_interval=0, proof_dir=proof_dir)
        submit, get_ts = _make_calendar_stub(_empty_timestamp)
        with patch("opentimestamps.calendar.RemoteCalendar.submit", submit), \
                patch("opentimestamps.calendar.RemoteCalendar.get_timestamp", get_ts):
            path = s.stamp(b"fallback-data")
        assert path is not None
        assert s.verify(b"fallback-data", path) is True

    def test_verify_rejects_attestation_less_fabricated_proof(self, proof_dir):
        """verify() rejects a proof carrying no attestation at all.

        This is defense-in-depth: the opentimestamps library already refuses to
        *serialize* an empty-attestation timestamp ("An empty timestamp can't
        be serialized"), so a crafted ``.ots`` file cannot normally be produced
        through the library. But a hand-built binary (or a future library
        change) could reach ``verify()`` with no calendar or chain behind the
        digest, and accepting it would let an attacker "verify" arbitrary data
        against a proof they manufactured offline. ``verify()`` must therefore
        reject proofs whose timestamp carries no attestation.
        """
        from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp
        from opentimestamps.core.op import OpSHA256

        s = TimeStamper(enabled=True, server="https://example.test",
                        min_interval=0, proof_dir=proof_dir)
        digest = hashlib.sha256(b"forged-data").digest()
        # A timestamp with NO attestations — no calendar, no chain.
        forged = DetachedTimestampFile(OpSHA256(), Timestamp(digest))
        path = proof_dir / "forged.ots"

        with patch.object(TimeStamper, "_read_proof", return_value=forged):
            assert s.verify(b"forged-data", path) is False


# --------------------------------------------------------------------------- #
# Canonical JSON & proof metadata
# --------------------------------------------------------------------------- #
class TestCanonicalAndMetadata:
    def test_canonical_json_deterministic(self):
        """The same dict always produces the same canonical JSON bytes."""
        d = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
        b1 = TimeStamper._canonical_json(d).encode("utf-8")
        b2 = TimeStamper._canonical_json(d).encode("utf-8")
        assert b1 == b2
        # Insertion order must not matter.
        d_reordered = {"a": 1, "b": 2, "nested": {"y": 8, "z": 9}}
        b3 = TimeStamper._canonical_json(d_reordered).encode("utf-8")
        assert b1 == b3

    def test_proof_info_confirmed(self, stamper, patched_calendar):
        """proof_info reports bitcoin blockchain for a confirmed proof."""
        path = stamper.stamp(b"info-data")
        info = stamper.proof_info(path)
        assert info["digest"] == path.stem
        assert info["blockchain"] == "bitcoin"
        assert info["timestamp"] != ""
        assert any("BitcoinBlockHeaderAttestation" in a for a in info["attestations"])

    def test_proof_info_pending(self, proof_dir):
        """proof_info reports pending blockchain for a pending proof."""
        s = TimeStamper(enabled=True, server="https://example.test",
                        min_interval=0, proof_dir=proof_dir)
        submit, get_ts = _make_calendar_stub(_pending_timestamp)
        with patch("opentimestamps.calendar.RemoteCalendar.submit", submit), \
                patch("opentimestamps.calendar.RemoteCalendar.get_timestamp", get_ts):
            path = s.stamp(b"pending-info")
        info = s.proof_info(path)
        assert info["blockchain"] == "pending"
        assert info["timestamp"] != ""

    def test_proof_info_bogus_file(self, stamper, proof_dir):
        """proof_info on a corrupt file returns the empty default dict."""
        bogus = proof_dir / "bogus.ots"
        bogus.write_bytes(b"garbage")
        info = stamper.proof_info(bogus)
        assert info["digest"] == ""
        assert info["blockchain"] == "unknown"
        assert info["attestations"] == []

    def test_render_proof_text(self, stamper, patched_calendar):
        """render_proof_text produces parseable key:value text."""
        path = stamper.stamp(b"render-data")
        text = stamper.render_proof_text(path)
        assert "Digest:" in text
        assert "Blockchain: bitcoin" in text
        assert "Timestamp:" in text
        # The meta sidecar exists alongside the proof.
        meta_path = stamper._meta_path_for(path)
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["digest"] == path.stem
        assert meta["blockchain"] == "bitcoin"

    def test_meta_path_for_non_ots(self, stamper):
        """_meta_path_for handles paths without the .ots suffix."""
        p = Path("/tmp/somefile")
        meta = stamper._meta_path_for(p)
        assert meta.name == "somefile.meta.json"

    def test_read_meta_timestamp_missing(self, stamper, proof_dir):
        """_read_meta_timestamp returns '' when no sidecar exists."""
        p = proof_dir / "lonely.ots"
        p.write_bytes(b"x")
        assert stamper._read_meta_timestamp(p) == ""


# --------------------------------------------------------------------------- #
# Server-error graceful degradation paths
# --------------------------------------------------------------------------- #
class TestGracefulDegradation:
    def test_get_timestamp_error_falls_back_to_pending(self, proof_dir):
        """If get_timestamp raises, a pending attestation is still added."""
        s = TimeStamper(enabled=True, server="https://example.test",
                        min_interval=0, proof_dir=proof_dir)

        @staticmethod
        def _submit(commitment, timeout=None):
            return None

        with patch("opentimestamps.calendar.RemoteCalendar.submit", _submit), \
                patch(
                    "opentimestamps.calendar.RemoteCalendar.get_timestamp",
                    side_effect=RuntimeError("upgrade not ready"),
                ):
            path = s.stamp(b"degrade-data")
        assert path is not None
        assert s.verify(b"degrade-data", path) is True
        info = s.proof_info(path)
        assert info["blockchain"] == "pending"

    def test_session_obj_reuses_session(self, stamper):
        """_session_obj returns the same Session across calls."""
        sess1 = stamper._session_obj()
        sess2 = stamper._session_obj()
        assert sess1 is sess2


# --------------------------------------------------------------------------- #
# Coverage gaps — Litecoin, unknown attestations, error branches
# --------------------------------------------------------------------------- #
class TestCoverageGaps:
    def test_needs_stamp_after_recent_stamp_false(self, stamper, patched_calendar):
        """needs_stamp() is False right after a stamp when min_interval > 0."""
        stamper.min_interval = 300
        stamper.stamp(b"recent")
        assert stamper.needs_stamp() is False

    def test_needs_stamp_after_elapsed_true(self, stamper, patched_calendar):
        """needs_stamp() is True once min_interval has elapsed."""
        stamper.min_interval = 1
        stamper.stamp(b"old")
        stamper._last_stamp_time = time.time() - 2
        assert stamper.needs_stamp() is True

    def test_proof_info_litecoin(self, proof_dir):
        """proof_info reports litecoin for a LitecoinBlockHeaderAttestation."""
        s = TimeStamper(enabled=True, server="https://example.test",
                        min_interval=0, proof_dir=proof_dir)

        def _litecoin(commitment):
            from opentimestamps.core.notary import LitecoinBlockHeaderAttestation
            from opentimestamps.core.timestamp import Timestamp
            ts = Timestamp(commitment)
            ts.attestations.add(LitecoinBlockHeaderAttestation(2000000))
            return ts

        submit, get_ts = _make_calendar_stub(_litecoin)
        with patch("opentimestamps.calendar.RemoteCalendar.submit", submit), \
                patch("opentimestamps.calendar.RemoteCalendar.get_timestamp", get_ts):
            path = s.stamp(b"ltc-data")
        info = s.proof_info(path)
        assert info["blockchain"] == "litecoin"
        assert any("LitecoinBlockHeaderAttestation" in a for a in info["attestations"])

    def test_describe_unknown_attestation(self):
        """_describe_attestation falls back to type name for unknown types."""
        class FakeAtt:
            pass

        assert TimeStamper._describe_attestation(FakeAtt()) == "FakeAtt"

    def test_blockchain_unknown_for_empty(self):
        """_blockchain_from_attestations returns unknown for no attestations."""
        assert TimeStamper._blockchain_from_attestations([]) == "unknown"

    def test_attestation_objects_non_tuple(self):
        """_attestation_objects handles non-tuple items (defensive)."""
        from src.time_stamper import _attestation_objects

        class StubTimestamp:
            def all_attestations(self):
                return iter([object()])

        result = _attestation_objects(StubTimestamp())  # type: ignore[arg-type]
        assert len(result) == 1

    def test_has_attestation_exception_returns_false(self):
        """_has_attestation returns False when all_attestations raises."""
        from src.time_stamper import _has_attestation

        class StubTimestamp:
            def all_attestations(self):
                raise RuntimeError("boom")

        assert _has_attestation(StubTimestamp()) is False  # type: ignore[arg-type]

    def test_ensure_proof_dir_oserror_logged(self, tmp_path):
        """An OSError creating the proof dir is logged, not raised."""
        target = tmp_path / "timestamps"
        s = TimeStamper(enabled=False, proof_dir=target)
        with patch.object(Path, "mkdir", side_effect=OSError("denied")):
            s._ensure_proof_dir()

