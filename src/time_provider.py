"""
Time Provider module for QRLP.

Handles time synchronization with multiple time servers and provides
accurate timestamp verification for QR codes.
"""

import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
import requests
import ntplib
from dataclasses import dataclass

from .config import TimeSettings

_logger = logging.getLogger("qrlp.time")



@dataclass
class TimeServerResponse:
    """Response from a time server."""
    server: str
    timestamp: float
    offset: float
    delay: float
    stratum: int
    success: bool
    error: Optional[str] = None


class TimeProvider:
    """
    Time synchronization provider for QRLP.

    Manages multiple time sources and provides accurate timestamps
    with verification capabilities for livestreaming authenticity.
    """

    def __init__(self, settings: TimeSettings):
        """
        Initialize time provider with settings.

        Args:
            settings: TimeSettings configuration object
        """
        self.settings = settings
        self.time_offsets: Dict[str, float] = {}
        self.last_sync_time = 0
        self.sync_lock = threading.Lock()
        self.ntp_client = ntplib.NTPClient()

        # Statistics
        self.total_syncs = 0
        self.successful_syncs = 0
        self.failed_syncs = 0

        # Perform initial synchronization
        self._sync_with_servers()

    def get_current_time(self) -> datetime:
        """
        Get current time with best available synchronization.

        Returns:
            datetime object in UTC timezone
        """
        # Use averaged offset from time servers
        current_time = time.time()

        if self.time_offsets:
            # Calculate median offset for robustness
            offsets = list(self.time_offsets.values())
            offsets.sort()
            n = len(offsets)
            if n % 2 == 0:
                median_offset = (offsets[n//2 - 1] + offsets[n//2]) / 2
            else:
                median_offset = offsets[n//2]

            adjusted_time = current_time + median_offset
        else:
            # Fall back to local time if no servers available
            adjusted_time = current_time

        return datetime.fromtimestamp(adjusted_time, timezone.utc)

    def get_time_server_verification(self) -> Dict[str, str]:
        """
        Get verification data from time servers.

        Returns:
            Dictionary with server verification information
        """
        # Refresh sync if needed
        if time.time() - self.last_sync_time > self.settings.update_interval:
            self._sync_with_servers()

        verification = {}
        current_time = time.time()

        for server, offset in self.time_offsets.items():
            server_time = current_time + offset
            verification[server] = {
                "timestamp": datetime.fromtimestamp(server_time, timezone.utc).isoformat(),
                "offset": offset,
                "last_sync": self.last_sync_time
            }

        return verification

    def verify_timestamp(self, timestamp_str: str, tolerance: float = 30.0) -> Dict[str, bool]:
        """
        Verify if a timestamp is within acceptable range of current time.

        Args:
            timestamp_str: ISO format timestamp string
            tolerance: Maximum seconds difference allowed

        Returns:
            Dictionary with verification results
        """
        try:
            given_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            current_time = self.get_current_time()

            time_diff = abs((current_time - given_time).total_seconds())

            return {
                "valid": time_diff <= tolerance,
                "time_difference": time_diff,
                "tolerance": tolerance,
                "current_time": current_time.isoformat(),
                "given_time": given_time.isoformat()
            }

        except (ValueError, TypeError) as e:
            return {
                "valid": False,
                "error": str(e)
            }

    def get_ntp_time(self, server: str) -> Optional[TimeServerResponse]:
        """
        Get time from specific NTP server.

        Args:
            server: NTP server hostname

        Returns:
            TimeServerResponse object or None if failed
        """
        try:
            response = self.ntp_client.request(server, timeout=self.settings.timeout)

            return TimeServerResponse(
                server=server,
                timestamp=response.tx_time,
                offset=response.offset,
                delay=response.delay,
                stratum=response.stratum,
                success=True
            )

        except Exception as e:
            return TimeServerResponse(
                server=server,
                timestamp=0,
                offset=0,
                delay=0,
                stratum=0,
                success=False,
                error=str(e)
            )

    def get_http_time(self, url: str = "http://worldtimeapi.org/api/timezone/UTC") -> Optional[TimeServerResponse]:
        """
        Get time from HTTP time API.

        Args:
            url: HTTP time service URL

        Returns:
            TimeServerResponse object or None if failed
        """
        try:
            response = requests.get(url, timeout=self.settings.timeout)
            response.raise_for_status()

            data = response.json()
            server_time = datetime.fromisoformat(data['datetime'].replace('Z', '+00:00'))
            timestamp = server_time.timestamp()
            local_time = time.time()
            offset = timestamp - local_time

            return TimeServerResponse(
                server=url,
                timestamp=timestamp,
                offset=offset,
                delay=0,  # HTTP doesn't provide delay measurement
                stratum=1,  # Assume stratum 1 for HTTP APIs
                success=True
            )

        except Exception as e:
            return TimeServerResponse(
                server=url,
                timestamp=0,
                offset=0,
                delay=0,
                stratum=0,
                success=False,
                error=str(e)
            )

    def sync_all_servers(self) -> List[TimeServerResponse]:
        """
        Synchronize with all configured time servers.

        Returns:
            List of TimeServerResponse objects
        """
        responses = []

        if not self.settings.time_servers:
            return responses

        # NTP servers
        for server in self.settings.time_servers:
            response = self.get_ntp_time(server)
            if response:
                responses.append(response)

        # HTTP time APIs
        http_apis = [
            "http://worldtimeapi.org/api/timezone/UTC",
            "https://timeapi.io/api/Time/current/zone?timeZone=UTC"
        ]

        for api_url in http_apis:
            response = self.get_http_time(api_url)
            if response:
                responses.append(response)

        return responses

    def get_statistics(self) -> Dict:
        """Get time provider statistics."""
        return {
            "total_syncs": self.total_syncs,
            "successful_syncs": self.successful_syncs,
            "failed_syncs": self.failed_syncs,
            "last_sync_time": self.last_sync_time,
            "active_servers": len(self.time_offsets),
            "time_offsets": self.time_offsets.copy(),
            "success_rate": self.successful_syncs / max(1, self.total_syncs)
        }

    def _sync_with_servers(self) -> None:
        """Internal method to synchronize with time servers."""
        if not self.sync_lock.acquire(blocking=False):
            return  # Already syncing

        try:
            self.total_syncs += 1
            responses = self.sync_all_servers()

            # Update offsets for successful responses
            new_offsets = {}
            successful_count = 0

            for response in responses:
                if response.success:
                    new_offsets[response.server] = response.offset
                    successful_count += 1

            if new_offsets:
                self.time_offsets = new_offsets
                self.successful_syncs += 1
                self.last_sync_time = time.time()
            else:
                self.failed_syncs += 1
                # Keep old offsets if all servers fail

        finally:
            self.sync_lock.release()

    def force_sync(self) -> bool:
        """
        Force immediate synchronization with time servers.

        Returns:
            True if sync was successful, False otherwise
        """
        old_count = self.successful_syncs
        self._sync_with_servers()
        return self.successful_syncs > old_count
