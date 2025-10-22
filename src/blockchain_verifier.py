"""
Blockchain Verifier module for QRLP.

Handles blockchain verification by retrieving current block hashes
from multiple blockchain networks to provide tamper-evident timestamps.
"""

import time
import hashlib
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import requests
from dataclasses import dataclass, asdict

from .config import BlockchainSettings


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
    
    Retrieves current block hashes from multiple blockchain networks
    to provide cryptographic proof of time and immutable verification.
    """
    
    def __init__(self, settings: BlockchainSettings):
        """
        Initialize blockchain verifier with settings.
        
        Args:
            settings: BlockchainSettings configuration object
        """
        self.settings = settings
        self.cached_blocks: Dict[str, BlockchainInfo] = {}
        self.last_update: Dict[str, float] = {}
        self.update_lock = threading.Lock()
        
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
        
        # Perform initial update in background
        threading.Thread(target=self._initial_update, daemon=True).start()
    
    def _initial_update(self):
        """Perform initial blockchain data update."""
        try:
            self._update_all_chains()
        except Exception as e:
            print(f"Initial blockchain update warning: {e}")
    
    def get_blockchain_hashes(self) -> Dict[str, str]:
        """
        Get current blockchain hashes for all enabled chains.
        
        Returns:
            Dictionary mapping chain names to block hashes
        """
        self._update_if_needed()
        
        hashes = {}
        for chain, block_info in self.cached_blocks.items():
            if chain in self.settings.enabled_chains:
                hashes[chain] = block_info.block_hash
        
        return hashes
    
    def get_blockchain_info(self, chain: str) -> Optional[BlockchainInfo]:
        """
        Get detailed blockchain information for a specific chain.
        
        Args:
            chain: Blockchain name (bitcoin, ethereum, etc.)
            
        Returns:
            BlockchainInfo object or None if not available
        """
        self._update_if_needed()
        return self.cached_blocks.get(chain)
    
    def get_all_blockchain_info(self) -> Dict[str, BlockchainInfo]:
        """Get detailed information for all cached blockchains."""
        self._update_if_needed()
        return {
            chain: info for chain, info in self.cached_blocks.items()
            if chain in self.settings.enabled_chains
        }
    
    def verify_blockchain_hash(self, chain: str, block_hash: str, tolerance_blocks: int = 10) -> Dict[str, Any]:
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
    
    def force_update(self, chain: Optional[str] = None) -> bool:
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
    
    def get_statistics(self) -> Dict:
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
        """Update blockchain data if cache is stale."""
        current_time = time.time()

        # Check if any chain needs updating
        needs_update = False
        for chain in self.settings.enabled_chains:
            last_update = self.last_update.get(chain, 0)
            if current_time - last_update > self.settings.cache_duration:
                needs_update = True
                break

        # Only update if needed and not already updating
        if needs_update and not hasattr(self, '_updating'):
            self._updating = True
            try:
                # Use a single thread to update all chains sequentially
                threading.Thread(target=self._update_all_chains, daemon=True).start()
            finally:
                # Reset the flag after a delay to prevent rapid-fire updates
                threading.Timer(1.0, lambda: setattr(self, '_updating', False) if hasattr(self, '_updating') else None).start()
    
    def _update_all_chains(self) -> bool:
        """Update all enabled blockchain chains."""
        success_count = 0
        
        for chain in self.settings.enabled_chains:
            try:
                if self._update_chain(chain):
                    success_count += 1
            except Exception as e:
                print(f"{chain.title()} API error: {e}")
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
            self.cache_hits += 1
            return True  # Another thread is updating
        
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
    
    def _make_request_with_fallback(self, chain: str, path: str = "") -> Optional[Dict]:
        """Make API request with fallback to multiple endpoints."""
        endpoints = self.api_endpoints.get(chain, [])
        
        for endpoint in endpoints:
            try:
                url = f"{endpoint}{path}"
                response = requests.get(url, timeout=self.settings.timeout)
                response.raise_for_status()
                
                # Handle different response types
                if response.headers.get('content-type', '').startswith('application/json'):
                    return response.json()
                else:
                    return {"text": response.text.strip()}
                    
            except Exception as e:
                print(f"API request failed for {endpoint}: {e}")
                continue
        
        return None
    
    def _get_bitcoin_info(self) -> Optional[BlockchainInfo]:
        """Get Bitcoin blockchain information with improved API handling."""
        try:
            # Try blockstream.info API first
            try:
                # Get latest block
                response = requests.get("https://blockstream.info/api/blocks/tip/hash", timeout=5)
                if response.status_code == 200:
                    block_hash = response.text.strip()

                    # Get block details
                    block_response = requests.get(f"https://blockstream.info/api/block/{block_hash}", timeout=5)
                    if block_response.status_code == 200:
                        block_data = block_response.json()

                        return BlockchainInfo(
                            chain="bitcoin",
                            block_number=block_data["height"],
                            block_hash=block_hash,
                            timestamp=datetime.fromtimestamp(block_data["timestamp"], timezone.utc),
                            retrieved_at=time.time()
                        )
            except Exception as e:
                print(f"Blockstream.info API failed: {e}")

            # Fallback to mempool.space
            try:
                response = requests.get("https://mempool.space/api/blocks/tip/hash", timeout=5)
                if response.status_code == 200:
                    block_hash = response.text.strip()

                    block_response = requests.get(f"https://mempool.space/api/block/{block_hash}", timeout=5)
                    if block_response.status_code == 200:
                        block_data = block_response.json()

                        return BlockchainInfo(
                            chain="bitcoin",
                            block_number=block_data["height"],
                            block_hash=block_hash,
                            timestamp=datetime.fromtimestamp(block_data["timestamp"], timezone.utc),
                            retrieved_at=time.time()
                        )
            except Exception as e:
                print(f"Mempool.space API failed: {e}")
            
            # Final fallback to blockcypher
            try:
                response = requests.get("https://api.blockcypher.com/v1/btc/main", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    
                    return BlockchainInfo(
                        chain="bitcoin",
                        block_number=data["height"],
                        block_hash=data["hash"],
                        timestamp=datetime.now(timezone.utc),
                        retrieved_at=time.time()
                    )
            except Exception:
                pass
            
            print("All Bitcoin API endpoints failed")
            return None
            
        except Exception as e:
            print(f"Bitcoin API error: {e}")
            return None
    
    def _get_ethereum_info(self) -> Optional[BlockchainInfo]:
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
                    timestamp=datetime.now(timezone.utc),
                    retrieved_at=time.time()
                )
            
            print("Ethereum API request failed")
            return None
            
        except Exception as e:
            print(f"Ethereum API error: {e}")
            return None
    
    def _get_litecoin_info(self) -> Optional[BlockchainInfo]:
        """Get Litecoin blockchain information."""
        try:
            response = requests.get("https://api.blockcypher.com/v1/ltc/main", timeout=self.settings.timeout)
            if response.status_code == 200:
                data = response.json()
                
                return BlockchainInfo(
                    chain="litecoin",
                    block_number=data["height"],
                    block_hash=data["hash"],
                    timestamp=datetime.now(timezone.utc),
                    retrieved_at=time.time()
                )
            
            print("Litecoin API request failed")
            return None
            
        except Exception as e:
            print(f"Litecoin API error: {e}")
            return None 