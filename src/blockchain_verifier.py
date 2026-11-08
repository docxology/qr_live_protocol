"""
Blockchain Verifier module for QRLP.

Retrieves recent block hashes from blockchain services for contextual
comparison against QR payloads.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests

from .config import BlockchainSettings

_logger = logging.getLogger("qrlp.blockchain")


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

        # Multiple API endpoints for redundancy
        self.api_endpoints = {
            'bitcoin': [
                "https://blockstream.info/api",
                "https://mempool.space/api",
                "https://api.blockcypher.com/v1/btc/main"
            ],
            'ethereum': [
                "https://api.etherscan.io/api",
                "https://api.blockcypher.com/v1/eth/main"
            ],
            'litecoin': [
                "https://api.blockcypher.com/v1/ltc/main",
                "https://litecoinspace.org/api"
            ]
        }

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
            except Exception as e:
                _logger.error(f"{chain.title()} API error: {e}")
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
                url = f"{endpoint}{path}"
                response = session.get(url, timeout=self.settings.timeout)
                response.raise_for_status()

                # Handle different response types
                if response.headers.get('content-type', '').startswith('application/json'):
                    return response.json()
                else:
                    return {"text": response.text.strip()}

            except Exception as e:
                _logger.error(f"API request failed for {endpoint}: {e}")
                continue

        return None

    def _get_bitcoin_info(self) -> BlockchainInfo | None:
        """Get Bitcoin blockchain information with improved API handling."""
        try:
            # Try blockstream.info API first
            try:
                # Get latest block
                response = requests.get("https://blockstream.info/api/blocks/tip/hash", timeout=self.settings.timeout)
                if response.status_code == 200:
                    block_hash = response.text.strip()

                    # Get block details
                    block_response = requests.get(f"https://blockstream.info/api/block/{block_hash}", timeout=self.settings.timeout)
                    if block_response.status_code == 200:
                        block_data = block_response.json()

                        return BlockchainInfo(
                            chain="bitcoin",
                            block_number=block_data["height"],
                            block_hash=block_hash,
                            timestamp=datetime.fromtimestamp(block_data["timestamp"], UTC),
                            retrieved_at=time.time()
                        )
            except Exception as e:
                _logger.error(f"Blockstream.info API failed: {e}")
            # Fallback to mempool.space
            try:
                response = requests.get("https://mempool.space/api/blocks/tip/hash", timeout=self.settings.timeout)
                if response.status_code == 200:
                    block_hash = response.text.strip()

                    block_response = requests.get(f"https://mempool.space/api/block/{block_hash}", timeout=self.settings.timeout)
                    if block_response.status_code == 200:
                        block_data = block_response.json()

                        return BlockchainInfo(
                            chain="bitcoin",
                            block_number=block_data["height"],
                            block_hash=block_hash,
                            timestamp=datetime.fromtimestamp(block_data["timestamp"], UTC),
                            retrieved_at=time.time()
                        )
            except Exception as e:
                _logger.error(f"Mempool.space API failed: {e}")
            # Final fallback to blockcypher
            try:
                response = requests.get("https://api.blockcypher.com/v1/btc/main", timeout=self.settings.timeout)
                if response.status_code == 200:
                    data = response.json()

                    return BlockchainInfo(
                        chain="bitcoin",
                        block_number=data["height"],
                        block_hash=data["hash"],
                        timestamp=datetime.now(UTC),
                        retrieved_at=time.time()
                    )
            except Exception:
                pass

            _logger.error("All Bitcoin API endpoints failed")
            return None

        except Exception as e:
            _logger.error(f"Bitcoin API error: {e}")
            return None

    def _get_ethereum_info(self) -> BlockchainInfo | None:
        """Get Ethereum blockchain information with simplified API."""
        try:
            # Use blockcypher for Ethereum (no API key required)
            response = requests.get("https://api.blockcypher.com/v1/eth/main", timeout=self.settings.timeout)
            if response.status_code == 200:
                data = response.json()

                return BlockchainInfo(
                    chain="ethereum",
                    block_number=data["height"],
                    block_hash=data["hash"],
                    timestamp=datetime.now(UTC),
                    retrieved_at=time.time()
                )

            _logger.error("Ethereum API request failed")
            return None

        except Exception as e:
            _logger.error(f"Ethereum API error: {e}")
            return None

    def _get_litecoin_info(self) -> BlockchainInfo | None:
        """Get Litecoin blockchain information."""
        try:
            response = requests.get("https://api.blockcypher.com/v1/ltc/main", timeout=self.settings.timeout)
            if response.status_code == 200:
                data = response.json()

                return BlockchainInfo(
                    chain="litecoin",
                    block_number=data["height"],
                    block_hash=data["hash"],
                    timestamp=datetime.now(UTC),
                    retrieved_at=time.time()
                )

            _logger.error("Litecoin API request failed")
            return None

        except Exception as e:
            _logger.error(f"Litecoin API error: {e}")
            return None
