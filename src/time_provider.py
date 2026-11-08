"""
Time Provider module for QRLP.

Handles time synchronization with multiple time servers and provides
accurate timestamp verification for QR codes.
"""

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from statistics import median
from typing import TypedDict
from urllib.parse import urlsplit, urlunsplit

import ntplib
import requests

from .config import TimeSettings


class TimeServerObservation(TypedDict):
    timestamp: str
    offset: float
    last_sync: float


@dataclass
class TimeServerResponse:
    """Response from a time server."""
    server: str
    timestamp: float
    offset: float
    delay: float
    stratum: int
    success: bool
    error: str | None = None


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
        self.time_offsets: dict[str, float] = {}
        self.last_sync_time = 0.0
        self._last_sync_attempt: float | None = None
        self.sync_lock = threading.Lock()
        self.ntp_client = ntplib.NTPClient()

        # Statistics
        self.total_syncs = 0
        self.successful_syncs = 0
        self.failed_syncs = 0

    def get_current_time(self) -> datetime:
        """
        Get current time with best available synchronization.

        Returns:
            datetime object in UTC timezone
        """
        self._refresh_if_needed()
        with self.sync_lock:
            offsets = tuple(self.time_offsets.values())
        if offsets:
            offset = median(offsets)
        elif self.settings.local_fallback:
            offset = 0.0
        else:
            raise RuntimeError("No configured time source is available")
        return datetime.fromtimestamp(time.time() + offset, UTC)

    def get_time_server_verification(self) -> dict[str, TimeServerObservation]:
        """Return the latest successful observations from configured sources."""
        self._refresh_if_needed()
        with self.sync_lock:
            offsets = self.time_offsets.copy()
            last_sync = self.last_sync_time

        current_time = time.time()
        return {
            server: {
                "timestamp": datetime.fromtimestamp(current_time + offset, UTC).isoformat(),
                "offset": offset,
                "last_sync": last_sync,
            }
            for server, offset in offsets.items()
        }

    def _refresh_if_needed(self) -> None:
        if self.settings.time_servers:
            self._sync_with_servers(force=False)

    def verify_timestamp(self, timestamp_str: str, tolerance: float = 30.0) -> dict[str, str | bool | float]:
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

        except (AttributeError, RuntimeError, ValueError, TypeError) as e:
            return {
                "valid": False,
                "error": str(e)
            }

    def get_ntp_time(self, server: str) -> TimeServerResponse | None:
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

    def get_http_time(self, url: str = "https://worldtimeapi.org/api/timezone/UTC") -> TimeServerResponse | None:
        """
        Get time from HTTP time API.

        Args:
            url: HTTP time service URL

        Returns:
            TimeServerResponse object or None if failed
        """
        source = ""
        try:
            parsed = urlsplit(url)
            source = urlunsplit((parsed.scheme, parsed.netloc.rsplit("@", 1)[-1], parsed.path, "", ""))
            response = requests.get(url, timeout=self.settings.timeout)
            response.raise_for_status()

            data = response.json()
            server_time = datetime.fromisoformat(data['datetime'].replace('Z', '+00:00'))
            if server_time.tzinfo is None:
                raise ValueError("HTTP time source did not provide a UTC offset")
            timestamp = server_time.timestamp()
            local_time = time.time()
            offset = timestamp - local_time

            return TimeServerResponse(
                server=source,
                timestamp=timestamp,
                offset=offset,
                delay=0,  # HTTP doesn't provide delay measurement
                stratum=1,  # Assume stratum 1 for HTTP APIs
                success=True
            )

        except Exception as e:
            return TimeServerResponse(
                server=source,
                timestamp=0,
                offset=0,
                delay=0,
                stratum=0,
                success=False,
                error=str(e)
            )

    def sync_all_servers(self) -> list[TimeServerResponse]:
        """
        Synchronize with all configured time servers.

        Returns:
            List of TimeServerResponse objects
        """
        responses = []
        for server in dict.fromkeys(self.settings.time_servers):
            if server.startswith(("https://", "http://")):
                response = self.get_http_time(server)
            else:
                response = self.get_ntp_time(server)
            if response is not None:
                responses.append(response)
        return responses

    def get_statistics(self) -> dict:
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

    def _sync_with_servers(self, *, force: bool) -> bool:
        """Refresh once and throttle scheduled attempts, including failures."""
        if not self.sync_lock.acquire(blocking=False):
            return False

        try:
            if (
                not force and self._last_sync_attempt is not None
                and time.monotonic() - self._last_sync_attempt < self.settings.update_interval
            ):
                return False

            self.total_syncs += 1
            try:
                responses = self.sync_all_servers()
            finally:
                self._last_sync_attempt = time.monotonic()

            self.time_offsets = {
                response.server: response.offset
                for response in responses
                if response.success and isfinite(response.offset)
            }
            if self.time_offsets:
                self.successful_syncs += 1
                self.last_sync_time = time.time()
                return True
            self.failed_syncs += 1
            return False
        finally:
            self.sync_lock.release()

    def force_sync(self) -> bool:
        """Refresh immediately, returning whether any source succeeded."""
        return self._sync_with_servers(force=True)
