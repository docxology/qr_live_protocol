"""
Extended tests for blockchain_verifier.py chain handlers and API fallbacks.

All network calls are mocked.
"""

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, call, patch

import pytest

from src.blockchain_verifier import BlockchainInfo, BlockchainVerifier
from src.config import BlockchainSettings


BLOCK_HASH = '0' * 16 + 'a5' * 24


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

        block_hash = BLOCK_HASH
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

        block_hash = BLOCK_HASH
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
                "hash": "0x" + BLOCK_HASH,
            })
            result = verifier._get_ethereum_info()
            assert result is not None
            assert result.chain == "ethereum"
            assert result.block_number == 18000000
            assert result.block_hash == "0x" + BLOCK_HASH

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
                "hash": BLOCK_HASH,
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
            timestamp=datetime.now(UTC), retrieved_at=time.time(),
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


def test_default_bitcoin_uses_blockcypher_after_esplora_failures():
    settings = BlockchainSettings(enabled_chains=set(), api_endpoints={})
    verifier = BlockchainVerifier(settings)
    with patch("requests.get", side_effect=[
        make_mock_response(503),
        make_mock_response(503),
        make_mock_response(200, json_data={"height": 800002, "hash": BLOCK_HASH}),
    ]) as mock_get:
        assert verifier.force_update("bitcoin")
    assert verifier.cached_blocks["bitcoin"].block_hash == BLOCK_HASH
    assert mock_get.call_args_list == [
        call("https://blockstream.info/api/blocks/tip/hash", timeout=settings.timeout),
        call("https://mempool.space/api/blocks/tip/hash", timeout=settings.timeout),
        call("https://api.blockcypher.com/v1/btc/main", timeout=settings.timeout),
    ]


def test_configured_esplora_base_preserves_auth_query_after_path():
    settings = BlockchainSettings(
        enabled_chains=set(),
        api_endpoints={"bitcoin": "https://mirror.example.test/prefix/api/?token=fixture%2F"},
    )
    verifier = BlockchainVerifier(settings)
    with patch("requests.get", side_effect=[
        make_mock_response(200, text=BLOCK_HASH + "\n"),
        make_mock_response(200, json_data={"id": BLOCK_HASH, "height": 800003, "timestamp": 1700000000}),
    ]) as mock_get:
        assert verifier.force_update("bitcoin")
    assert mock_get.call_args_list == [
        call("https://mirror.example.test/prefix/api/blocks/tip/hash?token=fixture%2F", timeout=settings.timeout),
        call(f"https://mirror.example.test/prefix/api/block/{BLOCK_HASH}?token=fixture%2F", timeout=settings.timeout),
    ]


def test_custom_bitcoin_failure_neither_falls_back_nor_logs_url(caplog):
    endpoint = "https://user:fixture-password@mirror.example.test/api?token=fixture-key"
    settings = BlockchainSettings(enabled_chains=set(), api_endpoints={"bitcoin": endpoint})
    verifier = BlockchainVerifier(settings)
    with patch("requests.get", side_effect=Exception(f"Failed request: {endpoint}")) as mock_get:
        assert not verifier.force_update("bitcoin")
    mock_get.assert_called_once()
    assert "Bitcoin provider attempt 1 failed" in caplog.text
    assert "fixture-password" not in caplog.text
    assert "fixture-key" not in caplog.text


def test_esplora_does_not_use_unvalidated_tip_as_a_path():
    settings = BlockchainSettings(
        enabled_chains=set(), api_endpoints={"bitcoin": "https://mirror.example.test/api"},
    )
    verifier = BlockchainVerifier(settings)
    with patch("requests.get", return_value=make_mock_response(200, text="../other")) as mock_get:
        assert not verifier.force_update("bitcoin")
    mock_get.assert_called_once_with("https://mirror.example.test/api/blocks/tip/hash", timeout=settings.timeout)


@pytest.mark.parametrize(("chain", "endpoint"), [
    ("ethereum", "https://api.blockcypher.com/v1/eth/main"),
    ("litecoin", "https://api.blockcypher.com/v1/ltc/main"),
])
def test_default_chain_info_url(chain, endpoint):
    settings = BlockchainSettings(enabled_chains=set())
    verifier = BlockchainVerifier(settings)
    with patch("requests.get", return_value=make_mock_response(
        200, json_data={"height": 800000, "hash": BLOCK_HASH},
    )) as mock_get:
        assert verifier.force_update(chain)
    mock_get.assert_called_once_with(endpoint, timeout=settings.timeout)


def test_legacy_generated_etherscan_setting_uses_existing_effective_provider():
    settings = BlockchainSettings(
        enabled_chains=set(), api_endpoints={"ethereum": "https://api.etherscan.io/api"},
    )
    verifier = BlockchainVerifier(settings)
    with patch("requests.get", return_value=make_mock_response(
        200, json_data={"height": 18000001, "hash": BLOCK_HASH},
    )) as mock_get:
        assert verifier.force_update("ethereum")
    mock_get.assert_called_once_with("https://api.blockcypher.com/v1/eth/main", timeout=settings.timeout)


@pytest.mark.parametrize("chain", ["ethereum", "litecoin"])
def test_configured_chain_info_url_is_used_without_rewriting(chain):
    endpoint = f"https://mirror.example.test/{chain}/chain-info/?token=fixture"
    settings = BlockchainSettings(enabled_chains=set(), api_endpoints={chain: endpoint})
    verifier = BlockchainVerifier(settings)
    with patch("requests.get", return_value=make_mock_response(
        200, json_data={"height": 800000, "hash": BLOCK_HASH},
    )) as mock_get:
        assert verifier.force_update(chain)
    assert verifier.cached_blocks[chain].block_hash == BLOCK_HASH
    mock_get.assert_called_once_with(endpoint, timeout=settings.timeout)
