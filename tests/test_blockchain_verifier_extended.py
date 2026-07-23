"""
Extended tests for blockchain_verifier.py chain handlers and API fallbacks.

All network calls are mocked.
"""

import time
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.blockchain_verifier import BlockchainVerifier, BlockchainInfo
from src.config import BlockchainSettings


def make_mock_response(status_code=200, json_data=None, text=None):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {'content-type': 'application/json' if json_data else 'text/plain'}
    if json_data is not None:
        resp.json.return_value = json_data
    if text is not None:
        resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


class TestGetBitcoinInfo:
    """Test _get_bitcoin_info with mocked APIs."""

    def test_bitcoin_via_blockstream(self):
        """Bitcoin info from blockstream.info API."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)  # Wait for initial bg thread

        block_hash = "00000000000000000008a15c6c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4"
        with patch('requests.get') as mock_get:
            mock_get.side_effect = [
                make_mock_response(200, text=block_hash),
                make_mock_response(200, json_data={"height": 800000, "timestamp": 1700000000}),
            ]
            result = verifier._get_bitcoin_info()
            assert result is not None
            assert result.chain == "bitcoin"
            assert result.block_number == 800000
            assert result.block_hash == block_hash

    def test_bitcoin_blockstream_fails_mempool_succeeds(self):
        """Falls back to mempool.space when blockstream fails."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        block_hash = "00000000000000000008a15c"
        with patch('requests.get') as mock_get:
            mock_get.side_effect = [
                Exception("blockstream down"),
                make_mock_response(200, text=block_hash),
                make_mock_response(200, json_data={"height": 800001, "timestamp": 1700000001}),
            ]
            result = verifier._get_bitcoin_info()
            assert result is not None
            assert result.block_number == 800001

    def test_bitcoin_all_apis_fail(self):
        """Returns None when all APIs fail."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        with patch('requests.get', side_effect=Exception("network down")):
            result = verifier._get_bitcoin_info()
            assert result is None


class TestGetEthereumInfo:
    """Test _get_ethereum_info with mocked API."""

    def test_ethereum_success(self):
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        with patch('requests.get') as mock_get:
            mock_get.return_value = make_mock_response(200, json_data={
                "height": 18000000,
                "hash": "0x1234567890abcdef",
            })
            result = verifier._get_ethereum_info()
            assert result is not None
            assert result.chain == "ethereum"
            assert result.block_number == 18000000
            assert result.block_hash == "0x1234567890abcdef"

    def test_ethereum_failure(self):
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        with patch('requests.get', side_effect=Exception("API down")):
            result = verifier._get_ethereum_info()
            assert result is None


class TestGetLitecoinInfo:
    """Test _get_litecoin_info with mocked API."""

    def test_litecoin_success(self):
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        with patch('requests.get') as mock_get:
            mock_get.return_value = make_mock_response(200, json_data={
                "height": 2400000,
                "hash": "litecoinhash123",
            })
            result = verifier._get_litecoin_info()
            assert result is not None
            assert result.chain == "litecoin"
            assert result.block_number == 2400000

    def test_litecoin_failure(self):
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        with patch('requests.get', side_effect=Exception("API down")):
            result = verifier._get_litecoin_info()
            assert result is None


class TestMakeRequestWithFallback:
    """Test _make_request_with_fallback."""

    def test_first_endpoint_succeeds(self):
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        mock_session = MagicMock()
        mock_session.get.return_value = make_mock_response(200, json_data={"key": "val"})
        verifier._session = mock_session
        result = verifier._make_request_with_fallback("bitcoin", "/tip/hash")
        assert result == {"key": "val"}

    def test_first_fails_second_succeeds(self):
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        mock_session = MagicMock()
        mock_session.get.side_effect = [
            Exception("first endpoint down"),
            make_mock_response(200, json_data={"key": "val"}),
        ]
        verifier._session = mock_session
        result = verifier._make_request_with_fallback("bitcoin", "/tip/hash")
        assert result == {"key": "val"}

    def test_all_endpoints_fail(self):
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("all down")
        verifier._session = mock_session
        result = verifier._make_request_with_fallback("bitcoin", "/tip/hash")
        assert result is None

    def test_text_response(self):
        """Non-JSON response returns as text."""
        settings = BlockchainSettings(enabled_chains=set())
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {'content-type': 'text/plain'}
        resp.text = "  plain text  "
        resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = resp
        verifier._session = mock_session
        result = verifier._make_request_with_fallback("bitcoin")
        assert result == {"text": "plain text"}


class TestUpdateAllChainsSafe:
    """Test _update_all_chains_safe clears _updating flag."""

    def test_clears_updating_flag_on_success(self):
        settings = BlockchainSettings(enabled_chains={"bitcoin"})
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        verifier._updating = True
        mock_info = BlockchainInfo(
            chain="bitcoin", block_number=1, block_hash="a",
            timestamp=datetime.now(timezone.utc), retrieved_at=time.time(),
        )
        verifier.chain_handlers["bitcoin"] = MagicMock(return_value=mock_info)
        verifier._update_all_chains_safe()
        assert verifier._updating is False

    def test_clears_updating_flag_on_failure(self):
        settings = BlockchainSettings(enabled_chains={"bitcoin"})
        verifier = BlockchainVerifier(settings)
        time.sleep(0.3)

        verifier._updating = True
        verifier.chain_handlers["bitcoin"] = MagicMock(side_effect=Exception("fail"))
        verifier._update_all_chains_safe()
        assert verifier._updating is False
