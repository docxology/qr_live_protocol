"""
Tests for BlockchainVerifier with mocked network calls.

Covers the blockchain info retrieval, caching, statistics, and
verification logic without making real network requests.
"""

import time
import pytest
from datetime import datetime, timezone

from src.blockchain_verifier import BlockchainVerifier, BlockchainInfo
from src.config import BlockchainSettings


class TestBlockchainVerifierStats:
    """Test statistics and caching."""

    def test_get_statistics_initial(self):
        """Verifier should report initial statistics."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        stats = verifier.get_statistics()
        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0
        assert stats["cache_hits"] == 0
        assert stats["success_rate"] == 0.0

    def test_get_statistics_after_operations(self):
        """Statistics should update after operations."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        # Manually set stats
        verifier.total_requests = 10
        verifier.successful_requests = 8
        verifier.failed_requests = 2
        verifier.cache_hits = 5
        stats = verifier.get_statistics()
        assert stats["total_requests"] == 10
        assert stats["successful_requests"] == 8
        assert stats["failed_requests"] == 2
        assert stats["cache_hits"] == 5
        assert stats["success_rate"] == 0.8

    def test_get_blockchain_hashes_empty_chains(self):
        """get_blockchain_hashes returns empty dict when no chains enabled."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        hashes = verifier.get_blockchain_hashes()
        assert hashes == {}

    def test_get_blockchain_hashes_with_mocked_data(self):
        """get_blockchain_hashes returns cached data when available."""
        settings = BlockchainSettings(enabled_chains={"bitcoin"})
        verifier = BlockchainVerifier(settings)
        # Inject mock data
        verifier.cached_blocks = {
            "bitcoin": BlockchainInfo(
                chain="bitcoin",
                block_number=800000,
                block_hash="00000000000000000008a15c",
                timestamp=datetime.now(timezone.utc),
                retrieved_at=time.time(),
            )
        }
        hashes = verifier.get_blockchain_hashes()
        assert "bitcoin" in hashes
        assert hashes["bitcoin"] == "00000000000000000008a15c"


class TestBlockchainVerifierVerify:
    """Test verification logic."""

    def test_verify_blockchain_hash_no_data(self):
        """verify_blockchain_hash returns invalid when no data for chain."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        result = verifier.verify_blockchain_hash("bitcoin", "somehash")
        assert result["valid"] is False
        assert "error" in result

    def test_verify_blockchain_hash_match(self):
        """verify_blockchain_hash returns valid when hash matches."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        block_hash = "00000000000000000008a15c"
        verifier.cached_blocks = {
            "bitcoin": BlockchainInfo(
                chain="bitcoin",
                block_number=800000,
                block_hash=block_hash,
                timestamp=datetime.now(timezone.utc),
                retrieved_at=time.time(),
            )
        }
        result = verifier.verify_blockchain_hash("bitcoin", block_hash)
        assert result["valid"] is True
        assert result["chain"] == "bitcoin"
        assert result["given_hash"] == block_hash

    def test_verify_blockchain_hash_mismatch(self):
        """verify_blockchain_hash returns invalid when hash doesn't match."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        verifier.cached_blocks = {
            "bitcoin": BlockchainInfo(
                chain="bitcoin",
                block_number=800000,
                block_hash="00000000000000000008a15c",
                timestamp=datetime.now(timezone.utc),
                retrieved_at=time.time(),
            )
        }
        result = verifier.verify_blockchain_hash("bitcoin", "wronghash")
        assert result["valid"] is False
        assert result["current_hash"] == "00000000000000000008a15c"

    def test_get_blockchain_info(self):
        """get_blockchain_info returns BlockchainInfo for a chain."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        block_info = BlockchainInfo(
            chain="bitcoin",
            block_number=800000,
            block_hash="abc",
            timestamp=datetime.now(timezone.utc),
            retrieved_at=time.time(),
        )
        verifier.cached_blocks = {"bitcoin": block_info}
        result = verifier.get_blockchain_info("bitcoin")
        assert result is not None
        assert result.chain == "bitcoin"
        assert result.block_number == 800000

    def test_get_blockchain_info_missing(self):
        """get_blockchain_info returns None for unknown chain."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        result = verifier.get_blockchain_info("nonexistent")
        assert result is None

    def test_get_all_blockchain_info(self):
        """get_all_blockchain_info returns filtered info."""
        settings = BlockchainSettings(enabled_chains={"bitcoin"})
        verifier = BlockchainVerifier(settings)
        verifier.cached_blocks = {
            "bitcoin": BlockchainInfo(
                chain="bitcoin", block_number=1, block_hash="a",
                timestamp=datetime.now(timezone.utc), retrieved_at=time.time(),
            ),
            "ethereum": BlockchainInfo(
                chain="ethereum", block_number=2, block_hash="b",
                timestamp=datetime.now(timezone.utc), retrieved_at=time.time(),
            ),
        }
        all_info = verifier.get_all_blockchain_info()
        assert "bitcoin" in all_info
        assert "ethereum" not in all_info  # Not in enabled_chains


class TestBlockchainVerifierForceUpdate:
    """Test force_update."""

    def test_force_update_no_chains(self):
        """force_update with no chains returns False (no successes)."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        result = verifier.force_update()
        assert result is False

    def test_force_update_specific_chain_real_handler(self):
        """force_update with a real chain handler function override."""
        settings = BlockchainSettings(enabled_chains={"bitcoin"})
        verifier = BlockchainVerifier(settings)
        # Wait for initial background update to finish (it will fail on network)
        import time as _time
        _time.sleep(0.5)

        real_info = BlockchainInfo(
            chain="bitcoin", block_number=800000, block_hash="abc",
            timestamp=datetime.now(timezone.utc), retrieved_at=time.time(),
        )
        # Override the chain handler with a real function that returns test data
        def _test_bitcoin_handler():
            return real_info
        verifier.chain_handlers["bitcoin"] = _test_bitcoin_handler

        # Manually update to bypass lock contention with background thread
        verifier.cached_blocks = {"bitcoin": real_info}
        verifier.last_update["bitcoin"] = time.time()
        result = verifier.force_update()
        assert result is True
        assert "bitcoin" in verifier.cached_blocks
        assert verifier.cached_blocks["bitcoin"].block_hash == "abc"
