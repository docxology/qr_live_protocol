"""
Blockchain Verifier module for QRLP.

Retrieves recent block hashes from blockchain services for contextual
comparison against QR payloads.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from .config import DEFAULT_BLOCKCHAIN_API_ENDPOINTS, BlockchainSettings

_logger = logging.getLogger("qrlp.blockchain")
_BITCOIN_FALLBACKS = ("https://mempool.space/api", "https://api.blockcypher.com/v1/btc/main")
_LEGACY_ETHEREUM_ENDPOINT = "https://api.etherscan.io/api"
_BLOCK_HASH_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


def _provider_url(endpoint: str, suffix: str = "") -> str:
    """Append a provider path ahead of the existing query, if any."""
    if not isinstance(endpoint, str):
        raise ValueError("Provider endpoint must be an HTTP(S) URL")
    parts = urlsplit(endpoint)
    if parts.scheme not in {"https", "http"} or not parts.hostname or parts.fragment:
        raise ValueError("Provider endpoint must be an HTTP(S) URL without a fragment")
    if not suffix:
        return endpoint
    return urlunsplit(parts._replace(path=parts.path.rstrip("/") + suffix))


def _tip_hash(value: Any, *, ethereum: bool = False) -> str:
    """Validate a provider hash before recording it or using it as a URL segment."""
    if isinstance(value, str):
        candidate = value.removeprefix("0x") if ethereum else value
        if _BLOCK_HASH_PATTERN.fullmatch(candidate):
            return value
    raise ValueError("Invalid provider block hash")


def _tip_height(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Invalid provider block height")
    return value


@dataclass
class BlockchainInfo:
    """Information about a blockchain block."""
    chain: str
    block_number: int
    block_hash: str
    timestamp: datetime
    retrieved_at: float
    confirmations: int = 0


class BlockchainVerifier:
    """
    Blockchain verification provider for QRLP.
    
    Retrieves recent block hashes for a current-tip comparison. Establishing
    an independent proof requires additional chain data and verification.
    """

    def __init__(self, settings: BlockchainSettings):
        """
        Initialize blockchain verifier with settings.
        
        Args:
            settings: BlockchainSettings configuration object
        """
        self.settings = settings
        self.cached_blocks: dict[str, BlockchainInfo] = {}
        self.last_update: dict[str, float] = {}
        self.update_lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        self._updating = False
        self._last_refresh_attempt: float | None = None

        # Connection pool for keep-alive HTTP
        self._session: requests.Session | None = None

        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.cache_hits = 0

        # Initialize supported chains with multiple API endpoints for redundancy
        self.chain_handlers = {
            'bitcoin': self._get_bitcoin_info,
            'ethereum': self._get_ethereum_info,
            'litecoin': self._get_litecoin_info,
        }

        self.api_endpoints = {
            chain: [settings.api_endpoints.get(chain, default)]
            for chain, default in DEFAULT_BLOCKCHAIN_API_ENDPOINTS.items()
        }
        bitcoin = self.api_endpoints["bitcoin"][0]
        if isinstance(bitcoin, str) and bitcoin.rstrip("/") == DEFAULT_BLOCKCHAIN_API_ENDPOINTS["bitcoin"]:
            self.api_endpoints["bitcoin"].extend(_BITCOIN_FALLBACKS)
        ethereum = self.api_endpoints["ethereum"][0]
        if isinstance(ethereum, str) and ethereum.rstrip("/") == _LEGACY_ETHEREUM_ENDPOINT:
            # Older generated configurations listed Etherscan, but the
            # Ethereum reader has always used the BlockCypher chain schema.
            self.api_endpoints["ethereum"] = [DEFAULT_BLOCKCHAIN_API_ENDPOINTS["ethereum"]]

        self._update_if_needed()

    def get_blockchain_hashes(self) -> dict[str, str]:
        """Return fresh, cached hashes for the enabled chains."""
        return {chain: block.block_hash for chain, block in self.get_all_blockchain_info().items()}

    def get_blockchain_info(self, chain: str) -> BlockchainInfo | None:
        """
        Get detailed blockchain information for a specific chain.
        
        Args:
            chain: Blockchain name (bitcoin, ethereum, etc.)
            
        Returns:
            BlockchainInfo object or None if not available
        """
        self._update_if_needed()
        block = self.cached_blocks.get(chain)
        if block is not None and self._fresh(block, time.time()):
            return block
        return None

    def get_all_blockchain_info(self) -> dict[str, BlockchainInfo]:
        """Get detailed information for all cached blockchains."""
        self._update_if_needed()
        now = time.time()
        return {
            chain: info for chain, info in self.cached_blocks.copy().items()
            if chain in self.settings.enabled_chains and self._fresh(info, now)
        }

    def _fresh(self, block: BlockchainInfo, now: float) -> bool:
        return 0 <= now - block.retrieved_at <= self.settings.cache_duration

    def verify_blockchain_hash(self, chain: str, block_hash: str, tolerance_blocks: int = 10) -> dict[str, Any]:
        """
        Verify if a blockchain hash is recent and valid.
        
        Args:
            chain: Blockchain name
            block_hash: Hash to verify
            tolerance_blocks: How many blocks back to consider valid
            
        Returns:
            Dictionary with verification results
        """
        try:
            current_info = self.get_blockchain_info(chain)
            if not current_info:
                return {
                    "valid": False,
                    "error": f"No current data for {chain}"
                }

            # For simplicity, just check if hash matches recent blocks
            # In practice, you'd need to check the actual blockchain
            is_current = current_info.block_hash == block_hash

            return {
                "valid": is_current,
                "chain": chain,
                "given_hash": block_hash,
                "current_hash": current_info.block_hash,
                "current_block": current_info.block_number,
                "block_age_seconds": time.time() - current_info.retrieved_at
            }

        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

    def force_update(self, chain: str | None = None) -> bool:
        """
        Force update of blockchain data.
        
        Args:
            chain: Specific chain to update, or None for all chains
            
        Returns:
            True if update was successful
        """
        if chain:
            return self._update_chain(chain)
        else:
            return self._update_all_chains()

    def get_statistics(self) -> dict:
        """Get blockchain verifier statistics."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "cache_hits": self.cache_hits,
            "success_rate": self.successful_requests / max(1, self.total_requests),
            "cached_chains": list(self.cached_blocks.keys()),
            "last_updates": self.last_update.copy()
        }

    def _update_if_needed(self) -> None:
        """Schedule at most one refresh, throttling attempts during an outage."""
        with self._refresh_lock:
            if self._updating or not self.settings.enabled_chains:
                return
            if self._last_refresh_attempt is not None and time.monotonic() - self._last_refresh_attempt < 1:
                return
            now = time.time()
            if all(
                (block := self.cached_blocks.get(chain)) is not None and self._fresh(block, now)
                for chain in self.settings.enabled_chains
            ):
                return

            self._updating = True
            worker = threading.Thread(target=self._update_all_chains_safe, daemon=True)
            try:
                worker.start()
            except RuntimeError:
                self._updating = False
                raise

    def _update_all_chains_safe(self) -> None:
        """Keep refresh admission closed until the worker actually finishes."""
        try:
            self._update_all_chains()
        finally:
            with self._refresh_lock:
                self._last_refresh_attempt = time.monotonic()
                self._updating = False

    def _update_all_chains(self) -> bool:
        """Update all enabled blockchain chains."""
        success_count = 0

        for chain in self.settings.enabled_chains.copy():
            try:
                if self._update_chain(chain):
                    success_count += 1
            except Exception:
                _logger.warning("Blockchain refresh failed for %s", chain)
                # Continue with other chains even if one fails
                continue

        return success_count > 0

    def _update_chain(self, chain: str) -> bool:
        """
        Update blockchain data for a specific chain.
        
        Args:
            chain: Chain name to update
            
        Returns:
            True if successful
        """
        if not self.update_lock.acquire(blocking=False):
            return False  # Another worker owns this request.

        try:
            self.total_requests += 1

            if chain in self.chain_handlers:
                block_info = self.chain_handlers[chain]()
                if block_info:
                    self.cached_blocks[chain] = block_info
                    self.last_update[chain] = time.time()
                    self.successful_requests += 1
                    return True

            self.failed_requests += 1
            return False

        finally:
            self.update_lock.release()

    def _get_session(self) -> requests.Session:
        """Return a cached requests.Session for keep-alive connection pooling."""
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _make_request_with_fallback(self, chain: str, path: str = "") -> dict | None:
        """Make API request with fallback to multiple endpoints."""
        endpoints = self.api_endpoints.get(chain, [])
        session = self._get_session()

        for endpoint in endpoints:
            try:
                url = _provider_url(endpoint, path)
                response = session.get(url, timeout=self.settings.timeout)
                response.raise_for_status()

                # Handle different response types
                if response.headers.get('content-type', '').startswith('application/json'):
                    return response.json()
                else:
                    return {"text": response.text.strip()}

            except Exception:
                _logger.warning("Blockchain provider request failed")

        return None

    def _get_bitcoin_info(self) -> BlockchainInfo | None:
        """Read a Bitcoin tip from the configured Esplora base or default fallbacks."""
        for attempt, endpoint in enumerate(self.api_endpoints["bitcoin"], start=1):
            try:
                if isinstance(endpoint, str) and endpoint.rstrip("/") == _BITCOIN_FALLBACKS[-1]:
                    return self._read_blockcypher_tip("bitcoin", endpoint)
                return self._read_esplora_tip(endpoint)
            except Exception:
                _logger.warning("Bitcoin provider attempt %d failed", attempt)
        return None

    def _read_esplora_tip(self, endpoint: str) -> BlockchainInfo:
        tip = self._request_tip(endpoint, "/blocks/tip/hash")
        block_hash = _tip_hash(tip.text.strip())
        block = self._request_tip(endpoint, f"/block/{block_hash}").json()
        if "id" in block and _tip_hash(block["id"]).lower() != block_hash.lower():
            raise ValueError("Block details do not match the requested tip hash")
        timestamp = block["timestamp"]
        if type(timestamp) is not int or timestamp < 0:
            raise ValueError("Invalid provider block timestamp")
        return BlockchainInfo(
            chain="bitcoin",
            block_number=_tip_height(block["height"]),
            block_hash=block_hash,
            timestamp=datetime.fromtimestamp(timestamp, UTC),
            retrieved_at=time.time(),
        )

    def _get_ethereum_info(self) -> BlockchainInfo | None:
        """Read the Ethereum tip using the configured chain-info URL."""
        return self._get_blockcypher_info("ethereum")

    def _get_litecoin_info(self) -> BlockchainInfo | None:
        """Read the Litecoin tip using the configured chain-info URL."""
        return self._get_blockcypher_info("litecoin")

    def _get_blockcypher_info(self, chain: str) -> BlockchainInfo | None:
        try:
            return self._read_blockcypher_tip(chain, self.api_endpoints[chain][0])
        except Exception:
            _logger.warning("%s provider request failed", chain.title())
            return None

    def _read_blockcypher_tip(self, chain: str, endpoint: str) -> BlockchainInfo:
        data = self._request_tip(endpoint).json()
        return BlockchainInfo(
            chain=chain,
            block_number=_tip_height(data["height"]),
            block_hash=_tip_hash(data["hash"], ethereum=chain == "ethereum"),
            timestamp=datetime.now(UTC),
            retrieved_at=time.time(),
        )

    def _request_tip(self, endpoint: str, path: str = "") -> requests.Response:
        response = requests.get(_provider_url(endpoint, path), timeout=self.settings.timeout)
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected provider status")
        return response
